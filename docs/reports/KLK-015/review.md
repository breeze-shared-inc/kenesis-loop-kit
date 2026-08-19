# KLK-015 レビュー詳細

生成: reviewer（代筆: orchestrator） / 最終更新: 2026-08-17
対象: SED-7（sedプログラム本文ホワイトリスト）実装の最終レビュー
要点はチケット `KLK-015` の「レビューメモ」を参照。本ファイルは全文。

## Approval Status: approved

## Critical Issues
なし。

## High Risks
なし。SED-7の設計不変条件（P8: under-removal方向にのみ倒れる）は独自の10パターンのアドバーサリアル検証（`_sed_skip_bracket_expression`のネスト特殊要素・`[.ab.]`単独形・`s]...]`型の区切り文字衝突・複数`-e`結合等）でも破れを確認できず、実機GNU sed 4.9の挙動と一致した。

## Medium Risks
- ブラケット式の`[.`/`[=`/`[:`特殊要素終端探索が`str.find`によるテキスト末尾までの貪欲探索であり、複数`-e`結合（`"\n".join(texts)`）時に改行をまたいだ意図しない終端一致の余地が理論上残る（tester・implementerが個別に実機裏取り済みで顕在化なし。将来のリグレッションで気づきにくい）
- `mentions_guarded`のエスケープ回避経路・`sed_strip_literals`のパス末尾`s`疑似境界探索（tester/implementer申し送り2件）は、いずれもSED-7導入前から存在するL2パス検出層の既知の限界であり、本チケットの承認済みスコープ（プログラム本文の文字ホワイトリスト）とは別層。実害未確認・別チケット候補として扱うのが妥当で承認判断には影響しない

## Missing Tests
未終端ブラケット式（`sed -n '/[abc/p'`等・対応する`]`が無い形）がNoneでdenyになることの固定回帰テストが無い（implementerの実装メモに実機確認の記載はあるが、`tests/`への固定化が未実施）。P8の安全側方向はコード構造上保証されるため必須ブロッカーではないが、次回改修時の検出力のために追加を推奨。

## Spec Violations
なし。AC1〜AC9はすべて設計書§4-7 実装Phaseテーブルでカバーされており（Phase1: AC1-3・5暫定・7暫定／Phase2: AC4／Phase3: AC6・7最終・8・9）、実装・テスト・ドキュメント訂正が設計書の指示と一致することを確認した。README・docstring・`docs/designs/KLK-010.md`の訂正はgrepでoverclaim文言ゼロを確認、`[KLK-015追記]`は設計書§4-5が要求する5箇所すべてに付与されている。

## Suggested Fixes
- 未終端ブラケット式のdeny固定テストを追加する（Missing Tests参照。ブロッカーではない）
- `mentions_guarded`のエスケープ回避・`sed_strip_literals`のパス末尾`s`境界探索の2件は、reviewer承認後に人間へ新規チケット化の要否を確認する

## 検証内容の要約

- コード差分（`.claude/hooks/guard_bash_writes.py`・`tests/test_guard_bash_writes.py`・`.claude/hooks/README.md`・`docs/designs/KLK-010.md`）を設計書§4-1〜§4-6と1対1で照合し、実装は設計コード例どおりであることを確認
- `python3 -m unittest tests.test_guard_bash_writes -v`で212/212件pass、`python3 -m unittest discover`でリポジトリ全体590/590件pass（worktree内で自ら再実行し実測）
- reviewer独自に10パターンのアドバーサリアルテスト（tester・implementerの検証パターンとは別構成）をGNU sed 4.9実機と突き合わせて実施し、新規バイパスなしを確認（`/tmp`配下scratchpadで実施。実チケットパスは使わず`OUTPUT.md`ダミーで検証）
- `mentions_guarded`のゲート変更（トークン単位→`mentions_guarded(flat)`）が旧`is_guarded_token`判定より狭まらないこと（`mentions_guarded`は`any(is_guarded_token(v) for v in values)`の定義そのもの）をコードレベルで確認
- git log 7コミットはすべて`[KLK-015] {内容}`規約に準拠しPhase単位（Phase1/2/3＋差し戻し対応1回）。`git diff develop...HEAD`に機密情報（APIキー・パスワード等）の混入なし

## 参照した実ファイル

- `.claude/hooks/guard_bash_writes.py`
- `tests/test_guard_bash_writes.py`
- `.claude/hooks/README.md`
- `docs/designs/KLK-010.md`
- `docs/designs/KLK-015.md`
- `docs/reports/KLK-015/investigation.md`
- `docs/reports/KLK-015/implementation.md`
- `docs/reports/KLK-015/test-report.md`
- `tickets/active/KLK-015_sedスクリプト引数の書き込み実行経路の網羅.md`
