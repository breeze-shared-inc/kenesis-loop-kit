# KLK-005 調査詳細

生成: investigator（代筆: orchestrator） / 最終更新: 2026-08-17
対象: CLAUDE.mdポリシー管理表の docs/policy-registry.md への分離
要点はチケット `KLK-005` の「調査メモ」を参照。本ファイルは全文。

## Findings

- CLAUDE.md は実測 21,252 バイト・191行（末尾改行込み、可視行190）。ticket記載の基準値と一致（`wc -c`実測）。
- 「## ポリシー管理の原則」セクションは150〜191行目、7,902バイト（全体の37.18%）。ticketの「7,901バイト」とほぼ一致（誤差1バイトは末尾改行の数え方の違い）。
- そのうち純粋な表本体（159〜188行目、ヘッダ+区切り+28データ行）は6,636バイト（全体の31.23%）。表を取り巻く前文＋「再肥大化の防止」原則＋締め文（150-158, 189-191行目）は1,266バイトで、AC1が「残すべき」と指定する部分と重なる。
- **AC1とAC3の間に算術的緊張がある**: AC1どおり原則文（745バイト）とポインタを残し表本体だけを外部化すると、削減量は概ね31〜32%にとどまり、AC3の35%目標に届かない可能性が高い（詳細は Risk Areas #1）。
- docs/policy-registry.md は未作成（`ls`で確認、`No such file or directory`）。新設が必要。

## Evidence

1. `CLAUDE.md`（150-191行目セクション、`wc -c`・行別バイト集計で実測、codebase, confidence high）。詳細な内訳は本ファイル末尾「セクション別バイトサイズ」参照。
2. `tests/test_klk003_doc_wiring.py::TestClaudeMdPolicyTable`（126-147行目、codebase, high）: `extract_section(CLAUDE_MD, "ポリシー管理の原則")` に依存する4アサーション。全文は本ファイル末尾参照。
3. `tests/test_klk004_doc_wiring.py::TestClaudeMdPolicyRow`（121-142行目、codebase, high）: **ticketの申し送りが言及していなかった、同一セクションに依存する追加の回帰ガード**。3アサーション。全文は本ファイル末尾参照。
4. README.md 211行目以降に、CLAUDE.mdの「スラッシュコマンド一覧」とほぼ並行する人間向け表が既に存在（重複）。
5. grep結果全量（「ポリシー管理の原則」／「CLAUDE\.md」／「スラッシュコマンド一覧」の参照ファイル一覧）は本ファイル末尾参照。

## Dependency Graph

- CLAUDE.md 6行目（冒頭説明）→「ポリシー管理の原則」の表という文言で自己参照。表を移設すると要書き換え（ticket未言及の新規発見）。
- CLAUDE.md 150-191行 →（`extract_section`経由）→ `tests/test_klk003_doc_wiring.py::TestClaudeMdPolicyTable`（4テスト）+ `tests/test_klk004_doc_wiring.py::TestClaudeMdPolicyRow`（3テスト）= 計2ファイル7アサーションが直接結合。
- 表内9行（164,167,168,171,172,173,175,180,187行目）が「本ファイル」という自己参照語を持つ→ 表を別ファイルへ移すと文脈上「CLAUDE.md」への書き換えが必須（AC4の「参照先洗い出し」に該当する内部依存）。
- docs/designs/{KLK-001,002,003,009,011}.md が表の行・締め文を歴史的記録として文字列引用（Editアンカー等）。ライブ結合ではないが将来の可読性リスク。
- スラッシュコマンド一覧セクション（10-33行目）は他ファイルからの機械的結合（テスト等）は確認されず、README.mdに重複表があるため分離時の影響は限定的。

## Risk Areas

