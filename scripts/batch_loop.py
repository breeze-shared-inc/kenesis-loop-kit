#!/usr/bin/env python3
"""Kenesis Loop Kit - バッチ外部駆動スクリプト（1チケット = 1セッション）

チケットごとに `claude -p "/start-loop {ID}"` を新規ヘッドレスセッションとして
逐次起動し、セッション終了ごとの境界でチケットファイルの状態を検査して
前進・停止を判定する。人間がターミナルで実行する監督ツール。
設計の正: docs/designs/KLK-001.md（プリフライトP1〜P9・境界判定1〜7）

規約:
- stdlib のみ。外部依存なし
- fail-closed: 内部エラー・判定不能時は停止する（hooks の fail-open 規約とは逆。
  本スクリプトは「疑わしければ止まって見せる」が安全側）
- tickets/ 配下へは一切書き込まない（読み取り専用。単一ライター原則の維持）
- 引数はチケットIDのみを受け付け、チケットのパスを引数に取らない
  （guard_bash_writes.py のパス言及検査に掛からない構造を維持する）

終了コード:
    0   全チケット done 到達（--dry-run のプリフライト通過も 0）
    1   想定外の内部エラー
    2   プリフライト・引数エラー・承認の不成立
    3   停止条件による中断（境界判定）
    130 SIGINT（子プロセスを terminate して中断）
"""
import argparse
import glob
import os
import re
import subprocess
import sys
import time
import traceback
from collections import namedtuple
from datetime import date, datetime
from pathlib import Path

# _ticket_lib（frontmatterパーサ・status定数）はスクリプトと同じリポジトリの
# .claude/hooks/ から import する。失敗時は駆動を開始しない（fail-closed）
_HOOKS_DIR = str(Path(__file__).resolve().parents[1] / ".claude" / "hooks")
sys.path.insert(0, _HOOKS_DIR)
try:
    import _ticket_lib as lib
except Exception as exc:  # pragma: no cover - 正常環境では到達しない
    sys.stderr.write(
        "エラー: _ticket_lib.py を import できません: %s\n"
        "       %s/_ticket_lib.py を確認してください。"
        "駆動を開始しません（fail-closed）\n" % (exc, _HOOKS_DIR)
    )
    sys.exit(2)

DEFAULT_PERMISSION_MODE = "acceptEdits"
DEFAULT_MAX_TURNS = 200
DEFAULT_CLAUDE_CMD = "claude"
# これらの status からはバッチを開始できない（todo〜test_passed の再開は許可）
EXCLUDED_START_STATUSES = {"cancelled", "blocked", "done"}
# P5: blocked のまま updated からこの日数を超えたチケットがあれば開始しない
# （設計書§4 P5「14日超」。/start-loop 起動時チェックリストのトリアージ対話が
# ヘッドレスで袋小路になるため事前排除する）
BLOCKED_TRIAGE_DAYS = 14
# P9: tickets/done/ がこの件数を超えたら警告（/archive 提案。開始は妨げない）
DONE_ARCHIVE_THRESHOLD = 20

# チケットIDとして受け付ける形式（パス区切り・glob文字の混入を拒否する）
ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*\Z")

# 駆動プロンプト（設計書§4「駆動プロンプト」の写し。変更時は設計書と同期させること）
PROMPT_TEMPLATE = """/start-loop {tid}

【外部バッチ駆動の前提（scripts/batch_loop.py が起動したヘッドレスセッション）】
- このセッションで処理するのはチケット {tid} の1件のみ。done到達（reviewer承認・done/へ移動・
  完了ログ追記まで）または blocked 化の時点で、要約を報告してセッションを終了すること。
  他のチケットへは着手しない。次チケットへの継続判断は駆動スクリプトと人間が行う
- 権限モードは駆動側が --permission-mode {mode} で明示済み。起動時チェックリストの
  「Autoモード確認」は充足として扱ってよい。14日blocked・in_progress上限は駆動側の
  プリフライトで確認済み。done/件数超過があれば報告のみ行い停止しない
- 人間の応答が必要な場面（AskUserQuestion・リトライ予算のリセット・改善ループ判断・
  破壊的操作の確認）では待機せず、チケットをblocked化（ブロッカーセクションへ理由を記録）
  して報告・終了すること"""

