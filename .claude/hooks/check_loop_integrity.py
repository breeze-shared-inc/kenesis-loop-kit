#!/usr/bin/env python3
"""Stop hook - ループ整合性チェック

orchestrator（メインエージェント）が応答を終えるたびに発火し、
tickets/active/ の各チケットが不変条件を満たしているか検査する。
不整合があれば decision=block で継続を強制し、終了前の修正を促す。

PreToolUse が Write/Edit を防いでも、Bash の mv や手編集で混入したドリフトは
この Stop hook が最後の砦として捕捉する。

ドリフト検知:
hook管理のサイドカー tickets/.metrics_state.json（record_metrics.py が
最後に観測した status / retry_counts）と各チケットの実体を突き合わせ、
Write/Edit を経ない書き換え（Bashリダイレクト・インタプリタ・手編集）を検出する。
検出時は block し、orchestrator に Edit ツールでの再適用
（観測値へ戻す、または観測値からの正当な遷移として適用し直す）を強制する。
サイドカー側を直接書き換えて解消してはならない。

fail-open: 内部エラーでは継続を許可（exit 0）。サイドカーに記録が無い
チケット（hook導入前の旧チケット等）はドリフト照合をスキップする。
無限ループ防止: stop_hook_active が真なら何もしない。
"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _ticket_lib as lib  # noqa: E402


def blocker_section_filled(text):
    """## ブロッカー セクションに実体（コメント以外）があるか。"""
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip().startswith("## ブロッカー"):
            start = i + 1
            break
    if start is None:
        return False
    for line in lines[start:]:
        s = line.strip()
        if s.startswith("## "):
            break  # 次セクション
        if not s or s.startswith("<!--"):
            continue
        return True
    return False


def check_body_table_sync(fm, text):
    """ハイブリッド同期: frontmatter retry_counts と本文表の一致を検証。"""
    errors = []
    _, body = lib.split_frontmatter(text)
    body_table = lib.parse_body_retry_table(body or "")
    rc = fm.get("retry_counts") if isinstance(fm.get("retry_counts"), dict) else {}
    for key in lib.RETRY_CAPS:
        if key in body_table and key in rc:
            try:
                if int(rc[key]) != int(body_table[key]):
                    errors.append(
                        "retry_counts.%s=%s が本文リトライカウンタ表(%s)と不一致です"
                        % (key, rc[key], body_table[key])
                    )
            except (TypeError, ValueError):
                pass
    return errors


def load_metrics_by_ticket(metrics_path):
    """.metrics.jsonl を {ticket_id: [events...(ts昇順)]} に読み込む。"""
    by_ticket = {}
    if not os.path.exists(metrics_path):
        return by_ticket
    try:
        with open(metrics_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except Exception:
                    continue
                by_ticket.setdefault(ev.get("ticket"), []).append(ev)
    except Exception:
        return {}
    for evs in by_ticket.values():
        evs.sort(key=lambda e: e.get("ts", ""))
    return by_ticket


def check_state_drift(fm, record):
    """サイドカーの最終観測値との突き合わせ。Write/Edit を経ない
    書き換え（Bash・手編集）の痕跡を文字列リストで返す。
    record が無い（hook導入前の旧チケット等）場合は照合しない（fail-open）。"""
    errors = []
    if not isinstance(record, dict):
        return errors

    observed = record.get("status")
    current = fm.get("status")
    if observed and current and observed != current:
        errors.append(
            "Write/Edit を経ないステータス変更を検出: 最後に検証された status は "
            "'%s'（現在 '%s'）。Edit ツールで '%s' へ戻すか、意図した変更なら "
            "'%s' からの正当な遷移として Edit で適用し直してください"
            "（tickets/.metrics_state.json は直接編集しないこと）"
            % (observed, current, observed, observed)
        )

    observed_rc = record.get("retry_counts")
    current_rc = fm.get("retry_counts")
    if isinstance(observed_rc, dict) and isinstance(current_rc, dict):
        for key in lib.RETRY_CAPS:
            try:
                before = int(observed_rc[key])
                after = int(current_rc[key])
            except (TypeError, ValueError, KeyError):
                continue
            if after < before:
                errors.append(
                    "Write/Edit を経ない retry_counts.%s の減少を検出: "
                    "最後に検証された値は %d（現在 %d）。Edit ツールで %d 以上へ"
                    "戻してください（カウンタは減らせません）"
                    % (key, before, after, before)
                )
    return errors


def check_ticket(path, events_by_ticket, state):
    """1チケットの不整合を文字列リストで返す。"""
    base = os.path.basename(path)
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except Exception:
        return []  # 読めないものは fail-open

    fm = lib.parse_frontmatter(text)
    if fm is None:
        return ["%s: frontmatter がありません" % base]

    errors = lib.validate_schema(fm) + lib.validate_retry_counts(fm)

    if fm.get("status") == "blocked" and not blocker_section_filled(text):
        errors.append("status=blocked だが ブロッカー セクションが空です")

    errors += check_body_table_sync(fm, text)

    # ドリフト検知: サイドカーの最終観測値との突き合わせ
    errors += check_state_drift(fm, state.get(fm.get("id")))

    # L3: 差し戻し履歴とカウンタの照合（イベントログがあれば）
    events = events_by_ticket.get(fm.get("id"), [])
    errors += lib.reconcile_rollbacks(fm.get("retry_counts"), events)

    return ["%s: %s" % (base, e) for e in errors]


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    if data.get("stop_hook_active"):
        sys.exit(0)  # 直前が Stop hook 由来の継続なら再ブロックしない

    cwd = data.get("cwd") or os.getcwd()
    active_dir = os.path.join(cwd, "tickets", "active")
    if not os.path.isdir(active_dir):
        sys.exit(0)

    events_by_ticket = load_metrics_by_ticket(
        os.path.join(cwd, "tickets", ".metrics.jsonl"))
    state = lib.load_state(os.path.join(cwd, "tickets"))

    problems = []
    for path in sorted(glob.glob(os.path.join(active_dir, "*.md"))):
        if os.path.basename(path) == "_index.md":
            continue
        problems.extend(check_ticket(path, events_by_ticket, state))

    if problems:
        reason = (
            "ループ整合性チェックで不整合を検出しました。"
            "終了前に以下を修正してください:\n- " + "\n- ".join(problems)
        )
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "Stop",
                "decision": "block",
                "reason": reason,
            }
        }))
    sys.exit(0)


if __name__ == "__main__":
    main()
