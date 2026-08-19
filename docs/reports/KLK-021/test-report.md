# KLK-021 テストレポート（tester分）

## 実行環境
- worktree: `/home/bzg55/workspace/breeze/kenesis-loop-kit.wt/KLK-021`
- ブランチ: `fix/KLK-021-list-tickets-cwd-fix`（implementer実装済みコミット 2dc404f/472ca89/de542e5の上に、テストコードの追加変更なし。tester分はコミットに含める新規ファイルなし＝本レポートのみ）
- 実行コマンド: `python3 -m unittest discover -s tests -p "test_*.py" -v`

## 1. 全体テストスイート再実行
- 実測 **586件 / 586件 pass**（AC2の目安 581+5=586 と一致）。2回独立実行し両方OK。
- 実行中に見えた`batch_loop.py: error: --timeout-min...`等のstderr文字列は既存の
  `test_batch_loop.py`系がサブプロセスのstderrを意図的にキャプチャして検証している
  既存挙動であり、本チケットの変更とは無関係（新規failureなし）。

## 2. AC1〜AC9 個別検証
- **AC1（H1）**: worktree内（本ディレクトリ）で`python3 scripts/list_tickets.py`を実行し、
  `対象: /home/bzg55/workspace/breeze/kenesis-loop-kit.wt/KLK-021/tickets/active`
  （tickets/activeは`.gitkeep`のみの空ディレクトリ）が出力冒頭に現れ、`計 0 件`との
  組み合わせで「対象取り違え」が判別可能なことを実機確認した。
- **AC1（M2）**: メインツリー（develop, 13件の実チケット）を対象に、worktree版
  `list_tickets.main(root=<絶対パス>)` と `main(root=".")`（chdir後）を比較し、両者の
  stdout・rcが完全一致（`対象:`行含め同一13件）することを確認した。
- **AC2**: 上記1.のとおり586件pass。
- **AC3**: `format_target`の呼び出しが`print(LEGEND)`の直前にあり、出力冒頭
  （凡例行より前）に`対象: <絶対パス>`が1行のみ現れることをソース読解と実行出力の両方で確認。
  `argparse`/`sys.argv`不参照であることはT4（後述）で固定済み＝CLI引数は増えていない。
- **AC4**: `git diff develop -- .claude/commands/start-loop.md .claude/agents/orchestrator.md`
  でそれぞれ1文追記（「メインworktree（orchestratorの作業ツリー）で実行すること」）を確認。
- **AC5**: `main`のroot解決が`root = Path(root).resolve() if root is not None else ...`に
  なっていることをソースで確認。T3
  (`TestMain.test_relative_root_matches_absolute_root`)を単体実行しpassを確認。
- **AC6**: `TestGuardBashWrites.test_list_tickets_cli_allow`を単体実行しpass。
  `assertAllow`は`_util.run_script(_util.GUARD_BASH, ...)`で`guard_bash_writes.py`を
  実サブプロセス起動しており、モックではなく実挙動を検証している。
- **AC7**: `docs/policy-registry.md`のポリシー一覧表で対象行の直後にダミー行
  `| ダミー行(AC7ミューテーションテスト用・後で削除) | dummy | dummy | dummy |`を一時挿入し、
  `test_row_is_last_line_of_contiguous_table_block`のみが
  `AssertionError: 30 != 31 : 追加行が表の最終行になっていない(表途中への誤挿入)`で
  redになることを確認。直後に`cp`で原本へ復元し、`git status --porcelain`が空
  （差分なし）であることと、`TestClaudeMdPolicyTable`全件再passを確認した。
- **AC8**: `TestNoPositionalPathArguments`の2メソッドを単体実行しpass。
- **AC9**: `git ls-files -s scripts/list_tickets.py` → `100755 ...` を確認（shebang行は
  `#!/usr/bin/env python3`のまま維持）。

## 3. エッジケース（tempdir経由os.chdirの干渉確認）
- `ListTicketsBase.setUp`で`self.addCleanup(shutil.rmtree, ...)`が先に登録され、T3の
  `os.chdir`復帰用`addCleanup`はテストメソッド内で後から登録される。unittestの
  addCleanupはLIFO実行のため、`os.chdir`復帰が`rmtree`より必ず先に走る（ソース読解で確認）。
- 実測でも`test_relative_root_matches_absolute_root`単体実行の前後で`pwd`が
  worktreeルートのまま変化していないことを確認（テスト内chdir→cleanupでの復帰が
  正しく機能し、後続テストへの干渉が起きていない）。

## 4. モック方針の確認
- 新規テスト（T1〜T4）はいずれも既存ユーティリティ（`ListTicketsBase`/`TestMain.run_main`/
  `_util.run_script`・`_util.GUARD_BASH`/`extract_section`等）を再利用しており、新規の
  モック導入は確認されなかった（各テストファイルの新規メソッドをdiff相当で目視確認）。

## 5. 追加テストの要否判断
- **追加不要**と判断する。根拠: (a) AC1〜AC9それぞれに対応するテスト・実機確認手段が
  既に存在し、上記2.で全て独立に再検証できた（AC7は意図的なミューテーションでred化も
  実証済み）、(b) 設計書§9「テスト観点」が明示する境界（in-process呼び出し/静的ソース
  走査のみで十分・モック不要）を満たしている、(c) 出力フォーマット変更は`assertIn`部分一致
  4件の既存アサーションに対して非破壊であることを実行結果で確認済みで追加の回帰テストを
  要する新規分岐は見当たらない。
