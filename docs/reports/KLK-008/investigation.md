# KLK-008 調査レポート（investigator）

- 実施日: 2026-08-19
- 記録: orchestrator代筆（investigatorはWrite/Editツールを持たないため）
- チケット: tickets/active/KLK-008_batch-loopリアルタイム表示のサブエージェント区別とストリーム後処理の堅牢化.md

## Findings

- `render_event()`（`scripts/batch_loop.py:530-588`）は `etype in ("assistant","user")` 分岐（565-579行）が `parent_tool_use_id` 分岐（581-586行）より先に評価され、無条件でreturnするため、たとえ `evt` に `parent_tool_use_id`/`subagent_type` が含まれていても到達しない。これがAC1の対象。
- KLK-007 VS-2実測（`docs/batch-loop.md:133`）により、サブエージェント自身の発話は実際に `type:"assistant"/"user"` に `parent_tool_use_id`・`subagent_type` を伴って届くと**確認済み**（単発Task委譲1件のみの実測）。よって本問題は仮説ではなく実測確認済みの表示欠落。
- `run_session()`（594-684行）は `proc.stdout` を明示closeしておらず、GC任せ（AC2対象）。`_reader_thread`（635-643行）も `finally` で `out_queue.put(("eof",None))` するのみでpipe closeなし。
- 既存テストで `parent_tool_use_id`/`subagent_type` を持つ `assistant`/`user` イベントを検証するテストは無い（`TestRenderEvent`のassistant/userテスト群にこのフィールドを含む事例なし）。追加時の新規テストが必要（AC4）。
- close追加箇所とタイミング次第で `_reader_thread` とのスレッド競合リスクあり（詳細はRisk Areas・詳細3節）。

## Evidence

- `codebase`: `scripts/batch_loop.py:530-588`（render_event分岐順序）、`594-684`（run_session/_reader_thread/_terminate、pipe管理箇所）を直読確認。
- `local_docs`: `docs/batch-loop.md:133`（VS-2実測: assistant/user型に`parent_tool_use_id`・`subagent_type`同伴の記述）。`tickets/done/KLK-007_batch-loopのリアルタイム化と旧方式の別コマンド復旧.md:80`（reviewerメモMedium2件の原文）。
- `local_docs`: `tests/test_batch_loop.py:537-614`（TestRenderEventの既存assistant/user・fallback分岐テスト、いずれも`parent_tool_use_id`を含まない）、`1056-1150`（タイムアウト・SIGINTのE2Eテスト実体）。
- `empirical`（本調査時実施）: Python 3.12.3にて `Popen.__exit__` のソース確認、および別スレッドが `pipe.readline()` でブロック中に主スレッドから `pipe.close()` した場合の挙動を実測（本環境ではreaderが例外なくEOFを受け取り正常終了。ただしこれは限定的な合成再現であり、本番のタイミング窓とは異なる可能性がある旨を明記。詳細3節参照）。

## Dependency Graph

- `render_event`/`run_session`/`_reader_thread`/`_terminate` は `scripts/batch_loop.py` 内で自己完結。他ファイルからのimportはテスト（`tests/test_batch_loop.py`）のみ。
- `.claude/commands/batch-loop.md` は `--dry-run` のみ代行し、stream-json表示ロジックには触れない。`/batch-loop-inline` はbatch_loop.pyを一切呼ばない別経路（`.claude/commands/batch-loop-inline.md:3`）。
- `docs/batch-loop.md`・`docs/batch-loop-inline.md` に `[subagent]`/`[tool]`/`[result]` 等の表示例の記載は無し（grep確認済み・0件）→ 表示変更によるドキュメント記載との衝突は無い。
- `scripts/list_tickets.py` はbatch_loop.pyの設計パターンをコメントで参照するのみで機能依存なし。
- CHANGELOG.md:15に「`run_session()`の外部契約（引数・戻り値）は不変」と明記 — AC3が求める契約維持の既存合意はここが根拠。

## Risk Areas

