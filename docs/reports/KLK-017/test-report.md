# KLK-017 テストレポート（tester）

## 実行結果
- `python3 -m unittest discover -s tests` → **659件 OK**（failures 0・errors 0）。うち647件は既存（implementer報告と一致）、12件は本レポートで追加した `tests/test_klk017_doc_wiring.py`。
- `python3 -m unittest tests.test_guard_bash_writes -v` → 226件 OK（`INV-AWKLEX-14`・`INV-SH-22` の2件を含む）。
- stderrに出る `batch_loop.py: error: ...` の2行は既存テストの意図的な異常系検証の標準エラー出力であり失敗ではない（`Ran ... OK` で確認）。

## 受け入れ条件の確認結果（1件ずつ）
| 受け入れ条件 | 確認方法 | 結果 |
|---|---|---|
| INV-AWKLEX-14 新設（C10） | `tests/test_guard_bash_writes.py` 577行目付近を確認・`test_inventory_cases_match_expected_decisions` のsubTestで実行 | 期待値`deny`で登録済み・pass |
| §3-6 D11／§4-1 の記述訂正 | `docs/designs/KLK-010.md` 849行目（D11見出し）・1397行目（§4-1訂正文）を確認 | 反映済み（architectの設計作業。コード変更なしのため実行テストは対象外） |
| S1' 訂正・V-15の14サブケース化・§6 R36/R37 | 設計書の該当節（675行目S1'・§3-9-3・§6リスク表）を確認 | 反映済み（同上） |
| INV-SH-22 新設（H6・deny登録） | `tests/test_guard_bash_writes.py` 524行目付近を確認・同subTestで実行 | 期待値`deny`で登録済み・pass |
| INV-SED-09（H7）は既存ID充足済みで新規登録しない | `INVENTORY_CASES`のINV-SED-09〜16が変更されておらず全件`deny`であることを新規回帰テストで固定 | pass（後述「追加したテスト」） |
| SV-22（README/docstringは追記不要） | `git diff develop..feature/KLK-017-design-doc-backfill -- .claude/hooks/README.md .claude/hooks/guard_bash_writes.py` が空diffであることを確認＋新規回帰テストで文言を固定 | 差分0件・pass |
| SV-23〜25・M28（記述訂正） | 設計書の該当箇所（§4-8 Phase 14/15行・§4-9分類1等）を確認 | 反映済み（SV-25のPhase 14/15「完了」化は新規テストで固定） |
| M27（CHANGELOG件数の規約） | 設計書§10「決着事項」に「件数を書かない」方針採用と、Kit全体規約化は人間判断へ委ねる旨の記載を確認 | 文書決定のみ・テスト対象外（architectの裁量範囲） |
| V-13（設計ID⊆INVENTORY_CASES） | 新規回帰テストで機械照合を常設化（従来は未コミットの一時スクリプトのみ） | pass（欠落0件） |
| V-16（設計と実装の関数突き合わせ） | implementer報告（10件・乖離なし）を確認。コード変更が無いため既存647件のpass自体が回帰確認になる | 乖離報告なし |
| 既存テスト全件パス | discover実行 | 659件 OK |

## リグレッション確認
- `git diff --stat develop..feature/KLK-017-design-doc-backfill` → `docs/reports/KLK-017/implementation.md`・`tests/test_guard_bash_writes.py` の2ファイルのみ変更（本レポート作成前の時点）。`.claude/hooks/guard_bash_writes.py`・`.claude/hooks/README.md`・`CHANGELOG.md` は差分0件（プロダクションコード無変更を確認）。
- INV-SED-09〜16（H7の充足根拠・KLK-015管轄）が本チケットの変更前後で一切変更されておらず、全件`deny`のまま機能することを新規テストで固定した。
- 既存647件は全件無変更（削除0行）で659件へ増加。

## 追加したテスト
`tests/test_klk017_doc_wiring.py`（新規・12件、`docs/designs/KLK-010.md`本体・`.claude/hooks/README.md`・`.claude/hooks/guard_bash_writes.py`は一切変更せず読み取りのみ）:
1. `TestV13DesignIdsSubsetOfInventoryCases` — 設計書§3-11のINV IDが`INVENTORY_CASES`に1件残らず存在すること（V-13の機械照合をテストスイートへ常設。implementerの一時スクリプトを置き換える永続的な回帰ガード）
2. `TestNewHighRegistrationsRegisteredAsDeny` — `INV-AWKLEX-14`・`INV-SH-22`が期待値`deny`で存在すること
3. `TestH7Sv22DecisionsRecordedInDesignDoc` — 設計書§10 Open Questionsに、人間承認済み（2026-08-17）のH7/SV-22決着文言が残っていること、および未決着のOpen Questionが無い旨の記述が残っていること
4. `TestH7RegressionInvSedRangeUnchanged` — `INV-SED-09`〜`16`（KLK-015・H7の充足根拠）が全件`deny`のまま変更されていないこと
5. `TestSv22ReadmeAndDocstringAccuracyPreserved` — README.md／モジュールdocstringのsed w/Wホワイトリスト記述が維持され、ticket原案が求めていた「アドレス前置き形は未対応」という誤った注記が新設されていないこと
6. `TestPhase14And15MarkedComplete` — 設計書§4-8 Phase表のPhase 14・15行が「未実施」ではなく「完了」＋コミットハッシュ（`0a42478`／`e26fcf4`）を維持していること（SV-25）

## Quality Gate
pass（647件無変更のうえ12件追加・全659件OK。プロダクションコード変更なし・INV-SED-09〜16とREADME/docstringの無変更を確認済み）
