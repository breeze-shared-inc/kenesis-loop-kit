"""validate_ticket_state.py（PreToolUse）の統合テスト"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _util  # noqa: E402


def edit_payload(path, old, new):
    return {"tool_name": "Edit",
            "tool_input": {"file_path": path, "old_string": old, "new_string": new}}


def write_payload(path, content):
    return {"tool_name": "Write",
            "tool_input": {"file_path": path, "content": content}}


class TestValidator(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def run_validator(self, payload):
        rc, out, _ = _util.run_script(_util.VALIDATOR, payload, cwd=self.cwd)
        self.assertEqual(rc, 0)  # hookは常に exit 0
        return _util.hook_output(out)

    def assertAllow(self, payload):
        self.assertIsNone(self.run_validator(payload), "expected allow")

    def assertDeny(self, payload):
        out = self.run_validator(payload)
        self.assertIsNotNone(out, "expected deny")
        self.assertEqual(out.get("permissionDecision"), "deny")
        return out

    def assertAsk(self, payload):
        out = self.run_validator(payload)
        self.assertIsNotNone(out, "expected ask")
        self.assertEqual(out.get("permissionDecision"), "ask")
        return out

    def test_legal_forward_transition_allow(self):
        path = _util.write_ticket(self.cwd, "APP-001.md", status="design_done")
        self.assertAllow(edit_payload(path, "status: design_done",
                                      "status: implementation_done"))

    def test_illegal_skip_transition_deny(self):
        path = _util.write_ticket(self.cwd, "APP-001.md", status="design_done")
        self.assertDeny(edit_payload(path, "status: design_done", "status: done"))

    def test_retry_over_cap_deny(self):
        path = _util.write_ticket(self.cwd, "APP-001.md", status="design_done")
        out = self.assertDeny(edit_payload(path, "tester_to_implementer: 0",
                                           "tester_to_implementer: 4"))
        self.assertIn("上限", out.get("permissionDecisionReason", ""))

    def test_blocked_to_done_resume_allow(self):
        # CLAUDE.md ステータス定義表: blocked の遷移先は any（done含む）
        path = _util.write_ticket(self.cwd, "APP-001.md", status="blocked")
        self.assertAllow(edit_payload(path, "status: blocked", "status: done"))

    def test_log_append_status_unchanged_allow(self):
        path = _util.write_ticket(self.cwd, "APP-001.md", status="design_done")
        self.assertAllow(edit_payload(path, "## ログ", "## ログ\n- 2026-06-14: note"))

    def test_new_ticket_todo_allow(self):
        path = os.path.join(self.cwd, "tickets", "active", "APP-002.md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.assertAllow(write_payload(path, _util.ticket(status="todo", tid="APP-002")))

    def test_new_ticket_non_todo_deny(self):
        path = os.path.join(self.cwd, "tickets", "active", "APP-003.md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.assertDeny(write_payload(path, _util.ticket(status="design_done", tid="APP-003")))

    def test_missing_required_key_deny(self):
        path = os.path.join(self.cwd, "tickets", "active", "APP-004.md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        broken = _util.ticket(status="todo", tid="APP-004").replace(
            'project: "demo"\n', "")
        self.assertDeny(write_payload(path, broken))

    def test_counter_decrease_ask(self):
        # 減少 = リトライ予算のリセット。deny ではなく人間確認（ask）に回す
        path = _util.write_ticket(self.cwd, "APP-001.md", status="design_done", tti=1)
        out = self.assertAsk(edit_payload(path, "tester_to_implementer: 1",
                                          "tester_to_implementer: 0"))
        self.assertIn("リセット", out.get("permissionDecisionReason", ""))

    def test_counter_decrease_with_illegal_transition_deny(self):
        # 他の不変条件違反を伴う減少は ask ではなく deny（deny優先）
        path = _util.write_ticket(self.cwd, "APP-001.md", status="design_done", tti=1)
        content = _util.ticket(status="done", tti=0)  # design_done→done は不正遷移
        self.assertDeny(write_payload(path, content))

    def test_counter_increase_allow(self):
        path = _util.write_ticket(self.cwd, "APP-001.md", status="design_done", tti=1)
        self.assertAllow(edit_payload(path, "tester_to_implementer: 1",
                                      "tester_to_implementer: 2"))

    def test_non_ticket_path_allow(self):
        path = os.path.join(self.cwd, "src", "x.ts")
        self.assertAllow(write_payload(path, "const x = 1;"))

    def test_templates_path_allow(self):
        path = os.path.join(self.cwd, "tickets", "Templates", "ticket.md")
        self.assertAllow(write_payload(path, _util.ticket(status="todo")))

    def test_broken_stdin_allow(self):
        rc, out, _ = _util.run_script(_util.VALIDATOR, "not json", cwd=self.cwd)
        self.assertEqual(rc, 0)
        self.assertIsNone(_util.hook_output(out))

    # --- サイドカー（.metrics_state.json）を prior の正とする検証 ---

    def test_drift_restore_to_observed_allow(self):
        # Bashドリフトで file=done / 観測=design_done。観測値へ戻す Edit は
        # 同一status扱いで許可される（ファイルベースなら done→design_done は不正）
        path = _util.write_ticket(self.cwd, "APP-001.md", status="done")
        _util.write_state(self.cwd, {"APP-001": _util.state_record("design_done")})
        self.assertAllow(edit_payload(path, "status: done", "status: design_done"))

    def test_drift_laundering_edit_deny(self):
        # file=done / 観測=todo（不正ジャンプのドリフト）。ログ追記だけの Edit も
        # 観測値 todo からの遷移 todo→done として検証され、deny される
        path = _util.write_ticket(self.cwd, "APP-001.md", status="done")
        _util.write_state(self.cwd, {"APP-001": _util.state_record("todo")})
        self.assertDeny(edit_payload(path, "## ログ", "## ログ\n- note"))

    def test_drift_legal_reapply_allow(self):
        # file=test_passed / 観測=implementation_done（正当な遷移のドリフト）。
        # ログ追記 Edit が implementation_done→test_passed として検証され許可、
        # PostToolUse の record_metrics がイベントを記録して state が同期する
        path = _util.write_ticket(self.cwd, "APP-001.md", status="test_passed")
        _util.write_state(
            self.cwd, {"APP-001": _util.state_record("implementation_done")})
        self.assertAllow(edit_payload(path, "## ログ", "## ログ\n- note"))

    def test_state_other_ticket_ignored(self):
        # 他チケットのレコードは prior に影響しない（ファイルベースで検証）
        path = _util.write_ticket(self.cwd, "APP-001.md", status="design_done")
        _util.write_state(self.cwd, {"APP-999": _util.state_record("todo")})
        self.assertAllow(edit_payload(path, "status: design_done",
                                      "status: implementation_done"))

    def test_counter_floor_from_state_ask(self):
        # Bashドリフトで file の tti が観測値 2 より低い 0 に。観測値を下限として
        # 0→1 への Edit も減少扱いになり、人間確認（ask）に回る
        path = _util.write_ticket(self.cwd, "APP-001.md",
                                  status="design_done", tti=0)
        _util.write_state(
            self.cwd, {"APP-001": _util.state_record("design_done", tti=2)})
        out = self.assertAsk(edit_payload(path, "tester_to_implementer: 0",
                                          "tester_to_implementer: 1"))
        self.assertIn("減少", out.get("permissionDecisionReason", ""))

    def test_counter_restore_to_state_floor_allow(self):
        # 観測値 2 まで戻す Edit は許可される
        path = _util.write_ticket(self.cwd, "APP-001.md",
                                  status="design_done", tti=0)
        _util.write_state(
            self.cwd, {"APP-001": _util.state_record("design_done", tti=2)})
        self.assertAllow(edit_payload(path, "tester_to_implementer: 0",
                                      "tester_to_implementer: 2"))

    def test_new_ticket_ignores_stale_state(self):
        # ファイル不存在（新規作成）ではサイドカーを参照しない（ID再利用時の誤判定防止）
        _util.write_state(self.cwd, {"APP-005": _util.state_record("done")})
        path = os.path.join(self.cwd, "tickets", "active", "APP-005.md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.assertAllow(write_payload(path, _util.ticket(status="todo", tid="APP-005")))

    # --- in_progress 上限（着手時の人間確認ゲート） ---

    def _fill_in_progress(self, n):
        statuses = ["investigation_done", "design_done", "implementation_done"]
        for i in range(n):
            _util.write_ticket(self.cwd, "APP-90%d.md" % i,
                               status=statuses[i % 3], tid="APP-90%d" % i)

    def test_start_ticket_at_limit_ask(self):
        # 他に3件進行中 → todo→investigation_done の着手は人間確認
        self._fill_in_progress(3)
        path = _util.write_ticket(self.cwd, "APP-001.md", status="todo")
        out = self.assertAsk(edit_payload(path, "status: todo",
                                          "status: investigation_done"))
        self.assertIn("in_progress", out.get("permissionDecisionReason", ""))

    def test_start_ticket_under_limit_allow(self):
        self._fill_in_progress(2)
        path = _util.write_ticket(self.cwd, "APP-001.md", status="todo")
        self.assertAllow(edit_payload(path, "status: todo",
                                      "status: investigation_done"))

    def test_create_todo_at_limit_allow(self):
        # 起票（todoの新規作成）は着手ではないので上限に達していても許可
        self._fill_in_progress(3)
        path = os.path.join(self.cwd, "tickets", "active", "APP-001.md")
        self.assertAllow(write_payload(path, _util.ticket(status="todo")))

    def test_blocked_tickets_not_counted(self):
        # blocked は in_progress に数えない
        self._fill_in_progress(2)
        _util.write_ticket(self.cwd, "APP-910.md", status="blocked",
                           tid="APP-910", blocker="対応待ち")
        path = _util.write_ticket(self.cwd, "APP-001.md", status="todo")
        self.assertAllow(edit_payload(path, "status: todo",
                                      "status: investigation_done"))


if __name__ == "__main__":
    unittest.main()
