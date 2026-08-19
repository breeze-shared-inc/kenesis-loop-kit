# KLK-008 レビュー詳細（reviewer）

- 実施日: 2026-08-19
- 記録: orchestrator代筆（reviewerはWrite/Editツールを持たないため）
- 対象: `feature/KLK-008-subagent-prefix-pipe-close`（worktree: kenesis-loop-kit.wt/KLK-008）
- コミット: 2dab9d6（Phase 1）・de1a081（Phase 2）・056cea8（実装レポート）・165f4c8（testerテスト追加）
- 結果: **approved**

## 1. 事前確認

- tester Quality Gate: pass（docs/reports/KLK-008/test-report.md）。レビュー時に独立再実行して裏取り: `python3 -m unittest discover -s tests` 797件 OK（31.2s）、`python3 -W error::ResourceWarning -m unittest tests.test_batch_loop` 135件 OK、`git status --porcelain` 出力なし（worktreeクリーン）
- SPEC突き合わせ: spec_version "n/a"（Kit自身の運用改善）のため対象外。要件の正はチケットAC4件

## 2. 設計整合（観点1）

- `_subagent_prefix()`: 設計書§4(1)の確定コードと実装が一致。truthy判定（`parent_tool_use_id: null` 明示で非発火）・トップレベル/message内両対応・`isinstance(msg, dict)` ガード・ラベル連鎖 `subagent_type`（トップ→message内）→`name`→`"subagent"` すべて設計どおり
- assistant/user分岐: 行生成より先に `prefix = _subagent_prefix(evt)` を評価し、tool_use/tool_result の各行へ前置。分岐の並べ替えなし。text-only は従来どおり `None`（表示対象を拡大しない）。フォールバック分岐（`"parent_tool_use_id" in evt`）は無変更で残置
- `run_session()`: 設計書§4(2)の全体像と一字レベルで一致。差分は「`return code, ...` のtry内移動」と「finally追加」のみ。whileループ本体・except節・`_reader_thread`・`_terminate`・`handle_stream_line` は無変更
- 却下案の混入なし: `with Popen` 不使用・readerスレッド自身のclose不使用・キー存在判定不使用・フォールバック分岐の移動なしを差分で確認

## 3. AC充足（観点2）

| AC | Phase表カバー | 実証 |
|---|---|---|
| AC1（接頭辞） | Phase 1 | 単体8件（発火・null非発火・message内配置・ラベル連鎖2段・複数行・text-only）+ E2E 1件（フェイクclaude経由で `[subagent:investigator] [tool] Read(` を実プロセス出力に確認） |
| AC2（pipe close） | Phase 2 | `TestRunSessionPipeClose` 3件（正常・timeout・KeyboardInterrupt）で `proc.stdout.closed` と `poll() is not None`（reap済み）を実bash子プロセスでアサート |
| AC3（既存テスト無改修通過） | 両Phase完了条件 | `git diff develop...HEAD -- tests/` 純追加のみ（実削除0行、tester機械確認+レビューで差分目視）。timeout/SIGINT E2E含む全既存テストgreen |
| AC4（実証テスト追加） | 両Phase | 上記11件+tester補完1件（message非dict防御）。いずれも出力・状態を検証する実質的テスト |

## 4. リグレッション・副作用（観点3・5）

