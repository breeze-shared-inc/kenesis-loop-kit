"""Kenesis Loop Kit - 状態検証hook共有ライブラリ

stdlib のみ。外部依存なし。
呼び出し側は「内部エラー時は allow（fail-open）」「検知した違反のみ deny（fail-closed）」
という方針で利用する。
"""
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


def is_ticket(path):
    """path が状態検証対象の実チケット（tickets/active|done/*.md）か。
    テンプレート（/Templates/）とダッシュボード（_index.md）は対象外。"""
    n = path.replace("\\", "/")
    if "/Templates/" in n:
        return False
    if os.path.basename(n) == "_index.md":
        return False
    if not n.endswith(".md"):
        return False
    return ("/tickets/active/" in n) or ("/tickets/done/" in n)


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
                data[current_map][key.strip()] = _unquote(val)
            continue
        current_map = None
        if ":" not in raw:
            continue
        key, _, val = raw.partition(":")
        key = key.strip()
        val = val.strip()
        if val == "":
            data[key] = {}
            current_map = key
        else:
            data[key] = _unquote(val)
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
