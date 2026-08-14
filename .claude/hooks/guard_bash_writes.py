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

判定は3レイヤに分かれる。

  L1 字句（lex）— クォート状態だけを追跡して走査し、**クォート外の**演算子
    （`;` `&&` `||` `|` `>` `>>` `<<` 等）を最長一致で切り出す。演算子で区切った
    語チャンクは shlex.split(posix=True) でクォート解除する。したがって正規表現や
    パターンの中にある `|` `<<` `>` `#`（例: `grep -E '^(id|title):' tickets/...`）は
    ステートメント分割・特殊構文判定を引き起こさない。`$(...)` / バッククォート /
    プロセス置換は内側テキストを取り出してプレースホルダへ置き換える。

  L2 パス（guarded_paths）— 任意のテキストからパス様の候補を抽出し、
    os.path.normpath で正規化してから `.claude` 成分を除外して分類する。
    トークン境界に依存しないため `python3 -c "open('docs/SPEC.md','w')..."` のように
    1トークンへ埋め込まれたパスも検出する。正規化を除外判定より**先に**行うため、
    `./tickets/active/../../.claude/../tickets/active/X.md` のようなパストラバーサルで
    除外を悪用できない。

  L3 構文（find_violation）— 「証拠があるときだけ deny する」。出力リダイレクトは
    ステートメント単位で判定し、リダイレクト先が保護対象パスか、**同一コマンド内で
    保護対象を代入された変数**を参照する場合に deny する（無関係な後段リダイレクト
    `cat tickets/... && echo x > "$TMP"` を巻き添えにしない）。パイプで連結された
    区間はどこかで保護対象に言及していれば全区間の先頭コマンドがホワイトリストに
    載っている必要がある（`find tickets/... | xargs rm` のようなパイプ越しの
    書き込み連鎖を防ぐため）。

保護対象パスの判定（guarded_paths / is_guarded_token）は _ticket_lib.is_ticket とは
**意図的に基準が異なる**。is_ticket は「Write/Edit の対象ファイルが状態検証対象の
実チケットか」を判定する厳密判定（絶対パス・前後スラッシュ・.md 拡張子を要求）である
のに対し、本 hook が必要とするのは「コマンド文字列の断片が保護対象に言及しているか」
という再現率優先の判定（相対パス・ディレクトリ指定・引用符やコードの中に埋もれた
パスまで拾う）である。統一すると `ls tickets/active/` や `docs/SPEC.md` を取りこぼす
ため、統一しない。

既知の限界:
  - 別のコマンドで export された変数経由のリダイレクトは検出できない（hook は
    1回の Bash 呼び出ししか見えない）。tickets/ 宛ては check_loop_integrity.py の
    ドリフト検知がバックストップになるが、docs/SPEC.md 宛てにはバックストップが無い。
  - `$'...'`（ANSI-C 引用）は shlex が bash と同一には解釈しないが、語として
    1トークンに収まるため判定は保守側（deny 方向）へ倒れる。

