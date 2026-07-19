"""`.claude/agents/*.md` のfrontmatter健全性テスト（KLK-002）

PyYAML等の外部依存を追加せず、stdlibのみの簡易frontmatterパーサで
`name` / `description` / `tools` / `model` / `skills` の健全性を検証する。
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _util  # noqa: E402

AGENTS_DIR = os.path.join(_util.REPO, ".claude", "agents")

# model frontmatterが存在してよい許容値（公式ドキュメントの許容値 + フルモデルIDらしき文字列）
MODEL_ALIASES = {"sonnet", "opus", "haiku", "fable", "inherit"}
FULL_MODEL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def is_allowed_model_value(value):
    """許容値集合（エイリアス）またはフルモデルIDらしき文字列であること。"""
    if value in MODEL_ALIASES:
        return True
    return bool(FULL_MODEL_ID_RE.match(value))


def parse_frontmatter(text):
    """先頭の `---` 〜 `---` ブロックのみを対象に簡易parseする。

    本文中に偶然 `---` が出現しても誤検出しないよう、frontmatterの終端は
    「ファイル先頭行が `---`」であることを確認したうえで、2番目に現れる
    `---` 行までに限定する。戻り値は None（frontmatterなし）または dict。
    スカラー値は文字列、`key:`（値なし）+ 直後の `- item` 行はリストとして扱う。
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return None

    block = lines[1:end_idx]
    data = {}
    i = 0
    while i < len(block):
        line = block[i]
        if not line.strip():
            i += 1
            continue
        if line.startswith(" ") or line.startswith("-"):
            # トップレベルキー行ではない（リスト項目の続きなど）。呼び出し側で消費済みのはず。
            i += 1
            continue
        key, sep, rest = line.partition(":")
        if not sep:
            i += 1
            continue
        key = key.strip()
        rest = rest.strip()
        if rest:
            data[key] = rest
            i += 1
        else:
            # 値なし: 直後の `- item` 行をリストとして読む
            items = []
            j = i + 1
            while j < len(block) and block[j].strip().startswith("- "):
                items.append(block[j].strip()[2:].strip())
                j += 1
            data[key] = items
            i = j
    return data


def read_agent(name):
    path = os.path.join(AGENTS_DIR, name)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


ALL_AGENT_FILES = [
    "tester.md",
    "investigator.md",
    "architect.md",
    "reviewer.md",
    "implementer.md",
    "orchestrator.md",
]

SONNET_ASSIGNED = {"tester.md", "investigator.md"}
NO_MODEL_KEY = {"architect.md", "reviewer.md", "implementer.md", "orchestrator.md"}


class TestParserEdgeCases(unittest.TestCase):
    """簡易パーサ自体のエッジケース（設計書9節「エッジケース重点」）。"""

    def test_body_dashes_do_not_confuse_parser(self):
        text = (
            "---\n"
            "name: sample\n"
            "description: d\n"
            "tools: Read\n"
            "---\n"
            "\n"
            "# Sample\n"
            "\n"
            "---\n"
            "some horizontal-rule-like body content\n"
            "---\n"
        )
        fm = parse_frontmatter(text)
        self.assertEqual(fm["name"], "sample")
        self.assertEqual(fm["tools"], "Read")

    def test_no_leading_frontmatter_returns_none(self):
        self.assertIsNone(parse_frontmatter("# just a heading\nno fm here\n---\nx\n---\n"))

    def test_scalar_and_list_mixed(self):
        text = (
            "---\n"
            "name: x\n"
            "tools: Read, Write\n"
            "skills:\n"
            "  - a\n"
            "  - b\n"
            "---\n"
        )
        fm = parse_frontmatter(text)
        self.assertEqual(fm["tools"], "Read, Write")
        self.assertEqual(fm["skills"], ["a", "b"])


