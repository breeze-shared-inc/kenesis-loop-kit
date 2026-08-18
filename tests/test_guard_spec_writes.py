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

    # --- KLK-012 AC5: 非 dict 入力でクラッシュしない ---

    def test_non_dict_stdin_allow(self):
        rc, out, _ = _util.run_script(_util.GUARD, "[]")
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), "")

    def test_non_dict_tool_input_allow(self):
        self.assertAllow({"tool_name": "Write", "tool_input": []})

    def test_non_str_file_path_allow(self):
        self.assertAllow({"tool_name": "Write",
                          "tool_input": {"file_path": 123}})

    # --- KLK-020 D1: SPEC.md 判定の case-insensitive 化（AC3） ---

    def test_lowercase_spec_ask(self):
        self.assertAsk(payload("Write", "/repo/docs/spec.md"))

    def test_mixed_case_spec_ask(self):
        self.assertAsk(payload("Edit", "/repo/docs/Spec.md"))

    def test_uppercase_ext_spec_ask(self):
        self.assertAsk(payload("Write", "/repo/docs/SPEC.MD"))

    def test_random_mixed_case_spec_ask(self):
        self.assertAsk(payload("Edit", "/repo/docs/SpEc.Md"))

    def test_claude_dir_lowercase_spec_allow(self):
        # .claude/ 配下は大小区別化後も引き続き対象外（回帰確認）
        self.assertAllow(payload(
            "Write", "/repo/.claude/skills/spec-interview/templates/spec.md"))

    def test_non_md_extension_lowercase_allow(self):
        # 拡張子が .md でない場合は大小区別化後も引き続き不一致（回帰確認）
        self.assertAllow(payload("Write", "/repo/docs/spec.mdx"))

    def test_template_lowercase_variant_allow(self):
        # SPEC_TEMPLATE.md は大小を変えても basename 完全一致ではないため
        # 引き続き不一致（回帰確認）
        self.assertAllow(payload("Write", "/repo/docs/spec_template.md"))


if __name__ == "__main__":
    unittest.main()
