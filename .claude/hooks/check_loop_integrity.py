#!/usr/bin/env python3
"""Stop hook - ループ整合性チェック

orchestrator（メインエージェント）が応答を終えるたびに発火し、
tickets/active/ の各チケットが不変条件を満たしているか検査する。
tickets/done/ はドリフト検知のみ実施する（アーカイブ済み・hook導入前の
旧チケットを誤検知しないため。done/ のチケットは正規フローでは
状態が変化しない — 改善ループ/ロールバックは active/ へ移動してから編集する）。
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

SPEC.mdドリフト検知（KLK-016）:
hook管理のサイドカー docs/.spec_state.json（record_metrics.py が最後に観測
した sha256ハッシュ）と docs/SPEC.md（プロジェクト直下のみ。ネストした
SPEC.md は対象外）の内容を突き合わせ、Write/Edit を経ない書き換えを検出
する。SPEC.md が存在しない、またはサイドカーに記録が無い（hook導入前・
SPEC.md作成直後で一度もWrite/Editを経ていない等）場合は照合しない
（fail-open）。

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
                    "戻してください（正規のリトライ予算リセットは Edit + "
                    "人間承認で行う）" % (key, before, after, before)
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


def check_done_ticket_drift(path, state):
    """done/ のチケットはドリフト検知のみ（全量検査は active/ 限定）。"""
    try:
        with open(path, encoding="utf-8") as f:
            fm = lib.parse_frontmatter(f.read())
    except Exception:
        return []
    if not fm:
        return []
    errors = check_state_drift(fm, state.get(fm.get("id")))
    return ["%s: %s" % (os.path.basename(path), e) for e in errors]


def check_spec_drift(cwd):
    """docs/SPEC.md（プロジェクト直下）のハッシュドリフトを検知する（KLK-016）。
    SPEC.md が存在しない、またはサイドカーに記録が無い場合は照合しない
    （fail-open。AC3）。"""
    spec_path = lib.spec_path_for(cwd)
    if not spec_path or not os.path.isfile(spec_path):
        return []
    record = lib.load_spec_state(cwd)
    if not isinstance(record, dict):
        return []
    observed = record.get("hash")
    if not observed:
        return []
    current = lib.sha256_file(spec_path)
    if current is None:
        return []
    if current != observed:
        return [
            "docs/SPEC.md: Write/Edit を経ない変更を検出しました"
            "（最後に検証されたハッシュと現在の内容が不一致）。"
            "正規経路（Write/Edit ツール・人間の diff 承認）で変更を"
            "再適用するか、意図しない変更なら元の内容へ戻してください"
            "（docs/.spec_state.json は直接編集しないこと）"
        ]
    return []


def main():
    # 入力型の正規化は hook 境界（main）で行う（KLK-012 §3 D5）。
    # 非 dict の payload・非 str の cwd はいずれも fail-open
    data = lib.read_hook_payload()
    if data is None:
        sys.exit(0)

    if data.get("stop_hook_active"):
        sys.exit(0)  # 直前が Stop hook 由来の継続なら再ブロックしない

    cwd = data.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        cwd = os.getcwd()
    active_dir = os.path.join(cwd, "tickets", "active")
    done_dir = os.path.join(cwd, "tickets", "done")
    if not os.path.isdir(active_dir):
        sys.exit(0)

    events_by_ticket = lib.group_events_by_ticket(
        lib.load_events(os.path.join(cwd, "tickets", ".metrics.jsonl")))
    state = lib.load_state(os.path.join(cwd, "tickets"))

    problems = []
    for path in sorted(glob.glob(os.path.join(active_dir, "*.md"))):
        if os.path.basename(path) == "_index.md":
            continue
        problems.extend(check_ticket(path, events_by_ticket, state))
    for path in sorted(glob.glob(os.path.join(done_dir, "*.md"))):
        problems.extend(check_done_ticket_drift(path, state))

    problems.extend(check_spec_drift(cwd))

    if problems:
        reason = (
            "ループ整合性チェックで不整合を検出しました。"
            "終了前に以下を修正してください:\n- " + "\n- ".join(problems)
        )
        # Stop hook は decision/reason をトップレベルで返す（Claude Code の契約）。
        # hookSpecificOutput にネストすると block が無視されるため注意。
        print(json.dumps({
            "decision": "block",
            "reason": reason,
        }))
    sys.exit(0)


if __name__ == "__main__":
    main()
