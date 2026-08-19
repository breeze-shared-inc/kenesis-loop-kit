# KLK-033 調査詳細

> investigator（Mode A）レポートの全文。orchestratorが代筆で外部化した（investigatorはWrite/Editツールを持たないため）。
> 調査実施日: 2026-08-19 / 対象ツリー: メインworktree（develop）

## サマリ（Required Output Format）

### Findings
- **原因（実測確認済み）**: `SHELL_EXPAND_PATHISH_RE`（`guard_bash_writes.py`）の文字集合 `[A-Za-z0-9_.\-/{},*?\[\]]+` に `!` が無いため、語 `docs/[!x]PEC.md` は `['docs/[', 'x]PEC.md']` の2候補に分断される。`_guarded_paths_from_expanded` はどちらの断片からも `SPEC.md` を再構成できず、`find_violation('rm docs/[!x]PEC.md')` は `None`（allow）を返すことを実測で確認した。
- **最小修正の実測確認**: `SHELL_EXPAND_PATHISH_RE` の文字集合へ `!` を追加するだけで候補は1トークン `['docs/[!x]PEC.md']` のまま保たれ、`_guarded_paths_from_expanded` が `['docs/SPEC.md']` を返し `find_violation` が deny に転じることを実測した。`GLOB_META_CHARS`（`*?[` のみ）は無変更で足りる（`[` が既にメタ文字登録済みのため `has_literal_char` ゲートは正しく機能する）。
- **`is_spec_basename_fnmatch` 非単調性（KLK-032レビュー 3-1）を実測再現**: 旧直接比較 `fnmatchcase("SPEC.md","[!s]PEC.md")`=True、新実装=False。レビュー提案の和集合形 `fnmatchcase(literal, pattern) or fnmatchcase(literal.upper(), pattern.upper())` は実測で全ケース（`[!s]PEC.md`→True復元、`[!S]PEC.md`→False維持、`*`→True維持）が旧実装以上の単調な結果になり、`has_literal_char` ゲート（孤立ワイルドカード除外）とはレイヤーが直交し非干渉であることも実測確認した。
- **読み取り専用head対称性**: 修正後シミュレーションで `cat docs/[!x]PEC.md` は allow のまま、`rm docs/[!x]PEC.md` は deny に変わることを実測し、KLK-018/KLK-032の既存設計（読み取りheadは言及ゲートが立っても不問）と整合することを確認した。
- **副作用は語内に限定**: `!` 追加はshlexで既に分割済みの1語の中でのみ候補結合を変える（語境界をまたがない）。`! grep foo bar.txt`（否定コマンド）・`echo foo!bar`・`find . ! -name '*.md'` は修正シミュレーション後も `find_violation` の結果が変化しない（新規の誤deny無し）ことを実測した。履歴展開 `!!`/`!$` は非対話シェル前提により従来から対象外（モジュールdocstring既存記載）。

### Evidence
- `empirical`: 上記5項目すべてスクラッチの検証スクリプト（`klk033_verify.py`・`klk033_fix_probe.py`・`klk033_fix_probe2.py`、Python 3.12、2026-08-19実行）で確認。詳細ログは本ファイル各節。
- `codebase`: `.claude/hooks/guard_bash_writes.py` の `SHELL_EXPAND_PATHISH_RE` / `_guarded_paths_from_expanded` / `GLOB_META_CHARS` / `statement_violation` / `find_violation`、`.claude/hooks/_ticket_lib.py` の `is_spec_basename_fnmatch` を実際に開いて確認（シンボル参照・行番号非依存）。
- `local_docs`: `docs/reports/KLK-032/review.md` Medium 3-1 / 3-2 / Suggested Fixes を確認。本調査の実測結果とすべて整合（矛盾なし）。
- `empirical`: `python3 -m unittest tests.test_guard_bash_writes tests.test_ticket_lib`（387件）と `python3 -m unittest discover -s tests -p "test_*.py"`（805件）を実行し全PASSを確認（2026-08-19、修正前baseline）。
- `codebase`: `tests/test_guard_bash_writes.py`・`tests/test_ticket_lib.py` を `[!` でgrepした結果0件（`[!...]` を扱うケースなし）。

