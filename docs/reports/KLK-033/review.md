# KLK-033 レビュー詳細

> reviewerレポートの詳細。チケット本文の「レビューメモ」には要点5行＋本ファイルへの
> ポインタのみを残す（orchestratorが代筆）。
> レビュー日: 2026-08-19 / worktree: `../kenesis-loop-kit.wt/KLK-033/`
> ブランチ: `fix/KLK-033-negated-class-glob-pathish-fragmentation`
> 対象コミット: `09af704`（Phase 1）・`d3ca849`（Phase 2）・`0d0571f`（tester追加）
> tester Quality Gate: **pass**（`docs/reports/KLK-033/test-report.md`）をレビュー開始前に確認

## 1. 検証方法（reviewerが独立に実施したもの）

1. `git diff develop...HEAD` の全量精査（コード2ファイル・テスト2ファイル・レポート2件のみ）。
2. `python3 -m unittest discover -s tests -p "test_*.py"` の再実行 → **Ran 818 tests, OK**
   （tester申告と一致）。
3. **差分挙動の実測**: `SHELL_EXPAND_PATHISH_RE` と `lib.is_spec_basename_fnmatch` を
   実行時のみdevelop形（旧正規表現・`.upper()` 単独）へ差し替え、同一コマンド集合に対する
   `find_violation` の deny/allow を新旧で対照（リポジトリのコードは変更していない）。
4. **実bashのglob真値確認（非破壊）**: 使い捨て `mktemp -d` に `docs/SPEC.md`・
   `tickets/active/APP-001.md` を作成し、`rm` ではなく `echo` でパターンの展開結果のみを確認。
   設計§3 D4 ①が禁じた「実ファイルへの `rm` 実行」は行っていない。
5. fnmatch意味論の直接確認（`fnmatch.fnmatchcase` と `lib.is_spec_basename_fnmatch` の比較）。
6. 検証スクリプトはセッションのスクラッチ領域（リポジトリ外）に置き、コミットしていない。
   `[!...]` を含む文字列はインラインBashへ書かず、すべてスクリプト経由で扱った（設計§4-4）。

## 2. 設計整合（§3 D1〜D4）

| 決定 | 実装 | 判定 |
|---|---|---|
| D1: `!` を既存集合の末尾（`\]` の直後）へ追加 | `re.compile(r"[A-Za-z0-9_.\-/{},*?\[\]!]+")` | 一致（設計・investigation実測形とバイト同一） |
| D1: `GLOB_META_CHARS` 無変更 | `frozenset("*?[")` のまま。`has_literal_char` 行・`if index == last_index and has_literal_char:`・`fnmatchcase(literal, component)`・`GUARDED_DIR_NAMES` も無変更 | 一致（差分ヒットはコメント本文のみ） |
| D2: 和集合形（(a)採用・(b)却下） | `if not isinstance(...): return False` ＋ `fnmatchcase("SPEC.md", pattern) or fnmatchcase("SPEC.MD", pattern.upper())` | 一致。非str契約も保持 |
| D3: docstring 3箇所 | `_guarded_paths_from_expanded` ②／`guarded_paths_after_shell_expansion` KLK-033ブロック／モジュール「既知の限界」 | 一致（指定文面どおり） |
| D4 ①: 実bash `rm` 検証は行わない | reviewerも `rm` 実行はせず `echo` のみで真値確認 | 遵守 |
| D4 ②: 既存4テスト無変更でPASS | 削除行0の純追加。`test_is_spec_basename_fnmatch_*` 4件PASS | 一致 |
| D4 ③: degraded必須2件＋任意1件 | 必須2件はimplementer、任意1件はtesterが実測 `allow` で固定 | 一致 |
| §4-5/§7: Phase 1を単一コミット・部分ロールバック禁止 | `09af704` に2変更同居（他ファイルなし）。docstring・設計§8に禁止を明記 | 一致 |

公開インターフェース: `is_spec_basename_fnmatch` の本番呼び出し元は
`guard_bash_writes._guarded_paths_from_expanded` の1箇所のみ（repo全grepで確認）。
他hook（`validate_ticket_state.py` 等）への波及なし。

## 3. 実測結果

### 3-1. 修正の効果（allow→DENY。すべて設計の意図どおり）

| コマンド | develop | KLK-033 |
|---|---|---|
| `rm docs/[!x]PEC.md` | allow | **DENY** |
| `rm docs/[!s]PEC.md`（和集合形が必要な形） | allow | **DENY** |
| `rm docs/S[!x]EC.md` | allow | **DENY** |
| `rm docs/[!x]P*.md` | allow | **DENY** |
| `rm tickets/[!x]ctive/APP-001.md`（tester補完分） | allow | **DENY** |

`cat docs/[!x]PEC.md`（読み取りhead対称性）・`rm foo!bar`・`rm a!b/c.md`・
`rm a{1,2}!b{3,4}.txt`・`echo !!`・`find . ! -name ...` は新旧ともallowで不変。

