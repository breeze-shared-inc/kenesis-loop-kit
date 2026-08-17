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
- **writer分担（自筆/代筆）**: Write/Editツールを既に持つエージェント（implementer・tester）は自ら当該ファイルを作成・上書きする。Write/Editツールを持たないエージェント（investigator・reviewer）は、orchestratorが受け取った全文を代筆で書き出す（本表は各エージェント定義の Ticket Integration／Git Rules 節を正とする横断サマリであり、詳細は各 `.claude/agents/*.md` を参照）
- **上書き運用**: 同一チケット・同一phaseの再実行時は同一ファイルを上書きする。差し戻しで同じロールが再実行された場合、チケットのログに「{phase}を再実施 - 理由」の1行を追記する（`docs/designs/{ID}.md` の改訂運用と同型）。過去の内容はGitヒストリで追う（ファイル自体にライフサイクル状態は持たせない）
- **gitignore方針（プリセットにより異なる。KLK-026 AC5決定）**: プライベートプリセット（`.gitignore.private`）では`docs/reports/`を`docs/designs/`・`docs/wireframes/*.html`と同じくGitで追跡する。パブリックプリセット（`.gitignore.public`）では`docs/reports/{ID}/`配下（`docs/reports/*/`）を除外する（`tickets/active|done/*.md`と同じ「生の作業ログ・プロセス記録」の性質を理由とする）。本ファイル（`docs/reports/README.md`）自体は`docs/reports/`直下のためどちらのプリセットでも常に追跡される
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

## ポインタの解決性（いつ読めるか）

チケット本文の「詳細: docs/reports/{ID}/{phase}.md」ポインタは、ファイルの書き込み場所に
よってメインツリー（`tickets/`と同じ場所）から即座に解決できるかどうかが異なる。

- **investigation.md・review.md（orchestratorが代筆）**: いずれもメインツリーで作成し即座に
  commitされる（手順は `.claude/agents/orchestrator.md`「worktreeライフサイクル管理」を正と
  する。investigation.mdはworktree作成時、review.mdはレビュー完了時にそれぞれcommitされる）。
  以後はメインツリーのチケットから常に解決できる
- **implementation.md・test-report.md（implementer/testerが自筆）**: チケット専用worktree内
  の作業ブランチ上でcommitされ、developへはreviewer承認後のマージでのみ取り込まれる。
  そのため実装完了直後からreviewer承認・マージ完了までの間（tester→implementer・
  reviewer→implementerの差し戻しで滞留している間を含む）は、メインツリーのチケットから
  ポインタを解決できない
  - この間に内容を確認する必要がある場合は、該当worktreeを直接参照する:
    `cd ../{リポジトリ名}.wt/{ID} && cat docs/reports/{ID}/implementation.md`
  - マージ完了後は他の閲覧者にも通常どおり見える
  - この制約はコード自体が既に持つ制約と同型であり、新たな非対称ではない
    （`docs/designs/KLK-004.md` §6リスク表で許容と判断済み）
