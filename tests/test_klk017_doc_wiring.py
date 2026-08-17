"""KLK-017（KLK-010設計書の実装反映と記述訂正）の受け入れ条件の機械的回帰ガード。

本チケットはコード変更を伴わない文書修正チケット（C10/H6の書き戻し・H7/SV-22の
決着記録・SV-25のPhase状態更新）であり、成果の大半は `docs/designs/KLK-010.md`
の文言に現れる。前例（tests/test_klk004_doc_wiring.py・test_klk005_doc_wiring.py・
test_klk026_doc_wiring.py）に倣い、将来の編集で以下の決着事項が無言のうちに
失われていないかを軽量に検証する。

1. V-13（設計書 §3-11 の INV ID と `INVENTORY_CASES` の機械照合）を、
   implementerがその場で使った未コミットのdiffスクリプトではなく、
   スイートに常設する形で固定する（設計にあるIDが実装データに1件も
   欠けていないことを継続的に検証する）。
2. INV-AWKLEX-14（C10）・INV-SH-22（H6）が期待値 `deny` で登録されていること。
3. H7（INV-SED-09）・SV-22の「決着事項」（人間承認済み・2026-08-17）が
   設計書 §10 に記録され続けていること、およびINV-SED-09〜16が
   変更されず期待値 `deny` のまま機能し続けること（H7の充足根拠の回帰確認）。
4. SV-25: §4-8 Phase表のPhase 14・15が「未実施」ではなく「完了」の
   状態文言・コミットハッシュを維持していること。
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _util  # noqa: E402
import test_guard_bash_writes as tgb  # noqa: E402

DESIGN_DOC = os.path.join(_util.REPO, "docs", "designs", "KLK-010.md")
README_MD = os.path.join(_util.HOOKS, "README.md")

INV_ID_RE = re.compile(r"INV-(?:AWKLEX|AWK|SED|SH)-\d+")


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


def inventory_case_ids():
    return {case[0] for case in tgb.INVENTORY_CASES}


def inventory_case_expected(case_id):
    for cid, _syntax, _command, expected in tgb.INVENTORY_CASES:
        if cid == case_id:
            return expected
    raise AssertionError("INVENTORY_CASES に %s が見つからない" % case_id)


class TestV13DesignIdsSubsetOfInventoryCases(unittest.TestCase):
    """V-13: §3-11 の写像表に現れるIDが `INVENTORY_CASES` に1件残らず
    存在すること（設計にあって実装データに無いIDが0件であること）。"""

    def test_all_design_section_3_11_ids_exist_in_inventory_cases(self):
        section = extract_section(read(DESIGN_DOC), "### 3-11.")
        design_ids = set(INV_ID_RE.findall(section))
        self.assertTrue(design_ids, "§3-11 からIDを1件も抽出できなかった")
        case_ids = inventory_case_ids()
        missing = sorted(design_ids - case_ids)
        self.assertEqual(
            missing, [],
            "設計書 §3-11 にあるが INVENTORY_CASES に無いID: %r" % missing,
        )


class TestNewHighRegistrationsRegisteredAsDeny(unittest.TestCase):
    """C10・H6の書き戻し: INV-AWKLEX-14・INV-SH-22が期待値denyで存在すること。"""

    def test_inv_awklex_14_present_and_deny(self):
        self.assertEqual(inventory_case_expected("INV-AWKLEX-14"), "deny")

    def test_inv_sh_22_present_and_deny(self):
        self.assertEqual(inventory_case_expected("INV-SH-22"), "deny")


class TestH7Sv22DecisionsRecordedInDesignDoc(unittest.TestCase):
    """H7（INV-SED-09のID競合）・SV-22（README/docstringの前提変化）の
    人間承認済み決着（2026-08-17）が §10 Open Questions に残っていること。"""

    def setUp(self):
        self.section = extract_section(read(DESIGN_DOC), "## 10. Open Questions")

    def test_h7_decision_present(self):
        self.assertIn("INV-SED-09", self.section)
        self.assertIn("新規登録は行わず", self.section)
        self.assertIn("2026-08-17", self.section)

    def test_sv22_decision_present(self):
        self.assertIn("SV-22", self.section)
        self.assertIn("追加は行わない", self.section)

    def test_no_unresolved_open_question_remains(self):
        self.assertIn("未決着の Open Question は無い", self.section)


class TestH7RegressionInvSedRangeUnchanged(unittest.TestCase):
    """H7の充足根拠（KLK-015のINV-SED-09〜16がすべてdeny）が
    本チケットの変更で壊れていないこと。"""

    def test_inv_sed_09_through_16_all_deny(self):
        for i in range(9, 17):
            case_id = "INV-SED-%02d" % i
            with self.subTest(id=case_id):
                self.assertEqual(inventory_case_expected(case_id), "deny")


class TestSv22ReadmeAndDocstringAccuracyPreserved(unittest.TestCase):
    """SV-22: README.md・モジュールdocstringのsed w/Wに関する条件付き
    記述（許可文字集合に基づくホワイトリスト）が維持され、かつ
    architectが「追加すると誤りを生む」と判断した『アドレス前置き形は
    未対応』という注記が新設されていないこと。"""

    def test_readme_still_states_whitelist_based_denial(self):
        text = read(README_MD)
        self.assertIn(
            "`w`/`W`/`r`/`R`/`e`/`a`/`i`/`c`/`b`/`t`/`T`"
            "等の書き込み・情報開示・実行・分岐系コマンドを許可せず",
            text,
        )

    def test_docstring_still_states_whitelist_based_denial(self):
        text = read(_util.GUARD_BASH)
        self.assertRegex(
            text,
            re.compile(r"未知の文字・未収載のコマンド.*?deny\s*側へ落ちる", re.S),
        )

    def test_no_stale_address_prefixed_unsupported_note_added(self):
        # チケットが当初求めた「アドレス前置き形は未対応」注記は、SV-22の
        # 決着（追加は行わない）に反するため新設されていないこと。
        for path in (README_MD, _util.GUARD_BASH):
            self.assertNotIn("アドレス前置き", read(path))


class TestPhase14And15MarkedComplete(unittest.TestCase):
    """SV-25: §4-8 Phase表のPhase 14・15が「未実施」から「完了」へ
    更新され、対応コミットハッシュが残っていること。"""

    def setUp(self):
        self.section = extract_section(read(DESIGN_DOC), "### 4-8.")
        rows = [
            ln for ln in self.section.splitlines()
            if ln.strip().startswith("|")
        ]
        self.phase_rows = {}
        for row in rows:
            cols = [c.strip() for c in row.strip().strip("|").split("|")]
            if not cols:
                continue
            # Phase番号列は "**14**" のようにMarkdownの強調記法を伴う
            phase_num = cols[0].strip("*").strip()
            if phase_num in ("14", "15"):
                self.phase_rows[phase_num] = row

    def test_phase_14_row_found_and_complete(self):
        self.assertIn("14", self.phase_rows, "Phase 14の行が見つからない")
        row = self.phase_rows["14"]
        self.assertIn("完了", row)
        self.assertIn("0a42478", row)
        self.assertNotIn("未実施", row)

    def test_phase_15_row_found_and_complete(self):
        self.assertIn("15", self.phase_rows, "Phase 15の行が見つからない")
        row = self.phase_rows["15"]
        self.assertIn("完了", row)
        self.assertIn("e26fcf4", row)
        self.assertNotIn("未実施", row)


if __name__ == "__main__":
    unittest.main()
