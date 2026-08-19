# KLK-034 実装レポート（implementer）

対象チケット: KLK-034（否定文字クラス `[^...]` とPOSIX文字クラス `[[:class:]]` が
pathish分断で検出されずSPEC.md操作が誤allowされる）
設計書: `docs/designs/KLK-034.md`（全10節。実装の正）
作業ブランチ: `fix/KLK-034-caret-negated-class-posix-class`（develop `6f7fdb2` から派生）
worktree: `../kenesis-loop-kit.wt/KLK-034`

## 1. コミット構成（3 Phase + 本レポート）

| コミット | Phase | 内容 | 変更行数 |
|---|---|---|---|
| `e6af191` | 1 | `guard_bash_writes.py`（文字集合拡張＋正規化関数2つ＋配線＋docstring3箇所）・`_ticket_lib.py`（docstringのみ） | +205 / -9（2ファイル） |
| `f1fd0e5` | 2 | `tests/test_guard_bash_writes.py` KLK-034節 19メソッド（純追加） | +216 / -0 |
| `a260475` | 3 | `docs/designs/KLK-033.md` §5表1セル・§7の1文・§8のrevertコマンドと注意点（docsのみ） | +27 / -6 |
| （本ファイル） | - | 実装レポートの外部化 | - |

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
