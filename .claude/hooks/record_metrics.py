#!/usr/bin/env python3
"""PostToolUse hook - ループイベントの記録

Write / Edit が tickets/active|done/*.md に対して実行された「後」に発火し、
チケットのステータスが前回観測値から変化していれば tickets/.metrics.jsonl に
1イベントを追記する。前回観測値は hook 管理のサイドカー
tickets/.metrics_state.json に保持する（LLMは触らない）。

PostToolUse はツール実行後に動くため書き込みを妨げない。常に exit 0。
fail-open: いかなる内部エラーでも何もせず正常終了する。
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _ticket_lib as lib  # noqa: E402


def is_ticket(path):
    n = path.replace("\\", "/")
    if "/Templates/" in n:
        return False
    if os.path.basename(n) == "_index.md":
        return False
    if not n.endswith(".md"):
        return False
    return ("/tickets/active/" in n) or ("/tickets/done/" in n)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    if data.get("tool_name") not in ("Write", "Edit"):
        sys.exit(0)

    tool_input = data.get("tool_input") or {}
    path = tool_input.get("file_path", "")
    if not path or not is_ticket(path):
        sys.exit(0)

    cwd = data.get("cwd") or os.getcwd()
    tickets_dir = os.path.join(cwd, "tickets")
    metrics_path = os.path.join(tickets_dir, ".metrics.jsonl")
    state_path = os.path.join(tickets_dir, ".metrics_state.json")

    try:
        if not os.path.exists(path):
            sys.exit(0)
        with open(path, encoding="utf-8") as f:
            fm = lib.parse_frontmatter(f.read())
        if not fm:
            sys.exit(0)

        ticket_id = fm.get("id")
        status = fm.get("status")
        if not ticket_id or not status:
            sys.exit(0)

        state = {}
        if os.path.exists(state_path):
            try:
                with open(state_path, encoding="utf-8") as f:
                    state = json.load(f)
            except Exception:
                state = {}

        prev = state.get(ticket_id)
        prev_status = prev.get("status") if isinstance(prev, dict) else None
        if prev_status == status:
            sys.exit(0)  # ステータス未変化 → 記録しない

        now = datetime.datetime.now().isoformat(timespec="seconds")
        rc = fm.get("retry_counts")
        event = {
            "ts": now,
            "ticket": ticket_id,
            "type": "created" if prev_status is None else "transition",
            "from": prev_status,
            "to": status,
            "project": fm.get("project"),
            "priority": fm.get("priority"),
            "retry_counts": rc if isinstance(rc, dict) else {},
        }

        with open(metrics_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

        state[ticket_id] = {"status": status, "ts": now}
        tmp = state_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        os.replace(tmp, state_path)
    except Exception:
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
