"""_ticket_lib.py の単体テスト（検証ルールの中核）"""
import io
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _util  # noqa: E402

sys.path.insert(0, _util.HOOKS)
import _ticket_lib as lib  # noqa: E402


def frontmatter(*lines):
    """frontmatter だけを持つ最小のチケット本文を組み立てる（パーサのテスト用）。"""
    return "---\n" + "\n".join(lines) + "\n---\n\n# body\n"


class TestParsing(unittest.TestCase):
    def test_parse_valid_frontmatter(self):
        fm = lib.parse_frontmatter(_util.ticket(status="design_done", tti=1))
        self.assertEqual(fm["status"], "design_done")
        self.assertEqual(fm["id"], "APP-001")
        self.assertIsInstance(fm["retry_counts"], dict)
        self.assertEqual(fm["retry_counts"]["tester_to_implementer"], "1")

    def test_no_frontmatter_returns_none(self):
        self.assertIsNone(lib.parse_frontmatter("# just a heading\nno fm"))

    def test_split_frontmatter_body(self):
        _, body = lib.split_frontmatter(_util.ticket())
        self.assertIn("## リトライカウンタ", body)
        self.assertNotIn("status:", body)

    def test_body_retry_table(self):
        _, body = lib.split_frontmatter(_util.ticket(tti=2, rti=1, rtv=0))
        table = lib.parse_body_retry_table(body)
        self.assertEqual(table["tester_to_implementer"], 2)
        self.assertEqual(table["reviewer_to_implementer"], 1)
        self.assertEqual(table["reviewer_to_investigator"], 0)

    # --- KLK-012 AC4: クォート外インラインコメントの除去 ---

    def test_inline_comment_stripped_from_status(self):
        fm = lib.parse_frontmatter(frontmatter("status: todo # 未着手"))
        self.assertEqual(fm["status"], "todo")

    def test_hash_inside_quotes_preserved(self):
        # over-strip の回帰ガード（現状すでに正しい挙動を壊さないこと）
        fm = lib.parse_frontmatter(frontmatter('title: "issue #123 fix"'))
        self.assertEqual(fm["title"], "issue #123 fix")

    def test_hash_inside_single_quotes_preserved(self):
        fm = lib.parse_frontmatter(frontmatter("title: 'issue #123 fix'"))
        self.assertEqual(fm["title"], "issue #123 fix")

    def test_quoted_value_with_trailing_comment(self):
        # コメントを先に除去することで _unquote の既存条件が満たされる
        fm = lib.parse_frontmatter(
            frontmatter('title: "issue #123 fix" # trailing comment'))
        self.assertEqual(fm["title"], "issue #123 fix")

    def test_comment_only_value_opens_nested_map(self):
        fm = lib.parse_frontmatter(frontmatter(
            "retry_counts: # コメント",
            "  tester_to_implementer: 0",
            "  reviewer_to_implementer: 1",
            "  reviewer_to_investigator: 0",
        ))
        self.assertIsInstance(fm["retry_counts"], dict)
        self.assertEqual(fm["retry_counts"]["tester_to_implementer"], "0")
        self.assertEqual(fm["retry_counts"]["reviewer_to_implementer"], "1")
        self.assertEqual(fm["retry_counts"]["reviewer_to_investigator"], "0")

    def test_nested_value_trailing_comment_stripped(self):
        fm = lib.parse_frontmatter(frontmatter(
            "retry_counts:",
            "  tester_to_implementer: 1 # note",
        ))
        self.assertEqual(fm["retry_counts"]["tester_to_implementer"], "1")

    def test_hash_without_preceding_space_preserved(self):
        fm = lib.parse_frontmatter(frontmatter("title: C#sharp"))
        self.assertEqual(fm["title"], "C#sharp")

    def test_unclosed_quote_not_stripped(self):
        # 壊れた入力では「除去しすぎない」安全側へ倒れる
        fm = lib.parse_frontmatter(frontmatter('title: "a # b'))
        self.assertEqual(fm["title"], '"a # b')

    def test_leading_comment_lines_ignored(self):
        fm = lib.parse_frontmatter(frontmatter(
            "# 行頭コメント",
            "status: todo",
        ))
        self.assertEqual(fm, {"status": "todo"})

    def test_standard_ticket_unchanged_by_comment_stripping(self):
        # AC4 回帰: コメントを含まない標準チケットの解釈は不変
        fm = lib.parse_frontmatter(_util.ticket(status="test_passed", tti=2))
        self.assertEqual(fm["status"], "test_passed")
        self.assertEqual(fm["title"], "t")
        self.assertEqual(fm["retry_counts"]["tester_to_implementer"], "2")
        self.assertEqual(lib.validate_schema(fm), [])

    # --- KLK-028 AC1: トップレベルscalarキーのcomment-only値の期待挙動 ---

    def test_scalar_comment_only_value_becomes_none(self):
        # 子行が続かない場合、コメントの有無に関わらずYAML準拠でNoneになる
        # （{}=ネストマップ確定ではない。KLK-012 M3の残課題）
        fm = lib.parse_frontmatter(frontmatter(
            "title: # コメント",
            "status: todo",
        ))
        self.assertIsNone(fm["title"])
        self.assertEqual(fm["status"], "todo")

    def test_scalar_empty_value_without_comment_becomes_none(self):
        # コメントを伴わない空値も同じ規則（子行の有無のみが基準）
        fm = lib.parse_frontmatter(frontmatter(
            "title:",
            "status: todo",
        ))
        self.assertIsNone(fm["title"])

    def test_trailing_comment_only_key_at_end_of_frontmatter_becomes_none(self):
        # current_mapが開いたままfrontmatterが終端に達するケース（ループ後処理の回帰ガード）
        fm = lib.parse_frontmatter(frontmatter(
            "status: todo",
            "title: # コメント",
        ))
        self.assertIsNone(fm["title"])

    def test_blank_line_before_child_still_attaches_to_map(self):
        # 既存の挙動（空行を挟んでもcurrent_mapはリセットされない）が本チケットの
        # 修正で変化しないことを固定する（investigator調査メモ。AC1の対象外だが
        # 同じコードパスを通るため回帰ガードとして残す）
        fm = lib.parse_frontmatter(frontmatter(
            "title: # コメント",
            "",
            "  x: 1",
            "status: todo",
        ))
        self.assertEqual(fm["title"], {"x": "1"})


