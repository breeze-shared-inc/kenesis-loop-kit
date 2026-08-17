"""AC4（KLK-027）: git check-ignoreの実行結果でdocs/reports/{ID}/のプリセット別
ignore実挙動を固定する回帰ガード。

docs/designs/KLK-027.md §10の決定(a)（2026-08-17 19:40）に基づき、publicプリセットでは
docs/reports/{ID}/配下がIGNOREDに、docs/reports/README.mdは常にNOT IGNOREDになることを、
一時gitリポジトリ上で実際にgit check-ignoreを実行して検証する。
tests/test_klk026_doc_wiring.py の TestGitignorePresetAsymmetry（文字列存在チェックのみ）を
実挙動検証まで拡張する統合テストであり、tests/test_metrics.py の TestRecorder
（サブプロセス実行パターン）を踏襲する。
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _util  # noqa: E402

GITIGNORE_PUBLIC = os.path.join(_util.REPO, ".gitignore.public")
GITIGNORE_PRIVATE = os.path.join(_util.REPO, ".gitignore.private")


def make_repo_with_gitignore(gitignore_src):
    """一時gitリポジトリを作成しgitignore_srcの内容を.gitignoreとして配置する。
    呼び出し側がcleanup()すること。"""
    tmp = tempfile.TemporaryDirectory()
    cwd = tmp.name
    subprocess.run(["git", "init", "-q"], cwd=cwd, check=True)
    shutil.copyfile(gitignore_src, os.path.join(cwd, ".gitignore"))
    return tmp


def check_ignore(cwd, path):
    """git check-ignoreを実行し (is_ignored, returncode) を返す。
    rc=0: ignored, rc=1: not ignored。他のrcは実行時異常としてfailさせる。"""
    proc = subprocess.run(["git", "check-ignore", path],
                           cwd=cwd, capture_output=True, text=True)
    if proc.returncode not in (0, 1):
        raise AssertionError(
            "git check-ignoreが異常終了 (rc=%d): %s" % (proc.returncode, proc.stderr))
    return proc.returncode == 0, proc.returncode


class TestPublicPresetGitCheckIgnore(unittest.TestCase):
    """AC4(a): publicプリセットではdocs/reports/{ID}/配下がIGNOREDに、
    docs/reports/README.mdは常にNOT IGNOREDになる。"""

    @classmethod
    def setUpClass(cls):
        cls.tmp = make_repo_with_gitignore(GITIGNORE_PUBLIC)
        cls.cwd = cls.tmp.name

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_report_id_subdir_file_is_ignored(self):
        ignored, rc = check_ignore(self.cwd, "docs/reports/APP-001/investigation.md")
        self.assertTrue(ignored, "IGNOREDのはず (rc=%d)" % rc)

    def test_reports_readme_is_not_ignored(self):
        ignored, rc = check_ignore(self.cwd, "docs/reports/README.md")
        self.assertFalse(ignored, "NOT IGNOREDのはず (rc=%d)" % rc)


class TestPrivatePresetGitCheckIgnore(unittest.TestCase):
    """AC4(a)対比: privateプリセットではdocs/reports/配下が常にNOT IGNORED
    （KLK-026 AC5決定）。"""

    @classmethod
    def setUpClass(cls):
        cls.tmp = make_repo_with_gitignore(GITIGNORE_PRIVATE)
        cls.cwd = cls.tmp.name

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_report_id_subdir_file_is_not_ignored(self):
        ignored, _ = check_ignore(self.cwd, "docs/reports/APP-001/investigation.md")
        self.assertFalse(ignored)

    def test_reports_readme_is_not_ignored(self):
        ignored, _ = check_ignore(self.cwd, "docs/reports/README.md")
        self.assertFalse(ignored)


if __name__ == "__main__":
    unittest.main()
