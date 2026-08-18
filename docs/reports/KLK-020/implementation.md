# KLK-020 実装報告（implementer）

implementer.md の Required Output Format に基づく詳細外部化ファイル。チケット本文・レポートには要点＋本ファイルへのポインタのみを残す。

## 1. 実装の概要

設計書 `docs/designs/KLK-020.md` §4 のPhase 1〜3を順に実装した。作業ブランチ:
`fix/KLK-020-hookのパス判定基準統一`（worktree: `../kenesis-loop-kit.wt/KLK-020`）。

## 2. Phase 1（AC1(a)部分・AC3）: SPEC.md判定の一本化とcase-insensitive化（D1）

コミット: `0766bb0`

- `.claude/hooks/_ticket_lib.py` に共有ヘルパー `is_spec_basename(name)` を新設
  （`is_project_spec` の直前に配置）。`isinstance(name, str) and name.upper() == "SPEC.MD"`。
- `guard_spec_writes.is_spec`: `n.rsplit("/", 1)[-1] == "SPEC.md"` →
  `lib.is_spec_basename(n.rsplit("/", 1)[-1])`
- `guard_bash_writes._is_guarded_path`: `os.path.basename(path) == "SPEC.md"` →
  `lib.is_spec_basename(os.path.basename(path))`
- `guard_bash_writes._is_guarded_path_component`: `"SPEC.md" in path.split("/")` →
  `any(lib.is_spec_basename(seg) for seg in path.split("/"))`
- `_ticket_lib.is_project_spec`: basename部分のみ `is_spec_basename` 経由でcase-insensitive化。
  実装は設計書§4のコード例（`rpartition("/")`で分解して比較する形）とは異なる形にしたが、
  同じ制約（ディレクトリ部分は大小区別を維持・KLK-016 D3のネスト除外を維持）を満たす
  よりシンプルな実装を採用した:
  ```python
  n = _normalize_path(path)
  n_dir, _, n_base = n.rpartition("/")
  if not is_spec_basename(n_base):
      return False
  target_dir = _normalize_path(target).rpartition("/")[0]
  return n_dir == target_dir or n_dir == "docs"
  ```
  basenameが`is_spec_basename`を満たし、かつ「ディレクトリ部分が`cwd`直下の`docs`と
  一致（絶対形）」または「ディレクトリ部分が文字列`"docs"`そのもの（相対形の純字句判定）」
  のいずれかを満たす場合にTrueとする。ディレクトリ部分の比較は素の文字列比較のため
  大小区別は維持される（`Docs/SPEC.md`は引き続きFalse）。ネストしたパス
  （`docs/foo/SPEC.md`等）はディレクトリ部分が`docs/foo`になり`docs`とも
  `<cwd>/docs`とも一致しないため引き続きFalse。
- テスト追加: `tests/test_guard_spec_writes.py`（7件）・`tests/test_guard_bash_writes.py`
  （6件）・`tests/test_ticket_lib.py`（6件）。4箇所それぞれで`SPEC.md`/`spec.md`/
  `Spec.md`/`SPEC.MD`/ランダム大小混在がTrueになること、`.claude/`配下・非`.md`拡張子・
  `SPEC_TEMPLATE.md`型・ネスト除外・ディレクトリ大小区別が引き続き不一致であることを確認。

## 3. Phase 2（AC1(b)部分・AC4）: is_ticket↔is_guarded_token「意図的な不統一を維持」の確定（D2）

コミット: `34d20af`

- `_ticket_lib.is_ticket`のdocstringと`guard_bash_writes.py`モジュールdocstring内の
  該当段落を更新し、「KLK-020でKLK-010 D2の根拠3点を再評価し『意図的な不統一を維持する』
  と確定した。根拠は`docs/designs/KLK-020.md` §3 D2を参照」という一文を追記した
  （コード変更なし、記述のみ）。
- pinningテストを`tests/test_guard_bash_writes.py`へ2件追加:
  - `test_klk020_is_ticket_vs_is_guarded_token_asymmetry_pinning`:
    `"mytickets/active/APP-001.md"`で`guard.lib.is_ticket`=False・
    `guard._is_guarded_path`/`guard.is_guarded_token`=Trueという非対称を固定。
    KLK-010 D2・KLK-020参照のコメントを付し「意図的な非対称でありバグとして
    誤修正しないこと」を明記。
  - `test_klk020_is_ticket_vs_is_guarded_token_relative_paths_converged`:
    KLK-012で収束した相対パスケース（`sub/tickets/active/...`・
    `x/../tickets/active/...`）が両者とも True/True になることを回帰確認。
  - `guard.lib`は`guard_bash_writes.py`が`import _ticket_lib as lib`で保持する
    モジュール参照をそのまま利用（テスト側での追加import不要）。

## 4. Phase 3（AC2・AC5）: README addendumと全体回帰検証（D3）

コミット: `b90c347`

- `.claude/hooks/README.md`「ルールを変更するとき」の既存3ステップ直後に、
  設計書§4記載の文面をそのまま追記（状態機械定数専用でありパス判定関数には
  適用されない旨・棚卸し手順・テスト追加手順の3点）。
- `python3 -m unittest discover -s tests` 実行結果: **757件 OK**（failures/errors 0）。
  内訳: 既存736件 + Phase 1追加19件（guard_spec_writes 7・guard_bash_writes 6・
  ticket_lib 6） + Phase 2追加2件（pinningテスト） = 757件で一致。

## 5. 設計からの逸脱

- `is_project_spec`の実装形（§2参照）は設計書§4のコード例と字面が異なるが、
  要求される制約（ディレクトリ部分の大小区別維持・ネスト除外維持・basenameの
  case-insensitive化）はすべて満たしており、設計書§4「実装の最終形は
  implementerの裁量とする」の範囲内。

## 6. 残存リスク・申し送り

- 設計書§6のリスク表に記載済みのもの以外に新規リスクは無い。
- `is_ticket`↔`is_guarded_token`の非対称（`mytickets/...`等）はKLK-012の対象外として
  意図的に残存させる設計判断であり、本チケットの範囲では解消しない
  （設計書§3 D2・§5参照）。
