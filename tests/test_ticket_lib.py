"""_ticket_lib.py の単体テスト（検証ルールの中核）"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _util  # noqa: E402

sys.path.insert(0, _util.HOOKS)
import _ticket_lib as lib  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
