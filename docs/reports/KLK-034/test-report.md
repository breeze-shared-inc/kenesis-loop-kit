# KLK-034 テストレポート（tester）

対象チケット: KLK-034（否定文字クラス `[^...]` とPOSIX文字クラス `[[:class:]]` が
pathish分断で検出されず誤allowされる）
設計書: `docs/designs/KLK-034.md`（全10節）
実装レポート: `docs/reports/KLK-034/implementation.md`
作業ブランチ: `fix/KLK-034-caret-negated-class-posix-class`
worktree: `/home/bzg55/workspace/breeze/kenesis-loop-kit.wt/KLK-034`

## 1. 全件テスト実行結果

```
python3 -m unittest discover -s tests -p "test_*.py"
```
- implementer報告どおりの再実測: **837件 OK**（tester追加前）
- tester追加3件を含めた最終実測: **840件 OK**（回帰0）
- 実行時間: 約59〜92秒（実行環境依存の揺れ。失敗0件）

**Phase 4（reviewer差し戻し対応）再実測（2026-08-19・本worktree HEAD `8cec2bf`）:**
- `python3 -m unittest discover -s tests -p "test_*.py"` → **849件 OK**（失敗0）。
  実行時間 44.826s。差し戻し時点baseline 840件に対し **回帰0**（+9件はPhase 4(ii)の
  上限境界・コスト回帰・`/`メンバー・既知の限界・意味論乖離のテスト）。
- KLK-034関連テスト31メソッド（Phase1/2の19＋tester既存3＋Phase4(ii)の9）を個別実行し
  全件okを確認（`python3 -m unittest -v tests.test_guard_bash_writes` でメソッド名grep）。
- 詳細は本レポート§9を参照。

## 2. 受け入れ条件×テスト観点6群の照合結果

設計書§9のテスト観点6群と実装済み19メソッドを突き合わせ、全群に最低1メソッドが
対応していることを確認した（1対1対応の一覧は`docs/reports/KLK-034/implementation.md`
§5の表のとおりで齟齬なし）。

| 群 | AC | 実装メソッド数 | 判定 |
|---|---|---|---|
| ①正規化ヘルパー単体 | AC2・AC3 | 1（12形） | 充足 |
| ②候補抽出・展開単体 | AC1(a)・AC2・AC3 | 1 | 充足 |
| ③end-to-end deny | AC1(a)(b)(c) | 5 | 充足 |
| ④allow精度・読み取り対称性 | AC1(d)・AC2・D4 | 5 | 充足 |
| ⑤degraded | AC1(e) | 3 | 充足 |
| ⑥誤deny予算・分断規則検出器 | AC5 | 4 | 充足 |

AC1(a)〜(e)・AC2・AC3・AC4・AC5はすべてend-to-endまたは単体テストで実証されている
（本レポート§4「AC1(a)〜(e)の実証」参照）。AC6・AC7・AC8はコード・docstring・
他チケット設計書の記述面の受け入れ条件であり、テストの対象外（`git diff`による
記述照合は本レポート§5・§6で実施）。

## 3. tester追加テスト（カバレッジの薄い箇所の補強）

設計書§9の19メソッドはAC1〜AC5を過不足なくカバーしているが、下記3点は
設計書§3 D3の対応表・§6リスク表・D2(b)走査規則で言及されているにもかかわらず
専用テストが無かったため、テスターの責務（未カバー経路の追加）として3メソッドを
新規追加した（`tests/test_guard_bash_writes.py`、純追加・既存メソッド無変更）。

1. `test_klk034_bracket_normalizer_boundary_unit` — `_bash_bracket_to_fnmatch`の
   境界形7件（空ブラケット`[]`・`[]]`・`[^]]`・`[^]...]`・隣接する2つの否定クラス
   `[^abc][^def]`・ブラケット内`/`を含む形`[a/b]`・`[^a/b]`）。実測して期待値を
   固定した（本ワークツリーでのpython3直呼び。2026-08-19）。
2. `test_klk034_bracket_member_outside_charset_known_limitation_allow` — 設計書
   §3 D3対応表・モジュールdocstring「既知の限界」が明記する未対応形
   （`docs/[+S]PEC.md`・`[@S]`・`[%S]`・`[~S]`・`[#S]`）のallowを固定する検出器。
   将来この限界を閉塞する変更が入った際に失敗して気づけるようにする。
