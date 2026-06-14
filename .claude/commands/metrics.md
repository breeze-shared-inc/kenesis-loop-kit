# /metrics

ループの観測メトリクスを表示する。`tickets/.metrics.jsonl`（record_metrics.py が記録したイベントログ）を集計する。

## 手順

1. プロジェクトルートで以下を実行する
   ```bash
   python3 .claude/metrics/aggregate.py $ARGUMENTS
   ```
   - `$ARGUMENTS` にチケットID/プロジェクト名の一部を渡すと、その部分一致でフィルタする（例: `/metrics APP-001`）
2. スクリプトの出力をそのまま提示する（数値を勝手に加工・推測しない）
3. ログが存在しない旨が出力された場合は、「ループをまだ回していないためデータが無い」ことを伝える

## 表示される内容

- サイクルタイム（created → done の所要時間）と平均
- フェーズ別の平均滞留時間（どのステータスで詰まるか）
- 差し戻し（rollback）の総数・種別・チケット別
- blocked の発生履歴
- 現在進行中チケットと経過時間

## 使用例

```
/metrics
/metrics APP-001
/metrics demo-project
```
