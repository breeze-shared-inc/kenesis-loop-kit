"""AC1・AC2・AC3・AC6（KLK-022）のドキュメント改訂結果の機械的検証。

docs/designs/KLK-022.md §3-§4の決定（triage.md手順1のCLI検出＋候補限定フル読み取りへの
分割、start-loop.md「14日超blockedチケットの検出」項目からの委譲時の手順1スキップ明示、
triage.mdへの「メインworktree実行」注記追加、policy-registry.md該当行の更新）を回帰ガード
する。tests/test_klk004_doc_wiring.py・tests/test_klk027_doc_wiring.py の前例に倣い、
本ファイルはKLK-022固有の検証のみを新規ファイルとして持つ（既存ファイルは編集しない）。
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _util  # noqa: E402

TRIAGE_MD = os.path.join(_util.REPO, ".claude", "commands", "triage.md")
START_LOOP_MD = os.path.join(_util.REPO, ".claude", "commands", "start-loop.md")
POLICY_REGISTRY_MD = os.path.join(_util.REPO, "docs", "policy-registry.md")

CLI_INVOCATION = "python3 scripts/list_tickets.py"
OLD_STEP1_PHRASE = (
    "tickets/active/ の全チケットを読み取り、`status = blocked` "
    "かつ条件（経過日数またはID一致）を満たすチケットを一覧表示する"
)


def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def extract_section(text, heading):
    """`## {heading}` から次の `## ` 見出し（または末尾）までを抜き出す。
    tests/test_klk003_doc_wiring.py の実装を移植する。"""
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


class TestTriageMdStep1CliSplit(unittest.TestCase):
    """AC1・AC3: triage.md 手順1のCLI検出化と、候補限定フル読み取りの明示。"""

    def setUp(self):
        self.section = extract_section(read(TRIAGE_MD), "手順")

    def test_old_full_scan_phrase_removed(self):
        self.assertNotIn(OLD_STEP1_PHRASE, self.section)

    def test_cli_invocation_present(self):
        self.assertIn(CLI_INVOCATION, self.section)

    def test_two_path_branching_present(self):
        self.assertIn("start-loopから委譲された場合", self.section)
        self.assertIn("単体実行する場合", self.section)

    def test_no_redetection_on_delegation_present(self):
        # 委譲時は再検出しない旨が明示されている(AC2の一部)
        self.assertIn("再検出", self.section)

    def test_candidate_only_full_read_grain_present(self):
        # 候補と確定したチケットのみをフル読み取りする粒度の明示(AC3)
        self.assertIn("候補IDのみ", self.section)
        self.assertIn("候補以外のチケットは読み取らない", self.section)

    def test_main_worktree_note_present(self):
        self.assertIn("メインworktree", self.section)

    def test_step_numbers_1_and_6_present(self):
        # 手順が1つ増え6段階になっている(既存5段階からの繰り下げが行われた回帰ガード)
        body = "\n" + self.section
        self.assertIn("\n1. ", body)
        self.assertIn("\n6. ", body)


class TestStartLoopTriageHandoffNoDoubleDetection(unittest.TestCase):
    """AC2: start-loop.md「14日超blockedチケットの検出」からtriage.mdへの委譲時、
    手順1(検出)を再実行しない導線が文面上明示されていること。"""

    def setUp(self):
        text = read(START_LOOP_MD)
        self.checklist = extract_section(text, "起動時チェックリスト（必須・スキップ禁止）")

    def test_cli_invocation_still_present_at_least_twice(self):
        # KLK-003が固定した既存の観点(test_klk003_doc_wiring.py)を本ファイルでも独立に確認する
        count = self.checklist.count(CLI_INVOCATION)
        self.assertGreaterEqual(count, 2)

    def test_handoff_skips_triage_step1(self):
        self.assertIn("手順1", self.checklist)
        self.assertIn("スキップ", self.checklist)

    def test_triage_reference_present(self):
        self.assertIn(".claude/commands/triage.md", self.checklist)


class TestPolicyRegistryRowUpdated(unittest.TestCase):
    """AC6: policy-registry.md該当行にtriage.mdが追記されていること。"""

    def setUp(self):
        self.section = extract_section(read(POLICY_REGISTRY_MD), "ポリシー一覧")

    def test_row_still_unique(self):
        rows = [ln for ln in self.section.splitlines()
                if "scripts/list_tickets.py" in ln]
        self.assertEqual(len(rows), 1, "該当行が一意でない: %r" % rows)
        self.row = rows[0]

    def test_row_mentions_triage_command(self):
        rows = [ln for ln in self.section.splitlines()
                if "scripts/list_tickets.py" in ln]
        self.assertIn("/triage", rows[0])
        self.assertIn(".claude/commands/triage.md", rows[0])

    def test_row_mentions_new_test_file(self):
        rows = [ln for ln in self.section.splitlines()
                if "scripts/list_tickets.py" in ln]
        self.assertIn("tests/test_klk022_doc_wiring.py", rows[0])


if __name__ == "__main__":
    unittest.main()
