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

## 8. Quality Gate

pass。全件テスト840件OK（回帰0）。AC1〜AC8すべてに対応するテスト・記述面の
根拠を確認した。production code（`.claude/hooks/*.py`）は変更していない。
