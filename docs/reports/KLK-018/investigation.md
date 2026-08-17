# KLK-018 調査報告（investigator・Mode A）

## 1. Findings
- `.claude/hooks/guard_bash_writes.py` に**ブレース展開・glob展開を認識する処理は一切存在しない**（`grep -n "brace"` 等でヒット無し）。`PATHISH_RE = r"[A-Za-z0-9_.\-/]+"` が `{` `}` `,` `*` `?` `[` `]` を含まないため、`guarded_paths`/`_is_guarded_path`（部分文字列判定）に候補が届く前に bash の展開文字がテキストを分断し、証拠が消える。
- 実機検証（本セッション・WSL2 bash）: `echo tickets/{acti,don}{ve,e}/APP-001.md` → `tickets/active/APP-001.md tickets/actie/APP-001.md tickets/donve/APP-001.md tickets/done/APP-001.md` の4語に展開。ネスト・直積形でも保護対象パスがargvに現れることを確認した（コマンド文字列上は非連続のため hook からは見えない）。
- パラメータ展開（`f=tickets/active/APP-001.md; rm $f`）は設計上・実装上ともに**構造的にPreToolUseでは閉じられない**ことを確認: `record_assignments`/`guarded_vars` は同一ステートメント内の代入を追跡し**リダイレクト先**にのみ適用する（`guarded_write_target`）。**引数側**の値は hook のプロセス内に一切現れず、これは「別コマンドでexportされた変数が見えない」という既知の限界と同じ原理的制約（モジュールdocstring「既知の限界」／設計書 INV-SH-11）。
- `tests/test_guard_bash_writes.py` の `INVENTORY_CASES` に INV-SH-07（ブレース展開）・INV-SH-09（分断glob）・INV-SH-11（パラメータ展開）が期待値 `allow` で既に登録済みで、実行すると現状 `ok`（=未対応のまま）。全226件（本ファイル単体）は現時点で green。
- チケット記載の「LEGACY_DENY_COMMANDS 126件」は実測すると現在**130件**（`INVENTORY_CASES`は90件）。KLK-015/024/029 の追加分の反映漏れと見られ、実装フェーズの回帰確認では実測値（130件）を基準にすべき。

## 2. Evidence
- codebase: `.claude/hooks/guard_bash_writes.py` — `PATHISH_RE`／`guarded_paths`／`_is_guarded_path`／`lex`／`normalize_line_continuations`（brace/glob無関係の確認）、モジュールdocstring「既知の限界」節（シェル展開の次元の未対応記述）
- codebase: `tests/test_guard_bash_writes.py` — `INVENTORY_CASES` の INV-SH-06〜12（シェル展開の次元一式）、`LEGACY_DENY_COMMANDS`（実測130件）
- local_docs: `docs/designs/KLK-010.md` §3-9-2（シェル展開の次元の棚卸し表）・§3-11（INV-SH-01〜22写像表）・§3-7（`PATHISH_RE`拡張の却下理由）・§6 R31・§10 申し送り9（いずれも「未対応・別チケット」として本チケットの根拠）
- empirical（本セッション・2026-08-17実施）: `python3 -m unittest tests.test_guard_bash_writes` → `Ran 226 tests ... OK`／`bash -c 'echo tickets/{acti,don}{ve,e}/APP-001.md'` 等の展開結果（上記Findings参照）