- **表示変更**: 既存assistant/userテスト（`test_assistant_tool_use`等、537-590行）は`parent_tool_use_id`キーを含まないため、prefix追加を「`parent_tool_use_id`存在時のみ」に限定すれば既存アサーション（`assertEqual`含む）は無改修で通過可能と判断（衝突なし）。
- **pipe close競合**: `_terminate(proc)`は内部で`proc.wait()`を完了させてから返るため、`_terminate`呼び出し後にcloseする実装順であれば競合窓は実質ほぼ無い。だが`with subprocess.Popen(...) as proc:`で関数全体を包む素朴な実装だと、`__exit__`が`self.stdout.close()`を無条件・無同期に呼ぶ（Python 3.12.3ソースで確認済み）。closeの位置づけ（`_terminate`後か、reader thread join後か）を設計判断で明示する必要あり。
- 本調査の競合再現実験はタイミングを人工的に作った限定的検証であり、本番の`_terminate`直後という極めて短い窓でも同一挙動が保証されるとは言い切れない（OS/Pythonバージョン依存の一般的注意点、根拠general_knowledge）。

## Assumptions

- `parent_tool_use_id`/`subagent_type`は`assistant`/`user`イベントのトップレベル（`evt`直下、`message`の外）に存在すると推定（既存フォールバック分岐が`"parent_tool_use_id" in evt`をトップレベル判定している設計踏襲に基づく推測。docs/batch-loop.mdの記述はJSON構造の具体例を伴わない）。
- サブエージェント名の取得元は`evt.get("subagent_type")`が第一候補（`system/task_started`分岐で既に同名フィールドを使用）。既存フォールバック分岐の`evt.get("name")`は実スキーマでの裏付けなし（テスト専用の合成値）。

## Unknowns

- **Unknown 1**: `assistant`/`user`イベントの`parent_tool_use_id`/`subagent_type`の正確なJSON構造（トップレベルか`message`内か）を示す生JSONLの実例がrepo内に存在しない（docs/batch-loop.mdはprose記述のみ、KLK-007のVS-2実測は「単発Task委譲1件」の限定的な検証）。architect/implementerが実装前に検証タスク（VS的な軽量プローブ）を要するか、既存の`subagent_type`優先ロジックの延長で進めるかは人間/architect判断事項。
- **Unknown 2**: サブエージェント種別（investigator/architect/implementer/tester/reviewer等、KLK-002のモデル割当対象）ごとに`subagent_type`の命名・存在が一貫しているかは未検証（VS-2はgeneral-purposeサブエージェント1件のみ）。
- **Unknown 3**: pipe close追加の実装順序（`_terminate`後 vs readerスレッドjoin後 vs readerスレッド自身がclose）についてdocs/designs/KLK-007.mdに設計判断の記載なし（新規設計判断が必要）。

Unknownsは3件（いずれも致命的なブロッカーではなく、architectが設計判断で解消可能な性質。人間確認が必須なレベルのUnknownsではないと判断）。

## 次エージェント（architect）への申し送り

Unknownsは設計判断で解消可能な範囲のため、architectへの引き継ぎを推奨する。

1. prefix追加条件を `parent_tool_use_id in evt` 存在時に限定する実装（既存テスト無改修の鍵）
2. pipe closeは `_terminate()` 完了後（子プロセスreap後）に行う順序を設計書に明記すること
3. 新規テストは実際の `subagent_type`+`parent_tool_use_id` 同伴イベントをフェイクclaudeで再現するE2Eテスト（`TestBatchEndToEnd`パターン踏襲）を推奨

---

## 詳細

### 1. render_event() 分岐順序の詳細（`scripts/batch_loop.py`）

```
530: def render_event(evt):
539:     etype = evt.get("type")
541:     if etype == "system":                     # ← 1番目に評価
543-556行: init / task_started / task_notification を処理してreturn（Noneも含む）
559:     if etype == "stream_event":                # ← 2番目
561-563行: text_delta処理
565:     if etype in ("assistant", "user"):          # ← 3番目・問題の分岐
566-579行: message.content の tool_use/tool_result のみ処理してreturn
              **parent_tool_use_id/subagent_typeを一切見ない**
581:     if etype in ("task_started","task_notification") or "parent_tool_use_id" in evt:
              # ← 4番目。実スキーマ上は etype=="assistant"/"user" の場合ここに
              #   到達しない（3番目で既にreturn済みのため）
582-586行: サブエージェント接頭辞付与ロジック（label = subagent_type or name or "subagent"）
588:     return None
```

結論: `parent_tool_use_id`分岐（581-586）は、`etype`が`"assistant"`/`"user"`以外（例: `type`キー不在、または将来スキーマ変化時の未知type）のときのみ到達する。VS-2実測で確定した実スキーマ（`type:"assistant"/"user"` + `parent_tool_use_id`/`subagent_type`同伴）は3番目の分岐で必ず先取りされ、4番目には到達しない。これがKLK-007 reviewerメモMedium(1)・KLK-008 AC1の対象そのもの。

