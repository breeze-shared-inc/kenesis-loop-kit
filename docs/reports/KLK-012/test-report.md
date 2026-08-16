# KLK-012 test-report

生成: tester / 最終更新: 2026-08-16

対象コミット: `3072feb`（Phase1）→ `f0416f7`（Phase2）→ `05738da`（Phase3）→ `83d7873`（レポート外部化）
ブランチ: `fix/KLK-012-hook-metrics-robustness`

---

## 1. テスト実行結果（実測）

```
$ python3 -m unittest discover -s tests
Ran 546 tests in 17.817s
OK
```

failures 0 / errors 0。implementer 報告の546件と一致（着手時494 → Phase1 520 → Phase2 541 → Phase3 546）。

---

## 2. 追加テストの「空振りでないこと」の独立裏取り

implementer は aggregate.py（Phase3・AC2/AC3）についてのみ「変更前へ戻すと新規5件が失敗」を報告していた。
本チケットの指示に従い、**Phase1・Phase2 を含む52件全件**について、pre-fix コード（develop `f271f71` 時点の
`.claude/hooks/*.py`・`.claude/metrics/aggregate.py`）と現行の新規テストファイルを組み合わせて再実行し、
どのテストが実際にバグを検出するか（fail-before/pass-after）を確認した。

手法: スクラッチ領域に `sandbox_repo/.claude/{hooks,metrics}`（`f271f71` 時点のプロダクションコード）＋
`sandbox_repo/tests`（現行の新規テストファイル一式）を組み、
`python3 -m unittest tests.test_ticket_lib tests.test_validator tests.test_metrics tests.test_loop_integrity tests.test_guard_spec_writes tests.test_guard_bash_writes`
を実行（worktree のプロダクションコードは一切変更していない）。

結果: **29件が pre-fix コードで failures/errors**（現行コードでは全件 pass）。内訳:

| ファイル | fail-before/pass-after 件数 | 主な内容 |
|---|---|---|
| `test_ticket_lib.py` | 8 | `TestPayloadHelpers` 4件（`read_hook_payload`/`as_dict` 未実装でImportError系）／`TestIsTicket` 相対形3件・traversal是正1件 |
| `test_ticket_lib.py`（`TestParsing`） | 4 | インラインコメント除去・クォート付き末尾コメント・ネストマップのコメント吸収 |
| `test_validator.py` | 3 | 相対パス不正遷移deny（AC1中核）・非dict stdin・非str file_path |
| `test_metrics.py`（Aggregate） | 5 | done+末尾retry_reset・進行中+末尾retry_reset・tz混在dwell・tz混在in_progress・retry_reset onlyチケット |
| `test_metrics.py`（Recorder） | 4 | 相対パス記録・非dict stdin・非str file_path・非str cwd |
| `test_loop_integrity.py` | 2 | 非dict stdin・非str cwdのフォールバック |
| `test_guard_spec_writes.py` | 2 | 非dict stdin・非str file_path |
| `test_guard_bash_writes.py` | 1 | 非dict stdin |

残り23件は「回帰ガード」（絶対形・Templates/_index/非md除外・未閉じクォート非除去・空白なし`#`保持・
D6境界の絶対パスdeny等、pre-fixでも既に正しい挙動を固定するテスト）および偶発的に安全側だった
入力型（例: `guard_bash_writes.py` は `find_violation` 呼び出しが既存の broad try/except に
包まれていたため非str commandでも例外経由でfail-openしていた）で、pre-fixでもpassする。
これは設計書 D5 が明記する「(b)(c) は外側だけ塞いで内側は素通りという非対称を残さないための拡張」
の性質どおりであり、空振りではなく意図した回帰ガードである。

---

## 3. AC別の実機再現・実証（自分で hook を直接起動）

チケットの「再現手順」①〜⑤を、スクラッチ領域に作った合成チケット・合成 stdin ペイロードを
新旧2つの hook 実装（`f271f71` 時点 vs 現行 HEAD）へ直接投入して比較した。

### AC1（is_ticket・相対パスdeny）— 中核

- 合成チケット `APP-001.md`（status: design_done）をサンドボックスの `tickets/active/` へ配置し、
  `validate_ticket_state.py` へ相対 file_path（`tickets/active/APP-001.md`）で
  `status: done`（不正遷移）を含む Write payload を投入。
  - **現行 HEAD**: `permissionDecision: deny`（理由: `不正な状態遷移: design_done → done`）
  - **pre-fix (`f271f71`)**: rc=0・無出力（=allow。素通り＝再現手順①の再現を確認）
