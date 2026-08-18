# KLK-031 調査報告（investigator, Mode A）

## Findings
- 再現手順1〜3は実ソースと一致（実測: `guarded_paths_after_shell_expansion("*")` は `["SPEC.md"]`。"?"・"["単体は空リストで無害）。
- 再現手順4（最重要）: **実際にdeny/askへ影響する。** `statement_violation`の`gate_hit`が`mentions_guarded_expanded`経由で孤立`*`によりTrueになり、head非ホワイトリスト（`rm`/`chmod`/`tar`/`cp`/`mkdir`等）だと`segment_violation`が`"'X' は許可されていません"`でdenyする。ALLOWED_HEADS（`ls`/`cat`等）は本バグの影響を受けない。
- 実機で本セッション自身のBashツール呼び出し`true *`（無害なno-op）が本環境の稼働中PreToolUseフックにより実際に誤denyされることを確認した（下記Evidence）。
- 影響範囲は孤立`*`単体に限らず、`dir/*`（末尾セグメントが素の`*`。`rm build/*`等の頻出パターン）や`**`・`*?`・`?*`（ワイルドカードのみで構成される成分全般）にも及ぶ。`?`単体・`[`単体は該当literal（"active"6/"done"4/"SPEC.md"7文字）と長さ不一致・非パターンのため再現しない。
- 既存テスト（`tests/test_guard_bash_writes.py`のKLK-018系）にこのケースの回帰カバレッジは無い。ただし`docs/designs/KLK-018.md` §9 AC4の閉じた列挙(N2)の文言はこの形を明示的に除外していない（Unknowns参照）。

## Evidence
- `codebase`: `.claude/hooks/guard_bash_writes.py` — `_guarded_paths_from_expanded`(L1005-1043)・`guarded_paths_after_shell_expansion`(L1046-1112)・`is_guarded_token_expanded`(L1115-1122)・`mentions_guarded_expanded`(L1125-1127)・`statement_violation`(L2873-2926、特にL2900-2910の`gate_hit`算出とL2922-2925の`segment_violation`呼び出し)・`segment_violation`(L2490-2573、特にL2509-2510の`ALLOWED_HEADS`判定)。
- `empirical`(2026-08-18、本セッションのBash実行・python3): `guarded_paths_after_shell_expansion("*")` → `['SPEC.md']`。`find_violation("rm *")` → `"'rm' は許可されていません"`。`find_violation("rm build/*")`・`find_violation("chmod 755 *")`・`find_violation("tar cf out.tar *")`・`find_violation("cp * dest")`・`find_violation("mkdir *")`も同様にdeny。`find_violation("ls *")`・`find_violation("rm ?")`・`find_violation("rm [")`はNone（allow）。
- `empirical`(同上・実機フック): このBashツール呼び出し自体で`true *`を実行したところ、本環境の稼働中`guard_bash_writes.py`により`"'true' は許可されていません"`で実際にdenyされた（PreToolUseフックとして生きて動作している証拠）。
- `local_docs`: `docs/designs/KLK-018.md` §9 AC4 (N2)「分断globが`active`/`done`/`SPEC.md`にfnmatchし得る語を含み、かつ非ホワイトリストheadを持つ文」は誤deny予算の閉じた列挙内に記載されている（孤立ワイルドカードを除外する文言はない）。`docs/reports/KLK-030/investigation.md` L68-70「補足（KLK-030スコープ外・副次的発見）」に元記録あり（KLK-030investigator自身の検証コマンドが誤denyされた旨の記述と一致）。
- `codebase`: `python3 -m unittest discover -s tests -q` 実行結果 = 736件全PASS（本バグ修正前のベースライン）。

