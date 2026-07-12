# worktree並行作業ガイド（worktree分離ポリシー）

複数のチケットを並行して作業するときに、`git worktree` で作業ツリーを分離するための運用ルールです。

## 原則：コードだけをworktreeへ、チケットはメインツリーに一本化

このKitでは「コードはブランチで分岐してよいが、**チケット状態は分岐してはいけない**」。

- `.gitignore.public` プリセットでは `tickets/active|done/*.md`・`tickets/.metrics*.json*` がGit管理外のため、worktreeを新規作成してもそこには空の `tickets/` しか存在しない
- 状態検証hook（validate_ticket_state / record_metrics / check_loop_integrity）は各作業ツリーの `tickets/` を基準に検証・記録するため、複数のworktreeでチケットを更新すると状態機械とメトリクスがworktreeごとに分裂し、ドリフト検知の前提が壊れる
- privateプリセット（実チケットをコミットする運用）でも、複数ツリーで同一チケットを編集すればマージ競合と整合性崩壊を招く

したがって、**チケット・メトリクスへの書き込みはメインworktree（orchestratorが動く場所）のみ**で行い、追加のworktreeはコード作業専用とする。これは「チケット書き込みはorchestrator専任」ポリシー（CLAUDE.md チケット管理ルール）の空間方向への拡張である。

## 運用ルール

### 1チケット = 1ブランチ = 1worktree
- worktreeはチケット単位で作成する。ブランチ命名は既存規約どおり `feature/{チケットID}-{タイトルのkebab-case}`（`.claude/agents/implementer.md`「Git Rules」）
- 並行worktreeは**最大3つ**まで（in_progress上限3件と対にし、既存ルールと矛盾させない）

### 配置と命名
- リポジトリの**兄弟ディレクトリ**に置く: `../{リポジトリ名}.wt/{チケットID}/`
- リポジトリ内（`.worktrees/` 等）には置かない — glob検索やhookの走査対象に紛れ込むリスクがあるため

### ライフサイクル（worktreeの寿命 = チケットの寿命）

```bash
# チケット着手時（developから派生）
git worktree add ../{リポジトリ名}.wt/APP-012 -b feature/APP-012-{slug} develop

# developへのマージ完了後
git worktree remove ../{リポジトリ名}.wt/APP-012
git worktree prune   # 残骸の掃除
```

- ディレクトリを手動 `rm -rf` で消すと管理情報の残骸が出るため禁止。必ず `git worktree remove` を使う
- マージ完了後に放置しない。「worktreeの寿命 = チケットの寿命」で揃える

### worktree側でやってはいけないこと
- `tickets/`・`docs/SPEC.md` の編集（そもそも存在しないか、状態分裂の元になる）
- `git push`（既存規約どおり人間のみ）
- worktree側のセッションは成果を**コミットまで**で止める。チケットへのステータス反映は、メインworktreeのorchestratorに報告して行わせる

## Claude Code側のworktree機能との使い分け

| 場面 | 手段 |
|---|---|
| 1セッション内でサブエージェントが並行してファイルを触る | Agentツールの `isolation: "worktree"`（自動作成・未変更なら自動掃除） |
| 人間が複数セッションを並行して走らせる | 本ガイドの手動worktree |

## 注意点

- `.claude/settings.local.json` はGit管理外のため、worktree側のセッションには個人の許可設定が引き継がれない（hookは `.claude/` 配下でGit追跡されているため全worktreeで有効に働く）
- privateプリセットでメトリクスも追跡する運用にした場合は、`.gitattributes` に `tickets/.metrics.jsonl merge=union` を指定すると追記ログのマージ競合を回避できる
