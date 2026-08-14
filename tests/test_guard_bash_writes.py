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
    # --- 旧版でも allow だったが本改訂で閉じた形（維持規律3が許容する追加） ---
    "sort -o tickets/active/APP-001.md in.md",
    "sort --output=docs/SPEC.md x.md",
    "uniq in.md tickets/active/APP-001.md",
    "find tickets/active -name '*.md' -fprint0 /tmp/x",
]


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

    # --- KLK-010 Phase 5: 固定リスト回帰ガード（設計書§4-7・D5） ---

    def test_legacy_deny_commands_all_still_deny(self):
        # T-LEGACY: 旧版が deny していた集合が allow へ転じていないことを
        # 一括で固定する。git・ネットワークに依存しない hermetic な回帰ガード
        for command in LEGACY_DENY_COMMANDS:
            with self.subTest(command=command):
                self.assertDeny(command)


if __name__ == "__main__":
    unittest.main()
