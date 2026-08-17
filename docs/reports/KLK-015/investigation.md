# KLK-015 調査詳細

生成: investigator（代筆: orchestrator） / 最終更新: 2026-08-17
対象: `guard_bash_writes.py` の sed スクリプト引数の書き込み・実行経路の網羅（ホワイトリスト化）
要点はチケット `KLK-015` の「調査メモ」を参照。本ファイルは全文。

## Findings

- `SED_WRITE_RE`（`(?:^|[;{}\s/])[wW]\s+\S`）は `w`/`W` の直前文字が `;{}` 空白 `/` 以外（数字・`$`・`,`・`!`・`~` 等のアドレス構文）のとき不一致になる。アドレス前置きの `w` は全表記で **allow** に素通りする（実機GNU sed 4.9で書き込みを確認済み）。
- 上記の欠陥は**アドレス前置きに限らない**。`s` の区切り文字が `/` 以外（`#`・`,`・`|` 等）の場合も同じ理由で不一致になり、`s#a#XYZ#w FILE` が allow のまま実際に書き込む（実機確認済み・チケット本文には明記されていない追加発見）。
- GNU sedの `s///e`・`e` コマンド・`-f SCRIPT` は `segment_violation` のsed分岐に判定コードが一切無く、常時 allow（実機で `e`/`s///e` の任意コマンド実行、`-f` の書き込みを確認済み）。これは新規欠陥ではなく、KLK-010が `D6-3`/`D4` でスコープ外と判断し `INVENTORY_CASES` の `INV-SED-05〜07` に allow 登録済みの**既知の穴**。
- README・モジュールdocstring・設計書は「sedの `w`/`W` コマンドは遮断する」と**無条件に**記述しており、上記アドレス前置き・任意区切り文字の欠落を反映していない（overclaim）。一方、`-f`/`e`系は既にdocstring・設計書とも「未対応（別チケット）」と正しく記載済み。
- `tests/test_guard_bash_writes.py` の `INV-SED-01/02/04` および `test_sed_write_command_deny` は `s/a/b/w` `/x/W` 形のみを対象にしており、アドレス前置き形・任意区切り文字形の回帰テストは1件も存在しない。

## Evidence

### 調査対象コードの該当箇所

```python
# .claude/hooks/guard_bash_writes.py
SED_INPLACE_SHORT_RE = re.compile(r"-[A-Za-z]*i")     # -i / -i.bak / -ni / -si.bak
SED_WRITE_RE = re.compile(r"(?:^|[;{}\s/])[wW]\s+\S")  # s/a/b/w FILE ・ /re/w FILE
```

```python
# segment_violation() 内 sed 分岐（1636-1652行付近）
if head == "sed":
    flat = [t for variant in variants for t in variant]
    if any(SED_INPLACE_SHORT_RE.match(t) or t == "--in-place" or
           t.startswith("--in-place=") for t in flat):
        return "sed -i（in-place編集）は許可されていません"
    strict = cwd_is_guarded(cwd)
    if strict:
        flat = flat + [" ".join(words)]
    if any(SED_WRITE_RE.search(t) for t in flat
           if strict or is_guarded_token(t)):
        return "sed の w コマンド（ファイル書き出し）は許可されていません"
```
sedに対する判定はこれが全てであり、`s///e`・`e`コマンド・`-f`に対応する分岐はコード上に一切存在しない（意図的スコープ外・INV-SED-05〜07で可視化済み）。

### 再現手順Aの regex 単体検証（`python3 -c`、guarded pathを含まず実行）

```
'1w out.txt'        -> NO MATCH
'$w out.txt'        -> NO MATCH
'1,2w out.txt'      -> NO MATCH
'2!w out.txt'       -> NO MATCH
'0~2w out.txt'      -> NO MATCH
'1W out.txt'        -> NO MATCH
's/a/b/w out.txt'   -> MATCH   (対照: 正しく検出される代表形)
'/re/w out.txt'     -> MATCH   (対照)
'1 w out.txt'       -> MATCH   (対照: wの直前が空白)
```
追加発見（ticket未記載）:
```
's#a#b#w out.txt'   -> NO MATCH   (区切り文字が '#')
's,a,b,w out.txt'   -> NO MATCH   (区切り文字が ',')
's|a|b|w out.txt'   -> NO MATCH   (区切り文字が '|')
'3,/end/w out.txt'  -> MATCH      (アドレスの終端が'/re/'型なので直前が'/'になり一致)
```

### 実機GNU sed 4.9 検証（`/tmp/klk015_test` 配下、リポジトリ非改変）

`sed --version` → `sed (GNU sed) 4.9`

入力ファイル `in.txt` = `line1\nline2\nline3\n`

