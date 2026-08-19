"""Kenesis Loop Kit - 状態検証hook共有ライブラリ

stdlib のみ。外部依存なし。
呼び出し側は「内部エラー時は allow（fail-open）」「検知した違反のみ deny（fail-closed）」
という方針で利用する。
"""
import fnmatch
import hashlib
import json
import os
import sys

VALID_STATUS = {
    "todo",
    "investigation_done",
    "design_done",
    "implementation_done",
    "test_passed",
    "done",
    "blocked",
    "cancelled",
}

REQUIRED_KEYS = [
    "id",
    "title",
    "status",
    "priority",
    "type",
    "created",
    "updated",
    "project",
    "retry_counts",
]

# 差し戻し種別ごとの上限（orchestrator.md「リトライカウンタ管理」と一致させること）
RETRY_CAPS = {
    "tester_to_implementer": 3,
    "reviewer_to_implementer": 2,
    "reviewer_to_investigator": 1,
}

# in_progress（着手済み）とみなす status と同時進行の上限
# （orchestrator.md「in_progress上限」と一致させること。blocked / todo は数えない）
IN_PROGRESS_STATUSES = {
    "investigation_done",
    "design_done",
    "implementation_done",
    "test_passed",
}
IN_PROGRESS_LIMIT = 3

# 本文「リトライカウンタ」表のラベル -> frontmatterキー
RETRY_LABELS = {
    "tester → implementer": "tester_to_implementer",
    "reviewer → implementer": "reviewer_to_implementer",
    "reviewer → investigator": "reviewer_to_investigator",
}

# 前進・差し戻し・改善ループの遷移。
# 「同一status据え置き」「any -> blocked」「any -> cancelled」はコード側で別途許可する。
LEGAL_TRANSITIONS = {
    "todo": {"investigation_done"},
    "investigation_done": {"design_done"},
    "design_done": {"implementation_done"},
    # 差し戻し: tester Quality Gate fail -> design_done（test_passedは合格時のみ付与されるため、
    # tester差し戻しは implementation_done 起点になる）
    "implementation_done": {"test_passed", "design_done"},
    # 差し戻し: reviewer reject(実装起因) -> design_done、reviewer reject(設計起因) -> todo
    "test_passed": {"done", "design_done", "todo"},
    # 改善ループ: done から再開（architect -> investigation_done、investigator -> todo）
    # ロールバック: done -> implementation_done（revert実装をtesterから再開。.claude/commands/rollback.md）
    "done": {"investigation_done", "todo", "implementation_done"},
    # blocked からの再開（CLAUDE.md ステータス定義表の「遷移先 any」に対応。
    # done 段階で blocked になったチケットの復帰も許可する）
    "blocked": {
        "todo",
        "investigation_done",
        "design_done",
        "implementation_done",
        "test_passed",
        "done",
    },
    "cancelled": set(),
}


def tickets_dir_for(ticket_path):
    """チケットファイルのパスから tickets/ ディレクトリを導出する。
    .../tickets/active/X.md → .../tickets。導出できなければ None。"""
    n = ticket_path.replace("\\", "/")
    for marker in ("/tickets/active/", "/tickets/done/"):
        idx = n.rfind(marker)
        if idx != -1:
            return n[:idx] + "/tickets"
    return None


def _normalize_path(path):
    """判定用のパス正規化（cwd 非依存の純字句正規化）。

    バックスラッシュ区切りをスラッシュへ寄せ、`.` / `..` / 重複スラッシュを畳む。
    相対形は相対のまま返す（os.path.abspath は使わない = プロセスの作業
    ディレクトリに依存させないため。docs/designs/KLK-012.md §3 D1）。
    """
    n = os.path.normpath(path.replace("\\", "/"))
    return n.replace("\\", "/")  # Windows の normpath が '/' を '\' へ戻すため


def _under_dir(n, marker):
    """正規化済みパス n が marker（例 "tickets/active/"）配下を指すか。
    先頭一致（相対形）と '/' 直後の一致（絶対形・サブパス）の両方を認める
    = パスコンポーネント境界での一致。'mytickets/active/X.md' は一致しない。"""
    return n.startswith(marker) or ("/" + marker) in n


