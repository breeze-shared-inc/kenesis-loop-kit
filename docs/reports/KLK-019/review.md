# KLK-019 review

生成: reviewer（orchestrator代筆） / 最終更新: 2026-08-18

## 事前確認
- worktree（`/home/bzg55/workspace/breeze/kenesis-loop-kit.wt/KLK-019`、ブランチ`fix/KLK-019-control-structure-false-deny`）の全コミットを`git log develop..HEAD`・`git diff develop...HEAD`で確認
- `tickets/active/KLK-019_...md`（status: test_passed、tester_to_implementer=1）・`docs/designs/KLK-019.md`（develop最新48bb1ed、Open Questions 0件）を確認した上でレビュー開始
- `python3 -m unittest discover -s tests -v`をworktreeで実際に実行し735件全件PASSを独立に再現確認（tester報告と一致）

## Critical Issues
なし。

## High Risks
- なし。核心制約`ALLOWED_HEADS`/`CWD_SAFE_HEADS`はgit diffで一切の変更が無いことを確認（該当行のdiffヒット0件）
- R-CTRL1（ループ変数値追跡不能）・R-CTRL4（cwd追跡/登録共有漏れ）・R-CTRL7（case共有時の登録漏れ）はいずれも専用回帰テスト（`test_klk019_r_ctrl4_*`・`_regression_nested_*`5件・`_r_ctrl7_*`4件）で固定され、実機bash検証済み
- `degraded_violation`は設計書どおり無変更を確認（diff上に本関数への変更なし）

## Medium Risks
- **test-report.md §8-1の実測値誤り**: 「LEGACY_DENY_COMMANDS: 138件」と記載されていたが、実際にworktreeでモジュールをimportして計測すると130件（ブランチ分岐点・develop双方と同じ、無回帰）。AC5は実測値主義を明示的に要求しており、この数値のみ不正確だった。機能的な回帰は無い。**→ implementerが訂正済み（コミット`fd21d92`）**
- コードコメントの参照先テスト名の不整合: `.claude/hooks/guard_bash_writes.py`の`CONTROL_CLOSING_KEYWORDS`定義コメントが検出器として誤ったテスト名を挙げていた（実装コメントのみのドリフト、機能影響なし）。**→ implementerが訂正済み（コミット`fd21d92`）**
- 「重要な注記」のスクリプトファイル迂回について: README「既知の未対応（本hook導入当初から遮断できていない）」の記載、および本チケットのdiffが制御構文ストリップ関連関数に限定され`ALLOWED_HEADS`へ`bash`等を追加していないことから、KLK-019の変更が新たに生んだ穴ではないと確認。tester自身のtest-report.md §8-4の記述（developにKLK-019未反映であることが直接原因）とも整合しており、本チケットのスコープ外の既存構造的限界であることを確認した

## Missing Tests
見当たらず。`INVENTORY_CASES`にINV-CTRL-01〜28（実測28件、120件中）を追加、`test_klk019_*`専用テスト19件、AC6のtester独自25パターン検証（mismatch 0）でAC1〜AC7・R-CTRL1〜7の全観点をカバー。`LEGACY_DENY_COMMANDS`130件・既存`INVENTORY_CASES`（INV-SH-11含む）は無回帰と直接計測で確認。

## Spec Violations
なし。実装（`strip_control_prefix`・`strip_outer_control_keywords`・`_strip_leading_outer_keyword`・`_parse_for_header`・`_strip_case_clause`・`mentions_guarded_var`・`record_loop_binding`・`record_assignments`）は設計書§4のコードとほぼ逐語一致（R-CTRL3・R-CTRL7の設計修正はarchitectが§10で正式承認済み）。Phase表（Phase1→AC1/AC5基盤、Phase2→AC2/AC3、Phase3→AC4/AC6/AC7）は本チケットのAC1〜AC7全件をカバーしている。

## Suggested Fixes
上記Medium Risksの2件はimplementerが本レビュー後に修正済み（コミット`fd21d92`）。追加の推奨事項なし。

## Approval Status
**approved**

上記Medium Risksの2件は文書・コメント上の不整合であり、コード自体の安全性（`ALLOWED_HEADS`/`CWD_SAFE_HEADS`無変更・735件全件PASS・R-CTRL1〜7の実機bash二方向検証済み・新規の許可経路が無いこと）を損なわないため承認。指摘した2件はimplementerが即座に修正済み。

## 参照ファイル（絶対パス）
- `/home/bzg55/workspace/breeze/kenesis-loop-kit.wt/KLK-019/.claude/hooks/guard_bash_writes.py`
- `/home/bzg55/workspace/breeze/kenesis-loop-kit.wt/KLK-019/tests/test_guard_bash_writes.py`
- `/home/bzg55/workspace/breeze/kenesis-loop-kit/docs/designs/KLK-019.md`
- `/home/bzg55/workspace/breeze/kenesis-loop-kit/tickets/active/KLK-019_シェル制御構文の誤deny解消.md`
- `/home/bzg55/workspace/breeze/kenesis-loop-kit.wt/KLK-019/docs/reports/KLK-019/implementation.md`
- `/home/bzg55/workspace/breeze/kenesis-loop-kit.wt/KLK-019/docs/reports/KLK-019/test-report.md`
