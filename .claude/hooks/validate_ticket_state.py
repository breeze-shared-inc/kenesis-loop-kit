#!/usr/bin/env python3
"""PreToolUse hook - チケット状態の書き込み前検証

Write / Edit が tickets/active|done/*.md に対して行われる直前に発火し、
適用後の最終内容を再構成して不変条件を検証する。違反があれば deny で弾く。

検証内容:
- スキーマ（status enum / 必須キー / retry_counts 構造・上限）
- 状態遷移の正当性
- L2: リトライカウンタの単調性（減少禁止＝cap回避防止）

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
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _ticket_lib as lib  # noqa: E402

ALLOW = object()  # reconstruct() が「対象外・素通り」を表す番兵


def allow():
    sys.exit(0)


def deny(reason):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def is_ticket(path):
    n = path.replace("\\", "/")
    if "/Templates/" in n:
        return False
    if os.path.basename(n) == "_index.md":
        return False
    if not n.endswith(".md"):
        return False
    return ("/tickets/active/" in n) or ("/tickets/done/" in n)


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


def collect_errors(new_content, prior_text, path):
    """検証エラーのリストを返す。frontmatter が無い場合は (None, 致命メッセージ)。"""
    new_fm = lib.parse_frontmatter(new_content)
    if new_fm is None:
        return None, "チケットに frontmatter がありません。テンプレートに従ってください。"

    errors = lib.validate_schema(new_fm)
    errors += lib.validate_retry_counts(new_fm)

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

    # L2: カウンタ単調性（減少＝cap回避を禁止）。
    # ファイル上の prior とサイドカーの最終観測値の要素ごとの最大値を下限とする
    prior_for_monotonic = merge_retry_floor(prior_fm, record)
    errors += lib.validate_retry_monotonic(prior_for_monotonic, new_fm)
    return errors, None


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
    if not path or not is_ticket(path):
        allow()

    try:
        result = reconstruct(tool, tool_input, path)
    except Exception:
        allow()
    if result is ALLOW:
        allow()

    new_content, prior_text = result
    try:
        errors, fatal = collect_errors(new_content, prior_text, path)
    except Exception:
        allow()

    if fatal:
        deny(fatal)
    if errors:
        deny("チケット状態検証エラー:\n- " + "\n- ".join(errors))
    allow()


if __name__ == "__main__":
    main()
