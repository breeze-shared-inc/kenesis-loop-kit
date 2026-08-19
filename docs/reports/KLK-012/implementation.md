# KLK-012 implementation

生成: implementer / 最終更新: 2026-08-16

設計書 `docs/designs/KLK-012.md`（D1〜D7・§4 実装詳細・§9 受け入れ条件）に従い、
Phase 1〜3 を順に実装した。ブランチ `fix/KLK-012-hook-metrics-robustness`（develop `f271f71` 起点）。

---

## 1. Phase 別コミット

| Phase | コミット | 内容 | 対応AC |
|---|---|---|---|
| 1 | `3072feb` | `_ticket_lib.py`（`_normalize_path` / `_under_dir` / `is_ticket` / `_strip_comment` / `parse_frontmatter` / `read_hook_payload` / `as_dict`）＋ `tests/test_ticket_lib.py` | AC1(lib)・AC4・AC5(基盤)・AC7 |
| 2 | `f0416f7` | 5 hook の入口型正規化＋相対 Write の fail-open＋`guard_bash_writes` docstring 訂正＋5テストファイル | AC1(実証)・AC5・AC7 |
| 3 | `05738da` | `aggregate.py`（status イベントフィルタ・tz 正規化）＋ README＋CHANGELOG＋`test_metrics.py` | AC2・AC3・AC7 |

Phase 1 → 2 は共有ヘルパ（`read_hook_payload` / `as_dict`）の依存があるため順序固定。
Phase 3 はファイル的に独立するが AC7 のゲートを共有する。

---

## 2. 変更ファイル一覧（15ファイル・+539 / -42 行）

**プロダクションコード（9）**

| ファイル | 変更 |
|---|---|
| `.claude/hooks/_ticket_lib.py` | `_normalize_path` / `_under_dir` を追加、`is_ticket` 本体と docstring を置換（§4-1）／`_strip_comment` を追加し `parse_frontmatter` の2箇所へ適用（§4-2）／モジュール末尾へ `read_hook_payload` / `as_dict` を追加（§4-3 前半） |
| `.claude/hooks/validate_ticket_state.py` | main() 入口の型正規化（§4-3）／`reconstruct` の Write 分岐へ相対パス fail-open（§4-4）／未使用となった `import json` を除去 |
| `.claude/hooks/record_metrics.py` | main() 入口の型正規化＋`cwd` の非 str フォールバック（§4-3） |
| `.claude/hooks/check_loop_integrity.py` | main() 入口の型正規化＋`cwd` の非 str フォールバック（§4-3） |
| `.claude/hooks/guard_spec_writes.py` | main() 入口の型正規化のみ（§4-3）／未使用 `import json` を除去。**`is_spec` 本体は不変** |
| `.claude/hooks/guard_bash_writes.py` | main() 入口の型正規化（§4-3）／モジュール docstring 1文の事実訂正（§4-6-1）／未使用 `import json` を除去。**`find_violation` 以下の判定ロジックは1文字も変更していない** |
| `.claude/metrics/aggregate.py` | `parse_ts` の tz 正規化／`is_status_event` を追加／チケットループ先頭で `evs` を絞り込み／`now` を aware 化（§4-5） |
| `.claude/hooks/README.md` | `_ticket_lib.py` 行の共有ヘルパ列挙を更新（§4-6-2） |
| `CHANGELOG.md` | `[Unreleased]` の `### Fixed` へ1エントリ（AC1〜AC5＋AC6分離＋実測件数）（§4-6-3） |

**テストコード（6）**: `tests/test_ticket_lib.py` / `test_validator.py` / `test_metrics.py` /
`test_loop_integrity.py` / `test_guard_spec_writes.py` / `test_guard_bash_writes.py`

**変更なし（設計どおり）**: `scripts/batch_loop.py`・`.claude/settings.json`・
`_ticket_lib.tickets_dir_for`（§3 D3）・`guard_spec_writes.is_spec`（AC6 スコープ外）。
`tickets/`・`docs/SPEC.md` には一切触れていない。

---

## 3. 設計判断への準拠

