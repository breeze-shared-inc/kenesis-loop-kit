# /improvement-loop

.claude/agents/orchestrator.md を読み込み、orchestratorとして改善ループを起動してください。

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

## 判断基準（人間向け）

reviewerの承認後、人間が成果物を確認して次のアクションを判断する。orchestratorは人間の判断を待ち、指示を受けてから次のループへ進む。

- **実装ループ継続** — 設計の方向性は正しく、次のチケットへ進む（このコマンドは不要。`/start-loop` で次のチケットへ）
- **改善ループ** — 成果物を見て設計方針の見直しが必要と判断した場合、investigatorまたはarchitectへ戻す（このコマンドを実行）

人間の判断例文:
- 「実装ループを継続して、次のチケットに進んでください」
- 「設計を見直したいので、investigatorからやり直してください」 → `/improvement-loop {ID} investigator`
- 「architectの設計方針を修正して、再実装してください」 → `/improvement-loop {ID} architect`

## 使用例

```
/improvement-loop APP-001
/improvement-loop APP-001 investigator
/improvement-loop APP-001 architect
```
