---
id: "{{TICKET_ID}}"
title: "{{TITLE}}"
status: todo
priority: medium
type: feature
created: "{{DATE}}"
updated: "{{DATE}}"
project: "{{PROJECT_NAME}}"
tags: []
related_files: []
retry_counts:
  tester_to_implementer: 0
  reviewer_to_implementer: 0
  reviewer_to_investigator: 0
---

# {{TITLE}}

## 概要
<!-- 何を・なぜやるかを1〜3行で -->

## 受け入れ条件
<!-- 完了とみなす条件を箇条書きで。各エージェントはこのリストを基準に作業する -->
- [ ] 

## 実装メモ
<!-- 各エージェントが調査結果・設計サマリ・レビュー結果をここに追記する -->

### 調査メモ (investigator)

### 設計メモ (architect)

### レビューメモ (reviewer)

## ブロッカー
<!-- Unknowns・Open Questionsが発生した場合にここへ記載。解消後は削除する -->

## リトライカウンタ
<!-- orchestratorが差し戻しのたびに更新する。フロントマターのretry_countsと常に同期させること -->
<!-- 上限超過時はstatusをblockedに変更し、ブロッカーセクションへ記録して人間へ報告する -->
| 差し戻し種別 | 回数 | 上限 |
|---|---|---|
| tester → implementer | 0 | 3 |
| reviewer → implementer | 0 | 2 |
| reviewer → investigator | 0 | 1 |

## ログ
<!-- 各エージェントが YYYY-MM-DD HH:MM: {内容} 形式で追記する。削除しない -->

## 関連
<!-- 関連チケットID・参考URL・docs/designs/{ID}.mdへの参照など -->
