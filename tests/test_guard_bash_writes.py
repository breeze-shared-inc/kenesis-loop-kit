"""guard_bash_writes.py（PreToolUse・Bash）のテスト"""
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _util  # noqa: E402


def payload(command):
    return {"tool_name": "Bash", "tool_input": {"command": command}}


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


if __name__ == "__main__":
    unittest.main()
