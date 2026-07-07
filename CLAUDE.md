# CLAUDE.md - Kenesis Loop Kit

このファイルはClaude Codeへの運用ルールを定義します。
作業開始前に必ずこのファイルを読み込んでください。

---

## スラッシュコマンド一覧

| コマンド | 用途 | 引数 |
|---|---|---|
| `/spec-interview` | 対話形式で要件定義書(docs/SPEC.md)を作成・改訂する | モード（最短/フル・省略可） |
| `/interrogate-spec` | SPECを敵対的にレビューし、質問リストの対話解決でSPEC改訂・決定ログ化する | spec-path モード（省略可） |
| `/wireframe-gen` | SPECの画面一覧からワイヤーフレーム(docs/wireframes/)を生成する | SCR-ID/モード（省略可） |
| `/start-loop` | ループを開始・再開する | チケットID（省略可） |
| `/batch-loop` | 複数チケットを承認ゲートで止めずに連続ループさせる | チケットID列（2件以上・実行順） |
| `/new-ticket` | チケットを新規作成する | タイトル（必須） |
| `/improvement-loop` | 改善ループを起動する | チケットID 差し戻し先（省略可） |
| `/rollback` | 承認後に問題が発覚したチケットをロールバックする | チケットID（必須） コミットハッシュ（省略可） |
| `/triage` | 長期放置blockedチケットをトリアージする | 日数/チケットID（省略可・省略時14日） |
| `/archive` | 完了チケットを個人vaultへ移動する | アーカイブ先パス（省略可） |
| `/metrics` | ループの観測メトリクスを表示する | チケットID/プロジェクト名（省略可・フィルタ） |

- `/spec-interview`・`/interrogate-spec`・`/wireframe-gen` は開発ループの**前工程**（SPEC・ワイヤーフレームの整備）を担うスキル。定義は `.claude/skills/` を参照。
- ループ本体のコマンド（`/start-loop` 以降）の詳細は `.claude/commands/` を参照してください。

---

## エージェント構成

| エージェント   | 役割                                 | 定義ファイル                      |
|----------------|--------------------------------------|-----------------------------------|
| orchestrator   | ループ管理・エージェント委譲         | .claude/agents/orchestrator.md    |
| investigator   | 既存コード調査・影響範囲特定         | .claude/agents/investigator.md    |
| architect      | 設計・docs/designs/{ID}.md作成・受け入れ基準定義| .claude/agents/architect.md  |
| implementer    | 承認済み設計に基づくコード実装       | .claude/agents/implementer.md     |
| tester         | テスト実行・カバレッジ確認・品質検証 | .claude/agents/tester.md          |
| reviewer       | コードレビュー・整合性チェック       | .claude/agents/reviewer.md        |

各エージェントを呼び出す際は、対応する定義ファイルを必ず参照してください。

---

## 開発ループフロー

```
[SPEC作成 /spec-interview] → [SPEC尋問 /interrogate-spec] → [ワイヤーフレーム /wireframe-gen] → [チケット作成]
                                                                                                       ↓
                                                                                                 orchestrator
                                                                                                       ↓
investigator → architect → implementer → tester → reviewer
                                 ↑                     |
                                 └────── 実装ループ ────┘
                                        (差し戻し・修正)
                                               ↓
                                       [成果物を人間が確認]
                                        ↙              ↘
                               実装ループ継続          改善ループ
                               (新チケット作成)     investigator or
                                                    architectへ戻る
```

### 実装ループ
エージェントが自律的に回すループ。人間は介在しない。

- testerからの差し戻し → implementerへ（テスト失敗・カバレッジ不足）
- reviewerからの差し戻し（実装起因）→ implementerへ
- reviewerからの差し戻し（設計起因）→ investigatorへ（再調査）

### 改善ループ
reviewerが承認し、人間が成果物を確認した後に判断する。

