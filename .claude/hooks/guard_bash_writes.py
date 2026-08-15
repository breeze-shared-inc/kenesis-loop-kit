#!/usr/bin/env python3
"""PreToolUse hook - チケット・SPEC.md への Bash 書き込みゲート

Bash ツールの実行前に発火し、コマンドが保護対象
（tickets/active|done/ 配下・basename が SPEC.md のファイル）に言及している場合、
読み取り・移動系のホワイトリストに載らないコマンドを deny で弾く。

チケット状態機械の強制境界は Write/Edit の PreToolUse hook にあるため、
Bash 経由の書き込み（リダイレクト・sed -i・tee・`python3 -c` 等の
インタプリタワンライナー・find -exec・ヒアドキュメント）は検証を迂回できてしまう。
この hook はその迂回路をベストエフォートで塞ぐ。パスをリテラルに含まない
迂回（変数展開・スクリプト内での組み立て）はすり抜けるが、それは
check_loop_integrity.py のドリフト検知（Stop）が捕捉する。

判定は3レイヤに分かれる。

  L1 字句（lex）— クォート状態だけを追跡して走査し、**クォート外の**演算子
    （`;` `&&` `||` `|` `>` `>>` `<<` 等）を最長一致で切り出す。演算子で区切った
    語チャンクは shlex.split(posix=True) でクォート解除する。したがって正規表現や
    パターンの中にある `|` `<<` `>` `#`（例: `grep -E '^(id|title):' tickets/...`）は
    ステートメント分割・特殊構文判定を引き起こさない。`$(...)` / バッククォート /
    プロセス置換は内側テキストを substs へ退避し、元の位置には**位置インデックス
    付きのプレースホルダ**（`__KLK_SUBST_0__`）を置く。インデックスがあることで
    「どの語がどの置換に由来するか」を後段が復元できる。行継続（`\`+改行）は
    bash と同じく**削除して前後の語を連結する**（空白へ置換すると
    `rm tickets/acti\<改行>ve/APP-001.md` の語が割れて証拠が分断される）。
    ただしシングルクォートの**内側**では bash は行継続を解釈せずリテラルの
    `\`+改行として残す（＝そこで語が割れる）のに対し、本 hook は内側でも
    連結する。相違は**証拠が増える方向（保守側）**にのみ働く。

  判定不能なステートメント（ANSI-C 引用 $'...' / ロケール翻訳 $"...'）—
    bash はこの2形を**展開時にデコード／翻訳する**ため、hook が見る字面と
    コマンドが実際に受け取る文字列が一致しない（`$'…\x22…'` の `\x22` は
    実際には `"` になり、`\x7c` は `|` になる）。一致しないことが確定して
    いる以上、ホワイトリスト（awk のプログラム本文）でもブラックリスト
    （`system(` 等の照合）でも判定できない — 前者は「見えているテキストが
    安全か」しか確認できず、後者は符号化された字面に一致しないためである。
    そこで lex() は**クォート外の** `$'` / `$"` を検出して「判定不能」の印を
    トークン列へ残し（語の内容は1文字も変えない）、L3 は言及ゲート／保護対象
    cwd が成立した時点でそのステートメントを無条件に deny する。証拠が無い
    ステートメント（`printf $'a\tb'` 単独）は従来どおり allow である。
    ダブルクォート内の `$'` は bash も展開しないため印を置かない。
    判定は head 非依存（awk 限定にすると `sed $'s/a/b/\x77 ...'` が残る）。

  プレースホルダ契約 — L3 は置換を2方向に評価する。内側方向（置換の中身が
    書き込み。`ls $(rm tickets/...)`）は substs を同じ判定へ再帰させる。外側方向
    （置換の結果が外側の書き込みへ供給される。`rm $(echo docs/SPEC.md)`）は
    expand_substs で語を解決してから判定する。解決するのは「言及ゲート」
    「リダイレクト先」「変数代入値」「sed / awk の追加規則」の4用途。
    先頭コマンド名（head_of）と find / git の完全一致規則は解決しない
    （前者は置換をコマンド名に使う形をそのまま不許可にするため、後者は
    完全一致の意味論を保つため）。解決は証拠テキストを増やす操作であり、
    判定を緩める方向には働かない。

  L2 パス（guarded_paths）— 任意のテキストからパス様の候補を抽出し、
    os.path.normpath で正規化してから `.claude` 成分を除外して分類する。
    トークン境界に依存しないため `python3 -c "open('docs/SPEC.md','w')..."` のように
    1トークンへ埋め込まれたパスも検出する。正規化を除外判定より**先に**行うため、
    `./tickets/active/../../.claude/../tickets/active/X.md` のようなパストラバーサルで
    除外を悪用できない。素の字面で見つからないときに限り、ANSI-C エスケープを
    復号した字面でももう一度判定する（`rm $'\x74ickets/active/APP-001.md'` の
    ように**証拠そのものを符号化して隠す**形を捕捉するため）。復号は
    **証拠収集専用**であり、判定用テキスト（awk のプログラム本文・先頭コマンド
    名・cd の移動先）へ渡してはならない（「復号後は安全な形」と誤認する余地を
    作らないため）。復号器が誤っても最悪「証拠が増えない＝現状維持」になる。

  L3 構文（find_violation）— 「証拠があるときだけ deny する」。出力リダイレクトは
    ステートメント単位で判定し、リダイレクト先が保護対象パスか、**同一コマンド内で
    保護対象を代入された変数**を参照する場合に deny する（無関係な後段リダイレクト
    `cat tickets/... && echo x > "$TMP"` を巻き添えにしない）。パイプで連結された
    区間はどこかで保護対象に言及していれば全区間の先頭コマンドがホワイトリストに
    載っている必要がある（`find tickets/... | xargs rm` のようなパイプ越しの
    書き込み連鎖を防ぐため）。ホワイトリスト収載コマンドのうち引数だけで書ける
    ものには追加規則を持つ（sed の -i 全表記と w／W コマンド、awk の
    プログラム内リダイレクト・変数束縛・**オプション**〔既知の読み取り専用
    オプションのホワイトリスト。未知の `-` 始まりの語は deny〕・**プログラム
    本文**〔下記〕、sort の -o／--output、uniq の第2位置引数、find の
    書き込み系フラグ、git のサブコマンド）。

  awk のプログラム本文（awk_program_violation）— awk が実際に実行する
    テキスト（`-e` / `--source` の値と、無ければ位置引数の先頭オペランド）
    だけを取り出し、**ホワイトリスト**で判定する。ファイル名オペランド・
    変数束縛値は awk が実行しないため判定対象にしない。判定は
    (1) 文字列・正規表現リテラルを**左→右の1パス**で除去し
    (2) 許可文字集合（`@` と `|` を含まない＝間接呼び出し・@load・
    出力パイプ・`"cmd" | getline`・コプロセスの入口を閉じる）
    (3) 呼び出し名の許可集合（`system` を含まない。同一プログラム内で
    `function NAME(` と宣言された名前は許可。**未知の名前は deny**）
    (4) `print`/`printf` の後に `>` `>>` `|` が現れる出力構文の不在
    の4段で行う。**未知の文字・未知の関数名は自動的に deny 側へ落ちる**ため、
    gawk に新しい実行経路が加わってもホワイトリストへ収載しない限りすり抜け
    ない（規則を積み増すブラックリストではこの次元で4ラウンド連続して穴が
    出たため、第4版でホワイトリストへ反転した）。1パス除去でなければならない
    のは、2パス（文字列を全部消してから正規表現を消す等）だと片方のリテラルの
    内側に見える引用符／スラッシュが実際には外側にあるコードを飲み込むため
    （`/"/ {system("rm F")}` と `BEGIN{x="(/a"; system("rm /F")}` が実例）。
    なお degraded mode（下記）は空白分割でプログラム本文の同一性が失われる
    ためこの判定を適用できず、`system(` / `@load` / `@include` と間接呼び出し
    `@f(...)` のブラックリスト（語単位＋空白結合テキスト）で見る。

  書き込み先オペランドと cwd — 語のうち**構文的に書き込み先と確定している**もの
    （出力リダイレクトの直後の語・sort の -o の値・uniq の第2位置引数）だけを
    「書き込み先オペランド」と呼び、cwd との結合（相対パスの解決）は
    guarded_write_target でこのオペランドに限って行う。任意の語へ cwd を
    結合してはならない（tickets を部分文字列で判定するため
    `tickets/active/NR>1 {print}` のような語が保護対象と誤判定される）。
    `cd` は作業ディレクトリを追跡し（セグメント自体は常に許可）、保護対象配下へ
    移動した後はステートメントの言及ゲートを無条件に真とする。書き込み先
    オペランドを取り出せない書き込み形（awk の `print > "REL"`・sed の
    `w REL`）は、保護対象を cwd とする場合に「構文の存在」で deny する（保守側）。
    保護対象 cwd 下で許可する先頭コマンドは CWD_SAFE_HEADS の明示列挙であり、
    ALLOWED_HEADS へ足すだけでは cwd 下の許可を得られない（棚卸し忘れが
    deny 側へ落ちるフォールセーフ既定）。

保護対象パスの判定（guarded_paths / is_guarded_token）は _ticket_lib.is_ticket とは
**意図的に基準が異なる**。is_ticket は「Write/Edit の対象ファイルが状態検証対象の
実チケットか」を判定する厳密判定（絶対パス・前後スラッシュ・.md 拡張子を要求）である
のに対し、本 hook が必要とするのは「コマンド文字列の断片が保護対象に言及しているか」
という再現率優先の判定（相対パス・ディレクトリ指定・引用符やコードの中に埋もれた
パスまで拾う）である。統一すると `ls tickets/active/` や `docs/SPEC.md` を取りこぼす
ため、統一しない。

既知の限界:
  - 別のコマンドで export された変数経由のリダイレクトは検出できない（hook は
    1回の Bash 呼び出ししか見えない）。tickets/ 宛ては check_loop_integrity.py の
    ドリフト検知がバックストップになるが、docs/SPEC.md 宛てにはバックストップが無い。
  - **シェル展開の次元**（bash が解釈するがコマンド文字列上は見えない変換）の
    うち、次は**未対応**である。いずれも本 hook の導入当初から allow で、
    保護対象パスがコマンド文字列上で再構成できないため検出できない:
    ブレース展開（`rm tickets/{active,done}/APP-001.md`）、パス中に `*` が
    入って分断される glob（`rm tickets/acti*e/APP-001.md`）、パラメータ展開
    （`f=tickets/active/APP-001.md; rm $f` の**引数側**。値が別コマンドで
    export された場合は原理的に見えない。リダイレクト先については同一コマンド
    内の代入を guarded_vars が追跡して deny する）。`tickets/active/*.md` の
    ように保護対象ディレクトリが素で残る形は従来どおり deny される。
    ANSI-C 引用・ロケール翻訳・行継続は上記「判定不能なステートメント」と
    L1 の行継続連結で対処済み。履歴展開（`!!`・`!$`）は非対話シェルでは
    既定で無効のため相違を生まない。
  - cd の作業ディレクトリ追跡はリテラルのオペランドに限る。`cd "$DIR"` /
    `cd $(...)` / `cd` / `cd -` は追跡を打ち切り、以降は cwd による強化を行わない。
  - cwd と相対パスの**両方に接頭辞が分割**された形は捕捉できない
    （`cd tickets/active && cd .. && rm active/APP-001.md`）。cwd が
    `tickets` へ戻るため cwd 判定が偽になり、`active/APP-001.md` 単体は
    保護対象パターンに一致しない。一般解は `cd . && rm foo` のような形まで
    deny する誤deny爆発を招くため実装していない。
  - `mv` は保護対象 cwd 下でも許可する（`cd tickets/active && mv /tmp/e
    APP-001.md`）。CLAUDE.md が active/ ↔ done/ の移動を Bash `mv` の正規手段と
    定めているためで、**意図的な許可**である。
  - degraded mode（下記）は旧版と同じ素朴な分割を使うため、クォート内の `|` と
    未閉じクォートが同時に成立する入力（`grep -E '^(id|title):' tickets/... # don't`）
    は誤denyになる。これは旧版と同一の挙動であり、正常に字句解析できる入力
    （コメントを伴わない同じコマンド）では発生しない。
  - degraded mode の awk には**プログラム本文のホワイトリスト（AW-7）が
    及ばない**（空白分割でプログラム本文の同一性が失われるため）。`|` 系は
    パイプ分割で後段の head が `getline`／`&` になりホワイトリスト非収載で
    deny、`system (`・`@ f(` は空白結合テキストで deny になるが、この経路には
    「未知の構文は deny」という機械的既定が無い。degraded の awk は旧版で
    常に deny だったため保護の後退ではない。
  - 保守側へ倒している判定（誤deny方向。保護対象に言及する／保護対象を cwd と
    する場合に限る）: 保護対象を cwd とする sed のスクリプトに ` w <非空白>` が
    現れる形（`sed 's/a w b/c/'`）／mawk・BWK awk 固有のオプション（`-W ...` 等）と
    gawk の未収載オプション（`-I`・`--trace`・`-O`・`-L`）は AWK_SAFE_FLAGS /
    AWK_SAFE_VALUE_FLAGS に無いため deny になる（安全性を確認してから収載する）／
    **awk のプログラム本文がホワイトリスト（AW-7）の3条件を満たさない形**は
    すべて deny になる。具体的には ① `@namespace` 指令（`@` は許可文字集合に
    無い） ② AWK_SAFE_CALLS 未収載の組み込み関数・拡張関数の呼び出し
    （gawk の新しい関数を含む） ③ `|` を伴う形（`print | "cmd"`・
    `"cmd" | getline`・`|&`。いずれも実際に外部コマンドを起動する）
    ④ リテラル**外**にバックスラッシュ・バッククォート・シングルクォート・
    非ASCII文字が現れる形 ⑤ `{print a (b)}` のような `IDENT (` 形の文字列連結
    （未知の関数呼び出しに見える） ⑥ プログラムが `$(...)`／バッククォート
    由来で、置換の内側テキストがシェル引用符を含む形 ⑦ 未閉じの文字列
    リテラルを含むプログラム ⑧ コメント（`#` 以降）に `@`・`|` を含む形
    （改行が `;` へ正規化されるためコメント範囲を確定できず除去しない）。
    いずれも deny 理由文が原因（許可されない文字／関数名）を示す。回避するには
    `cat`／`grep` を単独で使うか、保護対象パスを引数に取らない形にする。
    なお**文字列／正規表現リテラルの中身**（`print "contact: a@b (see docs)"`）
    と**プログラム以外のオペランド**（ファイル名 `'system(1).md'`・変数束縛値）
    は awk が実行し得ないため判定対象にしない（第4版で誤denyを解消した）／
    degraded mode では
    awk のプログラムが空白で分割されるため、`-` で始まる断片（`{print -$2}` の
    `-$2}`）がオプションと見なされて deny になる（旧版は degraded の awk を
    常に deny していたため回帰ではない。正常に字句解析できる同じコマンドは
    allow）／**クォート外に `$'...'` を含む形**（`awk -F$'\t' '{print $1}' T`・
    `grep $'\t' T`・`sed $'s/\t/ /' T`）は判定不能として deny になる。
    **回避策が確実に存在する**: `awk -F'\t'`（awk 自身がエスケープを解釈する）・
    `grep -P '\t'`・リテラルのタブを書く（`"$(printf '\t')"` は printf が
    ホワイトリスト非収載のため使えない）／同じく `$"..."` を含む形／
    degraded mode ではクォート状態を追えないため、引用符の**内側**に `$'`・
    `$"` の2文字並びがあるだけで deny になる（`awk '{print "cost: $"}' T #'`）／
    ANSI-C 復号によって保護対象パスが現れる語を含む形（`\x74ickets/...` の
    ような字面を実ファイル名として扱っている場合のみ）。
  - ホワイトリスト収載コマンドのうち次の書き込み／実行経路は**未対応**である。
    いずれも本 hook の導入当初から存在する穴で、別チケットで扱う:
    `python3 IDENTIFIER=VALUE <READONLY_SCRIPT> ...` による READONLY_SCRIPTS の
    許可経路の偽装（python3 が実行するのは `IDENTIFIER=VALUE` という名前の
    ファイルであり、**任意コード実行**に到達しうる。深刻度が最も高い）、
    `sed -f SCRIPT`（外部スクリプトでプログラムが不可視）、GNU sed の `e`
    フラグ・`e` コマンド（**任意コマンド実行**）、
    `sort --compress-program=PROG`（外部プログラム実行）、
    `git diff --output=FILE`。
  - パスがリテラルに現れない形（変数・置換の出力・断片の結合。
    `awk -v d=tickets -v f=active/X.md '{print > (d"/"f)}'` 等）は検出できない。
  - ALLOWED_HEADS へコマンドを追加するときの手順（設計書
    docs/designs/KLK-010.md §3-9・§3-10 と同内容）:
      1. `man <cmd>` / `<cmd> --help` を**4次元**で走査する
         （① 書き込みを行うオプション ② 外部コード〔プログラム・ライブラリ・
         拡張〕を読み込むオプション ③ プログラム／スクリプト内の書き込み・実行
         構文 ④ 位置引数そのものが出力先）。迷う経路は「危険」側に分類する。
      2. §3-9 の棚卸し表へ行を追加する（4列すべてを埋め、「なし」も明記して
         空白セルを残さない）。
      3. cwd 安全性を判定し、「書き込み経路が無い」「書き込み判定がパスに
         依存しない」「書き込み判定が cwd 対応済み」のいずれかを満たすときだけ
         CWD_SAFE_HEADS へ収載する（満たさない／判定できない場合は収載しない）。
      4. 新たに deny できるようになった形と、意図的に allow のままにする形の
         **両方**を tests/test_guard_bash_writes.py の LEGACY_DENY_COMMANDS と
         allow 固定テストへ追加する。
      5. 本「既知の限界」を更新する。

fail-open: 内部エラーでは allow。検知した違反のみ deny。ただし字句解析できない
入力（未閉じシングル／ダブルクォート・未閉じバッククォート・未閉じ `$(` ・末尾の
孤立エスケープの5系統。`don't` のような英文コメントでも成立する）は allow せず、
degraded_violation へ落とす。degraded は旧版の判定要素（全体の言及ゲート・
リテラルリダイレクト・heredoc の部分文字列判定・ステートメント分割・パイプ分割・
パイプライン単位の言及ゲート・セグメント判定）をすべて持つ。旧版から意図的に
外しているのは「リダイレクト先が `$` / バッククォートを含むだけで deny する」
規則のみ（無関係な後段リダイレクトの誤denyを解消するため）。
"""
import json
import os
import re
import shlex
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _ticket_lib as lib  # noqa: E402

