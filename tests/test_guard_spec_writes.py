"""guard_spec_writes.py（PreToolUse）のテスト"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _util  # noqa: E402


def payload(tool, path):
    tool_input = {"file_path": path}
    if tool == "Write":
        tool_input["content"] = "x"
    else:
        tool_input["old_string"] = "a"
        tool_input["new_string"] = "b"
    return {"tool_name": tool, "tool_input": tool_input}


class TestGuardSpecWrites(unittest.TestCase):
    def run_guard(self, data):
        rc, out, _ = _util.run_script(_util.GUARD, data)
        self.assertEqual(rc, 0)  # hookは常に exit 0
        return _util.hook_output(out)

    def assertAllow(self, data):
        self.assertIsNone(self.run_guard(data), "expected allow")

    def assertAsk(self, data):
        out = self.run_guard(data)
        self.assertIsNotNone(out, "expected ask")
        self.assertEqual(out.get("permissionDecision"), "ask")

    def test_docs_spec_write_ask(self):
        self.assertAsk(payload("Write", "/repo/docs/SPEC.md"))

    def test_docs_spec_edit_ask(self):
        self.assertAsk(payload("Edit", "/repo/docs/SPEC.md"))

    def test_nested_spec_ask(self):
        self.assertAsk(payload("Edit", "/repo/docs/expense/SPEC.md"))

    def test_root_spec_ask(self):
        self.assertAsk(payload("Write", "/repo/SPEC.md"))

    def test_other_file_allow(self):
        self.assertAllow(payload("Edit", "/repo/docs/designs/APP-001.md"))

    def test_spec_qa_state_file_allow(self):
        self.assertAllow(payload("Write", "/repo/docs/spec-qa/SPEC/QUESTIONS.yaml"))

    def test_template_allow(self):
        self.assertAllow(payload("Write", "/repo/docs/SPEC_TEMPLATE.md"))

    def test_claude_dir_allow(self):
        self.assertAllow(payload(
            "Write", "/repo/.claude/skills/spec-interview/templates/SPEC.md"))

    def test_missing_path_allow(self):
        self.assertAllow({"tool_name": "Write", "tool_input": {}})

    def test_broken_stdin_allow(self):
        rc, out, _ = _util.run_script(_util.GUARD, "not json")
        self.assertEqual(rc, 0)
        self.assertIsNone(_util.hook_output(out))


if __name__ == "__main__":
    unittest.main()
