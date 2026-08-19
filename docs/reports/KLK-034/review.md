# KLK-034 レビューレポート（reviewer）

対象チケット: KLK-034（`[^...]`・`[[:class:]]` のpathish分断による誤allow是正）
レビュー対象: worktree `/home/bzg55/workspace/breeze/kenesis-loop-kit.wt/KLK-034`
ブランチ: `fix/KLK-034-caret-negated-class-posix-class` / HEAD `e17c55d` / worktree clean
判定: **rejected**（差し戻し先: implementer）
レビュー日: 2026-08-19（APIセッション上限による中断後の再実行）

## 0. 前提（tester Quality Gate）

- `docs/reports/KLK-034/test-report.md` §8 で **pass / 840件 OK（失敗0）** を確認。
- reviewer自身の再実測: `python3 -m unittest discover -s tests -p "test_*.py"` → **Ran 840 tests / OK / 53.088s**。
- `git diff develop...HEAD --numstat`:
  `_ticket_lib.py` +6/-0、`guard_bash_writes.py` +199/-9、`docs/designs/KLK-033.md` +27/-6、
  `tests/test_guard_bash_writes.py` +284/-0、reports 2ファイル +309/-0。
  `tests/test_ticket_lib.py` は差分に現れない（完全無変更）。tests側の削除行は **0件**。
  KLK-034テストメソッド数 = **22**（implementer 19 + tester 3）。

## 1. Critical: 新設スキャナの超線形・無上限コスト（本チケットが導入した回帰）

### 1-1. 実測値（すべてreviewerが本worktreeで実測）

ヘルパー単体 `_bash_bracket_to_fnmatch("[:"×k)`:

| 入力長 | 所要 |
|---|---|
| 500字 | 0.0074s |
| 1,000字 | 0.0339s |
| 2,000字 | 0.169s |
| 4,000字 | 0.904s |

→ 倍長あたり約4.6〜5.3倍＝**O(n^2.2〜2.4)**。`"["×n` も同様（500字0.0089s → 4,000字0.606s）。

end-to-end `find_violation` 新旧対照（`SHELL_EXPAND_PATHISH_RE` と `_bash_bracket_to_fnmatch` を
実行時のみdevelop形へ差し替え。リポジトリのコードは変更していない）:

| 単一トークン長 | develop（旧） | KLK-034（新） | 倍率 |
|---|---|---|---|
| 4,000字 | 0.006s | 1.011s | ×168 |
| 8,000字 | 0.011s | 6.029s | ×548 |
| 16,000字 | 0.022s | 36.967s | ×1,680 |

保護対象書き込みと同一文・病的語が先行する形（`rm "[:"×k docs/SPEC.md`）:

| 病的語長 | 所要 | 最終判定 |
|---|---|---|
| 8,000字 | 6.01s | DENY |
| 16,000字 | 38.33s | DENY |
| 24,000字 | **118.72s** | DENY |

原因の切り分け（`"[:"×8000` = 16,000字、`echo <word>`）:

| 構成 | 所要 |
|---|---|
| 新charset + 恒等正規化 | 0.064s |
| 新charset + 新正規化 | 36.639s |
| `"["×16000` + 新正規化 | 13.938s |
| `"["×16000` + 恒等正規化 | 0.009s |

→ **コスト増は `:` の文字集合追加ではなく新設スキャナに起因**（`[` のみの語でも成立）。

### 1-2. 機序

- `_scan_bracket_expression` の `pattern.find(leader + "]", i + 2)` は**語末まで無制限**に探索する。
  終端 `]` が無い `[:` が多数並ぶ語では、内部ループの各 `[:` ごとに O(n) の `find` が走る。
- `_bash_bracket_to_fnmatch` は `[` を見つけるたびに `_scan_bracket_expression` を呼び直す（未閉塞時は
  1文字進めるだけ）ため、走査が重複して全体で O(n²)〜O(n³) に達する。
- 上流に長さ上限が無い（`MAX_BRACE_DEPTH`/`MAX_BRACE_COMBINATIONS`/`MAX_BRACE_CHAR_COUNT` は
  ブレース専用。コマンド長・候補長・成分長の上限は `guard_bash_writes.py` に存在しない）。

### 1-3. セキュリティ上の意味

