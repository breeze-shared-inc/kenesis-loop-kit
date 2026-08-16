"""scripts/list_tickets.py（チケット一覧CLI）のテスト

設計書 docs/designs/KLK-003.md §9「受け入れ条件」AC1・AC4に対応する。

モック方針（§9 AC4）: `_util.ticket()`/`_util.write_ticket()` は priority/updated を
パラメータ化していないため流用せず、本ファイル専用の最小限のticket文字列ビルダー
（`make_ticket()`）を用いる。`_util` はリポジトリルート解決（`_util.REPO`）にのみ使う。
"""
import contextlib
import io
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _util  # noqa: E402

sys.path.insert(0, os.path.join(_util.REPO, "scripts"))
import list_tickets  # noqa: E402


TICKET_TEMPLATE = """---
id: "{tid}"
title: "t"
status: {status}
priority: {priority}
type: feature
created: "2026-06-14"
updated: "{updated}"
project: "demo"
tags: []
related_files: []
retry_counts:
  tester_to_implementer: {tti}
  reviewer_to_implementer: {rti}
  reviewer_to_investigator: {rtv}
---

# t

## ログ
"""


def make_ticket(tid="KLK-001", status="todo", priority="medium",
                updated="2026-07-18", tti=0, rti=0, rtv=0):
    """本テスト専用の最小限のticket文字列ビルダー（priority/updatedをパラメータ化）。"""
    return TICKET_TEMPLATE.format(
        tid=tid, status=status, priority=priority, updated=updated,
        tti=tti, rti=rti, rtv=rtv,
    )


def write_file(active_dir, filename, content):
    path = active_dir / filename
    path.write_text(content, encoding="utf-8")
    return path


class ListTicketsBase(unittest.TestCase):
    """tempdirに疑似的な tickets/active/ を構築する。"""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="klk_list_tickets_"))
        self.addCleanup(shutil.rmtree, str(self.root), ignore_errors=True)
        self.active_dir = self.root / "tickets" / "active"
        self.active_dir.mkdir(parents=True)

    def write_ticket(self, filename, **kwargs):
        return write_file(self.active_dir, filename, make_ticket(**kwargs))


# ---------------------------------------------------------------------------
# build_row: 正常系・異常系（malformed frontmatterの可視化）
# ---------------------------------------------------------------------------

class TestBuildRow(ListTicketsBase):
    def test_normal_row(self):
        path = self.write_ticket(
            "KLK-002_t.md", tid="KLK-002", status="test_passed",
            priority="high", updated="2026-07-18 09:00", tti=2, rti=1, rtv=0)
        row, err = list_tickets.build_row(path)
        self.assertIsNone(err)
        self.assertEqual(row, {
            "id": "KLK-002",
            "status": "test_passed",
            "priority": "high",
            "updated": "2026-07-18 09:00",
            "tti": 2,
            "rti": 1,
            "rtv": 0,
        })

    def test_no_frontmatter(self):
        path = write_file(self.active_dir, "KLK-900_broken.md",
                          "# no frontmatter here\njust text\n")
        row, err = list_tickets.build_row(path)
        self.assertIsNone(row)
        self.assertIn("frontmatter", err)

    def test_missing_required_keys(self):
        # priority と updated を欠落させる
        content = """---
id: "KLK-901"
status: todo
retry_counts:
  tester_to_implementer: 0
  reviewer_to_implementer: 0
  reviewer_to_investigator: 0
---
# t
"""
        path = write_file(self.active_dir, "KLK-901_t.md", content)
        row, err = list_tickets.build_row(path)
        self.assertIsNone(row)
        self.assertIn("priority", err)
        self.assertIn("updated", err)

    def test_retry_counts_not_dict(self):
        content = """---
id: "KLK-902"
status: todo
priority: medium
updated: "2026-07-18"
retry_counts: none
---
# t
"""
        path = write_file(self.active_dir, "KLK-902_t.md", content)
        row, err = list_tickets.build_row(path)
        self.assertIsNone(row)
        self.assertIn("retry_counts", err)

    def test_retry_counts_missing_key(self):
        content = """---
id: "KLK-903"
status: todo
priority: medium
updated: "2026-07-18"
retry_counts:
  tester_to_implementer: 0
  reviewer_to_implementer: 0
---
# t
"""
        path = write_file(self.active_dir, "KLK-903_t.md", content)
        row, err = list_tickets.build_row(path)
        self.assertIsNone(row)
        self.assertIn("reviewer_to_investigator", err)

    def test_retry_counts_non_integer(self):
        content = """---
id: "KLK-904"
status: todo
priority: medium
updated: "2026-07-18"
retry_counts:
  tester_to_implementer: abc
  reviewer_to_implementer: 0
  reviewer_to_investigator: 0
---
# t
"""
        path = write_file(self.active_dir, "KLK-904_t.md", content)
        row, err = list_tickets.build_row(path)
        self.assertIsNone(row)
        self.assertIn("tester_to_implementer", err)


