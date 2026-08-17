# KLK-018 テストレポート

生成: tester / 最終更新: 2026-08-17（reviewer差し戻し→implementer修正後の再検証を追記）

---

## 0. 再検証（reviewer差し戻し2回目対応・RecursionError修正の独立検証）

### 0-1. 全体テスト実行結果

```
$ python3 -m unittest discover -s tests -v
Ran 678 tests in 24.687s
OK
```

implementer修正後676件（差し戻し前672件＋implementer新規4件）＋tester追加2件＝678件、全件pass。
失敗・エラーなし。

### 0-2. Critical Issue修正の独立PoC検証（実装報告を鵜呑みにせず再現）

`.claude/hooks/guard_bash_writes.py`をサブプロセス起動し、reviewerと同様の実機PoCを
implementerの報告とは独立に再実施した（詳細スクリプトはコミット対象外・tmp scratchpad）。

- 修正前コード（commit `d094c82`時点の`guard_bash_writes.py`を複製）に対し、隣接ブレース
  1000〜5000個規模で`RecursionError`相当のフェイルオープン（`permissionDecision`が
  返らずallow）を再現。修正後コード（`9000bac`）では同一入力が全てdeny・実行時間
  約30msで返ることを確認（RecursionErrorは発生せず）
- **呼び出し経路の確認**: `_brace_combination_count`／`expand_braces`の呼び出し箇所を
  全文grepし、本番コード上の呼び出し元が`guarded_paths_after_shell_expansion`内の2箇所
  （事前チェック・try/except共に実装済み）のみであることを確認。バイパス経路は
  発見されなかった
- **閾値回避の可能性を確認**: `MAX_BRACE_CHAR_COUNT`は候補中の`{`出現数（構造的な
  再帰深さに直結する量）を直接カウントするため、カンマの有無・組み合わせ数に
  依存しない。境界値N=49/50/51/52でも`MAX_BRACE_COMBINATIONS`超過（直積2^N型のため
  N=10前後で既に超過）により別経路でdenyになることを確認し、閾値をわずかに下回る
  個数での再現は見つからなかった
- **重要な発見（新たなテストギャップ）**: implementer追加の
  `test_klk018_adjacent_braces_regression_does_not_mask_existing_deny`は、
  既存deny対象語を隣接ブレース語より**前**に置く語順のため、`any()`の短絡評価により
  隣接ブレース語（RecursionErrorを起こしうる語）を一度も評価しない。独立PoCで、
  修正前コードに対して**同じ語順**では確かにdenyになる（＝当該テストは修正前
  コードでも偶然passしてしまい、reviewerが指摘した「masking」シナリオを実際には
  判別できていなかった）ことを確認した。語順を逆転（隣接ブレース語を先に）すると
  修正前コードはallowへフェイルオープンし、修正後コードのみdenyを維持することを
  確認した（下記§0-4でテストとして追加・固定）
- **カンマ無し隣接ブレースでの再現**: `"{x,y}"`（直積で急増）以外に、カンマ無し
  `"{x}"`（bashが展開しないリテラル。旧実装の組み合わせ数見積もりは1のまま増えない
  独立した形）でも隣接1000個規模で修正前コードがallowへフェイルオープンし、
  修正後コードがdenyを維持することを確認した（下記§0-4で追加）

### 0-3. MAX_BRACE_CHAR_COUNT=50の誤deny予算への影響

既存の固定allowケース群（`test_klk018_erroneous_deny_budget_allow`の6件、
`test_klk018_brace_*_within_limit_allow`等）はいずれも`{`出現数が10未満であり、
本閾値到達には遠く及ばないため無影響（678件全件passで確認）。50個超の隣接
ブレースを使う正当なユースケースは設計書・investigator調査のいずれにも
記載が無く、想定される日常操作の範囲では影響なしと判断する。

### 0-4. Added Tests（本ラウンド追加分）

`tests/test_guard_bash_writes.py`へ2件追加（上記§0-2の発見に対応）:

- `test_klk018_adjacent_braces_regression_does_not_mask_existing_deny_blob_first`:
  既存deny対象語を隣接ブレース語より**後**に置く語順（`any()`の短絡評価を実際に
  回避する順）。修正前コードでは独立PoCでallowへ転じることを確認済み、修正後は
  deny維持を固定
