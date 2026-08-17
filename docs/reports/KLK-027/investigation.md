# KLK-027 investigation

生成: investigator（orchestrator代筆） / 最終更新: 2026-08-17

## AC1: 書き手分担3重記述

3箇所（各agent .mdのRequired Output Format直下括弧・同Ticket Integration/Git Rules・
docs/reports/README.mdのwriter表）は目視比較の結果、内容としては一致している
（investigator/reviewer = orchestrator代筆、implementer/tester = 自筆）。

`tests/test_klk004_doc_wiring.py` の `TestReportsReadmeConsistencyWithAgentFiles` クラスは
`test_self_write_roles_present_in_own_agent_files` と
`test_ghost_write_roles_present_in_own_agent_files` の2テストで構成される。いずれも各
エージェントファイル全文に対して `assertIn("自ら", text)` / `assertIn("代筆", text)` という
部分文字列の存在確認のみを行っており、3箇所間の対応関係（どの記述とどの記述が同じことを
指しているか）や、いずれか1箇所だけが将来改訂された場合の矛盾検出は行っていない。

**ギャップ**: 3箇所間の相互整合を機械的に固定するテストが存在しない。

## AC2: 現行API瑕疵テストの扱い

`mentions_guarded(values)` の実装（`.claude/hooks/guard_bash_writes.py:752-754`）:

```python
def mentions_guarded(values):
    return any(is_guarded_token(v) for v in values)
```

`values` に生文字列を渡すと文字単位でイテレートされるため、`is_guarded_token` は各1文字を
判定することになり実質的に常に `False` を返す。KLK-010 Phase1（commit `4ae9f61`）で
「生文字列」から「事前分割済みトークン列」へ契約が変更されたことに由来する。

`tests/test_guard_bash_writes.py:690-716` に2テストが存在する:
- `test_docs_reports_path_not_mentioned_as_guarded` — 正常系の契約どおりの呼び出し
- `test_mentions_guarded_raw_string_call_is_a_false_negative_trap` — 契約違反（生文字列）の
  呼び出しが常に `False` になる**現行実装の瑕疵**をそのまま仕様として固定している

仮に `isinstance(values, str)` による防御的強化（自動split等）を加えた場合、後者のテストの
`assertFalse(...)` が成立しなくなり fail する。fail方向は「deny側＝より保護的な検出」に倒れる
（安全側）。この推定は静的読解に基づくもので、実際に強化コードを実装した実測ではない
（confidence: medium）。

**ギャップ**: 防御的強化を先に行うか、瑕疵挙動を意図的な仕様として残すかは未決。
どちらを選んでも現行テストの扱い（残す/書き換える）の判断が必要。

## AC3: 文言一致の機械検証テスト

「AC1『文言は設計書§4のとおり』」を厳密一致で検証するテストは存在しない。既存テストは
`CAP_PHRASE = "要点5行以内"` という短い部分文字列の存在確認のみ。

`docs/designs/KLK-004.md` §4は各エージェントの共通文言テンプレートを定義するが、
investigator.md等の実装はこのテンプレートに加えて「writer分担の括弧補記」を追加している
（KLK-004で受理された設計逸脱）。この追記部分は §4 本文には含まれないため、厳密一致テストが
無い現状ではテストから不可視になっている。

**ギャップ**: 設計逸脱（括弧補記）を許容する前提のテスト設計が必要（厳密一致にすると
既存の正当な逸脱がテスト側で検出されてしまうため、単純な文字列完全一致では不適切）。

## AC4: docs/reports/ gitignore非対象テスト

KLK-026完了（AC5決定: 選択肢(b)）により `.gitignore.public:46-50` に `docs/reports/*/`
除外パターンが実在することを確認した。

```
# KLK-026 AC5(b): docs/reports/{ID}/配下はプロセス記録のため公開プリセットで除外
docs/reports/*/
```

`tests/test_klk026_doc_wiring.py` の `TestGitignorePresetAsymmetry` はこのパターンの
**文字列としての存在**を確認するのみで、`git check-ignore` による実際のignore挙動
（末尾スラッシュの有無・`docs/reports/README.md`自体が意図通り追跡対象に残るか等）を
固定する実測テストはリポジトリ全体をgrep検索した結果、存在しない。

**ギャップ（事実整理・判断はarchitectへ）**: チケット本文のAC4原文は「`git check-ignore`が
NOT IGNOREDを返すこと」を求めているが、これはKLK-026 AC5決定**前**（docs/reports/を
追跡する前提）の文言のまま更新されていない。KLK-026 AC5(b)決定後の実態は
「`docs/reports/{ID}/`配下はIGNOREDが正」であるため、AC4の文言自体を
「IGNOREDになることを固定する」方向に訂正するかどうかの判断が必要。

## AC5/AC6: record_metrics.py非衝突・ポインタ書式テスト

`is_ticket()`（`.claude/hooks/_ticket_lib.py:116-`）自体は `tests/test_ticket_lib.py:110-124`
で `docs/reports/` 配下パスがFalseになることを直接テストされている。

`record_metrics.py` はticket判定を`lib.is_ticket(path)`ゲート1点に委譲しており、
`docs/reports`固有の分岐は持たない（全文確認済み）。しかし `tests/test_metrics.py` には
`docs/reports`を対象にした専用の非衝突シナリオテストはない（`test_non_ticket_ignored`等の
既存テストと対照した結果、`docs/reports`ケースが明示的にカバーされていないことを確認）。

「詳細: docs/reports/{ID}/{phase}.md」というポインタ書式そのものの存在を固定するテストは、
リポジトリ全体をgrep検索した結果、見つからなかった（ヒットなし）。

**ギャップ**: record_metrics.py側の`docs/reports`非衝突を対象にした専用テスト、および
ポインタ書式の存在を確認するテストのいずれも未実装。

## 参照ファイル（絶対パス）

- `.claude/agents/investigator.md` / `implementer.md` / `tester.md` / `reviewer.md` / `orchestrator.md`
- `docs/reports/README.md`
- `docs/designs/KLK-004.md`（§4・§9）
- `tests/test_klk004_doc_wiring.py:145-174`（`TestReportsReadmeConsistencyWithAgentFiles`）
- `tests/test_guard_bash_writes.py:690-716`
- `tests/test_klk026_doc_wiring.py`（`TestGitignorePresetAsymmetry`）
- `tests/test_ticket_lib.py:110-124`
- `tests/test_metrics.py`
- `.claude/hooks/guard_bash_writes.py:752-754`（`mentions_guarded`）
- `.claude/hooks/record_metrics.py`（全文）
- `.claude/hooks/_ticket_lib.py:116-`（`is_ticket`）
- `.gitignore.public:46-50`
- `tickets/done/KLK-026_docs-reports運用の実効化.md:100`

## Assumptions

- 「3箇所の内容一致」は目視比較の結果であり、将来のwriter分担変更が3箇所すべてに反映される
  保証は現行テストにはない、という前提でリスクを記載した
- AC2の「fail方向が安全側」は静的読解による推定（confidence: medium）。他の全項目は
  codebaseへの直接Read/grepに基づき confidence: high
- AC4/AC5の「専用テストが存在しない」は`grep -rn`によるリポジトリ全文検索の結果に基づく。
  100%の網羅を主張するものではない

## Unknowns

なし。本チケット範囲内でarchitectが判断すべき設計事項（一本化かテスト固定か、AC2テストの
去就、AC4文言の要訂正）はいずれも人間/architectの決定事項であり、investigator側で確定不能な
「調査上のUnknown」には該当しない。