3. `test_klk034_posix_class_only_component_length_match_deny` — 設計書§6リスク表
   「POSIXクラスのみで構成される成分が長さ一致で保護対象名に一致する形
   〔`tickets/[[:alpha:]]×6/…`〕」の実証。SPEC.md側（`[[:upper:]]`×4+`.md`＝7文字）・
   active側（`[[:alpha:]]`×6＝6文字）の両方でdenyを確認し固定した。

いずれも実装（production code）は変更していない。3件とも実行してPASSを確認済み
（`python3 -m unittest tests.test_guard_bash_writes -v` で個別確認、上記全件テストにも
含まれる）。

## 4. AC1(a)〜(e)の実証状況

- (a) 一般形・偶然一致形: `test_klk034_caret_negated_class_glob_deny`
  （`rm docs/[^x]PEC.md`・`[^s]`・`S[^x]EC.md`）で実証済み。
- (b) POSIXクラス／照合要素: `test_klk034_posix_class_glob_deny`で実証済み。
- (c) tickets側: `test_klk034_guarded_dir_side_deny`・`test_klk034_colon_member_class_deny`
  で実証済み。
- (d) 読み取りhead対称性: `test_klk034_spec_side_read_allow`（`cat`）・
  `test_klk034_degraded_spec_side_read_allow`（degraded版）で実証済み。allowのまま
  であることを確認。
- (e) degraded経路: `test_klk034_degraded_caret_class_deny`・
  `test_klk034_degraded_posix_class_deny`で実証済み。

## 5. 既存テストの非改変確認

```
git diff develop..HEAD -- tests/
```
- `tests/test_guard_bash_writes.py`: implementerコミット（Phase 2, `f1fd0e5`）で
  +216/-0、tester追加分で+68/-0。**削除行0件**（`git diff --stat`で確認）。
  KLK-018系・KLK-031系・KLK-032系・KLK-033系（AC4指定の11メソッドを含む計45メソッド）
  は1行も変更されていない。
- `tests/test_ticket_lib.py`: `git diff develop..HEAD`が0行（完全無変更）。
  AC4指定の`test_is_spec_basename_fnmatch_*`6件を含め全件無変更でPASSを確認。
- AC4が明記する既存2形（`pwd && cut -d: -f2 tickets/active/APP-001.md`・
  `sed -n '/[^/]/p' tickets/active/APP-001.md`）が既存テスト内に存在し無変更で
  PASSすることを確認済み。

## 6. AC6・AC7・AC8（記述面）の照合

- AC6: `git diff develop..HEAD -- docs/designs/KLK-033.md`でPhase 3の2箇所
  （§5表1セル・§7の1文）が設計書§4-5(1)(2)の文面案どおりに差し替わっていることを
  確認した。他の節に差分は無い。
- AC7: 同diffで§8のrevertコマンドが`git revert 0d0571f d3ca849 09af704`へ、
  注意点が「3つ」へ、tester追加コミット`0d0571f`を含める根拠説明が追加されている
  ことを確認した。
- AC8: `.claude/hooks/guard_bash_writes.py`のモジュールdocstring「既知の限界」に
  KLK-033欄の限定文とKLK-034欄（対応済み／未対応の一覧）が追加され、
  `_guarded_paths_from_expanded`docstring②の重複が統合され、
  `guarded_paths_after_shell_expansion`docstringにKLK-034ブロックが追加されている
  ことをファイル読み取りで確認した。`.claude/hooks/_ticket_lib.py`の差分は
  `is_spec_basename_fnmatch`docstringへの+6行のみ（判定式・シグネチャ無変更）。

## 7. 回帰リスクの評価

- DENY→allow 6形（`rm docs/SP*.md:1`等）はimplementation.md §4-1の新旧対照実測に
  基づき、いずれもbashが保護対象パスに一致させない形であることを確認した。
  旧denyは誤denyであり是正方向であることに同意する。「denyがallowへ転じない」という
  不変条件は成立しないという設計書の主張（§5・§7）は実測と整合している。
- リテラル形（`rm docs/SPEC.md:1`・`rm tickets/active/APP-001.md:1`）のDENY維持は
  `test_klk034_literal_path_with_caret_colon_still_deny`で実測固定済み（`PATHISH_RE`
  とのORが機能していることを確認）。
