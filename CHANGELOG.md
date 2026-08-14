# CHANGELOG

Kenesis Loop Kitのすべての変更はこのファイルに記録されます。
フォーマットは [Keep a Changelog](https://keepachangelog.com/ja/1.0.0/) に準拠し、
バージョン管理は [Semantic Versioning](https://semver.org/lang/ja/) に従います。

---

## [Unreleased]

### Added
- バッチ外部駆動スクリプト `scripts/batch_loop.py`（1チケット=1セッション）: チケットごとに `claude -p "/start-loop {ID}"` を新規ヘッドレスセッションで逐次起動し、セッション境界でチケットファイルの状態を検査して前進・停止を判定する（完了判定はファイル状態が正: done/に `status: done`。終了コードは異常検出の補助）。プリフライトP1〜P9（linked worktree検出・ID一意存在・status検証・in_progress上限・14日blocked排除・SPEC存在または `--allow-missing-spec`・claude CLI実行可能性・status/retry_countsスナップショット・done/件数警告）を機械化し、違反は開始前に一括表示して停止。実行前の承認サマリへのy/N応答が旧バッチ事前承認の実体（`--yes` でスキップ可）。停止条件（境界判定）は異常終了（exit≠0/timeout）・active/残存done・blocked（リトライ上限超過を包含・ブロッカー本文表示）・未完了status・範囲外チケット変化・差し戻し増分（既定停止・`--continue-on-rework` で人間が明示緩和可）で、正常完了時のみ次チケットへ進み最終チケット後は必ず停止する。暴走ガードは `--max-turns 200` 既定・`--max-budget-usd`・`--timeout-min`。stdlibのみ・fail-closed（hooksのfail-open規約とは逆・人間実行の監督ツール）・tickets/読み取り専用（単一ライター原則の維持）。終了コード 0/1/2/3/130。設計は `docs/designs/KLK-001.md`
- `tests/test_batch_loop.py`（59テスト）: プリフライトP1〜P9・境界判定1〜7の分岐と優先順位・駆動プロンプト組立・フラグ伝播・fail-closed（`_ticket_lib` import失敗・frontmatter解析不能）・SIGINT時の子プロセスterminateを検証。claude起動は `--claude-cmd` へのフェイク実行ファイル注入で代替し、CI・テストで実claudeを起動しない
- ヘッドレスCLI挙動の実測記録（2026-07-19・claude CLI v2.1.215）: PreToolUse `ask` はヘッドレスで自動deny（ハングなし）／正常完了・deny多発は exit 0・`--max-turns` 到達は exit 1／Stop hookの `decision: "block"` は `-p` でも機能（境界判定2〜4は代替ではなく防御の重複）／`--max-turns` は `--help` 非掲載の隠しオプションだが機能する（将来削除時は初回セッションでAPI消費なしに即停止・回避は `--max-turns 0`）。docs/designs/KLK-001.md §4 と docs/batch-loop.md に記録
- `scripts/batch_loop.py`のstream-json化: `build_claude_command()`へ `--output-format stream-json --verbose --include-partial-messages --forward-subagent-text` を無条件付加し、`run_session()`をstdout PIPE化＋専用リーダースレッド＋queueベースのタイムアウト管理へ置き換え、子プロセスの応答をリアルタイムに人間可読な進捗（assistantテキストデルタ・tool_use・tool_result・サブエージェント進捗）として標準出力へ表示するようにした（現状の素通し継承表示から変更）。`render_event`/`_brief`/`handle_stream_line`は表示専用の防御的パース（JSONデコード失敗・未知のtype・レンダラー内部例外はいずれも表示スキップに留め）で、境界判定・終了コードには一切影響しない。`run_session()`の外部契約（引数・戻り値）は不変で、既存のタイムアウト・SIGINT契約はそのまま維持される。`scripts/batch_loop.py`に実行権限（`chmod +x`）を付与。`tests/test_batch_loop.py`にrender_event単体テスト・stream-json統合テストを追加（44件）。stream-json下のヘッドレス挙動実測（VS-1）と`--forward-subagent-text`の実イベント列実測（VS-2。実スキーマに合わせrender_eventを校正）はdocs/batch-loop.md「ヘッドレスセッションの挙動」節に記録。設計は`docs/designs/KLK-007.md`
- `/batch-loop-inline`コマンド（`.claude/commands/batch-loop-inline.md`）と運用ガイド`docs/batch-loop-inline.md`を新設: KLK-001が非推奨化した旧方式（単一セッションへ事前承認テンプレートを送り、orchestratorが同一セッション内で複数チケットを連続処理する方式）を、現行ポリシー（`docs/worktree-policy.md`のworktree分離・KLK-002のモデル割当）と整合させたうえで、外部駆動`/batch-loop`とは別コマンドとして復旧した。差し戻し検知の粒度を旧方式の「即停止」から外部駆動版と同じ「チケット境界での停止」へ変更（実装ループ内の人間非介在の原則を優先。理由はdocs/batch-loop-inline.mdに明記）。対話セッション専用（ヘッドレス実行は想定しない）で、少数件（目安2〜3件）での利用を推奨

### Changed
- **`/batch-loop` の役割を「セッション内での連続ループ実行」から「プリフライト検証（`--dry-run`）と実行コマンドラインの案内」へ変更（後方非互換）**: バッチ本体は人間がターミナルで `python3 scripts/batch_loop.py {ID列}` を実行する外部駆動方式（1チケット=1セッション）となり、単一セッションへのサブエージェントレポート蓄積によるトークン累積を解消。コマンドはNeverで「セッション内で `claude -p` を起動しない」「`--dry-run` 以外を実行しない（`--yes` での承認代行も禁止）」を明示
- `docs/batch-loop.md` をバッチ外部駆動ガイドへ全面改訂: 旧→新セマンティクスの写像表（差し戻し即停止→セッション境界停止を含む）・プリフライト・停止条件・フラグ・終了コード・ヘッドレス実測記録・「実行中は同リポジトリで対話セッションを開かない」（二重ライター防止）を掲載。旧・セッション内手動テンプレート方式は非推奨（トークン累積）として1段落の言及に縮小（テンプレートはGitヒストリ参照）
- CLAUDE.md スラッシュコマンド一覧の `/batch-loop` 行と、ポリシー表「バッチ連続実行の事前承認」行を新方式へ更新（定義の正は docs/batch-loop.md のまま・実行責任者=人間 + scripts/batch_loop.py・本文セクションの追加なし）。`start-loop.md`・`plan-tickets.md`・`setup.md` の `/batch-loop` 誘導文、README（ディレクトリツリーへ scripts/ 追加・コマンド表・使用例）も追随
- `docs/batch-loop.md`冒頭に外部駆動`/batch-loop`とセッション内`/batch-loop-inline`の使い分け指針（比較表）を追加し、末尾「旧方式（セッション内手動テンプレート）について」節を`/batch-loop-inline`への案内へ差し替え
- `.claude/agents/orchestrator.md`「改善ループ（人間の判断後）」テーブル直下に、バッチ実行（`/batch-loop`・`/batch-loop-inline`）時はバッチ開始時の事前承認がチケット間の前進判断を代行し、テーブルの判断が適用されるのはバッチ終了後であることを明記する注記を追加（テーブル自体は再定義しない）
- CLAUDE.md スラッシュコマンド一覧へ `/batch-loop-inline` 行を追加し、ポリシー表「バッチ連続実行の事前承認」行を外部駆動/セッション内の2コマンド体制に更新（本文セクションの追加なし）。`batch-loop.md`・`start-loop.md`・`plan-tickets.md`・`setup.md`・READMEに`/batch-loop-inline`への相互参照を追記
- `guard_bash_writes.py` の判定粒度を3レイヤ（L1字句／L2パス／L3構文）へ再構成し、`.claude/hooks/README.md` の該当行を更新。ホワイトリスト `ALLOWED_HEADS` に書き込み経路を持たないコマンド（`cd`〔セグメント自体は無条件許可。移動先の作業ディレクトリのみ追跡し、後続ステートメントの相対パス判定に使う〕・`pwd`・`echo`・`cut`・`tr`・`awk`・`nl`・`rev`・`realpath`・`readlink`）を追加した。`printf` は README「ローカルでの動作確認」の注記（printf はホワイトリスト外）と対であるため意図的に追加していない。`_ticket_lib.is_ticket`（厳密判定）との基準不統一は目的の違いによる意図的なものとしてモジュール docstring に明記した（統一の検討は別チケット）

### Fixed
- `guard_bash_writes.py` の誤deny（false positive）とすり抜け（false negative）を解消: 素朴な `command.split("|")`・空白トークン分割・部分文字列判定をやめ、シェルの字句解析を尊重する方式（クォート状態を追跡してクォート外の演算子だけを最長一致で切り出し、語チャンクは `shlex.split(posix=True)` でクォート解除）へ置き換えた。両者は同一根因の表裏であり一体で修正している。設計は `docs/designs/KLK-010.md`
  - **誤denyの解消**: 正規表現の選択子（`grep -E '^(id|title):' tickets/...`）をシェルパイプと誤認しない／`cd`・`awk` 等がホワイトリスト不在で弾かれない／クォート内の `<<`（`grep -c '<<EOF' ...`）をヒアドキュメントと誤認しない／保護対象に触れない後段リダイレクト（`cat tickets/... && echo x > "$TMP"`）を巻き添えにしない（出力リダイレクトをステートメント単位で判定し、変数先は同一コマンド内で保護対象を代入された変数のときのみ deny）
  - **すり抜けの解消**: sed in-place の全表記（`-i` / `-i.bak` / `-ni` / `-si.bak` / `--in-place` / `--in-place=SUFFIX` / `-i''`）／インタプリタワンライナー内のリテラルパス（`python3 -c "open('docs/SPEC.md','w')..."`。パス検出をトークン境界に依存しない候補抽出＋basename 完全一致へ変更し、`MYSPEC.md`・`SPEC.md.bak` では誤denyしない）／コマンド置換・プロセス置換の内側（`ls $(rm tickets/...)`・バッククォート・`<(...)`。深さ上限3で再帰し上限到達時は保守側で打ち切り）／パストラバーサルによる `.claude` 除外の悪用（`os.path.normpath` による正規化を除外判定より先に適用）
  - **副作用の予防**: `awk` をホワイトリストへ加えたことで新たに素通りしうる awk のプログラム内リダイレクト（`awk '{print > "docs/SPEC.md"}'`）を同時に検出対象へ追加し、同型の sed の `w` コマンド（`s/a/b/w FILE`）へも一般化した
  - **新しい解析基盤が生んだ抜けの解消**: 字句レイヤの導入で新設された4系統の false negative を塞いだ。(1) コマンド置換の**外側**方向 — 置換で包むだけで判定を外せた形（`rm $(echo docs/SPEC.md)`・`` rm `…` ``・`sed -i 's/a/b/' $(…)`・`cat a | tee $(…)`・`echo x > $(…)`）を、位置インデックス付きプレースホルダ（`__KLK_SUBST_0__`）で置換の帰属を保持し、言及ゲート・リダイレクト先・変数代入値・sed/awk 規則の4用途で解決することで捕捉する（先頭コマンド名と find/git の完全一致規則は意図的に解決しない）。帰属が厳密なため `ls $(cat tickets/…); rm /tmp/junk` の後続ステートメントは巻き添えにしない。(2) degraded mode — 旧版が持っていたステートメント分割・パイプ分割・パイプライン単位の言及ゲートを復元し、`ls ; rm docs/SPEC.md #'`・`cat x && tee tickets/… #'`・`find tickets/… | xargs rm #'` を捕捉する。(3) awk の変数束縛 — `-v f=PATH` / `-vf=PATH` / `--assign f=PATH` / 位置引数 `f=PATH` で保護対象を awk 変数へ束縛する形（`awk '{print > f}' f=docs/SPEC.md in.txt`）と、文字列リテラルを除去したうえでの `print`/`printf` 出力リダイレクト（`awk '{print > FILENAME}' tickets/…`）を検出する。読み取り awk（`-F'|'`・`NR>1`・`$1 > 2`・`printf "%s|%s"`・`-v OFS=,`）は allow のまま。(4) `cd` による作業ディレクトリの移動 — 保護対象配下へ移動した後の相対パス書き込み（`cd tickets/active && rm APP-001.md`・`cd tickets/done && echo x > APP-001.md`）を捕捉する（`cd` セグメント自体は無条件許可を維持。`cd "$DIR"` / `cd $(…)` は追跡打ち切りで誤denyしない）。あわせて `( rm tickets/… )`（`(` が独立語になる形）の先頭コマンド判定と、演算子の種別表の一元化（`OPERATOR_KINDS`）を行った
  - **先頭コマンド位置の一元化**: 先頭コマンドに当たる語の位置判定を `head_index` へ集約し、`head_of`・`cd` のオペランド抽出・`git` のサブコマンド抽出・`awk` の引数走査が同じ位置を共有するようにした。従来これらは「先頭語の次から」（`words[1:]`）を前提にしていたため、環境変数代入の前置きやグループ化の `(` があると前提がずれ、`X=1 cd tickets/active && rm APP-001.md`（および `( cd tickets/active && rm APP-001.md )`）で cwd 追跡が働かず素通りし、逆に `X=1 git add tickets/active/APP-001.md` は `git` 自身をサブコマンドと誤認して誤denyになっていた。両者を同時に解消している（`X=1 git checkout` / `git rm` / `git restore` は従来どおり deny）
  - 字句解析できない入力（未閉じシングル/ダブルクォート・未閉じバッククォート・未閉じ `$(`・末尾の孤立エスケープの5系統。`don't` のような英文コメントでも成立する）は allow せず、**旧版と同じ判定要素をすべて持つ**簡易判定へ落とす（`rm tickets/... #'` を素通りさせないため）。旧版から意図的に外したのは「リダイレクト先が `$`/バッククォートを含むだけで deny する」規則のみ。この経路ではクォート内の `|` を誤ってパイプと解釈する誤denyが旧版と同じく残る。内部エラーでの fail-open は従来どおり
  - **既知の未対応（本 hook の導入当初から存在する穴・別チケット候補）**: `sort -o FILE` / `--output=FILE`・`uniq INPUT OUTPUT` の第2位置引数・`sed -f SCRIPT`・GNU sed の `e` フラグ（任意コマンド実行）。モジュール docstring と `.claude/hooks/README.md` に明記し、`ALLOWED_HEADS` へコマンドを追加するときは設計書 §3-9 の書き込みベクタ棚卸し表を更新する規律を定めた
  - `tests/test_guard_bash_writes.py` に回帰テスト62件を追加（既存29件は無変更・29件 → 91件、スイート全体 293件 → 355件）。旧版が deny していたコマンド集合を `LEGACY_DENY_COMMANDS`（31件）として定数化し、1テストで全件 deny を固定する回帰ガードを設けた

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
