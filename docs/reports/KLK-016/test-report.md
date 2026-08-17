# KLK-016 テストレポート

生成: tester / 最終更新: 2026-08-17

## 1. 全体テスト実行結果

```
$ python3 -m unittest discover -s tests -v
Ran 644 tests in 22.934s
OK
```

内訳: 既存639件（implementer実装完了時点） + tester追加5件（`tests/test_ticket_lib.py`
`TestSpecDriftPureFunctions`）= 644件、全件pass。失敗・エラーなし。

## 2. リグレッション確認（個別サブセット実行）

implementerが変更したhookに対応する既存テストファイルを単独でも再実行し、無改変で
全件passすることを確認した（設計書§9(b)の指示）。

```
$ python3 -m unittest tests.test_metrics tests.test_loop_integrity \
    tests.test_guard_spec_writes tests.test_guard_bash_writes -v
Ran 283 tests in 24.146s
OK
```

`git diff --stat` で `tests/test_metrics.py` / `tests/test_loop_integrity.py` /
`tests/test_guard_spec_writes.py` / `tests/test_guard_bash_writes.py` はいずれも
無変更（diffなし）であることを確認済み（tester変更は`tests/test_ticket_lib.py`のみ）。

## 3. 新設統合テスト（implementer作成分）の再実行

```
$ python3 -m unittest tests.test_ticket_lib tests.test_spec_drift -v
Ran 88 tests in 0.525s
OK
```

`tests/test_spec_drift.py`（10ケース: `TestSpecStateRecording` 4件 +
`TestSpecDriftDetection` 6件）はいずれもtempdir上に実ファイルを生成しサブプロセス
起動で検証する統合テストスタイルで、全件pass。

## 4. tester追加テスト（純粋関数の単体境界）

設計書§9「単体境界テスト（純粋関数）について」・implementer実装メモ末尾で明示され、
`tests/test_spec_drift.py`（統合テスト）ではカバーされていなかった3観点を
`tests/test_ticket_lib.py::TestSpecDriftPureFunctions`（5テスト）として追加した。
`tests/test_ticket_lib.py`は既存の`_ticket_lib.py`単体テスト置き場であり、
`lib.sha256_file`/`lib.is_project_spec`/`lib.load_spec_state`をモックなしで直接
呼び出し、fail-open分岐の根拠をtest_spec_drift.pyとは独立に固定する。

- `test_sha256_file_missing_path_returns_none`: 存在しないパスで`None`
- `test_is_project_spec_nested_spec_is_false`: `docs/foo/SPEC.md`（絶対・相対とも）で`False`
- `test_is_project_spec_root_spec_is_true`: 対照ケース。プロジェクト直下（絶対・相対とも）で`True`
- `test_load_spec_state_broken_json_returns_none`: 壊れたJSON文字列で`None`
- `test_load_spec_state_non_dict_returns_none`: 有効なJSONだが非dict（リスト）で`None`

プロダクションコード（`.claude/hooks/`配下）は変更していない。

## 5. AC1〜AC6 個別検証状況

| AC | 検証テスト | 結果 |
|---|---|---|
| AC1 | `test_spec_drift.py::TestSpecDriftDetection::test_bash_edit_without_write_tool_blocks`・`test_full_cycle_record_then_legit_edit_then_drift` | block・reasonに"docs/SPEC.md"を含むことを確認。pass |
| AC2 | 同`test_matching_hash_allows`・`test_legit_write_then_edit_does_not_false_positive` | 正規経路後はblockしないことを確認。pass |
| AC3 | 同`test_no_spec_file_allows`・`test_spec_without_state_allows` | いずれもexit 0・無出力（fail-open）。pass |
| AC4 | 設計書§3 D1（選択理由記載済み）+ `.gitignore`3ファイルへ`docs/.spec_state.json`追加（grep確認済み）+ `TestSpecDriftPureFunctions`（fail-open境界の単体確認） | 記載・実装とも確認 |
| AC5 | `.claude/hooks/README.md`のhook一覧表2行・「メトリクスの運用」節2行を grep で確認（L9,10,19,20） | 追記内容がPhase1/2実装（プロジェクト直下限定・fail-open条件）と一致 |
| AC6 | `python3 -m unittest discover -s tests -v` 644件全pass | pass |

## 6. 手動確認不可の範囲について

設計書§9(c)のとおり、本リポジトリには`docs/SPEC.md`が存在しないため実SPEC.mdが
存在するプロジェクトでの実機動作確認はできない。tempdir上のunittest（10+5=15件）が
検証手段のすべてであることをimplementer実装メモと合わせて確認した。
