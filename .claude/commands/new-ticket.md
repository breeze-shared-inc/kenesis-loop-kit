# /new-ticket

CLAUDE.md のチケット管理ルールに従い、新規チケットを作成してください。

## 手順

1. プロジェクト略称を特定する: CLAUDE.md「チケットID採番」節の「このプロジェクトの略称」の行を優先し、無ければプロジェクトルートのフォルダ名から推定する（`/setup` で確定・追記できる）
2. tickets/active/ と tickets/done/ を確認し、現在の最大IDを特定して次の連番を採番する
3. $ARGUMENTS の内容からチケット種別を判断する
   - "bug" "バグ" "エラー" "不具合" を含む場合 → tickets/Templates/ticket-bug.md を使用
   - それ以外 → tickets/Templates/ticket.md を使用
4. テンプレートをコピーし、以下を置換する
   - `{{TICKET_ID}}` → 採番したID（例: APP-001）
   - `{{TITLE}}` → $ARGUMENTS から読み取ったタイトル
   - `{{DATE}}` → 現在日時（YYYY-MM-DD形式）
   - `{{PROJECT_NAME}}` → 手順1で特定したプロジェクト略称の取得元と同じ（CLAUDE.mdの略称行、無ければフォルダ名）
5. tickets/active/{ID}_{タイトル}.md として保存する（スペースは_で代替）
6. 作成したチケットの内容を表示し、ユーザーに確認を求める

## 使用例

```
/new-ticket ログイン機能の実装
/new-ticket バグ: ログイン後にセッションが切れる
```