- 実装ループ継続 — 設計の方向性は正しく、次のチケットへ進む
- 改善ループ — 成果物を見て設計方針の見直しが必要と判断した場合、investigatorまたはarchitectへ戻す

---

## ドキュメント管理ルール

| ファイル | 作成者 | 用途 |
|---|---|---|
| `docs/SPEC.md` | 人間（`/spec-interview` で対話生成し人間が承認） | 要件定義・仕様。investigatorとarchitectが参照する |
| `docs/wireframes/*.html` | `/wireframe-gen`（人間が確認） | 画面のレイアウト・見た目の正。SPEC §6と対をなす |
| `docs/spec-qa/<spec名>/` | `/interrogate-spec`（人間が回答・承認） | SPEC尋問の状態ファイル（QUESTIONS.yaml・DECISION_LOG.md・VERIFICATION_BACKLOG.md・ESCAPES.md）。SPEC.mdの改訂は人間のdiff承認を経る |
| `.claude/skills/spec-interview/templates/SPEC_TEMPLATE.md` | - | SPEC.mdのテンプレート（`/spec-interview` がコピー元に使う） |
| `docs/designs/{ID}.md` | architect | チケット単位の設計書。architectが生成し、implementerが参照する |
| `docs/designs/_TEMPLATE.md` | - | 設計書テンプレート（architectがコピー元に使う） |
| `docs/obsidian-setup.md` | - | Obsidianの初期設定ガイド |

- `docs/SPEC.md` が存在しない・不完全な場合、investigatorは作業を開始せず `/spec-interview` の実行（人間による要件定義）を促すこと
- 設計書はチケットごとに `docs/designs/{ID}.md` として分割管理する（単一 `DESIGN.md` への追記方式は廃止）。architectは `docs/designs/_TEMPLATE.md` をコピーして作成する
- 設計を作り直す場合は同じ `docs/designs/{ID}.md` を上書きし、チケットのログに改訂理由を残す。過去の設計はGitヒストリで追える（設計ファイルにライフサイクル状態は持たせない）。詳細は `docs/designs/README.md` を参照

---

## Git運用規約

### ブランチ戦略（git-flow）

```
main        ← リリース済みの本番コード
develop     ← 開発統合ブランチ（通常の作業ブランチ）
  │
  ├── feature/APP-001-ログイン機能    ← 機能開発（developから派生）
  ├── fix/APP-002-セッション切れ対応   ← バグ修正（developから派生）
  └── release/1.1.0                  ← リリース準備（developから派生）

hotfix/APP-003-緊急パッチ            ← 緊急修正（mainから派生・main+developにマージ）
```

**ブランチ命名規則:**
```
feature/{チケットID}-{タイトルのkebab-case}
fix/{チケットID}-{タイトルのkebab-case}
hotfix/{チケットID}-{タイトルのkebab-case}
release/{バージョン番号}
```

- implementerはdevelopから`feature/`または`fix/`ブランチを作成して作業する
- testerは追加・修正したテストをimplementerの作業ブランチ上で `[{チケットID}] テスト追加: {概要}` としてコミットする（**Quality Gate fail時も含む**。失敗状態を外部化し、テスト改変をreviewerのdiffで検出可能にするため。ステージ対象はテストファイルのみ）
- `git push`は人間が行う。エージェントはブランチ作成・コミットまでを担当する

### コミットメッセージ規約

```
[{チケットID}] {変更内容の要約}

例:
[APP-001] ログイン機能の実装
[APP-002] バグ修正: セッション切れの対応
[APP-001][WIP] ログインフォームのUI実装途中
```

- implementerはコミット前にチケットIDが含まれているか確認する
- 1コミット = 1チケットの作業を原則とする
- WIPコミットは `[APP-001][WIP] {内容}` の形式を使う

---

## チケット管理ルール

### ステータス定義

