# KLK-025 調査詳細

生成: investigator（代筆: orchestrator） / 最終更新: 2026-08-17
対象: `docs/designs/KLK-014.md` への実装Phase表（`_TEMPLATE.md`§4準拠）追加
要点はチケット `KLK-025` の「調査メモ」を参照。本ファイルは全文。

## Findings

1. `_TEMPLATE.md`§4の「実装Phase」表フォーマットを確認。列見出しは「Phase／内容／完了条件／対応する受け入れ条件」の**4列**（`docs/designs/_TEMPLATE.md` 79-82行目）。
2. `docs/designs/KLK-014.md`には該当表が実在しない。§4は4-1〜4-6の6サブセクション（126-344行目）のみで構成され、grepで「実装Phase」の文字列ヒットは0件。欠落を確認。
3. `docs/designs/KLK-010.md`§4-8（2929-2973行目）が参考実例。ただし列構成は「Phase／状態／内容／完了条件／対応する受け入れ条件」の**5列**（`_TEMPLATE.md`の4列に「状態」列を独自追加したもの）。
4. コミット`0c66699`（`.claude/hooks/guard_bash_writes.py`＋`.claude/hooks/README.md`変更、テスト変更なし）と`fe47ff0`（`tests/test_guard_bash_writes.py`へ12関数・105行追加のみ）を実測。チケット本文「実装メモ(implementer)」記載のPhase1/Phase2の切り分けと完全一致、齟齬なし（AC2充足）。
5. 本タスクは「新たな設計判断は行わない」転記作業であり、Phase構成・AC対応関係はチケット本文「設計メモ(architect)」に既に文章で確定済み。architectが行うのは表形式への機械的整形が中心で、実質的な新規設計判断は発生しない可能性が高い（下記Risk Areas 1参照 — 列数の統一判断のみは残る）。

## Evidence

1. `docs/designs/_TEMPLATE.md` 71-82行目（codebase, confidence high）— 「実装Phase」節・4列表フォーマットの定義本体。全文は下記「A」参照。
2. `docs/designs/KLK-010.md` 2929-2973行目（codebase, high）— §4-8実装Phase表の実例（5列パターン・Phase数自己点検／全ACカバレッジ自己点検の補足段落あり）。全文は下記「B」参照。
3. `docs/designs/KLK-014.md` 全410行（codebase, high）— §4は4-1〜4-6のみ、「実装Phase」表なし（grep確認）。章立て全体は下記「C」参照。
4. `tickets/done/KLK-014_degradedモードがコマンド置換を評価しない.md` 69-77行目（設計メモ）・49-55行目（実装メモ）（local_docs, high）— Phase1/Phase2の内容・AC対応の記述元。全文は下記「D」「E」参照。
5. `git show --stat 0c66699` / `fe47ff0` 実行結果（empirical, 2026-08-17実行, high）— 実装内容とチケット記述の突合。全文は下記「F」参照。

## Dependency Graph

- `docs/designs/_TEMPLATE.md`§4（フォーマット定義）→ `docs/designs/KLK-014.md`§4（追加対象）。
- `tickets/done/KLK-014...md`「設計メモ(architect)」（転記元テキスト）→ 新設Phase表の内容。
- コミット`0c66699`・`fe47ff0`（実装の実体）→ Phase表「完了条件」列の裏付け根拠。
- `docs/designs/KLK-010.md`§4-8（参考実装パターン）→ 新設表の書式・粒度の手本（ただし列数に相違あり、Risk Areas参照）。
- KLK-025は文書のみの変更であり、他の並行チケット（KLK-016/018等）のコード変更とは無関係（依存なし）。

## Risk Areas