def is_ticket(path):
    """path が状態検証対象の実チケット（tickets/active|done/*.md）か。

    テンプレート（/Templates/）とダッシュボード（_index.md）は対象外。
    パスは _normalize_path で正規化したうえで、絶対形と相対形（先頭スラッシュ
    無し）の双方を受け付ける（KLK-012 AC1）。

    guard_bash_writes.py 側の保護対象判定（_is_guarded_path / is_guarded_token）
    とは目的が異なるため基準は統一していない（KLK-010 D2。KLK-020でKLK-010 D2の
    根拠3点を再評価し「意図的な不統一を維持する」と確定した。根拠は
    docs/designs/KLK-020.md §3 D2を参照）。相対形のチケットパスでは
    tickets_dir_for が None を返すため、
    サイドカー由来の prior と in_progress ゲートは fail-open で効かない
    （KLK-012 §3 D3・§6 R10）。判定は str を前提とし、型の正規化は各 hook の
    main() 側で行う（KLK-012 §3 D5）。
    """
    n = _normalize_path(path)
    if "/Templates/" in n:
        return False
    if os.path.basename(n) == "_index.md":
        return False
    if not n.endswith(".md"):
        return False
    return _under_dir(n, "tickets/active/") or _under_dir(n, "tickets/done/")


def spec_path_for(cwd):
    """cwd 直下の docs/SPEC.md のパスを返す（cwd が非str/空なら None）。
    ネストした SPEC.md は対象外（D3）。"""
    if not isinstance(cwd, str) or not cwd:
        return None
    return os.path.join(cwd, "docs", "SPEC.md")


def spec_state_path(cwd):
    """SPEC.md ドリフト検知用サイドカー docs/.spec_state.json のパスを返す
    （cwd が非str/空なら None）。hook（record_metrics.py）が自動生成する。
    LLM・エージェントは直接編集しない。"""
    if not isinstance(cwd, str) or not cwd:
        return None
    return os.path.join(cwd, "docs", ".spec_state.json")


def is_spec_basename(name):
    """basename が大小を区別せず 'SPEC.md' と一致するか（KLK-020: is_spec /
    _is_guarded_path / _is_guarded_path_component / is_project_spec の
    SPEC.md 判定を一本化する単一の正規化ポイント）。glob パターン照合版は
    is_spec_basename_fnmatch（KLK-032）。"""
    return isinstance(name, str) and name.upper() == "SPEC.MD"


def is_spec_basename_fnmatch(pattern):
    """glob パターン pattern が 'SPEC.md' に fnmatch するか（大小の扱いは
    下記2項の和集合。KLK-032 で新設し KLK-033 で和集合形へ拡張した）。

    ① fnmatch.fnmatchcase("SPEC.md", pattern)
       bash が実ファイル docs/SPEC.md に対して行う照合と同一意味論
       （大小をそのまま比較する）。取りこぼすと「bash では一致するのに
       hook は検出しない」= allow 方向（危険）になるため、健全性の要。
    ② fnmatch.fnmatchcase("SPEC.MD", pattern.upper())
       KLK-020／KLK-032 が確定した「SPEC.md 判定は大小を区別しない」
       方針による意図的な過大近似（deny 方向=安全側）。

    ①を欠くと `.upper()` が `[!s]` を `[!S]` へ変える非単調な操作になり、
    `[!s]PEC.md` が False になる（KLK-032 レビュー Medium 3-1）。KLK-033 で
    SHELL_EXPAND_PATHISH_RE に `!` を追加したことでこの経路は到達可能に
    なったため、①②の和集合が必須である（docs/designs/KLK-033.md §3 D2）。

    残余の限界: ②は pattern 全体を大文字化するため、ブラケット表現を含む
    パターンについては 'SPEC.md' 以外の大小変種（'Spec.md' 等）を対象と
    する一致を取りこぼしうる（例: '[!s]pec.md' は False。正規形
    'SPEC.md' には bash でも一致しない）。全大小変種に対する完全閉包は
    スコープ外（docs/designs/KLK-033.md §3 D2・§6）。

    注意: リテラル文字を1文字も含まないパターン（'*'・'**' 等）にも True を
    返す。呼び出し側の KLK-031 ゲート（has_literal_char。リテラル文字0の
    成分では GUARDED_FILENAME を照合対象に加えない）が先に除外する前提で
    あり、本関数は孤立ワイルドカードの扱いに関知しない（レイヤーを分離）。
    """
    if not isinstance(pattern, str):
        return False
    return (fnmatch.fnmatchcase("SPEC.md", pattern)
            or fnmatch.fnmatchcase("SPEC.MD", pattern.upper()))