| status               | 意味                                                          | 遷移元              | 遷移先              |
|----------------------|---------------------------------------------------------------|---------------------|---------------------|
| todo                 | 未着手                                                        | -                   | investigation_done  |
| investigation_done   | investigator完了                                              | todo                | design_done         |
| design_done          | architect完了                                                 | investigation_done  | implementation_done |
| implementation_done  | implementer完了                                               | design_done         | test_passed         |
| test_passed          | tester Quality Gate通過                                       | implementation_done | done                |
| done                 | reviewer承認・完了。人間が成果物を確認し次のループを判断する  | test_passed         | -                   |
| blocked              | ブロッカー発生・人間対応待ち                                  | any                 | any                 |

上表は正常系（前進方向）の遷移を示す。差し戻し時はステータスの巻き戻しが発生する（tester fail: `implementation_done → design_done`〔test_passedは合格時のみ付与されるため〕、reviewer reject 実装起因: `test_passed → design_done`、reviewer reject 設計起因: `test_passed → todo`）。詳細は orchestrator.md の「差し戻し・完了時のステータス操作」を参照。

### チケットID採番
- 形式: `{プロジェクト略称}-{3桁連番}` 例: `APP-001`
- 採番時は `tickets/active/` と `tickets/done/` の両方を確認し、最大IDの次の番号を使う

### 新規チケット作成
1. バグは `tickets/Templates/ticket-bug.md`、それ以外は `tickets/Templates/ticket.md` をコピー
2. `tickets/active/` に `{ID}_{タイトル}.md` の形式で配置（スペースは`_`で代替）
3. フロントマターの `id` / `title` / `created` / `updated` / `project` を埋める
4. ユーザーに内容確認を取ってから作業を開始する

### 作業中の更新ルール
- チケットファイルへの書き込みはorchestratorのみが行う。各エージェントはレポートで報告し、orchestratorがチケットへ反映する
- チケット・SPEC.mdをBash経由（リダイレクト・sed・tee等）で書き換えない。hookの検証を通すため必ずWrite/Editツールを使う
- ログセクションは追記のみ。削除・上書き禁止
- `updated` はorchestratorがエージェントの完了報告を反映するたびに現在日時へ更新する
- `related_files` は変更・参照したファイルを追記する（重複不可）
- ブロッカーが発生したら `blocked` セクションに記載し、statusを `blocked` に変更する

### 完了時
1. statusを `done` に変更
2. ログに「完了 - YYYY-MM-DD HH:MM」を追記
3. `tickets/active/` から `tickets/done/` へファイルを移動

### アーカイブ
- `tickets/done/` が20件を超えたら、個人vaultの `Archives/{project}/` へ移動する
- 移動後は `tickets/done/` から削除してよい

---

## リポジトリ可視性による.gitignore運用

**プライベートリポジトリ:**
```
tickets/.obsidian/
```

**パブリックリポジトリ:**
```
tickets/active/*
tickets/done/*
!tickets/active/.gitkeep
!tickets/done/.gitkeep
tickets/.obsidian/
```

