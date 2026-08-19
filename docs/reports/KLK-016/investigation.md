# KLK-016 investigation.md

## 1. check_loop_integrity.py の実装詳細

- Stop hookとして `.claude/settings.json` の `hooks.Stop`（matcher指定なし＝毎回発火）に登録。コマンドは `python3 "${CLAUDE_PROJECT_DIR:-.}/.claude/hooks/check_loop_integrity.py"`。
- `main()`（L155-196）の処理順:
  1. `lib.read_hook_payload()` でstdinのJSONを読む。dictでなければ即 `sys.exit(0)`（fail-open）。
  2. `stop_hook_active` が真なら即終了（無限ループ防止）。
  3. `cwd`（非str/空ならos.getcwd()にフォールバック）から `active_dir = cwd/tickets/active`、`done_dir = cwd/tickets/done` を組み立てる。
  4. `active_dir` が存在しなければ即終了（fail-open。ticketsディレクトリ自体が無い環境向け）。**docs/SPEC.mdの有無は一切参照されない。**
  5. `lib.load_events(cwd/tickets/.metrics.jsonl)` と `lib.load_state(cwd/tickets)`（`tickets/.metrics_state.json`）を読み込む。
  6. `active_dir/*.md`（`_index.md`除く）を`sorted(glob.glob(...))`で走査し `check_ticket()` を呼ぶ。
  7. `done_dir/*.md` を走査し `check_done_ticket_drift()` を呼ぶ（ドリフト検知のみ）。
  8. `problems` が1件でもあれば `{"decision": "block", "reason": ...}` をJSON標準出力し、そうでなければ無出力で `sys.exit(0)`。

- `check_ticket(path, events_by_ticket, state)`（L112-139）: frontmatter読み込み→`validate_schema`+`validate_retry_counts`→blockedセクション充足チェック→本文表同期チェック（`check_body_table_sync`）→**ドリフト検知**（`check_state_drift(fm, state.get(fm.get("id")))`）→L3差し戻し履歴照合（`lib.reconcile_rollbacks`）の順にエラー文字列を積み上げる。

- `check_state_drift(fm, record)`（L74-109）: サイドカーの最終観測値（`record`＝`state[ticket_id]`）とチケットfrontmatterの `status`/`retry_counts` を突き合わせる。`record`が無ければ（=このticket_idについて一度もrecord_metrics.pyが記録していない＝旧チケット等）照合をスキップ（fail-open）。status不一致・retry_counts減少をそれぞれ検出しエラー文字列を返す。**このロジックはticket_idをキーとするサイドカー構造に強く依存しており、SPEC.mdのような「単一ファイル・frontmatterなし」の対象には直接適用できない。**

- `check_done_ticket_drift(path, state)`（L142-152）: done/配下は全量検査せず `check_state_drift` のみ呼ぶ（アーカイブ済みチケットの巻き戻り検知に限定）。

- `blocker_section_filled` / `check_body_table_sync` はSPEC.md向けドリフト検知とは無関係（チケットのMarkdown構造前提）。

## 2. guard_spec_writes.py の実装詳細