- **[高] AC1×AC3の未達リスク**: 表本体のみの分離では約31-32%減（6,636〜6,740/21,252）で35%に届かない可能性が高い。AC2（スラッシュコマンド表、2,376バイト=11.2%）の一部分離、または他セクション（例:「開発ループフロー」ASCII図1,838バイト）の圧縮も併用しないと目標未達の恐れ。数値は文面ドラフト前の推定であり、architectが実際の置換文を書いた上で`wc -c`再実測が必要。
- **[高] ticket未言及の回帰ガード**: `tests/test_klk004_doc_wiring.py::TestClaudeMdPolicyRow`（3テスト）も`extract_section(CLAUDE_MD, "ポリシー管理の原則")`に依存し、`docs/reports/{ID}/{phase}.md`行と締め文「新しいポリシーを追加する際は」の位置を検証している。ticketの申し送りは`test_klk003_doc_wiring.py`のみ言及していたが、実際は**2ファイル・計7アサーション**が影響を受ける。
- **[中] 見出し依存の失敗モード**: 両テストの`extract_section`は`"## {heading}"`の完全一致でセクションを探すため、見出し名「ポリシー管理の原則」自体を変更/削除すると通常のassertion失敗ではなく`AssertionError("見出し '## ...' が見つかりません")`という別モードで壊れる。見出し名はCLAUDE.md側に残す設計が無難。
- **[中] 自己参照9箇所の書き換え漏れ**: 「本ファイル」→「CLAUDE.md」への機械的置換が必要な箇所が表内に9箇所（CLAUDE.md自身の6・154行含めると11箇所相当）。見落とすと移設後の表が「本ファイル＝docs/policy-registry.md」と誤読される。
- **[低] 歴史設計書の陳腐化**: docs/designs/{KLK-001,002,003,009,011}.mdの引用は「過去の設計はGitヒストリで追う」という既存運用ルール上、更新不要と解釈できるが、明文の免除規定はCLAUDE.mdのドキュメント管理表に無い（Unknowns参照）。

## Assumptions

- ticketの「ポリシー管理表」= 表本体（データ行）を指し、AC1が「残す」とする「再肥大化の防止」原則文（154-158行目）は表に含まれない、という読み方を採用（ticket本文に明示のバイト内訳はないため、architectの解釈確認を推奨）。
- docs/policy-registry.mdは既存テンプレート（docs/designs/_TEMPLATE.md相当）を持たない新設ファイルと仮定（該当テンプレートの存在をgrep・ls双方で確認できず）。
- CHANGELOG.mdの過去エントリ（「ポリシー管理の原則」「スラッシュコマンド一覧」を言及する記述）は追記専用の履歴であり本チケットでの更新対象外、と仮定（ただしCLAUDE.mdのドキュメント管理ルール表にCHANGELOG.md自体の記載がなく、確証はない。Unknowns参照）。

## Unknowns

- CLAUDE.mdのバイト削減35%達成が「AC1の表のみ分離」で足りるか「AC2のスラッシュコマンド表も一部併用」が必要かは、実際の置換文言をarchitectが確定して`wc -c`実測するまで確定不能（surrendered。verification_hint: 置換後CLAUDE.mdに対し`wc -c`を再実行し21,252×0.65=13,814バイト以下になるか確認）。
- CHANGELOG.mdの歴史的記述（「ポリシー管理の原則」表を言及する4箇所）を更新対象に含めるべきかは、CLAUDE.mdのドキュメント管理ルール表にCHANGELOG.md運用ルールの明記がなく確定不能（surrendered。verification_hint: 人間またはarchitectにCHANGELOG.mdの改訂方針＝追記専用/凍結かを確認）。
- docs/designs/{KLK-001,002,003,009,011}.mdの過去の文字列引用（表の最終行等をEditアンカーとして使う設計指示）を、本チケット後に更新すべきか「Gitヒストリで追う」対象として放置すべきかは明文ルールがなく確定不能（surrendered。verification_hint: architectに「過去設計書の引用は不変条件か」を確認）。

## 詳細データ

### 1. CLAUDE.md セクション別バイトサイズ（`## `見出し単位、実測）

```
('## スラッシュコマンド一覧', 10, 33, 2376)
('## エージェント構成', 34, 48, 1010)
('## 開発ループフロー', 49, 72, 1838)
('## ドキュメント管理ルール', 73, 91, 1833)
('## Git運用規約', 92, 97, 852)
('## チケット管理ルール', 98, 128, 3397)
('## リポジトリ可視性による.gitignore運用', 129, 134, 392)
('## 状態検証hook・メトリクス（自動強制・観測性）', 135, 143, 808)
('## セキュリティ・機密情報の取り扱い', 144, 149, 364)
('## ポリシー管理の原則', 150, 191, 7902)
合計: 21252バイト / 191行（冒頭0-9行目=タイトル・説明文・区切り線を含む）
```

### 2. 「ポリシー管理の原則」セクション内の詳細内訳（実測）

```
150行目 見出し: 32バイト
152行目（+153空行） 冒頭説明文（「下表」参照あり）: 308バイト
154-158行目 「再肥大化の防止」原則文＋手順1・2（「下表」参照あり）: 745バイト
159-160行目 表ヘッダ＋区切り行: 92バイト
161-188行目 データ行28行: 6544バイト
189-191行目（空行＋締め文「新しいポリシーを追加する際は…」＋末尾改行）: 181バイト
合計: 7902バイト
```