# 保護対象に言及するコマンドで許可する先頭コマンド（読み取り・移動系）。
# 収載の条件は「引数だけでファイルを書き込む経路を持たない」か、
# **持つ場合はその経路を下記の追加規則で個別に deny できていること**
# （sed・awk・sort・uniq・find・git は後者。書き込み経路の棚卸しは設計書
# docs/designs/KLK-010.md §3-9 の表を正とし、追加時の手順はモジュール
# docstring「既知の限界」末尾の5手順に従う）。
# xargs（任意コマンド実行）・tee/cp/rm/touch（書き込み系）・
# python3/perl/ruby/node（任意実行。READONLY_SCRIPTS の例外のみ）は載せない。
ALLOWED_HEADS = {
    "ls", "cat", "head", "tail", "wc", "grep", "diff", "sort", "uniq",
    "stat", "file", "basename", "dirname", "test", "[",
    "cd",    # ディレクトリ移動のみ。セグメント自体は無条件許可。
             # ただし移動先は next_cwd で追跡し、後続の相対パス判定に使う
    "pwd", "echo", "cut", "tr", "nl", "rev", "realpath", "readlink",
    "mv",    # active/ ↔ done/ の移動・アーカイブは設計上 Bash mv が正規手段
    "sed",   # -i（in-place）・w コマンドが無ければ読み取り
    "awk",   # プログラム内リダイレクト（print > file）・system()・
             # 書き出し／外部コード読み込みオプションが無ければ読み取り
    "find",  # -exec / -delete 等が無ければ読み取り
    "git",   # サブコマンドを別途判定
}