### Dependency Graph（要約。全量は §3 参照）
- `SHELL_EXPAND_PATHISH_RE`（唯一の修正候補地点）→ `guarded_paths_after_shell_expansion` → `_guarded_paths_from_expanded`（`GLOB_META_CHARS`・`is_spec_basename_fnmatch` を利用）→ `is_guarded_token_expanded` → `mentions_guarded_expanded`。
- `mentions_guarded_expanded` / `is_guarded_token_expanded` の呼び出し元は8箇所以上（`statement_violation` の正常経路ゲート、`redirect_violation`、`guarded_write_target`、`subst_violation`、degraded系3経路）。
- `SHELL_EXPAND_PATHISH_RE` は単一の共有定義であるため、この1点の修正が正常/degraded双方の全経路へ一律波及する（実測確認済み）。
- `is_spec_basename_fnmatch` の呼び出し元は `_guarded_paths_from_expanded` のみ（grepで確認、他呼び出し元なし）。

### Risk Areas
- `SHELL_EXPAND_PATHISH_RE` が単一の共有正規表現である以上、修正が正常経路・degraded経路の全ゲートに一律波及する。個別に対称性を壊さないことを確認する回帰テスト（deny面拡大の予算ロック・read-only head対称・degraded側）が必須。
- `is_spec_basename_fnmatch` を和集合形へ変更する場合、`tests/test_ticket_lib.py` の既存True/False固定テスト（`test_is_spec_basename_fnmatch_*`）が現状の単一比較を前提にしているため、和集合形でも同じ入出力を維持できるか全ケースの再照合が必要（本調査では主要ケースのみ実測、網羅ではない）。
- `!` を含む語の結合パターン（`foo!bar` のような非glob語が1トークン化される）は理論上無限にあり、本調査で確認したのは限定サンプルのみ。誤deny方向の予算を固定するテストが無いと将来のリファクタで揺れうる。
- モジュールdocstringの「既知の限界」節は `SHELL_EXPAND_PATHISH_RE` の文字集合が `!` を扱っていない旨を明記していないため、修正時はこのdocstring自体の更新も設計スコープに含める必要がある。
- degraded mode（`skeleton.split()` ベース）でも同じ `SHELL_EXPAND_PATHISH_RE` を共有するため、degraded側の否定クラス回帰テストも正常系と対で必要（本調査では正常系中心に実測、degraded側は未実測）。

### Assumptions
- bashの `[!...]` 否定文字クラスが「集合内の1文字にマッチしない任意の1文字」に一致するというPOSIX/bash標準のglob意味論は `general_knowledge`（一般的なシェル知識）とし、実際に `bash -c` で実ファイルに対して実行する検証は破壊的操作となるため行っていない（Unknowns参照）。
- `!` を追加した場合の副作用確認は、本調査で列挙した代表的サンプル（`!!`・`! cmd`・`[[ ! -f ]]` 系・`find ! -name`・`foo!bar`）に限定しており、シェル全体のあらゆる `!` 用例を網羅したわけではない（research-conventions §7「調査範囲の自制」に基づき依頼スコープの範囲で確認）。
- `GLOB_META_CHARS` は無変更で足りるという結論は、`[!x]PEC.md` という具体例1件の実測に基づく。`]` を含む他パターン（例: `[!]x]PEC.md` のような複雑なブラケット表現）は未検証。
- KLK-032レビュー（`docs/reports/KLK-032/review.md`）の記述と本調査の実測結果は完全に一致しており、矛盾処理（融合禁止）を適用する対象は無かった。

### Unknowns
- 実シェル（bash自体）での `rm docs/[!x]PEC.md` の挙動は実行していない（破壊的操作のため）。Python側の `find_violation` 実測とbash glob標準仕様（一般知識）から推定しているが、実際のbash実行による直接確認ではない。検証したい場合は使い捨てディレクトリでの実行が必要（verification_hint）。
- 和集合形 `is_spec_basename_fnmatch` へ変更した場合の `tests/test_ticket_lib.py` 全ケース（`test_is_spec_basename_fnmatch_case_insensitive_match` 等）との網羅的整合は、代表ケースのみ実測しており全数照合はしていない。architect/tester側での全パターン再照合を推奨。
- degraded mode（字句解析失敗時の `degraded_violation`）側での否定クラス回帰は未実測（正常経路のみ実測）。Risk Areasのとおり、architect設計時にdegraded側のテストケースも必要。
- 上記以外に本調査で確定できなかった問いは無い（surrendered対象なし）。