1. `docs/designs/KLK-010.md`§4-8は「状態」列を含む**5列**だが、`_TEMPLATE.md`§4は**4列**のみを規定。KLK-025のAC3は「`_TEMPLATE.md`§4準拠の4列」を明記しているため、KLK-010の5列パターンをそのまま模倣すると列数不一致（テンプレート逸脱の再発）になりうる。列数はarchitectが4列厳守／5列踏襲のいずれかを判断し明記する必要がある。
2. Phase1（`0c66699`）単独実行時点でのテストスイート結果（既存437件pass）が実装メモ・コミットメッセージのいずれにも明記されていない（437+12=449は両Phase後の記述）。「完了条件」欄を厳密に書く場合、Phase1単独の完了条件の記述粒度をどうするか判断が要る。
3. 転記の際にAC1〜5の対応関係（特にAC4=`LEGACY_DENY_COMMANDS`回帰・AC5=テスト件数）を要約しすぎると、チケット本文の原文とのニュアンス相違が生じうる。
4. コード変更を伴わないため実装リスクはゼロ。文書整合性（テンプレート準拠）のみがスコープ。

## Assumptions

- 表の挿入位置は§4末尾（4-6の後、`## 5. 影響範囲`の前）に新規サブセクション（例: `### 4-7. 実装Phase`）として追加するのが自然（KLK-010の配置パターンに倣った推測。architectが正式決定する事項）。
- チケット本文「設計メモ(architect)」の1行要約（Phase1/Phase2の区切り）が、当時のarchitectが実際に意図したPhase境界を正確に表しているとの前提（検証手段はコミット単位の差分突合のみ）。

## Unknowns

- Phase1単独時点でのテストスイート全件pass確認の有無・件数は、実装メモ・コミットログいずれにも記載がなく確定不能（surrendered。verification_hint: 当時のworktreeログやCI記録が別途残っていれば確認可能だが、本調査範囲内のソースには存在しない）。
- 「本タスクに実質的な設計判断が発生するか」は、architectが実際にPhase表を起草してみないと最終確定できない（列数統一など軽微な判断は入り得る）。investigatorとしては「転記中心で新規の設計判断は不要と見込まれる」との評価に留める。

## 詳細情報（引用全文）

### A. `_TEMPLATE.md`§4「実装Phase」節（該当箇所全文）

`docs/designs/_TEMPLATE.md` 71-82行目:

```
**実装Phase:**

<!-- 実装の段階と順序を定義する。implementerはこの順に実装する -->
<!-- Phaseの完了条件は作業チェックポイントであり、チケットの受け入れ条件を再定義・緩和しない。全受け入れ条件が少なくとも1つのPhaseでカバーされていること（architectがセルフチェックし、reviewerが検証する） -->
<!-- 例外: 完了条件がreviewer自身の確認行為そのものであり、新たな実装作業を伴わないAC（例:「reviewerがSPEC §xとの整合を確認する」）は、Phase表の対象外としてよい。ただし§9の受け入れ条件リストからは削除しない。実装作業を要するACをこの例外を理由に除外することは禁止する -->
<!-- Phaseが4つ以上になる、または各Phaseが独立してレビュー・リリース可能な粒度になる場合は、チケット分割の見直しが必要なサイン。設計を確定せずorchestratorへ報告し、人間による /plan-tickets の差分起票を仰ぐ -->
<!-- Phaseの進行はチケットstatusに反映しない（statusは implementation_done の粒度のまま）。進行はimplementerのコミットとレポートで追う -->

| Phase | 内容 | 完了条件 | 対応する受け入れ条件 |
|---|---|---|---|
| 1 |  |  |  |
| 2 |  |  |  |
```

→ 4列（Phase／内容／完了条件／対応する受け入れ条件）が正。「状態」列は規定されていない。

### B. `KLK-010.md`§4-8の実例（列構成の相違点）

`docs/designs/KLK-010.md` 2935-2936行目のヘッダ:

```
| Phase | 状態 | 内容 | 完了条件 | 対応する受け入れ条件 |
|---|---|---|---|---|
```

5列（`_TEMPLATE.md`にない「状態」列を追加）。「完了」「未実施」等のPhase進捗をここで管理している。同ファイル末尾（2959行目）に「Phase数の自己点検」、2961-2973行目に「全受け入れ条件のカバレッジ自己点検」という補足表が付随している（`_TEMPLATE.md`には規定されていない拡張パターン。KLK-010固有の運用、必須ではない）。

### C. `KLK-014.md`の現状（章立て全体）