- **D1（AC1）**: `os.path.normpath` による cwd 非依存の純字句正規化＋`_under_dir` による
  パスコンポーネント境界一致。`os.path.abspath` は使用していない（プロセス cwd 非依存を維持）。
  `mytickets/active/APP-001.md`・`docs/tickets_active/x.md` を誤判定しないことをテストで固定
- **D2（AC2）**: `is_status_event`（`type != "retry_reset"` かつ `to is not None` の論理積）で
  イベント列を絞り込む方式。単純な末尾除外は採らず、進行中チケットの現在ステータスが
  失われないことを専用テスト（`test_in_progress_status_kept_after_retry_reset`）で実証
- **D3**: `tickets_dir_for` は無変更（diff で確認済み。docstring 内での言及のみ）
- **D4（AC4）**: クォート状態を追跡する走査で `_unquote` の**前**に適用。クォート内 `#`・
  空白を伴わない `#`・未閉じクォートの3つを回帰ガードとしてテスト化
- **D5（AC5）**: 共有ヘルパへ一元化し、fail-open の出口（`allow()` / `sys.exit(0)`）は
  各 hook のローカルに残した（R4 の取り違え防止）
- **D6（AC1 副作用）**: 相対パスかつ実体不在の Write は `ALLOW`。絶対パスで実体不在の場合は
  従来どおり新規作成として扱う（両方をテストで固定）
- **D7（AC3）**: naive をローカル tz とみなして aware 化。`now` も `astimezone()`

---

## 4. 設計書と現物の差異（実装時に判断した点・3件）

いずれも設計の意図を変えない範囲の調整である。

1. **`TestIsTicket` は「新設」ではなく既存クラスへの追加とした。** 設計書 §4-7 は
   `TestIsTicket`（新設）と書いているが、設計執筆後にマージされた KLK-004 が
   `tests/test_ticket_lib.py` へ同名クラスを既に追加していた。同名クラスを2つ宣言すると
   後者が前者を隠蔽して KLK-004 のテストが実行されなくなるため、既存クラスへ AC1 の
   ケース群を追記し、クラス docstring へ KLK-012 の観点を1行足した。
   同様に `TestParsing` も既存クラスへの追加（設計書の指定どおり）
2. **未使用になった `import json` を3ファイルから除去した。** main() 入口の置き換えで
   `validate_ticket_state.py`・`guard_spec_writes.py`・`guard_bash_writes.py` の `json` が
   完全に未参照になったため（`grep -n "json\."` で0件を確認）。設計書の変更ファイル一覧の
   範囲内であり、判定ロジックには影響しない
3. **`guard_bash_writes.py` の docstring 訂正は1文を2行に分けた。** 原文が1行に収まらない
   長さになったため改行を1つ入れた。後続の「統一すると `ls tickets/active/` や
   `docs/SPEC.md` を取りこぼすため、統一しない。」は設計書の指示どおり保持している
   （KLK-010 D2 は有効なまま）

---

## 5. 実測テスト件数

| 時点 | 件数 | 差分 |
|---|---|---|
| 着手時（develop `f271f71`） | **494** | — |
| Phase 1 完了時 | **520** | +26 |
| Phase 2 完了時 | **541** | +21 |
| Phase 3 完了時（最終） | **546** | +5（合計 +52） |

`python3 -m unittest discover -s tests` → **Ran 546 tests / OK（failures 0・errors 0）**。
設計書 §4-7 は着手時 437件と記載しているが、これは設計執筆時（develop `2963be8`）の値であり、
その後 KLK-003・KLK-004・KLK-013 のマージでベースラインが 494件へ増えている。
AC7 の「437件＋追加分」は満たしている。

### 追加テストの内訳

