# バッチ外部駆動ガイド（1チケット=1セッション）

複数のactiveチケットを連続でループさせるための運用手順です。チケットごとに `claude -p "/start-loop {ID}"` を**新規ヘッドレスセッション**として逐次起動する外部駆動スクリプト `scripts/batch_loop.py` を、人間がターミナルで実行します。

> **実行はセッション外・ターミナルから**: `python3 scripts/batch_loop.py {ID-1} {ID-2} ...`
> Claude Codeセッション内の `/batch-loop {ID-1} {ID-2} ...` は**プリフライト検証（--dry-run）と実行コマンドラインの提示のみ**を行い、バッチ本体は起動しません（定義: `.claude/commands/batch-loop.md`）。設計の詳細は `docs/designs/KLK-001.md` を参照。

## なぜ外部駆動か（1チケット=1セッション）

旧方式（単一セッションへバッチ事前承認テンプレートを送り、orchestratorが同一セッション内で連続実行する）では、全チケットの investigator〜reviewer のサブエージェントレポートがメインスレッドのコンテキストへ蓄積し、後続チケットほどトークン消費が累積する。本Kitは状態をチケットファイルへ外部化済みのため、セッションをチケット単位で使い捨てにしてもループは成立する。駆動スクリプトがセッションの境界でチケットファイルの状態を検査し、前進・停止を判定する。

## 使い方

```bash
# リポジトリルートで実行（メインworktreeのみ。linked worktreeでは開始しない）
python3 scripts/batch_loop.py APP-001 APP-002

# docs/SPEC.md を持たないプロジェクト（SPEC免除が人間承認済みの場合のみ）
python3 scripts/batch_loop.py --allow-missing-spec KLK-001 KLK-002

# プリフライトのみ（/batch-loop コマンドが代行実行するのもこれ）
python3 scripts/batch_loop.py --dry-run APP-001 APP-002
```

実行フロー:

1. **プリフライトP1〜P9**（下表）— 全件検査し、違反があれば一括表示して開始しない
2. **承認サマリ（y/N）** — 対象チケット・実行順・権限モード・ガード値・停止条件を表示する。**このy/N応答が従来のバッチ事前承認の実体**（`--yes` でスキップ可）
3. チケットごとに `claude -p "/start-loop {ID}" --permission-mode acceptEdits --max-turns 200 --add-dir ../{リポジトリ名}.wt` を新規セッションとして起動する（標準入出力は継承・ターミナルでライブ監視できる）。`--add-dir` はorchestratorが作成するコード作業用worktree（docs/worktree-policy.md）への書き込み許可で、配置先ディレクトリはスクリプトが起動前に作成する。駆動プロンプトには「このセッションで処理するのは {ID} の1件のみ」を明示し、バッチの事前承認はセッションへ**与えない**
4. セッション終了ごとに**境界判定1〜7**（下表）— 正常完了時のみ次チケットへ進み、最終チケット後は必ず停止する

### フラグ

| フラグ | 既定 | 意味 |
|---|---|---|
| `--dry-run` | - | プリフライトのみ実行して終了（`/batch-loop` コマンドが利用） |
| `--yes` | - | 実行前の承認プロンプト（y/N）をスキップ |
| `--permission-mode MODE` | `acceptEdits` | claudeへ渡す権限モード |
| `--max-turns N` | `200` | セッションあたりのターン上限（`0` で無効） |
| `--max-budget-usd X` | なし | セッションあたりの費用上限 |
| `--timeout-min N` | なし | セッションあたりの実時間上限（分）。超過時は子プロセスをterminateして異常終了扱い |
| `--continue-on-rework` | 停止 | 差し戻し検知（retry_counts増分）でも次チケットへ進む（事前承認の範囲を人間が明示的に広げる操作） |
| `--allow-missing-spec` | - | docs/SPEC.md不在を人間承認済みとして、SPEC免除の前提を駆動プロンプトへ付す |
| `--claude-cmd PATH` | `claude` | claude CLIのパス |

### 終了コード