# git は状態を書き換えないサブコマンド＋mv/ステージ/コミットのみ許可
# （checkout / restore / rm はチケットファイルを検証なしで書き換え・削除できるため除外）
ALLOWED_GIT_SUBCOMMANDS = {
    "mv", "add", "commit", "diff", "log", "show", "status", "blame",
}

# 保護対象ディレクトリを作業ディレクトリとする状況でも許可できる先頭コマンド。
# 収載の条件は「書き込み経路が無い」「書き込み判定がパスに依存しない
# （フラグ名・サブコマンド名で決まる）」「書き込み判定が cwd 対応済み」の
# いずれかを満たすこと（設計書 docs/designs/KLK-010.md §3-9「cwd 安全性」列）。
# ALLOWED_HEADS へ head を追加しても、ここへ収載しない限り保護対象 cwd 下では
# deny になる。棚卸しの忘れが deny 側へ落ちるフォールセーフ既定であり、
# 現行の ALLOWED_HEADS は全て収載済みのためこの規則は今は到達しない。
CWD_SAFE_HEADS = {
    "ls", "cat", "head", "tail", "wc", "grep", "diff", "sort", "uniq",
    "stat", "file", "basename", "dirname", "test", "[", "cd", "pwd", "echo",
    "cut", "tr", "nl", "rev", "realpath", "readlink", "mv", "sed", "awk",
    "find", "git",
}

FIND_WRITE_FLAGS = {"-exec", "-execdir", "-ok", "-okdir", "-delete",
                    "-fprint", "-fprint0", "-fprintf", "-fls"}

# sort / uniq の出力先オペランド抽出に使う（引数だけで書き込める経路）。
SORT_OUTPUT_FLAGS = ("-o", "--output")
UNIQ_VALUE_FLAGS = ("-f", "-s", "-w",
                    "--skip-fields", "--skip-chars", "--check-chars")

# 保護対象(SPEC.md等)を引数に取っても許可する読み取り専用スクリプト。
# いずれも読み取りのみで書き込み経路を持たないことを確認済み
# (スクリプト側のdocstringにも「書き込み処理を追加してはならない」と明記)
READONLY_SCRIPTS = (
    ".claude/skills/spec-interview/scripts/check_spec_structure.py",
)

# シェル演算子。種別とセットを1つの表から導出する（種別の宣言漏れを構造的に防ぐ）。
# 新しい演算子を足すときはここへ (演算子, 種別) を1行加えるだけでよい。
OPERATOR_KINDS = (
    # 3文字
    ("<<<", "heredoc"),
    # 2文字
    ("<<", "heredoc"), (">>", "redirect_out"), ("&>", "redirect_out"),
    (">&", "redirect_out"), (">|", "redirect_out"), ("<>", "redirect_out"),
    ("<&", "redirect_in"), ("|&", "pipe"),
    ("&&", "sep"), ("||", "sep"), (";;", "sep"),
    # 1文字
    (">", "redirect_out"), ("<", "redirect_in"), ("|", "pipe"),
    (";", "sep"), ("&", "sep"),
)
# 走査は先頭一致の最初の候補を採るため、必ず長い演算子から並べる。
# 表の並び順に依存しないよう、ここで長さの降順へ明示的に整列する
# （安定ソートなので同じ長さの相対順序は表のまま）。
OPERATORS = tuple(op for op, _ in
                  sorted(OPERATOR_KINDS, key=lambda kv: -len(kv[0])))
OPERATOR_KIND_MAP = dict(OPERATOR_KINDS)
OPERATOR_CHARS = ";&|<>"

# コマンド置換の退避先インデックスを埋め込むプレースホルダ。
# 「どのプレースホルダがどの置換か」を後段（言及ゲート・リダイレクト先判定）が
# 復元できるようにするため、不透明な固定文字列ではなく位置付きにしている。
SUBST_PLACEHOLDER = "__KLK_SUBST_%d__"
SUBST_PLACEHOLDER_RE = re.compile(r"__KLK_SUBST_(\d+)__")
MAX_SUBST_DEPTH = 3

PATHISH_RE = re.compile(r"[A-Za-z0-9_.\-/]+")
ASSIGN_RE = re.compile(r"[A-Za-z_][A-Za-z_0-9]*=")
VAR_REF_RE = re.compile(r"\$\{?([A-Za-z_][A-Za-z_0-9]*)\}?")
SED_INPLACE_SHORT_RE = re.compile(r"-[A-Za-z]*i")     # -i / -i.bak / -ni / -si.bak
SED_WRITE_RE = re.compile(r"(?:^|[;{}\s/])[wW]\s+\S")  # s/a/b/w FILE ・ /re/w FILE

# awk 専用（プログラム内リダイレクトと変数束縛の検出）
AWK_ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z_0-9]*=(.*)$", re.S)
AWK_STRING_RE = re.compile(r'"(?:\\.|[^"\\])*"')       # 文字列リテラル（除去用）
AWK_OUTPUT_RE = re.compile(r"\b(?:print|printf)\b[^;}\n]*(?:>>?|\|)")

# awk の「読み取りだけで完結する」オプション（値を取らない形）。**ホワイトリスト**
# であり、ここに無い `-` 始まりの語は未知＝deny 側へ落ちる（is_safe_awk_flag）。
# GNU Awk 5.2.1 の `awk --help` と突き合わせて収載した。意図的に載せていないのは
# 外部コード（プログラム・ライブラリ・拡張）を読み込む -f / -i / -l / -E / -D と、
# ファイルへ書き出す -o / -p / -d である（-i inplace は gawk の in-place 拡張＝
# sed -i の awk 版）。
AWK_SAFE_FLAGS = {
    "-", "--",
    "-b", "-c", "-C", "-g", "-h", "-n", "-M", "-N", "-P", "-r", "-s", "-S",
    "-t", "-V",
    "--characters-as-bytes", "--traditional", "--compat", "--copyright",
    "--gen-pot", "--help", "--non-decimal-data", "--bignum",
    "--use-lc-numeric", "--posix", "--re-interval", "--no-optimize",
    "--sandbox", "--lint-old", "--version", "--lint",
}
# 値を取る安全なオプション（-FVALUE / -F VALUE / --long=VALUE / --long VALUE）。
AWK_SAFE_VALUE_FLAGS = ("-F", "-v", "-e",
                        "--field-separator", "--assign", "--source", "--lint")

# awk の外部コマンド実行・拡張読み込み。文字列リテラル除去**前**の語に当てる
# （除去後より必ず広く一致する＝保守側）。
AWK_EXEC_RE = re.compile(r"\bsystem\s*\(|@(?:load|include)\b")

# gawk（4.1.2 以降）の**間接関数呼び出し** `@varname(...)`。関数名を文字列変数から
# 供給できるため、`system(` というリテラルがコマンド文字列に現れないまま
# system() を呼び出せる（`awk 'BEGIN{f="system"; @f("rm ...")}'`）。値の中身は
# 追跡せず**構文の存在**を証拠とする（AW-2 の変数束縛・AW-3 の出力構文と同じ
# 設計思想。エイリアスや文字列連結で容易に迂回できるため値の追跡は防御にならない）。
# 本ホストの GNU Awk 5.2.1 で成立するのは `@f(` と `@ f(`（`@` の直後の空白のみ許容）
# であり、`@f (` / `@"system"(` / `@(f g)(` / `@a[1](` / `@ENVIRON["X"](` は
# いずれも構文エラーになる（実測）。正規表現は成立形より広く取る（保守側）。
# **第4版で degraded mode 専用**（正常経路は AW-7 が担う）。
AWK_INDIRECT_CALL_RE = re.compile(r"@\s*[A-Za-z_][A-Za-z_0-9]*\s*\(")

# --- AW-7: awk プログラム本文のホワイトリスト --------------------------------
#
# awk のプログラム内構文の次元は、規則を積み増すブラックリストでは4ラウンド
# 連続して穴が出た（print > file → system() → @f() → "cmd" | getline）。
# 第4版ではこの次元を**ホワイトリストへ反転**し、「安全と確認できる狭い
# プログラム形」だけを許可する。未知の文字・未知の呼び出し名は自動的に
# deny 側へ落ちる（原則 P4 の3つ目の機械的既定）。

