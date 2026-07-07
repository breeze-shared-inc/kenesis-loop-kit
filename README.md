# Kenesis Loop Kit

Claude Codeとのループエンジニアリングを実践するための、チケット管理・エージェント定義フレームワークです。

---

## コンセプト

**ループエンジニアリング**は、AIエージェントと人間が反復的に協調しながら開発を進める手法です。そのために重要なのが**状態の外部化**——作業の状態・文脈・判断の根拠をAIのメモリに依存せず、ファイルとして明示的に保持することです。

Kenesis Loop Kitは以下の3つを組み合わせてこれを実現します。

- **Obsidian** — チケットの可視化・人間向けの状態管理UI（**任意**）
- **Markdownチケット** — Claude Codeが読み書きできる状態の外部化媒体
- **エージェント定義** — 各フェーズで呼び出すClaude Codeのサブエージェントルール

> **Obsidianは必須ではありません。** このフレームワークの実体はMarkdownファイル群であり、Claude Codeとテキストエディタ（VS Code等）だけで完結します。チケットの作成・更新・ステータス管理・ループの進行はすべてClaude Codeがファイルを直接読み書きして行うため、Obsidianが無くても全機能が動作します。Obsidianは「人間がチケットを一覧・可視化するためのUI」を追加で提供するだけの位置づけです。ダッシュボード（`tickets/_index.md`）のDataviewクエリやKanban表示が不要であれば、導入をスキップして構いません。

---

## ディレクトリ構成

```
kenesis-loop-kit/
├── README.md
├── CHANGELOG.md                     ← フレームワークの変更履歴
├── CLAUDE.md                        ← Claude Codeへの運用ルール（必ず読み込む）
├── .gitignore
├── .gitignore.private               ← プライベートリポジトリ用テンプレート
├── .gitignore.public                ← パブリックリポジトリ用テンプレート
├── .claude/
│   ├── settings.json                ← Claude Codeの権限設定・hook登録
│   ├── agents/                      ← サブエージェント定義
│   │   ├── orchestrator.md
│   │   ├── investigator.md
│   │   ├── architect.md
│   │   ├── implementer.md
│   │   ├── tester.md
│   │   └── reviewer.md
│   ├── hooks/                       ← 状態検証・メトリクス記録hook
│   │   ├── validate_ticket_state.py ← 書き込み前の状態検証（PreToolUse）
│   │   ├── check_loop_integrity.py  ← 終了時のループ整合性チェック（Stop）
│   │   ├── record_metrics.py        ← ステータス遷移の記録（PostToolUse）
│   │   └── _ticket_lib.py           ← 検証ルール共有ライブラリ
│   ├── metrics/
│   │   └── aggregate.py             ← メトリクス集計（/metricsが実行）
│   └── commands/                    ← スラッシュコマンド定義
│       ├── start-loop.md            ← /start-loop
│       ├── new-ticket.md            ← /new-ticket
│       ├── improvement-loop.md      ← /improvement-loop
│       ├── archive.md               ← /archive
│       └── metrics.md               ← /metrics
├── docs/
│   ├── SPEC.md                      ← 要件定義（人間が記述）
│   ├── designs/                     ← チケット単位の設計書（architectが生成）
│   │   ├── _TEMPLATE.md             ← 設計書テンプレート
│   │   └── {ID}.md                  ← 例: APP-001.md
│   └── obsidian-setup.md            ← Obsidian初期設定ガイド
├── src/                             ← プロジェクトのソースコード
├── tests/                           ← hook検証・メトリクスの自動テスト（unittest）
└── tickets/                         ← Obsidian vaultとして開く
    ├── .obsidian/                   ← 常にgitignore
    ├── _index.md                    ← チケットダッシュボード
    ├── Templates/
    │   ├── ticket.md                ← 通常チケット
    │   └── ticket-bug.md            ← バグチケット
    ├── active/                      ← 進行中チケット
    └── done/                        ← 完了チケット
```

---

## セットアップ

### 1. リポジトリのクローン

```bash
git clone https://github.com/your-org/kenesis-loop-kit.git my-project
cd my-project
```

### 2. .gitignoreの設定

デフォルトの`.gitignore`はパブリックリポジトリ用（`tickets/active/`・`tickets/done/`の実チケットのみ除外する安全側）に設定されています。`tickets/Templates/`と`tickets/_index.md`はフレームワーク配布物としてどちらのプリセットでも追跡されます。

**プライベートリポジトリで`tickets/active/`・`tickets/done/`の実ファイルもコミットしたい場合のみ**、以下を実行してください。

```bash
cp .gitignore.private .gitignore
```

| ファイル | 用途 | tickets/active・done の扱い |
|---|---|---|
| `.gitignore`（デフォルト） | パブリックリポジトリ用 | 除外（安全側） |
| `.gitignore.private` | プライベートリポジトリ用 | コミット対象 |
| `.gitignore.public` | パブリックリポジトリ用 | 除外（デフォルトと同一） |

### 3. Obsidianでvaultを開く（任意）

> このステップはスキップ可能です。Obsidianを使わない場合は、`tickets/` 配下のMarkdownを通常のエディタで開けば同じ運用ができます。

ObsidianでOpen folder as vaultから`tickets/`フォルダを選択します。

推奨プラグイン:

| プラグイン | 用途 |
|---|---|
| Dataview | チケット一覧のクエリ表示 |
| Templater | テンプレートからの自動生成 |
| Kanban | ドラッグ&ドロップでのステータス変更 |

詳細なセットアップ手順は `docs/obsidian-setup.md` を参照してください。

### 4. docs/SPEC.mdを作成する

要件定義をまとめた`docs/SPEC.md`を作成します。investigatorとarchitectがこのファイルを参照して作業を進めます。SPEC.mdが存在しない場合、エージェントは作業を開始しません。

