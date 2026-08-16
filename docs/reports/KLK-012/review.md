# KLK-012 レビュー詳細

生成: reviewer（代筆: orchestrator） / 最終更新: 2026-08-16
対象: ブランチ `fix/KLK-012-hook-metrics-robustness` / HEAD `2c62624`（develop `f271f71` 起点）
判定: **approved**（Critical 0 / High 0 / Medium 5）

要点はチケット `KLK-012` の「レビューメモ」を参照。本ファイルは全文。

## 1. 検証方法

テストの主張を信じず、develop（`f271f71`）時点のコードをスクラッチ領域へ取り出し、新旧を同一入力で並走させて差分を取る方針で検証した。

1. `is_ticket` — 34パスの新旧比較
2. `validate_ticket_state` — 4種の綴り × 実体あり/なし = 8パターンのサブプロセス実行比較
3. `parse_frontmatter` — 実チケット36ファイル（メインツリー active/done ＋ designs）の新旧比較＋14の単行ケース＋ネストマップ2ケース
4. `aggregate.py` — 5シナリオの合成 `.metrics.jsonl` で新旧の rc と「現在進行中」節を比較
5. 5 hook × 12種の異常 payload = 60実行の fail-open 確認
6. 全テストスイート再実測（**546件 OK**・`git status` クリーン）

## 2. AC 別の検証結果

### AC1（相対パス素通り）— 充足

`is_ticket` の新旧差分は7件で、すべて設計どおり。

| パス | 旧 | 新 | 評価 |
|---|---|---|---|
| `tickets/active/A.md` | False | True | AC1 中心・意図どおり |
| `tickets/done/A.md` | False | True | 意図どおり |
| `tickets/active/sub/A.md` | False | True | 意図どおり |
| `tickets/active//A.md`・`tickets//active/A.md` | False | True | normpath の副次効果・妥当 |
| `tickets/active/.hidden.md` | False | True | 絶対形と整合（旧も絶対形なら True） |
| `/repo/tickets/active/../../evil.md` | **True** | **False** | 唯一の True→False。実チケットではないため強制の喪失なし |

- **偽陽性なし**: `mytickets/active/A.md`・`/repo/mytickets/active/A.md`・`docs/tickets_active/A.md`・`ticketsactive/A.md`・`atickets/active/A.md` はすべて False（新旧一致）
- **除外の維持**: `Templates/`（相対・絶対とも）・`_index.md`（相対・絶対とも）・非 `.md`・空文字列・`.`・`/` はすべて False
- Windows 綴り `C:\repo\tickets\active\A.md` は True で不変
- 正当な再入 traversal は維持: `/repo/tickets/active/../done/A.md` → True、`x/../tickets/active/A.md` → True
- **実証**（validator サブプロセス）: 相対パス（実体あり）で `design_done → done` は **deny**、`design_done → implementation_done` は allow。Write 分岐でも相対パス × 実体ありは deny（`reconstruct` は `exists` を先に、`isabs` を後に見る正しい順序）

### AC2（二重表示）— 充足

| シナリオ | 旧 | 新 |
|---|---|---|
| done → 同一 ts の retry_reset | 現在進行中に `A-001 None 経過 …`（サイクルタイムと二重計上） | 「なし」・出力に `None` なし・サイクルタイムには計上 |
| design_done → retry_reset（進行中） | `B-001 None` | `B-001 design_done`（現在ステータスを保持） |
| retry_reset のみのチケット | `E-001 None` | 集計対象外（IndexError なし） |

`is_status_event` は `type != "retry_reset" and to is not None` の論理積で、将来の非 status イベントにも耐える。`aggregate.py` は元々 retry_reset を明示的に集計・表示していないため、フィルタによる情報欠落は「status を伴わないイベント」に限られる。

### AC3（tz クラッシュ）— 充足

- dwell 経路（`+09:00` を中間イベントに混入）: 旧 rc=1 `TypeError: can't subtract offset-naive and offset-aware datetimes` → **新 rc=0 で完走**、サイクルタイム・滞留時間とも出力
- in_progress 経路（末尾イベントのみ aware）: 旧 rc=1 → **新 rc=0** で「現在進行中」に行が出る
- naive をローカル tz とみなす解釈は `record_metrics` の記録形式（naive ローカル）と一致
- `"…Z"` 非対応は設計で明示的に対象外（クラッシュせず黙って落ちる既存挙動のまま）

### AC4（コメント除去）— 充足

**実チケット・設計書36ファイルで新旧の parse 結果差分 0**（reviewer が独立に再実行して確認）。

単行ケース（旧 → 新）:

