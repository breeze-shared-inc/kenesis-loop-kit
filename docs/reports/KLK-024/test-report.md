# KLK-024 テストレポート（tester）

対応する設計書: `docs/designs/KLK-024.md`（§9 受け入れ条件・テスト観点）
対応する実装レポート: `docs/reports/KLK-024/implementation.md`

## 1. テスト実行結果

- `python3 -m unittest tests.test_guard_bash_writes -v` → **220件全件pass**（実装時219件＋tester追加1件）
- `test_legacy_deny_commands_all_still_deny` 単独実行 → pass（`LEGACY_DENY_COMMANDS` 130件、全件denyのまま回帰なし）
- `test_klk024_unescape_backtick_body_unit_boundary` 単独実行 → pass

## 2. AC1〜AC6 個別検証（テストコードを読んで確認）

- **AC1**: `test_klk024_escaped_nested_backtick_write_vector_deny`（T-KLK024a）がチケット再現手順1を`docs/SPEC.md`・`tickets/active/*.md`双方でdeny固定。テストコード確認済み、実行pass
- **AC2**: `test_klk024_contrast_dollar_paren_and_plain_backtick_deny`（T-KLK024b）が`$(echo \`rm...\`)`・`` `rm...` ``の対照2件をdeny固定。判定不変を確認
- **AC3**: `test_klk024_lone_escaped_backtick_false_deny_budget_allow`（T-KLK024e、単独`\``がallowのまま）・`test_klk024_readonly_backtick_substitution_regression_allow`（T-KLK024f）で誤deny予算を固定。列挙外の新規denyは全件実行（220件pass）で検出されず
- **AC4**: `test_legacy_deny_commands_all_still_deny`（130件）が全件pass。回帰なし
- **AC5**: 全220件pass（新規T-KLK024a〜f＋tester追加g）
- **AC6**: `test_klk024_degraded_path_shares_fix_deny`（T-KLK024d）を直接インストルメントして検証（下記4節）。degraded経路が本チケットの修正を共有していることを実機的に確認

## 3. Coverage Summary

- `_take_backtick`修正1箇所（正常経路`lex()`・degraded経路`_extract_degraded_substs`の両方から共有呼び出し）はT-KLK024a〜d・実測（下記）でカバー
- `_unescape_backtick_body`（純粋関数）: T-KLK024a〜fは全てhook経由のE2Eのみで、この関数を直接呼ぶ単体テストが**存在しなかった**（設計書§9末尾の指示「純粋関数のためモック不要、最低2形ずつ確認」が未充足）。testerが`test_klk024_unescape_backtick_body_unit_boundary`（T-KLK024g）を追加し、対象3種（`` \` ``・`\$`・`\\`）各2形＋対象外3種（`\;`・`\ `・`\`+改行）各2形、計12ケースを直接固定
- `_skip_backtick`/`_skip_balanced`/`find_violation`/`subst_violation`: 無変更のため既存219件でカバー継続

## 4. Failing Tests

なし（fail 0件）

## 5. Added Tests

- `tests/test_guard_bash_writes.py`: `test_klk024_unescape_backtick_body_unit_boundary`（T-KLK024g）を追加。`guard._unescape_backtick_body`を直接呼び出し、対象3種・対象外3種を計12ケース（各2形）で固定

## 6. Edge Cases Verified（tester独自検証・実装レポートの検証）

- **多段ネストの経路区別（設計依頼の3番）**: `guard.find_violation`を直接呼び出し、返却reasonを実測。depth2・3は`"'rm' は許可されていません"`（**genuineなhead検出**、MAX_SUBST_DEPTH未到達での実解釈）。depth4・5は`"深いコマンド置換の内側で保護対象パスに言及しています"`（**MAX_SUBST_DEPTH=3の保守的打ち切り**、`subst_violation`のdepth>=3分岐）。実装レポートの記述（「depth4・5はsubst_violationの既存の保守的深さ打ち切りでdeny」）と整合を実測で確認
- **degraded経路の実証（AC6）**: `test_klk024_degraded_path_shares_fix_deny`のコマンドを直接`guard.lex()`へ投入し`ValueError("no closing quotation")`を実測で確認（正常経路`lex()`は失敗し`degraded_violation`へフォールバックすることを確認、`find_violation`の最終reasonは`"'rm' は許可されていません"`）。正常経路が先に成功して実はdegraded分岐を通っていない、という誤りは無いことを確認
- **`_unescape_backtick_body`単体境界**: 対象3種・対象外3種を各2形、計12ケースをtester追加テストで直接固定（上記5節）

## 7. Regression Risks

- `_take_backtick`は`lex()`・`_extract_degraded_substs`双方から共有呼び出しされるが、両呼び出し箇所とも本チケットの修正1箇所で同時にカバーされることをAC6検証で実測済み。呼び出し箇所以外への影響なし
- `LEGACY_DENY_COMMANDS`（130件）・既存バッククォート読み取り専用テスト・既存の行継続テスト（`\`+改行を含む既存テスト、`_unescape_backtick_body`のno-op経路を偶然カバーしていた）全て回帰なし
- 設計書R3で分析済みの2ケース（`\`+改行を含み閉じたバッククォート・末尾`\``が対で消費され`ValueError`になるケース）は既存テストのまま変更なし、実行結果でも回帰なし

## 8. Quality Gate Status

**pass**
