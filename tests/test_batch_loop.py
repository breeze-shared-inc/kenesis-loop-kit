"""scripts/batch_loop.py（バッチ外部駆動スクリプト）のテスト

設計書 docs/designs/KLK-001.md §9「テスト観点」に対応する。
実 claude は一切起動しない — セッション起動は `--claude-cmd` へ注入する
フェイク実行ファイル（bash）で代替し、tempdir に tickets/active|done/ と
frontmatter 付きダミーチケットを構築して検証する。
"""
import contextlib
import io
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import date, timedelta
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _util  # noqa: E402

sys.path.insert(0, os.path.join(_util.REPO, "scripts"))
import batch_loop  # noqa: E402

BATCH_SCRIPT = os.path.join(_util.REPO, "scripts", "batch_loop.py")
TICKET_LIB = os.path.join(_util.HOOKS, "_ticket_lib.py")

# フェイク claude（bash）。--version に応答し、それ以外は呼び出しを記録して
# シナリオを実行する。cwd はスクリプトがリポジトリルートに固定するため、
# 相対パスで tickets/ を操作できる。TID は駆動プロンプト1行目から取り出す
FAKE_HEADER = """#!/bin/bash
if [ "$1" = "--version" ]; then echo "fake-claude 0.0.1"; exit 0; fi
printf '%s\\n---call---\\n' "$*" >> claude_calls.log
TID=$(printf '%s' "$2" | head -n1 | awk '{print $2}')
finish_ok() {
  sed -i 's/^status: .*/status: done/' "tickets/active/${TID}_t.md"
  mv "tickets/active/${TID}_t.md" "tickets/done/${TID}_t.md"
}
"""


def make_entry(loc="done", status="done", tti=0, rti=0, rtv=0):
    """judge_boundary 単体テスト用のチケット状態エントリ。"""
    return {
        "location": loc,
        "path": None,
        "status": status,
        "retry": {
            "tester_to_implementer": tti,
            "reviewer_to_implementer": rti,
            "reviewer_to_investigator": rtv,
        },
        "title": "t",
    }


class BatchLoopBase(unittest.TestCase):
    """tempdir にダミーのリポジトリルート（tickets/・docs/SPEC.md）を構築する。"""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="klk_batch_")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        os.makedirs(os.path.join(self.root, "tickets", "active"))
        os.makedirs(os.path.join(self.root, "tickets", "done"))
        os.makedirs(os.path.join(self.root, "docs"))
        with open(os.path.join(self.root, "docs", "SPEC.md"), "w",
                  encoding="utf-8") as f:
            f.write("# SPEC\n")

    def add_ticket(self, tid, status="todo", dirname="active", filename=None,
                   **kwargs):
        return _util.write_ticket(
            self.root, filename or "%s_t.md" % tid, dirname=dirname,
            tid=tid, status=status, **kwargs)

    def set_updated(self, path, value):
        """_util テンプレート固定の updated を書き換える。"""
        with open(path, encoding="utf-8") as f:
            text = f.read()
        with open(path, "w", encoding="utf-8") as f:
            f.write(text.replace('updated: "2026-06-14"', 'updated: "%s"' % value))

    def write_fake(self, scenario=""):
        path = os.path.join(self.root, "fake_claude")
        with open(path, "w", encoding="utf-8") as f:
            f.write(FAKE_HEADER + scenario + "\nexit 0\n")
        os.chmod(path, 0o755)
        return path

    def calls(self):
        log = os.path.join(self.root, "claude_calls.log")
        if not os.path.exists(log):
            return []
        with open(log, encoding="utf-8") as f:
            return [c for c in f.read().split("---call---") if c.strip()]

    def run_main(self, argv, root=None):
        out = io.StringIO()
        err = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = batch_loop.main(argv, root=root or self.root)
        return rc, out.getvalue() + err.getvalue()


# ---------------------------------------------------------------------------
# プリフライト P1〜P9（--dry-run で検証。セッションは起動しない）
# ---------------------------------------------------------------------------

