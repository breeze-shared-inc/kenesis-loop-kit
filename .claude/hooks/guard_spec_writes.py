#!/usr/bin/env python3
"""PreToolUse hook - SPEC.md 書き込みゲート

Write / Edit が SPEC.md（basename一致）に対して行われる直前に発火し、
`permissionDecision: ask` で人間への確認を強制する。autoモード等の
自動承認モードでも確認プロンプトが挟まるため、「SPEC.md への書き込みは
人間の diff 承認を経る」（ドキュメント管理ルール / interrogate-spec Phase 4 /
spec-interview）を LLM の手順遵守だけに依存せず機械的に担保する。

対象外:
- .claude/ 配下（スキル同梱のテンプレート・参照ファイル）
- basename が SPEC.md でないファイル（SPEC_TEMPLATE.md 等）

fail-open: 内部エラー（パース不能など）では allow。
注意: --dangerously-skip-permissions 起動時は ask が貫通する（hook共通の限界）。
注意: Bashツール経由の書き込み（リダイレクト・sed -i・インタプリタ等）は
      このhookの対象外。guard_bash_writes.py（PreToolUse・Bash）が
      ベストエフォートで遮断し、各エージェント定義の Never ルールで補強する
      （KLK-016 で Stop hook にも SPEC.md のハッシュドリフト検知を追加した。
      観測サイドカーは docs/.spec_state.json。ネストした SPEC.md は対象外）。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _ticket_lib as lib  # noqa: E402


def allow():
    sys.exit(0)


def ask(reason):
    lib.emit_pretooluse_decision("ask", reason)


def is_spec(path):
    n = path.replace("\\", "/")
    if "/.claude/" in n or n.startswith(".claude/"):
        return False
    return n.rsplit("/", 1)[-1] == "SPEC.md"


def main():
    # 入力型の正規化は hook 境界（main）で行い、判定関数（is_spec）は str を
    # 前提とする（KLK-012 §3 D5）。非 dict の payload / tool_input、非 str の
    # file_path はいずれも fail-open（allow）
    data = lib.read_hook_payload()
    if data is None:
        allow()

    tool_input = lib.as_dict(data.get("tool_input"))
    path = tool_input.get("file_path")
    if not isinstance(path, str) or not path or not is_spec(path):
        allow()

    ask(
        "SPEC.md への書き込みです。提示された diff を確認し、"
        "承認する場合のみ許可してください"
        "（ドキュメント管理ルール: SPEC.md の改訂は人間の承認を経る）。"
    )


if __name__ == "__main__":
    main()
