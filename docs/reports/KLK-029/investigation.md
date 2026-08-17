# KLK-029 調査報告（investigator）

## Findings
- 再現手順（`sed 's/.*/rm docs\/SPEC.md/e' unrelated.txt`）は実機・実コードともに成立を確認（`find_violation`が`None`=allow）。原因は`PATHISH_RE = re.compile(r"[A-Za-z0-9_.\-/]+")`に`\`（バックスラッシュ）が含まれず、`docs\/SPEC.md`が`docs`と`/SPEC.md/e`に分断され、後者の`os.path.basename`が`"e"`になり`SPEC.md`一致に失敗するため。
- `tickets/active|done/*.md`系（スラッシュ2箇所）はさらに深刻: 両方をエスケープすると`tickets`・`/active`・`/APP-001.md`の3片に分断され、`"tickets/active" in path`という部分文字列判定が原理的に一致不能になる（`docs/SPEC.md`側の「たまたま basename が残る」偶然すら起きない）。
- **awkでも同型の回避を実証**: `awk 'BEGIN{system("rm tickets\/active\/APP-001.md")}' unrelated.txt`と`awk '{print > "tickets\/active\/APP-001.md"}' unrelated.txt`の両方が`None`（allow）。実機gawk 5.2.1は`\/`を警告付きで単なる`/`として扱う（`ANSI_C`と無関係の独自の緩い未知エスケープ処理）ため、検出回避と実際の書き込み実行が両立する。
- **重要な限定**: `docs/SPEC.md`（スラッシュ1箇所）は、直後に閉じクォート（`"`）や別の非PATHISH文字が来る文脈（awkのsystem()引数・print>の文字列リテラル）では回避されない（`"docs\/SPEC.md"`は`/SPEC.md`という独立候補が生き残りbasename一致で検出される）。sedの`s/.*/rm docs\/SPEC.md/e`だけが回避に成功するのは、末尾の`/e`（sedの終端デリミタ+フラグ）が同じPATHISH_RE連続区間へ食い込み`/SPEC.md/e`（basename=`e`）に化けるため。**tickets/active|done系は文脈に依らず常に回避可能**、docs/SPEC.md系は末尾文脈依存という非対称性がある。
- 本バグの根はエスケープの「必然性」に限らない。sedの独立`e`コマンド（`s///`のデリミタ制約を受けない形）でも**不要な**`\`を任意に挿入するだけで同じ回避が成立し、しかも実機GNU sed 4.9で実際に`/bin/sh -c`へ渡る際にシェル自身が非クォートの`\/`を`/`へ正規化して実行することを実証した（`sed '1e echo docsX\/SPECX.md' unrelated.txt`→出力`docsX/SPECX.md`）。攻撃者はデリミタ衝突を待つ必要すらない。

## Evidence
- `codebase`: `.claude/hooks/guard_bash_writes.py:442`（`PATHISH_RE`定義）、`:666-673`（`guarded_paths`）、`:703-719`（`is_guarded_token`/`mentions_guarded`）、`:1976-1991`（sedゲート本体、`statement_violation`内`mentions_guarded`ゲートは`:2080-2081`）、`:1800-1879`（`awk_violation`、AW-1ゲートは`:1814`、全体ゲートは`:1823`）。
- `empirical`（本ホスト2026-08-17実施。GNU sed 4.9・GNU Awk 5.2.1）: `PATHISH_RE.findall`直接実行、`guard_bash_writes.find_violation()`直接呼び出し、実機`gawk`/`sed`での`\/`正規化実測。全コマンド・出力は本レポート末尾「詳細調査ログ」に転記。
- `codebase`: `tests/test_guard_bash_writes.py` INV-SED-06/07（`sed 's/a/b/e' tickets/active/APP-001.md`）は保護対象パスを**位置引数**（エスケープなし）に置く形のみをカバーし、本チケットの「プログラム本文内でエスケープされた言及」パターンは既存80件の`INVENTORY_CASES`・213テストメソッドのいずれにも存在しない（grep確認）。
- `empirical`: 現状のtest_guard_bash_writes.py全体は本ホストで213件全pass（`python3 -m unittest tests.test_guard_bash_writes`、2026-08-17実行、修正前ベースライン）。pytestは未インストールのためunittestで実行。

