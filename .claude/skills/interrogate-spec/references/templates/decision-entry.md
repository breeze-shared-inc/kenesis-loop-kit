# decision-entry.md — DECISION_LOG.md エントリ雛形

DECISION_LOG.md は不変ファクトレコードである。追記のみ許可、既存エントリの
編集・削除は禁止(訂正が必要な場合は新しい決定エントリで上書き宣言する)。

このエントリ構造は **test-designer スキルへの入力契約**を兼ねる。
`machine` ブロック(YAML)は test-designer が機械的にパースする部分であり、
フィールドの削除・改名はスキル間契約の破壊にあたる(追加は可)。

---

## エントリ形式

各エントリは以下の形式で DECISION_LOG.md 末尾に追記する:

````markdown
## D-NNN: <決定の一行要約>

```yaml
# --- machine block: test-designer 入力契約(削除・改名禁止) ---
id: D-NNN
question_id: Q-NNN            # 起点となった質問
outcome: spec_revision        # spec_revision | out_of_scope
decided_at: <ISO8601>
batch_id: B-NNN
spec_target_sections:         # SPEC反映先の節(out_of_scope の場合は Out of Scope 節)
  - "<節番号または見出し>"
decision: >                   # 確定した仕様の記述(規範文。〜する/〜しない で書く)
  <この決定により SPEC が宣言する振る舞い・規則を、単独で読んで意味が
   通る完結した文で記述する。「Q-NNN の通り」のような参照だけの記述は禁止>
test_relevance: true          # true = テストケース化が必要(test-designer の抽出対象)
test_notes: >                 # test_relevance: true の場合のみ。null 可
  <観測可能な振る舞いとして何を検証すべきかのヒント。
   例: 変更日を境に前後の定期区間で控除額が切り替わることを、
   境界日当日の申請で確認する>
superseded_by: null           # 後続の決定で上書きされた場合に D-NNN を記入
# --------------------------------------------------------------
```

### 経緯

- **回答者の判断**: <人間の回答の要約。選択肢のどれを選び、何を理由としたか>
- **採用しなかった案**: <推奨/代替/選択肢のうち見送ったものと、その理由(簡潔に)>
- **参照**: <deferrals 経由の場合は V-NNN、依存元がある場合は関連 Q-NNN / D-NNN>
````

## 記入規則

- `decision` は SPEC 本文に転記できる品質の規範文で書く。経緯・理由は
  `### 経緯` 側に書き、machine block に混ぜない。
- `test_relevance` の判定基準: この決定は**観測可能な振る舞い**を定めたか?
  - true の例: 計算規則、状態遷移、バリデーション、エラー時の挙動
  - false の例: 用語の定義の統一、ドキュメント構成の変更、純粋なスコープ外宣言
  - out_of_scope でも true になりうる(例: 「定期区間控除は行わない」→
    控除されないことを確認するテストは有効)
- 訂正時は新エントリを起票し、旧エントリの `superseded_by` のみ更新する
  (machine block で唯一、後から変更してよいフィールド)。
- 1 決定 = 1 エントリ。1 つの質問への回答が複数の独立した決定を含む場合は
  エントリを分け、同じ question_id を共有する。