- `.claude/settings.json` の当該hook定義に `timeout` 指定は無く、Claude CodeのPreToolUse既定
  タイムアウト（60s）が適用される。`.claude/hooks/README.md` は **fail-open** を明文の設計原則と
  している（「hook内部のエラーではループをブロックしない」）。
- 実測から、約20,000字の単一トークン（`[:` の反復）で60sを超える。したがって
  `rm <病的語> docs/SPEC.md` 型のコマンドは、hookがdenyを出す前に打ち切られ、
  **人間承認ゲートをすり抜ける**経路になりうる（本チケットが閉塞した欠陥と同じ結果）。
- 併せて、そこまで至らなくてもBash呼び出しごとに数十秒の遅延が発生する（実運用の可用性劣化）。
- KLK-018は同種のコスト爆発（ブレース直積・RecursionError）を**上限＋deny方向フォールバック**で
  抑える前例を確立している（`guarded_paths_after_shell_expansion` docstring「RecursionError 安全性」）。
  本経路にはその上限もフォールバックも無い。

### 1-4. 設計書との矛盾（Spec Violation）

設計書§6リスク表:

> | 新関数の走査が病的入力（`[` を大量に含む語）でコストを消費する | low |
> 走査は語の長さに対して線形（各文字を定数回訪問し、`find` も終端探索の範囲内）。…

「線形」「`find` も終端探索の範囲内」はいずれも成立しない（上記1-1・1-2）。軽減策の根拠が
崩れているため、本項目が「low」として通過してしまった。修正と同時に§6を訂正しないと、
将来の保守者が同じ誤った前提を引き継ぐ。

### 1-5. 推奨修正

1. `find(leader + "]", i + 2)` を当該ブラケット式の探索範囲に限定する（第3引数で上限を与える）。
2. それだけでは `"["×n` の O(n²) が残るため、KLK-018前例に倣うコスト上限を追加する
   （例: 成分長 or `[` 出現数の上限）。**超過時のフォールバックは deny 方向に倒す**こと
   （正規化スキップ＝allow方向は不可。KLK-034が閉じた誤allowを再導入するため）。
3. 上限境界のテストを追加する（KLK-018の `MAX_BRACE_*` 境界テストと同型）。
4. 設計書§6の該当行を実測値とともに訂正する。

## 2. High Risks

1. Critical項目の悪用には意図的な病的入力（数千〜2万字の単一トークン）が必要で、通常コマンドの
   判定内容・レイテンシには影響しない（実運用形は全て短語）。したがって「実運用の即時障害」では
   なく「セキュリティ境界の新しい抜け道＋可用性劣化」である。
2. fail-openへの到達はハーネス側の打ち切り挙動に依存する。reviewerが実測したのはhook単体の
   経過時間（最大118.7s）と内部上限の不在であり、Claude Code側の実タイムアウト挙動は
   README記載のfail-open原則と既定値からの推定である。
3. 新スキャナのコスト境界を固定するテストが無いため、修正後も再発を機械的に検出できない。
4. `find` の無制限探索はコストだけでなくbash字句規則との乖離も生む（下記3-1）。修正は両者を
   同時に閉じる形が望ましい。

## 3. Medium Risks

### 3-1. bashとの意味論乖離2形（実害なし・未文書）

ガジェット総当たり（後述4-2）で検出した唯一の「一致を失う」形:

| ガジェット | 正規化後 | bashが一致させる文字 | fnmatchの結果 |
|---|---|---|---|
| `[![:]` | `[![:]`（恒等） | `[` | 不一致 |
| `[^[:]` | `[![:]` | `[` | 不一致 |

- 機序: bashは `[:` を文字クラス開始として読み進めてメンバー集合から外すが、Pythonの `fnmatch`
  は `[` と `:` を否定クラスのメンバーとして扱う。よってPython側が**bashより狭い**（＝allow方向）。
- 影響: 失う文字は `[` のみ。保護対象名（`SPEC.md`・`active`・`done`）に `[` は含まれないため
  誤allowにはならない。`[![:]` はKLK-033の `!` 追加時点から存在し、本チケットは `[^[:]` を
  同じ形へ正規化して継承したにすぎない。
- 根因はCritical項目と同じ「`find` の無制限探索」であり、1-5の修正時に併せて閉じられる。

