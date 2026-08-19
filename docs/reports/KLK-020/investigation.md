# KLK-020 調査報告（investigator / Mode A）

investigator.md の Required Output Format に基づく詳細外部化ファイル。チケット本文には要点＋本ファイルへのポインタのみを残す。

## 1. Findings
1. **(a) SPEC.md大小区別は実際に再現する**: `is_spec`・`_is_guarded_path` とも `"docs/spec.md"`・`"docs/Spec.md"`・`"docs/SPEC.MD"` を実機で **True→False** に取りこぼす（両者とも同じ大小区別で対称に穴がある＝実測確認済み）。
2. **(b) 非対称も再現するが、内容は「先頭スラッシュ不問」よりさらに広い**: `_is_guarded_path` は境界チェック無しの純粋な部分文字列一致（`"tickets/active" in path`）で、`"mytickets/active/A.md"` や `"atickets/active/A.md"` まで True にする。`is_ticket` はコンポーネント境界を要求し、これらを False にする（実測で確認、詳細後述）。
3. `guard_bash_writes.py` は `_ticket_lib.is_ticket` を**一度も呼んでいない**（docstringで言及するのみ）。両者は完全に独立実装であり「統一」は関数呼び出しの共有ではなく判定ロジックの整合を意味する。
4. **チケットAC自体に不整合がある**: AC（frontmatter L39）は設計判断の記録先を `docs/designs/KLK-013.md` としているが、`docs/designs/KLK-013.md` は既に**別チケット**（is_readonly_script_call の任意コード実行）の設計書として存在する。KLK-013→KLK-020への改番（ログ2026-08-16 11:31）後に修正されなかった記述ミスと判断される。
5. `.claude/hooks/README.md`「ルールを変更するとき」は `_ticket_lib.py` の状態機械定数（VALID_STATUS等）専用の手順であり、パス判定関数（is_spec/_is_guarded_path/is_ticket）の変更手順は記載がない。

## 2. Evidence
1. 実機検証（empirical, 2026-08-18, 本リポジトリdevelop HEAD `f3cff49`）: SPEC.md大小区別・is_ticket非対称ともに再現をpythonから直接呼び出して確認（全文は下記A・B節）。
2. `codebase`: `.claude/hooks/guard_spec_writes.py:37-41`（`is_spec`）、`.claude/hooks/guard_bash_writes.py:787-794`（`_is_guarded_path`）、`.claude/hooks/_ticket_lib.py:109-137`（`_under_dir`/`is_ticket`）。
3. `codebase`: `is_ticket` 呼び出し元は4件（`validate_ticket_state.py:203`／`record_metrics.py:53`／`scripts/batch_loop.py:150,330,395`／`scripts/list_tickets.py:104`）。M2の指摘どおり4件目が現存することをgrepで確認。
4. `local_docs`: `docs/designs/KLK-010.md` L701-703（D2）、`docs/reports/KLK-012/review.md`（M1・M2・R10節）。
5. `empirical`: `python3 -m unittest discover -s tests` 実行 → **736件 OK**（failures/errors 0）。詳細はF節。

## 3. Dependency Graph
1. `is_spec`（guard_spec_writes.py）← 呼び出し元1件（main）。`_ticket_lib` は `emit_pretooluse_decision` のみ利用、`is_spec`とは無関係。
2. `_is_guarded_path`（guard_bash_writes.py）← `guarded_paths`／`cwd_is_guarded`／`guarded_write_target` 経由で多数の判定点から利用。並行実装 `_is_guarded_path_component`（sed/awk専用）も同型のSPEC.md大小区別を独立に持つ（3箇所目）。
3. `is_ticket`（_ticket_lib.py）← 4呼び出し元（Evidence③）。すべて状態検証・メトリクス・一覧表示系で、guard_bash_writes.pyからは非参照。
4. `is_project_spec`（_ticket_lib.py, KLK-016）← `record_metrics.py` のみ。SPEC大小区別を独立に持つ4箇所目（ticket未言及だが影響範囲として要考慮）。
5. 詳細な呼び出し一覧・grep結果は下記C節参照。