fail-open: 内部エラーでは allow。検知した違反のみ deny。ただし未閉じクォート等で
字句解析できない入力は allow せず、素朴なトークン分割による簡易判定
（degraded_violation）へ落とす（`rm tickets/... #'` を素通りさせないため）。
"""
import json
import os
import re
import shlex
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

# 保護対象(SPEC.md等)を引数に取っても許可する読み取り専用スクリプト。
# いずれも読み取りのみで書き込み経路を持たないことを確認済み
# (スクリプト側のdocstringにも「書き込み処理を追加してはならない」と明記)
READONLY_SCRIPTS = (
    ".claude/skills/spec-interview/scripts/check_spec_structure.py",
)

# シェル演算子（長いものから最長一致させる）
OPERATORS = ("<<<", ">>", "<<", "&&", "||", ";;", "|&", "&>", ">&", "<&",
             "<>", ">|", ";", "&", "|", "<", ">")
OPERATOR_CHARS = ";&|<>"
SUBST_PLACEHOLDER = "__KLK_SUBST__"

PATHISH_RE = re.compile(r"[A-Za-z0-9_.\-/]+")
ASSIGN_RE = re.compile(r"[A-Za-z_][A-Za-z_0-9]*=")
VAR_REF_RE = re.compile(r"\$\{?([A-Za-z_][A-Za-z_0-9]*)\}?")
# 字句解析に失敗した入力向けの簡易判定でのみ使う（degraded_violation）
LEGACY_REDIRECT_RE = re.compile(r"\d?>>?\s*([^\s;|&]+)")


def allow():
    sys.exit(0)


def deny(reason):
    lib.emit_pretooluse_decision("deny", reason)


# --- L2: パスレイヤ ---------------------------------------------------------

def _is_guarded_path(path):
    """正規化済みパスが保護対象か。正規化 → .claude 除外 → 分類の順で判定する。"""
    if ".claude" in path.split("/"):
        return False  # スキル同梱のテンプレート等は対象外
    if "tickets/active" in path or "tickets/done" in path:
        # テンプレート・ダッシュボードは対象外（validator と同じ除外）
        return "/Templates/" not in path and not path.endswith("_index.md")
    return os.path.basename(path) == "SPEC.md"


def guarded_paths(text):
    """任意テキストから保護対象パスを列挙する（トークン境界に依存しない）。"""
    found = []
    for candidate in PATHISH_RE.findall(text):
        path = os.path.normpath(candidate)
        if _is_guarded_path(path):
            found.append(path)
    return found


def is_guarded_token(text):
    """テキスト（トークン・コマンド断片のいずれでも可）が保護対象に言及するか。"""
    return bool(guarded_paths(text))


def mentions_guarded(values):
    """語の集合のいずれかが保護対象に言及するか。"""
    return any(is_guarded_token(v) for v in values)


# --- L1: 字句レイヤ ---------------------------------------------------------

def _take_subst(command, start, buf, substs):
    """`$(` / `<(` / `>(` の内側を置換として取り込み、終端 `)` の次の位置を返す。"""
    depth, i, n, quote = 1, start, len(command), ""
    while i < n:
        c = command[i]
        if quote:
            if c == "\\" and quote == '"' and i + 1 < n:
                i += 2
                continue
            if c == quote:
                quote = ""
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            i += 2
            continue
        if c in "'\"":
            quote = c
            i += 1
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                substs.append(command[start:i])
                buf.append(SUBST_PLACEHOLDER)
                return i + 1
        i += 1
    raise ValueError("no closing parenthesis")


def _take_backtick(command, start, buf, substs):
    """バッククォート置換の内側を取り込み、終端の次の位置を返す。"""
    i, n = start, len(command)
    while i < n:
        c = command[i]
        if c == "\\" and i + 1 < n:
            i += 2
            continue
        if c == "`":
            substs.append(command[start:i])
            buf.append(SUBST_PLACEHOLDER)
            return i + 1
        i += 1
    raise ValueError("no closing backquote")


def lex(command):
    """コマンドを (tokens, substitutions) へ分解する。

    tokens: [("w", クォート解除済みの語), ("op", 演算子文字列), ...]
    substitutions: `$(...)` / バッククォート / プロセス置換の内側テキスト
    未閉じクォート・未閉じ括弧では ValueError を送出する。
    """
    command = command.replace("\\\n", " ").replace("\n", ";")
    tokens, substs, buf = [], [], []

    def flush():
        chunk = "".join(buf)
        del buf[:]
        if chunk.strip():
            for word in shlex.split(chunk, comments=False, posix=True):
                tokens.append(("w", word))

    i, n, quote = 0, len(command), ""
    while i < n:
        c = command[i]
        if quote == "'":
            buf.append(c)
            if c == "'":
                quote = ""
            i += 1
            continue
        if quote == '"':
            if c == "\\" and i + 1 < n:
                buf.append(c)
                buf.append(command[i + 1])
                i += 2
                continue
            if c == "$" and i + 1 < n and command[i + 1] == "(":
                i = _take_subst(command, i + 2, buf, substs)
                continue
            if c == "`":
                i = _take_backtick(command, i + 1, buf, substs)
                continue
            buf.append(c)
            if c == '"':
                quote = ""
            i += 1
            continue
        # 通常状態
        if c == "\\" and i + 1 < n:
            buf.append(c)
            buf.append(command[i + 1])
            i += 2
            continue
        if c in "'\"":
            buf.append(c)
            quote = c
            i += 1
            continue
        if c == "$" and i + 1 < n and command[i + 1] == "(":
            i = _take_subst(command, i + 2, buf, substs)
            continue
        if c in "<>" and i + 1 < n and command[i + 1] == "(":
            i = _take_subst(command, i + 2, buf, substs)  # プロセス置換
            continue
        if c == "`":
            i = _take_backtick(command, i + 1, buf, substs)
            continue
        if c in OPERATOR_CHARS:
            flush()
            op = next(o for o in OPERATORS if command.startswith(o, i))
            tokens.append(("op", op))
            i += len(op)
            continue
        buf.append(c)
        i += 1
    if quote:
        raise ValueError("no closing quotation")
    flush()
    return tokens, substs


def op_kind(op):
    """演算子の種別を返す。"""
    if "<<" in op:
        return "heredoc"
    if ">" in op:
        return "redirect_out"
    if "<" in op:
        return "redirect_in"
    if op in ("|", "|&"):
        return "pipe"
    return "sep"


# --- L3: 構文レイヤ ---------------------------------------------------------

def split_statements(tokens):
    """トークン列を `;` `&&` `||` `&` でステートメントへ分割する。"""
    statements, current = [], []
    for token in tokens:
        if token[0] == "op" and op_kind(token[1]) == "sep":
            statements.append(current)
            current = []
            continue
        current.append(token)
    statements.append(current)
    return statements


def pipe_segments(statement):
    """ステートメントをパイプ区間の語リストへ分割する（リダイレクト先の語は除く）。"""
    segments, current, skip_next = [], [], False
    for kind, value in statement:
        if kind == "op":
            kind_of_op = op_kind(value)
            if kind_of_op == "pipe":
                segments.append(current)
                current = []
                skip_next = False
            else:
                skip_next = kind_of_op in ("redirect_out", "redirect_in",
                                           "heredoc")
            continue
        if skip_next:
            skip_next = False  # リダイレクト先・heredoc の終端子はコマンドではない
            continue
        current.append(value)
    segments.append(current)
    return segments


def head_of(words):
    """語リストの先頭コマンド名を返す（環境変数代入・パス前置きは剥がす）。"""
    for word in words:
        if re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*=.*", word):
            continue  # FOO=bar 形式の前置き
        return os.path.basename(word.lstrip("("))
    return ""


def is_readonly_script_call(words):
    """`python3 <READONLY_SCRIPTS> <args>` の形か。
    スクリプトパスの前にフラグがある形(-c/-m 等の別実行経路)は不許可。"""
    seen_interp = False
    for word in words:
        if re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*=.*", word):
            continue  # FOO=bar 形式の前置き
        if not seen_interp:
            seen_interp = True  # インタプリタ本体
            continue
        if word.startswith("-"):
            return False
        return os.path.normpath(word).endswith(READONLY_SCRIPTS)
    return False


def segment_violation(words):
    """パイプ区間（語リスト）単位の違反理由を返す。問題なければ None。"""
    head = head_of(words)
    if not head:
        return None
    if head in ("python3", "python") and is_readonly_script_call(words):
        return None
    if head not in ALLOWED_HEADS:
        return "'%s' は許可されていません" % head
    if head == "sed" and any(t == "-i" or t.startswith("-i.") or
                             t == "--in-place" for t in words):
        return "sed -i（in-place編集）は許可されていません"
    if head == "find" and any(t in FIND_WRITE_FLAGS for t in words):
        return "find の書き込み系フラグ（-exec/-delete等）は許可されていません"
    if head == "git":
        sub = next((t for t in words[1:] if not t.startswith("-")), "")
        if sub not in ALLOWED_GIT_SUBCOMMANDS:
            return "git %s は許可されていません" % sub
    return None


def record_assignments(statement, guarded_vars):
    """`NAME=保護対象パス` の前置き代入を記録する（リダイレクト先の追跡用）。"""
    for words in pipe_segments(statement):
        for word in words:
            match = ASSIGN_RE.match(word)
            if not match:
                break  # 先頭から連続する代入のみが前置き
            if is_guarded_token(word[match.end():]):
                guarded_vars.add(word[:match.end() - 1])


def redirect_violation(statement, guarded_vars):
    """出力リダイレクト先が保護対象・保護対象を代入された変数なら理由を返す。"""
    for index, (kind, value) in enumerate(statement):
        if kind != "op" or op_kind(value) != "redirect_out":
            continue
        if index + 1 >= len(statement):
            continue
        next_kind, target = statement[index + 1]
        if next_kind != "w":
            continue
        if "&" in value and (target.isdigit() or target == "-"):
            continue  # 2>&1 等の fd 複製
        if is_guarded_token(target):
            return "リダイレクト（> %s）による書き込み" % target
        if any(name in guarded_vars for name in VAR_REF_RE.findall(target)):
            return "リダイレクト（> %s）による書き込み" % target
    return None


def statement_violation(statement, guarded_vars):
    """ステートメント単位の違反理由を返す。問題なければ None。"""
    reason = redirect_violation(statement, guarded_vars)
    if reason:
        return reason
    if not mentions_guarded([v for k, v in statement if k == "w"]):
        return None
    if any(k == "op" and op_kind(v) == "heredoc" for k, v in statement):
        return "ヒアドキュメントによる書き込みの可能性"
    for words in pipe_segments(statement):
        reason = segment_violation(words)
        if reason:
            return reason
    return None


def degraded_violation(command):
    """字句解析できない入力向けの簡易判定（素朴なトークン分割・リテラル先のみ）。"""
    words = command.split()
    if not mentions_guarded(words):
        return None
    for match in LEGACY_REDIRECT_RE.finditer(command):
        target = match.group(1)
        if target.startswith("&"):
            continue  # 2>&1 等の fd 複製
        if is_guarded_token(target):
            return "リダイレクト（> %s）による書き込み" % target
    return segment_violation(words)


def find_violation(command):
    """コマンド全体の違反理由を返す。問題なければ None。"""
    try:
        tokens, _ = lex(command)
    except ValueError:
        return degraded_violation(command)
    guarded_vars = set()
    for statement in split_statements(tokens):
        record_assignments(statement, guarded_vars)
        reason = statement_violation(statement, guarded_vars)
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
