# KLK-015 実装レポート（implementer）

## 実施内容

### Phase 1: SED-7（プログラム本文ホワイトリスト）検出ロジック実装
- `.claude/hooks/guard_bash_writes.py`: `SED_WRITE_RE` の直後へ設計書§4-1の定数
  （`SED_SAFE_COMMANDS`／`SED_SAFE_STRUCTURAL_CHARS`／`SED_SAFE_PROGRAM_CHARS`／
  `SED_PROGRAM_TEXT_FLAGS`／`SED_SCRIPT_VALUE_FLAGS`）を設計書のコード例のまま追加。
- `awk_program_violation` の直後（`awk_violation` の手前）へ設計書§4-2の関数
  （`sed_strip_literals`／`sed_program_texts`／`sed_program_violation`）を設計書の
  コード例のまま追加。
- `segment_violation` の `head == "sed"` 分岐を設計書§4-3のとおり置き換え。
  `degraded=True` のときのみ従来の `SED_WRITE_RE` ブラックリストを維持し、
  正常経路では `mentions_guarded(flat) or strict` をゲートに
  `sed_program_texts`/`sed_program_violation` を適用する2分岐へ改めた。
- `ALLOWED_HEADS` の `"sed"` コメントを設計書§4-4のとおり更新。
- 完了条件の実測: 既存テスト203件中201件pass（INV-SED-06/07は設計どおり
  一時的にfail。Phase3で期待値をdenyへ更新して解消）。チケット本文の再現手順
  A・A-4・Bの全形をローカルでhookへ通し、期待どおりdeny/allowになることを確認
  （詳細は本ファイル「実機二方向検証（AC8）」節）。

### Phase 2: ドキュメント訂正
- `.claude/hooks/README.md`: sedの`w`コマンド遮断の記述をSED-7ホワイトリストの
  説明へ差し替え、「既知の未対応」列からGNU sedの`e`フラグを削除。「保守側へ
  倒している判定」列も、旧`SED_WRITE_RE`ベースの誤deny例（`sed 's/a w b/c/'`）
  がSED-7で解消されたことを反映し、R1の新規deny一覧へ差し替えた。
- `.claude/hooks/guard_bash_writes.py` モジュールdocstring: 「sedの-i全表記と
  w／Wコマンド」→「sedの-i全表記とプログラム本文のホワイトリスト（SED-7）」に
  修正。awkのプログラム本文説明ブロックの直後にSED-7の説明ブロック（P9の3点：
  否定形・向き・検出器）を新設。「既知の未対応」列からGNU sedの`e`フラグ・
  `e`コマンドを削除（`-f SCRIPT`のみ残存）。「保守側へ倒している判定」列を
  README.mdと同様にR1の新規deny一覧へ更新。
- `docs/designs/KLK-010.md`: §3-9 sed行（`GNU e フラグ・eコマンド→未対応`・
  `この次元は第4版でもブラックリストのまま`）、§3-11 INV-SED-01/02/04/06/07行、
  §6 R12・R25行、§10-1申し送り2の該当箇所へ、すべて`[KLK-015追記]`形式で
  追記した（既存記述は削除していない）。
- 完了条件の確認: `grep -rn "w／W コマンド\|w/W コマンド"` で
  README・docstring・KLK-010.mdに実装より強い保護を主張する記述が残っていない
  ことを確認。

### Phase 3: 回帰テスト追加・実機二方向検証
- `tests/test_guard_bash_writes.py` の `INVENTORY_CASES` へ INV-SED-09〜26
  （アドレス前置き6形・区切り文字任意性3形・組み合わせ2形・r/i/branch/
  大文字小文字無視フラグ各1形・日常読み取り追加固定1形）を追加。
  INV-SED-26の第2例（`1,+3p`）は個別テスト
  `test_sed_gnu_extended_address_allow` として追加（design表は1IDに2例を
  併記していたため）。
- INV-SED-06・07の期待値を `allow` → `deny` へ更新。ヘッダコメント・
  「期待値allowの3分類」コメントの該当箇所（INV-SED-05〜07→INV-SED-05のみ）
  も整合するよう更新した。
- `test_sed_write_command_deny` の近傍へ `test_sed_address_prefixed_write_deny`・
  `test_sed_arbitrary_delimiter_write_deny` を、`test_cwd_guarded_sed_write_command_deny`
  の近傍へ `test_cwd_guarded_sed_address_and_delimiter_write_deny` を追加し、
  代表形をsubTest頼みにしない固定点とした（KLK-010のT-SEDWと同じ運用）。

## 実測結果

- `python3 -m unittest tests.test_guard_bash_writes -v`: **207件中207件pass**
  （Phase1着手前の実測値は203件。チケット記載の「437件」は未確認の推測値
  だったため、実測値203→207件を正として報告する）。