| コード | 意味 |
|---|---|
| 0 | 全チケットdone到達（`--dry-run` のプリフライト通過も0） |
| 1 | 想定外の内部エラー（fail-closed） |
| 2 | プリフライト・引数エラー・承認の不成立 |
| 3 | 停止条件による中断（境界判定） |
| 130 | SIGINT（Ctrl-C。子プロセスをterminateして中断） |

## プリフライトP1〜P9

旧 `/batch-loop` 手順2（ID列検証）と `/start-loop` 起動時チェックリストの機械化。全件チェックして違反を一括表示し、1件でもあれば開始しない。

| # | 検査 | 失敗時 |
|---|---|---|
| P1 | リポジトリルートに `tickets/active/` が存在し、linked worktreeでない（チケット書き込みのメインworktree一本化。docs/worktree-policy.md） | 停止 |
| P2 | 各IDが `tickets/active/{ID}_*.md` に一意に存在する（0件・複数件マッチ・引数内のID重複はエラー） | 停止 |
| P3 | 各チケットのstatusが `cancelled` / `blocked` / `done` のいずれでもない（todo〜test_passed の中間statusからの再開は許可） | 停止 |
| P4 | in_progressチケット（investigation_done〜test_passed）が上限3件未満（ヘッドレスで着手時のask hookを踏ませない） | 停止（チケット整理を案内） |
| P5 | `status: blocked` のまま `updated` から14日超のチケットが active/ に存在しない（トリアージ対話はヘッドレスで袋小路になるため事前排除） | 停止（`/triage` を案内） |
| P6 | `docs/SPEC.md` が存在する。不在時は `--allow-missing-spec` 指定が必須（SPEC免除の人間承認をフラグで明示させる） | 停止（フラグを案内） |
| P7 | `claude --version` が実行可能（バージョン文字列を実行ログに常時表示。CLI挙動変化の切り分け材料） | 停止 |
| P8 | 全対象チケットの status / retry_counts をスナップショット（境界判定の基準） | - |
| P9 | `tickets/done/` が20件超なら警告表示（`/archive` 提案。開始は妨げない） | 警告のみ |

## 停止条件（境界判定1〜7）

セッション終了ごとに上から順に評価し、最初に該当した停止条件で報告・中断する（exit 3）。判定は毎回チケットファイルを再読取して行う — **完了判定はファイル状態が正**（`tickets/done/` に `status: done`）であり、終了コードは異常検出の補助。チケット状態が判定できない場合も停止する（fail-closed）。

| 順 | 条件 | 動作 |
|---|---|---|
| 1 | セッションの終了コード≠0（`--timeout-min` 超過を含む） | 停止「異常終了」（doneに到達していても停止し、両事実を報告） |
| 2 | active/ に `status: done` のまま残存（done/へ未移動の中間状態） | 停止「完了手続き不完全」（`/start-loop {ID}` での再開を案内） |
| 3 | `status: blocked` | 停止「blocked」（ブロッカーセクション本文を表示。リトライ上限超過もここに包含される） |
| 4 | statusが done 以外（中間statusのままセッション終了。ヘッドレスで応答不能な承認・askの発生を含む） | 停止「未完了」（再開コマンドを案内） |
| 5 | 他のバッチ対象チケットのstatusがスナップショットから変化 | 停止「範囲外変更の検知」（1セッション1チケットの前提が破れた疑い） |
| 6 | retry_counts がスナップショットから増加 | 既定: 停止「差し戻し発生（done到達済み）」／`--continue-on-rework` 指定時: 報告して次へ進む |
| 7 | 上記いずれでもない（done/に `status: done`） | 完了報告して次チケットへ。最終チケットならバッチサマリを表示して終了（exit 0） |

## 旧方式からのセマンティクス写像

旧・事前承認セマンティクス（本ガイドの旧版が定義）は、新方式へ次のように写像され維持される。

