---
ticket: "KLK-019"
phase: "test"
created: "2026-08-18"
---

# [KLK-019] テストレポート

## 1. 実行結果（実測）

- `python3 -m unittest discover -s tests -v`: **731件中5件FAIL**（implementer報告時点の726件＋tester追加5件。既存726件はすべてPASS、FAILは全てtester追加の回帰固定テスト）
- `python3 -m unittest tests.test_guard_bash_writes -v`: 264件中5件FAIL（既存259件PASS＋追加5件FAIL）
- `LEGACY_DENY_COMMANDS`: 130件（実測。全件deny維持を確認）
- `INVENTORY_CASES`: 117件（実測。うち`INV-CTRL-*`25件。全件が期待どおりの判定 = INV-CTRL-01〜25の期待値と一致することを個別確認）
- `INV-SH-11`（`f=tickets/active/APP-001.md; rm $f`が恒久的にallow）: 回帰なし。KLK-019追加の`test_klk019_inv_sh_11_unaffected_by_loop_var_separation`もPASS

## 2. R-CTRL3補正・test_klk019_closing_keyword_* の確認

- 設計書§6 R-CTRL3は実装時に「fi/done/escは常に統計の末尾で単独語」という前提が破れることが判明し補正されている。§4のコード（`CONTROL_CLOSING_KEYWORDS`の定義コメント・`strip_control_prefix`のdocstring「実装時の補正」節）と実装コード（`.claude/hooks/guard_bash_writes.py` 550-577行目, 2676-2720行目）は完全に一致することをReadで確認した
- `test_klk019_closing_keyword_trailing_redirect_allow`: `done`/`fi`/`esac`直後に区切りなしで`< FILE`（読み取りリダイレクト）が続く3形がallowになることを固定。アサーション内容は意図どおり（`<`はredirect_inで書き込みを発生させないため安全）
- `test_klk019_closing_keyword_pipe_write_still_denies`: 同じ閉じキーワード直後がパイプで実コマンドへ続く形（`done | rm ...`）が独立したパイプ区間として引き続きdenyされ、新しい許可経路を作っていないことを固定。対の`done | cat ...`がallowになることも同一テスト内で確認しており、アサーションは意図どおり機能している
- 実測: 上記2テストおよび`test_klk019_standalone_closing_keywords_allow`はいずれもPASS（726件の一部として確認済み）

## 3. 新規テスト内容の確認（Read実施）

- `test_klk019_*`14件（実装時点）＋tester追加5件＝19件、`INV-CTRL-01`〜`25`の計25件を全件Readし、コマンド文字列とallow/deny期待値の対応を設計書§9 AC1〜AC6・実装Phase表と突き合わせた。矛盾なし
- AC4の分岐列挙（classic for読み取り／書き込み（リテラル/ループ変数）／`for NAME;do`／C形式for／while/until/if各形／case各形／入れ子／cwd追跡／単独閉じキーワード）とINV-CTRL-01〜25が1対1で対応していることを確認

## 4. AC6独自検証（重点実施）— **新たなdeny→allow転換をブロッカーとして検出**

設計書§9 N1〜N6以外の形で新たにallowへ転じるものがないか、`strip_control_prefix`・`record_loop_binding`・`record_assignments`を実ファイルでReadし、深い入れ子・複数制御構文の組み合わせ・C形式for・caseの複数パターン等、追加パターンを実機bash（scratchpad内の隔離フィクスチャ、実プロジェクトファイルは一切変更していない）で検証した。

**検出した問題（Quality Gate: FAIL相当のブロッカー）:**

`record_loop_binding`（for ループ変数の登録）と`record_assignments`（前置き代入の登録）は、いずれも`strip_control_prefix`を経由しない**生の（un-stripped）statement語**を見て「先頭語が`for`か」「先頭語が`NAME=value`形か」を判定している。これに対し、`statement_violation`のALLOWED_HEADS判定と`find_violation`のcwd追跡は`control_stripped_segments`（§4 R-CTRL4で共有必須と明記）を経由する。この非対称のため、**内側の`for NAME in LIST`ヘッダーや前置き代入が、外側の制御構文の`do`/`then`と`;`区切りで同一statementを共有する**（`; do for f in ...`のような、入れ子ループのごく一般的な書き方）と、`NAME`/代入変数の登録が丸ごと失敗し、後続の書き込み文（`do rm $f`等）にゲートが一切立たず**allowへ転じる**。

