# KLK-018 実装詳細

> チケット本文の実装メモから参照される外部化ファイル。implementer作成。

## 1. Summary（詳細）

設計書 docs/designs/KLK-018.md §4-1〜§4-4 に従い、`.claude/hooks/guard_bash_writes.py`
へブレース展開・分断 glob の展開後判定を専用関数として新設し、既存の
`PATHISH_RE`／`guarded_paths`／`_is_guarded_path`／`is_guarded_token`／
`mentions_guarded` は無変更のまま、7箇所の既存呼び出しを OR 追加のみで
`_expanded` 版へ差し替えた（KLK-029 の `is_guarded_token_in_program` と同型の
安全側設計）。全3Phaseを設計書どおりのコミット粒度で実施し、
`python3 -m unittest discover -s tests -v` は668件全件パス
（baseline 659件 + 新規9件。INVENTORY_CASES 92件・LEGACY_DENY_COMMANDS 130件を
含む。既存226件は235件に増加）。

## 2. Files Changed（詳細）

- `.claude/hooks/guard_bash_writes.py`（Phase1）
  - import に `fnmatch` を追加
  - `PATHISH_RE` 定義直後に新規定数6個（`SHELL_EXPAND_PATHISH_RE`・
    `MAX_BRACE_DEPTH`・`MAX_BRACE_COMBINATIONS`・`GUARDED_DIR_NAMES`・
    `GUARDED_FILENAME`・`GLOB_META_CHARS`）を追加
  - `mentions_guarded()` の直後に新規関数7個
    （`_find_matching_brace`・`_split_top_level_commas`・
    `_brace_combination_count`・`expand_braces`・`_guarded_paths_from_expanded`・
    `guarded_paths_after_shell_expansion`・`is_guarded_token_expanded`・
    `mentions_guarded_expanded`。計8個、うち3個はプライベートヘルパ）を追加
  - 既存7呼び出し箇所を `_expanded` 版へ差し替え（設計書§4-2の1〜7と1対1対応。
    詳細は下記§3参照）
  - モジュール docstring「既知の限界」節のシェル展開パラグラフを更新
- `tests/test_guard_bash_writes.py`（Phase2）
  - `INVENTORY_CASES` の `INV-SH-07`・`INV-SH-09` を `allow`→`deny` へ変更し
    説明文言を更新（周辺コメント2箇所も「INV-SH-11のみが未対応」へ修正）
  - 新規テストメソッド9個を追加（AC1・AC2・AC4対応。詳細は下記§4参照）
- `.claude/hooks/README.md`（Phase3）
  - `guard_bash_writes.py` の行にある「既知の未対応」列挙からブレース展開・
    分断globの2例を除去し、パラメータ展開のみを未対応として残した
    （`INVENTORY_CASES` 参照も `INV-SH-11` のみへ更新）

## 3. 7呼び出し箇所の差し替え（設計書§4-2との対応）

1. `statement_violation`: `has_program_head` の両分岐に `mentions_guarded_expanded`
   をOR追加（True分岐は既存の `mentions_guarded_in_program` に加えてOR追加、
   False分岐は素の `mentions_guarded` を `mentions_guarded_expanded` へ置換）
2. `redirect_violation`: `is_guarded_token(resolved)` →
   `is_guarded_token_expanded(resolved)`
3. `guarded_write_target`: `is_guarded_token(target)` →
   `is_guarded_token_expanded(target)`（cwd結合分岐は無変更）
4. `degraded_violation`（関数レベルゲート）: `mentions_guarded(skeleton.split())` →
   `mentions_guarded_expanded(skeleton.split())`
5. `degraded_violation`（リテラルリダイレクト判定）:
   `is_guarded_token(target)` → `is_guarded_token_expanded(target)`
6. `degraded_violation`（ステートメント単位ゲート）:
   `mentions_guarded(w) for w in words_list` →
   `mentions_guarded_expanded(w) for w in words_list`
7. `subst_violation`（深追い打ち切り）: `is_guarded_token(inner)` →
   `is_guarded_token_expanded(inner)`

