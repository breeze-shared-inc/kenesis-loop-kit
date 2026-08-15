"""guard_bash_writes.py（PreToolUse・Bash）のテスト"""
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _util  # noqa: E402


def payload(command):
    return {"tool_name": "Bash", "tool_input": {"command": command}}


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
    # --- sed のプログラム内構文（§3-9 ③列。この次元は第4版でも
    # ブラックリストのまま＝設計書 §6 R25） ---
    ("INV-SED-01", "s/a/b/w FILE",
     "sed 's/a/b/w tickets/active/APP-001.md' in.md", "deny"),
    ("INV-SED-02", "/re/W FILE", "sed '/x/W docs/SPEC.md' in.md", "deny"),
    ("INV-SED-03", "-i 全表記", "sed -i 's/a/b/' tickets/active/APP-001.md",
     "deny"),
    ("INV-SED-04", "保護対象 cwd 下の w REL",
     "cd tickets/active && sed 's/a/b/w APP-001.md' in.md", "deny"),
    ("INV-SED-05", "-f SCRIPT（プログラム不可視・**未対応**・別チケット）",
     "sed -f script.sed tickets/active/APP-001.md", "allow"),
    ("INV-SED-06", "GNU sed の s///e（**未対応**・別チケット）",
     "sed 's/a/b/e' tickets/active/APP-001.md", "allow"),
    ("INV-SED-07", "GNU sed の e コマンド（**未対応**・別チケット）",
     "sed '1e cat /etc/hosts' tickets/active/APP-001.md", "allow"),
    ("INV-SED-08", "-n '1,5p'（読み取り・意図的に allow）",
     "sed -n '1,5p' tickets/active/APP-001.md", "allow"),
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
    ("INV-SH-07", "ブレース展開による分断（**未対応**・別チケット）",
     "rm tickets/{active,done}/APP-001.md", "allow"),
    ("INV-SH-08", "glob（保護対象ディレクトリが素で残り証拠になる形）",
     "rm tickets/active/*.md", "deny"),
    ("INV-SH-09", "glob（パス中に * が入り分断される形・**未対応**）",
     "rm tickets/acti*e/APP-001.md", "allow"),
    ("INV-SH-10", "チルダ展開（残りのパスが証拠として残る）",
     "rm ~/kit/tickets/active/APP-001.md", "deny"),
    ("INV-SH-11", "パラメータ展開（値は不可視＝構造的限界・**未対応**）",
     "f=tickets/active/APP-001.md; rm $f", "allow"),
    ("INV-SH-12", "算術展開（$( としてコマンド置換扱い＝保守側の副作用）",
     "echo $((1+2)) && cat tickets/active/APP-001.md", "allow"),
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

    # --- fail-open ---

    def test_non_bash_tool_allow(self):
        out = self.run_guard({"tool_name": "Write",
                              "tool_input": {"file_path": "x"}})
        self.assertIsNone(out)

    def test_broken_stdin_allow(self):
        rc, out, _ = _util.run_script(_util.GUARD_BASH, "not json")
        self.assertEqual(rc, 0)
        self.assertIsNone(_util.hook_output(out))

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


if __name__ == "__main__":
    unittest.main()
