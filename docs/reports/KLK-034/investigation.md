# KLK-034 調査詳細（investigator）

検証環境: WSL2 (Linux 6.6.87.2-microsoft-standard-WSL2) / bash / Python 3（`.claude/hooks` 実行系と同一バージョン）。
検証日: 2026-08-19。すべてのスクリプトはセッションのスクラッチパッド（リポジトリ外）に置き、コミットしていない。
ブラケット式を含む文字列はインラインBashへ直接書かず、すべて一時Pythonスクリプト経由で扱った
（KLK-032/033設計書§4-4と同じ運用）。

## 1. 候補抽出パイプラインの構造（シンボル名・データフロー）

```
Bash(command)
  → find_violation → lex（正常経路）／degraded_violation（lex失敗時）
    → statement_violation／redirect_violation／guarded_write_target／
      record_loop_binding／subst_violation
    → mentions_guarded_expanded／is_guarded_token_expanded
      （呼び出し箇所は正常経路6＋degraded経路3＝計9箇所。KLK-033設計書§5で
      確認済みで本チケットでも不変。is_guarded_token_expanded(text) =
      is_guarded_token(text) OR guarded_paths_after_shell_expansion(text)）
      → guarded_paths_after_shell_expansion(text)
          ① SHELL_EXPAND_PATHISH_RE.findall(text)
             現行: re.compile(r"[A-Za-z0-9_.\-/{},*?\[\]!]+")
             `^` と `:` が文字集合に無いため、これらの文字がトークン境界となり
             候補が分断される（本欠陥の発生点）。
          ② 各候補について candidate.count("{") と MAX_BRACE_CHAR_COUNT の
             比較（軽量事前チェック）→ _brace_combination_count →
             MAX_BRACE_COMBINATIONS 比較 → expand_braces（RecursionError
             を2段でtry/exceptし、いずれも「候補全体を保護対象候補とみなす」
             deny方向のフォールバックへ合流。KLK-018差し戻し対応）
          ③ 各展開後候補を _guarded_paths_from_expanded(expanded) へ渡す
              (a) path = os.path.normpath(expanded);
                  _is_guarded_path(path) が真なら即採用（直接一致）
              (b) 満たさない場合、path.split("/") で成分ごとに走査:
                  - any(ch in component for ch in GLOB_META_CHARS)
                    （GLOB_META_CHARS = frozenset("*?[")、無変更対象）
                    を満たさない成分はスキップ
                  - has_literal_char = any(ch not in GLOB_META_CHARS
                    for ch in component)（KLK-031ゲート、無変更対象）
                  - literals = ["active", "done"]（GUARDED_DIR_NAMES）。
                    index == last_index and has_literal_char の場合のみ
                    literals へ "SPEC.md"（GUARDED_FILENAME）を追加
                  - literal == GUARDED_FILENAME の場合は
                    lib.is_spec_basename_fnmatch(component) で照合、
                    それ以外は fnmatch.fnmatchcase(literal, component)
                  - 一致した literal でその成分だけを置換して文字列を
                    再構成し、os.path.normpath 後に _is_guarded_path を
                    再評価（成立すれば found へ追加）
```

`is_spec_basename_fnmatch`（`.claude/hooks/_ticket_lib.py`）は
`_guarded_paths_from_expanded` からのみ呼ばれる単一の呼び出し元
（reviewerがrepo全grepで確認済み。本調査でも `grep -rn is_spec_basename_fnmatch`
で再確認: `_ticket_lib.py` 定義と `guard_bash_writes.py` の1呼び出しのみ）。現行実装:

```python
def is_spec_basename_fnmatch(pattern):
    if not isinstance(pattern, str):
        return False
    return (fnmatch.fnmatchcase("SPEC.md", pattern)
            or fnmatch.fnmatchcase("SPEC.MD", pattern.upper()))
```

## 2. bash と Python fnmatch の意味論の乖離（実測）

### 2-1. `fnmatch.translate` の生出力（実測）

