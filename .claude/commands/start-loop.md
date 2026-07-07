# /start-loop

.claude/agents/orchestrator.md を読み込み、orchestratorとして以下を実行してください。

## 起動時チェックリスト（必須・スキップ禁止）

ループを開始する前に以下を順番に確認し、問題があれば人間に報告してから次へ進む。

- [ ] **Autoモードの確認**
  権限モードがautoになっているか確認する。`.claude/settings.json` の `permissions.defaultMode` が `"auto"` 以外、または現在のセッションがautoモードでない場合は、人間に「Autoモードを有効化しないと、コマンド承認でループが頻繁に停止する」旨を伝え、有効化を促す（`defaultMode: "auto"` の設定、またはセッションのモード切替）。autoが有効になるまでループ本処理へ進まない。

- [ ] **14日超blockedチケットの検出**
  tickets/active/ の全チケットを読み取り、`status = blocked` かつ `updated` から14日以上経過しているチケットを一覧表示する。該当チケットがあれば人間に「再開 / クローズ / 期限延長」のいずれかを確認する。

- [ ] **in_progress上限チェック**
  `status` が `investigation_done` / `design_done` / `implementation_done` / `test_passed` のいずれかのチケット件数を集計する（blockedは数えない。積み上がりは14日トリアージが担当）。3件以上の場合は「既存チケットを完了またはcancelledにしてから新規着手してよいか」を人間に確認する。

- [ ] **done/件数チェック（アーカイブ提案）**
  tickets/done/ のチケット件数（.gitkeepを除く）を確認する。20件を超えている場合は `/archive` の実行を人間に提案する（CLAUDE.md「アーカイブ」参照）。

## ループ実行手順

1. tickets/active/ を全件読み取り、statusとpriorityを確認する
2. 処理対象チケットをpriority順に一覧表示する（cancelled / blocked を除く）
3. 最優先チケットのstatusに応じて、次に委譲すべきエージェントを判断する
4. 対応するエージェント定義ファイル（.claude/agents/*.md）を読み込み、作業を開始する

引数が指定された場合（例: /start-loop APP-001）は、指定されたチケットIDを優先して処理する。

複数チケットを各完了時の承認ゲートで止めずに連続実行したい場合は、`docs/batch-loop.md`（複数チケットの連続ループ実行ガイド）を参照する。
