#!/usr/bin/env python3
"""SPEC.md のテンプレート準拠を機械判定する構造チェッカー。

構造の正は同スキルの templates/SPEC_TEMPLATE.md。テンプレートの構造
(セクション構成・ID規則・必須列)を変更した場合は本スクリプトと
tests/test_check_spec_structure.py も追随させること。

判定は3層に分かれ、機械判定できるのは前2層のみ:
- FAIL: 決定的に判定できる違反(見出し欠落・ID未付番・定義表の欠落・検証方法の
  空欄・スコープ外0項目・定義表内のID重複・§5↔§6の参照切れ・Must要件の明示的な
  OQ依存)。1件でもあればテンプレート非準拠と判定し、/spec-interview 改訂モード
  での構造化を要する
- WARN: 疑いの提示(見出しの不一致・小見出しの欠落・命名揺れ・出自注記の不在)。
  準拠判定は妨げないが人間の確認を要する
- 対象外: 意味論(失敗時挙動の実質性・検証方法の実行可能性・シークレット不在の
  証明・暗黙のOQ依存)。これらの検査は /interrogate-spec と人間レビューの責務

利用箇所:
- /setup 手順5(現在地診断): Bashで実行し、FAILありなら /spec-interview 改訂モード
  へ誘導する
- /interrogate-spec Phase 0(構造受付): 実行可能ならスクリプトで、不可なら
  同基準をReadで確認する
- /spec-interview 改訂モード・Step 3: 構造化後のセルフチェック

本スクリプトは読み取り専用であり、書き込み経路を持たない。
.claude/hooks/guard_bash_writes.py はこの前提で「SPEC.mdを引数に取る本スクリプトの
実行」を許可している。書き込み処理を追加してはならない。

使い方: python3 check_spec_structure.py <SPEC.mdのパス>
終了コード: 0=準拠(WARNは許容) / 1=非準拠(FAILあり) / 2=ファイルなし・引数誤り
"""
import re
import sys

EXPECTED_SECTIONS = {
    0: "文書情報・変更履歴", 1: "プロジェクト概要", 2: "背景・目的", 3: "用語集",
    4: "ユーザー・ステークホルダー", 5: "機能要件", 6: "画面・インターフェース一覧",
    7: "エラーハンドリング・異常系方針", 8: "非機能要件", 9: "技術的制約",
    10: "データ・外部インターフェース要件", 11: "スコープ外(明示的な除外事項)",
    12: "未決事項(Open Questions)", 13: "成功基準", 14: "参考資料",
}

# 各IDの定義セクション(重複検査はこの中でのみ行う。他セクションでの表形式の
# 参照——§13が推奨するID参照など——を重複と誤検知しないため)
ID_DEF_SECTIONS = (
    ("REQ", 5), ("SCR", 6), ("IF", 6), ("EH", 7), ("NFR", 8), ("OQ", 12),
)

# 検証方法セルとして「空」とみなすプレースホルダ
EMPTY_CELL = ("", "-", "－")


def split_sections(text):
    """`## N. 見出し` 単位で本文を分割し {番号: (見出し, 本文)} を返す"""
    heads = list(re.finditer(r"^## (\d+)\. (.+?)\s*$", text, re.M))
    result = {}
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        result[int(m.group(1))] = (m.group(2), text[m.end():end])
    return result


def split_subsections(body):
    """セクション本文を `### 見出し` 単位で分割する。小見出し前の前文は '' キー"""
    heads = list(re.finditer(r"^### (.+?)\s*$", body, re.M))
    result = {"": body[: heads[0].start()] if heads else body}
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(body)
        result[m.group(1)] = body[m.end():end]
    return result


def table_rows(body):
    """Markdownテーブルの行をセルのリストとして返す(区切り行を除く)"""
    rows = []
    for line in body.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if all(re.fullmatch(r":?-+:?", c) for c in cells if c):
            continue
        rows.append(cells)
    return rows


def column_index(rows, name, default):
    """ヘッダー行から列名のインデックスを解決する(列の追加・並び替えに耐えるため。
    見つからなければテンプレートの既定位置にフォールバック)"""
    for row in rows:
        if name in row:
            return row.index(name)
    return default


def ids_in(text, prefix):
    return set(re.findall(rf"{prefix}-\d{{3}}", text))


def table_key_ids(body, prefix):
    """表の主キー位置(1列目)にあるIDの出現リストを返す"""
    return re.findall(rf"^\|\s*({prefix}-\d{{3}})\s*\|", body, re.M)