### 3-2. 残存誤allowの記述精度（AC8の趣旨）

reviewer実測で確認した残存誤allow（bashは `docs/SPEC.md` に一致させるがhookはallow）:

| コマンド | bash展開 | hook |
|---|---|---|
| `rm docs/[+S]PEC.md` | `docs/SPEC.md` | allow |
| `rm docs/[[=S=]]PEC.md` | `docs/SPEC.md` | allow |
| `rm docs/[^+]PEC.md` | `docs/SPEC.md` | allow |
| `rm docs/[^=]PEC.md` | `docs/SPEC.md` | allow |

- いずれも「ブラケット式のメンバーに候補抽出の文字集合外の文字を含む形」であり、モジュール
  docstringの未対応リスト（`+`・`@`・`%`・`=`・`~`・`#`・空白・引用符・`$`・`(`・`)`・`|`・`&`・`;`）に
  文字としては列挙されている＝スコープ外として文書化済み。
- ただし同docstringの「**対応済み**＝…`[^...]`・`[^]abc]`（KLK-034 の正規化）」は無条件に読める。
  未対応節の例示が肯定クラス `docs/[+S]PEC.md` のみのため、`[^+]`・`[^=]` のような**否定クラスでも
  同じ限界がある**ことが読み手に伝わりにくい。AC8「読み手が誤解しない形」の趣旨から一文の追記を推奨。
- 設計書§3 D3表の `[[=c=]]` 行は「実装はするが候補抽出に `=` が無く到達しない」と機序のみを述べ、
  **結果として誤allowが残る**ことを書いていない（他行が「未対応（誤allowが残る。既知の限界）」と
  明記しているのと不整合）。

### 3-3. §8 ロールバック手順の列挙の不整合（軽微）

- KLK-034設計書§8 手順2は「Phase 3 のコミットを除外し、**残り全部**（Phase 1・Phase 2・tester が
  追加した全テストコミット）を逆時系列でrevert」と書くが、括弧内の列挙にレポート外部化コミット
  `5873620` が含まれない。「残り全部」と括弧内列挙が一致しない。
- 実害はない（docs/reports のみで実行時挙動・テスト期待値に影響しない）が、KLK-033訂正では
  `4b4eaeb`（レポート外部化）と `6853236`（マージ）を**明示的に対象外**と書いており、対称性を欠く。
  同じ「revert対象の完全性」を是正するチケットであるため、記述の統一を推奨。
- 本チケットの実コミット構成（§8適用時の対象）:
  `e17c55d`（tester: テスト3件＋test-report.md）→ `5873620`（レポート外部化・docs のみ）→
  `a260475`（Phase 3・**除外**）→ `f1fd0e5`（Phase 2）→ `e6af191`（Phase 1）。
  `git revert e17c55d f1fd0e5 e6af191` で実装・テストが整合して旧挙動へ戻る（設計書の手順は
  ハッシュを固定せず「列挙して全件」と規定しており、testerコミットを構造的に取り込める＝
  KLK-033の欠落の再発防止としては**有効に機能している**）。

### 3-4. 設計書 D2(b) 規則3の記述が実装より狭い

- 設計書§3 D2(b) 規則3: 「**否定マーカーの直後**の `]` はクラスの終端ではなくリテラルメンバー」。
- 実装 `_scan_bracket_expression` は否定マーカーの有無に関係なく `[` 直後の `]` を無条件にスキップ
  （`if i < n and pattern[i] == "]": i += 1`）。
- 実装のほうが正しい（POSIX・bash・Python `fnmatch.translate` はいずれも「リスト先頭の `]` は
  リテラル」）。tester追加テスト `test_klk034_bracket_normalizer_boundary_unit` のコメントが
  正しい規則を明記しており挙動は固定済み。設計書側の文言を実装に合わせる修正を推奨。

## 4. セキュリティ検証（誤allowの残存ベクタ探索）

すべてreviewerが独立に実施。制約（インラインBashにブラケット式を書かない・heredoc不使用・
実bashは非破壊の `echo`/`mktemp -d` のみ）を守り、スクラッチ領域の一時Pythonスクリプト経由で実行。
bash側の真値は `mktemp -d` 配下に空の `docs/SPEC.md`・`tickets/active/APP-001.md`・
`tickets/done/APP-001.md` を作り、`echo <pattern>` の展開結果のみを観測して取得（`rm` は一切実行せず）。

