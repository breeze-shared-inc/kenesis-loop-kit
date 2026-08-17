# KLK-021 レビュー詳細

生成: reviewer（代筆: orchestrator） / 最終更新: 2026-08-17
対象: list_tickets.pyのcwd依存・相対root指定による無言0件の是正
要点はチケット `KLK-021` の「レビューメモ」を参照。本ファイルは全文。

## Approval Status: approved

## Critical Issues / High Risks / Medium Risks
なし（独自検証で解消）

## Missing Tests
なし。AC1〜AC9それぞれに対応する自動テストまたは実機確認手段が揃っており、T1(AC6)・T2(AC7)・T3(AC5)・T4×2(AC8)で新規5件、実測586件全pass

## Spec Violations
なし。設計書§9のAC1〜AC9を個別に独立検証し、全て充足を確認

## Suggested Fixes
特になし（軽微な指摘・改善提案もなし）

## 独立検証の詳細

**Git履歴・スコープ確認**
- `git log develop..HEAD --oneline`: 2dc404f(Phase1)/472ca89(Phase2)/de542e5(Phase3)/d9f84f9(testレポート)の4コミットのみ。developへの未承認マージなし（`git merge-base --is-ancestor HEAD develop`で確認）
- `git diff develop...HEAD --stat`: `scripts/list_tickets.py`・`tests/test_list_tickets.py`・`tests/test_guard_bash_writes.py`・`tests/test_klk003_doc_wiring.py`・`.claude/commands/start-loop.md`・`.claude/agents/orchestrator.md`・`docs/reports/KLK-021/test-report.md`の7ファイルのみ変更。設計書§4/§5に記載のファイル構成と完全一致。`test-report.md`はtester自身のレポート外部化（Write/Edit保持者が自ら書く運用）であり、scope外の変更ではない
- 機密情報スキャン（API key/password/secret/token等）: diff中に該当なし

**AC1〜AC9 個別検証（全て独立に確認）**
- AC1(H1): worktree内で`python3 scripts/list_tickets.py`を実機実行し、`対象: /home/.../KLK-021/tickets/active`が冒頭に出力され`計 0 件`との組み合わせで対象取り違えが判別可能なことを確認
- AC1(M2): T3テスト(`test_relative_root_matches_absolute_root`)を単体実行しpassを確認（絶対root/相対root+chdirの出力完全一致）
- AC2: `python3 -m unittest discover -s tests`を独立に2回実行し、両方とも**586件全pass**
- AC3: diff上で`format_target()`の呼び出しが`print(LEGEND)`の直前にあることを確認。実機出力でも冒頭1行目に現れることを確認
- AC4: `git diff develop...HEAD -- .claude/commands/start-loop.md .claude/agents/orchestrator.md`で各1文追記を確認
- AC5: `root = Path(root).resolve() if root is not None else ...`をソースで確認。M2は既にKLK-012の`is_ticket()`で解消済みだが、AC3の「解決済み絶対パス表示」要件のためには`.resolve()`化が別途必要（M2解消の有無に関わらずAC3充足のために必須）というdesign §3の論理は妥当と判断
- AC6: T1(`test_list_tickets_cli_allow`)は`_util.run_script(_util.GUARD_BASH, ...)`で`guard_bash_writes.py`を実サブプロセス起動しており、モックではなく実挙動を検証している（コード確認済み）
- AC7: **独自にミューテーション実験を実施**。`docs/policy-registry.md`の対象行の直後にダミー行を挿入した状態でT2(`test_row_is_last_line_of_contiguous_table_block`)を単体実行し、`AssertionError: 30 != 31 : 追加行が表の最終行になっていない(表途中への誤挿入)`でredになることを確認。直後に原本を復元し、`git status --porcelain`が空であること、`TestClaudeMdPolicyTable`全件再passを確認。tester報告と独立に整合する結果を得た
- AC8: `TestNoPositionalPathArguments`の2メソッドを含む全体テストが586件中でpassしていることを確認済み
- AC9: `git ls-files -s scripts/list_tickets.py` → `100755`を確認。shebang（`#!/usr/bin/env python3`）は1行目のまま変更なし

**CLI_INVOCATION衝突チェック**
- `tests/test_klk003_doc_wiring.py`の`CLI_INVOCATION = "python3 scripts/list_tickets.py"`（完全一致文字列）を追記文が含まないことを確認（追記文中は`` `scripts/list_tickets.py` ``のみ）。`grep -c`で確認したところ、追記後も start-loop.md 3件・orchestrator.md 1件で、既存の`test_cli_invocation_in_checklist_at_least_twice`（>=2件要求）等のアサーションと非衝突

**ファイルモード変更**
- `100644`→`100755`への変更のみで、shebang維持・機能変更なし。前例(KLK-007 `batch_loop.py`)と同型。テストスイートへの影響なし

**worktree専用性**
- 全コミットがfeatureブランチ`fix/KLK-021-list-tickets-cwd-fix`上にのみ存在し、developへの副作用なし

## 参照した実ファイル

- `docs/designs/KLK-021.md`
- `scripts/list_tickets.py`
- `tests/test_list_tickets.py`
- `tests/test_guard_bash_writes.py`
- `tests/test_klk003_doc_wiring.py`
- `.claude/commands/start-loop.md`
- `.claude/agents/orchestrator.md`
- `docs/reports/KLK-021/test-report.md`