| コマンド形 | 実行結果 |
|---|---|
| `sed -n '1w out_1w.txt' in.txt` | rc=0、`out_1w.txt`に`line1`が書き込まれた |
| `sed -n '$w out_dollarw.txt' in.txt` | `out_dollarw.txt`に`line3` |
| `sed -n '1,2w out_12w.txt' in.txt` | `out_12w.txt`に`line1`,`line2` |
| `sed -n '2!w out_2bw.txt' in.txt` | `out_2bw.txt`に`line1`,`line3` |
| `sed -n '0~2w out_step.txt' in.txt` | `out_step.txt`に`line2` |
| `sed -n '1W out_1W.txt' in.txt` | `out_1W.txt`に`line1` |
| `sed -n -e '1w out_eflag.txt' in.txt` | `out_eflag.txt`に`line1` |
| `sed -n '1 w out_spacew.txt' in.txt`（対照） | `out_spacew.txt`に`line1`（wの直前に空白があるためSED_WRITE_REは正しく検出できる形。書き込み自体は他形と同じ） |
| `sed 's/.*/touch marker_eflag.txt/e' in.txt` | `marker_eflag.txt`が作成＝置換結果をコマンドとして実行（任意コマンド実行を確認） |
| `sed -n 'e touch marker_ecmd.txt' in.txt` | `marker_ecmd.txt`が作成＝`e`コマンドの任意コマンド実行を確認 |
| `sed -n -f script.sed in.txt`（script.sedの内容: `1w out_fscript.txt`） | `out_fscript.txt`に`line1`。外部スクリプトファイル経由の書き込みを確認 |
| `sed 's#a#XYZ#w out_hashdelim.txt' in.txt` | `out_hashdelim.txt`が作成された（区切り文字`#`のケースで実際に書き込みが発生することを確認。チケット本文未記載の追加発見） |

全てのallow側の形で実際の書き込み/コマンド実行が発生することを確認した（「allow側で書き込みが起きるか」の実機検証は完了）。deny側（既存の`s/a/b/w`・`-i`等）については既存テストスイートが実機非依存の正規表現マッチのみで判定しており、本調査では新たなdeny側の実機再検証は行っていない（既存テストが203メソッド全passであることのみ確認。deny側の実機再検証はチケットのAC「実機GNU sedとの二方向検証」の実装後フェーズでtester/architectが行うべき事項として申し送る）。

### 設計書・README・docstring のoverclaim箇所

- `.claude/hooks/README.md` 12行目: 「リダイレクト・sed -i（全表記）・sed の `w` コマンド…をベストエフォートで遮断する」— アドレス前置き・任意区切り文字形の除外を明記していない。
- `.claude/hooks/guard_bash_writes.py` モジュールdocstring 102行目: 「追加規則を持つ（sedの-i全表記とw／Wコマンド…）」— 同様に無条件表現。
- 一方、同docstring 278-283行目「既知の限界」節は`sed -f SCRIPT`・GNU sedの`e`フラグ・`e`コマンドを明示的に「未対応」と正しく記載済み（この部分はAC上の訂正対象ではない）。
- `docs/designs/KLK-010.md` 964行目（§3-9棚卸し表sed行）: 「`w`＝`SED_WRITE_RE`（cwd対応＝§3-8）」と記載し、`-f`・`e`のみ「未対応」と限定している＝アドレス前置き・任意区切り文字形の欠落は棚卸し表自体に一度も記載されたことがない（KLK-010の設計・レビューでも一度も検出されていない、真の新規発見）。

### INV-SED写像表の現状（`tests/test_guard_bash_writes.py` 300行〜、350-364行）

| INV ID | 構文 | 期待 | 備考 |
|---|---|---|---|
| INV-SED-01 | `s/a/b/w FILE` | deny | 区切り文字`/`のため現行regexで正しく検出 |
| INV-SED-02 | `/re/W FILE` | deny | 同上 |
| INV-SED-03 | `-i` 全表記 | deny | `SED_INPLACE_SHORT_RE`等で検出（本チケットと無関係） |
| INV-SED-04 | 保護対象cwd下の`w REL`（`s/a/b/w APP-001.md`形） | deny | strict分岐だが区切り文字`/`の代表形のみ。アドレス前置き形はテストされていない |
| INV-SED-05 | `-f SCRIPT` | allow（意図的・未対応） | D6-3・別チケット |
| INV-SED-06 | `s///e` | allow（意図的・未対応） | D6-3・別チケット |
| INV-SED-07 | `e`コマンド | allow（意図的・未対応） | D6-3・別チケット |
| INV-SED-08 | `-n '1,5p'` | allow（意図的・読み取り） | 回帰対象外 |

