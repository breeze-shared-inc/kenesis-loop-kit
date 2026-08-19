# KLK-034 実装レポート（implementer）

対象チケット: KLK-034（否定文字クラス `[^...]` とPOSIX文字クラス `[[:class:]]` が
pathish分断で検出されずSPEC.md操作が誤allowされる）
設計書: `docs/designs/KLK-034.md`（全10節。実装の正）
作業ブランチ: `fix/KLK-034-caret-negated-class-posix-class`（develop `6f7fdb2` から派生）
worktree: `../kenesis-loop-kit.wt/KLK-034`

## 1. コミット構成（3 Phase + 本レポート + 差し戻し対応の Phase 4）

**注記（2026-08-19）:** reviewer 差し戻しへの対応は §8「Phase 4」に記載する。
§2 の「再帰なし・語長に線形」という走査コストの評価は**誤り**であり、§8 が正である。

| コミット | Phase | 内容 | 変更行数 |
|---|---|---|---|
| `e6af191` | 1 | `guard_bash_writes.py`（文字集合拡張＋正規化関数2つ＋配線＋docstring3箇所）・`_ticket_lib.py`（docstringのみ） | +205 / -9（2ファイル） |
| `f1fd0e5` | 2 | `tests/test_guard_bash_writes.py` KLK-034節 19メソッド（純追加） | +216 / -0 |
| `a260475` | 3 | `docs/designs/KLK-033.md` §5表1セル・§7の1文・§8のrevertコマンドと注意点（docsのみ） | +27 / -6 |
| （本ファイル） | - | 実装レポートの外部化 | - |
| `248c782` | 4(i) | **差し戻し対応（コード）**: `guard_bash_writes.py` の走査範囲上限＋`MAX_BRACKET_SCAN_WORK` の事前チェック（deny方向フォールバック）＋docstring 4箇所 | +110 / -6（実行行は5行） |
| `f2dd344` | 4(ii) | **差し戻し対応（テスト）**: `tests/test_guard_bash_writes.py` に9メソッド追加（上限境界4件・コスト回帰2件・`/` メンバー1件・既知の限界1件・意味論乖離1件）＋`fnmatch`／`time` の import | +130 / -1 |
| `fad60dd` | 4(iii) | **差し戻し対応（設計書）**: `docs/designs/KLK-034.md` §3 D2(b)(d)・§3 D3表2行・§4-2・§4-7・§5・§6・§8・§9⑦の訂正・追記（docsのみ） | +150 / -26 |

Phase 1は設計書§3 代替案(I)のとおり文字集合拡張（§4-1）と正規化（§4-2・§4-3）を
**単一コミット**にまとめている（片方だけが入った中間状態を作らないため）。
Phase 3は設計書§8のロールバック対象から除外するため独立コミットにしている。

## 2. 実装内容（設計書との対応）

- §4-1: `SHELL_EXPAND_PATHISH_RE` を `r"[A-Za-z0-9_.\-/{},*?\[\]!^:]+"` へ。
  追加は既存集合の末尾（`!` の直後）で、Python `re` のクラス内で `^` が否定に
  ならない位置。KLK-034コメントブロックを定数行の直前へ追加（KLK-033コメントは残置）。
- §4-2: `BRACKET_CLASS_LEADERS = ":.="`・`_scan_bracket_expression`・
  `_bash_bracket_to_fnmatch` を `_guarded_paths_from_expanded` の直前へ新設。
  設計書のコード断片・docstring文面をそのまま採用（再帰なし・語長に線形）。
- §4-3: `match_component = _bash_bracket_to_fnmatch(component)` を
  `has_literal_char` ゲート通過後に1回だけ計算し、`lib.is_spec_basename_fnmatch` と
  `fnmatch.fnmatchcase` の**照合2箇所のみ**へ渡す。`rebuilt` の再構成は
  正規化前の `components` のまま。
- §4-4: docstring 4箇所（`_guarded_paths_from_expanded` ②の重複・不正確の統合／
  `guarded_paths_after_shell_expansion` へ「KLK-034 による精緻化」ブロック追加／
  モジュール「既知の限界」のKLK-033箇条書きの限定＋KLK-034箇条書き新設／
  `_ticket_lib.is_spec_basename_fnmatch` へ呼び出し側契約1段落）。