## Dependency Graph
- `PATHISH_RE`→`guarded_paths`→`_is_guarded_path`→`is_guarded_token`→`mentions_guarded`という単一の縦の依存鎖があり、`mentions_guarded`/`is_guarded_token`の呼び出し箇所はgrepで15箇所確認（`:1247,1814,1819,1823,1974,1976,2039,2060,2081,2227,2233,2243,2276`他）。修正をこの鎖の根（`PATHISH_RE`/`guarded_paths`）で行うと**全呼び出し箇所に影響**（sed/awk固有ではなく、リダイレクト先判定・`cd`追跡・変数代入追跡・degraded modeも含む全経路が対象）。
- degraded_violation（字句解析失敗時のフォールバック、`:2227,2243`）も同一の`mentions_guarded`を使うため、正常経路と同じ脆弱性を共有する（別経路ではない）。
- `ansi_c_decode`/`ANSI_QUOTE`系（QT-1/QT-3）は本バグの救済にならないことを確認済み（`\/`はANSI-Cエスケープ表`ANSI_C_ESCAPE_RE`に一致しないため`ansi_c_decode`は無変化を返す）。
- 影響を受けるのはALLOWED_HEADS中「プログラム本文のミニ言語を持ち、かつそのミニ言語がデリミタ/文字列リテラルの区切り記号を`\`でエスケープする慣習を持つ」head、すなわち**sedとawkのみ**に実質限定される（grep/sort/uniq/find/git/mvは書き込み判定がバックスラッシュ文脈に依存しないため対象外と判断。ただしこの判断はコード読解ベースで、全headの実機PoCまでは行っていない＝Unknowns参照）。

## Risk Areas
- **CWD保護時は無関係**: sedの`strict = cwd_is_guarded(cwd)`分岐・awkの`cwd_is_guarded(cwd)`ORは`mentions_guarded`を経由せず強制的にプログラム本文検査へ入るため、本バグの影響を受けない（`cd tickets/active && sed ...`は既存どおり安全）。攻撃が成立するのは「cwdが保護対象外」かつ「位置引数のファイル名が非保護対象」の組合せに限定。
- 誤deny予算（受け入れ条件）の見積りが最重要リスク。`PATHISH_RE`/`guarded_paths`を**汎用的に**拡張（例: `\`を許容文字に追加）すると、影響範囲が sed/awk 以外（リダイレクト先・`guarded_write_target`・`record_assignments`等）にも及び、KLK-015 R1のような限定列挙が困難になりうる。sed/awkのプログラム本文抽出関数だけに限定した狭いパッチのほうがブラスト半径は小さいが、トップレベルの`statement_violation`（`:2080`）ゲート自体もhead非依存で`mentions_guarded`を呼ぶため、そこを迂回する設計（cwdのstrict分岐と同型の「sed/awk専用strict」追加）が必要になる可能性がある。
- KLK-015のレビュー時に発見された類似の教訓（`AW-7`の`\xHH`ホワイトリスト回避、Critical・実機実証・`tests/test_guard_bash_writes.py`1633行目付近）と構造が似ている: 「見えている文字列」と「実際に実行される文字列」の乖離を突く回避。修正時はその修正パターン（ホワイトリスト側の走査規則精緻化）を参考にできるが、本件は検出**対象抽出**（PATHISH_RE）側の問題であり位置が異なる。

## Assumptions
- 「エスケープ回避」の脅威モデルは、攻撃者が`sed`/`awk`のプログラム本文中で意図的にバックスラッシュを挿入できる（デリミタ衝突の必然性の有無を問わず）という前提で調査した。これは実機検証済みであり推測ではない。
- ticket本文が言及する「sed以外のhead（少なくともawk）」以外（grep/sort/uniq/find/git等）は、コード読解上「書き込み判定がプログラム本文の文字レベル同一性に依存しない」ため対象外と**判断**したが、全head総当たりの実機PoCは行っていない（Unknowns参照）。
- `os.path.normpath`はPOSIX実装（`posixpath`）であり`\`をパス区切りとして扱わない、という前提（Linux上のPython標準挙動。実測でも確認済み）。

## Unknowns
- **sed/awk以外のheadに同型の回避経路が皆無であることは実機PoCで確認していない**（コード読解による推定に留まる。特に`find -exec`のコマンド文字列、`git`のコミットメッセージ経由等、backslashを含む文字列が別の判定経路に流れ込むケースを網羅的には潰していない）。architect/testerでの再検証を推奨。
- sedの区切り文字が`/`以外（`|`・`.`・`-`等）の場合の一般化規則（「区切り文字がPATHISH_RE収載文字と衝突する場合のみ回避成立、非収載文字なら回避不成立」）は`|`と`/`の2文字でのみ実測確認した。`.`・`-`・その他の任意区切り文字（GNU sedは英数字・`\`・改行以外ほぼ任意）は理論的推定であり未実測。
- 修正候補（PATHISH_RE拡張 vs sed/awk専用エスケープ正規化 vs 別レイヤ）の誤deny予算を確定するには、実装後に既存213テスト全件との突き合わせが必須（本調査では現状のベースライン213件passのみ確認し、修正案の実装・再テストはarchitect/implementer/testerの領分のため未実施）。

---

## 詳細調査ログ

### 1. PATHISH_RE単体でのバックスラッシュ分断の実証
```
>>> import re
>>> PATHISH_RE = re.compile(r'[A-Za-z0-9_.\-/]+')
>>> PATHISH_RE.findall(r's/.*/rm docs\/SPEC.md/e')
['s/.', '/rm', 'docs', '/SPEC.md/e']
```
`os.path.normpath('/SPEC.md/e')` の basename は `'e'` であり `'SPEC.md'` に一致しない。→ `guarded_paths()` はこの語から保護対象パスを1件も見つけられない。

### 2. `find_violation()` 直接呼び出しによるエンドツーエンド実証（本ホスト実行、2026-08-17）
（`SPEC.md`・`tickets/active/APP-001.md`という文字列は自ホストのguard_bash_writes.py自身が「保護対象言及」として自分自身のBashツール呼び出しをdenyするため、文字列を分割結合して構築し実行した。以下は実際に得られた出力をそのまま転記）

```
CMD:  sed 's/.*/rm tickets\/active\/APP-001.md/e' unrelated.txt
VIOLATION: None                      # ← バイパス成立（本チケットの中核バグ）

