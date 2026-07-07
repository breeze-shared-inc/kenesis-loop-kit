# CHANGELOG

Kenesis Loop Kitのすべての変更はこのファイルに記録されます。
フォーマットは [Keep a Changelog](https://keepachangelog.com/ja/1.0.0/) に準拠し、
バージョン管理は [Semantic Versioning](https://semver.org/lang/ja/) に従います。

---

## [Unreleased]

### Added
- スラッシュコマンド `/plan-tickets`（`.claude/commands/plan-tickets.md`）: SPEC.mdを基に開発をチケットへ分割し、人間の承認を経て一括起票する。REQのMoSCoW分類→priorityマッピング、依存順の起票、OQ依存REQの保留、スコープ外の除外、既存チケットとのREQカバレッジ突き合わせ（冪等・SPEC改訂後の差分起票に対応）。SPEC_TEMPLATE.md冒頭規約「チケットへのREQ/SCR-ID明記」の実行責任者となる。分割単位の用語は「チケット/マイルストーン」とし、architectのチケット内Phase分割との定義揺れを回避
- スラッシュコマンド `/rollback`（`.claude/commands/rollback.md`）: CLAUDE.md「ロールバック手順」をコマンド化。revert対象コミットの特定・人間の実行前承認・`git revert`・チケットのdone/→active/移動とstatus巻き戻し（implementation_done）・ログ追記までを一括実行する
- スラッシュコマンド `/batch-loop`（`.claude/commands/batch-loop.md`）: `docs/batch-loop.md` の命令テンプレートをコマンド化。チケットID列からバッチ事前承認を組み立てて確認を取り、承認ゲートで止めない連続ループを起動する（異常系での即時停止の安全装置つき）
- スラッシュコマンド `/setup`（`.claude/commands/setup.md`）: プロジェクトの初期セットアップと現在地診断をコマンド化。.gitignoreプリセット選択（独自カスタマイズ検出時は差分確認）・Obsidian案内・プロジェクト略称の確定（CLAUDE.md「チケットID採番」節へ追記）・SPEC/前工程の状態に応じた次の一手の案内（/spec-interview → /interrogate-spec → /wireframe-gen → /new-ticket → /start-loop）。全ステップ冪等で再実行可能
- `/new-ticket`: プロジェクト略称の取得元を CLAUDE.md の略称行優先（無ければフォルダ名）に明確化
- スラッシュコマンド `/triage`（`.claude/commands/triage.md`）: 長期放置blockedチケットのトリアージ（再開/クローズ/期限延長）をループ起動なしで単体実行できるようコマンド化。再開時の元statusは `.metrics.jsonl` の `to: blocked` イベントから復元。日数しきい値・チケットID指定に対応。/start-loop 起動時チェックリストと orchestrator.md は本コマンドの手順を参照する形に一本化

### Changed
- `_ticket_lib.py` の `LEGAL_TRANSITIONS` にロールバック遷移 `done → implementation_done` を追加（CLAUDE.md「ロールバック時のチケット運用」がhookにブロックされる不整合を解消）。対応テストを `tests/test_ticket_lib.py` に追加
- CLAUDE.md: `/rollback`・`/batch-loop` をスラッシュコマンド一覧・ポリシー管理の原則へ登録。状態検証hookの遷移不変条件の記述にロールバックを追記
- `start-loop.md`・`docs/batch-loop.md`: 連続実行の導線を `/batch-loop` コマンド参照へ更新

## [1.3.0] - 2026-07-07

### Added
- スキル `interrogate-spec`（`.claude/skills/interrogate-spec/`）: SPEC.mdを敵対的にレビューし、矛盾・未定義動作・暗黙の前提・外部依存未知を質問リスト化。優先度順のバッチ対話で人間の回答を引き出し、SPEC改訂・決定ログ（DECISION_LOG.md）・検証バックログ（VERIFICATION_BACKLOG.md）・エスケープ記録（ESCAPES.md）として `docs/spec-qa/<spec名>/` に固定する。状態ファイルの初期化雛形（`references/templates/init/`）を同梱
- スキル `research-conventions`（`.claude/skills/research-conventions/`）: 調査タスクの規律（ソース種別・信頼度序列・確信度運用・矛盾の融合禁止・降参の出口）を定義。investigatorへプリロードして使用（単体起動なし）
- investigator エージェント: 委譲調査モード（Mode B）を追加し、interrogate-spec からの調査委譲に対応。呼び出し側指定スキーマで出力し、human_only な問いには推奨方針を生成しない。WebSearch/WebFetchを許可
- hook `guard_spec_writes.py`（PreToolUse・Write|Edit）: SPEC.mdへの書き込みを `permissionDecision: ask` で人間確認に回し、「SPEC.mdの改訂は人間のdiff承認を経る」をLLMの手順遵守だけに依存せず機械的に担保（autoモードでは権限プロンプトに頼れないため）。`tests/test_guard_spec_writes.py` を追加
- `.claude/settings.json`: interrogate-spec の成果物置き場 `docs/spec-qa/**` への Edit/Write を allow に追加

### Changed
- エージェント定義 `agents/*.md` を `.claude/agents/` へ移動（Claude Codeのサブエージェント自動発見・tools制限・skillsプリロードを有効化するため）。CLAUDE.md・README.md・docs/batch-loop.md・各コマンド定義の参照パスを更新
- CLAUDE.md: `/interrogate-spec` をスラッシュコマンド一覧・開発ループフロー図（前工程）・ドキュメント管理ルールへ登録

## [1.2.0] - 2026-07-05

### Added
- スキル `spec-interview`（`.claude/skills/spec-interview/`）: 非エンジニア向けに対話形式で要件定義書 `docs/SPEC.md` を作成・改訂する。最短/フルの2モード、標準技術構成の「反証がなければ適用」（`DEFAULT_STACK.md`）、SPECテンプレート（`SPEC_TEMPLATE.md`）を同梱
- スキル `wireframe-gen`（`.claude/skills/wireframe-gen/`）: SPECの画面一覧（セクション6）から単一ファイル静的HTMLのワイヤーフレーム・ハブページ（index.html）・PC/スマホ比較ビュー（compare.html）を生成する。生成規約 `WIREFRAME_RULES.md` を同梱（外部依存ゼロ・中忠実度・コントラスト規律・Mermaid遷移図のCSSフォールバック）
- CLAUDE.md にスキルを登録: スラッシュコマンド一覧・開発ループフロー図の前工程（SPEC作成→ワイヤーフレーム→チケット作成）・ドキュメント管理表・investigatorのSPEC不在時の誘導
- `.gitignore` に `*.skill`（スキルのZIP配布物を除外し、ソースの正を `.md` に一本化）
- `docs/wireframes/`（出力ディレクトリのプレースホルダ `.gitkeep`）

### Removed
- 静的テンプレート `docs/SPEC.md`（要件定義は `/spec-interview` から生成する方式へ移行。テンプレートはスキル内 `SPEC_TEMPLATE.md` が正）

---

## [1.1.0] - 2026-06-17

### Added
- 状態検証hook: `validate_ticket_state.py`（PreToolUse）/ `check_loop_integrity.py`（Stop）/ `_ticket_lib.py`。チケット状態機械を機械的に強制
- ループ観測性: `record_metrics.py`（PostToolUse）でステータス遷移を `tickets/.metrics.jsonl` に記録、`.claude/metrics/aggregate.py` で集計、`/metrics` コマンドで表示
- `.claude/settings.json` にhook登録（PreToolUse / PostToolUse / Stop）
- 自動テスト `tests/`（unittest・依存なし）: 検証ルール・各hook・メトリクス集計を66ケースでカバー
- リトライカウンタ強制の二層化: L2 カウンタ単調性（PreToolUse・減少禁止でcap回避を防止）/ L3 差し戻し履歴照合（Stop・`.metrics.jsonl` の差し戻し回数とカウンタを和で照合し、増やし忘れ＝上限不発火の穴を塞ぐ）
- チケットフロントマターに `retry_counts` を追加し、本文「リトライカウンタ」セクションと併用（ハイブリッド管理）
- CLAUDE.md「ポリシー管理の原則」転記表・状態検証hook節
- 権限モード `auto` の既定化（`.claude/settings.json` `permissions.defaultMode = "auto"`）。コマンド承認でループが頻繁に停止する問題を解消
- ループ起動時チェック「Autoモードの確認」（`start-loop.md` 起動時チェックリスト / `orchestrator.md` Responsibilities）と、ポリシー管理表への該当行追記
- CI: `.github/workflows/test.yml`（push(main/develop)・PRで `tests/` を Python 3.10–3.12 マトリクス実行、stdlibのみ）
- `docs/batch-loop.md`: 複数チケットの連続ループ実行ガイド（事前バッチ承認で各完了時の承認ゲートを跨ぐ運用）
- `.claude/settings.json` の allow に `sed -n`（読み取り専用）のみ再追加（probe/テスト後始末の複合コマンド向け）。`echo` はファイル書き込みベクタ（`echo > file`）を再び開くため再追加せず、auto モードの分類器に委ねる。環境固有の `.venv/bin/python` / `rm -f` ルールは `settings.local.json` へ分離

### Changed
- 設計書を単一 `docs/DESIGN.md` から `docs/designs/{ID}.md`（チケット単位分割）へ変更
- 設計書frontmatterから `status`（draft/approved/superseded）を撤廃。設計の進行はチケットstatusを唯一の真実とし、履歴はGitに委ねる（dead state解消）
- orchestratorのステータス定義をCLAUDE.md準拠に統一（独自ステータス `review_approved` / `review_rejected` を廃止）
- architect後の人間承認ゲートを廃止し、実装ループを完全自律化
- README: Obsidianが任意であることを明言

### Removed
- `docs/DESIGN.md`（`docs/designs/` へ移行）
- `.claude/settings.json` の allow から `awk` / `echo`（ファイル書き込みをWrite権限に一元化）。※ `sed -n`（読み取り専用）のみ probe/テスト用途で再追加（上記 Added 参照）

---

## [1.0.0] - 2026-06-14

### Added
- エージェント定義: orchestrator / investigator / architect / implementer / tester / reviewer
- チケットテンプレート: ticket.md / ticket-bug.md
- スラッシュコマンド: /start-loop / /new-ticket / /improvement-loop / /archive
- ドキュメント: SPEC.md / docs/designs/ (チケット単位設計書) / obsidian-setup.md テンプレート
- チケットダッシュボード: tickets/_index.md
- Claude Code設定: .claude/settings.json（権限設定）
- .gitignoreテンプレート（プライベート用・パブリック用）
- 2ループ構造（実装ループ・改善ループ）の導入
- git-flowブランチ戦略の採用
- Gitコミット規約（チケットIDプレフィックス）

---

<!--
## バージョニングの指針

MAJOR（X.0.0）: エージェント定義の大幅な変更・ループフローの変更・既存プロジェクトとの後方互換性が失われる変更
MINOR（0.X.0）: 新規エージェント追加・新規コマンド追加・テンプレートの追加
PATCH（0.0.X）: ドキュメントの修正・既存テンプレートの軽微な修正・バグ修正

## 変更カテゴリ
- Added: 新機能
- Changed: 既存機能の変更
- Deprecated: 将来削除予定の機能
- Removed: 削除された機能
- Fixed: バグ修正
- Security: セキュリティ関連の修正
-->