class TestIsTicket(unittest.TestCase):
    """KLK-004: docs/reports/{ID}/{phase}.md が is_ticket() の対象外であることを検証する
    （tickets/active|done/*.md のみを実チケット扱いする既存境界は変えない）。
    KLK-012 AC1: 正規化と相対形の受理を追加する（絶対形の既存判定は不変）。"""

    def test_docs_reports_path_not_a_ticket(self):
        self.assertFalse(
            lib.is_ticket("/repo/docs/reports/KLK-004/investigation.md"))

    def test_docs_reports_other_phases_not_a_ticket(self):
        for phase in ("implementation", "test-report", "review"):
            self.assertFalse(
                lib.is_ticket("/repo/docs/reports/KLK-004/%s.md" % phase))

    def test_ticket_active_path_still_a_ticket(self):
        self.assertTrue(lib.is_ticket("/repo/tickets/active/KLK-004.md"))

    # --- KLK-012 AC1 ---

    def test_absolute_paths_still_tickets(self):
        self.assertTrue(lib.is_ticket("/repo/tickets/active/APP-001.md"))
        self.assertTrue(lib.is_ticket("/repo/tickets/done/APP-001.md"))

    def test_relative_active_path_is_ticket(self):
        # AC1 の中心ケース: 先頭スラッシュ無しでも取りこぼさない
        self.assertTrue(lib.is_ticket("tickets/active/APP-001.md"))

    def test_relative_done_path_is_ticket(self):
        self.assertTrue(lib.is_ticket("tickets/done/APP-001.md"))

    def test_dot_prefixed_relative_path_is_ticket(self):
        self.assertTrue(lib.is_ticket("./tickets/active/APP-001.md"))

    def test_subdirectory_under_active_is_ticket(self):
        self.assertTrue(lib.is_ticket("tickets/active/sub/APP-001.md"))

    def test_traversal_into_tickets_is_ticket(self):
        self.assertTrue(lib.is_ticket("x/../tickets/active/APP-001.md"))

    def test_traversal_out_of_tickets_is_not_ticket(self):
        # 従来は誤って True（チケットでないファイルへ検証をかけていた）
        self.assertFalse(lib.is_ticket("/repo/tickets/active/../../evil.md"))

    def test_component_boundary_false_positives(self):
        self.assertFalse(lib.is_ticket("mytickets/active/APP-001.md"))
        self.assertFalse(lib.is_ticket("docs/tickets_active/x.md"))

    def test_templates_excluded(self):
        self.assertFalse(lib.is_ticket("tickets/active/Templates/ticket.md"))
        self.assertFalse(lib.is_ticket("/repo/tickets/Templates/t.md"))

    def test_index_excluded(self):
        self.assertFalse(lib.is_ticket("tickets/active/_index.md"))

    def test_non_markdown_excluded(self):
        self.assertFalse(lib.is_ticket("tickets/active/APP-001.txt"))

    def test_backslash_separators_still_supported(self):
        self.assertTrue(lib.is_ticket(r"C:\repo\tickets\active\APP-001.md"))