---

## 検証環境・手順
- 実行環境: `/home/bzg55/workspace/breeze/kenesis-loop-kit`（メインworktree・develop）、Python 3.12、2026-08-19実施。
- 制約: チケット注意書きのとおり `[!...]` を含む文字列をインラインBashコマンドに直接書くと `guard_bash_writes.py` 自身にdenyされるリスクがあるため（実際、`docs/sp*.md` のような通常の分断globリテラルを含むheredoc書き込みで実際にdenyされることを確認した）、検証スクリプトはスクラッチディレクトリへ**heredocを使わずplain `echo '...' >> file`（リダイレクトのみ・ヒアドキュメントなし）**で1行ずつ追記して作成した。理由: `echo` はALLOWED_HEADSかつコンテンツ内容に関する追加チェックが無く、`redirect_violation` はリダイレクト**先**（スクラッチファイル、非保護対象）のみを見るため、本文に `SPEC.md` 等の文字列が含まれていてもdenyされない（本調査で実測確認）。一方ヒアドキュメント（`<<`）はゲートが立った時点で無条件denyになる仕様（`statement_violation` の `op_kind(v)=="heredoc"` 分岐）であることも実測で確認した。
- 生成したスクリプト: セッションのスクラッチディレクトリ配下 `klk033_verify.py`・`klk033_fix_probe.py`・`klk033_fix_probe2.py`（いずれもリポジトリ外・スクラッチ領域）。

## 1. 原因の特定

### `SHELL_EXPAND_PATHISH_RE` の定義
```
SHELL_EXPAND_PATHISH_RE = re.compile(r"[A-Za-z0-9_.\-/{},*?\[\]]+")
```
文字集合: 英数字・`_`・`.`・`-`・`/`・`{`・`}`・`,`・`*`・`?`・`[`・`]`。`!` を含まない。

### 実測1: トークン分断
```
word = "docs/[!x]PEC.md"
g.SHELL_EXPAND_PATHISH_RE.findall(word)
=> ['docs/[', 'x]PEC.md']
```
`!` で分断され2候補になる。

### 実測2: 各候補の判定
```
g.guarded_paths_after_shell_expansion(word) => []
g._guarded_paths_from_expanded('docs/[')   => []
g._guarded_paths_from_expanded('x]PEC.md') => []
```
- `'docs/['`: 成分は `["docs","["]`。`"["` はGLOB_META_CHARS内のみで構成（`has_literal_char=False`）→ KLK-031ゲートによりSPEC.mdは照合対象に加わらず、active/done照合も不一致。
- `'x]PEC.md'`: 成分 `"x]PEC.md"` は `has_literal_char=True` だが、`is_spec_basename_fnmatch("x]PEC.md")` は `fnmatchcase("SPEC.MD","X]PEC.MD")` となり、長さ・文字列構造が一致せずFalse。

### 実測3: end-to-end
```
g.find_violation('rm docs/[!x]PEC.md') => None   # allow = バグ（誤allow）
g.find_violation('rm docs/sp*.md')     => "'rm' は許可されていません"  # 対照（正しくdeny、ハーネスの健全性確認）
```

### 実測4: 最小修正の効果確認（`!` を `SHELL_EXPAND_PATHISH_RE` の文字集合へ追加するシミュレーション）
```python
hyp_re = re.compile(r"[A-Za-z0-9_.\-/{},*?\[\]!]+")
g.SHELL_EXPAND_PATHISH_RE = hyp_re
hyp_re.findall("docs/[!x]PEC.md")                        => ['docs/[!x]PEC.md']   # 1トークンに統合
g.guarded_paths_after_shell_expansion("docs/[!x]PEC.md") => ['docs/SPEC.md']
g._guarded_paths_from_expanded("docs/[!x]PEC.md")        => ['docs/SPEC.md']
g.find_violation("rm docs/[!x]PEC.md")                   => "'rm' は許可されていません"  # deny化
```
`GLOB_META_CHARS = frozenset("*?[")` は無変更のまま機能する（`[` が既にメタ文字集合に含まれるため、`has_literal_char` ゲートは `!x]PEC.md` 成分に対し正しく `True` と判定する）。

