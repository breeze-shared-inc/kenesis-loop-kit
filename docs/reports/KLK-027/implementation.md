# KLK-027 implementation

生成: implementer / 最終更新: 2026-08-17（追記: リポジトリ直下.gitignore同期のrevert）

## Summary

docs/designs/KLK-027.md §3-§4・実装Phase表（Phase1〜3）に従い、AC1〜AC6および
リポジトリ直下`.gitignore`同期を実装した。書き手分担の重複記述①（Required Output
Format直下の括弧補記）を4エージェントファイルから削除し、②（Ticket Integration／Git
Rules）を単一の正とした。investigator.md/reviewer.mdのTicket Integrationへ「代筆で」を
1語挿入し、①削除で失われる「代筆」の語を②へ移設した（既存test_klk004_doc_wiring.pyの
`test_ghost_write_roles_present_in_own_agent_files`退行を防止）。AC2は現状維持を決定し
docstringのみ追記。AC4はgit check-ignore統合テストで実挙動を固定。AC5はrecord_metrics.py
の非衝突をサブプロセス実行で検証。AC6はポインタ書式定義の存在確認。リポジトリ直下
`.gitignore`を`.gitignore.public`と全行一致させた。

**追記（取消対応）**: 上記のリポジトリ直下`.gitignore`同期（`docs/reports/*/`除外ブロック
5行の追記）が、本リポジトリ自身の「docs/reports/{ID}/{phase}.mdをdevelopへコミットする」
運用と衝突すること（本ファイル自身が`git add`不能になった）が判明したため、人間の決定
（docs/designs/KLK-027.md develop最新版 §5・§6・§7・§9・§10）により当該追記をrevertした。
`.gitignore`は`*.skill`までの元の内容に戻し、`git diff develop -- .gitignore`が空である
ことを確認した。この結果、本ファイルは通常どおり`git add`可能になった。

## Files Changed

**Phase 1（コミット 2eb411d）:**
- `.claude/agents/investigator.md` — ROF括弧削除、Ticket Integrationへ「代筆で」挿入
- `.claude/agents/reviewer.md` — 同上
- `.claude/agents/implementer.md` — ROF括弧削除のみ
- `.claude/agents/tester.md` — ROF括弧削除のみ
- `docs/reports/README.md` — writer分担表末尾へ「②を正とする横断サマリ」の1文追記
- `tests/test_guard_bash_writes.py` — AC2決定のコメント追記（ロジック・アサーション変更なし）
- `.gitignore` — `.gitignore.public`46-50行目の`docs/reports/*/`ブロックを追記し全行一致化

**Phase 2（コミット 9d42fb0）:**
- `tests/test_klk027_doc_wiring.py`（新規） — AC1クロスチェック・AC3完全一致・AC6ポインタ書式
- `tests/test_metrics.py` — TestRecorderへ`test_docs_reports_path_ignored`を1件追加（AC5）

**Phase 3（コミット eaaef2c）:**
- `tests/test_klk027_gitignore_checkignore.py`（新規） — AC4: git check-ignore統合テスト

**revert対応（本コミット）:**
- `.gitignore` — Phase1で追記した`docs/reports/*/`除外ブロック（コメント含む5行）を削除し、
  `*.skill`までの元の内容に戻した（人間決定による取消。理由は上記Summary「追記」参照）
- `docs/reports/KLK-027/implementation.md`（本ファイル） — revert対応の追記

## Implementation Notes

- §4-Cの骨子どおり`extract_section`はtests/test_klk026_doc_wiring.pyの実装をそのまま移植した。
  骨子内の`test_rof_section_has_no_writer_attribution_bracket`の冗長な三項演算子
  （両分岐が同じ結果になる不要な条件分岐）は`"## " + rof_heading`に単純化した
- `test_readme_writer_table_matches_role_classification`は、骨子の
  `readme.split("代筆で書き出す", 1)[0]`によるself_sentence切り出しをそのまま採用しつつ、
  ghost側の`idx_ghost`計算をループ外に一度だけ出す軽微な整理を行った（挙動は骨子と同一）
- README.md「writer分担」行には元々"investigator"/"reviewer"の語が同一文より手前
  （phase一覧表）に出現するため、クロスチェックテストは弱いが骨子の意図（②③の齟齬検出）
  どおりに実装した
- Phase3のgit check-ignoreは、対象パスをファイルシステム上に実体化せずに実行しても
  4件全て意図通りの結果を返した（設計書§4-F実装注記のフォールバック手順は不要だった）
- 全編集はテキストレベルの削除・1語挿入・1文追加・新規テストファイルのみで、
  hookロジック・状態機械には触れていない

## Test Coverage

- `python3 -m unittest discover -s tests -v` 実測: **712件 実行、すべてOK**（Phase1+2完了時点は708件、Phase3で+4件）
- 既存`tests/test_klk004_doc_wiring.py`（14件）・`tests/test_klk026_doc_wiring.py`（19件）を
  個別実行し退行なしを確認（33件 OK）
- 新規`tests/test_klk027_doc_wiring.py`: 7件（TestWriterAttributionUnified 4件、
  TestRequiredOutputFormatMatchesDesignTemplate 1件、TestPointerFormatDefinitionExists 2件）
- 新規`tests/test_klk027_gitignore_checkignore.py`: 4件（public 2件・private 2件）
- `tests/test_metrics.py`追加分`test_docs_reports_path_ignored`: 1件
- （revert前）リポジトリ直下`.gitignore`と`.gitignore.public`は`diff -u`で差分なしを確認済み
- **revert後の再実測**: `python3 -m unittest discover -s tests -v` = **712件 実行、すべてOK**
  （revert前と同数、退行なし）。`tests/test_klk027_gitignore_checkignore.py`は
  `.gitignore.public`/`.gitignore.private`プリセットファイルを一時gitリポジトリへコピーして
  検証する設計（`GITIGNORE_PUBLIC`/`GITIGNORE_PRIVATE`定数）であり、リポジトリ実`.gitignore`
  には依存しないため4件とも影響なしを個別実行でも確認した
- `git diff develop -- .gitignore` は空（revert完全。`*.skill`までdevelopと全行一致）

## Remaining Risks

- なし（設計書§6リスクは全て軽減策どおり実装・実測確認済み）。README.mdのwriter分担
  クロスチェックはREADME内の語順に依存する弱い検定である旨は上記Implementation Notesに
  記録した（設計書の骨子どおりの実装であり、意図的な設計判断）
- revert対応: リポジトリ直下`.gitignore`は`.gitignore.public`と再び不一致になった
  （`docs/reports/*/`ブロック分）が、これは人間決定による意図的な状態であり
  docs/designs/KLK-027.md develop最新版§7に記録済み。追加のリスクは無い