### 2. run_session()のstdout pipe管理詳細

```
646: def run_session(cmd, root, timeout_min):
651-654: proc = subprocess.Popen(cmd, cwd=..., stdin=DEVNULL,
                                  stdout=subprocess.PIPE, text=True,
                                  bufsize=1, errors="replace")
          # ← ここで生成されたproc.stdoutの明示close箇所は関数内に一切ない
655-658: out_queue = queue.Queue(); reader = threading.Thread(
             target=_reader_thread, args=(proc.stdout, out_queue), daemon=True)
661-684: try:
             while True:  # メインループ。deadline超過でterminateしてreturn "timeout",...
                 kind, payload = out_queue.get(timeout=remaining)
                 if kind == "eof": break
                 handle_stream_line(payload, state)
             code = proc.wait()
         except KeyboardInterrupt:
             _terminate(proc); raise
         return code, elapsed
```

`_reader_thread`（635-643行）:

```
def _reader_thread(pipe, out_queue):
    try:
        for line in iter(pipe.readline, ""):
            out_queue.put(("line", line))
    finally:
        out_queue.put(("eof", None))   # ← closeなし。sentinelのみ
```

`_terminate(proc)`（620-632行）は `proc.terminate()` → `proc.wait(timeout=10)` → (TimeoutExpired時) `proc.kill()` → `proc.wait(timeout=5)` と、**必ず子プロセスの終了を待ち切ってから返る**。つまりtimeout/SIGINTいずれの経路でも、`run_session()`が`_terminate(proc)`から制御を戻された時点で子プロセスは既にreap済み＝OS側でstdout書き込み側は既に閉じている。この事実は、「`_terminate()`完了後にcloseする」実装順序であれば競合窓が実質的に極小であることの根拠になる。

### 3. 実測: Popen.__exit__の挙動とclose/reader競合実験（本調査で実施・Python 3.12.3・Linux/WSL2環境、2026-08-19実施）

`inspect.getsource(subprocess.Popen.__exit__)` の結果:

```python
def __exit__(self, exc_type, value, traceback):
    if self.stdout:
        self.stdout.close()
    if self.stderr:
        self.stderr.close()
    try:
        if self.stdin:
            self.stdin.close()
    finally:
        if exc_type == KeyboardInterrupt:
            if self._sigint_wait_secs > 0:
                try:
                    self._wait(timeout=self._sigint_wait_secs)
                except TimeoutExpired:
                    pass
            self._sigint_wait_secs = 0
            return
        self.wait()
```

`with subprocess.Popen(...) as proc:` を採用すると、`with`ブロックを抜ける（`return`/例外いずれでも）タイミングで無条件に`self.stdout.close()`が呼ばれる。KeyboardInterrupt伝播時は特殊分岐（`self.wait()`をスキップして即`return`）を通る点も差異として存在（テスト側で`proc.wait()`呼び出し回数等をモックで厳密検証している場合は影響し得るが、現行テストはE2Eの外形（終了コード・出力文字列・所要時間）のみを見ているため直接の影響は無いと判断）。

close/reader競合の合成実験（別スレッドが`pipe.readline()`でブロック中にメインスレッドから`close()`した場合）:

```python
proc = subprocess.Popen(["sleep","5"], stdout=subprocess.PIPE, text=True, bufsize=1)
# readerスレッドをブロッキングread中の状態にしてから
proc.stdout.close()  # ← メインスレッドから
```

結果: `close()`は例外を出さず正常終了し、reader側の`readline()`はEOF(`""`)を受けてforループを正常終了、`finally`の`("eof", None)`をqueueへput。例外は一切発生しなかった。

**この実験の限界（明記）**: (1) 意図的に0.3秒のsleepを挟んでreaderが確実にブロック中である状態を作った人工的な再現であり、本番の`_terminate()`直後という極めて短い競合窓と同一とは限らない。(2) 本環境（Python 3.12.3・Linux系カーネル）固有の挙動であり、他のPython実装・OSでの同一性は未検証（一般にPOSIXの「別スレッドがブロッキングread中のfdをclose()する」挙動は移植性の低い注意点として知られる — この一般論はgeneral_knowledge由来であり本実験では反証も確証もしていない）。(3) 従って「naive `with`化は安全」と断定はできず、architectが実装順序（`_terminate()`完了後にcloseする、またはreader thread自身がcloseする、のいずれか）を設計として明示することを推奨する。

