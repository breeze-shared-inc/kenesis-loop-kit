"""AC3・AC5（KLK-005）のドキュメント分離結果の機械的回帰ガード。

設計書 docs/designs/KLK-005.md §9「受け入れ条件」AC3・AC5はCLAUDE.mdの
バイトサイズ削減とdocs/policy-registry.mdへの表移設であり、tester(このファイル)が
実装完了後に独立検証した。ticket・設計書はテスト追加を明示指示していないが、
本チケットの成果（CLAUDE.mdスリム化）は将来の編集で無言のうちに再肥大化・
誤編集し得るため、以下2点を機械的な回帰ガードとして追加する
（tester.md「追加すべきテストがあるとすれば…」の判断に基づく）。

1. AC3: CLAUDE.mdのバイトサイズが着手時基準(21,252B)の65%以下（13,813.8B以下）
   であること。将来の編集でCLAUDE.mdへ本文が書き戻され閾値を超えたら検出する。
2. AC5: docs/policy-registry.mdの「CLAUDE.md＝インデックス＋共通定義の維持」行の
   「定義（正）」列が`docs/policy-registry.md`自身ではなく`CLAUDE.md`側（原則の正が
   移設先ではなく残置側にあること）を指し続けているか。既存のtest_klk003/004の
   回帰ガードはKLK-003・KLK-004由来の行（list_tickets.py行・reports行）のみを
   検証しており、KLK-005固有のAC5行はいずれもカバーしていない。
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _util  # noqa: E402

CLAUDE_MD = os.path.join(_util.REPO, "CLAUDE.md")
POLICY_REGISTRY_MD = os.path.join(_util.REPO, "docs", "policy-registry.md")

# 設計書 docs/designs/KLK-005.md AC3: 着手時実測 21,252バイトの35%以上削減
# = 13,813.8バイト以下（21252 * 0.65）。
BASELINE_BYTES = 21252
THRESHOLD_BYTES = BASELINE_BYTES * 0.65  # 13,813.8


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


class TestClaudeMdByteSizeThreshold(unittest.TestCase):
    """AC3: CLAUDE.mdのバイトサイズが35%以上削減された閾値以下に維持されている。"""

    def test_byte_size_at_or_below_ac3_threshold(self):
        size = os.path.getsize(CLAUDE_MD)
        self.assertLessEqual(
            size, THRESHOLD_BYTES,
            "CLAUDE.mdが%dバイトに増大し、KLK-005 AC3の閾値%.1fバイト（着手時%dバイトの"
            "65%%）を超過している。再肥大化していないか確認すること。"
            % (size, THRESHOLD_BYTES, BASELINE_BYTES),
        )


class TestPolicyRegistrySelfReferenceRow(unittest.TestCase):
    """AC5: 「CLAUDE.md＝インデックス＋共通定義の維持」行の定義（正）がCLAUDE.md側を指す。"""

    def setUp(self):
        self.section = extract_section(read(POLICY_REGISTRY_MD), "ポリシー一覧")

    def _self_reference_row(self):
        rows = [
            ln for ln in self.section.splitlines()
            if "CLAUDE.md＝インデックス＋共通定義の維持" in ln
        ]
        self.assertEqual(len(rows), 1, "該当行が一意でない: %r" % rows)
        return rows[0]

    def test_row_exists_and_is_a_table_row(self):
        row = self._self_reference_row()
        self.assertTrue(row.strip().startswith("|"),
                        "該当行がテーブル行の書式（'|'開始）になっていない")

    def test_definition_column_points_to_claude_md_not_registry_itself(self):
        row = self._self_reference_row()
        cols = [c.strip() for c in row.strip().strip("|").split("|")]
        self.assertGreaterEqual(len(cols), 2, "列数が不足: %r" % cols)
        definition_col = cols[1]
        self.assertIn("CLAUDE.md", definition_col)
        self.assertIn("ポリシー管理の原則", definition_col)
        self.assertNotIn("policy-registry.md", definition_col)


if __name__ == "__main__":
    unittest.main()