| パターン | `fnmatch.translate` 出力 | `fnmatchcase("SPEC.md", p)` | `fnmatchcase("SPEC.MD", p.upper())` |
|---|---|---|---|
| `[^x]PEC.md` | `(?s:[\^x]PEC\.md)\Z` | False | False |
| `[^s]PEC.md` | `(?s:[\^s]PEC\.md)\Z` | False | **True**（偶然。upper後のクラスが`{^,S}`となり先頭'S'に一致） |
| `[!x]PEC.md`（KLK-033で既に閉じた形・比較用） | `(?s:[^x]PEC\.md)\Z` | True | True |
| `[!s]PEC.md`（同上） | `(?s:[^s]PEC\.md)\Z` | True | False |
| `[[:upper:]]PEC.md` | `(?s:[\[:upper:]\]PEC\.md)\Z` | False | False |
| `[[:alpha:]]PEC.md` | `(?s:[\[:alpha:]\]PEC\.md)\Z` | False | False |

解釈（事実）: Python `re`（`fnmatch.translate` が生成する正規表現）は文字クラス内の先頭 `^`
を否定ではなく「クラスに `^` という1文字を追加する」ものとしてエスケープする
（`[^x]` → `[\^x]`＝「`^`または`x`のいずれか1文字」）。これはbashのブラケット式が
`^`（および `!`）を否定マーカーとして扱うのと明確に異なる意味論であり、
`is_spec_basename_fnmatch` の和集合形（KLK-032/033で確定した2項）のいずれの項でも
`[^x]PEC.md` は捕捉できない。

`[[:upper:]]PEC.md` については、`translate` が `[:upper:` を「`[`・`:`・`u`・`p`・`e`・`r`
の6文字からなる肯定クラス」として字面どおりに解釈する（POSIX文字クラス構文
`[:name:]` を特別扱いしない）。したがって先頭1文字がこの6文字集合のいずれかで、
かつ残りが文字通り `]PEC.md` と一致する場合のみ真になるが、対象文字列
`SPEC.md`／`SPEC.MD` はいずれも条件を満たさず False のまま。**`:` を候補抽出の
文字集合へ追加しても（分断が解消されても）、fnmatch側のこの解釈自体は変わらない
ため `[[:upper:]]PEC.md` は依然として一致しない**（下記2-3で `:` 追加を実装した
状態でも `find_violation` が `None` のままであることを直接確認済み）。

### 2-2. 候補抽出の分断（実測。`guard_bash_writes.SHELL_EXPAND_PATHISH_RE.findall`）

```
findall("rm docs/[^s]PEC.md")        -> ['rm', 'docs/[', 's]PEC.md']
findall("rm docs/[^x]PEC.md")        -> ['rm', 'docs/[', 'x]PEC.md']
findall("rm docs/[[:upper:]]PEC.md") -> ['rm', 'docs/[[', 'upper', ']]PEC.md']
findall("rm docs/[[:alpha:]]PEC.md") -> ['rm', 'docs/[[', 'alpha', ']]PEC.md']
```

（チケット記載の再現手順4と完全一致。`guarded_paths_after_shell_expansion` は
いずれも `[]`、`find_violation` はいずれも `None`＝誤allow、を実測確認済み。）

### 2-3. `^`/`:` を文字集合へ単純追加した場合の効果

実測。モジュール属性を実行時monkeypatchし、リポジトリのコードは変更していない。

```python
guard.SHELL_EXPAND_PATHISH_RE = re.compile(r"[A-Za-z0-9_.\-/{},*?\[\]!^:]+")
```

| コマンド | 候補（widened） | find_violation（widenedのみ・`[^`→`[!`正規化なし） |
|---|---|---|
| `rm docs/[[:upper:]]PEC.md` | `['rm', 'docs/[[:upper:]]PEC.md']` | `None`（依然未検出＝POSIXクラスはこれだけでは閉じない） |
| `rm docs/[[:alpha:]]PEC.md` | 同様に1トークン化 | `None`（同上） |
| `rm docs/[^s]PEC.md` | `['rm', 'docs/[^s]PEC.md']` | **denyされた**（`is_spec_basename_fnmatch` の第2項が `s` 固有の偶然一致で拾うため。§2-1参照） |
| `rm docs/[^x]PEC.md` | `['rm', 'docs/[^x]PEC.md']` | `None`（依然未検出。`x` はこの偶然一致が起きないため一般形の代表） |
| `rm tickets/[:a]ctive/APP-001.md` | `['rm', 'tickets/[:a]ctive/APP-001.md']` | **denyされた**（後述4章参照。真陽性） |

