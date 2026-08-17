"""AC1・AC3・AC6（KLK-027）のドキュメント改訂結果の機械的検証。

docs/designs/KLK-027.md §3-§4の決定（①削除・②を正とする一本化、Required Output Format
文言の設計書§4への完全一致、ポインタ書式定義の存在）を回帰ガードする。
tests/test_klk004_doc_wiring.py の前例に倣い、本ファイルはKLK-027固有の検証のみを
新規ファイルとして持つ（既存ファイルは編集しない）。
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _util  # noqa: E402

AGENTS_DIR = os.path.join(_util.REPO, ".claude", "agents")
REPORTS_README = os.path.join(_util.REPO, "docs", "reports", "README.md")
KLK004_DESIGN = os.path.join(_util.REPO, "docs", "designs", "KLK-004.md")

# role -> (phase, ROF見出し（"## "抜き）, Integration/Git Rules見出し（"## "付き）, 分類)
ROLES = {
    "investigator": ("investigation", "Required Output Format (Mode A only)",
                      "## Ticket Integration", "ghost"),
    "implementer":  ("implementation", "Required Output Format",
                      "## Git Rules", "self"),
    "tester":       ("test-report", "Required Output Format",
                      "## Git Rules", "self"),
    "reviewer":     ("review", "Required Output Format",
                      "## Ticket Integration", "ghost"),
}
MARKER = {"self": "自ら", "ghost": "代筆"}
OPPOSITE = {"self": "代筆", "ghost": "自ら"}

COMMON_TEMPLATE = (
    "各項目は要点5行以内の箇条書きで記述する。5行を超える詳細"
    "（全文・生ログ・網羅的な根拠列挙等）はチケット本文へ書かず"
    "`docs/reports/{ID}/%s.md`へ外部化し、該当項目には"
    "「詳細: docs/reports/{ID}/%s.md」という1行のポインタのみを残す。"
)


def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def extract_section(text, heading_prefix):
    """`heading_prefix` で始まる見出し行から、同レベル以下の次の見出しまで
    （または末尾まで）を抜き出す。見出しレベル（`#`の数）を跨がない。

    tests/test_klk026_doc_wiring.py の実装をそのまま移植する。
    """
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


def normalize_ws(s):
    return re.sub(r"\s+", "", s)


class TestWriterAttributionUnified(unittest.TestCase):
    """AC1: ①(ROF括弧)が削除され②(Integration/Git Rules)が単一の正であること、
    ③(README)が②と矛盾しないことを横断的に確認する。"""

    def test_rof_section_has_no_writer_attribution_bracket(self):
        # ①削除の回帰ガード: ROF節に「自ら」「代筆」いずれの語も存在しない
        for role, (_, rof_heading, _, _) in ROLES.items():
            section = extract_section(read(os.path.join(AGENTS_DIR, role + ".md")),
                                       "## " + rof_heading)
            self.assertNotIn("自ら", section, role)
            self.assertNotIn("代筆", section, role)

    def test_integration_or_git_rules_has_correct_marker(self):
        # ②が正: 役割ごとの分類と一致する語がIntegration/Git Rules節にあり、
        # 逆側の語は無い
        for role, (_, _, heading_prefix, kind) in ROLES.items():
            section = extract_section(read(os.path.join(AGENTS_DIR, role + ".md")),
                                       heading_prefix)
            self.assertIn(MARKER[kind], section, role)
            self.assertNotIn(OPPOSITE[kind], section, role)

    def test_readme_writer_table_matches_role_classification(self):
        # ③がREADME内部で②と矛盾しないこと（selfロール名は「代筆で書き出す」より
        # 手前に、ghostロール名は「代筆で書き出す」より手前かつ言及があること）
        readme = read(REPORTS_README)
        idx_ghost = readme.index("代筆で書き出す")
        self_sentence = readme[:idx_ghost]
        for role, (_, _, _, kind) in ROLES.items():
            if kind == "self":
                self.assertIn(role, self_sentence, role)
            else:
                idx_role = readme.index(role)
                self.assertLess(idx_role, idx_ghost, role)

    def test_readme_declares_agent_files_as_source_of_truth(self):
        self.assertIn("正とする横断サマリ", read(REPORTS_README))


class TestRequiredOutputFormatMatchesDesignTemplate(unittest.TestCase):
    """AC3: Required Output Format文言が設計書§4の共通テンプレートと
    (空白差異を除き) 完全一致すること。"""

    def test_four_roles_match_template_exactly(self):
        for role, (phase, rof_heading, _, _) in ROLES.items():
            section = extract_section(read(os.path.join(AGENTS_DIR, role + ".md")),
                                       "## " + rof_heading)
            paragraph = section.strip().split("\n\n", 1)[0]
            expected = COMMON_TEMPLATE % (phase, phase)
            self.assertEqual(normalize_ws(paragraph), normalize_ws(expected), role)


class TestPointerFormatDefinitionExists(unittest.TestCase):
    """AC6: ポインタ書式「詳細: docs/reports/{ID}/{phase}.md」の定義が
    設計書とREADMEの双方に存在すること。"""

    POINTER = "詳細: docs/reports/{ID}/{phase}.md"

    def test_present_in_klk004_design(self):
        self.assertIn(self.POINTER, read(KLK004_DESIGN))

    def test_present_in_reports_readme_pointer_resolvability_section(self):
        section = extract_section(read(REPORTS_README), "## ポインタの解決性")
        self.assertIn(self.POINTER, section)


if __name__ == "__main__":
    unittest.main()