チケット本体（tickets/active/*.md・tickets/done/*.md）のみが除外対象であり、
tickets/Templates/・tickets/_index.md はどちらのプリセットでも追跡対象として
配布される。パブリックリポジトリのclone直後もこれらのファイルは存在する前提でよい。

---

## ポリシー管理の原則

CLAUDE.mdで定義したポリシーは、それを実行する責任者（エージェント/コマンド）の定義ファイルにも必ず転記する。「CLAUDE.mdに定義した」だけでは実行されない。

| ポリシー | 定義 | 実行責任者 | 転記先 |
|---|---|---|---|
| Autoモード起動時チェック | CLAUDE.md | orchestrator / start-loop | orchestrator.md Responsibilities / start-loop.md 起動時チェックリスト |
| 14日blockedトリアージ | CLAUDE.md | orchestrator / start-loop / /triage | orchestrator.md Responsibilities / start-loop.md 起動時チェックリスト / triage.md 手順 |
| in_progress上限3件 | CLAUDE.md | orchestrator | orchestrator.md Responsibilities / Constraints / start-loop.md 起動時チェックリスト |
| cancelledステータス | CLAUDE.md | orchestrator | orchestrator.md 委譲テーブル / tickets/_index.md クエリ |
| リトライ上限 | CLAUDE.md | orchestrator | orchestrator.md Responsibilities |
| チケット状態の不変条件 | CLAUDE.md（ステータス定義 / リトライ上限） | PreToolUse + Stop hook（自動強制） | .claude/hooks/validate_ticket_state.py / check_loop_integrity.py |
| SPEC.md書き込みの人間承認 | CLAUDE.md（ドキュメント管理ルール） | PreToolUse hook（自動強制） | .claude/hooks/guard_spec_writes.py |
| done/20件超のアーカイブ提案 | CLAUDE.md（アーカイブ） | orchestrator / start-loop | start-loop.md 起動時チェックリスト |
| チケット書き込みのorchestrator専任 | CLAUDE.md（作業中の更新ルール） | orchestrator / 各エージェント | orchestrator.md Responsibilities / 各agents/*.md Ticket Integration・Never |
| Git運用規約（ブランチ作成・コミット規約・機密確認） | CLAUDE.md（Git運用規約） | implementer / tester | implementer.md Git Rules / tester.md Git Rules |
| ロールバック手順 | CLAUDE.md（ロールバック手順） | /rollback | rollback.md 手順・Never |
| バッチ連続実行の事前承認 | docs/batch-loop.md | /batch-loop | batch-loop.md 手順・制約 |

新しいポリシーを追加する際は、このテーブルを更新し、転記先ファイルへの反映まで完了させること。

---

## 改善ループの判断基準

reviewerの承認後、人間が成果物を確認して次のアクションを判断します。
orchestratorは人間の判断を待ち、指示を受けてから次のループへ進みます。

人間の判断例文:
- 「実装ループを継続して、次のチケットに進んでください」
- 「設計を見直したいので、investigatorからやり直してください」
- 「architectの設計方針を修正して、再実装してください」

## 実装ループのリトライ制限

無限ループを防ぐため、差し戻し回数に上限を設ける。

| 差し戻し種別 | 上限回数 | フロントマターキー | 超過時のエスカレーション先 |
|---|---|---|---|
| tester → implementer | 3回 | tester_to_implementer | 人間へ報告・blockedに変更 |
| reviewer → implementer | 2回 | reviewer_to_implementer | 人間へ報告・blockedに変更 |
| reviewer → investigator | 1回 | reviewer_to_investigator | 人間へ報告・blockedに変更 |

**リトライ回数の保存先（状態の外部化）:**
リトライ回数はAIのコンテキストに保持せず、チケットへ外部化する。フロントマターの `retry_counts` を機械的判定の正とし、本文の「リトライカウンタ」セクションへ人間可読の形で併記する（ハイブリッド管理）。orchestratorは差し戻し委譲のたびに両方を同期更新し、判定時は必ずファイルから読み取る。

**上限超過時のorchestratorの動作:**
1. チケットのstatusを`blocked`に変更する
2. ブロッカーセクションに「リトライ上限超過 - {差し戻し種別} {N}回」を記録する
3. 人間へ以下の情報を報告してから停止する
   - 差し戻しの経緯（ログセクションを要約）
   - 最後の指摘内容（reviewerまたはtesterのレポート）
   - 推奨される次のアクション（設計見直し・要件の再確認など）

**リトライ回数の推奨値の根拠:**
testerは機械的な検証なので3回まで許容する。reviewerは設計上の問題を発見することが多く、2回超えた場合は実装ではなく設計に問題がある可能性が高いため上限を低く設定する。

---

## 状態検証hook（自動強制）

チケットの状態機械はLLMの遵守だけに依存せず、Claude Codeのhookで機械的に強制する。設定は `.claude/settings.json` に登録済み。

| hook | イベント | 対象 | 役割 |
|---|---|---|---|
| `validate_ticket_state.py` | PreToolUse（Write\|Edit） | tickets/active\|done/*.md | 書き込み前に検証し、違反を deny でブロックする |
| `check_loop_integrity.py` | Stop | tickets/active/*.md | 応答終了時に全チケットを検査し、不整合があれば継続を強制する |
| `guard_spec_writes.py` | PreToolUse（Write\|Edit） | **/SPEC.md（.claude/配下を除く） | 書き込み前に ask で人間の確認を強制する（autoモードでもSPEC改訂のdiff承認を担保） |

