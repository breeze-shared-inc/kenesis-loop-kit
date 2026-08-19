# KLK-030 テストレポート（tester）

作成: 2026-08-18（tester自身が作成。docs/reports/{ID}/ はWrite/Edit可）

対応する設計書: `docs/designs/KLK-030.md`（方針b: コード無変更・安全性主張の明文化＋回帰テスト固定化）。
対応する実装ノート: `docs/reports/KLK-030/implementation.md`。

## 1. テスト実行結果

- `python3 -m unittest tests.test_guard_bash_writes -v` → **246件全件 OK**（既存INV-SED-01〜31を含む既存ケース＋implementerが追加したINV-SED-32〜48・`test_sed_strip_literals_path_pseudo_boundary_documented`）。
- `python3 -m unittest discover -s tests -v` → リポジトリ全体（`test_guard_bash_writes.py`以外の18ファイル含む）で**713件全件 OK**。KLK-030の変更（テスト追加のみ）が他モジュール（`test_ticket_lib.py`・`test_loop_integrity.py`・`test_validator.py`等）へ影響していないことを確認。

## 2. `git diff develop -- .claude/hooks/guard_bash_writes.py`

- 出力は空（差分なし）。`git diff develop --stat`では`tests/test_guard_bash_writes.py`（+88行）と`docs/reports/KLK-030/implementation.md`（新規）のみが変更対象。
- 補足: 同stat差分に`docs/designs/KLK-019.md`等の削除表示が出るが、これはこのfeatureブランチがdevelopの分岐後（`659c80f`）にマージされたKLK-019の2コミット（`9e9f04a`・`554bb34`）をまだ取り込んでいないことによるブランチ間の drift であり、KLK-030の実装が削除したものではない（`git log`で分岐点`659c80f`を確認済み）。マージ時にorchestratorが認識しておくべき情報として記録。

## 3. 設計書§9テスト観点(a)(b)(c)の個別確認

**(a) 危険文字が疑似トリガーの後にあるか:** INV-SED-32〜48の全17件を目視確認。いずれも先頭付近（アドレス前置き・実路パス構造模倣・カスタムデリミタ等、13カテゴリ）で発生する最初の生の`s`/`y`（`tickets`由来）より**後**の位置にw/r/eが配置されている。前方（既存INV-SED-09〜21と重複するような順序）に配置されたケースは無い。詳細はコード内コメント（`tests/test_guard_bash_writes.py` INV-SED-32直前のブロックコメント）を参照。

**(b) 単体テストの入力がticket再現手順そのものか:** `test_sed_strip_literals_path_pseudo_boundary_documented`の入力は`"1w tickets/active/sub/APP-001.md"`であり、チケット本文「再現手順」記載の入力文字列と完全一致（`git diff`で確認）。戻り値`"1w ticketsAPP-001.md"`とのassertEqualも再現手順の記述と整合。

**(c) Phase 1実機照合でallow(検出漏れ)が0件か:** `docs/reports/KLK-030/implementation.md`§2に17件全件の実機GNU sed 4.9照合結果が記録されている（15件は未定義ラベルエラー、2件はパース構文エラーで、いずれも実行前に停止。checker側も全件deny）。記録あり・検出漏れ0件を確認。

## 4. AC1〜AC4の個別チェック

- **AC1**: §4-1単体テスト1件＋§4-2 INV-SED-32〜48（17件）が追加され、`unittest`実行で全件期待どおりpass。13カテゴリ×最低1件・逆順重視の条件を満たす（§3の対応表と一致）。**満たす**。
- **AC2**: 既存INVENTORY_CASES（INV-SED-01〜31含む）は`git diff`で無変更、pytest/unittest実行でも全件pass。**満たす**。
- **AC3**: `.claude/hooks/guard_bash_writes.py`に差分なし（§2で確認）。新規denyはINV-SED-32〜48の17件に限定され列挙どおり。列挙外の新規denyは無い。**満たす**。
- **AC4**: `docs/designs/KLK-030.md`§3に主張・破れる形・向き・検出器・スコープ外（①〜⑤）が明記されている。§4-1・§4-2のテストが検出器として機能（本レポート§1・§3で実証）。**満たす**。

## 5. 独立エッジケース検証（implementerの17件とは別角度）

implementerが使用しなかった危険文字`a`/`i`/`c`/`b`/`t`/`T`/`:`を疑似トリガー（`tickets`のs）の後に配置する追加ケース、およびbranch系(`b`/`t`/`T`直前ラベル)・カスタムデリミタ`y`コマンド・複数文字接着等、13カテゴリの組み合わせを変えた計18件を`sed_program_violation`・`sed_strip_literals`・`find_violation`（コマンド全体）の3経路で個別に検証した（再現コマンドはスクラッチパッド`/tmp/.../scratchpad/verify1.py`・`verify2.py`。リポジトリには含めていない一時検証）。

- 全18件、3経路とも**DENY**（allow化なし）。
- うち12件は実機GNU sed 4.9でも実行し、全件`sed: can't find label for jump to ...`（終了コード4）でパース時点停止・サンドボックス内に新規ファイル生成なし。checker・実機とも実害0件で、implementerの結論（investigatorの3,345件照合と整合）を裏付け。
- 副次的な観察: 保護対象パス`tickets`自体が`SED_SAFE_COMMANDS`外の文字（`t`/`i`/`c`/`k`/`e`）を複数含むため、疑似境界探索で`s`以降が除去されても`ticket`部分（`s`を除く残り）がstripped内に残り、単独でdeny確定に寄与する。これは設計書§3(1)の「順序非依存」の主張をさらに裏付ける構造であり、`tickets`・`docs`等の現行の保護対象パス文字列を素材とする限り、危険文字の位置（前後）によらずdenyへ倒れることが構造的にほぼ保証される。検出漏れは見つからなかった。

## 6. 回帰リスク

- `.claude/hooks/guard_bash_writes.py`本体は無変更であり、実装ロジック起因の回帰リスクは構造的にゼロ。
- テスト追加分（17件＋1件）は既存INV-SED-01〜31と重複しない新規領域（逆順配置）をカバーしており、既存ケースとの重複による偽の安心感は生じていない。
- 全713件の既存テストスイートへの影響なし（§1で確認）。
