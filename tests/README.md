# テスト

状態検証hookとメトリクス機構の自動テスト。検証ロジックを変更した際の回帰を防ぐ。
**依存なし**（Python3標準ライブラリの `unittest` のみ。pytest不要）。

## 実行

```bash
# プロジェクトルートで
python3 -m unittest discover -s tests -v
```

## 構成

| ファイル | 対象 |
|---|---|
| `test_ticket_lib.py` | `_ticket_lib.py` の検証ルール単体（パース・schema・retry上限・遷移表） |
| `test_validator.py` | `validate_ticket_state.py`（PreToolUse）をサブプロセス起動して allow/deny を検証 |
| `test_loop_integrity.py` | `check_loop_integrity.py`（Stop）の整合性チェック |
| `test_metrics.py` | `record_metrics.py`（PostToolUse）の記録と `aggregate.py` の集計 |
| `test_guard_spec_writes.py` | `guard_spec_writes.py`（PreToolUse）の ask/allow 判定（SPEC.md書き込みゲート） |
| `_util.py` | 共有ヘルパ（hook起動・チケット生成テンプレート） |

## ルールを変更したら

`_ticket_lib.py` の定数（`VALID_STATUS` / `RETRY_CAPS` / `LEGAL_TRANSITIONS` など）や
CLAUDE.md のステータス定義を変更したら、対応するテストを更新して全件パスを確認すること。

## CIで回す場合

```bash
python3 -m unittest discover -s tests
# 失敗時は非ゼロ終了するため、そのまま CI のステップに組み込める
```
