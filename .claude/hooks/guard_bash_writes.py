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
    プロセス置換は内側テキストを substs へ退避し、元の位置には**位置インデックス
    付きのプレースホルダ**（`__KLK_SUBST_0__`）を置く。インデックスがあることで
    「どの語がどの置換に由来するか」を後段が復元できる。

  プレースホルダ契約 — L3 は置換を2方向に評価する。内側方向（置換の中身が
    書き込み。`ls $(rm tickets/...)`）は substs を同じ判定へ再帰させる。外側方向
    （置換の結果が外側の書き込みへ供給される。`rm $(echo docs/SPEC.md)`）は
    expand_substs で語を解決してから判定する。解決するのは「言及ゲート」
    「リダイレクト先」「変数代入値」「sed / awk の追加規則」の4用途。
    先頭コマンド名（head_of）と find / git の完全一致規則は解決しない
    （前者は置換をコマンド名に使う形をそのまま不許可にするため、後者は
    完全一致の意味論を保つため）。解決は証拠テキストを増やす操作であり、
    判定を緩める方向には働かない。

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
    書き込み連鎖を防ぐため）。ホワイトリスト収載コマンドのうち引数だけで書ける
    ものには追加規則を持つ（sed の -i 全表記と w コマンド、awk のプログラム内
    リダイレクト・変数束縛、find の書き込み系フラグ、git のサブコマンド）。
    加えて `cd` は作業ディレクトリを追跡し、保護対象配下へ移動した後は
    ステートメントの言及ゲートを無条件に真とし、相対パスへの出力リダイレクトを
    cwd と結合して判定する（`cd` セグメント自体は常に許可）。

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
  - cd の作業ディレクトリ追跡はリテラルのオペランドに限る。`cd "$DIR"` /
    `cd $(...)` / `cd` / `cd -` は追跡を打ち切り、以降は cwd による強化を行わない。
  - degraded mode（下記）は旧版と同じ素朴な分割を使うため、クォート内の `|` と
    未閉じクォートが同時に成立する入力（`grep -E '^(id|title):' tickets/... # don't`）
    は誤denyになる。これは旧版と同一の挙動であり、正常に字句解析できる入力
    （コメントを伴わない同じコマンド）では発生しない。
  - ホワイトリスト収載コマンドのうち次の書き込み／実行経路は**未対応**である。
    いずれも本 hook の導入当初から存在する穴で、別チケットで扱う:
    `sort -o FILE` / `sort --output=FILE`、`uniq INPUT OUTPUT` の第2位置引数、
    `sed -f SCRIPT`（外部スクリプト）、GNU sed の `e` フラグ（**任意コマンド実行**）。
  - ALLOWED_HEADS へコマンドを追加するときは、設計書 docs/designs/KLK-010.md §3-9
    の書き込みベクタ棚卸し表へ行を追加し、「引数だけで書き込み／任意コマンド実行が
    できる経路」を列挙してから追加すること（awk の変数束縛の見落としの再発防止）。

