# KLK-024 レビュー詳細

生成: reviewer（代筆: orchestrator） / 最終更新: 2026-08-17
対象: `.claude/hooks/guard_bash_writes.py` の `_take_backtick` 1段階アンエスケープ修正（worktree `../kenesis-loop-kit.wt/KLK-024`, ブランチ `fix/KLK-024-backtick-unescape`, コミット `f2a8763`→`111a2f7`→`83c4f99`）
要点はチケット `KLK-024` の「レビューメモ」を参照。本ファイルは全文。

## Tester Quality Gate結果の確認
独立に`python3 -m unittest tests.test_guard_bash_writes -v`を実行し220件全件pass、`LEGACY_DENY_COMMANDS`が130件（ast解析で件数確認）であることを確認。`git diff f2a8763 --stat`でプロダクションコード（`.claude/hooks/guard_bash_writes.py`）とテスト（`tests/test_guard_bash_writes.py`）以外に変更が無いことも確認済み。Quality Gate pass報告は妥当と判断しレビューを開始した。

## 独自の実機検証
修正前（f2a8763時点）のhookコピーと修正後のhookを並べて同一入力に投入し、AC1再現形が旧=allow・新=denyへ転じることを実際に確認（tester報告の裏付け）。AC1/AC2/多段ネスト(depth2〜5)/AC3系も独自スクリプトで再現し、テストコードの主張と一致することを確認した。

## 1. Critical Issues
なし。

## 2. High Risks
なし。

## 3. Medium Risks
- `_unescape_backtick_body`の対象3種のうち`` \` ``はE2E(hook経由)テストで実測されているが、`\$`→`$`はpure-function単体テスト(T-KLK024g)でのみ検証され、実際に`` `echo \$(rm ...)` ``（バックティック内でエスケープされた`$(...)`が1段階アンエスケープで真の`$(...)`置換に化けるケース）を通しで検証するE2Eテストが無い。独自に検証した結果、実装は正しくdenyしており（旧コードは同ベクタをallowしていたことも確認済み）バグではないが、`_take_subst`/`_skip_balanced`との相互作用を固定する回帰テストが欠落しており、将来のリファクタで無警告のまま壊れうる。

## 4. Missing Tests
- 上記3の`\$`統合シナリオ（`` `echo \$(rm docs/SPEC.md)` ``相当）を固定するE2Eテストが無い。T-KLK024hとして追加を推奨（必須ではない。実装済み挙動は独自検証で正しいことを確認済み）。

## 5. Spec Violations
なし。`_take_backtick`・`BACKTICK_UNESCAPE_RE`・`_unescape_backtick_body`は設計書§4-1のコードと完全一致（diff照合済み）。`_skip_backtick`・`_skip_balanced`・`_extract_degraded_substs`・`find_violation`・`subst_violation`は無変更（diff全文照合・シンボル行番号照合で確認）。AC1〜AC6は設計書§9・実装Phase表（単一Phase）で全てカバーされており、T-KLK024a〜g（tester追加g含む）で個別に裏付けられている。AC6の「`_extract_degraded_substs`が`_take_backtick`を共有呼び出し」は`grep`でコード上直接確認済み（正常経路の呼び出し行1067/1119と同一関数）。コミットメッセージ（`[KLK-024] Phase 1: ...`・`[KLK-024] テスト追加: ...`）は`implementer.md`/`tester.md`のGit Rulesと一致。ロールバック戦略（`_unescape_backtick_body`先頭への`return text`挿入）は既存コード構造上機能する単一無効化点であることを確認。

## 6. Suggested Fixes
- Medium Risksで指摘した`\$`+`$(...)`統合シナリオの回帰テスト追加を、次のフォローアップ（改善ループまたは別チケット）で検討することを推奨する（本チケットのブロッカーとはしない）。

## 7. Approval Status
**approved**