- PreToolUse（matcher: `Write|Edit`）に `validate_ticket_state.py` と並んで登録（`.claude/settings.json` L104-118）。
- `is_spec(path)`（L37-41）: パスの `\`→`/` 正規化後、`.claude/`配下（または先頭が`.claude/`）を除外し、`rsplit("/", 1)[-1] == "SPEC.md"`（basename一致）で判定。ネストしたSPEC.md（`docs/expense/SPEC.md`等）も対象になる（`test_nested_spec_ask`で確認済み）。テンプレート（`SPEC_TEMPLATE.md`）はbasename不一致で対象外。
- `main()`: payloadがdictでない／`tool_input.file_path`が非str・空・`is_spec`不成立ならallow（`sys.exit(0)`、出力なし）。該当すれば `lib.emit_pretooluse_decision("ask", ...)` で`permissionDecision: ask`をJSON出力してexit 0。
- **「正規の変更経路」とは**: LLMがWrite/Editツールでdocs/SPEC.mdへ書き込もうとすると、このhookが`ask`を返し、Claude Codeのpermission systemが人間に確認プロンプトを出す。人間が許可すれば書き込みが実行される（=「diff承認を経た」正規経路）。`--dangerously-skip-permissions`起動時はaskが貫通する既知の限界がdocstringに明記されている。
- docstring末尾（L16-20）: 「注意: Bashツール経由の書き込み（リダイレクト・sed -i・インタプリタ等）はこのhookの対象外。guard_bash_writes.py（PreToolUse・Bash）がベストエフォートで遮断し、各エージェント定義のNeverルールで補強する（チケット側と異なりStop hookのドリフト検知は無い — SPEC.mdには観測サイドカーが存在しないため）。」— **本チケットの前提を実装者自身が明記した一次証拠。**

## 3. _ticket_lib.py の既存drift検知・状態保存の仕組み、SPEC.md用への転用可否

- `load_state(tickets_dir)`（L153-165）: `tickets_dir/.metrics_state.json` をJSONとして読み、dictでなければ`{}`。ファイル無し・パース失敗はいずれも`{}`（fail-open）。**キー構造は `{ticket_id: {"status":..., "ts":..., "retry_counts": {...}}}` を前提**（`check_state_drift`が`record.get("status")`/`record.get("retry_counts")`を直接参照）。
- `load_events(path)`（L167-186）: `.metrics.jsonl`を1行1JSONとして読み、不正行はスキップ。イベントは`{"ts":..., "ticket":..., "type": "created"|"transition"|"retry_reset", "from":..., "to":..., ...}`という「チケットの状態遷移」専用スキーマ。SPEC.mdの「変更検知イベント」を同じ`.metrics.jsonl`に混在させる場合、`group_events_by_ticket`が`ev.get("ticket")`でグルーピングするため、SPEC.md用に別の識別子（例: `"ticket": "__SPEC__"`固定値、または別ファイル）を用意する必要がある。
- 書き込み側（`record_metrics.py`）: `write_state(state_path, state)`（L146-150）は`tmp`ファイルへ書いてから`os.replace`（アトミック置換）。`main()`は`lib.is_ticket(path)`でSPEC.mdを除外済み（L46: `if not isinstance(path, str) or not path or not lib.is_ticket(path): sys.exit(0)`）。**SPEC.md対応を追加するには、`is_ticket`とは別に「SPEC.mdか」を判定する分岐を`record_metrics.py`のmain()内に追加し、frontmatter/ticket_id前提でないハッシュ/mtime記録ロジックを別途実装する必要がある。**
- **転用可否の結論（事実整理）**: 「ファイル・スキーマの直接再利用」は不可（ticket_id/status/retry_counts前提の構造が食い違う）。「hookが自動生成・LLM非編集・`.gitignore`対象という運用パターン」は転用可能（README.md「メトリクスの運用」節の3原則がそのまま当てはまる）。
- `is_ticket(path)`（L115-137）と`guard_spec_writes.is_spec(path)`は別々に定義されており、`_ticket_lib.py`には現在「SPEC.mdか」を判定する共有関数が無い。README.mdのguard_bash_writes.py行が明記する通り、`_ticket_lib.is_ticket`と`guard_bash_writes.py`内の保護対象判定も意図的に基準を分けている前例があるため、「統一しない」という設計判断も選択肢としてありうる（ただし本チケットではcheck_loop_integrity.py・record_metrics.py・guard_spec_writes.pyの3箇所が同じ「SPEC.mdか」判定を必要とするため、共有ヘルパ化のメリットは大きいと推測される＝事実整理としての記載であり推奨ではない）。

## 4. README.md の現在の構造

- `.claude/hooks/README.md` は次の構成: タイトル→説明文2行→hook一覧表（`| ファイル | イベント | 役割 |`の3列、7行: validate_ticket_state.py / check_loop_integrity.py / record_metrics.py / guard_spec_writes.py / guard_bash_writes.py（巨大な1セル）/ _ticket_lib.py）→「メトリクスの運用」節（3箇条書き）→「設計方針」節（4箇条書き：fail-open／依存なし／単一の真実／無限ループ防止）→「ローカルでの動作確認」節（bashコマンド例）→「自動テストは`tests/`にある」の1行→「注意」節（2箇条書き）→「ルールを変更するとき」節（3手順）。
- **「強制する不変条件」という文字列自体はREADME.md内に存在しない。** CLAUDE.md（L120）が「hook一覧・強制する不変条件・fail-open設計・メトリクス運用・ルール変更手順は`.claude/hooks/README.md`を正とする」と書いているが、これは「README.mdの中のどれかのセクション（表の役割列や設計方針節）が不変条件の記述を担っている」という意味に読める。KLK-016のAC「hook一覧と『強制する不変条件』へ追記する」は、実務上は①hook一覧の表（check_loop_integrity.py行とguard_spec_writes.py行の役割列テキストの更新）②必要なら「メトリクスの運用」節へSPEC.md用サイドカーの言及を追加、の2箇所への追記と解釈するのが自然（architect確認要）。
- 表の役割列の記述スタイル: 検出内容を**太字**で強調しつつ日本語で1〜3文にまとめる（例: check_loop_integrity.py行の「**ドリフト検知（`.metrics_state.json`の最終観測値とstatus/retry_countsを突き合わせ...）**」）。KLK-016で追記する際もこのスタイルを踏襲するのが自然。

## 5. tests/ 配下の既存hookテストの構成・実行方法

- 実行方法: `python3 -m unittest discover -s tests -v`（pytestではない。README.md L49に明記。ただし`.claude/settings.json`のallowリストには`Bash(pytest *)`も含まれるが、これはリポジトリ一般のCI許可であり、本プロジェクトのhookテストの実行規約はunittest discoverが正）。
- `tests/_util.py`: 全hookテスト共通ヘルパ。`run_script(script, payload, cwd=None)`でhookスクリプトをサブプロセス起動しstdinへJSON payloadを渡す。`hook_output`（PreToolUse用、`hookSpecificOutput`を取り出す）と`top_level_output`（Stop用、トップレベルJSONをそのまま返す）の2種のパーサ。`write_ticket`/`ticket`/`write_state`/`state_record`はチケット・サイドカー生成のテスト用テンプレート関数。
- `tests/test_loop_integrity.py`（250行）: `TestLoopIntegrity`クラス。`setUp`/`tearDown`で`tempfile.TemporaryDirectory()`を使い、実ファイルシステム上にtickets/構造を作ってサブプロセスでhookを起動する統合テストスタイル（モックなし）。`run_stop(stop_hook_active=False)`ヘルパで`{"hook_event_name": "Stop", "cwd": ..., "stop_hook_active": ...}`payloadを送る。ドリフト検知のテストは`write_state`で`.metrics_state.json`相当を用意し、チケットfrontmatterと故意にずらして`assertBlock`する形と推測される（本ファイルの全文は250行中冒頭70行のみ確認、ドリフト検知固有のtestケース名は本調査では未確認＝**Unknown寄りの情報**）。
- `tests/test_guard_spec_writes.py`（83行、全文確認済み）: `TestGuardSpecWrites`クラス。`payload(tool, path)`ヘルパでWrite/Edit双方のpayloadを生成。`assertAllow`/`assertAsk`の2ヘルパ。9テストケース（ネストしたSPEC.md、ルート直下SPEC.md、他ファイルallow、spec-qa配下のYAML状態ファイルallow、SPEC_TEMPLATE.md allow、.claude配下allow、file_path欠落allow）。**SPEC.mdが実在するかどうかに依存しないテスト設計**（実ファイルを作らずpayloadのfile_pathのみで判定するため、ドリフト検知テストを同パターンで追加する場合は、実際にSPEC.mdファイルをtempdir上に書き出す必要がある＝test_loop_integrity.pyの`write_ticket`パターンに近くなる）。
- `tests/test_metrics.py`（328行、未読・行数のみ確認）: record_metrics.pyのテストと推測されるが本調査では中身未確認。KLK-016でrecord_metrics.pyを拡張する場合、この既存テストへの回帰影響確認が必要（**Unknown**: 具体的なテストケース内容は未確認）。
- `tests/test_ticket_lib.py`（444行）: `_ticket_lib.py`の単体テスト。`is_ticket`/`load_state`/`parse_frontmatter`等の単体テストが含まれると推測されるが中身は未読。

## 6. ハッシュ監視 vs mtime監視 vs その他の方式：一次データ整理（決定はarchitect）

事実整理のみ。推奨は行わない（investigator.mdの職掌・research-conventions §7に基づく）。

- **ハッシュ監視（例: `hashlib.sha256`でSPEC.mdの内容ハッシュをサイドカーに保存し、Stop hookで再計算して比較）**
  - 長所（一般論・general_knowledge）: ファイル内容そのものの変化を検出する。mtimeと異なり「内容が同じならtouchされても誤検知しない」性質を持つ。
  - 短所: 正規のWrite/Edit経路でも都度ファイル全体を読んでハッシュ計算するコストが発生する（SPEC.mdのサイズ次第。本リポジトリでは現在SPEC.mdが存在しないため実測不可）。「正規の変更で毎回ハッシュが変わる」という前提のため、`record_metrics.py`（PostToolUse）側でも同様にファイルを読んでハッシュを更新する必要があり、Write/Edit成功直後に実ファイルを再読み込みする処理が新規に必要（`record_metrics.py`は既にticketについて同様の「書き込み後にファイルを開いて内容を読む」処理を行っている＝L60-63のパターンが先例として転用できる）。
- **mtime監視（`os.path.getmtime`）**
  - 長所: ファイル内容を読まずに済み軽量。
  - 短所（一般論）: `touch`コマンド等、内容を変更しないBash操作でもmtimeが変化し誤検知しうる（ただし「内容を変えないtouch」は`guard_bash_writes.py`のALLOWED_HEADSに`touch`が含まれておらず、保護対象パスへの`touch`は現状denyされる可能性が高い＝要確認だが、ALLOWED_HEADSリスト（L372-385）に`touch`は無いことを確認済み。ただしこれは書き込み系コマンドとして意図的に除外されている（README.md「xargs（任意コマンド実行）・tee/cp/rm/touch（書き込み系）...は載せない」）ため、正規経路以外でのtouchはそもそもguard_bash_writes.pyでdenyされる可能性が高い＝mtimeの弱点である「無害なtouchでの誤検知」は本システムでは発生しにくいと推測される。**ただしこれは推測であり実測ではない**）。OS・ファイルシステム間でmtimeの精度（秒単位/ナノ秒単位）が異なる一般的リスクもある。
  - 既存コードとの整合性: `record_metrics.py`は既に`ts`（`datetime.datetime.now().isoformat`）をイベントに記録しており、mtime相当の「時刻ベースの記録」という発想自体は既存パターンと親和的。ただし比較対象は「前回のイベント時刻」ではなく「ファイルの実際のmtime」なので、Stop hook側で`os.path.getmtime("docs/SPEC.md")`を都度取得し、サイドカーに保存した値と比較する形になる。
- **その他（例: サイズ+mtimeの組み合わせ、行数、簡易チェックサムなど）**: 本調査では具体的な代替手法の先行事例をコードベース内に発見できなかった（`hashlib`/`getmtime`/`st_mtime`いずれも未使用）。
- **既存コードパターンとの整合性という観点での中立的整理**:
  - `_ticket_lib.py`の既存drift検知（`check_state_drift`）は「値そのもの（status文字列・retry_counts整数）の一致判定」という単純な等価比較モデルであり、ハッシュ・mtimeいずれを採用しても「サイドカーに保存した値」と「現在値」を等価比較するという処理構造自体は`check_state_drift`と揃えられる（≒既存の設計パターンへの追従しやすさは同程度）。
  - `record_metrics.py`は既に「Write/Edit直後にファイルを開いて中身を読む」処理を実装済み（チケットのfrontmatterパース目的）ため、ハッシュ方式を採る場合はこの既存の「ファイルを読む」処理点にハッシュ計算を追加するだけで済み、実装上の追加コストは小さいと推測される（**推測。実測ではない**）。
  - mtime方式はこの「ファイルを読む」処理そのものを省略できる点で実装がより単純になりうるが、`os.stat`呼び出しを新規に導入することになる（現状`.claude/hooks`配下に`os.stat`系呼び出しは1件も無い）。

## 7. その他の関連事実

- `.claude/settings.json`のPostToolUse Write|Edit（`record_metrics.py`）はmatcherで全ファイルを対象にしており、SPEC.md宛ての呼び出しも既にhookプロセス自体は起動している（内部で`is_ticket`によりreturnしているだけ）。したがってSPEC.md対応を追加する場合、settings.jsonの変更は不要と推測される（Stop hook・PostToolUse hookともに既存の登録のまま、スクリプト内部の分岐追加で完結できる）。
- 本リポジトリには`docs/SPEC.md`が存在しない（`find . -iname SPEC.md -not -path "*/.claude/*"`で非検出）。CLAUDE.mdドキュメント管理ルールの表にも「`docs/SPEC.md` | 人間（`/spec-interview`で対話生成し人間が承認）」とあり、本リポジトリ自身はメタ開発用でSPEC.mdを持たない運用（2026-07-05コミット6bd2ec9の経緯はオーケストレーターの補足による伝聞であり、investigatorは当該コミットの中身を独自に確認していない＝伝聞情報として区別）。

## architectへの申し送り推奨事項

1. README.md「強制する不変条件」の解釈（表の役割列への追記か、新規見出し新設か）を設計時に明確化してください。
2. `docs/policy-registry.md` L22の記述（check_loop_integrity.pyが既にSPEC.mdをカバーしているかのような記載）と現状実装の齟齬は、本チケットのrelated_files外ですが、完了後に整合させる必要がある旨を人間へ報告することを推奨します（別チケット化候補）。
3. ハッシュ/mtime監視の選択理由は先例ゼロの新規決定であるため、設計書に「なぜその方式か」だけでなく「他方式を採らなかった理由」も明記することを推奨します。

## Unknowns（architectの設計判断が必要・investigatorでは確定不能）

- ハッシュ監視 vs mtime監視の最終選択
- 新規サイドカーを既存`tickets/.metrics_state.json`に相乗りさせるか、別ファイル（例: `tickets/.spec_state.json`）に分離するか
- `docs/SPEC.md`が実在するプロジェクトでの実機動作確認（本リポジトリにSPEC.mdが無いため、tempdir上のunittestでのみ検証可能）