- POSIXクラスの過大近似による誤deny面の拡大（`?`への置換）は、tester追加テスト
  （§3）でallow方向の劣化が構造的に起きないことを直接実証した（長さ一致のみで
  denyへ倒れる＝安全側）。

## 8. Quality Gate（初回。840件時点）

pass。全件テスト840件OK（回帰0）。AC1〜AC8すべてに対応するテスト・記述面の
根拠を確認した。production code（`.claude/hooks/*.py`）は変更していない。

**この判定はreviewerにより差し戻された（review.md §1 Critical: 新設スキャナの
超線形・無上限コスト）。Phase 4対応後の再判定は§9・§10を正とする。**

## 9. Phase 4（reviewer差し戻し対応）検証

対象コミット: `248c782`（コード）→`f2dd344`（テスト9件）→`fad60dd`（設計書）→
`8cec2bf`（実装レポート）。差し戻し理由: `_scan_bracket_expression`／
`_bash_bracket_to_fnmatch` の走査コストが超線形・無上限で、約2万字の単一トークンで
hookの所要時間がPreToolUse既定タイムアウト（60s）を超え、fail-open方針と重なって
人間承認ゲートをすり抜けうるというもの（review.md §1）。

すべて `pre` = `e17c55d`（差し戻し対象。scratchpad `prefix_hooks` へ複製し
`git show e17c55d:.claude/hooks/guard_bash_writes.py` とのdiff0で複製の正しさを確認済み）、
`new` = 本worktree HEAD `8cec2bf` として、tester自身が本worktree上で実測した
（検証スクリプトはリポジトリ外のスクラッチ領域のみに置き、コミットしていない）。

### 9-1. Criticalの解消（自前実測。修正前後の対照）

reviewerが実測した形そのもの（`"[:"×k` 単一トークン）を tester が独立に再実測した。

| 対象 | 長さ | pre（e17c55d） | new（HEAD） | 倍率 |
|---|---|---|---|---|
| `_bash_bracket_to_fnmatch` 単体 | 8,000字 | 6.614s | 0.00224s | ×2,952 |
| 同 | 16,000字 | 49.231s | 0.00240s | ×20,510 |
| 同 | 24,000字 | 146.109s | 0.00668s | ×21,884 |
| end-to-end `find_violation("rm "+word)` | 8,000字 | 7.404s | 0.00444s（fallback denyのため） | ×1,668 |
| end-to-end `find_violation("rm "+word+" docs/SPEC.md")` | 16,000字 | 49.007s・**DENY** | 0.00785s・**DENY** | ×6,244 |
| 同 | 24,000字（reviewer実測形と同一） | 150.979s・**DENY** | 0.01987s・**DENY** | ×7,599 |
| `"["×n`（コロン無し。POSIXクラス要素なしでもO(n²)であることの確認） | 8,000字 | 3.086s | 0.00137s | ×2,252 |

- reviewer実測値（review.md §1-1）は16,000字=37.0s（単体）／38.33s（end-to-end）・
  24,000字=118.7s（end-to-end）。tester実測（本worktree・本環境）はそれより大きい値
  （16,000字=49.0〜49.2s・24,000字=146〜151s）だが、**桁は一致**しており
  「約2万字でPreToolUse既定タイムアウト60sを大きく超える」という結論は
  environment differenceに関わらず成立する。修正後はいずれも0.02s未満で、
  **DENYという判定内容は修正前後で一致**（=Criticalの核心である「timeoutで
  fail-openに落ちる前にdenyを返せる」ことを実測で確認）。
- サブプロセス経由（実際のhookエントリポイントを起動する`_util.run_script`。
  Python起動オーバーヘッドを含む）でも24,000字end-to-endが**0.064〜0.103s**
  （3回計測）であり、`test_klk034_bracket_scan_cost_regression_end_to_end`の
  しきい値15.0sに対して約150〜230倍の余裕がある。単体テストのしきい値5.0sも
  実測0.002〜0.007sに対して約700〜2,500倍の余裕。→ **時間しきい値2件は
  現実的な環境ゆらぎで不安定になる可能性は極めて低い**と判断する。

### 9-2. 「戻り値不変」の主張の検証（修正前後の出力対照）