class TestPreflight(BatchLoopBase):
    def dry(self, *ids, extra=()):
        fake = self.write_fake()
        return self.run_main(["--dry-run", "--claude-cmd", fake,
                              *extra, *ids])

    def test_dry_run_ok(self):
        self.add_ticket("KLK-101")
        rc, out = self.dry("KLK-101")
        self.assertEqual(rc, 0)
        self.assertIn("プリフライト: OK", out)
        self.assertIn("fake-claude 0.0.1", out)  # P7 のバージョン表示
        self.assertIn("実行コマンドライン", out)
        self.assertEqual(self.calls(), [])  # dry-run ではセッションを起動しない

    def test_p1_missing_active_dir(self):
        shutil.rmtree(os.path.join(self.root, "tickets", "active"))
        rc, out = self.dry("KLK-101")
        self.assertEqual(rc, 2)
        self.assertIn("P1", out)

    @unittest.skipUnless(shutil.which("git"), "git が利用できない環境")
    def test_p1_linked_worktree(self):
        base = tempfile.mkdtemp(prefix="klk_wt_")
        self.addCleanup(shutil.rmtree, base, ignore_errors=True)
        main_repo = os.path.join(base, "main")
        os.makedirs(main_repo)
        git = ["git", "-c", "user.email=t@t", "-c", "user.name=t"]
        subprocess.run(["git", "init", "-q"], cwd=main_repo, check=True)
        with open(os.path.join(main_repo, "a.txt"), "w") as f:
            f.write("a\n")
        subprocess.run(["git", "add", "a.txt"], cwd=main_repo, check=True)
        subprocess.run(git + ["commit", "-qm", "init"], cwd=main_repo, check=True)
        subprocess.run(["git", "worktree", "add", "-q", "../wt"],
                       cwd=main_repo, check=True)
        wt = os.path.join(base, "wt")
        os.makedirs(os.path.join(wt, "tickets", "active"))
        os.makedirs(os.path.join(wt, "docs"))
        with open(os.path.join(wt, "docs", "SPEC.md"), "w") as f:
            f.write("# SPEC\n")
        _util.write_ticket(wt, "KLK-101_t.md", tid="KLK-101")
        fake = self.write_fake()
        rc, out = self.run_main(
            ["--dry-run", "--claude-cmd", fake, "KLK-101"], root=wt)
        self.assertEqual(rc, 2)
        self.assertIn("linked worktree", out)

    def test_p2_missing_ticket(self):
        rc, out = self.dry("KLK-999")
        self.assertEqual(rc, 2)
        self.assertIn("P2: KLK-999: tickets/active/ に見つかりません", out)

    def test_p2_multiple_match(self):
        self.add_ticket("KLK-101", filename="KLK-101_a.md")
        self.add_ticket("KLK-101", filename="KLK-101_b.md")
        rc, out = self.dry("KLK-101")
        self.assertEqual(rc, 2)
        self.assertIn("複数マッチ", out)

    def test_p2_duplicate_args(self):
        self.add_ticket("KLK-101")
        rc, out = self.dry("KLK-101", "KLK-101")
        self.assertEqual(rc, 2)
        self.assertIn("重複", out)

    def test_p2_invalid_id_format(self):
        rc, out = self.dry("../evil")
        self.assertEqual(rc, 2)
        self.assertIn("不正な文字列", out)

    def test_p3_excluded_statuses(self):
        self.add_ticket("KLK-101", status="blocked")
        self.add_ticket("KLK-102", status="cancelled")
        self.add_ticket("KLK-103", status="done")
        rc, out = self.dry("KLK-101", "KLK-102", "KLK-103")
        self.assertEqual(rc, 2)
        for tid in ("KLK-101", "KLK-102", "KLK-103"):
            self.assertIn("P3: %s" % tid, out)

    def test_p3_intermediate_statuses_allowed(self):
        # todo〜test_passed の各中間statusから開始できる。
        # P4（in_progress上限3）に抵触しないよう2組に分けて確認する
        self.add_ticket("KLK-101", status="todo")
        self.add_ticket("KLK-102", status="implementation_done")
        self.add_ticket("KLK-103", status="test_passed")
        rc, out = self.dry("KLK-101", "KLK-102", "KLK-103")
        self.assertEqual(rc, 0, out)

    def test_p3_intermediate_statuses_allowed_2(self):
        self.add_ticket("KLK-104", status="investigation_done")
        self.add_ticket("KLK-105", status="design_done")
        rc, out = self.dry("KLK-104", "KLK-105")
        self.assertEqual(rc, 0, out)

    def test_p3_invalid_status(self):
        self.add_ticket("KLK-101", status="doing")
        rc, out = self.dry("KLK-101")
        self.assertEqual(rc, 2)
        self.assertIn("P3: KLK-101", out)

    def test_p3_broken_frontmatter(self):
        path = os.path.join(self.root, "tickets", "active", "KLK-101_t.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("# frontmatter なし\n")
        rc, out = self.dry("KLK-101")
        self.assertEqual(rc, 2)
        self.assertIn("frontmatter を解析できません", out)

    def test_p4_under_limit_ok(self):
        self.add_ticket("KLK-101", status="todo")
        self.add_ticket("KLK-201", status="implementation_done")
        self.add_ticket("KLK-202", status="test_passed")
        rc, out = self.dry("KLK-101")
        self.assertEqual(rc, 0, out)

    def test_p4_at_limit_stops(self):
        self.add_ticket("KLK-101", status="todo")
        self.add_ticket("KLK-201", status="implementation_done")
        self.add_ticket("KLK-202", status="test_passed")
        self.add_ticket("KLK-203", status="design_done")
        rc, out = self.dry("KLK-101")
        self.assertEqual(rc, 2)
        self.assertIn("P4", out)

    def test_p5_blocked_over_14_days_stops(self):
        self.add_ticket("KLK-101", status="todo")
        path = self.add_ticket("KLK-201", status="blocked")
        self.set_updated(path, (date.today() - timedelta(days=15)).isoformat())
        rc, out = self.dry("KLK-101")
        self.assertEqual(rc, 2)
        self.assertIn("P5", out)
        self.assertIn("/triage", out)

    def test_p5_blocked_exactly_14_days_ok(self):
        # 設計書§4 P5 は「14日超」（>14）。ちょうど14日は通す
        self.add_ticket("KLK-101", status="todo")
        path = self.add_ticket("KLK-201", status="blocked")
        self.set_updated(path, (date.today() - timedelta(days=14)).isoformat())
        rc, out = self.dry("KLK-101")
        self.assertEqual(rc, 0, out)

    def test_p6_missing_spec_stops(self):
        os.remove(os.path.join(self.root, "docs", "SPEC.md"))
        self.add_ticket("KLK-101")
        rc, out = self.dry("KLK-101")
        self.assertEqual(rc, 2)
        self.assertIn("P6", out)
        self.assertIn("--allow-missing-spec", out)

    def test_p6_missing_spec_with_flag_ok(self):
        os.remove(os.path.join(self.root, "docs", "SPEC.md"))
        self.add_ticket("KLK-101")
        rc, out = self.dry("KLK-101", extra=("--allow-missing-spec",))
        self.assertEqual(rc, 0, out)

    def test_p7_claude_not_executable(self):
        self.add_ticket("KLK-101")
        rc, out = self.run_main(
            ["--dry-run", "--claude-cmd", "/no/such/claude", "KLK-101"])
        self.assertEqual(rc, 2)
        self.assertIn("P7", out)

    def test_p9_done_over_20_warns_but_ok(self):
        self.add_ticket("KLK-101")
        for i in range(21):
            self.add_ticket("KLK-%03d" % (500 + i), status="done",
                            dirname="done")
        rc, out = self.dry("KLK-101")
        self.assertEqual(rc, 0, out)
        self.assertIn("P9", out)
        self.assertIn("/archive", out)

    def test_violations_reported_in_bulk(self):
        # 全件チェックして一括表示する（最初の違反で打ち切らない）
        os.remove(os.path.join(self.root, "docs", "SPEC.md"))
        rc, out = self.dry("KLK-901", "KLK-902")
        self.assertEqual(rc, 2)
        self.assertIn("KLK-901", out)
        self.assertIn("KLK-902", out)
        self.assertIn("P6", out)

    def test_argparse_no_ids_is_error(self):
        rc, _out = self.run_main([])
        self.assertEqual(rc, 2)


# ---------------------------------------------------------------------------
# 駆動プロンプト・claude コマンドの組み立て
# ---------------------------------------------------------------------------

class TestPromptAndCommand(unittest.TestCase):
    def test_prompt_basic(self):
        prompt = batch_loop.build_prompt("KLK-101", "acceptEdits", False)
        self.assertTrue(prompt.startswith("/start-loop KLK-101\n"))
        self.assertIn("1件のみ", prompt)
        self.assertIn("--permission-mode acceptEdits", prompt)
        self.assertIn("blocked化", prompt)
        self.assertNotIn("SPECゲート", prompt)

    def test_prompt_with_missing_spec(self):
        prompt = batch_loop.build_prompt("KLK-101", "plan", True)
        self.assertIn("--permission-mode plan", prompt)
        self.assertIn("SPECゲートで停止せず", prompt)

    def test_command_defaults(self):
        args = batch_loop.parse_args(["KLK-101"])
        cmd = batch_loop.build_claude_command(args, "PROMPT")
        self.assertEqual(cmd[:3], ["claude", "-p", "PROMPT"])
        self.assertIn("--permission-mode", cmd)
        self.assertEqual(cmd[cmd.index("--permission-mode") + 1], "acceptEdits")
        self.assertEqual(cmd[cmd.index("--max-turns") + 1], "200")
        self.assertNotIn("--max-budget-usd", cmd)
        self.assertNotIn("--bare", cmd)

    def test_command_with_flags(self):
        args = batch_loop.parse_args(
            ["--claude-cmd", "/x/claude", "--max-turns", "50",
             "--max-budget-usd", "2.5", "--permission-mode", "plan", "KLK-101"])
        cmd = batch_loop.build_claude_command(args, "PROMPT")
        self.assertEqual(cmd[0], "/x/claude")
        self.assertEqual(cmd[cmd.index("--max-turns") + 1], "50")
        self.assertEqual(cmd[cmd.index("--max-budget-usd") + 1], "2.5")
        self.assertEqual(cmd[cmd.index("--permission-mode") + 1], "plan")

    def test_max_turns_zero_disables(self):
        args = batch_loop.parse_args(["--max-turns", "0", "KLK-101"])
        cmd = batch_loop.build_claude_command(args, "PROMPT")
        self.assertNotIn("--max-turns", cmd)

    def test_negative_max_turns_rejected(self):
        with self.assertRaises(SystemExit):
            batch_loop.parse_args(["--max-turns", "-1", "KLK-101"])


# ---------------------------------------------------------------------------
# 境界判定 1〜7（純粋関数として分岐・優先順位を網羅）
# ---------------------------------------------------------------------------

class TestJudgeBoundary(unittest.TestCase):
    def judge(self, exit_status=0, cur=None, err=None, body="", out=(),
              snap=None, cont=False):
        return batch_loop.judge_boundary(
            "KLK-101", exit_status, cur, body, err, list(out),
            snap or make_entry(loc="active", status="todo"), cont)

    def test_1_exit_nonzero_stops(self):
        j = self.judge(exit_status=5, cur=make_entry(loc="active", status="todo"))
        self.assertTrue(j.stop)
        self.assertEqual(j.label, "異常終了")

    def test_1_wins_even_if_done(self):
        j = self.judge(exit_status=7, cur=make_entry())
        self.assertTrue(j.stop)
        self.assertEqual(j.label, "異常終了")
        self.assertIn("done に到達", "\n".join(j.lines))

    def test_1_timeout(self):
        j = self.judge(exit_status="timeout", cur=make_entry())
        self.assertTrue(j.stop)
        self.assertEqual(j.label, "異常終了")
        self.assertIn("timeout-min", "\n".join(j.lines))

    def test_fail_closed_on_unreadable_state(self):
        j = self.judge(err="frontmatter を解析できません")
        self.assertTrue(j.stop)
        self.assertEqual(j.label, "状態判定不能")

    def test_2_active_done_remains(self):
        j = self.judge(cur=make_entry(loc="active", status="done"))
        self.assertTrue(j.stop)
        self.assertEqual(j.label, "完了手続き不完全")

    def test_2_wins_over_5_and_6(self):
        j = self.judge(cur=make_entry(loc="active", status="done", tti=1),
                       out=["KLK-102: active/todo → active/done"])
        self.assertEqual(j.label, "完了手続き不完全")

    def test_3_blocked_shows_blocker_body(self):
        body = "# t\n\n## ブロッカー\nAPIキー未発行のため停止\n\n## ログ\n"
        j = self.judge(cur=make_entry(loc="active", status="blocked"), body=body)
        self.assertTrue(j.stop)
        self.assertEqual(j.label, "blocked")
        self.assertIn("APIキー未発行のため停止", "\n".join(j.lines))

    def test_4_incomplete_status(self):
        j = self.judge(cur=make_entry(loc="active", status="implementation_done"))
        self.assertTrue(j.stop)
        self.assertEqual(j.label, "未完了")

    def test_5_out_of_scope_wins_over_6(self):
        j = self.judge(cur=make_entry(tti=1),
                       out=["KLK-102: active/todo → active/design_done"])
        self.assertTrue(j.stop)
        self.assertEqual(j.label, "範囲外変更の検知")

    def test_6_rework_stops_by_default(self):
        j = self.judge(cur=make_entry(tti=1))
        self.assertTrue(j.stop)
        self.assertEqual(j.label, "差し戻し発生（done到達済み）")
        self.assertIn("tester_to_implementer: 0→1", "\n".join(j.lines))

    def test_6_rework_continues_with_flag(self):
        j = self.judge(cur=make_entry(rti=1), cont=True)
        self.assertFalse(j.stop)
        self.assertEqual(j.increments, ["reviewer_to_implementer: 0→1"])

    def test_7_done_continues(self):
        j = self.judge(cur=make_entry())
        self.assertFalse(j.stop)
        self.assertEqual(j.label, "done")


# ---------------------------------------------------------------------------
# E2E（フェイク claude で逐次実行・境界停止・フラグ伝播を検証）
# ---------------------------------------------------------------------------

class TestBatchEndToEnd(BatchLoopBase):
    def batch(self, *ids, scenario="finish_ok", extra=()):
        fake = self.write_fake(scenario)
        return self.run_main(["--yes", "--claude-cmd", fake, *extra, *ids])

    def test_happy_path_two_tickets(self):
        self.add_ticket("KLK-101")
        self.add_ticket("KLK-102", status="design_done")
        rc, out = self.batch("KLK-101", "KLK-102")
        self.assertEqual(rc, 0, out)
        self.assertIn("バッチ完了", out)
        self.assertIn("全 2 件", out)
        calls = self.calls()
        self.assertEqual(len(calls), 2)
        self.assertIn("/start-loop KLK-101", calls[0])
        self.assertIn("/start-loop KLK-102", calls[1])

    def test_prompt_and_default_flags_passed(self):
        self.add_ticket("KLK-101")
        rc, _out = self.batch("KLK-101")
        self.assertEqual(rc, 0)
        call = self.calls()[0]
        self.assertIn("1件のみ", call)
        self.assertIn("--permission-mode acceptEdits", call)
        self.assertIn("--max-turns 200", call)

    def test_flag_propagation(self):
        self.add_ticket("KLK-101")
        rc, _out = self.batch(
            "KLK-101", extra=("--max-turns", "50", "--max-budget-usd", "2.5",
                              "--permission-mode", "plan"))
        self.assertEqual(rc, 0)
        call = self.calls()[0]
        self.assertIn("--max-turns 50", call)
        self.assertIn("--max-budget-usd 2.5", call)
        self.assertIn("--permission-mode plan", call)

    def test_stop_on_nonzero_exit(self):
        self.add_ticket("KLK-101")
        self.add_ticket("KLK-102")
        rc, out = self.batch("KLK-101", "KLK-102", scenario="exit 5")
        self.assertEqual(rc, 3)
        self.assertIn("異常終了", out)
        self.assertEqual(len(self.calls()), 1)  # 2件目は起動しない
        self.assertIn("未実行のチケット: KLK-102", out)

    def test_stop_on_nonzero_exit_even_if_done(self):
        self.add_ticket("KLK-101")
        rc, out = self.batch("KLK-101", scenario="finish_ok\nexit 7")
        self.assertEqual(rc, 3)
        self.assertIn("異常終了", out)
        self.assertIn("done に到達", out)

    def test_stop_on_active_done_remains(self):
        self.add_ticket("KLK-101")
        scenario = 'sed -i "s/^status: .*/status: done/" "tickets/active/${TID}_t.md"'
        rc, out = self.batch("KLK-101", scenario=scenario)
        self.assertEqual(rc, 3)
        self.assertIn("完了手続き不完全", out)

    def test_stop_on_blocked_with_blocker_body(self):
        self.add_ticket("KLK-101", blocker="外部APIの資格情報が未発行")
        scenario = ('sed -i "s/^status: .*/status: blocked/" '
                    '"tickets/active/${TID}_t.md"')
        rc, out = self.batch("KLK-101", scenario=scenario)
        self.assertEqual(rc, 3)
        self.assertIn("blocked", out)
        self.assertIn("外部APIの資格情報が未発行", out)

    def test_stop_on_incomplete_status(self):
        self.add_ticket("KLK-101")
        scenario = ('sed -i "s/^status: .*/status: implementation_done/" '
                    '"tickets/active/${TID}_t.md"')
        rc, out = self.batch("KLK-101", scenario=scenario)
        self.assertEqual(rc, 3)
        self.assertIn("未完了", out)

    def test_stop_on_out_of_scope_change(self):
        self.add_ticket("KLK-101")
        self.add_ticket("KLK-102")
        scenario = (
            'if [ "$TID" = "KLK-101" ]; then\n'
            '  sed -i "s/^status: .*/status: investigation_done/" '
            'tickets/active/KLK-102_t.md\n'
            '  finish_ok\n'
            'fi'
        )
        rc, out = self.batch("KLK-101", "KLK-102", scenario=scenario)
        self.assertEqual(rc, 3)
        self.assertIn("範囲外変更の検知", out)
        self.assertEqual(len(self.calls()), 1)

    def test_stop_on_rework_by_default(self):
        self.add_ticket("KLK-101")
        scenario = (
            'sed -i "s/tester_to_implementer: 0/tester_to_implementer: 1/" '
            '"tickets/active/${TID}_t.md"\n'
            'finish_ok'
        )
        rc, out = self.batch("KLK-101", scenario=scenario)
        self.assertEqual(rc, 3)
        self.assertIn("差し戻し発生", out)
        self.assertIn("tester_to_implementer: 0→1", out)

    def test_rework_continues_with_flag(self):
        self.add_ticket("KLK-101")
        self.add_ticket("KLK-102")
        scenario = (
            'sed -i "s/tester_to_implementer: 0/tester_to_implementer: 1/" '
            '"tickets/active/${TID}_t.md"\n'
            'finish_ok'
        )
        rc, out = self.batch("KLK-101", "KLK-102", scenario=scenario,
                             extra=("--continue-on-rework",))
        self.assertEqual(rc, 0, out)
        self.assertIn("差し戻しあり・続行", out)
        self.assertEqual(len(self.calls()), 2)

    def test_stop_on_ticket_vanished(self):
        self.add_ticket("KLK-101")
        rc, out = self.batch("KLK-101",
                             scenario='rm "tickets/active/${TID}_t.md"')
        self.assertEqual(rc, 3)
        self.assertIn("状態判定不能", out)

    def test_stop_on_corrupt_frontmatter_after_session(self):
        self.add_ticket("KLK-101")
        rc, out = self.batch(
            "KLK-101", scenario='printf "broken" > "tickets/active/${TID}_t.md"')
        self.assertEqual(rc, 3)
        self.assertIn("状態判定不能", out)

    def test_approval_decline_runs_nothing(self):
        self.add_ticket("KLK-101")
        fake = self.write_fake("finish_ok")
        with mock.patch("builtins.input", return_value="n"):
            rc, out = self.run_main(["--claude-cmd", fake, "KLK-101"])
        self.assertEqual(rc, 2)
        self.assertIn("承認が得られなかった", out)
        self.assertEqual(self.calls(), [])

    def test_approval_accept_runs(self):
        self.add_ticket("KLK-101")
        fake = self.write_fake("finish_ok")
        with mock.patch("builtins.input", return_value="y"):
            rc, out = self.run_main(["--claude-cmd", fake, "KLK-101"])
        self.assertEqual(rc, 0, out)
        self.assertEqual(len(self.calls()), 1)

    def test_approval_summary_content(self):
        self.add_ticket("KLK-101")
        rc, out = self.batch("KLK-101")
        self.assertEqual(rc, 0)
        self.assertIn("承認サマリ", out)
        self.assertIn("権限モード: acceptEdits", out)
        self.assertIn("停止条件", out)
        self.assertIn("対話セッションや別バッチを開かない", out)

    def test_internal_error_returns_1(self):
        self.add_ticket("KLK-101")
        with mock.patch.object(batch_loop, "run_preflight",
                               side_effect=RuntimeError("boom")):
            rc, out = self.run_main(["--yes", "KLK-101"])
        self.assertEqual(rc, 1)
        self.assertIn("想定外の内部エラー", out)


# ---------------------------------------------------------------------------
# サブプロセス実行（fail-closed の import 停止・SIGINT）
# ---------------------------------------------------------------------------

class TestSubprocessBehaviors(unittest.TestCase):
    """batch_loop.py をコピーした擬似リポジトリで、プロセスレベルの挙動を検証。"""

    def make_fake_repo(self, with_lib=True):
        base = tempfile.mkdtemp(prefix="klk_repo_")
        self.addCleanup(shutil.rmtree, base, ignore_errors=True)
        os.makedirs(os.path.join(base, "scripts"))
        shutil.copy(BATCH_SCRIPT, os.path.join(base, "scripts"))
        if with_lib:
            hooks = os.path.join(base, ".claude", "hooks")
            os.makedirs(hooks)
            shutil.copy(TICKET_LIB, hooks)
        os.makedirs(os.path.join(base, "tickets", "active"))
        os.makedirs(os.path.join(base, "tickets", "done"))
        os.makedirs(os.path.join(base, "docs"))
        with open(os.path.join(base, "docs", "SPEC.md"), "w") as f:
            f.write("# SPEC\n")
        return base

    def test_ticket_lib_import_failure_is_fail_closed(self):
        base = self.make_fake_repo(with_lib=False)
        proc = subprocess.run(
            [sys.executable, os.path.join(base, "scripts", "batch_loop.py"),
             "--dry-run", "KLK-101"],
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("_ticket_lib", proc.stdout + proc.stderr)

    def test_sigint_terminates_child_and_exits_130(self):
        base = self.make_fake_repo()
        _util.write_ticket(base, "KLK-101_t.md", tid="KLK-101")
        fake = os.path.join(base, "fake_claude")
        with open(fake, "w") as f:
            f.write('#!/bin/bash\n'
                    'if [ "$1" = "--version" ]; then echo fake; exit 0; fi\n'
                    'touch session_started\n'
                    'exec sleep 30\n')
        os.chmod(fake, 0o755)
        start = time.monotonic()
        proc = subprocess.Popen(
            [sys.executable, os.path.join(base, "scripts", "batch_loop.py"),
             "--yes", "--claude-cmd", fake, "KLK-101"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        try:
            marker = os.path.join(base, "session_started")
            deadline = time.monotonic() + 15
            while not os.path.exists(marker):
                if time.monotonic() > deadline:
                    self.fail("フェイク claude セッションが開始しませんでした")
                time.sleep(0.1)
            proc.send_signal(signal.SIGINT)
            out, _ = proc.communicate(timeout=20)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate()
        elapsed = time.monotonic() - start
        self.assertEqual(proc.returncode, 130)
        self.assertIn("SIGINT", out)
        # 子（sleep 30）を待たずに terminate して速やかに終了していること
        self.assertLess(elapsed, 25)


if __name__ == "__main__":
    unittest.main()
