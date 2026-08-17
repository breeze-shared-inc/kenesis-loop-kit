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

## 6. tester差し戻し対応（AC6独自検証で検出されたQuality Gate FAIL）

### 6-1. 原因

`record_loop_binding`（forループ変数の登録）・`record_assignments`（前置き
代入の登録）は、`statement_violation`のALLOWED_HEADS判定・`find_violation`
のcwd追跡と異なり、`control_stripped_segments`／`strip_control_prefix`を
経由しない**生のstatement語**を見て「先頭語が`for`か」「先頭語が
`NAME=value`形か」を判定していた（§3-3で報告した`control_stripped_segments`
共有ルールの適用対象からこの2関数が漏れていた）。このため、内側の
`for NAME in LIST`ヘッダーや前置き代入が外側制御構文の`do`/`then`/`while`と
`;`区切りで同一statementを共有する入れ子ループ（`for i in 1 2; do for f in
tickets/active/*.md; do rm $f; done; done`等）で、`NAME`/代入変数の登録が
丸ごと失敗し、後続の書き込み文にゲートが一切立たずallowへ転じていた
（tester報告・実機bashでの書き込み発生を確認済み）。

### 6-2. 対応方針とコード変更

`strip_control_prefix`をそのまま転用すると`for`/`case`に到達した時点で
ヘッダーごと消費・破棄される（ALLOWED_HEADS判定には正しい挙動だが、
`record_loop_binding`/`record_assignments`には逆の要件がある）ため、
**新設の軽量ヘルパーを追加**した:

- `_strip_leading_outer_keyword(tokens)`: 先頭1語が外側制御構文キーワード
  （`CONTROL_CONDITION_KEYWORDS`・`CONTROL_BODY_KEYWORDS`・
  `CONTROL_CLOSING_KEYWORDS`）ならそれだけを剥がす。`for`/`case`は対象外
  （判定しない＝呼び出し元に残す）
- `strip_outer_control_keywords(statement)`: 上記を繰り返し適用し、
  `for`/`case`に到達しても止まらず残余トークン列を返す（変化の有無を
  Noneで示す設計を採らず、常にトークン列を返す）
- `strip_control_prefix`自身も`_strip_leading_outer_keyword`を内部で呼ぶ
  ようリファクタリングし、重複ロジックを解消（`for`/`case`分岐の判定・
  戻り値の意味〔剥がすものが無ければNone〕は無変更）
- `record_assignments`: `pipe_segments(statement)` →
  `pipe_segments(strip_outer_control_keywords(statement))`
- `record_loop_binding`: `words = [v for k, v in statement if k == "w"]` の
  前段に `tokens = strip_outer_control_keywords(statement)` を追加し、
  `tokens`から語を抽出するよう変更

配置は`_strip_case_clause`の直後・`strip_control_prefix`の直前
（`_strip_leading_outer_keyword`・`_OUTER_CONTROL_KEYWORDS`）と、
`strip_control_prefix`の直後（`strip_outer_control_keywords`）。
`ALLOWED_HEADS`/`CWD_SAFE_HEADS`は無変更。

### 6-3. 検証結果（実測）

- `python3 -m unittest discover -s tests -v`: **731件全件PASS**
  （既存726件＋tester追加5件。新規テスト追加なし＝実装側の修正のみ）
- tester追加の回帰固定テスト5件（`test_klk019_regression_nested_for_loop_var_write_denies_do_prefix`・`_then_prefix`・`_while_prefix`・
  `test_klk019_regression_nested_for_loop_var_redirect_write_denies`・
  `test_klk019_regression_nested_assignment_redirect_write_denies`）は
  **全件PASS**
- `test_legacy_deny_commands_all_still_deny`（`LEGACY_DENY_COMMANDS`130件）・
  `test_inventory_cases_match_expected_decisions`（`INVENTORY_CASES`117件。
  `INV-SH-11`・`INV-CTRL-01`〜`25`含む）を個別実行し、いずれもPASS
  （無回帰）
- 実機bash検証（scratchpadの`tempfile.mkdtemp()`使い捨てディレクトリ。
  本番`tickets/`・`docs/SPEC.md`には一切触れていない）: tester報告の5件の
  再現手順すべてで、修正後の`find_violation()`がdenyを返すこと、
  「ゲート適用済みワークフロー」（denyなら実行しない）ではサンドボックスの
  ファイルが1バイトも変化しないこと、対照実験として同じコマンドを
  ゲート無しで実行すると実際に削除・上書きが発生すること（＝真陽性である
  ことの裏付け）の3点を確認した