- §4-5: Phase 3で `docs/designs/KLK-033.md` の3箇所を設計書の文面案どおりに適用。

設計書からの逸脱・追加判断は**なし**（コード断片・docstring文面・テスト観点は
設計書§4・§9の記載どおり。机上トレース12形も実測で全件一致）。

## 3. Phase 1 完了条件(b): 不変対象のバイト単位無変更の確認

`git diff`（Phase 1コミット時点）の `+`／`-` 行に下記の文字列が**1件も現れない**ことを
機械的に確認した（スクラッチのスクリプトで `git diff -- <path>` を解析。判定: PASS）。

| 不変対象 | 結果 |
|---|---|
| `GLOB_META_CHARS = frozenset("*?[")` | 未変更 |
| `PATHISH_RE = re.compile(r"[A-Za-z0-9_.\-/]+")` | 未変更 |
| `has_literal_char = any(ch not in GLOB_META_CHARS for ch in component)` | 未変更 |
| `if index == last_index and has_literal_char:` | 未変更 |
| `literals = literals + [GUARDED_FILENAME]` | 未変更 |
| `if not any(ch in component for ch in GLOB_META_CHARS):`（事前フィルタ） | 未変更 |
| `rebuilt = "/".join(` ／ `literal if i == index else c` ／ `rebuilt_path = os.path.normpath(rebuilt)` | 未変更 |
| `return (fnmatch.fnmatchcase("SPEC.md", pattern)` ／ `or fnmatch.fnmatchcase("SPEC.MD", pattern.upper()))` | 未変更 |

`_ticket_lib.py` の差分は **+6行のみ**（すべて `is_spec_basename_fnmatch` docstring
本文の追記。コード行・シグネチャ・判定式に差分なし）。

## 4. Phase 1 完了条件(c): 差分挙動の実測（develop形 → KLK-034形）

方法: `SHELL_EXPAND_PATHISH_RE` を develop形 `r"[A-Za-z0-9_.\-/{},*?\[\]!]+"` へ、
`_guarded_paths_from_expanded` を develop HEAD（`6853236`）の複製（照合2箇所へ
`component` を渡す形。他は同一）へ**実行時のみ**差し替え、`find_violation` の
None（allow）／非None（DENY）を新旧対照した。リポジトリのコードは変更していない。
スクリプトはスクラッチ領域に置き、コミットしていない（設計書§4-6の運用）。

### 4-1. DENY → allow の転換形（**6件**。非単調性の実測）

| コマンド | develop | KLK-034 | allowが正しい根拠 |
|---|---|---|---|
| `rm docs/SP*.md:1` | DENY | allow | bashは `docs/SPEC.md` に一致させない（末尾 `:1` が余分）。旧denyは誤deny |
| `rm docs/SP*.md^y` | DENY | allow | 同上（末尾 `^y`） |
| `rm docs/:SP*.md` | DENY | allow | basenameが `:SP*.md` であり `SPEC.md` に一致しない |
| `rm docs/^SP*.md` | DENY | allow | 同上（`^SP*.md`） |
| `rm tickets/acti*e:x/APP-001.md` | DENY | allow | 成分 `acti*e:x` は `active` に一致しない |
| `rm tickets/acti*e^x/APP-001.md` | DENY | allow | 成分 `acti*e^x` は `active` に一致しない |

原因はいずれも候補結合の変化（従来は `^`／`:` で分断され `docs/SP*.md`・`acti*e` が
独立候補になっていたものが1候補へ吸収され、glob構造条件を満たさなくなる）。
設計書§5・§7(2)の予測（6形）と**完全に一致**した。代表2形
（`rm docs/SP*.md:1`＝SPEC.md側・`rm tickets/acti*e^x/APP-001.md`＝active/done側）を
`test_klk034_fragmentation_rule_change_allow` に根拠コメント付きで固定した。

### 4-2. allow → DENY（新規deny。意図した是正。**12件**）

`rm docs/[^x]PEC.md`・`rm docs/[^s]PEC.md`・`rm docs/S[^x]EC.md`・
`rm docs/[[:upper:]]PEC.md`・`rm docs/[[:alpha:]]PEC.md`・`rm docs/[[.S.]]PEC.md`・
`rm tickets/[^x]ctive/APP-001.md`・`rm tickets/[[:lower:]]ctive/APP-001.md`・
`rm docs/[:S]PEC.md`・`rm tickets/[:a]ctive/APP-001.md`・
`rm docs/[^x]PEC.md # don't`（degraded）・`rm docs/[[:upper:]]PEC.md # don't`（degraded）