# --allow-missing-spec 指定時のみ追記する免除前提
MISSING_SPEC_SUPPLEMENT = """
- docs/SPEC.md が無い/対象外であることは人間が承認済み（チケットのログを参照）。
  SPECゲートで停止せず、チケットに記載された要件の正に従うこと"""

# 境界判定の結果。stop=True なら報告して中断（exit 3）
Judgment = namedtuple("Judgment", ["stop", "label", "lines", "increments"])


def say(*args_):
    """ライブ監視用に必ず flush して表示する（子プロセス出力との順序を保つ）。"""
    print(*args_, flush=True)


# ---------------------------------------------------------------------------
# 引数
# ---------------------------------------------------------------------------

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="batch_loop.py",
        description="チケットごとに claude -p \"/start-loop {ID}\" を新規セッションで"
                    "逐次起動する外部駆動スクリプト（設計: docs/designs/KLK-001.md）",
        epilog="例: python3 scripts/batch_loop.py APP-001 APP-002",
    )
    parser.add_argument("ids", nargs="+", metavar="ID",
                        help="実行順のチケットID（1件以上・重複不可）")
    parser.add_argument("--dry-run", action="store_true",
                        help="プリフライトのみ実行して終了（/batch-loop コマンドが利用）")
    parser.add_argument("--yes", action="store_true",
                        help="実行前の承認プロンプト（y/N）をスキップ")
    parser.add_argument("--permission-mode", default=DEFAULT_PERMISSION_MODE,
                        metavar="MODE",
                        help="claude へ渡す権限モード（既定: %(default)s）")
    parser.add_argument("--max-turns", type=int, default=DEFAULT_MAX_TURNS,
                        metavar="N",
                        help="セッションあたりのターン上限（既定: %(default)s。0で無効）")
    parser.add_argument("--max-budget-usd", type=float, default=None, metavar="X",
                        help="セッションあたりの費用上限（既定: なし）")
    parser.add_argument("--timeout-min", type=float, default=None, metavar="N",
                        help="セッションあたりの実時間上限・分（既定: なし。"
                             "超過時は子プロセスを terminate して異常終了扱い）")
    parser.add_argument("--continue-on-rework", action="store_true",
                        help="差し戻し検知（retry_counts増分）でも次チケットへ進む（既定: 停止）")
    parser.add_argument("--allow-missing-spec", action="store_true",
                        help="docs/SPEC.md 不在を人間承認済みとして免除前提をプロンプトに付す")
    parser.add_argument("--claude-cmd", default=DEFAULT_CLAUDE_CMD, metavar="PATH",
                        help="claude CLI のパス（既定: %(default)s）")
    args = parser.parse_args(argv)
    if args.max_turns < 0:
        parser.error("--max-turns は 0 以上を指定してください")
    if args.max_budget_usd is not None and args.max_budget_usd <= 0:
        parser.error("--max-budget-usd は正の値を指定してください")
    if args.timeout_min is not None and args.timeout_min <= 0:
        parser.error("--timeout-min は正の値を指定してください")
    return args


# ---------------------------------------------------------------------------
# チケット読み取り（読み取り専用）
# ---------------------------------------------------------------------------

def find_ticket_files(root, tid, dirname):
    """tickets/<dirname>/{ID}_*.md にマッチする実チケットのリスト。"""
    directory = root / "tickets" / dirname
    if not directory.is_dir():
        return []
    pattern = glob.escape(tid) + "_*.md"
    return sorted(p for p in directory.glob(pattern) if lib.is_ticket(str(p)))


def retry_ints(fm):
    """frontmatter から retry_counts を {key: int} で返す。解析不能なら None。"""
    rc = fm.get("retry_counts")
    if not isinstance(rc, dict):
        return None
    out = {}
    for key in lib.RETRY_CAPS:
        try:
            out[key] = int(rc[key])
        except (KeyError, TypeError, ValueError):
            return None
    return out


def read_entry_at(loc, path):
    """チケットファイルを読み (entry, body, err) を返す。err は fail-closed 用。"""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, "", "読み取り失敗: %s" % exc
    fm = lib.parse_frontmatter(text)
    if fm is None:
        return None, "", "frontmatter を解析できません"
    status = fm.get("status")
    if status not in lib.VALID_STATUS:
        return None, "", "status が不正です: %r" % (status,)
    retry = retry_ints(fm)
    if retry is None:
        return None, "", "retry_counts を解析できません"
    _, body = lib.split_frontmatter(text)
    entry = {
        "location": loc,
        "path": path,
        "status": status,
        "retry": retry,
        "title": str(fm.get("title", "")),
    }
    return entry, body, None


