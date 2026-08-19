# KLK-028 調査レポート（investigator）

## 0. 前提・スコープ確認
本チケットは KLK-012（`docs/designs/KLK-012.md`）の reviewer レポート（`docs/reports/KLK-012/review.md`）に基づくフォローアップ。M1・M2（KLK-020へ）、M5・R10（対応不要）は対象外として調査していない（チケット記載どおり）。

---

## 1. M3: `parse_frontmatter` の未固定な副次変更

**原因箇所**: `.claude/hooks/_ticket_lib.py` `parse_frontmatter`（303-332行目）のトップレベル分岐

```
323  key, _, val = raw.partition(":")
324  key = key.strip()
325  val = val.strip()
326  val = _strip_comment(val)      # ← コメント除去
327  if val == "":                  # ← 空値判定（除去の後）
328      data[key] = {}
329      current_map = key
330  else:
331      data[key] = _unquote(val)
```

326行目（`_strip_comment` 呼び出し）が327行目（`val == ""` 判定）より先に実行される順序に依存しており、「本来は空値（真にネストを開くべき行、例: `retry_counts:`）」と「コメントだけが書かれた行（例: `title: # コメント`）」を区別できない。

**現状の挙動（empirical, 2026-08-17実測）**:
```python
lib.parse_frontmatter("---\ntitle: # コメント\nstatus: todo\n---\n\n# body\n")
# => {'title': {}, 'status': 'todo'}
```
`title` が空dict（ネストマップ）になる。

**KLK-012前（想定）の挙動**: `docs/reports/KLK-012/review.md` M3 の記述および `docs/designs/KLK-012.md` D4 の記述（「`if val == "":`（ネストマップを開く判定）は**コメント除去の後**に行う」という設計変更点そのもの）から、KLK-012前は `_strip_comment` が存在しない/適用順が異なり、`val` は `"# コメント"`（非空）のまま `_unquote` を通り文字列として保持されていたと推定される。これを模した簡易再現コードで実測すると `{'title': '# コメント', 'status': 'todo'}` となった（kind: empirical、ただし「KLK-012前の実コード」ではなく差分の再構成による近似実装での再現である点に注意）。

**YAML準拠時の挙動（empirical, PyYAML 6.0.1で確認, 2026-08-17）**:
```python
import yaml
yaml.safe_load("title: # comment\nstatus: todo\n")
# => {'title': None, 'status': 'todo'}
```
YAML準拠では `title` は `None`（null）になる。`{}`（辞書）でも元の文字列保持でもない。

**取り込みの実際の機構（empirical確認済み）**: `current_map` は「非インデント行」に到達したときのみリセットされる（320行目）。312行目の空行/行頭コメント判定は `continue` するだけで `current_map` をリセットしないため、コメントのみの行の**直後に空行を挟んでも**、後続のインデント行は取り込まれる。
```python
lib.parse_frontmatter("---\ntitle: # コメント\n\n  x: 1\nstatus: todo\n---\n\n# body\n")
# => {'title': {'x': '1'}, 'status': 'todo'}
```

**影響範囲**:
- `validate_schema`（335-347行目）は `REQUIRED_KEYS` の「キーの存在」しか見ないため、`title` が `{}` であっても「存在する」ので必須キー欠落エラーにはならない（`title` 自体が壊れても検出はされない）
- 「安全側」に働くのは、**この現象によって別の必須キーの行そのものが取り込まれて独立したトップレベルキーとして登録されなくなった場合**であり、その場合は `validate_schema` が当該キーを「存在しない」として検出し deny する、という間接的な経路。ただし現行のチケットテンプレート（`tests/_util.py` `_TICKET_TEMPLATE` 相当の構造）では、唯一の真正なネストキーである `retry_counts` は自分自身の行（非インデント）で `current_map` を必ずリセットして開くため、標準的なテンプレート構造下では他キーの取り込みは再現しない。KLK-012レビューでの実チケット36ファイル比較（AC4関連）はこのM3固有の「scalar key + comment-only value」パターンを明示的に対象にしたものではないため、実チケットでの発生ゼロは確認されていない（未検証。根拠不足）

