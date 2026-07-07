# チケットダッシュボード

## 🔴 ブロッカーあり

```dataview
TABLE title, priority, updated
FROM "active"
WHERE status = "blocked"
SORT priority DESC
```

## 🟡 進行中（active）

```dataview
TABLE status, priority, updated
FROM "active"
WHERE status != "blocked" AND status != "todo" AND status != "cancelled"
SORT priority DESC, updated ASC
```

## ⚪ 未着手（todo）

```dataview
TABLE priority, created
FROM "active"
WHERE status = "todo"
SORT priority DESC, created ASC
```

## ✅ 完了（直近10件）

```dataview
TABLE updated
FROM "done"
WHERE status != "cancelled"
SORT updated DESC
LIMIT 10
```

## 🚫 キャンセル済み

```dataview
TABLE title, updated
FROM "done"
WHERE status = "cancelled"
SORT updated DESC
```