### 5. Claude Codeでの初回起動

```bash
claude
```

Claude Codeは起動時に`CLAUDE.md`を読み込み、エージェント構成と運用ルールを把握します。

---

## エージェント構成

開発ループは6つのサブエージェントで構成されます。各エージェントの詳細は`.claude/agents/`フォルダの定義ファイルを参照してください。

| エージェント | 役割 | 定義ファイル |
|---|---|---|
| orchestrator | ループ管理・チケット状態管理・エージェント委譲 | .claude/agents/orchestrator.md |
| investigator | 既存コード調査・依存関係トレース・影響範囲特定 | .claude/agents/investigator.md |
| architect | 設計・docs/designs/{ID}.md作成・受け入れ基準定義 | .claude/agents/architect.md |
| implementer | 承認済み設計に基づくコード実装 | .claude/agents/implementer.md |
| tester | テスト実行・カバレッジ確認・品質レポート生成 | .claude/agents/tester.md |
| reviewer | コードレビュー・SPEC/設計書との整合性チェック | .claude/agents/reviewer.md |

---

## 開発ループフロー

Kenesis Loop Kitは**実装ループ**と**改善ループ**の2つのループで構成されます。

```
[チケット作成]
      ↓
orchestrator
      ↓
investigator → architect → implementer → tester → reviewer
                                 ↑                     |
                                 └────── 実装ループ ────┘
                                        (差し戻し・修正)
                                               ↓
                                       [成果物を人間が確認]
                                        ↙              ↘
                               実装ループ継続          改善ループ
                               (新チケット作成)     investigator or
                                                    architectへ戻る
```

**実装ループ** — investigatorからreviewerまでエージェントが自律的に回します。差し戻しが発生してもエージェント間で完結し、人間は介在しません。

**改善ループ** — reviewerが承認した後、人間が実際の成果物を確認して判断します。設計の方向性が正しければ実装ループを継続し、見直しが必要なら調査・設計フェーズへ戻します。

### チケットのステータス遷移

```
todo
  └→ investigation_done   investigator完了
       └→ design_done          architect完了
            └→ implementation_done  implementer完了
                 └→ test_passed         tester Quality Gate通過
                      └→ done               reviewer承認・人間が成果物を確認
```

ブロッカーが発生した場合はいつでも`blocked`に遷移し、解消後に元のステータスへ戻ります。

---

## スラッシュコマンド

Claude Codeのスラッシュコマンドでよく使う操作を呼び出せます。

| コマンド | 用途 | 使用例 |
|---|---|---|
| `/start-loop` | ループを開始・再開する | `/start-loop` `/start-loop APP-001` |
| `/new-ticket` | チケットを新規作成する | `/new-ticket ログイン機能の実装` |
| `/improvement-loop` | 改善ループを起動する | `/improvement-loop APP-001 architect` |
| `/archive` | 完了チケットを個人vaultへ移動する | `/archive ~/my-vault/Archives/project-a/` |
| `/metrics` | ループの観測メトリクスを表示する | `/metrics` `/metrics APP-001` |

---

## チケットの使い方

### 新規チケット作成

`tickets/Templates/ticket.md`をコピーして`tickets/active/`に配置します。

```
tickets/active/APP-001_ログイン機能実装.md
```

ファイル名の形式: `{ID}_{タイトル}.md`（スペースは`_`で代替）

IDの形式: `{プロジェクト略称}-{3桁連番}`（例: `APP-001`）

### Claude Codeへの指示例

**ループを開始する:**
```
/start-loop
```

**特定チケットからループを開始する:**
```
/start-loop APP-001
```

**新規チケットを作成する:**
```
/new-ticket ログイン機能の実装
/new-ticket バグ: ログイン後にセッションが切れる
```

**成果物確認後に改善ループを起動する:**
```
/improvement-loop APP-001
/improvement-loop APP-001 investigator
```

**完了チケットをアーカイブする:**
```
/archive ~/my-vault/Archives/project-a/
```

---

## チケットテンプレート構造

各テンプレートは以下のセクションで構成されています。

```
フロントマター    ← orchestratorが状態管理に使用
概要             ← 何を・なぜやるか
受け入れ条件     ← 各エージェントの作業基準
実装メモ         ← investigator / architect / reviewer が追記
ブロッカー       ← Unknown・Open Questions を記録（解消後削除）
リトライカウンタ ← orchestratorが差し戻し回数を記録（frontmatter retry_countsと同期）
ログ             ← 全エージェントが時系列で追記（削除禁止）
関連             ← 関連チケット・docs/designs/{ID}.md・参考URLなど
```

---

## 複数プロジェクトでの運用

Kenesis Loop Kitを複数プロジェクトで使う場合、完了チケットを個人vaultにアーカイブする運用を推奨します。

```
my-vault/（プライベートリポジトリ）
└── Archives/
    ├── project-a/
    └── project-b/
```

`tickets/done/`が20件を超えたタイミングで、Claude Codeに以下のように指示します。

```
tickets/done/ のチケットを個人vaultの Archives/project-a/ へ移動してください。
```

---

## このフレームワークをベースに新プロジェクトを始める

1. このリポジトリをテンプレートとして使用（GitHub: Use this template）
2. プライベートリポジトリで`tickets/active/`・`tickets/done/`の実ファイルもコミットしたい場合のみ`cp .gitignore.private .gitignore`を実行する（デフォルトは安全側のpublic設定）
3. `docs/SPEC.md` を作成して要件定義を記述する
4. Obsidianで`tickets/`を開き、`docs/obsidian-setup.md`に従って初期設定をする
5. 最初のチケットを `/new-ticket` で作成して `/start-loop` でループを開始する

---

## ライセンス

MIT
