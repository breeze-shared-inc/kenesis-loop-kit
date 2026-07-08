#!/usr/bin/env python3
"""PreToolUse hook - チケット状態の書き込み前検証

Write / Edit が tickets/active|done/*.md に対して行われる直前に発火し、
適用後の最終内容を再構成して不変条件を検証する。違反があれば deny で弾く。
人間の判断に委ねるべき操作は ask で人間確認に回す。

検証内容（deny）:
- スキーマ（status enum / 必須キー / retry_counts 構造・上限）
- 状態遷移の正当性

人間確認（ask）:
- L2: リトライカウンタの減少 — リトライ予算のリセットは人間の承認があれば
  正規の操作（改善ループ・blocked解消後の再挑戦など「新しい試行」の開始時）。
  承認されると record_metrics.py が retry_reset イベントを記録し、
  L3照合はリセットをエポックとして継続する
- in_progress 上限 — todo → investigation_done の着手時、他チケットの
  in_progress が上限（3件）に達していれば人間の承認を求める

遷移元（prior）の決定:
既存ファイルへの書き込みでは、hook管理のサイドカー tickets/.metrics_state.json
（record_metrics.py が最後に観測した status / retry_counts）が存在すれば
それを prior の正とし、無ければファイル内容から取る。これにより、
Bash・手編集でファイルだけが書き換わった（ドリフトした）場合も、
次の Write/Edit は「最後に検証された状態」からの遷移として検証される。
新規作成（ファイル不存在）では従来どおり prior 無しとして扱う。

fail-open: 内部エラー（IO・パース不能など）では allow。
fail-closed: 検知した違反のみ deny。
"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _ticket_lib as lib  # noqa: E402

ALLOW = object()  # reconstruct() が「対象外・素通り」を表す番兵


def allow():
    sys.exit(0)


def deny(reason):
    lib.emit_pretooluse_decision("deny", reason)


def ask(reason):
    lib.emit_pretooluse_decision("ask", reason)


def read_file(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def reconstruct(tool, tool_input, path):
    """適用後の最終内容と遷移前内容を再構成し (new_content, prior_text) を返す。
    対象外・再構成不能なら ALLOW を返す（素通り）。"""
    if tool == "Write":
        new_content = tool_input.get("content", "")
        prior_text = read_file(path) if os.path.exists(path) else None
        return new_content, prior_text

    if tool == "Edit":
        if not os.path.exists(path):
            return ALLOW  # Edit は存在しないファイルでは失敗する
        prior_text = read_file(path)
        old = tool_input.get("old_string", "")
        new = tool_input.get("new_string", "")
        if old == "" or old not in prior_text:
            return ALLOW  # 再構成不能。Edit 自身のエラーに委ねる
        if tool_input.get("replace_all"):
            return prior_text.replace(old, new), prior_text
        return prior_text.replace(old, new, 1), prior_text

    return ALLOW


def state_record(path, prior_fm, new_fm):
    """既存ファイルへの書き込み時、サイドカーの最終観測レコードを返す。
    無ければ None。ID は prior（壊れていれば new）の frontmatter から引く。"""
    ticket_id = None
    if prior_fm:
        ticket_id = prior_fm.get("id")
    if not ticket_id and new_fm:
        ticket_id = new_fm.get("id")
    if not ticket_id:
        return None
    record = lib.load_state(lib.tickets_dir_for(path)).get(ticket_id)
    return record if isinstance(record, dict) else None


def count_other_in_progress(path):
    """同じ tickets/active/ にある他チケットの in_progress 件数を返す。
    数えられなければ None（fail-open）。"""
    tickets_dir = lib.tickets_dir_for(path)
    if not tickets_dir:
        return None
    count = 0
    for p in glob.glob(os.path.join(tickets_dir, "active", "*.md")):
        if os.path.basename(p) == "_index.md":
            continue
        if os.path.abspath(p) == os.path.abspath(path):
            continue
        try:
            with open(p, encoding="utf-8") as f:
                fm = lib.parse_frontmatter(f.read())
        except Exception:
            continue
        if fm and fm.get("status") in lib.IN_PROGRESS_STATUSES:
            count += 1
    return count


def collect_errors(new_content, prior_text, path):
    """(deny_errors, ask_reasons, fatal) を返す。
    frontmatter が無い場合は fatal に致命メッセージが入る。"""
    new_fm = lib.parse_frontmatter(new_content)
    if new_fm is None:
        return [], [], "チケットに frontmatter がありません。テンプレートに従ってください。"

    errors = lib.validate_schema(new_fm)
    errors += lib.validate_retry_counts(new_fm)
    asks = []

    prior_fm = lib.parse_frontmatter(prior_text) if prior_text is not None else None
    prior_status = prior_fm.get("status") if prior_fm else None

    # 既存ファイルではサイドカーの最終観測値を prior の正とする
    # （Bash・手編集によるドリフトを「最後に検証された状態」から検証するため）
    record = state_record(path, prior_fm, new_fm) if prior_text is not None else None
    if record and record.get("status"):
        prior_status = record["status"]

    transition_error = lib.validate_transition(prior_status, new_fm.get("status"))
    if transition_error:
        errors.append(transition_error)

    # L2: カウンタ単調性。ファイル上の prior とサイドカーの最終観測値の
    # 要素ごとの最大値を下限とし、減少は人間確認（ask）に回す
    # （リトライ予算のリセット。人間が承認した場合のみ正規の操作となる）
    prior_for_monotonic = merge_retry_floor(prior_fm, record)
    decreases = lib.validate_retry_monotonic(prior_for_monotonic, new_fm)
    if decreases:
        asks.append(
            "リトライカウンタの減少（リトライ予算のリセット）:\n- "
            + "\n- ".join(decreases)
            + "\n改善ループやblocked解消後の再挑戦など「新しい試行」の開始として"
            "人間がリセットを意図した場合のみ承認してください。"
        )

    # in_progress 上限: todo → investigation_done の着手時にゲートする
    if prior_status == "todo" and new_fm.get("status") == "investigation_done":
        n = count_other_in_progress(path)
        if n is not None and n >= lib.IN_PROGRESS_LIMIT:
            asks.append(
                "in_progress 上限: 進行中チケットが既に %d 件あります（上限 %d）。"
                "既存チケットを完了または blocked にしてからの着手が原則です。"
                "上限を超えて新規着手することを人間が承認する場合のみ許可してください。"
                % (n, lib.IN_PROGRESS_LIMIT)
            )

    return errors, asks, None


def merge_retry_floor(prior_fm, record):
    """ファイル prior とサイドカー観測値から、キーごとに最大のカウンタ値を
    まとめた {"retry_counts": {...}} を返す。どちらも無ければ None。"""
    merged = {}
    for src in (prior_fm, record):
        rc = src.get("retry_counts") if isinstance(src, dict) else None
        if not isinstance(rc, dict):
            continue
        for key in lib.RETRY_CAPS:
            try:
                val = int(rc.get(key))
            except (TypeError, ValueError):
                continue
            if key not in merged or val > merged[key]:
                merged[key] = val
    return {"retry_counts": merged} if merged else None


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        allow()

    tool = data.get("tool_name", "")
    tool_input = data.get("tool_input") or {}
    path = tool_input.get("file_path", "")
    if not path or not lib.is_ticket(path):
        allow()

    try:
        result = reconstruct(tool, tool_input, path)
    except Exception:
        allow()
    if result is ALLOW:
        allow()

    new_content, prior_text = result
    try:
        errors, asks, fatal = collect_errors(new_content, prior_text, path)
    except Exception:
        allow()

    if fatal:
        deny(fatal)
    if errors:
        # deny が ask より優先（他の不変条件違反があるならリセット承認の余地はない）
        deny("チケット状態検証エラー:\n- " + "\n- ".join(errors))
    if asks:
        ask("人間の確認が必要です:\n" + "\n".join(asks))
    allow()


if __name__ == "__main__":
    main()
