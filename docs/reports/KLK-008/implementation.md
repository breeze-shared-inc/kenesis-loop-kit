# KLK-008 実装レポート（implementer）

- 実施日: 2026-08-19
- ブランチ: `feature/KLK-008-subagent-prefix-pipe-close`（worktree `../kenesis-loop-kit.wt/KLK-008`）
- 設計の正: docs/designs/KLK-008.md（§4のコード雛形・テスト一覧・Phase分割に準拠）

## コミット

| Phase | コミット | 内容 |
|---|---|---|
| 1 | 2dab9d6 | `_subagent_prefix()` 新設・assistant/user分岐の接頭辞対応・単体8件+E2E 1件 |
| 2 | de1a081 | `run_session()` try/finally再構成（明示close）・`TestRunSessionPipeClose` 3件 |

## Phase 1: サブエージェント接頭辞（AC1・AC4表示側）

`scripts/batch_loop.py`:

- `_subagent_prefix(evt)` を `_brief()` と `render_event()` の間に新設。設計書§4(1)の雛形どおり:
  truthy判定（`parent_tool_use_id: null` 明示・キー欠落のいずれでも非発火）、
  トップレベル→message内の両対応ルックアップ、ラベル連鎖
  `subagent_type`（トップレベル）→ message内`subagent_type` → `name` → `"subagent"`
- `render_event()` の assistant/user 分岐で、行生成より先に `prefix = _subagent_prefix(evt)` を評価し、
  `[tool]`/`[result]` の各表示行へ前置（複数ブロック時も1行ごとに接頭辞）
- text-only content は従来どおり `None`（表示対象を拡大しない）。フォールバック分岐
  （`etype in ("task_started", "task_notification") or "parent_tool_use_id" in evt`）は無変更
- `render_event()` docstringへKLK-008の接頭辞方針を2行追記

`tests/test_batch_loop.py` — `TestRenderEvent` へ単体8件（設計書§4(3)の表と1:1対応）:

1. `test_assistant_subagent_tool_use_prefixed` — トップレベル配置のtool_useに接頭辞
2. `test_user_subagent_tool_result_prefixed` — tool_resultに接頭辞（assertEqual厳密一致）
3. `test_assistant_parent_tool_use_id_null_not_prefixed` — null明示は非発火
4. `test_assistant_subagent_fields_inside_message_prefixed` — message内配置（防御側）で発火
5. `test_assistant_subagent_label_falls_back_to_name` — `name:"reviewer"` フォールバック
6. `test_assistant_subagent_label_placeholder` — `"subagent"` プレースホルダ
7. `test_assistant_subagent_multiple_blocks_each_prefixed` — 2行とも接頭辞付き
8. `test_assistant_subagent_text_only_returns_none` — text-onlyはNoneのまま

`TestBatchEndToEnd` へE2E 1件: `test_stream_json_subagent_utterance_prefixed`
（フェイクclaudeがJSONL行をecho → rc==0 かつ出力に `[subagent:investigator] [tool] Read(` を含む）。

## Phase 2: stdout pipe明示close（AC2・AC4 close側）

`scripts/batch_loop.py` `run_session()`:

- 設計書§4(2)の雛形どおり `return code, time.monotonic() - start` をtry内へ移動し、finally節を追加。
  whileループ本体・except節（KeyboardInterrupt→`_terminate`→raise）・timeout経路の
  `return "timeout", ...` は無変更。外部契約 `(exit_status, elapsed_sec)` 不変
- finallyの順序保証: `if proc.poll() is None: _terminate(proc)`（想定外例外経路の防御）→
  `reader.join(timeout=5)`（子reap済のためreadlineはEOFで自然終了・通常即時）→
  `proc.stdout.close()`（読んでいるスレッドがいない状態でのメインスレッドclose）
- docstringへclose方針（多層防御・close順序）を3行追記

`tests/test_batch_loop.py` — 新クラス `TestRunSessionPipeClose`（`TestBatchEndToEnd` と
`TestSubprocessBehaviors` の間に配置）3件:

- setUpで `batch_loop.subprocess.Popen` を実Popenのスパイ（`mock.patch.object` +
  side_effect）でラップし、実procインスタンスを捕捉。実claudeは起動しない（bash直接）
- `test_normal_exit_closes_stdout_after_reap` — `bash -c 'echo hi'`・timeout無効 →
  戻り値 `(0, _)`・`proc.stdout.closed`・`poll() is not None`
- `test_timeout_path_closes_stdout_after_reap` — `bash -c 'sleep 30'`・`timeout_min=0.01` →
  `("timeout", _)`・closed・reap済み
- `test_keyboard_interrupt_path_closes_stdout_after_reap` — `handle_stream_line` を
  `side_effect=KeyboardInterrupt` でpatch・子は1行echo後sleep → `assertRaises`・closed・reap済み

## テスト実行結果

| 実行 | 結果 |
|---|---|
| Phase 1後 `python3 -m unittest tests.test_batch_loop` | 131件 OK（既存122+新規9） |
| Phase 1後 全スイート `python3 -m unittest discover -s tests` | 793件 OK |
| Phase 2後 `python3 -m unittest tests.test_batch_loop` | 134件 OK（+close側3件） |
| Phase 2後 全スイート | 796件 OK・failed 0 |
| Phase 2後 `-W error::ResourceWarning` 付き batch_loopスイート | 134件 OK |

- AC3対象の `test_timeout_terminates_child_and_stops`・`test_sigint_terminates_child_and_exits_130`
  を含む既存テストはすべて無改修で通過（テストファイルの既存行への変更はゼロ、追加のみ）
- 副次的観測: Phase 1時点の全スイート実行で出ていた未closeパイプ由来の `ResourceWarning` が
  Phase 2適用後に消滅（grep 0件）。AC2の実効性の傍証

## 受け入れ条件セルフチェック

- AC1: 接頭辞ロジック実装済み・単体8件+E2E 1件で検証 → 充足
- AC2: 全経路（正常・timeout・KeyboardInterrupt・想定外例外）でfinally close。
  想定外例外経路のみ直接テストなし（設計書§4(3)のテスト一覧も3経路指定。finally構造で保証）
- AC3: 既存テスト無改修・全796件通過 → 充足
- AC4: 新規12件（表示8+E2E 1+close 3）すべてgreen → 充足

## 残リスク（設計書§6の再掲＋実装時所見）

- 実スキーマでのフィールド位置（Unknown 1）が両候補とも外れる可能性は残る（表示専用・
  フェイルセーフのため回帰なし。人間監視パイロット実行 docs/batch-loop.md V-4 で実機確認予定）
- `reader.join(timeout=5)` 超過の病的ケースではread中fdへのcloseとなりうるが、
  本環境で実測無害（investigation.md 詳細3節）かつfdリーク放置より安全側という設計判断どおり