- `test_klk018_adjacent_braces_regression_no_comma_literal_denies_conservatively`:
  カンマ無し隣接ブレース`"{x}"`×1000個（直積で組み合わせ数が増えない独立した形）
  でも修正後コードがdeny維持することを固定

いずれも修正前コード（複製）に対する独立PoCで実際にallow（フェイルオープン）に
転じることを確認した上で追加しており、恣意的に通るだけの弱いテストではない。

### 0-5. Regression Risks（本ラウンド）

- 新規2件・既存676件を含め678件全件pass。既存共有シンボル
  （`PATHISH_RE`／`guarded_paths`／`is_guarded_token`等）は本ラウンドでも無変更
- `_brace_combination_count`・`expand_braces`自体の非有界再帰構造は温存されたまま
  （implementerのRemaining Risksどおり）。将来この2関数を新しい呼び出し元から
  直接呼ぶ場合は同じ2段防御パターンの踏襲が必須（既存docstringに明記済み）
- 本ラウンドで発見した「語順依存の短絡評価によるテストの見かけ上のpass」は、
  今回追加した語順逆転テストで解消済み。ただし短絡評価（`any()`）自体の一般的な
  性質のため、将来同種の複合語検証を追加する際は同じ落とし穴に注意が必要
  （reviewerへの申し送り事項）

### 0-6. Quality Gate Status（本ラウンド）: **pass**

reviewerへの引き継ぎ可否: **可**。Critical Issue（RecursionError→フェイルオープン）
の修正を実装報告とは独立の実機PoCで再現・確認し、バイパス経路は発見されなかった。
テストギャップ（既存回帰テスト1件が語順により無力化されていた点）を発見し、
語順逆転・カンマ無し形の2件を追加して補強済み。reviewerへは§0-2「重要な発見」を
申し送り事項として明記する。

---

## 1. 全体テスト実行結果

```
$ python3 -m unittest discover -s tests -v
Ran 672 tests in 24.162s
OK
```

内訳: implementer完了時点668件（baseline 659 + 新規9） + tester追加4件
（`MAX_BRACE_DEPTH`／`MAX_BRACE_COMBINATIONS` 境界値テスト）= 672件、全件pass。
失敗・エラーなし。`LEGACY_DENY_COMMANDS`（実測130件）・`INVENTORY_CASES`
（実測92件）を含む。

## 2. 受け入れ条件（設計書 §9）とテストの対応

| AC | 内容 | 対応テスト |
|---|---|---|
| AC1 | ブレース展開（単純・直積・入れ子）deny | `test_klk018_brace_expansion_simple_deny`／`_direct_product_deny`／`_nested_deny`／`_no_comma_stays_literal_allow`（裏付け） |
| AC2 | 分断glob（`*`/`?`/`[...]`）・N3（guarded_write_target経由）・degraded対称性 | `test_klk018_fragmented_glob_deny`／`_write_target_deny`／`_spec_side_read_allow`／`test_klk018_degraded_mode_fragmented_glob_deny` |
| AC3 | パラメータ展開の限界明記・INV-SH-11 allow維持 | docstring（`.claude/hooks/guard_bash_writes.py:218-249`）・README.md（該当パラグラフ）を確認。`INV-SH-11`は`allow`のまま（テストファイル489-490行）。コード変更なしのため新規テスト不要 |
| AC4 | 誤deny予算（N1〜N4閉列挙＋固定allow） | `test_klk018_erroneous_deny_budget_allow`（6件）。tester追加の境界値テスト4件は下記§4参照（**N1〜N4外の新しいdeny経路を検出**） |
| AC5 | LEGACY_DENY_COMMANDS 130件回帰なし | 既存テストランナー内で実行・pass（全件discoverに含む） |
| AC6 | INV-SH-07/09を allow→deny | テストファイル481-486行で確認済み |
| AC7 | 全件pass | 上記§1（672件 OK） |

## 3. 特に確認してほしい事項（implementer申し送り）の検証結果

