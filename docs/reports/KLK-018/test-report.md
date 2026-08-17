# KLK-018 テストレポート

生成: tester / 最終更新: 2026-08-17

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