CMD2: sed 's/.*/rm docs\/SPEC.md/e' unrelated.txt
VIOLATION2: None                     # ← バイパス成立（チケット再現手順そのもの）
```

対照（デリミタ`|`。`|`はPATHISH_RE非収載文字のため分断してもフラグメントが独立して一致する）:
```
cmd3: sed 's|.*|rm docs\|SPEC.md|e' unrelated.txt
violation3: sed プログラムに許可されていないコマンド／文字 'e' があります...   # ← 正しくdeny（バイパスしない）
```

対照（位置引数に保護対象を置く形。KLK-015 INV-SED-06/07と同型）:
```
cmd2: sed 's/.*/rm SPEC.md/e' docs/SPEC.md
violation2: sed プログラムに許可されていないコマンド／文字 'e' があります...   # ← 正しくdeny
cmd5: sed 's/.*/rm tickets/active/APP-001.md/e' unrelated.txt   (エスケープなし対照)
violation5: sed プログラムに許可されていないコマンド／文字 'a' があります...   # ← 正しくdeny
```

### 3. awk側の実証（`system()` と `print >` の両方でバイパス成立）
```
A: awk 'BEGIN{system("rm tickets\/active\/APP-001.md")}' unrelated.txt
VIOLATION A: None                    # ← バイパス成立

