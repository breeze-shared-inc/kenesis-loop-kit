# KLK-015 テストレポート（tester）

## 1. テスト実行結果

- `python3 -m unittest tests.test_guard_bash_writes -v`: **211件中210件pass・1件fail**
  （実測。implementer完了時点の207件 + tester追加4件 = 211件）。
- `python3 -m unittest discover -s tests -p "test_*.py"`: リポジトリ全体
  **589件中588件pass・1件fail**（実測。implementer完了時点585件 +
  tester追加4件 = 589件）。巻き添え不合格は無し（fail 1件は tester が
  新規発見した欠陥を実証するために追加した回帰テスト）。
- pytest未インストールのため `python3 -m unittest` で代替（implementer前例と同じ）。

## 2. カバレッジサマリ（AC1〜AC9個別確認）

- AC1（INV-SED-09〜16）: `INVENTORY_CASES`内の`test_inventory_cases_match_expected_decisions`
  （subTest）で個別pass確認。`test_sed_address_prefixed_write_deny`が代表形3件を
  subTest非依存の固定点として追加済み（implementer実装）
- AC2（INV-SED-17〜21）: 同上。`test_sed_arbitrary_delimiter_write_deny`・
  `test_cwd_guarded_sed_address_and_delimiter_write_deny`が固定点
- AC3（INV-SED-06/07→deny更新・INV-SED-05は`allow`維持）: `INVENTORY_CASES`で確認。
  grep で `INV-SED-06`/`07` の期待値が `"deny"` であることを直接確認済み
- AC4（README・docstring・KLK-010.md訂正）: `grep -n "w／W コマンド\|w/W コマンド"`で
  overclaim文言が0件であることを確認。`docs/designs/KLK-010.md`に
  `[KLK-015追記]`が4箇所（§3-9・§6 R12・§6 R25・§10-1）入っていることを確認。
  README・docstringはSED-7の新規説明ブロックとして追記されており
  （既存文の書き換えではなく新設のため`[KLK-015追記]`タグ自体は無いが、
  旧文言の削除漏れが無いことをgrepで確認済み）
- AC5（INV-SED-08・26）: pass確認。加えてtesterが日常読み取り18パターンを
  追加で手動検証（後述4節）し、想定外denyが無いことを確認
- AC6（誤deny予算）: **fail**。詳細は4節
- AC7（既存deny回帰なし）: `LEGACY_DENY_COMMANDS`・INV-SED-01〜05・08すべてpass
- AC8（実機二方向検証）: implementer実施分（`docs/reports/KLK-015/implementation.md`）を
  tester側でも一部再現・追試（5節）。整合確認
- AC9（全件pass）: **fail**（tester追加分1件を含めると589件中588件pass。
  実装自体は既存207/585件を破壊していない＝実装起因の回帰は無し）

## 3. Failing Tests

- `tests/test_guard_bash_writes.py::TestGuardBashWrites::test_sed_bracket_expression_containing_delimiter_allow`
  （tester新規追加。**現状の実装に対して意図的にfailする回帰テスト**）
- 内容: `sed -n '/[/]/p' FILE`・`sed -n '/[^/]/p' FILE`・`sed 's/[/]/X/' FILE`
  （いずれも「区切り文字を含む文字クラス（ブラケット式）」を使う、実機で
  書き込み・実行を一切伴わない読み取り専用の日常パターン）が `deny` される
- 原因: `sed_strip_literals`（`.claude/hooks/guard_bash_writes.py`）はPOSIX/GNUの
  ブラケット式（`[...]`）を認識しないため、ブラケット式内の区切り文字（例:
  `[/]`内の`/`）を「アドレス正規表現の閉じデリミタ」と誤認して早期にクローズし、
  後続の走査が破綻して「字句を確定できません」（`None`）を返し deny になる
- 実機確認: `sed -n '/[/]/p' file`（スラッシュを含む行を表示するだけ）は
  GNU sed 4.9で書き込み・実行を一切行わない安全な読み取り専用コマンドである
  （`/tmp`配下で実行確認済み。exit=0・ファイル内容不変）
- **AC6違反の根拠**: 設計書 `docs/designs/KLK-015.md` §6 R1は新規denyを
  `r`/`R`・`a`/`i`/`c`・`b`/`t`/`T`/`:`・GNU拡張`z`/`F`/`v`・`s`/`y`の`i`/`I`/`m`/`M`
  フラグ・その他未収載の1文字コマンドの6分類に限定列挙しているが、本欠陥は
  この列挙のいずれにも該当しない「文字クラス（ブラケット式）非対応」という
  **第7の新規deny経路**であり、列挙外である
