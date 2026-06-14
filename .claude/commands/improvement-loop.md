# /improvement-loop

agents/orchestrator.md を読み込み、orchestratorとして改善ループを起動してください。

## 手順

1. $ARGUMENTS からチケットIDと差し戻し先を読み取る
   - 形式: `{チケットID} {差し戻し先}` （例: APP-001 architect）
   - 差し戻し先の省略時は architect をデフォルトとする
2. 指定されたチケットを tickets/active/ または tickets/done/ から読み込む
3. tickets/done/ にある場合は tickets/active/ へ移動する
4. 差し戻し先に応じてstatusを更新する
   - investigator → status を todo に変更
   - architect → status を investigation_done に変更
5. チケットのログセクションに「改善ループ開始 - YYYY-MM-DD HH:MM: {差し戻し先}へ戻す」を追記する
6. 対象エージェントの定義ファイルを読み込み、作業を開始する

## 使用例

```
/improvement-loop APP-001
/improvement-loop APP-001 investigator
/improvement-loop APP-001 architect
```
