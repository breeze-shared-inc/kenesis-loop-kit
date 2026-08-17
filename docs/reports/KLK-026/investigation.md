# KLK-026 調査詳細

生成: investigator（代筆: orchestrator） / 最終更新: 2026-08-17
対象: `docs/reports/{ID}/{phase}.md` 運用（KLK-004導入）の手順欠落
要点はチケット `KLK-026` の「調査メモ」を参照。本ファイルは全文。

## Findings

- **再現手順1（裏取り成立）**: `grep -rln "docs/reports"` は13ファイルにヒットするが、いずれも命名規則・phase定義・writer分担（自筆/代筆）・gitignore対象外の宣言のみで、「いつ・誰が・どこでコミットするか」を規定する記述は**ゼロ**（`docs/reports/README.md`・`.claude/agents/*.md`・`CLAUDE.md`・`docs/designs/KLK-004.md`を全文確認）。
- **再現手順2（裏取り成立）**: `orchestrator.md`「worktreeライフサイクル管理」節は `docs/designs/{ID}.md` のコミットのみ規定（下記Evidence引用）。同節・同ファイル中のdocs/reports言及3箇所（Responsibilities/Required Output Format/Ticket Integration）はすべて「代筆する」「ポインタを追記する」という**書く場所**の話で、**コミットする**という動詞は一切登場しない。
- **再現手順3（裏取り成立、一部ニュアンス追加）**: `docs/worktree-policy.md`「作業場所の境界」表は2行（メインツリー=orchestrator/investigator/architect、worktree=implementer/tester/reviewer）のみで `docs/reports/` の記載なし。ただしreviewerは表上「worktree」側に分類されており、KLK-004設計 §3方針5が定める「review.mdはメインworktreeで作成」という規定と**字面上の緊張関係**がある（下記「Risk Areas」参照）。
- **再現手順4（裏取り成立）**: `docs/reports/README.md` はコミットタイミング・ポインタ解決性への言及が皆無（命名規則・phase一覧・writer分担・上書き運用・gitignore対象外・frontmatterなし・機密情報規約のみを記載）。
- **再現手順5（部分的に規定あり、ただし弱い）**: implementer.md/tester.mdのGit Rulesには「自ら作成し」「コミットで反映してよい」（実装メモ）・「本ファイルも含めてよい」（test-report）の記述が既にあるが、いずれも**許可（〜してよい）であって義務（〜する）ではない**。次工程へ引き渡す前に必ずコミットする、という強制はテキスト上ない。

## Evidence

1. `.claude/agents/orchestrator.md`「worktreeライフサイクル管理」作成手順2（codebase, confidence high）:
   > `docs/designs/{ID}.md` が未コミットならdevelopへコミットする: `git add docs/designs/{ID}.md && git commit -m "[{ID}] 設計書追加"`

   docs/reports/{ID}/investigation.md・review.mdへの同種記述は同節に存在しない（grep確認）。

2. `docs/worktree-policy.md`「作業場所の境界」表（codebase, high）:
   > | メインツリー | orchestrator / investigator / architect | チケット・メトリクス・SPEC・設計書（docs/designs/） |
   > | チケット専用worktree | implementer / tester / reviewer | コード・テスト・コミット |

3. `docs/designs/KLK-004.md` §3方針3（local_docs, high）:
   > detail fileの置き場は `docs/reports/{ID}/{phase}.md`（ロール単位で1ファイル）とし、Gitで追跡する（.gitignore対象にしない）。

4. `docs/designs/KLK-004.md` §3方針5（local_docs, high）:
   > reviewerはWrite/Editツールを持たないため、orchestratorがメインworktree（既存の「チケット・メトリクスの書き込みはメインworktreeのみ」原則が適用される場）で`docs/reports/{ID}/review.md`を作成する。これによりreviewerの承認/差し戻しいずれの結果でもマージのタイミングに依存せず即座に参照可能になる。

5. `git show 979c062 --stat` / `git log --graph` / `git cat-file -p ffaf02b`（empirical、実測、2026-08-17実行、confidence high）:
   `979c062` はKLK-012のfixブランチ上の子コミット（親 `2c62624`）であり、developへは後続のマージコミット `ffaf02b`（親 `d21ffdf` と `979c062` の2つ）で取り込まれた。**review.mdはメインworktreeではなくチケットworktree側のブランチにコミットされた**ことを確認した。チケット本文「実運用での回避実績」の申告と一致する。

6. `docs/designs/KLK-004.md` §5「影響範囲」表（local_docs, high）:
   > `.gitignore.public` / `.gitignore.private` 行は「変更なし」・「`docs/reports/` はGit追跡対象とする（§3方針3）」と明記。KLK-004設計時点では「公開/非公開を問わず一律追跡」という前提だった。

7. `.gitignore.public` / `.gitignore.private`（codebase, high）: いずれのファイルにも `docs/reports` への言及なし。現状は両プリセットで `docs/reports/` を追跡対象としている（除外設定なし）。

8. `.claude/commands/setup.md` 手順2（codebase, high）: .gitignoreプリセット選択の案内文に `docs/reports/` への言及なし（実チケット `tickets/active|done/*.md` の扱いのみを案内）。

