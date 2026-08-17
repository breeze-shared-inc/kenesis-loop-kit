# KLK-029 レビュー結果（reviewer）

worktree `/home/bzg55/workspace/breeze/kenesis-loop-kit.wt/KLK-029`（ブランチ `fix/KLK-029-escape-aware-mention-gate`、develop起点4コミット）を対象に、チケット・設計書・investigator/implementer/testerレポートを確認したうえで、コードレベルで独立検証を実施した。

## 独立検証で実施したこと
1. `git diff develop...HEAD` で `PATHISH_RE`/`guarded_paths`/`_is_guarded_path`/`is_guarded_token`/`mentions_guarded` の5定義をPython ASTベースで抽出し develop/HEAD 間で完全一致（byte-identical）であることを確認（AC4）
2. `is_guarded_token`/`mentions_guarded` の他の呼び出し箇所（13箇所）が引き続き素の関数を使っており、置換ではなくOR追加のみであることをgrepで確認（R2主張の裏付け）
3. `_is_guarded_path_component` と `_is_guarded_path` の差分がSPEC.md判定1行のみ（成分一致 vs basename完全一致）であり、tickets/active|done・.claude除外ロジックは同一であることを確認
4. `degraded_violation` 関数本体・`awk_violation`内`if degraded:`分岐（AW-5/AW-6）が本diffのハンク範囲外であり無変更であることを確認（R-U1の裏付け）
5. `python3 -m unittest tests.test_guard_bash_writes -v` を実行し216件全pass（自分の環境で再現）
6. tester報告のsubTest破壊実験を自分でも再実行（INV-SED-27の期待値を一時的に反転→`FAIL`が個別パラメータ付きで検出されることを確認→`git checkout`で復元・`git status`クリーンを確認）。tester手法の妥当性を独立担保
7. コミット4件（Phase1/2/3+テスト追加）・機密情報混入なしをgrepで確認

## Critical Issues
なし。

## High Risks
なし。AC4（既存鎖無変更）・P8型OR追加のみの安全性主張は独立検証により裏付けが取れており、allow方向への後退は構造的に発生しない。

## Medium Risks
- R1⑥（`_is_guarded_path_component`の成分一致緩和がSPEC.mdを中間成分として含む無関係言及を新規denyにしうる理論的リスク）は216件全pass中に実例化なし。sed/awk専用ゲート限定・deny方向限定のため影響範囲は設計どおり局所的
- R-U1（degraded経路の同型バイパス）・R-U2（sed/awk以外headの同型バイパス）は人間承認済みUnknownとして残存。コード上も`degraded_violation`が本diffの変更対象外であることを確認済みで、記載と実装に矛盾なし

## Missing Tests
実質的な欠落なし。単体境界3形（畳み込み・成分融合差分）・誤検出方向固定（INV-SED-30/31・INV-AWK-24/25）・非sed/awkパイプ回帰（既存`cat|grep`ケース）まで一貫してカバー。implementerのPhase1手動確認は`find_violation()`直接呼びで設計書の「hookへ実際に投入」の字面と厳密には異なるが、INVENTORY_CASES側のテストは`run_guard`経由で実際の`permissionDecision`出力を検証しており実質ギャップなし。

## Spec Violations
該当なし。本チケットはKit自体の改善で`spec_version: "なし"`（設計書冒頭に明記）のためSPEC.md参照は対象外。

## Suggested Fixes
必須の修正なし（マージ可能な状態）。任意提案: R1⑥の境界を明示的にexerciseするテストケース（SPEC.mdを中間成分として含むが無関係な言及）を将来チケットで追加すると、現状「理論的境界・未実例化」の主張がより強く固定される。

## Approval Status
**approved**

## 実測結果の詳細
- AC4差分確認コマンド結果: `guarded_paths`/`_is_guarded_path`/`is_guarded_token`/`mentions_guarded`の4関数本体と`PATHISH_RE`定義がdevelop/HEAD間で完全一致（`identical: True`をPythonで確認）
- `python3 -m unittest tests.test_guard_bash_writes -v` → `Ran 216 tests ... OK`（自環境で再現）
- 破壊実験再現: `INV-SED-27`の期待値を`"deny"`→`"allow"`に書き換え単独実行した結果、`test_inventory_cases_match_expected_decisions ... (id='INV-SED-27', ...) ... FAIL`が個別表示され`AssertionError`のトレースバックが出力された。直後に`git checkout -- tests/test_guard_bash_writes.py`で復元し`git status --short`が空であることを確認
- `awk_violation`のAW-1/AW-2/ゲートが`degraded`の値に関わらず`is_guarded_token_in_program`/`mentions_guarded_in_program`を使う実装（設計書§3「対象外の明示」どおり、deny方向にのみ作用するため安全と判断）をコードで確認
- `statement_violation`の`has_program_head`分岐は`has_program_head`が偽の場合`gate_hit = cwd_is_guarded(cwd) or mentions_guarded(expanded_words)`と旧コード同一であり、sed/awk非含有文の挙動が変わらないことをコードで確認
- コミット粒度: `374c098`(Phase1)/`212cfbb`(Phase2)/`2a2fe48`(Phase3)/`c3be2bb`(テスト追加)の4件。コミットメッセージは`[KLK-029] {要約}`規約に準拠。`git diff develop...HEAD`全体をgrepし機密情報（password/api-key/secret/token=/秘密鍵ヘッダ）該当なし

## 参照した成果物パス
- `tickets/active/KLK-029_mentions_guardedのエスケープ回避によるsedゲート未発火.md`
- `docs/designs/KLK-029.md`
- `docs/reports/KLK-029/implementation.md`
- `docs/reports/KLK-029/test-report.md`
- `.claude/hooks/guard_bash_writes.py`（worktree内）
- `tests/test_guard_bash_writes.py`（worktree内）
