# KLK-031 テストレポート（tester）

## 1. 実行結果

- `python3 -m unittest discover -s tests -v`（worktree
  `/home/bzg55/workspace/breeze/kenesis-loop-kit.wt/KLK-031`、ブランチ
  `fix/KLK-031-fragmented-glob-spec-md-false-deny`）を実行。
- 実装直後（tester追加前）: 756件 Ran, OK（implementer報告値と一致）。
- tester追加後（4メソッド追加後）: **760件 Ran, OK**（失敗・エラー0件）。
- `python3 -m unittest tests.test_guard_bash_writes -k klk031 -v`:
  KLK-031関連11メソッド（implementer7＋tester4）すべて `ok`。

## 2. implementer新規テスト（7メソッド）のエッジケース網羅確認

設計書§9「テスト観点（tester向け）」(1)〜(6)との対応:

| # | エッジケース | 対応するimplementerテスト | 判定 |
|---|---|---|---|
| 1 | 孤立`*`単体 | `test_klk031_isolated_wildcard_component_allow`（`rm *`等7例） | 充足 |
| 2 | `dir/*`末尾`*`（"tickets/"を含まないディレクトリ名） | 同上（`rm build/*`） | 充足 |
| 3 | `**`・`*?`・`?*` | `test_klk031_multi_char_glob_only_component_allow` | 充足 |
| 4 | redirect_violation・guarded_write_target・degraded_violation経由 | `test_klk031_redirect_violation_allow`・`test_klk031_guarded_write_target_allow`・`test_klk031_degraded_violation_allow` | 充足 |
| 5 | `rm tickets/*`のGUARDED_DIR_NAMES側回帰ロック | `test_klk031_guarded_dir_names_side_unchanged_deny` | 充足 |
| 6 | 既存KLK-018固定ケース（`acti*e`・`activ?`・`activ[e]`・`SPEC*.md`） | `test_klk031_existing_klk018_fixed_cases_unaffected_deny` | 充足 |

7メソッド・19アサーションいずれも設計書§9の想定どおりの内容で、誤った向き
（allow化）を検出するテストは無い（全てdeny側の安全性を固定するか、無関係
コマンドのallowを固定するテスト）。

## 3. 呼び出し箇所の数の齟齬（8 vs 9）の検証

`grep -n "is_guarded_token_expanded\|mentions_guarded_expanded" .claude/hooks/guard_bash_writes.py`
で現存する呼び出し箇所（定義・docstring言及を除く実呼び出し）を関数単位で
洗い出した:

| 関数 | 呼び出し行 | 件数 |
|---|---|---|
| `guarded_write_target` | 1844 | 1 |
| `redirect_violation` | 2675 | 1 |
| `record_loop_binding`（KLK-019 forループ変数追跡） | 2909 | 1 |
| `statement_violation`（gate_hit算出2分岐） | 2943, 2945 | 2 |
| `degraded_violation`（関数レベルゲート・リテラルリダイレクト判定・ステートメント単位ゲート） | 3096, 3102, 3113 | 3 |
| `subst_violation` | 3146 | 1 |
| **合計** | | **9** |

設計書§4-1の「計8箇所」という数値は、本文が列挙する6シンボル
（`guarded_write_target`・`redirect_violation`・`record_loop_binding`・
`statement_violation`(2)・`degraded_violation`(3)・`subst_violation`）を
単純合算すると9になり、記述上の合算ミス（列挙漏れではない）と判断した。
implementerの実装レポート（`docs/reports/KLK-031/implementation.md`）も
同じ結論に至っている。

**実装当初、7メソッドは6シンボルのうち4つ
（`guarded_write_target`・`redirect_violation`・`degraded_violation`・
`statement_violation`（isolated wildcard/multi-char系の一般ケース経由))
のみを明示的に固定しており、`record_loop_binding`と`subst_violation`は
未カバーだった。** tester観点で以下を実機検証:

- `for f in *; do rm $f; done` → allow（`record_loop_binding`が孤立`*`で
  誤ってNAMEをguarded_loop_varsへ登録しないこと）
- `for f in tickets/*; do rm $f; done` → deny（"tickets/"文脈では引き続き
  正しく登録・deny）
- `echo $(echo $(echo $(rm *)))`（depth 3。MAX_SUBST_DEPTH到達時の
  `subst_violation`内`is_guarded_token_expanded(inner)`直呼び出し分岐） → allow
- `echo $(echo $(echo $(rm tickets/*)))` → deny

いずれも期待どおりであることをスクリプトで実機確認した上で、
`tests/test_guard_bash_writes.py`のKLK-031セクションへ4メソッド
（`test_klk031_record_loop_binding_allow`・
`test_klk031_record_loop_binding_tickets_context_deny`・
`test_klk031_subst_violation_deep_allow`・
`test_klk031_subst_violation_deep_tickets_context_deny`）として追加し、
9呼び出し箇所すべてに対応する経路をテストで固定した。

## 4. KLK-018固定ケースの回帰確認

`test_klk031_existing_klk018_fixed_cases_unaffected_deny`
（`rm tickets/acti*e/APP-001.md`・`rm tickets/activ?/APP-001.md`・
`rm tickets/activ[e]/APP-001.md`・`rm docs/SPEC*.md`）に加え、既存の
`test_klk018_fragmented_glob_deny`・
`test_klk018_fragmented_glob_write_target_deny`・
`test_klk018_fragmented_glob_spec_side_read_allow`・
`test_klk018_erroneous_deny_budget_allow`を含む全既存KLK-018系テストが
フルスイート実行で引き続きPASSしていることを確認した（回帰なし）。

## 5. 誤りの向きの再確認

`rm tickets/*`は本セクション追加テスト・implementerテストの両方でdeny
確認済み。孤立ワイルドカードのみの成分に対する修正は「SPEC.md側の判定候補
追加条件の限定」のみであり、GUARDED_DIR_NAMES側・`_is_guarded_path`・
`fnmatch.fnmatchcase`・`GLOB_META_CHARS`・`GUARDED_FILENAME`はいずれも
無変更（`git diff 66c8c43..7c04d9e -- .claude/hooks/guard_bash_writes.py`
でコード差分が単一箇所のロジック追加＋docstring3箇所のみであることを確認
済み）。allow方向への劣化は無い。