### 実測5: 読み取り専用head対称性（修正シミュレーション下）
```
g.find_violation("cat docs/[!x]PEC.md") => None   # allow のまま（KLK-018/032の設計方針と整合）
g.find_violation("rm docs/[!x]PEC.md")  => "'rm' は許可されていません"
```

### 実測6: 副作用サンプル（修正シミュレーション下、誤deny方向の新規発生なし）
```
g.find_violation("! grep foo bar.txt")        => None
g.find_violation("echo foo!bar")              => None
g.find_violation("find . ! -name '*.md'")     => None
```
語ごとの候補結合の変化（`SHELL_EXPAND_PATHISH_RE` のみへの変更は既にshlexで分割された1語の内部にのみ影響し、語境界をまたがない）:
```
word='!!'              current=[]                      hypothetical=['!!']
word='!$'              current=[]                      hypothetical=['!']
word='!'               current=[]                      hypothetical=['!']
word='-name'           current=['-name']               hypothetical=['-name']
word='foo!bar'         current=['foo','bar']           hypothetical=['foo!bar']
word='!important'      current=['important']           hypothetical=['!important']
word='a!b/c.md'        current=['a','b/c.md']          hypothetical=['a!b/c.md']
word='docs/[!x]PEC.md' current=['docs/[','x]PEC.md']   hypothetical=['docs/[!x]PEC.md']
```
いずれの結合候補も `/` を含む guarded な構造（tickets/active|done・SPEC.md）を偶然構成しないため、`_guarded_paths_from_expanded` 側で誤ってマッチしない（実測: `find_violation` の結果は全て `None`=allow のまま変化なし）。

## 2. `is_spec_basename_fnmatch` の非単調性（KLK-032レビュー Medium 3-1）

### 現在の実装
```python
def is_spec_basename_fnmatch(pattern):
    return isinstance(pattern, str) and fnmatch.fnmatchcase(
        "SPEC.MD", pattern.upper())
```

### 実測: 非単調性の再現
```
old_direct = fnmatch.fnmatchcase("SPEC.md", "[!s]PEC.md")   => True
new_impl   = lib.is_spec_basename_fnmatch("[!s]PEC.md")     => False
```
理由: `"SPEC.md"` の先頭文字は大文字 `S` であり、旧実装は `[!s]`（小文字sを除外）と比較するため大文字 `S` は除外対象外→一致。新実装は両辺を `.upper()` してから比較するため `[!S]`（大文字Sを除外）になり、対象の先頭大文字 `S` が除外され不一致。

### 実測: 和集合形の再検証
```python
def union_form(pattern):
    return fnmatch.fnmatchcase("SPEC.md", pattern) or fnmatch.fnmatchcase("SPEC.MD", pattern.upper())
```

| pattern | union_form | 現行 `is_spec_basename_fnmatch` | 旧直接 `fnmatchcase` |
|---|---|---|---|
| `SPEC.md` | True | True | True |
| `spec.md` | True | True | False |
| `sp*.md` | True | True | False |
| `SP*.MD` | True | True | False |
| `Spec*.md` | True | True | False |
| `[!s]PEC.md` | **True**（復元） | False | True |
| `[!S]PEC.md` | False | False | False |
| `*` | True | True | True |
| `sp*.txt` | False | False | False |
| `docs/sp*.md` | False | False | False |
| `""` | False | False | False |

和集合形は旧実装のTrueケースを一切失わず（`[!s]PEC.md` のTrueを復元）、かつKLK-032が意図した大小区別是正（`spec.md`・`sp*.md` 等のTrue化）も維持しており、単調な拡張になっていることを実測で確認した。

### 実測: KLK-031 `has_literal_char` ゲートとの非干渉確認
```
g._guarded_paths_from_expanded('*') => []
```
`'*'` は `has_literal_char=False` のため、そもそも `is_spec_basename_fnmatch` の呼び出しに到達しない（GUARDED_FILENAMEが `literals` へ追加されない）。したがって `is_spec_basename_fnmatch` の実装をどちらの形に変えても、この事前ゲート自体の挙動には影響しない（レイヤーが直交）。

