"""AC1〜AC6（KLK-026）のドキュメント改訂結果の機械的検証。

設計書 docs/designs/KLK-026.md §9「受け入れ条件」AC1〜AC6は
`.claude/agents/orchestrator.md`・`docs/worktree-policy.md`・`docs/reports/README.md`・
`.claude/agents/implementer.md`・`.claude/agents/tester.md`・`.gitignore.public`・
`.gitignore.private`・`docs/designs/KLK-004.md` の文言改訂であり、コードとして実行
されないため通常の自動テスト対象ではない。本ファイルは前例（tests/test_klk004_doc_wiring.py、
KLK-004）に倣い、将来の編集によって運用手順（誰が・いつ・どこでコミットするか）の要点が
静かに失われていないかを軽量に検証する回帰ガードである。

手続き的な遵守（実際にエージェントがコミットを忘れないこと）自体はプロンプトベースの
規約であり検証対象外（docs/designs/KLK-026.md §6リスク表で明記済み）。本ファイルは
文言・差分の存在のみを検証する。
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _util  # noqa: E402

AGENTS_DIR = os.path.join(_util.REPO, ".claude", "agents")
ORCHESTRATOR_MD = os.path.join(AGENTS_DIR, "orchestrator.md")
IMPLEMENTER_MD = os.path.join(AGENTS_DIR, "implementer.md")
TESTER_MD = os.path.join(AGENTS_DIR, "tester.md")
WORKTREE_POLICY = os.path.join(_util.REPO, "docs", "worktree-policy.md")
REPORTS_README = os.path.join(_util.REPO, "docs", "reports", "README.md")
KLK004_DESIGN = os.path.join(_util.REPO, "docs", "designs", "KLK-004.md")
GITIGNORE_PUBLIC = os.path.join(_util.REPO, ".gitignore.public")
GITIGNORE_PRIVATE = os.path.join(_util.REPO, ".gitignore.private")


def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def extract_section(text, heading_prefix):
    """`heading_prefix` で始まる見出し行から、同レベル以下の次の見出しまで
    （または末尾まで）を抜き出す。見出しレベル（`#`の数）を跨がない。"""
    lines = text.splitlines()
    start = None
    level = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(heading_prefix):
            start = i + 1
            level = len(stripped) - len(stripped.lstrip("#"))
            break
    if start is None:
        raise AssertionError("見出し '%s' が見つかりません" % heading_prefix)
    end = len(lines)
    for i in range(start, len(lines)):
        candidate = lines[i]
        if candidate.startswith("#"):
            cur_level = len(candidate) - len(candidate.lstrip("#"))
            if cur_level <= level:
                end = i
                break
    return "\n".join(lines[start:end])


class TestOrchestratorWorktreeLifecycleCommitRules(unittest.TestCase):
    """AC1: orchestrator.md「worktreeライフサイクル管理」に
    investigation.md/review.mdのコミット規定が追加されていること。"""

    def setUp(self):
        self.section = extract_section(
            read(ORCHESTRATOR_MD), "### worktreeライフサイクル管理"
        )

    def test_investigation_md_commit_instruction_present(self):
        self.assertIn("docs/reports/{ID}/investigation.md", self.section)
        # 作成手順内でdevelopへコミットする指示であること
        self.assertIn("develop", self.section)
        self.assertIn("コミットする", self.section)

    def test_review_md_commit_instruction_present(self):
        self.assertIn("docs/reports/{ID}/review.md", self.section)
        # マージ・削除手順（承認時のみ実行）より前にコミットする旨の明記
        self.assertIn("より前に行う", self.section)

    def test_klk012_method_explicitly_not_adopted(self):
        # KLK-012実運用（featureブランチ側コミット）を正規手順として採用しない旨の明記
        self.assertTrue(
            "979c062" in self.section or "正規手順として採用しない" in self.section,
            "KLK-012方式を採用しない旨の記述が見当たらない",
        )


class TestWorktreePolicyBoundaryTable(unittest.TestCase):
    """AC3: docs/worktree-policy.md「作業場所の境界」表へのdocs/reports/行追加。"""

    def setUp(self):
        self.section = extract_section(
            read(WORKTREE_POLICY), "## 作業場所の境界"
        )

    def test_main_tree_row_has_investigation_and_review(self):
        rows = [ln for ln in self.section.splitlines() if ln.strip().startswith("|")]
        main_tree_rows = [r for r in rows if "メインツリー" in r]
        self.assertTrue(main_tree_rows, "メインツリー行が見つからない")
        row = main_tree_rows[0]
        self.assertIn("docs/reports/{ID}/investigation.md", row)
        self.assertIn("review.md", row)

    def test_worktree_row_has_implementation_and_test_report(self):
        rows = [ln for ln in self.section.splitlines() if ln.strip().startswith("|")]
        worktree_rows = [r for r in rows if "チケット専用worktree" in r]
        self.assertTrue(worktree_rows, "チケット専用worktree行が見つからない")
        row = worktree_rows[0]
        self.assertIn("docs/reports/{ID}/implementation.md", row)
        self.assertIn("test-report.md", row)

    def test_reviewer_appears_only_in_worktree_row_note(self):
        # reviewerが表の「エージェント」列でworktree行にのみ現れる旨の注記
        self.assertIn("チケット専用worktree", self.section)
        self.assertIn("行にのみ現れる", self.section)


class TestWorktreePolicyLifecycleMirrorsOrchestrator(unittest.TestCase):
    """AC1/AC3: worktree-policy.mdのライフサイクル節がorchestrator.mdと
    同じ運用（investigation.mdのバンドルコミット・review.mdのメインツリー
    直接commit・KLK-012方式の非採用）を指していること。"""

    def setUp(self):
        self.section = extract_section(
            read(WORKTREE_POLICY),
            "### ライフサイクル（orchestratorが管理・worktreeの寿命",
        )

    def test_creation_step_bundles_investigation_md(self):
        self.assertIn("docs/reports/{ID}/investigation.md", self.section)

    def test_review_completion_subsection_present(self):
        self.assertIn("レビュー完了時", self.section)
        self.assertIn("docs/reports/{ID}/review.md", self.section)
        self.assertTrue(
            "KLK-012" in self.section and "採用しない" in self.section,
            "KLK-012方式を採用しない旨の記述が見当たらない",
        )


class TestReportsReadmePointerResolvability(unittest.TestCase):
    """AC4: docs/reports/README.mdに「ポインタの解決性」節が追加され、
    未解決タイミングが明記されていること。"""

    def setUp(self):
        self.readme = read(REPORTS_README)

    def test_pointer_resolvability_heading_present(self):
        self.assertIn("## ポインタの解決性", self.readme)

    def test_implementation_and_test_report_unresolvable_window_documented(self):
        section = extract_section(self.readme, "## ポインタの解決性")
        self.assertIn("implementation.md", section)
        self.assertIn("test-report.md", section)
        self.assertIn("解決できない", section)

    def test_investigation_and_review_always_resolvable(self):
        section = extract_section(self.readme, "## ポインタの解決性")
        self.assertIn("investigation.md", section)
        self.assertIn("review.md", section)
        self.assertIn("常に解決できる", section)


class TestImplementerTesterCommitObligation(unittest.TestCase):
    """AC2: implementer.md/tester.mdのGit Rulesで自筆分コミットが
    「してよい」ではなく義務表現に変わっていること。"""

    def test_implementer_git_rules_mandates_commit(self):
        section = extract_section(read(IMPLEMENTER_MD), "## Git Rules")
        self.assertIn("必ずコミットする", section)
        self.assertNotIn("反映してよい", section)

    def test_tester_git_rules_mandates_commit(self):
        section = extract_section(read(TESTER_MD), "## Git Rules")
        self.assertIn("必ずコミットする", section)
        self.assertNotIn("含めてよい", section)

    def test_tester_fail_path_also_covers_test_report_md(self):
        section = extract_section(read(TESTER_MD), "## Git Rules")
        self.assertIn("Quality Gate fail時も", section)
        self.assertIn("test-report.md", section)


class TestGitignorePresetAsymmetry(unittest.TestCase):
    """AC5: .gitignore.publicにのみdocs/reports/*/除外パターンを追加し、
    .gitignore.privateは変更しないこと。"""

    def test_public_excludes_reports_subdirs(self):
        text = read(GITIGNORE_PUBLIC)
        self.assertIn("docs/reports/*/", text)

    def test_private_does_not_exclude_reports(self):
        text = read(GITIGNORE_PRIVATE)
        self.assertNotIn("docs/reports/*/", text)
        self.assertNotIn("docs/reports/", text)


