"""record_metrics.py（PostToolUse）と aggregate.py の統合テスト"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _util  # noqa: E402


class TestRecorder(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = self.tmp.name
        self.active = os.path.join(self.cwd, "tickets", "active")
        os.makedirs(self.active)
        self.path = os.path.join(self.active, "APP-001.md")
        self.jsonl = os.path.join(self.cwd, "tickets", ".metrics.jsonl")

    def tearDown(self):
        self.tmp.cleanup()

    def record(self, status):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(_util.ticket(status=status))
        payload = {"tool_name": "Write", "cwd": self.cwd,
                   "tool_input": {"file_path": self.path}}
        rc, _, _ = _util.run_script(_util.RECORDER, payload, cwd=self.cwd)
        self.assertEqual(rc, 0)

    def events(self):
        if not os.path.exists(self.jsonl):
            return []
        with open(self.jsonl, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]

    def test_records_status_changes_only(self):
        self.record("todo")               # created
        self.record("investigation_done")  # transition
        self.record("investigation_done")  # 変化なし -> 記録されない
        self.record("design_done")         # transition
        evs = self.events()
        self.assertEqual(len(evs), 3)
        self.assertEqual(evs[0]["type"], "created")
        self.assertIsNone(evs[0]["from"])
        self.assertEqual(evs[0]["to"], "todo")
        self.assertEqual(evs[1]["from"], "todo")
        self.assertEqual(evs[1]["to"], "investigation_done")
        self.assertEqual(evs[2]["to"], "design_done")

    def test_state_sidecar_written(self):
        self.record("todo")
        state_path = os.path.join(self.cwd, "tickets", ".metrics_state.json")
        self.assertTrue(os.path.exists(state_path))
        with open(state_path, encoding="utf-8") as f:
            state = json.load(f)
        self.assertEqual(state["APP-001"]["status"], "todo")

    def test_non_ticket_ignored(self):
        payload = {"tool_name": "Write", "cwd": self.cwd,
                   "tool_input": {"file_path": os.path.join(self.cwd, "src", "x.ts")}}
        _util.run_script(_util.RECORDER, payload, cwd=self.cwd)
        self.assertEqual(self.events(), [])


class TestAggregate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = self.tmp.name
        os.makedirs(os.path.join(self.cwd, "tickets"))
        self.jsonl = os.path.join(self.cwd, "tickets", ".metrics.jsonl")

    def tearDown(self):
        self.tmp.cleanup()

    def write_log(self, rows):
        with open(self.jsonl, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    def test_missing_log_message(self):
        import subprocess
        proc = subprocess.run([sys.executable, _util.AGGREGATE],
                              capture_output=True, text=True, cwd=self.cwd)
        self.assertIn("まだありません", proc.stdout)

    def test_full_report(self):
        import subprocess
        rows = [
            {"ts": "2026-06-10T09:00:00", "ticket": "APP-001", "type": "created",
             "from": None, "to": "todo", "project": "demo"},
            {"ts": "2026-06-10T10:00:00", "ticket": "APP-001", "type": "transition",
             "from": "todo", "to": "investigation_done", "project": "demo"},
            {"ts": "2026-06-10T12:00:00", "ticket": "APP-001", "type": "transition",
             "from": "investigation_done", "to": "design_done", "project": "demo"},
            {"ts": "2026-06-11T09:00:00", "ticket": "APP-001", "type": "transition",
             "from": "design_done", "to": "implementation_done", "project": "demo"},
            {"ts": "2026-06-11T11:00:00", "ticket": "APP-001", "type": "transition",
             "from": "implementation_done", "to": "test_passed", "project": "demo"},
            {"ts": "2026-06-11T12:00:00", "ticket": "APP-001", "type": "transition",
             "from": "test_passed", "to": "design_done", "project": "demo"},
            {"ts": "2026-06-12T09:00:00", "ticket": "APP-001", "type": "transition",
             "from": "design_done", "to": "done", "project": "demo"},
        ]
        self.write_log(rows)
        proc = subprocess.run([sys.executable, _util.AGGREGATE],
                              capture_output=True, text=True, cwd=self.cwd)
        out = proc.stdout
        self.assertIn("サイクルタイム", out)
        self.assertIn("test_passed→design_done", out)  # rollback captured
        self.assertIn("APP-001", out)

    def test_filter(self):
        import subprocess
        rows = [
            {"ts": "2026-06-10T09:00:00", "ticket": "APP-001", "type": "created",
             "from": None, "to": "todo", "project": "demo"},
            {"ts": "2026-06-10T09:00:00", "ticket": "APP-099", "type": "created",
             "from": None, "to": "todo", "project": "other"},
        ]
        self.write_log(rows)
        proc = subprocess.run([sys.executable, _util.AGGREGATE, "APP-099"],
                              capture_output=True, text=True, cwd=self.cwd)
        self.assertIn("チケット数: 1", proc.stdout)


if __name__ == "__main__":
    unittest.main()