- 追加の安全性確認（別statementへの巻き込み・C形式for/複数パターンcaseの
  フォールバックdeny・変数名`do`との衝突なし等）をscratchpadの使い捨て
  スクリプトで個別確認し、いずれも期待どおり（既存挙動の維持）であることを
  確認した

### 6-4. 設計書への反映要否（次工程への申し送り）

`docs/designs/KLK-019.md`§4は`strip_control_prefix`・`control_stripped_segments`
のコードをそのまま転記しており、§6 R-CTRL4も「`control_stripped_segments`を
ALLOWED_HEADS判定とcwd追跡の両方から呼ぶこと」を明記しているが、
**`record_loop_binding`・`record_assignments`もこの共有ルールの適用対象で
あるべきだったことは明記されていない**（本チケットのPhase1/2実装時点の
設計漏れ）。新設した`_strip_leading_outer_keyword`・
`strip_outer_control_keywords`は§4のコード転記・Phase表（Phase1/2）・
§6 R-CTRL4の記述と整合させるための更新が必要と判断する（architectの
権限のため本実装では設計書自体は編集していない。反映有無・要否の最終判断は
architect/orchestratorへ委ねる）。

## 7. R-CTRL7対応（architectが設計書レビュー中に静的読解で発見した未検証リスク）

### 7-1. 実機検証結果（修正前・コミット349ec69時点）

architectの推論どおり、`case`ヘッダーが内側の`for`ヘッダー／前置き代入と
同一statementを共有する形で、実際に**deny→allowの回帰が発生することを
実機で確認した**。検証はscratchpadの使い捨てディレクトリ
（`/tmp/claude-.../scratchpad/klk019-verify/`。本番`tickets/`・`docs/SPEC.md`
には一切触れていない）で、`guard_bash_writes.py`へJSON payloadを直接
標準入力から投入し、修正前バイナリで以下を確認した:

- **`case x in *) for f in tickets/active/*.md; do rm $f; done ;; esac`**:
  修正前は**allow**（stdout 0バイト・exit 0）。同一コマンドから`case ... ;;
  esac`のラッパーを外した`for f in tickets/active/*.md; do rm $f; done`は
  修正前・後とも一貫して**deny**（`'rm' は許可されていません`）であり、
  ラッパーの有無だけでdeny→allowが切り替わることを確認した
- **`case x in *) f=tickets/active/APP-001.md; echo hi > $f ;; esac`**:
  同様に修正前は**allow**。ラッパー無しの
  `f=tickets/active/APP-001.md; echo hi > $f`は修正前・後とも一貫して
  **deny**（`リダイレクト（> $f）による書き込み`）
- **ゲート無しの実機bash実行（サンドボックス内、ゲートを経由しない直接実行）**:
  上記1件目は`tickets/active/`配下のダミーファイル（APP-001.md・
  APP-002.md）が実際に削除されることを、2件目はダミーファイルの内容が
  `original content 1`から`hi`へ実際に上書きされることを確認した。
  すなわちこの2形はいずれも「hookをすり抜けて実際にチケットファイルを
  破壊しうる」真陽性の穴であった

### 7-2. 原因（architectの推論の裏付け）

architectの推論は正確だった。`strip_control_prefix`（ALLOWED_HEADS判定・
cwd追跡用）は`_strip_case_clause`で`case`ヘッダーを剥がすため、
`case`ヘッダーを含むstatement自体は正しく空残余（またはfor同様に空残余）
へ倒れ、その1文単体はdenyにならない。一方、`record_assignments`・
`record_loop_binding`が使う`strip_outer_control_keywords`（tester差し戻し
対応で新設。§6参照）は、修正前は`for`/`case`をいずれも対象外としていた
（`_strip_leading_outer_keyword`のdocstringどおり）。このため`case`ヘッダーを
含むstatementでは残余の先頭が常に生の`"case"`のままとなり、
`_parse_for_header`（先頭語が`"for"`であることを要求）・`ASSIGN_RE`
（先頭語が`NAME=`形であることを要求）のいずれとも一致せず、後続statement
（`do rm $f`・`echo hi > $f`）が参照する`guarded_loop_vars`・`guarded_vars`
への登録が漏れていた。登録が漏れた結果、後続statementの`gate_hit`が
一切立たず、ALLOWED_HEADS判定（`rm`は本来ALLOWED_HEADS外）・
`redirect_violation`（`$f`は本来guarded_varsに登録されているべき）の
いずれにも到達せずallowになっていた。