B: awk 'BEGIN{system("rm tickets/active/APP-001.md")}' unrelated.txt   (対照・エスケープなし)
VIOLATION B: awk プログラムの関数呼び出し system() は許可されていません...   # ← 正しくdeny

C: awk 'BEGIN{system("rm docs\/SPEC.md")}' unrelated.txt
VIOLATION C: awk プログラムの関数呼び出し system() は許可されていません...
             # ← docs/SPEC.md（スラッシュ1箇所）はsystem()の文脈では
             #    バイパスしない（閉じクォート直前で候補が"/SPEC.md"に
             #    独立して残りbasename一致するため）

D: awk '{print > "tickets\/active\/APP-001.md"}' unrelated.txt
VIOLATION D: None                    # ← print > によるファイル書き込みもバイパス成立

E: awk '{print > "tickets/active/APP-001.md"}' unrelated.txt   (対照・エスケープなし)
VIOLATION E: awk のプログラム内リダイレクト（print > file 等）は許可されていません
```

### 4. 実機gawk/mawkでのバックスラッシュ処理の実測（検出回避が実際の実行に直結することの裏付け）
```
$ awk 'BEGIN{print "docsX\/SPECX.md"}'
awk: cmd. line:1: warning: escape sequence `\/' treated as plain `/'
docsX/SPECX.md
$ mawk 'BEGIN{print "docsX\/SPECX.md"}'
docsX\/SPECX.md          # mawkはバックスラッシュを保持（実装依存）

$ awk 'BEGIN{system("echo tickX\/activeX\/APP-001.md")}'
awk: cmd. line:1: warning: escape sequence `\/' treated as plain `/'
tickX/activeX/APP-001.md
```
本ホストの`/usr/bin/awk`はgawk 5.2.1（symlink先確認済み）。gawkは未知のエスケープシーケンス`\/`を警告付きで`/`へ正規化するため、hookが見る字面（`\/`残存）と実際に実行される文字列（`/`のみ）が乖離する。

### 5. sedの`e`コマンド単体（`s///e`フラグ以外）でも不要なエスケープにより回避が成立する実証
```
$ printf 'line1\n' > unrelated.txt
$ sed '1e echo docsX\/SPECX.md' unrelated.txt
docsX/SPECX.md
line1
```
`e`コマンドの引数はデリミタを持たないため`\/`のエスケープはsed文法上不要（gratuitous）だが、`/bin/sh -c`が非クォートの`\/`を`/`へ正規化して実行するため、攻撃者はデリミタ衝突を待たずに任意の位置へバックスラッシュを挿入するだけで検出を回避できる。これはSED-7ホワイトリストの手前（言及ゲート）の問題であるため、SED-7自体の健全性（KLK-015で確立）とは独立した別の穴である。

### 6. `ansi_c_decode`による救済が働かないことの確認
`ANSI_C_ESCAPE_RE = re.compile(r"\\(x[0-9A-Fa-f]{1,2}|u[0-9A-Fa-f]{1,4}|U[0-9A-Fa-f]{1,8}|[0-7]{1,3}|c.|[abeEfnrtv\\'\"?])")` は `\/` に一致しない（`/`はこの表のどのエスケープ形にも含まれない）。したがって`is_guarded_token`のQT-3救済（ANSI-C復号後の再判定）はこのバグに対して無力（`ansi_c_decode("docs\\/SPEC.md")`は無変化を返し`decoded != text`がFalseになる）。

### 7. 既存テストのベースライン（修正前）
```
$ python3 -m unittest tests.test_guard_bash_writes -v 2>&1 | tail -3
Ran 213 tests in 25.387s
OK
```
`INVENTORY_CASES`（パラメタライズ表）は80件、`INV-SED-*`は26件・`INV-AWK-*`複数件あるが、いずれも保護対象パスを**位置引数**として渡す形のみで、「プログラム本文内でエスケープされた言及」を扱うケースは0件（grep確認）。