class TestPayloadHelpers(unittest.TestCase):
    """KLK-012 AC5: hook 入口の入力型正規化ヘルパ"""

    def test_dict_payload_returned(self):
        self.assertEqual(
            lib.read_hook_payload(io.StringIO('{"a": 1}')), {"a": 1})

    def test_non_dict_json_returns_none(self):
        for raw in ("[]", '"x"', "3", "null"):
            self.assertIsNone(lib.read_hook_payload(io.StringIO(raw)), raw)

    def test_broken_json_returns_none(self):
        self.assertIsNone(lib.read_hook_payload(io.StringIO("not json")))

    def test_as_dict_passthrough_and_normalization(self):
        self.assertEqual(lib.as_dict({"a": 1}), {"a": 1})
        self.assertEqual(lib.as_dict([]), {})
        self.assertEqual(lib.as_dict(None), {})
        self.assertEqual(lib.as_dict("x"), {})
        self.assertEqual(lib.as_dict(3), {})


class TestSchema(unittest.TestCase):
    def test_valid_passes(self):
        fm = lib.parse_frontmatter(_util.ticket())
        self.assertEqual(lib.validate_schema(fm), [])

    def test_missing_required_key(self):
        fm = lib.parse_frontmatter(_util.ticket())
        del fm["project"]
        errs = lib.validate_schema(fm)
        self.assertTrue(any("project" in e for e in errs))

    def test_invalid_status(self):
        fm = lib.parse_frontmatter(_util.ticket())
        fm["status"] = "bogus"
        errs = lib.validate_schema(fm)
        self.assertTrue(any("bogus" in e for e in errs))


class TestRetryCounts(unittest.TestCase):
    def test_valid(self):
        fm = lib.parse_frontmatter(_util.ticket(tti=3, rti=2, rtv=1))
        self.assertEqual(lib.validate_retry_counts(fm), [])

    def test_over_cap(self):
        fm = lib.parse_frontmatter(_util.ticket(tti=4))
        errs = lib.validate_retry_counts(fm)
        self.assertTrue(any("上限" in e for e in errs))

    def test_negative(self):
        fm = {"retry_counts": {"tester_to_implementer": -1,
                               "reviewer_to_implementer": 0,
                               "reviewer_to_investigator": 0}}
        errs = lib.validate_retry_counts(fm)
        self.assertTrue(any("負の値" in e for e in errs))

    def test_non_integer(self):
        fm = {"retry_counts": {"tester_to_implementer": "x",
                               "reviewer_to_implementer": 0,
                               "reviewer_to_investigator": 0}}
        errs = lib.validate_retry_counts(fm)
        self.assertTrue(any("整数ではありません" in e for e in errs))

    def test_missing_subkey(self):
        fm = {"retry_counts": {"tester_to_implementer": 0}}
        errs = lib.validate_retry_counts(fm)
        self.assertTrue(any("reviewer_to_implementer" in e for e in errs))

    def test_not_a_mapping(self):
        errs = lib.validate_retry_counts({"retry_counts": "0"})
        self.assertTrue(any("マッピング" in e for e in errs))