- 旧実装（`SED_WRITE_RE`ベース）との比較: `SED_WRITE_RE`は`[wW]`の存在を要求する
  正規表現であり、`w`/`W`を含まない`/[/]/p`には元々マッチしない（＝旧実装は
  allow）。したがって本件はSED-7導入によって**新たに**生まれた誤denyであり、
  「旧版からの既存の穴」ではない
- 再現性: `/[^/]/p`（否定文字クラス）・`s/[/]/X/`（s///のパターン内）でも
  同型の誤denyを確認。cwd guarded経路（`cd tickets/active && sed -n '/[/]/p' in.md`）
  でも同様に発生することを確認（ゲート経路に依らない）

## 4. Added Tests

- `tests/test_guard_bash_writes.py`
  - `test_sed_flag_area_allowed_flags_only_allow`（設計書§9テスト観点(c)後半形。
    s///のフラグ領域が許可済み文字のみの場合にallowのままであることの固定点）
  - `test_sed_multiple_dash_e_write_split_across_boundary_deny`（設計書§9
    テスト観点(b)・R3。複数`-e`の境界をまたぐwrite分割がdenyされる固定点。
    `len(texts) > 1`の結合チェック分岐に対する初のテストカバレッジ）
  - `test_sed_multiple_dash_e_readonly_combined_allow`（同(b)の対照allow側）
  - `test_sed_bracket_expression_containing_delimiter_allow`（tester新規発見の
    欠陥を実証する回帰テスト。**現状allowを期待して意図的にfail**）

## 5. Edge Cases Verified（設計書§9テスト観点(a)(b)(c)）

- (a) アドレス前置き×区切り文字の組み合わせ: INV-SED-20（実装済み）で十分に
  カバー済みと確認（追加不要）
- (b) 複数`-e`の境界をまたぐ分割: 実装済みコードパス（`len(texts) > 1`）が
  従来無テストだったため、tester側でdeny/allow双方の固定テストを追加
  （上記4節）。実機GNU sedでも二方向確認（block分割形`-e '1,2{' -e 'w FILE'
  -e '}'`は実際に書き込みが発生し、hookは正しくdeny。個々のフラグメント側で
  既に`w`が検出されるため、結合チェック自体が無くても現状denyは成立するが、
  結合チェックのコードパス自体に回帰テストが無かったため追加した）
- (c) s///のフラグ領域: `w`/`e`単独形（既存INV-SED-01/06）・`i`単独形
  （既存INV-SED-25）に加え、許可済みフラグのみの形（`g`/`p`/数字）の
  allow側をtesterが追加（4節）
- 追加で発見: ブラケット式（`[...]`）に区切り文字を含む形が誤denyになる
  （3節）。これは設計書のテスト観点3点には無い、tester独自の追加探索で
  発見した第4のエッジケースである

## 6. Regression Risks

- implementerの実装自体（Phase1〜3のコード）には既存回帰は無い
  （207/585件は全pass。tester追加分の1件failのみが新規）
- 発見した欠陥はSED-7導入前は存在しなかった新規の誤deny経路であり、
  ブラケット式を使うsedコマンド全般（アドレス正規表現・s///パターンの
  両方）に影響しうる。影響範囲はREADME・docstring・KLK-010.mdへの
  ドキュメント訂正（AC4）には含まれていないため、対応方針が確定するまで
  AC4の記述も再訂正が必要になる可能性がある

## 7. 実機再検証（AC8関連・抜粋）

- `sed -n '/[/]/p' file`・`sed -n '/[^/]/p' file`・`sed 's/[/]/X/' file`は
  いずれもGNU sed 4.9で書き込み・実行を伴わない（標準出力への表示のみ）
  ことを確認済み
- implementer報告のdeny側全形（アドレス前置き・区切り文字任意性・
  r/i/branch/大文字小文字無視フラグ・e系）の一部を再現し、書き込み・
  情報開示・実行が実際に発生することを再確認（`/[/]/w FILE`の変種も
  実機で書き込みを確認。ただしこの変種はhookが正しくdenyしている）

## 8. 再検証（2回目・commit fe4fd17・差し戻し1回目対応後）

### 8-1. 実行結果