class TestAgentFrontmatterCommon(unittest.TestCase):
    """全6ファイル共通の必須キー検証。"""

    def test_all_files_have_name_description_tools(self):
        for filename in ALL_AGENT_FILES:
            with self.subTest(filename=filename):
                fm = parse_frontmatter(read_agent(filename))
                self.assertIsNotNone(fm, "%s: frontmatterが見つからない" % filename)
                for key in ("name", "description", "tools"):
                    self.assertIn(key, fm, "%s: %s キーが無い" % (filename, key))
                    self.assertTrue(
                        fm[key].strip(),
                        "%s: %s キーが空文字" % (filename, key),
                    )

    def test_investigator_has_skills_list(self):
        fm = parse_frontmatter(read_agent("investigator.md"))
        self.assertIn("skills", fm)
        self.assertIsInstance(fm["skills"], list)
        self.assertGreaterEqual(len(fm["skills"]), 1)

    def test_other_files_have_no_skills_key(self):
        # skillsはinvestigator.mdのみが持つ既存書式（回帰検知）
        for filename in ALL_AGENT_FILES:
            if filename == "investigator.md":
                continue
            with self.subTest(filename=filename):
                fm = parse_frontmatter(read_agent(filename))
                self.assertNotIn("skills", fm, "%s: skillsキーが想定外に存在する" % filename)


class TestModelAssignment(unittest.TestCase):
    """AC1・AC2: モデル割当のfrontmatter検証（KLK-002）。"""

    def test_sonnet_assigned_files_have_model_sonnet(self):
        for filename in SONNET_ASSIGNED:
            with self.subTest(filename=filename):
                fm = parse_frontmatter(read_agent(filename))
                self.assertEqual(fm.get("model"), "sonnet",
                                  "%s: model: sonnet が見つからない" % filename)

    def test_non_assigned_files_have_no_model_key(self):
        for filename in NO_MODEL_KEY:
            with self.subTest(filename=filename):
                fm = parse_frontmatter(read_agent(filename))
                self.assertNotIn("model", fm,
                                  "%s: modelキーが存在してはいけない（inherit維持）" % filename)

    def test_model_value_within_allowed_set_when_present(self):
        for filename in ALL_AGENT_FILES:
            with self.subTest(filename=filename):
                fm = parse_frontmatter(read_agent(filename))
                if "model" in fm:
                    self.assertTrue(
                        is_allowed_model_value(fm["model"]),
                        "%s: model値 %r が許容値集合に含まれない"
                        % (filename, fm["model"]),
                    )


class TestIsAllowedModelValueFunction(unittest.TestCase):
    """`is_allowed_model_value` 自体の直接検証（合成値）。

    実ファイルは現時点で全て許容値のみを持つため、
    `test_model_value_within_allowed_set_when_present` は実ファイル経由では
    「許容値集合外の値が来たときに実際にFalseを返すか」を検証できない
    （常にTrueなfixtureしか通らないため、検証ロジック自体の回帰を検知できない）。
    このクラスは合成値（valid/invalid双方）で判定関数を直接検証し、将来
    許容値外のmodel値が混入した場合の検知を保証する（設計書9節エッジケース）。
    """

    def test_known_aliases_are_allowed(self):
        for alias in ("sonnet", "opus", "haiku", "fable", "inherit"):
            with self.subTest(alias=alias):
                self.assertTrue(is_allowed_model_value(alias))

    def test_full_model_id_like_string_is_allowed(self):
        self.assertTrue(is_allowed_model_value("claude-opus-4-1-20250805"))
        self.assertTrue(is_allowed_model_value("claude-sonnet-4-5-20250929"))

    def test_disallowed_value_with_invalid_characters_is_rejected(self):
        # 空白・記号を含む値は許容値集合にもフルモデルIDパターンにも
        # 一致しないため、将来の設定ミス（タイプミス・不正な値）を検知できる
        for bad_value in ("sonnet turbo!", "model/with/slash", "model:with:colon", ""):
            with self.subTest(bad_value=bad_value):
                self.assertFalse(is_allowed_model_value(bad_value))


if __name__ == "__main__":
    unittest.main()