# ---------------------------------------------------------------------------
# collect: フィルタリング・ソート・行/エラーの集計
# ---------------------------------------------------------------------------

class TestCollect(ListTicketsBase):
    def test_collect_normal_rows_status_priority_mixed(self):
        self.write_ticket("KLK-002_a.md", tid="KLK-002", status="todo",
                          priority="high", updated="2026-07-01",
                          tti=1, rti=0, rtv=0)
        self.write_ticket("KLK-010_b.md", tid="KLK-010", status="done",
                          priority="low", updated="2026-07-10",
                          tti=0, rti=2, rtv=1)
        rows, errors = list_tickets.collect(self.active_dir)
        self.assertEqual(errors, [])
        self.assertEqual(len(rows), 2)
        by_id = {r["id"]: r for r in rows}
        self.assertEqual(by_id["KLK-002"]["status"], "todo")
        self.assertEqual(by_id["KLK-002"]["priority"], "high")
        self.assertEqual(by_id["KLK-010"]["status"], "done")
        self.assertEqual(by_id["KLK-010"]["rti"], 2)
        self.assertEqual(by_id["KLK-010"]["rtv"], 1)

    def test_collect_sorted_by_filename_ascending(self):
        # 書き込み順をid降順にして、ファイル名昇順ソートを検証する
        self.write_ticket("KLK-010_b.md", tid="KLK-010")
        self.write_ticket("KLK-002_a.md", tid="KLK-002")
        rows, _errors = list_tickets.collect(self.active_dir)
        self.assertEqual([r["id"] for r in rows], ["KLK-002", "KLK-010"])

    def test_collect_reports_errors_and_excludes_from_rows(self):
        self.write_ticket("KLK-020_ok.md", tid="KLK-020")
        write_file(self.active_dir, "KLK-999_broken.md", "no frontmatter\n")
        rows, errors = list_tickets.collect(self.active_dir)
        self.assertEqual([r["id"] for r in rows], ["KLK-020"])
        self.assertEqual(len(errors), 1)
        self.assertTrue(errors[0].startswith("KLK-999_broken.md: "))

    def test_collect_excludes_index_md(self):
        self.write_ticket("KLK-030_ok.md", tid="KLK-030")
        # _index.md は is_ticket() が対象外と判定するため、ticket形式の内容でも除外される
        write_file(self.active_dir, "_index.md", make_ticket(tid="KLK-999"))
        rows, errors = list_tickets.collect(self.active_dir)
        self.assertEqual([r["id"] for r in rows], ["KLK-030"])
        self.assertEqual(errors, [])


# ---------------------------------------------------------------------------
# main: tickets/active/ 不在時の致命的エラー・正常系の出力フォーマット
# ---------------------------------------------------------------------------

class TestMain(ListTicketsBase):
    def run_main(self, root=None):
        out = io.StringIO()
        err = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = list_tickets.main(root=root if root is not None else self.root)
        return rc, out.getvalue(), err.getvalue()

    def test_missing_active_dir_returns_nonzero(self):
        empty_root = Path(tempfile.mkdtemp(prefix="klk_list_tickets_empty_"))
        self.addCleanup(shutil.rmtree, str(empty_root), ignore_errors=True)
        rc, _out, err = self.run_main(root=empty_root)
        self.assertNotEqual(rc, 0)
        self.assertIn("tickets/active", err)

    def test_main_outputs_rows_and_errors_with_exit_zero(self):
        self.write_ticket("KLK-005_t.md", tid="KLK-005", status="design_done",
                          priority="medium", updated="2026-07-15")
        write_file(self.active_dir, "KLK-777_broken.md", "not a ticket\n")
        rc, out, _err = self.run_main()
        self.assertEqual(rc, 0)
        self.assertIn("凡例:", out)
        self.assertIn("KLK-005", out)
        self.assertIn("ERROR KLK-777_broken.md:", out)
        self.assertIn("計 1 件（エラー 1 件）", out)


if __name__ == "__main__":
    unittest.main()
