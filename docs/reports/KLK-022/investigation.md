# KLK-022 調査レポート (investigator)

## 0. 実施した実測（empirical）

- `python3 -m unittest discover -s tests` を本セッションで実行 → **`Ran 736 tests ... OK`**（失敗0件）。チケット本文AC5の「現行461件」は起票時点（2026-08-16, KLK-003完了時）の陳腐化した数値であり、現在のdevelop HEADでの実測は**736件**。KLK-021は586件（461+新規)ではなく実測581件を基準に採用しており、KLK-019のtest-report.mdでは735件PASSと記載があった。以降の追加チケットで+1され736件になったと推測される（この推測は一般知識ではなくコミット履歴からの推定＝codebase）。

---

## 1. `.claude/commands/triage.md` の現状（精読結果）

- 手順1（該当箇所引用）:
  `1. tickets/active/ の全チケットを読み取り、\`status = blocked\` かつ条件（経過日数またはID一致）を満たすチケットを一覧表示する（ID・タイトル・ブロッカー内容・\`updated\` からの経過日数）`
  → KLK-003がstart-loop.md/orchestrator.mdで解消したのと同じ「全件フルリード→LLMでフィルタ」パターンがそのまま残存している（KLK-003設計書§2が指摘した現象と同型）。
- **重要な発見（単純な文言置換では済まない構造上の制約）**: 手順1は「ID・タイトル・ブロッカー内容・経過日数」の一覧表示を要求しているが、`scripts/list_tickets.py` の出力列は `id/status/priority/tti/rti/rtv/updated` のみで、**タイトルとブロッカー内容は含まれない**（`build_row()` 実装で確認、`scripts/list_tickets.py:85-93`）。したがって「手順1をCLI呼び出しに置換するだけ」では要求列を満たせず、①CLIでstatus/updatedのみによる絞り込み（候補ID抽出）→②候補IDのみ個別フル読み取り（タイトル・ブロッカー内容・経過日数の表示はここで行う）という2段階への手順分割が必要になる。KLK-003の「1件のみフル読み取り」と同じ思想だが、triageは対象が0件・1件・複数件になりうる点が異なる（orchestratorの「必ず1件選ぶ」とは性質が違う）。
- 手順2〜5（0件終了・人間への三択確認・実行・結果報告）は「対象を特定した後」の処理であり、CLIの出力列だけでは完結しない前提の手順のため、これらは変更不要と考えられる（KLK-003が手順2〜5相当を変更しなかったのと同型の判断）。
- 引数仕様（`/triage`, `/triage 7`, `/triage APP-003`）は、CLIに絞り込み機能が無い（後述§3）ため、現状通り「LLMがCLI出力のupdated列を読んで経過日数を計算し閾値/ID一致を判定する」という運用のまま変わらない見込み（start-loop.mdの現行手順と同じパターン）。

## 2. `.claude/commands/start-loop.md` のKLK-003改訂内容（参考にすべきパターン）

- 起動時チェックリスト冒頭に、一覧CLIは**必ずメインworktreeで実行**という注記が既に追加済み（KLK-021で追記。§7参照）:
  `本チェックリスト・ループ実行手順で使用する一覧CLI（\`scripts/list_tickets.py\`）は、必ずメインworktree（orchestratorの作業ツリー）で実行すること（worktree内から実行するとcwd依存で対象チケットを取り違える。詳細はKLK-021の設計を参照）。`
- 「14日超blockedチケットの検出」項目（KLK-003改訂後の実文言）:
  `\`python3 scripts/list_tickets.py\` の一覧（status・updated列）から \`status = blocked\` かつ \`updated\` から14日以上経過しているチケットを抽出する（個別チケットのフル読み取りは不要）。該当チケットがあれば \`.claude/commands/triage.md\` の手順（再開 / クローズ / 期限延長の三択を人間に確認）でトリアージしてからループへ進む。`
  → **この最後の一文が「triage.mdの手順」全体（手順1〜5）を指しており、手順1（検出）を再実行してよいのか/スキップすべきなのかを明示していない**。これがKLK-022 AC2が求める「文面上の二重検出防止」の具体的な欠落箇所。
