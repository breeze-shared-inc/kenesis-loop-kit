# interrogate-spec — SPEC尋問スキル

SPEC.mdを敵対的にレビューし、矛盾・未定義動作・暗黙の前提・外部依存未知を
質問リスト化して対話的に解決するClaude Codeスキル。回答は決定ログに固定され、
SPEC改訂またはスコープ外記録として必ず着地する。

## 構成

```
.claude/
├── skills/
│   ├── interrogate-spec/
│   │   ├── SKILL.md                 # 本体(手順の骨子)
│   │   └── references/
│   │       ├── question-schema.yaml # 質問スキーマ定義
│   │       ├── state-machine.md     # 状態遷移・バッチ編成・再トリアージ規則
│   │       ├── scan-axes.md         # 尋問スキャンの探索軸(Phase 1)
│   │       ├── authority-tests.md   # 回答権限の判定手順
│   │       ├── triage-rules.md      # 優先度分類規則
│   │       └── templates/           # エントリ雛形(*-entry.md)と状態ファイル雛形
│   │           └── init/            # 状態ファイルの初期状態(Phase 0 でコピー)
│   └── research-conventions/
│       └── SKILL.md                 # 調査規約(investigatorへプリロード)
└── agents/
    └── investigator.md              # 調査サブエージェント(要拡張、下記参照)

docs/spec-qa/<spec名>/               # 状態ファイル(スキル起動時に自動初期化)
├── QUESTIONS.yaml                   # 質問リスト(ライブ状態)
├── DECISION_LOG.md                  # 決定ログ(不変ファクトレコード)
├── VERIFICATION_BACKLOG.md          # サンドボックス検証等の棚上げタスク
└── ESCAPES.md                       # すり抜け分析台帳(尋問セッション外で記録。
                                     #   雛形: templates/escape-entry.md)
```

## セットアップ

### 1. SPEC書き込みゲートと状態ファイル権限(必須)

「SPEC.md への書き込みは毎回人間の diff 承認を経る」という安全弁は、2層で担保される:

1. **手順層**: SKILL.md Phase 4 / state-machine.md T3 が
   「diff 提示 → 人間の承認 → 適用」の順序を義務づける(LLMの手順遵守に依存)。
2. **強制層**: PreToolUse hook `.claude/hooks/guard_spec_writes.py` が SPEC.md
   (basename一致)への Write / Edit を検知し、`permissionDecision: ask` で
   人間への確認を強制する(`.claude/settings.json` に登録済み)。
   このキットはループ運用のため autoモード(自動承認)を推奨構成としており、
   権限プロンプトに頼れないため、hook による強制が安全弁の実体である。
   ただし `--dangerously-skip-permissions` 起動だけは ask が貫通する点に注意。

**注意**: SKILL.md の `allowed-tools` は「事前承認リスト」であり、ツールの利用を
制限するものではない(Write / Edit を載せていないのは事前承認しないという意味で、
書き込み自体は権限設定に従って可能)。したがって permissions.allow に Edit を
追加しても hook のゲートは消えないが、hook を settings.json から外すと
安全弁は手順層(LLMの遵守)だけになる。

状態ファイル(docs/spec-qa/ 配下)への保存は頻繁に発生するため、権限プロンプトが
出るモードで運用する場合に備え、`.claude/settings.json` のパススコープ許可で
静かに保存できるようにしてある(登録済み):

```json
{
  "permissions": {
    "allow": [
      "Edit(docs/spec-qa/**)",
      "Write(docs/spec-qa/**)"
    ]
  }
}
```

この2つを合わせて「状態ファイルは静かに保存、SPEC.md だけ毎回 diff 承認」が
権限モードに依存せず実現される。

### 2. investigator サブエージェントの拡張(必須)

`.claude/agents/investigator.md` の frontmatter に調査規約スキルをプリロードする:

```yaml
skills:
  - research-conventions
```

これにより、根拠・確信度の必須出力、矛盾ソースの融合禁止、
「調査では確定不能」の降参の出口が investigator に注入される。

### 3. 状態ディレクトリ

手動作成は不要。初回起動時に `docs/spec-qa/<spec名>/` が自動初期化される
(QUESTIONS.yaml は `references/templates/questions.yaml`、他3ファイルは `references/templates/init/` の
同名ファイルのコピー)。状態ファイルは git 管理に含めること(尋問の履歴・決定ログは
SPEC と同じライフサイクルでレビュー対象とする)。

## 使い方

```
/interrogate-spec                          # docs/SPEC.md、優先度上位5件のバッチ対話
/interrogate-spec docs/expense/SPEC.md     # 対象SPECを指定
/interrogate-spec docs/SPEC.md all         # 全件を5件ずつの連続バッチで実行
/interrogate-spec docs/SPEC.md Q-017       # 指定質問のみ
```

典型的なセッションの流れ:

1. 起動時ガード(SPEC改訂検知 → 中断バッチ再開確認 → 棚上げ件数の通知)
2. 質問の提示(推奨+代替、または選択肢+含意)
3. 回答 → 決定ログ起票 → SPEC diff の承認 → 反映
4. バッチ完了ごとに再トリアージ(無効化・改訂・派生質問は承認制)

## 設計上の前提(変更する場合は影響を確認すること)

- 質問IDは欠番保持・物理削除禁止。消えた論点は必ず追跡可能にする。
- `human_only` の質問には推奨方針を提示しない(アンカリング防止)。
- 終端処理の順序は「決定ログ → SPEC反映 → resolution → status」で固定
  (中断時に安全側の不整合に倒すため)。
- テストケース化は本スキルの責務外。DECISION_LOG.md を入力とする
  test-designer スキル(別途)が担う。

## 運用指標(推奨)

**無修正承認率**: 数バッチ運用後に「推奨方針の無修正承認率」を確認すること。
100% に近い場合、エージェントが優秀か、人間がレビューせず追認しているかの
いずれかであり、後者ならこの仕組みは堅牢性を生んでいない。

**すり抜け分析(escape analysis)**: 実装・テスト・運用段階で SPEC 起因の手戻りが
発覚したら、ESCAPES.md に記録する(雛形: templates/escape-entry.md)。
「質問が生成されなかった / 低優先度に沈んだ / 回答が誤っていた」の3分類が、
それぞれ scan-axes / triage-rules / 調査・アンカリング の穴を指す。
これが本スキル自体の継続的改善の主要な入力である。

**タンパリング防止規律**: すり抜け1件を理由に参照規則を即改訂しないこと。
1件は偶然原因として記録に留め、**同型のすり抜けが複数回(目安3件)観測されて
から**規則を改訂する。単発ノイズへの過剰反応は規則を場当たり的に肥大化させ、
かえって尋問品質のばらつきを増やす。