### 4-3. 不変（allow→allow／DENY→DENY）を確認した形

- リテラル形（DENY不変）: `rm docs/SPEC.md:1`・`rm docs/SPEC.md^y`・
  `rm tickets/active/APP-001.md:1` → `PATHISH_RE` 版 `is_guarded_token` とのORで
  保たれる（設計書§7(4)。`test_klk034_literal_path_with_caret_colon_still_deny`）
- 既存deny形（DENY不変）: `rm docs/SP*.md`・`rm docs/sp*.md`・
  `rm tickets/acti*e/APP-001.md`・`rm docs/[!x]PEC.md`・`rm docs/[!s]PEC.md`・
  `rm tickets/[!x]ctive/APP-001.md`・`rm docs/[A-Z]PEC.md`
- 誤deny予算（allow不変）: 非glob5例（`grep '^foo' file.txt`・`sed 's/^x/y/' file.txt`・
  `awk -F: '{print $1}' file.txt`・`PATH=a:b; date`・`git log --format=%h:%s`）／
  POSIXクラスイディオム4例（`tr -d '[:space:]' < file.txt`・
  `grep -o '[[:alpha:]]' file.txt`・`sed 's/[[:blank:]]\+/ /g' file.txt`・
  `cut -d: -f1 file.txt`）／ブレース2形（`rm a{1,2}^b{3,4}.txt`・
  `rm a{1,2}:b{3,4}.txt`）／既存の `^`／`:` 含み2形
  （`pwd && cut -d: -f2 tickets/active/APP-001.md`・
  `sed -n '/[^/]/p' tickets/active/APP-001.md`）
- 読み取りhead対称性（allow不変）: `cat docs/[^x]PEC.md`・
  `cat docs/[[:upper:]]PEC.md`・`cat docs/[^x]PEC.md # don't`（degraded）
- bash非一致形（allow不変）: `rm docs/[^S]PEC.md`・`rm tickets/[^d]one/APP-001.md`・
  `rm docs/[a[^]one`

### 4-4. 設計書§3 D4の未実測項目（Unknown）の実測確定

未閉塞ブラケット `rm docs/[^x`・`rm docs/[^xPEC.md` は **develop・KLK-034ともにallow**
（設計の予測どおり。denyへ転じていない）。`test_klk034_unclosed_bracket_allow` に
実測値として固定した。degraded読み取り `cat docs/[^x]PEC.md # don't` も**allow**
（KLK-033の同型ケースと対称。`test_klk034_degraded_spec_side_read_allow`）。

### 4-5. 単体レベルの実測値（テストの期待値の出所）

- `findall("docs/[^x]PEC.md")` → `['docs/[^x]PEC.md']`（修正前 `['docs/[', 'x]PEC.md']`）
- `findall("docs/[[:upper:]]PEC.md")` → `['docs/[[:upper:]]PEC.md']`
  （修正前 `['docs/[[', 'upper', ']]PEC.md']`）
- `_guarded_paths_from_expanded`: `docs/[^x]PEC.md`・`docs/[^s]PEC.md`・
  `docs/[[:upper:]]PEC.md`・`docs/[[:alpha:]]PEC.md`・`docs/[:S]PEC.md`・
  `docs/S[^x]EC.md`・`docs/[[.S.]]PEC.md` → `['docs/SPEC.md']` ／
  `tickets/[^x]ctive/APP-001.md`・`tickets/[:a]ctive/APP-001.md`・
  `tickets/[[:lower:]]ctive/APP-001.md` → `['tickets/active/APP-001.md']` ／
  `docs/[^S]PEC.md`・`docs/[a[^]one`・`docs/[[:upper:]]`・`*`・
  `tickets/[^d]one/APP-001.md` → `[]`
- `_bash_bracket_to_fnmatch`: 設計書§4-2の机上トレース12形が**全件一致**
  （`[a[^]one` が非変換であること＝意味反転が起きないことを含む）

## 5. テスト