| ファイル | 追加 | 主な観点 |
|---|---|---|
| `tests/test_ticket_lib.py` | +26 | AC1 の判定表12ケース（相対形・traversal・境界・Templates/_index/非md・バックスラッシュ）／AC4 の9ケース（コメント除去・クォート内 `#` 保持・未閉じクォート・ネストマップ・回帰）／AC5 の5ケース（`read_hook_payload` / `as_dict`） |
| `tests/test_validator.py` | +7 | 相対パスの不正遷移 deny（AC1 の実証）・相対の正当遷移 allow・相対×実体なし Write の allow・絶対×実体なし Write の deny（D6 の境界）・非 dict stdin / 非 dict `tool_input` / 非 str `file_path` |
| `tests/test_metrics.py` | +11 | Recorder: 相対パス記録・非 str `cwd` フォールバック・非 dict 3種／Aggregate: done＋末尾 `retry_reset`・進行中＋末尾 `retry_reset`・`retry_reset` のみ・tz 混在（dwell 経路）・tz 混在（in_progress 経路） |
| `tests/test_loop_integrity.py` | +3 | 非 dict stdin・不正 JSON・非 str `cwd` のフォールバック（検査は従来どおり働く） |
| `tests/test_guard_spec_writes.py` | +3 | 非 dict stdin・非 dict `tool_input`・非 str `file_path` |
| `tests/test_guard_bash_writes.py` | +3 | 非 dict stdin・非 dict `tool_input`・非 str `command` |

### 追加テストの回帰価値の確認（実測）

- **AC2・AC3**: `aggregate.py` を変更前（`HEAD`）へ一時的に戻して `TestAggregate` を実行したところ、
  新規5件が**すべて失敗**（`TypeError: can't subtract offset-naive and offset-aware datetimes` 2件・
  `現在進行中` に `None` や done チケットが出る 3件）。復元後は全件パス。バグを実際に検出する
- **AC1**: 変更前の `is_ticket` は `tickets/active/APP-001.md` に対して False を返すため、
  `test_relative_path_illegal_transition_deny` は変更前には allow（＝失敗）になる

---

## 6. 現物データに対する回帰確認（テスト以外の実測）

設計の R2・R3（AC4 の over-strip）と AC1 の「絶対形の既存判定は不変」を、
**実在するファイル**に対して機械的に確認した（いずれも読み取り専用のスクリプトを
スクラッチ領域で実行。リポジトリには残していない）。

1. **frontmatter パースの差分ゼロ**: メインworktreeと本worktreeの実チケット（`active` / `done`）と
   `docs/designs/*.md` の計 **49ファイル**について、旧パーサと新パーサの出力 dict を比較 → **差分 0**
2. **`is_ticket` の判定差分ゼロ（絶対パス）**: 両worktree配下の全ファイル **221件**の絶対パスで
   旧実装と新実装の判定を比較 → **差分 0**（緩和は相対形と traversal 是正にのみ作用している）

---

## 7. 残存リスク・申し送り

- **R10（設計書既知）**: 相対パスのチケットでは `tickets_dir_for` が `None` を返すため、
  サイドカー由来の prior（ドリフト耐性のある prior）と in_progress 上限ゲートは fail-open で
  効かない。「検証ゼロ」から「ファイル内容ベースの検証あり」への改善であり後退ではないが、
  相対形では強制が部分的である。`is_ticket` の docstring に明記済み・KLK-020 へ申し送り
- **R2（設計書既知）**: 未クォートの値に「空白＋`#`」を書くと切り詰められる
  （`title: fix #123` → `fix`）。YAML の正しい解釈と一致する方向であり、hook が検証するのは
  `status`・`retry_counts`・必須キーの存在のみ。テンプレートは `title` をクォートしている。
  実在49ファイルで差分ゼロを確認済み
- **R5（競合）**: `guard_bash_writes.py` を対象とする未着手チケット（KLK-014・015・017・018・019）は
  本チケットの develop マージ後に着手すること。本チケットの変更は main() 入口・docstring 1文・
  未使用 import の3点に限定してあるため、コンフリクト面は小さい
- **申し送り3（設計書 §11）**: `aggregate.py` の `"…Z"` 形式 ts は Python 3.11 未満で解析できず
  イベントが黙って集計から落ちる（クラッシュはしない）。本チケットでは対応していない
- **AC6 は未実装（人間承認によりスコープ外）**: `guard_spec_writes.is_spec` は1文字も変更していない。
  切り出し先は KLK-020