`_scan_bracket_expression`の走査範囲限定（`rfind("]")`による早期return・`while`条件・
`find`の第3引数）が`_bash_bracket_to_fnmatch`の戻り値を変えないという主張を、pre/new
両実装に同一入力を与えて直接対照した。

- 総当たり: alphabet `[]^!:.S`（7文字）× 長さ1〜5 = **19,607パターン**、不一致
  **0件**。
- ランダム: alphabet `[]^!:.=xS/`（10文字、`x`/`S`/`/`/`=`を含む）× 長さ1〜40 ×
  **20,000トライアル**（seed固定・再現可能）、不一致 **0件**。
- 境界形個別確認（`]`を含まない語・`]`が`[`より前にある語）: `"[abc"`・`"]abc["`・
  `"]]][[["`・`"a]b[c"` の4形すべてpre/new一致。
- 結論: **本worktreeで実測した範囲では戻り値不変の主張に反例なし**（全19,607＋
  20,000＋4件が一致）。

### 9-3. deny方向フォールバックの正しさ・しきい値境界の精度

- `MAX_BRACKET_SCAN_WORK = 20000`。しきい値の**直下**（積20,000。`"["×20+"a"×979`、
  長さ999）は正規に走査され、実際に一致しない語は**allow**を維持し、同コマンドに
  実際のdeny対象（`docs/SPEC.md`）を追加すれば**deny**（precision維持、fallback
  未発動）。しきい値**直上**（積21,000。1文字違いの`"["×21+"a"×979`）は
  fallbackが発動し単独でも**deny**（安全側）、かつ`cat`（読み取り専用head）では
  **allow**（fallbackは書き込み判定自体を変えない）。
- **実際に意味論的に一致する/一致しない語を使った境界確認（tester独自追加。設計書・
  implementer報告にはこの形の実測は無かった）:** `"[[:upper:]]"×5+".md"`
  （SPEC.mdとは長さ不一致＝常にallowが正しい）にフィラーを付加し、積が
  **ちょうど20,000**（フィラー1936字、候補長2000字）で**allow**（正しい。
  fallback未発動・精度維持）、フィラーを1字増やして積**20,010**（候補長2001字）で
  **deny**（fallback発動。実際は不一致だが安全側へ倒れる＝設計書§6リスク表が
  明記する「low」リスクそのもので新しい欠陥ではない）ことを確認。
- brace展開×ブラケット一致の組合せ（8通りの分岐のうち1つだけがSPEC.mdへ長さ一致する
  形）で、combo=8・product=192（しきい値に無関係な小さい値）でも実際に一致する
  分岐が検出されdeny、全分岐が不一致になるよう変更するとallowになることを確認
  （brace展開経路とブラケット正規化の組み合わせが正しく機能している）。
- degraded経路（`# don't`付与でlex失敗を誘発）でも同じ上限・同じ方向:
  しきい値超過の病的語を含む`rm`はdeny、同じ語を含む`cat`はallow
  （degraded_violationも`mentions_guarded_expanded`→`guarded_paths_after_shell_expansion`
  を共有関数として呼ぶため、正常経路と機構レベルで同一）。

### 9-4. 事前チェックがブレース展開の**前**の候補に対して行われることの安全性

review依頼で懸念された「展開後に`[`が増える形・ブレース直積と重なる形での抜け」を
検討した。`expand_braces`は各`{alt1,alt2,...}`群から**1つの選択肢を選んで置換する**
実装であり、raw candidate文字列は全選択肢の文字を字面上すべて含む（構文上の要請）。
したがって任意の1つの展開結果がもつ`[`出現数・長さは、raw candidateの`[`出現数・
長さを**超えない**（各展開はraw candidateの部分選択にすぎない）。tester作成の
4種の構成（`{[:,x}`×9＝512通り／`{[[[[,x}`×9＋末尾`]`5個／長い前後方文字列に
挟んだ形／単一群の一方の選択肢だけが長いブラケット列の形）で全て
`worst_expansion_metric <= candidate_metric` を実測確認（4/4）。理論上も
「rawがすべての選択肢を字面で保持する」という`expand_braces`の入力形式そのものから
導かれるため、**事前チェック（raw candidate単位）が抜けを生む経路は見当たらなかった**。

### 9-5. Missing Tests 4件（review.md §7）の実装確認

