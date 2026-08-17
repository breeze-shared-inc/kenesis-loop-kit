"""docs/SPEC.md ドリフト検知（KLK-016）の統合テスト

record_metrics.py の SPEC.md 対応（TestSpecStateRecording）と
check_loop_integrity.py の SPEC.md ドリフト検知（TestSpecDriftDetection）を
tempdir 上に実ファイルを生成してサブプロセス起動で検証する
（tests/test_loop_integrity.py・tests/test_metrics.py と同型。モックなし）。
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _util  # noqa: E402


def record_write(cwd, path):
    """path への Write を record_metrics.py へ送る。(returncode, stdout, stderr)"""
    payload = {"tool_name": "Write", "cwd": cwd,
               "tool_input": {"file_path": path}}
    return _util.run_script(_util.RECORDER, payload, cwd=cwd)


class TestSpecStateRecording(unittest.TestCase):
    """record_metrics.py の docs/SPEC.md 対応（AC4・AC6）。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def spec_state_path(self):
        return os.path.join(self.cwd, "docs", ".spec_state.json")

    def read_spec_state(self):
        with open(self.spec_state_path(), encoding="utf-8") as f:
            return json.load(f)

    def test_records_hash_on_spec_write(self):
        content = "# SPEC\n\n本文A\n"
        path = _util.write_spec(self.cwd, content)
        rc, _, _ = record_write(self.cwd, path)
        self.assertEqual(rc, 0)
        state = self.read_spec_state()
        self.assertEqual(state["hash"], _util.spec_hash(content))

    def test_updates_hash_on_subsequent_edit(self):
        path = _util.write_spec(self.cwd, "# SPEC\n\n本文A\n")
        record_write(self.cwd, path)
        first_hash = self.read_spec_state()["hash"]

        content2 = "# SPEC\n\n本文B（改訂）\n"
        _util.write_spec(self.cwd, content2)
        record_write(self.cwd, path)
        second_hash = self.read_spec_state()["hash"]

        self.assertNotEqual(first_hash, second_hash)
        self.assertEqual(second_hash, _util.spec_hash(content2))

    def test_nested_spec_not_recorded(self):
        nested_dir = os.path.join(self.cwd, "docs", "foo")
        os.makedirs(nested_dir)
        nested_path = os.path.join(nested_dir, "SPEC.md")
        with open(nested_path, "w", encoding="utf-8") as f:
            f.write("# nested SPEC\n")
        rc, _, _ = record_write(self.cwd, nested_path)
        self.assertEqual(rc, 0)
        self.assertFalse(os.path.exists(self.spec_state_path()))

    def test_ticket_write_unaffected(self):
        # 既存のticket記録（tickets/.metrics_state.json生成）が従来どおり動く（回帰確認）
        path = _util.write_ticket(self.cwd, "APP-001.md", status="todo")
        rc, _, _ = record_write(self.cwd, path)
        self.assertEqual(rc, 0)
        state_path = os.path.join(self.cwd, "tickets", ".metrics_state.json")
        self.assertTrue(os.path.exists(state_path))
        with open(state_path, encoding="utf-8") as f:
            state = json.load(f)
        self.assertEqual(state["APP-001"]["status"], "todo")
        self.assertFalse(os.path.exists(self.spec_state_path()))


class TestSpecDriftDetection(unittest.TestCase):
    """check_loop_integrity.py の docs/SPEC.md ドリフト検知（AC1〜AC3）。

    check_spec_drift(cwd) の呼び出しは main() の tickets/active 存在チェック
    より後にあるため（§4-2）、tickets/active を用意したうえで検証する
    （tests/test_loop_integrity.py の done/ ドリフトテストと同じ理由）。
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = self.tmp.name
        os.makedirs(os.path.join(self.cwd, "tickets", "active"))

    def tearDown(self):
        self.tmp.cleanup()

    def spec_path(self):
        return os.path.join(self.cwd, "docs", "SPEC.md")

    def run_stop(self):
        payload = {"hook_event_name": "Stop", "cwd": self.cwd,
                   "stop_hook_active": False}
        rc, out, _ = _util.run_script(_util.INTEGRITY, payload, cwd=self.cwd)
        self.assertEqual(rc, 0)
        return _util.top_level_output(out)

    def assertBlock(self, must_contain=None):
        out = self.run_stop()
        self.assertIsNotNone(out, "expected block")
        self.assertEqual(out.get("decision"), "block")
        if must_contain:
            self.assertIn(must_contain, out.get("reason", ""))
        return out

    def test_no_spec_file_allows(self):
        # docs/SPEC.md不在 → fail-open（AC3）
        self.assertIsNone(self.run_stop())

    def test_spec_without_state_allows(self):
        # SPEC.mdはあるがサイドカー未記録 → fail-open（D5・AC3）
        _util.write_spec(self.cwd)
        self.assertIsNone(self.run_stop())

    def test_matching_hash_allows(self):
        content = "# SPEC\n\n一致確認\n"
        _util.write_spec(self.cwd, content)
        _util.write_spec_state(
            self.cwd, {"hash": _util.spec_hash(content), "ts": "2026-06-14T00:00:00"})
        self.assertIsNone(self.run_stop())

    def test_bash_edit_without_write_tool_blocks(self):
        content = "# SPEC\n\n改変前\n"
        _util.write_spec(self.cwd, content)
        _util.write_spec_state(
            self.cwd, {"hash": _util.spec_hash(content), "ts": "2026-06-14T00:00:00"})
        # Bash相当の直接改変（Write/Editを経ない）
        with open(self.spec_path(), "w", encoding="utf-8") as f:
            f.write("# SPEC\n\n改変後（Bash直接）\n")
        self.assertBlock(must_contain="docs/SPEC.md")

    def test_legit_write_then_edit_does_not_false_positive(self):
        content = "# SPEC\n\n正規経路\n"
        path = _util.write_spec(self.cwd, content)
        rc, _, _ = record_write(self.cwd, path)
        self.assertEqual(rc, 0)
        self.assertIsNone(self.run_stop())

    def test_full_cycle_record_then_legit_edit_then_drift(self):
        path = self.spec_path()

        _util.write_spec(self.cwd, "# SPEC\n\n初版\n")
        rc, _, _ = record_write(self.cwd, path)
        self.assertEqual(rc, 0)
        self.assertIsNone(self.run_stop())  # 記録直後は一致

        _util.write_spec(self.cwd, "# SPEC\n\n正規改訂\n")
        rc, _, _ = record_write(self.cwd, path)  # 正規Edit相当（record更新）
        self.assertEqual(rc, 0)
        self.assertIsNone(self.run_stop())  # 更新後も一致

        with open(path, "w", encoding="utf-8") as f:
            f.write("# SPEC\n\nBash改変\n")
        self.assertBlock(must_contain="docs/SPEC.md")  # 最終ステップのみ検知


if __name__ == "__main__":
    unittest.main()
