# KLK-032 レビュー詳細（reviewer / orchestrator代筆）

- レビュー日: 2026-08-19
- レビュー対象: worktree `../kenesis-loop-kit.wt/KLK-032` のコミット `558ed28`（Phase 1: コード）・`4eb47a1`（Phase 2: テスト）・`762cada`（test-report）
- 前提: tester Quality Gate = pass（`docs/reports/KLK-032/test-report.md`、792件全PASS）
- 判定: **approved**

## 1. Critical Issues

- なし。

## 2. High Risks

- なし。実装は設計書§4（一意引用・変更後コード・docstring文面）と完全一致し、792件全PASSをreviewerが独立再実行で確認。AC4（KLK-031ゲート行4項目のバイト単位無変更）はdiffの `+`/`-` 行へのgrepで0件を機械的に確認し、ゲートブロックは現物でも無傷であることを確認した。

## 3. Medium Risks

### 3-1. 否定文字クラスでのunitレベルTrue→False（新規実装の非単調性・本番経路では回帰なし）

- `.upper()` 正規化は非単調であり、旧実装 `fnmatchcase("SPEC.md", "[!s]PEC.md")` = True が、新実装 `is_spec_basename_fnmatch("[!s]PEC.md")` = `fnmatchcase("SPEC.MD", "[!S]PEC.MD")` = False になる（実測で確認）。
- ただし `!` は `SHELL_EXPAND_PATHISH_RE`（guard_bash_writes.py L554）の文字集合外のため、`[!...]` を含むトークンは候補抽出の段階で分断され、本番経路では旧新いずれの実装でも当該比較に到達しない。end-to-end実測でも旧新とも `rm docs/[!s]PEC.md` はallowであり、回帰なし。
- 影響: 設計書§7の「True→Falseの後退は構造的に発生しない」はend-to-endでは成立する（実測確認済み）が、ヘルパー単体レベルでは厳密には不正確。`is_spec_basename_fnmatch` のdocstringにもこの但し書きがないため、将来 `is_spec_basename_fnmatch` に別の呼び出し元が追加された場合（pathish正規表現を経由しない経路）に顕在化しうる。

### 3-2. 既存の未文書化すり抜け（本修正起因ではない・同族の残存ベクタ）

- `rm docs/[!x]PEC.md` はディスク上の `SPEC.md` にシェルglobとして一致するが、pathish正規表現が `!` でトークンを分断するため、旧新いずれの実装でも検出されない（誤allow）。
- これはKLK-020レビュー（High Risk指摘）→KLK-032という系譜と同族の「候補抽出正規表現の文字集合起因」の残存ベクタであり、本チケットのスコープ（fnmatch比較の大小区別）とは独立した既存欠陥。フォローアップチケットの起票を推奨する。

### 3-3. 検証の結果、問題なしと判定した項目

- 例外経由fail-open懸念（upper後の無効範囲 `[Z-a]` → `[Z-A]`）: Python 3.12のfnmatchは例外を送出せずFalseを返す。旧新同挙動を実測確認。問題なし。
- Unicode upper特殊ケース（`ſpec.md` → `SPEC.MD` 等）: deny方向のみの拡大であり、設計書§6の想定内（`is_spec_basename` と同一の正規化方式で一貫）。問題なし。

## 4. Missing Tests

- `[!...]` 否定文字クラスの挙動固定がない（ヘルパー単体でのFalse・end-to-endでの現状allowのいずれも未ロック）。Medium 3-1／3-2の回帰検出器を兼ねるため、フォローアップチケット側でのテスト追加を推奨する。本チケットの設計書§9のテスト観点は全件充足済みのため、差し戻し理由とはしない。
- それ以外は設計書§9の観点(1)〜(4)＋libヘルパーTrue/False系と実装済みテストが1:1で一致（tester報告と独立に突き合わせて確認）。

## 5. Spec Violations

- なし。AC1〜AC4は設計書§4-5のPhase表で全カバーされ、実装・テストで実証済み。
  - AC1: 旧新比較の独立実測でも確認（旧: `docs/sp*.md` → `[]`／`find_violation` → None、新: → `['docs/SPEC.md']`／deny）
  - AC3: スコープ限定（active/done側 `fnmatchcase` 維持）を現物確認
  - AC4: ゲート行バイト単位無変更を機械的に確認
- 軽微: 設計書§7の「True→Falseの後退は構造的に発生しない」という主張がヘルパー単体レベルでは厳密でない（Medium 3-1参照）。end-to-endでは成立を実測確認済みのため違反とはしない。

## 6. Suggested Fixes（フォローアップ推奨・本チケットは差し戻し不要）

1. `[!...]` 否定クラスのpathish分断による既存すり抜け（Medium 3-2）の是正検討チケットを起票する。
2. その際、`is_spec_basename_fnmatch` を和集合形 `fnmatchcase("SPEC.md", pattern) or fnmatchcase("SPEC.MD", pattern.upper())` にすればヘルパー単体でも単調（deny面の縮小なし）にできる。
3. ヘルパーdocstringへ否定クラスの但し書き（非単調性）を追記する。
4. ロールバック戦略（設計書§8）は妥当: Phase 1/2が別コミットでrevert可能・状態なし。誤allow再導入となるため人間判断必須の注記も適切。

## 7. Approval Status

**approved**

承認サマリ: 実装は設計書§4と逸脱ゼロ、AC1〜AC4充足、792件全PASS（reviewer独立再実行）、AC4独立検証済み、deny面拡大は大小閉包に限定（予算ロックテストあり）。Medium指摘2件はいずれも本番経路で回帰なし（実測確認済み）または既存欠陥であり、フォローアップ起票で扱うのが適切。

## 主要ファイル

- `.claude/hooks/guard_bash_writes.py`（L1076-1094 比較分岐・L554 pathish正規表現）
- `.claude/hooks/_ticket_lib.py`（L169-181 `is_spec_basename_fnmatch`）
- `tests/test_guard_bash_writes.py`（KLK-032節）・`tests/test_ticket_lib.py`（ヘルパー単体）
- `docs/designs/KLK-032.md`・`docs/reports/KLK-032/investigation.md`・`docs/reports/KLK-032/test-report.md`