## 4. Risk Areas
1. **AC誤記による設計書破壊リスク**: architectがAC文面どおり `docs/designs/KLK-013.md` へ書き込むと、既存の無関係チケット（is_readonly_script_call）の設計書を上書きする。着手前に是正が必須。
2. **SPEC.md大小区別の実害はファイルシステム依存**: case-sensitiveなFS（Linux）では`spec.md`は別ファイルになるだけだが、case-insensitiveなFS（macOS既定/Windows）では実質的に同一ファイルへの書き込みとなり、人間承認ゲートを完全に迂回しうる。本環境のFS種別は未検証（Unknown参照）。
3. **is_project_spec（KLK-016のSPECドリフト検知）も同じ大小区別を独立に持つ**が、チケットのrelated_filesにも受け入れ条件にも明記が無い。is_spec/_is_guarded_pathだけ直すと3つ目の経路が取り残される非対称を新たに生む可能性。
4. `_is_guarded_path_component`（sed/awk専用ゲート）も同型の大小区別を持つ独立実装であり、is_spec/_is_guarded_pathのみを直すとここだけ取り残される。
5. `is_ticket`↔`_is_guarded_path`統一は「厳密判定 vs 再現率優先」という異なる用途要求の衝突であり、安易な統一は既存の設計判断（過検知の許容 for bash guard／過小検知の排除 for 状態検証）を壊すリスクがある。

## 5. Assumptions
1. チケットAC L39の `docs/designs/KLK-013.md` は `docs/designs/KLK-020.md` の誤記（KLK-013→KLK-020改番の巻き添え）と推測する（`docs/designs/README.md`の命名規約「{ID}はチケットIDと一致」に基づく推測。確定は人間/orchestratorの判断）。
2. KLK-010 D2の「影響半径（3hookへ波及）」は、KLK-010執筆時点の呼び出し元3件（validator/recorder/batch_loop）を指すと推測する（KLK-010.md本文に3件の内訳の明記は無く、KLK-012レビューが「設計§5は3件」と述べる記述と整合させた推測）。
3. 本番運用環境のファイルシステムのcase-sensitivity（WSL2/Linux/macOS/Windowsのどれで実運用されるか）は本調査では確認していない一般知識レベルの前提。

## 6. Unknowns
1. **【要人間確認】チケットAC L39の設計書参照先誤記**: `docs/designs/KLK-013.md`は既存の別チケット設計書であり衝突する。architect着手前に「KLK-020.mdへ書く」という訂正の承認が必要（investigatorはチケット編集権限を持たないため訂正できない）。
2. **【要人間確認】SPEC.md大小区別の実害を左右するデプロイ先FSのcase-sensitivity**は組織内の運用環境に関する情報であり、コード調査だけでは確定できない（surrendered。検証方法: 実運用環境でのFS確認、またはこの前提によらず一律修正する方針の確認）。
3. **is_ticket↔is_guarded_token「統一するか意図的不統一を維持するか」自体はarchitectの設計判断事項**（investigatorは判断せず材料提示に留める。KLK-010 D2の根拠3点のうち「KLK-012と衝突」は既にKLK-012完了により解消済みで、残る2点（目的の違い・影響半径）が再評価対象）。

---

## A. 再現手順の実機検証結果

`.claude/hooks` を `sys.path` に追加し、`gsw.is_spec` / `gbw._is_guarded_path` / `lib.is_ticket` を直接呼び出して検証（2026-08-18、develop HEAD `f3cff49`、Linux WSL2上）。

**(a) SPEC.md 大小区別**

| path | is_spec | _is_guarded_path |
|---|---|---|
| `docs/SPEC.md` | True | True |
| `docs/spec.md` | **False** | **False** |
| `docs/Spec.md` | **False** | **False** |
| `docs/SPEC.MD` | **False** | **False** |