class TestTransition(unittest.TestCase):
    def test_forward_ok(self):
        self.assertIsNone(lib.validate_transition("design_done", "implementation_done"))

    def test_illegal_skip(self):
        self.assertIsNotNone(lib.validate_transition("design_done", "done"))

    def test_rollback_tester_fail(self):
        # tester差し戻しは implementation_done 起点（test_passedは合格時のみ）
        self.assertIsNone(lib.validate_transition("implementation_done", "design_done"))

    def test_rollback_reviewer_impl(self):
        self.assertIsNone(lib.validate_transition("test_passed", "design_done"))

    def test_rollback_reviewer_design(self):
        self.assertIsNone(lib.validate_transition("test_passed", "todo"))

    def test_creation_requires_todo(self):
        self.assertIsNone(lib.validate_transition(None, "todo"))
        self.assertIsNotNone(lib.validate_transition(None, "design_done"))

    def test_same_status_allowed(self):
        self.assertIsNone(lib.validate_transition("design_done", "design_done"))

    def test_any_to_blocked(self):
        self.assertIsNone(lib.validate_transition("implementation_done", "blocked"))

    def test_any_to_cancelled(self):
        self.assertIsNone(lib.validate_transition("todo", "cancelled"))

    def test_blocked_resume(self):
        self.assertIsNone(lib.validate_transition("blocked", "design_done"))

    def test_improvement_loop_from_done(self):
        self.assertIsNone(lib.validate_transition("done", "investigation_done"))
        self.assertIsNone(lib.validate_transition("done", "todo"))

    def test_rollback_from_done(self):
        # ロールバック手順: revert実装をtesterから再開（.claude/commands/rollback.md 手順7）
        self.assertIsNone(lib.validate_transition("done", "implementation_done"))
        self.assertIsNotNone(lib.validate_transition("done", "design_done"))

    def test_backward_jump_illegal(self):
        self.assertIsNotNone(lib.validate_transition("implementation_done", "todo"))


class TestMonotonic(unittest.TestCase):
    """L2: カウンタ単調性"""

    def _fm(self, tti):
        return lib.parse_frontmatter(_util.ticket(tti=tti))

    def test_no_prior_ok(self):
        self.assertEqual(lib.validate_retry_monotonic(None, self._fm(0)), [])

    def test_equal_ok(self):
        self.assertEqual(lib.validate_retry_monotonic(self._fm(1), self._fm(1)), [])

    def test_increase_ok(self):
        self.assertEqual(lib.validate_retry_monotonic(self._fm(1), self._fm(2)), [])

    def test_decrease_flagged(self):
        errs = lib.validate_retry_monotonic(self._fm(2), self._fm(1))
        self.assertTrue(any("減少" in e for e in errs))