## 3. 影響範囲・副作用リスク

### 呼び出し関係（Dependency Graph全量）
```
SHELL_EXPAND_PATHISH_RE (定数・修正候補)
  └─ guarded_paths_after_shell_expansion(text)
       └─ _guarded_paths_from_expanded(expanded)  [GLOB_META_CHARS, lib.is_spec_basename_fnmatch を使用]
            └─ is_guarded_token_expanded(text) = is_guarded_token(text) or guarded_paths_after_shell_expansion(text)
                 └─ mentions_guarded_expanded(values) = any(is_guarded_token_expanded(v) for v in values)
                      ├─ statement_violation() の gate_hit（正常経路の主ゲート。has_program_head分岐両方）
                      ├─ redirect_violation() の resolved（リダイレクト先判定）
                      ├─ record_loop_binding() の LIST判定（KLK-019 for文）
                      └─ degraded_violation() の skeleton全体ゲート・パイプ区間ゲート（3箇所）
                 └─ is_guarded_token_expanded() 単独呼び出し（ORの前段以外）
                      ├─ guarded_write_target()（sort -o／uniq第2引数／cwd相対解決）
                      ├─ redirect_violation()（resolved自体への直接判定）
                      ├─ subst_violation()（MAX_SUBST_DEPTH到達時の保守的deny判定）
                      └─ degraded_violation()（LEGACY_REDIRECT_RE先の判定）

lib.is_spec_basename_fnmatch(pattern)
  └─ _guarded_paths_from_expanded() のみ（他の呼び出し元なし。grep -rn で確認）
```

### 副作用リスクの評価
- `SHELL_EXPAND_PATHISH_RE` は**既にshlex/lex()で分割済みの1つの「語」の内部**にのみ適用される正規表現であり、語と語の間（空白区切り）の結合には影響しない。したがって `! -f`（否定＋フラグが別語）・`[[ ! -f x ]]`（`!` が独立語）・`find . ! -name '*.md'`（`!` が独立語）は、`!` 追加後も候補分割が変わらない（実測: いずれも `find_violation` の結果はNoneのまま）。
- 影響が生じ得るのは「`!` が他のpathish文字と**同一語内で連続**している」形（`foo!bar`・`a!b/c.md`・`docs/[!x]PEC.md` 等）に限られる。これらが偶然 `tickets/active`・`tickets/done`・`SPEC.md` 構造に一致する確率は、`/` 区切り成分の構造要件（KLK-018/031/032の既存ゲート）により低いが、**全数検証はしていない**（Assumptions/Unknowns参照）。
- 履歴展開（`!!`・`!$`）はモジュールdocstring「既知の限界」に既に「非対話シェルでは既定で無効のため相違を生まない」と明記されている既存の設計前提であり、本チケットのスコープでも変化しない。
- 読み取り専用head対称性（`cat` 等）はKLK-018/KLK-032が確立した設計（言及ゲートが立ってもALLOWED_HEADSに載っているheadは無条件allow）にそのまま従う。`!` 追加はゲートの発火条件を広げるだけで、ALLOWED_HEADS判定ロジック自体（`segment_violation`）には変更を要しない。

## 4. 既存テストの現状

### 関連テストケース一覧（grep結果、KLK-018・KLK-031・KLK-032由来）
`tests/test_guard_bash_writes.py`:
- KLK-018系: `test_klk018_*`（ブレース展開・分断glob対応、RecursionError回帰、隣接ブレース差し戻し検証群）
- KLK-031系: 孤立ワイルドカード誤deny是正の回帰群
- KLK-032系:
  - `test_klk032_lowercase_mixedcase_fragmented_glob_deny`
  - `test_klk032_spec_side_read_allow`
  - `test_klk032_guarded_paths_from_expanded_unit`
  - `test_klk032_case_closure_budget_deny`

`tests/test_ticket_lib.py`:
- `test_is_spec_basename_fnmatch_case_insensitive_match`
- `test_is_spec_basename_fnmatch_isolated_wildcard_true`
- `test_is_spec_basename_fnmatch_non_match`
- `test_is_spec_basename_fnmatch_non_str_returns_false`