# リテラル（文字列・正規表現）除去後のプログラム本文に現れてよい文字。
# **ここに無い文字が1つでもあれば deny。** 意図的に含めない文字と根拠:
#   @  … 間接呼び出し @f( ・@load ・@include ・@namespace（gawk 拡張の入口）
#   |  … 出力パイプ print | "cmd" ・入力パイプ "cmd" | getline ・コプロセス |&
#   \ ` ' … リテラル外に現れる正当な用途が無い（行継続の \+改行は L1 が正規化）
#   非ASCII・制御文字 … gawk はリテラル外の非ASCII識別子を受け付けない
AWK_SAFE_PROGRAM_CHARS = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_"
    " \t"
    '$(){}[],;:?!~=<>+-*/%^&."#'
)

# 正規表現リテラルの開始か除算かを分けるための「直前の非空白文字がオペランドの
# 終端になりうるか」の集合（awk の字句規則の近似）。判定を誤っても「除算＝
# リテラルを除去しない＝内容が判定対象に残る」＝deny 方向へ倒れる。
AWK_OPERAND_END_CHARS = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_"
    '$)]".+-'
)

# 呼び出しを許可する名前。**ここに無い名前の `IDENT(` は deny。**
# system は意図的に非収載（AW-7 の中核。`system (` の空白形も IDENT\s*\( で
# 捕捉する）。getline は関数呼び出し構文を持たないため収載不要
# （`getline(` は awk の構文ではない）。収載を増やすときは man/info の説明に
# ファイル書き込み・プロセス起動が無いことを根拠として記録すること。
AWK_SAFE_CALLS = frozenset({
    # `(` を伴いうる構文キーワード
    "if", "else", "while", "for", "do", "switch", "case", "default",
    "return", "exit", "print", "printf", "delete", "break", "continue",
    "next", "nextfile", "function", "func",
    # 副作用の無い組み込み関数（GNU Awk マニュアルの Built-in Functions）
    "length", "substr", "index", "split", "sub", "gsub", "gensub", "match",
    "sprintf", "tolower", "toupper", "sin", "cos", "atan2", "exp", "log",
    "sqrt", "int", "rand", "srand", "patsplit", "asort", "asorti",
    "strtonum", "mktime", "strftime", "systime", "and", "or", "xor",
    "compl", "lshift", "rshift", "typeof", "isarray",
    # ストリームの解放のみで、プロセス起動・ファイル書き込みを行わない
    "close", "fflush",
})

AWK_CALL_RE = re.compile(r"([A-Za-z_][A-Za-z_0-9]*)\s*\(")
AWK_FUNC_DECL_RE = re.compile(
    r"\bfunc(?:tion)?\s+([A-Za-z_][A-Za-z_0-9]*)\s*\(")

# プログラム本文を供給するオプション（値は必ずプログラムとして検査する）。
AWK_PROGRAM_TEXT_FLAGS = ("-e", "--source")
# 値を「次の語」から取る安全オプション。**--lint は含めない**
# （gawk の --lint は省略可能引数のため `--lint=fatal` 形でしか値を取らない）。
# 載せ忘れると「その値をプログラム候補として検査する」＝deny 方向へ倒れる。
AWK_VALUE_CONSUMING_FLAGS = ("-F", "-v", "-e",
                             "--field-separator", "--assign", "--source")

# --- L1: ANSI-C 引用 $'...' / ロケール翻訳 $"..." の扱い（QT-1・QT-3）--------
#
# bash はこの2形を**展開時にデコード／翻訳する**ため、hook が見る字面と
# コマンドが実際に受け取る文字列が一致しない（`$'…\x22…'` は `"` になり、
# `\x7c` は `|` になる）。一致しないことが確定している以上、ホワイトリスト
# （AW-7）でもブラックリスト（AW-5／AW-6・SED_WRITE_RE）でも判定できない
# ——「見えているテキストが安全か」も「見えているテキストが危険か」も、
# 実行されるテキストと異なる入力に対しては意味を持たないためである。
# したがって「判定不能」の印を字句レイヤで残し、保護対象への言及または
# 保護対象 cwd が成立した時点で deny する（証拠が無ければ従来どおり allow）。
ANSI_QUOTE_KIND = "ansiq"          # 語でも演算子でもない印トークンの種別
ANSI_QUOTE_RE = re.compile(r"\$['\"]")   # degraded（クォート状態を追えない）用
ANSI_QUOTE_REASON = (
    "ANSI-C 引用（$'...'）／ロケール翻訳（$\"...\"）を含むコマンドは判定でき"
    "ません（bash が展開時にエスケープを復号・翻訳するため、hook が見る文字列と"
    "実際にコマンドが受け取る文字列が一致しません）。保護対象に触れるコマンドで"
    "は使わず、エスケープを使わない書き方（awk -F'\\t' / grep -P '\\t' 等）を"
    "使ってください")

# 証拠収集専用の ANSI-C 復号（QT-3）。**判定用テキストには決して使わない。**
# bash が $'...' 内で認識するエスケープのみを対象とし、認識しない形
# （`\|`・`\d` 等）はバックスラッシュを残す（bash と同じ）。
ANSI_C_SIMPLE_ESCAPES = {"a": "\a", "b": "\b", "e": "\x1b", "E": "\x1b",
                         "f": "\f", "n": "\n", "r": "\r", "t": "\t",
                         "v": "\v", "\\": "\\", "'": "'", '"': '"', "?": "?"}
ANSI_C_ESCAPE_RE = re.compile(
    r"\\(x[0-9A-Fa-f]{1,2}|u[0-9A-Fa-f]{1,4}|U[0-9A-Fa-f]{1,8}"
    r"|[0-7]{1,3}|c.|[abeEfnrtv\\'\"?])")

# 字句解析に失敗した入力向けの簡易判定でのみ使う（degraded_violation）。
# 旧版（KLK-010 以前）の find_violation と同じ分割を再現するためのもので、
# 正常経路では使わない。
LEGACY_REDIRECT_RE = re.compile(r"\d?>>?\s*([^\s;|&]+)")
LEGACY_STATEMENT_RE = re.compile(r"&&|\|\||;|\n")


def allow():
    sys.exit(0)


def deny(reason):
    lib.emit_pretooluse_decision("deny", reason)


# --- L2: パスレイヤ ---------------------------------------------------------

def _is_guarded_path(path):
    """正規化済みパスが保護対象か。正規化 → .claude 除外 → 分類の順で判定する。"""
    if ".claude" in path.split("/"):
        return False  # スキル同梱のテンプレート等は対象外
    if "tickets/active" in path or "tickets/done" in path:
        # テンプレート・ダッシュボードは対象外（validator と同じ除外）
        return "/Templates/" not in path and not path.endswith("_index.md")
    return os.path.basename(path) == "SPEC.md"


def guarded_paths(text):
    """任意テキストから保護対象パスを列挙する（トークン境界に依存しない）。"""
    found = []
    for candidate in PATHISH_RE.findall(text):
        path = os.path.normpath(candidate)
        if _is_guarded_path(path):
            found.append(path)
    return found


def ansi_c_decode(text):
    """$'...' の ANSI-C エスケープを復号する（QT-3）。

    **証拠収集専用。** 復号結果を is_guarded_token の追加判定以外で使っては
    ならない（プログラム本文の判定に渡すと「復号後は安全な形」と誤認する
    余地が生まれる。判定不能な入力は QT-1 が先に deny するため必要も無い）。
    復号できない・未知のエスケープは元の字面を残す（bash と同じ挙動）。
    """
    if "\\" not in text:
        return text

    def replace(match):
        body = match.group(1)
        try:
            if body[0] in "xuU":
                return chr(int(body[1:], 16))
            if body[0] == "c":
                return chr(ord(body[1].upper()) ^ 0x40)
            if body[0] in "01234567":
                return chr(int(body, 8) & 0xFF)
            return ANSI_C_SIMPLE_ESCAPES[body]
        except (ValueError, KeyError, IndexError):
            return match.group(0)  # 例外は出さない（hook 全体は fail-open）

    return ANSI_C_ESCAPE_RE.sub(replace, text)


def is_guarded_token(text):
    """テキスト（トークン・コマンド断片のいずれでも可）が保護対象に言及するか。

    QT-3: 素の字面で見つからないときに限り、ANSI-C エスケープを復号した字面でも
    もう一度判定する（`rm $'\\x74ickets/active/APP-001.md'` のように**証拠その
    ものを符号化して隠す**形を捕捉するため）。判定に使えるテキストが増える
    方向にのみ作用し、deny が allow へ転じることはない。
    """
    if guarded_paths(text):
        return True
    decoded = ansi_c_decode(text)
    return decoded != text and bool(guarded_paths(decoded))


def mentions_guarded(values):
    """語の集合のいずれかが保護対象に言及するか。"""
    return any(is_guarded_token(v) for v in values)


# --- L1: 字句レイヤ ---------------------------------------------------------

def _take_subst(command, start, buf, substs):
    """`$(` / `<(` / `>(` の内側を置換として取り込み、終端 `)` の次の位置を返す。"""
    depth, i, n, quote = 1, start, len(command), ""
    while i < n:
        c = command[i]
        if quote:
            if c == "\\" and quote == '"' and i + 1 < n:
                i += 2
                continue
            if c == quote:
                quote = ""
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            i += 2
            continue
        if c in "'\"":
            quote = c
            i += 1
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                substs.append(command[start:i])
                buf.append(SUBST_PLACEHOLDER % (len(substs) - 1))
                return i + 1
        i += 1
    raise ValueError("no closing parenthesis")


