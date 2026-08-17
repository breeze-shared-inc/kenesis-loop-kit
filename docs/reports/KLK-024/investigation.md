# KLK-024 調査詳細

生成: investigator（代筆: orchestrator） / 最終更新: 2026-08-17
対象: `.claude/hooks/guard_bash_writes.py` の通常経路（`lex()`成功時）における、エスケープされたネストのバッククォート置換の未評価
要点はチケット `KLK-024` の「調査メモ」を参照。本ファイルは全文。

## Findings（全文）

1. 通常経路（`lex()`成功）でも `` `echo \`rm docs/SPEC.md\`` `` 形はallowのまま（実機のhook投入で確認済み＝empirical）。対照2件（`$(...)`内側の単純バッククォート／エスケープなしの単純バッククォート）は共に正しくdeny。
2. 原因は `_take_backtick` が `substs` へ格納する内容（`_skip_backtick` が見つけた終端までの生テキスト）から、bashのバッククォート特有の1段階アンエスケープ（`` \` ``→`` ` ``、`\$`→`$`、`\\`→`\`）を一切行っていないこと。
3. 再帰評価時（`find_violation`→`subst_violation`→`lex()`再呼び出し）、substsの生テキストにまだ `` \` `` が残っているため、`lex()`通常状態の**汎用エスケープ分岐**（`if c == "\\" and i + 1 < n:`）が**バッククォート専用分岐**（`if c == "`":` → `_take_backtick`呼び出し）より**先に**評価され、`` \` `` を単なる2文字リテラルとして語（buf）へ吸収してしまう。結果として内側の`rm ...`は新規substsエントリにならず、どのheadチェックの対象にもならない。
4. `_skip_backtick`／`_skip_balanced`自体の「境界探索」（外側バッククォートの終端を見つける処理）は正しい（bashと同じくエスケープされたバッククォートを終端とみなさず読み飛ばす）。バグは境界探索ではなく、**抽出したテキストをそのまま次のlex()呼び出しに渡している**（アンエスケープしていない）点にある。
5. `find_violation`／`subst_violation`自体のロジックは正しく、substsに入った文字列を無条件で再帰評価する。バグの所在は`_take_backtick`（抽出時）に限局しており、`find_violation`側の変更は原理上不要と判断できる。

## Evidence（全文）

- kind: empirical — hookへstdin JSON経由で6ケース投入。エスケープされたネスト2形（SPEC.md/tickets/active双方）はexit0・stdout空（allow）、対照4形は全てdeny。
- kind: codebase — `guard_bash_writes.py` の `lex()`（通常状態ループ）の分岐順序。汎用エスケープ分岐が`c == "`"`分岐より前にあることをコード中で確認（現在の行番号は`_skip_balanced`:724, `_skip_backtick`:774, `_take_backtick`:804, `lex`:945。KLK-015マージにより調査中に旧行番号2011行版→2350行版へシフトしたためシンボル名を正とする）。
- kind: empirical — 直接importでの内省（`guard.lex(guard.normalize_line_continuations(...))`）により、substs[0]の再帰lex結果が`tokens=[('w','echo'),('w','`rm'),('w','docs/SPEC.md`')], substs=[]`となることを確認（新規substsが作られない＝再帰評価の入口に立たない、の直接証拠）。
- kind: empirical — 実機bash（本hookとは無関係、bash自体の仕様確認。`echo`のみで検証、rm等は未実行）で、(a) `$(...)`内側の`\``はアンエスケープされず**リテラルのまま**（`echo $(echo \`echo x\`)`→文字通り`` `echo x` ``が出力）、(b) 実際のバッククォート内側の`\``は**アンエスケープされ再解釈される**（`echo `echo \`echo x\`` `→`x`が実行される）、(c) 3階層ネストは1階層ごとにバックスラッシュを倍加する規則に従うことを確認。
- kind: codebase — `tests/test_guard_bash_writes.py`：現在212テスト全件pass（本バグを検出する回帰テストは未追加のためpass自体はバグの証拠にはならないが、`LEGACY_DENY_COMMANDS`・既存deny対象は現状回帰していないことの確認）。

## 詳細1: `_skip_backtick`/`_take_backtick`の正確な動作

`_skip_backtick(command, start)`（シンボル名を正とする。行番号は調査中のマージでシフトあり）:

```python
def _skip_backtick(command, start):
    i, n = start, len(command)
    while i < n:
        if command[i] == "\\" and i + 1 < n:
            i += 2
            continue
        if command[i] == "`":
            return i + 1
        i += 1
    return -1
