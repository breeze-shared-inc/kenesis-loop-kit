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

**差し戻し対応（reviewer指摘・RecursionError修正。§7参照）:**
`_brace_combination_count`／`expand_braces` が非入れ子で隣接する
ブレース群の連続に対し Python コールスタックを消費し続け
`RecursionError`（main() の広域 except で allow へフェイルオープン）を
起こす欠陥を、事前チェック＋try/exceptの2段防御で修正した。修正後
`python3 -m unittest discover -s tests -v` は676件全件パス（差し戻し前
672件 + 新規回帰テスト4件）。

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

## 7. 差し戻し対応（reviewer Critical Issue・RecursionError修正）

### 7-1. 問題

`_brace_combination_count`（および`expand_braces`）は、ネスト（body）方向の
再帰でのみ `depth` 引数を進め、直積（suffix）方向の再帰では進めない
（`MAX_BRACE_DEPTH` は「ネストの深さ」であり「隣接するブレース群の個数」
ではないため）。したがって非入れ子で隣接するブレース群が大量に連続する
入力（`"a" + "{x,y}" * 2000 + "b"`）は `MAX_BRACE_DEPTH` の早期リターンに
到達せず、隣接数に比例した Python コールスタックを消費し続け
`RecursionError` になる（実測: 隣接997個・`sys.getrecursionlimit()=1000`）。
この `RecursionError` は `main()` の広域 `except Exception: allow()` に
捕捉され、deny 方向ではなく allow 方向へフェイルオープンする。同一コマンド
文字列中に大量の隣接ブレースを含めるだけで、既存の明確な deny 対象
（例: `rm tickets/active/APP-001.md`）ごと allow になりうる欠陥だった。

### 7-2. 修正内容

`.claude/hooks/guard_bash_writes.py` の `guarded_paths_after_shell_expansion`
に2段の防御を追加した（設計の大枠変更なし・実装レベルの修正）。

1. 新規定数 `MAX_BRACE_CHAR_COUNT = 50`（`{` 出現数の軽量な事前上限）を
   `MAX_BRACE_COMBINATIONS` の直後に追加。候補中の `{` 出現数がこれを
   超える場合、`_brace_combination_count`／`expand_braces` を一切呼ばずに
   既存の安全側フォールバック（候補全体を無条件に「保護対象パスの候補」と
   みなす）へ倒す（定数時間の判定で重い再帰への入口自体を塞ぐ）。
2. 防御第2層として、`_brace_combination_count(candidate)` と
   `expand_braces(candidate)` の呼び出しを個別に `try/except RecursionError`
   で囲み、例外発生時も同じ安全側フォールバックへ倒す（①をすり抜けた場合
   のバックストップ）。

いずれも既存の `MAX_BRACE_COMBINATIONS` 超過時と同じ deny 方向の分岐へ
合流するため新しい判定パスは増えない。`_brace_combination_count`・
`expand_braces`・`guarded_paths_after_shell_expansion` の各docstringに
今回の欠陥・修正・安全性主張を追記した（モジュールの既存ドキュメント文化
（P8型の安全性主張・「破れる形」記載）に合わせた）。

### 7-3. 対象外にした2件

reviewerが「ブロッカーではない」と明記し、かつarchitectの職務範囲である
以下2件は今回のコミットに含めていない（委譲プロンプトの指示どおり）。

- 設計書AC2の`cat docs/SPEC*.md`deny例示（実装のallowが正しく設計書の
  記述誤りと判断済み。§5に既存の申し送りあり）
- 設計書AC4のN1〜N4閉列挙とMAX_BRACE_*フォールバックの文言不整合

### 7-4. 追加テスト（tests/test_guard_bash_writes.py）

- `test_klk018_adjacent_braces_regression_n1000_denies_conservatively`:
  隣接1000個（実測閾値997をまたぐ規模）。`rm`と組み合わせてdeny
- `test_klk018_adjacent_braces_regression_n1500_denies_conservatively`:
  隣接1500個（申し送りの上限規模）でも同様にdeny
- `test_klk018_adjacent_braces_regression_allow_symmetry`: 同じ隣接1500個
  でも読み取り専用head（cat）・tickets/を含まない場合はallowのまま
  （deny側との対照）
- `test_klk018_adjacent_braces_regression_does_not_mask_existing_deny`:
  reviewer指摘の核心シナリオ。既存の明確なdeny対象
  （`rm tickets/active/APP-001.md`）と隣接1200個のブレースを同一コマンド
  文字列中に含めてもdenyのままであることを固定

いずれもサブプロセス経由（`tests/_util.run_script`）で実際のhookスクリプト
を起動する既存の`assertAllow`/`assertDeny`ヘルパを使用しており、修正前は
`RecursionError`が`main()`内で握りつぶされてstdoutが空になり
（`assertDeny`が失敗する形で）検出できる構成になっている。

### 7-5. 実機確認

`python3 .claude/hooks/guard_bash_writes.py` へ`"a" + "{x,y}"*2000 + "b"`を
含む`rm`コマンドのペイロードを直接投入し、修正前は`RecursionError`発生・
修正後は約33msでdeny判定が返ることを確認した。`_brace_combination_count`を
直接呼び出す形（事前チェックを経由しない形）は関数自体が非有界のままの
ため引き続き`RecursionError`を送出する（設計上想定どおり。呼び出し元
`guarded_paths_after_shell_expansion`だけが保護されていればよい契約）。

### 7-6. Remaining Risks（差し戻し対応分）

- `MAX_BRACE_CHAR_COUNT=50`は既存の固定テスト（隣接最大6個）を大きく
  上回り、RecursionErrorの実測閾値（隣接997個）を大きく下回る値として
  選定したが、閾値そのものの妥当性検証（誤deny予算への影響測定）は
  行っていない。将来的に隣接ブレースを50個超使う正当なユースケースが
  出た場合は安全側フォールバックに倒れるだけ（allowへの後退ではない）。
- `_brace_combination_count`・`expand_braces` 自体の非有界な再帰構造は
  温存した（呼び出し元での防御のみ）。関数単体を直接呼ぶ新しい呼び出し
  箇所を将来追加する場合は、本チケットの防御パターン（事前チェック＋
  try/except）を踏襲する必要がある。
