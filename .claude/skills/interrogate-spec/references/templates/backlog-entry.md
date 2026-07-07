# backlog-entry.md — VERIFICATION_BACKLOG.md エントリ雛形

VERIFICATION_BACKLOG.md は「対話では確定できず、実証検証を要する問い」の台帳である。
尋問セッションの本流からは切り離されており、検証の実施は人間(または別ワークフロー)
が任意のタイミングで行う。検証完了の申告により T5(deferred → open)が駆動される。

---

## エントリ形式

````markdown
## V-NNN: <検証すべきことの一行要約>

```yaml
id: V-NNN
question_id: Q-NNN          # 対応する質問(deferrals.backlog_ref と相互参照)
status: pending             # pending | done | wont_verify
created_at: <ISO8601>
verified_at: null           # done になった時点で記入
```

- **確定できない理由**: <なぜ調査・対話では確定できないか(deferrals.reason の転記)>
- **検証方法**: <何をどう検証すれば確定するか。具体的な手順・対象を書く。
  例: freee サンドボックスで勤怠タグ付き打刻を作成し、
  GET /api/v1/employees/{id}/work_records のレスポンスにタグがどの粒度で
  含まれるかを確認する>
- **検証結果**: <done 時に記入。確認された事実を記述。この内容が T5(a) で
  research.sources に kind: empirical として追加される>
````

## 記入規則

- `検証方法` は「次に freee サンドボックスを触る人がこのエントリだけを読んで
  作業に着手できる」粒度で書く。質問の背景を知らなくても実行可能にする。
- 同一の検証作業で複数の質問が確定する場合(例: 1 回の API 呼び出しで
  Q-003 と Q-011 の両方が解ける)は、エントリを 1 つにまとめず質問ごとに起票し、
  `検証方法` に「V-NNN と同一の検証で確認可能」と相互参照を書く
  (T5 が質問単位で駆動されるため、台帳も質問単位を保つ)。
- `wont_verify` は「検証しないと決めた」場合に使う(例: 該当機能ごと
  スコープ外化した)。その場合、対応する質問は次のいずれかで閉じ、
  宙吊りの deferred を残さない:
  - 前提自体が消滅した場合 → T6(invalidated)
  - 検証によらず方針が確定した場合 → **T5(b)**(検証によらない方針確定の申告)で
    open に戻し、即時提示(single 相当)→ T3 で回答確定(通常は out_of_scope)