アドレス前置き形（`1w`/`$w`/`1,2w`/`2!w`/`0~2w`/`1W`）・任意区切り文字形（`s#..#w`等）は INV-SED-01〜08 のいずれにも該当せず、**棚卸し表自体に不在**。

### AW-7（awkプログラム本文ホワイトリスト）の3条件（`docs/designs/KLK-010.md` §3-6 D8、原則P4-3）

1. 許可文字集合（リテラル除去後）を満たすこと（`@`・`|`を含まない）
2. 呼び出し名の許可集合（`system`を除く。未知名はdeny）を満たすこと
3. `print`/`printf`直後の`>`/`>>`/`|`（出力構文）が無いこと

sedへ同型適用する場合の設計上の論点（KLK-010 P7/P8/P9に基づく検討事項。設計判断はarchitectの責務であり本調査では提案しない）:

1. **区切り文字の任意性**: sedの`s`/`y`コマンドは区切り文字を`/`以外の任意の1文字（`#`,`,`,`|`等、`\`と改行を除く）に選べる。AW-7は`"..."`・`/.../`という固定デリミタ前提で「文字列・正規表現リテラルの除去」を1パスで行っているが、sedでは「今読んでいる`s`コマンドの区切り文字は何か」を都度特定してから対応する終端を探す必要があり、字句解析の複雑度がむしろawkより高くなる可能性がある。
2. **アドレス構文の列挙**: 行番号・`$`・`/regex/`・`\cregexc`（regexのカスタム区切り）・範囲（`N,M`）・GNU拡張の`N~M`ステップ・`0,/regexp/`特殊範囲・`!`否定・複数アドレスの組み合わせを網羅的に列挙する必要がある（P7: 分岐条件の明示列挙）。
3. **GNU拡張と移植性**: `0~N`・`s///e`・`e`コマンドはGNU sed固有。ホワイトリスト化にあたり「GNU sed基準で設計し、他実装は判定不能→deny」とするか、複数実装を意識するかの方針決定が必要（AWKでのmawk/BWK対応の前例と同型の判断）。
4. **`{}`グルーピング・`;`区切り・複数`-e`/`-f`の合成**: 複数コマンドが`{}`でネストされたり`;`・改行で連結される構文をどう安全側で分解するか。
5. **`r`/`R`（外部ファイル読み込み）コマンド**: 書き込みではないが情報開示（読み取り）の経路になりうる。本hookの脅威モデル（書き込み・実行のゲート）の範囲外か、architectが要検討。
6. **s///eとeコマンドの扱い**: ホワイトリスト化すれば許可文字集合・呼び出し構文に`e`関連構文が含まれないため自動的にdeny側へ落ちる（AW-7の`system`非収載と同型の防御効果）。この設計にすれば、チケットの再現手順A・Bの両方を1つの構造で閉じられる可能性が高い（申し送り2の「第一候補」の技術的な裏付け）。

### 参考: 既存のsed関連の誤deny方向の既知事項（本チケットとは別方向）

`guard_bash_writes.py` 231-233行目に、保護対象cwd下で`sed`スクリプトに` w <非空白>`という部分文字列が現れる形（例: `sed 's/a w b/c/'`）が誤ってdenyになる既知の限界が既に記載されている。これは本チケットの「見落とし（false negative）」とは逆方向（false positive）の既存事象であり、修正時に混同しないよう留意が必要（設計書1870行目にも記載あり）。

## Dependency Graph

- `guard_bash_writes.py` の `main` → `find_violation` → `statement_violation` → `pipe_segments`/`segment_violation`（sed分岐）→ `SED_WRITE_RE`/`SED_INPLACE_SHORT_RE` の順で評価される。
- `segment_violation` の sed分岐は `cwd_is_guarded`（`strict`）と `is_guarded_token` にゲートされ、どちらも「対象テキストを regex に渡すか」の判定のみで、regex自体の網羅性には無関係（ゲートを通っても regex が不一致なら allow）。
- `INVENTORY_CASES`/`LEGACY_DENY_COMMANDS` は `tests/test_guard_bash_writes.py` 側に定義（`guard_bash_writes.py` 本体には無い）。回帰追加はテストファイル側の作業になる。
- `docs/designs/KLK-010.md` §3-9/§3-11 が「棚卸し表→実装→テスト」の対応関係の正であり（原則P5）、sed行を変更する場合はこの表・写像・`README.md`・docstringの4箇所を同時更新する必要がある（P9: 否定形・向き・検出器の3点併記が必須）。
- awkのAW-7（`AWK_SAFE_PROGRAM_CHARS`/`AWK_SAFE_CALLS`/`awk_strip_literals`等）が「プログラム形ホワイトリスト」の先行実装であり、sedへ同型適用する場合の直接の参照先になる（§3-6 D8）。

