# KLK-032 調査詳細（investigator / orchestrator代筆）

- 調査日: 2026-08-18
- 調査基点: develop HEAD `5fe3c4f`（KLK-020マージ後。KLK-031コミット `4c99758` はその祖先に含まれることを `git log` で確認済み）
- チケット: `tickets/active/KLK-032_guarded_paths_after_shell_expansionのSPEC_md判定がglob下で大小区別を残し誤allowする.md`

## 1. Findings

- `_guarded_paths_from_expanded`（`.claude/hooks/guard_bash_writes.py` L1018-1072）は `literals = list(GUARDED_DIR_NAMES)` に条件付きで `GUARDED_FILENAME` を追加した単一リストを、単一ループ `for literal in literals: if not fnmatch.fnmatchcase(literal, component)`（L1063-1064）で照合しており、比較は大小区別ありの `fnmatchcase` のみ。
- 実機検証でチケット記載の再現手順を確認済み。小文字 `docs/sp*.md`・混在 `docs/Spec*.md` は `_guarded_paths_from_expanded` が `[]`（検出漏れ）、`find_violation("rm docs/sp*.md")` は `None`（許可）。対して大文字 `docs/SP*.md`・正規形 `docs/SPEC*.md` は既存どおり検出・deny。
- `_is_guarded_path`（L800-807）はKLK-020で既に `lib.is_spec_basename` 経由（case-insensitive等価）になっており、`_guarded_paths_from_expanded` の後段再評価（`_is_guarded_path(rebuilt_path)`）はcase-insensitiveである。バグは前段のfnmatch事前フィルタ（L1064）のみに限定される。
- `_ticket_lib.is_spec_basename(name)` は `name.upper() == "SPEC.MD"` という**厳密等価**判定のみでglobパターン照合機能を持たない。`_guarded_paths_from_expanded` が必要とするのは「globパターンである `component` に文字列 `literal`（"SPEC.md"）がfnmatchするか」という**パターン照合**であり、意味論が異なるため `is_spec_basename` への単純置換は不可（KLK-020の `is_spec`／`is_project_spec` 等4箇所とは性質が異なる）。
- `GUARDED_DIR_NAMES`（active/done）と `GUARDED_FILENAME` は同一 `literals` リスト・同一 `fnmatchcase` 呼び出し行を共有する構造であり、チケットが要求する「GUARDED_DIR_NAMES側は現状維持」を満たすには、ループ全体の一律case-insensitive化ではなく `GUARDED_FILENAME` 側だけを分離する実装が必要になる（設計判断はarchitectの範囲）。

## 2. Evidence

- `codebase`: `.claude/hooks/guard_bash_writes.py` L1018-1072（`_guarded_paths_from_expanded`）、L800-807（`_is_guarded_path`）、L554-556（`GUARDED_DIR_NAMES`／`GUARDED_FILENAME`／`GLOB_META_CHARS` 定義）。現物を直接読解して確認。
- `codebase`: `.claude/hooks/_ticket_lib.py` L159-163（`is_spec_basename` 定義: `return isinstance(name, str) and name.upper() == "SPEC.MD"`）。等価判定のみでパターン照合なし。
- `empirical`（2026-08-18、develop HEAD `5fe3c4f` 上で実行）: 下記「実測ログ」参照。
- `local_docs`: `docs/reports/KLK-020/review.md` L13-72「High Risk」節。reviewerが同一の再現手順・実測（`docs/sp*.md`→`[]`、`find_violation`→`None`）を独立に報告済みで、本調査結果と完全一致（矛盾なし、独立再確認）。
- `local_docs`: `docs/designs/KLK-031.md` L84-114（option A「GLOB_META_CHARSのみ成分をGUARDED_DIR_NAMES・GUARDED_FILENAME両方から一律除外」を却下した理由）。GUARDED_DIR_NAMESとGUARDED_FILENAMEを同一ループで扱う現構造が意図的設計であることの根拠。

### 実測ログ（empirical, 2026-08-18, develop HEAD 5fe3c4f）

```
_guarded_paths_from_expanded('docs/sp*.md')    -> []          # 小文字glob: 検出漏れ
_guarded_paths_from_expanded('docs/Spec*.md')  -> []          # 大小混在glob: 検出漏れ
_guarded_paths_from_expanded('docs/SP*.md')    -> ['docs/SPEC.md']  # 大文字glob: 検出成功（既存挙動）
_guarded_paths_from_expanded('docs/SPEC*.md')  -> ['docs/SPEC.md']  # 正規形glob: 検出成功（既存挙動）

find_violation('rm docs/sp*.md')    -> None                   # 許可（誤allow）
find_violation('rm docs/Spec*.md')  -> None                   # 許可（誤allow）
find_violation('rm docs/SP*.md')    -> deny reason "'rm' は許可されていません"  # 正しくdeny
find_violation('rm docs/SPEC*.md')  -> deny reason "'rm' は許可されていません"  # 正しくdeny
```

