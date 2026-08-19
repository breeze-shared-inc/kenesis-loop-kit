# KLK-008 テストレポート（tester）

- 実施日: 2026-08-19
- worktree: `kenesis-loop-kit.wt/KLK-008`（ブランチ `feature/KLK-008-subagent-prefix-pipe-close`）
- 対象コミット: 2dab9d6（Phase 1）・de1a081（Phase 2）・056cea8（実装レポート）

## 1. テスト実行結果

| 実行 | 件数 | 結果 |
|---|---|---|
| `python3 -m unittest discover -s tests`（追加前） | 796 | OK・failed 0 |
| `python3 -m unittest discover -s tests`（テスト追加後） | 797 | OK・failed 0 |
| `python3 -m unittest tests.test_batch_loop`（追加後） | 135 | OK・failed 0 |
| `python3 -W error::ResourceWarning -m unittest tests.test_batch_loop` | 134 | OK（ResourceWarningなし。implementer報告と一致） |

- discover実行時に出た `ResourceWarning`（`test_check_spec_structure.py` の `SPEC_TEMPLATE.md` 未close）は
  KLK-008対象外ファイル・既存の別チケット由来の事象であり本チケットの回帰ではない
- `git diff develop...HEAD -- tests/test_batch_loop.py` を `grep '^-' | grep -v '^--- '` で確認し、
  実削除行0件（純追加のみ）。AC3「既存テスト無改修」を機械的に確認済み

## 2. 受け入れ条件とテストの突き合わせ

| AC | 対応テスト | 結果 |
|---|---|---|
| AC1（サブエージェント接頭辞） | `TestRenderEvent` 単体8件（`test_assistant_subagent_tool_use_prefixed` 等） | green |
| AC2（pipe明示close） | `TestRunSessionPipeClose` 3件（正常・timeout・KeyboardInterrupt） | green |
| AC3（既存テスト無改修で全通過） | 全796→797件（追加1件除く既存796件が無改修） + `test_timeout_terminates_child_and_stops` / `test_sigint_terminates_child_and_exits_130` 個別確認 | green |
| AC4（変更を実証するテスト追加） | 上記AC1・AC2対応の11件 + tester追加1件 | green |

## 3. 設計書§9 重点エッジケースの網羅確認

| エッジケース | 対応テスト | 状態 |
|---|---|---|
| `parent_tool_use_id: null` 明示（非発火） | `test_assistant_parent_tool_use_id_null_not_prefixed` | カバー済み（implementer作成） |
| `message` が非dict（例外なくNone） | 既存 `test_assistant_missing_message_returns_none`（messageキー欠落）はあるが、「`parent_tool_use_id`実値＋`message`が明示的に非dict」の組み合わせは未カバーと判明 → **tester追加** `test_assistant_subagent_message_none_no_exception_returns_none` | カバー済み（tester追加後） |
| text-onlyブロック（Noneのまま） | `test_assistant_subagent_text_only_returns_none` | カバー済み（implementer作成） |
| timeout経路でのclose完了（run_session復帰時点でclosed） | `test_timeout_path_closes_stdout_after_reap` | カバー済み（implementer作成） |

補足調査: `message` が truthy な非dict値（例: 文字列・非空リスト）の場合、`_subagent_prefix()` 自体は
`isinstance` ガードで例外を出さないことを直接確認したが（Python REPLで実行確認）、`render_event()` の
既存の内容抽出行 `content = ((evt.get("message") or {}).get("content")) or []`（KLK-008で無変更の
既存行）はtruthy非dict値に対し `AttributeError` を送出する。ただしこれはKLK-008の変更対象外の
既存挙動であり（`git diff` で当該行が変更されていないことを確認済み）、実行時は呼び出し元の
例外握りつぶし（既存 `test_render_event_exception_is_swallowed` で検証済みの契約）でフェイルセーフ
となるため、本チケットのAC・スコープには含めずテスト追加を見送った。

## 4. カバレッジ

- リポジトリに `coverage` パッケージ導入なし（`pip show coverage` で未検出）。カバレッジツールでの
  数値取得は不可のため、変更行の目視トレースで代替する
- `_subagent_prefix()` の全分岐（truthy判定の発火/非発火、message内フォールバック、ラベル連鎖の
  4段全て、isinstance非dictガード）・`render_event()` assistant/user分岐の接頭辞適用（tool_use/
  tool_result・複数ブロック）は、いずれも既存＋追加テストで実行経路を確認済み
- `run_session()` finally節: `reader.join(timeout=5)` と `proc.stdout.close()` は3経路（正常・timeout・
  KeyboardInterrupt）すべてで実行・アサート済み。`if proc.poll() is None: _terminate(proc)` の
  TRUE分岐（「想定外例外」経路の多層防御）は3経路いずれでも子が既にreap済みのため実行されず、
  直接テストなし。これは設計書§4(3)のテスト一覧・§6リスク表で明示的にスコープ外とされた
  構造的保証（finallyのコード構造のみで担保）であり、実装レポートも同様に認識済み

## 5. リグレッション確認

- `render_event()`: 既存の `TestRenderEvent` 全項目（system/stream_event/assistant/user/フォール
  バック分岐）が無改修で通過。`prefix` が空文字になる既存イベント（`parent_tool_use_id` 非同伴）では
  出力が旧来と完全一致することを既存アサーションで確認
- `run_session()`: 外部契約 `(exit_status, elapsed_sec)` は不変。`test_timeout_terminates_child_and_stops`
  （timeout外形・所要時間上限）・`test_sigint_terminates_child_and_exits_130`（終了コード130）が
  無改修で通過し、finally追加による遅延・契約変化がないことを確認
- `-W error::ResourceWarning` 付き実行で `TestRunSessionPipeClose` を含む134件がOK
  （未closeパイプ由来の警告が解消されたことの傍証。implementer報告と一致）