fail-open: 内部エラーでは allow。検知した違反のみ deny。ただし字句解析できない
入力（未閉じシングル／ダブルクォート・未閉じバッククォート・未閉じ `$(` ・末尾の
孤立エスケープの5系統。`don't` のような英文コメントでも成立する）は allow せず、
degraded_violation へ落とす。degraded は旧版の判定要素（全体の言及ゲート・
リテラルリダイレクト・heredoc の部分文字列判定・ステートメント分割・パイプ分割・
パイプライン単位の言及ゲート・セグメント判定）をすべて持つ。旧版から意図的に
外しているのは「リダイレクト先が `$` / バッククォートを含むだけで deny する」
規則のみ（無関係な後段リダイレクトの誤denyを解消するため）。
"""
import json
import os
import re
import shlex
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _ticket_lib as lib  # noqa: E402

# 保護対象に言及するコマンドで許可する先頭コマンド（読み取り・移動系）。
# いずれも「引数だけでファイルを書き込む経路を持たない」ことが条件。
# xargs（任意コマンド実行）・tee/cp/rm/touch（書き込み系）・
# python3/perl/ruby/node（任意実行。READONLY_SCRIPTS の例外のみ）は載せない。
ALLOWED_HEADS = {
    "ls", "cat", "head", "tail", "wc", "grep", "diff", "sort", "uniq",
    "stat", "file", "basename", "dirname", "test", "[",
    "cd",    # ディレクトリ移動のみ。セグメント自体は無条件許可。
             # ただし移動先は next_cwd で追跡し、後続の相対パス判定に使う
    "pwd", "echo", "cut", "tr", "nl", "rev", "realpath", "readlink",
    "mv",    # active/ ↔ done/ の移動・アーカイブは設計上 Bash mv が正規手段
    "sed",   # -i（in-place）・w コマンドが無ければ読み取り
    "awk",   # プログラム内リダイレクト（print > file）が無ければ読み取り
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

# シェル演算子。種別とセットを1つの表から導出する（種別の宣言漏れを構造的に防ぐ）。
# 新しい演算子を足すときはここへ (演算子, 種別) を1行加えるだけでよい。
OPERATOR_KINDS = (
    # 3文字
    ("<<<", "heredoc"),
    # 2文字
    ("<<", "heredoc"), (">>", "redirect_out"), ("&>", "redirect_out"),
    (">&", "redirect_out"), (">|", "redirect_out"), ("<>", "redirect_out"),
    ("<&", "redirect_in"), ("|&", "pipe"),
    ("&&", "sep"), ("||", "sep"), (";;", "sep"),
    # 1文字
    (">", "redirect_out"), ("<", "redirect_in"), ("|", "pipe"),
    (";", "sep"), ("&", "sep"),
)
# 走査は先頭一致の最初の候補を採るため、必ず長い演算子から並べる。
# 表の並び順に依存しないよう、ここで長さの降順へ明示的に整列する
# （安定ソートなので同じ長さの相対順序は表のまま）。
OPERATORS = tuple(op for op, _ in
                  sorted(OPERATOR_KINDS, key=lambda kv: -len(kv[0])))
OPERATOR_KIND_MAP = dict(OPERATOR_KINDS)
OPERATOR_CHARS = ";&|<>"

# コマンド置換の退避先インデックスを埋め込むプレースホルダ。
# 「どのプレースホルダがどの置換か」を後段（言及ゲート・リダイレクト先判定）が
# 復元できるようにするため、不透明な固定文字列ではなく位置付きにしている。
SUBST_PLACEHOLDER = "__KLK_SUBST_%d__"
SUBST_PLACEHOLDER_RE = re.compile(r"__KLK_SUBST_(\d+)__")
MAX_SUBST_DEPTH = 3

PATHISH_RE = re.compile(r"[A-Za-z0-9_.\-/]+")
ASSIGN_RE = re.compile(r"[A-Za-z_][A-Za-z_0-9]*=")
VAR_REF_RE = re.compile(r"\$\{?([A-Za-z_][A-Za-z_0-9]*)\}?")
SED_INPLACE_SHORT_RE = re.compile(r"-[A-Za-z]*i")     # -i / -i.bak / -ni / -si.bak
SED_WRITE_RE = re.compile(r"(?:^|[;{}\s/])[wW]\s+\S")  # s/a/b/w FILE ・ /re/w FILE

# awk 専用（プログラム内リダイレクトと変数束縛の検出）
AWK_ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z_0-9]*=(.*)$", re.S)
AWK_STRING_RE = re.compile(r'"(?:\\.|[^"\\])*"')       # 文字列リテラル（除去用）
AWK_OUTPUT_RE = re.compile(r"\b(?:print|printf)\b[^;}\n]*(?:>>?|\|)")

# 字句解析に失敗した入力向けの簡易判定でのみ使う（degraded_violation）。
# 旧版（KLK-010 以前）の find_violation と同じ分割を再現するためのもので、
# 正常経路では使わない。
LEGACY_REDIRECT_RE = re.compile(r"\d?>>?\s*([^\s;|&]+)")
LEGACY_STATEMENT_RE = re.compile(r"&&|\|\||;|\n")


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
                buf.append(SUBST_PLACEHOLDER % (len(substs) - 1))
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
            buf.append(SUBST_PLACEHOLDER % (len(substs) - 1))
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


def expand_substs(text, substs):
    """語トークン中のプレースホルダを、対応する置換の内側テキストへ展開する。

    証拠収集専用。展開は「判定に使えるテキストを増やす」方向にしか働かず、
    判定を緩めることはない。展開する用途・しない用途はモジュール docstring の
    「プレースホルダ契約」に従うこと。
    """
    if not substs or not SUBST_PLACEHOLDER_RE.search(text):
        return text

    def replace(match):
        index = int(match.group(1))
        if index >= len(substs):
            return match.group(0)  # 利用者が書いた同名リテラル。そのまま残す
        return " %s " % substs[index]  # 前後の空白で語の誤結合を防ぐ

    return SUBST_PLACEHOLDER_RE.sub(replace, text)


def expand_all(words, substs):
    """語リストの各要素をプレースホルダ解決したリストを返す。"""
    return [expand_substs(word, substs) for word in words]


def display_text(text):
    """deny 理由に載せる文字列から内部プレースホルダを隠す。"""
    return SUBST_PLACEHOLDER_RE.sub("$(...)", text)


def op_kind(op):
    """演算子の種別を返す。種別の正は OPERATOR_KINDS。"""
    return OPERATOR_KIND_MAP.get(op, "sep")


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
    """語リストの先頭コマンド名を返す（環境変数代入・グループ化の `(` は剥がす）。"""
    for word in words:
        if re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*=.*", word):
            continue  # FOO=bar 形式の前置き
        name = word.lstrip("(")
        if not name:
            continue  # `(` 単独＝サブシェル開始。本体は次の語
        return os.path.basename(name)
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


def awk_bindings(words):
    """awk の変数束縛の VALUE を列挙する（-v NAME=VALUE / -vNAME=VALUE /
    --assign NAME=VALUE / 位置引数 NAME=VALUE）。近似解析であり、オプションの
    引数消費までは厳密に追わない（追えない形は列挙しない＝安全側へ倒す）。"""
    values, expect_value = [], False
    for word in words[1:]:
        if expect_value:
            expect_value = False
            match = AWK_ASSIGN_RE.match(word)
            if match:
                values.append(match.group(1))
            continue
        if word in ("-v", "--assign"):
            expect_value = True
            continue
        if word.startswith("-v") and len(word) > 2:
            match = AWK_ASSIGN_RE.match(word[2:])
            if match:
                values.append(match.group(1))
            continue
        if word.startswith("--assign="):
            match = AWK_ASSIGN_RE.match(word[len("--assign="):])
            if match:
                values.append(match.group(1))
            continue
        if word.startswith("-"):
            continue  # -F / -f 等のその他オプション
        match = AWK_ASSIGN_RE.match(word)  # 位置引数の NAME=VALUE
        if match:
            values.append(match.group(1))
    return values


def awk_violation(words):
    """awk セグメントの違反理由を返す（プログラム内リダイレクトと変数束縛）。"""
    # 保護対象に言及する語そのものが > / | を含む（{print > "docs/SPEC.md"} 等）。
    # 正常な読み取りでは保護対象は素のパス引数として現れる（> も | も含まない）
    if any(">" in t or "|" in t for t in words if is_guarded_token(t)):
        return "awk のプログラム内リダイレクト（print > file 等）は許可されていません"
    # 保護対象パスを awk 変数へ束縛している（-v f=... / 位置引数 f=...）。
    # 参照側（print > f）まで追わないのは、エイリアス（g=f; print > g）で
    # 容易に迂回でき防御にならないため。束縛そのものを証拠とする
    if any(is_guarded_token(v) for v in awk_bindings(words)):
        return "awk の変数へ保護対象パスを束縛しています（-v / NAME=VALUE）"
    # 保護対象に言及するセグメントで print/printf の出力リダイレクトを使う。
    # 文字列リテラルを除去してから見るため printf "%s|%s" は一致しない
    if mentions_guarded(words):
        for word in words[1:]:
            if AWK_OUTPUT_RE.search(AWK_STRING_RE.sub('""', word)):
                return ("awk のプログラム内リダイレクト（print > file 等）は"
                        "許可されていません")
    return None


def segment_violation(words, substs=()):
    """パイプ区間（語リスト）単位の違反理由を返す。問題なければ None。

    words は未解決の語リスト。substs を与えると、sed / awk の追加規則を
    プレースホルダ解決後のテキストに対しても評価する（解決前の語も併せて
    見るため、判定は deny 方向にのみ広がる）。
    """
    head = head_of(words)
    if not head:
        return None
    if SUBST_PLACEHOLDER_RE.search(head):
        # コマンド名の位置にコマンド置換を使う形は解決せず不許可とする
        return "コマンド名の位置にコマンド置換が使われています"
    if head in ("python3", "python") and is_readonly_script_call(words):
        return None
    if head not in ALLOWED_HEADS:
        return "'%s' は許可されていません" % head
    words = list(words)
    expanded = expand_all(words, substs)
    variants = [words] if expanded == words else [words, expanded]
    if head == "sed":
        flat = [t for variant in variants for t in variant]
        if any(SED_INPLACE_SHORT_RE.match(t) or t == "--in-place" or
               t.startswith("--in-place=") for t in flat):
            return "sed -i（in-place編集）は許可されていません"
        # スクリプト引数に埋め込まれた書き出し（s/a/b/w FILE ・ /re/w FILE）
        if any(SED_WRITE_RE.search(t) for t in flat if is_guarded_token(t)):
            return "sed の w コマンド（ファイル書き出し）は許可されていません"
    if head == "awk":
        for variant in variants:
            reason = awk_violation(variant)
            if reason:
                return reason
    if head == "find" and any(t in FIND_WRITE_FLAGS for t in words):
        return "find の書き込み系フラグ（-exec/-delete等）は許可されていません"
    if head == "git":
        sub = next((t for t in words[1:] if not t.startswith("-")), "")
        if sub not in ALLOWED_GIT_SUBCOMMANDS:
            return "git %s は許可されていません" % sub
    return None


def next_cwd(words, cwd):
    """`cd DIR` 実行後の作業ディレクトリを返す。追跡不能なら None。"""
    if cwd is None:
        return None
    if head_of(words) != "cd":
        return cwd
    operand = next((w for w in words[1:] if not w.startswith("-")), "")
    if (not operand or "$" in operand or operand.startswith("~") or
            SUBST_PLACEHOLDER_RE.search(operand)):
        return None  # cd / cd - / cd "$D" / cd $(...) は追跡不能
    return os.path.normpath(os.path.join(cwd or ".", operand))


def cwd_is_guarded(cwd):
    """作業ディレクトリ自体が保護対象配下か（相対パス書き込みの検出用）。"""
    return bool(cwd) and _is_guarded_path(cwd)


def cwd_redirect_violation(target, cwd):
    """保護対象配下を作業ディレクトリとする相対パスへの出力リダイレクトか。

    `cd tickets/active && echo x > APP-001.md` のように、cd で作業ディレクトリを
    移すとリダイレクト先が保護対象パターンに一致しなくなる経路を塞ぐ。
    解決できない先（変数・コマンド置換）は allow 方向へ倒す。
    """
    if not cwd_is_guarded(cwd):
        return None
    if "$" in target or SUBST_PLACEHOLDER_RE.search(target):
        return None
    if not _is_guarded_path(os.path.normpath(os.path.join(cwd, target))):
        return None  # 絶対パス・cwd の外へ抜ける相対パスは対象外
    return "リダイレクト（> %s）による書き込み" % display_text(target)


def record_assignments(statement, guarded_vars, substs=()):
    """`NAME=保護対象パス` の前置き代入を記録する（リダイレクト先の追跡用）。"""
    for words in pipe_segments(statement):
        for word in words:
            match = ASSIGN_RE.match(word)
            if not match:
                break  # 先頭から連続する代入のみが前置き
            value = expand_substs(word[match.end():], substs)
            if is_guarded_token(value):
                guarded_vars.add(word[:match.end() - 1])


def redirect_violation(statement, guarded_vars, substs=(), cwd=""):
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
        # リダイレクト先はコマンドではないためパイプ区間の検査から外れる。
        # 置換の結果が書き込み先になる形（> $(echo docs/SPEC.md)）はここで解決する
        resolved = expand_substs(target, substs)
        if is_guarded_token(resolved):
            return "リダイレクト（> %s）による書き込み" % display_text(target)
        if any(name in guarded_vars for name in VAR_REF_RE.findall(resolved)):
            return "リダイレクト（> %s）による書き込み" % display_text(target)
        reason = cwd_redirect_violation(target, cwd)
        if reason:
            return reason
    return None


def statement_violation(statement, guarded_vars, substs=(), cwd=""):
    """ステートメント単位の違反理由を返す。問題なければ None。

    cwd は「このステートメントを実行する時点の作業ディレクトリ」（追跡不能なら
    None）。保護対象配下なら相対パスが保護対象を指しうるため判定を強める。
    """
    reason = redirect_violation(statement, guarded_vars, substs, cwd)
    if reason:
        return reason
    words = [v for k, v in statement if k == "w"]
    # 言及ゲートはプレースホルダ解決後のテキストで判定する（置換の結果が
    # 外側コマンドの引数になる形を取りこぼさないため）。作業ディレクトリが
    # 保護対象配下ならゲートは無条件に真とする
    if not (cwd_is_guarded(cwd) or
            mentions_guarded(expand_all(words, substs))):
        return None
    if any(k == "op" and op_kind(v) == "heredoc" for k, v in statement):
        return "ヒアドキュメントによる書き込みの可能性"
    for segment_words in pipe_segments(statement):
        reason = segment_violation(segment_words, substs)
        if reason:
            return reason
    return None


def degraded_violation(command):
    """字句解析できない入力向けのフォールバック。

    旧版（KLK-010 以前）の find_violation と同じ判定要素をすべて持つ:
    全体の言及ゲート → リテラルリダイレクト → heredoc の部分文字列判定 →
    ステートメント分割 → パイプ分割 → パイプライン単位の言及ゲート →
    セグメント判定。唯一の意図的な差分は「リダイレクト先が `$` /
    バッククォートを含むだけで deny する」規則を復活させないこと
    （無関係な後段リダイレクトの巻き添えを解消するため）。
    """
    if not mentions_guarded(command.split()):
        return None
    for match in LEGACY_REDIRECT_RE.finditer(command):
        target = match.group(1)
        if target.startswith("&"):
            continue  # 2>&1 等の fd 複製
        if is_guarded_token(target):
            return "リダイレクト（> %s）による書き込み" % target
    if "<<" in command:
        return "ヒアドキュメントによる書き込みの可能性"
    cwd = ""
    for statement in LEGACY_STATEMENT_RE.split(command):
        parts = [p for p in statement.split("|") if p.strip()]
        if not parts:
            continue
        words_list = [p.split() for p in parts]
        if cwd_is_guarded(cwd) or any(mentions_guarded(w) for w in words_list):
            for words in words_list:
                reason = segment_violation(words)
                if reason:
                    return reason
        for match in LEGACY_REDIRECT_RE.finditer(statement):
            reason = cwd_redirect_violation(match.group(1), cwd)
            if reason:
                return reason
        cwd = next_cwd(words_list[0], cwd)
    return None


def find_violation(command, depth=0):
    """コマンド全体の違反理由を返す。問題なければ None。"""
    try:
        tokens, substs = lex(command)
    except ValueError:
        return degraded_violation(command)
    for inner in substs:
        if depth >= MAX_SUBST_DEPTH:
            # 深追いはせず保守側で打ち切る（$($($(rm ...))) を抜け道にしないため）
            if is_guarded_token(inner):
                return "深いコマンド置換の内側で保護対象パスに言及しています"
            continue
        reason = find_violation(inner, depth + 1)
        if reason:
            return reason
    guarded_vars, cwd = set(), ""
    for statement in split_statements(tokens):
        record_assignments(statement, guarded_vars, substs)
        reason = statement_violation(statement, guarded_vars, substs, cwd)
        if reason:
            return reason
        segments = pipe_segments(statement)
        cwd = next_cwd(segments[0] if segments else [], cwd)
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