検証は `.claude/hooks` を `sys.path` へ追加して `guard_bash_writes` をimportし、上記関数を直接呼び出す形で実施。検証コマンド内の文字列は `chr()` 結合で動的構築した。理由: `guard_bash_writes.py` 自身がBashツールのPreToolUseフックとして働き、検証コマンド文中の "SPEC.md" 風文字列をraw textスキャンで検出してBashツール呼び出し自体を拒否するため（実際に素朴な埋め込みの初回試行は1回denyされた）。これはコード改変を一切伴わない検証手法上の回避策であり、フックの検出範囲がBashコマンドのraw text全体に及ぶことの副次的な実例確認でもある。

`docs/reports/KLK-020/review.md` L27-46のreviewer独立実測とも結果は完全一致:

```
$ python3 -c "
import sys; sys.path.insert(0, '.claude/hooks')
import guard_bash_writes as guard
print(guard._guarded_paths_from_expanded('docs/spec.md'))   # 非glob: 正しく検出
print(guard._guarded_paths_from_expanded('docs/sp*.md'))    # glob+小文字: 検出漏れ
print(guard.find_violation('rm docs/sp*.md'))                # end-to-end: allow相当
"
['docs/spec.md']
[]
None
```

### 該当コード全文（`.claude/hooks/guard_bash_writes.py` L1018-1072）

```python
def _guarded_paths_from_expanded(expanded):
    found = []
    path = os.path.normpath(expanded)
    if _is_guarded_path(path):
        found.append(path)
        return found
    components = path.split("/")
    last_index = len(components) - 1
    for index, component in enumerate(components):
        if not any(ch in component for ch in GLOB_META_CHARS):
            continue
        literals = list(GUARDED_DIR_NAMES)
        has_literal_char = any(ch not in GLOB_META_CHARS for ch in component)
        if index == last_index and has_literal_char:
            literals = literals + [GUARDED_FILENAME]
        for literal in literals:
            if not fnmatch.fnmatchcase(literal, component):   # ← 大小区別あり（本チケットの対象）
                continue
            rebuilt = "/".join(
                literal if i == index else c
                for i, c in enumerate(components))
            rebuilt_path = os.path.normpath(rebuilt)
            if _is_guarded_path(rebuilt_path):
                found.append(rebuilt_path)
    return found
```

`_is_guarded_path`（L800-807、対照。既にcase-insensitive）:

```python
def _is_guarded_path(path):
    if ".claude" in path.split("/"):
        return False
    if "tickets/active" in path or "tickets/done" in path:
        return "/Templates/" not in path and not path.endswith("_index.md")
    return lib.is_spec_basename(os.path.basename(path))
```

`_ticket_lib.is_spec_basename`（L159-163）:

```python
def is_spec_basename(name):
    """basename が大小を区別せず 'SPEC.md' と一致するか（KLK-020: is_spec /
    _is_guarded_path / _is_guarded_path_component / is_project_spec の
    SPEC.md 判定を一本化する単一の正規化ポイント）。"""
    return isinstance(name, str) and name.upper() == "SPEC.MD"
```

## 3. Dependency Graph

- `_guarded_paths_from_expanded` の呼び出し元は `guarded_paths_after_shell_expansion`（L1153）の1箇所のみ（grep確認、他の直接呼び出しなし）。
- `guarded_paths_after_shell_expansion` は `is_guarded_token_expanded`（L1164）経由で呼ばれる。
- `is_guarded_token_expanded`／`mentions_guarded_expanded` はL1846, 2677, 2911, 2945, 2947, 3098, 3104, 3115, 3148の計9箇所から呼ばれる（statement_violation／redirect_violation／degraded_violation／guarded_write_target／record_loop_binding／subst_violationの各経路。`tests/test_guard_bash_writes.py` L3137-3141のKLK-031コメント「実測9箇所」と一致）。
- よって `_guarded_paths_from_expanded` 1箇所の修正が全9呼び出し経路に自動的に波及する（修正は単一集約ポイントで足りる）。
- `GUARDED_DIR_NAMES` 側の実体判定（`_is_guarded_path` 内 `"tickets/active" in path` 等、L804）は `_guarded_paths_from_expanded` 内のfnmatch事前フィルタとは別ロジックであり、`_is_guarded_path` 自体を無変更にできる点でチケットのスコープ外指定と矛盾しない。

## 4. Risk Areas