```
26: ## 1. 目的
34: ## 2. 現状
103: ## 3. 設計方針
126: ## 4. 実装詳細
141:   ### 4-1. `_extract_degraded_substs` の実装
224:   ### 4-2. `degraded_violation` の改修
292:   ### 4-3. `find_violation` の呼び出し側
302:   ### 4-4. docstring・README の更新
328:   ### 4-5. `docs/designs/KLK-010.md` について（本チケットでは編集しない）
332:   ### 4-6. 既存テストへの影響トレース（実装前の机上検証）
345: ## 5. 影響範囲
358: ## 6. リスク
367: ## 7. マイグレーション戦略
371: ## 8. ロールバック戦略
379: ## 9. 受け入れ条件
406: ## 10. Open Questions
```

「実装Phase」の見出し・表は存在しない（grep該当ゼロ）。挿入候補は4-6の直後・`## 5. 影響範囲`（345行目）の直前（`### 4-7. 実装Phase`）。

### D. チケット本文「設計メモ(architect)」原文（転記元）

`tickets/done/KLK-014_degradedモードがコマンド置換を評価しない.md` 69-77行目:

```
### 設計メモ (architect)
- 設計書: `docs/designs/KLK-014.md`（新規作成、コミット`e972ee4`）。Open Questionsなし。
- investigatorの案A/B/Cから案C（置換境界の再帰評価）を採用。
- `degraded_violation`に`depth`パラメータを追加（デフォルト値付き、既存テストは無影響）、`find_violation`の呼び出し1行を更新して`MAX_SUBST_DEPTH`を正しく継承。
- Phase構成: Phase1(`_extract_degraded_substs`新設・`degraded_violation`改修・docstring/README更新)・Phase2(回帰テスト追加・誤deny予算の実機確認)。AC1〜5は全てPhase1/2でカバー済み、4Phase以上にはならないためチケット粒度見直し不要。
- 誤deny予算: 新規denyを3カテゴリ（意図した修正本体／プロセス置換リダイレクト先の副次closure／コメント内置換のCategory 3）に限定列挙。日常読み取り70件には該当形が無いことをinvestigatorが確認済み。
- KLK-017（KLK-010設計書の記述訂正・SV-23）との順序: KLK-017はKLK-014完了後に着手すべき
- 同時期チケット（KLK-013・KLK-015・KLK-018・KLK-019）との対象関数の直接競合は無し。developへの直列マージ＋都度全テスト実行を推奨。
```

### E. 「実装メモ(implementer)」原文（Phase内容の裏付け）

同ファイル 49-55行目:

```
- worktree `../kenesis-loop-kit.wt/KLK-014`（ブランチ `fix/KLK-014-degraded-substitution-blindspot`）で実装。
- Phase1（コミット`0c66699`）: `.claude/hooks/guard_bash_writes.py`に新規関数`_extract_degraded_substs`を追加、`degraded_violation(command, cwd="", depth=0)`へ改修（既存の`_skip_balanced`/`_skip_backtick`/`_take_subst`/`_take_backtick`を再利用し閉じている置換境界のみ抽出、`subst_violation`/`find_violation`へ回す）。`find_violation`の呼び出し1行を更新し`MAX_SUBST_DEPTH`を継承。`.claude/hooks/README.md`のD-5セルへH6修正の要約を追記。設計書からの逸脱なし。
- Phase2（コミット`fe47ff0`）: `tests/test_guard_bash_writes.py`へ「KLK-014（H6）」見出しで新規テスト12件追加（AC1: 置換3型×書き込みベクタ8種・ネスト・誘発形2種・cwd相対パス伝播／AC2: 正常経路無変更・読み取り専用置換のallow維持／AC3: Category2・Category3の代表形とその対照allow／MAX_SUBST_DEPTH境界）。
- テスト結果: `python3 -m unittest discover -s tests` で437件（既存）+12件（新規）=449件、全件pass。
- 実機二方向検証: 着手前コミット(`e972ee4`)版と新実装を突き合わせ、日常読み取り70件相当（自前再構築）は新旧ともdeny 1/70で変化なし、AC3のCategory3代表形2件は旧=allow・新=denyであることを確認（正当な新規denyと実証）。ただし日常読み取り70件はimplementerが独自に再構築したものであり、investigator使用の原本（`rv3.py`相当）との完全一致は未確認 — tester側での再検証を推奨。
```