**既存テストのカバレッジ**: `tests/test_ticket_lib.py:65-75` の `test_comment_only_value_opens_nested_map` は `retry_counts: # コメント` という**元々ネストが正しい**キーのケースのみを固定しており、M3が問題にしている「scalar keyのcomment-only value」パターンは一件もテストされていない（確認済み・漏れ）。

---

## 2. M4: `aggregate.py` のヘッダ件数と本文の不整合

**原因箇所**: `.claude/metrics/aggregate.py`
- ヘッダ集計元: 112行目 `by_ticket = lib.group_events_by_ticket(events)`（フィルタ前）
- 本文フィルタ: 129行目 `evs = [ev for ev in evs if is_status_event(ev)]`、130-131行目 `if not evs: continue`（`is_status_event` は 64-71行目）
- ヘッダ出力: 180-182行目 `print("イベント数: %d / チケット数: %d%s" % (len(events), len(by_ticket), ...))`

`len(events)` と `len(by_ticket)` はいずれも106-112行目のフィルタ前データから計算されるが、本文の各セクション（サイクルタイム・滞留・差し戻し・改善ループ・blocked・現在進行中）は131行目の `continue` で status イベントを一つも持たないチケット（`retry_reset` のみ等）を完全に除外した後の集合を対象にしている。

**実測（empirical, 2026-08-17）**: `APP-001`（created→todoのみ）と `APP-050`（retry_resetのみ）の2チケット分のイベントを与えると:
```
イベント数: 2 / チケット数: 2
...
— 現在進行中 —
  APP-001          todo                 経過 68d 9h 51m
```
ヘッダは「チケット数: 2」だが、本文に登場するチケットは `APP-001` の1件のみで `APP-050` はどのセクションにも出現しない。

**既存テストのカバレッジ**: `tests/test_metrics.py:288-293` の `test_retry_reset_only_ticket_survives` はこの状況を作っているが、アサーションは「現在進行中」節が「なし」であること・「完了チケットなし」が出ることのみで、**ヘッダの「チケット数」の値そのものは一切検証していない**。ヘッダ・本文の不整合を固定するテストは無い（確認済み・漏れ）。

**補足（イベント数についても同型の潜在的不整合）**: チケット本文には「チケット数」しか明示されていないが、`len(events)` も同様にフィルタ前の生イベント総数であり、本文側に `len(events)` 相当を直接表示する箇所は無い。`retry_reset` イベントは本文のどのセクションにも一切現れないため、「イベント数」ヘッダは本文で説明のつかない数を含む点は同種の課題としてarchitectに申し送る（M4の主題は「チケット数」だが同じ根本原因を共有する）。

---

## 3. AC3: `reconstruct` の `exists`/`isabs` 順序依存とテスト欠落

**該当箇所**: `.claude/hooks/validate_ticket_state.py` `reconstruct`（58-84行目）のWrite分岐（61-70行目）

```python
if tool == "Write":
    new_content = tool_input.get("content", "")
    if os.path.exists(path):          # 63行目: 先にexists判定
        return new_content, read_file(path)
    if not os.path.isabs(path):       # 65行目: 次にisabs判定
        return ALLOW
    return new_content, None
```

`docs/designs/KLK-012.md` §4-4（D6）にこの順序が明示されている。

**実測による順序依存の証明（empirical, 2026-08-17, スクラッチ領域で検証・本リポジトリは未変更）**:
1. `.claude/hooks` と `tests` をスクラッチディレクトリへコピーし、`reconstruct` のWrite分岐で `isabs` 判定を `exists` 判定より先に行う版へ書き換えた
2. `python3 -m unittest tests.test_validator tests.test_ticket_lib tests.test_metrics` を実行 → **131件全て成功**（順序を入れ替えても既存テストは何も落ちない）
3. 相対パス（`tickets/active/APP-001.md`、cwd上に実体あり）で `status: design_done → done`（不正遷移）のWrite payloadを直接実行 → 順序入れ替え前は `deny`（既存の `test_relative_path_illegal_transition_deny` はEdit版で確認済みのロジックと同型）だが、入れ替え後は **rc=0・stdout空（=allow）** となり、本来denyすべき不正遷移がバイパスされることを確認

