"""check_spec_structure.py（SPEC構造チェッカー）のテスト

レビューで実証された誤FAIL・誤PASSの回帰を防ぐ。
フィクスチャはテンプレート準拠の最小SPECを基点に、各ケースが変異を加える。
"""
import importlib.util
import os
import sys
import unittest

CHECKER = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".claude", "skills", "spec-interview", "scripts", "check_spec_structure.py")

spec = importlib.util.spec_from_file_location("check_spec_structure", CHECKER)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


CONFORMANT = """# SPEC.md

## 0. 文書情報・変更履歴

| 版数 | 更新日 | 更新者 | 変更概要 |
|---|---|---|---|
| v1.0 | 2026-07-01 | 山田 | 初版作成 |

## 1. プロジェクト概要
ログインできるWebアプリを作る。

## 2. 背景・目的
手作業をなくす。

## 3. 用語集

| 用語 | 定義 |
|---|---|
| ユーザー | 登録済みの利用者 |

## 4. ユーザー・ステークホルダー

| ユーザー種別 | 説明 | 主な操作 |
|---|---|---|
| 一般ユーザー | 登録済みの利用者 | ログイン・閲覧 |

## 5. 機能要件

### Must(必須)

| ID | 要件 | 関連画面 | 備考 |
|---|---|---|---|
| REQ-001 | ログインできる | SCR-001 | |

### Should(できれば)

| ID | 要件 | 関連画面 | 備考 |
|---|---|---|---|
| REQ-101 | パスワードリセット | - | OQ-001に依存 |

### Could(余裕があれば)

| ID | 要件 | 関連画面 | 備考 |
|---|---|---|---|

## 6. 画面・インターフェース一覧

### 画面一覧

| ID | 画面名 | 目的 | 主な要素 | 対応要件 | アクセス可能なユーザー | ワイヤーフレーム |
|---|---|---|---|---|---|---|
| SCR-001 | ログイン画面 | 認証 | フォーム | REQ-001 | 一般ユーザー | (未作成) |

### 提供インターフェース一覧

該当なし

### 画面遷移図

```mermaid
flowchart LR
    SCR001[SCR-001] --> SCR001
```

## 7. エラーハンドリング・異常系方針

| ID | 分類 | 方針 | 検証方法 |
|---|---|---|---|
| EH-001 | 入力検証 | サーバーサイドで検証 | 自動テスト |

## 8. 非機能要件

| ID | 項目 | 要件 | 検証方法 |
|---|---|---|---|
| NFR-001 | 応答時間 | 2秒以内 | 自動テストで計測 |

## 9. 技術的制約

本構成は標準構成 v1.0 (2026-01-01) をデフォルト適用したものである
- 使用言語: TypeScript 5.x

## 10. データ・外部インターフェース要件

| データ | 機密区分 | 保持期間 | 備考 |
|---|---|---|---|
| メールアドレス | 個人情報 | 退会後30日 | |

## 11. スコープ外(明示的な除外事項)

- 多言語対応

## 12. 未決事項(Open Questions)

| ID | 事項 | ステータス | 決定内容 |
|---|---|---|---|
| OQ-001 | メール送信サービスの選定 | 未決定 | |

## 13. 成功基準

- REQ-001が受け入れ基準を満たすこと

## 14. 参考資料

- なし
"""