class TestReconcile(unittest.TestCase):
    """L3: 差し戻し履歴とカウンタの照合"""

    @staticmethod
    def ev(frm, to):
        return {"ticket": "APP-001", "from": frm, "to": to}

    def created_then(self, *transitions):
        evs = [self.ev(None, "todo")]
        for frm, to in transitions:
            evs.append(self.ev(frm, to))
        return evs

    def test_match_tester(self):
        events = self.created_then(("implementation_done", "design_done"))
        rc = {"tester_to_implementer": 1, "reviewer_to_implementer": 0,
              "reviewer_to_investigator": 0}
        self.assertEqual(lib.reconcile_rollbacks(rc, events), [])

    def test_match_reviewer_impl(self):
        events = self.created_then(("test_passed", "design_done"))
        rc = {"tester_to_implementer": 0, "reviewer_to_implementer": 1,
              "reviewer_to_investigator": 0}
        self.assertEqual(lib.reconcile_rollbacks(rc, events), [])

    def test_match_per_category(self):
        # tester差し戻し1回 + reviewer実装差し戻し1回を個別に照合
        events = self.created_then(("implementation_done", "design_done"),
                                   ("test_passed", "design_done"))
        rc = {"tester_to_implementer": 1, "reviewer_to_implementer": 1,
              "reviewer_to_investigator": 0}
        self.assertEqual(lib.reconcile_rollbacks(rc, events), [])

    def test_forgot_increment_flagged(self):
        events = self.created_then(("test_passed", "design_done"))
        rc = {"tester_to_implementer": 0, "reviewer_to_implementer": 0,
              "reviewer_to_investigator": 0}
        errs = lib.reconcile_rollbacks(rc, events)
        self.assertTrue(any("design_done" in e for e in errs))

    def test_wrong_category_flagged(self):
        # tester差し戻しなのに reviewer_impl カウンタを上げている
        # → 遷移元で区別できるため「和」では隠れず、両カテゴリの不一致を検出
        events = self.created_then(("implementation_done", "design_done"))
        rc = {"tester_to_implementer": 0, "reviewer_to_implementer": 1,
              "reviewer_to_investigator": 0}
        errs = lib.reconcile_rollbacks(rc, events)
        self.assertEqual(len(errs), 2)  # tester不足 と reviewer_impl過剰

    def test_todo_rollback_match(self):
        events = self.created_then(("test_passed", "todo"))
        rc = {"tester_to_implementer": 0, "reviewer_to_implementer": 0,
              "reviewer_to_investigator": 1}
        self.assertEqual(lib.reconcile_rollbacks(rc, events), [])

    def test_improvement_loop_not_counted(self):
        # done→investigation_done は人間起因でリトライではない → 非カウント
        events = self.created_then(("test_passed", "done"),
                                   ("done", "investigation_done"))
        rc = {"tester_to_implementer": 0, "reviewer_to_implementer": 0,
              "reviewer_to_investigator": 0}
        self.assertEqual(lib.reconcile_rollbacks(rc, events), [])

    def test_partial_history_skipped(self):
        # created で始まらない＝全履歴が無い → 照合不能で素通り
        events = [self.ev("todo", "investigation_done"),
                  self.ev("test_passed", "design_done")]
        rc = {"tester_to_implementer": 0, "reviewer_to_implementer": 0,
              "reviewer_to_investigator": 0}
        self.assertEqual(lib.reconcile_rollbacks(rc, events), [])

    def test_no_events_skipped(self):
        self.assertEqual(lib.reconcile_rollbacks({"tester_to_implementer": 5}, []), [])

    # --- retry_reset をエポックとする照合 ---

    @staticmethod
    def reset_ev(**to_counts):
        counts = {"tester_to_implementer": 0, "reviewer_to_implementer": 0,
                  "reviewer_to_investigator": 0}
        counts.update(to_counts)
        return {"ticket": "APP-001", "type": "retry_reset", "to_counts": counts}

    def test_reset_epoch_match(self):
        # 差し戻し3回 → リセット(0) → 差し戻し1回。カウンタは 1 が正
        events = self.created_then(("implementation_done", "design_done"),
                                   ("implementation_done", "design_done"),
                                   ("implementation_done", "design_done"))
        events.append(self.reset_ev())
        events.append(self.ev("implementation_done", "design_done"))
        rc = {"tester_to_implementer": 1, "reviewer_to_implementer": 0,
              "reviewer_to_investigator": 0}
        self.assertEqual(lib.reconcile_rollbacks(rc, events), [])

    def test_reset_epoch_mismatch_flagged(self):
        # リセット後の差し戻しは1回なのにカウンタが3のまま → 不一致
        events = self.created_then(("implementation_done", "design_done"))
        events.append(self.reset_ev())
        events.append(self.ev("implementation_done", "design_done"))
        rc = {"tester_to_implementer": 3, "reviewer_to_implementer": 0,
              "reviewer_to_investigator": 0}
        errs = lib.reconcile_rollbacks(rc, events)
        self.assertTrue(any("tester_to_implementer" in e for e in errs))

    def test_reset_nonzero_baseline(self):
        # 部分リセット（2に減）→ 以降1回 → カウンタ 3 が正
        events = self.created_then(("implementation_done", "design_done"),
                                   ("implementation_done", "design_done"),
                                   ("implementation_done", "design_done"))
        events.append(self.reset_ev(tester_to_implementer=2))
        events.append(self.ev("implementation_done", "design_done"))
        rc = {"tester_to_implementer": 3, "reviewer_to_implementer": 0,
              "reviewer_to_investigator": 0}
        self.assertEqual(lib.reconcile_rollbacks(rc, events), [])

    def test_last_reset_wins(self):
        # 複数リセットがある場合は最後のリセットがエポック
        events = self.created_then(("implementation_done", "design_done"))
        events.append(self.reset_ev())
        events.append(self.ev("implementation_done", "design_done"))
        events.append(self.reset_ev())
        rc = {"tester_to_implementer": 0, "reviewer_to_implementer": 0,
              "reviewer_to_investigator": 0}
        self.assertEqual(lib.reconcile_rollbacks(rc, events), [])

    def test_broken_reset_record_skipped(self):
        # to_counts が壊れているリセット記録 → 照合不能で素通り（fail-open）
        events = self.created_then(("implementation_done", "design_done"))
        events.append({"ticket": "APP-001", "type": "retry_reset",
                       "to_counts": "broken"})
        rc = {"tester_to_implementer": 9, "reviewer_to_implementer": 0,
              "reviewer_to_investigator": 0}
        self.assertEqual(lib.reconcile_rollbacks(rc, events), [])