AC3必要削減量 = 21252 × 0.35 = 7438.2バイト。表本体のみ（159-188行目, 6636バイト）を移設し、他は現状維持＋ポインタ追記の場合、正味削減は概ね6636引くポインタ追記分（数十〜百数十バイト）で、6500〜6700バイト程度＝30.6〜31.5%相当にとどまる可能性が高い。原則文（154-158, 745バイト）を維持する前提だと、単純計算では目標未達となる余地が大きい。

### 3. `tests/test_klk003_doc_wiring.py::TestClaudeMdPolicyTable`（122-148行目）

```python
class TestClaudeMdPolicyTable(unittest.TestCase):
    """AC5: CLAUDE.md ポリシー管理表への1行追加。"""

    def setUp(self):
        self.section = extract_section(read(CLAUDE_MD), "ポリシー管理の原則")

    def test_policy_row_references_list_tickets_script(self):
        self.assertIn("scripts/list_tickets.py", self.section)

    def test_policy_row_points_to_design_doc(self):
        rows = [ln for ln in self.section.splitlines()
                if "scripts/list_tickets.py" in ln]
        self.assertEqual(len(rows), 1, "該当行が一意でない: %r" % rows)
        self.assertIn("docs/designs/KLK-003.md", rows[0])

    def test_policy_row_is_a_table_row(self):
        rows = [ln for ln in self.section.splitlines()
                if "scripts/list_tickets.py" in ln]
        self.assertTrue(rows[0].strip().startswith("|"), ...)

    def test_closing_sentence_still_after_table(self):
        idx_row = self.section.index("scripts/list_tickets.py")
        idx_closing = self.section.index("新しいポリシーを追加する際は")
        self.assertLess(idx_row, idx_closing)
```

`extract_section()`は`"## {heading}"`と完全一致する行を起点に、次の`"## "`見出し（または末尾）までを切り出すヘルパー（36-51行目、`test_klk004_doc_wiring.py`にも同名同実装が重複定義されている）。表本体・締め文が「ポリシー管理の原則」セクションから消えると、上記4テストは全て失敗する（`scripts/list_tickets.py`という文字列も、`新しいポリシーを追加する際は`という締め文も、セクション内から見つからなくなるため）。

### 4. `tests/test_klk004_doc_wiring.py::TestClaudeMdPolicyRow`（121-142行目、ticket申し送り未記載）

```python
class TestClaudeMdPolicyRow(unittest.TestCase):
    """AC5: CLAUDE.md ポリシー管理表への1行追加（本文セクション新設なし）。"""

    def setUp(self):
        self.section = extract_section(read(CLAUDE_MD), "ポリシー管理の原則")

    def test_policy_row_references_reports_path(self):
        self.assertIn("docs/reports/{ID}/{phase}.md", self.section)

    def test_policy_row_is_unique_table_row_pointing_to_design_doc(self):
        rows = [ln for ln in self.section.splitlines()
                if "docs/reports/{ID}/{phase}.md" in ln]
        table_rows = [r for r in rows if r.strip().startswith("|")]
        self.assertEqual(len(table_rows), 1, ...)
        self.assertIn("docs/designs/KLK-004.md", table_rows[0])

    def test_closing_sentence_still_after_table(self):
        idx_row = self.section.index("docs/reports/{ID}/{phase}.md")
        idx_closing = self.section.index("新しいポリシーを追加する際は")
        self.assertLess(idx_row, idx_closing)
```

これも同じ`extract_section(CLAUDE_MD, "ポリシー管理の原則")`パターンで、`docs/reports/{ID}/{phase}.md`という別の行の存在と締め文の順序を検証している。**KLK-005ticket本文はKLK-003側のテストのみ言及しているが、KLK-004側のこの3アサーションも同一の理由（表と締め文がセクションから消える）で確実に失敗する。**

### 5. grep結果全量（「ポリシー管理の原則」参照ファイル）

```
CLAUDE.md:6, CLAUDE.md:150, CLAUDE.md:187（自己参照）
docs/designs/KLK-002.md:51,78,114,190,213,229（履歴・引用）
docs/designs/KLK-003.md:185,187（履歴・Editアンカー引用）
docs/designs/KLK-011.md:54,81,209,220,342（履歴・Editアンカー引用）
docs/designs/KLK-009.md:97（整合性の説明として引用）
CHANGELOG.md:110,128,167（履歴ログ）
tests/test_klk004_doc_wiring.py:125（extract_section呼び出し）
tests/test_klk003_doc_wiring.py:126（extract_section呼び出し）
```