- 「ループ実行手順」手順1・「in_progress上限チェック」も同様にCLI利用へ改訂済み（`(この時点では個別チケットのフル読み取りは行わない)` という言い回しが繰り返し使われている＝triage.md側でも同じ言い回しを踏襲するのが自然）。
- ドキュメント差分の記述形式（変更前/変更後を一字一句引用）は `docs/designs/KLK-003.md` §4「ドキュメント差分」がテンプレート。KLK-022の設計でも同形式の採用が前例と整合する。

## 3. `scripts/list_tickets.py` のCLI仕様

- 出力列: `id, status, priority, tti(tester→implementer), rti(reviewer→implementer), rtv(reviewer→investigator), updated` の7列＋凡例行＋対象パス行（KLK-021で追加）＋件数サマリ。**タイトル・ブロッカー内容の列は無い**。
- **フィルタ機能は一切無い**。CLIは意図的に「パスを表す位置引数・オプション引数を一切持たない」設計（docstring・`scripts/list_tickets.py:11-20`）。これは`guard_bash_writes.py`の`mentions_guarded()`を発火させないための必須制約であり、KLK-003設計書§3で明記・KLK-021のT4（`TestNoPositionalPathArguments`、argparse不使用・sys.argv非参照の固定テスト）で機械的に固定済み。**triage.md向けに`--status=blocked`や`--days=14`のような絞り込み引数を新設する提案は、この制約に抵触するため不採用が妥当**（KLK-003/KLK-021の設計判断と整合。事実に基づく強い示唆であり、最終判断はarchitect）。
- 経過日数の計算・ID一致判定は、CLIではなく**呼び出し側（LLM）がupdated列の文字列を読んで計算する**運用（start-loop.mdの現行実装がそうなっている。CLI側にdatetime処理は無い）。同じ運用をtriage.mdにも踏襲するのが唯一の非破壊的な選択肢。
- 終了コード: `tickets/active/`不在時のみ1、それ以外は常に0（ERROR行があっても0）。

## 4. start-loop → triage の委譲経路（二重検出の具体的構造）

- start-loop.mdの「14日超blockedチケットの検出」チェックリスト項目は、既に`list_tickets.py`を実行し、status/updated列から候補IDをLLM推論で抽出済み（§2引用の通り）。
- その直後、`「.claude/commands/triage.md の手順（再開 / クローズ / 期限延長の三択を人間に確認）でトリアージしてからループへ進む」`と記述されており、**「triage.mdの手順」という表現がtriage.mdの手順1〜5全体を指す**。triage.md手順1は現状「tickets/active/ の全チケットを読み取り、条件を満たすチケットを一覧表示する」という**独立した検出ロジック**であるため、この委譲文言のまま読めば、start-loopが既に検出した同じ候補を、triage.md手順1が（現状は全件フルリードで、改訂後はCLI再実行で）**もう一度検出し直す**構造になっている。二重負荷の実体は「同じ`list_tickets.py`呼び出し＋同じLLMフィルタ推論を2回行う」ことであり、改訂後もこの構造自体を直さない限り解消しない。
- 一方、`/triage`は**start-loopを経由せず単体でも実行できる**（triage.md冒頭：「ループを起動せずにこのコマンド単体で実行できます」）。この経路では検出はtriage.md自身が担うほかない。したがって改訂は「start-loop経由で委譲された場合は候補リストをそのまま引き継ぎ手順1をスキップ／単体`/triage`実行時は手順1でCLI検出を行う」という**2経路対応**が必要（AC2の「二重検出を避ける」とtriage.md既存要件「単体実行可能」の両立が設計上の要点）。

## 5. `docs/designs/KLK-003.md` の設計方針・テスト設計