### 4-1. end-to-end 総当たり（bash真値 × hook判定の対照）

| スイープ | パターン数 | bashが保護対象に一致 | 新規誤allow |
|---|---|---|---|
| ブラケット本体を12文字集合×長さ≤3で全生成（`S ^ ! : ] [ x . / - * ?` ／ 挿入位置3種） | 8,865 | – | **0** |
| POSIXクラス/照合要素/等価クラスをトークンとして混成（15トークン×長さ≤3・挿入位置3種） | 10,848 | 58 | **0**（既知の限界 `=` 系 7件を除く） |
| 同トークン集合 × 挿入テンプレート9種（`SPEC.md` の各部・`active` の各部を置換） | 32,544 | 209 | **0**（既知の限界 24件を除く） |
| 個別の敵対的形（下記4-3） | 52 | – | **0**（既知の限界 4件を除く） |

「既知の限界」として除外したものは、すべて候補抽出の文字集合外の文字（`=`・`+` 等）を含む形＝
モジュールdocstringが明記済みの残余。

補足: 上記スイープで `docs/*`・`docs/**`・`docs/?*` 等の孤立ワイルドカード形は「bashは
`docs/SPEC.md` に一致させるがhookはallow」となるが、これは**KLK-031が誤deny是正のために
意図的に選んだ設計**（`has_literal_char` ゲート）であり、本チケットの前後で不変。スコープ外。

### 4-2. 過大近似の健全性（D3の「一致を失わない」主張の反例探索）

`?` 置換・`[^`→`[!` 正規化が **bashが一致させる文字を落とさない**ことを、文字レベルで直接検証。

- 方法: `mktemp -d` 配下に保護対象名の全構成文字を含むファイル群（`z<char>`）を作成し、
  ガジェット `[...]` について bashの一致集合と `fnmatch(normalize(...))` の一致集合を突き合わせ。
- 規模: 構文文字7種（`[ ] : . ^ ! S`）×長さ≤5 = **19,607ガジェット**、bashが一致した
  （ガジェット,ファイル名）組 **84,204組**。
- 結果: 一致を失う文字は **`[` のみ**（170ガジェット、いずれも `[!…[:]`／`[^…[:]` 族＝3-1の形）。
  **保護対象名に出現する文字（S P E C . m d a c t i v e o n）で一致を失う形は 0 件。**
- 別スイープ（10トークン×長さ≤4 = 11,110ガジェット、61,862組）では `[^[==]` が広範に一致を失うが、
  `=` は候補抽出の文字集合外で到達不能＝既知の限界の範囲内。
- 結論: **§3 D3の健全性主張（過大近似はallow方向へ劣化しない）は、保護対象名に関して実測上成立**。

### 4-3. 個別の敵対的形（抜粋。すべてbash真値と対照）

