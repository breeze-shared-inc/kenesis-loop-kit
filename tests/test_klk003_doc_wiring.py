"""AC2・AC3・AC5（KLK-003）のドキュメント改訂結果の機械的検証。

設計書 docs/designs/KLK-003.md §9「受け入れ条件」AC2・AC3・AC5は
`.claude/agents/orchestrator.md` / `.claude/commands/start-loop.md` / `CLAUDE.md`
の文言改訂であり、コードとして実行されないため通常の自動テスト対象ではない。
本ファイルは「一覧CLI (`python3 scripts/list_tickets.py`) への言及が該当セクションに
存在し続けているか」「旧・全件フルリード文言へ意図せず後退していないか」を
将来の編集（他チケットのマージ・リファクタリング等）に対する回帰ガードとして
軽量に検証する（前例: tests/test_agent_frontmatter.py がKLK-002でagent定義ファイルの
frontmatterを同様に機械検証している）。

厳密な文言一致ではなく、AC2・AC3・AC5の核である「CLIコマンド文字列への言及」
「1件のみのフルリードという趣旨」「旧文言の不在」を安定した部分文字列で検証する
（将来の言い回し変更で無用に壊れないよう、句読点まで厳密には固定しない）。
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _util  # noqa: E402

ORCHESTRATOR_MD = os.path.join(_util.REPO, ".claude", "agents", "orchestrator.md")
START_LOOP_MD = os.path.join(_util.REPO, ".claude", "commands", "start-loop.md")
CLAUDE_MD = os.path.join(_util.REPO, "CLAUDE.md")

CLI_INVOCATION = "python3 scripts/list_tickets.py"


def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def extract_section(text, heading):
    """`## {heading}` から次の `## ` 見出し（または末尾）までを抜き出す。"""
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == "## %s" % heading:
            start = i + 1
            break
    if start is None:
        raise AssertionError("見出し '## %s' が見つかりません" % heading)
    end = len(lines)
    for i in range(start, len(lines)):
        if lines[i].startswith("## "):
            end = i
            break
    return "\n".join(lines[start:end])


class TestOrchestratorTicketIntegration(unittest.TestCase):
    """AC2: orchestrator.md Ticket Integration。"""

    def setUp(self):
        self.section = extract_section(read(ORCHESTRATOR_MD), "Ticket Integration")

    def test_cli_invocation_present(self):
        self.assertIn(CLI_INVOCATION, self.section)

    def test_single_ticket_full_read_semantics_present(self):
        # 「処理対象1件のみをReadツールでフル読み取り」という趣旨が残っていること
        self.assertIn("1件のみ", self.section)
        self.assertIn("フル読み取り", self.section)

    def test_old_full_scan_phrase_removed(self):
        # 旧文言（全件読み取り、priority順に処理対象を選択）へ後退していないこと
        self.assertNotIn(
            "tickets/active/ を全件読み取り、priority順に処理対象を選択",
            self.section,
        )


class TestStartLoopChecklistAndProcedure(unittest.TestCase):
    """AC3: start-loop.md 起動時チェックリスト・ループ実行手順。"""

    def setUp(self):
        text = read(START_LOOP_MD)
        self.checklist = extract_section(text, "起動時チェックリスト（必須・スキップ禁止）")
        self.procedure = extract_section(text, "ループ実行手順")

    def test_cli_invocation_in_checklist_at_least_twice(self):
        # 「14日超blockedチケットの検出」「in_progress上限チェック」の2項目分
        count = self.checklist.count(CLI_INVOCATION)
        self.assertGreaterEqual(
            count, 2,
            "起動時チェックリスト内のCLI言及が2件未満（実測 %d 件）" % count,
        )

    def test_cli_invocation_in_procedure_step1(self):
        self.assertIn(CLI_INVOCATION, self.procedure)

    def test_old_full_read_phrases_removed_from_checklist(self):
        self.assertNotIn(
            "tickets/active/ の全チケットを読み取り",
            self.checklist,
        )
        self.assertNotIn(
            "の全チケットを読み取り、`status = blocked`",
            self.checklist,
        )

    def test_old_full_read_phrase_removed_from_procedure_step1(self):
        self.assertNotIn(
            "tickets/active/ を全件読み取り、statusとpriorityを確認する",
            self.procedure,
        )

    def test_procedure_steps_2_to_5_unchanged_no_cli_mentions(self):
        # 設計書§4: 「手順2〜5は変更しない」。CLI言及が手順1以外に漏れ出していないことを
        # 大まかに確認する（手順1の行を除いた残りにCLI文字列が出現しない）
        lines = [ln for ln in self.procedure.splitlines() if ln.strip()]
        step1_lines = [ln for ln in lines if ln.strip().startswith("1.")]
        other_lines = [ln for ln in lines if not ln.strip().startswith("1.")]
        self.assertTrue(step1_lines, "手順1の行が見つかりません")
        for ln in other_lines:
            self.assertNotIn(CLI_INVOCATION, ln)


class TestClaudeMdPolicyTable(unittest.TestCase):
    """AC5: CLAUDE.md ポリシー管理表への1行追加。"""

    def setUp(self):
        self.section = extract_section(read(CLAUDE_MD), "ポリシー管理の原則")

    def test_policy_row_references_list_tickets_script(self):
        self.assertIn("scripts/list_tickets.py", self.section)

    def test_policy_row_points_to_design_doc(self):
        rows = [ln for ln in self.section.splitlines()
                if "scripts/list_tickets.py" in ln]
        self.assertEqual(len(rows), 1, "該当行が一意でない: %r" % rows)
        self.assertIn("docs/designs/KLK-003.md", rows[0])

    def test_policy_row_is_a_table_row(self):
        rows = [ln for ln in self.section.splitlines()
                if "scripts/list_tickets.py" in ln]
        self.assertTrue(rows[0].strip().startswith("|"),
                        "追加行がテーブル行の書式（'|'開始）になっていない")

    def test_closing_sentence_still_after_table(self):
        # 締め文が表の後段に残っている（表の途中への誤挿入がないことの簡易確認）
        idx_row = self.section.index("scripts/list_tickets.py")
        idx_closing = self.section.index("新しいポリシーを追加する際は")
        self.assertLess(idx_row, idx_closing)


if __name__ == "__main__":
    unittest.main()
