"""check_loop_integrity.py（Stop）の統合テスト"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _util  # noqa: E402


def write_metrics(cwd, events):
    path = os.path.join(cwd, "tickets", ".metrics.jsonl")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


class TestLoopIntegrity(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def run_stop(self, stop_hook_active=False):
        payload = {"hook_event_name": "Stop", "cwd": self.cwd,
                   "stop_hook_active": stop_hook_active}
        rc, out, _ = _util.run_script(_util.INTEGRITY, payload, cwd=self.cwd)
        self.assertEqual(rc, 0)
        return _util.hook_output(out)

    def assertBlock(self, must_contain=None):
        out = self.run_stop()
        self.assertIsNotNone(out, "expected block")
        self.assertEqual(out.get("decision"), "block")
        if must_contain:
            self.assertIn(must_contain, out.get("reason", ""))
        return out

    def test_clean_active_allows_stop(self):
        _util.write_ticket(self.cwd, "APP-001.md", status="todo")
        self.assertIsNone(self.run_stop())

    def test_invalid_status_blocks(self):
        _util.write_ticket(self.cwd, "APP-001.md", status="bogus")
        self.assertBlock()

    def test_blocked_without_blocker_blocks(self):
        _util.write_ticket(self.cwd, "APP-001.md", status="blocked", blocker="")
        self.assertBlock(must_contain="ブロッカー")

    def test_blocked_with_blocker_allows(self):
        _util.write_ticket(self.cwd, "APP-001.md", status="blocked",
                           blocker="リトライ上限超過 - tester→implementer 4回")
        self.assertIsNone(self.run_stop())

    def test_body_table_mismatch_blocks(self):
        content = _util.ticket(status="todo", tti=0).replace(
            "| tester → implementer | 0 | 3 |",
            "| tester → implementer | 2 | 3 |")
        active = os.path.join(self.cwd, "tickets", "active")
        os.makedirs(active, exist_ok=True)
        with open(os.path.join(active, "APP-001.md"), "w", encoding="utf-8") as f:
            f.write(content)
        self.assertBlock(must_contain="不一致")

    def test_over_cap_retry_blocks(self):
        _util.write_ticket(self.cwd, "APP-001.md", status="design_done", tti=4)
        self.assertBlock(must_contain="上限")

    def test_stop_hook_active_suppresses(self):
        _util.write_ticket(self.cwd, "APP-001.md", status="bogus")
        self.assertIsNone(self.run_stop(stop_hook_active=True))

    def test_no_tickets_dir_allows(self):
        self.assertIsNone(self.run_stop())

    # --- L3: 差し戻し履歴の照合 ---

    def test_rollback_reconcile_mismatch_blocks(self):
        # 履歴上は design_done への差し戻し1回。だがカウンタは全0（増やし忘れ）
        _util.write_ticket(self.cwd, "APP-001.md", status="design_done", tti=0)
        write_metrics(self.cwd, [
            {"ticket": "APP-001", "from": None, "to": "todo"},
            {"ticket": "APP-001", "from": "test_passed", "to": "design_done"},
        ])
        self.assertBlock(must_contain="不一致")

    def test_rollback_reconcile_match_allows(self):
        _util.write_ticket(self.cwd, "APP-001.md", status="design_done", tti=1)
        write_metrics(self.cwd, [
            {"ticket": "APP-001", "from": None, "to": "todo"},
            {"ticket": "APP-001", "from": "test_passed", "to": "design_done"},
        ])
        self.assertIsNone(self.run_stop())

    def test_partial_history_skips_reconcile(self):
        # created で始まらない履歴は照合不能 → L3はスキップ（他チェックも通る想定）
        _util.write_ticket(self.cwd, "APP-001.md", status="todo", tti=0)
        write_metrics(self.cwd, [
            {"ticket": "APP-001", "from": "todo", "to": "investigation_done"},
            {"ticket": "APP-001", "from": "test_passed", "to": "design_done"},
        ])
        self.assertIsNone(self.run_stop())

    def test_no_metrics_log_skips_reconcile(self):
        _util.write_ticket(self.cwd, "APP-001.md", status="design_done", tti=0)
        self.assertIsNone(self.run_stop())  # ログ無し → fail-open


if __name__ == "__main__":
    unittest.main()
