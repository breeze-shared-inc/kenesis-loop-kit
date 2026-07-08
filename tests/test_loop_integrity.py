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
        return _util.top_level_output(out)

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

    def test_block_uses_top_level_decision(self):
        # Stop hook の契約: decision/reason はトップレベル。hookSpecificOutput に
        # ネストすると Claude Code が block を無視するため、形式退行を防ぐ。
        _util.write_ticket(self.cwd, "APP-001.md", status="bogus")
        payload = {"hook_event_name": "Stop", "cwd": self.cwd,
                   "stop_hook_active": False}
        _, out, _ = _util.run_script(_util.INTEGRITY, payload, cwd=self.cwd)
        obj = json.loads(out)
        self.assertEqual(obj.get("decision"), "block")
        self.assertIn("reason", obj)
        self.assertNotIn("hookSpecificOutput", obj)

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
        # tester差し戻し（implementation_done起点）は tester_to_implementer と照合される
        _util.write_ticket(self.cwd, "APP-001.md", status="design_done", tti=1)
        write_metrics(self.cwd, [
            {"ticket": "APP-001", "from": None, "to": "todo"},
            {"ticket": "APP-001", "from": "implementation_done", "to": "design_done"},
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

    # --- ドリフト検知: サイドカー観測値との突き合わせ ---

    def test_status_drift_blocks(self):
        # 観測=design_done なのにファイルは done（Write/Editを経ない書き換え）
        _util.write_ticket(self.cwd, "APP-001.md", status="done")
        _util.write_state(self.cwd, {"APP-001": _util.state_record("design_done")})
        out = self.assertBlock(must_contain="Write/Edit を経ない")
        self.assertIn("design_done", out.get("reason", ""))

    def test_status_matches_state_allows(self):
        _util.write_ticket(self.cwd, "APP-001.md", status="design_done")
        _util.write_state(self.cwd, {"APP-001": _util.state_record("design_done")})
        self.assertIsNone(self.run_stop())

    def test_no_state_record_skips_drift(self):
        # サイドカーに記録が無いチケット（hook導入前）は照合しない
        _util.write_ticket(self.cwd, "APP-001.md", status="design_done")
        _util.write_state(self.cwd, {"APP-999": _util.state_record("todo")})
        self.assertIsNone(self.run_stop())

    def test_counter_drift_blocks(self):
        # 観測 tti=2 なのにファイルは 0（Bash等での減少 = cap回避）
        _util.write_ticket(self.cwd, "APP-001.md", status="design_done", tti=0)
        _util.write_state(
            self.cwd, {"APP-001": _util.state_record("design_done", tti=2)})
        self.assertBlock(must_contain="retry_counts.tester_to_implementer")

    def test_counter_ahead_of_state_allows(self):
        # ファイルが観測値より進んでいるのは正常（stateは遅行しうる）
        _util.write_ticket(self.cwd, "APP-001.md", status="design_done", tti=2)
        _util.write_state(
            self.cwd, {"APP-001": _util.state_record("design_done", tti=1)})
        self.assertIsNone(self.run_stop())

    def test_legacy_state_without_counters_skips_counter_drift(self):
        # 旧形式の state（retry_counts無し）でも status 照合のみで通る
        _util.write_ticket(self.cwd, "APP-001.md", status="design_done", tti=1)
        _util.write_state(
            self.cwd,
            {"APP-001": {"status": "design_done", "ts": "2026-06-14T00:00:00"}})
        self.assertIsNone(self.run_stop())

    # --- done/ のドリフト検知 ---

    def test_done_ticket_drift_blocks(self):
        # done/ のチケットがBash等で書き換えられた（観測=done、実体=todo）
        os.makedirs(os.path.join(self.cwd, "tickets", "active"), exist_ok=True)
        _util.write_ticket(self.cwd, "APP-001.md", dirname="done", status="todo")
        _util.write_state(self.cwd, {"APP-001": _util.state_record("done")})
        self.assertBlock(must_contain="Write/Edit を経ない")

    def test_done_ticket_matching_state_allows(self):
        os.makedirs(os.path.join(self.cwd, "tickets", "active"), exist_ok=True)
        _util.write_ticket(self.cwd, "APP-001.md", dirname="done", status="done")
        _util.write_state(self.cwd, {"APP-001": _util.state_record("done")})
        self.assertIsNone(self.run_stop())

    def test_done_legacy_ticket_not_fully_checked(self):
        # done/ はドリフト検知のみ。retry_counts の無い旧チケットでも block しない
        content = _util.ticket(status="done").replace(
            "retry_counts:\n  tester_to_implementer: 0\n"
            "  reviewer_to_implementer: 0\n  reviewer_to_investigator: 0\n", "")
        done = os.path.join(self.cwd, "tickets", "done")
        os.makedirs(done, exist_ok=True)
        with open(os.path.join(done, "OLD-001.md"), "w", encoding="utf-8") as f:
            f.write(content)
        os.makedirs(os.path.join(self.cwd, "tickets", "active"), exist_ok=True)
        self.assertIsNone(self.run_stop())

    # --- L3: retry_reset エポックの統合確認 ---

    def test_reconcile_respects_reset_epoch(self):
        # 差し戻し1回 → リセット(0) → 差し戻し1回。カウンタ1で整合
        _util.write_ticket(self.cwd, "APP-001.md", status="design_done", tti=1)
        write_metrics(self.cwd, [
            {"ticket": "APP-001", "from": None, "to": "todo"},
            {"ticket": "APP-001", "from": "implementation_done",
             "to": "design_done"},
            {"ticket": "APP-001", "type": "retry_reset",
             "to_counts": {"tester_to_implementer": 0,
                           "reviewer_to_implementer": 0,
                           "reviewer_to_investigator": 0}},
            {"ticket": "APP-001", "from": "implementation_done",
             "to": "design_done"},
        ])
        self.assertIsNone(self.run_stop())


if __name__ == "__main__":
    unittest.main()