class TestCheckSpecStructure(unittest.TestCase):
    def run_check(self, text):
        ok, ng, warn = mod.check(text)
        return ng, warn

    def assertConformant(self, text, msg=""):
        ng, _ = self.run_check(text)
        self.assertEqual(ng, [], msg or "FAILなしのはず: %s" % ng)

    def assertFails(self, text, fragment):
        ng, _ = self.run_check(text)
        self.assertTrue(any(fragment in m for m in ng),
                        "FAIL「%s」が出るはず: %s" % (fragment, ng))

    # --- 基本判定 ---

    def test_conformant_passes(self):
        ng, warn = self.run_check(CONFORMANT)
        self.assertEqual(ng, [])
        self.assertEqual(warn, [])

    def test_template_itself_passes(self):
        path = os.path.join(os.path.dirname(CHECKER), "..",
                            "templates", "SPEC_TEMPLATE.md")
        ng, warn = self.run_check(open(path, encoding="utf-8").read())
        self.assertEqual(ng, [])
        self.assertEqual(warn, [])

    def test_freeform_fails(self):
        self.assertFails("# 要件定義\n\n## 1. 概要\n作る。\n", "存在しない")

    def test_missing_scr_and_nashi_fails(self):
        text = CONFORMANT.replace(
            "| SCR-001 | ログイン画面 | 認証 | フォーム | REQ-001 | 一般ユーザー | (未作成) |",
            "ログイン画面がある。")
        self.assertFails(text, "SCR-IDも「該当なし」の明記もない")

    # --- 検証方法列（誤FAIL・誤PASSの回帰） ---

    def test_extra_column_no_false_fail(self):
        # 検証方法の後に備考列を足しても、記載済みなら誤FAILしない
        text = CONFORMANT.replace(
            "| ID | 分類 | 方針 | 検証方法 |\n|---|---|---|---|\n"
            "| EH-001 | 入力検証 | サーバーサイドで検証 | 自動テスト |",
            "| ID | 分類 | 方針 | 検証方法 | 備考 |\n|---|---|---|---|---|\n"
            "| EH-001 | 入力検証 | サーバーサイドで検証 | 自動テスト | メモ |")
        self.assertConformant(text)

    def test_empty_verify_with_trailing_column_fails(self):
        # 検証方法が空で末尾の備考だけ埋まっている行は見逃さない
        text = CONFORMANT.replace(
            "| ID | 分類 | 方針 | 検証方法 |\n|---|---|---|---|\n"
            "| EH-001 | 入力検証 | サーバーサイドで検証 | 自動テスト |",
            "| ID | 分類 | 方針 | 検証方法 | 備考 |\n|---|---|---|---|---|\n"
            "| EH-001 | 入力検証 | サーバーサイドで検証 | | メモ |")
        self.assertFails(text, "EH-001 の検証方法が空")

    def test_verify_dash_placeholder_fails(self):
        text = CONFORMANT.replace(
            "| NFR-001 | 応答時間 | 2秒以内 | 自動テストで計測 |",
            "| NFR-001 | 応答時間 | 2秒以内 | - |")
        self.assertFails(text, "NFR-001 の検証方法が空")

    def test_nfr_bullets_without_table_fails(self):
        # 表を使わない箇条書きのNFRは検証方法が定義できないためFAIL
        text = CONFORMANT.replace(
            "| ID | 項目 | 要件 | 検証方法 |\n|---|---|---|---|\n"
            "| NFR-001 | 応答時間 | 2秒以内 | 自動テストで計測 |",
            "- NFR-001: 応答時間は2秒以内")
        self.assertFails(text, "NFR-IDが表の主キー位置にない")

    # --- Must-OQ依存（見出し欠落時の誤FAIL回帰） ---

    def test_oq_in_could_without_should_heading_passes(self):
        # Should節が無くても、Could配下の合法なOQ依存を誤FAILしない
        text = CONFORMANT.replace(
            "### Should(できれば)\n\n| ID | 要件 | 関連画面 | 備考 |\n"
            "|---|---|---|---|\n| REQ-101 | パスワードリセット | - | OQ-001に依存 |\n\n"
            "### Could(余裕があれば)\n\n| ID | 要件 | 関連画面 | 備考 |\n|---|---|---|---|",
            "### Could(余裕があれば)\n\n| ID | 要件 | 関連画面 | 備考 |\n"
            "|---|---|---|---|\n| REQ-201 | パスワードリセット | - | OQ-001に依存 |")
        self.assertConformant(text)

    def test_oq_in_must_fails(self):
        text = CONFORMANT.replace(
            "| REQ-001 | ログインできる | SCR-001 | |",
            "| REQ-001 | ログインできる | SCR-001 | OQ-001に依存 |")
        self.assertFails(text, "Must要件がOQに依存")

    # --- ID重複（参照表の誤検知回帰） ---

    def test_reference_table_in_13_no_false_dup(self):
        text = CONFORMANT.replace(
            "## 13. 成功基準\n\n- REQ-001が受け入れ基準を満たすこと",
            "## 13. 成功基準\n\n| ID | 達成条件 |\n|---|---|\n"
            "| REQ-001 | doneであること |\n| NFR-001 | 検証済みであること |")
        self.assertConformant(text)

    def test_real_duplicate_in_definition_fails(self):
        text = CONFORMANT.replace(
            "| EH-001 | 入力検証 | サーバーサイドで検証 | 自動テスト |",
            "| EH-001 | 入力検証 | サーバーサイドで検証 | 自動テスト |\n"
            "| EH-001 | 認証失敗 | ロックする | 自動テスト |")
        self.assertFails(text, "ID重複")

    # --- UIなしプロジェクト ---

    def test_noui_with_if_table_passes(self):
        text = CONFORMANT.replace(
            "| SCR-001 | ログイン画面 | 認証 | フォーム | REQ-001 | 一般ユーザー | (未作成) |",
            "該当なし").replace(
            "### 提供インターフェース一覧\n\n該当なし",
            "### 提供インターフェース一覧\n\n"
            "| ID | 名称 | 種別 | 目的 | 入力・出力の概要 | 対応要件 | 利用者 |\n"
            "|---|---|---|---|---|---|---|\n"
            "| IF-001 | 認証API | REST API | 認証 | 入出力 | REQ-001 | EC |").replace(
            "| REQ-001 | ログインできる | SCR-001 | |",
            "| REQ-001 | ログインできる | - | |")
        self.assertConformant(text)

    def test_noui_prose_if_only_fails(self):
        # 散文中のIF-ID言及だけでは提供IF一覧にならない
        text = CONFORMANT.replace(
            "| SCR-001 | ログイン画面 | 認証 | フォーム | REQ-001 | 一般ユーザー | (未作成) |",
            "該当なし").replace(
            "### 提供インターフェース一覧\n\n該当なし",
            "### 提供インターフェース一覧\n\n認証は IF-001 として提供する。").replace(
            "| REQ-001 | ログインできる | SCR-001 | |",
            "| REQ-001 | ログインできる | - | |")
        self.assertFails(text, "提供インターフェース一覧")

    # --- その他の回帰 ---

    def test_numbered_scope_list_passes(self):
        text = CONFORMANT.replace(
            "- 多言語対応", "1. 多言語対応\n2. モバイルアプリ")
        self.assertConformant(text)

    def test_html_comment_star_not_counted_as_origin_note(self):
        # コメント内の★や標準構成の言及は出自注記とみなさない
        text = CONFORMANT.replace(
            "本構成は標準構成 v1.0 (2026-01-01) をデフォルト適用したものである",
            "<!-- 指定項目には★を付す。標準構成 v1.0 参照 -->")
        _, warn = self.run_check(text)
        self.assertTrue(any("出自注記" in m for m in warn), warn)

    def test_dangling_screen_reference_fails(self):
        text = CONFORMANT.replace(
            "| REQ-001 | ログインできる | SCR-001 | |",
            "| REQ-001 | ログインできる | SCR-009 | |")
        self.assertFails(text, "§5が参照する画面が§6に存在しない")

    # --- CLI契約 ---

    def test_cli_exit_codes(self):
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            good = os.path.join(d, "check_target_ok.md")
            with open(good, "w", encoding="utf-8") as f:
                f.write(CONFORMANT)
            bad = os.path.join(d, "check_target_ng.md")
            with open(bad, "w", encoding="utf-8") as f:
                f.write("# x\n")
            sjis = os.path.join(d, "check_target_sjis.md")
            with open(sjis, "wb") as f:
                f.write("## 概要 日本語".encode("cp932"))
            run = lambda *args: subprocess.run(
                [sys.executable, CHECKER, *args],
                capture_output=True, text=True).returncode
            self.assertEqual(run(good), 0)
            self.assertEqual(run(bad), 1)
            self.assertEqual(run(sjis), 2)   # UnicodeDecodeErrorは契約どおり2
            self.assertEqual(run(), 2)       # 引数なし
            self.assertEqual(run(os.path.join(d, "none.md")), 2)


if __name__ == "__main__":
    unittest.main()