結論（事実）: `^`/`:` を文字集合へ追加するだけでは一般形の否定クラス
（`[^x]PEC.md` 型）もPOSIXクラスも閉じない。`[^s]PEC.md` のような
「upper化後にたまたま含まれる1文字」だけの偶然一致で閉じるケースがあるのみ
（KLK-032 Medium 3-1と同型の非単調性の再来であり、根本対処にならない）。

## 3. `[^` → `[!` 正規化の妥当性（副作用の洗い出し。実測）

### 3-1. 「leading `]` はリテラル」ルールはPythonでも成立（実測。安全側の確認）

```
pattern = "[!]abc]one"
fnmatch.translate(pattern) -> "(?s:[^]abc]one)\\Z"
fnmatchcase("done", pattern)  -> True   （'d' は {],a,b,c} に含まれないため）
fnmatchcase("]one", pattern)  -> False  （']' が除外集合に含まれるため）
```

Python の `re` 文字クラスも「`^` の直後に来る `]` はクラスの終端ではなくリテラル
メンバー」という規則を持つため、`[!]abc]` → `[^]abc]`（Pythonの `re` 表記）は
bashの `[^]abc]`（否定＋`]` をリテラルメンバーに含む）と同じ振る舞いになる。
この点に限れば `[^` → `[!` の単純な位置一致（ブラケット開始直後の `^`）の
置換は安全に機能する。

### 3-2. 無条件の部分文字列置換が意味を変える具体例（実測。反例）

```python
orig     = "[a[^]one"     # 「[」をリテラルメンバーとして含む肯定クラス
                          # （メンバー: a, [, ^）+ 続く literal "one"
replaced = re.sub(r"\[\^", "[!", orig)  # -> "[a[!]one"（ナイーブな全置換）

fnmatch.translate(orig)     -> "(?s:[a[^]one)\\Z"
fnmatch.translate(replaced) -> "(?s:[a[!]one)\\Z"

fnmatchcase("^one", orig)     -> True    fnmatchcase("^one", replaced)     -> False
fnmatchcase("!one", orig)     -> False   fnmatchcase("!one", replaced)     -> True
fnmatchcase("aone", orig)     -> True    fnmatchcase("aone", replaced)     -> True（不変）
fnmatchcase("[one", orig)     -> True    fnmatchcase("[one", replaced)     -> True（不変）
```

`orig` の2文字目が既に `[`（リテラルメンバーとしてのブラケット）であり、その直後の
`^` は「クラスの3番目のメンバー（リテラル `^`）」であって否定マーカーではない。
文字列全体に対する無条件の `"[^" → "[!"` 置換は、この位置と「真にブラケット開始
直後にある `^`」を区別できず、`^one` に一致していたパターンが `!one` に一致する
パターンへ意味そのものが反転する。**この反例は「`[` をリテラルクラスメンバーとして
含む」という稀だが合法なglob構文が前提であり、実運用での出現頻度は低いが、
単純な文字列置換では防げないことを示す構造的な事実である。**

### 3-3. 二重否定・非先頭 `^` は素朴な正規表現置換（`\[\^`）で概ね安全（実測）

`[^^]`（否定クラス、除外対象はリテラル `^` 1文字）に対し `re.sub(r"\[\^", "[!", ...)`
を適用すると、マッチするのは先頭の `[^` のみ（2文字目以降の走査再開位置は
`^` であって `[` ではないため再ヒットしない）。結果は `[!^]` となり、これは元の
`[^^]` と同一の述語（「`^` 以外の任意の1文字」）を保つ。**非先頭の `^`
（`[a^b]` 等、`[` の直後が `^` でない形）はそもそも `"[^"` という2文字連続を
含まないため、素朴な `re.sub(r"\[\^", ...)` の対象にならず無変化のまま安全。**
リスクが顕在化するのは3-2のように「`[` がリテラルメンバーとして先行し、その次に
`^` が続く」形に限定される。

### 3-4. 未閉塞ブラケットへの適用可否（未検証・要architect判断）

