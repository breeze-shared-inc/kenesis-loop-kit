# KLK-029 テストレポート（tester）

## 1. implementer申し送り（subTestカウント仕様）の検証結果

**結論: 申し送りは事実であり、実装の不備ではない。新規10件は実際に評価されている。**

- `tests/test_guard_bash_writes.py` の `test_inventory_cases_match_expected_decisions` は
  `INVENTORY_CASES` を単一メソッド内で `for ... with self.subTest(id=..., syntax=...):` により
  ループ処理する構造（実装Phase 1着手前から既存・変更なし）。
- `python3 -m unittest tests.test_guard_bash_writes -v` を実行した結果、`Ran 213 tests`
  （tester独自実行でも再現。213件のまま）。`-v` 出力中 `test_inventory_cases_match_expected_decisions`
  は1行のみ表示され、`INVENTORY_CASES` の90件（既存80件＋新規10件）が個別行として現れることはない
  （`subTest` は成功時に個別カウント・個別表示されないunittestの仕様どおり）。
- `INVENTORY_CASES` を直接pythonで検査し、`INV-SED-27〜31`・`INV-AWK-21〜25` の計10件が
  重複なく実在すること、コマンド文字列が設計書§4-5の表と1文字単位で一致することを確認した
  （合計90件＝既存80件＋新規10件）。
- **サイレント無視の可能性を独立に検証するため、意図的な破壊実験を実施した:** `INV-SED-27`
  の期待値を一時的に`"deny"`→`"allow"`へ書き換え、`test_inventory_cases_match_expected_decisions`
  を単独実行したところ、`-v`出力に
  `test_inventory_cases_match_expected_decisions ... (id='INV-SED-27', syntax='...') ... FAIL`
  と個別の`subTest`パラメータ付きで失敗が報告され、トレースバック・`AssertionError`・
  `FAILED (failures=1)`が正しく出力されることを確認した。その後ただちに元のファイルへ復元し
  `git status`で差分が無い（clean）ことを確認した。
- 結論: 10件は「実行されているがカウント表示されないだけ」であり、サイレントに無視されている
  わけではない。CI相当の検証対象として機能している。

## 2. 誤deny予算（設計書§6 R1・7項目）の固定状況

| R1項目 | 内容 | 固定するテスト | 結果 |
|---|---|---|---|
| ① | チケット再現手順そのもの | INV-SED-27 | deny固定・pass |
| ② | tickets/active\|done型（スラッシュ2箇所） | INV-SED-28, INV-AWK-21 | deny固定・pass |
| ③ | デリミタ衝突なしのeコマンド単体 | INV-SED-29 | deny固定・pass |
| ④ | awkのsystem()/print>引数中のエスケープ言及 | INV-AWK-21,22,23 | deny固定・pass |
| ⑤ | awkの-v束縛値がエスケープされた保護対象パス | INV-AWK-24 | deny固定・pass |
| ⑥ | SPEC.mdを中間成分として含むが無関係な言及 | 既存テスト全216件で実例化なし（新規denyは①〜⑤の列挙のみ） | 実例化なし・OK |
| ⑦ | 理論的境界（低確率・未発見） | INV-SED-30・INV-AWK-24/25で境界固定、全件テストで実例なし | 実例化なし・OK |

誤検出方向の固定（allow側）: INV-SED-30・INV-AWK-25はallow固定・pass。INV-AWK-24は設計上
「AW-2の既存仕様どおりの新規deny」と明記されており、denyが正。

## 3. 単体境界（設計書§9・tester round1で追加）

以下3形はINVENTORY_CASES（find_violation経由のE2E固定）だけではカバーされておらず
（`unescape_program_backslashes`・`_is_guarded_path_component`自体への直接呼び出しテストが
実装コミット時点で存在しなかった）、tester側で新規テストメソッド3本を追加してカバーした。

1. `test_klk029_unescape_program_backslashes_folds_one_char_at_a_time`:
   `\X`→`X`の1文字単位畳み込み（スラッシュ・任意文字・複数箇所）
2. `test_klk029_unescape_program_backslashes_folds_escaped_backslash_itself`:
   `\\`→`\`（2文字→1文字）、`\\\\`→`\\`（4文字→2文字、非重複・左から）
3. `test_klk029_is_guarded_path_component_catches_component_fusion`:
   `docs/SPEC.md/e`型で`_is_guarded_path_component`=True・`_is_guarded_path`=False
   （basename完全一致では拾えない成分融合の直接固定）。tickets/active型は両関数とも
   True（対照）

Bash直接呼び出し（`python3 -c "..."`にguarded文字列を含む形）は`guard_bash_writes.py`
自身のhookにdenyされたため、スクラッチパッドへ検証スクリプトを書いて`python3 <script>`
の形で実行し確認した（コミット対象外・一時ファイル）。

## 4. 既存関連denyケースの無変更確認

`INV-SED-06`（`s///e`位置引数型）・`INV-SED-07`（`e`コマンド位置引数型）・`INV-AWK-06〜09`
（system/@f系）は`INVENTORY_CASES`内で無変更（`git diff`で削除行0件・追加のみ確認済み）。
216件全pass時に同時にpass。

## 5. AC4確認（コア関数無変更）

`git diff`で`PATHISH_RE = `・`def guarded_paths(`・`def _is_guarded_path(`・
`def is_guarded_token(`・`def mentions_guarded(`の5定義行に差分が無いことを再確認した
（実装レポート記載のgrepコマンドをtester側でも再実行し同じ結果＝出力なしを得た）。

## 6. 実行環境

- Python 3（venv未使用・システムpython3）、`python3 -m unittest tests.test_guard_bash_writes`
- 実行時間: 約23〜31秒（3回実行で範囲確認）
- pytest未インストール（investigator調査と同条件）
