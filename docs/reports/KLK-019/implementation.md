# KLK-019 実装詳細

> チケット本文の実装メモから参照される外部化ファイル。implementer作成。

## 1. Summary（詳細）

設計書 docs/designs/KLK-019.md §4 に従い、`.claude/hooks/guard_bash_writes.py`
へ制御構文（for/while/until/if/elif/do/then/else/case）の先頭キーワードを
再帰的に剥がす機構（`strip_control_prefix`・`_strip_case_clause`・
`_parse_for_header`・`control_stripped_segments`）と、ループ変数経由の
書き込み検出機構（`guarded_loop_vars`・`record_loop_binding`・
`mentions_guarded_var`）を新設した。`ALLOWED_HEADS`/`CWD_SAFE_HEADS` は
一切変更していない（§3方針1）。Phase1・Phase2は設計どおり連続実装し、
コミットはPhase単位で分けた。Phase3でINV-CTRL-*・専用回帰テスト・AC6誤deny
予算固定テストを追加し、V-14をscratchpadで実施した。

`python3 -m unittest discover -s tests -v` は**726件全件パス**
（`tests/test_guard_bash_writes.py`単体は259件: 既存245件 + 新規
`test_klk019_*` 14件。`LEGACY_DENY_COMMANDS`は130件、`INVENTORY_CASES`は
117件〔うちINV-CTRL-*が25件〕、いずれも全件パス）。

## 2. Files Changed（詳細）

- `.claude/hooks/guard_bash_writes.py`
  - 新規定数5個（`CONTROL_CONDITION_KEYWORDS`・`CONTROL_BODY_KEYWORDS`・
    `CONTROL_CLOSING_KEYWORDS`・`BASH_NAME_RE`。既存の `SED_WRITE_RE` 定義
    直後、KLK-018のブレース展開節と同じ位置づけで追加）
  - 新規関数6個（`_parse_for_header`・`_strip_case_clause`・
    `strip_control_prefix`・`control_stripped_segments`・
    `mentions_guarded_var`・`record_loop_binding`。いずれも
    `redirect_violation` の直後、`statement_violation` の手前に配置）
  - `redirect_violation`: `guarded_loop_vars=()` 引数を追加し、リダイレクト先の
    変数参照チェックへ `guarded_vars` とのOR条件として組み込み
  - `statement_violation`: `guarded_loop_vars=()` 引数を追加。
    `redirect_violation` 呼び出しへ受け渡し、`segments = pipe_segments(statement)`
    を `segments = control_stripped_segments(statement)` へ差し替え、
    `gate_hit` へ `mentions_guarded_var(expanded_words, guarded_loop_vars)` を
    OR追加
  - `find_violation`: `guarded_vars, seen = set(), set()` を
    `guarded_vars, guarded_loop_vars, seen = set(), set(), set()` へ変更、
    `record_assignments` の直後に `record_loop_binding` を追加、
    `statement_violation` 呼び出しへ `guarded_loop_vars` を追加、
    cwd追跡の `segments = pipe_segments(statement)` を
    `segments = control_stripped_segments(statement)` へ差し替え
  - `degraded_violation` は無変更（設計書§4末尾のとおり）
- `tests/test_guard_bash_writes.py`
  - `INVENTORY_CASES` へ `INV-CTRL-01`〜`INV-CTRL-25`（25件）を追加
  - 新規テストメソッド14個（`test_klk019_*`）を追加

## 3. 設計からの逸脱（要報告・レビュー必須）

設計書§4の`strip_control_prefix`・`CONTROL_CLOSING_KEYWORDS`は「fi/done/esac
は常に統計の末尾で単独語にしかならず特別扱い不要（§6 R-CTRL3）」としていたが、
**この前提はAC1の実例で破れることを実測で確認した**。

### 3-1. 発見した問題

設計書§9 AC1の例 `while read l; do echo $l; done < tickets/active/APP-001.md`
を設計書§4のコードそのまま（closing keywordを剥がさない版）で実行すると、
以下の理由で**denyになってしまい、AC1（allow）を満たさない**:

- `done < tickets/active/APP-001.md` は `;` 等の区切りが無いため1ステートメント
  になる（bash文法上、閉じキーワード直後の区切り無しリダイレクトは有効）
- リダイレクト先の語はパイプ区間（`segments`）からは除外されるが、gate_hit
  判定用の `words`（ステートメント中の全"w"トークン）には含まれるため、
  保護対象を言及するリダイレクト先を持つだけでgate_hitが立つ
- 剥がされない生の `done` がheadになり、`ALLOWED_HEADS`外として
  `segment_violation` がdenyを返す

実測（本実装作業中に確認）:
```
strip_control_prefix(["done","<","tickets/active/APP-001.md"]) -> None
control_stripped_segments(...) -> [["done"]]
-> head_of(["done"])="done" -> ALLOWED_HEADS外 -> deny
```