| 入力 | 旧 | 新 | 評価 |
|---|---|---|---|
| `status: todo # comment` | `'todo # comment'` | `'todo'` | AC4 中心 |
| `title: "issue #123 fix"` | 変化なし | 変化なし | **over-strip 回帰なし** |
| `title: 'single #q'` | 変化なし | 変化なし | シングルクォートも保持 |
| `title: "issue #123 fix" # trailing` | `'"issue #123 fix" # trailing'` | `'issue #123 fix'` | investigator の追加発見が解消 |
| `title: "a # b`（未閉じ） | `'"a # b'` | `'"a # b'` | **非除去** |
| `title: it's a plan # note` | そのまま | そのまま | アポストロフィで未閉じ扱い＝安全側 |
| `title: C#sharp` / `status: todo#nospace` / `url: https://x/#frag` | 保持 | 保持 | 空白なし `#` は保持 |
| `status: todo\t# tab comment` | — | `'todo'` | タブも空白として扱う |
| `tags: [a, b] # note` | — | `'[a, b]'` | |
| `title: he said "hi # there" ok` | 保持 | 保持 | |

ネストマップ: `retry_counts: # コメント` 配下3キーが旧は全欠落 → 新は正しく dict 化。ネスト値の末尾コメント `1 # note` → `'1'`。

4つの呼び出し元（validator / recorder / integrity / batch_loop）への波及はすべて「誤 deny・誤検知・fail-closed 停止の解消」方向。**コメントで検証を迂回することはできない**（除去後の値そのものが `VALID_STATUS` で検証される）ことをコードで確認。

### AC5（非 dict fail-open）— 充足

5 hook × 12 payload（`[]` / `"x"` / `3` / `null` / 不正 JSON / `tool_input` 配列 / `file_path` 整数 / `file_path` null / `cwd` 整数 / `command` 整数 / `command` 配列 / `{}`）= **60実行で、いずれも rc=0・stdout/stderr 空**。

唯一の例外は「絶対パスの実チケット × content 無し」を含む payload で validator が deny を返したケースで、これは `cwd` の型とは無関係の正当な deny（新規チケットの frontmatter 欠落）。

- fail-open の出口が hook ごとに正しい: PreToolUse 3本は `allow()`、PostToolUse / Stop 2本は `sys.exit(0)`（設計 R4 の取り違えなし）
- `read_hook_payload` / `as_dict` は既存の dict 入力に対して完全に透過
- **fail-open の範囲は「入口の型」に限定**されており、本来 deny すべき dict 入力が allow へ落ちる箇所は無い

### AC7 — 充足

546件（failures 0 / errors 0）をレビュー時に再実測。追加52件、着手時494件。

### AC6 — 対象外（人間承認済み）

`guard_spec_writes.py` の差分は main() 入口と `import json` 除去のみで、**`is_spec` 本体は不変**。設計 §9「reviewer の確認事項」(a)〜(d) すべて充足。

## 3. Medium リスク詳細

### M1（要記録）: D6 による deny → allow の転換

同一 payload での新旧比較（Write・`content` の status = `done`・新規扱い）:

| 綴り | 実体 | 旧 | 新 |
|---|---|---|---|
| 絶対パス | あり/なし | deny | deny |
| `tickets/active/APP-001.md` | あり | allow（**旧の全面バイパス**） | **deny** |
| `tickets/active/APP-001.md` | なし | allow | allow |
| `./tickets/active/APP-001.md` | あり | deny | deny |
| `./tickets/active/APP-001.md` | なし | **deny** | **allow** |
| `sub/tickets/active/APP-001.md` | なし（解決不能） | **deny** | **allow** |

失われる検査は「新規チケットの初期 status は todo」＋新規内容のスキーマ検証の2つ。**既存チケットの遷移検証は失われない。**

**総合評価は改善**: 最も素朴な相対形（`tickets/…`）が旧実装では既存チケットの不正遷移まで含めて全面素通りしていたのに対し、新実装では解決可能な相対形が完全に検証される。緩和されるのは「hook プロセスの cwd で解決できない相対パスの新規作成」のみ。

追加の緩和要因: (a) Write/Edit の `file_path` は実運用で絶対パス（`.metrics.jsonl` に通過実績）、(b) Stop hook `check_loop_integrity.check_ticket` が active/ 全件に `validate_schema` ＋ドリフト検知をかけるため、素通りした不正チケットはターン終了時に捕捉される。

指摘の本質は**記述精度の問題** — 設計 D6・CHANGELOG は「AC1 が新たに生む誤 deny の対策」としか書いていないが、実際には旧実装から存在した deny も1つ消している。KLK-020 で payload `cwd` を用いた相対解決を検討すれば、R10 と併せて閉じられる。