- `python3 -m unittest discover -s tests -p "test_*.py"`: リポジトリ全体
  **585件中585件pass**（巻き添え不合格なし）。
- 実行環境にpytestが未インストールのため、KLK-005前例と同様に
  `python3 -m unittest` で代替実施。

## 実機二方向検証（AC8）

`/tmp/klk015_verify`（`prot_dir/PROTECTED.md` を保護対象ダミー・`in.md` を
`a\nb\nc\n` とする3行入力）で、GNU sed 4.9を**hookを経由せず直接**実行し、
設計書§4-6の新規deny全形が実際に書き込み・情報開示・任意コマンド実行を
行うことと、allow側が読み取りのみで書き込みを起こさないことを確認した。

**deny側（実際に危険な効果を確認）:**
- アドレス前置き（INV-SED-09〜14・16・20）: `1w`/`$w`/`1,2w`/`2!w`/`0~2w`/
  `1W`/cwd相対/組み合わせ形のいずれも `PROTECTED.md` の内容を入力行で上書き。
- `-e`形（INV-SED-15）・区切り文字任意性（INV-SED-17〜19・21、`#`/`,`/`\|`/
  `y`コマンド）も同様に上書きを確認。
- INV-SED-22（`r /etc/hosts` 相当）: 外部ファイル内容が標準出力に混入
  （情報開示を確認）。
- INV-SED-23（`1i hello`）: 任意テキストが出力へ挿入されることを確認。
- INV-SED-24（`:a;b a`）: 無限ループ（`timeout 2`でexit=124）となり、
  分岐・ラベルが読み取り専用の想定を逸脱する制御構文であることを確認。
- INV-SED-25（`s/a/b/i`）: 大文字小文字無視フラグが実際に有効であることを確認
  （`Line1` → `X1`）。
- チケット本文 再現手順B: `e`コマンド（`sed 'e echo INJECTED' ...`）・
  `s///e`（`sed 's/.*/echo INJECTED2/e' ...`）のいずれも任意シェルコマンドが
  実行されることを確認。

**allow側（読み取りのみで書き込みなしを確認）:**
- INV-SED-08（`-n '1,5p'`）・INV-SED-26（`-n '0~2p'`・`-n '1,+3p'`）は
  いずれも `PROTECTED.md` の内容が実行前後で不変。
- INV-SED-05（`-f SCRIPT`）はスコープ外の既知の穴のとおり実際に上書きが
  発生することも確認済み（本チケットでは対応しない。設計書R1・AC3の
  「`-f`のみ残存」という記載と整合）。

## コミット

- `871ed4b` `[KLK-015] Phase 1: SED-7（sedプログラム本文ホワイトリスト）の検出ロジック実装`
- `9e27e93` `[KLK-015] Phase 2: ドキュメント訂正（README・docstring・KLK-010.md）`
- `8c4992f` `[KLK-015] Phase 3: 回帰テスト追加（INV-SED-09〜26）・実機二方向検証`

## 残存リスク・orchestratorへの申し送り

- **新規発見（L2パス検出の既知の限界。本チケットのスコープ外・SED-7の欠陥ではない）**:
  `sed_program_violation` はプログラム本文が保護対象へ言及する／保護対象を
  cwdとする場合にのみゲートされる（`mentions_guarded(flat) or strict`）。
  `mentions_guarded` は `PATHISH_RE`（`[A-Za-z0-9_.\-/]+`）でパス候補を抽出する
  ため、`s///` の区切り文字が `/` の場合、置換文字列中の保護対象パスを
  エスケープする必要がある（例: `sed 's/.*/rm docs\/SPEC.md/e' unrelated.txt`）と、
  バックスラッシュがパス候補のマッチを分断し `mentions_guarded` が偽になる
  （検証済み: `s/.*/rm docs\/SPEC.md/e` は `docs\/SPEC.md` がguarded pathとして
  検出されず、outer操作対象`unrelated.txt`もguardedでないため、この1コマンドは
  ゲート自体が発火せず allow のまま）。この経路は同じ構造（AW-2/AW-7も
  `mentions_guarded`をゲートに使う）がawk側にも理論上存在しうるが、awkの
  文字列リテラルは`/`のエスケープを要さないため顕在化しにくい。設計書の
  正式回帰テスト（INV-SED-06・07）は保護対象を独立した位置引数
  （`tickets/active/APP-001.md`）に置く形で構成されており、この形は正しく
  denyになることを確認済み（AC3は充足）。上記の「エスケープでゲートを
  すり抜ける」形は設計書のOpen Questions・Risk表（R1〜R7）に記載がなく、
  本チケットの承認済みスコープ（SED-7のコマンド文字ホワイトリスト）とは
  別の層（L2パス検出）の話であるため、設計変更の承認なしに実装を拡張する
  ことは避け、**新規発見として本レポートで報告するに留めた**。対応する場合は
  `PATHISH_RE`もしくは`guarded_paths`の拡張が必要で、他のhead（sed以外）にも
  影響する可能性があるため、追加チケットでの検討を推奨する。