**強制する不変条件:**
- `status` が定義済みenumであること（ステータス定義表）
- 必須frontmatterキー（retry_counts含む）が揃っていること
- 状態遷移が正当であること（前進・差し戻し・改善ループ・ロールバックの許可集合のみ）
- `retry_counts` が整数かつ各上限以下であること（上限超過は status=blocked を要求）
- **（L2）`retry_counts` は減少不可**（単調非減少。リセットによるcap回避を禁止）
- 新規チケットの初期 status が todo であること
- （Stop）status=blocked のチケットにブロッカー記載があること
- （Stop）frontmatter `retry_counts` と本文「リトライカウンタ」表が一致していること
- **（Stop / L3）差し戻し履歴と `retry_counts` の整合** — `tickets/.metrics.jsonl` の差し戻し回数とカウンタを**カテゴリ個別**に照合する（`implementation_done→design_done` 回数 == tester_to_implementer、`test_passed→design_done` 回数 == reviewer_to_implementer、`test_passed→todo` 回数 == reviewer_to_investigator。差し戻し3種は遷移元で区別できる）。増やし忘れ・誤計上を検出。履歴が無い/不完全なら照合不能として素通り（fail-open）

**設計方針:**
- **fail-open** — hookの内部エラー（パース不能等）ではループをブロックしない。**検知した違反のみ**ブロックする
- 依存なし（Python3標準ライブラリのみ）。検証ロジックは `.claude/hooks/_ticket_lib.py` に集約
- ルールを変更する場合は、CLAUDE.mdのステータス定義・リトライ上限と `_ticket_lib.py` の定数を必ず同期させる

**注意:**
- `retry_counts` を持たない旧チケットは検証エラーになる。既存チケットにはfrontmatterへ `retry_counts` を追加すること
- hookを一時的に無効化したい場合は `.claude/settings.json` の `hooks` セクションを編集する

---

## ループの観測性（メトリクス）

ループの進行をデータとして観測できるよう、ステータス遷移をイベントログへ外部化する。

| 仕組み | 種別 | 役割 |
|---|---|---|
| `record_metrics.py` | PostToolUse hook | チケットのステータスが変化したとき `tickets/.metrics.jsonl` に1イベント追記。前回状態は `tickets/.metrics_state.json`（hook管理）で保持 |
| `aggregate.py` | 集計スクリプト | `.metrics.jsonl` からサイクルタイム・滞留時間・差し戻し率・blocked発生を算出 |
| `/metrics` | スラッシュコマンド | 上記集計を表示（チケットID/プロジェクトでフィルタ可） |

- イベントログ（`tickets/.metrics*.json*`）はhookが自動生成する。**LLMやエージェントは直接編集しない**
- これらのファイルはデフォルトで `.gitignore` 対象（環境固有のため）。チームで履歴を共有したい場合は `.gitignore` の該当行を解除する
- 記録されるのは「ステータス遷移」のみ。ログ追記やrelated_files更新など状態を変えない編集は記録しない

---

## 並行チケットのポリシー

同時に進行できるチケット数に上限を設けることで、コンテキストの分散と未完了タスクの積み上がりを防ぐ。

| 状態 | 上限数 | 備考 |
|---|---|---|
| in_progress（active全体） | 3件 | statusがinvestigation_done / design_done / implementation_done / test_passedのチケット合計。blockedは数えない（積み上がりは14日トリアージが担当） |
| 同一フェーズの並行実行 | 1件 | 例: implementerを2チケット同時に実行しない |