- baseline（develop `6f7fdb2`）: **818件 OK**
- Phase 1完了時点: **818件 OK**（回帰0。既存テストの変更なし）
- Phase 2完了時点: **837件 OK**（新規19件。`tests/test_ticket_lib.py` は無変更で
  既存6件PASS、KLK-018/031/032/033系も無変更でPASS）

新規19メソッド（設計書§9のテスト観点6群に対応）:

| 群 | メソッド |
|---|---|
| ① 正規化ヘルパー単体 | `test_klk034_bracket_normalizer_unit`（12形。`[a[^]one` の意味反転検出器） |
| ② 候補抽出・展開単体 | `test_klk034_pathish_and_expanded_unit` |
| ③ end-to-end deny | `test_klk034_caret_negated_class_glob_deny`／`test_klk034_posix_class_glob_deny`／`test_klk034_guarded_dir_side_deny`／`test_klk034_colon_member_class_deny`／`test_klk034_range_class_unchanged_deny` |
| ④ allow精度・読み取り対称性 | `test_klk034_spec_side_read_allow`／`test_klk034_bash_excluded_forms_allow`／`test_klk034_bracket_literal_member_allow`／`test_klk034_unclosed_bracket_allow`／`test_klk034_posix_class_idiom_allow` |
| ⑤ degraded | `test_klk034_degraded_caret_class_deny`／`test_klk034_degraded_posix_class_deny`／`test_klk034_degraded_spec_side_read_allow` |
| ⑥ 誤deny予算・分断規則検出器 | `test_klk034_caret_colon_non_glob_words_unchanged_allow`／`test_klk034_literal_path_with_caret_colon_still_deny`／`test_klk034_fragmentation_rule_change_allow`／`test_klk034_brace_cost_with_caret_colon_allow` |

## 6. 受け入れ条件の充足状況（implementer視点。最終判定はtester/reviewer）

| AC | 状況 |
|---|---|
| AC1 | 充足（§9③⑤のdeny 12形と④の読み取り対称性をend-to-endで固定。上記4-2） |
| AC2 | 充足（正規化を実装し机上トレース12形＋end-to-end対照で固定。`[a[^]one` 非変換を単体で固定） |
| AC3 | 充足（POSIXクラスを `?` へ過大近似して閉塞。閉塞範囲の対応表をモジュールdocstringへ転記。`[:space:]` 型・`tr -d` 型の非巻き込みを固定） |
| AC4 | 充足（837件OK・回帰0。既存テストは1行も変更していない） |
| AC5 | 充足（非globコマンド9例のallow不変を固定。DENY→allow転換形6件を洗い出し代表2形を固定） |
| AC6 | 充足（Phase 3で §5表・§7を訂正） |
| AC7 | 充足（Phase 3で §8のrevert対象へ testerコミット `0d0571f` を追記し、含めない場合の失敗理由を注意点として明記） |
| AC8 | 充足（モジュールdocstring「既知の限界」にKLK-034欄と対応済み／未対応の一覧、KLK-033欄の限定を追記。docstring②の重複・不正確を1段落へ統合。`guarded_paths_after_shell_expansion` へKLK-034ブロック追加） |

## 7. 残存リスク・申し送り（tester/reviewer向け）

1. **DENY→allow の6形は実測どおり是正方向だが不変条件ではない。** 将来 文字集合を
   さらに広げる変更を行う場合は、同じ新旧対照を再実施すること（`PATHISH_RE` を
   無変更に保つことが非単調性をglob成分に限定する唯一の仕組み。設計書§7(4)）。
2. **既知の限界（未対応の誤allow）:** ブラケット式のメンバーに候補抽出の文字集合外の
   文字を含む形（`docs/[+S]PEC.md`・`[@S]`・`[%S]`・`[~S]`・`[#S]`・空白・引用符・
   `$`・`(`・`)`・`|`・`&`・`;`）と extglob・globstar・`{1..3}`。モジュール
   docstringへ明記済み。閉塞には文字集合の無制限拡張が必要で誤deny予算の再評価を
   伴うため、必要になった時点で別チケット（設計書§10）。
3. **POSIXクラスの過大近似による誤deny面:** `rm docs/[[:digit:]]PEC.md` のように
   bashが一致させない形もdenyになる（向きは安全側）。日常イディオム4例のallowは
   固定済みだが、`?` へ落とす方式ゆえ長さ一致だけで一致する形は増える。
