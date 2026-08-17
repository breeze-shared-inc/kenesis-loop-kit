# KLK-029 実装レポート（implementer）

## Phase 1: ゲート改修

### 変更内容
`docs/designs/KLK-029.md` §4-1〜§4-4のとおり実装。

- §4-1: `mentions_guarded`直後に`unescape_program_backslashes`・`_is_guarded_path_component`・
  `guarded_paths_in_program`・`is_guarded_token_in_program`・`mentions_guarded_in_program`・
  定数`PROGRAM_TEXT_HEADS`を新設。設計書のコードをそのまま転記。
- §4-2: `segment_violation`の`elif strict or mentions_guarded(flat):`を
  `mentions_guarded_in_program(flat)`へ差し替え（degraded分岐の`is_guarded_token(t)`は無変更）。
- §4-3: `awk_violation`のAW-1・AW-2・共有ゲート3箇所を`is_guarded_token_in_program`／
  `mentions_guarded_in_program`へ差し替え。
- §4-4: `statement_violation`の共有ゲートを、`pipe_segments`を1回だけ呼び出して
  `head_of(seg) in PROGRAM_TEXT_HEADS`でsed/awk含有文を判定し、含む場合のみ
  `mentions_guarded_in_program`を使うよう差し替え。

### 設計との差分（軽微・非意味論的）
`_is_guarded_path_component`のdocstringに`\/`が含まれるため、設計書の転記どおり`"""`のままだと
`SyntaxWarning: invalid escape sequence '\/'`が出た（Python 3.12）。docstring本文は一切変更せず、
`r"""`（raw文字列プレフィックス）を付けるだけの修正を行った（`unescape_program_backslashes`は
設計書の時点で既に`r"""`だったため、同じ扱いに揃えた形）。動作・文言に影響なし。

### AC4確認（`git diff`によるdiff無し確認）
```
$ git diff -U0 .claude/hooks/guard_bash_writes.py \
    | grep -E "^[-+][^-+]" \
    | grep -E "PATHISH_RE = |^def guarded_paths\(|^def _is_guarded_path\(|^def is_guarded_token\(|^def mentions_guarded\("
（出力なし = 上記5定義に変更なし）
```
`git diff --stat`: `.claude/hooks/guard_bash_writes.py | 134 ++++++++++++++--- (124 insertions, 10 deletions)`。
削除10行はすべて§4-2〜4-4の3箇所の呼び出し名差し替え・`statement_violation`のゲート整形分。

### 既存テスト（ベースライン213件）
```
$ python3 -m unittest tests.test_guard_bash_writes
Ran 213 tests in ~24-36s
OK
```
（Phase 1適用後、追加テストなしの状態で実行。213件全pass）

### 再現手順の実機投入結果（AC1）
`find_violation()`を直接呼び出して確認（investigation.md 詳細調査ログ2・3の形）。

| コマンド | 修正前（investigation.md記載） | 修正後（本実装） |
|---|---|---|
| `sed 's/.*/rm docs\/SPEC.md/e' unrelated.txt` | `None`（allow） | `sed プログラムに許可されていないコマンド／文字 'e' があります…`（deny） |
| `sed 's/.*/rm tickets\/active\/APP-001.md/e' unrelated.txt` | `None`（allow） | 同上（deny） |
| `awk 'BEGIN{system("rm tickets\/active\/APP-001.md")}' unrelated.txt` | `None`（allow） | `awk プログラムの関数呼び出し system() は許可されていません…`（deny） |
| `awk '{print > "tickets\/active\/APP-001.md"}' unrelated.txt` | `None`（allow） | `awk のプログラム内リダイレクト（print > file 等）は許可されていません`（deny） |
| `sed '1e echo tickets\/active\/APP-001.md' unrelated.txt`（investigation.md詳細調査ログ5系） | （調査時未実機投入・理論上バイパス） | `sed プログラムの字句を確定できません…`（deny。SED-7本体のfail-closed経由で到達・確認） |