再現手順（実機bash・隔離フィクスチャで確認。V-14と同型の二方向検証をtester自身が実施）:
```
for i in 1 2; do for f in tickets/active/*.md; do rm $f; done; done   # 現状: allow（誤り。deny必須）
if true; then for f in tickets/active/*.md; do rm $f; done; fi        # 同上
while true; do for f in tickets/active/*.md; do rm $f; done; break; done  # 同上
for i in 1 2; do for f in tickets/active/*.md; do echo x > $f; done; done  # redirect経路も同様にallow
for i in 1 2; do f=tickets/active/APP-001.md; echo x > $f; done       # 前置き代入側も同型の穴
```
上記5形はいずれも、pre-KLK-019版（コミット`e0dbb49`の親）では`'do'`/`'then'`が未許可headとして正しくdenyしていたことをgit show経由で再確認済み（＝KLK-019のPhase1/2実装で新たに開いた穴であり、既存の限界の継続ではない）。実機bash実行でも、隔離フィクスチャ上のダミーファイルが実際に削除・上書きされることを確認した（本番のtickets/active配下は一切操作していない）。

N1〜N6のいずれにも該当しない（N1〜N5は「入れ子の末端COND/BODYがN1条件を満たす場合」だが、本件は末端ではなく**ループ変数登録という中間状態の消失**が原因であり性質が異なる）。**AC6により1件でもあればブロッカー**の条件に該当する。

## 5. Added Tests（詳細）

`tests/test_guard_bash_writes.py`へ5件追加（いずれも上記バグの回帰固定・現状FAIL）:
- `test_klk019_regression_nested_for_loop_var_write_denies_do_prefix`
- `test_klk019_regression_nested_for_loop_var_write_denies_then_prefix`
- `test_klk019_regression_nested_for_loop_var_write_denies_while_prefix`
- `test_klk019_regression_nested_for_loop_var_redirect_write_denies`
- `test_klk019_regression_nested_assignment_redirect_write_denies`

いずれもプロダクションコード（`.claude/hooks/guard_bash_writes.py`）は変更していない。テストファイルのみの追加。

## 6. Edge Cases Verified（AC6独自パターン一覧・実機bash確認込み）

allowと判定され実機でも書き込みが起きない（正しい）ことを確認したもの: 深い3重入れ子読み取り（for→while→if→case）・複数elif分岐の読み取り・caseのブラケットパターン`[ab])`読み取り・cd追跡＋case/while組み合わせの読み取り・ループ変数エイリアス読み取り。
denyと判定され意図どおりのもの: 深い3重入れ子書き込み・複数elif分岐の書き込み・caseブラケットパターン書き込み・while条件節書き込み・until本体書き込み・C形式for・caseの複数パターン・forヘッダー内のコマンド置換書き込み・cd追跡＋whileの書き込み。
**allowと判定されたが実機で書き込みが発生した（バグ）**: 上記§4の5パターン。
ループ変数エイリアス書き込み（`g=$f; rm $g`）はallowだったが、これは既存INV-SH-11と同型の「値追跡は原理的に不可能」という既存の限界の延長であり、pre-KLK-019でも別経路（一次代入の値追跡）で同様に閉じられない旨が設計書に明記済みのため新規回帰としては扱っていない（トップレベルの`f=path;rm $f`が既存allowであることと同型）。

## 7. Regression Risks

- LEGACY_DENY_COMMANDS 130件・INVENTORY_CASES 117件は無回帰（実測）
- INV-SH-11の分離設計（guarded_vars/guarded_loop_vars）は退行なし
- 上記§4のバグはPhase1/2実装（`record_loop_binding`・`record_assignments`）の設計とのズレが原因であり、設計書自体（`control_stripped_segments`をALLOWED_HEADS判定・cwd追跡の両方に適用する設計）に誤りはない。修正は実装側（`record_loop_binding`/`record_assignments`の呼び出し前に対象statementを`strip_control_prefix`相当で正規化する）に閉じると見込まれる