- orchestratorは新規チケットを開始する前にin_progress件数を確認する
- 上限に達している場合は「既存チケットを完了または blockedにしてから新規着手してよいか」を人間に確認する
- 依存関係のあるチケットは依存元が`done`になるまで着手しない

---

## 長期放置チケットのポリシー

`blocked`のまま放置されたチケットは定期的にトリアージする。

**放置の定義:**
- `blocked`ステータスで14日以上`updated`が更新されていないチケット

トリアージは `/triage` で単体実行できる（定義: `.claude/commands/triage.md`。日数しきい値・チケットID指定も可能）。/start-loop の起動時チェックリストも同じ手順を参照する。

**orchestratorの定期チェック（/start-loop実行時）:**
1. `blocked`チケットの`updated`を確認し、14日以上経過しているものを一覧表示する
2. 人間に以下のいずれかのアクションを促す

| アクション | 条件 | 手順 |
|---|---|---|
| 再開 | ブロッカーが解消された | statusを元のstatusへ戻し、ループを再開 |
| クローズ | 不要になった | statusを`cancelled`に変更し、done/へ移動 |
| 期限延長 | 引き続き対応待ち | updatedを更新してブロッカーに期限を追記 |

**ステータスに`cancelled`を追加:**

| status | 意味 |
|---|---|
| cancelled | 不要と判断してクローズ。done/へ移動して保管 |

---

## セキュリティ・機密情報の取り扱い

**チケットやドキュメントに記載してはならない情報:**
- APIキー・シークレットキー・アクセストークン
- パスワード・接続文字列
- 個人情報（氏名・メールアドレス・電話番号など）
- 社内の非公開情報（売上・顧客情報など）

**エージェントへの指示:**
- 上記の情報をチケットのいずれのセクションにも記載しない
- 設計書（docs/designs/{ID}.md）に接続先を記載する場合は環境変数名のみを記載する（例: `process.env.DATABASE_URL`）
- コードに機密情報をハードコードしない。`.env`ファイルを使用し`.gitignore`に追加する
- コミット前に`git diff`で機密情報が含まれていないことを確認する

**.gitignoreに必ず含めるべき項目:**
```gitignore
.env
.env.*
!.env.example
*.pem
*.key
secrets/
```

---

## ロールバック手順

reviewer承認後に問題が発覚した場合の対応手順。
通常のロールバックとチケット運用は `/rollback {チケットID}` で実行できる（定義: `.claude/commands/rollback.md`）。

### 通常のロールバック（推奨）

`git revert`はコミット履歴を保持するため、チームでの追跡が容易になる。

```bash
# 1. 問題のあるコミットハッシュを特定する
git log --oneline

# 2. revertコミットを作成する（コミットは自動生成される）
git revert {コミットハッシュ}

# 3. コミットメッセージにチケットIDを付与する
# 例: [APP-001][REVERT] ログイン機能の実装を取り消し
```

### 緊急ロールバック（本番障害時）

hotfixブランチをmainから作成し、修正後にmainとdevelopの両方にマージする。

```bash
git checkout main
git checkout -b hotfix/APP-XXX-{内容}
# 修正を実施
git checkout main && git merge hotfix/APP-XXX-{内容}
git checkout develop && git merge hotfix/APP-XXX-{内容}
```

### ロールバック時のチケット運用

1. ロールバック対象のチケットをdone/からactive/へ戻す
2. statusを`implementation_done`に変更する（revert実装はtesterから再開）
3. ログセクションに「YYYY-MM-DD HH:MM: ロールバック実施 - {理由}」を追記する
4. `/start-loop {チケットID}`でループを再開する

### ロールバックをNeverとすべき操作

- `git reset --hard`のリモートへの`push --force`（チーム開発では履歴が失われる）
- mainブランチへの直接`reset`（本番コードの整合性が失われる）