→ 再現手順(a)は完全に再現し、`is_spec`と`_is_guarded_path`は**対称に**（両方とも）同じ大小区別を持つ。片方だけ直すと新たな非対称を作るため「同時に」修正する必要があるというACの前提は妥当。

**(b) is_ticket ↔ _is_guarded_path の非対称**

| path | is_ticket | _is_guarded_path(normpath後) | norm |
|---|---|---|---|
| `tickets/active/APP-001.md` | True | True | 同一 |
| `mytickets/active/APP-001.md` | **False** | **True** | 非対称 |
| `/repo/mytickets/active/APP-001.md` | **False** | **True** | 非対称 |
| `sub/tickets/active/APP-001.md` | True | True | 同一（KLK-012で相対対応済み） |
| `x/../tickets/active/APP-001.md` | True | True | 同一（traversal正規化後） |
| `docs/tickets_active/APP-001.md` | False | False | 同一（区切り文字が無く両者とも非該当） |
| `atickets/active/APP-001.md` | **False** | **True** | 非対称 |

→ 再現手順(b)も再現する。ただしチケット本文の表現「先頭スラッシュ不問」よりも実態は広い。`_ticket_lib._under_dir` は `n.startswith(marker) or ("/" + marker) in n`（`marker="tickets/active/"`）で**コンポーネント境界**（文字列先頭 or 直前が`/`）を要求するのに対し、`guard_bash_writes._is_guarded_path` は `"tickets/active" in path`という**境界チェックなしの部分文字列一致**であり、「`tickets`の直前に`/`が無くてもよい」だけでなく「`tickets`の直前がアルファベットで連結していても一致する」（`mytickets`・`atickets`）。この非対称の向きは「`guard_bash_writes`側が過剰検知（安全側）・`is_ticket`側が精密（過検知回避）」であり、KLK-010 D2の「再現率優先」という設計意図と整合する挙動である（バグではなく設計どおりの帰結）。

## B. SPEC.md判定ロジックの現在箇所（大小区別の影響範囲）

同一の大小区別特性を持つ実装が**4箇所**存在する。ACは(1)(2)の2箇所のみを名指ししているが、(3)(4)も同型の欠陥を独立に持つため、architectはこれらを「同時に直すか」「意図的にスコープ外とするか」を明示的に判断する必要がある。

1. `guard_spec_writes.is_spec`（`.claude/hooks/guard_spec_writes.py:37-41`）— `n.rsplit("/", 1)[-1] == "SPEC.md"` 完全一致。ACで名指し。
2. `guard_bash_writes._is_guarded_path`（`.claude/hooks/guard_bash_writes.py:787-794`）— `os.path.basename(path) == "SPEC.md"`。ACで名指し。
3. `guard_bash_writes._is_guarded_path_component`（同ファイル1176-1188付近）— sed/awk専用ゲート（KLK-029で新設）。`"SPEC.md" in path.split("/")` で同じ大小区別。docstringには「`_is_guarded_path`のOR追加専用」と明記されており、`_is_guarded_path`側を直した場合でもこちらは独立して大小区別が残る。**ACに記載なし**。
4. `_ticket_lib.is_project_spec`（`.claude/hooks/_ticket_lib.py:157-172`, KLK-016で新設）— `n == _normalize_path(target) or n == "docs/SPEC.md"`。`record_metrics.py`のSPECドリフト検知サイドカー（`docs/.spec_state.json`）の基準になる。case-insensitiveなFS上では、(1)(2)を直しても本関数が大小区別のままだと「大小変え字での書き込みがsha256ハッシュ監視の対象から漏れる」余地が残る。**ACにもrelated_filesにも記載なし**（ただし`_ticket_lib.py`自体はrelated_filesに含まれている）。

