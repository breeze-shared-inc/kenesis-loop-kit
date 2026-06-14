# /new-ticket

CLAUDE.md のチケット管理ルールに従い、新規チケットを作成してください。

## 手順

1. tickets/active/ と tickets/done/ を確認し、現在の最大IDを特定して次の連番を採番する
2. $ARGUMENTS の内容からチケット種別を判断する
   - "bug" "バグ" "エラー" "不具合" を含む場合 → tickets/Templates/ticket-bug.md を使用
   - それ以外 → tickets/Templates/ticket.md を使用
3. テンプレートをコピーし、以下を置換する
   - `{{TICKET_ID}}` → 採番したID（例: APP-001）
   - `{{TITLE}}` → $ARGUMENTS から読み取ったタイトル
   - `{{DATE}}` → 現在日時（YYYY-MM-DD形式）
   - `{{PROJECT_NAME}}` → CLAUDE.md またはプロジェクトルートのフォルダ名から取得
4. tickets/active/{ID}_{タイトル}.md として保存する（スペースは_で代替）
5. 作成したチケットの内容を表示し、ユーザーに確認を求める

## 使用例

```
/new-ticket ログイン機能の実装
/new-ticket バグ: ログイン後にセッションが切れる
```