### M2: 設計 §5 の影響評価に4件目の呼び出し元が欠落

`is_ticket` の呼び出し元が設計では3件（validator / recorder / batch_loop）だが、**KLK-003 で追加された `scripts/list_tickets.py` が4件目**として存在する（設計執筆後に develop へマージされたため）。実挙動は無害と確認済み。KLK-020 の調査対象に加えること。

### M3: `parse_frontmatter` の副次変更が未固定

トップレベルの `title: # コメント`（値が丸ごとコメント）は旧 `'#コメント'` → 新 `{}`。`val == ""` 判定がコメント除去後に来るため、ネストマップとして開き後続のインデント行を取り込む。YAML 的には null が正しく `validate_schema` は必須キー空として検出する方向（安全側）だが、期待挙動としてテストで固定されていない。

### M4: `aggregate.py` のヘッダ件数と本文の不整合

status イベントを持たないチケットを `continue` で落とすが、ヘッダの「チケット数」には従来どおり計上されるため、件数と本文が一致しない状態が生じうる（実測確認）。観測性の穴というより軽微な不整合。

### M5（受容済み）: 未クォート値の over-strip

`title: fix #123` → `fix` は設計 R2 で受容済み（YAML 準拠方向）。ファイル自体は書き換わらず hook 側の解釈のみに影響することを確認。

## 4. Missing Tests

- **相対パス × 実体あり × Write 分岐**の deny（現状は Edit 分岐のみ）。手動では deny を確認したが、`reconstruct` の `exists` 判定と `isabs` 判定の順序が入れ替わっても既存テストは全通過してしまう
- `./tickets/active/X.md` × 実体なし = allow（M1 の意図的な緩和）を明示的に固定するケース
- M3（`key: # コメント` のみの行）の期待挙動を固定するケース

いずれも欠落による現在の不具合ではない。既存52件は fail-before/pass-after が tester により独立検証済みで、レビュー時に空振りでないことを再確認した。

## 5. 隣接チケットとの干渉

- **`guard_bash_writes.py`**: 変更は3ハンク・15行（docstring 2行への書き換え・`import json` 除去・main() 入口）のみ。**KLK-013 が書き換えた `is_readonly_script_call()` を含む `find_violation` 以下は無変更**。docstring 訂正は「統一しない」文を保持しており KLK-010 D2 と整合
- **KLK-017**（docstring 記述の重なり）は設計 §11 申し送り4 のとおり本チケットのマージ後を出発点にすれば衝突しない
- **KLK-020 への入力**: D1・D3・R10 に加えて、本レビューの M1（旧 deny → 新 allow の3綴り）と M2（`scripts/list_tickets.py` が4件目の呼び出し元）を追加すべき

## 6. 残存限界 R10 の妥当性評価

**妥当と判断する。** 相対形では `tickets_dir_for` が None を返すためサイドカー prior と in_progress ゲートが効かないが、

- 相対形は従来**検証ゼロ**（`is_ticket` が False で validator ごと素通り）だったため、ファイル内容ベースの prior による遷移検証・スキーマ検証が働くようになった時点で純増
- `tickets_dir_for` を相対対応させると `record_metrics` が hook プロセスの cwd 依存の場所へ `.metrics.jsonl` を書きうる（**サイドカー分裂＝ドリフト検知の基盤破壊**）ため、D3 の「変更しない」判断は安全側で正しい
- 限界が `is_ticket` の docstring・設計 §6 R10・CHANGELOG の3箇所に明記され、実装より強い保護を主張していない

ただし M1 と併せて「相対パスは部分的にしか強制されない」ことが KLK-020 の必須入力になる点は明確に申し送るべき。

## 7. implementer 自己申告の差異3件

いずれも**妥当**と判断。

1. `TestIsTicket` を新設せず既存クラスへ追記（KLK-004 が同名クラスを追加済みで、2重宣言だと KLK-004 のテストが隠蔽されるため）
2. 未参照になった `import json` を3ファイルから除去 — 残存利用が無いことを全ファイルで確認済み（`record_metrics` / `check_loop_integrity` / `_ticket_lib` では正しく保持）
3. `guard_bash_writes` docstring の2行化

## 8. ロールバック懸念

なし。`.metrics.jsonl` / `.metrics_state.json` の形式不変・`.claude/settings.json` 不変で、コードを戻すだけで完全復帰する（設計 §8 のとおり）。ファイル単位の部分ロールバックも可能（`aggregate.py` は独立、`is_ticket` を戻しても D6 の fail-open は無害）。