なお(4)は`guard_spec_writes.is_spec`とは**別の意図的不統一**（KLK-016 D3・ネストしたSPEC.mdの扱い範囲の違い）を既に持っており、これは大小区別の論点とは直交する。architectが(4)を触る場合、KLK-016 D3の意図（プロジェクト直下のみを対象とする）まで壊さないよう切り分けが必要。

## C. is_ticket呼び出し元の全数（M2対応）

`grep -rn "is_ticket\b"` で確認した現在の呼び出し元は4件（KLK-012レビューM2の指摘どおり）:

1. `.claude/hooks/validate_ticket_state.py:203` — Write/Edit前の状態遷移検証（PreToolUse hook）
2. `.claude/hooks/record_metrics.py:53` — 遷移イベント記録の対象フィルタ（PostToolUse hook）
3. `scripts/batch_loop.py:150,330,395` — バッチループの対象チケット列挙・in_progress件数カウント
4. `scripts/list_tickets.py:104` — 一覧表示が使うチケット一覧表示のフィルタ（KLK-003で追加、KLK-012設計評価時には存在せず漏れていた）

4件のうちhookディレクトリ内（`.claude/hooks/`）にあるのは(1)(2)の2件のみで、(3)(4)は`scripts/`配下のCLIスクリプト。KLK-010 D2本文の「影響半径（3hookへ波及）」という表現は、KLK-010執筆当時の呼び出し元3件（validator/recorder/batch_loop）を指すと推測されるが、KLK-010.md本文中に3件の内訳を明示した記述は見当たらず（推測であることを明記。Assumptions参照）。いずれにせよ、いずれの呼び出し元も「チケットの状態機械検証・観測性・一覧表示」という**精密性が要求される用途**であり、`guard_bash_writes`の「コマンド文字列の断片が保護対象に言及しているか」という再現率優先の用途とは性質が異なる、というKLK-010 D2の目的論的根拠自体は本調査でも追認できる。

## D. KLK-010 D2 の根拠の現況（再評価用材料）

D2原文（`docs/designs/KLK-010.md` L701-703）:
> 目的（厳密判定 vs 再現率優先）・スコープ（related_files 外・KLK-012 と衝突）・影響半径（3hookへ波及）の3点が根拠。意図的な不統一である旨は docstring に記載済み。

3点の現況:
1. **目的（厳密判定 vs 再現率優先）**— 現在も有効な論点。B/Cで確認したとおり、用途が異なる（状態機械の精密な適用対象識別 vs コマンド文字列中の言及の見落としゼロ化）。安易な統一（例: is_ticketの境界判定をguard_bash_writes側にも採用）は`ls tickets/active/`のような日常コマンドの取りこぼしを生む（同docstring L210に明記）。
2. **スコープ（related_files外・KLK-012と衝突）**— KLK-012は2026-08-16に完了（マージコミット`ffaf02b`、チケット記載）。この「衝突」による保留理由は**解消済み**であり、現時点でこの理由だけでは不統一維持の根拠にならない。
3. **影響半径（3hookへ波及）**— 現在は4呼び出し元（C参照）。KLK-012でis_ticketに相対パス対応（境界判定を保った上でのAC1）が入ったことで、`is_ticket`はより多くのケースで`_is_guarded_path`と同じ結論（True/True）を返すようになっている（Bの表の`sub/tickets/active/...`・`x/../tickets/active/...`行を参照）。したがって両者の**乖離幅は縮小**しているが、`mytickets/active/...`等の境界なし一致というギャップ自体はKLK-012の変更範囲外であり残存する。

KLK-012レビュー（`docs/reports/KLK-012/review.md`）からKLK-020への申し送り原文（M1・M2・R10・「隣接チケットとの干渉」節）はチケット本文に既に転記されており、本調査で内容の齟齬は確認されなかった（review.mdの全文を読了し、チケット記載と突き合わせ済み）。特にR10節末尾「ただしM1と併せて『相対パスは部分的にしか強制されない』ことがKLK-020の必須入力になる点は明確に申し送るべき」という一文は、KLK-020のAC「is_ticketとis_guarded_tokenの判定基準統一」の議論に、M1（相対Writeの一部allow化）とR10（相対形でのfail-open）の両方を結び付けて検討すべきという要求であり、architectはこの2点をD2再評価とセットで扱う必要がある。