| コマンド | bash展開 | hook | 判定 |
|---|---|---|---|
| `rm docs/[^x]PEC.md` / `[^s]` / `S[^x]EC.md` | `docs/SPEC.md` | DENY | AC1(a) ✓ |
| `rm docs/[[:upper:]]PEC.md` / `[[:alpha:]]` / `[[.S.]]` | `docs/SPEC.md` | DENY | AC1(b) ✓ |
| `rm tickets/[^x]ctive/…` / `[[:lower:]]ctive/…` | `tickets/active/APP-001.md` | DENY | AC1(c) ✓ |
| `rm docs/[:S]PEC.md` / `rm tickets/[:a]ctive/…` | 一致 | DENY | `:` 追加の真陽性 ✓ |
| `rm docs/[^/]PEC.md` / `[/S]PEC.md` / `tickets/[^/]ctive/…` | **非一致（bashも `/` で語を先に分割）** | allow | D2(a)の前提を実証 ✓ |
| `rm docs/[\S]PEC.md` | `docs/SPEC.md` | DENY（lexが `\` を除去） | ✓ |
| `rm docs/[^^]PEC.md` / `[^]x]` / `[!^]` / `[[:upper:]x]` | `docs/SPEC.md` | DENY | ✓ |
| `rm docs/[[:upper:]]×4 .md` / `[^x]×4 .md` / `????.md` | `docs/SPEC.md` | DENY | 長さ一致経路 ✓ |
| `rm tickets/[[:alpha:]]×6/APP-001.md` | `tickets/active/APP-001.md` | DENY | ✓ |
| `rm docs/[^S]PEC.md` / `[^x][^P]EC.md` / `[a[^]one` / `[^x`（未閉塞） | 非一致 | allow | 精度 ✓ |
| `rm docs/[[:x]PEC.md:]]` / `[[.x]PEC.md.]]`（過大消費プローブ） | 非一致 | allow | 一致喪失なし ✓ |
| `rm docs/[+S]PEC.md` / `[[=S=]]` / `[^+]` / `[^=]` | `docs/SPEC.md` | allow | 既知の限界（3-2） |
| `rm "docs/[^x]PEC.md"` / `'…'` / `[\^x]` | 非一致 | DENY | 誤deny（安全側・軽微） |

### 4-4. degraded経路と正常経路の対称性

| コマンド | 旧 | 新 |
|---|---|---|
| `rm docs/[^x]PEC.md # don't`（degraded） | allow | **DENY** |
| `rm docs/[[:upper:]]PEC.md # don't`（degraded） | allow | **DENY** |
| `cat docs/[^x]PEC.md # don't`（degraded・読み取り） | allow | allow |
| `cat docs/[^x]PEC.md` / `cat docs/[[:upper:]]PEC.md` / `head -5 …` | allow | allow |
| `echo x > docs/[^x]PEC.md` / `echo x >> tickets/[^x]ctive/…` | allow | **DENY** |

→ AC1(d)(e) 充足。degradedと正常経路は書き込み系でdeny・読み取り系でallowが対称。

### 4-5. 新旧対照（implementation.md の主張の独立検証）

- **DENY→allow 6件**: `rm docs/SP*.md:1`・`docs/SP*.md^y`・`docs/:SP*.md`・`docs/^SP*.md`・
  `tickets/acti*e:x/APP-001.md`・`tickets/acti*e^x/APP-001.md` → **6/6を再現**。
  さらに6形すべてについて実bash展開を観測し、いずれも保護対象に一致しない（語がリテラルのまま
  出力される）ことを確認 → **旧denyは誤denyであり是正方向という結論は妥当**。
- **allow→DENY 12件**: implementation.md §4-2の12形を **12/12再現**。
- 誤deny予算（20形の現実的コマンド）: `grep '^foo'`・`sed 's/^x/y/'`・`awk -F:`・`PATH=a:b`・
  `git log --format=%h:%s`・`cut -d:`・`tr -d '[:space:]'`・`grep -o '[[:alpha:]]'`・
  `awk -F'[:,]'`・`grep -E '^[A-Z]:'`・`rm build/*`・`ls tickets/active`・`cat docs/SPEC.md`・
  `find . -name '*.md'`・`git commit -m "[KLK-034] fix"`・`mv tickets/active/… tickets/done/`・
  `docker run -v .:/app`・`rm dist/*:cache`・`rm a{1,2}^b{3,4}.txt`・`rm a{1,2}:b{3,4}.txt`
  → **全件 判定不変**（新規誤denyなし）。
- AC4が明示する既存2形: `pwd && cut -d: -f2 tickets/active/APP-001.md`＝allow不変、
  `sed -n '/[^/]/p' tickets/active/APP-001.md`＝allow不変を確認。
- リテラル形のDENY維持: `rm docs/SPEC.md:1`・`rm tickets/active/APP-001.md:1` → DENY不変
  （`PATHISH_RE` 側 `is_guarded_token` とのORが機能。§7(4)の仕組みを実証）。

## 5. 受け入れ条件の充足確認（AC×検証手段）

