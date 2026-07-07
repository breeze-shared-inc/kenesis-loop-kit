# CLAUDE.md - Kenesis Loop Kit

このファイルはClaude Codeへの運用ルールを定義します。
作業開始前に必ずこのファイルを読み込んでください。

本ファイルは全体像のインデックスと、複数ファイルから参照される共通定義（ステータス定義・チケットID採番）を持ちます。個別ポリシーの詳細は「ポリシー管理の原則」の表が示す定義ファイルを正とします。

---

## スラッシュコマンド一覧

| コマンド | 用途 | 引数 |
|---|---|---|
| `/setup` | プロジェクトの初期セットアップと現在地診断（.gitignoreプリセット・略称確定・前工程への誘導） | なし |
| `/spec-interview` | 対話形式で要件定義書(docs/SPEC.md)を作成・改訂する | モード（最短/フル・省略可） |
| `/interrogate-spec` | SPECを敵対的にレビューし、質問リストの対話解決でSPEC改訂・決定ログ化する | spec-path モード（省略可） |
| `/wireframe-gen` | SPECの画面一覧からワイヤーフレーム(docs/wireframes/)を生成する | SCR-ID/モード（省略可） |
| `/plan-tickets` | SPECを基に開発をチケットへ分割し、承認を経て一括起票する | spec-path（省略可） |
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
[SPEC作成 /spec-interview] → [SPEC尋問 /interrogate-spec] → [ワイヤーフレーム /wireframe-gen] → [チケット作成 /plan-tickets]
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

- **実装ループ** — エージェントが自律的に回すループ。人間は介在しない。差し戻しの方向・ステータス巻き戻し・リトライ上限（超過時はblocked化して人間へ報告）は `.claude/agents/orchestrator.md`「Agent Delegation Rules」「リトライカウンタ管理」を正とする
- **改善ループ** — reviewer承認後、人間が成果物を確認して「実装ループ継続」か「investigator/architectへの差し戻し」を判断する。orchestratorは人間の指示を待つ。手順・判断基準・例文は `.claude/commands/improvement-loop.md` を参照

---

## ドキュメント管理ルール

| ファイル | 作成者 | 用途 |
|---|---|---|
| `docs/SPEC.md` | 人間（`/spec-interview` で対話生成し人間が承認） | 要件定義・仕様。investigatorとarchitectが参照する |
| `docs/wireframes/*.html` | `/wireframe-gen`（人間が確認） | 画面のレイアウト・見た目の正。SPEC §6と対をなす |
| `docs/spec-qa/<spec名>/` | `/interrogate-spec`（人間が回答・承認） | SPEC尋問の状態ファイル。SPEC.mdの改訂は人間のdiff承認を経る |
| `.claude/skills/spec-interview/templates/SPEC_TEMPLATE.md` | - | SPEC.mdのテンプレート（`/spec-interview` がコピー元に使う） |
| `docs/designs/{ID}.md` | architect | チケット単位の設計書。architectが生成し、implementerが参照する |
| `docs/designs/_TEMPLATE.md` | - | 設計書テンプレート（architectがコピー元に使う） |
| `docs/security-policy.md` | - | 機密情報の取り扱い規約（全エージェント共通） |
| `docs/obsidian-setup.md` | - | Obsidianの初期設定ガイド |

- `docs/SPEC.md` が存在しない・不完全な場合、investigatorは作業を開始せず `/spec-interview` の実行（人間による要件定義）を促すこと
- 設計書はチケットごとに `docs/designs/{ID}.md` として分割管理する。作り直しは同ファイルの上書き＋チケットログへの改訂理由記録（過去の設計はGitヒストリで追う）。詳細は `docs/designs/README.md` と `.claude/agents/architect.md` を参照

---

## Git運用規約

git-flow（main / develop / feature / fix / release / hotfix）を採用する。ブランチ戦略の全体図・命名規則・コミットメッセージ規約 `[{チケットID}] {変更内容の要約}`・コミット前の機密確認は `.claude/agents/implementer.md`「Git Rules」を、testerのテストコミット規約は `tester.md`「Git Rules」を正とする。`git push` は人間のみが行う。緊急時のhotfix運用は `.claude/commands/rollback.md`「緊急ロールバック」を参照。

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
| cancelled            | 不要と判断してクローズ（`/triage`）。done/へ移動して保管      | any                 | -                   |

