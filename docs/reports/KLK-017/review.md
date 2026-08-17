# KLK-017 レビュー詳細（reviewer）

レビュー日: 2026-08-17
対象: worktree `../kenesis-loop-kit.wt/KLK-017`（ブランチ `feature/KLK-017-design-doc-backfill`、コミット `d13284b`〜`75ef681`）
tester Quality Gate = pass（659件、failures 0・errors 0）を`python3 -m unittest discover -s tests`で再現確認済み（23.18秒）

## 1. Critical Issues
なし。

## 2. High Risks
なし。プロダクションコード（`.claude/hooks/guard_bash_writes.py`）・`README.md`・`CHANGELOG.md`の差分0件を`git diff develop...HEAD`で確認し、文書修正チケットの前提と一致。

## 3. Medium Risks
- Phase表（§4-8）でKLK-017のスコープは「Phase 15 追補」の1行に集約され、C10書き戻し6項目・H6・H7・SV-22〜25・M27・M28・V-13・V-16という約15項目の受け入れ条件が単一Phaseへ束ねられている。設計書自身が「独立してリリースできる粒度ではない」と自己点検で明記しており妥当性の説明はあるが、本チケット固有の粒度としては薄い。ブロッキングではないが記録として指摘。
- `tests/test_guard_bash_writes.py`のINV-SH-22エントリで文字列リテラルがコンマなしで2行に暗黙連結されており（Pythonとしては正しく動作するが他行のフォーマットと不統一）、将来の編集で見落とされやすい。

## 4. Missing Tests
なし。`tests/test_klk017_doc_wiring.py`（12件）がV-13の機械照合常設化・INV-AWKLEX-14/INV-SH-22のdeny確認・H7/SV-22の決着記録・README/docstringの現状記述維持・SV-25のPhase完了状態を全てカバー。新規2件（INV-AWKLEX-14・INV-SH-22）は既存の`test_inventory_cases_match_expected_decisions`（T-INVENTORY、hookをサブプロセス実行するend-to-end検証）にも自動的に含まれ実働確認済み。

## 5. Spec Violations
なし。INV-SED-09（`sed -n '1w tickets/active/APP-001.md' in.md`、期待値deny）が実在し、H7の脅威型と完全に一致することを`tests/test_guard_bash_writes.py`407行目で直接確認。README.md・モジュールdocstringは`SED_SAFE_PROGRAM_CHARS`に基づく位置非依存のホワイトリスト記述であり、アドレス前置き形も含めて`w`/`W`は自動deny — 「未対応」注記は不要という設計判断が正確であることをソース直読で確認。

## 6. Suggested Fixes
- （任意・非ブロッキング）`tests/test_guard_bash_writes.py`のINV-SH-22タプルの文字列連結をコンマ付きの通常の複数要素、または1行の文字列に統一する。

## 7. Approval Status
**approved**

## 確認根拠ファイル
- `docs/designs/KLK-010.md`（§10 Open Questions決着事項、§4-8 Phase 15追補、§3-11写像表）
- `tests/test_guard_bash_writes.py`（INVENTORY_CASES、INV-SED-09〜16、T-INVENTORY）
- `tests/test_klk017_doc_wiring.py`（新規12件）
- `.claude/hooks/README.md`・`.claude/hooks/guard_bash_writes.py`（差分0件を確認）
- `docs/reports/KLK-017/implementation.md`・`docs/reports/KLK-017/test-report.md`