現行の `GLOB_META_CHARS` ヒット判定（`any(ch in component for ch in GLOB_META_CHARS)`）
は成分にブラケットが閉じているかどうかを検証しない（`docs/[^x` のような未閉塞でも
`[` を含むため判定対象になる）。bashは未閉塞のブラケットを含む語をglobとして
展開せず、語をそのままリテラルとして扱う（ファイルが存在しなければ無変化で
渡すか、`failglob` 設定次第でエラーになる）。したがって未閉塞ブラケットに対し
`[^`→`[!` 正規化やfnmatch照合を行うこと自体が、bashの実際の挙動
（「一切globとして解釈しない」）と乖離した判定を生む可能性があるが、
本調査では未閉塞ブラケットに対する現行実装の挙動を個別に実測しておらず、
架空の反例を作れるかどうかも未検証（Unknownとして計上）。

## 4. POSIX文字クラスの閉塞可能性（判断材料）

- `:` を候補抽出の文字集合へ追加すると、トークン分断は解消される（`findall` が
  1トークンを返すことを2-3で確認済み）。**しかしfnmatch側の解釈が変わらない
  限り、`[[:upper:]]PEC.md` 等の一致判定は依然False**（2-3で直接確認）。
- 一方で、`:` を含むが真のPOSIXクラス構文ではない「ブラケット+コロンの合成」
  （例: `tickets/[:a]ctive/APP-001.md` — `[:a]` は「`:` または `a` のいずれか1文字」
  という**通常の**肯定クラスであり、POSIXの `[:name:]`（コロン2つで名前を挟む）
  形とは構文的に別物）については、Pythonのfnmatchと実bashが**偶然一致**する
  ケースがある。実測（`mktemp -d` に `tickets/active/X.md` を作成し、
  `subprocess` 経由でネストしたbashを起動して確認。Claude Code側の
  PreToolUse hookは外側のBash呼び出しのみを検査するため、内部の
  `subprocess.run(["bash","-c",...])` はhookの対象外＝KLK-033設計書§3 D4①が
  示した「テストファイル内からsubprocess経由で起動する」非破壊検証手法と同型）:

  ```
  echo tickets/[:a]ctive/X.md  (cwd=一時ディレクトリ、実ファイル tickets/active/X.md あり)
  -> stdout: 'tickets/active/X.md'
  ```

  この場合 `fnmatch.fnmatchcase("active", "[:a]ctive")` も `True`（実測）であり、
  `:` を追加した候補抽出＋既存のactive/done照合ロジックの組み合わせで
  `find_violation('rm tickets/[:a]ctive/APP-001.md')` は実際に **deny された**
  （2-3の表参照）。**これは真陽性であり、新規の誤denyではない。**
- 対照的に、真のPOSIXクラス構文 `[[:alpha:]]`・`[[:upper:]]` 等（コロンで
  名前を挟む厳密な2文字境界形）はbashでは「文字種カテゴリ全体」を意味する
  広い一致だが、Pythonのfnmatchは常に「ブラケット内の文字を字面どおりの
  要素集合」として扱うため、この2つの意味論は `:` の追加だけでは絶対に
  一致しない（2-1・2-3で実測確認）。**閉塞するには、fnmatchへ渡す前に
  `[:alpha:]` のような真のPOSIXクラス片を等価なPython `re` 文字範囲
  （例: `[a-zA-Z]`）へ変換する専用のトランスレータが必要**であり、
  「候補抽出の文字集合を広げるだけ」の対処では原理的に閉塞できない
  （判断材料。対処するか・既知の限界として明記して見送るかはarchitectの決定）。

## 5. `^`/`:` 追加による誤deny方向の副作用（実測。5パターン＋追加検証）

### 5-1. チケット指定の5パターン（実測。widenedのみ・normalizeなし）

| コマンド | before候補 | after候補（`^:` 追加） | find_violation（before/after） |
|---|---|---|---|
| `grep '^foo' file.txt` | `['grep','foo','file.txt']` | `['grep','^foo','file.txt']` | None / None |
| `sed 's/^x/y/' file.txt` | `['sed','s/','x/y/','file.txt']` | `['sed','s/^x/y/','file.txt']` | None / None |
| `awk -F: '{print $1}' file.txt` | `['awk','-F','{print','1}','file.txt']` | `['awk','-F:','{print','1}','file.txt']` | None / None |
| `PATH=a:b; date` | `['PATH','a','b','date']` | `['PATH','a:b','date']` | None / None |
| `git log --format=%h:%s` | `['git','log','--format','h','s']` | `['git','log','--format','h:','s']` | None / None |