4. **検証時の自己遮断（運用注意）:** 本修正後は `[^`・`[[:` を含む文字列をBashコマンドの
   生テキストに書くと本hook自身が当該Bash呼び出しをdenyしうる。動作確認は
   テストファイルまたはスクラッチのPythonスクリプト経由で行い、heredocは使わず、
   コミットメッセージにも当該文字列を含めない（設計書§4-6）。
5. **実bashでの `rm` 実行検証は行っていない**（破壊的操作。設計書§4-6の判断に従い、
   bash側の真値は investigation.md／KLK-033 reviewer の非破壊実測を根拠とする）。

## 8. Phase 4: reviewer 差し戻し対応（2026-08-19）

差し戻し理由（`docs/reports/KLK-034/review.md` §1）: 新設した `_bash_bracket_to_fnmatch`
の走査コストが**超線形かつ無上限**で、`[` を大量に含む単一トークンで hook 単体の所要時間が
PreToolUse の既定タイムアウト（60s）を超え、README の fail-open 方針と重なって**人間承認
ゲートをすり抜ける**新しい経路になっていた（本チケットが閉じた欠陥と同じ結果）。
上記 §2 の「再帰なし・語長に線形」という記述は**誤り**であり、本節が正である。
D1〜D5 の設計判断（文字集合の選択・正規化の粒度・POSIXクラスの閉塞方式）は変更していない。

### 8-1. 修正内容（実行行は5行）

| # | 変更 | 判定への影響 |
|---|---|---|
| ① | `_scan_bracket_expression` 冒頭で `last_close = pattern.rfind("]")` を求め、`last_close <= open_index` なら即 `None` | **なし**（`]` が無ければブラケット式は閉じ得ない＝走査は必ず失敗する） |
| ② | `while i < n` → `while i <= last_close`、`find(leader + "]", i + 2)` → `find(leader + "]", i + 2, last_close + 1)` | **なし**（クラス要素の終端 `:]`／`.]`／`=]` も `]` を含むため最後の `]` より後ろでは成功し得ない） |
| ③ | `MAX_BRACKET_SCAN_WORK = 20000` を追加し、`guarded_paths_after_shell_expansion` の候補ループに `candidate.count("[") * len(candidate) > MAX_BRACKET_SCAN_WORK` の事前チェックを置き、超過時は `found.append(candidate)`（KLK-018 と同じ **deny 方向**のフォールバック）へ合流 | 上限超過時のみ allow→deny（安全側）。正規化スキップ＝allow 方向のフォールバックは採らない |
| ④ | docstring 4箇所（モジュール §KLK-034 欄・`_scan_bracket_expression`・`_bash_bracket_to_fnmatch`・`guarded_paths_after_shell_expansion`）へ機序・実測値・上限の根拠・「本関数自体は上限を持たないので新しい呼び出し元は同じ事前チェックを通すこと」を追記。あわせて review.md §3-2 の指摘（「対応済み」はメンバーが候補抽出の文字集合内の場合に限る／`[^+]`・`[^=]`・`[[=S=]]` は誤allowが残る）を明記 | なし（記述のみ） |

①②のみでは reviewer 指摘どおり `"["×n` 等の O(n²) が残る（後述 8-2 の実測）。③が本質的な
有界化であり、①②は「`]` を含まない語を定数時間で棄却する」ことでその大半を前段で削る。

### 8-2. 実測値（すべて本worktreeで implementer が実測。単位は秒）

**(1) `_bash_bracket_to_fnmatch` 単体（reviewer の Critical 入力を再現）**

| 入力 | 長さ | develop（関数なし） | 修正前（`e17c55d`） | 修正後（`248c782`） |
|---|---|---|---|---|
| `"[:"` 反復 | 4,000 | – | 0.957 | 0.0004 |
| 同 | 8,000 | – | 5.937 | 0.0008 |
| 同 | 16,000 | – | **38.63** | **0.0020**（約1.9万倍） |
| 同 | 24,000 | – | （reviewer実測 90s超） | 0.0035 |
| `"["` 反復 | 16,000 | – | 11.22 | 0.0031 |
| `"[[::]"` 反復 | 40,000 | – | 8.55 | 8.48（**関数単体では未有界**。end-to-end では③が前段で棄却するため到達しない。docstringに明記） |

**(2) end-to-end `find_violation`**