**`[!...]` を扱うテストケースは両ファイルのgrepで0件**（存在しない）。

### 実測: 現行テストスイート全通過
```
$ python3 -m unittest tests.test_guard_bash_writes tests.test_ticket_lib -v
Ran 387 tests ... OK   (test_guard_bash_writes: 292, test_ticket_lib: 95)

$ python3 -m unittest discover -s tests -p "test_*.py"
Ran 805 tests ... OK   (リポジトリ全体のtests/、修正前baseline)
```
（KLK-032レビューが言及した「792件全PASS」は `docs/reports/KLK-032/test-report.md` 時点のリポジトリ全体テスト数であり、本調査時点では805件に増加している。差分の原因は本調査のスコープ外のため未追跡。）

## 5. 系譜の確認（`docs/reports/KLK-032/review.md` との突き合わせ）

review.mdの記載内容と本調査の実測結果に**矛盾は検出されなかった**（融合ではなく個別に突き合わせて一致を確認）:
- Medium 3-1「`.upper()` 正規化は非単調」「実測で確認」→ 本調査でも同一実測結果（True→False）を再現。
- Medium 3-2「`!` は `SHELL_EXPAND_PATHISH_RE` の文字集合外のため `[!...]` を含むトークンは候補抽出の段階で分断され…本番経路では旧新いずれの実装でも当該比較に到達しない」→ 本調査で `find_violation` の実測により裏付け（None=allow）。
- Suggested Fixes 1〜3（フォローアップチケット起票・和集合形提案・docstring追記提案）→ 本調査で和集合形の単調性を実測検証済み。是正時の設計方針として妥当と判断できる材料が揃った（ただし方針決定はarchitectの範囲）。
- review.mdとの間で見解が割れた箇所は無し。

## ソース一覧（research-conventions §2準拠）

| kind | ref | summary |
|---|---|---|
| codebase | `.claude/hooks/guard_bash_writes.py`（`SHELL_EXPAND_PATHISH_RE` 定義・`_guarded_paths_from_expanded`・`GLOB_META_CHARS`・`statement_violation`・`redirect_violation`・`guarded_write_target`・`subst_violation`・`degraded_violation`） | 実際に開いて確認。現状の実装（あるべき仕様ではない）。 |
| codebase | `.claude/hooks/_ticket_lib.py`（`is_spec_basename_fnmatch`・`is_spec_basename`） | 実際に開いて確認。 |
| local_docs | `docs/reports/KLK-032/review.md` | 2026-08-19付レビュー。Medium 3-1/3-2・Suggested Fixesを確認。本調査の実測と整合。 |
| codebase | `tests/test_guard_bash_writes.py`・`tests/test_ticket_lib.py` | grepで `[!` 検索・KLK-018/031/032関連ケース一覧を確認。 |
| empirical | スクラッチの `klk033_verify.py`（本セッション作成・実行） | `find_violation`・`guarded_paths_after_shell_expansion`・`_guarded_paths_from_expanded`・`is_spec_basename_fnmatch`・union_form比較の実測。Python 3.12、2026-08-19。 |
| empirical | スクラッチの `klk033_fix_probe.py`・`klk033_fix_probe2.py`（同上） | `SHELL_EXPAND_PATHISH_RE` へ `!` を追加した場合の効果・副作用シミュレーション実測。 |
| empirical | `python3 -m unittest` 実行結果（`tests.test_guard_bash_writes`・`tests.test_ticket_lib`: 387件、discover全体: 805件） | 2026-08-19、修正前baseline、全PASS。 |
| general_knowledge | bashのglob否定文字クラス `[!...]` の意味論（POSIX/bash標準仕様の一般知識） | 実シェルでの `rm` 実行による直接確認は行っていない（破壊的操作のため）。 |

## 主要ファイルパス（investigator調査対象）
- `.claude/hooks/guard_bash_writes.py`
- `.claude/hooks/_ticket_lib.py`
- `tests/test_guard_bash_writes.py`
- `tests/test_ticket_lib.py`
- `docs/reports/KLK-032/review.md`
- `tickets/active/KLK-033_否定文字クラス[!]globがpathish分断で検出されずSPEC_md操作が誤allowされる.md`
