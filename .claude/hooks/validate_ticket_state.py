#!/usr/bin/env python3
"""PreToolUse hook - チケット状態の書き込み前検証

Write / Edit が tickets/active|done/*.md に対して行われる直前に発火し、
適用後の最終内容を再構成して不変条件を検証する。違反があれば deny で弾く。

検証内容:
- スキーマ（status enum / 必須キー / retry_counts 構造・上限）
- 状態遷移の正当性
- L2: リトライカウンタの単調性（減少禁止＝cap回避防止）

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


def collect_errors(new_content, prior_text):
    """検証エラーのリストを返す。frontmatter が無い場合は (None, 致命メッセージ)。"""
    new_fm = lib.parse_frontmatter(new_content)
    if new_fm is None:
        return None, "チケットに frontmatter がありません。テンプレートに従ってください。"

    errors = lib.validate_schema(new_fm)
    errors += lib.validate_retry_counts(new_fm)

    prior_fm = lib.parse_frontmatter(prior_text) if prior_text is not None else None
    prior_status = prior_fm.get("status") if prior_fm else None

    transition_error = lib.validate_transition(prior_status, new_fm.get("status"))
    if transition_error:
        errors.append(transition_error)

    # L2: カウンタ単調性（減少＝cap回避を禁止）
    errors += lib.validate_retry_monotonic(prior_fm, new_fm)
    return errors, None


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
        errors, fatal = collect_errors(new_content, prior_text)
    except Exception:
        allow()

    if fatal:
        deny(fatal)
    if errors:
        deny("チケット状態検証エラー:\n- " + "\n- ".join(errors))
    allow()


if __name__ == "__main__":
    main()
