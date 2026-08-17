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

    def record(self, status, **kwargs):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(_util.ticket(status=status, **kwargs))
        payload = {"tool_name": "Write", "cwd": self.cwd,
                   "tool_input": {"file_path": self.path}}
        rc, _, _ = _util.run_script(_util.RECORDER, payload, cwd=self.cwd)
        self.assertEqual(rc, 0)

    def state(self):
        path = os.path.join(self.cwd, "tickets", ".metrics_state.json")
        with open(path, encoding="utf-8") as f:
            return json.load(f)

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
        state = self.state()
        self.assertEqual(state["APP-001"]["status"], "todo")
        self.assertEqual(
            state["APP-001"]["retry_counts"]["tester_to_implementer"], 0)

    def test_state_counters_refresh_without_event(self):
        # status不変で retry_counts が増加 → イベントは増えず state だけ更新
        self.record("design_done")
        self.assertEqual(len(self.events()), 1)
        self.record("design_done", tti=1)
        self.assertEqual(len(self.events()), 1)  # イベント追加なし
        self.assertEqual(
            self.state()["APP-001"]["retry_counts"]["tester_to_implementer"], 1)

    def test_counter_decrease_records_retry_reset(self):
        # 減少（人間承認済みリセット）→ retry_reset イベントを記録し state 更新
        self.record("design_done", tti=2)
        self.record("design_done", tti=0)
        evs = self.events()
        self.assertEqual(len(evs), 2)
        reset = evs[-1]
        self.assertEqual(reset["type"], "retry_reset")
        self.assertEqual(reset["from_counts"]["tester_to_implementer"], 2)
        self.assertEqual(reset["to_counts"]["tester_to_implementer"], 0)
        self.assertEqual(
            self.state()["APP-001"]["retry_counts"]["tester_to_implementer"], 0)

    def test_transition_with_reset_orders_events(self):
        # 遷移とリセットが同時 → 遷移イベントの後にリセットイベント
        self.record("blocked", tti=3)
        self.record("design_done", tti=0)
        evs = self.events()
        self.assertEqual([e["type"] for e in evs],
                         ["created", "transition", "retry_reset"])
        self.assertEqual(evs[1]["from"], "blocked")
        self.assertEqual(evs[1]["to"], "design_done")

    def test_non_ticket_ignored(self):
        payload = {"tool_name": "Write", "cwd": self.cwd,
                   "tool_input": {"file_path": os.path.join(self.cwd, "src", "x.ts")}}
        _util.run_script(_util.RECORDER, payload, cwd=self.cwd)
        self.assertEqual(self.events(), [])

    # --- KLK-012 AC1: 相対パスでもイベントが記録される ---

    def test_relative_path_recorded(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(_util.ticket(status="todo"))
        rel = os.path.join("tickets", "active", "APP-001.md")
        payload = {"tool_name": "Write", "cwd": self.cwd,
                   "tool_input": {"file_path": rel}}
        rc, _, _ = _util.run_script(_util.RECORDER, payload, cwd=self.cwd)
        self.assertEqual(rc, 0)
        evs = self.events()
        self.assertEqual(len(evs), 1)
        self.assertEqual(evs[0]["to"], "todo")

    def test_relative_path_with_non_str_cwd_falls_back(self):
        # 非 str の cwd は os.getcwd() へフォールバックする（AC5）
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(_util.ticket(status="todo"))
        rel = os.path.join("tickets", "active", "APP-001.md")
        payload = {"tool_name": "Write", "cwd": 123,
                   "tool_input": {"file_path": rel}}
        rc, _, _ = _util.run_script(_util.RECORDER, payload, cwd=self.cwd)
        self.assertEqual(rc, 0)
        self.assertEqual(len(self.events()), 1)

    # --- KLK-012 AC5: 非 dict 入力でクラッシュしない ---

    def test_non_dict_stdin_ignored(self):
        rc, out, _ = _util.run_script(_util.RECORDER, "[]", cwd=self.cwd)
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), "")
        self.assertEqual(self.events(), [])

    def test_non_dict_tool_input_ignored(self):
        payload = {"tool_name": "Write", "cwd": self.cwd, "tool_input": []}
        rc, out, _ = _util.run_script(_util.RECORDER, payload, cwd=self.cwd)
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), "")
        self.assertEqual(self.events(), [])

    def test_non_str_file_path_ignored(self):
        payload = {"tool_name": "Write", "cwd": self.cwd,
                   "tool_input": {"file_path": 123}}
        rc, _, _ = _util.run_script(_util.RECORDER, payload, cwd=self.cwd)
        self.assertEqual(rc, 0)
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

    def run_aggregate(self, *args):
        """aggregate.py を実行して stdout を返す（rc=0 を確認する）。"""
        import subprocess
        proc = subprocess.run([sys.executable, _util.AGGREGATE] + list(args),
                              capture_output=True, text=True, cwd=self.cwd)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout

    @staticmethod
    def section(out, title):
        """`— <title> —` 節の本文を返す（次の節見出しの手前まで）。"""
        body = out.split("— %s —" % title, 1)[1]
        return body.split("\n— ", 1)[0]

    @staticmethod
    def reset_row(ts, ticket="APP-001"):
        return {"ts": ts, "ticket": ticket, "type": "retry_reset",
                "from_counts": {"tester_to_implementer": 2},
                "to_counts": {"tester_to_implementer": 0},
                "project": "demo"}

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

    def test_improvement_loop_not_counted_as_rollback(self):
        import subprocess
        rows = [
            {"ts": "2026-06-10T09:00:00", "ticket": "APP-001", "type": "created",
             "from": None, "to": "todo", "project": "demo"},
            {"ts": "2026-06-11T09:00:00", "ticket": "APP-001", "type": "transition",
             "from": "test_passed", "to": "done", "project": "demo"},
            {"ts": "2026-06-12T09:00:00", "ticket": "APP-001", "type": "transition",
             "from": "done", "to": "todo", "project": "demo"},
        ]
        self.write_log(rows)
        proc = subprocess.run([sys.executable, _util.AGGREGATE],
                              capture_output=True, text=True, cwd=self.cwd)
        out = proc.stdout
        # done→todo は改善ループとして計上し、差し戻しには含めない
        imp_section = out.split("— 改善ループ")[1].split("— blocked")[0]
        self.assertIn("done→todo", imp_section)
        rb_section = out.split("— 差し戻し")[1].split("— 改善ループ")[0]
        self.assertNotIn("done→todo", rb_section)
        self.assertIn("なし", rb_section)

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

    # --- KLK-012 AC2: status を伴わないイベントを集計から除外する ---

    def test_done_with_trailing_retry_reset_not_in_progress(self):
        # done の直後に同一 ts の retry_reset。従来は last_to が None になり
        # 「サイクルタイム」と「現在進行中」へ二重計上されていた
        self.write_log([
            {"ts": "2026-06-10T09:00:00", "ticket": "APP-001", "type": "created",
             "from": None, "to": "todo", "project": "demo"},
            {"ts": "2026-06-12T09:00:00", "ticket": "APP-001",
             "type": "transition", "from": "test_passed", "to": "done",
             "project": "demo"},
            self.reset_row("2026-06-12T09:00:00"),
        ])
        out = self.run_aggregate()
        self.assertIn("なし", self.section(out, "現在進行中"))
        self.assertNotIn("None", out)
        self.assertIn("APP-001", self.section(out, "サイクルタイム（created → done）"))

    def test_in_progress_status_kept_after_retry_reset(self):
        # 進行中チケットの末尾に retry_reset が来ても現在ステータスを失わない
        # （「末尾を1件読み飛ばす」方式では表示できないケース）
        self.write_log([
            {"ts": "2026-06-10T09:00:00", "ticket": "APP-001", "type": "created",
             "from": None, "to": "todo", "project": "demo"},
            {"ts": "2026-06-10T10:00:00", "ticket": "APP-001",
             "type": "transition", "from": "todo", "to": "investigation_done",
             "project": "demo"},
            {"ts": "2026-06-10T12:00:00", "ticket": "APP-001",
             "type": "transition", "from": "investigation_done",
             "to": "design_done", "project": "demo"},
            self.reset_row("2026-06-10T12:00:00"),
        ])
        section = self.section(self.run_aggregate(), "現在進行中")
        self.assertIn("APP-001", section)
        self.assertIn("design_done", section)

    def test_retry_reset_only_ticket_survives(self):
        # status イベントが1件も無いチケットでも IndexError にならない
        self.write_log([self.reset_row("2026-06-10T09:00:00", ticket="APP-050")])
        out = self.run_aggregate()
        self.assertIn("なし", self.section(out, "現在進行中"))
        self.assertIn("完了チケットなし", out)

    # --- KLK-028 AC2: ヘッダの件数を本文の集計対象と一致させる ---

    def test_header_counts_exclude_retry_reset_only_ticket(self):
        # investigatorの実測repro: APP-001(created→todo) + APP-050(retry_resetのみ)
        # ヘッダは本文と同じ「1チケット・1イベント」を示すべき（従来は2/2）
        self.write_log([
            {"ts": "2026-06-10T09:00:00", "ticket": "APP-001", "type": "created",
             "from": None, "to": "todo", "project": "demo"},
            self.reset_row("2026-06-10T09:00:00", ticket="APP-050"),
        ])
        out = self.run_aggregate()
        self.assertIn("イベント数: 1 / チケット数: 1", out)

    def test_header_zero_when_all_tickets_retry_reset_only(self):
        # 本文が「なし」「完了チケットなし」になるログでは、ヘッダも0/0になる
        # （フィルタ前の生カウントに戻ってしまう不整合を明示的に禁止する）
        self.write_log([self.reset_row("2026-06-10T09:00:00", ticket="APP-050")])
        out = self.run_aggregate()
        self.assertIn("イベント数: 0 / チケット数: 0", out)

    # --- KLK-012 AC3: tz-aware な ts が混入しても完走する ---

    def test_mixed_timezone_dwell_path(self):
        # dwell 計算（次イベントとの減算）とサイクルタイム計算の経路
        self.write_log([
            {"ts": "2026-06-10T09:00:00+09:00", "ticket": "APP-001",
             "type": "created", "from": None, "to": "todo", "project": "demo"},
            {"ts": "2026-06-10T12:00:00", "ticket": "APP-001",
             "type": "transition", "from": "todo", "to": "investigation_done",
             "project": "demo"},
            {"ts": "2026-06-11T09:00:00", "ticket": "APP-001",
             "type": "transition", "from": "investigation_done", "to": "done",
             "project": "demo"},
        ])
        out = self.run_aggregate()
        self.assertIn("APP-001", self.section(out, "サイクルタイム（created → done）"))
        self.assertNotIn("データ不足", self.section(out, "フェーズ別 平均滞留時間"))

    def test_mixed_timezone_in_progress_path(self):
        # in_progress 計算（now との減算）の経路。末尾イベントだけ tz-aware
        self.write_log([
            {"ts": "2026-06-10T09:00:00", "ticket": "APP-001", "type": "created",
             "from": None, "to": "todo", "project": "demo"},
            {"ts": "2026-06-10T12:00:00+09:00", "ticket": "APP-001",
             "type": "transition", "from": "todo", "to": "investigation_done",
             "project": "demo"},
        ])
        section = self.section(self.run_aggregate(), "現在進行中")
        self.assertIn("APP-001", section)
        self.assertIn("investigation_done", section)


if __name__ == "__main__":
    unittest.main()