## Risk Areas

- **regex欠陥はチケット記載の8形に留まらない**: 任意区切り文字（`s#..#w`・`s,..,w`・`s|..|w`等）も同一理由で不一致になることを実機確認済み。修正時は「アドレス前置き」だけでなく「区切り文字がwhitelist外」の次元も同時に塞がないと同型の穴が残る（KLK-010のawk字句次元で4ラウンド繰り返された失敗と同型のリスク）。
- sedは区切り文字を`s`/`y`コマンドごとに任意選択できるため、リテラル（正規表現・置換文字列）の開始・終端条件をP7/P8/P9流に厳密化しようとすると、awkの固定デリミタ（`"..."`・`/.../`）より**構文解析の複雑度がむしろ高くなりうる**（「sedはawkより言語が小さいのでコストが低い」という申し送りの前提を部分的に覆す可能性がある論点）。
- ホワイトリスト化する場合、GNU拡張（`0~N`ステップアドレス・`0,/re/`特殊レンジ・`s///e`・`e`コマンド）とPOSIX/BSD sedの構文差をどう扱うか（awkがGNU Awk基準・mawk/BWK未知フラグをdeny落ちとしたのと同型の判断が必要）。
- `sed`を`ALLOWED_HEADS`から外す/残すという上位判断が未決のまま実装を進めると、AC・テスト・ドキュメントの手戻りリスクが高い（下記Unknowns参照）。

## Assumptions

- 実行環境はGNU sed（本調査ではv4.9で検証）を前提とする。BSD/mawk相当の他sed実装での挙動差は未検証（一般知識としてBSD sedは`0~N`・`s///e`・`e`コマンドを持たないことは知られているが、実機未検証）。
- チケット記載の「437件」（KLK-010完了時点）は`unittest`のトップレベルテストメソッド数ではなく、`subTest`（`INVENTORY_CASES`等）を個別カウントした数と推測する（現状`unittest`実行では203メソッド・全pass）。未確認のため推測と明記。
- README/docstringの「w／Wコマンドを遮断する」という記述は、執筆時点で`s/a/b/w`等の代表形のみを検証対象にしていたための overclaim と推測する（当時アドレス前置き形・任意区切り文字形は棚卸し対象になっていなかった、という技術的経緯の推測）。

## Unknowns

- **`sed`を`ALLOWED_HEADS`に残すかどうかという上位判断（チケット本文・KLK-010設計書§10-1申し送り2で明記された人間承認事項）は本調査では解決不能。** これはAC改訂を伴いうるOpen Questionであり、architectが設計着手前に人間へ確認する必要がある。選択肢は少なくとも (a) AW-7型のプログラム本文ホワイトリストをsedへ新設し`ALLOWED_HEADS`に残す (b) regexの拡張のみで既存のブラックリスト方式を維持し`ALLOWED_HEADS`に残す (c) 保護対象言及／保護対象cwd下に限り`sed`をhead単位でdenyする、の3系統があるが、どれを選ぶかは人間判断が必要。
- 「437件」という数値の正確な算出方法（subTest込みか否か）は本調査で確定できず、テスト件数の申告根拠として使う場合は要確認（verification_hint: `pytest --collect-only`相当でsubTest展開後の総数を数える、またはKLK-010完了コミットのtester報告を参照する）。
- BSD sed等、GNU以外のsed実装がこのKit運用環境で使われる可能性の有無は未確認（verification_hint: 運用環境のOS/シェル設定を人間に確認する。macOS等ではデフォルトsedがBSD系のため、ホワイトリスト設計のGNU依存度に影響しうる）。

## 参照した実ファイル

- `.claude/hooks/guard_bash_writes.py`（`SED_WRITE_RE`・`SED_INPLACE_SHORT_RE`・`segment_violation`・`ALLOWED_HEADS`）
- `tests/test_guard_bash_writes.py`（`INVENTORY_CASES`・`LEGACY_DENY_COMMANDS`・`test_sed_write_command_deny`・`test_inventory_cases_match_expected_decisions`）
- `.claude/hooks/README.md`（sed関連の記述）
- `docs/designs/KLK-010.md`（§3-1 P7/P8/P9、§3-6 D4/D6-2/D6-3/D8、§3-9 sed行、§3-11 INV-SED-01〜08、§6 R12/R25、§10-1 申し送り2）
- `tickets/active/KLK-015_sedスクリプト引数の書き込み実行経路の網羅.md`
- 実機検証: GNU sed 4.9（`/tmp/klk015_test` 配下、リポジトリ非改変）
