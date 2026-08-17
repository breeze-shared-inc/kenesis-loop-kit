"""guard_bash_writes.py（PreToolUse・Bash）のテスト"""
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _util  # noqa: E402

sys.path.insert(0, _util.HOOKS)
import guard_bash_writes as guard  # noqa: E402


def payload(command):
    return {"tool_name": "Bash", "tool_input": {"command": command}}


def _escape_once_for_backtick(text):
    r"""次の外側のバッククォートへ埋め込むために、text 中の `` ` ``・`$`・`\`
    をそれぞれ1段階分エスケープする（guard_bash_writes._unescape_backtick_body
    の逆演算。KLK-024のテスト専用ヘルパ）。"""
    return (text.replace("\\", "\\\\")
                .replace("`", "\\`")
                .replace("$", "\\$"))


def _nested_backtick_command(depth, inner="rm docs/SPEC.md"):
    r"""バッククォートを `depth` 階層ネストしたコマンド文字列を機械的に構築
    する（各階層は `echo` でラップする）。depth=1 は `` `inner` ``、depth=2 は
    チケット KLK-024 の再現手順1と同型（`_escape_once_for_backtick` を1回
    適用した形が完全に一致することを設計時に手計算で確認済み。
    docs/designs/KLK-024.md §3参照）。"""
    command = "`%s`" % inner
    for _ in range(depth - 1):
        command = "`echo %s`" % _escape_once_for_backtick(command)
    return command


# 旧版（KLK-010 マージ前の develop）が deny していたコマンド集合。
# 本 hook の改修でこれらが allow へ転じることは保護の後退に当たる。
#
# 維持規律:
#   1. 本リストは削除禁止。項目を消す＝保護を弱めることであり、受け入れ条件
#      「既存の deny 対象を回帰させない」の再定義に当たる。
#   2. ALLOWED_HEADS を増やす／判定を緩める変更を行うときは、設計書
#      docs/designs/KLK-010.md §3-9 の書き込みベクタ棚卸し表へ行を追加し、
#      対応する回帰ケースを本リストへ追加すること。
#   3. 「旧版が deny していた集合」に限らず、将来見つかった穴を塞いだ時点で
#      本リストへ追加してよい。
#   4. 収載の基準は「**old（merge-base 72ae730）が deny していたか**」または
#      「本改訂で塞いだ穴か」である。
#      - `old=allow` の形を「新版の保守的既定（未知は deny）によって deny に
#        なった」という理由**だけ**で入れてはならない（将来安全性を確認して
#        緩める余地を残すため）。
#      - **`old=deny` の形は、現在は誤deny寄りに見えても収載してよい。**
#        例: `awk 'BEGIN{xyzzy("rm docs/SPEC.md")}'` は実機 gawk が構文として
#        受け付けない未知の関数名だが、旧版は awk を ALLOWED_HEADS に持たず
#        保護対象に言及する awk をコマンドごと deny していた＝old=deny であり、
#        収載は「未知の呼び出し名は deny」という機械的既定の回帰ガードとして
#        機能する（この1行を消すとその既定が守られなくなる）。
#      - **将来 allow へ緩める余地を残したい形は、本リストへ収載せず個別テストと
#        INVENTORY_CASES で判定を固定する。** 例: `@namespace`（old=deny だが
#        安全性を確認できれば許可文字集合へ加える余地を残す）。
LEGACY_DENY_COMMANDS = [
    # --- 既存の書き込みベクタ ---
    "echo x > tickets/active/APP-001.md",
    "cat note.md >> tickets/active/APP-001.md",
    "sed -i 's/todo/done/' tickets/active/APP-001.md",
    "echo x | tee tickets/active/APP-001.md",
    "find tickets/active -name '*.md' -exec sed -i 's/a/b/' {} \\;",
    "find tickets/active -name '*.md' | xargs rm",
    "cat > tickets/active/APP-001.md <<EOF\nx\nEOF",
    "git checkout -- tickets/active/APP-001.md",
    "cat draft.md > docs/SPEC.md",
    # --- コマンド置換（置換の結果が外側の書き込みへ供給される形） ---
    "rm $(echo docs/SPEC.md)", "rm `echo docs/SPEC.md`",
    "sed -i 's/a/b/' $(echo tickets/active/APP-001.md)",
    "cp /tmp/e $(echo docs/SPEC.md)", "truncate -s 0 $(echo docs/SPEC.md)",
    "cat a | tee $(echo docs/SPEC.md)",
    "echo x > $(echo docs/SPEC.md)", 'echo x > "$(echo docs/SPEC.md)"',
    "echo x > `echo docs/SPEC.md`",
    "rm $(basename docs/SPEC.md)", "rm $(ls tickets/active/APP-001.md)",
    # --- degraded mode（字句解析できない入力） ---
    "ls ; rm docs/SPEC.md #'",
    "cat README.md ; rm docs/SPEC.md # it's stale",
    "cat x; sed -i 's/a/b/' tickets/active/APP-001.md #'",
    "cat x && tee tickets/active/APP-001.md #'",
    "cd .; rm docs/SPEC.md #'", "ls x; cp /tmp/e docs/SPEC.md #'",
    # --- awk の変数代入形 ---
    "awk '{print > f}' f=docs/SPEC.md in.txt",
    "awk -v f=docs/SPEC.md '{print > f}' in.txt",
    "awk '{print > f}' f=tickets/active/APP-001.md in.txt",
    # --- cd + 相対パス ---
    "cd tickets/active && rm APP-001.md",
    "cd tickets/done && echo x > APP-001.md",
    # --- C3: gawk の in-place 拡張と外部コード読み込みオプション ---
    "awk -i inplace '{gsub(/a/,\"b\")}1' tickets/active/APP-001.md",
    "awk -i inplace '{gsub(/a/,\"b\")}1' docs/SPEC.md",
    "awk -iinplace '{print}' tickets/active/APP-001.md",
    "awk --include inplace '{print}' tickets/active/APP-001.md",
    "awk --include=inplace '{print}' tickets/active/APP-001.md",
    "awk -i inplace '{print}' tickets/active/APP-001.md #'",
    "awk -f prog.awk tickets/active/APP-001.md",
    # --- C4: awk の外部コマンド実行 ---
    "awk 'BEGIN{system(\"rm tickets/active/APP-001.md\")}'",
    "awk '{system(\"rm tickets/active/APP-001.md\")}' /dev/null",
    "awk 'END{system(\"rm tickets/active/APP-001.md\")}' /dev/null",
    "awk 'BEGIN{system(\"rm docs/SPEC.md\")}'",
    "awk 'BEGIN{system(\"rm docs/SPEC.md\")}' #'",
    # --- C4（続き）: awk の間接関数呼び出し @f(...) 経由の system() 実行 ---
    # gawk 4.1.2 以降は関数名を文字列変数から供給できるため、system( という
    # リテラルがコマンド文字列に現れない。旧版は awk を ALLOWED_HEADS に
    # 持たず全 awk を deny していたため old=deny である
    "awk 'BEGIN{f=\"system\"; @f(\"rm tickets/active/APP-001.md\")}'",
    "awk 'BEGIN{cmd=\"system\"; @cmd(\"rm tickets/active/APP-001.md\")}'",
    "awk 'BEGIN{f=\"system\"; @f(\"rm docs/SPEC.md\")}'",
    "awk -v f=system 'BEGIN{@f(\"rm tickets/active/APP-001.md\")}'",
    "awk 'BEGIN{f=\"system\"; @ f(\"rm tickets/active/APP-001.md\")}'",
    "awk -e'BEGIN{f=\"system\"; @f(\"rm docs/SPEC.md\")}'",
    "awk --source='BEGIN{f=\"system\"; @f(\"rm docs/SPEC.md\")}'",
    "awk 'BEGIN{f=\"system\"; @f(\"rm docs/SPEC.md\")}' #'",
    "cd tickets/active && awk 'BEGIN{f=\"system\"; @f(\"rm APP-001.md\")}'",
    # degraded mode の空白分割で `@ f(` / `system (` が2語に割れる形
    # （gawk は `@` の直後と関数名の直後の空白をどちらも受け付ける）
    "awk -v f=system 'BEGIN{@ f(\"rm tickets/active/APP-001.md\")}' #'",
    "awk -v f=system 'BEGIN{@ f(\"rm docs/SPEC.md\")}' #'",
    "awk 'BEGIN{system (\"rm docs/SPEC.md\")}' #'",
    "cd tickets/active; awk -v f=system "
    "'BEGIN{@ f(\"rm APP-001.md\")}' #'",
    # --- H2: 保護対象を作業ディレクトリとする相対パス書き込み ---
    "cd tickets/active && awk '{print > \"APP-001.md\"}' in.txt",
    "cd tickets/active && awk '{printf \"x\" >> \"APP-001.md\"}' in.txt",
    "cd tickets/active && awk -v f=APP-001.md '{print > f}' in.txt",
    "cd tickets/active && awk '{print > f}' f=APP-001.md in.txt",
    "cd tickets/active && sed 's/a/b/w APP-001.md' in.md",
    "cd tickets/active; sed 's/a/b/w APP-001.md' in.md #'",
    "cd tickets/active && sort -o APP-001.md in.md",
    "cd tickets/active && uniq in.md APP-001.md",
    "cd tickets/active && ls $(rm APP-001.md)",
    "cd tickets/active && ls `rm APP-001.md`",
    "cd tickets/active && cat <(rm APP-001.md)",
    # --- C5: system() 以外の外部コマンド実行経路（AW-7・プログラム本文の
    # ホワイトリスト）。`"cmd" | getline` と `|& getline` は print/printf を
    # 伴わないため AW-3 に一致せず、cwd 保護下ではリテラルパスも現れないため
    # AW-1 も発火しなかった。実機 gawk で実際にファイルを削除・改変できる
    # ことを使い捨てディレクトリで確認済み ---
    "cd tickets/active && awk 'BEGIN{\"rm APP-001.md\" | getline x}'",
    "cd tickets/done && "
    "awk 'BEGIN{\"truncate -s 0 APP-001.md\" | getline x}'",
    "cd tickets/active && awk 'BEGIN{\"rm APP-001.md\" |& getline x}'",
    "awk 'BEGIN{\"rm tickets/active/APP-001.md\" | getline}'",
    "awk 'BEGIN{while((\"ls\" | getline l)>0) print l}' "
    "tickets/active/APP-001.md",
    "awk 'BEGIN{print \"x\" |& \"cat\"}' tickets/active/APP-001.md",
    # --- AW-7: 呼び出し名のホワイトリスト（組み込み名と `(` の間の空白形・
    # 未知の関数名）---
    "awk 'BEGIN{system (\"rm docs/SPEC.md\")}'",
    "awk 'BEGIN{xyzzy(\"rm docs/SPEC.md\")}'",
    # --- AW-7: リテラル除去の健全性（S1）。2パス実装だと allow に転じる形 ---
    "awk '/\"/ {system(\"rm docs/SPEC.md\")}' in.txt",
    "awk 'BEGIN{x=\"(/a\"; system(\"rm /docs/SPEC.md\")}'",
    "awk 'BEGIN{x=1/2; system(\"rm docs/SPEC.md\")/3}'",
    # --- C6: $'...'（ANSI-C 引用）の hex エスケープによるバイパス（QT-1）。
    # bash が \x22 を `"` へ、\x7c を `|` へ復号するため、hook から見ると全体が
    # 1つの巨大な文字列リテラル（安全）に見えるが、実機では文字列が途中で閉じて
    # system(...) と入力パイプ getline が実行コードとして残る。使い捨て
    # ディレクトリで実機 gawk が EXIT 0 でファイルを削除することを確認済み ---
    "awk $'BEGIN{x=\"foo\\x22system(\\x22rm "
    "tickets/active/APP-001.md\\x22)\\x22\"}'",
    "cd tickets/active && awk $'BEGIN{x=\"foo\\x22system(\\x22rm "
    "APP-001.md\\x22)\\x22\"}'",
    "awk $'BEGIN{x=\"foo\\x22(\\x22rm "
    "tickets/active/APP-001.md\\x22\\x7cgetline x)\\x22\"}'",
    "cd tickets/active && awk $'BEGIN{x=\"foo\\x22(\\x22rm "
    "APP-001.md\\x22\\x7cgetline x)\\x22\"}'",
    # degraded 版（末尾に ` #'` を足すだけで字句解析が失敗する）
    "awk $'BEGIN{x=\"foo\\x22system(\\x22rm "
    "tickets/active/APP-001.md\\x22)\\x22\"}' #'",
    # 印トークンの挿入位置の回帰ガード（既存テストと同形）
    "rm $'tickets/active/APP-001.md'",
    # --- 旧版でも allow だったが本改訂で閉じた形（維持規律3が許容する追加） ---
    "sort -o tickets/active/APP-001.md in.md",
    "sort --output=docs/SPEC.md x.md",
    "uniq in.md tickets/active/APP-001.md",
    "find tickets/active -name '*.md' -fprint0 /tmp/x",
    # C6 の SPEC.md 宛て（ドリフト検知のバックストップが無い経路）
    "awk $'BEGIN{x=\"foo\\x22system(\\x22rm docs/SPEC.md\\x22)\\x22\"}'",
    # C6-2: sed の w（ファイル書き出し）を \x77 で隠す形（QT-1 は head 非依存）
    "sed $'s/a/b/\\x77 tickets/active/APP-001.md' in.md",
    # SH-1: 行継続で語を分断する形（QT-2。bash は削除して連結する）
    "rm tickets/acti\\\nve/APP-001.md",
    # INV-SH-04: 証拠そのものを符号化する形（QT-3 の証拠復号）
    "rm $'\\x74ickets/active/APP-001.md'",
    # --- C7: 行継続の削除がステートメント区切りを飲み込む形（LX-2）。
    # bash が行継続として扱うのは「バックスラッシュが自身エスケープされて
    # いないとき」だけであり、①偶数個並ぶ形 ②`#` コメント末尾の形 では改行は
    # **本物のコマンド区切り**になる。無条件に削除すると後続コマンドの head が
    # 前の語へ吸収され、ALLOWED_HEADS 判定に使われる head が先頭の許可
    # コマンドになる（＝任意の読み取りコマンドに2文字足すだけで hook 全体が
    # 無効化される）。旧版は改行で無条件に分割していたため old=deny。
    # 実機 bash が後続コマンドを実行してファイルを削除・改変することを
    # 使い捨てディレクトリで確認済み ---
    "echo x\\\\\nrm docs/SPEC.md",                    # 2個（偶数）
    "ls \\\\\nrm docs/SPEC.md",
    "echo x\\\\\\\\\nrm docs/SPEC.md",                # 4個（偶数）
    "pwd\\\\\ntruncate -s 0 docs/SPEC.md",
    "cat README.md #\\\nsed -i 's/orig/pwned/' "
    "tickets/active/APP-001.md",                      # コメント末尾
    "ls #x\\\nrm docs/SPEC.md",
    "grep x README.md #\\\ncat y | tee docs/SPEC.md",
    # ダブルクォート内のコマンド置換の中はコマンド文脈へ戻るため `#` が
    # コメントになる（置換の内側は無加工で残し再帰の入口で正規化する）
    'cat "$(ls #\\\nrm docs/SPEC.md)"',
    # 連結の直後にコメントが始まる形（正規化走査が連結時に「直前の文字」を
    # 書き換えないことの回帰ガード。書き換えると allow に転じる）
    "echo a \\\n#c\\\nrm docs/SPEC.md",
    # --- C8: degraded の関数レベルゲートが cwd を見ない形。保護対象 cwd 下で
    # 「字句解析できない置換」を1つ挟むだけで全判定を回避できた。旧版は `cd` を
    # ALLOWED_HEADS に持たず `cd tickets/active` を含むコマンドを丸ごと deny
    # していたため old=deny。実機 bash が削除・上書きすることを確認済み ---
    "cd tickets/active && ls `rm APP-001.md #'`",
    "cd tickets/active && ls `echo x > APP-001.md #'`",
    "cd tickets/active && ls `sed -i 's/a/b/' APP-001.md #'`",
    "cd tickets/active && ls `find . -delete #'`",
    "cd tickets/done && ls `rm APP-001.md #'`",
    # 同型の入れ子（`$( )` の内側のバッククォート）。置換の終端探索が
    # バッククォート領域を読み飛ばさないと対応する `)` を見失い、コマンド
    # 全体が degraded へ落ちて内側の `rm` が `ls` セグメントへ埋もれる
    "cd tickets/active && ls $(ls `rm APP-001.md #'`)",
    # --- C9: awk の `#` コメントに引用符を1つ置いて文字列リテラルの
    # パリティをずらす形（AWL-3）。コメントがモデル化されておらず文字列走査が
    # 改行で打ち切られなかったため、awk が実際に実行する `system(` 等が
    # 文字列の中身として消え、除去後テキストが AW-7 の3条件をすべて満たして
    # allow になっていた。コメント側に `"` をもう1つ置いてパリティを戻すため
    # 「未閉じ文字列＝deny」にも掛からない。旧版は awk を ALLOWED_HEADS に
    # 持たず保護対象に言及する awk をコマンドごと deny していたため old=deny。
    # 実機 gawk 5.2.1 が rc=0 で削除・改変することを確認済み ---
    "awk 'BEGIN{ #\"\nsystem(\"rm docs/SPEC.md\") #\"\n}'",
    "awk 'BEGIN{ #\"\nsystem(\"sed -i s/a/b/ tickets/active/APP-001.md\")"
    " #\"\n}'",
    "awk 'BEGIN{ #\"\nprint \"x\" > \"docs/SPEC.md\" #\"\n}'",
    "awk 'BEGIN{ #\"\n\"rm docs/SPEC.md\" | getline x #\"\n}'",
    "awk 'BEGIN{ #\"\nx=\"system\"; @x(\"rm docs/SPEC.md\") #\"\n}'",
    "awk -e 'BEGIN{ #\"\nsystem(\"rm docs/SPEC.md\") #\"\n}'",
    "awk --source='BEGIN{ #\"\nsystem(\"rm docs/SPEC.md\") #\"\n}'",
    "cd tickets/active && awk 'BEGIN{ #\"\nsystem(\"rm APP-001.md\") #\"\n}'",
    # --- AWL-4: 正規表現／除算の曖昧位置（判定不能→deny）。
    # AWK_OPERAND_END_CHARS が `+` を含むため hook はここを除算と読むが、
    # 実機 gawk は `1 + /re/` を正規表現定数として受け付け後段を実行する
    # （V-15(3a) で実測）。曖昧位置では除去せず判定不能として deny する。
    # 3件目は AWL-1 の改行終端（awk の文字列は行をまたげない） ---
    "awk 'BEGIN{x=1+ /#/; system(\"rm docs/SPEC.md\")}'",
    "awk 'BEGIN{x=1+ /\"/ ; system(\"rm docs/SPEC.md\") ; y=2+ /\"/ }'",
    "awk 'BEGIN{x=\"a\nb\"; system(\"rm docs/SPEC.md\")}'",
    # --- H5: degraded のステートメント区切りに単独 `&` が無く、` #'` の
    # 2文字を足すだけで `&` の後段が先頭 head のセグメントへ埋もれる形。
    # **old=allow だが維持規律3（将来見つかった穴を塞いだ時点で追加してよい）
    # に基づき収載する。** 実機 bash が rc=0 で削除・改変することを確認済み ---
    "ls & rm docs/SPEC.md #'",
    "ls & sed -i 's/a/b/' tickets/active/APP-001.md #'",
    "ls & truncate -s 0 docs/SPEC.md #'",
    "cd tickets/active & rm APP-001.md #'",
    # --- C10: 正規表現リテラルが閉じた直後の `/` は awk では必ず除算だが、
    # `prev` に残るのは `/` の1文字だけで AWK_OPERAND_END_CHARS に無いため、
    # AWL-2 の正規表現除去分岐へ再突入し「2つ目〜3つ目の `/`」（＝awk が
    # 実行する式そのもの）が丸ごとリテラルとして消えていた。**この経路は
    # 除算として据え置く分岐を通らないため div_seen が立たず AWL-4 の
    # 曖昧ガードは一度も発火しない。** 対象は `/` を含まないベース名に限る
    # （パス中の `/` があると鎖がそこで切れて `system(` が残るため）。
    # tester round11 が固定した4形（別テスト T-C10a）に加え、**同一根因で
    # 同時に閉じた3形**を収載する。実機 gawk 5.2.1 が victim を実際に削除する
    # ことを確認済み（`system()` の副作用は式評価中に発生し、その後
    # division by zero で awk 自体は異常終了する）。3件目（間接呼び出し）は
    # **old=allow だが維持規律3・4「本改訂で塞いだ穴」に基づく収載** ---
    "awk 'BEGIN{// / system(\"rm SPEC.md\") / 1}'",
    "awk 'BEGIN{/x// system(\"rm SPEC.md\") / 1}'",
    "awk 'BEGIN{f=\"system\"; /x/ / @f(\"rm SPEC.md\") / 1}'",
    "cd tickets/active && awk 'BEGIN{// / system(\"rm APP-001.md\") / 1}'",
    # --- KLK-013: is_readonly_script_call() の許可経路偽装（python3
    # IDENTIFIER=VALUE 形）。old=allow（KLK-010 以前から存在する既存の穴。
    # KLK-010 設計書 §6 R21 として記録済み）だが、維持規律3・4（将来見つかった
    # 穴を塞いだ時点で追加してよい／本改訂で塞いだ穴）に基づき収載する ---
    "python3 x=y .claude/skills/spec-interview/scripts/"
    "check_spec_structure.py docs/SPEC.md",
    "python3 x=y z=w .claude/skills/spec-interview/scripts/"
    "check_spec_structure.py docs/SPEC.md",
    "FOO=bar python3 x=y .claude/skills/spec-interview/scripts/"
    "check_spec_structure.py docs/SPEC.md",
    "python x=y .claude/skills/spec-interview/scripts/"
    "check_spec_structure.py docs/SPEC.md",
]

