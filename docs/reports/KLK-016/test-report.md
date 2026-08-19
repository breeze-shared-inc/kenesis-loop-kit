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

---

## 改訂: 改善ループ・フォローアップ対応（第2版・2026-08-17）

reviewer承認時のフォローアップ3件（AC-F1〜AC-F3、設計書第2版§9）に対するimplementer
実装（Phase F1: コミットd05b8ee／Phase F2: コミット1e54088）を独立に再検証した。
worktree `../kenesis-loop-kit.wt/KLK-016`・ブランチ`feature/KLK-016-spec-drift-detection`
上で実施（新規ブランチは作成せず）。

### 6-1. 全件再実行

```
$ python3 -m unittest discover -s tests -v
Ran 662 tests in 27.657s
OK
```

orchestratorが事前に確認した662件全passを独立実行で再確認した。失敗・エラーなし。
`tests/test_spec_drift.py`（13件。既存10件＋フォローアップ新規3件）・
`tests/test_loop_integrity.py`（27件・無改変）・`tests/test_metrics.py`（20件・無改変）を
個別サブセットでも再実行し（`python3 -m unittest tests.test_spec_drift
tests.test_loop_integrity tests.test_metrics -v`）60件全passを確認（全件実行との
非依存性・順序非依存性の確認）。

### 6-2. AC-F1〜AC-F3の検証内容の妥当性確認

`docs/designs/KLK-016.md`§4-7（`check_loop_integrity.py`実装）・§4-8（テスト追加）を
`git diff develop...HEAD`で対比し、一意な引用文字列どおりに適用されていることを確認した。

- **AC-F1**（tickets/active非依存で`check_spec_drift`が実行される）:
  `TestSpecDriftIndependentOfTicketsDir`の2ケースはいずれも`setUp`で`tickets/active`を
  作成せず、テスト内で`assertFalse(os.path.isdir(...))`により不在を明示している。
  `test_matching_hash_allows_without_tickets_active_dir`（fail-open側）単体では
  「呼ばれて[]を返した」のか「呼ばれなかった」のかを区別できないが、
  `test_bash_edit_detected_without_tickets_active_dir`（block検出側）が同じ
  tickets/active不在の条件下でblockを要求するため、2ケースの組み合わせで
  「tickets/active不在でも`check_spec_drift`が実際に実行される」ことを実証できている
  （呼ばれていなければ後者はblockできない）。AC-F1は充足していると判断する。
- **AC-F2**（tickets/active不在＋Bash相当改変の同時発生でblockしreasonに
  "docs/SPEC.md"を含む）: `test_bash_edit_detected_without_tickets_active_dir`が
  `assertEqual(out.get("decision"), "block")`・`assertIn("docs/SPEC.md",
  out.get("reason", ""))`の両方を検証しており、そのままAC-F2の文言と一致する。
- **AC-F3**（`is_project_spec`の相対パス分岐の統合テスト）:
  `is_project_spec`の実装（`.claude/hooks/_ticket_lib.py`）を確認し、絶対形は
  `_normalize_path`で正規化して`spec_path_for(cwd)`と比較する分岐、相対形は
  文字列`"docs/SPEC.md"`そのものとの一致のみを認める分岐、の2分岐があることを
  確認した。既存の`test_records_hash_on_spec_write`は`_util.write_spec`が返す
  絶対パスを使うため絶対形分岐しか経由しない。新設
  `test_records_hash_with_relative_file_path`は`tool_input.file_path`に文字列
  `"docs/SPEC.md"`（相対）を直接指定しており、これまで統合テストで経由していな
  かった相対形分岐を`record_metrics.py`サブプロセス経由で実際に検証している
  （タウトロジーではない — `_util.spec_hash`は実装のsha256_fileを呼ばず独立算出）。
  AC-F3は充足していると判断する。

### 6-3. `check_loop_integrity.py`既存ロジックへの影響確認（`git diff`）

`git diff develop...HEAD -- .claude/hooks/check_loop_integrity.py`を確認した。
`check_ticket`・`check_done_ticket_drift`の関数定義自体は差分に一切現れず
（`main()`とモジュールdocstringのみが差分対象）、変更は次の2点に限定されている:
(1) `problems.extend(check_spec_drift(cwd))`を`tickets/active`存在チェックより前へ
移動、(2) 既存の`events_by_ticket`/`state`計算・`check_ticket`/`check_done_ticket_drift`
呼び出しループを`if os.path.isdir(active_dir):`ブロックでそのまま包んだのみ（呼び出し
順序・引数は無変更）。設計書§4-7「既存ロジックは1行も書き換えない」という記述と
実装が一致していることを確認した。

### 6-4. 回帰確認（`tests/test_loop_integrity.py`）

`git diff develop...HEAD -- tests/test_loop_integrity.py`は0行（差分なし）であることを
確認した。無改変のまま27件全passであり、Phase F1の呼び出し順序変更が既存の
`check_ticket`/`check_done_ticket_drift`検証（done/ドリフト検知・schema・blocker・
本文同期・L3差し戻し照合を含む）に一切回帰を出していないことを実証している。
`tests/test_metrics.py`も同様に差分0行・全件pass（既存ticket記録ロジックへの回帰なし）。

### 6-5. テスト追加について

AC-F1〜AC-F3はいずれもimplementer実装（Phase F2、コミット1e54088）の
`tests/test_spec_drift.py`既存3ケースで充足しており、tester独自のテスト追加は
不要と判断した（本節6-2で妥当性を個別に確認済み）。プロダクションコード
（`.claude/hooks/`配下）への変更は行っていない。