def check(text):
    ok, ng, warn = [], [], []

    # HTMLコメント(テンプレートの記入ガイド)は判定対象から除く。コメント内の
    # 例示(★・SCR-001等)が出自注記やID検出を誤って満たすのを防ぐ
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)

    sections = split_sections(text)

    # 構造: セクション0〜14の存在と見出し一致
    for num, expected in EXPECTED_SECTIONS.items():
        if num not in sections:
            ng.append(f"§{num}「{expected}」が存在しない")
        elif sections[num][0] != expected:
            warn.append(
                f"§{num} 見出しがテンプレートと不一致:"
                f"「{sections[num][0]}」(期待:「{expected}」)")
        else:
            ok.append(f"§{num} 見出し一致")

    def body(n):
        return sections.get(n, ("", ""))[1]

    # 構造: §0 版数行が1行以上
    if re.search(r"^\|\s*v\d+\.\d+\s*\|", body(0), re.M):
        ok.append("§0 版数行あり")
    else:
        ng.append("§0 変更履歴に版数行(vX.Y)がない")

    # 構造: §5 REQ-IDとMust/Should/Could小見出し
    reqs = ids_in(body(5), "REQ")
    if reqs:
        ok.append(f"§5 REQ-ID {len(reqs)}件")
    else:
        ng.append("§5 にREQ-IDが1件もない")
    for sub in ("Must", "Should", "Could"):
        if not re.search(rf"^### {sub}", body(5), re.M):
            warn.append(f"§5 小見出し「### {sub}...」が見つからない")

    # 構造: §6 は小見出し単位で判定する(「該当なし」は画面一覧と提供IF一覧の
    # どちらにも合法に現れるため、セクション全体での文字列検索は誤判定する)
    subs = split_subsections(body(6))
    screens_body = subs.get("画面一覧")
    if_body = subs.get("提供インターフェース一覧")
    flow_body = subs.get("画面遷移図")

    if screens_body is None:
        # 小見出しが無い旧形式・独自形式はセクション全体で判定する
        screens_body = body(6)
        if 6 in sections:
            warn.append("§6 小見出し「### 画面一覧」がない(旧形式の可能性)")
    scrs = ids_in(screens_body, "SCR")
    no_ui = "該当なし" in screens_body
    if scrs:
        ok.append(f"§6 画面一覧: SCR-ID {len(scrs)}件")
    elif no_ui:
        ok.append("§6 画面一覧: 該当なし明記(UIなしプロジェクト)")
    else:
        ng.append("§6 画面一覧にSCR-IDも「該当なし」の明記もない"
                  "(wireframe-gen受付で差し戻される)")

    if if_body is None and 6 in sections:
        warn.append("§6 小見出し「### 提供インターフェース一覧」がない"
                    "(旧形式の可能性)")
    if_source = if_body if if_body is not None else body(6)
    if_table_ids = set(table_key_ids(if_source, "IF"))
    if no_ui and not scrs:
        # UIなしプロジェクトは提供IF一覧(表形式)が必須。散文中のID言及では
        # 名称・種別・入出力等が定義されないため、表の主キー位置で数える
        if if_table_ids:
            ok.append(f"§6 提供インターフェース: IF-ID {len(if_table_ids)}件")
        else:
            ng.append("§6 UIなし宣言なのに提供インターフェース一覧"
                      "(IF-xxxを主キーとする表)がない")

    if scrs and not re.search(r"```mermaid", body(6)) and (
            flow_body is None or "該当なし" not in flow_body):
        warn.append("§6 画面遷移図(mermaid)がない")

    # 構造: §7/§8 は定義表(主キー位置のID)と検証方法列の非空を要求する。
    # 本文散在のIDだけでは検証方法が定義されないため表を必須とする
    for num, prefix in ((7, "EH"), (8, "NFR")):
        rows = table_rows(body(num))
        key_ids = {r[0] for r in rows
                   if r and re.match(rf"{prefix}-\d{{3}}", r[0])}
        if key_ids:
            ok.append(f"§{num} {prefix}-ID {len(key_ids)}件")
            v_idx = column_index(rows, "検証方法", 3)
            for row in rows:
                if row and re.match(rf"{prefix}-\d{{3}}", row[0]):
                    cell = row[v_idx] if len(row) > v_idx else ""
                    if cell in EMPTY_CELL:
                        ng.append(f"§{num} {row[0]} の検証方法が空")
        elif ids_in(body(num), prefix):
            ng.append(f"§{num} の{prefix}-IDが表の主キー位置にない"
                      "(検証方法列を持つ表形式の一覧が必要)")
        else:
            ng.append(f"§{num} に{prefix}-IDが1件もない")

    # 構造: §9 出自注記(標準構成の版数 or ユーザー指定★)
    if re.search(r"標準構成\s*v\d|★", body(9)):
        ok.append("§9 出自注記あり")
    else:
        warn.append("§9 に出自注記(「標準構成 vX.X」の注記または★)が見つからない"
                    "(完成チェックリストでは必須。/spec-interview で充足する)")

    # 構造: §11 スコープ外が1項目以上(箇条書き・番号付きリストの双方を数える)
    scope_items = [l for l in body(11).splitlines()
                   if re.match(r"^\s*(?:[-*+]|\d+[.)]) \S", l)]
    if scope_items:
        ok.append(f"§11 スコープ外 {len(scope_items)}項目")
    else:
        ng.append("§11 スコープ外が0項目(完成チェックリスト違反: 最低1項目必須)")

    # 構造: 定義セクション内のID重複(他セクションの参照表は対象外)
    for prefix, sec in ID_DEF_SECTIONS:
        all_ids = table_key_ids(body(sec), prefix)
        dups = {i for i in all_ids if all_ids.count(i) > 1}
        if dups:
            ng.append(f"§{sec} 定義表内のID重複: {sorted(dups)}")

    # 参照整合: §5関連画面 ⊆ §6 SCR / §6対応要件 ⊆ §5 REQ
    rows5 = table_rows(body(5))
    rel_idx = column_index(rows5, "関連画面", 2)
    ref_scrs = ids_in("\n".join(
        r[rel_idx] for r in rows5
        if len(r) > rel_idx and re.match(r"REQ-\d{3}", r[0])), "SCR")
    dangling = ref_scrs - scrs
    if dangling:
        ng.append(f"§5が参照する画面が§6に存在しない: {sorted(dangling)}")
    elif reqs:
        ok.append("§5→§6 画面参照の整合OK")
    dangling = ids_in(body(6), "REQ") - reqs
    if dangling:
        ng.append(f"§6が参照する要件が§5に存在しない: {sorted(dangling)}")
    elif scrs or if_table_ids:
        ok.append("§6→§5 要件参照の整合OK")

    # 横断: §6アクセス可能なユーザー ⊆ §4ユーザー種別(命名揺れに脆いためWARN)
    user_types = {r[0] for r in table_rows(body(4))
                  if r and r[0] and r[0] != "ユーザー種別"}
    rows_scr = table_rows(screens_body)
    au_idx = column_index(rows_scr, "アクセス可能なユーザー", 5)
    for row in rows_scr:
        if row and re.match(r"SCR-\d{3}", row[0]) and len(row) > au_idx:
            for u in re.split(r"[・,、/]", row[au_idx]):
                if u.strip() and u.strip() not in user_types:
                    warn.append(f"§6 {row[0]} のアクセス可能なユーザー"
                                f"「{u.strip()}」が§4のユーザー種別に見つからない")

    # 構造: Must小見出し配下の備考に明示的なOQ参照がない(明示分のみ検出可能)。
    # Must小見出しが特定できない場合は誤検知を避けて未検査とする
    # (小見出しの欠落自体は上のWARNが指摘する)
    must_bodies = [b for h, b in split_subsections(body(5)).items()
                   if h.startswith("Must")]
    if must_bodies:
        oq_in_must = ids_in("\n".join(must_bodies), "OQ")
        if oq_in_must:
            ng.append("Must要件がOQに依存(Should以下へ降格が必要): "
                      f"{sorted(oq_in_must)}")
        elif reqs:
            ok.append("Must要件に明示的なOQ依存なし")

    return ok, ng, warn


