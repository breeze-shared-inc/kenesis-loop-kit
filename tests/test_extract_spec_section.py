"""extract_spec_section.py（SPEC部分抽出CLI）のテスト

check_spec_structure.py・test_check_spec_structure.pyの実証済みパターン
（動的import・CLI契約テスト）を踏襲する。フィクスチャは本テスト専用の
自己完結フィクスチャ（§5・§6のみを含む）とし、test_check_spec_structure.py
のCONFORMANTには依存しない（テストファイル間の結合を避けるため）。
"""
import importlib.util
import os
import sys
import unittest

EXTRACTOR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".claude", "skills", "spec-interview", "scripts", "extract_spec_section.py")

spec = importlib.util.spec_from_file_location("extract_spec_section", EXTRACTOR)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


# 本テスト専用の自己完結フィクスチャ。§5・§6のみを含み、REQ(Must/Should/Could)・
# SCR(画面一覧)・IF(提供インターフェース一覧)それぞれ正常系1件ずつを持つ。
FIXTURE = """## 5. 機能要件

### Must(必須)

| ID | 要件 | 関連画面 | 備考 |
|---|---|---|---|
| REQ-001 | ログインできる | SCR-001 | |

### Should(できれば)

| ID | 要件 | 関連画面 | 備考 |
|---|---|---|---|
| REQ-101 | パスワードリセット | - | |

### Could(余裕があれば)

| ID | 要件 | 関連画面 | 備考 |
|---|---|---|---|
| REQ-201 | ダークモード | - | |

## 6. 画面・インターフェース一覧

### 画面一覧

| ID | 画面名 | 目的 | 主な要素 | 対応要件 | アクセス可能なユーザー | ワイヤーフレーム |
|---|---|---|---|---|---|---|
| SCR-001 | ログイン画面 | 認証 | フォーム | REQ-001 | 一般ユーザー | (未作成) |

### 提供インターフェース一覧

| ID | 名称 | 種別 | 目的 | 入力・出力の概要 | 対応要件 | 利用者 |
|---|---|---|---|---|---|---|
| IF-001 | 認証API | REST API | 認証 | 入出力 | REQ-001 | EC |
"""

# 小見出しの無い旧形式SPEC（セクション全体へのフォールバックを検証する）
LEGACY_FIXTURE = """## 5. 機能要件

| ID | 要件 | 関連画面 | 備考 |
|---|---|---|---|
| REQ-500 | 旧形式の要件 | - | |
"""

# 同一IDが2つの小見出しに重複定義された非準拠SPEC（複数件返却＋WARNを検証する）
DUPLICATE_FIXTURE = """## 5. 機能要件

### Must(必須)

| ID | 要件 | 関連画面 | 備考 |
|---|---|---|---|
| REQ-777 | 要件A | - | |

### Should(できれば)

| ID | 要件 | 関連画面 | 備考 |
|---|---|---|---|
| REQ-777 | 要件B | - | |
"""


class TestClassify(unittest.TestCase):
    def test_req_supported(self):
        self.assertEqual(mod.classify("REQ-001"), ("REQ", "supported"))

    def test_scr_supported(self):
        self.assertEqual(mod.classify("SCR-001"), ("SCR", "supported"))

    def test_if_supported(self):
        self.assertEqual(mod.classify("IF-001"), ("IF", "supported"))

    def test_digit_mismatch_too_few_invalid_format(self):
        self.assertEqual(mod.classify("REQ-1"), ("REQ", "invalid_format"))

    def test_digit_mismatch_too_many_invalid_format(self):
        self.assertEqual(mod.classify("REQ-0001"), ("REQ", "invalid_format"))

    def test_eh_unsupported_prefix(self):
        self.assertEqual(mod.classify("EH-001"), ("EH", "unsupported_prefix"))

    def test_nfr_unsupported_prefix(self):
        self.assertEqual(mod.classify("NFR-001"), ("NFR", "unsupported_prefix"))

    def test_oq_unsupported_prefix(self):
        self.assertEqual(mod.classify("OQ-001"), ("OQ", "unsupported_prefix"))

    def test_non_id_string_invalid_format(self):
        self.assertEqual(mod.classify("abc"), (None, "invalid_format"))

    def test_lowercase_prefix_invalid_format(self):
        # 桁数は正しくてもprefixが小文字だと現状の実装ではsupported扱い
        # にならない（re.fullmatchは大文字化前のid_全体と照合するため）。
        # この挙動を固定するリグレッションテスト。
        self.assertEqual(mod.classify("req-001"), ("REQ", "invalid_format"))

    def test_mixed_case_prefix_invalid_format(self):
        self.assertEqual(mod.classify("Req-001"), ("REQ", "invalid_format"))

    def test_id_with_leading_whitespace_invalid_format(self):
        self.assertEqual(mod.classify(" REQ-001"), (None, "invalid_format"))

    def test_id_with_trailing_whitespace_invalid_format(self):
        self.assertEqual(mod.classify("REQ-001 "), (None, "invalid_format"))