`record_assignments` の `is_guarded_token(value)`・KLK-029の
`mentions_guarded_in_program`／`guarded_paths_in_program` 自体・
`segment_violation` のsed degraded分岐にある `is_guarded_token(t)`
（`SED_WRITE_RE` 判定用。設計書7箇所に含まれない既存呼び出し）は、
設計書§4-2の除外方針どおり無変更。

## 4. 新規テストの内容（AC1・AC2・AC4対応）

- `test_klk018_brace_expansion_simple_deny`: 単純ブレース展開（AC1）
- `test_klk018_brace_expansion_direct_product_deny`: 直積（investigator実機検証と同型。AC1）
- `test_klk018_brace_expansion_nested_deny`: 入れ子（AC1）
- `test_klk018_brace_expansion_no_comma_stays_literal_allow`: カンマ無し `{word}` は非展開（AC1裏付け・AC4）
- `test_klk018_fragmented_glob_deny`: `*`・`?`・`[...]` の分断glob（AC2）
- `test_klk018_fragmented_glob_write_target_deny`: `sort -o` 経由（AC2 N3）
- `test_klk018_fragmented_glob_spec_side_read_allow`: 下記§5参照（AC2の逸脱記録）
- `test_klk018_degraded_mode_fragmented_glob_deny`: degraded modeでの対称性（AC2 N4）
- `test_klk018_erroneous_deny_budget_allow`: 誤deny予算の固定allow6件（AC4）

実機bash（WSL2）で `echo tickets/{acti,don}{ve,e}/APP-001.md` 等を実行し、
`expand_braces` の展開結果が実機argvと一致することをV-14型検証として確認済み
（bashの直積展開順序は実装と異なるが、生成される語の集合は完全一致）。

## 5. 設計書からの逸脱（要報告）

設計書§9 AC2は誤deny予算の固定allowケースの一つとして
`cat docs/SPEC*.md`（SPEC.md側）を**deny**として追加するよう指示しているが、
実装・実測の結果これは**常にallowのまま**であることを確認した。

理由: `cat` は `ALLOWED_HEADS` の中でも `segment_violation` に追加規則を
持たない読み取り専用headであり、`mentions_guarded_expanded` によって
言及ゲート（`gate_hit`）が真になっても、`segment_violation` の
`head not in ALLOWED_HEADS` 判定を通過し以降の分岐（sed/awk/sort/uniq/find/git
のいずれでもない）が全て素通りするため、最終的に `None`（allow）を返す。
これは既存の `test_read_commands_allow`（`cat tickets/active/APP-001.md`が
allow）と同型の、本チケット以前からの設計上の性質であり、KLK-018の
言及ゲート拡張（head単位の判定は変更しない）で覆るものではない。

対応: `test_klk018_fragmented_glob_spec_side_read_allow` として
`cat docs/SPEC*.md` が実際にallowのままであることを固定し、対照として
書き込み系headに差し替えた `rm docs/SPEC*.md` がdenyになることを併記した。
guarded_paths_after_shell_expansion自体がSPEC.md側のglobを正しく検出する
ことは `guard._guarded_paths_from_expanded` の単体確認（本実装作業中に
`python3` REPL相当のスクリプトで実測。結果は `['docs/SPEC.md']`）で確認済み
であり、アルゴリズム自体には問題が無い。orchestrator/reviewerへの申し送り
事項として明記する。

## 6. Remaining Risks（詳細）

- MAX_BRACE_DEPTH・MAX_BRACE_COMBINATIONSの上限到達時（コスト爆発の恐れが
  ある入力）は候補全体を無条件でguarded扱いにするフォールバックを実装したが、
  この分岐を実際に踏む入力（深いネスト・大量直積）の専用テストは追加して
  いない（設計書§6のリスク軽減策どおり実装したが、境界値テストはtester
  フェーズでの追加を推奨）。
- README.mdは着手時点でgit status上UU表示だったが、競合マーカーは無く
  Editツールでの編集・コミットに問題は無かった（設計書§4-3の懸念どおり）。
