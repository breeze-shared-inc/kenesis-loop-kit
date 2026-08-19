#!/usr/bin/env python3
"""Kenesis Loop Kit - チケット一覧CLI（frontmatterスキャン）

orchestratorが作業開始時に `tickets/active/` を全件フル読みする代わりに、
frontmatter（id / status / priority / retry_counts / updated）のみを
コンパクトな一覧として出力する。設計の正: docs/designs/KLK-003.md。

規約:
- stdlib のみ。外部依存なし
- tickets/ 配下へは一切書き込まない（読み取り専用）
- CLIはパスを表す位置引数・オプション引数を一切持たない。常に
  `<リポジトリルート>/tickets/active/` を対象にする（ルートは
  Path(__file__).resolve().parents[1] で自己解決）。テスト用のルート注入は
  main(root=None) という Python 関数引数（CLI引数ではない）で行う
  （scripts/batch_loop.py の main(argv=None, root=None) と同じ設計）。
  この制約は .claude/hooks/guard_bash_writes.py の mentions_guarded() を
  発動させない（Bashコマンド文字列に "tickets/active" というリテラルが
  現れない）ための必須設計であり、崩してはならない。将来パスを引数化する
  変更を行う場合は、guard_bash_writes.py の READONLY_SCRIPTS にこの
  スクリプトを追加する変更が必須になる

使い方:
    python3 scripts/list_tickets.py
"""
import sys
from pathlib import Path

# _ticket_lib（frontmatterパーサ・is_ticket）はスクリプトと同じリポジトリの
# .claude/hooks/ から import する（scripts/batch_loop.py と同じ手法）。
_HOOKS_DIR = str(Path(__file__).resolve().parents[1] / ".claude" / "hooks")
sys.path.insert(0, _HOOKS_DIR)
import _ticket_lib as lib  # noqa: E402

REQUIRED_LIST_FIELDS = ("id", "status", "priority", "updated")

# retry_counts の frontmatterキー -> 一覧の列名（略称）
RETRY_COLUMNS = (
    ("tti", "tester_to_implementer"),
    ("rti", "reviewer_to_implementer"),
    ("rtv", "reviewer_to_investigator"),
)

LEGEND = ("凡例: tti=tester→implementer rti=reviewer→implementer "
          "rtv=reviewer→investigator")

# 列幅は目安（実データがはみ出しても右へずれるだけでよい。厳密な整列は対象外）
ROW_FORMAT = "%-12s%-22s%-10s%-5s%-5s%-5s%s"


def build_row(path):
    """1チケットファイルを読み、(row, None) または (None, error_message) を返す。
    row のキー: id, status, priority, updated（すべて文字列）、
    tti, rti, rtv（すべて int）。row と error_message は排他。
    frontmatterが無い/必須フィールド欠落/retry_countsが不正な場合は
    row=None かつ error_message に理由を入れる（黙ってスキップしない）。
    error_message はファイル名を含まない（呼び出し側の collect() が付す）。"""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, "読み取り失敗: %s" % exc

    fm = lib.parse_frontmatter(text)
    if fm is None:
        return None, "frontmatter を解析できません"

    missing = [key for key in REQUIRED_LIST_FIELDS if key not in fm]
    if missing:
        return None, ("必須キーが frontmatter に存在しません: %s"
                      % ", ".join(missing))

    rc = fm.get("retry_counts")
    if not isinstance(rc, dict):
        return None, "retry_counts がマッピングとして存在しません"

    retry = {}
    for column, key in RETRY_COLUMNS:
        if key not in rc:
            return None, "retry_counts.%s が存在しません" % key
        try:
            retry[column] = int(rc[key])
        except (TypeError, ValueError):
            return None, ("retry_counts.%s が整数ではありません: %r"
                          % (key, rc[key]))

    row = {
        "id": str(fm["id"]),
        "status": str(fm["status"]),
        "priority": str(fm["priority"]),
        "updated": str(fm["updated"]),
        "tti": retry["tti"],
        "rti": retry["rti"],
        "rtv": retry["rtv"],
    }
    return row, None


def collect(active_dir):
    """active_dir 配下を `lib.is_ticket()` でフィルタしつつファイル名昇順で
    走査し、(rows, errors) を返す。rows は build_row が成功した行のみ、
    errors は "<filename>: <理由>" 形式の文字列リスト。"""
    rows = []
    errors = []
    for path in sorted(active_dir.glob("*.md"), key=lambda p: p.name):
        if not lib.is_ticket(str(path)):
            continue
        row, err = build_row(path)
        if err:
            errors.append("%s: %s" % (path.name, err))
        else:
            rows.append(row)
    return rows, errors


def format_header():
    return ROW_FORMAT % ("id", "status", "priority", "tti", "rti", "rtv",
                        "updated")


def format_row(row):
    return ROW_FORMAT % (row["id"], row["status"], row["priority"],
                        row["tti"], row["rti"], row["rtv"], row["updated"])


def format_target(active_dir):
    """対象ディレクトリの絶対パスを1行で表す(H1: cwd依存の無言0件対策の可視化)。
    root は main() で Path(root).resolve() 済み(または既定値が絶対)のため、
    active_dir は常に絶対パスであることが呼び出し前提。"""
    return "対象: %s" % active_dir


def main(root=None):
    """root（省略時は Path(__file__).resolve().parents[1]）配下の
    tickets/active/ を一覧表示する。tickets/active/ が存在しなければ
    stderr にエラーを書き 1 を返す（致命的エラー）。存在すれば凡例行・
    ヘッダ行・データ行・ERROR行・件数サマリを stdout に出力し 0 を返す
    （ERROR行があっても0のまま。ツール自体はinformationalであり、
    個別チケットの不整合はorchestrator/testerが後続で対処する）。"""
    root = Path(root).resolve() if root is not None else Path(__file__).resolve().parents[1]
    active_dir = root / "tickets" / "active"
    if not active_dir.is_dir():
        sys.stderr.write("エラー: tickets/active/ が見つかりません: %s\n"
                         % active_dir)
        return 1

    rows, errors = collect(active_dir)

    print(format_target(active_dir))
    print(LEGEND)
    print(format_header())
    for row in rows:
        print(format_row(row))
    for err in errors:
        print("ERROR %s" % err)
    print("計 %d 件（エラー %d 件）" % (len(rows), len(errors)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
