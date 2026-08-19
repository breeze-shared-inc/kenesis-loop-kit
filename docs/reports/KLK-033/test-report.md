# KLK-033 テスト詳細

> testerレポートの詳細。チケット本文の「テストメモ (tester)」には要点5行＋本ファイルへの
> ポインタのみを残す（orchestratorが反映）。
> 検証日: 2026-08-19 / worktree: `../kenesis-loop-kit.wt/KLK-033/`
> ブランチ: `fix/KLK-033-negated-class-glob-pathish-fragmentation`

## 1. 全体テスト実行結果（申告の実測再現）

```
$ python3 -m unittest discover -s tests -p "test_*.py"
Ran 814 tests ... OK   （tester追加テスト4件を加える前。implementer申告どおり）

$ python3 -m unittest discover -s tests -p "test_*.py"   （tester追加テスト4件を含む）
Ran 818 tests ... OK   （FAIL/ERROR 0件）
```
implementer申告「814件PASS（baseline 805＋新規9・回帰0）」を自分の実行で再現し一致を確認した。
差分なし。標準エラーに出た `batch_loop.py: error: ...` 系メッセージ・`ResourceWarning`
（`test_check_spec_structure.py`）はテスト内で意図的に検証しているCLI引数エラー出力／
既存の無関係な警告であり、`unittest` の結果自体は `OK`（FAIL/ERROR 0）である。

## 2. 受け入れ条件（チケット4件・設計§9 AC1〜AC4）とテストの対応表

| 受け入れ条件 | 対応するテストメソッド | 結果 |
|---|---|---|
| AC1(a) unit: 候補抽出が1トークンに保たれ `_guarded_paths_from_expanded` がSPEC.mdを検出 | `tests.test_guard_bash_writes.test_klk033_pathish_and_expanded_unit` | PASS |
| AC1(b) end-to-end deny（`[!x]`・和集合形が必要な`[!s]`） | `tests.test_guard_bash_writes.test_klk033_negated_class_glob_deny` | PASS |
| AC1(c) 読み取りhead対称性（正常経路・`cat`） | `tests.test_guard_bash_writes.test_klk033_negated_class_spec_side_read_allow` | PASS |
| AC1(d) degraded経路deny | `tests.test_guard_bash_writes.test_klk033_degraded_negated_class_deny` | PASS |
| AC1(d)対称・degraded読み取りhead（設計§9③「任意」項目。tester実測固定） | `tests.test_guard_bash_writes.test_klk033_degraded_negated_class_spec_side_read_allow`（tester追加） | PASS |
| AC2 既存全件回帰なし（KLK-018/031/032系・`test_is_spec_basename_fnmatch_*`4件） | discover全818件＋個別grep確認（§3参照） | PASS |
| AC3 ヘルパー単体（非単調性の是正を固定） | `tests.test_ticket_lib.test_is_spec_basename_fnmatch_negated_class_monotonic_true` / `_excluded_false` | PASS |
| AC3 end-to-end（AC1(b)(c)(d)と同一） | 上記AC1行と同じ | PASS |
| AC4 誤deny予算（独立語・非独立語の`!`含み語） | `tests.test_guard_bash_writes.test_klk033_bang_words_unchanged_allow` | PASS |
| AC4 degraded側誤deny予算 | `tests.test_guard_bash_writes.test_klk033_degraded_bang_word_allow` | PASS |
| AC4 ブレース展開コスト会計 | `tests.test_guard_bash_writes.test_klk033_brace_cost_with_bang_allow` | PASS |
| AC4 GUARDED_DIR_NAMES側の新規deny確認（tester追加・§4参照） | `tests.test_guard_bash_writes.test_klk033_negated_class_guarded_dir_side_deny` | PASS |
| AC4 GUARDED_DIR_NAMES側の誤deny予算（対照・非一致） | `tests.test_guard_bash_writes.test_klk033_negated_class_guarded_dir_side_non_match_allow` | PASS |
| AC4 ブラケット無しの`!`部分割り込みが誤denyにならないこと | `tests.test_guard_bash_writes.test_klk033_bang_adjacent_guarded_dir_literal_allow` | PASS |

4条件すべてに対応するテストが実在し、全件PASSしていることを確認した。

## 3. AC2個別確認（設計§9AC2が名指しした既存メソッド）

個別に `-v` 実行してPASSを確認:
- KLK-018系: `test_klk018_fragmented_glob_spec_side_read_allow`、
  `test_klk018_adjacent_braces_regression_*`（設計書AC2の表記
  `_recursion_regression_*` はメソッド名の言い回しの揺れであり、実体は
  `test_klk018_adjacent_braces_regression_{allow_symmetry, n1000_denies_conservatively,
  n1500_denies_conservatively, does_not_mask_existing_deny, does_not_mask_existing_deny_blob_first,
  no_comma_literal_denies_conservatively}` の6件。全件ok）、
  `test_klk018_brace_depth_within_limit_allow`／`_exceeded_denies_conservatively`、
  `test_klk018_brace_combinations_within_limit_allow`／`_exceeded_denies_conservatively`