`grep -rln "policy-registry"` は0件（新設前のため該当なし、想定通り）。

`grep -rln "CLAUDE\.md"`（全体参照ファイル一覧、23ファイル）: CLAUDE.md, README.md, docs/security-policy.md, CHANGELOG.md, docs/designs/KLK-004.md, docs/worktree-policy.md, docs/designs/KLK-007.md, docs/designs/KLK-003.md, docs/designs/KLK-009.md, docs/designs/KLK-001.md, docs/batch-loop-inline.md, docs/designs/KLK-002.md, .claude/commands/setup.md, docs/designs/KLK-010.md, docs/designs/KLK-012.md, .claude/hooks/README.md, .claude/hooks/_ticket_lib.py, docs/designs/KLK-011.md, .claude/agents/implementer.md, .claude/hooks/guard_bash_writes.py, .claude/commands/new-ticket.md, .claude/skills/interrogate-spec/SKILL.md, tests/test_klk004_doc_wiring.py, tests/README.md, tests/test_klk003_doc_wiring.py, tests/test_validator.py, .claude/agents/orchestrator.md — このうち「ポリシー管理の原則」の表・個別行を直接転記/機械参照しているのは上記のtests 2件とdocs/designs履歴のみ。他は「CLAUDE.md」という一般名詞的言及（節名参照等）で、表の移設による直接的な破損はない。

### 6. スラッシュコマンド一覧の分離可否判断材料

- `grep -rn "スラッシュコマンド一覧"` の一致は CLAUDE.md:10（自己）とCHANGELOG.md（履歴4箇所）とdocs/designs/{KLK-001,007}.md（履歴）のみ。**現行テスト・hook・スクリプトのいずれからも機械的に参照されていない**（=分離してもテスト破損リスクはゼロ）。
- README.md 211-230行目付近に、ほぼ並行する人間向け「## スラッシュコマンド」表（使用例列付き）が既に存在。CLAUDE.mdの表を分離しても、人間向けの一覧はREADME.mdに残る。
- ただしCLAUDE.mdの表はLLM（orchestrator含む全サブエージェント）が起動時に自動注入されるコンテキストの一部であり、README.mdはそうではない。分離した場合、エージェントが「どのスラッシュコマンドが存在するか」を自動コンテキストから失う点は、AC2の「結論と根拠」に含めるべきトレードオフ。
- KLK-001/KLK-007の履歴を見る限り、新コマンド追加のたびにCLAUDE.mdのスラッシュコマンド一覧とポリシー表の両方に1行ずつ追記する運用が定着している（変更頻度が中程度にある可変ブロック）。

## 次のステップへの推奨（investigator所見）

Unknowns（3件）はいずれも「人間/architectの判断待ち」の性質であり、致命的なブロッカーではないため、architectへの引き継ぎを推奨する。architectには特に次を申し送ること。

1. AC1（原則文+ポインタのみ残す）とAC3（35%以上削減）の両立が表単独の分離では数値上厳しいこと（本ファイル「詳細データ2」参照）を前提に、(a) AC2のスラッシュコマンド表も一部/全部分離する、(b)「再肥大化の防止」原則文自体を簡潔化する、のいずれか（または両方）の方針を設計段階で決め、実際の置換文言を書いた上で`wc -c`により実測すること。
2. `tests/test_klk003_doc_wiring.py::TestClaudeMdPolicyTable`（4テスト）と`tests/test_klk004_doc_wiring.py::TestClaudeMdPolicyRow`（3テスト）の**両方**を、docs/policy-registry.mdを検査対象に含めるよう改訂する必要があること（ticket本文はKLK-003側のみ言及しているため、この見落としを埋める）。
3. 表内の「本ファイル」という自己参照（9箇所）を「CLAUDE.md」への明示表現に置換すること。
4. AC5（「CLAUDE.md＝インデックス＋共通定義の維持」の正の所在）は、表移設後もCLAUDE.md 154-158行目の「再肥大化の防止」原則文が正であり続ける、という設計結論を表187行目の「定義（正）」列に反映すること（docs/policy-registry.mdへは移らない）。

## 参照した実ファイル

- `CLAUDE.md`
- `tests/test_klk003_doc_wiring.py`
- `tests/test_klk004_doc_wiring.py`
- `README.md`
- `docs/designs/KLK-001.md` / `KLK-002.md` / `KLK-003.md` / `KLK-009.md` / `KLK-011.md`
- `CHANGELOG.md`
- `tickets/active/KLK-005_CLAUDEmdポリシー管理表の分離によるスリム化.md`
