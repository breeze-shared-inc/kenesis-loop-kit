# KLK-016 実装詳細

生成: implementer / 最終更新: 2026-08-17

設計書 `docs/designs/KLK-016.md` §4「実装詳細」記載の一意な引用文字列どおりに
差分を適用した。独自の設計変更は行っていない（Open Questionsなし・設計確定済み）。

## Phase 1（コミット a4e8ba9）

- `.claude/hooks/_ticket_lib.py`: `import hashlib` を追加し、`is_ticket` 定義の
  直後・`emit_pretooluse_decision` の直前に5関数を追加した。
  - `spec_path_for(cwd)` / `spec_state_path(cwd)`: cwd の非str/空を None で
    fail-open。
  - `is_project_spec(path, cwd)`: 絶対形は `_normalize_path` で正規化して
    `spec_path_for(cwd)` と一致するかを比較し、相対形は文字列 `"docs/SPEC.md"`
    そのものだけを認める（`is_ticket` の相対形受理と同じ「cwd非依存の純字句
    判定」方針を踏襲）。ネストした `docs/foo/SPEC.md` はいずれの形でも一致
    しない（D3）。
  - `load_spec_state(cwd)`: JSON読み込み失敗・非dictはNone。
  - `sha256_file(path)`: 64KBチャンクで読み、失敗時はNone。
- `.claude/hooks/record_metrics.py`: `main()` の早期return条件を設計書
  §4-1の引用どおりに書き換え、`is_ticket` が偽の場合に `is_project_spec` を
  判定して真なら `record_spec_state` を呼ぶ分岐を追加した。以降の既存
  ticket処理ロジック（`tickets_dir = lib.tickets_dir_for(path)` 以下）は
  1行も変更していない。`record_spec_state(path, cwd)` を `write_state` の
  直前に新設（設計書のコードをそのまま採用）。
- `.gitignore` / `.gitignore.public` / `.gitignore.private`: いずれも
  `tickets/.metrics_state.json` の直後に `docs/.spec_state.json` を追加。
- 手動確認（Phase 1完了条件）: tempdir上でSPEC.mdへのWrite相当payloadを
  `record_metrics.py` へ送り、`docs/.spec_state.json` の `hash` が
  `hashlib.sha256(content).hexdigest()` と一致することを確認。ネストした
  `docs/foo/SPEC.md` への書き込みではサイドカーが生成されないことも確認。
- `tests/test_metrics.py`（既存20件）は無改変で全件pass。

## Phase 2（コミット 3e15b04）

- `.claude/hooks/check_loop_integrity.py`: `check_done_ticket_drift` の直後・
  `def main():` の直前に `check_spec_drift(cwd)` を設計書§4-2のコードそのまま
  追加。`main()` 内 `check_done_ticket_drift` ループの直後・`if problems:`
  の直前に `problems.extend(check_spec_drift(cwd))` を追加。モジュール
  docstringへ「SPEC.mdドリフト検知（KLK-016）」の段落を挿入。
- `.claude/hooks/guard_spec_writes.py` / `guard_bash_writes.py`: 設計書
  §4-3のとおりdocstring内の1文のみを修正（判定ロジック・関数本体は無変更）。
- 手動確認（Phase 2完了条件）: tempdir上で「SPEC.md不在」「サイドカー
  未記録」「正規記録と一致」「Bash相当の内容改変」の4パターンを実行し、
  最後の1パターンのみ `decision: block`・reasonに"docs/SPEC.md"を含むことを
  確認した（他3パターンは無出力＝allow）。
- 補足: `check_spec_drift` の呼び出し位置は `main()` の
  `if not os.path.isdir(active_dir): sys.exit(0)` より後にあるため、
  `tickets/active` が存在しないcwdではSPEC.mdドリフト検知自体が実行されず
  main()が早期終了する（既存の `check_done_ticket_drift` と同じ制約）。
  Phase 3のテストではこの理由で `tickets/active` を明示的に作成している
  （§6リスク表に記載なし・軽微な設計上の前提のため実装メモへ記録）。
- `tests/test_loop_integrity.py`（既存27件）は無改変で全件pass。

## Phase 3（コミット d993ece）

- `.claude/hooks/README.md`: 設計書§4-4のとおり4箇所へ追記（hook一覧表
  `check_loop_integrity.py`行・`record_metrics.py`行、`guard_bash_writes.py`
  行内の1文、「メトリクスの運用」節の1行目修正＋新規箇条書き1行）。
- `tests/_util.py`: `import hashlib` を冒頭のimport群へ追加し、
  `state_record` の直後に `write_spec` / `write_spec_state` / `spec_hash`
  を設計書§4-5のコードそのまま追加（`spec_hash` 内のローカル
  `import hashlib` は冒頭importへ集約したため削除）。
- `tests/test_spec_drift.py`（新設・10ケース）: 設計書§4-6のテストケース
  一覧どおりに実装。`TestSpecStateRecording`（4件）・
  `TestSpecDriftDetection`（6件、`setUp` で `tickets/active` を作成）。
  いずれも tempdir 上に実ファイルを生成しサブプロセス起動で検証する
  統合テストスタイル（既存2ファイルと同型・モックなし）。
- `python3 -m unittest discover -s tests -v` で全639件（既存629件＋
  新規10件）がpassすることを確認済み。

## 実機動作確認について（§9テスト観点 (c)）

本リポジトリには `docs/SPEC.md` が存在しないため、実SPEC.mdが存在する
プロジェクトでの実機動作確認は本リポジトリ単体では不可。tempdir上の
unittest（`tests/test_spec_drift.py` 全10件・Phase 1/2の手動確認）が
検証手段のすべてである。

## §9 単体境界テスト（純粋関数）について

`sha256_file` の存在しないパスでNoneを返す挙動・`is_project_spec` が
ネストしたSPEC.mdで偽を返す挙動・`load_spec_state` が壊れたJSON/非dictで
Noneを返す挙動は、設計書§9で「tester・reviewerへの指示」として明示された
テスト観点であり、`tests/test_spec_drift.py`（統合テスト）でカバーされない
純粋関数の単体境界確認をtester工程で追加することを前提とする（実装側では
既存の`tests/test_ticket_lib.py`相当の単体テストファイルへ新規追加していない）。