上表は正常系（前進方向）の遷移を示す。差し戻し時のステータス巻き戻し（tester fail / reviewer reject）・改善ループ・ロールバックの遷移は `.claude/agents/orchestrator.md`「差し戻し・完了時のステータス操作」を正とし、許可される遷移集合は `.claude/hooks/_ticket_lib.py` の `LEGAL_TRANSITIONS` でhookが機械的に強制する。

### チケットID採番
- 形式: `{プロジェクト略称}-{3桁連番}` 例: `APP-001`
- 採番時は `tickets/active/` と `tickets/done/` の両方を確認し、最大IDの次の番号を使う
- 略称は `/setup` で確定し、本節に「このプロジェクトの略称: `XXX`」として追記する（未追記の場合はプロジェクトルートのフォルダ名から推定する）

### 運用ルール
- 新規作成は `/new-ticket`（テンプレートコピー・配置・フロントマター・内容確認の手順は `.claude/commands/new-ticket.md`）
- チケットファイルへの書き込みはorchestratorのみがWrite/Editツールで行う。各エージェントはレポートで報告し、orchestratorが反映する。Bash経由の書き換えは禁止（読み取りと active/↔done/ の mv のみ可）。いずれもhookで機械的に強制される
- ログセクションは追記のみ（削除・上書き禁止）。`updated` は反映のたびに現在日時へ更新、`related_files` は重複なしで追記。ブロッカー発生時は `blocked` セクションに記載してstatusを `blocked` に変更する
- 完了時: statusを `done` に変更し、ログに「完了 - YYYY-MM-DD HH:MM」を追記して `tickets/active/` から `tickets/done/` へ移動する
- アーカイブ: `tickets/done/` が20件を超えたら `/archive` で個人vaultの `Archives/{project}/` へ移動する（移動後はdone/から削除してよい）

---

## リポジトリ可視性による.gitignore運用

