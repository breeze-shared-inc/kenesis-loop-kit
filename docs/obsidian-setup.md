# Obsidian セットアップガイド

`.obsidian/`はgitignore対象のため、新規クローン後にこのガイドを参考に設定してください。

---

## vault の開き方

1. Obsidianを起動
2. `Open folder as vault` を選択
3. プロジェクトルートの `tickets/` フォルダを選択

---

## 推奨プラグイン

### 1. Dataview（必須）

チケット一覧のクエリ表示に使用します。

**インストール:**
設定 → コミュニティプラグイン → 閲覧 → `Dataview` を検索してインストール

**有効化する設定:**
設定 → Dataview
- `Enable JavaScript Queries` → ON
- `Inline Query Prefix` → `=`（デフォルト）

### 2. Templater（推奨）

テンプレートからチケットを自動生成します。

**インストール:**
設定 → コミュニティプラグイン → 閲覧 → `Templater` を検索してインストール

**設定:**
設定 → Templater
- `Template folder location` → `Templates`
- `Trigger Templater on new file creation` → ON

### 3. Kanban（推奨）

ドラッグ&ドロップでチケットのステータスを変更できます。

**インストール:**
設定 → コミュニティプラグイン → 閲覧 → `Kanban` を検索してインストール

---

## ダッシュボードの設定

`tickets/_index.md` をObsidianで開くと、Dataviewによるチケット一覧が表示されます。

表示されない場合はDataviewプラグインが有効になっているか確認してください。

---

## Kanbanボードの作成（任意）

ステータスをカンバン形式で管理したい場合は以下の手順で作成できます。

1. `tickets/`内に新規ファイルを作成（例: `kanban.md`）
2. コマンドパレット（Cmd/Ctrl + P）から `Kanban: Create new board` を実行
3. 以下のステータスをレーンとして設定:
   - `todo`
   - `investigation_done`
   - `design_done`
   - `implementation_done`
   - `test_passed`
   - `done`

---

## おすすめのワークスペースレイアウト

```
左サイドバー: ファイルエクスプローラー（tickets/active/を展開）
メインエリア: _index.md（ダッシュボード）
右サイドバー: 作業中チケットのファイル
```

ワークスペースはObsidian設定 → ワークスペース から保存できます。
チーム展開時はこのドキュメントの末尾にワークスペース設定のスクリーンショットを追加しておくと便利です。