def locate_ticket(root, tid):
    """active/ → done/ の順に探し (location, path, err) を返す。"""
    for loc in ("active", "done"):
        matches = find_ticket_files(root, tid, loc)
        if len(matches) > 1:
            return None, None, "tickets/%s/ に複数マッチ: %s" % (
                loc, ", ".join(p.name for p in matches))
        if matches:
            return loc, matches[0], None
    return None, None, "tickets/active|done/ に見つかりません"


def read_entry(root, tid):
    """チケットの現在状態を (entry, body, err) で返す。"""
    loc, path, err = locate_ticket(root, tid)
    if err:
        return None, "", err
    return read_entry_at(loc, path)


def extract_blocker(body):
    """本文の「## ブロッカー」セクションを取り出す。"""
    captured = []
    in_section = False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            if in_section:
                break
            in_section = (stripped == "## ブロッカー")
            continue
        if in_section:
            captured.append(line)
    text = "\n".join(captured).strip()
    return text or "（ブロッカーセクションが空です）"


def parse_updated(value):
    """frontmatter updated の先頭10文字を日付として解釈する。不能なら None。"""
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# プリフライト P1〜P9（全件チェックして違反を一括表示。1件でもあれば開始しない）
# ---------------------------------------------------------------------------

def linked_worktree_reason(root):
    """linked worktree なら理由文字列を返す。git 利用不可・判定不能なら None
    （設計書§4 P1: git 利用可能な場合のみ検査する）。"""
    def rev_parse(arg):
        proc = subprocess.run(
            ["git", "rev-parse", arg], cwd=str(root),
            capture_output=True, text=True, timeout=30,
        )
        return proc.stdout.strip() if proc.returncode == 0 else None

    try:
        git_dir = rev_parse("--git-dir")
        common_dir = rev_parse("--git-common-dir")
    except (OSError, subprocess.SubprocessError):
        return None
    if not git_dir or not common_dir:
        return None
    resolve = lambda p: os.path.realpath(os.path.join(str(root), p))  # noqa: E731
    if resolve(git_dir) != resolve(common_dir):
        return ("linked worktree 上ではバッチを実行できません。チケット書き込みは"
                "メイン worktree に一本化してください（docs/worktree-policy.md）")
    return None


