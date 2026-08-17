# KLK-026 implementation

生成: implementer / 最終更新: 2026-08-17

## Summary

設計書 `docs/designs/KLK-026.md` のPhase1〜Phase3を、記載どおりの文言・差分で実装した。
AC1〜AC6・機械検証テストのすべてに対応する。設計からの逸脱・再定義は行っていない。

## Files Changed

- `.claude/agents/orchestrator.md`（変更）: 「worktreeライフサイクル管理」節へ (a)
  作成手順2直後に `docs/reports/{ID}/investigation.md` のdevelopコミット指示、(b)
  「マージ・削除」見出し直前に「レビュー完了時（承認・差し戻し共通・マージ判断の前）」
  サブセクション（`docs/reports/{ID}/review.md` のメインツリー作成・develop即時コミット・
  KLK-012方式非採用の明記）を追加
- `docs/worktree-policy.md`（変更）: 「作業場所の境界」表を2行とも `docs/reports/` の
  行き先を含む形に差し替え、表直後に「reviewerはworktree行にのみ現れる」注記を追加。
  「ライフサイクル」作成手順1をdocs/reports/{ID}/investigation.mdバンドルコミット版に
  差し替え、「削除」見出し直前に「レビュー完了時」サブセクションを追加（orchestrator.mdと
  同一運用をミラー）
- `docs/reports/README.md`（変更）: 末尾に「## ポインタの解決性（いつ読めるか）」節を新設
  （investigation/review＝常に解決可能、implementation/test-report＝マージ前・差し戻し
  滞留中は解決不能、を明記）。既存「gitignore対象外」箇条書きをプリセット別（public除外・
  private追跡）の記述に訂正（AC5・Phase2）
- `.claude/agents/implementer.md`（変更）: Git Rulesの実装メモ外部化の1文を、
  「testerへの引き継ぎ前に必ずコミットする」という義務表現に改訂（従来の「反映してよい」を置換）
- `.claude/agents/tester.md`（変更）: Git Rulesの2文を、「reviewerへの引き継ぎ前に必ず
  コミットする」「Quality Gate fail時もtest-report.mdをコミットしてから差し戻す」という
  義務表現に改訂
- `.gitignore.public`（変更・Phase2）: 末尾に `docs/reports/*/` 除外パターンを追加
  （`docs/reports/README.md` はサブディレクトリでないため対象外のまま追跡される）
- `.gitignore.private`（変更なし・設計指示どおり）
- `docs/designs/KLK-004.md`（変更・Phase2・AC6）: §5「影響範囲」表の
  `.gitignore.public` / `.gitignore.private` 1行まとめの記述を、2行に分割・訂正
  （public=変更・除外パターン追加、private=変更なし・引き続き追跡）
- `tests/test_klk026_doc_wiring.py`（新規・Phase3）: 上記すべての文言・差分を検証する
  回帰ガード。既存 `tests/test_klk004_doc_wiring.py` と同型の文言存在検証パターン

## Implementation Notes

- すべて設計書§4の文言・old_string/new_stringどおりに適用した（再定義なし）
- orchestrator.mdとdocs/worktree-policy.mdの「レビュー完了時」サブセクションは、両ファイルで
  KLK-012実運用（コミット `979c062`）を正規手順として不採用と明記する形で同期させた
- `.gitignore.public`への`docs/reports/*/`追加は新規ファイルのみに効き、既存追跡済み
  （KLK-005/012/023/026の各`docs/reports/{ID}/*.md`）を遡及的に追跡解除しないことを
  設計§7どおり確認済み（実装では`git rm --cached`等の操作は行っていない）
- 実装対象7ファイルの変更はすべて追加的（文言追加・行分割・置換）で、状態機械・hookロジック
  （`.claude/hooks/*.py`）には一切触れていない
- worktree内で `docs/reports/KLK-026/investigation.md` が読めない状態（本チケットが
  修正しようとしているバグそのものの再現）を確認した。これはメインツリー側で
  investigator完了時に未コミットのまま残っていたためで、本チケットのAC1実装により
  今後のチケットから解消される（本チケット自体の遡及修正はスコープ外）

## Test Coverage

- `python3 -m unittest discover -s tests -v` を実行し、578件全件pass（既存558件＋新規20件）
- 新規テスト `tests/test_klk026_doc_wiring.py`: AC1（investigation/review.mdコミット手順・
  KLK-012非採用の明記）、AC2（implementer/tester義務表現）、AC3（境界表2行＋reviewer注記）、
  AC4（ポインタの解決性節）、AC5（gitignore非対称性）、AC5/AC6（KLK-004.md訂正）を
  文言存在ベースで検証
- 詳細: docs/reports/KLK-026/implementation.md（本ファイル）

## Remaining Risks

- 設計§6が既に指摘済み: 本チケットの規定はプロンプトベースの義務であり、hookによる
  機械強制ではないため、エージェントが実際にコミットを忘れる可能性は残る
  （`tests/test_klk026_doc_wiring.py`は文言の回帰のみを保証する）
- `docs/reports/KLK-005,012,023,026`の既存追跡済みファイルは`.gitignore.public`変更後も
  Git管理下に残り続ける（設計§7のとおり、遡及的追跡解除は別判断としてスコープ外）