Phase 4(ii)（`f2dd344`）で以下がすべて実装済みであることをコード読み取り・
実行結果の両方で確認した。抜け・期待値の誤りは見つからなかった。

1. 上限境界＋fallback方向: `test_klk034_bracket_scan_work_within_limit_precision`・
   `..._exceeded_denies_conservatively`・`..._exceeded_allow_symmetry`・
   `..._exceeded_does_not_mask_existing_deny`（4件）。
2. `/`メンバー形end-to-end: `test_klk034_bracket_with_slash_member_allow`
   （`docs/[^/]PEC.md`・`docs/[/S]PEC.md`・`tickets/[^/]ctive/APP-001.md`）。
   tester独自にmktemp配下でbash実`echo`展開を確認し、いずれも非一致（リテラルの
   まま出力）であることを裏付けた＝allowが正しい。
3. `=`・`+`系の既知の限界（否定クラス側）:
   `test_klk034_negated_class_outside_charset_known_limitation_allow`
   （`docs/[[=S=]]PEC.md`・`docs/[^=]PEC.md`・`docs/[^+]PEC.md`）。tester独自に
   bash `echo`展開で確認し、3形とも`docs/SPEC.md`へ一致する（hookはallow＝
   既知の限界）ことを裏付けた。
4. 意味論乖離2形: `test_klk034_bracket_semantics_divergence_unit`。
   tester独自にbash実環境で`[![:]`（`[^[:]`の正規化後と同一）が一致させる
   ファイル名集合を実測（`S`・`[`・`]`・`x`に一致、`:`のみ不一致）し、
   Python `fnmatch.fnmatchcase`では`[`が不一致（`]`・`S`・`x`は一致、`:`は
   不一致）であることを直接実測。**bashが一致させる`[`だけをfnmatchが
   取りこぼす**という記述は正確であることを確認した。

### 9-6. 既存テストの非改変

`git diff develop...HEAD --numstat -- tests/` → `tests/test_guard_bash_writes.py`
439行追加・**0行削除**（Phase1/2/tester既存3件/Phase4(ii)9件すべて純追加）。
`tests/test_ticket_lib.py`は差分なし（完全無変更）。KLK-018/031/032/033系の既存
メソッドに変更はない。

### 9-7. 新規回帰の探索結果（tester独自）

- 早期return境界（`]`を含まない語／`]`が`[`より前にある語）: pre/new完全一致
  （§9-2参照）。誤allowを生む形は見つからなかった。
- 事前チェックの積がブレース展開前の候補に対して行われることの抜け: §9-4の通り
  理論・実測ともに反例なし。
- しきい値20000の直上・直下の精度: §9-3で意味論的に一致/不一致する実例を用いて
  確認済み。直上でのfallbackはdeny方向のみ（allow方向への劣化は無い）。
- degraded経路: §9-3の通り、正常経路と同じ関数（`guarded_paths_after_shell_expansion`）
  を共有するため機構的に対称。個別実測でも確認。
- 追加で検討したが反例が見つからなかった項目: `.claude/hooks/guard_bash_writes.py`の
  `MAX_BRACE_CHAR_COUNT`チェックとの順序（ブレース文字数チェック→ブラケット走査
  コストチェック→組合せ数チェックの順。いずれも同じdeny方向フォールバックへ
  合流するため順序自体は判定に影響しない）。

## 10. Quality Gate（Phase 4対応後・最終）

**pass**。全件テスト**849件OK**（差し戻し時点baseline 840件に対し回帰0）。
reviewer Critical（走査コストの超線形・無上限）はtester独自の再測定で解消を確認
（§9-1）。「戻り値不変」の主張は19,607＋20,000＋4件の新旧対照で反例なし（§9-2）。
deny方向フォールバックの正しさ・しきい値境界の精度をtester独自の意味論的境界形で
確認（§9-3）。ブレース展開前チェックの安全性を理論・実測両面で確認（§9-4）。
Missing Tests 4件はすべて実装済みで期待値も実bash真値と整合（§9-5）。既存テストの
非改変を確認（§9-6）。production code（`.claude/hooks/*.py`）はtesterは変更していない。
時間しきい値を持つテスト2件（5.0s／15.0s）は実測に対して700〜2,500倍の余裕があり、
環境ゆらぎによるフレークのリスクは低いと判断する。