def is_project_spec(path, cwd):
    """path が cwd 直下の docs/SPEC.md と同一ファイルを指すか。

    guard_spec_writes.is_spec（basename一致・ネスト許容）とは意図的に基準を
    分ける（D3。KLK-010 D2と同型の判断）。絶対形は cwd 直下の docs/SPEC.md と
    正規化して比較し、相対形は "docs/SPEC.md" という字句そのものだけを認める
    （is_ticket と同様、相対形は cwd 非依存の純字句判定にとどめる）。
    basename部分は is_spec_basename 経由で大小を区別しない
    （KLK-020 D1）が、ディレクトリ部分（"docs"）の比較は大小を区別した
    まま維持する（D1のスコープ限定）。
    ネストした SPEC.md（docs/foo/SPEC.md 等）はいずれの形でも一致しない
    （KLK-016 D3）。
    """
    if not isinstance(path, str) or not path:
        return False
    target = spec_path_for(cwd)
    if not target:
        return False
    n = _normalize_path(path)
    n_dir, _, n_base = n.rpartition("/")
    if not is_spec_basename(n_base):
        return False
    target_dir = _normalize_path(target).rpartition("/")[0]
    return n_dir == target_dir or n_dir == "docs"


def load_spec_state(cwd):
    """docs/.spec_state.json を読む。読めない・無い・dict でない場合は None
    （fail-open）。"""
    path = spec_state_path(cwd)
    if not path:
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def sha256_file(path):
    """path の内容（バイト列）の sha256 ハッシュ(hex)を返す。読めない場合は
    None（fail-open）。record_metrics.py（記録側）と check_loop_integrity.py
    （検知側）が同一アルゴリズムを共有するためここへ集約する。"""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def emit_pretooluse_decision(decision, reason):
    """PreToolUse hook の permissionDecision（deny / ask）を出力して exit 0。
    出力フォーマットは Claude Code の PreToolUse 契約（hookSpecificOutput に
    ネスト）。allow は出力せず素通りさせる（呼び出し側で sys.exit(0)）。"""
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def load_state(tickets_dir):
    """hook管理のサイドカー tickets/.metrics_state.json を読む。
    読めない・無い場合は {}（fail-open）。"""
    if not tickets_dir:
        return {}
    path = os.path.join(tickets_dir, ".metrics_state.json")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def load_events(path):
    """`.metrics.jsonl`（record_metrics.py が1行1イベントで追記）を読み、
    イベント dict のリストを返す。空行・不正行はスキップ。ファイルが無い・
    読めない場合は [] （fail-open）。並び順は記録順（ts昇順とは限らない）。"""
    events = []
    if not os.path.exists(path):
        return events
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        return []
    return events


def group_events_by_ticket(events):
    """イベント列を {ticket_id: [events...]} にまとめ、各リストを ts 昇順に
    ソートして返す。"""
    by_ticket = {}
    for ev in events:
        by_ticket.setdefault(ev.get("ticket"), []).append(ev)
    for evs in by_ticket.values():
        evs.sort(key=lambda e: e.get("ts", ""))
    return by_ticket


def _strip_comment(value):
    """クォート外の `#` 以降をコメントとして除去する（YAML のコメント規則の近似）。

    `#` がコメントを開始するのは「値の先頭」または「空白（スペース/タブ）の
    直後」に現れ、かつクォートの外側にある場合のみ。クォート内の `#`
    （`title: "issue #123 fix"`）と、空白を伴わない `#`（`title: C#`）は保持する。
    クォートが閉じていない値では除去を行わない（除去しすぎ = 値の破壊を避ける
    安全側。走査がクォート状態のまま終端に達するので分岐は不要）。
    """
    quote = None
    for i, ch in enumerate(value):
        if quote is not None:
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
        elif ch == "#" and (i == 0 or value[i - 1] in (" ", "\t")):
            return value[:i].rstrip()
    return value


def _unquote(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def split_frontmatter(text):
    """(frontmatter_text, body_text) を返す。frontmatterが無ければ (None, text)。"""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1:])
    return None, text