def claude_version(claude_cmd, root):
    """`claude --version` の出力文字列。実行不能なら None。"""
    try:
        proc = subprocess.run(
            [claude_cmd, "--version"], cwd=str(root),
            capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or proc.stderr.strip() or "(バージョン文字列なし)"


def run_preflight(root, args, today=None):
    """(violations, warnings, info, snapshot) を返す。"""
    today = today or date.today()
    violations = []
    warnings = []
    info = []
    snapshot = {}

    # --- P1: tickets/active/ の存在・linked worktree でないこと
    active_dir = root / "tickets" / "active"
    if not active_dir.is_dir():
        violations.append("P1: tickets/active/ が見つかりません: %s" % active_dir)
    worktree_reason = linked_worktree_reason(root)
    if worktree_reason:
        violations.append("P1: %s" % worktree_reason)

    # --- P2: ID の形式・重複・一意マッチ / P3: status 検証（スナップショット構築）
    seen = set()
    for tid in args.ids:
        if tid in seen:
            violations.append("P2: 引数内でチケットIDが重複しています: %s" % tid)
            continue
        seen.add(tid)
        if not ID_RE.match(tid):
            violations.append("P2: チケットIDとして不正な文字列です: %r" % tid)
            continue
        matches = find_ticket_files(root, tid, "active")
        if not matches:
            violations.append("P2: %s: tickets/active/ に見つかりません" % tid)
            continue
        if len(matches) > 1:
            violations.append("P2: %s: tickets/active/ に複数マッチします: %s" % (
                tid, ", ".join(p.name for p in matches)))
            continue
        entry, _body, err = read_entry_at("active", matches[0])
        if err:
            violations.append("P3: %s: %s" % (tid, err))
            continue
        if entry["status"] in EXCLUDED_START_STATUSES:
            violations.append(
                "P3: %s: status '%s' からは開始できません"
                "（対象は todo〜test_passed）" % (tid, entry["status"]))
            continue
        snapshot[tid] = entry

    # --- P4/P5 用: active/ 全チケットの走査
    in_progress = []
    blocked_tickets = []
    if active_dir.is_dir():
        for path in sorted(active_dir.glob("*.md")):
            if not lib.is_ticket(str(path)):
                continue
            try:
                fm = lib.parse_frontmatter(path.read_text(encoding="utf-8"))
            except OSError:
                continue
            status = (fm or {}).get("status")
            if status in lib.IN_PROGRESS_STATUSES:
                in_progress.append(path.name)
            elif status == "blocked":
                blocked_tickets.append((path, fm))

    # --- P4: in_progress 上限（ヘッドレスで着手時の ask hook を踏ませない）
    if len(in_progress) >= lib.IN_PROGRESS_LIMIT:
        violations.append(
            "P4: in_progress チケットが %d 件あり上限 %d に達しています（%s）。"
            "完了または cancelled で整理してから再実行してください"
            % (len(in_progress), lib.IN_PROGRESS_LIMIT, ", ".join(in_progress)))

    # --- P5: 14日超 blocked の事前排除（トリアージ対話はヘッドレスで袋小路）
    for path, fm in blocked_tickets:
        updated = parse_updated(fm.get("updated"))
        if updated is None:
            violations.append(
                "P5: %s: blocked チケットの updated を解析できません"
                "（fail-closed）" % path.name)
            continue
        days = (today - updated).days
        if days > BLOCKED_TRIAGE_DAYS:
            violations.append(
                "P5: %s: blocked のまま %d 日経過しています（%d日超）。"
                "/triage でトリアージしてから再実行してください"
                % (path.name, days, BLOCKED_TRIAGE_DAYS))

    # --- P6: SPEC.md の存在（不在時は --allow-missing-spec で人間承認を明示）
    spec = root / "docs" / "SPEC.md"
    if not spec.is_file():
        if args.allow_missing_spec:
            info.append("P6: docs/SPEC.md 不在は --allow-missing-spec により"
                        "人間承認済みとして続行します（免除前提をプロンプトへ追記）")
        else:
            violations.append(
                "P6: docs/SPEC.md がありません。SPEC 免除が人間承認済みであれば "
                "--allow-missing-spec を付けて再実行してください")
    elif args.allow_missing_spec:
        warnings.append("P6: docs/SPEC.md が存在しますが --allow-missing-spec が"
                        "指定されています（免除前提がプロンプトへ追記されます）")

    # --- P7: claude CLI の実行可能性（バージョンを実行ログに常時表示）
    version = claude_version(args.claude_cmd, root)
    if version is None:
        violations.append("P7: claude CLI（%s）を実行できません"
                          "（--version が失敗）" % args.claude_cmd)
    else:
        info.append("P7: claude CLI: %s" % version)

    # --- P8: 境界判定の基準スナップショット（P2/P3 通過分）
    if snapshot:
        info.append("P8: 対象 %d 件の status / retry_counts を"
                    "スナップショットしました" % len(snapshot))

    # --- P9: done/ 件数の警告（開始は妨げない）
    done_dir = root / "tickets" / "done"
    done_count = 0
    if done_dir.is_dir():
        done_count = len([p for p in done_dir.glob("*.md") if lib.is_ticket(str(p))])
    if done_count > DONE_ARCHIVE_THRESHOLD:
        warnings.append(
            "P9: tickets/done/ が %d 件あります（%d件超）。/archive の実行を"
            "検討してください（開始は妨げません）"
            % (done_count, DONE_ARCHIVE_THRESHOLD))

    return violations, warnings, info, snapshot


def report_preflight(violations, warnings, info):
    say("=== プリフライト（P1〜P9） ===")
    for line in info:
        say("  %s" % line)
    for line in warnings:
        say("  警告 %s" % line)
    for line in violations:
        say("  NG %s" % line)
    if violations:
        say("プリフライト: NG %d件。開始しません"
            "（全違反を解消してから再実行してください）" % len(violations))
    else:
        say("プリフライト: OK（警告 %d件）" % len(warnings))


# ---------------------------------------------------------------------------
# 承認サマリ（y/N 応答が従来のバッチ事前承認の実体）
# ---------------------------------------------------------------------------

def format_guard(value, suffix=""):
    return ("%s%s" % (value, suffix)) if value else "なし"


def print_approval_summary(args, snapshot):
    say("")
    say("=== バッチ実行の承認サマリ ===")
    say("対象チケット（実行順）:")
    for i, tid in enumerate(args.ids, 1):
        entry = snapshot[tid]
        say("  %d. %s [%s] %s" % (i, tid, entry["status"], entry["title"]))
    say("権限モード: %s" % args.permission_mode)
    say("ガード: max-turns=%s / max-budget-usd=%s / timeout-min=%s" % (
        args.max_turns if args.max_turns else "無効",
        format_guard(args.max_budget_usd, " USD"),
        format_guard(args.timeout_min, " 分"),
    ))
    say("停止条件: 異常終了(exit≠0/timeout) / blocked（リトライ上限超過を包含） / "
        "未完了status / active/残存done / 範囲外変更 / 差し戻し増分（%s）"
        % ("--continue-on-rework 指定のため続行" if args.continue_on_rework
           else "停止・--continue-on-rework で緩和可"))
    say("最終チケット到達後は必ず停止します")
    say("注意: 実行中は同じリポジトリで対話セッションや別バッチを開かないでください"
        "（二重ライター防止）")


def confirm():
    """y/N 確認。y 以外・EOF は不成立（fail-closed）。"""
    try:
        answer = input("実行しますか? [y/N]: ")
    except EOFError:
        return False
    return answer.strip().lower() in ("y", "yes")


def suggest_command_line(args):
    """--dry-run 時に提示する実行コマンドライン（既定値と同じフラグは省略）。"""
    parts = ["python3", "scripts/batch_loop.py"]
    if args.permission_mode != DEFAULT_PERMISSION_MODE:
        parts += ["--permission-mode", args.permission_mode]
    if args.max_turns != DEFAULT_MAX_TURNS:
        parts += ["--max-turns", str(args.max_turns)]
    if args.max_budget_usd is not None:
        parts += ["--max-budget-usd", str(args.max_budget_usd)]
    if args.timeout_min is not None:
        parts += ["--timeout-min", str(args.timeout_min)]
    if args.continue_on_rework:
        parts.append("--continue-on-rework")
    if args.allow_missing_spec:
        parts.append("--allow-missing-spec")
    if args.claude_cmd != DEFAULT_CLAUDE_CMD:
        parts += ["--claude-cmd", args.claude_cmd]
    parts += args.ids
    return " ".join(parts)


# ---------------------------------------------------------------------------
# セッション起動（cwd=リポジトリルート・標準入出力は継承・--bare は付けない）
# ---------------------------------------------------------------------------

def build_prompt(tid, mode, allow_missing_spec):
    prompt = PROMPT_TEMPLATE.format(tid=tid, mode=mode)
    if allow_missing_spec:
        prompt += MISSING_SPEC_SUPPLEMENT
    return prompt


def build_claude_command(args, prompt):
    cmd = [args.claude_cmd, "-p", prompt, "--permission-mode", args.permission_mode]
    if args.max_turns:
        cmd += ["--max-turns", str(args.max_turns)]
    if args.max_budget_usd is not None:
        cmd += ["--max-budget-usd", str(args.max_budget_usd)]
    return cmd


def _terminate(proc):
    """子プロセスを terminate し、猶予後も残っていれば kill する。"""
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass


def run_session(cmd, root, timeout_min):
    """claude セッションを1つ実行し (exit_status, elapsed_sec) を返す。
    exit_status はプロセス終了コード、タイムアウト時は文字列 "timeout"。"""
    start = time.monotonic()
    proc = subprocess.Popen(cmd, cwd=str(root))
    try:
        if timeout_min:
            try:
                code = proc.wait(timeout=timeout_min * 60)
            except subprocess.TimeoutExpired:
                _terminate(proc)
                return "timeout", time.monotonic() - start
        else:
            code = proc.wait()
    except KeyboardInterrupt:
        _terminate(proc)
        raise
    return code, time.monotonic() - start


# ---------------------------------------------------------------------------
# 境界判定 1〜7（設計書§4。上から順に評価し、最初に該当した停止条件で中断）
# ---------------------------------------------------------------------------

def diff_increments(before, after):
    """retry_counts の増分を ["key: 0→1", ...] で返す。"""
    return [
        "%s: %d→%d" % (key, before.get(key, 0), after[key])
        for key in sorted(lib.RETRY_CAPS)
        if key in after and after[key] > before.get(key, 0)
    ]


def detect_out_of_scope(root, snapshot, current_tid):
    """他のバッチ対象チケットの (location, status) がスナップショットから
    変化していれば変化の一覧を返す（読めない場合も fail-closed で変化扱い）。"""
    changes = []
    for tid, snap in snapshot.items():
        if tid == current_tid:
            continue
        entry, _body, err = read_entry(root, tid)
        if err:
            changes.append("%s: %s（fail-closed で変化として扱います）" % (tid, err))
            continue
        if (entry["location"], entry["status"]) != (snap["location"], snap["status"]):
            changes.append("%s: %s/%s → %s/%s" % (
                tid, snap["location"], snap["status"],
                entry["location"], entry["status"]))
    return changes


def judge_boundary(tid, exit_status, entry, body, err, out_changes,
                   snap_entry, continue_on_rework):
    """境界判定 1〜7。優先順位は設計書§4 の列挙順。"""
    # 1) 異常終了（doneに到達していても停止・両事実を報告）
    if exit_status != 0:
        lines = []
        if exit_status == "timeout":
            lines.append("--timeout-min 超過により子プロセスを terminate しました")
        else:
            lines.append("claude が非ゼロ終了コード %s で終了しました" % exit_status)
        if entry and entry["location"] == "done" and entry["status"] == "done":
            lines.append("チケット自体は done に到達していますが、"
                         "安全側で停止して報告します")
        lines.append("状態を確認のうえ、必要なら /start-loop %s"
                     "（対話セッション）で再開してください" % tid)
        return Judgment(True, "異常終了", lines, [])

    # fail-closed: チケット状態が判定できなければ停止（判定2〜4の前提）
    if err:
        return Judgment(True, "状態判定不能", [
            "チケット %s の状態を判定できません: %s" % (tid, err),
            "tickets/ を手動で確認してください（fail-closed）",
        ], [])

    status = entry["status"]

    # 2) active/ に status: done のまま残存（Edit→mv 間の中断）
    if entry["location"] == "active" and status == "done":
        return Judgment(True, "完了手続き不完全", [
            "status は done ですが tickets/done/ へ移動されていません",
            "/start-loop %s（対話セッション）で完了手続きを再開してください" % tid,
        ], [])

    # 3) blocked（リトライ上限超過もここに包含される）
    if status == "blocked":
        blocker = extract_blocker(body)
        lines = ["チケットが blocked になりました。ブロッカー内容:"]
        lines += ["  %s" % line for line in blocker.splitlines()]
        lines.append("ブロッカーを解消してから /start-loop %s で再開してください" % tid)
        return Judgment(True, "blocked", lines, [])

    # 4) 未完了（中間 status のままセッション終了）
    if status != "done":
        return Judgment(True, "未完了", [
            "status: %s のままセッションが終了しました（done 未到達）" % status,
            "/start-loop %s（対話セッション）、または本スクリプトの再実行で"
            "再開できます" % tid,
        ], [])

    # 5) 他のバッチ対象チケットの変化（1セッション1チケットの前提が破れた疑い）
    if out_changes:
        lines = ["他のバッチ対象チケットの状態が変化しています"
                 "（1セッション1チケットの前提が破れた疑い）:"]
        lines += ["  %s" % change for change in out_changes]
        return Judgment(True, "範囲外変更の検知", lines, [])

    # 6) 差し戻し増分（既定: done 到達済みでも停止。--continue-on-rework で緩和）
    increments = diff_increments(snap_entry["retry"], entry["retry"])
    if increments:
        if continue_on_rework:
            return Judgment(False, "差し戻しあり・続行", [
                "retry_counts 増分: %s" % ", ".join(increments),
                "--continue-on-rework 指定のため次チケットへ進みます",
            ], increments)
        return Judgment(True, "差し戻し発生（done到達済み）", [
            "セッション内で差し戻しが発生していました: %s" % ", ".join(increments),
            "チケットは done に到達していますが、事前承認セマンティクス"
            "（差し戻し発生バッチを人間確認なしに進めない）に基づき停止します",
            "確認のうえ問題なければ、残りIDでの再実行または "
            "--continue-on-rework を検討してください",
        ], increments)

    # 7) 正常完了
    return Judgment(False, "done", [], [])


# ---------------------------------------------------------------------------
# バッチ実行
# ---------------------------------------------------------------------------

def print_stop(tid, judgment, remaining):
    say("")
    say("=== 停止: %s [%s] ===" % (tid, judgment.label))
    for line in judgment.lines:
        say("  %s" % line)
    if remaining:
        say("  未実行のチケット: %s" % " ".join(remaining))
        say("  現在のチケットの状態を確認・解消後、"
            "python3 scripts/batch_loop.py %s で再開できます" % " ".join(remaining))


def run_batch(args, root, snapshot):
    processed = []
    batch_start = time.monotonic()
    total = len(args.ids)

    for index, tid in enumerate(args.ids):
        remaining = args.ids[index + 1:]

        # 開始前の再確認（fail-closed）: セッション外での変更を検知したら停止し、
        # 直前の状態を境界判定6（retry増分）の基準としてスナップショットする
        entry, _body, err = read_entry(root, tid)
        if err:
            print_stop(tid, Judgment(True, "状態判定不能", [
                "開始前の再確認でチケット %s を読めません: %s" % (tid, err),
            ], []), remaining)
            return 3
        snap = snapshot[tid]
        if ((entry["location"], entry["status"]) != (snap["location"], snap["status"])
                or entry["retry"] != snap["retry"]):
            print_stop(tid, Judgment(True, "範囲外変更の検知", [
                "開始前の再確認で %s がスナップショットから変化しています: "
                "%s/%s → %s/%s" % (tid, snap["location"], snap["status"],
                                   entry["location"], entry["status"]),
                "バッチ実行中に別セッションがチケットへ書き込んだ疑いがあります"
                "（二重ライター防止のため停止）",
            ], []), remaining)
            return 3
        snapshot[tid] = entry
        before_status = entry["status"]

        say("")
        say("=== [%d/%d] %s のセッションを開始します ===" % (index + 1, total, tid))
        prompt = build_prompt(tid, args.permission_mode, args.allow_missing_spec)
        cmd = build_claude_command(args, prompt)
        exit_status, elapsed = run_session(cmd, root, args.timeout_min)

        # 境界判定（毎回チケットファイルを再読取。状態の外部化が正）
        current, body, cur_err = read_entry(root, tid)
        out_changes = detect_out_of_scope(root, snapshot, tid)
        judgment = judge_boundary(
            tid, exit_status, current, body, cur_err, out_changes,
            snapshot[tid], args.continue_on_rework)

        after_status = current["status"] if current else "?"
        say("結果: %s %.1f分 %s→%s retry増分%d exit=%s → %s" % (
            tid, elapsed / 60, before_status, after_status,
            len(judgment.increments), exit_status, judgment.label))

        if judgment.stop:
            print_stop(tid, judgment, remaining)
            return 3

        for line in judgment.lines:
            say("  %s" % line)

        snapshot[tid] = current  # 完了後の状態で更新（以降の境界判定5の基準）
        processed.append((tid, judgment.label, elapsed))

    say("")
    say("=== バッチ完了 ===")
    for tid, label, elapsed in processed:
        say("  %s: %s（%.1f分）" % (tid, label, elapsed / 60))
    say("全 %d 件が done に到達しました（合計 %.1f 分）" % (
        len(processed), (time.monotonic() - batch_start) / 60))
    return 0


# ---------------------------------------------------------------------------
# エントリポイント
# ---------------------------------------------------------------------------

def _run(args, root):
    violations, warnings, info, snapshot = run_preflight(root, args)
    report_preflight(violations, warnings, info)
    if violations:
        return 2

    if args.dry_run:
        say("")
        say("--dry-run: プリフライトのみ実行しました（セッションは起動していません）")
        say("実行コマンドライン: %s" % suggest_command_line(args))
        say("各チケットの起動コマンド: %s" %
            " ".join(build_claude_command(args, "<駆動プロンプト>")))
        return 0

    print_approval_summary(args, snapshot)
    if not args.yes and not confirm():
        say("承認が得られなかったため開始しません（何も実行していません）")
        return 2

    return run_batch(args, root, snapshot)


def main(argv=None, root=None):
    try:
        args = parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    try:
        return _run(args, root)
    except KeyboardInterrupt:
        say("")
        say("中断: SIGINT を受信しました。子プロセスを terminate しました。"
            "チケットは中間 status のまま外部化されているため "
            "/start-loop {ID} で再開できます")
        return 130
    except Exception:
        traceback.print_exc()
        say("エラー: 想定外の内部エラーのため停止します（fail-closed）")
        return 1


if __name__ == "__main__":
    sys.exit(main())