いずれもdenyへ転じたことを確認済み。5件目は文字列パターンが厳密なアドレス正規表現として解釈されずSED-7本体の字句解析失敗によるfail-closed denyとなったが、ゲート自体は正しく通過しSED-7本体（無変更）へ到達している。

## Phase 2: 回帰テスト追加

### 変更内容
`tests/test_guard_bash_writes.py`の`INVENTORY_CASES`へ設計書§4-5のとおりINV-SED-27〜31
（INV-SED-26の直後）・INV-AWK-21〜25（INV-AWK-20の直後）の計10件を追加。コマンド文字列は
設計書表の記載と1文字単位で一致することを`repr()`出力で確認済み。

### 実行結果と設計書記載値との差異（重要・テスターへの申し送り）
`INVENTORY_CASES`は単一のテストメソッド`test_inventory_cases_match_expected_decisions`内で
`subTest`によりループ処理される実装（Phase 1着手前から既存の構造・変更していない）。そのため
`python3 -m unittest`の`Ran N tests`はエントリ数を追加しても**213のまま**動かない
（`subTest`は失敗時のみ個別に表示され、成功時はテストケース数としてカウントされない仕様）。
設計書§4-7完了条件の「全件（213+10件）がpass」は、`Ran 223 tests`という数値としては現れない
（unittestの仕様上の制約であり実装の不備ではない）。実際には10件個別に`guard.find_violation()`
を直接呼び出して期待値と突き合わせ、全10件が一致することを確認した（下記）。

```
INV-AWK-21: expected=deny actual=deny [OK]
INV-AWK-22: expected=deny actual=deny [OK]
INV-AWK-23: expected=deny actual=deny [OK]
INV-AWK-24: expected=deny actual=deny [OK]
INV-AWK-25: expected=allow actual=allow [OK]
INV-SED-27: expected=deny actual=deny [OK]
INV-SED-28: expected=deny actual=deny [OK]
INV-SED-29: expected=deny actual=deny [OK]
INV-SED-30: expected=allow actual=allow [OK]
INV-SED-31: expected=deny actual=deny [OK]
```

### 全件再実行（回帰なしの確認）
```
$ python3 -m unittest tests.test_guard_bash_writes
Ran 213 tests in ~24-25s
OK
```
既存213件のexpected値は一切変更していない（追加のみ）。新規10件は設計書§6 R1の列挙（①〜⑤）と
1対1に対応し、列挙外の新規denyは発生していない（AC5）。

## Phase 3: ドキュメント更新

### 変更内容
- `.claude/hooks/README.md`の`guard_bash_writes.py`説明行、「**保守側へ倒している判定**」の
  直前へ設計書§4-6記載の追記文（sed/awkゲート緩和の内容・degraded mode対象外＝R-U1）を
  そのまま挿入。
- `.claude/hooks/guard_bash_writes.py`モジュールdocstring、sedプログラム本文の説明ブロック
  （SED-7）の直後・「書き込み先オペランドとcwd」ブロックの直前へ、既存の他ブロックと同じ
  P8/P9形式（主張・破れる形（否定形）・向き・検出器）で追記。§4-1のコード内コメントブロック
  の要旨を転記し、degraded mode対象外である旨も明記。

### 整合性確認
`grep -n "KLK-029" .claude/hooks/guard_bash_writes.py`で、新設関数群（§4-1）・awk_violation
差し替え箇所（§4-3）・statement_violation差し替え箇所（§4-4）・モジュールdocstring追記（§4-6）
の4系統にKLK-029コメントが対応していることを確認。README追記は「sed/awk限定」「degraded
mode対象外」の2点がPhase 1実装（PROGRAM_TEXT_HEADS = {"sed","awk"}・degraded_violation無変更）
と一致することを確認済み。

### 最終確認
```
$ python3 -W error::SyntaxWarning -c "import ast; ast.parse(open('.claude/hooks/guard_bash_writes.py').read())"
（エラー・警告なし）
$ python3 -m unittest tests.test_guard_bash_writes
Ran 213 tests in ~25-27s
OK
```