- 設計方針の要点: ①別ファイルCLI新設（`_ticket_lib.py`への機能追加ではない）②パス引数を持たない（guard_bash_writes非干渉のため。§3で詳述・最重要制約）③プレーンテキスト出力（JSON不採用）④priorityソートはCLI側で行わない（LLM側の推論に委ねる）⑤malformedなfrontmatterは黙ってスキップせずERROR行で可視化。
- `tests/test_klk003_doc_wiring.py`（KLK-021でT2追加済み・現在171行）は、コード実行されないドキュメント文言改訂（AC2/AC3/AC5）を、見出し単位でセクションを抽出し「CLI呼称文字列の存在」「旧・全件フルリード文言の不在（回帰ガード）」「手順2〜5の不変」「ポリシー表追加行が表の最終行であること」を**部分文字列の安定した特徴**で機械検証するアプローチ。KLK-022のAC4（機械検証テストの要否判断）は、このファイルの手法をtriage.mdにも同様に適用するのが直接の前例。
- **ファイル名の論点**: `test_klk003_doc_wiring.py`という名称は「KLK-003」固有だが、KLK-021（別チケット）のT2テストも同ファイルに追加された前例がある（`docs/designs/KLK-021.md`§4）。したがってKLK-022でも同ファイルへ`TestTriageMd`的なクラスを追加する／新規`tests/test_klk022_doc_wiring.py`を切る、のいずれも前例上ありうる。判断はarchitectに委ねる材料として提示する。

## 6. `docs/policy-registry.md` の該当行

- 関連する行が2つ存在する（役割が異なる点に注意）:
  1. `| 14日blockedトリアージ | triage.md | orchestrator / start-loop / /triage | orchestrator.md Responsibilities / start-loop.md 起動時チェックリスト |`（triage.mdというポリシー定義自体の行。list_tickets.pyへの言及なし）
  2. `| orchestratorのチケット一覧取得（frontmatterスキャンCLI・パス引数を持たない設計） | scripts/list_tickets.py（実装の正はdocs/designs/KLK-003.md） | orchestrator / start-loop | orchestrator.md Ticket Integration / start-loop.md 起動時チェックリスト・ループ実行手順1 / tests/test_list_tickets.py |`（KLK-022チケット本文AC6が名指しする「KLK-003が追加した一覧CLIの行」はこちら）
- 行2の「転記先・強制」欄は現状 `tests/test_list_tickets.py` のみを挙げており、実際に文書改訂（orchestrator.md/start-loop.md）を機械検証している`tests/test_klk003_doc_wiring.py`や、KLK-021で追加された`tests/test_guard_bash_writes.py`のT1・同ファイルのT2は**記載されていない**（codebase上の事実。過去にも追随更新が漏れている前例がある、という参考情報）。AC6の「triage.mdを加えるか」判断は、この既存の運用実態（完全な追随更新が徹底されていない）も踏まえてarchitectが決める事項であり、投機的な推奨はしない。

## 7. KLK-021の変更内容・「メインworktree」注記の要否判断材料

- KLK-021（`tickets/done/KLK-021_list_ticketsのcwd依存による無言0件の是正.md`、`docs/designs/KLK-021.md`）は既にdone。主な変更: `main()`のroot解決の`.resolve()`化、`format_target()`新設（出力冒頭に`対象: <絶対パス>`行）、T1〜T4テスト追加、**start-loop.md起動時チェックリスト冒頭**と**orchestrator.md Ticket Integration先頭項目末尾**への「本CLIは必ずメインworktreeで実行すること」の1文追記（両方とも実ファイルで確認済み）。
- **triage.mdには現在この注記が一切存在しない**（ファイル全文精読で確認、「worktree」という語自体が出現しない）。triage.md手順1が今後`list_tickets.py`を直接呼び出す設計になる以上（AC1）、orchestrator.md/start-loop.mdと同じ「メインworktreeで実行する」注記をtriage.mdにも追加するのが整合的、という材料は揃っている（cwd依存でtriage対象を取り違えるリスクは、start-loop経由でもtriage単体実行でも構造的に同一）。ただし、この注記を追加するか・どこに書くかはarchitectの設計判断であり、investigatorとして断定はしない。

---

## Required Output Format