| 旧方式（単一セッション内の事前承認） | 新方式（外部駆動）での対応 |
|---|---|
| バッチ事前承認テンプレートをセッションへ送る | スクリプト実行前の承認サマリへのy/N応答（人間がセッション外で物理的に承認・起動する。関与はむしろ強まる） |
| done到達時は成果物の要約を報告し、停止せず次へ（報告は省かず*待たない*だけ） | 各セッションがdone到達時に要約を報告して終了し、駆動スクリプトが境界判定7で次へ前進する |
| 最終チケットで停止して人間の判断を待つ | 最終チケット後は必ず停止する（バッチサマリを表示。以降の継続判断は人間） |
| 差し戻し（tester/reviewer）で**即停止** | **セッション境界停止**に写像: 開始前に retry_counts をスナップショットし、増分検出時はdone到達済みでも次へ進まず停止する（境界判定6。`--continue-on-rework` で人間が明示的に緩和可）。1チケット=1セッションのモデルではセッション内の差し戻しは `/start-loop` 単体実行と同じ正常な自律実装ループであり、外部から観測可能な最も早いタイミングがセッション境界となる。「差し戻しが発生したバッチを人間の確認なしに進めない」という意図は維持される |
| リトライ上限超過・blocked発生で即停止 | blockedはチケットファイルへ外部化され、境界判定3で停止する（ブロッカー本文を表示。リトライ上限超過はblockedに包含） |
| 事前承認は列挙したID間の遷移のみに有効 | セッションへバッチの事前承認を**与えない**（駆動プロンプトで1セッション1チケットを明示。orchestratorのNeverにより承認なしでdone後に自走する根拠がない）。範囲外チケットの変化は境界判定5で停止する |

## ヘッドレスセッションの挙動（実測 2026-07-19・claude CLI v2.1.215）

- **権限モードは明示渡し**: `defaultMode: "auto"` はCLI v2.1.142以降プロジェクトsettingsからは無視されるため、駆動側が `--permission-mode acceptEdits` を既定として明示的に渡す。acceptEditsはファイル編集を自動承認しつつ、Bashはsettings.jsonのallow/denyリストとPreToolUse hookを通常どおり通す。`bypassPermissions` はask系hook（SPECゲート・リトライリセット等）を貫通し機械強制を壊すため既定にしない（人間が `--permission-mode` で明示指定した場合のみ）
- **askは自動denyになる（V-1実測）**: PreToolUse hookの `ask` はヘッドレスでは**ツール実行拒否に自動変換**される（ハングしない）。承認プロンプトで止まる代わりにチケットが前進せず、境界判定4（未完了）で停止する
- **終了コード（V-2実測）**: 正常完了=0（ツールdenyがあってもセッションが最後まで進めば0）／`--max-turns` 到達=1（「Error: Reached max turns」）／**deny多発でも0** — deny多発は終了コードでは検出できず、境界判定4が受け皿となる
- **Stop hookはヘッドレスでも機能する（V-3実測）**: check_loop_integrity（Stop hook）の `decision: "block"` は `-p` でも発火し、モデルはblock理由に従って行動する。境界判定2〜4はStop hookの「代替」ではなく**防御の重複**である
- **1セッション1チケット限定（V-4実測・縮約版）**: 駆動プロンプトの1件限定指示は縮約スケールで遵守を確認済み。本物のフルループ（investigator〜reviewer）での確認は未実施のため、**初回の実運用バッチは人間監視下のパイロット実行**と位置づけること
- **`--max-turns` は隠しオプション**: v2.1.215の `--help` に掲載されていないが機能する（既定200で使用）。将来のCLIで削除された場合、未知オプションはAPI呼び出し前に exit 1 となるため、バッチは初回セッションの境界判定1で**API消費なしに即停止**する（fail-closed）。その場合は `--max-turns 0`（無効化）で回避し、`--max-budget-usd`・`--timeout-min` を代替ガードにする

### stream-json下の追加実測（VS-1・VS-2・KLK-007 2026-07-20・claude CLI v2.1.215）

KLK-007で `--output-format stream-json --verbose --include-partial-messages --forward-subagent-text` を常時付加する変更を入れたため、上記V-1・V-3（text出力下の実測）がstream-json下でも同一かをダミープロジェクトで再検証した（VS-1）。あわせて `--forward-subagent-text` の実イベント列を単発Task委譲で実測した（VS-2）。