class TestSpecDriftPureFunctions(unittest.TestCase):
    """KLK-016 設計書§9「単体境界テスト（純粋関数）について」で明示された3観点。
    tests/test_spec_drift.py はサブプロセス起動の統合テストスタイルであり、
    これらの純粋関数の境界はモック不要で直接呼び出して確認できる（フェイル
    オープンの根拠になる分岐のため、統合テストとは独立に固定する）。"""

    def test_sha256_file_missing_path_returns_none(self):
        self.assertIsNone(
            lib.sha256_file("/nonexistent/path/does-not-exist.md"))

    def test_is_project_spec_nested_spec_is_false(self):
        # docs/foo/SPEC.md はネストしたSPEC.mdであり、basename一致の
        # guard_spec_writes.is_spec とは異なり is_project_spec は
        # プロジェクト直下の docs/SPEC.md のみを対象とする（D3）
        self.assertFalse(lib.is_project_spec("/repo/docs/foo/SPEC.md", "/repo"))
        self.assertFalse(lib.is_project_spec("docs/foo/SPEC.md", "/repo"))

    def test_is_project_spec_root_spec_is_true(self):
        # 対照ケース: プロジェクト直下（絶対形・相対形とも）は真になる
        self.assertTrue(lib.is_project_spec("/repo/docs/SPEC.md", "/repo"))
        self.assertTrue(lib.is_project_spec("docs/SPEC.md", "/repo"))

    def test_load_spec_state_broken_json_returns_none(self):
        with tempfile.TemporaryDirectory() as cwd:
            docs = os.path.join(cwd, "docs")
            os.makedirs(docs)
            with open(os.path.join(docs, ".spec_state.json"), "w",
                      encoding="utf-8") as f:
                f.write("not json")
            self.assertIsNone(lib.load_spec_state(cwd))

    def test_load_spec_state_non_dict_returns_none(self):
        with tempfile.TemporaryDirectory() as cwd:
            docs = os.path.join(cwd, "docs")
            os.makedirs(docs)
            with open(os.path.join(docs, ".spec_state.json"), "w",
                      encoding="utf-8") as f:
                json.dump([1, 2, 3], f)
            self.assertIsNone(lib.load_spec_state(cwd))


if __name__ == "__main__":
    unittest.main()