- 同じ相対パスで正当遷移（`design_done → implementation_done`）: 現行 HEAD で allow（過検知が無いことを確認）
- `is_ticket` 単体を新旧で12ケース比較（絶対形・相対形・`./`・サブディレクトリ・traversal・
  コンポーネント境界・Templates/_index/非md・バックスラッシュ）:
  pre-fixは3ケースで期待値と不一致（相対形2件がFalse＝再現手順①、traversal是正1件が誤ってTrue）。
  現行HEADは12ケース全て一致。

### D6（相対×実体なし=allow／絶対×実体なし=deny）

- 相対パス・実体なしの Write（新規チケットのふりをした status:done）: 現行HEAD allow（fail-open）
- 絶対パス・実体なしの Write（同内容）: 現行HEAD deny（`新規チケットの初期 status は todo である必要があります`）
  — D6が絶対パスの既存挙動を壊していないことを確認

### AC5（非dict stdin・5 hook）

- `validate_ticket_state.py` / `record_metrics.py` / `check_loop_integrity.py` /
  `guard_spec_writes.py` / `guard_bash_writes.py` の5本すべてに `[]` / `"x"` / `3` / `null` を投入
  - **現行HEAD**: 全20パターンで rc=0・無出力
  - **pre-fix**: 全20パターンで rc=1・`AttributeError`（`'list'/'str'/'int'/'NoneType' object has no attribute 'get'`）
    — 再現手順⑤を5 hook全件で実機確認

### AC4（コメント除去・over-strip回帰ガード）

`_ticket_lib.parse_frontmatter` を新旧で直接比較（`sys.path` 切替でモジュール読み込み）:

| 入力 | pre-fix | 現行HEAD |
|---|---|---|
| `status: todo # note` | `'todo # note'`（VALID_STATUS外でdeny相当・再現手順④） | `'todo'` |
| `title: "issue #123 fix"` | `'issue #123 fix'`（**修正前から正しい**） | `'issue #123 fix'`（**回帰なし**） |
| `title: "issue #123 fix" # trailing comment` | `'"issue #123 fix" # trailing comment'`（`_unquote`不発火） | `'issue #123 fix'` |
| `title: C#sharp`（空白なし`#`） | 保持 | 保持（回帰なし） |
| `title: "a # b`（未閉じクォート） | `'"a # b'`（無変更） | `'"a # b'`（**除去しすぎない**ことを確認） |
| `retry_counts: # コメント` + ネスト2キー | ネストキー欠落 | ネストdict正しく取得 |

D4が要求する「クォート内`#`は修正前から動作していた」という前提を上記表で直接確認し、
現行HEADが**その挙動を壊していない**（over-strip無し）ことを実証した。

### AC2・AC3（aggregate.py）— 独立検証

implementer 報告とは別に、5シナリオ（done+末尾retry_reset同一ts／進行中+末尾retry_reset／
tz混在dwell経路／tz混在in_progress経路／retry_reset onlyチケット）を合成した `.metrics.jsonl` を
新旧 `aggregate.py` へ投入して比較。

- **pre-fix**: `TypeError: can't subtract offset-naive and offset-aware datetimes` で rc=1
  （全シナリオ投入時）。tz混入シナリオを除いた3シナリオ（A/B/E）のみでも:
  「現在進行中」に done チケット（SCEN-A）が `None` 経過として誤表示（**AC2二重計上を再現**）、
  進行中チケット（SCEN-B）の現在ステータスが `None` に消失（**D2の落とし穴を再現**）、
  フェーズ別滞留に `design_done 平均0m(n=1)` `done 平均0m(n=1)` という0秒ノイズが混入
- **現行HEAD**: 全シナリオ含めて rc=0 で完走。SCEN-Aは「現在進行中」に出ずサイクルタイムに1件のみ計上、
  SCEN-Bは「現在進行中」に `design_done` の正しいステータスで表示、SCEN-D（末尾のみtz-aware）も
  「現在進行中」に正しく出現、SCEN-E（retry_resetのみ）はどちらの節にも出ずクラッシュもしない

### 実データ回帰確認（独立実施）

メインツリー（`/home/bzg55/workspace/breeze/kenesis-loop-kit`）の実チケット（`tickets/active/`・
`tickets/done/` 現存分）と `docs/designs/*.md` 計37ファイルについて、新旧 `parse_frontmatter` と
絶対パス `is_ticket` を比較 → **差分0**（implementer報告の49ファイル/221ファイルとは対象時点が異なるが、
現時点のメインツリーで独立に再確認し一致）。

---

## 4. 見つかった問題

なし。設計書（D1〜D7・§4実装詳細）と現物コードの diff（`git diff f271f71 HEAD`）を全変更ファイルで
突き合わせ、設計逸脱は無いことを確認した。`is_spec` 本体・`tickets_dir_for`・`find_violation` 以下・
`scripts/batch_loop.py`・`.claude/settings.json` はいずれも無変更（diffで確認）。