| AC | 判定 | reviewerの検証手段 |
|---|---|---|
| AC1 | 充足 | (a)(b)(c) end-to-end DENY を自前実測、(d) `cat`/`head`（正常・degraded）allow、(e) degraded DENY（4-3・4-4） |
| AC2 | 充足 | 正規化方針は§3 D1/D2・代替案(A)(B)(C)に明示。`_bash_bracket_to_fnmatch("[a[^]one") == "[a[^]one"` を単体テストで固定済み（意味反転の唯一の検出器）。机上トレース12形は実装と一致 |
| AC3 | 充足 | POSIXクラスの `:` 追加では閉塞不能である評価が§2・§3 D3にあり、閉塞範囲の対応表がdocstringへ転記済み。`[:space:]` 型・`tr -d` 型の非巻き込みを実測 |
| AC4 | 充足 | 840件OK（自前再実測）。tests削除0行、`tests/test_ticket_lib.py` 無変更、KLK-018/031/032/033系45メソッド無変更 |
| AC5 | 充足 | 20形の現実的コマンドで判定不変を実測。DENY→allow 6形を再現し代表2形がテストに固定済み |
| AC6 | 充足 | `docs/designs/KLK-033.md` §5表セル・§7が§4-5(1)(2)の文面どおり訂正（他節に差分なし） |
| AC7 | 充足 | 同§8のrevertが `git revert 0d0571f d3ca849 09af704`（逆時系列・testerコミット込み）へ、注意点が「3つ」へ、失敗理由の明記あり。`4b4eaeb`/`6853236` の対象外根拠も記載 |
| AC8 | 充足（精度指摘あり: 3-2） | モジュールdocstring「既知の限界」にKLK-033欄の限定文とKLK-034欄（対応済み/未対応の一覧・非単調性）を確認。`_guarded_paths_from_expanded` docstring②は5行→統合1段落へ差し替わり「大小を区別しない」の不正確が解消。`guarded_paths_after_shell_expansion` にKLK-034ブロック追加。`_ticket_lib.is_spec_basename_fnmatch` は docstring +6行のみ（判定式・シグネチャ無変更） |

§4-7 Phase表（Phase1: AC1/2/3/5/8、Phase2: AC1/2/3/4/5、Phase3: AC6/7）で **AC1〜AC8すべてが
カバーされている**。§4例外（完了条件がreviewer自身の確認行為であるAC）に該当するACは無い。

## 6. Phase 1 完了条件(b) の独立確認（不変対象のバイト単位無変更）

`git diff develop...HEAD -- .claude/hooks/` の ± 行を機械照合。下記はいずれも ± に現れない
（コメント・docstring内での言及のみ）:

- `GLOB_META_CHARS = frozenset("*?[")`
- `PATHISH_RE = re.compile(r"[A-Za-z0-9_.\-/]+")`
- `has_literal_char = any(ch not in GLOB_META_CHARS for ch in component)`
- `if index == last_index and has_literal_char:` / `literals = literals + [GUARDED_FILENAME]`
- `if not any(ch in component for ch in GLOB_META_CHARS):`（事前フィルタ）
- `rebuilt = "/".join(` / `literal if i == index else c` / `rebuilt_path = os.path.normpath(rebuilt)`
- `is_spec_basename_fnmatch` の判定式2行

コード側の実変更は (1) `SHELL_EXPAND_PATHISH_RE` の1行、(2) 新関数2つ＋定数1つ、
(3) `match_component = _bash_bracket_to_fnmatch(component)` の1行追加、
(4) 照合2行の引数差し替え、(5) docstring 4箇所。`-9` 行の内訳は旧regex1行＋docstring 8行で、
コードの削除は regex 1行と照合2行のみ。**設計書§4-1〜§4-4と完全に一致**（逸脱なし）。

## 7. テスト十分性の評価

- 22メソッドが設計書§9のテスト観点6群を実質的にカバー（①1・②1・③5・④5・⑤3・⑥4 ＋ tester 3）。
- 期待値の自己言及性: **概ね回避されている**。`test_klk034_bracket_normalizer_unit` は設計書の
  机上トレース表（実装前に確定した表）と一致、end-to-end群はbash意味論の根拠コメント付き、
  `test_klk034_fragmentation_rule_change_allow` は「bashでも保護対象に一致しない」根拠を明記。
  reviewerが実bash展開で真値を独立確認した結果、**期待値の向きはすべて正しい**（4-3・4-5）。
- `assertDeny`/`assertAllow` はhook本体をサブプロセス起動する真のend-to-endヘルパー
  （`run_guard(payload(command))` → `permissionDecision` を検査）であり、内部関数の
  モックではない＝回帰検出力がある。
