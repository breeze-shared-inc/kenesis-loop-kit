# /batch-loop-inline

.claude/agents/orchestrator.md を読み込み、orchestratorとしてセッション内バッチ（旧方式復旧・1セッションで複数チケットを連続実行）を起動してください。**このコマンドは対話セッション専用**です（ヘッドレス実行は想定しません。ヘッドレスでの連続実行が必要な場合は `/batch-loop`（外部駆動・`scripts/batch_loop.py`）を使ってください）。運用ガイド・事前承認テンプレートの正・停止条件の詳細は `docs/batch-loop-inline.md` を参照してください。使い分けは `docs/batch-loop.md` 冒頭の比較表を参照してください。

## 手順

1. $ARGUMENTS からチケットID列を読み取る（スペース区切り・記載順が実行順）
   - 形式: `{チケットID} {チケットID} ...`（例: `APP-001 APP-002`）
   - IDが1件以下の場合は連続実行の意味がないため `/start-loop {ID}` を案内して終了する
2. ID列を検証する: 各IDが `tickets/active/{ID}_*.md` に一意に存在し、statusが `cancelled` / `blocked` / `done` のいずれでもないこと（引数内のID重複は拒否する）。違反があれば一覧提示して開始しない
3. `.claude/commands/start-loop.md`「起動時チェックリスト」（Autoモード確認・14日blockedトリアージ・in_progress上限・done/件数警告・残存worktree検出）を**バッチ開始前に1回だけ**実行する（1セッション内で状態は変わらない前提。チケットごとの再チェックはしない）
4. `docs/SPEC.md` が存在しない場合、SPEC免除が人間承認済みであることを人間に確認する
5. `docs/batch-loop-inline.md`「事前承認テンプレート」を対象チケット列で埋めて人間へ提示し、明示的な承認を得る。**このテンプレートへの人間の承認が「バッチ連続実行の事前承認」の実体**（承認が得られなければ開始しない）
6. 承認後、対象チケットを先頭から順に処理する。各チケット開始前に `retry_counts` をスナップショットする
7. 1チケットの処理は通常の実装ループ委譲ロジック（orchestrator.md Agent Delegation Rules）にそのまま従う。対話セッションのためAskUserQuestion等はそのまま人間に確認してよい（`/batch-loop` のヘッドレス制約は適用されない）
8. チケットが `done` または `blocked` になるたびに次の判定を行う
   - `blocked` → 停止して報告し、人間の指示を待つ
   - `done` かつ `retry_counts` 増分あり → 要約報告して停止し、続行の再承認を求める
   - `done` かつ増分なしかつ残りチケットあり → 要約報告して次のチケットへ進む
   - `done` かつ残りチケットなし（最終チケット）→ 要約報告して停止し、通常の改善ループ判断（実装ループ継続/設計見直し/調査やり直し）を人間に確認する
9. チケットのstatus更新・ログ追記・done/への移動は通常どおりorchestratorが行う（本コマンド固有の書き込みルールはない。単一ライター原則・worktreeライフサイクル管理は orchestrator.md・docs/worktree-policy.md のまま）

## Never

- ヘッドレス実行を想定しない（ask hook等ヘッドレス固有の配慮は不要。ヘッドレス連続実行が必要な場合は `/batch-loop`（外部駆動）を使う）
- 事前承認（手順5）を得ずにチケット間を自動前進しない
- `retry_counts` 増分を検知したにもかかわらず人間の再承認なしに次のチケットへ進まない
- 大量件数・長時間の無人実行を目的として使わない（トークン累積のトレードオフを人間へ明示せずに実行しない）。多数件・無人実行が目的の場合は `/batch-loop` を案内する

## 使用例

```
/batch-loop-inline APP-001 APP-002
/batch-loop-inline APP-001 APP-002 APP-003
```