# 設計書 docs/designs/KLK-010.md §3-9 の書き込みベクタ棚卸し表と、実装の
# 対応を機械的に固定する（§3-11・原則 P5）。**表に構文を1行足したら、
# ここへ1件以上足す。** 第3版までは表が `"cmd" | getline` と `|&` を
# 列挙していたのに規則もテストも存在せず、それが4回目の穴（C5）になった。
# 「表に書いてあること」は防御ではなく、実装とテストへの写像があって初めて
# 防御になる。
#
# LEGACY_DENY_COMMANDS が「旧版が deny していた集合を守る」ものであるのに
# 対し、本リストは「棚卸し表の各セルが実装されていることを守る」もの
# （目的が異なるため統合しない）。期待値 "allow" の行は**意図的に未対応の
# 穴**であり、塞いだ時点で "deny" へ変える（変更は意識的な行為になる）。
#
# **↑ この記述は下記のとおり精密化する（期待値 "allow" の行を一律に「未対応の
# 穴」と読むと、正しい allow を "deny" へ変える事故が起きる）。**
#
# **期待値 "allow" の行には3種類があり、混同してはならない**（混同すると
# 「穴を塞いだつもりで正しい allow を deny へ変える」事故が起きる）:
#   (a) **意図的に未対応の穴**（INV-SH-11〔パラメータ展開・引数側。原理的に
#       PreToolUse では閉じられないため恒久的に allow のまま維持する。
#       KLK-016 の事後検出に委ねる〕・INV-SED-05
#       〔`-f SCRIPT` のみ。INV-SED-06・07 は KLK-015 の SED-7 で、
#       INV-SH-07・09（ブレース展開・分断glob）は KLK-018 で、それぞれ
#       対応済み＝ "deny" 側へ移動した〕ほか）—
#       塞いだ時点で "deny" へ変える（変更は意識的な行為になる）。
#   (b) **bash と一致した結果としての allow**（INV-SH-15・16・19 ほか）—
#       bash も後続コマンドを実行しない／触るのは保護対象ではない別名で
#       あるため、**"deny" へ変えたら誤り**（過剰deny）。
#   (c) **awk と一致した結果としての allow**（INV-AWKLEX-06・07・08・09・
#       12・13、INV-AWK-16〜20 ほか）— awk が**実行しない**テキスト
#       （コメント・リテラル・プログラム以外のオペランド）にのみ危険様
#       パターンが現れる形、および曖昧さが実行に到達しえない形であるため、
#       **"deny" へ変えたら誤り**。
# (b)(c) を変更するには、設計書 §3-9-2-1／§3-9-3 の分岐条件そのものを覆す
# 実測（V-14(7)／V-15）が要る。
INVENTORY_CASES = (
    # --- awk のプログラム内構文（§3-9 ③列・§3-11 の写像表） ---
    ("INV-AWK-01", "print/printf ... > >>（出力リダイレクト）",
     "awk '{print > \"docs/SPEC.md\"}' x.md", "deny"),
    ("INV-AWK-02", 'print ... | "cmd"（出力パイプ）',
     "awk '{print | \"sort\"}' tickets/active/APP-001.md", "deny"),
    ("INV-AWK-03", 'print ... |& "cmd"（コプロセス出力）',
     "awk 'BEGIN{print \"x\" |& \"cat\"}' tickets/active/APP-001.md", "deny"),
    ("INV-AWK-04", '"cmd" | getline（入力パイプ＝C5）',
     "cd tickets/active && awk 'BEGIN{\"rm APP-001.md\" | getline x}'",
     "deny"),
    ("INV-AWK-05", '"cmd" |& getline（コプロセス入力＝C5）',
     "cd tickets/active && awk 'BEGIN{\"rm APP-001.md\" |& getline x}'",
     "deny"),
    ("INV-AWK-06", 'system("...")',
     "awk 'BEGIN{system(\"rm docs/SPEC.md\")}'", "deny"),
    ("INV-AWK-07", 'system ("...")（組み込み名と ( の間の空白）',
     "awk 'BEGIN{system (\"rm docs/SPEC.md\")}'", "deny"),
    ("INV-AWK-08", '@f("...")（間接関数呼び出し）',
     "awk 'BEGIN{f=\"system\"; @f(\"rm docs/SPEC.md\")}'", "deny"),
    ("INV-AWK-09", '@ f("...")（@ 直後の空白）',
     "awk 'BEGIN{f=\"system\"; @ f(\"rm docs/SPEC.md\")}'", "deny"),
    ("INV-AWK-10", "@load / @include（拡張・ライブラリ読み込み）",
     "awk '@load \"inplace\"; {print}' tickets/active/APP-001.md", "deny"),
    ("INV-AWK-11", "@namespace（gawk 5 の名前空間指令・誤deny側）",
     "awk '@namespace \"util\"; {print $1}' tickets/active/APP-001.md",
     "deny"),
    ("INV-AWK-12", "未収載の関数呼び出し（未知＝deny の機械的既定）",
     "awk 'BEGIN{xyzzy(\"rm docs/SPEC.md\")}'", "deny"),
    ("INV-AWK-13", "許可文字集合外の文字（バックスラッシュ等）",
     "awk 'BEGIN{t=1 \\ 2}' tickets/active/APP-001.md", "deny"),
    ("INV-AWK-14", "ENVIRON / PROCINFO 経由の出力先間接参照",
     "awk '{print > ENVIRON[\"O\"]}' tickets/active/APP-001.md", "deny"),
    ("INV-AWK-15", "変数束縛経由の出力先（-v f=... / 位置引数 f=...）",
     "awk -v f=docs/SPEC.md '{print > f}' in.txt", "deny"),
    ("INV-AWK-16", 'getline < "FILE"（| を伴わない読み取り・意図的に allow）',
     "awk 'BEGIN{getline l < \"tickets/active/APP-001.md\"; print l}'",
     "allow"),
    ("INV-AWK-17", "ユーザー定義関数の宣言と呼び出し",
     "awk 'function p(x){print x} {p($1)}' tickets/active/APP-001.md",
     "allow"),
    ("INV-AWK-18", "比較演算子の >（AW-7 の順序条件）",
     "awk 'NR>1 {print}' tickets/active/APP-001.md", "allow"),
    ("INV-AWK-19", "文字列／正規表現リテラル内の @ ・| ・system(（M11）",
     "awk 'BEGIN{print \"contact: a@b (see docs)\"}' "
     "tickets/active/APP-001.md", "allow"),
    ("INV-AWK-20", "プログラム以外のオペランド中の system(（M12）",
     "awk '{print}' 'system(1).md' tickets/active/APP-001.md", "allow"),
    # --- KLK-029: awk プログラム本文中のバックスラッシュエスケープによる
    # 言及ゲート回避（investigation.md 詳細調査ログ3）。§4-3・§4-5 ---
    ("INV-AWK-21", "system() 引数中のエスケープ（tickets/active型）",
     "awk 'BEGIN{system(\"rm tickets\\/active\\/APP-001.md\")}' "
     "unrelated.txt", "deny"),
    ("INV-AWK-22", "print > のリダイレクト先文字列中のエスケープ",
     "awk '{print > \"tickets\\/active\\/APP-001.md\"}' unrelated.txt",
     "deny"),
    ("INV-AWK-23", "system() 引数中のエスケープ（docs/SPEC.md型・回帰固定）",
     "awk 'BEGIN{system(\"rm docs\\/SPEC.md\")}' unrelated.txt", "deny"),
    ("INV-AWK-24", "対照: -v 束縛のエスケープ言及（AW-2は束縛自体を証拠とする）",
     "awk -v f=\"tickets\\/active\\/APP-001.md\" 'BEGIN{print f}' "
     "unrelated.txt", "deny"),
    ("INV-AWK-25", "対照: 保護対象と無関係な \\ 使用（誤denyが起きないことの固定）",
     "awk 'BEGIN{print \"a\\tb\"}' unrelated.txt", "allow"),
    # --- sed のプログラム内構文（§3-9 ③列。KLK-015 で SED-7
    # （プログラム本文のホワイトリスト）へ反転。正常経路はここで判定し、
    # degraded 経路のみ従来の SED_WRITE_RE ブラックリストを維持する
    # ＝設計書 docs/designs/KLK-015.md §3・§6 R25） ---
    ("INV-SED-01", "s/a/b/w FILE",
     "sed 's/a/b/w tickets/active/APP-001.md' in.md", "deny"),
    ("INV-SED-02", "/re/W FILE", "sed '/x/W docs/SPEC.md' in.md", "deny"),
    ("INV-SED-03", "-i 全表記", "sed -i 's/a/b/' tickets/active/APP-001.md",
     "deny"),
    ("INV-SED-04", "保護対象 cwd 下の w REL",
     "cd tickets/active && sed 's/a/b/w APP-001.md' in.md", "deny"),
    ("INV-SED-05", "-f SCRIPT（プログラム不可視・**未対応**・別チケット）",
     "sed -f script.sed tickets/active/APP-001.md", "allow"),
    ("INV-SED-06", "GNU sed の s///e（KLK-015・SED-7で自動deny＝対応済み）",
     "sed 's/a/b/e' tickets/active/APP-001.md", "deny"),
    ("INV-SED-07", "GNU sed の e コマンド（KLK-015・SED-7で自動deny＝対応済み）",
     "sed '1e cat /etc/hosts' tickets/active/APP-001.md", "deny"),
    ("INV-SED-08", "-n '1,5p'（読み取り・意図的に allow）",
     "sed -n '1,5p' tickets/active/APP-001.md", "allow"),
    # --- KLK-015: SED-7 の回帰テスト（アドレス前置き・区切り文字任意性・
    # r/a/i/c/branch/フラグの新規deny・日常読み取りの追加固定） ---
    ("INV-SED-09", "1w FILE（アドレス前置き）",
     "sed -n '1w tickets/active/APP-001.md' in.md", "deny"),
    ("INV-SED-10", "$w FILE",
     "sed -n '$w tickets/active/APP-001.md' in.md", "deny"),
    ("INV-SED-11", "1,2w FILE",
     "sed -n '1,2w tickets/active/APP-001.md' in.md", "deny"),
    ("INV-SED-12", "2!w FILE",
     "sed -n '2!w tickets/active/APP-001.md' in.md", "deny"),
    ("INV-SED-13", "0~2w FILE（GNU拡張ステップアドレス）",
     "sed -n '0~2w tickets/active/APP-001.md' in.md", "deny"),
    ("INV-SED-14", "1W FILE（大文字）",
     "sed -n '1W tickets/active/APP-001.md' in.md", "deny"),
    ("INV-SED-15", "-e '1w FILE' 形",
     "sed -n -e '1w tickets/active/APP-001.md' in.md", "deny"),
    ("INV-SED-16", "cwd相対形",
     "cd tickets/active && sed -n '1w APP-001.md' in.md", "deny"),
    ("INV-SED-17", "区切り文字 #",
     "sed 's#a#XYZ#w tickets/active/APP-001.md' in.md", "deny"),
    ("INV-SED-18", "区切り文字 ,",
     "sed 's,a,b,w tickets/active/APP-001.md' in.md", "deny"),
    ("INV-SED-19", "区切り文字 |",
     "sed 's|a|b|w tickets/active/APP-001.md' in.md", "deny"),
    ("INV-SED-20", "アドレス前置き×区切り文字の組み合わせ",
     "sed -n '1s#a#XYZ#w tickets/active/APP-001.md' in.md", "deny"),
    ("INV-SED-21", "y コマンド＋区切り文字任意性",
     "sed -n '1y,ab,ba,;2w tickets/active/APP-001.md' in.md", "deny"),
    ("INV-SED-22", "r FILE（外部ファイル読み込み・新規deny）",
     "sed -n '1r /etc/hosts' tickets/active/APP-001.md", "deny"),
    ("INV-SED-23", "1i TEXT（挿入コマンド・新規deny）",
     "sed '1i hello' tickets/active/APP-001.md", "deny"),
    ("INV-SED-24", ":label / b label（分岐・ラベル・新規deny）",
     "sed ':a;b a' tickets/active/APP-001.md", "deny"),
    ("INV-SED-25", "s/a/b/i（大文字小文字無視フラグ・新規deny）",
     "sed 's/a/b/i' tickets/active/APP-001.md", "deny"),
    ("INV-SED-26", "日常読み取りの追加固定（GNU拡張アドレス）",
     "sed -n '0~2p' tickets/active/APP-001.md", "allow"),
    # --- KLK-029: sed プログラム本文中のバックスラッシュエスケープによる
    # 言及ゲート回避（チケット再現手順・investigation.md 詳細調査ログ2・5）。
    # §4-2・§4-5 ---
    ("INV-SED-27", "docs/SPEC.md（スラッシュ1箇所）をs///eの置換文字列内でエスケープ"
     "（チケット再現手順そのもの）",
     "sed 's/.*/rm docs\\/SPEC.md/e' unrelated.txt", "deny"),
    ("INV-SED-28", "tickets/active/*.md（スラッシュ2箇所）を同様にエスケープ",
     "sed 's/.*/rm tickets\\/active\\/APP-001.md/e' unrelated.txt", "deny"),
    ("INV-SED-29", "デリミタ衝突なしのeコマンド単体＋不要なエスケープ挿入",
     "sed '1e echo tickets\\/active\\/APP-001.md' unrelated.txt", "deny"),
    ("INV-SED-30", "対照: 同じエスケープ言及だがSED-7安全文字のみ"
     "（ゲートが広がってもdenyにならないことの固定）",
     "sed -n 's/x/y/; /tickets\\/active\\/APP-001.md/p' unrelated.txt",
     "allow"),
    ("INV-SED-31", "対照: |区切りは元々検出済み・回帰確認",
     "sed 's|.*|rm docs\\|SPEC.md|e' unrelated.txt", "deny"),
    # --- シェル展開の次元（§3-9-2。bash が解釈するがコマンド文字列上は
    # 見えない変換）。この次元は第4版まで棚卸し表に1行も無く、C6 はその空白
    # から出た。相違の**向き**（allow 方向＝危険／deny 方向＝保守的）を
    # 判定として固定する ---
    ("INV-SH-01", "$'...' の hex エスケープで system( を隠す（QT-1）",
     "awk $'BEGIN{x=\"foo\\x22system(\\x22rm "
     "tickets/active/APP-001.md\\x22)\\x22\"}'", "deny"),
    ("INV-SH-02", "$'...' の hex エスケープで | （入力パイプ）を隠す（QT-1）",
     "awk $'BEGIN{x=\"foo\\x22(\\x22rm "
     "tickets/active/APP-001.md\\x22\\x7cgetline x)\\x22\"}'", "deny"),
    ("INV-SH-03", "$'...' × 保護対象 cwd（リテラルパスが現れない形・QT-1）",
     "cd tickets/active && awk $'BEGIN{x=\"foo\\x22system(\\x22rm "
     "APP-001.md\\x22)\\x22\"}'", "deny"),
    ("INV-SH-04", "$'...' で保護対象パス自体を符号化して証拠を隠す（QT-3）",
     "rm $'\\x74ickets/active/APP-001.md'", "deny"),
    ("INV-SH-05", '$"..."（ロケール翻訳・復号は原理的に不可能＝QT-1 のみ）',
     'awk $"BEGIN{print}" tickets/active/APP-001.md', "deny"),
    ("INV-SH-06", "行継続（\\+改行）による語の分断（QT-2）",
     "rm tickets/acti\\\nve/APP-001.md", "deny"),
    ("INV-SH-07", "ブレース展開による分断（KLK-018で対応済み）",
     "rm tickets/{active,done}/APP-001.md", "deny"),
    ("INV-SH-08", "glob（保護対象ディレクトリが素で残り証拠になる形）",
     "rm tickets/active/*.md", "deny"),
    ("INV-SH-09", "glob（パス中に * が入り分断される形・KLK-018で対応済み）",
     "rm tickets/acti*e/APP-001.md", "deny"),
    ("INV-SH-10", "チルダ展開（残りのパスが証拠として残る）",
     "rm ~/kit/tickets/active/APP-001.md", "deny"),
    ("INV-SH-11", "パラメータ展開（値は不可視＝構造的限界・**未対応**）",
     "f=tickets/active/APP-001.md; rm $f", "allow"),
    ("INV-SH-12", "算術展開（$( としてコマンド置換扱い＝保守側の副作用）",
     "echo $((1+2)) && cat tickets/active/APP-001.md", "allow"),
    # --- 行継続と `#` コメントの**分岐条件**（§3-9-2-1）。棚卸し表の行は
    # 「bash の挙動が分岐する条件」まで分解して初めて防御になる（表に
    # 「行継続」という行は存在していたのに、バックスラッシュの偶奇・コメント
    # 内かどうかというサブケースが分解されていなかったために穴が出た）。
    #
    # **期待値 allow の行には2種類があり、混同してはならない**:
    #   (a) **意図的に未対応の穴**（INV-SH-11。INV-SH-07・09 は KLK-018 で
    #       対応済みのため "deny" 側へ移動した）— 塞いだ時点で "deny" へ変える。
    #   (b) **bash と一致した結果としての allow**（INV-SH-15・16・19）—
    #       bash も後続コマンドを実行しない／触るのは保護対象ではない別名で
    #       あるため、**"deny" へ変えたら誤り**（過剰deny＝AC2 違反）。
    ("INV-SH-13", "行継続・バックスラッシュ偶数個（＝リテラル\\ + 区切り）",
     "echo x\\\\\nrm docs/SPEC.md", "deny"),
    ("INV-SH-14", "行継続・# コメント末尾（＝区切り）",
     "cat README.md #\\\nsed -i 's/a/b/' tickets/active/APP-001.md", "deny"),
    ("INV-SH-15", "行継続・奇数個で後続が語へ吸収される（bash も連結＝(b)）",
     "echo x\\\nrm docs/SPEC.md", "allow"),
    ("INV-SH-16", "行継続・'…' の内側（bash は連結しない＝(b)）",
     "rm 'tickets/acti\\\nve/APP-001.md'", "allow"),
    ("INV-SH-17", '行継続・"…" の内側（bash は連結する）',
     'rm "tickets/acti\\\nve/APP-001.md"', "deny"),
    ("INV-SH-18", "dq 内のコマンド置換の中のコメント（内側はコマンド文脈）",
     'cat "$(ls #\\\nrm docs/SPEC.md)"', "deny"),
    ("INV-SH-19", "連結後に basename が保護対象でなくなる形（＝(b)）",
     "echo x > docs/SPEC.md\\\n.bak", "allow"),
    ("INV-SH-20", "クォート内・語中の # はコメントではない（AC1 との整合）",
     "rm 'x#y' tickets/acti\\\nve/APP-001.md", "deny"),
    ("INV-SH-21", "degraded の単独 & ステートメント区切り（H5）",
     "ls & rm docs/SPEC.md #'", "deny"),
    # --- KLK-017（H6）: degraded がコマンド置換／バッククォート／プロセス
    # 置換の内側を評価しない形。KLK-014（`_extract_degraded_substs`）で
    # 対処済みのため、期待値は "allow" ではなく "deny" として登録する
    # （チケット本文の「先に KLK-014／KLK-015 が完了した場合は deny として
    # 登録する」に該当。設計書 §3-11 INV-SH-22・T-H6a と同型） ---
    ("INV-SH-22", "degraded がコマンド置換の内側を評価しない形"
     "（H6・KLK-014 で deny 済み）",
     "ls $(rm docs/SPEC.md) #'", "deny"),
    # --- awk の**字句次元**（§3-9-3）。hook はプログラム本文の字面を見るが、
    # awk が実行するのは「リテラルでもコメントでもない部分」だけである。
    # 両者が食い違う条件をサブケースへ分解して固定する（P7／P8）。
    # テキストを除去する近似には**方向の非対称**があり、除去しすぎ
    # （over-removal）だけが allow 方向（危険）、除去しなさすぎ
    # （under-removal）は deny 方向（安全）になる。
    #
    # **期待値 allow の行の3種類目（(c)）をここで追加する**:
    #   (c) **awk と一致した結果としての allow**（INV-AWKLEX-06・07・08・09・
    #       12・13）— awk が**実行しない**テキスト（コメント・リテラル）に
    #       のみ危険様パターンが現れる形、および曖昧さが実行に到達しえない
    #       形であることが根拠であり、**"deny" へ変えたら誤り**。変更するには
    #       設計書 §3-9-3 の分岐条件そのものを覆す実測（V-15）が要る。
    # 逆に INV-AWKLEX-01〜05・10・11 は「判定不能→deny」の固定点であり、
    # "allow" へ変えたら C9 と同型の穴が開く。
    ("INV-AWKLEX-01", 'コメント本文の " で文字列パリティをずらす（C9-1）',
     "awk 'BEGIN{ #\"\nsystem(\"rm docs/SPEC.md\") #\"\n}'", "deny"),
    ("INV-AWKLEX-02", "同・-e 形（C9-4）",
     "awk -e 'BEGIN{ #\"\nsystem(\"rm docs/SPEC.md\") #\"\n}'", "deny"),
    ("INV-AWKLEX-03", "同・保護対象 cwd 相対（C9-5）",
     "cd tickets/active && awk 'BEGIN{ #\"\nsystem(\"rm APP-001.md\")"
     " #\"\n}'", "deny"),
    ("INV-AWKLEX-04", "同・間接呼び出し（C9-3）",
     "awk 'BEGIN{ #\"\nx=\"system\"; @x(\"rm docs/SPEC.md\") #\"\n}'",
     "deny"),
    ("INV-AWKLEX-05", "文字列が改行に達する（未終端＝判定不能）",
     "awk 'BEGIN{x=\"a\nb\"; system(\"rm docs/SPEC.md\")}'", "deny"),
    ("INV-AWKLEX-06", "文字列内の \\+改行（gawk の行継続＝(c)）",
     "awk 'BEGIN{x=\"a\\\nb\"; print x}' tickets/active/APP-001.md", "allow"),
    ("INV-AWKLEX-07", "コメント本文の | / @ / system(（読み取り＝(c)）",
     "awk '{print $1} # a|b @c system(' tickets/active/APP-001.md", "allow"),
    ("INV-AWKLEX-08", "正規表現内の #（AWL-2 が先に消費＝(c)）",
     "awk '/#/ {print}' tickets/active/APP-001.md", "allow"),
    ("INV-AWKLEX-09", "文字列内の #（AWL-1 が先に消費＝(c)）",
     "awk '{print \"#\"}' tickets/active/APP-001.md", "allow"),
    ("INV-AWKLEX-10", "除算の後の # × 同一行に / が残る（AWL-4）",
     "awk 'BEGIN{x=1+ /#/; system(\"rm docs/SPEC.md\")}'", "deny"),
    ("INV-AWKLEX-11", "除算の後の文字列 × 同一行に / が残る（AWL-4）",
     "awk 'BEGIN{x=1+ /\"/ ; system(\"rm docs/SPEC.md\") ; y=2+ /\"/ }'",
     "deny"),
    ("INV-AWKLEX-12", "除算あり・以降に / が残らない（AWL-4 の非発火＝(c)）",
     "awk '{print $1/2, $3/4, \"ratio\"}' tickets/active/APP-001.md",
     "allow"),
    ("INV-AWKLEX-13", "複数行プログラム（D-1 の固定点＝(c)）",
     "awk 'BEGIN{FS=\":\"}\n{print $2}' tickets/active/APP-001.md", "allow"),
    # --- C10（Phase 14 実施中に発見・KLK-017 で書き戻し）: 閉じた正規表現
    # リテラルの直後に除算に見える `/` が連なる形。開始条件の食い違い
    # （`prev_regex` の欠落）による over-removal＝allow の穴だった。
    # T-C10a（test_awk_chained_division_after_regex_bypasses_awl4_deny）の
    # 正準形と同型 ---
    ("INV-AWKLEX-14", "閉じた正規表現直後の連鎖除算（C10・AWL-2 の prev_regex）",
     "awk 'BEGIN{/x/ / system(\"rm SPEC.md\") / 1}'", "deny"),
    # --- KLK-019: シェル制御構文（for/while/until/if/elif/case）の本体再帰
    # 判定（設計書 docs/designs/KLK-019.md §9 AC4 の分岐列挙と1対1対応させる）。
    # ALLOWED_HEADS/CWD_SAFE_HEADS は変更していない（§3方針1）。
    ("INV-CTRL-01", "classic for 読み取り（AC1）",
     "for f in tickets/active/*.md; do echo $f; done", "allow"),
    ("INV-CTRL-02", "for 本体の書き込み（リテラルパス。ループ変数不使用）",
     "for i in 1 2 3; do rm tickets/active/APP-001.md; done", "deny"),
    ("INV-CTRL-03", "for 本体の書き込み（ループ変数経由。AC2/AC3の核心）",
     "for f in tickets/active/*.md; do rm $f; done", "deny"),
    ("INV-CTRL-04", "for 本体の読み取り（ループ変数経由。AC3の裏付け）",
     "for f in tickets/active/*.md; do cat $f; done", "allow"),
    ("INV-CTRL-05", "for NAME; do（in 省略。LIST が無いため guarded_loop_vars"
     "へ未登録＝安全側）",
     "for f; do cat $f; done", "allow"),
    ("INV-CTRL-06", "C形式for（構造を確定できずフォールバックdeny）",
     "for ((i=0; i<3; i++)); do rm tickets/active/APP-001.md; done", "deny"),
    ("INV-CTRL-07", "while 読み取り",
     "while read l; do echo $l; done < tickets/active/APP-001.md", "allow"),
    ("INV-CTRL-08", "while 条件節の書き込み",
     "while rm tickets/active/APP-001.md; do echo done; done", "deny"),
    ("INV-CTRL-09", "until 読み取り",
     "until false; do cat tickets/active/APP-001.md; break; done", "allow"),
    ("INV-CTRL-10", "if-then-fi 読み取り",
     "if [ -f tickets/active/APP-001.md ]; then echo yes; fi", "allow"),
    ("INV-CTRL-11", "if-then-else-fi 読み取り",
     "if true; then cat tickets/active/APP-001.md; else echo no; fi", "allow"),
    ("INV-CTRL-12", "if-elif-else-fi 読み取り",
     "if false; then echo a; elif true; then cat tickets/active/APP-001.md;"
     " else echo b; fi", "allow"),
    ("INV-CTRL-13", "if 条件節の書き込み",
     "if rm tickets/active/APP-001.md; then echo ok; fi", "deny"),
    ("INV-CTRL-14", "if 本体（then）の書き込み",
     "if true; then rm tickets/active/APP-001.md; fi", "deny"),
    ("INV-CTRL-15", "case 単一パターン読み取り",
     "case x in *.md) cat tickets/active/APP-001.md ;; esac", "allow"),
    ("INV-CTRL-16", "case 単一パターン書き込み",
     "case x in *) rm tickets/active/APP-001.md ;; esac", "deny"),
    ("INV-CTRL-17", "case 複数パターン a|b)（構造を確定できずフォールバックdeny）",
     "case x in a|b) cat tickets/active/APP-001.md ;; esac", "deny"),
    ("INV-CTRL-18", "case で in 欠落（構造を確定できずフォールバックdeny）",
     "case x *) rm tickets/active/APP-001.md ;; esac", "deny"),
    ("INV-CTRL-19", "入れ子制御構文（読み取り。for内if）",
     "for f in tickets/active/*.md; do if true; then cat $f; fi; done",
     "allow"),
    ("INV-CTRL-20", "入れ子制御構文（深い階層での書き込み。for内ifのループ変数）",
     "for f in tickets/active/*.md; do if true; then rm $f; fi; done", "deny"),
    ("INV-CTRL-21", "if cd DIR; then ...; fi による cwd 追跡（R-CTRL4回帰"
     "ガード・deny側）",
     "if cd tickets/active; then rm APP-001.md; fi", "deny"),
    ("INV-CTRL-22", "if cd DIR; then ...; fi による cwd 追跡（R-CTRL4回帰"
     "ガード・allow側）",
     "if cd tickets/active; then cat APP-001.md; fi", "allow"),
    ("INV-CTRL-23", "単独 fi のみのステートメント（R-CTRL3）",
     "fi", "allow"),
    ("INV-CTRL-24", "単独 done のみのステートメント（R-CTRL3）",
     "done", "allow"),
    ("INV-CTRL-25", "単独 esac のみのステートメント（R-CTRL3）",
     "esac", "allow"),
)


