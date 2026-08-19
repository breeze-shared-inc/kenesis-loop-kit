# KLK-032 テストレポート（tester）

対象コミット: Phase 1 `558ed28`／Phase 2 `4eb47a1`（ブランチ `fix/KLK-032-glob-spec-case-insensitive`）
検証者: tester（Quality Gate検証）
検証日: 2026-08-19

## 1. 実行結果（独立再実行）

```
$ python3 -m unittest discover -s tests -v
...
----------------------------------------------------------------------
Ran 792 tests in 28.479s

OK
```

implementer報告どおり792件全PASS（既存784＋新規8）。新規8件の内訳:
- `tests/test_guard_bash_writes.py`（KLK-032節、4件）:
  `test_klk032_lowercase_mixedcase_fragmented_glob_deny`,
  `test_klk032_spec_side_read_allow`,
  `test_klk032_guarded_paths_from_expanded_unit`,
  `test_klk032_case_closure_budget_deny`
- `tests/test_ticket_lib.py`（`is_spec_basename_fnmatch`単体、4件）:
  `test_is_spec_basename_fnmatch_case_insensitive_match`,
  `test_is_spec_basename_fnmatch_isolated_wildcard_true`,
  `test_is_spec_basename_fnmatch_non_match`,
  `test_is_spec_basename_fnmatch_non_str_returns_false`

いずれも `... ok` を個別に確認済み（`-v` ログをgrepして8件全件のPASSを確認）。

## 2. 受け入れ条件（設計書§9）との突き合わせ

- **AC1(a) unit**: `test_klk032_guarded_paths_from_expanded_unit` が
  `_guarded_paths_from_expanded('docs/sp*.md')` → `['docs/SPEC.md']`、
  `('docs/Spec*.md')` → `['docs/SPEC.md']` を実証。PASS。
- **AC1(b) end-to-end**: `test_klk032_lowercase_mixedcase_fragmented_glob_deny` が
  `rm docs/sp*.md`・`rm docs/Spec*.md`・degraded形
  `rm docs/sp*.md # don't` のdenyを実証。`test_klk032_spec_side_read_allow` が
  `cat docs/sp*.md` のallowを実証し、既存
  `test_klk018_fragmented_glob_spec_side_read_allow`（`cat docs/SPEC*.md`）との
  対称性を確認。両方PASS。
- **AC2**: KLK-018系 `test_klk018_fragmented_glob_spec_side_read_allow`、
  KLK-031系 `test_klk031_isolated_wildcard_component_allow`・
  `test_klk031_multi_char_glob_only_component_allow`・
  `test_klk031_guarded_dir_names_side_unchanged_deny`・
  `test_klk031_existing_klk018_fixed_cases_unaffected_deny` の5件を個別に
  grepで確認、全件PASS。回帰なし。
- **AC3**: `test_klk032_guarded_paths_from_expanded_unit` 内
  `_guarded_paths_from_expanded('tickets/ACTI*E/APP-001.md')` → `[]` を実証。
  GUARDED_DIR_NAMES側の大小区別維持を確認。PASS。
- **AC4**: 同テスト内 `_guarded_paths_from_expanded('*')` → `[]` を実証
  （KLK-031ゲート優先）。加えて `git diff develop -- .claude/hooks/guard_bash_writes.py`
  を確認し、KLK-031ゲート4項目
  （`has_literal_char = any(...)`／`if index == last_index and has_literal_char:`／
  `literals = literals + [GUARDED_FILENAME]`／直前のKLK-031コメントブロック）が
  diffの `+`/`-` 行に一切含まれず、コンテキスト行としてのみ出現することを確認
  （`has_literal_char = any` 定義行はhunk範囲外で無変更、他2行は変更hunk内の
  コンテキスト行として無変更）。バイト単位無変更を確認済み。

## 3. エッジケース・未カバー経路

設計書§9「テスト観点」列挙の新規ケース(1)〜(4)＋libヘルパー単体True/False系は、
実装済みテスト（Phase 2、implementer作成）がすべて設計書の例示メソッド名・
入力値と1:1で網羅している。tester独自の追加テストは不要と判断（詳細は
本レポート§2の突き合わせ結果）。

`_guarded_paths_from_expanded` の9呼び出し経路（investigation.md §3、
`find_violation` 配下: statement_violation／redirect_violation／
degraded_violation／guarded_write_target／record_loop_binding／
subst_violation 等）は、KLK-018系・KLK-031系の既存回帰テストが経路ごとの
allow/deny を個別にカバーしており、今回の変更は
`_guarded_paths_from_expanded` 内部の1箇所（比較分岐）に閉じているため
呼び出し経路側の追加テストは不要（設計書§5「単一集約ポイントの修正が
自動波及」）。

## 4. 回帰チェック

792件中、実装差分が触れた経路に関連する既存テスト（KLK-018系19件・
KLK-031系10件、grep実測）を個別に確認し全件PASS。実装前後でdeny→allowの
後退（劣化）が生じていないことを、設計書§7「マイグレーション戦略」の主張
（構造的にTrue→Falseの後退は発生しない）と実測結果の両面で確認。

## 5. Quality Gate判定

pass。全792件PASS、AC1〜AC4すべて対応するテストが存在しPASS、
KLK-031ゲート行の無変更をgit diffで確認、回帰なし。tester追加テストなし
（既存Phase2実装が設計書§9を充足済みのため）。