**既存テストのカバレッジ**: `tests/test_validator.py` の相対パス関連テスト（130-155行目）は
- `test_relative_path_illegal_transition_deny` / `test_relative_path_legal_transition_allow`: **Edit**分岐×実体あり
- `test_relative_path_missing_file_write_allow`: **Write**分岐×実体なし
のみで、「Write分岐×実体あり×相対パス」の組み合わせを専用に検証するテストは存在しない（確認済み・漏れ、reviewerの指摘と整合）。

---

## 4. AC4: `./tickets/active/X.md` × 実体なし = allow のテスト欠落

**該当箇所**: 同じ `reconstruct` のWrite分岐65-69行目（D6のfail-open本体）。`docs/designs/KLK-012.md` §3 D6 に設計意図の記載あり。

**既存テストとの差**: `tests/test_validator.py:143-148` の `test_relative_path_missing_file_write_allow` は `os.path.join("tickets", "active", "APP-777.md")` で `./` プレフィックス無しの相対形を使用している。`docs/reports/KLK-012/review.md` M1節の表では、`./tickets/active/APP-001.md`（ドット始まり）× 実体なし が「旧: deny → 新: allow」という**明示的な挙動反転**として特筆されており、これは無印の相対形（旧から allow）とは異なる遷移パターンである。現行コードでは `os.path.normpath` により両者は同一に正規化されるため機能的な差は無いが（`is_ticket` は `_normalize_path` を通す。`reconstruct` 自体は正規化前の生 `path` で `os.path.exists`/`os.path.isabs` を呼ぶが、Pythonの `os.path` 関数は `./` プレフィックスを透過的に扱うため挙動は一致する）、reviewerがD6の意図的緩和として名指しした**この綴り（`./` 明示形）**を固定するテストは存在しない（確認済み・漏れ）。

---

## 5. KLK-012の文脈（「実害軽微」「安全側」と判断された理由）

出典: `docs/reports/KLK-012/review.md`（最終更新2026-08-16）、`docs/designs/KLK-012.md`

- M3は「YAML的にはnullが正しく、`validate_schema` は必須キー空として検出する方向（安全側）」と評価されている。これは deny（fail-closed）に振れる方向のバグであり、誤って allow してしまう方向のバグではないことが「実害軽微」の判断材料になっている（review.md 128行目付近）
- M4は「観測性の穴というより軽微な不整合」と評価。`aggregate.py` はデバッグ/観測用ツールであり、hookのdeny/allow判定には影響しないため実害が軽微とされている（review.md 132行目付近）
- AC3・AC4のMissing Testsは「いずれも欠落による現在の不具合ではない」（review.md 144行目）と明記されており、reviewerは手動で実際のdeny/allow挙動を確認済みだが、その確認を自動テストとして固定していない、という位置づけ
- D4（`docs/designs/KLK-012.md` 189-206行目）は「`if val == "":` はコメント除去の後に行う」ことを明示的な設計判断として記載しており、これは `retry_counts: # コメント` の子キー欠落バグを閉じるための意図的な選択であり、M3（scalar keyへの副作用）はこの選択の**認識された代償**ではなく、reviewerが後から発見した副次効果である

---

## ソース一覧