9. `tests/test_klk004_doc_wiring.py`（codebase, high）: `.claude/agents/*.md`・`CLAUDE.md`・`docs/reports/README.md` の**文言存在**のみを検証する回帰ガード。コミット手順やタイミングという**手続き的振る舞いは検証していない**（docstringに前例 `test_klk003_doc_wiring.py` への言及あり）。

10. implementer.md / tester.md Git Rules（codebase, high）: 実装メモ・test-reportについて「自ら作成してよい」「含めてよい」という許可表現のみで、コミットの強制（義務）を表す文言はなし。

## Dependency Graph

- `orchestrator.md`「worktreeライフサイクル管理」と`docs/worktree-policy.md`「ライフサイクル（作成・削除）」は**内容が重複・ミラーされている**（worktree-policy.md自身が「詳細手順は`.claude/agents/orchestrator.md`を正とする」と明記）。AC1でorchestrator.md側にdocs/reports commit手順を追加する場合、worktree-policy.md側のミラー記述（作成手順1「docs/designs/{ID}.mdをdevelopへコミットしてから派生する」の並び）も同時更新しないと**2ファイルが再び乖離する**。
- `docs/reports/README.md`の「gitignore対象外」記述は`.gitignore.public`/`.gitignore.private`の現状（両ファイルとも`docs/reports/`への言及なし＝現状は両プリセットで追跡対象）と**整合済み**。AC5で`.gitignore.public`へ`docs/reports/`を追加する場合、README.mdの当該記述の見直しが連鎖する。
- `tests/test_klk004_doc_wiring.py`は`.claude/agents/*.md`・`CLAUDE.md`・`docs/reports/README.md`の**文言存在**のみを検証する回帰ガードであり、コミット手順やタイミングという**手続き的振る舞いは検証していない**。AC1〜3で文言追加する場合、同種の`test_klk026_doc_wiring.py`（またはtest_klk004拡張）が同じ設計パターンで書ける。

## Risk Areas

- **設計と実運用の矛盾（要architect判断・融合せず報告）**: `docs/designs/KLK-004.md`§3方針5は「review.mdはメインworktreeで作成」と明記するが、実際のKLK-012運用（`979c062`）では**チケットworktree側のブランチにコミットしてマージで取り込む**方式が取られた。これはチケット本文「実運用での回避実績」の申告と一致する（事実確認済み）。どちらを正規手順とするかはAC1・AC6の設計判断であり、investigatorは判定しない。confidence: 矛盾の存在自体はhigh、どちらが「あるべき姿」かはlow（judgment事項）。
- `docs/worktree-policy.md`の境界表は現在**2行**のみで、reviewerが「worktree」側に分類されているため、AC3が提案する「メインツリー＝investigation/review、worktree＝implementation/test-report」という新しい行を素直に追加すると、**reviewerが両方の場所に現れる**（既存行=worktree、新規行=メインツリー）ことになり、表の一貫性をどう保つかは設計判断が必要。
- implementer/tester自筆分の既存記述（「〜してよい」）は許可であり義務でないため、AC2で「コミットのタイミングと場所」を明記する際、既存の任意表現との整合（強制へ引き上げるか、既存文言を活かすか）を明示しないと、規約の実効性は変わらない可能性がある。

## Assumptions

- AC5の判断材料（事実のみ、推奨なし）: 現状`.gitignore.public`/`.gitignore.private`のいずれも`docs/reports/`を除外していない（＝現状はどちらのプリセットでも追跡対象）。選択肢は(a) 現状維持（docs/designs/と同じ「常に追跡」precedentを保つ）、(b) `.gitignore.public`にのみ`docs/reports/`を追加（公開リポジトリでは内部意思決定記録を非公開にする）、(c) `setup.md`手順2で人間に選択を委ねる案内文を追加する、の3通りが考えられる。トレードオフの詳細判断は人間/architectに委ねる（investigatorは選択肢の提示に留める）。
- `docs/designs/KLK-004.md`§5「影響範囲」表の記述（KLK-004設計時点では「公開/非公開を問わず一律追跡」という前提）から、AC5でプリセットに差を設ける場合、この一文の訂正がAC6（設計書との整合）の対象になる可能性がある（推測。断定はしない）。

## Unknowns

- 明確な「調査で確定不能」な項目は無し（10項目すべてgrep/Read/git showで裏取り済み）。ただし上記「設計と実運用の矛盾」（review.mdの作成場所）は**architectの設計判断が必要な決定事項**であり、investigatorとしてどちらが正規手順かは判定しない（research-conventions §4 矛盾の処理に基づき融合せず両論併記のみ）。
- AC5は人間判断事項として明示的にflagする（チケット指示どおり）。

## 参照した実ファイル

- `.claude/agents/orchestrator.md`
- `.claude/agents/investigator.md`
- `.claude/agents/implementer.md`
- `.claude/agents/tester.md`
- `.claude/agents/reviewer.md`
- `docs/worktree-policy.md`
- `docs/reports/README.md`
- `docs/designs/KLK-004.md`
- `.gitignore.public`
- `.gitignore.private`
- `.claude/commands/setup.md`
- `tests/test_klk004_doc_wiring.py`
- `tickets/active/KLK-026_docs-reports運用の実効化.md`
- git commits: `979c062`, `ffaf02b`, `2c62624`（`git show`/`git log --graph`で実行確認済み）
