# state-machine.md — interrogate-spec スキル: 状態遷移規則

QUESTIONS.yaml 内の質問エントリの状態遷移と、遷移を駆動するワークフロー規則を定義する。
フィールドの構造と制約は question-schema.yaml を参照。

## 1. 状態と遷移の全体像

```
                > 起票 <
                   │
                   v
   ┌──────────> [open] ─────────────┐
   │            │     │              │ 調査で確定不能
   │ 検証完了    │     │ バッチ編成    │ (surrendered, T4)
   │ (T5)       │     v              │
   │            │ [presented]        │
   │            │   │    │           │
   │            │   │    │ 回答確定   │
   │   実証検証  │   │    └──> [answered] ※終端
   │   が必要    │   │                │
   │   (T4)     │   │(バッチ中断は    │
   │            v   v presentedのまま │
   └────── [deferred] <──────────────┘  永続化)

   open / presented / deferred ──(前提消滅, T6)──> [invalidated] ※終端
```

終端状態: `answered` / `invalidated`。逆遷移は禁止。
再検討が必要になった場合は新IDで再起票し、`derived_from` で旧IDに紐づける。

## 2. 遷移規則

### T1: (起票) → open
- トリガー: 初回尋問スキャン、または再トリアージでの派生質問生成。
- 必須処理: `next_id` から採番し `next_id` をインクリメント。`derived_from` を設定
  (派生時)。優先度の仮置き(likelihood × impact → rank)。
- 起票時点で investigator への調査委譲を行い、`research` を格納してから
  バッチ編成対象とする。調査未完了(`research: null`)の質問は提示しない。

### T2: open → presented
- トリガー: バッチ編成での選出(編成規則は §3)。
- 必須処理: `batches` に新規バッチエントリを追加し、選出した質問IDを記録。
  各質問の status を presented に更新。**提示前検査**(§5)を実行。

### T3: presented → answered
- トリガー: 人間の回答確定 + 終端処理の完了。
- 必須処理(この順で実行し、全完了までは answered に遷移させない):
  1. 回答内容から DECISION_LOG.md エントリを起票(D-NNN)。
  2. outcome を判定: spec_revision → SPEC.md の改訂 diff を提示し人間の承認を得て
     適用 / out_of_scope → SPEC.md の Out of Scope 節への追記 diff を提示し承認・適用。
  3. `resolution` を記入(outcome / decision_log_ref / batch_id / answered_at)。
  4. status を answered に更新。
- 禁止: 決定ログ未起票のまま answered にすること。SPEC への書き込みは毎回
  人間の diff 承認を経る(allowed-tools に含めない運用の前提)。

### T4: open / presented → deferred
- トリガー:
  - (a) open → deferred: Phase 2 で research.surrendered = true が格納された時点で
    **即座に**遷移する(バッチ編成を待たない)。
  - (b) presented → deferred: 対話中に人間・エージェントいずれかが
    「実証検証が必要」と判定。
- 必須処理: VERIFICATION_BACKLOG.md にエントリを起票(V-NNN)。`deferrals` に
  新規エントリを追加(backlog_ref / reason / verification_hint / deferred_at、
  reopened_at は null)。過去のエントリは上書きせず履歴として保持する。

### T5: deferred → open
- トリガー(いずれか):
  - (a) 人間が**検証完了**を申告(例: 「V-005 のサンドボックス検証が終わった」)。
  - (b) 人間が**検証によらない方針確定**を申告(検証不要と判断し、回答の用意が
    ある場合。例: 該当機能ごとスコープ外化する決定。対応する VERIFICATION_BACKLOG
    エントリは wont_verify に更新する)。
- 必須処理:
  1. (a) の場合: 検証結果の要約を人間から受領し、`research` を更新
     (sources に kind: empirical として検証結果を追加、confidence を再評価)。
     (b) の場合: research の更新は不要(回答は T3 の決定ログに記録される)。
  2. **`research.surrendered` を false に更新する**(これを怠ると再バッチ編成で
     即座に T4(a) が発火し、deferred へ送り返される無限ループになる)。
  3. `deferrals` の当該エントリ(reopened_at = null のもの)に reopened_at を記入。
     エントリは削除せず履歴として保持する。
  4. status を open に戻す。
  5. (b) の場合: 当該質問を single 相当で即時提示し(T2)、回答を受けて T3 で閉じる
     (deferred → answered の直接遷移は設けない。回答は必ず presented を経由し、
     提示前検査とバッチ記録を通す)。
- 例外: (a) で検証結果をもってなお確定できない場合は open に戻さない。当該 deferrals
  エントリの reason / verification_hint を更新し、deferred のまま維持する。

### T6: open / presented / deferred → invalidated
- トリガー: 再トリアージ(§4)で、他質問の回答により前提が消滅したと判定。
- 必須処理: `invalidation` を記入(invalidated_by / reason / invalidated_at)。
- **依存連鎖の孤立防止(必須)**: 無効化する質問IDを `depends_on` に持つ質問を
  必ず洗い出し、次のいずれかを無効化候補と**同時に**人間へ提示する:
  - (a) 連鎖無効化(依存元の論点自体が消滅した場合)
  - (b) depends_on からの当該IDの除去(依存関係のみ消滅し、論点は残る場合)
  孤立依存(answered に到達し得ないIDを depends_on に残した状態)を放置したまま
  無効化を確定してはならない。放置すると依存元がバッチ編成から永久に除外される。
