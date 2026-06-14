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

    def test_counter_decrease_deny(self):
        path = _util.write_ticket(self.cwd, "APP-001.md", status="design_done", tti=1)
        out = self.assertDeny(edit_payload(path, "tester_to_implementer: 1",
                                           "tester_to_implementer: 0"))
        self.assertIn("減少", out.get("permissionDecisionReason", ""))

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


if __name__ == "__main__":
    unittest.main()
