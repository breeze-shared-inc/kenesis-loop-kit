# 設計書（チケット単位）

設計書はチケットごとに `docs/designs/{ID}.md` として分割管理する。
単一の `DESIGN.md` に追記する方式は、チケットが増えるとファイルが肥大化するため廃止した。

## 運用ルール

- **architect** が `_TEMPLATE.md` をコピーして `docs/designs/{ID}.md` を作成する（例: `docs/designs/APP-001.md`）
- 1チケット = 1設計ファイル。`{ID}` はチケットIDと一致させ、このファイルが**常に現行**
- 設計を作り直す場合は**同じファイルを上書き**し、チケットのログに「設計を改訂 - 理由」を1行残す
- **過去の設計はGitヒストリで参照する**（`git log -p docs/designs/{ID}.md`）。設計ファイルにライフサイクル状態（draft/approved等）は持たせない
- **implementer / tester / reviewer** はチケットの `related_files` に記載された `docs/designs/{ID}.md` を参照する

> 設計の進行状況（作業中／完了）はチケットのステータス（`investigation_done` → architect作業中、`design_done` → 設計完了）が唯一の真実。設計ファイル側に重複して持たない。

## ファイル

| ファイル | 用途 |
|---|---|
| `_TEMPLATE.md` | architectが新規設計を起こす際のテンプレート |
| `{ID}.md` | チケット {ID} の設計書 |