いずれも merged token に `GLOB_META_CHARS`（`*?[`）を含まないため、
`_guarded_paths_from_expanded` の②分岐（glob成分の事前フィルタ）に一切入らず、
①の直接一致（`_is_guarded_path`）にも該当しない。**したがってこの5例に限れば
`^`/`:` を追加しても誤denyは発生しない**（実測で確認。ただし網羅的な反証には
なっていないことに注意）。

### 5-2. ブラケット+コロン/キャレット合成での探索（実測。追加で試したパターン）

`tr -d '[:space:]' < file`・`grep -o '[[:alpha:]]' file`・
`sed 's/[[:blank:]]\+/ /g' file`・`awk -F'[:,]' '{print $1}' file`・
`cut -d: -f1 file` を widened regex で試したが、いずれも `find_violation` は
`None`（変化なし）。理由: マージ後の成分が `space`・`alpha`・`blank`・`,`
であり、`active`／`done`／`SPEC.md` のいずれの末尾構造とも一致しないため。
**「ブラケット+コロン」が真に誤denyを生むのは、成分が偶然
`[:x]tail` の形で `tail` が `active`/`done`/`ctive` 等の一部と組み合わさり
`GUARDED_DIR_NAMES`/`GUARDED_FILENAME` にfnmatch一致する場合に限られ、
現実的な日常コマンド（`tr`/`grep -o`/`sed` のPOSIXクラスイディオム）では
この構造が偶然形成される可能性は低い**（4章の `tickets/[:a]ctive` は
意図的に構成した例であり、実運用での典型例ではない）。

### 5-3. 組み合わせシミュレーション（widened + `[^`→`[!` 正規化を同時適用）

```
rm docs/[^x]PEC.md            -> DENY（意図どおり）
rm docs/[^s]PEC.md            -> DENY（意図どおり）
rm tickets/[^x]ctive/APP-001.md -> DENY（意図どおり）
cat docs/[^x]PEC.md           -> None（読み取りhead対称性は保たれる。ALLOWED_HEADSの
                                  仕組み上、gate_hitがTrueになってもcatは無条件許可のため）
rm docs/[[:upper:]]PEC.md     -> None（依然未検出。4章のとおり構造的限界）
grep '^foo' 等5例             -> すべてNone（5-1と同じ結果を維持）
```

この結果は、`^`/`:` の追加＋位置依存の `[^`→`[!` 正規化という対処の方向性が
「読み取りhead対称性」「非glob誤deny予算」を壊さずに `[^...]` 一般形を
閉じられることを示す一方、POSIXクラスは対処の対象外として残ることを示す
（対処方針の採否自体はarchitectの決定事項）。

## 6. KLK-018/031/032/033 との整合

- 読み取り専用head（`cat` 等）のallow対称性: `ALLOWED_HEADS` に含まれるheadは、
  gate_hit（言及ゲート）が真になっても単純呼び出し（リダイレクトなし）では
  無条件allowになる構造（`statement_violation` 等が別途 head 判定を行う設計）。
  KLK-018 `test_klk018_fragmented_glob_spec_side_read_allow`／KLK-032
  `test_klk032_spec_side_read_allow`／KLK-033
  `test_klk033_negated_class_spec_side_read_allow` の3代とも同じ仕組みに
  依拠しており、本チケットの修正もこの構造を変更しない限り対称性が
  自動的に維持される（5-3で `cat docs/[^x]PEC.md` が allow のままである
  ことを実測確認）。
- `has_literal_char` ゲート（KLK-031）: 成分が `GLOB_META_CHARS` 以外の文字を
  最低1文字含む場合のみSPEC.md照合対象に加える設計。`^`/`:` を
  `GLOB_META_CHARS` に含めない限り、これらは「リテラル文字」としてカウント
  され続け、KLK-033の `!` と同じ扱いになる（KLK-033設計書§3 D1根拠2と同型の
  判断材料。architectが同様の結論に至るかは本調査の範囲外）。