### 3-2. High: 同族の誤allowが未閉塞（`[^...]`・`[[:class:]]`。先在・本修正の回帰ではない）

実bash真値（使い捨てディレクトリに `docs/SPEC.md` を置き `echo` で展開）:

| パターン | bashの展開結果 | fnmatchcase("SPEC.md", p) | is_spec_basename_fnmatch(p) | hook判定（新旧同じ） |
|---|---|---|---|---|
| `[!s]PEC.md` | `SPEC.md` | True | True | DENY（本修正で閉じた） |
| `[^s]PEC.md` | **`SPEC.md`** | False | True（偶然） | **allow（誤allowが残る）** |
| `[^x]PEC.md` | **`SPEC.md`** | False | **False** | **allow（誤allowが残る）** |
| `[[:upper:]]PEC.md` | **`SPEC.md`** | False | False | **allow（誤allowが残る）** |
| `[!S]PEC.md` | 一致せず | False | False | allow（正しい） |

候補抽出の様子（`^`・`:` が文字集合に無く分断される）:
- `SHELL_EXPAND_PATHISH_RE.findall("rm docs/[^s]PEC.md")` → `['rm', 'docs/[', 's]PEC.md']`
- `findall("rm docs/[[:upper:]]PEC.md")` → `['rm', 'docs/[[', 'upper', ']]PEC.md']`

重要な補足: **`^` を文字集合へ足すだけでは閉じない。** Python `fnmatch.translate` は
先頭 `^` をエスケープするため `[^x]` は「`^` と `x` を含む肯定クラス」になり、bashの否定と
意味論が乖離する（`[^x]PEC.md` は上表のとおり両項Falseのまま）。閉じるには
`[^` → `[!` の正規化（設計が代替案(D)として却下した種類の前処理）が必要になる。
設計§3 D1の記述「POSIXブラケット式の `[!...]` と異なり、Python `re` の否定は `^` のみ」は
Python `re` についての言及であり、**bashのブラケット式が `^` を否定として受け付ける事実**は
investigation.md・設計書のいずれにも評価が無い（grepで確認）。

影響と扱い:
- 修正前後で判定は変わらない（新規に開いた穴ではない）。本修正は `[!...]` について厳密に
  改善しており、部分修正としての正しさは損なわれない。
- 実害の懸念は「記録の欠落」。新設のモジュールdocstring KLK-033箇条書き・設計§6は残余の
  限界を**大小変種のみ**として記述しており、否定文字クラス全般が閉じたと読める。
- 推奨: フォローアップチケット起票（人間判断）＋つなぎとして既知の限界1行の追記。

### 3-3. Medium: 設計§5・§7の不変条件の主張が不正確（DENY→allowが実在する）

差分挙動の実測で以下4形の `DENY→allow` を検出した:

| コマンド | develop | KLK-033 | bashの展開結果（実測） |
|---|---|---|---|
| `rm docs/SP*.md!y` | DENY | allow | `docs/SP*.md!y`（リテラル・保護対象に不一致） |
| `rm docs/S*.md!` | DENY | allow | `docs/S*.md!`（同） |
| `rm docs/SPE?.md!` | DENY | allow | `docs/SPE?.md!`（同） |
| `rm tickets/acti*e!x/APP-001.md` | DENY | allow | `tickets/acti*e!x/APP-001.md`（同） |

対照として `docs/SP*.md` → `docs/SPEC.md`、`tickets/acti*e/APP-001.md` →
`tickets/active/APP-001.md` はbashで実際に一致する（＝denyが正しい形）ことも確認済み。

評価:
- **危険はない。** 4形はいずれもbashが保護対象へ到達しないため、旧denyは誤denyであり、
  今回の変化はその是正である（候補が `!` を含む1語としてbashの語意味論に忠実になった）。
- しかし設計§5「deny方向のみ」・§7「既存のdenyがallowへ転じる変化は構造的に発生しない」は
  成立しない。理由: 和集合形は確かに単調拡張だが、**候補の分断規則の変更は単調ではない**
  （KLK-018/KLK-029の「OR追加」と異質。ある語で以前は独立候補だった断片が、より大きな
  1候補へ吸収されて構造条件を満たさなくなる）。
- なお `docs/SPEC.md!x`・`docs/SPEC.md!`・`!tickets/active/APP-001.md` は新旧ともDENYを
  維持する。これは `is_guarded_token_expanded` が `!` を含まない `PATHISH_RE` 版
  （`is_guarded_token`）とORで結合されているため。分断規則変更の影響が限定される仕組みは
  存在するが、glob成分側（`SP*.md` 等・`PATHISH_RE` では拾えない）には効かない。
- 対応（実行時挙動の変更は不要）: 設計§5/§7の表現を実測に合わせて訂正する。
  将来の文字集合変更時にこの誤った不変条件を前提にすると、真のdenyを黙って失う経路が
  生まれるため、記述の訂正は将来のリグレッション検出のために意味がある。
- 任意: `rm docs/SP*.md!y` を「bashが保護対象に一致しないため allow が正しい」という
  根拠コメント付きでallow固定すると、分断規則変更の検出器になる。