def _take_backtick(command, start, buf, substs):
    """バッククォート置換の内側を取り込み、終端の次の位置を返す。"""
    i, n = start, len(command)
    while i < n:
        c = command[i]
        if c == "\\" and i + 1 < n:
            i += 2
            continue
        if c == "`":
            substs.append(command[start:i])
            buf.append(SUBST_PLACEHOLDER % (len(substs) - 1))
            return i + 1
        i += 1
    raise ValueError("no closing backquote")


def lex(command):
    """コマンドを (tokens, substitutions) へ分解する。

    tokens: [("w", クォート解除済みの語), ("op", 演算子文字列),
             ("ansiq", "$'" | '$"')]  ← QT-1 の「判定不能」の印
    substitutions: `$(...)` / バッククォート / プロセス置換の内側テキスト
    未閉じクォート・未閉じ括弧では ValueError を送出する。
    """
    # QT-2: bash は行継続 `\`+改行を**削除して前後の語を連結する**。空白へ
    # 置換すると `rm tickets/acti\<改行>ve/APP-001.md` の語が割れて言及ゲートが
    # 偽になり、bash が実際には保護対象を rm するのに allow になる。連結は
    # 部分文字列としての証拠を失わせないため、証拠は増える方向にしか動かない。
    command = command.replace("\\\n", "").replace("\n", ";")
    tokens, substs, buf, pending = [], [], [], []

    def flush():
        chunk = "".join(buf)
        del buf[:]
        if chunk.strip():
            for word in shlex.split(chunk, comments=False, posix=True):
                tokens.append(("w", word))
        # QT-1: 印は**そのチャンクの語をすべて出した後**に置く。演算子と
        # 「その次の語」の間に割り込ませると redirect_violation がリダイレクト
        # 先を見失う（`echo x > $'tickets/active/APP-001.md'` が allow になる）。
        # flush() は演算子トークンを積む直前と入力末尾でしか呼ばれないため、
        # この位置なら印が演算子と語の間へ入ることは構造的に起こらない。
        for mark in pending:
            tokens.append((ANSI_QUOTE_KIND, mark))
        del pending[:]

    i, n, quote = 0, len(command), ""
    while i < n:
        c = command[i]
        if quote == "'":
            buf.append(c)
            if c == "'":
                quote = ""
            i += 1
            continue
        if quote == '"':
            if c == "\\" and i + 1 < n:
                buf.append(c)
                buf.append(command[i + 1])
                i += 2
                continue
            if c == "$" and i + 1 < n and command[i + 1] == "(":
                i = _take_subst(command, i + 2, buf, substs)
                continue
            if c == "`":
                i = _take_backtick(command, i + 1, buf, substs)
                continue
            buf.append(c)
            if c == '"':
                quote = ""
            i += 1
            continue
        # 通常状態
        if c == "\\" and i + 1 < n:
            buf.append(c)
            buf.append(command[i + 1])
            i += 2
            continue
        if c in "'\"":
            buf.append(c)
            quote = c
            i += 1
            continue
        # QT-1: クォート**外**の `$'` / `$"` だけが ANSI-C 引用・ロケール翻訳に
        # なる。`"$'...'"` のようにダブルクォート内に現れる `$'` は bash では
        # 展開されない（素の `$` + `'`）ため、この判定は「通常状態」の分岐に
        # しか置いてはならない。**語の取り込み方は一切変えない**（`$` はこの後の
        # 共通処理で buf へ積まれ、続く引用符が従来どおりクォート状態を開始
        # する）＝証拠となるテキストは1文字も変わらない
        if c == "$" and i + 1 < n and command[i + 1] in "'\"":
            pending.append(command[i:i + 2])     # "$'" または '$"'
        if c == "$" and i + 1 < n and command[i + 1] == "(":
            i = _take_subst(command, i + 2, buf, substs)
            continue
        if c in "<>" and i + 1 < n and command[i + 1] == "(":
            i = _take_subst(command, i + 2, buf, substs)  # プロセス置換
            continue
        if c == "`":
            i = _take_backtick(command, i + 1, buf, substs)
            continue
        if c in OPERATOR_CHARS:
            flush()
            op = next(o for o in OPERATORS if command.startswith(o, i))
            tokens.append(("op", op))
            i += len(op)
            continue
        buf.append(c)
        i += 1
    if quote:
        raise ValueError("no closing quotation")
    flush()
    return tokens, substs


def expand_substs(text, substs):
    """語トークン中のプレースホルダを、対応する置換の内側テキストへ展開する。

    証拠収集専用。展開は「判定に使えるテキストを増やす」方向にしか働かず、
    判定を緩めることはない。展開する用途・しない用途はモジュール docstring の
    「プレースホルダ契約」に従うこと。
    """
    if not substs or not SUBST_PLACEHOLDER_RE.search(text):
        return text

    def replace(match):
        index = int(match.group(1))
        if index >= len(substs):
            return match.group(0)  # 利用者が書いた同名リテラル。そのまま残す
        return " %s " % substs[index]  # 前後の空白で語の誤結合を防ぐ

    return SUBST_PLACEHOLDER_RE.sub(replace, text)


def expand_all(words, substs):
    """語リストの各要素をプレースホルダ解決したリストを返す。"""
    return [expand_substs(word, substs) for word in words]


def display_text(text):
    """deny 理由に載せる文字列から内部プレースホルダを隠す。"""
    return SUBST_PLACEHOLDER_RE.sub("$(...)", text)


def op_kind(op):
    """演算子の種別を返す。種別の正は OPERATOR_KINDS。"""
    return OPERATOR_KIND_MAP.get(op, "sep")


# --- L3: 構文レイヤ ---------------------------------------------------------

def split_statements(tokens):
    """トークン列を `;` `&&` `||` `&` でステートメントへ分割する。"""
    statements, current = [], []
    for token in tokens:
        if token[0] == "op" and op_kind(token[1]) == "sep":
            statements.append(current)
            current = []
            continue
        current.append(token)
    statements.append(current)
    return statements


def pipe_segments(statement):
    """ステートメントをパイプ区間の語リストへ分割する（リダイレクト先の語は除く）。"""
    segments, current, skip_next = [], [], False
    for kind, value in statement:
        if kind == "op":
            kind_of_op = op_kind(value)
            if kind_of_op == "pipe":
                segments.append(current)
                current = []
                skip_next = False
            else:
                skip_next = kind_of_op in ("redirect_out", "redirect_in",
                                           "heredoc")
            continue
        if kind != "w":
            continue  # QT-1 の印トークンは語ではない。**skip_next を消費させ
            # ない**ため、この判定は skip_next の処理より前に置く（印は演算子と
            # 語の間に入らない設計だが、防御的にこの順序にする）
        if skip_next:
            skip_next = False  # リダイレクト先・heredoc の終端子はコマンドではない
            continue
        current.append(value)
    segments.append(current)
    return segments


