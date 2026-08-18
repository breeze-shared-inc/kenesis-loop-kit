# ポリシー管理表

このファイルはCLAUDE.md「ポリシー管理の原則」から分離した、プロジェクト運用ポリシーの一覧表です（KLK-005でCLAUDE.mdのコンテキスト注入コストを削減するため分離）。

CLAUDE.mdはインデックスであり、各ポリシーの正（定義）は下表のファイルが持つ。ポリシーは、それを実行する責任者（エージェント/コマンド/hook）の定義ファイルに必ず記載する。「どこかに書いた」だけでは実行されない。新しいポリシー・手続きを追加する手順（実行責任者ファイルへの正の定義 → 下表へ1行追加）は `CLAUDE.md`「ポリシー管理の原則」（再肥大化の防止）を正とする。

## ポリシー一覧

| ポリシー | 定義（正） | 実行責任者 | 転記先・強制 |
|---|---|---|---|
| Autoモード起動時チェック | start-loop.md 起動時チェックリスト | orchestrator / start-loop | orchestrator.md Responsibilities |
| 14日blockedトリアージ | triage.md | orchestrator / start-loop / /triage | orchestrator.md Responsibilities / start-loop.md 起動時チェックリスト |
| in_progress上限3件 | orchestrator.md Responsibilities | orchestrator + hook | start-loop.md 起動時チェックリスト / validate_ticket_state.py（着手時ask強制）・_ticket_lib.py IN_PROGRESS_LIMIT |
| cancelledステータス | CLAUDE.md ステータス定義 / triage.md | orchestrator | orchestrator.md 委譲テーブル / tickets/_index.md クエリ / _ticket_lib.py VALID_STATUS |
| リトライ上限（3/2/1） | orchestrator.md リトライカウンタ管理 | orchestrator + hook | _ticket_lib.py RETRY_CAPS（自動強制） |
| リトライ予算のリセット（人間承認ask） | orchestrator.md リトライ予算のリセット | 人間 + hook | validate_ticket_state.py（減少をask） / record_metrics.py（retry_reset記録） / check_loop_integrity.py（L3エポック照合） |
| チケット状態の不変条件 | CLAUDE.md ステータス定義 / _ticket_lib.py | PreToolUse + Stop hook（自動強制） | .claude/hooks/validate_ticket_state.py / check_loop_integrity.py |
| SPEC.md書き込みの人間承認 | CLAUDE.md ドキュメント管理ルール | PreToolUse hook（自動強制） | .claude/hooks/guard_spec_writes.py |
| SPEC構造の機械チェック（テンプレート準拠の受付） | .claude/skills/spec-interview/scripts/check_spec_structure.py（構造の正はSPEC_TEMPLATE.md） | /setup / /interrogate-spec / /spec-interview | setup.md 手順5 診断表 / interrogate-spec SKILL.md Phase 0 構造受付 / spec-interview SKILL.md Step 3・改訂モード手順5 |
| SPECのID指向部分抽出（REQ/SCR/IFの該当セクション優先読み・全文はフォールバック） | .claude/skills/spec-interview/scripts/extract_spec_section.py（実装の正はdocs/designs/KLK-006.md。構造の正はSPEC_TEMPLATE.md） | investigator / architect / reviewer | investigator.md Ticket Integration「On start」/ architect.md Ticket Integration「作業開始時」/ reviewer.md Ticket Integration「作業開始時」/ .claude/hooks/guard_bash_writes.py READONLY_SCRIPTS / tests/test_extract_spec_section.py |
| 前工程の次の一手ルーティング | setup.md 手順5（診断表） | /setup | interrogate-spec SKILL.md セッション終了時（ポインタ転記） / spec-interview SKILL.md Step 4（ハンドオフ） |
| チケット・SPEC.mdのBash書き換え禁止 | CLAUDE.md チケット管理ルール | PreToolUse + Stop hook（自動強制）+ 各エージェント | .claude/hooks/guard_bash_writes.py / check_loop_integrity.py（ドリフト検知） / 各agents/*.md Never |
| done/20件超のアーカイブ提案 | CLAUDE.md チケット管理ルール / start-loop.md | orchestrator / start-loop | start-loop.md 起動時チェックリスト |
| チケット書き込みのorchestrator専任 | CLAUDE.md チケット管理ルール | orchestrator / 各エージェント | orchestrator.md Responsibilities / 各agents/*.md Ticket Integration・Never |
| Git運用規約（ブランチ・コミット・機密確認） | implementer.md / tester.md Git Rules | implementer / tester | - |
| worktree分離（implementer以降のコード作業・done時にdevelopへマージし削除・チケットはメインツリー一本化） | docs/worktree-policy.md | orchestrator + implementer / tester / reviewer | orchestrator.md worktreeライフサイクル管理 / implementer.md Git Rules 運用ルール / tester.md・reviewer.md / start-loop.md 起動時チェックリスト / batch_loop.py（--add-dir） / CLAUDE.md Git運用規約（ポインタ） |
| ロールバック手順 | rollback.md | /rollback | _ticket_lib.py LEGAL_TRANSITIONS（done→implementation_done） |
| バッチ連続実行の事前承認 | docs/batch-loop.md（外部駆動）/ docs/batch-loop-inline.md（セッション内） | 人間 + scripts/batch_loop.py（外部駆動・/batch-loopは検証・案内）／ orchestrator（セッション内・/batch-loop-inline） | batch-loop.md 手順・Never・停止条件 / batch-loop-inline.md 手順・Never・停止条件 / orchestrator.md 改善ループテーブル直下の注記（バッチ実行時の代行範囲の明記） |
| Kitからの切り離し（clone導入時の.git再初期化） | setup.md 手順1 | /setup | setup.md Never（.git削除の明示承認・Kit本体除外） |
| リポジトリ可視性の.gitignoreプリセット | .gitignore.public / .private + setup.md 手順2 | /setup | - |
| プロジェクト略称の確定 | CLAUDE.md チケットID採番 | /setup / new-ticket | setup.md 手順4 / new-ticket.md 手順1 |
| チケットへのREQ/SCR/IF-ID明記（トレーサビリティ） | SPEC_TEMPLATE.md 冒頭規約 | /plan-tickets / architect | plan-tickets.md 手順5 / designs/_TEMPLATE.md §1コメント |
| NFR/EHカバレッジのチケット割当 | plan-tickets.md 手順3・4 | /plan-tickets | SPEC_TEMPLATE.md §7・§8コメント |
| Phase分割の規律（AC非再定義・全ACカバー・粒度ガード） | designs/_TEMPLATE.md §4「実装Phase」コメント | architect | architect.md Ticket Integration・Never / reviewer.md Responsibilities / implementer.md Git Rules |
| セキュリティ・機密情報の取り扱い | docs/security-policy.md | 各エージェント | implementer.md Git Rules（コミット前の機密確認） / designs/_TEMPLATE.md §4コメント |
| エージェントのモデル割当（役割別の軽量化・見直しトリガー） | `.claude/agents/*.md`（orchestrator.mdを除く5ファイル）の本文「## Model Assignment」節 + frontmatter `model`（sonnet割当時のみ記述） | architect（設計）+ 人間（承認） | agents/*.md Model Assignment節（tester/investigator=sonnet、architect/reviewer/implementer=inherit維持） |
| サブエージェントレポートの要約上限・詳細外部化（docs/reports/{ID}/{phase}.md） | docs/designs/KLK-004.md + 各 `.claude/agents/*.md` Required Output Format | 各エージェント + orchestrator（Write/Edit非保持エージェント分の代筆） | 各agents/*.md Required Output Format・Ticket Integration・Git Rules / orchestrator.md Responsibilities・Ticket Integration / docs/reports/README.md |
| CLAUDE.md＝インデックス＋共通定義の維持 | CLAUDE.md ポリシー管理の原則（再肥大化の防止） | CLAUDE.mdを編集する人間 / Claude | - |
| orchestratorのチケット一覧取得（frontmatterスキャンCLI・パス引数を持たない設計） | scripts/list_tickets.py（実装の正はdocs/designs/KLK-003.md） | orchestrator / start-loop / /triage | orchestrator.md Ticket Integration / start-loop.md 起動時チェックリスト・ループ実行手順1 / .claude/commands/triage.md 手順1 / tests/test_list_tickets.py / tests/test_klk022_doc_wiring.py |

新しいポリシーを追加する際は、`CLAUDE.md`「ポリシー管理の原則」（再肥大化の防止）が定める2手順に従い、定義ファイルへの反映と本表の更新まで完了させること。
