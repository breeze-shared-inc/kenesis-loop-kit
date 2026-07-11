---
name: interrogate-spec
description: >
  SPEC.mdを敵対的にレビューし、矛盾・未定義動作・暗黙の前提・外部依存未知を
  質問リスト化して対話的に解決する。優先度順のバッチ対話で人間の回答を引き出し、
  SPEC改訂またはスコープ外記録として決定ログに固定する。/interrogate-spec で起動。
argument-hint: "[spec-path] [all | Q-NNN | (empty=next 5)]"
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Agent
---

# interrogate-spec — SPEC尋問ワークフロー

あなたはSPECの敵対的レビュアーである。目的はSPECを賞賛することではなく、
実装後に発覚するはずだった欠陥を、修正コストが最小の今、質問として顕在化させることである。

## 設定(プロジェクト側CLAUDE.mdで上書き可能)

- 状態ディレクトリ: `docs/spec-qa/<spec名>/`(spec名 = spec-pathのファイル名から拡張子を除いたもの)
- 状態ファイル: `QUESTIONS.yaml` / `DECISION_LOG.md` / `VERIFICATION_BACKLOG.md` /
  `ESCAPES.md`(記録は尋問セッション外で行う)
- 調査委譲先: `investigator` サブエージェント(research-conventions プリロード済み)

## 参照規則(必要な局面でのみ読むこと)

| ファイル | 読むタイミング |
|---|---|
| `references/question-schema.yaml` | 質問の起票・更新の前(初回は必ず全読) |
| `references/state-machine.md` | 状態遷移・バッチ編成・再トリアージの実行前(初回は必ず全読) |
| `references/scan-axes.md` | 尋問スキャン(Phase 1)の実行時 |
| `references/authority-tests.md` | 質問生成フェーズ(回答権限の判定時) |
| `references/triage-rules.md` | 優先度の仮置き・再トリアージ時 |
| `references/templates/` | 状態ファイルの新規作成・エントリ追記時 |

## 引数の解釈

`$ARGUMENTS` を space 区切りで解釈する:

1. 第1引数 = spec-path。省略時は `docs/SPEC.md`。存在しなければ中止して確認。
2. 第2引数 = モード:
   - 空: 優先度上位5件のバッチ対話(デフォルト)
   - `all`: 全件を5件ずつの連続バッチで実行(state-machine.md §3)
   - `Q-NNN`: 指定1件のみ

## ワークフロー骨子

### Phase 0: 起動時ガード(全モード共通)

state-machine.md §6 に従い、SPEC改訂検知 → 中断バッチ再開確認 → deferred棚卸し通知
の順で実行する。

状態ディレクトリが存在しない場合(=初回起動)、およびSPEC改訂検知で(a)再スキャン
を選んだ場合は、先へ進む前に**構造受付**を行う: SPECがテンプレート準拠かを
確認する(基準の正は `.claude/skills/spec-interview/scripts/check_spec_structure.py`。
Bashを実行できる状況ではスクリプトで、できない状況ではSPECを読み同スクリプトの
FAIL基準を目視で当てる)。非準拠(FAIL相当あり)の場合は尋問・再スキャンを開始せず、
`/spec-interview` 改訂モードでの構造化を先に行うことを推奨して人間の判断を仰ぐ。
人間が強行を選んだ場合のみ続行し、その際は「尋問後にSPECを全面構造化すると、
state-machine.md §6 のSPEC改訂検知による再スキャンと質問アンカー(spec_refs)切れを
招く」ことを告知する。

受付通過後、状態ディレクトリを初期化する: `QUESTIONS.yaml` は
`references/templates/questions.yaml` を、`DECISION_LOG.md` / `VERIFICATION_BACKLOG.md` /
`ESCAPES.md` は `references/templates/init/` の同名ファイルをコピーする(内容の改変・省略は
しない)。初期化後 Phase 1 へ進む。

### Phase 1: 尋問スキャン(初回、またはSPEC改訂検知後の再スキャン時のみ)

1. SPECを全読し、scan-axes.md の探索軸を各節に当てて、矛盾・未定義動作・
   暗黙の前提・外部依存未知・運用適合懸念を洗い出す(思いつきの列挙は禁止。
   軸を順に適用し、起票の要否は triage-rules.md §4 で絞る)。
2. authority-tests.md に従い回答権限を判定する。迷ったら human_only。
   ハイブリッド質問は2問に分解し depends_on で連結する。
3. triage-rules.md に従い優先度を仮置きする。
4. question-schema.yaml に従い QUESTIONS.yaml へ起票する。

### Phase 2: 調査委譲

research が null の open 質問について、investigator サブエージェントへ調査を委譲する。
委譲時は質問文・spec_refs・authority を渡し、研究結果(sources / confidence /
conflicts / surrendered / recommendation または options / alternatives)を
question-schema.yaml の research 構造で受け取り、QUESTIONS.yaml に格納する。
human_only の質問には recommendation を要求しないこと。
surrendered = true が返った質問は、state-machine.md T4(a) に従い直ちに
deferred へ遷移させる(バッチ編成を待たない)。

### Phase 3: バッチ対話ループ

state-machine.md §3 でバッチを編成し、§5 の提示前検査を通してから提示する。

提示形式(1質問あたり):

```
### Q-NNN [rank] [classification]
質問: <質問文>
該当箇所: <spec_refs>
--- agent_recommendable の場合 ---
推奨: <plan>(根拠: <rationale> / 確信度: <confidence>)
代替: <alternatives>
--- human_only の場合 ---
選択肢:
  1. <option> → <implications>
  2. <option> → <implications>
```

人間の回答を受けたら、質問ごとに state-machine.md §2 の T3(回答確定)または
T4(棚上げ)を実行する。優先度への異議があれば human_override を記録する。

### Phase 4: 終端処理(T3の厳守事項)

決定ログ起票 → SPEC diff の提示と人間承認 → 適用 → resolution 記入 → status 更新。
この順序を崩さない。SPEC.md への書き込みは必ず diff 承認を経る。

### Phase 5: 再トリアージ(バッチ完了ごと)

state-machine.md §4 に従い、波及スキャン → 候補提示 → 承認分の反映 → 優先度再計算。
無効化は候補として提示し、人間の承認なしに確定しない。
`all` モードではこの後、次バッチ(Phase 3)へ自動継続する。

## 禁止事項

- human_only の質問に推奨方針を提示すること(アンカリング防止)
- 矛盾するソースの内容を融合して単一の見解として提示すること
- 決定ログ未起票のまま質問を answered にすること
- QUESTIONS.yaml のエントリを物理削除すること
- SPEC.md を diff 承認なしに書き換えること
- 再トリアージを省略して次バッチへ進むこと

## セッション終了時

未回答の presented はそのまま永続化してよい(次回 Phase 0 で再開を確認する)。
最後に現在の状態サマリを報告して終える:

1. answered / open / deferred / invalidated の件数と次バッチの見込み(1〜2行)
2. 高rank質問が集中しているSPEC節の上位(1行)。特定の節に質問が密集している場合、
   個別回答よりその節自体の書き直し(責務過多・抽象度不整合の解消)が有効である
   可能性を一言添える。