## 3. Dependency Graph
- `guard_bash_writes.py` は `_ticket_lib.emit_pretooluse_decision` にのみ依存する単発PreToolUseフック。ブレース展開・glob対応を追加する場合、`guarded_paths`/`is_guarded_token`/`mentions_guarded`（他13箇所超から呼ばれる共有シンボル。KLK-029のdocstringに明記）に手を入れると全呼び出し経路（言及ゲート・リダイレクト先・変数代入値・sed/awkプログラム本文）に波及するため、**専用の展開後判定関数を新設してOR追加する**（KLK-029のsed/awk専用ゲート緩和と同型パターン）方が安全側の設計になりうる。
- パラメータ展開の限界はKLK-016（`docs/SPEC.md`のドリフト検知バックストップ・事後検出）と対をなす。git status確認時点でKLK-016はマージコンフリクトによりblockedだが、KLK-018の調査スコープ（PreToolUse側のみ）には影響しない。
- 設計書`docs/designs/KLK-010.md`は同時に別チケットKLK-017（awk字句次元・`.wt/KLK-017`worktreeで進行中）からも編集対象になっており（git statusでmainワーキングツリーが `M docs/designs/KLK-010.md`）、architectはマージ順序・差分の競合に注意が必要。
- テスト側は`tests/_util.py`経由で`.claude/hooks`をsys.path解決。`INVENTORY_CASES`と`LEGACY_DENY_COMMANDS`は目的が異なり統合しない設計（P5系規律）。

## 4. Risk Areas
- ブレース展開を正しく閉じるには「入れ子・直積を含む展開の実装」が必要で、単純な文字クラス拡張では bash の意味論を再現できず**部分実装の穴**（一部の形だけ拾い他を見逃す）を生みやすい。
- **誤deny予算の根拠に疑義あり**: チケット・KLK-010が挙げる具体例 `_is_guarded_path("tickets/active/NR>1 {print}")` は、実際には**別の却下案（H2: cwdと全語のjoin）**の実測結果であり、`PATHISH_RE`拡張提案そのものの誤deny再現例ではない可能性がある（§3-7該当箇所を精読した限り、両者が同じ根拠として引用されているが機序は異なる）。architectは新設計着手前にV-14型の実機二方向検証で「単語単位でどのAWK/SEDプログラムが実際に新規誤denyになるか」を再確認すべき。
- 回帰基準はLEGACY_DENY_COMMANDS（実測130件。チケット記載126件は要更新）とINVENTORY_CASES（90件）＋既存226件（`test_guard_bash_writes.py`単体）を総なめすること。

## 5. Assumptions
- 調査はチケット指定どおりPreToolUse側（ブレース展開・分断glob）の実現可能性確認に限定し、パラメータ展開は「原理的に閉じられないこと」の技術確認に留めた。
- LEGACY_DENY_COMMANDS/INVENTORY_CASESの実測件数は現在のdevelopブランチのワーキングツリー内容に基づく（KLK-017マージ後に変動しうる）。
- `docs/designs/KLK-010.md`のmainワーキングツリー上の未コミット差分は、本調査で読んだ内容（KLK-017関連追記込み）がそのまま架構の前提であるとして扱った（`git diff`自体は未確認）。

## 6. Unknowns
- **[要architect確認・フラグ]** KLK-010が根拠として挙げる「`PATHISH_RE`単純拡張時の誤deny例」を本調査では単語単位で独立に再現できなかった（上記Risk Areas参照）。これは研究による確定不能というより**設計フェーズでのV-14/V-15型実機検証で埋めるべき項目**であり、architect主導での再検証を推奨する（human判断による差し戻しよりも、architectが設計時に検証する形での進行が妥当と考える）。

---
**引き継ぎ推奨**: 上記Unknownsは実装方針の検証項目であり、architectフェーズで解消可能と判断する。次のエージェントとして **architect** への委譲を推奨する（investigation自体はブロッカーなく完了）。

参照ファイル（絶対パス）:
- `/home/bzg55/workspace/breeze/kenesis-loop-kit/.claude/hooks/guard_bash_writes.py`
- `/home/bzg55/workspace/breeze/kenesis-loop-kit/tests/test_guard_bash_writes.py`
- `/home/bzg55/workspace/breeze/kenesis-loop-kit/docs/designs/KLK-010.md`
- `/home/bzg55/workspace/breeze/kenesis-loop-kit/tickets/active/KLK-018_シェル展開による保護対象パスの分断.md`
