# CHANGELOG

Kenesis Loop Kitのすべての変更はこのファイルに記録されます。
フォーマットは [Keep a Changelog](https://keepachangelog.com/ja/1.0.0/) に準拠し、
バージョン管理は [Semantic Versioning](https://semver.org/lang/ja/) に従います。

---

## [1.5.1] - 2026-07-08

### Fixed
- Stop hook `check_loop_integrity.py` のブロックが本番で発火しない不具合を修正: `decision`/`reason` を `hookSpecificOutput` にネストして出力していたが、Claude Code の Stop/SubagentStop 契約では両者はトップレベル（`hookSpecificOutput` は `additionalContext` のみ受理）。ネストされた `decision` は無視されるため、整合性検査・ドリフト検知が block を一切返せていなかった（PreToolUse 系の `hookSpecificOutput.permissionDecision` は仕様どおりで影響なし）。トップレベル出力に修正し、テストヘルパ `_util.top_level_output` を追加、`test_loop_integrity.py` を実契約に合わせて更新。形式退行を防ぐ `test_block_uses_top_level_decision`（トップレベル `decision: block`・`hookSpecificOutput` 不在を検証）を追加

### Changed
- 状態検証hookの重複コードを `_ticket_lib.py` へ集約（内部リファクタ・挙動不変・全137テスト通過）: `is_ticket`（チケットパス判定）を validator / recorder から一本化。PreToolUse の decision 出力（`hookSpecificOutput` 契約）を `emit_pretooluse_decision` に集約（validate_ticket_state / guard_bash_writes / guard_spec_writes）。`.metrics.jsonl` の読み込み・ticket別グルーピングを `load_events` / `group_events_by_ticket` に集約（check_loop_integrity / aggregate で共有）。record_metrics のサイドカー読み込みも `load_state` へ統一（非dict正規化ガードで壊れたサイドカーを次回書き込みで自己修復）。README（hookドキュメント）の `_ticket_lib.py` 役割記述も追随

## [1.5.0] - 2026-07-08

### Added
- リトライ予算のリセット（人間承認ゲート）: カウンタの減少を deny から `ask` に変更し、人間が承認プロンプトで許可した場合のみ正規のリセットとして成立する（改善ループ・blocked解消後の再挑戦など「新しい試行」の開始時）。承認後は `record_metrics.py` が `retry_reset` イベントを記録し、L3照合は「最終リセット時の値＋以降の差し戻し回数」のエポック方式で継続する。Bash・手編集による減少は従来どおりドリフト検知が block する。運用規約は orchestrator.md「リトライ予算のリセット」に定義
- in_progress上限のhook強制: `todo → investigation_done` の着手時に他チケットの in_progress が上限（3件・`_ticket_lib.py IN_PROGRESS_LIMIT`）に達していれば `ask` で人間確認を強制する（「上限到達時は人間に確認」ポリシーの機械化。起票=todo作成はゲートしない）
- Stop hookのドリフト検知を tickets/done/ にも拡大（ドリフト検知のみ。旧チケットの誤検知を避けるため全量検査は active/ 限定のまま）
- hook `guard_bash_writes.py`（PreToolUse・Bash）: tickets/active|done/・SPEC.md に言及するBashコマンドのうち、読み取り・移動系ホワイトリスト（cat/grep/ls/mv/git add 等）以外を deny でブロック。リダイレクト・sed -i・tee・インタプリタワンライナー（`python3 -c` 等）・find -exec・ヒアドキュメントによる状態検証hookの迂回をベストエフォートで遮断する。`tests/test_guard_bash_writes.py` を追加
- ドリフト検知（Stop）: `check_loop_integrity.py` が `tickets/.metrics_state.json`（hookの最終観測値）と各チケットの status / retry_counts を突き合わせ、Write/Edit を経ない書き換え（Bash・手編集。パス非リテラルの迂回を含む）を検出して block する。復旧は Edit ツールでの再適用（観測値へ戻す / 観測値からの正当な遷移として適用し直す）に限定し、検証の権威を validate_ticket_state.py に保つ
- SPEC_TEMPLATE.md §6を「画面・インターフェース一覧」へ汎用化: UIを持たないプロジェクト（API・バッチ等）向けに「提供インターフェース一覧」（IF-xxx採番・欠番再利用禁止）を追加し、旧「該当なし」運用を置換。spec-interview（ヒアリング指針・完成チェックリスト）・wireframe-gen（受付判定でUIなしSPECを旧形式と誤判定しないよう修正）・plan-tickets（起票時のIF-ID明記）・CLAUDE.mdポリシー表を整合
- SPEC_TEMPLATE.md §7エラーハンドリング・異常系方針をEH-xxx付きの表形式へ変更（検証方法列を必須化・「人間が確認」の明記規約は§8と統一）。§5のMust失敗時挙動から備考でEH-IDを参照可能にし、無IDだった§7のトレーサビリティの穴を解消
- `/plan-tickets` にNFR/EHカバレッジ割当を追加: §7・§8の読み取り、割当ルール（自動検証は関連機能チケットまたは横断検証チケットへ、「人間が確認」はループ外として明示）、承認時のNFR/EH割当表（宙に浮いたIDを残さない）、起票時のNFR/EH-ID明記と受け入れ条件への検証方法反映
- designs/_TEMPLATE.md §4に「実装Phase」表（Phase / 内容 / 完了条件 / 対応する受け入れ条件）を追加: implementer定義の「承認済みのPhaseとplan」を実体化。AC非再定義・全ACカバレッジ（architectセルフチェック＋reviewer検証）・粒度ガード（Phase 4つ以上はチケット分割見直しとして人間へ報告）・チケットstatus非反映の4原則をコメントで明文化し、architect.md（Phase分割手順・Never）/ reviewer.md（カバレッジ検証）/ implementer.md（Phase単位コミット `[{ID}] Phase {N}: {内容}`）へ転記
- designs/_TEMPLATE.md フロントマターに `spec_version` を追加（設計が準拠したSPEC版数の追跡。SPEC §0「設計書がどの版に基づいたか追跡」の実現）

### Changed
- リトライ上限超過時のdenyメッセージを修正: 「上限超過時は status を blocked にしてください」→「上限到達後の差し戻しではカウンタを増やさず、status を blocked にして人間へ報告してください」（blockedでもcap超の書き込みはdenyされるため、従来の文言はdenyループを誘発しうる誤誘導だった）
- orchestrator.md: メインスレッド実行の注意（サブエージェントとして起動するとAgentツールで再委譲できず委譲ループが機能しない）とリセット運用規約・Never（人間の指示なしにカウンタをリセットしない）を追記
- `.gitignore.public` に `*.skill` 除外を追加（現行 `.gitignore` との乖離で `/setup` 手順1が「独自カスタマイズあり」と誤診断する問題を解消）
- README: セットアップ手順4を `/spec-interview` フローに更新（手書きSPEC.md前提の旧記述を解消）
- `validate_ticket_state.py`: 既存チケットへの書き込みの遷移元（prior）を `.metrics_state.json` の最終観測値を正として決定するよう変更（ファイル内容はフォールバック）。ドリフト後の書き込みも「最後に検証された状態」からの遷移として検証されるため、ログ追記だけのEditで不正遷移を洗浄できない。L2カウンタ単調性もファイルpriorと観測値の要素ごと最大値を下限として照合する
- `record_metrics.py`: 状態サイドカーに retry_counts も保持する（ドリフト検知・L2下限の基準）。status不変で retry_counts のみ変化したEditでは、イベントを追記せず state のみ更新する。tickets/ ディレクトリはチケットパスから導出する（cwd はフォールバック）
- 各エージェント定義の Never「Bash経由でチケット・SPEC.mdを書き換えない」を書き込みベクタ全般（インタプリタワンライナー・find -exec・ヒアドキュメント含む）に拡張。CLAUDE.md 作業中の更新ルール・状態検証hook表・ポリシー管理の原則にも同内容を転記
- SPEC_TEMPLATE.md: §9に標準構成の出自注記規約（「標準構成 vX.X をデフォルト適用」の注記・ユーザー指定★。正はDEFAULT_STACK.md §3）のコメントを追加。全ID種（REQ/SCR/IF/EH/NFR/OQ）の欠番再利用禁止を各セクションコメントと改訂モード規約で統一
- designs/_TEMPLATE.md: 受け入れ条件（§9）を「/plan-ticketsで人間が承認した契約」と位置づけ、弱める変更・再定義をOpen Question経由の人間判断に限定（権限の一方向化: SPEC→チケットAC→設計§9→Phase完了条件）。§1にSPEC ID明記（REQ/SCR/IF/EH/NFR）、§4にシークレット実値の記載禁止（環境変数名のみ）、§9に割当NFR/EHの検証方法具体化とテスト観点（単体/結合境界・モック方針・エッジケース）、§10にOQ解消時のチケットログ記録を追加

## [1.4.0] - 2026-07-07

### Added
- スラッシュコマンド `/plan-tickets`（`.claude/commands/plan-tickets.md`）: SPEC.mdを基に開発をチケットへ分割し、人間の承認を経て一括起票する。REQのMoSCoW分類→priorityマッピング、依存順の起票、OQ依存REQの保留、スコープ外の除外、既存チケットとのREQカバレッジ突き合わせ（冪等・SPEC改訂後の差分起票に対応）。SPEC_TEMPLATE.md冒頭規約「チケットへのREQ/SCR-ID明記」の実行責任者となる。分割単位の用語は「チケット/マイルストーン」とし、architectのチケット内Phase分割との定義揺れを回避
- スラッシュコマンド `/rollback`（`.claude/commands/rollback.md`）: CLAUDE.md「ロールバック手順」をコマンド化。revert対象コミットの特定・人間の実行前承認・`git revert`・チケットのdone/→active/移動とstatus巻き戻し（implementation_done）・ログ追記までを一括実行する
- スラッシュコマンド `/batch-loop`（`.claude/commands/batch-loop.md`）: `docs/batch-loop.md` の命令テンプレートをコマンド化。チケットID列からバッチ事前承認を組み立てて確認を取り、承認ゲートで止めない連続ループを起動する（異常系での即時停止の安全装置つき）
- スラッシュコマンド `/setup`（`.claude/commands/setup.md`）: プロジェクトの初期セットアップと現在地診断をコマンド化。.gitignoreプリセット選択（独自カスタマイズ検出時は差分確認）・Obsidian案内・プロジェクト略称の確定（CLAUDE.md「チケットID採番」節へ追記）・SPEC/前工程の状態に応じた次の一手の案内（/spec-interview → /interrogate-spec → /wireframe-gen → /new-ticket → /start-loop）。全ステップ冪等で再実行可能
- `/new-ticket`: プロジェクト略称の取得元を CLAUDE.md の略称行優先（無ければフォルダ名）に明確化
- スラッシュコマンド `/triage`（`.claude/commands/triage.md`）: 長期放置blockedチケットのトリアージ（再開/クローズ/期限延長）をループ起動なしで単体実行できるようコマンド化。再開時の元statusは `.metrics.jsonl` の `to: blocked` イベントから復元。日数しきい値・チケットID指定に対応。/start-loop 起動時チェックリストと orchestrator.md は本コマンドの手順を参照する形に一本化

### Changed
- `/start-loop`: 処理対象0件時の分岐を定義。active/が完全に0件なら `/plan-tickets` を実行（SPEC無しは /spec-interview へカスケード）、全件が blocked / cancelled ならブロッカー滞留として `/triage` を案内して停止（チケット積み増しへの誤誘導を防止）
- `/plan-tickets`: REQカバレッジ集計から `status: cancelled` を除外（クローズ済みチケットのREQをカバー済みと誤判定するのを防止）。未カバーREQ 0件時の完了報告（カバレッジ表・改善ループ / SPEC改訂 / アーカイブの選択肢案内）を追加
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
