#!/usr/bin/env python3
"""PostToolUse hook - ループイベントの記録

Write / Edit が tickets/active|done/*.md に対して実行された「後」に発火し、
チケットのステータスが前回観測値から変化していれば tickets/.metrics.jsonl に
1イベントを追記する。前回観測値は hook 管理のサイドカー
tickets/.metrics_state.json に保持する（LLMは触らない）。

サイドカーには status に加えて retry_counts も保持する。これは
validate_ticket_state.py（prior の正）と check_loop_integrity.py
（Write/Edit を経ないドリフトの検出）が「最後に検証された状態」として参照する。
status が変化しない Edit でも retry_counts が変わっていれば state を更新する。

retry_counts が前回観測値から減少していた場合（= validator の ask を人間が
承認したリトライ予算のリセット）は `type: "retry_reset"` イベントを追記する。
check_loop_integrity.py の L3 照合はこのイベントをエポックとして
「リセット時の値 + 以降の差し戻し回数」で照合を継続する。
同一の書き込みでステータス遷移とリセットが同時に起きた場合は
遷移イベント → リセットイベントの順で記録する（リセットは最終状態に適用）。

PostToolUse はツール実行後に動くため書き込みを妨げない。常に exit 0。
fail-open: いかなる内部エラーでも何もせず正常終了する。
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _ticket_lib as lib  # noqa: E402


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    if data.get("tool_name") not in ("Write", "Edit"):
        sys.exit(0)

    tool_input = data.get("tool_input") or {}
    path = tool_input.get("file_path", "")
    if not path or not lib.is_ticket(path):
        sys.exit(0)

    # tickets/ ディレクトリはチケットパスから導出する（cwd はフォールバック）
    tickets_dir = lib.tickets_dir_for(path)
    if not tickets_dir:
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

        # 最終観測サイドカーの読み込みは lib.load_state に集約
        # （非dictを {} に正規化 → 壊れたサイドカーは次の書き込みで自己修復）
        state = lib.load_state(tickets_dir)

        rc = retry_ints(fm.get("retry_counts"))
        now = datetime.datetime.now().isoformat(timespec="seconds")
        prev = state.get(ticket_id)
        prev_status = prev.get("status") if isinstance(prev, dict) else None
        prev_rc = prev.get("retry_counts") if isinstance(prev, dict) else None

        events = []
        if prev_status != status:
            events.append({
                "ts": now,
                "ticket": ticket_id,
                "type": "created" if prev_status is None else "transition",
                "from": prev_status,
                "to": status,
                "project": fm.get("project"),
                "priority": fm.get("priority"),
                "retry_counts": rc,
            })

        # 人間承認済みのリトライ予算リセット（減少はvalidatorのaskを通過している）。
        # L3照合のエポックとして記録する。遷移と同時なら遷移の後に置く
        if counters_decreased(prev_rc, rc):
            events.append({
                "ts": now,
                "ticket": ticket_id,
                "type": "retry_reset",
                "from_counts": prev_rc,
                "to_counts": rc,
                "project": fm.get("project"),
            })

        if events:
            with open(metrics_path, "a", encoding="utf-8") as f:
                for event in events:
                    f.write(json.dumps(event, ensure_ascii=False) + "\n")

        if events or (isinstance(prev, dict) and prev.get("retry_counts") != rc):
            state[ticket_id] = {"status": status, "ts": now, "retry_counts": rc}
            write_state(state_path, state)
    except Exception:
        pass

    sys.exit(0)


def counters_decreased(prev_rc, rc):
    """前回観測値からいずれかのカウンタが減少したか。"""
    if not isinstance(prev_rc, dict) or not isinstance(rc, dict):
        return False
    for key, before in prev_rc.items():
        try:
            if int(rc.get(key, before)) < int(before):
                return True
        except (TypeError, ValueError):
            continue
    return False


def retry_ints(rc):
    """retry_counts を {key: int} に正規化する（数値化できない値は落とす）。"""
    result = {}
    if isinstance(rc, dict):
        for key, val in rc.items():
            try:
                result[key] = int(val)
            except (TypeError, ValueError):
                continue
    return result


def write_state(state_path, state):
    tmp = state_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, state_path)


if __name__ == "__main__":
    main()