class TestGuardBashWrites(unittest.TestCase):
    def run_guard(self, data):
        rc, out, _ = _util.run_script(_util.GUARD_BASH, data)
        self.assertEqual(rc, 0)  # hookは常に exit 0
        return _util.hook_output(out)

    def assertAllow(self, command):
        self.assertIsNone(self.run_guard(payload(command)),
                          "expected allow: %s" % command)

    def assertDeny(self, command):
        out = self.run_guard(payload(command))
        self.assertIsNotNone(out, "expected deny: %s" % command)
        self.assertEqual(out.get("permissionDecision"), "deny")
        return out

    # --- 書き込みベクタは deny ---

    def test_redirect_to_ticket_deny(self):
        self.assertDeny("echo x > tickets/active/APP-001.md")

    def test_append_redirect_deny(self):
        self.assertDeny("cat note.md >> tickets/active/APP-001.md")

    def test_interpreter_oneliner_deny(self):
        self.assertDeny(
            "python3 -c \"open('tickets/active/APP-001.md','w').write('x')\"")

    def test_sed_inplace_deny(self):
        self.assertDeny("sed -i 's/todo/done/' tickets/active/APP-001.md")

    def test_tee_deny(self):
        self.assertDeny("echo x | tee tickets/active/APP-001.md")

    def test_find_exec_deny(self):
        self.assertDeny(
            "find tickets/active -name '*.md' -exec sed -i 's/a/b/' {} \\;")

    def test_pipe_to_xargs_rm_deny(self):
        self.assertDeny("find tickets/active -name '*.md' | xargs rm")

    def test_rm_ticket_deny(self):
        self.assertDeny("rm tickets/active/APP-001.md")

    def test_cp_into_tickets_deny(self):
        self.assertDeny("cp rogue.md tickets/active/APP-001.md")

    def test_spec_redirect_deny(self):
        self.assertDeny("cat draft.md > docs/SPEC.md")

    def test_heredoc_deny(self):
        self.assertDeny("cat > tickets/active/APP-001.md <<EOF\nx\nEOF")

    def test_git_checkout_ticket_deny(self):
        self.assertDeny("git checkout -- tickets/active/APP-001.md")

    def test_redirect_to_variable_deny(self):
        self.assertDeny('f=tickets/active/APP-001.md; cat x > "$f"')

    # --- 読み取り・移動系は allow ---

    def test_mv_between_active_done_allow(self):
        self.assertAllow("mv tickets/done/APP-001_x.md tickets/active/")

    def test_mv_archive_allow(self):
        self.assertAllow("mv tickets/done/APP-001_x.md ~/vault/Archives/proj/")

    def test_read_commands_allow(self):
        self.assertAllow("cat tickets/active/APP-001.md")
        self.assertAllow("ls tickets/active/")
        self.assertAllow("grep -rl REQ-001 tickets/active tickets/done")
        self.assertAllow("head -20 docs/SPEC.md")
        self.assertAllow("sed -n '1,10p' tickets/active/APP-001.md")
        self.assertAllow("find tickets/active -name '*.md'")

    def test_pipe_readonly_allow(self):
        self.assertAllow("cat tickets/active/APP-001.md | grep status | wc -l")

    def test_git_readonly_and_stage_allow(self):
        self.assertAllow("git add tickets/active/APP-001.md && "
                         "git commit -m '[APP-001] update'")
        self.assertAllow("git diff tickets/active/APP-001.md")
        self.assertAllow("git log --oneline -- tickets/done/")

    def test_test_and_echo_statement_allow(self):
        # 保護対象に言及しないステートメント（echo）は検査対象外
        self.assertAllow("[ -f tickets/active/APP-001.md ] && echo exists")

    def test_unrelated_command_allow(self):
        self.assertAllow("python3 -m pytest tests/")
        self.assertAllow("npm run build && npm test")

    def test_claude_dir_spec_template_allow(self):
        self.assertAllow(
            "cp .claude/skills/spec-interview/templates/SPEC.md /tmp/x.md")

    def test_templates_and_index_allow(self):
        # Templates・_index.md は validator と同様に対象外
        self.assertAllow("cat tickets/Templates/ticket.md")

    def test_metrics_aggregate_allow(self):
        self.assertAllow("python3 .claude/metrics/aggregate.py APP-001")

    def test_list_tickets_cli_allow(self):
        self.assertAllow("python3 scripts/list_tickets.py")

    # --- KLK-004: docs/reports/{ID}/ は保護対象外（is_ticket()の境界と同型） ---

    def test_docs_reports_path_not_mentioned_as_guarded(self):
        # mentions_guarded() は KLK-010 Phase 1 (4ae9f61) で「事前分割済みの語のリスト」を
        # 受け取る契約へ変更された（旧実装は内部で command.split() していたため生の
        # コマンド文字列を渡しても正しく動いた）。生の文字列をそのまま渡すと Python が
        # 文字単位でイテレートし、どんな入力でも常に False を返してしまう（偽陰性）ため、
        # 呼び出し規約どおり事前分割済みのトークン列で呼び出す。
        self.assertFalse(
            guard.mentions_guarded(
                ["rm", "docs/reports/KLK-004/investigation.md"]))

    def test_mentions_guarded_raw_string_call_is_a_false_negative_trap(self):
        # 上のテストの呼び方が「たまたま常にFalseになる壊れた呼び方」ではないことの
        # 対照実験。同じ raw-string 呼び出し方（文字単位イテレート）で本来 True になる
        # べき保護対象パス（tickets/active/ 配下）を渡しても、文字単位分割では
        # is_guarded_token に完全なパスが渡らないため False になってしまうことを示す。
        guarded_word = "tickets/" + "active/APP-001.md"
        self.assertFalse(guard.mentions_guarded("rm " + guarded_word))
        # 正しい呼び方（事前分割済みトークン列）であれば True になる
        self.assertTrue(guard.mentions_guarded(["rm", guarded_word]))
        # （KLK-027で決定: 本チケット時点の全3呼び出し箇所（guard_bash_writes.py内、
        # expanded_words/skeleton.split()/words_list由来）は事前分割済みトークン契約を既に遵守しており、
        # 生文字列呼び出しの誤用は現存しない。isinstance等の防御的強化は「現存しないバグの予防的修正」
        # であり自動split実装の追加が新たな不一致リスクを生みうるため見送り、本テストは意図的な
        # 仕様固定として維持する）

    def test_docs_reports_rm_allow(self):
        # ホワイトリスト外の先頭コマンド（rm）でも docs/reports/ 配下は非対象のため deny されない
        self.assertAllow("rm docs/reports/KLK-004/investigation.md")

    def test_docs_reports_redirect_allow(self):
        # リダイレクトによる書き込みも docs/reports/ 配下は非対象
        self.assertAllow("echo x > docs/reports/KLK-004/implementation.md")

    # --- 読み取り専用スクリプト（READONLY_SCRIPTS）の例外 ---

    def test_spec_structure_checker_allow(self):
        self.assertAllow(
            "python3 .claude/skills/spec-interview/scripts/"
            "check_spec_structure.py docs/SPEC.md")

    def test_other_python_script_with_spec_deny(self):
        # 許可はREADONLY_SCRIPTSのパス一致に限る
        self.assertDeny("python3 evil.py docs/SPEC.md")

    def test_python_flag_before_checker_deny(self):
        # -c/-m 等の別実行経路はスクリプトパスがあっても不許可
        self.assertDeny(
            "python3 -c \"x\" .claude/skills/spec-interview/scripts/"
            "check_spec_structure.py docs/SPEC.md")

    def test_checker_redirect_to_spec_still_deny(self):
        self.assertDeny(
            "python3 .claude/skills/spec-interview/scripts/"
            "check_spec_structure.py docs/SPEC.md > docs/SPEC.md")

    # KLK-013: is_readonly_script_call() の許可経路偽装（先頭コマンドより
    # 後ろの NAME=VALUE 語を位置によらずスキップしていたことが原因）。

    def test_disguised_env_assignment_after_interpreter_deny(self):
        # チケット再現手順そのもの
        self.assertDeny(
            "python3 x=y .claude/skills/spec-interview/scripts/"
            "check_spec_structure.py docs/SPEC.md")

    def test_disguised_multiple_env_assignments_after_interpreter_deny(self):
        # 代入語風の語が2連続
        self.assertDeny(
            "python3 x=y z=w .claude/skills/spec-interview/scripts/"
            "check_spec_structure.py docs/SPEC.md")

    def test_disguised_env_assignment_with_legit_prefix_deny(self):
        # 正規の FOO=bar 前置きと偽装の組合せ
        self.assertDeny(
            "FOO=bar python3 x=y .claude/skills/spec-interview/scripts/"
            "check_spec_structure.py docs/SPEC.md")

    def test_disguised_env_assignment_python_alias_deny(self):
        # python エイリアスでも同様に偽装できてはならない
        self.assertDeny(
            "python x=y .claude/skills/spec-interview/scripts/"
            "check_spec_structure.py docs/SPEC.md")

    def test_readonly_script_with_env_prefix_allow(self):
        # 正規の許可経路（環境変数前置き付き）は壊れない
        self.assertAllow(
            "FOO=bar python3 .claude/skills/spec-interview/scripts/"
            "check_spec_structure.py docs/SPEC.md")

    # KLK-013 tester能動検証: 上記の書き換え（head_args()の最初の語だけを見る）は
    # is_assignment_word() によるフィルタを head_args()[0] 自体には適用しない。
    # このため「NAME=」を空白なしで READONLY_SCRIPTS の実パスへ直接連結した語」は、
    # 代入語としてスキップされず、かつ os.path.normpath(...).endswith(READONLY_SCRIPTS)
    # が単純な文字列サフィックス一致であるために誤って一致してしまい、allowになる
    # （実際に python3 が開こうとするファイルは「x=.claude/.../check_spec_structure.py」
    # という別名であり、本物の READONLY_SCRIPTS ではない＝本チケットの脅威モデルと同型）。
    # merge-base（2963be8）の旧実装ではこの語が is_assignment_word() でスキップされ、
    # 後続に実スクリプト語が無いため deny だった（旧=deny・新=allow の回帰。AC3違反）。
    # 検出器: is_readonly_script_call()（本チケットの修正対象そのもの）。
    def test_disguised_env_assignment_glued_to_readonly_script_deny(self):
        # 空白を除いた「x=<READONLY_SCRIPT>」1語。旧実装は is_assignment_word() で
        # この1語ごとスキップし後続に一致する語が無いため deny だったが、新実装は
        # head_args()[0] をそのまま endswith(READONLY_SCRIPTS) 判定するため、
        # 語全体の末尾が READONLY_SCRIPTS と文字列一致してしまい allow に回帰する。
        self.assertDeny(
            "python3 x=.claude/skills/spec-interview/scripts/"
            "check_spec_structure.py docs/SPEC.md")

    def test_disguised_env_assignment_glued_alt_name_deny(self):
        # 変数名・区切りを変えた同型（y=z...）。単発の偶然ではないことの裏取り。
        self.assertDeny(
            "python3 y=z.claude/skills/spec-interview/scripts/"
            "check_spec_structure.py docs/SPEC.md")

    def test_disguised_three_env_assignments_after_interpreter_deny(self):
        # 代入語風の語が3連続（implementerの2連続テストの境界を1段先へ）。
        # 新実装は head_args()[0] のみを見るため N の数に関わらずdenyのはずだが、
        # 将来 head_args() 自体が変わった際の回帰検知として固定する。
        self.assertDeny(
            "python3 a=1 b=2 c=3 .claude/skills/spec-interview/scripts/"
            "check_spec_structure.py docs/SPEC.md")

    def test_disguised_env_assignment_then_flag_deny(self):
        # 代入語風の語の直後にさらにフラグが来る形。head_args()[0] が代入語風でも
        # 単に一致しない語として deny されることの裏取り（-c 等の別経路と合成されても
        # 壊れないことの確認）。
        self.assertDeny(
            "python3 x=y -u .claude/skills/spec-interview/scripts/"
            "check_spec_structure.py docs/SPEC.md")

    # KLK-013 差し戻し後の再検証で判明: os.path.normpath(first).endswith(
    # READONLY_SCRIPTS) は「代入語の glue」に限らず、READONLY_SCRIPTS の要素と
    # 文字列末尾が一致しさえすれば任意の前置ディレクトリを許してしまう、より
    # 広い偽装クラスを持っていた（境界が "/" で揃うため部分一致として成立する）。
    # 攻撃者が cwd から到達可能などこかに「.claude/skills/spec-interview/scripts/
    # check_spec_structure.py」という同じ相対パスの入れ子ディレクトリを用意できれば
    # （例: 書き込み可能などこかに `evil_dir/.claude/skills/spec-interview/scripts/
    # check_spec_structure.py` という偽物を配置）、endswith 一致によりそれが本物の
    # READONLY_SCRIPTS であるかのように誤認され allow になっていた（旧=allow）。
    # os.path.normpath(first) in READONLY_SCRIPTS への完全一致化（367cecd）により、
    # これらは一律 deny に転じる（旧=allow→新=deny・安全側）。これは本チケット
    # タイトル「許可経路偽装による任意コード実行」と同型の別インスタンスであり、
    # 完全一致化がこのクラス全体を閉じたことを固定するための回帰ガード。
    def test_disguised_directory_prefix_relative_deny(self):
        # 相対パスの前に無関係なディレクトリ1段を付けただけの形。
        # 旧 endswith 実装では "/" 境界が揃うため誤って一致し allow だった。
        self.assertDeny(
            "python3 a/.claude/skills/spec-interview/scripts/"
            "check_spec_structure.py docs/SPEC.md")

    def test_disguised_directory_prefix_absolute_deny(self):
        # 絶対パスの前置き版。同じ境界一致の問題が絶対パスでも成立していた。
        self.assertDeny(
            "python3 /tmp/evil/.claude/skills/spec-interview/scripts/"
            "check_spec_structure.py docs/SPEC.md")

    # --- extract_spec_section.py（KLK-006）の同型許可 ---
    # is_readonly_script_call()はREADONLY_SCRIPTSの完全一致判定のみを行う
    # ため、新規登録スクリプトについても既存のcheck_spec_structure.py向け
    # テストと同じ判定ロジックが働く。判定ロジック自体は変更していないため、
    # ここでは代表的な許可・deny各1件と偽装パターン1件のみ確認し、既存の
    # 全偽装パターン（KLK-013系列）の再複製はしない（判定関数が共通のため
    # 冗長になる）。

    def test_extract_spec_section_allow(self):
        self.assertAllow(
            "python3 .claude/skills/spec-interview/scripts/"
            "extract_spec_section.py docs/SPEC.md REQ-001")

    def test_extract_spec_section_wrong_script_deny(self):
        self.assertDeny("python3 evil.py docs/SPEC.md REQ-001")

    def test_extract_spec_section_disguised_directory_prefix_deny(self):
        self.assertDeny(
            "python3 a/.claude/skills/spec-interview/scripts/"
            "extract_spec_section.py docs/SPEC.md REQ-001")

    # --- fail-open ---

    def test_non_bash_tool_allow(self):
        out = self.run_guard({"tool_name": "Write",
                              "tool_input": {"file_path": "x"}})
        self.assertIsNone(out)

    def test_broken_stdin_allow(self):
        rc, out, _ = _util.run_script(_util.GUARD_BASH, "not json")
        self.assertEqual(rc, 0)
        self.assertIsNone(_util.hook_output(out))

    # --- KLK-012 AC5: 非 dict 入力でクラッシュしない ---

    def test_non_dict_stdin_allow(self):
        rc, out, _ = _util.run_script(_util.GUARD_BASH, "[]")
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), "")

    def test_non_dict_tool_input_allow(self):
        out = self.run_guard({"tool_name": "Bash", "tool_input": []})
        self.assertIsNone(out)

    def test_non_str_command_allow(self):
        out = self.run_guard({"tool_name": "Bash",
                              "tool_input": {"command": 123}})
        self.assertIsNone(out)

    # --- KLK-010: クォート内の演算子で誤denyしない（AC1・AC2） ---

    def test_regex_alternation_in_quotes_allow(self):
        # T-A1: 正規表現の選択子 `|` をシェルパイプと誤認しない
        self.assertAllow(
            "grep -E '^(id|title):' tickets/active/APP-001.md")

    def test_heredoc_pattern_in_quotes_allow(self):
        # T-A3b: クォート内の `<<` をヒアドキュメントと誤認しない
        self.assertAllow("grep -c '<<EOF' tickets/active/APP-001.md")

    def test_unrelated_trailing_redirect_allow(self):
        # T-A3c: 保護対象に触れない後段リダイレクトを巻き添えにしない
        self.assertAllow(
            'cat tickets/active/APP-001.md && echo x > "$TMP"')

    def test_redirect_char_in_quotes_allow(self):
        # T-A4: クォート内の `>` をリダイレクトと誤認しない
        self.assertAllow("grep -c '>' tickets/active/APP-001.md")

    def test_comment_char_in_quotes_allow(self):
        # T-A5: クォート内の `#` をコメントと誤認しない
        self.assertAllow("grep -n '#' tickets/active/APP-001.md")

    def test_sed_read_only_flags_allow(self):
        # T-SED-N: in-place 判定が -n を誤爆しない
        self.assertAllow("sed -n '1,10p' tickets/active/APP-001.md")

    def test_sed_gnu_extended_address_allow(self):
        # T-SED7d（KLK-015・INV-SED-26の第2形）: GNU拡張の相対アドレス
        # （1,+3）も SED_SAFE_STRUCTURAL_CHARS で読み取りのまま allow になる
        self.assertAllow("sed -n '1,+3p' tickets/active/APP-001.md")

    # --- KLK-010: すり抜けを塞ぐ（AC4・AC5） ---

    def test_sed_inplace_empty_suffix_deny(self):
        # T-B4c: `-i''`（空サフィックス直結）
        self.assertDeny("sed -i'' 's/a/b/' tickets/active/APP-001.md")

    def test_interpreter_oneliner_spec_deny(self):
        # T-B5: 1トークンへ埋め込まれたリテラルパス
        self.assertDeny(
            "python3 -c \"open('docs/SPEC.md','w').write('x')\"")

    def test_path_traversal_via_claude_dir_deny(self):
        # T-B6b: 正規化後に .claude 成分が消えるパストラバーサル
        self.assertDeny(
            "rm ./tickets/active/../../.claude/../tickets/active/APP-001.md")

    # --- KLK-010: 非該当パスで誤denyしない（R3） ---

    def test_similar_but_unguarded_paths_allow(self):
        # T-FP: ホワイトリスト外の head で検証する（判定差が出る形）
        self.assertAllow("python3 -c \"print('MYSPEC.md')\"")
        self.assertAllow("cp docs/SPEC.md.bak /tmp/x")

    # --- KLK-010: degraded mode（字句解析できない入力） ---

    def test_unparsable_write_deny(self):
        # T-D1: 未閉じクォートでも書き込みは素通りさせない
        self.assertDeny("rm tickets/active/APP-001.md #'")

    def test_unparsable_read_allow(self):
        # T-D2: 未閉じクォートでも読み取りは誤denyしない
        self.assertAllow("cat tickets/active/APP-001.md #'")

    # --- KLK-010: ホワイトリスト追加コマンド（AC3・AC2） ---

    def test_cd_allow(self):
        # T-A2: cd は書き込み経路を持たないため無条件許可
        self.assertAllow("cd tickets/active && ls")

    def test_awk_field_separator_allow(self):
        # T-A3a: -F'|' は保護対象に言及しないため内蔵リダイレクトと区別できる
        self.assertAllow(
            "awk -F'|' '{print $1}' tickets/active/APP-001.md")

    def test_added_readonly_heads_allow(self):
        # T-A6: AC3 で追加した読み取り・変換系（入力リダイレクトを含む）
        self.assertAllow("pwd && cut -d: -f2 tickets/active/APP-001.md")
        self.assertAllow("tr -d '\\r' < tickets/active/APP-001.md")
        self.assertAllow("echo tickets/active/APP-001.md")

    # --- KLK-010: sed in-place の別表記・スクリプト内書き出し（AC4） ---

    def test_sed_long_inplace_with_suffix_deny(self):
        # T-B4a: --in-place=SUFFIX
        self.assertDeny(
            "sed --in-place=.bak 's/a/b/' tickets/active/APP-001.md")

    def test_sed_combined_short_flags_deny(self):
        # T-B4b: 短フラグ結合 -ni
        self.assertDeny("sed -ni 's/a/b/p' tickets/active/APP-001.md")

    def test_sed_write_command_deny(self):
        # T-SEDW: sed の w コマンド（スクリプト引数に埋め込まれた書き出し）
        self.assertDeny("sed 's/a/b/w tickets/active/APP-001.md' in.md")
        self.assertDeny("sed '/x/w docs/SPEC.md' in.md")

    def test_sed_address_prefixed_write_deny(self):
        # T-SED7a（KLK-015・INV-SED-09〜11の固定点）: SED_WRITE_RE が取りこぼす
        # アドレス前置きの w/W を SED-7 が字句非依存で捕捉すること
        self.assertDeny("sed -n '1w tickets/active/APP-001.md' in.md")
        self.assertDeny("sed -n '$w tickets/active/APP-001.md' in.md")
        self.assertDeny("sed -n '1,2w tickets/active/APP-001.md' in.md")

    def test_sed_arbitrary_delimiter_write_deny(self):
        # T-SED7b（KLK-015・INV-SED-17〜19の固定点）: s/y の区切り文字が `/`
        # 以外でも w コマンドを取りこぼさないこと
        self.assertDeny("sed 's#a#XYZ#w tickets/active/APP-001.md' in.md")
        self.assertDeny("sed 's,a,b,w tickets/active/APP-001.md' in.md")
        self.assertDeny("sed 's|a|b|w tickets/active/APP-001.md' in.md")

    def test_sed_flag_area_allowed_flags_only_allow(self):
        # T-SED7e（設計書§9テスト観点(c)の後半形）: s/// のフラグ領域に
        # 許可済み文字（g/p/数字）のみが現れる形は、w/e が単独で現れる形
        # （INV-SED-01・06・25）と対で、正しく allow のまま維持されること
        self.assertAllow("sed 's/a/b/g' tickets/active/APP-001.md")
        self.assertAllow("sed 's/a/b/gp' tickets/active/APP-001.md")
        self.assertAllow("sed 's/a/b/3' tickets/active/APP-001.md")

    def test_sed_multiple_dash_e_write_split_across_boundary_deny(self):
        # T-SED7f（設計書§9テスト観点(b)・R3）: w コマンドをアドレスと
        # 本体で2つの -e 引数へ分割しても、GNU sed が改行結合して1つの
        # プログラムとして実行する経路を取りこぼさないこと
        # （`sed_program_texts` が複数 -e を列挙し、`len(texts) > 1` の
        # 結合チェック分岐を経由する）
        self.assertDeny(
            "sed -n -e '1' -e 'w tickets/active/APP-001.md' in.md")
        self.assertDeny(
            "sed -e 's/a/b' -e '/w tickets/active/APP-001.md' in.md")

    def test_sed_multiple_dash_e_readonly_combined_allow(self):
        # T-SED7g（設計書§9テスト観点(b)の対照・allow側）: 複数 -e に
        # 分割された読み取り専用プログラムは、結合チェック分岐を経由しても
        # 誤denyしないこと
        self.assertAllow(
            "sed -n -e '1,2p' -e '4,5p' tickets/active/APP-001.md")

    def test_sed_bracket_expression_containing_delimiter_allow(self):
        # T-SED7h（tester発見・KLK-015 AC6違反。implementer差し戻し1回目で
        # 修正）: `sed_strip_literals` は当初POSIX/GNU の文字クラス
        # （ブラケット式 `[...]`）を認識せず、デリミタ文字がブラケット式の
        # 内側にあってもデリミタとしてクロージングしてしまい、実際には
        # 安全な読み取り専用プログラム（`/[/]/p`＝スラッシュを含む行を表示
        # するだけ）を字句未確定（None）として誤denyしていた。設計書
        # §6 R1 の新規deny列挙にこの形は無く、実機 GNU sed では書き込み・
        # 実行を一切伴わない純粋な読み取りである（`sed -n '/[/]/p' file`
        # は該当行を標準出力へ出すだけ）。`_sed_skip_bracket_expression`
        # の追加によりブラケット式の内側を読み飛ばして解消した（詳細:
        # docs/reports/KLK-015/implementation.md）。テストを緩めて
        # allow の期待値を deny へ変えないこと。
        self.assertAllow("sed -n '/[/]/p' tickets/active/APP-001.md")
        self.assertAllow("sed -n '/[^/]/p' tickets/active/APP-001.md")
        self.assertAllow("sed 's/[/]/X/' tickets/active/APP-001.md")

    def test_sed_bracket_expression_does_not_hide_real_write_deny(self):
        # ブラケット式対応（上記テスト）が新たなバイパス経路を生まないことの
        # 固定点。ブラケット式を読み飛ばして正しくアドレス正規表現
        # `/[/]/`（＝末尾のブラケットの外側にある `/` が閉じデリミタ）を
        # 確定した後に続く `w tickets/active/APP-001.md` は実機 GNU sed 4.9
        # で実際にファイル書き出しを行う（`/tmp`配下で実行確認済み）。
        # ブラケット式の内側だけを読み飛ばすべきところを誤って外側の実在の
        # `w` コマンドまで読み飛ばしてしまうと、この形が誤って allow に
        # 倒れてしまう。
        self.assertDeny("sed -n '/[/]/w tickets/active/APP-001.md' in.md")
        # s の**パターンフィールド**の内側にリテラルとして
        # `w tickets/active/APP-001.md` という文字列が現れても（実際は
        # 正規表現の一部であり `w` コマンドではない。区切り文字を `#` に
        # することでパス中の `/` と衝突させず検証。実機 GNU sed 4.9で
        # 書き込みが発生しないことを確認済み）、置換フィールドにブラケット式
        # は無いためデリミタ探索は従来どおりであり、誤って allow になる
        # ことを固定する（対照）。
        self.assertAllow(
            "sed 's#[/]w tickets/active/APP-001.md#X#' unrelated.txt")

    # --- KLK-010: awk のプログラム内リダイレクト（D1） ---

    def test_awk_internal_redirect_deny(self):
        # T-AWK: whitelist 追加で新規の false negative を作らない
        self.assertDeny(
            "awk '{print > \"tickets/active/APP-001.md\"}' x.md")
        self.assertDeny("awk '{print > \"docs/SPEC.md\"}' x.md")

    # --- KLK-010: コマンド置換・プロセス置換の再帰評価（AC4） ---

    def test_command_substitution_deny(self):
        # T-B6a: $(...) とバッククォート
        self.assertDeny("ls $(rm tickets/active/APP-001.md)")
        self.assertDeny("ls `rm tickets/active/APP-001.md`")

    def test_nested_command_substitution_deny(self):
        # T-NEST: 深さ2の入れ子
        self.assertDeny("ls $(echo $(rm tickets/active/APP-001.md))")

    def test_process_substitution_deny(self):
        # T-PROC: プロセス置換
        self.assertDeny("cat <(rm tickets/active/APP-001.md)")

    def test_readonly_command_substitution_allow(self):
        # 置換の内側が読み取りだけなら誤denyしない
        self.assertAllow("ls $(cat tickets/active/APP-001.md)")

    # --- KLK-010 (tester追加): 置換再帰の上限境界（AC4・設計§3-4 item5） ---

    def test_deep_substitution_cutoff_denies_even_readonly(self):
        # 深さ上限(3)に到達すると、内側が読み取り専用でも「言及があればdeny」の
        # 保守側判定へ切り替わる（設計書§3-4「上限到達時は保守側で打ち切り」）。
        # ネスト4段（$(echo $(echo $(echo $(cat ...))))）で上限に到達することを固定する。
        self.assertDeny(
            "ls $(echo $(echo $(echo $(cat tickets/active/APP-001.md))))")

    def test_nested_substitution_within_cutoff_readonly_allow(self):
        # ネスト3段（上限未到達）では通常どおり再帰評価され、読み取りのみなら allow。
        self.assertAllow(
            "ls $(echo $(echo $(cat tickets/active/APP-001.md)))")

    def test_mixed_process_and_command_substitution_deny(self):
        # $(...) の内側にプロセス置換が入れ子になった場合も再帰評価される
        self.assertDeny("ls $(cat <(rm tickets/active/APP-001.md))")

    # --- KLK-010 (tester追加): ANSI-Cクォート $'...' は保守側に倒れる（設計書 R4） ---

    def test_ansi_c_quoted_path_with_write_head_deny(self):
        # $'...' は shlex が bash と同一には解釈しないが、書き込み系headの判定
        # (head not in ALLOWED_HEADS) は変わらず deny される
        self.assertDeny("rm $'tickets/active/APP-001.md'")

    # --- KLK-010 (tester追加): 未クォートの#はコメントとして特別扱いしない（設計書§3-5） ---

    def test_unquoted_comment_with_write_after_semicolon_deny(self):
        # bashでは `#` 以降は行末までコメントとして無視されるが、本hookは
        # クォート外の `#` を特別扱いしないため、コメント中の `;` を実際の
        # ステートメント区切りとして処理し、コメント内の書き込みコマンドを
        # 保守的にdenyする（設計書§3-5で明示的に許容された副作用）
        self.assertDeny("echo hi # ; rm tickets/active/APP-001.md")

    # --- KLK-010 (tester追加): git の他の非許可サブコマンド（AC6回帰・checkout以外） ---

    def test_git_rm_ticket_deny(self):
        self.assertDeny("git rm tickets/active/APP-001.md")

    def test_git_restore_ticket_deny(self):
        self.assertDeny("git restore tickets/active/APP-001.md")

    # --- KLK-010 (tester追加): printf は意図的に ALLOWED_HEADS 未追加（README注記と対） ---

    def test_printf_not_whitelisted_deny(self):
        # §4-1: printf はREADMEのローカル動作確認の注記と対であるため意図的に
        # ALLOWED_HEADS へ追加しない。将来誤って追加されないことを固定する。
        self.assertDeny("printf '%s' tickets/active/APP-001.md")

    # --- KLK-010 Phase 4: 置換の「外側」方向（C1・設計書§3-2 P1） ---

    def test_substitution_result_as_argument_deny(self):
        # T-C1a: 置換で包んだだけで言及ゲートを外せてはならない
        self.assertDeny("rm $(echo docs/SPEC.md)")
        self.assertDeny("rm `echo docs/SPEC.md`")

    def test_substitution_result_as_sed_target_deny(self):
        # T-C1b: 置換 × sed -i
        self.assertDeny("sed -i 's/a/b/' $(echo tickets/active/APP-001.md)")

    def test_substitution_result_as_write_target_deny(self):
        # T-C1c: 置換 × 書き込み系 head
        self.assertDeny("cp /tmp/e $(echo docs/SPEC.md)")
        self.assertDeny("truncate -s 0 $(echo docs/SPEC.md)")

    def test_substitution_result_in_pipe_segment_deny(self):
        # T-C1d: 置換 × パイプ区間（tee）
        self.assertDeny("cat a | tee $(echo docs/SPEC.md)")

    def test_redirect_target_from_substitution_deny(self):
        # T-C1e: リダイレクト先が置換の結果（パイプ区間の検査から外れる経路）
        self.assertDeny("echo x > $(echo docs/SPEC.md)")
        self.assertDeny('echo x > "$(echo docs/SPEC.md)"')
        self.assertDeny("echo x > `echo docs/SPEC.md`")

    def test_substitution_of_readonly_command_result_deny(self):
        # T-C1f: 置換の内側が読み取りでも、結果が書き込み系 head の引数なら deny
        self.assertDeny("rm $(basename docs/SPEC.md)")
        self.assertDeny("rm $(ls tickets/active/APP-001.md)")

    def test_substitution_attribution_is_scoped_allow(self):
        # T-C1g: プレースホルダに帰属（インデックス）があるため、置換の言及が
        # 無関係な後続ステートメントを巻き添えにしない
        self.assertAllow("ls $(cat tickets/active/APP-001.md); rm /tmp/junk")

    def test_substitution_assigned_to_variable_redirect_deny(self):
        # T-C1h: 置換 × 変数追跡（代入値もプレースホルダを解決する）
        self.assertDeny('f=$(echo docs/SPEC.md); cat x > "$f"')

    # --- KLK-010 Phase 4: degraded mode の分割復元（C2・設計書§3-5 P2） ---

    def test_degraded_statement_split_deny(self):
        # T-C2a: 先頭が読み取りでも、後続ステートメントの書き込みを見逃さない
        self.assertDeny("ls ; rm docs/SPEC.md #'")

    def test_degraded_natural_english_comment_deny(self):
        # T-C2b: degraded は `#'` に限らず日常的な英文コメントでも発火する
        self.assertDeny("cat README.md ; rm docs/SPEC.md # it's stale")

    def test_degraded_statement_split_with_sed_deny(self):
        # T-C2c: degraded × sed -i
        self.assertDeny("cat x; sed -i 's/a/b/' tickets/active/APP-001.md #'")

    def test_degraded_and_operator_split_deny(self):
        # T-C2d: `&&` 区切り
        self.assertDeny("cat x && tee tickets/active/APP-001.md #'")

    def test_degraded_leading_cd_and_copy_deny(self):
        # T-C2e: 先頭が cd / ls でも後続の書き込みを検出する
        self.assertDeny("cd .; rm docs/SPEC.md #'")
        self.assertDeny("ls x; cp /tmp/e docs/SPEC.md #'")

    def test_degraded_pipe_split_deny(self):
        # T-C2f: パイプ分割（xargs へのパイプ越しの書き込み連鎖）
        self.assertDeny("find tickets/active -name '*.md' | xargs rm #'")

    def test_degraded_trailing_escape_deny(self):
        # T-C2g: 末尾の孤立エスケープも degraded の発火条件（shlex の ValueError）
        self.assertDeny("rm tickets/active/APP-001.md \\")

    def test_degraded_read_with_english_comment_allow(self):
        # T-C2h: degraded の誤denyを拡大しない（読み取りは allow のまま）
        self.assertAllow("cat tickets/active/APP-001.md # don't")

    # --- KLK-010 Phase 4: awk の変数束縛とプログラム内出力（H1・設計書§3-6 D1） ---

    def test_awk_positional_assignment_write_deny(self):
        # T-H1a: 位置引数の NAME=VALUE 束縛
        self.assertDeny("awk '{print > f}' f=docs/SPEC.md in.txt")

    def test_awk_v_assignment_write_deny(self):
        # T-H1b: -v NAME=VALUE 束縛
        self.assertDeny("awk -v f=docs/SPEC.md '{print > f}' in.txt")

    def test_awk_assignment_to_ticket_deny(self):
        # T-H1c: tickets 宛て
        self.assertDeny("awk '{print > f}' f=tickets/active/APP-001.md in.txt")

    def test_awk_external_program_with_assignment_deny(self):
        # T-H1d: プログラムが外部ファイルで見えない形でも束縛を証拠に deny
        self.assertDeny("awk -f prog.awk f=docs/SPEC.md in.txt")

    def test_awk_output_redirect_without_binding_deny(self):
        # T-H1e: 束縛を伴わない print > FILENAME 形
        self.assertDeny("awk '{print > FILENAME}' tickets/active/APP-001.md")

    def test_awk_readonly_programs_allow(self):
        # T-H1f: 読み取り awk を誤denyしない（AW-2/AW-3 の誤爆防止）
        self.assertAllow("awk -F'|' '{print $1}' tickets/active/APP-001.md")
        self.assertAllow("awk 'NR>1 {print}' tickets/active/APP-001.md")
        self.assertAllow(
            "awk '{if ($1 > 2) print $1}' tickets/active/APP-001.md")
        self.assertAllow(
            'awk \'{printf "%s|%s\\n", $1, $2}\' tickets/active/APP-001.md')
        self.assertAllow("awk -v OFS=, '{print $1,$2}' "
                         "tickets/active/APP-001.md")

    # --- KLK-010 Phase 4: cd による作業ディレクトリ追跡（M1・設計書§3-8） ---

    def test_cd_into_tickets_then_relative_write_deny(self):
        # T-M1a: cd 後の相対パス書き込み（cd 自体は allow のまま）
        self.assertDeny("cd tickets/active && rm APP-001.md")

    def test_cd_tracking_released_allow(self):
        # T-M1b: 保護対象外へ戻れば追跡は解除。追跡不能なら誤denyしない
        self.assertAllow("cd tickets/active && cd ../.. && rm foo.md")
        self.assertAllow('cd "$D" && rm APP-001.md')

    def test_cd_into_tickets_then_relative_redirect_deny(self):
        # T-M1c: cd 後の相対パスへのリダイレクト（head が echo でも書き込み）。
        # 旧版は `cd` がホワイトリスト不在だったため偶然 deny していた経路
        self.assertDeny("cd tickets/done && echo x > APP-001.md")
        self.assertDeny("cd tickets/active && cat draft.md >> APP-001.md")
        self.assertDeny("cd tickets/active && echo x > APP-001.md #'")

    def test_cd_into_tickets_then_redirect_outside_allow(self):
        # T-M1d: cwd 配下から外れる先（絶対パス・上位への相対）は誤denyしない
        self.assertAllow("cd tickets/active && cat APP-001.md > /tmp/x.md")
        self.assertAllow("cd tickets/active && cat APP-001.md > ../../out.txt")
        self.assertAllow('cd tickets/active && cat APP-001.md > "$TMP"')

    # --- KLK-010 Phase 4: サブシェルのグループ化（M4-5） ---

    def test_spaced_subshell_write_deny(self):
        # T-M45: `( ` が独立語になる形でも先頭コマンドを見失わない
        self.assertDeny("( rm tickets/active/APP-001.md )")

    def test_spaced_subshell_read_allow(self):
        # T-M45b: 読み取りは allow のまま
        self.assertAllow("( cat tickets/active/APP-001.md )")

    # --- KLK-010 (tester再検証・reviewer差し戻し後): next_cwd() の operand
    # 抽出が head_of() の柔軟な先頭コマンド検出に追随していない未閉塞サブ経路
    # （M1・新規発見） ---
    #
    # next_cwd() は `words[1:]`（＝「先頭語の次から」）を cd のオペランド列とみなす。
    # 一方 head_of() は FOO=bar 形式の環境変数代入前置きを読み飛ばして cd を
    # 見つける（M4-5 と同種の柔軟な先頭コマンド検出）。この2関数の前提が
    # 食い違うため、cd の前に代入前置きがあると next_cwd() の operand 抽出が
    # "cd" という語自身を誤って operand と誤認し（"tickets/active" ではなく）、
    # cwd 追跡が全く働かなくなる。旧版は cd が ALLOWED_HEADS に無く cd 自体が
    # 常に deny されていたため顕在化しなかった＝本チケットの M1 修正
    # （next_cwd の追加）が新設した false negative。

    def test_cd_after_env_assignment_prefix_relative_write_deny(self):
        self.assertDeny("X=1 cd tickets/active && rm APP-001.md")
        self.assertDeny("X=1 cd tickets/done && echo x > APP-001.md")
        self.assertDeny("X=1 Y=2 cd tickets/active && rm APP-001.md")

    def test_git_subcommand_after_env_assignment_prefix_allow(self):
        # 同根因の裏面（誤deny方向）: segment_violation() の git サブコマンド
        # 抽出（`next(t for t in words[1:] if not t.startswith("-"))`）も
        # 同じ「words[1:] = 先頭語の次から」という前提に依存している。
        # 環境変数代入前置きがあると "git" という語自身を誤ってサブコマンドと
        # みなし、ALLOWED_GIT_SUBCOMMANDS に無いため正規の `git add` まで
        # 誤denyする（AC2 の趣旨に反する新規の誤deny）。
        self.assertAllow("X=1 git add tickets/active/APP-001.md")

    def test_multiple_env_assignment_prefixes_before_allowed_git_allow(self):
        # head_index() への一元化がオフセットの想定回数を1つに限定していないか
        # の確認。GIT_PAGER=cat のような実運用でよく使う代入や、複数代入の
        # 積み重ねでも ALLOWED_GIT_SUBCOMMANDS のサブコマンドが誤denyされない
        self.assertAllow("GIT_PAGER=cat git status tickets/active/APP-001.md")
        self.assertAllow("X=1 Y=2 git add tickets/active/APP-001.md")
        self.assertAllow("X=1 git commit tickets/active/APP-001.md")
        self.assertAllow("X=1 git log tickets/active/APP-001.md")
        self.assertAllow("X=1 git show tickets/active/APP-001.md")
        self.assertAllow("X=1 git blame tickets/active/APP-001.md")

    def test_git_disallowed_subcommands_after_env_assignment_prefix_deny(self):
        # 同根因の修正が「代入前置き付きなら何でも通す」方向へ緩みすぎていないか
        # の確認（test_git_subcommand_after_env_assignment_prefix_allow の裏側）。
        # ALLOWED_GIT_SUBCOMMANDS に無いサブコマンドは代入前置きがあっても
        # 引き続き deny されること
        self.assertDeny("X=1 git checkout tickets/active/APP-001.md")
        self.assertDeny("X=1 git rm tickets/active/APP-001.md")
        self.assertDeny("X=1 git restore tickets/active/APP-001.md")
        self.assertDeny("GIT_DIR=x git clean -f tickets/active")
        self.assertDeny("X=1 git push tickets/active/APP-001.md")
        self.assertDeny("X=1 git reset tickets/active/APP-001.md")

    def test_spaced_subshell_cd_relative_write_deny(self):
        # M4-5（サブシェルの `(` 単独語スキップ）と M1（cd の cwd 追跡）の
        # 組み合わせで生じる副次的な穴（implementer 報告・修正の副産物として
        # 閉じたことを固定する）。`(` の直後に空白があるため `(` が独立語になり、
        # 代入前置きの有無にかかわらず cd の cwd 追跡が正しく機能する必要がある
        self.assertDeny("( cd tickets/active && rm APP-001.md )")
        self.assertDeny("X=1 ( cd tickets/active && rm APP-001.md )")
        self.assertDeny("( X=1 cd tickets/active && rm APP-001.md )")

    # --- KLK-010 Phase 6: awk のオプション次元（C3・設計書§3-6 D1 AW-4） ---
    #
    # gawk の `-i inplace`（in-place 拡張）は `>` も `|` も変数束縛も使わずに
    # ファイルを書き換える＝受け入れ条件が名指しする `sed -i` の awk 版。
    # 同じ次元に外部コード読み込み（-f/-i/-l/-E/-D）とファイル書き出し
    # （-o/-p/-d）が並ぶため、規則はブラックリストではなく
    # **既知の読み取り専用オプションのホワイトリスト**（未知は deny）とする。

    def test_awk_inplace_extension_deny(self):
        # T-C3a: gawk の in-place 拡張（tickets / SPEC.md の双方）
        self.assertDeny(
            "awk -i inplace '{gsub(/a/,\"b\")}1' tickets/active/APP-001.md")
        self.assertDeny("awk -i inplace '{gsub(/a/,\"b\")}1' docs/SPEC.md")

    def test_awk_inplace_extension_all_spellings_deny(self):
        # T-C3b: 結合形・長形式・長形式=VALUE
        self.assertDeny("awk -iinplace '{print}' tickets/active/APP-001.md")
        self.assertDeny(
            "awk --include inplace '{print}' tickets/active/APP-001.md")
        self.assertDeny(
            "awk --include=inplace '{print}' tickets/active/APP-001.md")

    def test_awk_inplace_extension_degraded_deny(self):
        # T-C3c: degraded mode（空白分割でも -i は独立語として残る）
        self.assertDeny(
            "awk -i inplace '{print}' tickets/active/APP-001.md #'")

    def test_awk_external_code_loading_options_deny(self):
        # T-C3d: 外部コード読み込み次元（プログラム本体・ライブラリ・拡張）。
        # -f は束縛が無くても deny になる（旧版は awk 自体が非ホワイトリスト
        # だったため deny だった＝ホワイトリスト追加で開いた穴）
        self.assertDeny("awk -f prog.awk tickets/active/APP-001.md")
        self.assertDeny("awk -E prog.awk tickets/active/APP-001.md")
        self.assertDeny("awk -l lib '{print}' tickets/active/APP-001.md")
        self.assertDeny("awk -D tickets/active/APP-001.md")

    def test_awk_file_writing_options_deny(self):
        # T-C3e: ファイル書き出し次元（--pretty-print / --profile /
        # --dump-variables の短形式）
        self.assertDeny("awk -o prof.out '{print}' tickets/active/APP-001.md")
        self.assertDeny("awk -d '{print}' tickets/active/APP-001.md")
        self.assertDeny("awk -p '{print}' tickets/active/APP-001.md")

    # --- KLK-010 Phase 6: awk の外部コマンド実行次元（C4・AW-5） ---

    def test_awk_system_call_deny(self):
        # T-C4a: system() は > も | も含まないため AW-1 に掛からない
        self.assertDeny(
            "awk 'BEGIN{system(\"rm tickets/active/APP-001.md\")}'")
        self.assertDeny(
            "awk '{system(\"rm tickets/active/APP-001.md\")}' /dev/null")
        self.assertDeny(
            "awk 'END{system(\"rm tickets/active/APP-001.md\")}' /dev/null")

    def test_awk_system_call_other_commands_deny(self):
        # T-C4b: rm 以外の外部コマンド・文字列連結でも deny
        self.assertDeny("awk 'BEGIN{system(\"cp /tmp/e docs/SPEC.md\")}'")
        self.assertDeny("awk 'BEGIN{system(\"truncate -s 0 docs/SPEC.md\")}'")
        self.assertDeny("awk 'BEGIN{system(\"rm \" \"docs/SPEC.md\")}'")

    def test_awk_system_call_degraded_deny(self):
        # T-C4c: degraded mode（空白分割でも先頭語に system( が残る）
        self.assertDeny("awk 'BEGIN{system(\"rm docs/SPEC.md\")}' #'")

    def test_awk_load_directive_deny(self):
        # T-C4d: gawk の @load / @include（拡張・ライブラリ読み込み指令）
        self.assertDeny(
            "awk '@load \"inplace\"; {print}' tickets/active/APP-001.md")

    # --- tester (Phase 6・7 再検証): AW-5 の未閉塞バイパス ---
    #
    # gawk は 4.1.2 以降「間接関数呼び出し」`@varname(...)` をサポートし、
    # 変数に格納した文字列名の関数（組み込みの system() を含む）をその場で
    # 呼び出せる（本ホストの GNU Awk 5.2.1 で実測確認済み。scratchpad で
    # `awk 'BEGIN{f="system"; @f("echo x > out.txt")}'` が実際に out.txt を
    # 作成することを確認した）。AWK_EXEC_RE は `\bsystem\s*\(` と
    # `@(?:load|include)\b` のみを見るため、"system" という文字列が変数へ
    # 代入され `@f(...)` 経由で間接呼び出しされる形は両方の分岐に一致せず、
    # AW-1（`>`/`|` を含む語）・AW-2（変数束縛の値）・AW-4（フラグ）・AW-3
    # （print/printf 構文）のいずれにも掛からない。degraded 版は
    # `f="system";` の `;` が LEGACY_STATEMENT_RE でステートメント分割され
    # 偶然 deny になるが、正常経路（字句解析に成功する通常の呼び出し）は
    # 素通りする。旧版は awk を ALLOWED_HEADS に持たず全 awk を deny して
    # いたため old=deny → new=allow の回帰であり、AC6 が名指しする C4
    # （awk の system() による任意コマンド実行）そのものである。
    def test_awk_indirect_system_call_deny(self):
        self.assertDeny(
            "awk 'BEGIN{f=\"system\"; "
            "@f(\"rm tickets/active/APP-001.md\")}'")
        self.assertDeny(
            "awk 'BEGIN{f=\"system\"; @f(\"rm docs/SPEC.md\")}'")
        self.assertDeny(
            "awk -v f=system 'BEGIN{@f(\"rm tickets/active/APP-001.md\")}'")

    def test_awk_indirect_system_call_cwd_guarded_deny(self):
        # 保護対象 cwd 下では書き込み先の相対パスさえコマンド文字列に
        # 現れない（`cd tickets/active` の後、引数は "APP-001.md" のみ）。
        self.assertDeny(
            "cd tickets/active && "
            "awk 'BEGIN{f=\"system\"; @f(\"rm APP-001.md\")}'")

    # --- KLK-010 AW-6: 間接関数呼び出しの回避形（implementer 追加） ---
    #
    # AW-6 は `@\s*IDENT\s*\(` という**構文の存在**を証拠にする（値は追跡
    # しない＝AW-2／AW-3 と同じ設計思想）。本ホストの GNU Awk 5.2.1 で実際に
    # 間接呼び出しが成立するのは `@f(` と `@ f(`（`@` の直後の空白／タブのみ
    # 許容）であり、`@f (`（識別子と `(` の間の空白）・`@"system"(`・
    # `@(f g)(`（連結）・`@a[1](`・`@ENVIRON["X"](` はいずれも構文エラーに
    # なることを実測で確認した。正規表現は成立形より広く取っている（保守側）。
    def test_awk_indirect_call_evasion_forms_deny(self):
        # `@` の直後の空白・タブ（どちらも gawk で実際に system() が走る）
        self.assertDeny(
            "awk 'BEGIN{f=\"system\"; @ f(\"rm docs/SPEC.md\")}'")
        self.assertDeny(
            "awk 'BEGIN{f=\"system\"; @\tf(\"rm docs/SPEC.md\")}'")
        # 変数名は任意（`f` 決め打ちの検出になっていないこと）
        self.assertDeny(
            "awk 'BEGIN{_x9=\"system\"; @_x9(\"rm docs/SPEC.md\")}'")
        # プログラムを -e / --source で与える形（オプションが安全でも同じ語に
        # AW-5／AW-6 を当てるため素通りしない）
        self.assertDeny(
            "awk -e'BEGIN{f=\"system\"; @f(\"rm docs/SPEC.md\")}'")
        self.assertDeny(
            "awk --source='BEGIN{f=\"system\"; @f(\"rm docs/SPEC.md\")}'")
        self.assertDeny(
            "awk -e 'BEGIN{f=\"system\"; @f(\"rm docs/SPEC.md\")}'")
        # degraded mode（字句解析できない入力）でも同じ規則が効く
        self.assertDeny(
            "awk 'BEGIN{f=\"system\"; @f(\"rm docs/SPEC.md\")}' #'")
        # 保護対象 cwd 下（保護対象パスがリテラルに現れない）
        self.assertDeny("cd tickets/done && "
                        "awk 'BEGIN{f=\"system\"; "
                        "@f(\"truncate -s 0 APP-001.md\")}'")
        self.assertDeny("cd tickets/active; "
                        "awk 'BEGIN{f=\"system\"; @f(\"rm APP-001.md\")}' #'")

    def test_awk_exec_syntax_split_across_words_deny(self):
        # degraded mode は空白分割のため `@ f(` が `@` と `f(` に、`system (` が
        # `system` と `(` に割れて語単位では一致しない。プログラム内に `;` が
        # 無ければステートメント分割にも掛からないため（束縛は `-v` で外から
        # 与える）、外部コマンド実行の検出（AW-5・AW-6）は空白結合した
        # テキストへも当てる。gawk は `@` の直後と関数名の直後の空白を
        # どちらも受け付けるため、これらの形は実際に system() を実行する
        self.assertDeny("awk -v f=system "
                        "'BEGIN{@ f(\"rm tickets/active/APP-001.md\")}' #'")
        self.assertDeny(
            "awk -v f=system 'BEGIN{@ f(\"rm docs/SPEC.md\")}' #'")
        self.assertDeny("awk 'BEGIN{system (\"rm docs/SPEC.md\")}' #'")
        self.assertDeny("cd tickets/active; awk -v f=system "
                        "'BEGIN{@ f(\"rm APP-001.md\")}' #'")

    def test_awk_at_sign_without_indirect_call_allow(self):
        # AW-6 が `@` を含むだけの読み取り awk を巻き添えにしないことを固定する。
        # 一致には「`@` + 識別子 + `(`」の3点が揃う必要がある
        self.assertAllow(
            "awk '/user@example.com/ {print}' tickets/active/APP-001.md")
        self.assertAllow(
            "awk '/@(id|title)/ {print}' tickets/active/APP-001.md")
        self.assertAllow(
            "awk -v m=a@b.example '$1==m {print}' tickets/active/APP-001.md")
        # 空白結合したテキストへの当て込みが語をまたいだ偶然の一致を
        # 生まないこと（`@` の後がパス区切り・`$` なら一致しない）
        self.assertAllow(
            "awk '/@/ {print}' 'report (1).md' tickets/active/APP-001.md")
        self.assertAllow(
            "awk -v s=@ '$1==s {print}' tickets/active/APP-001.md")
        self.assertAllow("awk '{print $1}' tickets/active/APP-001.md #'")
        self.assertAllow(
            "awk 'function p(x){print x} {p($1)}' tickets/active/APP-001.md")
        self.assertAllow('awk \'BEGIN{PROCINFO["sorted_in"]="cmp"} {print}\' '
                         "tickets/active/APP-001.md")

    # --- KLK-010 tester(AW-6再検証)差し戻し: system() 以外の外部コマンド
    # 実行経路（`"cmd" | getline` / `|& getline` 系）が AW-1/AW-3/AW-5/AW-6
    # のいずれにも掛からず素通りする（Quality Gate fail・未閉塞）。
    #
    # AW-3（AWK_OUTPUT_RE）は `print`/`printf` の直後に `>`/`>>`/`|` が
    # 現れる形しか見ておらず、`"cmd" | getline` のように **`print`/`printf`
    # を伴わない入力パイプ**（コマンドの標準出力を読み取る形。gawk はこの際
    # 実際に `cmd` を子プロセスとして起動する）には一致しない。AW-1 は
    # 「保護対象に言及する語」自身が `>`/`|` を含む場合のみ発火するため、
    # 保護対象 cwd 配下でリテラルパスがコマンド文字列に現れない形（相対
    # ファイル名のみ）では mentions_guarded も語単位の証拠も立たない。
    # 本ホスト（GNU Awk 5.2.1）で `"rm ..." | getline` および `|& getline`
    # が実際に外部コマンドを実行し対象ファイルを削除することを scratchpad の
    # 使い捨てディレクトリで実証済み（tester 実測）。旧版は awk を
    # ALLOWED_HEADS に持たず全 awk を deny していたため old=deny → new=allow
    # の回帰であり、AC6 が名指しする「C4 相当（awk の外部コマンド実行）」の
    # 未対応形。残存リスク4（「system()／"cmd" | getline／print | "cmd"／
    # |&／@f()／@load は列挙であり網羅証明ではない」）が的中した具体例。
    def test_awk_input_pipe_getline_bypasses_all_aw_rules_deny(self):
        self.assertDeny(
            "cd tickets/active && awk 'BEGIN{\"rm APP-001.md\" | getline x}'")
        self.assertDeny(
            "cd tickets/done && "
            "awk 'BEGIN{\"truncate -s 0 APP-001.md\" | getline x}'")

    def test_awk_coprocess_getline_bypasses_all_aw_rules_deny(self):
        # gawk 拡張の双方向コプロセス `|&` も同型（`getline` 側で外部コマンド
        # を起動する。`print ... |& "cmd"` は AW-3 が捕捉するが、読み取り方向
        # （`"cmd" |& getline`）は捕捉しない）
        self.assertDeny(
            "cd tickets/active && "
            "awk 'BEGIN{\"rm APP-001.md\" |& getline x}'")

    # --- KLK-010 tester(AW-6再検証)差し戻し: 過剰一致（誤deny）の新規発見 ---
    #
    # AW-5／AW-6 は「文字列リテラル除去**前**」の語で判定するため（保守側の
    # 意図的な設計）、awk プログラム内の**文字列リテラルの中身**に
    # `system(`／`@ident(` に見える部分文字列が現れるだけで deny になる。
    # 既存 T-AW6C（test_awk_at_sign_without_indirect_call_allow）は正規表現
    # 内の `@(id|title)` や `-v` 値の `a@b.example` は固定しているが、
    # 「メールアドレス様の文字列の直後に半角スペース+丸括弧が続く」形
    # （日常的な注記文でありうる）は未カバーだった。
    def test_awk_string_literal_at_paren_false_positive_allow(self):
        # AW-6 の正規表現はリテラル除去前の生テキストに当たるため、
        # 出力する文字列の中に「a@b (...)」という文面があるだけで
        # `@\s*IDENT\s*\(` に一致し、間接呼び出しと誤認される
        self.assertAllow(
            'awk \'BEGIN{print "contact: a@b (see docs)"}\' '
            "tickets/active/APP-001.md")

    def test_awk_filename_operand_matching_system_call_pattern_allow(self):
        # AW-5 は awk への**全引数**（プログラム文字列だけでなくファイル名
        # オペランドも含む）を語単位で走査するため、awk のプログラムとは
        # 無関係な「ファイル名」引数が `system(` に見える部分文字列を含む
        # だけで deny になる（結合テキスト評価とは無関係の単一語レベルの
        # 過剰一致。C4/AW-5 導入時点から存在）
        self.assertAllow(
            "awk '{print}' 'system(1).md' tickets/active/APP-001.md")

    def test_awk_safe_options_allow(self):
        # T-AWKOK: AW-4／AW-5 が読み取り awk を誤denyしないことを固定する。
        # ホワイトリストの収載漏れは可視な誤denyとして現れるため、代表形を
        # ここで固定しておく
        self.assertAllow("awk --posix '{print $1}' tickets/active/APP-001.md")
        self.assertAllow("awk -- '{print}' tickets/active/APP-001.md")
        self.assertAllow("awk -v n=3 '{print $n}' tickets/active/APP-001.md")
        self.assertAllow("awk --field-separator='|' '{print $1}' "
                         "tickets/active/APP-001.md")
        self.assertAllow(
            "awk 'BEGIN{OFS=\"|\"} {print $1}' tickets/active/APP-001.md")

    # --- KLK-010 Phase 6: 保護対象 cwd の相対パス書き込み（H2・設計書§3-8） ---
    #
    # 旧版は cd を ALLOWED_HEADS に持たなかったため、cd を含むコマンドは
    # 後続に何が来ても deny されていた。cd を無条件許可にした結果、保護対象を
    # 作業ディレクトリとする相対パス書き込みが新たに素通りするようになった。
    # 書き込み先オペランドを取り出せる形（sort -o / uniq 第2引数 /
    # リダイレクト）は cwd と結合して判定し、取り出せない形（awk の
    # print > "REL" / sed の w REL）は構文の存在そのものを証拠とする。

    def test_cwd_guarded_awk_internal_redirect_deny(self):
        # T-H2a: awk 4形（リテラル・追記・-v 束縛・位置引数束縛）
        self.assertDeny(
            "cd tickets/active && awk '{print > \"APP-001.md\"}' in.txt")
        self.assertDeny("cd tickets/active && "
                        "awk '{printf \"x\" >> \"APP-001.md\"}' in.txt")
        self.assertDeny("cd tickets/active && "
                        "awk -v f=APP-001.md '{print > f}' in.txt")
        self.assertDeny("cd tickets/active && "
                        "awk '{print > f}' f=APP-001.md in.txt")

    def test_cwd_guarded_sed_write_command_deny(self):
        # T-H2b: sed の w コマンド（正常経路と degraded の2形）。
        # degraded は空白分割で `w FILE` が2語に割れるため、保護対象 cwd 下では
        # 空白結合したテキストも併せて評価する
        self.assertDeny("cd tickets/active && sed 's/a/b/w APP-001.md' in.md")
        self.assertDeny("cd tickets/active; sed 's/a/b/w APP-001.md' in.md #'")

    def test_cwd_guarded_sed_address_and_delimiter_write_deny(self):
        # T-SED7c（KLK-015・INV-SED-16・20の固定点）: cwd 相対 × アドレス
        # 前置き／区切り文字任意性の組み合わせも取りこぼさないこと
        self.assertDeny("cd tickets/active && sed -n '1w APP-001.md' in.md")
        self.assertDeny(
            "cd tickets/active && sed -n '1s#a#XYZ#w APP-001.md' in.md")

    def test_cwd_guarded_sort_and_uniq_output_deny(self):
        # T-H2c: sort -o / uniq 第2位置引数（cwd 相対形）
        self.assertDeny("cd tickets/active && sort -o APP-001.md in.md")
        self.assertDeny("cd tickets/active && uniq in.md APP-001.md")

    def test_cwd_guarded_substitution_inner_write_deny(self):
        # T-H2d: 置換の内側方向へ cwd が伝播すること（$(...)・バッククォート・
        # プロセス置換の3形）
        self.assertDeny("cd tickets/active && ls $(rm APP-001.md)")
        self.assertDeny("cd tickets/active && ls `rm APP-001.md`")
        self.assertDeny("cd tickets/active && cat <(rm APP-001.md)")

    def test_sort_and_uniq_output_absolute_path_deny(self):
        # T-H2e: cwd 相対だけ deny・絶対パスは allow という非対称を残さない
        self.assertDeny("sort -o tickets/active/APP-001.md in.md")
        self.assertDeny("sort --output=docs/SPEC.md x.md")
        self.assertDeny("sort -otickets/active/APP-001.md in.md")
        self.assertDeny("uniq in.md tickets/active/APP-001.md")

    def test_cwd_guarded_read_commands_allow(self):
        # T-H2f: 保護対象 cwd 下の読み取りを新たに誤denyしないことを固定する
        # （本改訂で最も重要な allow 固定。head レベルの一律 deny 案を却下した
        # 根拠であり、日常の読み取り操作がここに集まる）
        self.assertAllow("cd tickets/active && awk '{print $1}' APP-001.md")
        self.assertAllow(
            "cd tickets/active && awk -F'|' '{print $1}' APP-001.md")
        self.assertAllow("cd tickets/active && sed -n '1,5p' APP-001.md")
        self.assertAllow("cd tickets/active && sort APP-001.md")
        self.assertAllow("cd tickets/active && uniq APP-001.md")
        self.assertAllow("cd tickets/active && uniq -f 2 APP-001.md")
        self.assertAllow("sort -o /tmp/out tickets/active/APP-001.md")

    def test_find_fprint0_flag_deny(self):
        # T-FIND0: FIND_WRITE_FLAGS の列挙漏れ（-fprint0）。フラグ名で判定する
        # ためパスに依存しない
        self.assertDeny("find tickets/active -name '*.md' -fprint0 /tmp/x")

    # --- KLK-010 Phase 8: awk のプログラム内構文のホワイトリスト化
    # （AW-7・設計書 §3-6 D1／D8・§4-4(d)） ---
    #
    # プログラム内構文の次元は規則を積み増すブラックリストで4ラウンド連続して
    # 穴が出た（print > file → system() → @f() → "cmd" | getline）。第4版は
    # この次元を反転し、awk が**実際に実行するテキスト**（-e/--source の値と、
    # 無ければ位置引数の先頭オペランド）だけを取り出して
    #   (1) リテラル（文字列・正規表現）を左→右の1パスで除去
    #   (2) 許可文字集合（`@` と `|` を含まない）
    #   (3) 呼び出し名の許可集合（system を含まない・未知名は deny）
    #   (4) print/printf の後に > >> | が現れる出力構文の不在
    # の3条件を満たす形だけを許可する。未知の文字・未知の関数名は自動的に
    # deny 側へ落ちる（この次元の機械的既定）。

    def test_awk_pipe_syntax_other_forms_deny(self):
        # T-AW7e: 入力パイプ（リテラルパス形）・while 内の入力パイプ・
        # コプロセス出力。いずれも gawk が実際に子プロセスを起動する
        # （使い捨てディレクトリで実測済み）
        self.assertDeny(
            "awk 'BEGIN{\"rm tickets/active/APP-001.md\" | getline}'")
        self.assertDeny("awk 'BEGIN{while((\"ls\" | getline l)>0) print l}' "
                        "tickets/active/APP-001.md")
        self.assertDeny(
            "awk 'BEGIN{print \"x\" |& \"cat\"}' tickets/active/APP-001.md")

    def test_awk_call_name_whitelist_deny(self):
        # T-AW7f: 呼び出し名のホワイトリスト。`system (`（組み込み名と `(` の
        # 間の空白。gawk は受け付ける＝実測）は正常経路でも捕捉され、
        # 未知の関数名は**未知＝deny の機械的既定**で落ちる
        self.assertDeny("awk 'BEGIN{system (\"rm docs/SPEC.md\")}'")
        self.assertDeny("awk 'BEGIN{xyzzy(\"rm docs/SPEC.md\")}'")

    def test_awk_namespace_directive_deny(self):
        # T-AW7g: 許可文字集合（`@`）の固定。@namespace は gawk 5 の名前空間
        # 指令であり、それ自体は書き込みを行わないが `@` を許可すると
        # @f( / @load / @include が同時に通るため deny 側に倒す（誤deny側・
        # 設計書 §6 R26 ① に列挙済み）
        self.assertDeny(
            "awk '@namespace \"util\"; {print $1}' tickets/active/APP-001.md")

    def test_awk_literal_stripping_soundness_deny(self):
        # T-AW7h: S1（リテラル除去が1パスであること）の健全性。2パス実装
        # （文字列を全部消してから正規表現を消す／その逆）だと、片方の
        # リテラルの内側に見える引用符・スラッシュが実際には外側にある
        # `system(` を飲み込み、いずれかが allow に転じる。実機 gawk で
        # 4形とも実際にファイルを削除することを確認済み
        self.assertDeny("awk '/\"/ {system(\"rm docs/SPEC.md\")}' in.txt")
        self.assertDeny("awk 'BEGIN{x=\"(/a\"; system(\"rm /docs/SPEC.md\")}'")
        self.assertDeny("awk 'BEGIN{x=1/2; system(\"rm docs/SPEC.md\")/3}'")
        self.assertDeny(
            "awk 'BEGIN{i=0; i++ /2; system(\"rm docs/SPEC.md\")/3}'")
        # 文字列リテラルの中身に `system(` があるだけでは実行されないが、
        # 同じプログラムの**リテラル外**に本物の呼び出しがあれば deny になる
        self.assertDeny(
            "awk 'BEGIN{print \"system(\" ; system(\"rm docs/SPEC.md\")}'")

    def test_awk_program_unsafe_characters_deny(self):
        # T-AW7i: 許可文字集合の固定。リテラル外のバックスラッシュ・
        # バッククォートは awk のプログラムとして正当な用途が無い
        self.assertDeny("awk 'BEGIN{t=1 \\ 2}' tickets/active/APP-001.md")
        self.assertDeny("awk 'BEGIN{x=`id`}' tickets/active/APP-001.md")
        # 未閉じの文字列リテラル（判定不能＝deny）
        self.assertDeny("awk 'BEGIN{print \"unterminated}' docs/SPEC.md")

    # --- KLK-010 tester（Phase 8・9 再検証）差し戻し: $'...'（ANSI-C クォート）
    # の hex エスケープ（\xHH）による AW-7 全面バイパス（Critical・実機実証） ---
    #
    # 根因: lex() は `$'...'` を素の `'...'` と同一に扱い、内容をそのまま
    # コピーする（エスケープを解釈しない）。一方 awk_strip_literals() は
    # 文字列リテラルの中で `\X`（バックスラッシュ+任意の1文字）を「1個の
    # エスケープ済み文字」とみなして無条件に読み飛ばす（awk 自身の
    # エスケープ規則の近似）。この2つの独立した「素朴な近似」が組み合わさると、
    # 実際の bash が `$'...'` を評価する際に `\x22` を実際の `"` へ、
    # `\x7c` を実際の `|` へデコードすることを考慮しないまま、
    # hook 側は「バックスラッシュ+次の1文字」をまとめて文字列内へ
    # 読み飛ばしてしまう。その結果、hook から見ると全体が1つの巨大な
    # 文字列リテラル（`""` へ丸ごと除去され安全）に見えるが、実際に bash が
    # `\x22` を `"` へ復号すると、**bash 側で文字列が途中で閉じ**、
    # `system(...)` や `"cmd" | getline` が**実際のプログラムでは文字列の
    # 外＝実行されるコード**になる。許可文字集合に無い `@`・`|` も、
    # 同じ理由でリテラル内に隠れているとみなされ検査対象から漏れる。
    #
    # 本ホスト（GNU Awk 5.2.1）の使い捨てディレクトリで実機検証済み:
    #   bash -c 'gawk $'"'"'BEGIN{x="foo\x22system(\x22rm F\x22)\x22"}'"'"''
    #   → 実際に F を削除する（EXIT 0）
    #   bash -c 'gawk $'"'"'BEGIN{x="foo\x22(\x22rm F\x22\x7cgetline x)\x22"}'"'"''
    #   → 実際に F を削除する（EXIT 0・C5 と同じ入力パイプ経路が再現する）
    # いずれも hook はコード変更なしで allow を返す（本テストが実証）。
    # docstring・設計書は「$'...' は shlex が bash と同一に解釈しないが
    # 語として1トークンに収まるため判定は保守側（deny 方向）へ倒れる」と
    # 記載しているが、本ケースにおいてその主張は成立しない
    # （allow 方向に倒れ、かつ実機で実行される）。
    def test_ansi_c_quoted_awk_program_system_call_bypasses_aw7_deny(self):
        self.assertDeny(
            "awk $'BEGIN{x=\"foo\\x22system(\\x22rm "
            "tickets/active/APP-001.md\\x22)\\x22\"}'")
        self.assertDeny(
            "cd tickets/active && "
            "awk $'BEGIN{x=\"foo\\x22system(\\x22rm "
            "APP-001.md\\x22)\\x22\"}'")
        self.assertDeny(
            "awk $'BEGIN{x=\"foo\\x22system(\\x22rm "
            "docs/SPEC.md\\x22)\\x22\"}'")

    def test_ansi_c_quoted_awk_program_pipe_getline_bypasses_aw7_deny(self):
        # C5（"cmd" | getline）が $'...' の hex エスケープ経由で再び開く形。
        # `\x7c` は許可文字集合に無い `|` へ復号されるが、hook 側からは
        # 依然として「文字列リテラルの中の1エスケープ文字」にしか見えない
        self.assertDeny(
            "awk $'BEGIN{x=\"foo\\x22(\\x22rm "
            "tickets/active/APP-001.md\\x22\\x7cgetline x)\\x22\"}'")
        self.assertDeny(
            "cd tickets/active && "
            "awk $'BEGIN{x=\"foo\\x22(\\x22rm "
            "APP-001.md\\x22\\x7cgetline x)\\x22\"}'")

    # --- KLK-010 Phase 10: QT-1／QT-2／QT-3（字句レイヤの ANSI-C デコード相違を
    # 閉じる）。設計書 §3-2・§3-4「判定不能なステートメント」・§3-6 D9・
    # §4-2〜§4-4(g)(h)・§4-5-4 ---
    #
    # QT-1: クォート**外**の `$'…'`／`$"…"` を含むステートメントは、hook が
    # 見ている字面と bash が実際にコマンドへ渡す文字列が一致しないことが確定
    # している。ホワイトリスト（AW-7）は「見えているテキストが安全か」しか
    # 確認できず、ブラックリスト（AW-5／AW-6・SED_WRITE_RE）は符号化された
    # 字面に一致しないため、どちらでも判定できない。したがって「判定不能」の
    # 印を字句レイヤで残し、証拠（言及ゲート／保護対象 cwd）が立った時点で
    # 無条件に deny する。

    def test_ansi_c_quoted_degraded_still_deny(self):
        # T-QT1c: C6 の5形の末尾に ` #'` を付けて未閉じクォート＝degraded へ
        # 落とした形。**degraded 側に QT-1 を置かないと ` #'` を1つ足すだけで
        # 全形が通る**（`\x7c` はコマンド文字列上に `|` として現れないため
        # degraded の statement.split("|") がパイプ分割せず、後段 head が
        # getline にならない。AW-1／AW-5／AW-6／AW-3 のいずれにも一致しない
        # ＝設計書 §3-6 D9 の11段トレース）。この規則を落とすと必ず失敗する
        for command in (
            "awk $'BEGIN{x=\"foo\\x22system(\\x22rm "
            "tickets/active/APP-001.md\\x22)\\x22\"}' #'",
            "cd tickets/active && awk $'BEGIN{x=\"foo\\x22system(\\x22rm "
            "APP-001.md\\x22)\\x22\"}' #'",
            "awk $'BEGIN{x=\"foo\\x22system(\\x22rm "
            "docs/SPEC.md\\x22)\\x22\"}' #'",
            "awk $'BEGIN{x=\"foo\\x22(\\x22rm "
            "tickets/active/APP-001.md\\x22\\x7cgetline x)\\x22\"}' #'",
            "cd tickets/active && awk $'BEGIN{x=\"foo\\x22(\\x22rm "
            "APP-001.md\\x22\\x7cgetline x)\\x22\"}' #'",
        ):
            with self.subTest(command=command):
                self.assertDeny(command)

    def test_ansi_c_quoted_sed_write_command_deny(self):
        # T-QT1d: QT-1 が head 非依存であることの固定。`\x77` は bash が `w`
        # （sed のファイル書き出しコマンド）へ復号するため、SED_WRITE_RE は
        # 復号前のテキストに一致しない。awk 限定の規則にすると1形目が通る
        self.assertDeny(
            "sed $'s/a/b/\\x77 tickets/active/APP-001.md' in.md")
        # エスケープを含まない同型（従来から SED_WRITE_RE でも deny）
        self.assertDeny("sed $'s/a/b/w tickets/active/APP-001.md' in.md")

    def test_ansi_c_quote_mark_does_not_break_redirect_target_deny(self):
        # T-QT1e: 印トークンの挿入位置（flush() 完了後）が redirect_violation を
        # 壊していないことの検出器。印を演算子と「次の語」の間に置く実装だと
        # リダイレクト先を見失い1形目が allow に転じる
        self.assertDeny("echo x > $'tickets/active/APP-001.md'")
        self.assertDeny("echo x > $'docs/SPEC.md'")
        self.assertDeny("rm $'tickets/active/APP-001.md'")

    def test_locale_translation_quoted_program_deny(self):
        # T-QT1f: `$"…"`（ロケール翻訳）。メッセージカタログがあれば任意の
        # 文字列へ置換されるため**復号は原理的に不可能**で、判定不能として
        # deny する以外に対処が無い（設計書 §6 R30・INV-SH-05）
        self.assertDeny('awk $"BEGIN{print}" tickets/active/APP-001.md')
        self.assertDeny('awk $"BEGIN{print}" docs/SPEC.md')

    def test_ansi_c_quote_without_guarded_evidence_allow(self):
        # T-QTOK: QT-1／QT-3 の誤deny上限の固定。
        #   1・2: 証拠（言及ゲート）が立たない `$'…'` は巻き添えにしない
        #        （2 はステートメント単位の粒度により第2文だけがゲート偽）
        #   3:   ダブルクォート内の `$'` は bash も展開しないため印を置かない
        #   4・5: `$'…'` の**代替となる推奨形**が使えること（R29 ① の回避策が
        #        実在することの担保）
        self.assertAllow("printf $'a\\tb'")
        self.assertAllow("cat tickets/active/APP-001.md && printf $'a\\tb'")
        self.assertAllow("echo \"$'not ansi'\" tickets/active/APP-001.md")
        self.assertAllow("awk -F'\\t' '{print $1}' tickets/active/APP-001.md")
        self.assertAllow(
            "awk '{printf \"%s\\t%s\\n\", $1, $2}' tickets/active/APP-001.md")

    def test_line_continuation_joins_words_deny(self):
        # T-QT2: bash は行継続（`\`+改行）を**削除して前後を連結する**。空白へ
        # 置換していた第4版までは語が割れて言及ゲートが偽になり、bash が実際に
        # 保護対象を rm するのに allow だった（設計書 §2-3 SH-1・old=allow）
        self.assertDeny("rm tickets/acti\\\nve/APP-001.md")
        self.assertDeny("rm docs/SP\\\nEC.md")

    def test_line_continuation_making_non_guarded_name_allow(self):
        # T-QT2b: QT-2 の帰結。連結後の語は `docs/SPEC.md.bak` であり bash も
        # 同じ語を作る＝**実際には保護対象を触らない**ため allow が正しい
        # （第4版までは誤deny。設計書 §4-9 の許容分類8）
        self.assertAllow("echo x > docs/SPEC.md\\\n.bak")

    def test_ansi_c_encoded_guarded_path_deny(self):
        # T-QT3: 証拠そのものを符号化して隠す形。`\x74` は `t` へ復号され
        # `tickets/active/…` になる。QT-3（証拠収集に限った復号）が無ければ
        # 言及ゲートが偽のまま allow になる（設計書 §3-3・INV-SH-04）
        self.assertDeny("rm $'\\x74ickets/active/APP-001.md'")
        self.assertDeny("rm $'\\x64ocs/SPEC.md'")

    def test_awk_everyday_read_programs_allow(self):
        # T-AW7OK: AW-7 が日常の読み取り awk を誤denyしないことの固定
        # （第4版で最重要の allow 固定。設計書 §3-6 D8 の16形・§4-5-3 の
        # トレースに対応する）。1件でも deny になったら設計の欠陥である
        ticket = "tickets/active/APP-001.md"
        for program in (
            "'NR>1 && $1!=\"\" {print $2}'",
            "-v n=3 '{if (NF > n) print $1}'",
            "'{print toupper($1)}'",
            "'{print length($0)}'",
            "'{gsub(/a/,\"b\"); print}'",
            "'{sub(/^ +/, \"\"); print}'",
            "'{n=split($0,a,\"|\"); print n}'",
            "'{printf(\"%s\\n\", substr($0,1,5))}'",
            "'{a[$1]++} END{for (k in a) print k, a[k]}'",
            "'BEGIN{FS=\":\"} {print $2}'",
            "'BEGIN{print \"日本語のメッセージ\"}'",
        ):
            command = "awk %s %s" % (program, ticket)
            with self.subTest(command=command):
                self.assertAllow(command)
        # `|` を伴わない getline（読み取り方向。意図的に allow）
        self.assertAllow(
            "awk 'BEGIN{getline l < \"tickets/active/APP-001.md\"; print l}'")

    # --- KLK-010 Phase 5: 固定リスト回帰ガード（設計書§4-7・D5） ---

    def test_legacy_deny_commands_all_still_deny(self):
        # T-LEGACY: 旧版が deny していた集合が allow へ転じていないことを
        # 一括で固定する。git・ネットワークに依存しない hermetic な回帰ガード
        for command in LEGACY_DENY_COMMANDS:
            with self.subTest(command=command):
                self.assertDeny(command)

    # --- KLK-010 Phase 9: 棚卸し表と実装の機械的対応（P5・設計書§3-11） ---

    def test_inventory_cases_match_expected_decisions(self):
        # T-INVENTORY: 設計書 §3-9 の書き込みベクタ棚卸し表の各構文が、
        # 実装で期待どおりに判定されることを固定する。「表には書いてあるが
        # 実装もテストも無い」状態（C5 の根因）を機械的に検出する。
        # 期待値 "allow" の行は意図的に未対応の穴であり、コード上で可視に
        # しておくためのもの（塞いだら "deny" へ変える）
        for inventory_id, syntax, command, expected in INVENTORY_CASES:
            with self.subTest(id=inventory_id, syntax=syntax):
                if expected == "deny":
                    self.assertDeny(command)
                else:
                    self.assertAllow(command)

    # --- KLK-010 Phase 10・11 差し戻し検証（tester・8ラウンド目）で追加した
    # 回帰ガード。QT-1/QT-2/QT-3 を破る形を探索したが新規バイパスは
    # 見つからなかった。以下は「見つからなかったことの証拠」として固定する
    # 境界ケースと、日常運用（Kit 自身のタブ区切り処理）で R29 ① に
    # 該当する追加形である。既存137件は無変更（本メソッド群のみ追加）---

    def test_r29_tab_processing_daily_forms_deny(self):
        # R29 ① の一般化: 「クォート外の $'…' を含む形」は awk -F$'\t' /
        # grep $'\t' / sed $'s/\t/ /' の3例に限らず、保護対象へ言及する
        # あらゆる ALLOWED_HEADS コマンドで同じ理由により判定不能＝deny になる
        # （回避策は常に awk -F'\t' 等のリテラルタブ表記）。Kit 自身のログ整形・
        # メトリクス集計・フロントマター抽出で使われがちなタブ処理コマンドで
        # 固定する（tester round8 の探索・新規バイパスなし）
        self.assertDeny("grep $'\\t' tickets/active/APP-001.md")
        self.assertDeny("sed $'s/\\t/ /' tickets/active/APP-001.md")
        self.assertDeny("cat tickets/active/APP-001.md | cut -f1 -d$'\\t'")
        self.assertDeny("awk -F$'\\t' '{print $1}' tickets/active/APP-001.md")
        # 対になる allow 側の回避策（重複回避のためリテラルタブ表記のみ・
        # 既存 T-QTOK は awk -F'\t' を固定済み）
        self.assertAllow("grep -P '\\t' tickets/active/APP-001.md")
        self.assertAllow(
            "cat tickets/active/APP-001.md | cut -f1 -d'\t'")

    def test_ansi_c_quote_inside_nested_substitution_all_depths_deny(self):
        # tester round8: QT-1 の印は lex() の「通常状態」でのみ検出される。
        # $(...) の内側は _take_subst が退避し、後段で find_violation を
        # 再帰させて改めて lex() を通すため、各深さで独立に検出できることを
        # 固定する（深さ0〜MAX_SUBST_DEPTH(3) 境界・その先の深さ4も含む）。
        # 深さ4以降は subst_violation が保守側で打ち切るが、保護対象パスが
        # リテラルで現れる限り is_guarded_token（QT-3の復号込み）が
        # 引き続き deny させることも併せて固定する
        inner = ("awk $'BEGIN{x=\"foo\\x22system(\\x22rm "
                 "tickets/active/APP-001.md\\x22)\\x22\"}'")
        self.assertDeny(inner)
        self.assertDeny("ls $(%s)" % inner)
        self.assertDeny("ls $(echo $(%s))" % inner)
        self.assertDeny("ls $(echo $(echo $(%s)))" % inner)
        self.assertDeny("ls $(echo $(echo $(echo $(%s))))" % inner)  # depth 4

    def test_ansi_c_quote_inside_backtick_and_process_subst_deny(self):
        # tester round8: バッククォート／プロセス置換の内側に $'...' が
        # ある形も、置換内側の再帰評価（find_violation の再帰呼び出し）で
        # 新しい lex() 走査が行われるため検出されることを固定する
        inner = ("awk $'BEGIN{x=\"foo\\x22system(\\x22rm "
                 "tickets/active/APP-001.md\\x22)\\x22\"}'")
        self.assertDeny("ls `%s`" % inner)
        self.assertDeny("cat <(%s)" % inner)

    def test_degraded_line_split_between_dollar_and_quote_still_deny(self):
        # tester round8 の探索: degraded_violation の QT-1 判定
        # （ANSI_QUOTE_RE = \$['"]）はステートメント分割後の**部分文字列**
        # 判定であり、行継続 `\`+改行 の削除は lex() 内でのみ行われ
        # degraded_violation は元の（未結合の）command を受け取る。
        # そのため「$」と「'」の間に未エスケープの生の改行を挟むと
        # （bash は通常の行継続として結合するので実機では同一の $'...' に
        # なる。実機 gawk で実際にファイルを truncate/削除することを
        # 使い捨てディレクトリで確認済み）、degraded の
        # LEGACY_STATEMENT_RE（`\n` を分離子に含む）がこの生の改行でも
        # ステートメントを分割してしまい、$ と ' が別ピースへ分かれるため
        # ANSI_QUOTE_RE はどちらのピースにも一致しない。
        # それでも実際には deny のままである — 分割によって「awk」という
        # head が「$'...'」の胴体（実際の payload）から切り離され、payload
        # 側のピースの先頭語が引用符で始まる未知の head になり、
        # 「'...' は許可されていません」という**別の理由**で deny される
        # ためである（ANSI_QUOTE_REASON ではない）。この安全網は
        # head_of() が引用符付きの語をそのまま未知の head として扱う
        # ことに依存する偶発的なものであり、将来 head_of() が先頭の
        # 引用符文字を正規化・除去するようになった場合に無音で allow へ
        # 転じうる。回帰検出のためここに固定する
        payload_system = (
            "awk $\\\n'BEGIN{x=\"foo\\x22system(\\x22rm "
            "tickets/active/APP-001.md\\x22)\\x22\"}' #'"
        )
        self.assertDeny(payload_system)
        payload_cwd = (
            "cd tickets/active && awk $\\\n'BEGIN{x=\"foo\\x22system(\\x22rm "
            "APP-001.md\\x22)\\x22\"}' #'"
        )
        self.assertDeny(payload_cwd)

    # --- KLK-010 Phase 12: 行継続の正規化を bash の字句規則へ一致させる
    # （設計書 §3-2-1 LX-1〜LX-5・§4-2-2）。行継続の近似は bash と一致して
    # いなければ**両方向へ倒れる**ため、deny 側（T-C7a/b/e/f/h）と allow 側
    # （T-C7c/T-C7d(b)/T-C7g）を**対で**固定する。片方だけでは検出できない ---

    def test_line_continuation_even_backslash_run_is_separator_deny(self):
        # T-C7a: バックスラッシュが**偶数個**並ぶと、最後の `\` はリテラルの
        # バックスラッシュであり続く改行は**制御演算子（区切り）**である。
        # 無条件に `\`+改行 を削除する実装は後続コマンドの head を前の語へ
        # 吸収させ、ALLOWED_HEADS 判定に使われる head が先頭の許可コマンドに
        # なる（＝任意の読み取りコマンドに2文字足すだけで hook 全体が無効化
        # される）。実機 bash は後続コマンドを実行してファイルを削除・改変する
        for command in (
            "echo x\\\\\nrm docs/SPEC.md",                 # 2個（偶数）
            "ls \\\\\nrm docs/SPEC.md",
            "echo x\\\\\\\\\nrm docs/SPEC.md",             # 4個（偶数）
            "pwd\\\\\ntruncate -s 0 docs/SPEC.md",
            "echo x\\\\\nsed -i 's/a/b/' tickets/active/APP-001.md",
            "ls a\\\\\ncat b | tee docs/SPEC.md",
        ):
            with self.subTest(command=command):
                self.assertDeny(command)

    def test_line_continuation_after_comment_is_separator_deny(self):
        # T-C7b: `#` コメントの内側では `\` は特別な意味を持たず、改行が
        # コメントを終わらせる＝**区切り**である。コメントをモデル化せずに
        # `\`+改行 を削除すると、ここでも後続コマンドの head が吸収される
        for command in (
            "cat README.md #\\\nsed -i 's/orig/pwned/' "
            "tickets/active/APP-001.md",
            "ls #x\\\nrm docs/SPEC.md",
            "grep x README.md #\\\ncat y | tee docs/SPEC.md",
            "echo x #\\\ntruncate -s 0 tickets/active/APP-001.md",
        ):
            with self.subTest(command=command):
                self.assertDeny(command)

    def test_line_continuation_odd_backslash_run_stays_allow(self):
        # T-C7c: **二方向要求の固定点。** バックスラッシュが奇数個で終わる形は
        # bash も行継続として連結する（後続コマンドは実行されない）。したがって
        # deny は**誤り**であり、過剰deny側へ倒した実装をここで機械的に検出
        # する。実機 bash で使い捨てディレクトリを用い「ファイルが残る」ことを
        # 確認済み（1個・3個とも実行されない）
        for command in (
            "echo x\\\nrm docs/SPEC.md",                   # 1個（奇数）
            "echo x\\\\\\\nrm docs/SPEC.md",               # 3個（奇数）
            "ls \\\nrm tickets/active/APP-001.md",
        ):
            with self.subTest(command=command):
                self.assertAllow(command)

    def test_line_continuation_quote_kind_branches(self):
        # T-C7d: クォート種別で bash の挙動が分岐する。`"…"` の内側では
        # 行継続として削除されるが、`'…'` の内側では `\` も改行もリテラルで
        # あり連結されない（bash が触るのは「改行を含む別名のファイル」で
        # あって保護対象ではないため allow が正しい＝設計書 §4-9 許容分類9）
        self.assertDeny('rm "tickets/acti\\\nve/APP-001.md"')
        self.assertAllow("rm 'tickets/acti\\\nve/APP-001.md'")

    def test_line_continuation_inside_substitution_is_command_context(self):
        # T-C7e: コマンド置換の内側は**コマンド文脈へ戻る**ため、ダブル
        # クォートの内側にあっても `#` はコメントになる。正規化が置換の内側へ
        # 一律に適用されると、内側を再帰評価する前に区切りが失われる。
        # 内側を無加工で残し、再帰の入口で内側の文脈として正規化することで
        # 閉じる（文脈スタックを持たずに正しくなる）
        self.assertDeny('cat "$(ls #\\\nrm docs/SPEC.md)"')
        self.assertDeny("ls `ls #\\\nrm docs/SPEC.md`")

    def test_hash_not_at_word_start_is_not_a_comment(self):
        # T-C7f: `#` がコメントになるのは**クォート外で語頭に現れたとき**
        # だけである。クォート内・語中・コマンド置換の直後の `#` をコメントと
        # 誤検出すると、そこで行継続の適用が止まって保護対象パスが2語に割れ、
        # 言及ゲートが偽になる（AC1「クォート内の `#` で特殊構文判定をしない」
        # との整合の固定点でもある）
        for command in (
            "rm 'x#y' tickets/acti\\\nve/APP-001.md",
            "rm a#b tickets/acti\\\nve/APP-001.md",
            "rm $(echo x)#y tickets/acti\\\nve/APP-001.md",
        ):
            with self.subTest(command=command):
                self.assertDeny(command)

    def test_hash_modelling_does_not_break_everyday_reads(self):
        # T-C7g: `#` のモデル化が日常の読み取りを誤denyしないことの固定
        # （LX-3 の誤deny上限）
        for command in (
            "grep -c '#' tickets/active/APP-001.md",
            "grep -n '#\\|x' tickets/active/APP-001.md",
            "awk '{print}' tickets/active/APP-001.md # メモ",
        ):
            with self.subTest(command=command):
                self.assertAllow(command)

    def test_line_continuation_does_not_shift_comment_start_context(self):
        # T-C7h: **正規化走査が「連結時に直前の文字を書き換えない」ことの
        # 検出器。** bash は `\`+改行 を取り除いて前後を直接隣接させるため、
        # 語頭判定に効くのは「削除前の直前の文字」である。連結時に直前の文字を
        # 書き換える実装だと、続く `#` を語頭と認識できずコメントを見落とし、
        # 2つ目の行継続まで連結して **allow に転じる**（C7 の再発）
        self.assertDeny("echo a \\\n#c\\\nrm docs/SPEC.md")

    def test_degraded_inside_substitution_under_guarded_cwd_deny(self):
        # T-C8a: `degraded_violation` の**関数レベルゲート**が cwd を見ないと、
        # 保護対象 cwd 下で「字句解析できない置換」を1つ挟むだけで全判定を
        # 回避できる。到達経路は find_violation → subst_violation →
        # find_violation(inner, depth+1, cwd) → lex の ValueError →
        # degraded_violation(inner, cwd)。`_take_backtick` がクォート状態を
        # 追わないのは bash と同じ仕様であり、修正すべきはゲートの側である。
        # 実機 bash で実際に削除・上書きが起きることを確認済み
        for command in (
            "cd tickets/active && ls `rm APP-001.md #'`",
            "cd tickets/active && ls `echo x > APP-001.md #'`",
            "cd tickets/active && ls `sed -i 's/a/b/' APP-001.md #'`",
            "cd tickets/active && ls `find . -delete #'`",
            "cd tickets/active && ls `cp /tmp/e APP-001.md #'`",
            "cd tickets/active && ls `truncate -s 0 APP-001.md #'`",
            "cd tickets/active && ls `cat /tmp/e | tee APP-001.md #'`",
            "cd tickets/active && echo `tee APP-001.md #'`",
            "cd tickets/done && ls `rm APP-001.md #'`",
            # $( ) の内側にバッククォートがあり、その中の引用符が不均衡な形。
            # 置換の終端探索がバッククォート領域を読み飛ばさないと、対応する
            # `)` を見失ってコマンド全体が degraded へ落ち、内側の `rm` が
            # 空白分割で `ls` セグメントへ埋もれる（実機 bash は削除する）
            "cd tickets/active && ls $(ls `rm APP-001.md #'`)",
        ):
            with self.subTest(command=command):
                self.assertDeny(command)

    def test_degraded_gate_still_returns_early_outside_guarded_cwd(self):
        # T-C8b（対照）: C8 の修正が保護対象外へ波及しないことの固定。
        # 保護対象への言及も保護対象 cwd も無い入力では、関数レベルゲートは
        # 依然として early return しなければならない
        self.assertAllow("cd /tmp && ls `rm x.md #'`")
        self.assertAllow("ls `rm x.md #'`")

    def test_normalized_command_is_shared_with_degraded_path(self):
        # T-H4a: 正規化を find_violation の入口で1回だけ行い、正規化後の
        # **同じ文字列**を lex() と degraded_violation() の双方へ渡す。
        # 第5版は lex() だけが結合後を見て degraded は生の command を見ていた
        # ため、同じ入力に対して2つの経路が異なる行構造を評価していた。
        # 正規化後は degraded でも `$'` が隣接して ANSI_QUOTE_RE に一致し、
        # 「判定不能」という**意図された理由**で deny になる（既存の回帰ガード
        # test_degraded_line_split_between_dollar_and_quote_still_deny は
        # 理由文字列を assert していないため無変更で pass する）
        self.assertDeny(
            "awk $\\\n'BEGIN{x=\"foo\\x22system(\\x22rm "
            "tickets/active/APP-001.md\\x22)\\x22\"}' #'")
        self.assertDeny(
            "cd tickets/active && awk $\\\n'BEGIN{x=\"foo\\x22system(\\x22rm "
            "APP-001.md\\x22)\\x22\"}' #'")

    def test_multiline_awk_program_stays_allow(self):
        # 生の改行（`\`+改行 ではない）は awk では `;` と同じ**文の終端**で
        # ある。行構造の走査化にあたり、クォート内の改行が `;` へ置換されなく
        # なるため、AW-7 の許可文字集合へ改行を明示収載していないと複数行の
        # 読み取り awk が新規に誤denyになる（設計書 §6 R33 の列挙外＝V-12(c)
        # のブロッカー）。両方向を固定する
        self.assertAllow(
            "awk 'BEGIN{FS=\":\"}\n{print $2}' tickets/active/APP-001.md")
        self.assertAllow(
            "awk '\nNR>1 {\n  print $1\n}\n' tickets/active/APP-001.md")
        self.assertDeny(
            "awk '{\nprint > \"docs/SPEC.md\"\n}' in.txt")
        self.assertDeny(
            "awk 'BEGIN{\nsystem(\"rm docs/SPEC.md\")\n}'")

    # --- KLK-010 tester round9（reviewer 3回目差し戻し後）: D-1/D-2 の逸脱・
    # F1-2/F1-7 の分類確認のため追加。normalize_line_continuations() を破る
    # 形を約90通り探索したが新規バイパスは見つからなかった。以下はその過程で
    # 見つかった「既存テストに無い正当な allow／回帰対象」を固定する ---

    def test_backtick_readonly_substitution_allow(self):
        # D-2 の回帰確認: `_skip_balanced` がバッククォート領域を
        # `_skip_backtick` と同じ規則で読み飛ばすよう変更されたことが、
        # 日常的な（読み取り専用の）バッククォート置換の解析を壊していない
        # ことを固定する。ネスト（$(...) を内側に持つ形）・クォート内容
        # （bash 自身もバッククォート内ではクォート状態を追わない仕様）を含む
        self.assertAllow("echo `date +%Y` tickets/active/APP-001.md")
        self.assertAllow("echo `echo $(echo hi)` tickets/active/APP-001.md")
        self.assertAllow(
            "echo `echo \"a'b\"` tickets/active/APP-001.md")
        self.assertAllow("echo `git rev-parse HEAD` tickets/active/APP-001.md")

    def test_line_continuation_even_run_separator_survives_nested_substitution_deny(
            self):
        # T-C7 と AC4（置換再帰）の組み合わせ確認: 偶数個の `\`+改行 が
        # コマンド置換の内側で「区切り」として働くことは、置換の内側が
        # find_violation により独立に再正規化・再字句解析されるため、
        # ネスト深さに関わらず（MAX_SUBST_DEPTH=3 の境界を越えても）
        # 保たれなければならない。実機 bash で深さ1〜5すべてにおいて
        # 内側の rm が独立コマンドとして実行されファイルが削除されることを
        # 確認済み（tester round9）
        for depth in range(1, 6):
            inner = "echo x\\\\\nrm tickets/active/APP-001.md"
            wrapped = inner
            for _ in range(depth):
                wrapped = "echo $(%s)" % wrapped
            with self.subTest(depth=depth):
                self.assertDeny(wrapped)

    def test_line_continuation_even_backslash_run_generalizes_across_heads_deny(
            self):
        # T-C7a の一般化固定: 「head が許可コマンドなら何でも成立する」という
        # reviewer の指摘（3回目レビューメモ）を、既存テストが使っていない
        # 許可 head（cd・grep・awk・cut）でも実機 bash と突き合わせて固定する。
        # いずれも偶数個（2個）の `\`+改行 の後続に書き込みコマンドが続き、
        # 実機 bash はこれを独立した2つ目のステートメントとして実行する
        for command in (
            "cd ..\\\\\nrm tickets/active/APP-001.md",
            "grep x README.md\\\\\nrm tickets/active/APP-001.md",
            "awk '{print}' README.md\\\\\nrm tickets/active/APP-001.md",
            "cut -d: -f1 README.md\\\\\nrm tickets/active/APP-001.md",
        ):
            with self.subTest(command=command):
                self.assertDeny(command)

    def test_f1_2_and_f1_7_bash_syntax_error_forms_allow(self):
        # reviewer 3回目レビューメモ・implementer Phase12/13 実装メモが分類を
        # 委ねた2形（F1-2／F1-7）。tester round9 で使い捨てディレクトリの
        # 実機 bash（GNU bash）に投入し検証した:
        #   F1-2 `cd tickets/active && ls `rm APP-001.md \``
        #     -> rc=2 "unexpected EOF while looking for matching ``'"
        #        対象ファイルは変更されない
        #   F1-7 `cd tickets/active && cat <(rm APP-001.md #')`
        #     -> rc=2 "unexpected EOF while looking for matching `)'"
        #        対象ファイルは変更されない
        # いずれも bash 自身が構文エラーで何も実行しないため、hook が allow
        # でも実害が無い。§4-9 の許容分類10（bash が実際には保護対象を
        # 触らない）と同じ根拠で許容できるという tester の判断を固定する。
        # 将来 lex()／`_skip_balanced` の変更でこれらが「実際に実行される
        # 構文」に転じた場合はこのテストが deny への変更を要求する形で
        # 検出できるようにするため、ここに固定しておく
        self.assertAllow("cd tickets/active && ls `rm APP-001.md \\`")
        self.assertAllow("cd tickets/active && cat <(rm APP-001.md #')")

    # --- KLK-010 Phase 14: awk の**字句次元**（コメント・リテラルの終端規則）を
    # awk の規則へ一致させる（設計書 §3-6 D11 の AWL-1〜AWL-4・§3-9-3）と、
    # degraded のステートメント区切り集合を正常経路へ一致させる（H5）。
    # テキストを除去する近似には**方向の非対称**がある — 除去しすぎ
    # （over-removal）は allow 方向（危険）、除去しなさすぎ（under-removal）は
    # deny 方向（安全）。したがって deny 側（T-C9a〜e）と allow 側
    # （T-C9f〜h）を**対で**固定する。片方だけでは検出できない ---

    def test_awk_comment_shifts_string_parity_deny(self):
        # T-C9a（AWL-3・INV-AWKLEX-01）: awk の `#` コメントをモデル化せず、
        # 文字列リテラルの走査が改行で打ち切られないと、**コメント内の `"` が
        # 文字列の対応をずらし、awk が実際に実行するコード（system( 等）が
        # リテラルとして飲み込まれる**。コメント側に `"` をもう1つ置いて
        # パリティを戻せば「未閉じ文字列＝deny」にも掛からず、除去後テキストが
        # AW-7 の3条件をすべて満たして allow になっていた。実機 gawk 5.2.1 が
        # rc=0 で docs/SPEC.md を削除し、sed -i でチケットを改変することを
        # 使い捨てディレクトリで確認済み。**`#` 分岐（AWL-3）を落とすと
        # 全件が失敗する**
        for payload in (
            'system("rm docs/SPEC.md")',
            'system("sed -i s/a/b/ tickets/active/APP-001.md")',
            'print "x" > "docs/SPEC.md"',
            '"rm docs/SPEC.md" | getline x',
        ):
            command = "awk 'BEGIN{ #\"\n%s #\"\n}'" % payload
            with self.subTest(payload=payload):
                self.assertDeny(command)

    def test_awk_comment_parity_across_program_sources_deny(self):
        # T-C9b（INV-AWKLEX-02／04）: プログラム本文の**供給形**を変えても
        # 閉じていること。`-e` / `--source=` は awk_program_texts が拾う経路で
        # あり、間接呼び出し `@x(` は許可文字集合（`@` 非収載）で落ちる。
        # いずれもコメントが正しく除去されて初めて到達する
        shift = 'BEGIN{ #"\n%s #"\n}'
        self.assertDeny("awk -e '%s'" % (shift % 'system("rm docs/SPEC.md")'))
        self.assertDeny(
            "awk --source='%s'" % (shift % 'system("rm docs/SPEC.md")'))
        self.assertDeny(
            "awk '%s'" % (shift % 'x="system"; @x("rm docs/SPEC.md")'))

    def test_awk_comment_parity_under_guarded_cwd_deny(self):
        # T-C9c（INV-AWKLEX-03）: 語に保護対象パスが1文字も現れない形。
        # 言及ゲートではなく cwd ゲート（cwd_is_guarded）で AW-7 に到達する
        for directory in ("tickets/active", "tickets/done"):
            command = ("cd %s && awk 'BEGIN{ #\"\nsystem(\"rm APP-001.md\")"
                       " #\"\n}'" % directory)
            with self.subTest(cwd=directory):
                self.assertDeny(command)

    def test_awk_ambiguous_division_before_comment_deny(self):
        # T-C9d（AWL-4・INV-AWKLEX-10）: **AWL-3 だけを入れた実装で allow に
        # 転じる検出器。** AWK_OPERAND_END_CHARS は post-increment（`a++ /2/`）
        # を除算と判定するため `+` を含む。そのため hook はここを除算と読むが、
        # awk の文法は `+` の直後にオペランドを期待するため `/#/` を**正規表現
        # 定数**として読みうる（その場合 system(…) は実行される）。除算として
        # 据え置いた `/` と同じ行に除去対象があり、その位置以降にも `/` が
        # 残るときは、いかなる除去も行わず「判定不能」＝deny とする
        self.assertDeny("awk 'BEGIN{x=1+ /#/; system(\"rm docs/SPEC.md\")}'")

    def test_awk_ambiguous_division_before_string_deny(self):
        # T-C9e（AWL-4／AWL-1・INV-AWKLEX-11／05）: 同型の文字列版
        # （AWL-4 が無ければ2つの `"` が対になって `; system(` を飲み込み
        # allow になる）と、**文字列リテラルが生の改行に達する形**
        # （awk の文字列は行をまたげない＝未終端＝判定不能）
        self.assertDeny(
            "awk 'BEGIN{x=1+ /\"/ ; system(\"rm docs/SPEC.md\")"
            " ; y=2+ /\"/ }'")
        self.assertDeny("awk 'BEGIN{x=\"a\nb\"; system(\"rm docs/SPEC.md\")}'")

    def test_awk_hash_inside_literals_is_not_a_comment_allow(self):
        # T-C9f（allow 固定・INV-AWKLEX-08／09／06）: 過剰deny側へ倒した実装を
        # 機械的に検出する。文字列・正規表現の分岐はスパン全体を1回の反復で
        # 消費して `i` を進めるため、**リテラル内側の `#` はループ先頭へ到達
        # しない**（`/#/`・`"#"` をコメントと誤検出しない）。3形目は
        # **AWL-1 のエスケープ対消費が改行判定より前にある**ことの検出器で、
        # 順序を逆にすると gawk が受け付ける文字列内の行継続が「未終端＝deny」
        # に転じる
        for command in (
            "awk '/#/ {print}' tickets/active/APP-001.md",
            "awk '{print \"#\"}' tickets/active/APP-001.md",
            "awk 'BEGIN{x=\"a\\\nb\"; print x}' tickets/active/APP-001.md",
        ):
            with self.subTest(command=command):
                self.assertAllow(command)

    def test_awk_division_without_trailing_slash_allow(self):
        # T-C9g（allow 固定・INV-AWKLEX-12）: **AWL-4 の誤deny上限。**
        # 除算があっても、除去位置以降・同一行に `/` が残らなければ、awk 側の
        # 解釈では正規表現が閉じず fatal error になり1文も実行されない＝
        # 曖昧さが実行に到達しえないため除去してよい
        for command in (
            "awk '{print $1/2, $3/4, \"ratio\"}' tickets/active/APP-001.md",
            "awk '{print $1/$2}' tickets/active/APP-001.md",
        ):
            with self.subTest(command=command):
                self.assertAllow(command)

    def test_awk_comment_body_only_patterns_allow(self):
        # T-C9h（allow 固定・INV-AWKLEX-07／13）: **awk はコメントを実行しない
        # ため deny する根拠が無い。** 危険様パターン（`|`・`@`・`system(`・
        # 引用符の不均衡）がコメント本文にしか現れない形は allow が正しい
        # （設計書 §6 R26⑧ の誤denyの解消＝§4-9 許容分類11）。3形目は
        # 複数行プログラム（改行は awk では `;` と同じ文終端）の固定点
        for command in (
            "awk '{print $1} # a|b @c system(' tickets/active/APP-001.md",
            "awk '{ #\"\nprint $1 }' tickets/active/APP-001.md",
            "awk 'BEGIN{FS=\":\"}\n{print $2}' tickets/active/APP-001.md",
        ):
            with self.subTest(command=command):
                self.assertAllow(command)

    def test_degraded_single_ampersand_is_statement_separator_deny(self):
        # T-H5a（INV-SH-21）: 正常経路は `&` を "sep"（ステートメント区切り）
        # として扱うのに degraded の LEGACY_STATEMENT_RE に単独 `&` が無いと、
        # ` #'` の2文字を足すだけで `&` の後段が先頭 head のセグメントへ
        # 埋もれて全防御が消える（実機 bash は rc=0 で削除・改変する）。
        # **この1文字を戻すと全件が失敗する**
        for command in (
            "ls & rm docs/SPEC.md #'",
            "ls & sed -i 's/a/b/' tickets/active/APP-001.md #'",
            "ls & truncate -s 0 docs/SPEC.md #'",
            "cd tickets/active & rm APP-001.md #'",
        ):
            with self.subTest(command=command):
                self.assertDeny(command)

    def test_degraded_ampersand_does_not_spill_into_reads_allow(self):
        # T-H5b（allow 固定・対照）: `&` の追加が fd 複製（`2>&1`）と、
        # 後段の head が許可されている読み取りへ波及しないことの固定
        self.assertAllow("cat tickets/active/APP-001.md 2>&1 #'")
        self.assertAllow("ls & cat tickets/active/APP-001.md #'")

    # --- tester round11（reviewer 4回目 rejected 後の検証）: AWL-4 の外側の穴。
    # AWK_OPERAND_END_CHARS に `/` 自身（正規表現リテラルの終端文字）が
    # 含まれていない。正規表現リテラル `/x/` が閉じた直後は awk 上は
    # 「値（0/1）が確定した」＝オペランドの終端であり、続く `/` は正当な
    # 除算演算子であるはずだが、`awk_strip_literals` の `prev` は `/` に
    # なり、`AWK_OPERAND_END_CHARS` に `/` が無いため、この2つ目の `/` は
    # 「除算として据え置く」（`div_seen = True`）分岐を通らず、AWL-2 の
    # 正規表現除去分岐（`char == "/" and prev not in AWK_OPERAND_END_CHARS`）
    # へ再突入する。同一行中に3つ目の `/` があり `;`／改行を跨がなければ、
    # 2つ目と3つ目の `/` の間（= 実際には awk が実行する式そのもの。
    # `system(...)` を含みうる）が「正規表現」として `//` に丸ごと除去
    # される。この除去は `if closed: ...; continue` 経路を通るため
    # **`div_seen` を一度も True にせず** AWL-4 の `ambiguous()` は
    # `if not div_seen: return False` で必ず素通りする。したがって
    # AWL-4（C9 で新設した曖昧ガード）はこの鎖（正規表現の直後に除算が
    # 連続する形）を一切検出できない。C9 の13サブケース
    # （INV-AWKLEX-01〜13・いずれも `#` コメントを起点とする）はこの経路を
    # 1つもカバーしていない。
    #
    # 実機 GNU Awk 5.2.1 で確認済み（使い捨てディレクトリ・テストには
    # 含めない）: `awk 'BEGIN{/x/ / system("rm victim.md") / 1}'` は
    # `victim.md` を実際に削除したうえで `system()` の戻り値 0 による
    # 「division by zero」で fatal 終了する（rc=2 だが削除は既に発生済み）。
    # 対象を保護対象のベース名 `SPEC.md`（`/` を含まないため上の鎖が
    # 途中で `"` にぶつからず成立する）にしても同じ経路で allow になる
    # ことを本テストで固定する。旧版（merge-base 72ae7306）はこれらを
    # すべて deny する（`awk` が ALLOWED_HEADS に無いため）ので
    # old=deny -> new=allow の新規リグレッションである。
    def test_awk_chained_division_after_regex_bypasses_awl4_deny(self):
        for command in (
            'awk \'BEGIN{/x/ / system("rm SPEC.md") / 1}\'',
            'awk -e \'BEGIN{/x/ / system("rm SPEC.md") / 1}\'',
            "awk --source='BEGIN{/x/ / system(\"rm SPEC.md\") / 1}'",
            'cd tickets/active && awk \'BEGIN{/x/ / system("rm APP-001.md") / 1}\'',
        ):
            with self.subTest(command=command):
                self.assertDeny(command)

    # --- T-C10b（allow 固定・T-C10a＝直前の
    # test_awk_chained_division_after_regex_bypasses_awl4_deny と対をなす）:
    # C10 の修正は
    # 「閉じた正規表現の直後の `/` を除算として据え置く」＝**除去しない**
    # 方向の変更であり、除去しないことは判定対象テキストが増えるだけなので
    # deny 方向にしか倒れない。だからこそ**過剰denyへ倒れていないこと**を
    # 対で固定する必要がある（片方だけでは検出できない）。
    # ここに挙げた形は正規表現リテラルと除算が同居する日常の読み取りであり、
    # いずれも実機 gawk が正常に読み取りを行うだけで何も書き込まない。
    # **prev_regex を「改行でリセットしない」実装や、AWK_OPERAND_END_CHARS へ
    # `/` を足して除算の直後まで除算と読む実装にすると、この集合の一部が
    # deny へ転じる**（前者は複数行パターンの2件目、後者は AWL-4 の
    # 誤deny上限＝INV-AWKLEX-12 の周辺）。
    def test_awk_regex_followed_by_division_reads_stay_allow(self):
        for command in (
            # 閉じた正規表現の直後が除算（C10 の修正が直接触れる形）
            "awk '/x/ / 2 {print}' tickets/active/APP-001.md",
            "awk '/a/ {print $1/2}' tickets/active/APP-001.md",
            "cd tickets/active && awk '/a/ {print $1/2}' APP-001.md",
            # 正規表現・コメント・文字列と除算の同居（AWL-2／3／4 の非発火）
            "awk '{print $1/2, $3/4, \"ratio\"}' tickets/active/APP-001.md",
            "awk '/#/ {print}' tickets/active/APP-001.md",
            "awk '{print \"#\"}' tickets/active/APP-001.md",
            "awk '{gsub(/a/,\"b\"); print}' tickets/active/APP-001.md",
            "awk '/a/ && /b/ {print}' tickets/active/APP-001.md",
            # 改行で prev_regex がリセットされること（複数行パターン）
            "awk '/a/ {print}\n/b/ {print}' tickets/active/APP-001.md",
            "awk 'BEGIN{FS=\"/\"} {print $2}' tickets/active/APP-001.md",
        ):
            with self.subTest(command=command):
                self.assertAllow(command)

    # --- tester round12（C10 修正の検証・実装メモ「残存リスク1」の裏取り）:
    # `;`／改行／`&&`／`}`（トップレベルのルール境界）など、awk の文法上
    # **新しい文・新しいオペランド位置**を作るトークンを挟んで
    # 「閉じた正規表現」と「除算に見える連鎖」が隣り合う形は allow のまま
    # であることを固定する。C10 が閉じたのは「閉じた正規表現の**直後**の
    # `/`」だけであり、これらの境界トークンを挟む形は元々
    # `AWK_OPERAND_END_CHARS`／`prev_regex` の別経路で「新しい文・新しい
    # オペランド」と正しく解釈されるため、awk 側の解釈と一致した上での
    # allow である。使い捨てディレクトリで実機 GNU Awk 5.2.1 により
    # 直接確認済み（tester round12・victim.txt を対象に実行）:
    # `;`／改行／`&&`／`}` のいずれの境界でも rc=0 でファイルは無傷
    # （`system(...)` は実行されない。統計的な掃引として38種の境界文字・
    # 演算子を追加で試したが allow かつ「実機が保護対象へ到達する」形は
    # 0件だった）。**この allow を deny 側へ寄せる変更（例: `prev_regex` を
    # `;` や改行でリセットしない）は、`awk '/x/ ; /y/ {print}' T` のような
    # 日常の複文読み取りを過剰denyへ倒すため避けること。**
    def test_awk_regex_division_chain_across_statement_boundary_stays_allow(self):
        for command in (
            # `;` 文区切り（直後の `/` は awk の文法上つねに新しい文の
            # 先頭＝正規表現であり、除算に読める余地が無い）
            'awk \'BEGIN{/x/ ; / system("rm SPEC.md") / 1}\'',
            'cd tickets/active && awk \'BEGIN{/x/ ; '
            '/ system("rm APP-001.md") / 1}\'',
            # 改行（文終端。C10 修正が明示的に prev_regex をリセットする形）
            'awk \'BEGIN{/x/\n/ system("rm SPEC.md") / 1}\'',
            # `&&`（二項演算子の右辺＝新オペランド位置）
            'awk \'BEGIN{/x/ && / system("rm SPEC.md") / 1}\'',
            # `}`（トップレベルのルール境界。1つ目のパターン・アクション対の
            # 終端の直後は新しいルール＝パターン位置）
            'awk \'BEGIN{/x/}\n/ system("rm SPEC.md") / 1\'',
        ):
            with self.subTest(command=command):
                self.assertAllow(command)

    # --- tester round12（実装メモ「残存リスク2」の裏取り）: awk プログラム
    # *本文*（文字列・正規表現の外側）に現れる `\`＋改行（gawk 独自の行継続）
    # は実機 gawk が実際に `system()` を実行してしまう形だが（使い捨て
    # ディレクトリで実測: `gawk -f prog.awk` は victim.txt を削除した上で
    # division by zero により rc=2 で fatal 終了。副作用は既に発生済み）、
    # 本 hook が deny するのは `prev_regex` の状態機械が正しく境界を
    # 見分けているからでは**ない**（`awk_strip_literals` 単体を呼び出すと
    # `system(...)` は現に正規表現として除去され尽くす）。deny の実体は
    # **AW-7 の許可文字集合 `AWK_SAFE_PROGRAM_CHARS` に `\` が無いこと**の
    # 一点に依存している。このテストは実装メモが指摘する
    # 「`AWK_SAFE_PROGRAM_CHARS` へ `\` を足すと同型の穴が開く」という
    # 懸念のカナリアであり、将来 `\` を許可文字集合へ追加する変更が入ったら
    # 即座に失敗する。
    def test_awk_program_level_backslash_continuation_denies_via_char_whitelist(
            self):
        out = self.assertDeny(
            'awk \'BEGIN{/x/\\\n/ system("rm SPEC.md") / 1}\'')
        self.assertIn(
            "許可されていない文字", out.get("permissionDecisionReason", ""))

    # --- tester round12: 正規表現と除算が同居する日常の読み取り awk を
    # 追加で固定する（T-C10b の拡張。tester への委譲プロンプト項目3
    # 「日常操作のケースを自分で追加する」に対応）。いずれも system 等の
    # 危険様パターンを含まない素の読み取りである。
    def test_awk_daily_reads_combining_regex_and_division_stay_allow(self):
        for command in (
            # コメント行をスキップしてから比率を計算する日常形
            "awk '/^#/{next} {print $1/$2}' tickets/active/APP-001.md",
            # フィールド区切りを `/` にした比率計算（AWL-2 と無関係な `-F/`）
            "awk -F/ '{print $2/$3}' tickets/active/APP-001.md",
            # 正規表現内のエスケープされた `/`（分数表記 `3/4` を検出する形）
            "awk '{print ($0 ~ /[0-9]+\\/[0-9]+/)}' tickets/active/APP-001.md",
            # 複数行プログラム: パターン行のあとで比率を計算する日常形
            "awk 'BEGIN{FS=\"/\"}\n/^Total/{t=$2}\n{r=$1/t; print r}'"
            " tickets/active/APP-001.md",
        ):
            with self.subTest(command=command):
                self.assertAllow(command)

    # --- tester round12: 設計書 docs/designs/KLK-010.md 878行目・3107行目
    # （§3-6 D11／§6 R36 ②）が明示する「受容済みの誤deny」の代表形を固定する。
    # `div_seen` が真の行で正規表現除去を試みる位置は、`ambiguous()` の
    # 探索対象に自分自身の `/` を含めるため常に None（判定不能）になる
    # **設計上の意図した保守側の縮退**であり、バグではない
    # （設計書の言葉で「意図した保守側の縮退」）。本テストは tester が
    # daily-read 探索で独立にこの誤denyを再現し、設計の記述・R36 の分類
    # （新規誤deny3種類のうちの②）と一致することを確認した上で、
    # 今回の C10 修正（`prev_regex` の導入）でこの既知の誤denyバケットが
    # 意図せず広がっていないことを固定する回帰ガードである。
    def test_awk_division_then_regex_same_line_known_misdeny_r36_2(self):
        for command in (
            # 設計書 878/3107行目の正準形
            "awk '{if ($1/$2 > 0.5 && /foo/) print}' tickets/active/APP-001.md",
            # tester が daily-read 探索で見つけた同型（除算のあとで
            # regex を条件式に使う一行形）
            "awk '{ratio=$1/$2; if (ratio ~ /^[0-9]/) print ratio}'"
            " tickets/active/APP-001.md",
        ):
            with self.subTest(command=command):
                self.assertDeny(command)

    # --- KLK-014（H6）: degraded mode もコマンド置換の内側を再帰評価する
    # （`_extract_degraded_substs` 新設・案C）。investigator が実測した
    # 再現手順の全形（置換の型3種 × 書き込みベクタ計8種・ネスト・末尾の
    # 誘発形2種・保護対象2種）を deny 側で固定し、正常経路の判定（AC2）・
    # 誤deny予算の3カテゴリ（AC3・設計書§9）を allow/deny の両方向で
    # 対にして固定する ---

    def test_h6_subshell_substitution_all_write_vectors_deny(self):
        # T-H6a（AC1）: `$(...)` の内側にある各種書き込みベクタ（チケット
        # 記載の7種＋repro本体の rm）が、末尾 ` #'`（未閉じコメント内クォート）
        # で degraded へ落ちた形でも検出されることを固定する。対象は
        # docs/SPEC.md（investigator が実測したベースの保護対象）
        for command in (
            "ls $(rm docs/SPEC.md) #'",
            "ls $(sed -i 's/a/b/' docs/SPEC.md) #'",
            "ls $(awk -i inplace '{print}' docs/SPEC.md) #'",
            "ls $(tee docs/SPEC.md) #'",
            "ls $(cp /tmp/e docs/SPEC.md) #'",
            "ls $(truncate -s 0 docs/SPEC.md) #'",
            "ls $(find docs -name SPEC.md -delete) #'",
            "ls $(python3 -c \"open('docs/SPEC.md','w').write('x')\") #'",
        ):
            with self.subTest(command=command):
                self.assertDeny(command)

    def test_h6_backtick_substitution_write_vector_deny(self):
        # T-H6b（AC1）: バッククォート置換。保護対象は tickets/active/ 側
        # （docs/SPEC.md と tickets/active/*.md の両方で成立することの固定）
        self.assertDeny("ls `rm tickets/active/APP-001.md` #'")

    def test_h6_process_substitution_write_vector_deny(self):
        # T-H6c（AC1）: プロセス置換 `<(...)`（入力方向）
        self.assertDeny("cat <(rm docs/SPEC.md) #'")

    def test_h6_nested_substitution_deny(self):
        # T-H6d（AC1）: ネスト（`$( $(...) )`）
        self.assertDeny("ls $( $(rm docs/SPEC.md) ) #'")

    def test_h6_lone_trailing_backslash_also_triggers_degraded_deny(self):
        # T-H6e（AC1）: ` #'` だけでなく、末尾の孤立 `\` 1個でも degraded へ
        # 落ちる（H6 のもう1つの誘発形）ことの固定
        self.assertDeny("ls $(rm docs/SPEC.md) \\")

    def test_h6_cwd_relative_path_propagation_deny(self):
        # T-H6f（AC1・§9 テスト観点(2)）: cwd 伝播。保護対象 cwd 下では
        # 置換の内側が相対パス形（`APP-001.md`）でも検出されることの固定
        self.assertDeny("cd tickets/active && ls $(rm APP-001.md) #'")

    def test_h6_normal_path_judgement_unchanged_deny(self):
        # T-H6g（AC2）: 正常経路（lex() が成功する対照形）の判定は本チケットで
        # 1文字も変わらない。` #'` が無ければ引き続き deny のままである
        self.assertDeny("ls $(rm docs/SPEC.md)")

    def test_h6_readonly_substitution_inside_degraded_stays_allow(self):
        # T-H6h（AC2）: 置換の内側が読み取り専用なら degraded でも allow の
        # ままである（H6 は「内側が実際に違反か」を評価するため、却下した
        # 案Bのように置換記号があるだけで一律 deny にはしない）
        self.assertAllow("ls $(echo hi) #'")
        self.assertAllow("ls `echo hi` #'")

    def test_h6_max_subst_depth_boundary_degraded_deny(self):
        # T-H6i（§9 テスト観点(3)）: 正常経路の既存テスト
        # test_ansi_c_quote_inside_nested_substitution_all_depths_deny と対に
        # なる degraded 版。degraded の入口（末尾 ` #'`）から
        # MAX_SUBST_DEPTH(3) の境界・その先の深さ4まで、`depth` が
        # find_violation → degraded_violation → subst_violation と正しく
        # 伝播し続けることを固定する（find_violation の呼び出し側1行の修正が
        # 無いと、ネストのたびに depth が 0 へリセットされ、打ち切りが
        # 効かないまま無限に近い再帰が発生しうる）
        target = "rm docs/SPEC.md"
        wrapped = target
        self.assertDeny("ls $(%s) #'" % wrapped)                       # depth0
        for depth in range(1, 5):
            wrapped = "echo $(%s)" % wrapped
            with self.subTest(depth=depth):
                self.assertDeny("ls $(%s) #'" % wrapped)

    def test_h6_process_substitution_used_as_redirect_target_deny(self):
        # T-H6j（AC3 新規誤deny Category 2・設計書§9）: プロセス置換が
        # リダイレクト先に使われる形の副次的な closure。書き込みの実態が
        # あるため誤denyではないが、チケットの repro 列挙には無い形として
        # 明記・固定する
        self.assertDeny("echo x > >(tee docs/SPEC.md) #'")

    def test_h6_category3_comment_embedded_substitution_under_guarded_cwd_deny(
            self):
        # T-H6k（AC3 新規誤deny Category 3・要固定・設計書§6・§9）: 保護対象
        # cwd 下で、既に degraded な入力の `#` コメント内に、閉じている置換
        # （head が ALLOWED_HEADS に無い。`$(date)` ／ `` `whoami` ``）が
        # 書かれているだけの形。**旧実装（H6以前）ではこの2形は allow だった**
        # （`ls` が ALLOWED_HEADS かつ CWD_SAFE_HEADS のため、置換の中身は
        # 単なる引数語として埋もれていた。旧実装のコピーに対して実際に
        # allow のままであることを突き合わせ済み）。本チケットの再帰評価に
        # より、置換の内側 "date"／"whoami" の head が ALLOWED_HEADS に無く、
        # かつ cwd が保護対象配下であるため新たに deny になる
        self.assertDeny("cd tickets/active && ls file # via $(date) #'")
        self.assertDeny("cd tickets/active && ls file # via `whoami` #'")

    def test_h6_category3_without_guarded_cwd_stays_allow(self):
        # T-H6l（対照）: 保護対象 cwd が無ければ、同じコメント埋め込み置換は
        # 引き続き allow である（Category 3 は「保護対象 cwd 下」限定の形で
        # あり、日常読み取り70件相当（cwd を伴わない）には影響しないことの
        # 固定）
        self.assertAllow("ls file # via $(date) #'")

    # --- KLK-024: エスケープされたネストのバッククォート --------------------
    # investigator調査（docs/reports/KLK-024/investigation.md）に基づく。
    # `_take_backtick` がバッククォート内容確定時の1段階アンエスケープを
    # 実装していなかったため、エスケープされたネストのバッククォート
    # （`` `echo \`rm ...\`` ``）内側の書き込みが正常経路（degraded非経由）
    # でも allow になっていた。境界探索（`_skip_backtick`/`_skip_balanced`）
    # は変更していない ---

    def test_klk024_escaped_nested_backtick_write_vector_deny(self):
        # T-KLK024a（AC1）: チケット再現手順1。保護対象2種
        # （docs/SPEC.md・tickets/active/*.md）双方で成立することを固定する
        for target in ("docs/SPEC.md", "tickets/active/APP-001.md"):
            with self.subTest(target=target):
                self.assertDeny(
                    "ls %s" % _nested_backtick_command(2, "rm %s" % target))

    def test_klk024_contrast_dollar_paren_and_plain_backtick_deny(self):
        # T-KLK024b（AC2）: チケット再現手順2・3（対照）。本チケットの修正で
        # 判定が変わらないことの固定
        self.assertDeny("ls $(echo `rm docs/SPEC.md`)")
        self.assertDeny("ls `rm docs/SPEC.md`")

    def test_klk024_multi_level_nested_backtick_deny(self):
        # T-KLK024c（多段ネストへの一般化・設計書§3-4-1）: 2〜5階層
        # （MAX_SUBST_DEPTH=3 の境界とその先の深さ1つ分を含む）。depth=4・5は
        # subst_violation の保守的な深さ打ち切りで deny になる
        # （test_h6_max_subst_depth_boundary_degraded_deny と同型の境界）。
        # depth3の具体形は実装時に実機bashで手動検証済み（実装ノート参照）
        for depth in range(2, 6):
            with self.subTest(depth=depth):
                self.assertDeny("ls %s" % _nested_backtick_command(depth))

    def test_klk024_degraded_path_shares_fix_deny(self):
        # T-KLK024d（AC6の実証）: `_extract_degraded_substs` は
        # `_take_backtick` を共有呼び出しするため、本チケットの修正1箇所が
        # degraded 経路にも同時に適用されることを実機的に固定する。末尾に
        # `#'`（未閉じクォート）を付与して degraded を誘発する
        # （KLK-014のT-H6系と同型の誘発形）
        self.assertDeny(
            "ls %s #'" % _nested_backtick_command(2, "rm docs/SPEC.md"))

    def test_klk024_lone_escaped_backtick_false_deny_budget_allow(self):
        # T-KLK024e（AC3 誤deny予算）: ネストしていない単独の `` \` ``
        # （対応するバッククォートが無い）は実機bashでもリテラル解釈のままで
        # あり、`_take_backtick` を一度も起動しない（分岐3の汎用エスケープが
        # 消費するだけ）。本チケットの修正で新たに deny にならないことの固定
        self.assertAllow(
            "echo \\`not a real subst tickets/active/APP-001.md")

    def test_klk024_readonly_backtick_substitution_regression_allow(self):
        # T-KLK024f（AC3・AC4 回帰）: 既存 test_backtick_readonly_substitution_
        # allow はバッククォート内側にバックスラッシュを含まないため
        # `_unescape_backtick_body` は no-op であり、本チケットの修正後も
        # allow のままであることの明示固定（既存テストの再確認）
        self.assertAllow("echo `date +%Y` tickets/active/APP-001.md")
        self.assertAllow("echo `echo $(echo hi)` tickets/active/APP-001.md")

    def test_klk024_unescape_backtick_body_unit_boundary(self):
        # T-KLK024g（設計書§9「テスト観点」: `_unescape_backtick_body` の単体
        # 境界。純粋関数のため hook を経由せず直接呼び出す）。tester が追加
        # （T-KLK024a〜f は hook 経由の E2E のみで、この純粋関数を直接
        # 呼ぶ単体テストが無かったため）。アンエスケープ対象3種
        # （`` \` ``・`\$`・`\\`）を正しく変換する入力と、対象外の `\X`
        # （`\;`・`\ `（バックスラッシュ+空白）・`\`+改行）をそのまま残す
        # 入力を、それぞれ最低2形ずつ固定する
        unescape = guard._unescape_backtick_body

        # 対象1: `` \` `` -> `` ` ``
        self.assertEqual(unescape(r"echo \`date\`"), "echo `date`")
        self.assertEqual(unescape(r"\`\`"), "``")
        # 対象2: `\$` -> `$`
        self.assertEqual(unescape(r"echo \$HOME"), "echo $HOME")
        self.assertEqual(unescape(r"\$\$"), "$$")
        # 対象3: `\\` -> `\`
        self.assertEqual(unescape(r"a\\b"), "a\\b")
        self.assertEqual(unescape(r"\\\\"), "\\\\")

        # 対象外1: `\;`（そのまま残る＝no-op）
        for text in (r"a\;b", r"find . \; ok"):
            with self.subTest(text=text):
                self.assertEqual(unescape(text), text)
        # 対象外2: `\ `（バックスラッシュ+空白。そのまま残る＝no-op）
        for text in (r"a\ b", r"echo\ hi"):
            with self.subTest(text=text):
                self.assertEqual(unescape(text), text)
        # 対象外3: `\`+改行（行継続の生テキスト。そのまま残る＝no-op。
        # test_line_continuation_inside_substitution_is_command_context の
        # E2E 経路（`` `ls #\ +改行+ rm docs/SPEC.md` ``）と同型の負例を
        # 純粋関数として直接固定する）
        for text in ("a\\\nb", "echo x\\\ny"):
            with self.subTest(text=text):
                self.assertEqual(unescape(text), text)

    # --- KLK-029: 単体境界（設計書§9「テスト観点」・純粋関数・モック不要）---
    # INVENTORY_CASES は find_violation() 経由の end-to-end 固定であり、
    # unescape_program_backslashes / _is_guarded_path_component 自体の
    # 挙動（1文字単位の畳み込み・basename 完全一致との差分）は直接検証して
    # いなかった。tester round1 でこのギャップを検出し、下記3形を追加する
    # （test_docs_reports_path_not_mentioned_as_guarded 等、既存の
    # guard.<関数> 直接呼び出しスタイルに合わせる）。

    def test_klk029_unescape_program_backslashes_folds_one_char_at_a_time(
            self):
        # \X -> X を1文字単位で畳み込む（デリミタが / であるかに関わらず、
        # バックスラッシュ直後の1文字を一様に畳み込む。§4-1）
        escaped_slash = "docs" + chr(92) + "/" + "SPEC" + "." + "md"
        self.assertEqual(
            guard.unescape_program_backslashes(escaped_slash),
            "docs" + "/" + "SPEC" + "." + "md")
        # 複数箇所・スラッシュ以外の任意文字でも同様に1文字ずつ畳み込む
        arbitrary = "a" + chr(92) + "q" + "b" + chr(92) + "z" + "c"
        self.assertEqual(
            guard.unescape_program_backslashes(arbitrary), "aqbzc")
        # バックスラッシュを含まない入力はそのまま（早期リターン）
        self.assertEqual(
            guard.unescape_program_backslashes("no-backslash-here"),
            "no-backslash-here")

    def test_klk029_unescape_program_backslashes_folds_escaped_backslash_itself(
            self):
        # `\\`（エスケープされたバックスラッシュ自身）は1文字の `\` へ畳み込む
        two_backslashes = chr(92) * 2
        self.assertEqual(
            guard.unescape_program_backslashes(two_backslashes), chr(92))
        # 連続する2組（4文字）は左から非重複に畳み込まれ2文字の `\` になる
        four_backslashes = chr(92) * 4
        self.assertEqual(
            guard.unescape_program_backslashes(four_backslashes),
            chr(92) * 2)

    def test_klk029_is_guarded_path_component_catches_component_fusion(self):
        # _is_guarded_path は basename **完全一致**のため、sed の /e フラグが
        # 融合した候補 "docs/SPEC.md/e"（basename="e"）を拾えない。
        # _is_guarded_path_component は `/` 区切り成分のいずれかへの一致で
        # 判定するため、この融合形を拾えることを固定する（§3 設計初期案の
        # 誤り訂正の核心・_is_guarded_path との差分そのもの）
        fused = "docs" + "/" + "SPEC" + "." + "md" + "/e"
        self.assertTrue(guard._is_guarded_path_component(fused))
        self.assertFalse(guard._is_guarded_path(fused))
        # tickets/active・tickets/done は元々部分文字列判定のため、融合が
        # あっても両関数とも一致する（変更していないことの対照）
        fused_tickets = "tickets" + "/" + "active" + "/APP-001.md"
        self.assertTrue(guard._is_guarded_path_component(fused_tickets))
        self.assertTrue(guard._is_guarded_path(fused_tickets))

    # --- KLK-018: シェル展開（ブレース展開・分断glob）による保護対象パスの
    # 分断への対応（設計書 docs/designs/KLK-018.md §9 AC1・AC2・AC4）。
    # INVENTORY_CASES の INV-SH-07・09 も allow → deny へ更新済み（AC6）。

    def test_klk018_brace_expansion_simple_deny(self):
        # AC1: 単純なブレース展開（investigator実機検証・チケット再現手順1）
        self.assertDeny("rm tickets/{active,done}/APP-001.md")
        self.assertDeny("rm docs/{SPEC,OTHER}.md")

    def test_klk018_brace_expansion_direct_product_deny(self):
        # AC1: 直積（隣接する2つ以上の {...}）。investigator実機検証と同型
        # （bash: tickets/{acti,don}{ve,e}/... -> active/actie/donve/done）
        self.assertDeny("rm tickets/{acti,don}{ve,e}/APP-001.md")

    def test_klk018_brace_expansion_nested_deny(self):
        # AC1: 入れ子形（外側のカンマの1要素がさらに {} を持つ）
        self.assertDeny("rm tickets/{a,{active,x}}/APP-001.md")

    def test_klk018_brace_expansion_no_comma_stays_literal_allow(self):
        # AC1 の裏付け: カンマの無い {word} は bash も展開しないため、
        # 保護対象と無関係なブレースを含む日常コマンドを誤denyしない
        # （AC4 の固定 allow ケースの1つ）
        self.assertAllow("ls file{1,2}.txt")

    def test_klk018_fragmented_glob_deny(self):
        # AC2: 分断 glob（*・?・[...]）。tickets/active 側
        self.assertDeny("rm tickets/acti*e/APP-001.md")
        self.assertDeny("rm tickets/activ?/APP-001.md")
        self.assertDeny("rm tickets/activ[e]/APP-001.md")

    def test_klk018_fragmented_glob_write_target_deny(self):
        # AC2 (N3): guarded_write_target 経由（sort -o の値がブレース展開・
        # 分断globで保護対象と判定される形）
        self.assertDeny("sort -o tickets/acti*e/out.md in.md")

    def test_klk018_fragmented_glob_spec_side_read_allow(self):
        # AC2 で例示された "cat docs/SPEC*.md"（SPEC.md側）は、guarded_paths_
        # after_shell_expansion が "docs/SPEC.md" を保護対象として検出する
        # （guard._guarded_paths_from_expanded で確認済み）が、cat は
        # ALLOWED_HEADS の中でも追加規則を持たない読み取り専用 head であり、
        # 既存の "cat tickets/active/APP-001.md"（test_read_commands_allow）
        # と同じ理由で常に allow のままである（本チケットは head 単位の
        # 判定を変更しないため、この対称性は変わらない）。設計書 §9 AC2 の
        # 例示文言は「言及ゲートが検出できること」を指しており、head が
        # 読み取り専用であるため最終判定は allow のまま——という点を本テストで
        # 明示的に固定する（deny 化される head 側の同型確認は
        # test_klk018_erroneous_deny_budget_allow の対照ケースを参照）。
        self.assertAllow("cat docs/SPEC*.md")
        # 書き込み系 head（rm）に差し替えると同じ分断globが正しく deny に
        # なることを対照として固定する
        self.assertDeny("rm docs/SPEC*.md")

    def test_klk018_degraded_mode_fragmented_glob_deny(self):
        # AC2: degraded mode（未閉じクォート）でも正常経路と対称に deny する
        # （英文コメントの "don't" が未閉じシングルクォートを誘発する形。
        # 既存の INV-SH パターンと同型の誘発）
        self.assertDeny("rm tickets/acti*e/APP-001.md # don't")

    def test_klk018_erroneous_deny_budget_allow(self):
        # AC4: 誤deny予算の固定 allow ケース。tickets/ を一切含まない日常の
        # awk/cut/sort/grep のプログラム・オプション文字列（{}・,・[...] を
        # 含むが保護対象とは無関係）と、保護対象 cwd 下の読み取り専用 awk
        # （T-H2f系の再固定）が新たに誤denyにならないことを固定する
        self.assertAllow('awk \'BEGIN{FS=","}{print $1,$2}\' file')
        self.assertAllow("cut -f1,2 -d, file")
        self.assertAllow("sort -k1,2 file")
        self.assertAllow("grep -E '[0-9]{3}' file")
        self.assertAllow("cd tickets/active && awk 'NR>1 {print}' in.txt")
        self.assertAllow("ls file{1,2}.txt")

    # --- KLK-018: MAX_BRACE_DEPTH／MAX_BRACE_COMBINATIONS 上限到達時の
    # フォールバック分岐（設計書 §4-1・§6。tester申し送り＝implementerの
    # Remaining Risksで境界値テスト未追加と明記されていた項目）。
    # 上限超過時は保護対象と無関係な内容でも「一致し得る」ものとして安全側
    # （deny）に倒すため、tickets/ を一切含まない語でも非ホワイトリスト
    # head と組み合わせると deny になる。これは設計書§9 AC4のN1〜N4の
    # 文言（「保護対象パスとなる語を含み」）を字面上は満たさない新しい
    # deny 経路であり、reviewerに判断を委ねるためテストで実際の挙動を
    # 固定する（実測値は本テスト作成時にguard._brace_combination_countで
    # 事前確認済み）。

    def test_klk018_brace_depth_within_limit_allow(self):
        # ネスト深さ4（MAX_BRACE_DEPTH と同値）は上限内であり、通常の
        # expand_braces による展開結果（"axb"/"ayb"）はどちらも保護対象
        # ではないため allow のまま（フォールバックは発動しない）
        self.assertAllow("rm a{{{{x,y}}}}b")

    def test_klk018_brace_depth_exceeded_denies_conservatively(self):
        # ネスト深さ5（MAX_BRACE_DEPTH超）は _brace_combination_count が
        # depth ガードにより無条件で MAX_BRACE_COMBINATIONS+1 を返すため
        # フォールバックに入り、tickets/ を一切含まない候補でも
        # 「一致し得る」ものとして扱われる。非ホワイトリストhead（rm）と
        # 組み合わせると deny になることを固定する
        self.assertDeny("rm a{{{{{x,y}}}}}b")

    def test_klk018_brace_combinations_within_limit_allow(self):
        # 直積の組み合わせ数243（MAX_BRACE_COMBINATIONS=512未満）は
        # フォールバックが発動せず、実際に展開して非保護対象と判定され allow
        self.assertAllow("rm a{1,2,3}{1,2,3}{1,2,3}{1,2,3}{1,2,3}b")

    def test_klk018_brace_combinations_exceeded_denies_conservatively(self):
        # 直積の組み合わせ数729（MAX_BRACE_COMBINATIONS超）はフォールバック
        # により、tickets/ を一切含まない候補でも「一致し得る」ものとして
        # 扱われ、非ホワイトリストhead（rm）と組み合わせると deny になる
        self.assertDeny("rm a{1,2,3}{1,2,3}{1,2,3}{1,2,3}{1,2,3}{1,2,3}b")

    # --- KLK-018 差し戻し: 隣接ブレースの RecursionError 回帰（reviewer指摘）
    #
    # `_brace_combination_count`／`expand_braces` は非入れ子で隣接する
    # ブレース群が大量に連続すると depth が進まないため、隣接数に比例した
    # Python コールスタックを消費し RecursionError になっていた（実測:
    # 隣接997個・sys.getrecursionlimit()=1000）。この RecursionError は
    # main() の広域 except Exception: allow() に捕捉され、deny 方向ではなく
    # allow 方向へフェイルオープンしていた（設計書§4-1 P8「曖昧な位置は
    # 安全側=deny」に反する）。修正後は事前チェック（MAX_BRACE_CHAR_COUNT）
    # と try/except RecursionError の2段で安全側フォールバックへ倒す。
    # 以下は隣接900〜1500個規模で RecursionError が発生しないこと・deny に
    # 倒れることを固定する。

    def test_klk018_adjacent_braces_regression_n1000_denies_conservatively(self):
        # 隣接1000個（実測の閾値997をまたぐ規模）。tickets/ を一切含まない
        # 候補でもフォールバックにより「一致し得る」ものとして扱われ、
        # 非ホワイトリストhead（rm）と組み合わせると deny になる。修正前は
        # RecursionError が main() の広域 except で allow に化けていた
        candidate = "a" + "{x,y}" * 1000 + "b"
        self.assertDeny("rm " + candidate)

    def test_klk018_adjacent_braces_regression_n1500_denies_conservatively(self):
        # 隣接1500個（申し送りの上限規模）でも同様に RecursionError を起こさず
        # deny に倒れることを固定する
        candidate = "a" + "{x,y}" * 1500 + "b"
        self.assertDeny("rm " + candidate)

    def test_klk018_adjacent_braces_regression_allow_symmetry(self):
        # 同じ隣接1500個の候補でも、先頭コマンドが読み取り専用（cat）で
        # tickets/ を一切含まない場合は従来どおり allow のまま（フォール
        # バックは「保護対象パスの候補とみなす」だけであり、書き込み判定自体
        # を変えないことを確認する。deny 側の
        # test_klk018_adjacent_braces_regression_n1500_denies_conservatively
        # との対照ケース）
        candidate = "a" + "{x,y}" * 1500 + "b"
        self.assertAllow("cat " + candidate)

    def test_klk018_adjacent_braces_regression_does_not_mask_existing_deny(self):
        # reviewer指摘の核心シナリオ: 既存の明確な deny 対象
        # （tickets/active/APP-001.md への rm）と同一コマンド文字列中に
        # 大量の隣接ブレースを含めても、RecursionError 経由で丸ごと allow に
        # 転じてはならない（誤りの向きは常に allow=危険な方向という指摘への
        # 固定）
        candidate = "a" + "{x,y}" * 1200 + "b"
        self.assertDeny("rm tickets/active/APP-001.md " + candidate)

    def test_klk018_adjacent_braces_regression_does_not_mask_existing_deny_blob_first(self):
        # tester再検証で追加（KLK-018 再差し戻し検証）: 上記
        # test_..._does_not_mask_existing_deny は「デコイの隣接ブレース語」を
        # 既存 deny 対象の語より**後ろ**に置いているため、
        # mentions_guarded_expanded 内の any() が先に deny 対象語で True を
        # 返して短絡し、隣接ブレース語（＝RecursionError を起こしうる語）を
        # 実際には一度も評価しない。そのため当該テストは修正前の
        # バグ入りコードでも（短絡のおかげで）偶然 pass してしまい、
        # reviewerが指摘した「masking」シナリオを実際には判別できていな
        # かった（tester がpre-fixコードの複製に対する独立PoCで実証確認
        # 済み）。本テストは語順を逆転させ、隣接ブレース語を既存 deny 対象語
        # より**先**に置くことで、修正前コードなら RecursionError が deny
        # 対象語の評価前に発生し allow へフェイルオープンする経路を実際に
        # 通過させ、修正後コードが deny を維持することを固定する
        candidate = "a" + "{x,y}" * 1200 + "b"
        self.assertDeny("rm " + candidate + " tickets/active/APP-001.md")

    def test_klk018_adjacent_braces_regression_no_comma_literal_denies_conservatively(self):
        # tester再検証で追加（KLK-018 再差し戻し検証）: 既存の回帰テスト4件は
        # いずれも "{x,y}"（カンマ有り＝直積で combinations が急増する形）の
        # 隣接連続のみを対象にしている。カンマ無しの隣接ブレース（例:
        # "{x}"。bash は展開せずリテラルのまま扱う）は
        # _brace_combination_count が各グループで parts<2 の分岐（乗算せず
        # 1のまま）を通るため、旧実装でも MAX_BRACE_COMBINATIONS 超過に
        # よる安全側フォールバックには**そもそも到達し得ない**独立した形
        # だった（reviewerが指摘した「隣接兄弟ブレース数」次元がカンマの
        # 有無に関わらず独立して壊れうることの確認）。修正後の
        # MAX_BRACE_CHAR_COUNT はカンマの有無・combinations の値に関係なく
        # `{` の出現数のみで判定するため、この形でも RecursionError を
        # 起こさず deny に倒れることを固定する（tester がpre-fixコードの
        # 複製に対する独立PoCで、旧実装がこの形でも allow に化けることを
        # 確認済み）
        candidate = "a" + "{x}" * 1000 + "b"
        self.assertDeny("rm " + candidate)

    # --- KLK-019: シェル制御構文（for/while/until/if/elif/do/then/else/
    # case）の誤deny解消（設計書 docs/designs/KLK-019.md §9）。INV-CTRL-*
    # は上記 INVENTORY_CASES で機械的に固定済みであり、以下は AC の各観点
    # ごとに意図を明示した専用の回帰ガードを追加する。

    def test_klk019_ac1_read_only_control_structures_allow(self):
        # AC1: 読み取り専用の for/while/if/case/until がいずれも allow。
        # `;` 区切り形（本テスト）と改行区切り形（次のテスト）の両方を固定する
        self.assertAllow("for f in tickets/active/*.md; do echo $f; done")
        self.assertAllow(
            "while read l; do echo $l; done < tickets/active/APP-001.md")
        self.assertAllow("if [ -f tickets/active/APP-001.md ]; then echo yes; fi")
        self.assertAllow("case x in *) cat tickets/active/APP-001.md ;; esac")
        self.assertAllow(
            "until false; do cat tickets/active/APP-001.md; break; done")

    def test_klk019_ac1_read_only_control_structures_newline_form_allow(self):
        # AC1: split_statements は改行を `;` と同一視するため、`;` 区切り形と
        # 改行区切り形で結果が一致するはずであることをテストで固定する
        self.assertAllow(
            "for f in tickets/active/*.md\ndo echo $f\ndone")
        self.assertAllow(
            "while read l\ndo echo $l\ndone < tickets/active/APP-001.md")
        self.assertAllow(
            "if [ -f tickets/active/APP-001.md ]\nthen echo yes\nfi")
        self.assertAllow(
            "case x in *) cat tickets/active/APP-001.md ;;\nesac")
        self.assertAllow(
            "until false\ndo cat tickets/active/APP-001.md\nbreak\ndone")

    def test_klk019_ac2_write_via_loop_var_denies(self):
        # AC2: ループ変数経由の書き込み（rm・sed -i・リダイレクト）はいずれも deny
        self.assertDeny("for f in tickets/active/*.md; do rm $f; done")
        self.assertDeny(
            "for f in tickets/active/*.md; do sed -i 's/a/b/' $f; done")
        self.assertDeny("for f in tickets/active/*.md; do echo x > $f; done")

    def test_klk019_ac2_write_via_literal_path_without_loop_var_denies(self):
        # AC2: ループ変数を介さないリテラルパスの書き込みは Phase1 の
        # ALLOWED_HEADS 判定だけで denied のままであることを確認する
        # （Phase2 の guarded_loop_vars が無くても deny される経路）
        self.assertDeny(
            "while true; do rm tickets/active/APP-001.md; break; done")
        self.assertDeny(
            "for i in 1 2 3; do rm tickets/active/APP-001.md; done")

    def test_klk019_ac3_loop_var_reference_gate_is_conservative(self):
        # AC3: ループ変数への参照は「読み取りコマンドの引数であっても」
        # ゲートを開くが、最終的な許可・不許可は既存の ALLOWED_HEADS 判定に
        # 委ねる（cat は許可・rm は不許可のまま）
        self.assertAllow("for f in tickets/active/*.md; do cat $f; done")
        self.assertAllow("for f in tickets/active/*.md; do echo $f; done")
        self.assertDeny("for f in tickets/active/*.md; do rm $f; done")

    def test_klk019_inv_sh_11_unaffected_by_loop_var_separation(self):
        # §3方針5: guarded_vars（前置き代入の追跡）と guarded_loop_vars
        # （for ループ変数の追跡）は完全に分離した別集合であり、既存の
        # INV-SH-11（f=path; rm $f が恒久的に allow）の挙動を一切変えない
        self.assertAllow("f=tickets/active/APP-001.md; rm $f")

    def test_klk019_r_ctrl4_if_cd_then_rm_denies_via_cwd_tracking(self):
        # R-CTRL4（deny側）: if の条件節で cd した場合も、statement_violation
        # の ALLOWED_HEADS 判定と find_violation の cwd 追跡の両方が
        # control_stripped_segments を共有しているため、then 節の cwd 相対
        # 書き込みが正しく検出される
        self.assertDeny("if cd tickets/active; then rm APP-001.md; fi")

    def test_klk019_r_ctrl4_if_cd_then_cat_allows_via_cwd_tracking(self):
        # R-CTRL4（allow側）: 同じ cwd 追跡経路で、CWD_SAFE_HEADS 収載の
        # 読み取り専用コマンド（cat）は許可のまま
        self.assertAllow("if cd tickets/active; then cat APP-001.md; fi")

    def test_klk019_c_style_for_and_multi_pattern_case_fallback_deny(self):
        # §3方針2: C形式for・caseの複数パターン（`a|b)`）・in欠落のcaseは
        # 構造を確定できないため strip_control_prefix が None を返し、
        # 元の statement で判定する保守側フォールバックへ倒れる
        self.assertDeny(
            "for ((i=0; i<3; i++)); do rm tickets/active/APP-001.md; done")
        self.assertAllow("for ((i=0; i<3; i++)); do echo $i; done")
        self.assertDeny("case x in a|b) cat tickets/active/APP-001.md ;; esac")
        self.assertDeny("case x *) rm tickets/active/APP-001.md ;; esac")

    def test_klk019_nested_control_structures_write_at_deepest_level_denies(self):
        # テスト観点(1): 入れ子（for内if等）で最深部のみ書き込みがある場合に
        # 正しく deny されるか
        self.assertAllow(
            "for f in tickets/active/*.md; do if true; then cat $f; fi; done")
        self.assertDeny(
            "for f in tickets/active/*.md; do if true; then rm $f; fi; done")

    def test_klk019_closing_keyword_trailing_redirect_allow(self):
        # 実装時の補正（R-CTRL3の前提の見直し）: `done`/`fi`/`esac` の直後に
        # 区切り無しでリダイレクトが続く形（`done < FILE`）は bash 文法上
        # 有効であり、この場合「閉じキーワード＋リダイレクト」が1ステート
        # メントになる。リダイレクト先が保護対象を言及していても、`<` は
        # 読み取り専用（redirect_in）であり書き込みを発生させないため allow
        # のままであることを固定する（AC1 の while-read 例の回帰ガード）
        self.assertAllow(
            "while read l; do echo $l; done < tickets/active/APP-001.md")
        self.assertAllow("if true; then echo x; fi < tickets/active/APP-001.md")
        self.assertAllow(
            "case x in *) echo hi ;; esac < tickets/active/APP-001.md")

    def test_klk019_closing_keyword_pipe_write_still_denies(self):
        # 上記の補正が新しい許可経路を作らないことの安全性確認: 閉じ
        # キーワードの直後がリダイレクトではなくパイプで実コマンドへ続く形
        # （`done | rm ...`）は、そのコマンドが独立したパイプ区間として
        # 引き続き ALLOWED_HEADS 判定の対象になるため deny のまま
        self.assertDeny(
            "while true; do echo hi; done | rm tickets/active/APP-001.md")
        self.assertAllow(
            "while true; do echo hi; done | cat tickets/active/APP-001.md")

    def test_klk019_standalone_closing_keywords_allow(self):
        # R-CTRL3: 単独の fi/done/esac のみのステートメントは引数を取らない
        # ため言及ゲートが立たず、allow のまま（クラッシュしないことも含めて
        # 固定する）
        self.assertAllow("fi")
        self.assertAllow("done")
        self.assertAllow("esac")

    def test_klk019_erroneous_deny_budget_allow(self):
        # AC6: 誤deny予算の逆方向確認。N1〜N6に対応する代表例が新たに
        # allow へ転じることを固定する（列挙外の新規allowが無いことは
        # INVENTORY_CASES・LEGACY_DENY_COMMANDS の全件回帰と本ファイルの
        # 他の test_klk019_* が担保する）
        self.assertAllow(  # N1
            "for f in tickets/active/*.md; do echo $f; done")
        self.assertAllow(  # N2
            "while true; do cat tickets/active/APP-001.md; break; done")
        self.assertAllow(  # N3
            "if false; then echo a; elif true; then "
            "cat tickets/active/APP-001.md; else echo b; fi")
        self.assertAllow(  # N4
            "case x in *.md) cat tickets/active/APP-001.md ;; esac")
        self.assertAllow(  # N5（入れ子）
            "for f in tickets/active/*.md; do case $f in "
            "*) cat $f ;; esac; done")
        self.assertAllow(  # N6（cd 追跡）
            "if cd tickets/active; then cat APP-001.md; fi")
        # 対象外（引き続き deny）: C形式for・caseの複数パターン・ループ変数
        # 経由の書き込み
        self.assertDeny(
            "for ((i=0; i<3; i++)); do rm tickets/active/APP-001.md; done")
        self.assertDeny("case x in a|b) cat tickets/active/APP-001.md ;; esac")
        self.assertDeny("for f in tickets/active/*.md; do rm $f; done")


if __name__ == "__main__":
    unittest.main()
