# KLK-020 レビュー詳細（reviewer外部化レポート）

## レビュー対象
- worktree: `/home/bzg55/workspace/breeze/kenesis-loop-kit.wt/KLK-020`（ブランチ `fix/KLK-020-hookのパス判定基準統一`）
- 独立検証: `git diff develop...HEAD`（9ファイル変更）を全件読解、`python3 -m unittest discover -s tests` を自ら再実行し**760件OK**を確認（tester報告と一致）、`_ticket_lib.is_project_spec` は旧ロジックを再実装したうえで全パターン総当たり比較を実施し**回帰ゼロ・想定どおりの拡大のみ**を確認、さらに `guard_bash_writes` の `_guarded_paths_from_expanded`/`find_violation` を直接呼び出して独自の追加検証を実施

## is_project_spec 実装形の独立検証
実装形（`rpartition("/")`でdir/base分解）が設計書の制約を満たすか、旧ロジックを別途再実装し
全cwd×全パスの組合せで比較した（regressions=[], widened=[intended case-insensitive matchesのみ]）。
回帰（True→False）はゼロ。widenされたのは basename の大小差のみで、ディレクトリ部分・ネスト除外は
一切変化なし。implementer/testerの申し送りは妥当と判断。

## High Risk: GUARDED_FILENAME（_guarded_paths_from_expanded）のcase-sensitivity残存

### 該当コード（.claude/hooks/guard_bash_writes.py、本PRで未変更の既存コード）
```python
GUARDED_FILENAME = "SPEC.md"  # L544

def _guarded_paths_from_expanded(expanded):
    ...
    for literal in literals:
        if not fnmatch.fnmatchcase(literal, component):  # 大小区別あり
            continue
        ...
```

### 再現手順・実測結果（本worktreeで直接import・実行）
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
- 非glob形の小文字 `docs/spec.md` は本PRの修正どおり正しく `_is_guarded_path` で検出される。
- glob分断形（`docs/sp*.md`・`docs/Spec*.md`等、実測両方で確認）は `_guarded_paths_from_expanded`
  の component 照合が `fnmatch.fnmatchcase(GUARDED_FILENAME, component)`（大小区別あり）である
  ため検出漏れが発生し、`find_violation` が None（違反なし＝許可）を返す。
- 一方、大文字glob（`docs/SP*.md`）は既存の `test_klk018_fragmented_glob_spec_side_read_allow`
  （`assertDeny("rm docs/SPEC*.md")`）で検証済みどおり正しく検出される（本PRでの検証でも
  ブロックされることを確認）。

### 評価
- 本PRが新規に持ち込んだ回帰ではない（GUARDED_FILENAME・_guarded_paths_from_expandedはこの
  diffで未変更）。
- ただし設計書D1・チケット「期待する動作」が掲げる「一律case-insensitive化・片方だけ直すと
  新たな非対称を生む」という原則には照らすと未達成であり、investigation.md B節が数え上げた
  「4箇所」は実際には網羅的でなかった（5箇所目が存在した）ことになる。
- 実害条件: (1) 何らかの経路で既に小文字/混在名の docs/spec.md 実体が存在すること、
  (2) 攻撃者/エージェントがglob難読化（`sp*.md`等）で意図的にガードを回避しようとすること、
  の両方が揃って初めて意味を持つ。単純な `docs/spec.md` への直接書き込みは本PRの修正で
  正しくガードされる。

### 推奨修正
1. `_guarded_paths_from_expanded` のSPEC.md側照合を大小区別なしにする
   （`component.upper()` と `GUARDED_FILENAME.upper()` の比較、または
   KLK-031で導入された `has_literal_char` 条件と同様に `_ticket_lib.is_spec_basename`
   を経由する形へ寄せる）。GUARDED_DIR_NAMES（active/done）側はチケットのスコープ外の
   ため無変更のままでよい。
2. 回帰テスト追加（`docs/sp*.md`・`docs/Spec*.md` 等の小文字/混在globがdenyされること、
   KLK-018既存テストと対称の形で）。
3. KLK-031（別チケット、`guarded_paths_after_shell_expansion`の孤立globによる誤deny）の
   前例に倣い、本件も独立フォローアップチケットとして即時起票することを推奨する。
   なお、KLK-031のimplementerは同じ`_guarded_paths_from_expanded`のSPEC.md側判定条件に
   「成分がリテラル文字を最低1文字含む」条件を追加済み（コミット`4c99758`）であり、
   本件の推奨修正（大小区別なし比較）と隣接するコード領域を触るため、着手順序・
   コンフリクト回避を人間が判断すること。

## Medium: 陳腐化したdocstring
`.claude/hooks/guard_bash_writes.py` の `_is_guarded_path_component` docstring
（該当箇所: `_is_guarded_path 自体は無変更` の一文）が、本PRで `_is_guarded_path` を
`lib.is_spec_basename` 経由へ変更したことと矛盾する。機能影響はないが、KLK-029時点の
文脈説明がKLK-020後も未更新のまま残っている。次回このdocstringに触れる際に
「`_is_guarded_path`のbasename**完全一致という判定方式**自体はKLK-020後も変わらない
（case-insensitive化されたのみ）」等、誤解のない表現へ更新することを推奨する。

## Approval Status
**approved**

判定理由: チケットのAC1〜AC5はすべて設計書Phase表でカバーされ、実装・テストとも独立検証で
妥当性を確認した（760件PASS・回帰ゼロ・4箇所是正の正当性実証・pinningテストの防御コメント
確認・README addendumの整合確認）。上記High Riskの5箇所目の残存ギャップは本PRが新規に
持ち込んだ回帰ではなく、既存のKLK-018機構における前提から独立した別関数の話であるため、
本チケットの承認を妨げるブロッカーとはしない。ただし「一律case-insensitive化」という設計
原則を完全に達成するため、KLK-031と同様の形でフォローアップチケットの即時起票を強く推奨する。