### 3-1. 設計書からの逸脱（`cat docs/SPEC*.md` が deny 例示 → 実測allow）

`segment_violation`（`.claude/hooks/guard_bash_writes.py:2375`以降）を確認。
`cat`は`ALLOWED_HEADS`の中でも追加規則（sed/awk/sort/uniq/find/git向けの分岐）を
一切持たないheadであり、`gate_hit`（言及ゲート）が真であっても
`head not in ALLOWED_HEADS`判定を通過した後は素通りしNoneを返す。既存の
`test_read_commands_allow`（`cat tickets/active/APP-001.md`がallow）と全く同型の
既存性質であり、KLK-018のゲート拡張（head単位の判定は無変更）で覆るものではない
ことをコード追跡で確認した。**実装の逸脱は妥当** — 設計書§9 AC2の例示文言側が
実際のhead挙動と整合していなかったための記述誤りと判断する。reviewerへ設計書
記述の修正要否確認を推奨（implementerと同じ申し送り）。

### 3-2. MAX_BRACE_DEPTH／MAX_BRACE_COMBINATIONS 境界値テスト（未追加分）

4件追加（詳細は下記§4・§5）。実測の結果、上限超過時のフォールバックは
`tickets/`を一切含まない語でも「一致し得る」ものとして扱われ、**非ホワイトリスト
head（`rm`等）と組み合わせると新たにdenyになる**ことを確認した。これは設計書
§9 AC4のN1（「ブレース展開後に**保護対象パスとなる語を含み**」）の文言を字面上
満たさない新しいdeny経路であり、N1〜N4の閉じた列挙に文字通りは収まらない。
設計書§6リスク表には「上限で超過時は安全側（一致とみなす）へ倒す」と記載され
低深刻度の許容トレードオフとして扱われているが、AC4は「列挙外の誤denyが1件でも
あればブロッカー」と明記しているため、**reviewerへの判断材料として明示**する
（発生条件が隣接ブレース6個以上・直積729通り等、通常のチケット操作では
まず出現しない形である点は付記する）。

## 4. Added Tests（詳細）

`tests/test_guard_bash_writes.py`へ4件追加（`TestGuardBashWrites`クラス末尾、
`test_klk018_erroneous_deny_budget_allow`の直後）:

- `test_klk018_brace_depth_within_limit_allow`: ネスト深さ4（`MAX_BRACE_DEPTH`と
  同値・境界内）→ 通常展開で非保護対象と判定されallow
- `test_klk018_brace_depth_exceeded_denies_conservatively`: ネスト深さ5
  （上限超）→ フォールバックによりdeny（§3-2参照）
- `test_klk018_brace_combinations_within_limit_allow`: 直積243通り
  （`MAX_BRACE_COMBINATIONS`=512未満）→ 実展開の結果allow
- `test_klk018_brace_combinations_exceeded_denies_conservatively`: 直積729通り
  （上限超）→ フォールバックによりdeny（§3-2参照）

各値は`guard._brace_combination_count`を用いて事前に実測し境界を確定した
（本レポート作成時にテスト作成用スクリプトで検証。スクリプト自体はコミット対象外）。

## 5. Edge Cases Verified

- ブレース展開: 単純／直積／入れ子／カンマ無し非展開（AC1）
- 分断glob: `*`／`?`／`[...]`／`guarded_write_target`経由／degraded mode対称性（AC2）
- 誤deny固定6件（awk/cut/sort/grep/cwd下awk/無関係ブレース）（AC4）
- `MAX_BRACE_DEPTH`／`MAX_BRACE_COMBINATIONS`の境界値4件（境界内allow・境界超deny）
- `cat docs/SPEC*.md`のhead依存対称性（read-only allow vs `rm`のdeny）

## 6. Regression Risks

- `LEGACY_DENY_COMMANDS`130件・既存235件（旧226件+9）・`INVENTORY_CASES`92件を
  含む672件全件pass。回帰なし
- 上記§3-2のフォールバックdenyは新規追加関数のみに閉じており、既存共有シンボル
  （`PATHISH_RE`／`guarded_paths`／`is_guarded_token`等）は無変更のため、
  KLK-018対象外の経路への影響はない