## Dependency Graph
- `guarded_paths_after_shell_expansion` → `_guarded_paths_from_expanded`（`fnmatch.fnmatchcase`使用）
- `is_guarded_token_expanded` = `is_guarded_token` OR `guarded_paths_after_shell_expansion`
- `mentions_guarded_expanded`（語集合）→ 各語へ`is_guarded_token_expanded` → `statement_violation`の`gate_hit`
- `gate_hit=True`の場合のみ`segment_violation`（`ALLOWED_HEADS`判定含む）に進む。`gate_hit=False`なら即allow（本バグが無ければ`rm *`はここでallowになるはず）
- `is_guarded_token_expanded`は他に`redirect_violation`(L2635)・`degraded_violation`内(L3062/L3106)でも呼ばれており、リダイレクト先やdegraded経路でも同型の孤立ワイルドカード誤判定が理論上起こりうる（今回は未実測）

## Risk Areas
- `ALLOWED_HEADS`外の大半のコマンド（`rm`/`chmod`/`tar`/`cp`/`mkdir`/`curl`/`wget`等）で、末尾セグメントが素のglob（`*`・`**`・`*?`・`?*`）のみのコマンドが広く誤denyされる。`rm build/*`のような日常頻出パターンも該当。
- 誤りの向きは一貫してdeny方向（安全側）であり、allow化のリスクは実測範囲内では確認されていない（受け入れ条件「allow方向への劣化がないこと」は現状維持されている）。
- `docs/designs/KLK-018.md` AC4 (N2)の文言は本ケースを技術的に除外していないため、「設計が意図的に許容した誤deny予算内」なのか「設計時の見落とし」なのか記載から判別不能（Unknowns行き）。
- `redirect_violation`等の他呼び出し箇所（4箇所）も同型のOR構造のため、同種の誤denyがstatement_violation経由以外にも及ぶ可能性がある（未実測）。

## Assumptions
- チケット記載の行番号は古い可能性がある前提に従い、シンボル名（grep）で現版の実位置を特定した。
- 「ALLOWED_HEADSに無いhead」の代表例として`rm`/`chmod`/`tar`/`cp`/`mkdir`/`true`を用いたが、これは`ALLOWED_HEADS`（L440-453）との差集合全体を代表するサンプルであり網羅列挙ではない。
- fnmatchの標準ライブラリ実装（CPython）の挙動は環境非依存で安定していると仮定し、他OS/他Pythonバージョンでの差異は検証していない。

## Unknowns
- **【architect/human判断待ち】** `docs/designs/KLK-018.md` §9 AC4 (N2)の閉じた列挙が、本ケース（成分がワイルドカードのみで構成され実質「任意の名前にfnmatchし得る」場合）を意図的に許容範囲としていたのか、設計時の想定漏れ（本来の意図は`acti*e`のような部分アンカー付きパターンのみ）だったのかは記載からは判別できない。矛盾として報告し、判定はarchitectに委ねる。
- `redirect_violation`・awk/sed置換解決後経路（L1804/L2635/L3062/L3106）での孤立ワイルドカードの実挙動は未実測（今回はstatement_violation経由のhead判定に絞って深掘りした）。verification_hint: 同じ手法（`chr()`でglob文字を組み立てて`find_violation`を直接呼ぶ）でリダイレクト先パターン（`echo x > out*`等）を実測すれば確定可能。
- `*`・`**`・`*?`・`?*`の4パターンのみ実測しており、より長いワイルドカードのみ成分（例: `***`）や`[...]`が実際に有効なブラケット式になる形（`[a-z]`等、単一文字ではないケース）の網羅検証は行っていない。

Unknownsが存在するため、次エージェントへの直接推奨は行わず、orchestratorから人間へのエスカレーション（再調査要否・次フェーズ移行の判断）を推奨する。特に「N2該当性の解釈」は設計文書の意図に関わる判断であり、人間確認後にarchitectへ委譲するのが適切と考える。

## 主要参照ファイル（絶対パス）
- `/home/bzg55/workspace/breeze/kenesis-loop-kit/.claude/hooks/guard_bash_writes.py`
- `/home/bzg55/workspace/breeze/kenesis-loop-kit/tests/test_guard_bash_writes.py`
- `/home/bzg55/workspace/breeze/kenesis-loop-kit/docs/designs/KLK-018.md`
- `/home/bzg55/workspace/breeze/kenesis-loop-kit/docs/reports/KLK-030/investigation.md`