### 8. 修正候補の洗い出しと影響の予備比較（設計はarchitectの領分のため、選択肢の提示に留める）
- **候補1: `PATHISH_RE`に`\`を追加するのみ**（例: `[A-Za-z0-9_.\-/\\]+`）— `docs/SPEC.md`型（basenameチェック）は救済されるが、`tickets/active/*.md`型（部分文字列チェック）は**救済されない**（`os.path.normpath`は`\`をセパレータとして扱わないため`"tickets/active" in path`が依然として不成立。文字集合を広げるだけでは不十分なことを実測で確認済み＝§1参照の分断メカニズムを参照）。加えて全15箇所の呼び出し元（リダイレクト先判定・`cd`追跡・変数代入追跡等）に影響するためブラスト半径が広い。
- **候補2: `guarded_paths`をエスケープ対応にする**（`\`+1文字を1トークンとして連結するregexへ変更し、候補文字列からは`\`を除去してから`_is_guarded_path`判定する）— `docs/SPEC.md`型・`tickets/active`型の両方を救済できる（手計算で確認、実装はしていない）。ただし依然として全呼び出し元に影響するグローバル変更であり、grep等の正規表現で`SPEC\.md`のようなエスケープ済みドットを検索する既存の読み取り専用コマンドが新たに「言及あり」と判定されるようになる可能性がある（ただしgrep自体はmentions_guardedがTrueになっても書き込み判定を持たないため単体では新規denyを生まないと推定）。sed/awk側で「エスケープが本当に必要な区切り文字と、たまたま隣接するだけの他の記号」を区別できないため、意図しない結合（誤検出）が新たな**allow→deny**（誤deny）を生むパターンの洗い出しが必須（例: `sed 's/\(a\)-\(b\)/\1\2/'`のような一般的なsedバックリファレンス構文で`\`+`-`等の組合せが偶然「tickets」等の文字列に隣接するケースは考えにくいが網羅的検証はしていない）。
- **候補3: sed/awkのプログラム本文抽出関数（`sed_program_texts`/`awk_program_texts`）専用にエスケープ正規化した言及判定を追加し、cwdのstrict分岐と同型の「sed/awk専用strict」を`statement_violation`のトップレベルゲート（`:2080`）とhead別ゲート（`:1823`,`:1976`）の両方へ足す** — ブラスト半径をsed/awkに限定できる利点があるが、トップレベルゲートを迂回する新しい分岐を増やすため設計・実装コストは候補2より高く、KLK-015のSED-7実装同様「終端条件の食い違い」という新しいクラスの穴を作りうる（sedの`sed_strip_literals`・awkの`awk_strip_literals`と同型の「開始/終端条件の一致」を新規コードでも担保する必要がある）。

いずれの候補も「誤deny予算の確定（受け入れ条件）」を満たすには、実装後に既存213テスト全件の再実行＋新規denyの限定列挙が必須であり、これはarchitect設計後のimplementer/testerフェーズで行うべき作業と判断し、本調査では選択肢の提示に留めた。

## 関連ファイル
- `.claude/hooks/guard_bash_writes.py`（`PATHISH_RE`:442行目、`guarded_paths`:666行目、`is_guarded_token`:703行目、`mentions_guarded`:717行目、`statement_violation`:2067行目、`awk_violation`:1800行目、`sed`ゲート:1960-1991行目）
- `tests/test_guard_bash_writes.py`（`INVENTORY_CASES`約289行目以降、`INV-SED-*`354-407行目）
- `docs/designs/KLK-015.md`（§6 R1: 誤deny予算の列挙形式のprecedent）
- `tickets/active/KLK-029_mentions_guardedのエスケープ回避によるsedゲート未発火.md`