def main(argv):
    if len(argv) != 2:
        print("使い方: python3 check_spec_structure.py <SPEC.mdのパス>",
              file=sys.stderr)
        return 2
    try:
        text = open(argv[1], encoding="utf-8").read()
    except UnicodeDecodeError as e:
        print(f"読み込み失敗: {e}\nUTF-8で保存されているか確認してください",
              file=sys.stderr)
        return 2
    except OSError as e:
        print(f"読み込み失敗: {e}", file=sys.stderr)
        return 2

    ok, ng, warn = check(text)

    print(f"=== SPEC構造チェック: {argv[1]} ===")
    print(f"\n[PASS] {len(ok)}件")
    for m in ok:
        print(f"  ✓ {m}")
    if ng:
        print(f"\n[FAIL] {len(ng)}件 → テンプレート非準拠。"
              "/spec-interview 改訂モードで構造化してください")
        for m in ng:
            print(f"  ✗ {m}")
    if warn:
        print(f"\n[WARN] {len(warn)}件(準拠判定は妨げないが人間の確認を推奨)")
        for m in warn:
            print(f"  ⚠ {m}")
    if not ng:
        print("\n判定: テンプレート準拠(構造層)")
    print("""
[本チェックの対象外(LLM/人間の判断が必要な意味論項目)]
  - Must要件の「失敗時の挙動」が実質的に記述されているか
  - 検証方法が実際に検証可能な手順か
  - シークレット実値の不記載(パターン検出は可能だが不在証明は不可)
  - 明示されていないOQ依存・記述の曖昧さ・節の責務過多
  → これらは /interrogate-spec と人間レビューで検査する""")
    return 1 if ng else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
