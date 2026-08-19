"""SPEC.md からID指定でREQ/SCR/IF該当セクションのみを抽出するCLI。

見出しパーサはcheck_spec_structure.pyを流用する(sys.path.insert方式。
scripts/list_tickets.pyが_ticket_lib.pyを取り込む手法と同型)。
テンプレートの構造(セクション番号・小見出し名)を変更した場合は、
check_spec_structure.py・tests/test_check_spec_structure.pyに加えて
本スクリプトのPREFIX_LOCATIONSとtests/test_extract_spec_section.pyも
追随させること。

本スクリプトは読み取り専用であり、書き込み経路を持たない。
.claude/hooks/guard_bash_writes.py はこの前提で「SPEC.mdを引数に取る本
スクリプトの実行」を許可している(READONLY_SCRIPTS)。書き込み処理を
追加してはならない。

使い方: python3 extract_spec_section.py <SPEC.mdのパス> <ID> [<ID> ...]
終了コード: 0=正常終了(個々のIDが「該当なし」でも0) / 2=引数不足・
           ファイルなし・デコード失敗
"""
import os
import re
import sys

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPTS_DIR)
import check_spec_structure as checker  # noqa: E402

# 各プレフィックスの (定義セクション番号, 対象小見出し名, 判定方式)。
# REQは小見出しが「Must(必須)」のようにサフィックスを伴うためstartswith、
# SCR/IFは完全一致するためexactで判定する。
PREFIX_LOCATIONS = {
    "REQ": (5, ("Must", "Should", "Could"), "startswith"),
    "SCR": (6, ("画面一覧",), "exact"),
    "IF": (6, ("提供インターフェース一覧",), "exact"),
}
# 本スクリプトの対象外だがSPEC_TEMPLATE.mdで定義されている他のID系統
# (該当なし理由の文言を分けるためだけに使う。抽出ロジックはPREFIX_LOCATIONS外)
KNOWN_OTHER_PREFIXES = ("EH", "NFR", "OQ")


def classify(id_):
    """id_ を判定し (prefix_or_None, status) を返す。
    status: "supported" / "unsupported_prefix" / "invalid_format" """
    m = re.match(r"^([A-Za-z]+)-(\d+)$", id_)
    if not m:
        return None, "invalid_format"
    prefix = m.group(1).upper()
    if prefix in PREFIX_LOCATIONS:
        if re.fullmatch(rf"{prefix}-\d{{3}}", id_):
            return prefix, "supported"
        return prefix, "invalid_format"   # 桁数不一致（例: REQ-1, REQ-0001）
    if prefix in KNOWN_OTHER_PREFIXES:
        return prefix, "unsupported_prefix"
    return prefix, "invalid_format"


def find_id(text, prefix, id_):
    """text（HTMLコメント除去済み）からid_を探す。
    戻り値: [(見出しパス, 本文), ...]（空リスト=該当なし。2件以上は
    非準拠SPECでの重複検出であり、呼び出し側でWARN表示する。エラーにしない）"""
    sec_num, wanted_subs, mode = PREFIX_LOCATIONS[prefix]
    sections = checker.split_sections(text)
    if sec_num not in sections:
        return []
    heading, body = sections[sec_num]
    subsections = checker.split_subsections(body)
    matches = []
    for sub_name, sub_body in subsections.items():
        hit = (any(sub_name.startswith(w) for w in wanted_subs) if mode == "startswith"
               else sub_name in wanted_subs)
        if hit and id_ in checker.table_key_ids(sub_body, prefix):
            matches.append((f"{sec_num}. {heading} > {sub_name}", sub_body.strip()))
    if not matches and id_ in checker.table_key_ids(body, prefix):
        # 小見出しの無い旧形式、または対象小見出し外にIDがある非準拠SPECへの
        # フォールバック（check_spec_structure.pyのscreens_body/if_sourceと同じ方針）
        matches.append((f"{sec_num}. {heading}", body.strip()))
    return matches


def main(argv):
    if len(argv) < 3:
        print("使い方: python3 extract_spec_section.py <SPEC.mdのパス> <ID> [<ID> ...]",
              file=sys.stderr)
        return 2
    path, ids = argv[1], argv[2:]
    try:
        text = open(path, encoding="utf-8").read()
    except UnicodeDecodeError as e:
        print(f"読み込み失敗: {e}\nUTF-8で保存されているか確認してください", file=sys.stderr)
        return 2
    except OSError as e:
        print(f"読み込み失敗: {e}", file=sys.stderr)
        return 2

    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)  # check()と同じ前処理

    for id_ in ids:
        print(f"=== {id_} ===")
        prefix, status = classify(id_)
        if status == "invalid_format":
            print("該当なし（ID形式として認識できません。<PREFIX>-NNN 形式で"
                  "指定してください。対応プレフィックス: REQ/SCR/IF）")
        elif status == "unsupported_prefix":
            print(f"該当なし（{prefix}は本スクリプトの対応プレフィックス外です。"
                  "対応: REQ/SCR/IF。EH/NFR/OQ等はdocs/SPEC.mdを直接参照してください）")
        else:
            matches = find_id(text, prefix, id_)
            if not matches:
                print(f"該当なし（SPEC内に{id_}の定義が見つかりません）")
            else:
                if len(matches) > 1:
                    print(f"[WARN] {len(matches)}箇所で検出されました"
                          "（SPECがテンプレート非準拠の可能性。"
                          "check_spec_structure.pyで構造を確認してください）")
                for i, (heading_path, body) in enumerate(matches, 1):
                    if len(matches) > 1:
                        print(f"--- {i}件目 ---")
                    print(f"見出しパス: {heading_path}")
                    print(body)
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
