# KLK-020 テスト報告（tester）

tester.md の Required Output Format に基づく詳細外部化ファイル。チケット本文・レポートには要点＋本ファイルへのポインタのみを残す。

## 1. 実行結果

- `cd /home/bzg55/workspace/breeze/kenesis-loop-kit.wt/KLK-020 && python3 -m unittest discover -s tests` を実行。
- tester追加テスト前（implementer実装済み時点）: **757件 OK**（failures/errors 0）。実装報告の内訳（既存736 + Phase1追加19 + Phase2追加2）と一致。
- tester追加後（本レポート§3の3件を追加）: **760件 OK**（failures/errors 0）。
- 標準エラーに `batch_loop.py: error: --max-budget-usd は正の値を指定してください` 等が出力されるが、これは既存の異常系CLIテストが意図的に不正引数を渡して検証しているものであり、テスト結果自体は `OK`（既存の仕様、KLK-020の変更範囲外）。

## 2. AC別の確認結果

- **AC1(a)**: `guard_spec_writes` 側は `tests/test_guard_spec_writes.py` の `test_lowercase_spec_ask`/`test_mixed_case_spec_ask`/`test_uppercase_ext_spec_ask`/`test_random_mixed_case_spec_ask` で `spec.md`/`Spec.md`/`SPEC.MD`/`SpEc.Md` が `ask` になることを実証済み。`guard_bash_writes` 側は `test_klk020_lowercase_spec_redirect_denies_end_to_end` でリダイレクト経由の `deny` を実証済み。両経路とも人間承認ゲートを通ることを確認 — 充足。
- **AC1(b)**: `_ticket_lib.is_ticket` のdocstring・`guard_bash_writes.py` モジュールdocstラング双方にKLK-020参照の更新あり（コード確認済み）。pinningテスト `test_klk020_is_ticket_vs_is_guarded_token_asymmetry_pinning`（`mytickets/active/APP-001.md` で False/True/True の非対称固定）・`test_klk020_is_ticket_vs_is_guarded_token_relative_paths_converged`（KLK-012収束ケースの回帰）ともに存在し、KLK-010 D2・KLK-020参照コメント付き — 充足。
- **AC2**: 上記760件全件PASS（実測） — 充足。
- **AC3**: `is_spec_basename` 経由での一本化を4箇所（`is_spec`／`_is_guarded_path`／`_is_guarded_path_component`／`is_project_spec`）すべてでコード確認済み。各ファイルにcase-insensitive化テストあり（`test_guard_spec_writes.py` 4件・`test_guard_bash_writes.py` 6件・`test_ticket_lib.py` 6件）。`.claude/`配下除外・非`.md`拡張子・`SPEC_TEMPLATE.md`・ネスト除外の回帰確認テストも存在 — 充足。
- **AC4**: 設計書§3 D2にKLK-010 D2根拠3点の再評価（1件解消・2件再確認）が記録済み。「意図的な不統一を維持する」との判断が明示され、pinningテストも上記のとおり存在 — 充足。
- **AC5**: `.claude/hooks/README.md`「ルールを変更するとき」に既存3ステップ直後の1段落addendumを確認（状態機械定数専用・パス判定関数への非適用・棚卸し手順の3点）。設計書§4記載の文面と一致。全件テストPASS — 充足。

## 3. is_project_spec 実装形の追加検証（申し送り対応）

implementerの申し送り（設計書§4コード例と異なる `rpartition("/")` 分解形を採用）を受け、`tests/test_ticket_lib.py` の `TestSpecDriftPureFunctions` へ3件のエッジケーステストを追加してコードの制約充足を実証した。

- `test_is_project_spec_different_project_absolute_docs_not_matched`: 絶対形の別プロジェクト `docs/SPEC.md`（`/other/project/docs/SPEC.md`, cwd=`/repo`）が `n_dir=="docs"` という相対専用ショートカットに誤って引っかからず False になることを確認（cross-project誤検知が無いこと）。
- `test_is_project_spec_relative_nested_docs_suffix_not_matched`: `sub/docs/SPEC.md` が `n_dir` の完全一致（"docs"）ではなく末尾一致で誤ってTrueにならないことを確認（`rpartition`分解が完全一致判定であることの実証）。
- `test_is_project_spec_absolute_form_requires_exact_target_dir`: 同一basenameでも cwd が異なれば絶対形は一致しないこと（target_dir完全一致要求）を確認。

いずれもPASS。既存の `test_is_project_spec_directory_case_still_sensitive`（ディレクトリ部分の大小区別維持）・`test_is_project_spec_nested_spec_case_insensitive_still_false`（KLK-016 D3ネスト除外の維持）と合わせ、implementerの実装形が設計書の制約（ディレクトリ部分の大小区別維持・ネスト除外を壊さない）を満たすことを実測で裏付けた。

## 4. Phase1スコープ拡大（4箇所）の充足確認

- `is_spec`（guard_spec_writes.py）・`_is_guarded_path`（guard_bash_writes.py）・`_is_guarded_path_component`（guard_bash_writes.py、sed/awk専用）・`is_project_spec`（_ticket_lib.py）の4箇所すべてに `lib.is_spec_basename` 経由の実装とテストがあることをコード確認・テスト実行の両面で確認した（§2 AC3参照）。

## 5. Regression Risks

- 追加した3件のテストは既存の `is_project_spec` 呼び出し（`record_metrics.py`）の挙動には影響しない（読み取り専用の検証テストであり、プロダクションコードは変更していない）。
- 生成ずみの `.spec_state.json` 等サイドカーへの影響なし（テスト実行はtempfileベースの既存テストのみに依存し新規サイドカーは生成していない）。
