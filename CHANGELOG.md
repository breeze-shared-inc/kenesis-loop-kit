# CHANGELOG

Kenesis Loop Kitのすべての変更はこのファイルに記録されます。
フォーマットは [Keep a Changelog](https://keepachangelog.com/ja/1.0.0/) に準拠し、
バージョン管理は [Semantic Versioning](https://semver.org/lang/ja/) に従います。

---

## [1.8.0] - 2026-08-20

### Added
- バッチ外部駆動スクリプト `scripts/batch_loop.py`（1チケット=1セッション）: チケットごとに `claude -p "/start-loop {ID}"` を新規ヘッドレスセッションで逐次起動し、セッション境界でチケットファイルの状態を検査して前進・停止を判定する（完了判定はファイル状態が正: done/に `status: done`。終了コードは異常検出の補助）。プリフライトP1〜P9（linked worktree検出・ID一意存在・status検証・in_progress上限・14日blocked排除・SPEC存在または `--allow-missing-spec`・claude CLI実行可能性・status/retry_countsスナップショット・done/件数警告）を機械化し、違反は開始前に一括表示して停止。実行前の承認サマリへのy/N応答が旧バッチ事前承認の実体（`--yes` でスキップ可）。停止条件（境界判定）は異常終了（exit≠0/timeout）・active/残存done・blocked（リトライ上限超過を包含・ブロッカー本文表示）・未完了status・範囲外チケット変化・差し戻し増分（既定停止・`--continue-on-rework` で人間が明示緩和可）で、正常完了時のみ次チケットへ進み最終チケット後は必ず停止する。暴走ガードは `--max-turns 200` 既定・`--max-budget-usd`・`--timeout-min`。stdlibのみ・fail-closed（hooksのfail-open規約とは逆・人間実行の監督ツール）・tickets/読み取り専用（単一ライター原則の維持）。終了コード 0/1/2/3/130。設計は `docs/designs/KLK-001.md`
- `tests/test_batch_loop.py`（59テスト）: プリフライトP1〜P9・境界判定1〜7の分岐と優先順位・駆動プロンプト組立・フラグ伝播・fail-closed（`_ticket_lib` import失敗・frontmatter解析不能）・SIGINT時の子プロセスterminateを検証。claude起動は `--claude-cmd` へのフェイク実行ファイル注入で代替し、CI・テストで実claudeを起動しない
- ヘッドレスCLI挙動の実測記録（2026-07-19・claude CLI v2.1.215）: PreToolUse `ask` はヘッドレスで自動deny（ハングなし）／正常完了・deny多発は exit 0・`--max-turns` 到達は exit 1／Stop hookの `decision: "block"` は `-p` でも機能（境界判定2〜4は代替ではなく防御の重複）／`--max-turns` は `--help` 非掲載の隠しオプションだが機能する（将来削除時は初回セッションでAPI消費なしに即停止・回避は `--max-turns 0`）。docs/designs/KLK-001.md §4 と docs/batch-loop.md に記録
- `scripts/batch_loop.py`のstream-json化: `build_claude_command()`へ `--output-format stream-json --verbose --include-partial-messages --forward-subagent-text` を無条件付加し、`run_session()`をstdout PIPE化＋専用リーダースレッド＋queueベースのタイムアウト管理へ置き換え、子プロセスの応答をリアルタイムに人間可読な進捗（assistantテキストデルタ・tool_use・tool_result・サブエージェント進捗）として標準出力へ表示するようにした（現状の素通し継承表示から変更）。`render_event`/`_brief`/`handle_stream_line`は表示専用の防御的パース（JSONデコード失敗・未知のtype・レンダラー内部例外はいずれも表示スキップに留め）で、境界判定・終了コードには一切影響しない。`run_session()`の外部契約（引数・戻り値）は不変で、既存のタイムアウト・SIGINT契約はそのまま維持される。`scripts/batch_loop.py`に実行権限（`chmod +x`）を付与。`tests/test_batch_loop.py`にrender_event単体テスト・stream-json統合テストを追加（44件）。stream-json下のヘッドレス挙動実測（VS-1）と`--forward-subagent-text`の実イベント列実測（VS-2。実スキーマに合わせrender_eventを校正）はdocs/batch-loop.md「ヘッドレスセッションの挙動」節に記録。設計は`docs/designs/KLK-007.md`
- `/batch-loop-inline`コマンド（`.claude/commands/batch-loop-inline.md`）と運用ガイド`docs/batch-loop-inline.md`を新設: KLK-001が非推奨化した旧方式（単一セッションへ事前承認テンプレートを送り、orchestratorが同一セッション内で複数チケットを連続処理する方式）を、現行ポリシー（`docs/worktree-policy.md`のworktree分離・KLK-002のモデル割当）と整合させたうえで、外部駆動`/batch-loop`とは別コマンドとして復旧した。差し戻し検知の粒度を旧方式の「即停止」から外部駆動版と同じ「チケット境界での停止」へ変更（実装ループ内の人間非介在の原則を優先。理由はdocs/batch-loop-inline.mdに明記）。対話セッション専用（ヘッドレス実行は想定しない）で、少数件（目安2〜3件）での利用を推奨
- SPECのID指向部分抽出スクリプト `.claude/skills/spec-interview/scripts/extract_spec_section.py`: チケットに明記されたREQ/SCR/IF/EH/NFR-IDから該当セクションのみを抽出し、investigator / architect / reviewer がチケットごとにSPEC全文を読み直す固定コストを削減する。読み取り専用スクリプトとして `guard_bash_writes.py` の `READONLY_SCRIPTS` へ収載し、hookに遮断されずに規定動線から実行できるようにした。テストは `tests/test_extract_spec_section.py`。設計は `docs/designs/KLK-006.md`
- チケット一覧CLI `scripts/list_tickets.py`: `tickets/active/` のfrontmatter（id/status/priority/retry_counts/updated）のみをコンパクトな表として出力する。orchestratorの作業開始時の全件フルリードを「一覧で処理対象を1件選択 → その1件だけフル読み」へ置き換え、チケット数×ログ長に比例していた毎ループの固定トークン費を削減する。テストは `tests/test_list_tickets.py`。設計は `docs/designs/KLK-003.md`
- `docs/SPEC.md` のドリフト検知バックストップ: Stop hook `check_loop_integrity.py` の走査対象に `docs/SPEC.md` を追加し、PreToolUseの `guard_bash_writes.py` をすり抜けたSPEC.mdへの書き込みが誰にも検出されない非対称（チケット宛ての書き込みには2段目の防御があるのにSPEC.mdには無い）を解消した。テストは `tests/test_spec_drift.py`。設計は `docs/designs/KLK-016.md`
- サブエージェントレポートの外部化先 `docs/reports/{ID}/{phase}.md` の運用規定: orchestratorが代筆するファイル（investigation / review）のコミット責任・自筆/代筆の境界表・チケットからのポインタの解決性・gitignoreプリセットでの扱いを明文化した。KLK-004の規約が持っていた「Gitで追跡し将来も参照可能にする」という目的に対する運用面の欠落を埋めるもの。設計は `docs/designs/KLK-026.md`
- 文書側のポリシー記述を機械検査する回帰テスト群: `tests/test_agent_frontmatter.py`（エージェント定義frontmatterの規約）と文書配線テスト8件（`tests/test_klk003_doc_wiring.py`・`..._klk004_...`・`..._klk005_...`・`..._klk017_...`・`..._klk022_...`・`..._klk025_...`・`..._klk026_...`・`..._klk027_...`）、`tests/test_klk027_gitignore_checkignore.py`。ポリシーの正の所在と転記先の整合をテストで固定し、記述ドリフトを検出できるようにした

### Changed
- **`/batch-loop` の役割を「セッション内での連続ループ実行」から「プリフライト検証（`--dry-run`）と実行コマンドラインの案内」へ変更（後方非互換）**: バッチ本体は人間がターミナルで `python3 scripts/batch_loop.py {ID列}` を実行する外部駆動方式（1チケット=1セッション）となり、単一セッションへのサブエージェントレポート蓄積によるトークン累積を解消。コマンドはNeverで「セッション内で `claude -p` を起動しない」「`--dry-run` 以外を実行しない（`--yes` での承認代行も禁止）」を明示
- `docs/batch-loop.md` をバッチ外部駆動ガイドへ全面改訂: 旧→新セマンティクスの写像表（差し戻し即停止→セッション境界停止を含む）・プリフライト・停止条件・フラグ・終了コード・ヘッドレス実測記録・「実行中は同リポジトリで対話セッションを開かない」（二重ライター防止）を掲載。旧・セッション内手動テンプレート方式は非推奨（トークン累積）として1段落の言及に縮小（テンプレートはGitヒストリ参照）
- CLAUDE.md スラッシュコマンド一覧の `/batch-loop` 行と、ポリシー表「バッチ連続実行の事前承認」行を新方式へ更新（定義の正は docs/batch-loop.md のまま・実行責任者=人間 + scripts/batch_loop.py・本文セクションの追加なし）。`start-loop.md`・`plan-tickets.md`・`setup.md` の `/batch-loop` 誘導文、README（ディレクトリツリーへ scripts/ 追加・コマンド表・使用例）も追随
- `docs/batch-loop.md`冒頭に外部駆動`/batch-loop`とセッション内`/batch-loop-inline`の使い分け指針（比較表）を追加し、末尾「旧方式（セッション内手動テンプレート）について」節を`/batch-loop-inline`への案内へ差し替え
- `.claude/agents/orchestrator.md`「改善ループ（人間の判断後）」テーブル直下に、バッチ実行（`/batch-loop`・`/batch-loop-inline`）時はバッチ開始時の事前承認がチケット間の前進判断を代行し、テーブルの判断が適用されるのはバッチ終了後であることを明記する注記を追加（テーブル自体は再定義しない）
- CLAUDE.md スラッシュコマンド一覧へ `/batch-loop-inline` 行を追加し、ポリシー表「バッチ連続実行の事前承認」行を外部駆動/セッション内の2コマンド体制に更新（本文セクションの追加なし）。`batch-loop.md`・`start-loop.md`・`plan-tickets.md`・`setup.md`・READMEに`/batch-loop-inline`への相互参照を追記
- `guard_bash_writes.py` の判定粒度を3レイヤ（L1字句／L2パス／L3構文）へ再構成し、`.claude/hooks/README.md` の該当行を更新。ホワイトリスト `ALLOWED_HEADS` に書き込み経路を持たないコマンド（`cd`〔セグメント自体は無条件許可。移動先の作業ディレクトリのみ追跡し、後続ステートメントの相対パス判定に使う〕・`pwd`・`echo`・`cut`・`tr`・`awk`・`nl`・`rev`・`realpath`・`readlink`）を追加した。`printf` は README「ローカルでの動作確認」の注記（printf はホワイトリスト外）と対であるため意図的に追加していない。`_ticket_lib.is_ticket`（厳密判定）との基準不統一は目的の違いによる意図的なものとしてモジュール docstring に明記した（統一の検討は別チケット）
- CLAUDE.mdのポリシー管理表を `docs/policy-registry.md` へ分離し、CLAUDE.md本文は「全体像のインデックス」と「複数ファイルから参照される共通定義」のみを保持する構成へ変更: CLAUDE.mdはメインセッションと全サブエージェントのコンテキストへ注入されるため、ポリシー編集時にしか必要でない最大ブロックを外へ出して固定トークン費を削減した。あわせて「再肥大化の防止（構造維持の原則）」として、新規ポリシーは実行責任者のファイルへ正を定義しポリシー表へ1行追加する手順を規定。設計は `docs/designs/KLK-005.md`
- サブエージェントのRequired Output Formatへ要約の行数上限（各項目5行以内）を導入し、5行を超える詳細（調査全文・テスト出力全量・レビュー指摘の全量）は `docs/reports/{ID}/{phase}.md` へ外部化してチケットにはポインタ1行のみを残す規約へ変更: レポートがorchestratorのメインスレッドとチケットログの双方に積まれ、以後の全ループで再読される二重のトークン消費を解消する。書き手分担（Write/Edit保持者は自筆、非保持者はorchestratorが代筆）の3重記述も1箇所へ一本化した。設計は `docs/designs/KLK-004.md`・`docs/designs/KLK-027.md`
- `.claude/agents/*.md` 6ファイルをClaude 5世代のコンテキスト設計基準で精査し、(A) hookが機械強制する内容の反復、(B) Claude 5の既定動作と重複する汎用ルール、(C) 正の定義先との二重記載 の3層を削除: プロジェクト固有の状態機械と運用契約（保持対象）のみを残した。設計は `docs/designs/KLK-009.md`
- 設計書テンプレートへ参照ルールを追加: コード箇所は行番号ではなく**節見出し＋引用文字列またはシンボル名**で参照する。`.claude/agents/*.md`・CLAUDE.mdの行数変動によって進行中チケットの設計書の行番号参照がドリフトし、再開時にimplementerが誤った箇所を見るリスクへの対処（当該箇所の是正とCLAUDE.mdポリシー表の精度補正を同時に実施）。設計は `docs/designs/KLK-011.md`
- `.claude/commands/triage.md` 手順1を一覧CLI利用へ統一: `/start-loop` の14日超blocked検出で抽出済みの候補IDを引き継ぎ、同じ検出を二重に行わない手順へ改訂した（旧・全件フルリードが残置していたためKLK-003の削減効果が `/triage` 経路で相殺されていた）。設計は `docs/designs/KLK-022.md`
- 設計書と実装の記述同期3件（コード変更なし）: KLK-010設計書を第8版へ更新（最終ラウンドの修正とreviewer検出のH6・H7の未反映、および実装より強い保護を主張する記述と件数のずれを訂正。`docs/designs/KLK-017.md`）／KLK-013設計書へtester差し戻し後の最終実装を反映し副次的に解消された穴を記録（`docs/designs/KLK-023.md`）／KLK-014設計書へテンプレート§4準拠の実装Phase表を追加（`docs/designs/KLK-025.md`）
- テストスイート全体は 546件 → **849件**（本リリースで追加された回帰テストの累計。failures 0・errors 0）

### Fixed
- `guard_bash_writes.py` の誤deny（false positive）とすり抜け（false negative）を解消: 素朴な `command.split("|")`・空白トークン分割・部分文字列判定をやめ、シェルの字句解析を尊重する方式（クォート状態を追跡してクォート外の演算子だけを最長一致で切り出し、語チャンクは `shlex.split(posix=True)` でクォート解除）へ置き換えた。両者は同一根因の表裏であり一体で修正している。設計は `docs/designs/KLK-010.md`
  - **誤denyの解消**: 正規表現の選択子（`grep -E '^(id|title):' tickets/...`）をシェルパイプと誤認しない／`cd`・`awk` 等がホワイトリスト不在で弾かれない／クォート内の `<<`（`grep -c '<<EOF' ...`）をヒアドキュメントと誤認しない／保護対象に触れない後段リダイレクト（`cat tickets/... && echo x > "$TMP"`）を巻き添えにしない（出力リダイレクトをステートメント単位で判定し、変数先は同一コマンド内で保護対象を代入された変数のときのみ deny）
  - **すり抜けの解消**: sed in-place の全表記（`-i` / `-i.bak` / `-ni` / `-si.bak` / `--in-place` / `--in-place=SUFFIX` / `-i''`）／インタプリタワンライナー内のリテラルパス（`python3 -c "open('docs/SPEC.md','w')..."`。パス検出をトークン境界に依存しない候補抽出＋basename 完全一致へ変更し、`MYSPEC.md`・`SPEC.md.bak` では誤denyしない）／コマンド置換・プロセス置換の内側（`ls $(rm tickets/...)`・バッククォート・`<(...)`。深さ上限3で再帰し上限到達時は保守側で打ち切り）／パストラバーサルによる `.claude` 除外の悪用（`os.path.normpath` による正規化を除外判定より先に適用）
  - **副作用の予防**: `awk` をホワイトリストへ加えたことで新たに素通りしうる awk のプログラム内リダイレクト（`awk '{print > "docs/SPEC.md"}'`）を同時に検出対象へ追加し、同型の sed の `w` コマンド（`s/a/b/w FILE`）へも一般化した
  - **新しい解析基盤が生んだ抜けの解消**: 字句レイヤの導入で新設された4系統の false negative を塞いだ。(1) コマンド置換の**外側**方向 — 置換で包むだけで判定を外せた形（`rm $(echo docs/SPEC.md)`・`` rm `…` ``・`sed -i 's/a/b/' $(…)`・`cat a | tee $(…)`・`echo x > $(…)`）を、位置インデックス付きプレースホルダ（`__KLK_SUBST_0__`）で置換の帰属を保持し、言及ゲート・リダイレクト先・変数代入値・sed/awk 規則の4用途で解決することで捕捉する（先頭コマンド名と find/git の完全一致規則は意図的に解決しない）。帰属が厳密なため `ls $(cat tickets/…); rm /tmp/junk` の後続ステートメントは巻き添えにしない。(2) degraded mode — 旧版が持っていたステートメント分割・パイプ分割・パイプライン単位の言及ゲートを復元し、`ls ; rm docs/SPEC.md #'`・`cat x && tee tickets/… #'`・`find tickets/… | xargs rm #'` を捕捉する。(3) awk の変数束縛 — `-v f=PATH` / `-vf=PATH` / `--assign f=PATH` / 位置引数 `f=PATH` で保護対象を awk 変数へ束縛する形（`awk '{print > f}' f=docs/SPEC.md in.txt`）と、文字列リテラルを除去したうえでの `print`/`printf` 出力リダイレクト（`awk '{print > FILENAME}' tickets/…`）を検出する。読み取り awk（`-F'|'`・`NR>1`・`$1 > 2`・`printf "%s|%s"`・`-v OFS=,`）は allow のまま。(4) `cd` による作業ディレクトリの移動 — 保護対象配下へ移動した後の相対パス書き込みのうち、非ホワイトリストコマンド（`cd tickets/active && rm APP-001.md`）と出力リダイレクト（`cd tickets/done && echo x > APP-001.md`）を捕捉する（`cd` セグメント自体は無条件許可を維持。`cd "$DIR"` / `cd $(…)` は追跡打ち切りで誤denyしない）。**ホワイトリスト収載コマンドの引数経由（awk / sed / sort / uniq）と置換の内側は本項では閉じておらず、下記「引数だけで書ける／実行できる経路の追加閉塞」(3) で閉じた。**あわせて `( rm tickets/… )`（`(` が独立語になる形）の先頭コマンド判定と、演算子の種別表の一元化（`OPERATOR_KINDS`）を行った
  - **先頭コマンド位置の一元化**: 先頭コマンドに当たる語の位置判定を `head_index` へ集約し、`head_of`・`cd` のオペランド抽出・`git` のサブコマンド抽出・`awk` の引数走査が同じ位置を共有するようにした。従来これらは「先頭語の次から」（`words[1:]`）を前提にしていたため、環境変数代入の前置きやグループ化の `(` があると前提がずれ、`X=1 cd tickets/active && rm APP-001.md`（および `( cd tickets/active && rm APP-001.md )`）で cwd 追跡が働かず素通りし、逆に `X=1 git add tickets/active/APP-001.md` は `git` 自身をサブコマンドと誤認して誤denyになっていた。両者を同時に解消している（`X=1 git checkout` / `git rm` / `git restore` は従来どおり deny）
  - 字句解析できない入力（未閉じシングル/ダブルクォート・未閉じバッククォート・未閉じ `$(`・末尾の孤立エスケープの5系統。`don't` のような英文コメントでも成立する）は allow せず、**旧版と同じ判定要素をすべて持つ**簡易判定へ落とす（`rm tickets/... #'` を素通りさせないため）。旧版から意図的に外したのは「リダイレクト先が `$`/バッククォートを含むだけで deny する」規則のみ。この経路ではクォート内の `|` を誤ってパイプと解釈する誤denyが旧版と同じく残る。内部エラーでの fail-open は従来どおり
  - **ホワイトリスト収載コマンドの「引数だけで書ける／実行できる」経路の追加閉塞**: (1) **awk のオプション次元** — gawk の in-place 拡張（`awk -i inplace '{…}' tickets/…` の4表記。`sed -i` の awk 版であり実ファイルを書き換える）と外部コード読み込み（`-f`・`-l`・`-E`・`-D`）・ファイル書き出し（`-o`・`-p`・`-d`）を閉じた。規則はブラックリストではなく**既知の読み取り専用オプションのホワイトリスト**（`AWK_SAFE_FLAGS` / `AWK_SAFE_VALUE_FLAGS`。GNU Awk 5.2.1 の `awk --help` と突き合わせて収載）で、未知の `-` 始まりの語は deny 側へ落ちる（失敗方向が「可視な誤deny」になるため）。読み取り awk（`--posix`・`-F'|'`・`-v`・`--field-separator=`・`--`）は allow のまま。(2) **awk の外部コマンド実行次元** — `system()` / `@load` / `@include`（`awk 'BEGIN{system("rm docs/SPEC.md")}'` は `>` も `|` も含まないため従来の規則に掛からなかった）と、**間接関数呼び出し `@f(…)`**（gawk 4.1.2 以降は関数名を文字列変数から供給できるため、`awk 'BEGIN{f="system"; @f("rm tickets/…")}'` のように `system(` のリテラルが現れないまま `system()` を実行できる。`@load` / `@include` の指令名リストでも捕捉できないため、**間接呼び出し構文そのもの**を証拠とする。値の中身は追跡しない〔エイリアス・文字列連結で容易に迂回できるため〕。副作用として、読み取り専用のユーザー定義関数を `@f(…)` で間接呼び出しする形も deny になる〔呼び先を静的に判別できないため。`PROCINFO["sorted_in"]="cmp"` のような関数名文字列の受け渡しは `@f(` 構文を使わないため影響しない〕）。gawk は `@` の直後と関数名の直後の空白をどちらも受け付けるため、外部コマンド実行の検出（`system(` と `@f(`）は語単位に加えて**空白結合したテキスト**へも当てる（degraded mode は空白分割のため `@ f(` が `@` と `f(` に、`system (` が `system` と `(` に割れて語単位では一致しない）。オプション判定と出力構文の判定は結合テキストへは当てない（結合により語の意味が変わり誤denyになりうるため）。**なお、この (2) のブラックリスト（`system(` / `@load` / `@include` / `@f(` の語単位・空白結合テキスト評価）は後述の「プログラム内構文次元のホワイトリスト化」により degraded mode 専用へ縮小された。**(3) **保護対象を作業ディレクトリとする相対パス書き込み** — awk の `print > "REL"`・`printf >> "REL"`・変数束縛形、sed の `w REL`（正常系と degraded）、`sort -o REL`、`uniq in REL`、コマンド置換／バッククォート／プロセス置換の内側（`cd tickets/active && ls $(rm APP-001.md)`）。書き込み先オペランドの解決を単一ヘルパ `guarded_write_target` へ集約し（cwd と結合するのは**構文的に書き込み先と確定した語のみ**。任意の語へ結合すると `awk 'NR>1 {print}'` 等が誤denyになる）、置換の再帰へ cwd を伝播した。保護対象 cwd 下の読み取り（`cd tickets/active && awk '{print $1}' APP-001.md`・`sed -n '1,5p'`・`sort`・`uniq -f 2`）は allow のまま。(4) `sort -o FILE` / `--output=FILE`・`uniq INPUT OUTPUT` の第2位置引数（cwd 相対形・絶対パス形の両方）と `find -fprint0`（`FIND_WRITE_FLAGS` の列挙漏れ）。あわせて `CWD_SAFE_HEADS`（保護対象 cwd 下で許可する先頭コマンドの明示列挙。`ALLOWED_HEADS` へ足すだけでは cwd 下の許可を得られない）を導入し、棚卸しの忘れが deny 側へ落ちる既定を設けた
  - **既知の未対応（本 hook の導入当初から存在する穴・別チケット候補）**: `python3 IDENTIFIER=VALUE <READONLY_SCRIPT> …` による READONLY_SCRIPTS 許可経路の偽装（python3 が実行するのは `IDENTIFIER=VALUE` という名前のファイル。**任意コード実行**に到達しうるため最優先）・`sed -f SCRIPT`・GNU sed の `e` フラグ（任意コマンド実行）・`sort --compress-program=PROG`・`git diff --output=FILE`・パスがリテラルに現れない形（変数・置換の出力・断片の結合）・cwd と相対パスの両方に接頭辞が分割された形（`cd tickets/active && cd .. && rm active/APP-001.md`。一般解は誤deny爆発を招くため実装しない）。`mv` は CLAUDE.md が active/ ↔ done/ 移動の正規手段と定めるため保護対象 cwd 下でも**意図的に許可**する。モジュール docstring と `.claude/hooks/README.md` に明記し、`ALLOWED_HEADS` へコマンドを追加するときは設計書 §3-9 の棚卸し表を**4次元**（書き込みオプション／外部コード読み込みオプション／内部構文／位置引数の出力先）で更新し `CWD_SAFE_HEADS` の収載可否まで判定する5手順の規律を定めた
  - **awk のプログラム内構文次元をブラックリストからホワイトリストへ反転**: 同じ次元で4ラウンド連続して穴が出た（プログラム内リダイレクト → `system()` → 間接呼び出し `@f(…)` → `"cmd" | getline`）ため、規則を積み増す方式をやめ、**awk が実際に実行するテキストだけを取り出して「安全と確認できる形」以外を deny する**方式へ変更した。判定対象は `-e` / `--source` の値と、無ければ位置引数の**先頭オペランド**のみ（ファイル名オペランド・変数束縛値は awk が実行しないため対象外）。文字列・正規表現リテラルを**左→右の1パス**で除去したうえで、(a) 許可文字集合（`@` と `\|` を含まない＝間接呼び出し・`@load` / `@include` / `@namespace`・出力パイプ・`"cmd" \| getline`・コプロセス `\|&` の入口がすべて閉じる） (b) 呼び出し名の許可集合（`system` は非収載。`system (` の空白形も `IDENT\s*\(` で捕捉。同一プログラム内で `function NAME(` と宣言された名前は許可。**未知の名前は deny**） (c) `print` / `printf` の後に `>` `>>` `\|` が現れる出力構文の不在 の3条件を満たす形だけを許可する。これにより **`cd tickets/active && awk 'BEGIN{"rm APP-001.md" \| getline x}'` と `\|& getline`（実機 gawk で実際に対象ファイルを削除できることを確認済み）が閉じ**、gawk に新しい実行経路が加わっても収載しない限りすり抜けない（オプション次元・cwd 次元に続く3つ目の「未知は deny」の機械的既定）。1パス除去は必須で、2パス（文字列を全部消してから正規表現を消す／その逆）だと片方のリテラルの内側に見える引用符・スラッシュが外側の `system(` を飲み込む（`awk '/"/ {system("rm docs/SPEC.md")}'`・`awk 'BEGIN{x="(/a"; system("rm /docs/SPEC.md")}'` が実例で、いずれも回帰テストで固定）。**代償として新たに deny になる読み取り形**（保護対象に言及する／保護対象を cwd とする awk に限る）: `@namespace` 指令／収載していない組み込み・拡張関数の呼び出し（`mkbool`・`dcgettext`・`bindtextdomain` 等）／`\|` を伴う形／リテラル**外**のバックスラッシュ・バッククォート・シングルクォート・非ASCII文字／`{print a (b)}` のような `IDENT (` の連結／プログラムが `$(…)` 由来でシェル引用符を含む形／未閉じの文字列リテラル／`@`・`\|` を含むコメント。日常の読み取り（`{print $1}`・`NR>1 {print}`・`-F'\|'`・`gsub`／`sub`／`split`／`substr`／`toupper`・`for (k in a)`・ユーザー定義関数・正規表現内の `@`・日本語メッセージ等）は allow のまま（reviewer の日常読み取り70ケースの deny 件数は 1/70 で不変）
  - **awk の判定対象を「プログラム本文」に限定したことによる誤denyの解消**: `awk 'BEGIN{print "contact: a@b (see docs)"}' tickets/…`（**文字列リテラルの中身**が間接呼び出しに見えた）と `awk '{print}' 'system(1).md' tickets/…`（**ファイル名オペランド**が `system(` に見えた）が allow になった。awk には eval が無く、リテラルの中身とファイル名オペランドは実行され得ないため deny する根拠が無い。ブラックリスト（`system(` / `@load` / `@include` / `@f(` を語単位・空白結合テキストへ当てる規則）は**字句解析できない入力（degraded mode）専用**へ縮小した（空白分割ではプログラム本文の同一性が失われホワイトリストを適用できないため）
  - **字句レイヤの ANSI-C デコード相違を閉塞（L3 の防御が L1 の近似で迂回されていた）**: bash は `$'…'`（ANSI-C 引用）を**展開時にデコードする**ため、`awk $'BEGIN{x="foo\x22system(\x22rm tickets/active/APP-001.md\x22)\x22"}'` は hook からは「1つの巨大な文字列リテラル（＝丸ごと除去され安全）」に見えるのに、実機では `\x22` が `"` へ復号されて**文字列が途中で閉じ**、`system(…)` が実行コードとして残る（実機 GNU Awk 5.2.1 が EXIT 0 で対象ファイルを削除することを使い捨てディレクトリで確認済み）。`\x7c` を使えば同じ手口で `\|` を隠し、ホワイトリスト化で閉じたはずの `"cmd" \| getline` を**規則を1つも変えずに再開通**できた。ホワイトリストは「見えているテキストが安全か」しか確認できず、ブラックリストは符号化された字面に一致しないため、**どちらの方式でも判定できない**。そこで **(1) クォート外の `$'…'`／`$"…"` を含むステートメントを「判定不能」として扱い、保護対象への言及または保護対象 cwd が成立した時点で無条件に deny する**（語の内容は1文字も変えず、語でも演算子でもない印トークンを字句レイヤで残す方式。判定は head 非依存で `sed $'s/a/b/\x77 …'`〔`\x77` = sed の `w`〕も同時に閉じ、**degraded 経路にも同じ規則を置く** — 置かないと末尾に ` #'` を1つ足すだけで全形が通る）、**(2) 行継続（`\`＋改行）を削除して語を連結する**ように訂正（従来は空白へ置換していたため `rm tickets/acti\`＋改行＋`ve/APP-001.md` の語が割れて言及ゲートが偽になり、bash は実際に保護対象を削除するのに allow だった。**なお当初の実装は「無条件に削除」しており、これは下記「行構造の近似を bash の字句規則へ一致させた」の項で条件付きへ訂正している**）、**(3) 保護対象パスの判定に「証拠収集専用の ANSI-C 復号」を追加**（`rm $'\x74ickets/active/APP-001.md'` のように**証拠そのものを符号化して隠す**形を捕捉する。復号結果は判定用テキストへ渡さない）の3点を実施した。**代償として新たに deny になる形**（保護対象に言及する／保護対象を cwd とするコマンドに限る）: クォート外に `$'…'` を含む形（`awk -F$'\t' …`・`grep $'\t' …`。**`awk -F'\t'`・`grep -P '\t'` という等価な書き方が存在し** deny 理由文で案内する）／`$"…"` を含む形／degraded で引用符の内側に `$'`・`$"` の2文字並びがある形／復号で保護対象パスが現れる形。日常の読み取り70ケースの deny 件数は **1/70 で不変**であり、`$'…'`・`$"…"`・行継続を含まない入力の判定は**完全に不変**（old/new 比較スクリプト10本・約200コマンドで差分ゼロを実測）
  - **「文書化された前提が実測で裏付けられていなかった」ことへの構造的対処**: 従来の docstring と設計書は「`$'...'` は shlex が bash と同一には解釈しないが、語として1トークンに収まるため判定は保守側（deny 方向）へ倒れる」と明記していたが、**この主張は誤りだった**（allow 方向へ倒れ、かつ実機で実行される）。唯一の関連テストはエスケープを含まない `$'tickets/active/APP-001.md'` しか検証しておらず、主張の核心が一度も検証されていなかった。当該記述をすべて訂正したうえで、**「bash が実際にコマンドへ渡す argv」と「hook の語トークン」を突き合わせる検証手順**を設計書へ新設し（`$'…'`／`$"…"`／行継続3形／ブレース展開／glob／チルダ／パラメータ展開／算術展開／履歴展開の全行）、**相違があるのに規則も限界記載も無い形が1件でもあればブロッカー**とする合否条件を定めた。あわせて**シェル展開の次元**（bash が解釈するがコマンド文字列上は見えない変換）を書き込みベクタ棚卸し表へ新設した。**履歴展開が非対話シェルで無効であること**（`bash -c` の `$-` に `H` が無い）も実測で裏づけた
  - **棚卸し表と実装の機械的対応（`INVENTORY_CASES`・62件）**: 設計書 §3-9 の書き込みベクタ棚卸し表は `cmd \| getline` と `\|&` を**列挙していたのに規則もテストも存在せず**、それが4回目の穴になった。表の各構文に「規則ID・テストID・期待判定」の写像を持たせ、1テスト（`test_inventory_cases_match_expected_decisions`）が全件を `subTest` で固定する。**意図的に未対応の穴も期待値 `allow` として登録**し、穴がコード上で可視になるようにした（塞いだ時点で `deny` へ変える）: `sed -f SCRIPT`・GNU sed の `s///e`・`e` コマンド・**ブレース展開 `rm tickets/{active,done}/APP-001.md`・パス中に `*` が入る glob `rm tickets/acti*e/APP-001.md`・パラメータ展開 `f=…; rm $f` の引数側**（いずれも本 hook の導入当初から allow の既存穴。正しく閉じるにはブレース展開の実装が要り、パス候補抽出を単純に拡張すると awk のプログラム語が保護対象と誤判定されうる）。`LEGACY_DENY_COMMANDS`（旧版が deny していた集合を守る）とは目的が異なるため統合しない。**さらに、表の行は「bash の挙動が分岐する条件」まで分解して初めて防御になる** — 行継続は「1行」として存在していたのにサブケース（バックスラッシュの偶奇・コメント内か・クォート種別）が分解されていなかったために穴が出た。行継続と `#` コメントを8つのサブケースへ分解して登録し（40件 → 48件）、**期待値 `allow` の行を「意図的に未対応の穴」（塞いだら `deny` へ変える）と「bash と一致した結果の allow」（`deny` へ変えたら誤り）に区別**した
  - **行構造の近似を bash の字句規則へ一致させ、行継続の「無条件削除」が開けた穴を閉塞**: bash が `\`＋改行を行継続として扱うのは**バックスラッシュが自身エスケープされていないとき**だけであり、①バックスラッシュが**偶数個**並ぶ形（`\\` はリテラルの `\` で続く改行は制御演算子）②**`#` コメント末尾**にバックスラッシュがある形（コメント内で `\` は特別な意味を持たない）では、改行は**本物のコマンド区切り**になる。無条件に削除する実装はこの2条件でも連結してしまい、**後続コマンドの head が前の語へ吸収されてホワイトリスト判定に使われる head が先頭の許可コマンドになる** — すなわち `echo x\\`＋改行＋`rm docs/SPEC.md` のように**任意の読み取りコマンドへ2文字足すだけで hook 全体が無効化された**（実機 bash が `docs/SPEC.md` を削除し `sed -i` を実行することを使い捨てディレクトリで確認済み。head 側は `echo`/`ls`/`cat`/`pwd`/`cd`/`grep`/`awk`/`sed`/`cut`、書き込み側は `rm`/`sed -i`/`truncate`/`cp`/リダイレクトのいずれでも成立）。**「連結は証拠を増やす方向にしか動かない」という従来の安全性の主張は誤りであった** — 連結しすぎれば**ステートメント区切り**という証拠を失い、連結しなさすぎれば**語の同一性**という証拠を失う。**「安全側の近似」は存在せず、bash と一致させることだけが正解である。** そこで (1) 行継続の処理を専用の走査 `normalize_line_continuations()` **1箇所**へ集約し（偶奇はカウンタではなく「`\`＋次の1文字」の**対消費**の自然な帰結として決まるため、数え間違いという故障モードが構造的に存在しない）、(2) `#` を**この走査の中だけ**でモデル化し（クォート外で語頭に現れたときにコメントを開始し改行で終わる。**用途は行継続の適用可否の判定に限り、コメント本文は除去しない** — 除去は deny → allow 方向の変化を生むため）、(3) `'…'` の内側では連結せず `"…"` の内側では連結する（bash と同じ。前者で bash が触るのは「改行を含む別名のファイル」であって保護対象ではない）、(4) コマンド置換・プロセス置換の内側は**無加工で残して再帰評価の入口で内側の文脈として正規化する**（ダブルクォート内のコマンド置換の中では bash がコマンド文脈へ戻り `#` がコメントになる。文脈スタックを持たずに正しくなる）、(5) **正規化を `find_violation` の入口で1回だけ行い、正規化後の同じ文字列を字句解析と degraded 判定の双方へ渡す**（従来は正常経路だけが結合後を見て degraded は結合前の生のコマンドを見ており、**同じ入力に対して2つの経路が異なる行構造を評価していた**。これが本件と、degraded の「偶発的な安全網」の両方の根であった）。**奇数個の行継続は従来どおり allow のまま維持する**（bash も連結するため deny は誤り）ことを、実機 bash の実行効果（ファイルが残るか消えるか）と突き合わせる**両方向の検証**で固定した
  - **degraded 判定の関数レベルゲートが作業ディレクトリを見ていなかった問題を修正**（1行）: 保護対象ディレクトリを cwd とする状況で、**字句解析できない置換を1つ挟むだけで全判定を回避できた**（`` cd tickets/active && ls `rm APP-001.md #'` `` 等。実機で実際に削除・上書きされる）。同関数のステートメント単位のゲートは cwd を見ていたのに、その手前の関数レベルのゲートで早期 return していた。バッククォートの終端探索がクォート状態を追わないのは **bash と同じ仕様**であり、修正すべきはゲートの側である。あわせて同関数の全ゲート（関数レベル／リテラルリダイレクト／heredoc／文単位／セグメント）を cwd 観点で棚卸しし、cwd を見ないゲートが1つも残っていないことを確認した。同型の入れ子（`$( )` の内側のバッククォートの中で引用符が不均衡な形）については、**置換の終端探索がバッククォート領域を bash と同じ規則で読み飛ばす**ようにして閉じた（読み飛ばさないと対応する `)` を見失い、コマンド全体が degraded へ落ちて内側の書き込みコマンドが読み取りセグメントへ埋もれる）
  - **awk の「字句次元」（プログラム本文の除去規則）を awk の字句規則へ一致させ、「1パスだから安全」という未検証の安全性主張が開けた穴を閉塞**: AW-7（プログラム本文のホワイトリスト）の健全性は「除去したテキストは awk が実行しない」という前提に全面的に依存しているが、**1パス走査が保証するのは除去スパンの開始位置の一致だけで、終端の一致は独立した前提だった**。実際 `awk_strip_literals()` は awk の **`#` コメントを1つもモデル化しておらず**、かつ**文字列リテラルの走査が改行で打ち切られていなかった**ため、コメント内に `"` を1つ置くだけで文字列の対応がずれ、awk が実際に実行するコード（`system(…)` 等）がリテラルの中身として消えて allow になった（`awk 'BEGIN{ #"<改行>system("rm docs/SPEC.md") #"<改行>}'`。コメント側に `"` をもう1つ置いてパリティを戻すため「未閉じ文字列＝deny」にも掛からない。`-e`／`--source=`／間接呼び出し `@x(`／保護対象 cwd 相対のいずれの形でも成立し、実機 gawk 5.2.1 が rc=0 で削除・改変することを使い捨てディレクトリで確認済み）。**対処は除去規則を「開始条件×終端条件」へ分解すること**: ① `#` コメント分岐を1パス走査の**先頭**に置き行末まで除去する（改行は文終端として残す） ② 文字列リテラルの終端に**改行**を加える（awk の文字列は行をまたげない）＋ `\`＋次の1文字の対消費を改行判定より**前**に置く（gawk の文字列内行継続と一致させる。順序を誤ると日常の読み取りが誤denyになる） ③ **どちらの解釈も成り立つ位置では除去しない** — `/` を除算として据え置いた行では、除去位置以降・同一行に `/` が残るなら「判定不能」として deny する（`AWK_OPERAND_END_CHARS` が `+` を含むため hook は `1+ /#/` を除算と読むが、実機 gawk は正規表現定数として受け付け後段を実行する＝実測。① だけを入れると `awk 'BEGIN{x=1+ /#/; system("rm …")}'` で同型の穴が新規に開くため、① と ③ は必ず同時に入れる）。**除去しすぎ（over-removal）だけが allow 方向（危険）で、除去しなさすぎ（under-removal）は deny 方向（安全）**という方向の非対称があるため、曖昧位置では除去しないことが常に正しい
  - **上記の副次的効果として、awk のコメント本文に危険様パターンが現れるだけの読み取りの誤denyが解消**: `awk '{print $1} # a\|b @c system(' tickets/…` のように `#` 以降にのみ `\|`／`@`／`system(`／引用符の不均衡が現れる形は allow になった（**awk はコメントを実行しないため deny する根拠が無い**）。従来「コメント範囲を確定できないため除去しない」と文書化していたが、その根拠（字句レイヤが改行を `;` へ正規化するため）は行構造を走査化した時点で消滅していた。**「扱えない」と書いた記述は、その帰結の*向き*（deny 方向か allow 方向か）を必ず併記する**という規律を設計原則として追加した
  - **degraded 判定のステートメント区切りに単独の `&` を追加**（1文字）: 正常経路は `&` を区切りとして扱い `ls & rm docs/SPEC.md` を deny するようになったが、degraded 経路の区切り集合（`&&`・`\|\|`・`;`・改行）に単独 `&` が無かったため、**` #'` の2文字を足すだけで `&` の後段が先頭 head のセグメントへ埋もれて全防御が消えた**（`ls & rm docs/SPEC.md #'` は実機 bash が rc=0 で削除する。旧版も allow だったため回帰ではないが、「正常経路では deny・2文字足すと allow」という説明不能な非対称は本改修が作ったもの）。**degraded は「旧版の判定要素の上位互換」であることに加えて「正常経路のステートメント区切りの集合」を持たなければならない**。副作用として「クォート内に `&` を含む」×「未閉じクォート」×「後段に保護対象への言及」の形（`grep 'R&D' tickets/… #'`）が誤denyになるが、これは「クォート内 `;`／`&&`／改行 × 未閉じクォート」という旧版から存在する既知の誤denyクラスに対象文字が1つ増えるだけである
  - **正規表現リテラルの直後に除算が連なる形で、awk の字句次元にもう1つ穴が残っていたのを閉塞（曖昧ガードの外側）**: 上記③の曖昧ガードは「`/` を**除算として据え置いた**行」でしか働かないが、**正規表現リテラルが閉じた直後の `/` は awk では必ず除算である**にもかかわらず、除去規則の開始条件が「直前の非空白**文字**が `AWK_OPERAND_END_CHARS` にあるか」だけを見ており、そこに正規表現の終端文字 `/` 自身が無かったため、2つ目の `/` が再び正規表現の開始と読まれた。結果として **2つ目〜3つ目の `/` の間（＝awk が実行する式そのもの）が丸ごとリテラルとして除去され**、`awk 'BEGIN{/x/ / system("rm SPEC.md") / 1}'` が allow になった（`-e`／`--source=`／保護対象 cwd 相対／空正規表現 `//`／空白なし `/x//`／エスケープ入り `/x\/y/`／間接呼び出し `@f(` のいずれでも成立。実機 gawk 5.2.1 が対象ファイルを実際に削除することを使い捨てディレクトリで確認済み。`system()` の副作用は式評価中に発生し、その後 division by zero で awk 自体は異常終了する）。**この経路は除算として据え置く分岐を通らないため曖昧ガードの発火条件（`div_seen`）が一度も真にならず、①〜③で追加した13サブケース（すべて `#` コメント起点）はこの形を1つもカバーしていなかった** — **曖昧ガードは「開始条件が対象言語と一致していること」を前提とした二重の安全網であり、開始条件そのものの誤りは救えない**という教訓を docstring へ記録した。対処は「直前の非空白**トークン**が閉じた正規表現なら除算とみなす」ことであり、**文字集合（`AWK_OPERAND_END_CHARS`）へ `/` を足す形は採らない** — `prev` に残る `/` は「除算演算子の直後」と「正規表現の終端」の双方から来るため文字だけでは出自を区別できず、集合へ足すと前者（awk はオペランド＝正規表現を期待する位置）まで除算と読んで現に deny している形が allow へ転じるからである。改行は awk の文の終端であるためこの状態は改行でリセットする。**除去しない方向（deny 方向）にしか倒れない変更**であり、日常の読み取り70ケースの deny 件数は **1/70 で不変**、6486形の機械的掃引（前置きトークン×区切り×演算子×ペイロード×末尾の直積）で「実機が保護対象を触るのに allow」は **42件 → 0件**、比較スクリプト22本の出力は修正前後で**バイト単位で同一**
  - `tests/test_guard_bash_writes.py` に回帰テスト140件を追加（既存29件は無変更・29件 → 169件、スイート全体 293件 → 433件）。旧版が deny していたコマンド集合と本改修で新たに閉じた形を `LEGACY_DENY_COMMANDS`（126件）として定数化し、1テストで全件 deny を固定する回帰ガードを設けた。**収載の基準は「旧版が deny していたか」または「本改修で塞いだ穴か」**であり、`old=allow` の形を「新版の保守的既定（未知は deny）によって deny になった」という理由だけで入れてはならない（将来安全性を確認して緩める余地を残すため）。逆に `old=deny` の形は現在は誤deny寄りに見えても収載してよく、将来 allow へ緩める余地を残したい形（`@namespace` 等）は本リストではなく個別テストと `INVENTORY_CASES` で判定を固定する
- 状態検証 hook とメトリクス集計に残っていた堅牢性の欠陥5点を解消した（いずれも現行の実運用では発現しにくいが、機械強制の取りこぼしと観測値の誤りである）。設計は `docs/designs/KLK-012.md`
  - **相対パスのチケットが状態検証を素通りしていた問題を解消**: `_ticket_lib.is_ticket` は `"/tickets/active/" in n` で判定していたため `tickets` の直前にスラッシュが必要で、`tickets/active/APP-001.md`（先頭スラッシュ無し）が False になり、`validate_ticket_state.py` のスキーマ検証・遷移検証と `record_metrics.py` のイベント記録が**丸ごと飛んでいた**。判定を `os.path.normpath` による**cwd 非依存の純字句正規化**＋**パスコンポーネント境界での一致**（先頭一致または `/` 直後の一致）へ置き換え、絶対形・相対形の双方を受理する。`os.path.abspath` は採らない（述語がプロセスの作業ディレクトリという隠れた状態に依存し、`docs/worktree-policy.md` の運用前提が破れたとき黙って誤分類するため）。副次的に `x/../tickets/active/A.md` が正しく True になり、`/repo/tickets/active/../../evil.md` の**誤 True が是正**された。`mytickets/active/` のようなコンポーネント境界の偽陽性は生じない。あわせて相対パスかつ実体が hook プロセスの cwd で解決できない Write は「新規作成」と断定せず素通りさせる（AC1 が「初期 status は todo」の誤 deny を新たに生まないための fail-open）。**なお相対形では `tickets_dir_for` が None を返すため、サイドカー由来の prior と in_progress 上限ゲートは fail-open で効かない**（「検証ゼロ」から「ファイル内容ベースの検証あり」への改善であり後退ではない。限界は `is_ticket` の docstring に明記し、判定基準の統一とあわせて KLK-020 へ申し送った）。`guard_bash_writes.py` 側の保護対象判定との**完全な基準統一は行わない**（目的・影響半径が異なる。KLK-010 D2 は有効なまま）
  - **`/metrics` の「現在進行中」に完了チケットが二重表示される問題を解消**: `aggregate.py` が末尾イベントの `to` で現在ステータスを決めていたため、末尾が `retry_reset`（`from_counts`/`to_counts` のみで `to` を持たない）だと `last_to` が `None` になり、done チケットが「サイクルタイム」と「現在進行中（status=None）」へ二重計上されていた。チケットのイベント列を**status イベント（`type != "retry_reset"` かつ `to is not None`）**へ絞り込んでから集計する方式へ変更した。「末尾を1件読み飛ばす」方式は採らない（連続する `retry_reset` に弱く、**進行中チケットの末尾に正当な `retry_reset` が来たときに現在ステータスを失う**）。副次効果として `retry_reset` が「次イベント」となって生じていた 0 秒の滞留ノイズも消える。`check_loop_integrity.py` の L3 照合は `from`/`to` の実値一致で数えるため本バグの影響を受けておらず、変更していない
  - **tz-aware なタイムスタンプが1件混入すると `/metrics` 全体が落ちる問題を解消**: `parse_ts` に tz 正規化が無く `now` も naive だったため、フェーズ滞留の減算と in_progress の経過計算の**両方**が `TypeError` で rc=1 になっていた。naive な値はローカルタイムゾーンとみなして aware 化し（`record_metrics.py` が naive なローカル時刻で記録している事実と一致する解釈）、`now` も aware にした。aware 側を naive へ落とす案は異なるタイムゾーンで記録された時刻の順序を壊すため採らない。`"…Z"` 形式（UTC サフィックス）への対応は本項に含まない（Python 3.11 未満では解析できずイベントが黙って集計から落ちるが、クラッシュはしない。記録側の形式変更の要否とセットの判断のため別途）
  - **frontmatter のインラインコメントが値として解釈される問題を解消**: `status: todo # 未着手` が `'todo # 未着手'` として `VALID_STATUS` 外と判定され deny になり、`retry_counts: # コメント` は空値判定に掛からずネストマップが開かないため配下キーを取りこぼしていた。**クォート状態を追跡する走査**でクォート外の `#` 以降を除去する（`#` がコメントを開始するのは値の先頭または空白の直後に現れ、かつクォートの外側にある場合のみ）。**クォート内の `#`（`title: "issue #123 fix"`）と空白を伴わない `#`（`title: C#`）は保持し、クォートが閉じていない値では一切除去しない**（除去しすぎ＝値の破壊を避ける安全側）。正規表現 `\s+#.*$` 方式は現に正しく動いているクォート内の `#` を壊すため採らない。除去は `_unquote` の**前**に適用するため、`title: "issue #123 fix" # trailing comment` のように従来クォート解除が発火しなかった形も正しく解釈される。影響は `parse_frontmatter` の呼び出し元4箇所（validator・recorder・integrity・`scripts/batch_loop.py`）すべてに及び、いずれも誤 deny／誤検知／fail-closed 停止の解消方向である。なお `title` のような未クォート値に空白＋`#` を書くと切り詰められる（YAML の正しい解釈と一致。回避はクォート）
  - **妥当な JSON だが dict でない stdin で 5 hook すべてが `AttributeError` で rc=1 になる問題を解消**: 同一の構造的欠陥が5ファイルに複製されていたため、点の修正ではなく `_ticket_lib` の共有ヘルパ（`read_hook_payload` / `as_dict`）へ一元化した（README「単一の真実」の方針に沿う）。payload そのものが非 dict（`[]` / `"x"` / `3` / `null`）・`tool_input` が非 dict・`file_path` / `command` / `cwd` が非 str のいずれでも fail-open へ落ちる。**fail-open の出口は hook ごとに異なる**（PreToolUse 系は `allow()`、PostToolUse / Stop 系は `sys.exit(0)`）ためヘルパへは寄せず各 hook のローカルに残した。型の正規化は hook 境界（`main()`）で行い、判定関数（`is_ticket` / `is_spec`）は str を前提とするというレイヤ規約を置いている。`guard_bash_writes.py` は main() 入口と、AC1 により事実と食い違うようになったモジュール docstring 1文の訂正のみで、**判定ロジック（`find_violation` 以下）は1文字も変更していない**
  - `guard_spec_writes.py` の SPEC.md 判定の case-insensitive 化（`spec.md` 等の取りこぼし）は**人間の承認により本項のスコープ外**とし、hook のパス判定基準統一とあわせてチケット KLK-020 へ切り出した。`is_spec` の判定ロジックは変更していない
  - テストは `tests/test_ticket_lib.py`（相対形・パストラバーサル・コンポーネント境界・`Templates/`・`_index.md`・非 `.md` の判定、クォート内 `#` の保持と未閉じクォート、payload ヘルパ）・`tests/test_validator.py`（**相対パスの不正遷移が deny されることの実証**と相対 Write の fail-open）・`tests/test_metrics.py`（相対パスの記録、done＋末尾 `retry_reset`、進行中＋末尾 `retry_reset`、tz 混在を dwell 経路と in_progress 経路の両方で）・`tests/test_loop_integrity.py`・`tests/test_guard_spec_writes.py`・`tests/test_guard_bash_writes.py`（5 hook すべての非 dict stdin）へ **52件を追加**（スイート全体 494件 → **546件**・failures 0・errors 0）。①〜⑤のいずれにも専用テストが存在しなかった状態を解消している
- **`guard_bash_writes.py` の許可経路偽装による任意コード実行を閉塞**（KLK-013・high）: `is_readonly_script_call()` はインタプリタ以降のどの位置でも `NAME=VALUE` 形の語を「環境変数の代入前置き」とみなして読み飛ばしていたが、実際の `python3` は**インタプリタの後の最初の非フラグ語を実行対象スクリプトとして扱う**。この食い違いにより `READONLY_SCRIPTS` の許可経路を偽装して任意コード実行に到達できた。判定を実際のインタプリタの引数解釈へ揃えた。設計は `docs/designs/KLK-013.md`（設計書への実装反映は KLK-023）
- **degraded経路（字句解析できない入力）の能力の非対称を解消**（KLK-014・high）: `degraded_violation()` は空白分割した平坦な語リストしか見ないため、コマンド置換の内側にある書き込みが先頭head（`ls` 等）のセグメントへ埋もれていた。`don't` のような英文コメントや末尾の孤立 `\` を1つ足すだけでdegradedへ落とせるため、**置換内の書き込みをdenyする保護が2文字で全面的に失効**していた。設計は `docs/designs/KLK-014.md`
- **正常経路でのエスケープされたネストのバッククォート置換の未評価を閉塞**（KLK-024・high）: `_skip_backtick` がエスケープされたバッククォート（`` \` ``）をネスト置換の開始とみなさずリテラル文字として扱っていたため、`lex()` が成功する通常経路でも内側の書き込みが再帰評価されずallowになっていた（KLK-014のQuality Gate検証中にtester・reviewerが独立に発見した別系統の穴）。設計は `docs/designs/KLK-024.md`
- **`sed` スクリプト引数の書き込み・実行経路をホワイトリスト方式へ反転**（KLK-015・high）: `w`／`W` コマンドのアドレス前置き形の取りこぼし（**実機GNU sedで保護対象の上書きを確認済み**）、GNU sedの `e` フラグ・`e` コマンド・`-f SCRIPT` の未対応を閉塞した。あわせてREADME・docstring・設計書が実装より強く「sedの `w`／`W` を遮断する」と主張していた記述を訂正。設計は `docs/designs/KLK-015.md`
- **`mentions_guarded` のエスケープ回避によるsed本文検査ゲートの未発火を閉塞**（KLK-029・high）: `s///` の区切り文字が `/` の場合、置換文字列中の保護対象パスをエスケープする必要があり（`docs\/SPEC.md`）、このバックスラッシュが `PATHISH_RE` のマッチを分断していた。保護対象へ言及しているにもかかわらずゲート自体が発火せず、SED-7（KLK-015）の検査が素通りしていた。設計は `docs/designs/KLK-029.md`
- `sed_strip_literals` のパス末尾 `s` による疑似境界探索を是正（KLK-030）: トップレベル走査が「`s`／`y` という文字が現れたら常にs/yコマンドの開始とみなす」設計のため、`tickets`・`docs` のように末尾が `s` のパス文字列内で誤った区切り文字探索が発生していた（検証範囲では誤allowは未確認だが、`sed_strip_literals` 全体の設計特性として残存していたもの）。設計は `docs/designs/KLK-030.md`
- **シェル展開による保護対象パスの分断を閉塞**（KLK-018）: bashが展開して初めて保護対象になる形（ブレース展開・分断glob・パラメータ展開）は、コマンド文字列上に保護対象がリテラルで現れないためhookを完全に迂回できた。展開後の候補を照合する `guarded_paths_after_shell_expansion` を新設して7箇所の呼び出しを差し替え、直積・再帰の爆発は上限（`MAX_BRACE_COMBINATIONS`・`MAX_BRACE_CHAR_COUNT`）とdeny方向フォールバックで抑える。設計は `docs/designs/KLK-018.md`
- シェル制御構文（`for`／`while`／`if`）を含む読み取りコマンドの誤denyを解消（KLK-019）: `head_of()` が制御構文のキーワードを「コマンド」とみなし `ALLOWED_HEADS` に無いため、読み取り専用でもdenyされループが停滞していた（KLK-010と同じクラスの可用性の問題で、AC外だったため未対応で残っていたもの）。設計は `docs/designs/KLK-019.md`
- 孤立した `*` globによる誤deny（false positive）を解消（KLK-031）: `fnmatch.fnmatchcase("SPEC.md", "*")` が常に真になるため、`rm *`・`chmod 755 *`・`tar cf out.tar *` のように `tickets/`・`docs/SPEC.md` と一切関係のないコマンドが「保護対象パスへの言及」と誤判定されうる状態だった。成分がglobメタ文字のみで構成される場合を除外する `has_literal_char` ゲートを導入。設計は `docs/designs/KLK-031.md`
- **glob下のSPEC.md判定に残っていた大小区別による誤allowを閉塞**（KLK-032・high）: KLK-020でSPEC.md判定の主要4箇所が共有ヘルパー `_ticket_lib.is_spec_basename` 経由でcase-insensitive化されたが、`_guarded_paths_from_expanded` はこの一本化の対象に含まれず「5箇所目」として大小区別が残存していた。`docs/sp*.md`・`docs/Spec*.md` 等のglob難読化かつ大小混在のコマンドが人間承認ゲートをすり抜けていた。設計は `docs/designs/KLK-032.md`
- **否定文字クラス `[!...]` の候補抽出漏れによる誤allowを閉塞**（KLK-033）: 候補抽出正規表現 `SHELL_EXPAND_PATHISH_RE` の文字集合に `!` が無いため `rm docs/[!x]PEC.md` がトークン分断され、bashでは `docs/SPEC.md` に一致するのに「言及なし」と判定されていた。あわせて `_ticket_lib.is_spec_basename_fnmatch` の `.upper()` 正規化が否定クラス下で非単調になる問題を和集合形で是正。設計は `docs/designs/KLK-033.md`
- **キャレット否定クラス `[^...]`・POSIX文字クラス `[[:class:]]` の誤allowを閉塞し、ブラケット走査のコスト上限を導入**（KLK-034）: 候補抽出の文字集合へ `^`／`:` を追加し、bashのブラケット式方言（`[^...]`・`[[:class:]]`・`[[.sym.]]`）をPython `fnmatch` へ吸収する正規化を新設した（構造走査による位置依存の `[^`→`[!` 置換で `[a[^]one` 型の意味反転を回避し、クラス構文は `?` への過大近似＝一致集合の上位集合とすることでallow方向の劣化を構造的に排除）。あわせてレビューで検出された走査コストの超線形・無上限性（病的入力でhook自身がタイムアウトし、fail-open方針経由で承認ゲートをすり抜けうる経路）を、走査・終端探索の「pattern中の最後の `]`」での打ち切りと `MAX_BRACKET_SCAN_WORK` の事前チェック＋deny方向フォールバックで閉塞した（24,000字の病的トークンで118.7s → 0.015s・判定は不変）。残る既知の限界（ブラケットのメンバーに候補抽出の文字集合外の文字を含む形・extglob・globstar）はモジュールdocstringへ明記。設計は `docs/designs/KLK-034.md`
- `scripts/list_tickets.py` のcwd依存による**無言の「計 0 件」**を是正（KLK-021・high）: 呼び出し側（orchestrator / `/start-loop`）が「結果が空」と「チケットが存在しない」を区別できず、14日超blocked検出などが無言でno-op化していた。既定のrootをスクリプト位置から解決し、`tickets/active/` が存在しなければstderrへエラーを書いて終了コード1を返す（致命的エラー）ようにしたうえで、走査対象ディレクトリの絶対パスを出力の先頭へ表示する。あわせてKLK-003のreviewerが指摘したMissing Tests 4件（設計が唯一highと格付けしたリスクの固定を含む）を追加。設計は `docs/designs/KLK-021.md`
- KLK-012の副次的な挙動変更が未固定だった点と `.claude/metrics/aggregate.py` の件数不整合を是正（KLK-028）: いずれも承認スコープ内の欠陥ではないが、副次的な挙動変更がテストで固定されておらず将来のリグレッションを検出できない状態だった。設計は `docs/designs/KLK-028.md`
- `/batch-loop` のリアルタイム表示でサブエージェントの発話が区別されない問題と、ストリーム後処理の防御的多層化（KLK-008）: KLK-007のレビューで挙がった非ブロッキングのMedium指摘2件のフォローアップ（安全性＝境界判定・終了コードには影響しない表示品質の課題）。設計は `docs/designs/KLK-008.md`

## [1.7.0] - 2026-07-12

### Added
- SPEC構造チェッカー `.claude/skills/spec-interview/scripts/check_spec_structure.py`: SPEC.mdのテンプレート準拠を機械判定する（セクション0〜14の見出し・§0版数行・REQ/SCR/IF/EH/NFR-IDの付番・§6画面一覧のSCR-IDまたは「該当なし」明記〔UIなし時はIF-xxxを主キーとする提供IF一覧表が必須〕・§7/§8の定義表と検証方法列の非空〔「-」等のプレースホルダも空扱い・列追加はヘッダーから列位置を解決〕・§11スコープ外≥1項目〔番号付きリスト可〕・定義セクション内のID重複〔§13等の参照表は対象外〕・§5↔§6相互参照・Must小見出し配下の明示的OQ非依存）。判定層は FAIL=決定的な違反（上記）／WARN=疑いの提示（見出し不一致・小見出し欠落・§6ユーザー種別の命名揺れ・§9出自注記の不在）／意味論=対象外（/interrogate-specと人間レビューの責務）。HTMLコメント（テンプレートの記入ガイド）は判定前に除去。終了コード 0=準拠・1=非準拠・2=引数誤り/読み込み失敗（非UTF-8含む）。読み取り専用スクリプトであり、書き込み処理の追加は禁止（guard_bash_writes.pyの許可前提）。構造の正はSPEC_TEMPLATE.mdであり、テンプレートの構造変更時は本スクリプトと `tests/test_check_spec_structure.py`（回帰テスト22件）を追随させる
- `guard_bash_writes.py` に読み取り専用スクリプトの許可リスト `READONLY_SCRIPTS` を追加: SPEC.mdを引数に取る構造チェッカーの実行（`python3 <パス> docs/SPEC.md` 形式のみ。`-c`/`-m` 等の別実行経路やリダイレクト併用は従来どおりdeny）を許可する。これがないと本チェッカーの規定動線（/setup 手順5・/interrogate-spec Phase 0）がhookに遮断される
- `/setup` 手順5の診断表に「SPEC有り・構造チェックNG → `/spec-interview` 改訂モードで構造化」の分岐を追加: 外部で作成されたテンプレート非準拠SPECが構造チェックを経ずに `/interrogate-spec` へ誘導され、後工程（wireframe-gen受付・plan-ticketsのID トレーサビリティ）で差し戻されるギャップを解消
- `/interrogate-spec` Phase 0に構造受付を追加（初回起動時とSPEC改訂検知後の(a)再スキャン時）: 非準拠SPECには尋問・再スキャンを開始せず改訂モードでの構造化を推奨する（人間が強行を選択した場合のみ続行し、尋問後の全面構造化がSPEC改訂検知の再スキャンとspec_refsアンカー切れを招くことを告知する）
- spec-interview 改訂モードに手順5「テンプレート非準拠SPECの構造化」を明文化: 全セクション再構成・ID新規採番・不明項目のOQ化、着手前の `docs/spec-qa/` 有無確認と尋問状態アンカー切れの告知、旧→新ID対応の§0記録、完成後のチェックリスト再実行と構造チェッカーによる機械検査。完成チェックリストの変更履歴項目に改訂・構造化時の読み替え（版数を上げる行の追加・既存履歴の保全）を追記し、Step 3にも機械判定可能項目のセルフチェック手段として明記。`/setup` 手順5にも尋問開始済みプロジェクトでの構造化の影響告知を追加。CLAUDE.mdポリシー表へ1行追加

- `/interrogate-spec` セッション終了時に「次の一手の案内」を追加: open と presented がともに0件の場合のみ、deferred残数（件数・high rank有無の併記必須）とともに次工程を案内する（典型は `/wireframe-gen`、UIなしプロジェクトは `/plan-tickets`。ルーティングの正は setup.md 手順5のままポインタ転記）。前工程リレー3スキルのうち本スキルだけが前方ハンドオフを持たず、完了時に非エンジニアが次の一手を見失う導線の袋小路を解消。「完了」は宣言せず（deferredはT5でopenへ戻り得る）、次工程の実行もしない（案内のみ）。open/presented残の場合は「続きは `/interrogate-spec` の再実行」を添える。CLAUDE.mdポリシー表へ「前工程の次の一手ルーティング」行を追加し、既存の暗黙的転記（spec-interview Step 4のハンドオフ）も転記先として可視化

- worktree並行作業ポリシー `docs/worktree-policy.md` を新設: 複数チケットの並行作業時に `git worktree` で作業ツリーを分離する際の運用規約（コードだけをworktreeへ・チケット/メトリクス書き込みはメインworktreeに一本化する「単一ライター原則の空間版」）。gitignoreプリセットで `tickets/` がGit管理外のためworktree側にはチケットが存在せず、hookの状態機械がworktreeごとに分裂する問題を防ぐ。1チケット=1ブランチ=1worktree・並行最大3つ（in_progress上限と対）・配置は兄弟ディレクトリ `../{リポジトリ名}.wt/{チケットID}/`・寿命はチケットと同じ（`git worktree remove` で削除）。worktree側では `tickets/`・SPEC.md編集と `git push` を禁止し、ステータス反映はメインworktreeのorchestratorへ報告する。転記先: implementer.md Git Rules 運用ルール / orchestrator.md Responsibilities / CLAUDE.md Git運用規約（ポインタ）とポリシー表

### Fixed
- `/setup` 手順5の診断表が尋問の完了/未完了を識別できない欠陥を修正: 従来は `docs/spec-qa/` の存在のみで「尋問済み」と判定していたため、open質問が残っていても `/wireframe-gen` へ誘導していた。`QUESTIONS.yaml` の open/presented 残を確認する行を診断表に追加し、残があれば `/interrogate-spec` の続行へ誘導する（deferred は前進を妨げず、件数のみ報告して判断は人間に委ねる）
- SPEC_TEMPLATE.md §4の例にユーザー種別「ゲスト」を追加: §6の例（SCR-001/SCR-003のアクセス可能なユーザー=ゲスト）が§4のユーザー種別に存在せず、完成チェックリスト「アクセス可能なユーザーが§4のいずれかに対応」を例文自身が満たしていなかった不整合を解消（構造チェッカーの横断整合検査で検出）。§9の例にも出自注記の記入例（「本構成は標準構成 v1.0 をデフォルト適用」）を追加（従来はHTMLコメント内にのみ存在し、記入例としてコピーされない位置にあった）
- CLAUDE.md「リポジトリ可視性による.gitignore運用」節の参照を `setup.md 手順1` から `手順2` へ修正（1.6.0の手順繰り下げへの追随漏れ）

## [1.6.0] - 2026-07-08

### Added
- `/setup` に手順1「リポジトリの初期化判定（Kitからの切り離し）」を追加: `git clone` 経由でKitを導入すると新プロジェクトの `origin` がKit本体（`kenesis-loop-kit`）を指したままになり、そのまま `git push` するとKit本体へ向かう問題を検出し、人間の明示承認後にのみ `.git` を再初期化（`rm -rf .git && git init`）してクリーンな履歴で新プロジェクトを開始できるようにした。`origin` が `kenesis-loop-kit` を含まなければスキップ（冪等）、Kit本体の開発時は誤爆防止の確認で除外。既存手順（.gitignore/Obsidian/略称/SPEC診断/結果報告）は手順2〜6へ繰り下げ、CLAUDE.mdポリシー表の `setup.md 手順N` 参照とREADMEのセットアップ節を追随

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
