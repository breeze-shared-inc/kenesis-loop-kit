"""テスト共有ユーティリティ

hookスクリプトをサブプロセスとして起動するヘルパと、チケット生成テンプレートを提供する。
依存なし（標準ライブラリのみ）。
"""
import json
import os
import subprocess
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(TESTS_DIR, ".."))
HOOKS = os.path.join(REPO, ".claude", "hooks")
METRICS = os.path.join(REPO, ".claude", "metrics")

VALIDATOR = os.path.join(HOOKS, "validate_ticket_state.py")
INTEGRITY = os.path.join(HOOKS, "check_loop_integrity.py")
RECORDER = os.path.join(HOOKS, "record_metrics.py")
AGGREGATE = os.path.join(METRICS, "aggregate.py")


def run_script(script, payload, cwd=None):
    """hookスクリプトをstdin経由で実行し (returncode, stdout, stderr) を返す。"""
    data = payload if isinstance(payload, str) else json.dumps(payload)
    proc = subprocess.run(
        [sys.executable, script],
        input=data,
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    return proc.returncode, proc.stdout, proc.stderr


def hook_output(stdout):
    """stdoutから hookSpecificOutput を取り出す。空（=allow）なら None。"""
    stdout = stdout.strip()
    if not stdout:
        return None
    try:
        return json.loads(stdout)["hookSpecificOutput"]
    except Exception:
        return None


_TICKET_TEMPLATE = """---
id: "{tid}"
title: "t"
status: {status}
priority: high
type: feature
created: "2026-06-14"
updated: "2026-06-14"
project: "demo"
tags: []
related_files: []
retry_counts:
  tester_to_implementer: {tti}
  reviewer_to_implementer: {rti}
  reviewer_to_investigator: {rtv}
---

# t

## ブロッカー
{blocker}

## リトライカウンタ
| 差し戻し種別 | 回数 | 上限 |
|---|---|---|
| tester → implementer | {tti} | 3 |
| reviewer → implementer | {rti} | 2 |
| reviewer → investigator | {rtv} | 1 |

## ログ
"""


def ticket(status="todo", tti=0, rti=0, rtv=0, tid="APP-001", blocker="<!-- なし -->"):
    """テスト用チケットMarkdownを生成する。"""
    return _TICKET_TEMPLATE.format(
        tid=tid, status=status, tti=tti, rti=rti, rtv=rtv, blocker=blocker
    )


def write_ticket(cwd, filename, **kwargs):
    """tickets/active/<filename> にチケットを書き出し、絶対パスを返す。"""
    active = os.path.join(cwd, "tickets", "active")
    os.makedirs(active, exist_ok=True)
    path = os.path.join(active, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(ticket(**kwargs))
    return path