- **askの自動deny・stream-json下でも同一（VS-1）**: PreToolUse hookの `ask` はstream-json下でも従来どおり**ツール実行拒否に自動変換**される。deny時は `user` イベント内 `tool_result`（`is_error: true`）としてhookの拒否理由がそのままcontentに現れる。ハングせず、セッションは正常終了（exit 0）した
- **Stop hookのblockもstream-json下で発火（VS-1）**: `decision: "block"` を返すStop hookにより、モデルへ `Stop hook feedback: {reason}` という合成 `user` イベントが差し込まれ、継続を強制できることを確認した（`num_turns` が1→3へ増加）。あわせて `system` イベント（`subtype: "notification"`, `key: "stop-hook-error"`）が1件追加で流れることを観測したが、block自体は機能しており（合成フィードバックの配信・継続実行を実測で確認）、セッションは最終的に正常終了（exit 0）した。この通知イベントの正確な意味論はCLI内部実装に依存し未確認だが、`render_event()` は未知のsubtypeとして無視するだけなので表示・境界判定への影響はない
- **`render_event()` の防御的パースを実データで検証**: VS-1（上記deny・block誘発シナリオ）とVS-2（下記）で得た生JSONL（計131行）を `render_event()` に通し、例外が一件も発生しないことを確認した（AC1「表示ロジックの失敗は境界判定・終了コードに影響しない」の裏付け）
- **`--forward-subagent-text` の実イベント列（VS-2）**: 単発のTask委譲（`general-purpose` サブエージェントへの最小プロンプト）で実測したところ、サブエージェントのライフサイクルは `type: "task_started"` のようなトップレベルtypeではなく、**`type: "system"`, `subtype: "task_started"` / `"task_updated"` / `"task_notification"`** として届くことを確認した（設計書§4-1確定diffの想定と異なる）。サブエージェント自身の発言は `type: "assistant"`/`"user"` に `parent_tool_use_id`・`subagent_type` を伴って流れ、既存の assistant/user 分岐でそのまま拾える。この差異を踏まえ `render_event()` の `system` 分岐へ `task_started`（開始・description/prompt表示）・`task_notification`（完了・summary表示）の校正を実施した（コミット済み。`task_updated` は進行中パッチのみで表示価値が低いため未対応のまま無視）
- **測定方法の注記**: VS-1・VS-2とも、実運用の `/start-loop` 全体を回すコストは避け、最小限のダミーhook・単発Task委譲による軽量プローブで代替した。境界判定はいずれの実測でもファイル状態にのみ基づくため、この軽量化は安全側構成の前提（設計書§4-2）を損なわない

## 制約・注意点

- **実行中は同じリポジトリで対話セッションや別バッチを開かない** — 二重ライター防止。駆動スクリプト自体は `tickets/` へ一切書き込まない読み取り専用（単一ライター原則の維持）だが、並行セッションがチケットへ書き込むと範囲外変更・スナップショット差分として停止する
- **逐次実行であり並行ではない** — 1チケットを最後まで流してから次へ進む。同時並行はしない
- **メインworktree専用** — linked worktree上ではプリフライトP1で停止する（docs/worktree-policy.md）
- **コード作業はチケット専用worktreeで行われる** — セッション内のorchestratorがworktreeを作成し、implementer以降はそこで作業するため、メインツリーのHEADは常にdevelopに保たれる。セッションが異常終了してもfeatureブランチがメインツリーに残らず、次チケットのセッションが前のブランチ上で開始する事故を防ぐ。取り残されたworktreeは次回 `/start-loop` 起動時チェックリストが検出する
- **中断と再開** — Ctrl-C（SIGINT）で子プロセスをterminateして中断する（exit 130）。チケットは中間statusのままファイルへ外部化されているため、`/start-loop {ID}`（対話セッション）または残りIDでの本スクリプト再実行で再開できる
- **コストガード** — `--max-turns 200` 既定に加え、`--max-budget-usd`・`--timeout-min` を必要に応じて指定する

## 旧方式（セッション内手動テンプレート）について

旧方式 — 単一セッションへ「バッチ連続実行の事前承認」テンプレートを送り、orchestratorが同一セッション内で連続ループする — は、orchestratorの規範（改善ループ判断テーブルの人間判断を事前承認で充足する）上は引き続き成立するが、サブエージェントレポートの蓄積により後続チケットほどトークン消費が累積するため**非推奨**とする。旧テンプレートが必要な場合はGitヒストリ（v1.7.0以前の本ファイル）を参照。