### 4. 既存テストへの影響範囲（`tests/test_batch_loop.py`）

- `TestRenderEvent`（452-614行）: `test_assistant_tool_use`(537)・`test_user_tool_result`(548, `assertEqual`厳密一致)・`test_assistant_multiple_blocks_joined_by_newline`(557)・`test_assistant_unrecognized_block_type_returns_none`(567)・`test_assistant_content_not_list_returns_none`(574)・`test_assistant_missing_message_returns_none`(579)・`test_assistant_content_block_not_dict_is_skipped`(582) — いずれも`parent_tool_use_id`キーを持たないイベントのみを検証しており、prefix追加ロジックを「`parent_tool_use_id`存在時のみ発火」に限定すれば無改修で通過する。
- `test_subagent_task_started_with_text`(592)・`test_subagent_task_notification_without_text_uses_etype`(599)・`test_subagent_parent_tool_use_id_marks_as_subagent`(603, `etype`が`"assistant"/"user"/"system"/"stream_event"`のいずれでもない合成イベント) — 既存フォールバック分岐(581-586)のテストで、`assistant`/`user`向けの新ロジックとは独立（`etype`が異なるため衝突なし）。
- `TestBatchEndToEnd`内の`test_stream_json_lines_rendered_realtime`(827)・`test_stream_json_subagent_event_rendered`(841)・`test_stream_json_subagent_lifecycle_real_schema_rendered`(852) — フェイクclaude(`bash`)が`echo`でJSONL行を模擬し、実プロセス経由で`run_session`→`handle_stream_line`→`render_event`を通す統合テスト。pipe close変更はこれらの`assertIn`検証（出力文字列）に影響しないはずだが、closeタイミングを誤ると出力の一部が欠落する可能性はゼロではない（reader threadがEOF前に打ち切られるケースを作らないことが前提）。
- `test_timeout_terminates_child_and_stops`(1056行、`TestBatchEndToEnd`内): `--timeout-min 0.02`+`exec sleep 30`で`_terminate`経路を強制。`test_sigint_terminates_child_and_exits_130`(1118行、`TestSubprocessBehaviors`内): 実プロセスを`subprocess.Popen`で起動し`SIGINT`送信、`proc.communicate(timeout=20)`で回収。いずれも「異常終了」の文字列・終了コード・所要時間（`elapsed < 20/25`）のみを検証しており、pipe closeの有無自体を直接アサートしていない。したがって仕様上は無改修で通過可能だが、closeの実装がハング・例外を誘発しないことが前提条件（上記3節参照）。

### 5. ドキュメント記載への影響

- `docs/batch-loop.md`・`docs/batch-loop-inline.md`・`.claude/commands/batch-loop.md`・`.claude/commands/batch-loop-inline.md`に`[tool]`/`[result]`/`[subagent`等の具体的表示例・出力サンプルの記載は無し（grep確認、0件）。したがって表示接頭辞追加によるドキュメント修正は必須ではないが、`docs/batch-loop.md`「ヘッドレスセッションの挙動」節（VS-1・VS-2実測記録、117-134行）はKLK-007由来の実測記録であり、KLK-008での校正・新知見があれば同節への追記が将来的に妥当（architect判断事項、AC外）。

---

## 関連ファイルパス

- `scripts/batch_loop.py`（530-588行 render_event、594-684行 run_session/_reader_thread/_terminate）
- `tests/test_batch_loop.py`（452-614行 TestRenderEvent、790-945行 TestBatchEndToEnd、1056行 test_timeout_terminates_child_and_stops、1090-1150行 TestSubprocessBehaviors/test_sigint_terminates_child_and_exits_130）
- `docs/batch-loop.md`（117-134行 VS-1/VS-2実測記録）
- `docs/designs/KLK-007.md`（300-303行 fallback分岐の設計記述、127-148行 リーダースレッド設計方針）
- `tickets/done/KLK-007_batch-loopのリアルタイム化と旧方式の別コマンド復旧.md`（74-82行 reviewerメモMedium2件）

docs/SPEC.mdは本チケットの調査範囲外（REQ/SCR/IF-ID非引用の運用ツールフォローアップ）と判断し、フル読み取りは行っていない。