### 3-2. 実施した補正

設計書§3の一般原則（「先頭に連なる制御構文キーワードを再帰的に剥がす」）を
`CONTROL_CLOSING_KEYWORDS`（fi/done/esac）にも一貫して適用した
（`strip_control_prefix` の分岐条件へ `head in CONTROL_CLOSING_KEYWORDS` を
追加）。`ALLOWED_HEADS`/`CWD_SAFE_HEADS`・`redirect_violation`・
`segment_violation` は無変更。

### 3-3. 安全性の確認（実測）

- 剥がした残余は既存の`ALLOWED_HEADS`判定へそのまま委ねるため新しい許可経路は
  作らない。`done < FILE`は`<`（redirect_in）であり書き込みを発生させない
  ため、denyする実益が無い
- 閉じキーワードの後ろにパイプで実コマンドが続く形
  （`while true; do echo hi; done | rm tickets/active/APP-001.md`）は、
  そのパイプ区間が独立してALLOWED_HEADS判定の対象になるため**deny のまま**
  であることを実測済み（`test_klk019_closing_keyword_pipe_write_still_denies`）
- 対照として同型のcat版（`done | cat ...`）はallowのまま、
  `if true; then echo x; fi < tickets/active/APP-001.md`・
  `case x in *) echo hi ;; esac < tickets/active/APP-001.md`もallowであることを
  実測（`test_klk019_closing_keyword_trailing_redirect_allow`）
- この補正を含めた状態で`LEGACY_DENY_COMMANDS`130件・既存`INVENTORY_CASES`
  （INV-SH-11含む）は無回帰

**reviewerへの申し送り:** 本補正は設計書§4の literal なコードから逸脱して
いる（`CONTROL_CLOSING_KEYWORDS`の定義コメント「特別扱いは不要」という
記述とも矛盾する）。ALLOWED_HEADS/CWD_SAFE_HEADSを変更せず、既存の
strip機構の対象を1カテゴリ追加しただけであり、新しい許可経路を作らないこと
を上記のとおり実測確認済みだが、セキュリティ上重要な変更であるため、設計の
明示的な承認（設計書§4・§6 R-CTRL3の更新）を推奨する。

## 4. V-14実機検証（設計書§9 AC6末尾）

`/tmp` 配下の使い捨てディレクトリ（`tempfile.mkdtemp`。`tickets/active/`・
`tickets/done/`・`docs/SPEC.md`のダミーを配置）で、N1〜N6の代表例7件と
AC2の書き込み例4件を実機bash（`bash -c`）で実行し、以下を確認した
（検証スクリプト自体はテストスイートに含めていない。KLK-010§9の方針どおり）。

- **(a) allow側（読み取り専用性）**: N1（for読み取り）・N2（while読み取り）・
  N3（if-elif-else読み取り）・N4（case単一パターン読み取り）・N5（入れ子:
  for内case読み取り）・N6（if cd; then cat）・AC1（while read + trailing
  redirect）の7件すべてで、hookがallowと判定し、かつ実機実行後もダミー
  ファイルの内容が実行前と1バイトも変わらないことを確認した
- **(b) deny側（書き込みが実際に発生すること）**: forループ変数経由の
  `rm`・`sed -i`・リダイレクト書き込みの3件と、`if cd tickets/active; then
  rm APP-001.md; fi`（N6対・cwd追跡経由）の計4件すべてで、hookがdenyと
  判定し、かつ同じコマンドを実機bashで直接実行した場合はファイルの削除・
  内容変更が実際に発生することを確認した（＝denyが正しく機能を止めている
  ことの裏付け）

全11件が期待どおりの結果（`ALL V-14 CHECKS PASSED`）。検証に使った一時
ディレクトリは各ケースごとに実行後 `shutil.rmtree` で削除しており、実
リポジトリの `tickets/`・`docs/SPEC.md` には一切触れていない。

## 5. Remaining Risks（詳細）

- §3で報告した設計逸脱（CONTROL_CLOSING_KEYWORDSのストリップ追加）は
  reviewerの明示的な確認を要する
- R-CTRL5（設計確定事項）: `guarded_loop_vars`はステートメント全体で保持され
  続けるため、同名変数を無関係な用途で再利用した場合に過剰denyが起きうる
  （安全側の誤りであり、設計書§6で既知の限界として明記済み。追加対応なし）
- R-CTRL2（設計確定事項）: caseの複数パターン（`a|b)`）は字句解析器が`|`を
  パイプ演算子として扱うため正しく解析できずフォールバックdenyになる
  （設計書のスコープ外。将来別チケットの余地）
- degraded mode（字句解析失敗時）には本チケットの制御構文緩和が及ばない
  （設計書§4末尾で明記済み。既存の限界の継続であり新規の穴ではない）