- tester追加3件は妥当: 境界7形（`[]`・`[]]`・`[^]]`・`[^]...]`・隣接否定クラス・ブラケット内 `/`）、
  既知の限界の現状allow固定（将来の閉塞検出器）、POSIXクラス長さ一致のdeny実証。
- `test_klk034_bracket_member_outside_charset_known_limitation_allow` は**誤allowを期待値として
  固定**しているが、これは文書化済みの既知の限界に対する変更検出器であり、KLK-033 §3 代替案(B)の
  判断を踏襲した意図的なもの。許容。ただし `=`（等価クラス）系が抜けている（4項参照）。

### 不足しているテスト

1. 新スキャナのコスト上限テスト（上限到達時のフォールバック方向がdenyであることの固定）。
   現状は上限そのものが存在しないため、まず実装が必要（1-5）。
2. `/` を含むブラケット形のend-to-end固定。`rm docs/[^/]PEC.md`・`rm docs/[/S]PEC.md`・
   `rm tickets/[^/]ctive/APP-001.md` はいずれも **bashも非一致**（reviewer実測。bashは
   pathname expansionで語を `/` で先に分割するため、ブラケット式が `/` をまたげない）ため
   allowが正しい。これは§3 D2(a)「成分単位が意味論的に正しい最小の適用単位」という設計の
   中核前提そのものであり、根拠コメント付きで固定する価値が高い。
3. 既知の限界検出器への `=` 系追加: `rm docs/[[=S=]]PEC.md`・`rm docs/[^=]PEC.md`・
   `rm docs/[^+]PEC.md`（否定クラス側の残余も対象であることを明示する意味がある）。
4. 意味論乖離2形（`_bash_bracket_to_fnmatch("[^[:]") == "[![:]"` と、bashが `[` に一致させる
   のに対し正規化後は一致しないこと）の現状固定（優先度低）。

## 8. ロールバック懸念

- 設計書§8の手順（`git log --oneline develop..HEAD` で列挙 → Phase 3 を除外 → 逆時系列でrevert →
  全件テスト）で実際に安全に戻せる。`git revert e17c55d f1fd0e5 e6af191` により実装とテストが
  対で戻り、KLK-033系テストとの整合も保たれる。
- Phase 3（`docs/designs/KLK-033.md` の記述訂正）をrevert対象から除外する判断は妥当
  （戻すと「既存のdenyがallowへ転じる変化は構造的に発生しない」という誤った不変条件が復活する）。
- 部分ロールバック禁止（文字集合拡張のみ／正規化のみを残さない）の規定も妥当。中間状態が
  非原理的になる（`[^s]` のみ偶然一致でdeny）／死んだコードになるという根拠は、reviewerの
  新旧対照実測（`rm docs/[^S]PEC.md` が新実装ではallow＝正規化が精度を回復している）と整合。
- 唯一の不整合はレポート外部化コミット `5873620` の扱いの未規定（3-3）。実害なし。
- ハッシュを固定せず「列挙して全件」と規定した設計判断は、KLK-033の欠落（testerコミット漏れ）の
  再発防止として**構造的に有効**であり評価できる。

## 9. 総合判定

設計の骨格（D1〜D5）・閉塞範囲の決定・記述訂正（Phase 3）・テスト設計はいずれも妥当であり、
セキュリティ本体（誤allowの閉塞）は約4.1万コマンド形・8.4万文字組の敵対的検証で新規の穴が
見つからず、**受け入れ条件AC1〜AC8はすべて充足**している。

一方で本チケットは、セキュリティhookそのものに**無上限の超線形走査**という新しい回帰を導入し、
その軽減策として設計書§6が主張する「線形」は実測に反する。既定60sのhookタイムアウトと
本リポジトリ宣言のfail-open方針の組み合わせにより、約2万字の単一トークンで人間承認ゲートを
すり抜けうる（＝本チケットが閉じた欠陥と同じ結果）。修正は局所（探索範囲の限定＋KLK-018前例に
倣う上限とdeny方向フォールバック＋§6訂正＋境界テスト）で済むため、**implementerへ差し戻す**。

判定: **rejected**（差し戻し先: implementer / `reviewer → implementer` カウンタ +1）