- case-insensitive化（KLK-032/033）: `is_spec_basename_fnmatch` の和集合形は
  第1項（そのままの大小）・第2項（`.upper()` 正規化）のいずれかで真になる構造。
  `[^x]PEC.md` 一般形はどちらの項でも偶然一致しない（2-1参照）ため、既存の
  和集合形だけでは閉じられず、`[^`→`[!` 正規化という**候補文字列そのものの
  書き換え**が必要になる点が、KLK-032/033の「述語の拡張のみで閉じた」対処とは
  質的に異なる（reviewerがMedium 3-3で指摘した「候補の分断規則の変更は単調
  ではない」と同根の論点）。

## 7. 既存テストのbaseline（実測）

- `python3 -m unittest discover -s tests -p "test_*.py"` → `Ran 818 tests` `OK`
  （2026-08-19本セッションで再実行。チケット記載のbaseline 818件と一致）。
- `tests/test_guard_bash_writes.py` 内の `test_klk033_*` メソッド数: 11件（grep実測）。
- `tests/test_ticket_lib.py` 内の `is_spec_basename_fnmatch` 関連テスト: 6件
  （既存4件＋KLK-033追加2件 `test_is_spec_basename_fnmatch_negated_class_monotonic_true`／
  `..._excluded_false`）。
- 本チケットの修正候補となる直接関連テスト群: `test_klk033_negated_class_*`
  （SPEC.md側9件）、`test_klk033_negated_class_guarded_dir_side_*`・
  `test_klk033_bang_adjacent_guarded_dir_literal_allow`（tickets側3件、
  コミット `0d0571f`）、`test_klk033_degraded_*`（degraded経路2件）。
  これらはいずれも `[!...]` 専用の期待値（deny/allow）を固定しているため、
  本チケットの修正（`^`/`:` 追加・正規化）実装時に**候補抽出の挙動が変わって
  これら既存ケースの分断・一致結果を変えないこと**が回帰確認の要点になる
  （`!` 関連の既存ケースは `SHELL_EXPAND_PATHISH_RE` の文字集合へ `^`/`:` を
  「追加」するだけであれば `!` 自体の扱いは変わらないはずだが、正規化ロジックの
  実装によっては `[!...]` 成分の走査順にも影響しうるため、既存 `!` 系テストの
  全件再実行が必須）。

## 8. Medium指摘3件の事実確認

### (a) `docs/designs/KLK-033.md` §5/§7 と実測の食い違い

- §5冒頭表: 「対応方針 | ... | 影響あり（`[!...]` 含み語の検出面が広がる。
  **deny方向のみ**）」という記述。
- §7冒頭: 「判定の変化は…の2点のみで、**既存のdenyがallowへ転じる変化は
  構造的に発生しない**（和集合形は既存Trueを保持する単調拡張であり…）」。
- reviewerの実測（`docs/reports/KLK-033/review.md` §3-3）で
  `rm docs/SP*.md!y`・`rm docs/S*.md!`・`rm docs/SPE?.md!`・
  `rm tickets/acti*e!x/APP-001.md` の4形が **develop→KLK-033でDENY→allowに
  転じる**ことが確認されている（いずれもbashでは保護対象に一致しない語であり、
  是正自体は正しい＝旧denyが誤denyだった）。原因は「和集合形は単調」という
  主張自体は成立するが、**候補抽出（`SHELL_EXPAND_PATHISH_RE`）の文字集合変更が
  トークンの結合境界を変えるため、候補分断規則の変更それ自体は単調ではない**
  （以前は独立候補だった `!` 区切りの断片が1つの大きな候補へ吸収され、
  glob構造条件を満たさなくなるケースが生じる）。§5/§7はこの「候補分断規則の
  非単調性」を評価しておらず、記述として不正確——本チケット自身も
  `SHELL_EXPAND_PATHISH_RE` の文字集合を再度変更するため、同種の非単調な
  候補結合変化が起こりうる（5章の実測では偶然発生しなかったが、
  §5/§7の表現をそのまま踏襲すると同じ誤りを繰り返す）。

### (b) §8ロールバック手順のコミット構成

- 現行§8: `git revert {Phase2コミットハッシュ} {Phase1コミットハッシュ}`
  （`d3ca849` と `09af704` のみを指す）。tester追加コミット `0d0571f`
  （`docs/reports/KLK-033/review.md` 冒頭のコミット一覧に明記）が含まれない。