- 注意: invalidated は自動確定しない。再トリアージ結果の提示時に無効化候補として
  人間に示し、承認を得てから遷移させる(誤爆すると論点が静かに消えるため)。

### T7: presented → presented(セッション中断・再開)
- バッチ中断時、presented はファイル上そのまま残る。次回起動時に presented が
  存在する場合、新規バッチを編成せず「バッチ B-NNN の未回答 k 件から再開しますか」
  を最初に確認する。

## 3. バッチ編成規則(T2 の詳細)

1. 対象母集団: status = open かつ research ≠ null。
2. 除外: `depends_on` に answered 以外の質問IDを含むもの(依存未解決)。
3. 順序: rank(human_override 優先)の high → medium → low。同 rank 内は
   impact > likelihood > ID昇順。
4. 件数: モード引数に従う。
   - 空(デフォルト): 上位 5 件。batches エントリの mode は "batch"。
   - `all`: 全件を 5 件ずつの連続バッチとして実行し、各バッチ完了ごとに
     再トリアージ(§4)を挟む。一括提示は禁止(判断疲労対策)。
     生成される各バッチエントリの mode はすべて "all" とする(起動モードの記録)。
   - `Q-NNN`: 指定 1 件のみ(mode は "single")。対象の status に応じて:
     - open: depends_on 未解決なら警告し、人間が強行を選べば提示する。
     - presented: 当該質問の回答受付から再開する。
     - deferred: 提示せず、T5 フロー(検証完了の確認)を提案する。
     - answered / invalidated: その旨と resolution / invalidation の内容を報告して
       終了する。再検討したい場合は新IDでの再起票(derived_from 紐づけ)を案内する。

## 4. 再トリアージ規則(バッチ完了ごとに必須)

バッチ内の全質問が answered / deferred に達したら、次を実行してから次バッチへ進む:

1. **波及スキャン**: 今バッチで確定した各決定について、残質問(open / deferred)の
   `impact_scope` / `spec_refs` と突き合わせ、(a) 前提が消滅した質問 → 無効化候補、
   (b) 前提が変わった質問 → 質問文・優先度の改訂候補、(c) 新たに生じた論点 →
   派生質問の起票候補、(d) `depends_on` が今バッチで解決した質問 → 確定した前提を
   渡して investigator へ research の再委譲(条件付き recommendation を確定前提の
   ものに更新する)、を列挙する。
2. **人間への提示**: 候補一覧(無効化・改訂・新規)を提示し、承認されたものだけ反映。
   新規質問は T1 に従い起票する(derived_from 必須)。
3. **優先度再計算**: human_override が設定されていない質問のみ rank を再評価。
4. `meta.last_triaged_at` を更新。

## 5. 提示前検査(T2 内で毎回実行)

バッチ提示の直前に、選出した各質問について自己検査する。違反があれば修正してから提示:

- [ ] authority = human_only の質問に recommendation が設定されていない
- [ ] authority = human_only の質問に options が 2 件以上ある
- [ ] research.conflicts ≠ null の質問の confidence が low になっている
- [ ] research.surrendered = true の質問が混入していない(T4 へ回す)
- [ ] 全質問の priority.rank が triage-rules.md の導出規則(likelihood × impact
      マトリクス + contradiction 例外)と整合している(human_override 設定時を除く)

## 6. 起動時ガード(全モード共通の前処理)

1. **SPEC 改訂検知**: `meta.spec_hash` と現 SPEC のハッシュを照合。不一致なら
   「SPEC が外部で改訂されています」と警告し、(a) 差分を確認して影響質問を
   再スキャン → spec_hash 更新、(b) 中止、の選択を人間に委ねる。勝手に続行しない。
2. **presented 残留チェック**: T7 に従い、中断バッチの再開を最優先で確認する。
3. **deferred 棚卸し**: VERIFICATION_BACKLOG.md 起票済みの deferred が n 件ある旨を
   一行で通知する(対応は促すだけで、このセッションの本流は妨げない)。

## 7. 不変条件(全遷移で常に保つ)

- ID は単調増加・欠番保持。エントリの物理削除は行わない。
- answered には decision_log_ref が、deferred には有効な deferrals エントリ
  (reopened_at = null、backlog_ref 付き)がちょうど 1 件、invalidated には
  invalidated_by が必ず存在する(孤児終端の禁止)。
- deferred 以外の status で reopened_at = null の deferrals エントリが存在しては
  ならない(T5 の記入漏れ検知に使う)。
- QUESTIONS.yaml への書き込みは各遷移の完了時点で即座に行う(コンテキスト内の
  記憶を状態のマスタとしない)。
- 1 遷移 = 1 保存。複数質問の状態をまとめて更新する場合も、途中中断で
  ファイルが矛盾状態にならない順序(ログ起票 → 参照記入 → status 更新)を守る。
