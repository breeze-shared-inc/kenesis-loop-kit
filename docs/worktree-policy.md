# worktree分離ポリシー（コード作業の分離）

チケットのコード作業を `git worktree` でメインツリーから分離するための運用ルールです。開発ループ（`/start-loop`・バッチ外部駆動）ではworktree分離を**標準**とし、orchestratorがライフサイクル（作成・マージ・削除）を管理します。

## 原則：コードだけをworktreeへ、チケットはメインツリーに一本化

このKitでは「コードはブランチで分岐してよいが、**チケット状態は分岐してはいけない**」。

- `.gitignore.public` プリセットでは `tickets/active|done/*.md`・`tickets/.metrics*.json*` がGit管理外のため、worktreeを新規作成してもそこには空の `tickets/` しか存在しない
- 状態検証hook（validate_ticket_state / record_metrics / check_loop_integrity）は各作業ツリーの `tickets/` を基準に検証・記録するため、複数のworktreeでチケットを更新すると状態機械とメトリクスがworktreeごとに分裂し、ドリフト検知の前提が壊れる
- privateプリセット（実チケットをコミットする運用）でも、複数ツリーで同一チケットを編集すればマージ競合と整合性崩壊を招く

したがって、**チケット・メトリクスへの書き込みはメインworktree（orchestratorが動く場所）のみ**で行い、追加のworktreeはコード作業専用とする。これは「チケット書き込みはorchestrator専任」ポリシー（CLAUDE.md チケット管理ルール）の空間方向への拡張である。

## 作業場所の境界（誰がどこで働くか）

| 作業場所 | エージェント | 扱うもの |
|---|---|---|
| メインツリー | orchestrator / investigator / architect | チケット・メトリクス・SPEC・設計書（docs/designs/） |
| チケット専用worktree | implementer / tester / reviewer | コード・テスト・コミット |

- 境界は「ドキュメントとコードの境界」に一致する。設計より前の工程はコードを変更しないためメインツリーで完結し、実装以降はコードを触るためworktreeへ移る
- implementer / tester / reviewer への委譲時、orchestratorは委譲プロンプトにworktreeの絶対パスを明記する（手順は `.claude/agents/orchestrator.md`「worktreeライフサイクル管理」を正とする）

## 運用ルール

### 1チケット = 1ブランチ = 1worktree
- worktreeはチケット単位で作成する。ブランチ命名は既存規約どおり `feature/{チケットID}-{タイトルのkebab-case}`（`.claude/agents/implementer.md`「Git Rules」）
- 並行worktreeは**最大3つ**まで（in_progress上限3件と対にし、既存ルールと矛盾させない）

### 配置と命名
- リポジトリの**兄弟ディレクトリ**に置く: `../{リポジトリ名}.wt/{チケットID}/`
- リポジトリ内（`.worktrees/` 等）には置かない — glob検索やhookの走査対象に紛れ込むリスクがあるため

### ライフサイクル（orchestratorが管理・worktreeの寿命 = チケットの寿命）

**作成 — design_done → implementer委譲の直前**（詳細手順は `.claude/agents/orchestrator.md`「worktreeライフサイクル管理」を正とする）

1. `docs/designs/{ID}.md` をdevelopへコミットしてから派生する（worktree内から設計書を読めるようにするため）
2. `mkdir -p ../{リポジトリ名}.wt && git worktree add ../{リポジトリ名}.wt/{チケットID} -b feature/{チケットID}-{slug} develop`
3. 差し戻し再実装では既存のworktree・ブランチを継続使用する

**削除 — reviewer承認後・done化の前**

1. worktree内に未コミット変更がないことを確認する
2. メインツリー（develop）で `git merge --no-ff feature/{チケットID}-{slug}` を実行する — マージはorchestratorのローカル操作（`git push` は従来どおり人間のみ）
3. `git worktree remove ../{リポジトリ名}.wt/{チケットID} && git branch -d feature/{チケットID}-{slug} && git worktree prune`
4. マージ競合時は `git merge --abort` してチケットをblocked化し、人間へエスカレーションする（競合解決は人間の責務）

- ディレクトリを手動 `rm -rf` で消すと管理情報の残骸が出るため禁止。必ず `git worktree remove` を使う
- マージ完了後に放置しない。「worktreeの寿命 = チケットの寿命」で揃える。セッション中断等での取り残しは `/start-loop` 起動時チェックリストの「残存worktreeの検出」が拾う

### worktree側でやってはいけないこと（implementer / tester / reviewer共通）
- `tickets/`・`docs/SPEC.md` の編集（そもそも存在しないか、状態分裂の元になる）
- `git push`（既存規約どおり人間のみ）
- worktree側の作業は成果を**コミットまで**で止める。チケットへのステータス反映は、メインworktreeのorchestratorに報告して行わせる

### worktree内でのコマンド実行（権限allowlistとの整合）
- worktree内でのBash作業は `cd ../{リポジトリ名}.wt/{チケットID} && {コマンド}` の**複合コマンド**で行う
- `git -C {パス} {サブコマンド}` は使わない — `.claude/settings.json` の許可ルール（`Bash(git add*)` 等）はコマンド文字列の前方一致で評価されるため、`-C` を挟むと許可（`git add*`）にも拒否（`git push*`）にも合致しなくなる

## 権限設定（作業ディレクトリ外への書き込み許可）

worktreeはリポジトリの外（兄弟ディレクトリ）にあるため、セッションの追加作業ディレクトリとして登録しないとWrite/Editが許可されない。

- **対話セッション**: `.claude/settings.json` の `permissions.additionalDirectories` に `../{リポジトリ名}.wt/` を登録する。**リポジトリのフォルダ名を変えた（Kitを別名でcloneした）場合は、この値も実際のフォルダ名に合わせて変更する**
- **バッチ実行**: `scripts/batch_loop.py` が `--add-dir ../{リポジトリ名}.wt` を自動付与する（配置先ディレクトリも起動前に作成する）

## Claude Code側のworktree機能との使い分け

| 場面 | 手段 |
|---|---|
| 開発ループのコード作業（implementer / tester / reviewer） | 本ポリシーのチケット専用worktree（orchestratorがBashで作成・削除） |
| 1セッション内でサブエージェントが並行してファイルを触る（ループ外の作業） | Agentツールの `isolation: "worktree"`（自動作成・未変更なら自動掃除） |
| 人間が複数セッションを並行して走らせる | 本ポリシーのworktree（人間が作成・削除する場合も規約・配置・上限は同一） |

## 注意点

- `.claude/settings.local.json` はGit管理外のため、worktree側のセッションには個人の許可設定が引き継がれない（hookは `.claude/` 配下でGit追跡されているため全worktreeで有効に働く）
- 複数セッションを並行して走らせる場合、コードはworktreeで完全に分離されるが、チケット・メトリクスの書き込みはメインツリー一本化のままであり同時書き込みの調停はしない。バッチ実行中に同じリポジトリで対話セッションや別バッチを開かない、という既存の注意（docs/batch-loop.md）は引き続き守ること
- privateプリセットでメトリクスも追跡する運用にした場合は、`.gitattributes` に `tickets/.metrics.jsonl merge=union` を指定すると追記ログのマージ競合を回避できる
