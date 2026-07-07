# escape-entry.md — ESCAPES.md エントリ雛形

ESCAPES.md は「尋問をすり抜けて実装・テスト・運用段階で発覚した SPEC 起因の欠陥」
の台帳である(欠陥すり抜け分析)。目的は犯人探しではなく、interrogate-spec の
参照規則(scan-axes / triage-rules / authority-tests / research-conventions)の
どこに穴があるかを特定し、スキル自体の改善を駆動することにある。

記録のタイミングは尋問セッション外(実装・レビュー・テスト・運用中)でよい。
SPEC 起因でない欠陥(純粋な実装バグ)は対象外。

---

## エントリ形式

````markdown
## E-NNN: <すり抜けた欠陥の一行要約>

```yaml
id: E-NNN
detected_at: <ISO8601>
detected_phase: implementation   # implementation | review | test | production
spec_sections:
  - "<関連する SPEC の節>"
escape_class: not_generated      # 下記3分類
related_ids: []                  # 関連する Q-NNN / D-NNN(あれば)
suspected_hole: "<scan-axes.md 軸N の欠落 / triage-rules の判定 / 調査の確信度 등>"
status: recorded                 # recorded | rule_revised | dismissed
```

- **何が起きたか**: <発覚した欠陥と、本来 SPEC に書かれているべきだったこと>
- **なぜすり抜けたか**: <escape_class の判断根拠>
- **是正のヒント**: <どの参照規則をどう変えれば同型を捕捉できたか。
  即改訂はしない(下記のタンパリング防止規律)>
````

## escape_class の3分類

| 分類 | 意味 | 疑うべき穴 |
|---|---|---|
| `not_generated` | 該当する質問がそもそも生成されなかった | scan-axes.md の軸の欠落・不足 |
| `buried_by_triage` | 質問は生成されたが低優先度に沈み、未回答のまま実装に入った | triage-rules.md の尤度/影響度の判定基準 |
| `wrong_answer` | 質問は回答されたが、その回答が誤っていた | research の確信度運用、アンカリング(無修正承認)、authority の誤分類 |

## タンパリング防止規律(重要)

- すり抜け1件を理由に参照規則を即改訂**しない**。1件は偶然原因として
  記録(status: recorded)に留める。
- **同型のすり抜けが複数回(目安3件)観測された時点**で異常原因とみなし、
  該当する参照規則の改訂を行う。改訂したら該当エントリの status を
  rule_revised に更新し、改訂内容を是正のヒント欄に追記する。
- この規律は、単発のノイズへの過剰反応が規則を場当たり的に肥大化させ、
  かえって尋問品質のばらつきを増やすことを防ぐためにある(シューハートの
  偶然原因/異常原因の区別)。