| コマンド | develop（旧） | 修正前 | 修正後 |
|---|---|---|---|
| `rm <"[:"×8000>`（16,003字） | 0.023 | 約38（reviewer 36.97） | **0.008** |
| `rm <"[:"×12000> docs/SPEC.md`（24,016字） | 0.033 | **118.7（reviewer実測）** | **0.012**（判定は DENY を維持） |
| `rm <"[[::]"×12000>`（60,003字） | 0.072 | （8s超） | 0.045 |
| ブレース512×ブラケット（pad 16,000字） | 0.009 | 13.00 | 0.008 |

**(3) しきい値 20000 の決定根拠（reviewer 指定の判定基準(a)(b)）**

- **(a) 現実のコマンドが上限に達しない:** 現実形18種の候補ごとの積を実測。最大は
  `awk '{x[0]x[1]…x[29]}'` 型の1語で **4,260**、文字クラス12連結の正規表現で 2,880、
  `sed 's/[[:blank:]]\+/ /g'`＝26、`grep -o '[[:alpha:]]'`＝22、`tr -d '[:space:]'`＝9、
  `cut -d: -f1`／長い `PATH=a:b:…`／`rm build/*`／`docker run -v .:/app`＝0。
  既存849件のテストが用いる語の最大積は 440。→ **上限に対する余裕は約4.7倍**。
  上限に達するには「1語400字に80個の文字クラス」規模（`[a-z][0-9]` を40回連結＝積32,000）の
  機械生成パターンが必要で、この場合の向きは deny＝安全側（人間承認へ回る）。
- **(b) 上限到達時の所要時間がタイムアウトに対して十分小さい:** 上限直下の最悪形
  （`{x,y}`×9〔直積512〕＋閉じない `[` を C 個＋pad＋末尾のPOSIXクラス終端で最後の `]` を
  消費させ、C 回の走査がすべて末尾まで歩いて失敗する形）で **1.33s**（60s に対し約45倍の
  余裕）。上限超過形は事前チェックで即フォールバックし 0.02s 未満。
  参考: 上限を 50,000／100,000 へ緩めると同形が 3.64s／7.34s。20,000 は「現実形の4.7倍の
  余裕」と「最悪1.3s」の折り合い点。
- 上限超過時のフォールバック方向の実測: `rm <超過語>`＝DENY／`cat <超過語>`＝allow／
  `echo x > <超過語>`＝DENY／`rm <超過語> tickets/active/APP-001.md`＝DENY。

**(4) 語数に比例した増幅（残存・KLK-018 由来の既存性質）**

| 形 | develop（旧） | 修正後 |
|---|---|---|
| `{x,y}`×9＋`*`＋2,000字 の語を50個（102,442字） | **37.35** | 45.98 |
| 上限直下の重い語（ブラケット）を50個（166,392字） | （その形はdevelopでは1語にならない） | 55.32 |
| 1バイトあたり | 0.36ms | 0.33ms |

→ コマンド長に比例する増幅は **KLK-018 のブレース展開×fnmatch 経路が持つ既存の性質**で
あり、1バイトあたりのコストは develop と同等以下。KLK-034 が導入した「単一語で超線形かつ
無上限」という新しい次元は閉じた。コマンド全体の走査予算は別チケットの範囲（8-4 の1）。

### 8-3. テスト（Phase 4(ii)。9メソッド追加）

- 差し戻し時点の baseline **840件 OK** → 追加後 **849件 OK**（回帰0）。既存テストは
  1行も変更・削除していない（`git diff` の tests 側削除行は import 1行の差し替えのみ）。
- 机上トレース12形（`test_klk034_bracket_normalizer_unit`）と tester 追加の境界7形
  （`test_klk034_bracket_normalizer_boundary_unit`）が**無変更でPASS**＝①②が判定を
  変えていないことの機械的裏付け。
- 追加分（設計書§9⑦）: `..._scan_work_within_limit_precision`（上限直下で精度維持。
  20×999＝19,980）／`..._scan_work_exceeded_denies_conservatively`（21×1,000＝21,000 で
  deny。上と1文字違い）／`..._scan_work_exceeded_allow_symmetry`（`cat` は allow）／
  `..._scan_work_exceeded_does_not_mask_existing_deny`（病的語を先頭に置いても deny）／
  `..._bracket_scan_cost_regression_unit`（16,000字・24,000字で5.0s上限）／
  `..._bracket_scan_cost_regression_end_to_end`（reviewer の 118.7s シナリオを15.0s上限で
  固定）／`..._bracket_with_slash_member_allow`（`/` メンバー3形。bashも非一致）／
  `..._negated_class_outside_charset_known_limitation_allow`（`[[=S=]]`・`[^=]`・`[^+]`）／
  `..._bracket_semantics_divergence_unit`（`[^[:]` → `[![:]` と `[` 不一致）。