- degraded経路は設計どおり`SED_WRITE_RE`のまま変更していない（`w`/`e`/`i`
  以外を絶対に許可文字集合へ含めていないこと、AC1〜3が破れていないことは
  Phase1〜3のテストで確認済み）。

## 差し戻し対応（tester→implementer 1回目・ブラケット式の誤deny解消）

### 欠陥の原因

`sed_strip_literals`（`.claude/hooks/guard_bash_writes.py`）の3つのデリミタ走査
（アドレス正規表現`/…/`・カスタムデリミタ`\cXXXc`・`s`のパターンフィールド）が
POSIX/GNUのブラケット式（`[...]`）を認識せず、ブラケット式内側のデリミタ文字
（`[/]`内の`/`等）を閉じデリミタと誤認して早期にクローズし、後続の走査が破綻
して`None`（判定不能）を返しdenyになっていた（`test_sed_bracket_expression_
containing_delimiter_allow`が実証）。

### 修正内容

- 新設関数`_sed_skip_bracket_expression(text, i)`をPOSIXブラケット式の字句規則
  （`^`否定・先頭`]`のリテラル特例・`[.`/`[=`/`[:`特殊要素の対応`.]`/`=]`/`:]`
  までの読み飛ばし・改行での未終端判定）に従って実装し、`sed_strip_literals`の
  3走査すべてへ組み込んだ。`s`コマンドは**パターンフィールドのみ**
  （`found == 0`の間）にブラケット判定を適用し、置換フィールド・`y`コマンドの
  両フィールド（リテラルでブラケット構文を持たない）には適用しない。
- ブラケット式内部は**バックスラッシュをエスケープとして扱わない**（POSIXの
  規則どおり。GNU sed 4.9で実機確認済み: `[\]]`は「`\`のみの文字クラス」＋
  直後のリテラル`]`）。
- 未終端（対応する`]`が見つからない）はunder-skip側へ倒し`None`を返す
  （P8を維持。over-skipする経路は構造的に存在しない——最初に出会う`]`で
  必ず終了するため）。

### 実機再検証（GNU sed 4.9、`/tmp`配下で実行）

- `sed -n '/[/]/p'`・`sed -n '/[^/]/p'`・`sed 's/[/]/X/'`: いずれも書き込み
  なしの読み取り専用であることを再確認（tester報告と一致）。
- ブラケット式の周辺ケース: `[]/]`（先頭`]`のリテラル特例）・
  `[[:alpha:]]`（ネストした文字クラス）はいずれも正しく解析されallow。
  `/[/p`（未終端）・`/[.ab/p`（未終端の照合記号）は実機でも構文エラー
  （exit=1）であり、本実装も`None`（deny）を返すことを確認（P8整合）。
- **バイパス検証**: `sed 's/[/]w FILE/X/'`（パターンフィールド内にリテラル
  として`w FILE`という文字列が現れる形）は実機で書き込みが発生しない
  （`w FILE`は正規表現の一部であり`w`コマンドとして機能しない）ことを確認。
  本実装もこの形をallowにする（バイパスではなく実際の安全な形との一致）。
- **回帰なしの確認**: ブラケット式を含む正規表現の後に**実在の**`w`コマンドが
  続く形（`sed -n '/[/]/w FILE'`）は実機で実際にファイル書き込みが発生する
  ことを確認し、本実装も引き続きdenyすることを確認（`test_sed_bracket_
  expression_does_not_hide_real_write_deny`として固定化）。

### 追加テスト

- `tests/test_guard_bash_writes.py`
  - `test_sed_bracket_expression_containing_delimiter_allow`（tester追加分。
    コメントを「現状failを意図」から「差し戻し1回目で修正済み」へ更新。
    アサーション自体は変更していない）
  - `test_sed_bracket_expression_does_not_hide_real_write_deny`
    （implementer新規追加。ブラケット式対応が新たなバイパス経路を生まない
    ことの固定点。deny側1形・allow側の対照1形）

### 実測結果（再測）

- `python3 -m unittest tests.test_guard_bash_writes -v`: 212件中212件pass
  （tester時点211件 + 本修正で追加した1件 = 212件）。
- `python3 -m unittest discover -s tests -p "test_*.py"`: 590件中590件pass
  （巻き添え不合格なし）。