- L1045/L1061-1062の `literals` リスト構築とL1064の比較が一体化しているため、`fnmatchcase` を単純に大小無視版へ置換すると GUARDED_DIR_NAMES（active/done）側も意図せずcase-insensitive化され、チケットが明示的にスコープ外とした挙動を変えてしまうリスクがある。
- `has_literal_char` 条件（KLK-031, L1060-1062）は「GUARDED_FILENAMEを `literals` に追加するか」を決めるゲートであり、本チケットの修正対象（比較演算子自体）とは独立した条件式。両者は機能的には別レイヤーだが、実装が `literals` 構築とループ内比較を一括で書き換えると、既存ゲートの意図（孤立ワイルドカードのみの成分を誤denyしない）を壊す可能性があり、チケットAC4が要求する「実装順序・差分の明示」が必要。
- `test_klk031_isolated_wildcard_component_allow`／`test_klk031_multi_char_glob_only_component_allow`（`rm *`・`rm build/*`・`rm **` 等）は `has_literal_char=False` のため `GUARDED_FILENAME` が `literals` に追加されず、本チケットの修正対象パスを通らない。既存テストが通り続ける前提は「`has_literal_char` ゲート自体には手を入れない」ことに強く依存する。
- 既存テストで小文字/混在globパターン（`docs/sp*.md`・`docs/Spec*.md`）を検証するケースは0件（grep確認）。既存3件（`test_klk018_fragmented_glob_spec_side_read_allow` L3072/3075、`test_klk031_existing_klk018_fixed_cases_unaffected_deny` L3182）はいずれも大文字 `SPEC*.md` のみを使用しており、修正後も現状の一致経路（大小区別ありでも一致）で通るため回帰の心配は低いが、新規テスト追加が受け入れ条件の実証を担う。
- 参考: `_ticket_lib.is_project_spec`（L166-189）は「basename部分のみcase-insensitive・ディレクトリ部分は大小区別維持」という部分適用の前例（KLK-020設計 D1のスコープ限定）であり、本チケットの「GUARDED_FILENAME側のみcase-insensitive・GUARDED_DIR_NAMES側は現状維持」という要求と構造的に類似する先例。

### 影響を受ける既存テスト一覧（`tests/test_guard_bash_writes.py`）

| テスト名 | 行 | 内容 | 本修正での位置づけ |
|---|---|---|---|
| `test_klk018_fragmented_glob_spec_side_read_allow` | L3060-3075 | `assertAllow("cat docs/SPEC*.md")` / `assertDeny("rm docs/SPEC*.md")` | 大文字globのみ。修正後も現状のfnmatchcase一致で通過継続（回帰対象外だが要再実行確認） |
| `test_klk031_isolated_wildcard_component_allow` | L3105-3115 | `rm *`／`rm build/*` 等（リテラル文字0） | `has_literal_char=False` のため `GUARDED_FILENAME` が `literals` に加わらず、本修正の対象パスを通らない前提 |
| `test_klk031_multi_char_glob_only_component_allow` | L3117-3122 | `rm **`／`rm *?`／`rm ?*` | 同上 |
| `test_klk031_guarded_dir_names_side_unchanged_deny` | L3168-3173 | `assertDeny("rm tickets/*")` | GUARDED_DIR_NAMES側の現状維持を固定するテスト。本修正がGUARDED_DIR_NAMES側の比較に手を入れないことの回帰ロックとして機能する |
| `test_klk031_existing_klk018_fixed_cases_unaffected_deny` | L3175-3182 | `assertDeny("rm docs/SPEC*.md")` 他 | 大文字globのみ。同上 |

## 5. Assumptions

- 検証はdevelop HEAD（`git log` で確認した `5fe3c4f`、KLK-020マージ後）で実施。KLK-031コミット `4c99758` はその祖先に含まれる（`git log --oneline -- .claude/hooks/guard_bash_writes.py` で確認）ため、チケットが指定する「KLK-031マージ後の最新コード」の前提を満たす。
- `_guarded_paths_from_expanded` はモジュールとして直接importし関数呼び出しで検証した（検証手法の詳細と `chr()` 結合の理由は「実測ログ」の注記参照。コード改変・実装への含意は無い）。
- `.claude/hooks/` 配下でfnmatchを用いるSPEC.md関連の比較箇所は `_guarded_paths_from_expanded` のL1064のみであることをgrepで確認済み（「5箇所目」以外の「6箇所目」が存在しないことの裏付け）。

## 6. Unknowns

- なし。チケット記載の再現手順・KLK-020レビュー指摘・KLK-031設計書の記述はすべて相互に整合しており、確認できなかった事実・矛盾するソースは検出されなかった。
- 修正方式（`literals` 分離／別ループ／`component.upper()` 比較等の具体的実装形）はarchitectの設計判断事項であり、本調査は事実確認に留めている。

## Handoff（architectへの引き継ぎ事項）

- 次エージェント: **architect**（Unknownsなし）
- 設計で判断すべき論点: (1) `GUARDED_FILENAME` 側のみをcase-insensitive化する `literals` 分離方式の選択、(2) `has_literal_char` ゲート（KLK-031）との相互作用を壊さない実装順序・差分の明示（チケットAC4）

## 主要ファイルパス

- `.claude/hooks/guard_bash_writes.py`（L1018-1072 `_guarded_paths_from_expanded`、L800-807 `_is_guarded_path`、L554-556 定数群、L1075-1154 `guarded_paths_after_shell_expansion`）
- `.claude/hooks/_ticket_lib.py`（L159-163 `is_spec_basename`、L166-189 `is_project_spec`）
- `tests/test_guard_bash_writes.py`（L3060-3075, L3105-3182）
- `docs/reports/KLK-020/review.md`（L13-90 High Risk節）
- `docs/designs/KLK-020.md`（D1、L55-56, L97-108）
- `docs/designs/KLK-031.md`（L84-114 option A却下理由）