class TestFindId(unittest.TestCase):
    def test_req_must_extracted(self):
        matches = mod.find_id(FIXTURE, "REQ", "REQ-001")
        self.assertEqual(len(matches), 1)
        heading, body = matches[0]
        self.assertEqual(heading, "5. 機能要件 > Must(必須)")
        self.assertIn("REQ-001", body)
        self.assertIn("| ID | 要件 | 関連画面 | 備考 |", body)

    def test_req_should_extracted(self):
        matches = mod.find_id(FIXTURE, "REQ", "REQ-101")
        self.assertEqual(len(matches), 1)
        heading, body = matches[0]
        self.assertEqual(heading, "5. 機能要件 > Should(できれば)")
        self.assertIn("REQ-101", body)

    def test_req_could_extracted(self):
        matches = mod.find_id(FIXTURE, "REQ", "REQ-201")
        self.assertEqual(len(matches), 1)
        heading, body = matches[0]
        self.assertEqual(heading, "5. 機能要件 > Could(余裕があれば)")
        self.assertIn("REQ-201", body)

    def test_scr_extracted(self):
        matches = mod.find_id(FIXTURE, "SCR", "SCR-001")
        self.assertEqual(len(matches), 1)
        heading, body = matches[0]
        self.assertEqual(heading, "6. 画面・インターフェース一覧 > 画面一覧")
        self.assertIn("SCR-001", body)

    def test_if_extracted(self):
        matches = mod.find_id(FIXTURE, "IF", "IF-001")
        self.assertEqual(len(matches), 1)
        heading, body = matches[0]
        self.assertEqual(heading, "6. 画面・インターフェース一覧 > 提供インターフェース一覧")
        self.assertIn("IF-001", body)

    def test_not_found_returns_empty(self):
        self.assertEqual(mod.find_id(FIXTURE, "REQ", "REQ-999"), [])

    def test_legacy_fallback_to_whole_section(self):
        matches = mod.find_id(LEGACY_FIXTURE, "REQ", "REQ-500")
        self.assertEqual(len(matches), 1)
        heading, body = matches[0]
        self.assertEqual(heading, "5. 機能要件")
        self.assertIn("REQ-500", body)

    def test_duplicate_across_subsections_returns_multiple(self):
        matches = mod.find_id(DUPLICATE_FIXTURE, "REQ", "REQ-777")
        self.assertEqual(len(matches), 2)
        headings = [h for h, _ in matches]
        self.assertIn("5. 機能要件 > Must(必須)", headings)
        self.assertIn("5. 機能要件 > Should(できれば)", headings)


class TestCli(unittest.TestCase):
    def run_cli(self, *args):
        import subprocess
        return subprocess.run(
            [sys.executable, EXTRACTOR, *args],
            capture_output=True, text=True)

    def test_cli_exit_codes(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            good = os.path.join(d, "spec_ok.md")
            with open(good, "w", encoding="utf-8") as f:
                f.write(FIXTURE)
            sjis = os.path.join(d, "spec_sjis.md")
            with open(sjis, "wb") as f:
                f.write("## 概要 日本語".encode("cp932"))

            # 正常系(0)
            proc = self.run_cli(good, "REQ-001")
            self.assertEqual(proc.returncode, 0)
            self.assertIn("REQ-001", proc.stdout)

            # 該当なし系も0
            proc = self.run_cli(good, "REQ-999")
            self.assertEqual(proc.returncode, 0)
            self.assertIn("該当なし", proc.stdout)

            # 引数なし(SPECパスもID未指定)は2
            self.assertEqual(self.run_cli().returncode, 2)

            # ファイルなしは2
            self.assertEqual(
                self.run_cli(os.path.join(d, "none.md"), "REQ-001").returncode, 2)

            # SJISデコード失敗は2
            self.assertEqual(self.run_cli(sjis, "REQ-001").returncode, 2)

    def test_cli_unsupported_and_invalid_format_are_exit_zero(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            good = os.path.join(d, "spec_ok.md")
            with open(good, "w", encoding="utf-8") as f:
                f.write(FIXTURE)
            proc = self.run_cli(good, "EH-001", "REQ-1", "abc")
            self.assertEqual(proc.returncode, 0)
            self.assertIn("対応プレフィックス外", proc.stdout)
            self.assertIn("ID形式として認識できません", proc.stdout)

    def test_cli_empty_spec_file_no_crash_exit_zero(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            empty = os.path.join(d, "empty.md")
            open(empty, "w", encoding="utf-8").close()
            proc = self.run_cli(empty, "REQ-001")
            self.assertEqual(proc.returncode, 0)
            self.assertIn("該当なし", proc.stdout)


if __name__ == "__main__":
    unittest.main()