## E. README「ルールを変更するとき」の現状

`.claude/hooks/README.md` L57-61の手順は次の3ステップのみで、対象は明示的に状態機械定数（`VALID_STATUS`/`REQUIRED_KEYS`/`RETRY_CAPS`/`LEGAL_TRANSITIONS`）に限定されている:
1. `_ticket_lib.py`の定数を更新
2. CLAUDE.md/orchestrator.mdの対応定義も更新
3. `tests/`を更新し全件パス確認

パス判定関数（is_spec/_is_guarded_path/is_ticket等）の変更手順は**この節の対象外**であり、記載が無い。一方`guard_bash_writes.py`のdocstring内には`ALLOWED_HEADS`追加専用の5手順（KLK-010 §3-9/§3-10と同内容）が別途存在する。architectは「今回の修正がREADMEのどの手順に該当するか（既存手順の適用外であり、新たに記載を追加すべきか）」を設計に含めるかを判断する必要がある。ACは「READMEの手順に従い、testsを更新して全件パス」を求めているが、既存手順自体がパス判定ロジックの変更を想定していない点はarchitectへの申し送り事項。

## F. 既存テストの現状

`python3 -m unittest discover -s tests` を実行（2026-08-18、develop HEAD `f3cff49`）:
```
Ran 736 tests in 48.274s
OK
```
failures/errors 0。`test_ticket_lib.py`の`TestIsTicket`クラスには相対パス対応（KLK-012 AC1）のテストのみ存在し、大小区別（`spec.md`等）や`_is_guarded_path`との非対称（`mytickets/active/...`等）を対象にしたテストは**存在しない**（grepで"mytickets"・小文字"spec.md"を検索し不在を確認）。`test_guard_spec_writes.py`にも大小区別のテストは無い。`test_guard_bash_writes.py`は"SPEC.md"（大文字）を含むテストケースを多数持つが、小文字・混在ケースは1件も無い。したがって本チケットの修正後は新規テストの追加が必須であり、既存テストとの後方互換は（現状カバレッジが無いため）壊れる心配が無い。

## G. チケットAC自体の不整合（要人間確認事項の詳細）

チケットfrontmatter L39（受け入れ条件）:
> `_ticket_lib.is_ticket` と `guard_bash_writes` 側の判定基準について、統一 / 意図的な不統一の維持を設計判断として明示し、根拠を `docs/designs/KLK-013.md` に記録する

`docs/designs/KLK-013.md`は実在し、内容は「is_readonly_script_call()の許可経路偽装による任意コード実行」という**全く別のチケット**の設計書（frontmatter確認済み：`ticket: "KLK-013"`）。チケットのログ（2026-08-16 11:31）に「別セッションとのID重複によりKLK-013→KLK-020へ改番」とあり、この改番の際にAC本文中の設計書パス参照が追随更新されなかったものと推測される。`docs/designs/README.md`の規約「`{ID}`はチケットIDと一致させ」に従えば、正しい参照先は`docs/designs/KLK-020.md`のはず。architectがAC文面をそのまま実行すると、無関係な既存設計書（KLK-013.md）を上書き・追記してしまうため、**着手前に人間/orchestratorによる訂正確認が必要**。

## 次のエージェントについて

Unknowns（特にAC誤記の確認）が未解決のため、Mode Aの Handoff 規約に従い、architectへの一方的な推奨は行わず、orchestrator経由で人間へUnknownsをエスカレーションしAC訂正の要否判断を仰ぐことを推奨する。訂正が確認され次第、architectへの委譲（D2再評価・SPEC.md大小区別修正の設計）を推奨する。