プリセットの実体はリポジトリルートの `.gitignore.public`（実チケット tickets/active|done/*.md を除外する安全側デフォルト）と `.gitignore.private`（実チケットもコミットする）。選択・適用の手順とプリセットの前提は `.claude/commands/setup.md` 手順1を参照。

---

## 状態検証hook・メトリクス（自動強制・観測性）

チケットの状態機械はLLMの遵守だけに依存せず、hookで機械的に強制する（PreToolUseで違反をdeny、Stopで整合検査・ドリフト検知、PostToolUseでステータス遷移を `tickets/.metrics.jsonl` へ記録）。hook一覧・強制する不変条件・fail-open設計・メトリクス運用・ルール変更手順は `.claude/hooks/README.md` を正とする。検証定数（status enum・遷移表・リトライ上限）は `.claude/hooks/_ticket_lib.py` に集約されている。

- メトリクスファイル（`tickets/.metrics*.json*`）はhookが自動生成する。LLM・エージェントは直接編集しない
- 集計表示は `/metrics`（`.claude/metrics/aggregate.py`）

---

## セキュリティ・機密情報の取り扱い

機密情報（APIキー・パスワード・接続文字列・個人情報・社内非公開情報）をチケット・ドキュメント・コードに記載しないこと。禁止項目の一覧・エージェントへの指示・.gitignore必須項目は `docs/security-policy.md` を正とする。

---

## ポリシー管理の原則

CLAUDE.mdはインデックスであり、各ポリシーの正（定義）は下表のファイルが持つ。ポリシーは、それを実行する責任者（エージェント/コマンド/hook）の定義ファイルに必ず記載する。「どこかに書いた」だけでは実行されない。

**再肥大化の防止（構造維持の原則）:** 本ファイルが本文として持ってよいのは「全体像のインデックス」と「複数ファイルから参照される共通定義」のみ。新しいポリシー・手続きを追加するときは、本ファイルへ本文セクションを追加せず、次の2手順で行う。

1. 実行責任者となるファイルに正を定義する（手続きは `.claude/commands/` または `.claude/skills/`、エージェントの行動規範は `.claude/agents/*.md`、機械強制は `.claude/hooks/`、人間向け規約は `docs/`）
2. 下表へ1行追加する（必要なら本文セクションではなく既存セクションへのポインタ1行を足す）

| ポリシー | 定義（正） | 実行責任者 | 転記先・強制 |
|---|---|---|---|
| Autoモード起動時チェック | start-loop.md 起動時チェックリスト | orchestrator / start-loop | orchestrator.md Responsibilities |
| 14日blockedトリアージ | triage.md | orchestrator / start-loop / /triage | orchestrator.md Responsibilities / start-loop.md 起動時チェックリスト |
| in_progress上限3件・同一フェーズ並行1件 | orchestrator.md Responsibilities / Constraints | orchestrator + hook | start-loop.md 起動時チェックリスト / validate_ticket_state.py（着手時ask強制）・_ticket_lib.py IN_PROGRESS_LIMIT |
| cancelledステータス | 本ファイル ステータス定義 / triage.md | orchestrator | orchestrator.md 委譲テーブル / tickets/_index.md クエリ / _ticket_lib.py VALID_STATUS |
| リトライ上限（3/2/1） | orchestrator.md リトライカウンタ管理 | orchestrator + hook | _ticket_lib.py RETRY_CAPS（自動強制） |
| リトライ予算のリセット（人間承認ask） | orchestrator.md リトライ予算のリセット | 人間 + hook | validate_ticket_state.py（減少をask） / record_metrics.py（retry_reset記録） / check_loop_integrity.py（L3エポック照合） |
| チケット状態の不変条件 | 本ファイル ステータス定義 / _ticket_lib.py | PreToolUse + Stop hook（自動強制） | .claude/hooks/validate_ticket_state.py / check_loop_integrity.py |
| SPEC.md書き込みの人間承認 | 本ファイル ドキュメント管理ルール | PreToolUse hook（自動強制） | .claude/hooks/guard_spec_writes.py |
| チケット・SPEC.mdのBash書き換え禁止 | 本ファイル チケット管理ルール | PreToolUse + Stop hook（自動強制）+ 各エージェント | .claude/hooks/guard_bash_writes.py / check_loop_integrity.py（ドリフト検知） / 各agents/*.md Never |
| done/20件超のアーカイブ提案 | 本ファイル チケット管理ルール / start-loop.md | orchestrator / start-loop | start-loop.md 起動時チェックリスト |
| チケット書き込みのorchestrator専任 | 本ファイル チケット管理ルール | orchestrator / 各エージェント | orchestrator.md Responsibilities / 各agents/*.md Ticket Integration・Never |
| Git運用規約（ブランチ・コミット・機密確認） | implementer.md / tester.md Git Rules | implementer / tester | - |
| ロールバック手順 | rollback.md | /rollback | _ticket_lib.py LEGAL_TRANSITIONS（done→implementation_done） |
| バッチ連続実行の事前承認 | docs/batch-loop.md | /batch-loop | batch-loop.md 手順・制約 |
| リポジトリ可視性の.gitignoreプリセット | .gitignore.public / .private + setup.md 手順1 | /setup | - |
| プロジェクト略称の確定 | 本ファイル チケットID採番 | /setup / new-ticket | setup.md 手順3 / new-ticket.md 手順1 |
| チケットへのREQ/SCR/IF-ID明記（トレーサビリティ） | SPEC_TEMPLATE.md 冒頭規約 | /plan-tickets / architect | plan-tickets.md 手順5・Never / designs/_TEMPLATE.md §1コメント |
| NFR/EHカバレッジのチケット割当 | plan-tickets.md 手順3・4 | /plan-tickets | SPEC_TEMPLATE.md §7・§8コメント |
| Phase分割の規律（AC非再定義・全ACカバー・粒度ガード） | designs/_TEMPLATE.md §4「実装Phase」コメント | architect | architect.md Ticket Integration・Never / reviewer.md Responsibilities / implementer.md Git Rules |
| セキュリティ・機密情報の取り扱い | docs/security-policy.md | 各エージェント | implementer.md Git Rules（コミット前の機密確認） / designs/_TEMPLATE.md §4コメント |
| CLAUDE.md＝インデックス＋共通定義の維持 | 本ファイル ポリシー管理の原則（再肥大化の防止） | CLAUDE.mdを編集する人間 / Claude | - |

新しいポリシーを追加する際は、上記「再肥大化の防止」の2手順に従い、定義ファイルへの反映と本表の更新まで完了させること。