**1. Findings**
- triage.md手順1は全件フルリードのまま。KLK-003が同型で解消した箇所と同一パターン。詳細: 本レポート§1
- CLI出力にタイトル・ブロッカー内容列が無いため、単純なCLI置換では要求列を満たせず「CLI検出→候補のみフル読み取り」への手順分割が必要
- start-loop→triage委譲は「triage.mdの手順」全体を指す表現のみで、手順1スキップを明示していない＝二重検出が構造上発生する
- /triageは単体実行可能なため、委譲経路とは別に単体実行時の自己検出手段（CLI利用）を維持する必要がある
- 詳細: 本レポート全文

**2. Evidence**
- codebase: `.claude/commands/triage.md`（手順1原文引用済み・全文精読）
- codebase: `.claude/commands/start-loop.md`（14日超blocked検出項目・メインworktree注記を確認）
- codebase: `scripts/list_tickets.py`（出力列・引数無し設計をコード確認）
- local_docs: `docs/designs/KLK-003.md`§3/§4/§9、`docs/designs/KLK-021.md`§4、`tests/test_klk003_doc_wiring.py`全文
- empirical: `python3 -m unittest discover -s tests` 実行 → 736件PASS（2026-08-18本セッション）

**3. Dependency Graph**
- triage.md 手順1 → scripts/list_tickets.py（新規依存・引数なし制約を継承）
- start-loop.md 起動時チェックリスト → triage.md（委譲。二重検出の接続点）
- triage.md → tests/test_klk003_doc_wiring.py or 新規test_klk022_doc_wiring.py（AC4のテスト設計）
- docs/policy-registry.md 該当2行（14日blockedトリアージ行／list_tickets.py行）→ triage.md

**4. Risk Areas**
- CLIへ絞り込み引数（--days等）を新設するとguard_bash_writes.pyのmentions_guarded非干渉前提が崩れる（KLK-003/KLK-021の中核制約）
- タイトル・ブロッカー内容がCLI出力に無いため、手順1置換が不完全だと受け入れ条件の列挙要求を満たせない
- start-loop delegate時とtriage単体実行時の2経路を両立しないと、AC2（二重検出防止）とtriage.md既存機能（単体実行）が矛盾する
- テストファイル命名（test_klk003_doc_wiring.py拡張 or 新規ファイル）は前例が両方ありarchitect判断が必要

**5. Assumptions**
- 経過日数計算・ID一致判定は今後もLLM側推論（updated列を読んで計算）で行う運用が継続すると仮定（CLIに日付計算機能を追加しない前提。start-loop.mdの現行運用からの推定）
- 手順2〜5（0件終了・三択確認・実行・報告）はKLK-022のスコープ外で変更不要と仮定（KLK-003がstart-loop.md手順2〜5を不変としたのと同型判断）

**6. Unknowns**
- なし（人間確認を要するブロッカーは無し）。ただしAC6（policy-registry表への追記要否）とテストファイル命名は、investigatorが断定せずarchitectの設計判断に委ねるべき事項として明示する

---

### 参照した主要ファイル（絶対パス）
- `/home/bzg55/workspace/breeze/kenesis-loop-kit/tickets/active/KLK-022_triageの全件フルリードを一覧CLIへ統一.md`
- `/home/bzg55/workspace/breeze/kenesis-loop-kit/.claude/commands/triage.md`
- `/home/bzg55/workspace/breeze/kenesis-loop-kit/.claude/commands/start-loop.md`
- `/home/bzg55/workspace/breeze/kenesis-loop-kit/scripts/list_tickets.py`
- `/home/bzg55/workspace/breeze/kenesis-loop-kit/docs/designs/KLK-003.md`
- `/home/bzg55/workspace/breeze/kenesis-loop-kit/docs/designs/KLK-021.md`
- `/home/bzg55/workspace/breeze/kenesis-loop-kit/tests/test_klk003_doc_wiring.py`
- `/home/bzg55/workspace/breeze/kenesis-loop-kit/docs/policy-registry.md`
- `/home/bzg55/workspace/breeze/kenesis-loop-kit/tickets/done/KLK-021_list_ticketsのcwd依存による無言0件の是正.md`
- `/home/bzg55/workspace/breeze/kenesis-loop-kit/tickets/done/KLK-003_orchestratorチケット読み取りのfrontmatterスキャン化.md`