- KLK-031系: `test_klk031_isolated_wildcard_component_allow`、
  `test_klk031_multi_char_glob_only_component_allow`、
  `test_klk031_guarded_dir_names_side_unchanged_deny`、
  `test_klk031_existing_klk018_fixed_cases_unaffected_deny`、
  `test_klk031_degraded_violation_allow`
- KLK-032系4件: `test_klk032_lowercase_mixedcase_fragmented_glob_deny`、
  `test_klk032_spec_side_read_allow`、`test_klk032_guarded_paths_from_expanded_unit`、
  `test_klk032_case_closure_budget_deny`
- `tests/test_ticket_lib.py` の `test_is_spec_basename_fnmatch_*` 4件
全件 `ok`。既存メソッドはimplementerの申告どおり1行も変更されていない（`git diff` で
削除行0件を確認、§6参照）。

## 4. 設計§9③「任意」ケースの実測固定（degraded読み取りhead対称性）

implementerは設計の指示（期待値を事前に断定しない）に従い意図的に未実装とし、tester側へ
実測固定を委任していた。tester側で確認手順:
1. 一時プローブメソッドを `tests/test_guard_bash_writes.py` へ追加し
   `run_guard(payload("cat docs/[!x]PEC.md # don't"))` を実行、結果を `print` で確認。
2. 実測値: `None`（＝allow）。KLK-018/KLK-032が確立した「読み取り専用headは言及ゲートが
   立っても最終判定はallow」という既存設計からの**逸脱なし**（正常経路と対称）。
3. プローブを `test_klk033_degraded_negated_class_spec_side_read_allow`
   （`self.assertAllow("cat docs/[!x]PEC.md # don't")`）として恒久化しコミット対象に含めた。

結論: degraded側の読み取りhead対称性はallowであり、KLK-018/KLK-032の既存設計を維持している。
既存設計からの逸脱は検出されなかった。

## 5. implementerの無変更申告の検証

`git diff 419ac1b..HEAD -- .claude/hooks/guard_bash_writes.py .claude/hooks/_ticket_lib.py` を
精査した結果:
- 実コード変更は `SHELL_EXPAND_PATHISH_RE` の正規表現1行（`!` 追加）と
  `is_spec_basename_fnmatch` の判定式2行のみ。
- `GLOB_META_CHARS = frozenset` / `has_literal_char` / `fnmatchcase(literal, component)` /
  `GUARDED_DIR_NAMES` の各行に対する変更は0件（grep -c で確認）。ヒットした2件は
  いずれも新規追加された**コメント／docstring本文**中の言及（「GLOB_META_CHARS は無変更」
  という説明文）であり、定義・ロジック自体への変更ではないことを目視でも確認した。
- `tests/test_guard_bash_writes.py`・`tests/test_ticket_lib.py` の既存テストメソッドは
  `git diff` の削除行（`^-`、ヘッダ行除く）が実装コミット時点で0件（純追加のみ）。
  tester追加分もあわせて純追加のみ（§6参照）で、既存テストの弱体化・書き換えは無い。

## 6. tester追加テスト（差分の全量）

`git diff --stat` で `tests/test_guard_bash_writes.py` のみ38行純追加（削除0）。内訳:
1. `test_klk033_degraded_negated_class_spec_side_read_allow`（設計§9③の任意ケース実測固定）
2. `test_klk033_negated_class_guarded_dir_side_deny`（`rm tickets/[!x]ctive/APP-001.md` が
   deny になることを固定。設計・implementerテストはSPEC.md側のみを固定しており
   GUARDED_DIR_NAMES＝tickets/active・tickets/done側の否定文字クラスは未固定だったため追加。
   同一の`SHELL_EXPAND_PATHISH_RE`修正が波及することをbash意味論どおり実測確認）
3. `test_klk033_negated_class_guarded_dir_side_non_match_allow`（対照。`[!d]one` は
   bashでも`done`に不一致のためallowのまま。無条件denyでないことの固定）
4. `test_klk033_bang_adjacent_guarded_dir_literal_allow`（`activ!e`・`don!e` のような
   ブラケット無しの部分割り込みが誤denyにならないことの固定）

## 7. 機密情報スキャン

`git diff` に対し `api_key`／`password`／`secret`／`token`／接続文字列／秘密鍵ヘッダ等の
パターンをスキャンし0件。