| kind | ref | summary | confidence |
|---|---|---|---|
| codebase | `.claude/hooks/_ticket_lib.py:303-332` | `parse_frontmatter` のトップレベル分岐。326-327行目の順序がM3の直接原因 | high |
| codebase | `.claude/metrics/aggregate.py:64-71,111-131,179-182` | `is_status_event`／`main` のヘッダ・本文フィルタの非対称がM4の直接原因 | high |
| codebase | `.claude/hooks/validate_ticket_state.py:58-84` | `reconstruct` のWrite/Edit分岐。AC3・AC4の該当箇所 | high |
| codebase | `tests/test_ticket_lib.py:1-488`（特に65-75行目） | `parse_frontmatter` の既存テスト網羅範囲。scalar key の comment-only 値は未カバー | high |
| codebase | `tests/test_validator.py:1-269`（特に130-156行目） | 相対パス関連テストの網羅範囲。Write×実体あり、`./`明示形×実体なしは未カバー | high |
| codebase | `tests/test_metrics.py:150-325`（特に288-293行目） | `TestAggregate` の既存テスト。ヘッダ件数の検証が無いことを確認 | high |
| empirical | 2026-08-17実行, `python3 -c` による `parse_frontmatter` 直接呼び出し | `title: # コメント` が `{}` になること、空行を挟んでも取り込みが継続することを実測 | high |
| empirical | 2026-08-17実行, PyYAML 6.0.1 `yaml.safe_load` | YAML準拠実装では `title: # comment` が `None` になることを実測 | high |
| empirical | 2026-08-17実行, スクラッチ領域で `reconstruct` のexists/isabs順序を入替え、`python3 -m unittest tests.test_validator tests.test_ticket_lib tests.test_metrics`（131件成功）＋ 相対パス×実体あり×Writeの直接サブプロセス実行 | 順序を入れ替えても既存テストは全通過し、かつ相対パス既存チケットの不正遷移がdeny→allowへ反転することを確認。本リポジトリのファイルは変更していない（コピー先でのみ検証） | high |
| local_docs | `docs/reports/KLK-012/review.md`（2026-08-16付） | KLK-012 reviewerの全文レポート。M1-M5・Missing Tests・AC別検証結果の一次記録 | high |
| local_docs | `docs/designs/KLK-012.md` §3 D4・D6、§4-4・4-7 | M3の設計意図（D4）とAC3/AC4のfail-open設計意図（D6）、既存テスト設計表 | high |

## 矛盾・確信度に関する注記
矛盾は検出されなかった（review.md / 設計書 / コード読解 / 実測のいずれも整合）。

## Surrendered事項
なし。AC1について「決定」自体はarchitectの設計判断事項であり、investigatorとしては「現状の挙動」「YAML準拠時の挙動」「影響範囲（テンプレート構造上は他キー汚染が再現しないこと、ただし実チケットでの発生有無は未検証）」の事実収集に留めた。

## 調査中の追加所見（深掘りはしていない）
- M4関連で、ヘッダの「イベント数」も `retry_reset` イベントを含む生カウントであり、本文のどのセクションにも `retry_reset` 由来の件数が現れないため、architectが「チケット数」だけでなく「イベント数」の表示方針も合わせて検討する余地がある（本チケットのAC2はチケット数の不整合を主題としているが、根本原因は共通）。

## 参照ファイル（絶対パス）
- /home/bzg55/workspace/breeze/kenesis-loop-kit/tickets/active/KLK-028_KLK-012の残存副次変更とテスト整備.md
- /home/bzg55/workspace/breeze/kenesis-loop-kit/.claude/hooks/_ticket_lib.py
- /home/bzg55/workspace/breeze/kenesis-loop-kit/.claude/metrics/aggregate.py
- /home/bzg55/workspace/breeze/kenesis-loop-kit/.claude/hooks/validate_ticket_state.py
- /home/bzg55/workspace/breeze/kenesis-loop-kit/tests/test_ticket_lib.py
- /home/bzg55/workspace/breeze/kenesis-loop-kit/tests/test_validator.py
- /home/bzg55/workspace/breeze/kenesis-loop-kit/tests/test_metrics.py
- /home/bzg55/workspace/breeze/kenesis-loop-kit/tests/_util.py
- /home/bzg55/workspace/breeze/kenesis-loop-kit/docs/designs/KLK-012.md
- /home/bzg55/workspace/breeze/kenesis-loop-kit/docs/reports/KLK-012/review.md

## Handoff推奨
Unknownsなし。次エージェントとしてarchitectへの委譲を推奨する（AC1の設計判断、AC2のヘッダ整合方針、AC3・AC4のテスト追加方針の策定）。
