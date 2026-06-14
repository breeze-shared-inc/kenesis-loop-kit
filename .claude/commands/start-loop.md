# /start-loop

agents/orchestrator.md を読み込み、orchestratorとして以下を実行してください。

## 起動時チェックリスト（必須・スキップ禁止）

ループを開始する前に以下を順番に確認し、問題があれば人間に報告してから次へ進む。

- [ ] **14日超blockedチケットの検出**
  tickets/active/ の全チケットを読み取り、`status = blocked` かつ `updated` から14日以上経過しているチケットを一覧表示する。該当チケットがあれば人間に「再開 / クローズ / 期限延長」のいずれかを確認する。

- [ ] **in_progress上限チェック**
  `status != todo` かつ `status != done` かつ `status != cancelled` のチケット件数を集計する。3件以上の場合は「既存チケットを完了またはcancelledにしてから新規着手してよいか」を人間に確認する。

## ループ実行手順

1. tickets/active/ を全件読み取り、statusとpriorityを確認する
2. 処理対象チケットをpriority順に一覧表示する（cancelled / blocked を除く）
3. 最優先チケットのstatusに応じて、次に委譲すべきエージェントを判断する
4. 対応するエージェント定義ファイル（agents/*.md）を読み込み、作業を開始する

引数が指定された場合（例: /start-loop APP-001）は、指定されたチケットIDを優先して処理する。