### 7-3. 対応したコード変更

`.claude/hooks/guard_bash_writes.py`の`strip_outer_control_keywords`へ
`case`ヘッダーの剥がし処理を追加した（`_strip_leading_outer_keyword`自体は
`for`/`case`を対象外のまま変更していない——ALLOWED_HEADS判定用の
`strip_control_prefix`から見た`for`の特別扱いとは無関係であるため）:

```python
def strip_outer_control_keywords(statement):
    tokens = statement
    while True:
        if tokens and tokens[0][0] == "w" and tokens[0][1] == "case":
            residual = _strip_case_clause(tokens)
            if residual is None:
                return tokens
            tokens = residual
            continue
        stripped = _strip_leading_outer_keyword(tokens)
        if stripped is None:
            return tokens
        tokens = stripped
```

`case`ヘッダーは「実行されるコマンドを一切含まない構文マーカー」という点で
if/while/do等と同じであり（`for`とは異なりヘッダー自体に判定対象の情報＝
NAME/LISTを持たない）、`_strip_case_clause`で剥がして残余へ進めばよい。
`_strip_case_clause`が解析できない形（複数パターン`a|b)`等）は`None`を
返すため、その時点で残余をそのまま返す（既存の「剥がせない場合は元の
statementをそのまま渡す」規約を踏襲。安全側フォールバック）。
`_strip_leading_outer_keyword`・`strip_control_prefix`・`_OUTER_CONTROL_KEYWORDS`
自体は無変更。`record_assignments`・`record_loop_binding`のシグネチャ・
呼び出し元も無変更（内部で使う`strip_outer_control_keywords`の挙動だけが
変わる）。

### 7-4. 修正後の検証結果（実測）

- 同じscratchpadのJSON payloadをそのまま再投入し、上記2形がいずれも
  **deny**へ転じたことを確認した（1件目: `'rm' は許可されていません`。
  2件目: `リダイレクト（> $f）による書き込み`）
- 回帰確認: 読み取り版
  `case x in *) for f in tickets/active/*.md; do cat $f; done ;; esac`・
  `case x in *) cat tickets/active/APP-001.md ;; esac`は引き続き**allow**
- INV-SH-11の分離規律の回帰確認:
  `case x in *) f=tickets/active/APP-001.md; rm $f ;; esac`
  （`guarded_vars`はredirect_violationにのみ使われ、`mentions_guarded_var`の
  ゲートには使われないため、値の追跡不能という既存の恒久的allow）は
  修正後も一貫して**allow**のまま（既存INV-SH-11の挙動をcase共有の形でも
  変えていないことを確認）
- `tests/test_guard_bash_writes.py`へ`INVENTORY_CASES`3件
  （`INV-CTRL-26`〜`28`）と専用回帰テスト4件（`test_klk019_r_ctrl7_*`）を
  追加し、`python3 -m unittest discover -s tests -v`で**735件全件PASS**
  （既存731件＋今回追加4件。INV-CTRL-26〜28は既存の
  `test_inventory_cases_match_expected_decisions`のsubTestとして自動的に
  カバーされるため、テストメソッド数の増分には現れない）

### 7-5. Remaining Risks（追加分）

- R-CTRL2（既知・設計確定事項）と同様、`case`の複数パターン（`a|b)`）は
  `_strip_case_clause`が`None`を返しフォールバックdenyのままであり、
  `strip_outer_control_keywords`の今回の変更でもこの制約は変わらない
- 設計書`docs/designs/KLK-019.md`§4・§6には本R-CTRL7・対応する
  `strip_outer_control_keywords`のcase対応は未反映（tester差し戻し対応の
  `strip_outer_control_keywords`新設自体も設計書時点では未反映＝§6-4で
  既に申し送り済みの反映要否と合わせて、architect/orchestratorの判断に
  委ねる）
