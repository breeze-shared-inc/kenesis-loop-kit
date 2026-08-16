# KLK-023 test-report

生成: tester / 最終更新: 2026-08-16

## 1. テスト実行結果（詳細）

- コマンド: `python3 -m unittest discover -s tests`
- 実行環境1（現HEAD `5c93d9d`、worktree内）: `Ran 506 tests in 29.836s` / `OK`（failures 0, errors 0）
- 実行環境2（`develop` HEAD、`git archive develop` で抽出した別ディレクトリで独立実行）: `Ran 506 tests in 19.052s` / `OK`（failures 0, errors 0）
- 両者の件数は一致（506件）。設計書§9 AC5・Phase 1完了条件が想定する「改訂前と同じ件数」を実測で確認した
- なお設計書（docs/designs/KLK-023.md）Phase 1行の括弧書き「investigator報告では472件」は本チケット作成時点より前の別時点の報告と見られ、現在のdevelop HEAD（506件）とは一致しない。ただしAC5が要求するのは「改訂前後で変化しないこと」であり、develop HEAD時点と現HEAD時点が両方506件で一致するため、AC5自体は充足している（「472件」という記載自体が現状と乖離している点は、設計書側の情報として認識しておくべき差分）

## 2. git diff develop..HEAD の確認

- `git diff develop..HEAD --stat`: `docs/designs/KLK-010.md`（+6/-2）・`docs/designs/KLK-013.md`（+38/-10）の2ファイルのみ
- `.claude/hooks/` 配下・`tests/` 配下の差分は0（grepでも該当箇所なし）

## 3. AC1検証（§3コードと実装の一致）

- 実装側: `.claude/hooks/guard_bash_writes.py` の `def is_readonly_script_call` から `return os.path.normpath(first) in READONLY_SCRIPTS` までを抽出
- 設計書側: `docs/designs/KLK-013.md` 128〜161行目（改訂後の§3コードブロック）を抽出
- `diff` の結果: 差分なし（exit code 0）。docstring・実装本体とも一字一句一致を確認

## 4. AC2検証（§8ロールバック戦略とコミット構成の整合）

- `git log --all --pretty="%h %p %s"` で該当コミットの親子関係を実測:
  `a7a5bd9→3eff72e(Phase1)→fd7d561(Phase2)→8041af5(tester差戻・fail)→367cecd(修正)→bf34003(tester再検証)→2ed7ea2(マージ、親e945467・bf34003)`
- 設計書§8の参考情報（Phase1 `3eff72e`→Phase2 `fd7d561`→差し戻し `8041af5`→修正 `367cecd`→再検証 `bf34003`→マージ `2ed7ea2`）と完全一致
- ロールバック手順自体は `.claude/commands/rollback.md` の動的列挙手順へ委ねる記述に変更されており、コミット数のハードコードは撤去済み

## 5. AC3検証（追記のみで過去の記録を書き換えていないか）

- R21: 既存文「old=new=allow で本チケットの回帰ではないため...docstringの「既知の限界」に明記（Phase 7）」は一字一句保持。文末に `**[KLK-023追記]...**` を追加のみ
- D7: 既存パラグラフ「未対応（深刻度high・任意コード実行）...」は無変更。直後に新規パラグラフ `**[KLK-023追記]**` を追加
- §3-9棚卸し表: セル内の既存文言「許可経路の偽装は未対応（深刻度high・任意コード実行）」を保持したまま文末に `（KLK-023追記: KLK-013で解消）` を追加
- 3箇所とも「未対応」という過去の主張自体の削除・書き換えは無し。追記のみで構成されている

## 6. AC4検証（シンボル名・コミットハッシュ使用、行番号不使用）

- 改訂1〜6の参照はいずれも `is_readonly_script_call`・`head_args`・`READONLY_SCRIPTS`・`LEGACY_DENY_COMMANDS`・各テストメソッド名・コミットハッシュ（`3eff72e`等）を使用
- `L\d+` や「n行目」等の行番号参照は該当箇所に見当たらない

## 7. §4-3(a)実装反映注記とテスト実体の一致確認

- 記載された6テストメソッド名を `tests/test_guard_bash_writes.py` で `grep -c` した結果、いずれも1件ヒット:
  `test_disguised_env_assignment_glued_to_readonly_script_deny` / `test_disguised_env_assignment_glued_alt_name_deny` / `test_disguised_three_env_assignments_after_interpreter_deny` / `test_disguised_env_assignment_then_flag_deny` / `test_disguised_directory_prefix_relative_deny` / `test_disguised_directory_prefix_absolute_deny`
- 各テストの実体（`assertDeny`の引数コマンド文字列・コメント）を読み、注記の説明（代入語glue／3連続代入／代入+flag／ディレクトリ前置き相対・絶対）と整合することを確認
- `367cecd` への参照はテストファイル内コメント（711行目付近）に実在