def parse_frontmatter(text):
    """YAMLサブセットの簡易パーサ。retry_counts はネストした dict になる。
    frontmatterが無ければ None。"""
    fm_text, _ = split_frontmatter(text)
    if fm_text is None:
        return None
    data = {}
    current_map = None
    for raw in fm_text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw[0] in (" ", "\t"):  # 直前のマッピングキー配下
            if current_map is not None and ":" in raw:
                key, _, val = raw.strip().partition(":")
                data[current_map][key.strip()] = _unquote(
                    _strip_comment(val.strip()))
            continue
        if current_map is not None and not data[current_map]:
            data[current_map] = None  # 子行が1件も来なかった＝スカラーの空値（KLK-028 AC1）
        current_map = None
        if ":" not in raw:
            continue
        key, _, val = raw.partition(":")
        key = key.strip()
        val = val.strip()
        val = _strip_comment(val)
        if val == "":
            data[key] = {}
            current_map = key
        else:
            data[key] = _unquote(val)
    if current_map is not None and not data[current_map]:
        data[current_map] = None
    return data


def validate_schema(fm):
    """必須キーの存在と status enum を検証。エラー文字列のリストを返す。"""
    errors = []
    for key in REQUIRED_KEYS:
        if key not in fm:
            errors.append("必須キー '%s' が frontmatter に存在しません" % key)
    status = fm.get("status")
    if status is not None and status not in VALID_STATUS:
        errors.append(
            "status '%s' は不正です。許可: %s"
            % (status, ", ".join(sorted(VALID_STATUS)))
        )
    return errors


def validate_retry_counts(fm):
    """retry_counts の構造・型・上限を検証。エラー文字列のリストを返す。"""
    errors = []
    rc = fm.get("retry_counts")
    if not isinstance(rc, dict):
        errors.append("retry_counts がマッピングとして存在しません")
        return errors
    for key, cap in RETRY_CAPS.items():
        if key not in rc:
            errors.append("retry_counts.%s が存在しません" % key)
            continue
        try:
            n = int(rc[key])
        except (TypeError, ValueError):
            errors.append("retry_counts.%s が整数ではありません: %r" % (key, rc[key]))
            continue
        if n < 0:
            errors.append("retry_counts.%s が負の値です: %d" % (key, n))
        elif n > cap:
            errors.append(
                "retry_counts.%s=%d が上限 %d を超えています。"
                "上限到達後の差し戻しではカウンタを増やさず、"
                "status を blocked にして人間へ報告してください"
                "（リトライ上限規約）" % (key, n, cap)
            )
    return errors


def validate_transition(prior_status, new_status):
    """状態遷移の正当性を検証。エラー文字列、または None を返す。"""
    if new_status is None:
        return None  # status欠落は schema 側で検出
    if prior_status is None:  # 新規作成
        if new_status != "todo":
            return (
                "新規チケットの初期 status は todo である必要があります"
                "（指定: %s）" % new_status
            )
        return None
    if new_status == prior_status:
        return None  # 据え置き（ログ追記等）は常に許可
    if new_status == "blocked":
        return None  # any -> blocked
    if new_status == "cancelled":
        return None  # any -> cancelled（クローズ）
    if new_status in LEGAL_TRANSITIONS.get(prior_status, set()):
        return None
    return (
        "不正な状態遷移: %s → %s。"
        "許可される遷移のみ実行してください"
        "（CLAUDE.md / orchestrator.md 参照）" % (prior_status, new_status)
    )


def parse_body_retry_table(body):
    """本文「リトライカウンタ」表から {frontmatterキー: int} を抽出（部分的でも返す）。"""
    found = {}
    for line in body.splitlines():
        if "|" not in line:
            continue
        for label, key in RETRY_LABELS.items():
            if label in line:
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                if len(cells) >= 2:
                    try:
                        found[key] = int(cells[1])
                    except ValueError:
                        pass
    return found


def validate_retry_monotonic(prior_fm, new_fm):
    """L2: リトライカウンタの減少を検出する（単調非減少）。
    エラー文字列のリストを返す。prior が無い（新規作成）場合は検証不要。
    呼び出し側（validate_ticket_state.py）は減少を deny ではなく ask に変換する
    — 減少＝リトライ予算のリセットは人間の承認があれば正規の操作
    （承認後は record_metrics.py が retry_reset イベントを記録する）。"""
    errors = []
    if not prior_fm:
        return errors
    prior_rc = prior_fm.get("retry_counts")
    new_rc = new_fm.get("retry_counts")
    if not isinstance(prior_rc, dict) or not isinstance(new_rc, dict):
        return errors
    for key in RETRY_CAPS:
        if key in prior_rc and key in new_rc:
            try:
                before = int(prior_rc[key])
                after = int(new_rc[key])
            except (TypeError, ValueError):
                continue
            if after < before:
                errors.append(
                    "retry_counts.%s が減少しています: %d → %d"
                    "（カウンタは減らせません）" % (key, before, after)
                )
    return errors