- メインエージェント表示: `parent_tool_use_id` 非同伴イベントでは `prefix == ""` となり出力は旧来と完全一致（既存TestRenderEventの `assertEqual` 系が無改修greenであることが裏付け）
- 外部契約: 引数・戻り値 `(exit_status, elapsed_sec)` 不変。elapsedはreturn式評価時（finally実行前）に確定し、join追加の影響なし
- timeout/SIGINT外形: timeout経路の `return "timeout"` はtry内にありfinallyを通過してから復帰。SIGINT経路はexcept節の `_terminate` 後にfinallyのpollがスキップ（reap済み）されjoinは即時EOF。既存E2Eの所要時間上限アサーション（elapsed < 20/25）も無改修で通過
- 例外マスキング: finally内の3操作は実質非送出（`_terminate` は冒頭poll済みならreturn・TimeoutExpiredは内部で握る、`join(timeout)` は非送出、`TextIOWrapper.close()` は冪等）。KeyboardInterrupt再送出との相互作用も、finallyが再送出前に走るだけで元例外を置換しない。finally実行中の二度目のCtrl-C窓（ワーストjoin 5秒）は従来の `_terminate` 内wait(10)窓と同質で新規リスクではない
- 二重close: `proc.stdout` をcloseする箇所は追加したfinallyのみ。`close()` 自体も冪等で、GC/`Popen.__del__` との重複も無害
- daemon reader: join(5)超過時もdaemon=Trueのためインタプリタ終了を妨げない

## 5. Medium指摘の詳細

**(1) join(5)超過時の最終手段closeにおける理論的ハング可能性（非ブロッキング）**

- 病的ケース: 子claudeが孫プロセスを残し（例: SIGKILL後も生存するバックグラウンドプロセスがstdout writer側fdを継承）、readerが `readline()` で5秒超ブロックしたままjoinが超過した場合、メインスレッドの `proc.stdout.close()` はCPythonのバッファードIOロック（ブロック中のreadが保持）の解放を待ち、run_sessionが復帰しない可能性がある。旧来の挙動（fdリークして復帰継続）との交換になる
- investigation.mdの実測（reader側が例外なくEOF受領）は本人注記どおり「限定的な合成再現」であり、この特定のロック競合窓を保証するものではない
- 非ブロッキングと判断した理由: (a) 発生には孫プロセスのwriter継承+5秒超ブロックという複合的な病的条件が必要で実害未観測、(b) 設計§3方針5・§6リスク表が最終手段closeを意識的に受容済み（人間承認プロセスを経た設計判断）、(c) 設計§8が「ハング系ならPhase 2単独revert」の復旧手順を事前に明記、(d) 既存timeout/SIGINT E2E・close3経路テストで通常経路の無害性は実証済み
- 推奨: docs/batch-loop.md V-4のパイロット実行（既に義務化済み）でclose挙動と接頭辞発火を併せて観察する

**(2) 想定外例外経路（finallyの `if proc.poll() is None: _terminate(proc)` TRUE分岐）の直接テストなし（非ブロッキング）**

- 3経路テストではいずれも子がreap済みでFALSE分岐のみ通過。TRUE分岐はfinallyのコード構造でのみ担保
- 設計書§4(3)テスト一覧・§6リスク表が明示的にスコープ外とし、implementer/testerも同一認識を記録済み。従来コードでは同経路で子が残置されえたため、テストがなくとも方向としては安全側への改善

## 6. ロールバック（観点6）

- Phase 1（2dab9d6）は `_subagent_prefix`/render_event周辺（scripts 527〜595行付近）+ TestRenderEvent/TestBatchEndToEndへの追加、Phase 2（de1a081）は run_session周辺（664〜716行付近）+ 新クラス TestRunSessionPipeClose（別位置）で、hunkが重ならず相互依存なし。設計§8のPhase単位独立revertは実コミット構成で成立
- 056cea8・165f4c8 はレポート/テスト追加のみでrevert独立性に影響なし

## 7. 補足観察（対応不要）

- testerレポートが指摘した既存行 `content = ((evt.get("message") or {}).get("content")) or []` のtruthy非dict時 `AttributeError` はKLK-008無変更の既存挙動で、呼び出し元の例外握りつぶし契約（既存テストで検証済み）によりフェイルセーフ。スコープ外との判断は妥当
- `-W error::ResourceWarning` での `tests.test_batch_loop` green（Phase 2で未closeパイプ警告が解消）は、close実装が実際に効いていることの良い傍証
