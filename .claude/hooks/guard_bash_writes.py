#!/usr/bin/env python3
"""PreToolUse hook - チケット・SPEC.md への Bash 書き込みゲート

Bash ツールの実行前に発火し、コマンドが保護対象
（tickets/active|done/ 配下・basename が SPEC.md のファイル）に言及している場合、
読み取り・移動系のホワイトリストに載らないコマンドを deny で弾く。

チケット状態機械の強制境界は Write/Edit の PreToolUse hook にあるため、
Bash 経由の書き込み（リダイレクト・sed -i・tee・`python3 -c` 等の
インタプリタワンライナー・find -exec・ヒアドキュメント）は検証を迂回できてしまう。
この hook はその迂回路をベストエフォートで塞ぐ。パスをリテラルに含まない
迂回（変数展開・スクリプト内での組み立て）はすり抜けるが、それは
check_loop_integrity.py のドリフト検知（Stop）が捕捉する。

判定の粒度: コマンドを `&&` / `||` / `;` / 改行でステートメントに分割し、
保護対象に言及するステートメントのみ検査する。パイプ（`|`）で連結された
部分は一体として扱い、どこかで保護対象に言及していれば全パートの先頭コマンドが
ホワイトリストに載っている必要がある（`find tickets/... | xargs rm` のような
パイプ越しの書き込み連鎖を防ぐため）。リダイレクト先が保護対象・変数の場合は
コマンド全体で deny する。誤検知した場合はコマンドを分割すればよい。

fail-open: 内部エラーでは allow。検知した違反のみ deny。
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _ticket_lib as lib  # noqa: E402

# 保護対象に言及するコマンドで許可する先頭コマンド（読み取り・移動系）
ALLOWED_HEADS = {
    "ls", "cat", "head", "tail", "wc", "grep", "diff", "sort", "uniq",
    "stat", "file", "basename", "dirname", "test", "[",
    "mv",    # active/ ↔ done/ の移動・アーカイブは設計上 Bash mv が正規手段
    "sed",   # -i（in-place）が無ければ読み取り
    "find",  # -exec / -delete 等が無ければ読み取り
    "git",   # サブコマンドを別途判定
}

# git は状態を書き換えないサブコマンド＋mv/ステージ/コミットのみ許可
# （checkout / restore / rm はチケットファイルを検証なしで書き換え・削除できるため除外）
ALLOWED_GIT_SUBCOMMANDS = {
    "mv", "add", "commit", "diff", "log", "show", "status", "blame",
}

FIND_WRITE_FLAGS = {"-exec", "-execdir", "-ok", "-okdir", "-delete",
                    "-fprint", "-fprintf", "-fls"}

STATEMENT_RE = re.compile(r"&&|\|\||;|\n")
REDIRECT_RE = re.compile(r"\d?>>?\s*([^\s;|&]+)")


def allow():
    sys.exit(0)


def deny(reason):
    lib.emit_pretooluse_decision("deny", reason)


def is_guarded_token(token):
    """トークンが保護対象パスへの言及か。"""
    t = token.strip("'\"`()").rstrip(".,;:")
    if ".claude/" in t:
        return False  # スキル同梱のテンプレート等は対象外
    if "tickets/active" in t or "tickets/done" in t:
        # テンプレート・ダッシュボードは対象外（validator と同じ除外）
        return "/Templates/" not in t and not t.endswith("_index.md")
    return t.split("/")[-1] == "SPEC.md"


def mentions_guarded(command):
    return any(is_guarded_token(t) for t in command.split())


def head_of(segment):
    """セグメントの先頭コマンド名を返す（環境変数代入・パス前置きは剥がす）。"""
    for token in segment.split():
        if re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*=.*", token):
            continue  # FOO=bar 形式の前置き
        return token.strip("'\"`(").split("/")[-1]
    return ""


def segment_violation(segment):
    """セグメント単位の違反理由を返す。問題なければ None。"""
    head = head_of(segment)
    if not head:
        return None
    if head not in ALLOWED_HEADS:
        return "'%s' は許可されていません" % head
    tokens = segment.split()
    if head == "sed" and any(t == "-i" or t.startswith("-i.") or
                             t == "--in-place" for t in tokens):
        return "sed -i（in-place編集）は許可されていません"
    if head == "find" and any(t in FIND_WRITE_FLAGS for t in tokens):
        return "find の書き込み系フラグ（-exec/-delete等）は許可されていません"
    if head == "git":
        sub = next((t for t in tokens[1:] if not t.startswith("-")), "")
        if sub not in ALLOWED_GIT_SUBCOMMANDS:
            return "git %s は許可されていません" % sub
    return None


def find_violation(command):
    """コマンド全体の違反理由を返す。問題なければ None。"""
    # リダイレクト先が保護対象・不定（変数等）なら書き込みとみなす
    for match in REDIRECT_RE.finditer(command):
        target = match.group(1)
        if target.startswith("&"):
            continue  # 2>&1 等の fd 複製
        if is_guarded_token(target) or "$" in target or "`" in target:
            return "リダイレクト（> %s）による書き込み" % target
    if "<<" in command:
        return "ヒアドキュメントによる書き込みの可能性"
    for statement in STATEMENT_RE.split(command):
        parts = [p.strip() for p in statement.split("|") if p.strip()]
        # パイプラインのどこかで保護対象に言及していれば全パートを検査する
        if not any(mentions_guarded(p) for p in parts):
            continue
        for part in parts:
            reason = segment_violation(part)
            if reason:
                return reason
    return None


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        allow()

    if data.get("tool_name") != "Bash":
        allow()
    command = (data.get("tool_input") or {}).get("command", "")
    if not command:
        allow()

    try:
        if not mentions_guarded(command):
            allow()
        reason = find_violation(command)
    except Exception:
        allow()

    if reason:
        deny(
            "チケット（tickets/active|done/）・SPEC.md に触れる Bash コマンドで"
            "書き込みの可能性を検出しました: %s。チケット・SPEC.md の変更は"
            "必ず Write/Edit ツールで行ってください（状態検証 hook を通すため）。"
            "読み取りは cat/grep/ls 等を単独で、active/↔done/ の移動は mv を"
            "使ってください。" % reason
        )
    allow()


if __name__ == "__main__":
    main()