### 3-4. Medium: ロールバック手順が最新のコミット構成を反映していない

設計§8は `git revert {Phase2} {Phase1}` を提示するが、tester追加コミット `0d0571f` を
含まない。`0d0571f` の4件のうち `test_klk033_negated_class_guarded_dir_side_deny`
（`assertDeny("rm tickets/[!x]ctive/APP-001.md")`）は修正前はallow（3-1の表で実測）なので、
提示どおりrevertすると当該テストが**失敗する**。残る3件（degraded読み取りhead allow・
`[!d]one` allow・`activ!e`/`don!e` allow）は旧挙動でもallowのため影響しない。
→ revert対象に `0d0571f` を含めるよう §8 を修正するのが正。

### 3-5. Medium（軽微）: docstringの重複・旧記述の残置

`_guarded_paths_from_expanded` docstring② が
「SPEC.md 側の照合は大小を区別しない（KLK-032…）。」の直後に
「SPEC.md 側の照合は『そのままの大小での一致』と『大文字正規化後の一致』の和集合である
（KLK-033…）。」を並べる形になり、同じ主語の文が連続し、前者は現在は不正確。
設計§4-3が指定した文面どおりであり実装起因ではない。1文へ統合すると読みやすい。

## 4. テスト十分性の評価

- **bash意味論との一致を独立検証**（testerの期待値の根拠確認）:
  - `[!x]ctive` は `active` に一致（先頭 `a` は `x` でない）→ deny期待は正当。
  - `[!d]one` は `done` に不一致（先頭が実際に `d`）→ allow対照は正当。
  - `activ!e`・`don!e` はブラケットを伴わずGLOB_META_CHARSを含まないためglob分岐に入らず、
    bashでもリテラルで不一致 → allow期待は正当。
  - degraded読み取りhead（`cat docs/[!x]PEC.md # don't`）の実測 `allow` は正常経路の `cat`
    allowと対称で、KLK-018/032が確立した挙動からの逸脱なし。期待値の妥当性を確認した。
- 誤deny予算ロックは `rm`（ALLOWED_HEADS外）で言及ゲートを直接叩く形（`rm foo!bar`・
  `rm a!b/c.md`）を含むため、AC4の「ゲート自体の検証」を満たす。`find`/`echo` のみの
  ケースだけでは不足だったが、その点は設計・実装で正しく手当てされている。
- 単体（`SHELL_EXPAND_PATHISH_RE.findall` の1トークン保持・`_guarded_paths_from_expanded`
  の `["docs/SPEC.md"]`／`[]`）と end-to-end（サブプロセス実行の `assertDeny`/`assertAllow`）
  の両レベルが揃っており、原因レイヤーと外形の両方が固定されている。
- 不足（前掲）: 3-3のDENY→allow 4形の固定が無い。`[^...]`・`[[:class:]]` は既知ギャップの
  記録が適切（テスト化は閉塞時に破れるため非推奨）。
- 回帰: 全818件PASSをreviewer自身で再現。既存テストは削除行0の純追加で弱体化なし。

## 5. 既存資産への影響（KLK-018/031/032）

- KLK-018（ブレース展開・上限フォールバック）: `guarded_paths_after_shell_expansion` の
  `MAX_BRACE_CHAR_COUNT`／`MAX_BRACE_COMBINATIONS`／`RecursionError` 各分岐はいずれも
  `found.append(candidate)`（＝deny方向）で無変更。`!` による候補結合でコストが増えても
  合流先は安全側であることをコードで確認（`rm a{1,2}!b{3,4}.txt` は上限内でallow）。
- KLK-031（`has_literal_char` ゲート）: 定義・使用箇所ともバイト無変更。和集合形は
  「加えられたSPEC.mdをどう照合するか」のレイヤーにのみ作用し直交性を維持。
- KLK-032（case-insensitive化）: 第2項として保持され、既存4テストが無変更でPASS。
  第1項の追加は「bashの照合意味論そのもの」であり、第1項がTrueならbashも一致するため
  第1項が新たな誤denyを作ることは構造的にない（この健全性はコードから確認できる）。
- KLK-020（SPEC.md判定の `_ticket_lib` への集約）: 集約点は変えず判定式のみ拡張。

## 6. 結論

- Approval Status: **approved**
- 差し戻し不要。implementer起因の誤りは検出されなかった（設計文面への忠実な実装）。
  Medium 3-3/3-4/3-5は設計書の記述精度に関するもので、実行時挙動を変えない。
  High 3-2はスコープ外の先在ギャップで、フォローアップ起票の人間判断に委ねる。
- orchestrator依頼事項:
  1. 設計§5/§7の不変条件の表現を訂正、§8のrevert対象へ `0d0571f` を追記。
  2. `[^...]`・`[[:class:]]` 未閉塞を人間へ提示し、必要ならフォローアップチケットを起票。
  3. （任意）モジュールdocstringへ既知の限界1行、docstring②の重複解消。