- 検出器性としての確認: 修正前コード（`HEAD~1` の複製）に対して `rm <超過語>` と
  `echo x > <超過語>` が **allow** であること、単体16,000字が **38.4s**（しきい値5.0s超）で
  あることを実測し、追加テストが修正前なら失敗することを確認した。
- bash 真値の再確認（非破壊。`mktemp -d` 配下に空の `docs/SPEC.md`・
  `tickets/active/APP-001.md` を作り `echo` の展開のみ観測。`rm` は実行していない）:
  `docs/[^/]PEC.md`・`docs/[/S]PEC.md`・`tickets/[^/]ctive/APP-001.md` は**非一致**
  （語がリテラルのまま出力）→ allow が正しい。`docs/[[=S=]]PEC.md`・`docs/[^=]PEC.md`・
  `docs/[^+]PEC.md` は `docs/SPEC.md` に**一致**→ hook の allow は既知の限界。
  `[^[:]`・`[![:]` はいずれも `[` に一致 → 正規化後の fnmatch は不一致（Python 側が狭い）。

### 8-4. Phase 4 後の残存リスク（上記 §7 に追加）

1. **コマンド長に比例した増幅は残る（KLK-018 由来。本チケットでは悪化させていない）。**
   上限は候補（語）単位でありコマンド全体の予算ではないため、重い語を多数並べた
   十数万字のコマンドでは数十秒に達しうる（8-2(4)。develop も同規模）。閉じるには
   ブレース展開経路と合わせた「コマンド全体の走査予算」の導入が必要で、KLK-018 の
   フォールバック設計に触るため別チケットの範囲と判断した。
2. **`_bash_bracket_to_fnmatch` 自体は無上限**（8-2(1) の `"[[::]"` 反復）。有界性は
   呼び出し元の事前チェックに依存する。docstring に「新しい呼び出し元を追加する場合は
   同じ事前チェックを通すこと」を明記したが、機械的な強制はない。
3. **上限超過時のフォールバックは粗い**（候補全体を保護対象パスの候補とみなす）。
   `[` 出現数×語長が2万を超える語を含むコマンドは、保護対象と無関係でも非ホワイト
   リスト head なら deny になる（KLK-018 の既存フォールバックと同じ性質・同じ向き）。
4. **時間しきい値を持つテストが2件ある**（5.0s／15.0s）。実測値の1,000倍以上の余裕を
   取っているが、極端に負荷の高い環境では理論上ゆらぎうる。ゆらいだ場合は
   しきい値を上げるのではなく、まず走査コストの回帰を疑うこと（そのための検出器）。
5. **意味論乖離2形（review.md §3-1）は閉じていない — 意図的な判断。** reviewer は
   「根因はCriticalと同じ `find` の無制限探索であり 1-5 の修正時に併せて閉じられる」と
   予想していたが、本対応では探索範囲の上限を**「pattern 中の最後の `]`」という判定を
   一切変えない上界**に取った（8-1 ①②）。より狭い上界（例: クラス名の最大長で打ち切る）
   にすれば `[^[:]` の `[:` をクラス開始として消費しなくなり乖離は閉じるが、それは
   「クラス要素の終端探索の意味論」自体を変える変更であり、机上トレース12形・境界7形の
   期待値と D2(b) の走査規則に対する新しい未検証の前提を持ち込む。乖離の向きは
   allow 方向だが失う文字は `[` のみで保護対象名に含まれない（reviewer が 19,607
   ガジェット・84,204組で「保護対象名に出現する文字で一致を失う形は0件」を実測）ため、
   差し戻しの主因であるコスト問題とは切り離し、**現状を単体テストで固定**する方針を
   採った（review.md §7-4 が求める「現状固定（優先度低）」に対応）。閉じる場合は
   走査規則の変更としてD2(b)の再設計＝architect差し戻しが必要。