class TestKlk004DesignDocCorrection(unittest.TestCase):
    """AC5/AC6: docs/designs/KLK-004.md §5影響範囲表がAC5決定と
    一致するよう訂正されていること（KLK-026との矛盾解消）。"""

    def setUp(self):
        self.section = extract_section(read(KLK004_DESIGN), "## 5. 影響範囲")

    def test_public_and_private_rows_split(self):
        rows = [ln for ln in self.section.splitlines() if ln.strip().startswith("|")]
        public_rows = [
            r for r in rows if "`.gitignore.public`" in r and "`.gitignore.private`" not in r
        ]
        private_rows = [
            r for r in rows if "`.gitignore.private`" in r and "`.gitignore.public`" not in r
        ]
        self.assertEqual(len(public_rows), 1, "gitignore.public単独の行が一意でない")
        self.assertEqual(len(private_rows), 1, "gitignore.private単独の行が一意でない")
        self.assertIn("docs/reports/*/", public_rows[0])

    def test_no_stale_combined_row_remains(self):
        # 訂正前の「変更なし」1行まとめの記述が残っていないこと
        self.assertNotIn(
            "`.gitignore.public` / `.gitignore.private` | 変更なし", self.section
        )


class TestExistingKlk004RegressionUnaffected(unittest.TestCase):
    """KLK-026の変更がKLK-004回帰ガードの検証対象文言を壊していないこと
    （tests/test_klk004_doc_wiring.pyは本チケットの対象外だが、依存する
    フレーズをKLK-026が削除していないかの補助確認）。"""

    def test_cap_phrase_survives_in_implementer_and_tester(self):
        for path in (IMPLEMENTER_MD, TESTER_MD):
            self.assertIn("要点5行以内", read(path))

    def test_reports_readme_phase_names_survive(self):
        readme = read(REPORTS_README)
        for phase in ("investigation", "implementation", "test-report", "review"):
            self.assertIn("`%s`" % phase, readme)


if __name__ == "__main__":
    unittest.main()
