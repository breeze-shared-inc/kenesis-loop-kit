# /rollback

reviewer承認後に問題が発覚したチケットをロールバックしてください。CLAUDE.md「ロールバック手順」（通常のロールバック＋ロールバック時のチケット運用）を実行します。

## 手順

1. $ARGUMENTS からチケットIDとコミットハッシュ（任意）を読み取る
   - 形式: `{チケットID} [コミットハッシュ]`（例: `APP-001` / `APP-001 a1b2c3d`）
   - チケットIDが無い場合は「ロールバック対象のチケットIDを指定してください」と尋ねる
2. 対象チケットを tickets/done/ または tickets/active/ から読み込む。見つからない場合は報告して停止する
3. 現在のブランチを確認する（`git branch --show-current`）。mainの場合は通常ロールバックを実行せず、緊急ロールバック（hotfixブランチ運用・CLAUDE.md「緊急ロールバック」）を人間に案内して停止する
4. revert対象コミットを特定する
   - ハッシュ指定あり → `git log --oneline -1 {ハッシュ}` で存在と内容を確認する
   - 指定なし → `git log --oneline` から `[{チケットID}]` を含むコミットを一覧表示し、人間に選択してもらう
5. **実行前確認（必須）**: revert対象コミットの内容とこれから行うチケット操作を提示し、人間の承認を得る。承認が得られるまで実行しない
6. git操作を実行する
   - `git revert --no-edit {ハッシュ}`（複数コミットをrevertする場合は新しいものから順に）
   - コミットメッセージを `[{チケットID}][REVERT] {取り消した内容の要約}` へ修正する（`git commit --amend -m`）
   - `git push` はしない（pushは人間が行う）
7. チケット操作を実行する
   - tickets/done/ にある場合は、**status変更の前に** tickets/active/ へBashで移動する（/improvement-loop 手順2〜3と同じ順序。active/へ移動してからstatusを変更することで、PreToolUse検証とメトリクス記録が正しく効く）
   - statusを `implementation_done` に変更する（revert実装はtesterから再開するため）
   - ログセクションに「YYYY-MM-DD HH:MM: ロールバック実施 - {理由}」を追記する
   - `updated` を現在日時に更新する
   - チケットの変更は必ずWrite/Editツールで行う（Bashリダイレクト・sed・tee禁止）
8. revertコミットとチケットの状態を報告し、`/start-loop {チケットID}` でループを再開できることを伝える

## Never

- 人間の承認なしにrevertを実行しない
- `git reset --hard` のリモートへの `push --force` をしない
- mainブランチへの直接resetをしない
- ログセクションの既存記載を削除・上書きしない

## 使用例

```
/rollback APP-001
/rollback APP-001 a1b2c3d
```