- 実測: pre-KLK-033版（`git show 4698e22:.claude/hooks/guard_bash_writes.py`
  を分離実行）で `find_violation('rm tickets/[!x]ctive/APP-001.md')` は
  `None`。一方 `0d0571f` で追加された
  `test_klk033_negated_class_guarded_dir_side_deny` はこのコマンドに対し
  `assertDeny` を要求する。**したがって§8の手順どおり `0d0571f` を含めずに
  Phase1・Phase2のみをrevertすると、このテストが（実装が旧挙動へ戻るため）
  失敗する**——チケット記載のとおりであり実測で確定。

### (c) docstring不正確・重複箇所の特定（シンボル名で参照）

- `_guarded_paths_from_expanded` のdocstring②（該当ブロックの一意引用）:

  ```
  SPEC.md 側の照合は大小を区別しない（KLK-032、lib.is_spec_basename_fnmatch
  経由）。active／done 側の照合は従来どおり大小を区別する。
  SPEC.md 側の照合は「そのままの大小での一致」と「大文字正規化後の
  一致」の和集合である（KLK-033。否定文字クラス `[!...]` の下で
  .upper() 正規化が非単調になる問題への対処）。
  ```

  1文目「大小を区別しない」（KLK-032由来）は、`_ticket_lib.is_spec_basename_fnmatch`
  のdocstring自身が明記する「残余の限界」（ブラケット表現を含む
  パターンでは `SPEC.md` 以外の大小変種を取りこぼしうる。例:
  `[!s]pec.md` は `False`）と矛盾する——**厳密には「大小を区別しない」のではなく
  「2項の和集合で近似する（完全な大小非依存ではない）」**が正確な記述。
  2文目（KLK-033追加分）はこの和集合構造を正しく説明しており、実質的に
  1文目を包含・訂正する内容であるため、同じ主語（SPEC.md側の照合）について
  異なる精度の記述が連続する重複になっている。
- モジュールdocstring「既知の限界」のKLK-033箇条書き（一意引用の末尾部分）:

  ```
  残余の限界として、ブラケット表現を含むパターンについては `SPEC.md` 以外の
  大小変種（`Spec.md` 等）を対象とする一致を取りこぼしうる（例:
  `docs/[!s]pec.md`）。詳細は docs/designs/KLK-033.md 参照。
  ```

  この段落は「残余の限界」として**大小変種の取りこぼしのみ**を挙げており、
  `[^...]`（キャレット否定）・`[[:class:]]`（POSIXクラス）が**候補抽出の
  段階で一切検出されない**というより重大な限界（本チケットの主題そのもの）
  には一切触れていない。reviewerのHigh §3-2が指摘したとおり、読み手は
  「KLK-033で否定文字クラス全般が閉じた」と誤解しうる記述になっている。
  本チケットの受け入れ条件（「対応済みの否定構文と未対応の構文を読み手が
  誤解しない形にすること」）が要求する更新対象は、この段落（および同型の
  記述が繰り返されている `guarded_paths_after_shell_expansion` の
  「KLK-033 による精緻化」ブロック——一意引用冒頭
  `上記の主張はいずれも「候補抽出（SHELL_EXPAND_PATHISH_RE）が語を分断しない」
  ことを暗黙の前提にしていた。` から始まるブロックの末尾も同じ「残余は大小変種のみ」
  という記述で終わっている）。

## 9. 検証スクリプト・参照ファイル

検証に用いた9スクリプト（`fnmatch_probe.py`・`repro_probe.py`・`realbash_probe.py`・
`falsedeny_probe.py`・`posix_colon_probe.py`・`posix_class_still_undetected_probe.py`・
`bracket_edgecases_probe.py`・`combined_simulation_probe.py`・`revert_impact_probe.py`）は
セッションのスクラッチパッドに残存しているが、リポジトリ外のためコミット対象ではない。
architect/implementerが再現したい場合は上記の出力からそのまま再現できる。

参照した既存ファイル（読み取りのみ、変更なし）:

- `.claude/hooks/guard_bash_writes.py`
- `.claude/hooks/_ticket_lib.py`
- `tests/test_guard_bash_writes.py`
- `tests/test_ticket_lib.py`
- `docs/designs/KLK-033.md`
- `docs/reports/KLK-033/review.md`
- `tickets/active/KLK-034_キャレット否定クラスとPOSIX文字クラスがpathish分断で検出されず誤allowされる.md`