def is_assignment_word(word):
    """`FOO=bar` 形式の環境変数代入前置きか。"""
    return bool(re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*=.*", word))


def head_index(words):
    """語リスト中で「先頭コマンド名」に当たる語の位置を返す。無ければ -1。

    環境変数代入の前置き（`FOO=bar`）とグループ化の `(` 単独語を読み飛ばす。
    先頭コマンドの位置は head_of / next_cwd のオペランド抽出 / git のサブコマンド
    抽出 / awk の引数走査が共有する。「先頭語の次から」（words[1:]）と決め打ちすると
    代入前置きのある形（`X=1 cd tickets/active`・`X=1 git add ...`）で前提がずれ、
    語そのもの（"cd" / "git"）をオペランド・サブコマンドと誤認するため、
    位置の判定はこの1関数に集約する。
    """
    for index, word in enumerate(words):
        if is_assignment_word(word):
            continue  # FOO=bar 形式の前置き
        if not word.lstrip("("):
            continue  # `(` 単独＝サブシェル開始。本体は次の語
        return index
    return -1


def head_of(words):
    """語リストの先頭コマンド名を返す（環境変数代入・グループ化の `(` は剥がす）。"""
    index = head_index(words)
    if index < 0:
        return ""
    return os.path.basename(words[index].lstrip("("))


def head_args(words):
    """先頭コマンド名より後ろの語（引数列）を返す。先頭コマンドが無ければ空。"""
    index = head_index(words)
    return list(words[index + 1:]) if index >= 0 else []


def is_readonly_script_call(words):
    """`python3 <READONLY_SCRIPTS> <args>` の形か。
    スクリプトパスの前にフラグがある形(-c/-m 等の別実行経路)は不許可。"""
    seen_interp = False
    for word in words:
        if is_assignment_word(word):
            continue  # FOO=bar 形式の前置き
        if not seen_interp:
            seen_interp = True  # インタプリタ本体
            continue
        if word.startswith("-"):
            return False
        return os.path.normpath(word).endswith(READONLY_SCRIPTS)
    return False


def cwd_is_guarded(cwd):
    """作業ディレクトリ自体が保護対象配下か（相対パス書き込みの検出用）。"""
    return bool(cwd) and _is_guarded_path(cwd)


def guarded_write_target(target, cwd, substs=()):
    """書き込み先オペランドが保護対象を指すか（cwd 相対も解決する）。

    **構文的に書き込み先と確定しているオペランド**（出力リダイレクトの直後の語・
    sort の -o の値・uniq の第2位置引数）にだけ適用する。任意の語へ適用すると
    cwd と結合した結果が保護対象パターンに一致して誤denyになる
    （_is_guarded_path("tickets/active/NR>1 {print}") は True になる）。
    解決できない先（シェル変数・未解決プレースホルダ）は偽＝allow 方向。
    絶対パスは os.path.join の性質で cwd を無視するため、cwd 外への書き込みは
    allow のまま（`cd tickets/active && cat APP-001.md > /tmp/x.md`）。
    """
    if not target:
        return False
    target = expand_substs(target, substs).strip()
    if not target or "$" in target or SUBST_PLACEHOLDER_RE.search(target):
        return False
    if is_guarded_token(target):
        return True
    if not cwd_is_guarded(cwd):
        return False
    return _is_guarded_path(os.path.normpath(os.path.join(cwd, target)))


def awk_bindings(words):
    """awk の変数束縛の VALUE を列挙する（-v NAME=VALUE / -vNAME=VALUE /
    --assign NAME=VALUE / 位置引数 NAME=VALUE）。近似解析であり、オプションの
    引数消費までは厳密に追わない（追えない形は列挙しない＝安全側へ倒す）。"""
    values, expect_value = [], False
    for word in head_args(words):
        if expect_value:
            expect_value = False
            match = AWK_ASSIGN_RE.match(word)
            if match:
                values.append(match.group(1))
            continue
        if word in ("-v", "--assign"):
            expect_value = True
            continue
        if word.startswith("-v") and len(word) > 2:
            match = AWK_ASSIGN_RE.match(word[2:])
            if match:
                values.append(match.group(1))
            continue
        if word.startswith("--assign="):
            match = AWK_ASSIGN_RE.match(word[len("--assign="):])
            if match:
                values.append(match.group(1))
            continue
        if word.startswith("-"):
            continue  # -F / -f 等のその他オプション
        match = AWK_ASSIGN_RE.match(word)  # 位置引数の NAME=VALUE
        if match:
            values.append(match.group(1))
    return values


def is_safe_awk_flag(word):
    """awk のオプション語が「読み取りだけで完結する」既知の形か。

    **未知のオプションは False（deny 方向）へ倒す。** gawk の -f / -i / -l / -E /
    -D（外部プログラム・ライブラリ・拡張の読み込み）と -o / -p / -d（ファイルへの
    書き出し）はここへ載せないことで自動的に deny になる。オプション次元は
    man / --help で閉じた集合として列挙できるため、失敗方向は「安全な
    オプションの収載漏れ＝可視な誤deny」であって「危険なオプションの
    列挙漏れ＝黙ってすり抜け」ではない。
    収載を増やすときは man / --help の説明にファイル書き込み・コード読み込みが
    無いことを根拠として記録すること。迷うオプションは収載しない。
    """
    if word in AWK_SAFE_FLAGS:
        return True
    for flag in AWK_SAFE_VALUE_FLAGS:
        if word == flag or word.startswith(flag + "="):
            return True
        if len(flag) == 2 and len(word) > 2 and word.startswith(flag):
            return True  # -FVALUE / -vNAME=VALUE / -eTEXT の結合形
    return False


def awk_strip_literals(text):
    """awk プログラムの文字列リテラルと正規表現リテラルを**1パス**で除去する。

    左→右の1パスで「その位置に何のリテラルが始まるか」を awk の字句規則に
    倣って決める。2パス（文字列を全部消してから正規表現を消す等）にすると、
    片方のリテラルの内側に見える引用符／スラッシュが、実際には外側にある
    コードを飲み込む（`/"/ {system("rm F")}` は文字列先だと system( が消え、
    `BEGIN{x="(/a"; system("rm /F")}` は正規表現先だと消える）。1パスなら
    リテラルの開始位置が awk と一致するため、awk が実行するコードが
    リテラルとして消えることは起こらない。

    正規表現と除算の区別は「直前の非空白文字がオペランドの終端になりうるか」
    （AWK_OPERAND_END_CHARS）で行い、候補スパンが `;` や改行を含む場合は
    正規表現と認めない（二重の安全網）。誤ると「除算と判定してリテラルを
    除去しない＝内容が判定対象に残る」＝deny 方向へ倒れる。

    戻り値: 除去後テキスト（文字列は `""`・正規表現は `//` へ置換）。
            未閉じ文字列リテラルは None（判定不能＝呼び出し側で deny）。
    """
    out, i, n, prev = [], 0, len(text), ""
    while i < n:
        char = text[i]
        if char == '"':
            j, closed = i + 1, False
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == '"':
                    closed = True
                    break
                j += 1
            if not closed:
                return None
            out.append('""')
            prev, i = '"', j + 1
            continue
        if char == "/" and prev not in AWK_OPERAND_END_CHARS:
            j, closed = i + 1, False
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == "/":
                    closed = True
                    break
                if text[j] in ";\n":
                    break  # 正規表現リテラルは文・行をまたがない
                j += 1
            if closed:
                out.append("//")
                prev, i = "/", j + 1
                continue
        out.append(char)  # 除算・その他の文字はそのまま
        if not char.isspace():
            prev = char
        i += 1
    return "".join(out)


def awk_program_texts(words):
    """awk が**プログラムとして実行する**テキストを列挙する（設計書 §3-4）。

    - `-e TEXT` / `-eTEXT` / `--source TEXT` / `--source=TEXT` の値（複数可）
    - `-e` / `--source` が無い場合に限り、位置引数の**先頭のオペランド**
      （awk は最初の非オプション引数をプログラムとして扱い、2番目以降は
      NAME=VALUE 代入と入力ファイル名として扱う＝実行しない）
    - `-f FILE` / `--file=FILE` は AW-4 が deny するためここへ到達しない

    ファイル名オペランド・変数束縛値をプログラム候補に含めてはならない
    （awk が実行しないテキストを判定すると `'system(1).md' のような
    ファイル名が誤denyになる）。値を「次の語」から取るオプションは
    AWK_VALUE_CONSUMING_FLAGS に限る（載せ忘れた場合はその値をプログラム
    候補として検査する＝deny 方向）。
    """
    texts, positionals, expect = [], [], ""
    for word in head_args(words):
        if expect:
            if expect in AWK_PROGRAM_TEXT_FLAGS:
                texts.append(word)
            expect = ""
            continue
        if word in AWK_VALUE_CONSUMING_FLAGS:
            expect = word
            continue
        if word.startswith("-e") and len(word) > 2:
            texts.append(word[2:])
            continue
        if word.startswith("--source="):
            texts.append(word[len("--source="):])
            continue
        if word.startswith("-"):
            continue  # 値を取らないオプション・`-`・`--`
        positionals.append(word)
    if not texts and positionals:
        texts.append(positionals[0])
    return texts


def awk_program_violation(text):
    """プログラム本文が「安全と確認できる形」でなければ理由を返す（AW-7）。

    **ホワイトリスト。** 3条件（許可文字集合・呼び出し名の許可集合・
    print/printf 出力構文の不在）をすべて満たす形だけを許可し、未知の文字・
    未知の関数名はすべて deny 側へ落ちる。判定はリテラル除去後に行うため、
    文字列・正規表現の中身に `@` や `system(` が現れるだけの読み取りは
    許可される（awk に eval が無いため実行され得ない）。
    """
    stripped = awk_strip_literals(text)
    if stripped is None:
        return ("awk プログラムの文字列リテラルが閉じていません"
                "（安全と確認できるプログラム形に限り許可します）")
    unsafe = [c for c in stripped if c not in AWK_SAFE_PROGRAM_CHARS]
    if unsafe:
        return ("awk プログラムに許可されていない文字 %r があります"
                "（@ 間接呼び出し・@load・| パイプ／コプロセス等の"
                "外部コマンド実行経路になりうるため）" % unsafe[0])
    declared = set(AWK_FUNC_DECL_RE.findall(stripped))
    for name in AWK_CALL_RE.findall(stripped):
        if name not in AWK_SAFE_CALLS and name not in declared:
            return ("awk プログラムの関数呼び出し %s() は許可されていません"
                    "（副作用の無いことを確認した組み込み関数と、同じ"
                    "プログラム内で定義された関数のみ許可します）" % name)
    if AWK_OUTPUT_RE.search(stripped):
        return ("awk のプログラム内リダイレクト（print > file 等）は"
                "許可されていません")
    return None


def awk_violation(words, cwd="", degraded=False):
    """awk セグメントの違反理由を返す（設計書 §3-6 D1 の AW-1〜AW-7）。

    cwd が保護対象配下なら、プログラム内の出力リダイレクト・オプション・
    プログラム本文の判定を「保護対象に言及していなくても」適用する
    （相対パスで書き込む形は書き込み先オペランドを取り出せないため、
    構文の存在そのものを証拠にする）。

    degraded は「字句解析に失敗して空白分割へ落ちた入力か」。空白分割では
    プログラム本文の同一性が失われる（`BEGIN{@ f("rm x")}` が3語に割れる）
    ため AW-7 を適用できず、AW-5／AW-6 のブラックリストで見る。
    """
    # AW-1: 保護対象に言及する語そのものが > / | を含む（{print > "docs/SPEC.md"}
    # 等）。正常な読み取りでは保護対象は素のパス引数として現れる
    if any(">" in t or "|" in t for t in words if is_guarded_token(t)):
        return "awk のプログラム内リダイレクト（print > file 等）は許可されていません"
    # AW-2: 保護対象パスを awk 変数へ束縛している（-v f=... / 位置引数 f=...）。
    # 参照側（print > f）まで追わないのは、エイリアス（g=f; print > g）で
    # 容易に迂回でき防御にならないため。束縛そのものを証拠とする
    if any(is_guarded_token(v) for v in awk_bindings(words)):
        return "awk の変数へ保護対象パスを束縛しています（-v / NAME=VALUE）"
    # 以降は「保護対象に言及する awk」「保護対象を作業ディレクトリとする awk」
    # に限って適用する（読み取り awk を誤denyしないためのゲート）
    if not (mentions_guarded(words) or cwd_is_guarded(cwd)):
        return None
    for word in head_args(words):
        # AW-4: 未知・危険なオプション（外部コード読み込み／ファイル書き出し）。
        # gawk の `-i inplace` は sed -i と同じ in-place 書き込みになる
        if word.startswith("-") and not is_safe_awk_flag(word):
            return ("awk のオプション %s は許可されていません（外部プログラム・"
                    "拡張の読み込みとファイル書き出しの経路になりうるため）"
                    % display_text(word))
        if degraded:
            # AW-5 / AW-6（degraded 専用）。正常経路では AW-7 が同じ構文を
            # 「プログラム本文のみ・リテラル除去後」で判定するため、ここへ
            # 来ない（リテラルの中身やファイル名オペランドを巻き込む
            # 過剰一致を正常経路へ持ち込まないための分岐）
            #
            # AW-5: system() / @load / @include（外部コマンド実行・拡張読み込み）。
            # 文字列リテラル除去**前**の語で判定する（保守側）
            if AWK_EXEC_RE.search(word):
                return ("awk の system() / @load / @include（外部コマンド実行・"
                        "拡張読み込み）は許可されていません")
            # AW-6: gawk の間接関数呼び出し `@f(...)`。関数名を文字列変数から
            # 供給できるため `system(` のリテラルが現れないまま system() を
            # 呼べる。AW-2／AW-3 と同じく「構文の存在」を証拠とする
            if AWK_INDIRECT_CALL_RE.search(word):
                return ("awk の間接関数呼び出し（@f(...) 形式）は許可されて"
                        "いません（関数名を変数経由で供給して system() を"
                        "呼び出せるため）")
        # AW-3: print/printf の出力リダイレクト。文字列リテラルを除去してから
        # 見るため printf "%s|%s" は一致しない
        if AWK_OUTPUT_RE.search(AWK_STRING_RE.sub('""', word)):
            return ("awk のプログラム内リダイレクト（print > file 等）は"
                    "許可されていません")
    if degraded:
        # AW-5／AW-6 を空白結合したテキストへも当てる。degraded mode は空白
        # 分割のため `@ f(` が `@` と `f(` に、`system (` が `system` と `(` に
        # 割れて語単位では一致しない（`awk -v f=system 'BEGIN{@ f("rm ...")}' #'`
        # はプログラム内に `;` が無いためステートメント分割にも掛からない）。
        # gawk は `@` の直後と関数名の直後の空白をどちらも受け付けるため、
        # 語をまたぐ形も実際に system() を実行できる（実測）。結合は証拠
        # テキストを増やす操作であり判定を緩める方向には働かない。オプション
        # 判定（AW-4）と出力構文（AW-3）は結合テキストへ当てない（結合により
        # 語の意味が変わり誤denyになりうるため）
        args = head_args(words)
        if len(args) > 1:
            joined = " ".join(args)
            if AWK_EXEC_RE.search(joined):
                return ("awk の system() / @load / @include（外部コマンド実行・"
                        "拡張読み込み）は許可されていません")
            if AWK_INDIRECT_CALL_RE.search(joined):
                return ("awk の間接関数呼び出し（@f(...) 形式）は許可されて"
                        "いません（関数名を変数経由で供給して system() を"
                        "呼び出せるため）")
        return None
    # AW-7（正常経路の本体）: プログラム本文がホワイトリストの安全形か。
    # 判定対象はプログラム本文だけであり、ファイル名オペランド・変数束縛値は
    # awk が実行しないため検査しない
    texts = awk_program_texts(words)
    for text in texts:
        reason = awk_program_violation(text)
        if reason:
            return reason
    if len(texts) > 1:
        # gawk は複数の -e / --source を連結して1つのプログラムにする。
        # 語をまたいで `sys` + `tem(` のように割った形を取りこぼさない
        reason = awk_program_violation(" ".join(texts))
        if reason:
            return reason
    return None


def sort_output_operands(words):
    """sort の出力先を列挙する（-o FILE / -oFILE / --output FILE / --output=FILE）。
    """
    operands, expect = [], False
    for word in head_args(words):
        if expect:
            expect = False
            operands.append(word)
            continue
        if word in SORT_OUTPUT_FLAGS:
            expect = True
        elif word.startswith("-o") and len(word) > 2:
            operands.append(word[2:])
        elif word.startswith("--output="):
            operands.append(word[len("--output="):])
    return operands


def uniq_output_operand(words):
    """uniq の第2位置引数（出力ファイル）を返す。無ければ空文字列。

    -f/-s/-w とその長形式は値を取るため、位置引数の数え方を誤ると
    `uniq -f 2 FILE` の `2` を第1位置引数と数えて FILE を出力先と誤認する。
    """
    positionals, expect = [], False
    for word in head_args(words):
        if expect:
            expect = False
        elif word in UNIQ_VALUE_FLAGS:
            expect = True
        elif word.startswith("-") and word != "-":
            continue  # 結合形・その他のフラグ
        else:
            positionals.append(word)
    return positionals[1] if len(positionals) > 1 else ""


def segment_violation(words, substs=(), cwd="", degraded=False):
    """パイプ区間（語リスト）単位の違反理由を返す。問題なければ None。

    words は未解決の語リスト。substs を与えると、sed / awk の追加規則を
    プレースホルダ解決後のテキストに対しても評価する（解決前の語も併せて
    見るため、判定は deny 方向にのみ広がる）。cwd は「この区間を実行する時点の
    作業ディレクトリ」（追跡不能なら None）。保護対象配下なら相対パスが
    保護対象を指しうるため判定を強める。degraded は「字句解析に失敗して
    空白分割へ落ちた入力か」（awk のプログラム本文の同一性が失われるため
    AW-7 を適用せず AW-5／AW-6 で見る）。渡すのは degraded_violation だけ。
    """
    head = head_of(words)
    if not head:
        return None
    if SUBST_PLACEHOLDER_RE.search(head):
        # コマンド名の位置にコマンド置換を使う形は解決せず不許可とする
        return "コマンド名の位置にコマンド置換が使われています"
    if head in ("python3", "python") and is_readonly_script_call(words):
        return None
    if head not in ALLOWED_HEADS:
        return "'%s' は許可されていません" % head
    # フォールセーフ既定。現行の ALLOWED_HEADS は全て CWD_SAFE_HEADS へ
    # 収載済みのため到達しないが、ALLOWED_HEADS へ追加したときに cwd 次元の
    # 棚卸し忘れを deny 側へ倒すためにこの判定を置く
    if cwd_is_guarded(cwd) and head not in CWD_SAFE_HEADS:
        return ("保護対象ディレクトリを作業ディレクトリとする '%s' は"
                "許可されていません" % head)
    words = list(words)
    expanded = expand_all(words, substs)
    variants = [words] if expanded == words else [words, expanded]
    if head == "sed":
        flat = [t for variant in variants for t in variant]
        if any(SED_INPLACE_SHORT_RE.match(t) or t == "--in-place" or
               t.startswith("--in-place=") for t in flat):
            return "sed -i（in-place編集）は許可されていません"
        # スクリプト引数に埋め込まれた書き出し（s/a/b/w FILE ・ /re/w FILE）。
        # 保護対象を作業ディレクトリとする場合は書き出し先が相対パスになり
        # 保護対象パターンに一致しないため、語の言及フィルタを外して
        # 「w コマンドの存在」そのものを証拠とする（保守側）
        strict = cwd_is_guarded(cwd)
        if strict:
            # degraded は空白分割のため `w FILE` が2語に割れる。
            # 保護対象 cwd 下に限り空白結合したテキストも併せて評価する
            flat = flat + [" ".join(words)]
        if any(SED_WRITE_RE.search(t) for t in flat
               if strict or is_guarded_token(t)):
            return "sed の w コマンド（ファイル書き出し）は許可されていません"
    if head == "awk":
        for variant in variants:
            reason = awk_violation(variant, cwd, degraded)
            if reason:
                return reason
    if head == "sort":
        for operand in sort_output_operands(words):
            if guarded_write_target(operand, cwd, substs):
                return "sort の -o / --output（出力先指定）は許可されていません"
    if head == "uniq":
        if guarded_write_target(uniq_output_operand(words), cwd, substs):
            return ("uniq の第2引数（出力ファイル）への書き込みは"
                    "許可されていません")
    if head == "find" and any(t in FIND_WRITE_FLAGS for t in words):
        return "find の書き込み系フラグ（-exec/-delete等）は許可されていません"
    if head == "git":
        # 代入前置き（X=1 git add ...）があっても "git" 自身をサブコマンドと
        # 誤認しないよう、先頭コマンドの位置は head_index に合わせる
        sub = next((t for t in head_args(words) if not t.startswith("-")), "")
        if sub not in ALLOWED_GIT_SUBCOMMANDS:
            return "git %s は許可されていません" % sub
    return None


def next_cwd(words, cwd):
    """`cd DIR` 実行後の作業ディレクトリを返す。追跡不能なら None。"""
    if cwd is None:
        return None
    if head_of(words) != "cd":
        return cwd
    # 代入前置き（X=1 cd DIR）があっても "cd" 自身をオペランドと誤認しないよう、
    # 先頭コマンドの位置は head_of と同じ head_index で決める
    operand = next((w for w in head_args(words) if not w.startswith("-")), "")
    if (not operand or "$" in operand or operand.startswith("~") or
            SUBST_PLACEHOLDER_RE.search(operand)):
        return None  # cd / cd - / cd "$D" / cd $(...) は追跡不能
    return os.path.normpath(os.path.join(cwd or ".", operand))


def record_assignments(statement, guarded_vars, substs=()):
    """`NAME=保護対象パス` の前置き代入を記録する（リダイレクト先の追跡用）。"""
    for words in pipe_segments(statement):
        for word in words:
            match = ASSIGN_RE.match(word)
            if not match:
                break  # 先頭から連続する代入のみが前置き
            value = expand_substs(word[match.end():], substs)
            if is_guarded_token(value):
                guarded_vars.add(word[:match.end() - 1])


def redirect_violation(statement, guarded_vars, substs=(), cwd=""):
    """出力リダイレクト先が保護対象・保護対象を代入された変数なら理由を返す。"""
    for index, (kind, value) in enumerate(statement):
        if kind != "op" or op_kind(value) != "redirect_out":
            continue
        if index + 1 >= len(statement):
            continue
        next_kind, target = statement[index + 1]
        if next_kind != "w":
            continue
        if "&" in value and (target.isdigit() or target == "-"):
            continue  # 2>&1 等の fd 複製
        # リダイレクト先はコマンドではないためパイプ区間の検査から外れる。
        # 置換の結果が書き込み先になる形（> $(echo docs/SPEC.md)）はここで解決する。
        # guarded_write_target は cwd 相対のリダイレクト先も解決する
        # （`cd tickets/active && echo x > APP-001.md`）
        resolved = expand_substs(target, substs)
        if (is_guarded_token(resolved) or
                any(n in guarded_vars for n in VAR_REF_RE.findall(resolved)) or
                guarded_write_target(target, cwd, substs)):
            return "リダイレクト（> %s）による書き込み" % display_text(target)
    return None


def statement_violation(statement, guarded_vars, substs=(), cwd=""):
    """ステートメント単位の違反理由を返す。問題なければ None。

    cwd は「このステートメントを実行する時点の作業ディレクトリ」（追跡不能なら
    None）。保護対象配下なら相対パスが保護対象を指しうるため判定を強める。
    """
    reason = redirect_violation(statement, guarded_vars, substs, cwd)
    if reason:
        return reason
    words = [v for k, v in statement if k == "w"]
    # 言及ゲートはプレースホルダ解決後のテキストで判定する（置換の結果が
    # 外側コマンドの引数になる形を取りこぼさないため）。作業ディレクトリが
    # 保護対象配下ならゲートは無条件に真とする
    if not (cwd_is_guarded(cwd) or
            mentions_guarded(expand_all(words, substs))):
        return None
    # QT-1: この文には bash が展開時にデコード／翻訳する語がある。hook が見て
    # いる字面と実行される文字列が一致しないことが確定しているため、ホワイト
    # リスト（AW-7）でもブラックリスト（AW-5／AW-6・SED_WRITE_RE）でも判定
    # できない。**証拠（言及ゲート／保護対象 cwd）が立った時点で無条件に
    # deny する。** ゲートの後に置くのは `printf $'a\tb'` 単独のような保護対象と
    # 無関係なコマンドを巻き添えにしないため
    if any(k == ANSI_QUOTE_KIND for k, _ in statement):
        return ANSI_QUOTE_REASON
    if any(k == "op" and op_kind(v) == "heredoc" for k, v in statement):
        return "ヒアドキュメントによる書き込みの可能性"
    for segment_words in pipe_segments(statement):
        reason = segment_violation(segment_words, substs, cwd)
        if reason:
            return reason
    return None


def degraded_violation(command, cwd=""):
    """字句解析できない入力向けのフォールバック。

    旧版（KLK-010 以前）の find_violation と同じ判定要素をすべて持つ:
    全体の言及ゲート → リテラルリダイレクト → heredoc の部分文字列判定 →
    ステートメント分割 → パイプ分割 → パイプライン単位の言及ゲート →
    セグメント判定。唯一の意図的な差分は「リダイレクト先が `$` /
    バッククォートを含むだけで deny する」規則を復活させないこと
    （無関係な後段リダイレクトの巻き添えを解消するため）。

    cwd は呼び出し元（find_violation）が持つ作業ディレクトリで、ローカルの
    cwd 追跡の初期値になる（置換の内側が degraded になった場合にも効かせる）。
    保護対象 cwd 下の書き込み判定は segment_violation / awk_violation の内側に
    あるため、degraded は cwd を渡すだけで同じ保護を得る（判定を複製しない）。
    """
    if not mentions_guarded(command.split()):
        return None
    for match in LEGACY_REDIRECT_RE.finditer(command):
        target = match.group(1)
        if target.startswith("&"):
            continue  # 2>&1 等の fd 複製
        if is_guarded_token(target):
            return "リダイレクト（> %s）による書き込み" % target
    if "<<" in command:
        return "ヒアドキュメントによる書き込みの可能性"
    for statement in LEGACY_STATEMENT_RE.split(command):
        parts = [p for p in statement.split("|") if p.strip()]
        if not parts:
            continue
        words_list = [p.split() for p in parts]
        if cwd_is_guarded(cwd) or any(mentions_guarded(w) for w in words_list):
            # QT-1: degraded はクォート状態を追えないため、`$'` / `$"` の検出は
            # **部分文字列判定**で行う（クォート内側の `$'` にも発火する＝
            # 保守側）。**この規則を degraded にも置くことが必須である** —
            # 置かないと `awk $'…\x7cgetline…' #'` のように未閉じクォートを
            # 1つ足すだけで判定不能な入力がそのまま通る（degraded の
            # ブラックリストは符号化された字面に一致しない）
            if ANSI_QUOTE_RE.search(statement):
                return ANSI_QUOTE_REASON
            for words in words_list:
                # degraded=True: awk は AW-7 を使わず AW-5／AW-6 で見る
                reason = segment_violation(words, cwd=cwd, degraded=True)
                if reason:
                    return reason
        for match in LEGACY_REDIRECT_RE.finditer(statement):
            if guarded_write_target(match.group(1), cwd):
                return ("リダイレクト（> %s）による書き込み" % match.group(1))
        cwd = next_cwd(words_list[0], cwd)
    return None


def statement_subst_indexes(statement):
    """ステートメントの語トークンに現れるプレースホルダのインデックスを返す。"""
    return [int(m.group(1)) for kind, value in statement if kind == "w"
            for m in SUBST_PLACEHOLDER_RE.finditer(value)]


def subst_violation(substs, index, depth, cwd):
    """コマンド置換の内側（内側方向）を、その置換が現れた文の cwd で評価する。"""
    if index >= len(substs):
        return None  # 利用者が書いた同名リテラル（プレースホルダの偽装）
    inner = substs[index]
    if depth >= MAX_SUBST_DEPTH:
        # 深追いはせず保守側で打ち切る（$($($(rm ...))) を抜け道にしないため）
        if is_guarded_token(inner) or cwd_is_guarded(cwd):
            return "深いコマンド置換の内側で保護対象パスに言及しています"
        return None
    return find_violation(inner, depth + 1, cwd)


def find_violation(command, depth=0, cwd=""):
    """コマンド全体の違反理由を返す。問題なければ None。"""
    try:
        tokens, substs = lex(command)
    except ValueError:
        return degraded_violation(command, cwd)
    guarded_vars, seen = set(), set()
    for statement in split_statements(tokens):
        # 内側方向（置換の中身が書き込み）は、**その置換が現れた文の cwd**で
        # 評価する（`cd tickets/active && ls $(rm APP-001.md)` を閉じるため）。
        # プレースホルダにインデックスがあるため、どの置換がどの文に属するかが
        # 判る
        for index in statement_subst_indexes(statement):
            seen.add(index)
            reason = subst_violation(substs, index, depth, cwd)
            if reason:
                return reason
        record_assignments(statement, guarded_vars, substs)
        reason = statement_violation(statement, guarded_vars, substs, cwd)
        if reason:
            return reason
        segments = pipe_segments(statement)
        cwd = next_cwd(segments[0] if segments else [], cwd)
    # どの文の語にも現れなかった置換（構造上起きないが取りこぼしを作らない）。
    # 帰属が取れないため cwd は与えずに評価する
    for index in sorted(set(range(len(substs))) - seen):
        reason = subst_violation(substs, index, depth, "")
        if reason:
            return reason
    return None


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        allow()

    if data.get("tool_name") != "Bash":
        allow()
    command = (data.get("tool_input") or {}).get("command", "")
    if not command:
        allow()

    try:
        reason = find_violation(command)
    except Exception:
        allow()

    if reason:
        deny(
            "チケット（tickets/active|done/）・SPEC.md に触れる Bash コマンドで"
            "書き込みの可能性を検出しました: %s。チケット・SPEC.md の変更は"
            "必ず Write/Edit ツールで行ってください（状態検証 hook を通すため）。"
            "読み取りは cat/grep/ls 等を単独で、active/↔done/ の移動は mv を"
            "使ってください。" % reason
        )
    allow()


if __name__ == "__main__":
    main()
