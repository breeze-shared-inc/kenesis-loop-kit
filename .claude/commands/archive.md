# /archive

tickets/done/ の完了チケットを個人vaultへアーカイブしてください。

## 手順

1. tickets/done/ のチケット一覧を表示し、件数を確認する
2. アーカイブ先のパスをユーザーに確認する
   - $ARGUMENTS にパスが指定されている場合はそれを使用する
   - 指定がない場合は「アーカイブ先のパスを入力してください（例: ~/my-vault/Archives/project-a/）」と尋ねる
3. ユーザーの確認を得てから以下を実行する
   - tickets/done/ の全チケットファイルを指定パスへ移動する（`.gitkeep` は移動対象から除外する）
   - tickets/done/ に `.gitkeep` 以外が残っていないことを確認する
4. 移動したチケットの一覧を表示して完了を報告する

## 使用例

```
/archive
/archive ~/my-vault/Archives/project-a/
```
