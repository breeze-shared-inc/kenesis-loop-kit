"""AC1・AC3・AC5（KLK-004）のドキュメント改訂結果の機械的検証。

設計書 docs/designs/KLK-004.md §9「受け入れ条件」AC1・AC3・AC5は
`.claude/agents/*.md`（6ファイル）・`CLAUDE.md` の文言改訂であり、コードとして
実行されないため通常の自動テスト対象ではない。本ファイルは前例
（tests/test_klk003_doc_wiring.py、KLK-003）に倣い、将来の編集（他チケットが
同じ6ファイルへ手を入れる・リファクタリングする等）によって規約の要点が
静かに失われていないかを軽量に検証する回帰ガードである。

厳密な文言一致ではなく、AC1（要点5行以内＋外部化ポインタの一律導入・
phase名の対応・architectの明示的除外）・AC3（orchestrator.mdの委譲後ログ
追記ルールが3点を含むこと）・AC5（CLAUDE.mdポリシー管理表への1行追加）の
核を安定した部分文字列で検証する。付随して、`docs/reports/README.md` が
定義するphase名・writer分担が各エージェント定義と食い違っていないかも
確認する（AC2との整合。委譲プロンプトで確認を求められた項目）。
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _util  # noqa: E402

AGENTS_DIR = os.path.join(_util.REPO, ".claude", "agents")
CLAUDE_MD = os.path.join(_util.REPO, "CLAUDE.md")
REPORTS_README = os.path.join(_util.REPO, "docs", "reports", "README.md")

CAP_PHRASE = "要点5行以内"

ALL_SIX_AGENTS = (
    "orchestrator", "investigator", "architect",
    "implementer", "tester", "reviewer",
)

# phase を持つ4ロール（architectはdocs/designs/{ID}.md運用のため対象外）と、
# それぞれのRequired Output Format見出し（investigatorのみ"(Mode A only)"が付く）
REPORT_PHASE_FILES = {
    "investigator": ("investigation", "Required Output Format (Mode A only)"),
    "implementer": ("implementation", "Required Output Format"),
    "tester": ("test-report", "Required Output Format"),
    "reviewer": ("review", "Required Output Format"),
}


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


class TestAgentReportExternalizationCap(unittest.TestCase):
    """AC1: 各 .claude/agents/*.md に要約上限＋外部化規約が一律導入されていること。"""

    def test_all_six_agents_have_cap_phrase(self):
        for name in ALL_SIX_AGENTS:
            text = read(os.path.join(AGENTS_DIR, name + ".md"))
            self.assertIn(CAP_PHRASE, text,
                          "%s.md に '%s' の規約が見当たらない" % (name, CAP_PHRASE))

    def test_delegate_phase_pointer_matches_role(self):
        # phase名（investigation/implementation/test-report/review）が
        # 各ファイルの役割と対応していること
        for name, (phase, heading) in REPORT_PHASE_FILES.items():
            text = read(os.path.join(AGENTS_DIR, name + ".md"))
            section = extract_section(text, heading)
            pointer = "docs/reports/{ID}/%s.md" % phase
            self.assertIn(
                pointer, section,
                "%s.md の '%s' 節にポインタ '%s' が見当たらない"
                % (name, heading, pointer))

    def test_architect_points_to_designs_not_reports(self):
        # architectは新規ファイルを増やさず、既存docs/designs/{ID}.md運用の明文化のみ
        text = read(os.path.join(AGENTS_DIR, "architect.md"))
        section = extract_section(text, "Required Output Format")
        self.assertIn("docs/designs/{ID}.md", section)
        self.assertNotIn("docs/reports/", section)


class TestOrchestratorTicketIntegrationRules(unittest.TestCase):
    """AC3: orchestrator.mdの委譲後ログ追記ルールが3点を含むこと。"""

    def setUp(self):
        text = read(os.path.join(AGENTS_DIR, "orchestrator.md"))
        self.section = extract_section(text, "Ticket Integration")

    def test_summary_only_append(self):
        self.assertIn("要点5行以内", self.section)

    def test_ghostwriting_for_toolsless_agents(self):
        # orchestrator.md自身は「代筆」という語を使わず「Write/Editツールを
        # 持たないエージェント...の分はorchestratorが...書き出し」と表現する
        # （investigator.md/reviewer.mdは「代筆」を使う。表現は違うが趣旨は同一）
        self.assertIn("Write/Editツールを持たない", self.section)
        self.assertIn("書き出し", self.section)
        self.assertIn("investigator", self.section)
        self.assertIn("reviewer", self.section)

    def test_overwrite_on_rerun_with_log_entry(self):
        self.assertIn("同一ファイルを上書き", self.section)
        self.assertIn("を再実施 - 理由", self.section)


class TestClaudeMdPolicyRow(unittest.TestCase):
    """AC5: CLAUDE.md ポリシー管理表への1行追加（本文セクション新設なし）。"""

    def setUp(self):
        self.section = extract_section(read(CLAUDE_MD), "ポリシー管理の原則")

    def test_policy_row_references_reports_path(self):
        self.assertIn("docs/reports/{ID}/{phase}.md", self.section)

    def test_policy_row_is_unique_table_row_pointing_to_design_doc(self):
        rows = [ln for ln in self.section.splitlines()
                if "docs/reports/{ID}/{phase}.md" in ln]
        table_rows = [r for r in rows if r.strip().startswith("|")]
        self.assertEqual(len(table_rows), 1,
                          "該当するテーブル行が一意でない: %r" % table_rows)
        self.assertIn("docs/designs/KLK-004.md", table_rows[0])

    def test_closing_sentence_still_after_table(self):
        # 締め文が表の後段に残っている（表の途中への誤挿入がないことの簡易確認）
        idx_row = self.section.index("docs/reports/{ID}/{phase}.md")
        idx_closing = self.section.index("新しいポリシーを追加する際は")
        self.assertLess(idx_row, idx_closing)


class TestReportsReadmeConsistencyWithAgentFiles(unittest.TestCase):
    """docs/reports/README.md が定義するphase名・writer分担が
    6エージェント定義の記述と食い違っていないこと。"""

    def setUp(self):
        self.readme = read(REPORTS_README)

    def test_all_four_phase_names_present(self):
        for phase in ("investigation", "implementation", "test-report", "review"):
            self.assertIn("`%s`" % phase, self.readme)

    def test_self_write_roles_present_in_own_agent_files(self):
        # 自筆＝implementer・tester。README上の分担どおり、各エージェント自身の
        # 定義にも「自ら作成する」旨が明記されていること
        for name in ("implementer", "tester"):
            text = read(os.path.join(AGENTS_DIR, name + ".md"))
            self.assertIn("自ら", text,
                          "%s.md に自筆（自ら作成）の記述が見当たらない" % name)

    def test_ghost_write_roles_present_in_own_agent_files(self):
        # 代筆＝investigator・reviewer（orchestratorが代筆）。両ファイルとも
        # 自身はファイルを作成しない旨が明記されていること
        for name in ("investigator", "reviewer"):
            text = read(os.path.join(AGENTS_DIR, name + ".md"))
            self.assertIn("代筆", text,
                          "%s.md に代筆（orchestratorが代筆）の記述が見当たらない" % name)

    def test_architect_excluded_note_present(self):
        self.assertIn("architectは対象外", self.readme)


if __name__ == "__main__":
    unittest.main()