```

このヘルパは「終端（クローズ側）のバッククォートを探す」役割で、`\`+任意の1文字`を無条件でペアとして読み飛ばす（＝エスケープされたバッククォートは終端とみなさない）。これはbashの「バッククォートをスキャン中は`` \` ``が終端にならない」という規則の**境界探索部分**を正しく実装している。

`_take_backtick(command, start, buf, substs)`:
```python
def _take_backtick(command, start, buf, substs):
    end = _skip_backtick(command, start)
    if end < 0:
        raise ValueError("no closing backquote")
    substs.append(command[start:end - 1])
    buf.append(SUBST_PLACEHOLDER % (len(substs) - 1))
    return end
```
`substs.append(command[start:end - 1])` は**生のスライス**をそのまま格納する。すなわち、外側バッククォートの終端探索で読み飛ばした`` \` ``の**バックスラッシュ自体はここで一切除去されない**。bashの実際の規則では、バッククォートの内容を確定させる際に`` \` ``→`` ` ``（および`\$`→`$`、`\\`→`\`）の**1段階アンエスケープ**が行われ、その結果生じる生のバッククォート対が、内容を実行するサブシェルにとって「新たな、エスケープされていないバッククォート対」として現れる。本hookはこのアンエスケープを一切実装していない。

`_skip_balanced`（`$(`/`<(`/`>(`用）は、内側で見つけた（エスケープされていない）バッククォートの領域を`_skip_backtick`と**同じ規則**で読み飛ばす（コメントで明記: 「クォート外のバッククォート領域は `_skip_backtick` と同じ規則で読み飛ばす」）。これは`$(...)`の境界（対応する`)`）を見失わないための処理で、本チケットのバグとは別目的だが、内部で同じ`_skip_backtick`を呼ぶため同じ「エスケープされたバッククォートは読み飛ばす」規則を共有する。

`lex()`の通常状態（quote == ""）メインループの分岐順序（抜粋、意味は変えず順序のみ示す）:
1. 行継続関連の特殊ケース
2. 改行 → ステートメント区切り
3. **`if c == "\\" and i + 1 < n:` → `buf.append(c); buf.append(command[i+1]); i += 2; continue`**（汎用エスケープペア処理。任意の1文字をエスケープする目的の分岐で、`\;`・`\ `・`` \` ``などすべてがここで一律「2文字をリテラルとしてbufへ積む」処理を受ける）
4. クォート開始 `'`/`"`
5. `$'`/`$"` のANSI-C判定
6. `$(` → `_take_subst`
7. `<(`/`>(` → `_take_subst`
8. **`if c == "`": i = _take_backtick(command, i + 1, buf, substs); continue`**
9. 演算子
10. 通常文字の蓄積

分岐3が分岐8より**先**にあるため、`c == "\\"`かつ次の文字が`` ` ``であるケース（すなわち`` \` ``）は必ず分岐3で捕捉され、分岐8（`_take_backtick`呼び出し）には**到達しない**。これが本チケットの根本原因のコード上の所在である。

## 詳細2: なぜallowになるか ― トレースと直接内省による実証

対象コマンド: `` ls `echo \`rm docs/SPEC.md\`` `` （文字列としては `ls` + backtick + `echo ` + `\`` + `rm docs/SPEC.md` + `\`` + backtick）。

トップレベルの`lex()`呼び出し:
- `ls `の後、位置3の（エスケープされていない）`` ` ``に到達 → 分岐8がヒットし`_take_backtick`を呼ぶ。
- `_skip_backtick`は、内部の2つの`` \` ``をそれぞれ「バックスラッシュ+1文字」のペアとして読み飛ばし（終端とみなさない）、最後の（エスケープされていない）`` ` ``で終端。
- 結果、`substs[0] = "echo \\`rm docs/SPEC.md\\`"`（Pythonリテラル表記。実文字列は `echo ` + `\` + `` ` `` + `rm docs/SPEC.md` + `\` + `` ` ``）が**生のまま**格納される。ここまでは外側の境界探索としては正しい。

`find_violation`の再帰（`subst_violation` → `find_violation(inner, depth+1, cwd)`）で、この`substs[0]`が再度`normalize_line_continuations`→`lex()`にかけられる。実際に直接importして内省した結果（empirical）:

```
command: 'ls `echo \\`rm docs/SPEC.md\\``'
tokens: [('w', 'ls'), ('w', '__KLK_SUBST_0__')]
substs (top level): ['echo \\`rm docs/SPEC.md\\`']
--- recursing into substs[0] = 'echo \\`rm docs/SPEC.md\\`' ---
  inner tokens: [('w', 'echo'), ('w', '`rm'), ('w', 'docs/SPEC.md`')]
  inner substs: []
find_violation result: None
```

再帰後のlex()は、内側の`` \` ``（バックスラッシュ+バッククォート）に到達するたびに分岐3（汎用エスケープ処理）へ落ち、`buf`へ`` \` ``の2文字をそのまま積んで通過する。バッククォート自体が「単独の・エスケープされていない文字」として現れる瞬間が一度もないため、分岐8（`_take_backtick`）が一度も起動せず、新規`substs`エントリは作られない（`inner substs: []`）。flush時に`shlex.split`が`` \` ``のバックスラッシュを除去して`` ` ``だけを残すため、最終的な語トークンは`['echo', '`rm', 'docs/SPEC.md`']`となる（バッククォート文字自体は語の一部として生き残るが、もはや「置換の境界」としての意味を持たない）。

このステートメントのhead（先頭コマンド）は`echo`であり、`ALLOWED_HEADS`に含まれる。したがって、たとえ`docs/SPEC.md`という文字列が引数中に見えていても（`PATHISH_RE`は`` ` ``を含まない文字集合のため`docs/SPEC.md`部分だけがマッチし`guarded_paths`は真になる）、「保護対象に言及する語」が「許可された読み取り専用コマンドの引数」として現れているだけと判定され、write-vectorとしては扱われない。結果、`find_violation`はNoneを返し、allowになる。

## 詳細3: 対照2件がなぜ正しく動作するか

対照1: `` ls $(echo `rm docs/SPEC.md`) ``（`$(...)`内側に単純バッククォート、エスケープなし）
- `lex()`が`$(`に到達→`_take_subst`→`_skip_balanced`が`)`までを探索。内側で（エスケープされていない）`` ` ``に遭遇すると、`_skip_balanced`は`_skip_backtick`を呼んでその領域全体を読み飛ばし、対応する`)`を正しく発見する。
- `substs[0] = "echo `rm docs/SPEC.md`"`（生テキスト、エスケープなし）が格納される。
- 再帰`find_violation`が`substs[0]`を再度lexすると、内側の`` ` ``は**エスケープされていない**ため分岐8に直接ヒットし、`_take_backtick`が呼ばれ`inner_substs = ["rm docs/SPEC.md"]`が新規に作られる（empirical確認済み）。
- さらに1段再帰し、head=`rm`が`ALLOWED_HEADS`に無いため`"'rm' は許可されていません"`でdeny。

対照2: `` ls `rm docs/SPEC.md` ``（トップレベルの単純バッククォート、ネストなし）
- トップレベルの`lex()`が直接（エスケープされていない）`` ` ``に到達し分岐8がヒット。`substs[0] = "rm docs/SPEC.md"`。再帰後head=`rm`で即deny。

両対照とも、**バッククォートが「エスケープされていない」状態でlex()の走査に現れる**ため分岐8（`_take_backtick`）に正しく到達する。これがバグ形との唯一かつ本質的な違いであり、「エスケープされたバッククォートだけがバグを踏む」ことの直接証左になっている。

## 詳細4: `find_violation`の再帰評価と、修正がどこで十分か

`find_violation`はステートメント分割後、各ステートメント内の`__KLK_SUBST_N__`プレースホルダのインデックスを`statement_subst_indexes`で収集し、`subst_violation(substs, index, depth, cwd)`を呼ぶ。`subst_violation`は`MAX_SUBST_DEPTH`未満なら`find_violation(inner, depth+1, cwd)`を再帰呼び出しするだけで、**`substs`に何が入っているかについて一切の前提（エスケープの有無等）を持たない**。つまり`find_violation`／`subst_violation`は「渡された文字列をコマンド文脈として忠実に再評価する」という責務のみを持ち、その文字列を作る責務（バッククォートの内容を bash と同じ規則で復元する責務）は`_take_backtick`側にある。

したがって、`_take_backtick`が抽出した文字列に対して、bashのバッククォート内容確定規則（`` \` ``→`` ` ``、`\$`→`$`、`\\`→`\`の1段階アンエスケープ。**他の文字へのバックスラッシュはそのまま残す**——実機bashで確認: `` echo `echo hi` ``のように、対象文字以外へのエスケープは保持される）を適用してから`substs`へ格納するように直せば、以降は既存の`find_violation`／`subst_violation`の再帰機構がそのまま正しく機能する（新規substsを正しく作り、`rm`のheadチェックに正しく到達する）と判断できる。**`find_violation`自体の変更は不要**、というのが現時点の調査結論である（ただし多段ネストの一般化については後述参照。実機確認は3階層まで、`MAX_SUBST_DEPTH=3`と一致する範囲での確認に留まる）。

なお、`_skip_balanced`（`$(...)`用）に同じ「アンエスケープ」処理を追加してはならないことも実機確認済み（詳細1・下記参照）。`$(...)`内側の`` \` ``は実機bashでリテラルのまま解釈される（`echo $(echo \`echo x\`)` → 文字通り `` `echo x` `` が出力される）。この非対称性は本チケットの修正設計上の重要な制約になる。

## 詳細5: テスト構成と回帰テスト追加指針

`tests/test_guard_bash_writes.py`は単一クラス`TestGuardBashWrites(unittest.TestCase)`にすべてのテストを収め、`assertAllow(command)`/`assertDeny(command)`ヘルパ（`run_guard`経由でサブプロセス実行し、hookの実際のstdout JSON判定を検証）を使う。命名規則は`test_<内容>_deny`/`test_<内容>_allow`で、ticket由来の回帰は次のパターンで追加されている:
- ファイル冒頭の`LEGACY_DENY_COMMANDS`（削除禁止のリスト。「旧版がdenyしていた／過去に塞いだ穴」を1行ずつ列挙し、`test_legacy_deny_commands_all_still_deny`で一括検証）。
- ticket単位で`# --- KLK-XXX: ... ---`という見出しコメントブロックを追加し、その配下に`def test_h6_xxx_deny(self):`（KLK-014の例。T-H6a〜T-H6l のように設計書のテストID対応コメントを併記）を並べる。各テストのdocstring代わりにコメントで「T-番号（AC番号）: 何を固定するか」を明記する。
- KLK-014（H6・degraded側再帰評価）の書き方: `test_h6_backtick_substitution_write_vector_deny`のように、置換の型（`$(...)`/バッククォート/プロセス置換）×書き込みベクタの直積をsubTestで列挙し、ネスト（`test_h6_nested_substitution_deny`）・深さ境界（`test_h6_max_subst_depth_boundary_degraded_deny`）・cwd伝播（`test_h6_cwd_relative_path_propagation_deny`）・誤deny対照（`test_h6_readonly_substitution_inside_degraded_stays_allow`、`test_h6_category3_without_guarded_cwd_stays_allow`）を必ず対で固定している。

KLK-024の回帰テスト追加指針（investigatorの観察に基づく提案。設計はarchitect判断）:
1. `# --- KLK-024: エスケープされたネストのバッククォート ---`の見出しブロックを新設。
2. チケット再現手順1・対照1・対照2をそのまま固定するテストを追加し、保護対象2種（`docs/SPEC.md`・`tickets/active/*.md`）双方をsubTestで列挙する。
3. 多段ネスト（2階層・3階層、`MAX_SUBST_DEPTH`境界）の固定テストを、`test_h6_max_subst_depth_boundary_degraded_deny`と対になる正常経路版として追加することを推奨（実機bashのバックスラッシュ倍加規則に従った文字列を使うこと）。
4. 誤deny対照として、既存`test_backtick_readonly_substitution_allow`がそのまま通ることの回帰確認と、トップレベル単独の`` \` ``（ネストなし、bash実機ではリテラル）を含む読み取りコマンドがallowのままであることを新規に固定するテストを追加することを推奨する。
5. `LEGACY_DENY_COMMANDS`への追加要否は設計判断だが、リストの趣旨に照らすと、本チケットで新たに塞ぐ穴は追加対象になりうる。

## 詳細6: 修正の影響範囲

- `LEGACY_DENY_COMMANDS`（現状42件超、確認済み全件denyのままpass。全212テストpass）は本チケットのバグとは無関係のコード経路（`_take_backtick`のエスケープ処理）にのみ触れる想定の修正であれば影響を受けないと推測される。ただし実装後は必ず全件再実行して確認が必要。
- 日常の読み取り操作（grep・catなど、バッククォートを一切含まないコマンド）は、`lex()`のバッククォート関連分岐（3・8）に一度も到達しないため、`_take_backtick`だけを直す修正であれば**一切触れない**。誤deny増加のリスクは、バッククォートを実際に使うコマンド（`` `date` ``的な日常パターン）に限定される。
- 実機確認（詳細2参照）により、トップレベル単独の`` \` ``（他のバッククォートに包まれていない、エスケープされたバッククォート単体）は常にリテラル文字としてbashに解釈される。`_take_backtick`内だけを直す修正であれば、このようなトップレベル単独の`` \` ``パターンには一切触れないため、新規の誤deny源にはならないと推測される（実装後の網羅的な回帰テストでの確認が必要）。
- 想定される修正パターンの比較:
  - (a) 「`_take_backtick`の抽出結果に対してのみ`` \` ``/`\$`/`\\`をアンエスケープしてからsubstsへ格納する」— 実機bash仕様と一致する最小修正。`_skip_balanced`側は変更しない（変更すると`$(...)`内の良性の`\``パターンを誤ってネスト開始とみなし新規の誤deny源になりうる）。
  - (b) 「判定不能とみなし保守的に全体deny」（ANSI-Cクォート`$'...'`と同様の「判定不能マーク」方式）— アンエスケープの実装を避けられるが、良性の`` \`echo hi\` ``的パターン（ネストしているが内側が読み取り専用）まで一律denyになり、既存の誤deny予算に抵触する可能性がある。
  - どちらを採るかはarchitectの設計判断であり、investigatorとしてはコード事実・実機挙動の提示に留める。

## Unknowns（全文）

- **KLK-014の`_extract_degraded_substs`が同型の「エスケープされたネスト」バグを持つか未検証。** 検証方法: degradedへ落ちる形（末尾` #'`等）に本チケットと同じエスケープ済みネストバッククォートを組み合わせた入力をhookへ投入し、allow/denyを確認する。なお、この論点自体はチケットKLK-024の受け入れ条件に既に「KLK-014のdegraded側修正との関係を整理する（共通化できるかは設計判断とする）」と明記されており、architectの設計判断として想定済みの論点である。
- 本番運用で使われうるbashバージョン（POSIX sh実装差異、dash等）でこのバックスラッシュ規則が完全に同一かは未検証（本hookは「コマンド文字列がbashに解釈される」ことを前提にしている設計のため、影響は限定的と推測されるが確定情報ではない）。

## 関連ファイル（絶対パス）
- `.claude/hooks/guard_bash_writes.py`（`_skip_balanced`・`_skip_backtick`・`_take_subst`・`_take_backtick`・`lex`・`subst_violation`・`find_violation`）
- `tests/test_guard_bash_writes.py`（`LEGACY_DENY_COMMANDS`、`test_backtick_readonly_substitution_allow`、KLK-014系`test_h6_*`ブロック）
- `tickets/active/KLK-024_エスケープされたネストのバッククォート置換が正常経路でもallowのまま.md`
- `tickets/done/KLK-014_degradedモードがコマンド置換を評価しない.md`（参照のみ）