※「テスト結果」「実機二方向検証」の記述は両Phase完了後にまとめて書かれており、Phase1単独時点でのテスト実行結果（例: 既存437件のみでpass）は明記されていない（Unknown参照）。

### F. コミット実測結果（`git show --stat`）

```
$ git log --oneline -1 0c66699
0c66699 [KLK-014] Phase 1: degradedモードにコマンド置換の再帰評価を追加(_extract_degraded_substs)
 .claude/hooks/README.md            |   2 +-
 .claude/hooks/guard_bash_writes.py | 140 ++++++++++++++++++++++++++++++++++---
 2 files changed, 130 insertions(+), 12 deletions(-)

$ git log --oneline -1 fe47ff0
fe47ff0 [KLK-014] Phase 2: H6回帰テスト追加・誤deny予算の実機二方向検証
 tests/test_guard_bash_writes.py | 105 ++++++++++++++++++++++++++++++++++++++++
 1 file changed, 105 insertions(+)
```

関数レベル確認:

```
$ git show 0c66699 -- .claude/hooks/guard_bash_writes.py | grep -E "^\+def "
+def _extract_degraded_substs(command):
+def degraded_violation(command, cwd="", depth=0):

$ git show 0c66699 -- .claude/hooks/guard_bash_writes.py | grep -E "^[+-].*degraded_violation\(command"
-def degraded_violation(command, cwd=""):
+def degraded_violation(command, cwd="", depth=0):
-        return degraded_violation(command, cwd)
+        return degraded_violation(command, cwd, depth)

$ git show fe47ff0 -- tests/test_guard_bash_writes.py | grep -E "^\+ *def test_" | wc -l
12

$ git show 0c66699 -- .claude/hooks/README.md | grep -E "^\+" | grep -o "H6.\{0,60\}"
H6修正（KLK-014）**: 閉じているコマンド置換（`$(...)`）／バッククォート／プロセス置換の境界は `_extract_degraded_substs` が機械的に抽出し、
```

→ Phase1=コード実装＋README更新（テスト無し）／Phase2=テスト12件のみ、という実装メモの記述と1対1で一致。齟齬は検出されなかった（AC2充足）。

### G. Phase表の転記案（参考下書き。architectが正式に確定すべき事項）

以下は情報整理のための下書きであり、architectの正式決定を代替するものではない（列数「状態」の要否等、上記Risk Areas 1参照）:

| Phase | 内容 | 完了条件 | 対応する受け入れ条件 |
|---|---|---|---|
| 1 | `_extract_degraded_substs`新設・`degraded_violation`改修（`depth`引数追加）・`find_violation`呼び出し側1行更新・モジュールdocstring及び`.claude/hooks/README.md`該当セル更新（コミット`0c66699`） | §4-1〜4-4の実装がなされ、置換が無い入力ではスケルトンが元コマンドとバイト単位で同一という不変条件が成立する | AC2（構造的不変条件による担保）・AC4（既存deny対象への非干渉の前提） |
| 2 | AC1〜AC3の回帰テストを`tests/test_guard_bash_writes.py`へ12件追加。日常読み取り70件相当・新旧二方向比較による誤deny予算の実機検証（コミット`fe47ff0`） | 既存437件＋新規12件=449件が全件pass（failures 0・errors 0）。AC3の新規denyが列挙3カテゴリの範囲内であることを実機確認 | AC1・AC2・AC3・AC4（`LEGACY_DENY_COMMANDS`126件無改修pass含む）・AC5 |

## 参照した実ファイル

- `docs/designs/_TEMPLATE.md`
- `docs/designs/KLK-010.md`
- `docs/designs/KLK-014.md`
- `tickets/done/KLK-014_degradedモードがコマンド置換を評価しない.md`
- `tickets/active/KLK-025_KLK-014設計書への実装Phase表の追加.md`
- git commits: `0c66699`, `fe47ff0`（`git show --stat`/`git log --oneline`で実行確認済み）
