# サブエージェントレポートの詳細外部化

各エージェントのRequired Output Formatは、各項目「要点5行以内の箇条書き」を上限とする。
5行を超える詳細（全文・生ログ・網羅的な根拠列挙等）はチケット本文へ書かず、
このディレクトリ配下のファイルへ外部化し、チケットには要点＋ポインタのみを残す。

architectは対象外（既存どおり `docs/designs/{ID}.md` に設計全文を記載する運用を継続する）。

## 運用ルール

- **命名規則**: `docs/reports/{ID}/{phase}.md`。`{ID}` はチケットIDと一致させる
- **phase一覧**:
  | phase | 対応するロール | 作成タイミング |
  |---|---|---|
  | `investigation` | investigator | 調査報告の要点が5行を超える場合 |
  | `implementation` | implementer | 実装メモの要点が5行を超える場合 |
  | `test-report` | tester | テスト実行結果・カバレッジ詳細が5行を超える場合 |
  | `review` | reviewer | レビュー詳細（Critical/High/Medium Risksの全量等）が5行を超える場合 |
- **writer分担（自筆/代筆）**: Write/Editツールを既に持つエージェント（implementer・tester）は自ら当該ファイルを作成・上書きする。Write/Editツールを持たないエージェント（investigator・reviewer）は、orchestratorが受け取った全文を代筆で書き出す
- **上書き運用**: 同一チケット・同一phaseの再実行時は同一ファイルを上書きする。差し戻しで同じロールが再実行された場合、チケットのログに「{phase}を再実施 - 理由」の1行を追記する（`docs/designs/{ID}.md` の改訂運用と同型）。過去の内容はGitヒストリで追う（ファイル自体にライフサイクル状態は持たせない）
- **gitignore対象外**: `docs/reports/` はGitで追跡する（`docs/designs/`・`docs/wireframes/*.html` と同じ扱い）。ループメトリクス（`tickets/.metrics*`）のような環境固有の生成物とは異なり、意思決定の根拠を残す実質的なプロジェクト文書のため
- **frontmatterなし**: 先頭は `# {ID} {phase}` の見出しと「生成: {ロール} / 最終更新: {日付}」の1行に留める。チケットのfrontmatter（`status`・`retry_counts`等、hookが検証する）と視覚的に混同されないようにするため
- **機密情報の扱い**: `docs/security-policy.md` の規約がそのまま適用される。コミット前に機密情報（APIキー・パスワード・接続文字列等）が含まれていないことを確認する

## ファイル

| ファイル | 用途 |
|---|---|
| `{ID}/investigation.md` | investigatorの調査詳細（orchestratorが代筆） |
| `{ID}/implementation.md` | implementerの実装メモ詳細（自筆・上限超過時のみ） |
| `{ID}/test-report.md` | testerのテスト実行結果・カバレッジ詳細（自筆・上限超過時のみ） |
| `{ID}/review.md` | reviewerのレビュー詳細（orchestratorが代筆） |

詳細は `docs/designs/KLK-004.md` を参照。