- `python3 -m unittest tests.test_guard_bash_writes -v`: **212件中212件pass**
  （implementer報告と一致）。`test_sed_bracket_expression_containing_delimiter_allow`
  が今回passすることを個別実行でも確認。
- `python3 -m unittest discover -s tests -p "test_*.py"`: リポジトリ全体
  **590件中590件pass**（implementer報告と一致。巻き添え不合格なし）。
- `git diff a33c492 fe4fd17 --stat`: 変更は `.claude/hooks/guard_bash_writes.py`・
  `docs/reports/KLK-015/implementation.md`・`tests/test_guard_bash_writes.py`
  の3ファイルのみ。テストdiffは前回testerが追加した3assertion（コメントのみ更新、
  期待値・入力文字列は無傷）＋新規テスト1件の追加のみで、既存アサーションの
  弱体化・削除は無い。

### 8-2. 独自バイパス探索（bracket式起因）

`guard.find_violation` / `guard.sed_strip_literals` を直接importして10通りの
アドバーサリアルパターンを構成し、実機 GNU sed 4.9（`/tmp`配下）と突き合わせて
検証した。

- 検証対象: (A)アドレス内エスケープ`\[x\]`直後の実在w、(B)二重バックスラッシュ
  +素の否定クラス、(C)カスタム区切り文字と同じ文字をブラケット内容に含む形
  （`s@[@]@REPL@`）、(D)単独`[:w:]`（外側`[`無しの文字クラス風表記）、
  (E)ネストクラス`[[:alpha:]]`+外側の実在w、(F)ブラケット直後に空白なしで実在w、
  (G)未終端の照合記号`[.x`+実在w、(H)`[^]/]`（否定+先頭`]`特例）+実在w、
  (I)カスタムデリミタアドレス`\%[%]%p`、(J)非保護対象へのs///eフラグ形。
  加えて(K)s コマンドの区切り文字を`]`自体にする形（`s][b]]X]`
  ＝ブラケットの閉じ`]`と区切り文字`]`が字面上衝突する境界ケース）を追加検証。
- 結果: 全パターンでguardの判定は実機GNU sedの実際の安全性（書き込み・実行の
  有無）と整合。新たなバイパス（allowなのに実際に書き込み/実行が発生する形）
  は**発見されなかった**。(D)は実機GNU sedが`character class syntax is
  [[:space:]], not [:space:]`で構文エラー（exit=4）となり実行自体が起きない
  ため、guardのallow判定は無害（構文エラーで完全に処理が止まるsedの2パス
  コンパイル方式により副作用が生じ得ない）。(K)は実機で`s]a[b]c]`が
  `unterminated 's' command`エラーになる一方、`s][b]]X]`（ブラケットが
  正しく`]`で閉じ、直後の`]`が区切り文字として機能する境界例）は実機で
  安全に置換が成立し、Python側`sed_strip_literals`の判定（前者None＝deny、
  後者"s"＝allow）と完全に一致した。
- `_sed_skip_bracket_expression`の`[.`/`[=`/`[:`特殊要素の貪欲な`str.find`探索
  （途中の`]`を読み飛ばしてでも`.]`等の対応終端を探す）についても、実機で
  `[[.ab]cd.]]`（意図的に`]`を埋め込んだ照合記号もどき）が「Invalid
  collation character」エラーとなることを確認し、GNU sed自身も同じ貪欲探索
  を行っていることを裏取りした（over-skip側の懸念は実機的にも否定）。

### 8-3. 参考所見（本チケットのスコープ外・ブロッカーではない）

- `sed_strip_literals`のトップレベル走査は「`s`/`y`という**文字**が現れたら
  常にs/yコマンドの開始とみなす」設計のため、ガード対象パス文字列自体に
  `s`を含む（`tickets`・`docs`は末尾が`s`）場合、パス内で疑似的な区切り文字
  探索が発生することがある（例: `1w tickets/active/sub/APP-001.md`の
  stripped結果は`1w ticketsAPP-001.md`）。今回検証した範囲では、この現象が
  発生するのは実際の危険文字（`w`等）より**後**の位置のみであり、危険文字は
  常に`out`へ確定済みのため検出漏れ（allow化）には至らない。ブラケット式
  対応（本チケットのdiff）が原因ではなく、Phase 1由来の既存設計特性であり、
  今回のリトライ差分にも含まれない。allow化する具体例は見つからなかったが、
  `sed_strip_literals`全体の設計見直し（文単位でのs/yコマンド境界認識）は
  別チケットでの検討を推奨する。
