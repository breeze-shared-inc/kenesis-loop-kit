"""KLK-025（KLK-014設計書への実装Phase表の追加）の受け入れ条件の機械的回帰ガード。

本チケットはコード変更を伴わない文書追記チケット（`docs/designs/KLK-014.md` への
`### 4-7. 実装Phase` 節の新設のみ）であり、成果の大半は同ファイルの文言に現れる。
前例（tests/test_klk017_doc_wiring.py・test_klk026_doc_wiring.py）に倣い、将来の
編集で以下の決着事項が無言のうちに失われていないかを軽量に検証する。

1. AC1: `### 4-7. 実装Phase` 節が存在し、表が `_TEMPLATE.md` §4 準拠の4列
   （Phase／内容／完了条件／対応する受け入れ条件）であること（KLK-010 §4-8の
   「状態」列を含む5列拡張を踏襲していないこと）。
2. AC2: Phase1行にコミット`0c66699`、Phase2行にコミット`fe47ff0`が記載されており、
   各コミットの実際の変更点（関数名・ファイル名・件数）と齟齬がないこと。
3. §4-6の既存記述（末尾行）が本チケットの追記によって削除・改変されていないこと。
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _util  # noqa: E402

DESIGN_DOC = os.path.join(_util.REPO, "docs", "designs", "KLK-014.md")
TEMPLATE_DOC = os.path.join(_util.REPO, "docs", "designs", "_TEMPLATE.md")

EXISTING_46_LAST_LINE = (
    "| `test_backtick_readonly_substitution_allow`"
    "（4件・ネスト含む） | 含む | いずれも**未閉じクォート・未閉じ括弧が無い**"
    "ため外側 `lex()` が成功し degraded に一切落ちない（正常経路のみ）。無関係・無変更 |"
)


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


def table_rows(section_text):
    """セクション内の表行（`|` で始まる行）をリストで返す。"""
    return [ln for ln in section_text.splitlines() if ln.strip().startswith("|")]


def first_table_after(text, marker):
    """`marker` の出現位置より後ろで最初に現れる表（連続する`|`行の並び）を返す。
    `marker` はMarkdownの`#`見出しではない太字疑似見出しにも対応する
    （extract_sectionは`#`見出しの跨ぎ判定に依存するため、太字見出しには使えない）。"""
    idx = text.index(marker)
    lines = text[idx:].splitlines()
    rows = []
    started = False
    for ln in lines:
        if ln.strip().startswith("|"):
            started = True
            rows.append(ln)
        elif started:
            break
    return rows


class TestAC1FourColumnPhaseTableAddedFollowingTemplate(unittest.TestCase):
    """AC1: `### 4-7. 実装Phase` に `_TEMPLATE.md` §4準拠の4列表が存在すること。"""

    def setUp(self):
        self.doc_text = read(DESIGN_DOC)
        self.section = extract_section(self.doc_text, "### 4-7.")

    def test_section_4_7_heading_exists(self):
        # extract_section が例外を送出しない（見出しが存在する）ことに加え、
        # 節見出し直後に節タイトルの手掛かり語が含まれることを確認する。
        self.assertIn("実装Phase", self.doc_text[self.doc_text.index("### 4-7."):
                                                    self.doc_text.index("### 4-7.") + 40])

    def test_header_matches_template_section_4(self):
        template_text = read(TEMPLATE_DOC)
        template_rows = first_table_after(template_text, "**実装Phase:**")
        self.assertTrue(template_rows, "_TEMPLATE.md §4 に表が見つからない")
        template_header = template_rows[0].strip()

        doc_rows = table_rows(self.section)
        self.assertTrue(doc_rows, "KLK-014.md §4-7 に表が見つからない")
        doc_header = doc_rows[0].strip()

        self.assertEqual(doc_header, template_header)
        self.assertEqual(
            doc_header,
            "| Phase | 内容 | 完了条件 | 対応する受け入れ条件 |",
        )

    def test_table_is_four_columns_not_five(self):
        doc_rows = table_rows(self.section)
        header_cols = [c for c in doc_rows[0].strip().strip("|").split("|")]
        self.assertEqual(len(header_cols), 4, "KLK-010 §4-8の5列拡張は踏襲しない")
        self.assertNotIn("状態", doc_rows[0])

    def test_two_phase_rows_present(self):
        doc_rows = table_rows(self.section)
        # 1行目はヘッダ、2行目は区切り線、以降がデータ行
        data_rows = doc_rows[2:]
        self.assertEqual(len(data_rows), 2, "Phase1・Phase2の2行のみのはず")


class TestAC2PhaseContentMatchesActualCommits(unittest.TestCase):
    """AC2: Phase1=`0c66699`・Phase2=`fe47ff0` の記載内容が実際のコミットと一致すること。"""

    def setUp(self):
        self.section = extract_section(read(DESIGN_DOC), "### 4-7.")
        rows = table_rows(self.section)[2:]
        self.assertEqual(len(rows), 2)
        self.phase1_row, self.phase2_row = rows

    def test_phase1_references_commit_and_key_symbols(self):
        row = self.phase1_row
        self.assertIn("0c66699", row)
        self.assertIn("_extract_degraded_substs", row)
        self.assertIn("degraded_violation", row)
        self.assertIn("depth", row)
        self.assertIn("find_violation", row)
        self.assertIn(".claude/hooks/README.md", row)

    def test_phase2_references_commit_and_key_facts(self):
        row = self.phase2_row
        self.assertIn("fe47ff0", row)
        self.assertIn("tests/test_guard_bash_writes.py", row)
        self.assertIn("12", row)
        self.assertIn("449", row)

    def test_phase1_does_not_reference_phase2_commit(self):
        self.assertNotIn("fe47ff0", self.phase1_row)

    def test_phase2_does_not_reference_phase1_commit(self):
        self.assertNotIn("0c66699", self.phase2_row)


class TestExistingSection46UnchangedByAppend(unittest.TestCase):
    """§4-6の既存記述が本チケットの追記によって削除・改変されていないこと
    （`git diff develop -- docs/designs/KLK-014.md` が追加のみであることの
    内容面での裏付け）。"""

    def test_section_4_6_last_line_still_present_verbatim(self):
        text = read(DESIGN_DOC)
        self.assertIn(EXISTING_46_LAST_LINE, text)

    def test_section_5_heading_still_immediately_follows_phase_table(self):
        text = read(DESIGN_DOC)
        # `### 4-7.` の直後に `## 5. 影響範囲` が続き、その間に他の見出し（`#`行）が
        # 割り込んでいないこと（設計書§4のnew_stringが規定する隣接関係の維持を確認）。
        idx_4_7 = text.index("### 4-7.")
        idx_5 = text.index("## 5. 影響範囲", idx_4_7)
        between_lines = text[idx_4_7:idx_5].splitlines()[1:]  # 見出し行自体は除く
        heading_lines = [ln for ln in between_lines if ln.strip().startswith("#")]
        self.assertEqual(
            heading_lines, [],
            "§4-7と§5の間に他の見出しが割り込んでいる: %r" % heading_lines,
        )


if __name__ == "__main__":
    unittest.main()