def _count_transitions(events, from_status, to_status):
    return sum(
        1 for e in events
        if e.get("from") == from_status and e.get("to") == to_status
    )


def _retry_ints(rc):
    """retry_counts から (tti, rti, rtv) を返す。型不正なら None。"""
    if not isinstance(rc, dict):
        return None
    try:
        return (
            int(rc.get("tester_to_implementer")),
            int(rc.get("reviewer_to_implementer")),
            int(rc.get("reviewer_to_investigator")),
        )
    except (TypeError, ValueError):
        return None


def _last_reset_epoch(events):
    """最後の retry_reset イベントを探し (基準カウンタdict, それ以降のイベント列) を
    返す。リセットが無ければ ({}, events)。リセット記録が壊れていれば None（照合不能）。"""
    for i in range(len(events) - 1, -1, -1):
        if events[i].get("type") == "retry_reset":
            to_counts = events[i].get("to_counts")
            if not isinstance(to_counts, dict):
                return None
            return to_counts, events[i + 1:]
    return {}, events


def reconcile_rollbacks(retry_counts, events):
    """L3: 差し戻し履歴（events）と現在の retry_counts の整合を照合する。

    events は当該チケットの ts 昇順イベント列。差し戻し3種は遷移元で
    区別できるため、カテゴリ個別に照合する:
        implementation_done→design_done の回数 == tester_to_implementer
        test_passed→design_done         の回数 == reviewer_to_implementer
        test_passed→todo                の回数 == reviewer_to_investigator

    人間承認によるリトライ予算のリセット（retry_reset イベント）があれば、
    最後のリセットをエポックとし「リセット時の値 + それ以降の差し戻し回数」と
    照合する。

    履歴が created（from=None）で始まっていなければ全履歴が無いとみなし、
    照合不能として [] を返す（fail-open）。型不正も照合せず [] を返す
    （型は validate_retry_counts 側で検出）。エラー文字列のリストを返す。
    """
    if not events or events[0].get("from") is not None:
        return []
    vals = _retry_ints(retry_counts)
    if vals is None:
        return []
    epoch = _last_reset_epoch(events)
    if epoch is None:
        return []  # リセット記録が壊れている → 照合不能（fail-open）
    baseline, window = epoch

    tti, rti, rtv = vals
    checks = [
        ("implementation_done", "design_done", tti, "tester_to_implementer"),
        ("test_passed", "design_done", rti, "reviewer_to_implementer"),
        ("test_passed", "todo", rtv, "reviewer_to_investigator"),
    ]
    errors = []
    for frm, to, counter, key in checks:
        try:
            base = int(baseline.get(key, 0))
        except (TypeError, ValueError):
            continue  # このカテゴリのみ照合不能
        n = _count_transitions(window, frm, to)
        if counter != base + n:
            suffix = "（最終リセット時 %d + 以降の差し戻し %d回）" % (base, n) \
                if baseline else "（増やし忘れ/誤計上の疑い）"
            errors.append(
                "%s→%s の差し戻しに対し %s=%d が不一致・期待値 %d %s"
                % (frm, to, key, counter, base + n, suffix)
            )
    return errors


def read_hook_payload(stream=None):
    """hook の stdin から JSON payload を dict として読む。

    JSON として不正な場合と、妥当な JSON だが dict でない場合（配列・文字列・
    数値・null）の両方で None を返す。呼び出し側は None を fail-open として
    扱う（PreToolUse 系は allow、PostToolUse / Stop 系は exit 0）。
    stream はテスト用（未指定なら sys.stdin）。
    """
    try:
        data = json.load(sys.stdin if stream is None else stream)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def as_dict(value):
    """dict ならそのまま、それ以外（None・配列・スカラー）は空 dict を返す。
    hook 入口で tool_input 等の型を正規化するために使う。"""
    return value if isinstance(value, dict) else {}
