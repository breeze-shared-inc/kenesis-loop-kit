# KLK-019 investigation

生成: investigator（orchestrator代筆） / 最終更新: 2026-08-18

## Findings

1. **denyの正体は`head_of()`の統計エラー**: `find_violation()`→`split_statements()`（`;`/`&&`/`||`/`&`区切り）→`statement_violation()`→`pipe_segments()`→`segment_violation()`の経路で、各ステートメントの先頭語を無条件に`head_of()`（`head_index`）が「コマンド名」とみなす。`for`/`while`/`until`/`if`/`case`はもちろん、`do`/`then`/`else`/`elif`/`fi`/`done`/`esac`もすべて`ALLOWED_HEADS`に無いキーワードであり、それらが先頭語になった`;`区切りステートメントが保護対象パスに言及した瞬間denyになる。制御構文の特別扱いはコード中に一切存在しない（`.claude/hooks/README.md`にも記載なし）。
2. 実機でチケット再現手順3件＋`case`/`until`を含む計5パターンでdenyを再現し、deny理由が`'for'`/`'done'`/`'if'`/`'case'`/`'until'`というキーワードそのものであることを確認した。`while ... done < tickets/active/APP-001.md`は実は`while`ではなく最後の`done`が同一ステートメントにリダイレクト先を抱えたためdenyしている点に注意。
3. **重要**: `ALLOWED_HEADS`/`CWD_SAFE_HEADS`へ制御構文キーワードを単純追加する仮想パッチをin-memoryで作り検証したところ、`for f in tickets/active/*.md; do rm $f; done`／`if rm tickets/active/APP-001.md; then echo done; fi`／`case x in *) rm tickets/active/APP-001.md ;; esac`／`while true; do rm tickets/active/APP-001.md; break; done`の4形すべてがdeny→**allow**に転じることを実測した。KLK-010 implementerの懸念「本体を解析しないと安全性を保証できない」は現行アーキテクチャで具体的に実証される。
4. 根本原因は「`do`/`then`/`elif`/`else`の直後に続く実コマンド語がhead判定から一切見えない」こと。ステートメント分割は`;`単位のみのため、`do rm $f`は1ステートメントであり、`head_of`は先頭語`do`だけを見て`rm`を判定対象にしない。単純ホワイトリスト化は原理的に不可で、本体を再帰的にhead判定へ回す専用ロジックが必須。
5. ループ変数`$f`の値追跡機構は存在しない。`record_assignments`/`guarded_vars`は`NAME=value`前置き代入のみを追跡し`redirect_violation`の出力先判定にのみ使う。`for f in ...`の束縛は`ASSIGN_RE`不一致で対象外。既存の`INV-SH-11`（`f=tickets/active/APP-001.md; rm $f`→`allow`固定、tests/test_guard_bash_writes.py）とモジュールdocstringが「パラメータ展開の値は原理的に閉じられない」ことを既存の設計判断として明記済みであり、KLK-010 implementerの懸念と整合する。

## Evidence

- [codebase] `.claude/hooks/guard_bash_writes.py`: `head_of`/`head_index`・`segment_violation`・`split_statements`・`pipe_segments`・`ALLOWED_HEADS`・`CWD_SAFE_HEADS`を読み実装を確認
- [empirical, 2026-08-18] repoルートで`guard_bash_writes.find_violation()`を直接呼び出し、Findings2・3を確認。作業後`git status --short`はクリーン（コード無変更）
- [local_docs] `docs/designs/KLK-010.md`申し送り3「old=deny/new=deny・別チケット・設計判断要」、P7・P8・P9・V-14の定義、`tickets/done/KLK-010_....md`のLEGACY_DENY_COMMANDS 126件・INVENTORY_CASES 62件実測記録（KLK-010完了時点）
- [codebase] `tests/test_guard_bash_writes.py`: `LEGACY_DENY_COMMANDS`（現状ast計数130件・制御構文ケース0件）、`INVENTORY_CASES`（`(ID, 説明, command, expected)`4-tuple、現状92件、命名規約`INV-AWK-*`/`INV-SED-*`/`INV-SH-*`）、単一クラス`TestGuardBashWrites`、`assertAllow`/`assertDeny`（サブプロセス経由でend-to-end）

## Dependency Graph

`main()`→`find_violation()`→`normalize_line_continuations`→`lex()`(tokens,substs)→`split_statements()`→[各statementごとに `record_assignments`→`statement_violation`(`redirect_violation`, `pipe_segments`→`segment_violation`→`head_of`/`head_index`/`ALLOWED_HEADS`/`CWD_SAFE_HEADS`/`awk_violation`/`sed_program_violation`)]→`next_cwd`。字句解析失敗時は`degraded_violation`が同じ`segment_violation`/`head_of`を共有するが独自のステートメント分割(`LEGACY_STATEMENT_RE`)を持つ。`ALLOWED_HEADS`/`head_of`を参照するのは本ファイル単体で、他モジュール（`_ticket_lib.py`等）からの依存はない。`tests/test_guard_bash_writes.py`は`_util.run_script`によるサブプロセス実行でend-to-end検証（直接import呼び出しではない）。`.claude/settings.json`の`permissions.allow`は別レイヤの独立設定で本チケットの対象外。

## Risk Areas

1. **最大のリスク**: 制御構文キーワードの単純ALLOWED_HEADS追加は`do`/`then`/`else`直後の書き込みコマンド（`rm`/`sed -i`等）を無検出でallowに変える穴を開ける（Findings3で実測確認済み）。architectは「本体語を再帰的にhead判定へ回す」設計が必須
2. ループ変数値追跡はhookの構造上不可能（パラメータ展開はテキストに現れない）。AC「保守的にdeny」を満たすには、`for ... in ...; do <body>; done`の本体中で変数参照(`$var`)が書き込み系コマンドの引数位置に現れる構文パターン自体をdenyする新ルールが必要（既存`guarded_vars`機構の単純流用では届かない）
3. `LEGACY_DENY_COMMANDS`はKLK-010完了時126件との記載だが現状130件、`INVENTORY_CASES`は62→92件。テスト総数「437件」も過去KLK-012/013/014/015/017で繰り返し「集計方法不明・再現不可」と指摘済みの未解決の数値（`python3 -m unittest tests.test_guard_bash_writes`=245、`discover -s tests`=712、いずれもsubTest非展開）
4. 本チケットはallow方向の変更であり、同一hookはKLK-010で13ラウンド・穴10件・安全性主張の誤り4件の実績がある。P9（否定形・向き・検出器の3点併記）を満たさない安全性主張は設計書・docstringに書けない規律が適用される
5. `case`構文のパターン部`)`は`OPERATOR_CHARS`に含まれず1語として残存する（例: `*.md)`）。将来`case`本体をパースする設計を採る場合、パターンと`)`の境界検出に新規ロジックが要る

## Assumptions

1. 本調査（monkeypatch含む）はコード変更を伴わないin-memory検証に限定し、`git status`で無変更を確認済み
2. 調査対象は2026-08-18時点のdevelop HEADの実装
3. 「old=deny/new=deny」の当時の生ログは`docs/reports/KLK-010/`が存在しないため参照不可。`docs/designs/KLK-010.md`申し送り3の一文のみを根拠とし、現行コードでのdeny再現（本調査）と結論が整合するためconfidence highのまま扱うが、KLK-010当時のold版そのものへの再検証は行っていない
4. `LEGACY_DENY_COMMANDS`/`INVENTORY_CASES`の件数はast静的解析によるリスト長カウントであり、実行時のsubTest展開数とは異なる

## Unknowns

1. 「テスト437件」の集計方法は本調査でも再現できなかった（既知の未解決事項、KLK-012/013/014/015/017で反復指摘済み）。verification_hint: KLK-010完了当時のtester/reviewerログの生の実行コマンドを確認するか、KLK-010 D3方式（絶対数を固定せず実測値＋追加分で全pass）を踏襲する
2. AC5の「LEGACY_DENY_COMMANDS 126件」は現状130件、「INVENTORY_CASES 62件」は現状92件（自然増分だが数値記述の不一致）。architectが設計書へ数値を書く際は実測値を正とする（過去チケットの前例と同様）
3. 制御構文サブケースを`INVENTORY_CASES`へ登録する際のIDプレフィックス（新設`INV-CTRL-*`か既存`INV-SH-*`延長か）は命名規約上の設計判断であり、architectへ委ねる
4. `do`/`then`/`elif`/`else`直後の実コマンドを安全に検出する具体的実装方式（本体を再帰的に`find_violation`へ回す／専用の"1語ずらし"パーサ等）は複数の設計選択肢があり、本調査では「なぜ単純ホワイトリスト化が危険か」の事実確認に留め、選定はしていない

## orchestratorによる注記

Unknown 1・2（テスト件数・既存リスト件数の数値不一致）は、KLK-010以降の一連のチケット（KLK-012/013/014/015/017/027等）で一貫して採用されてきた運用（受け入れ条件・設計書の件数は目安とし、tester/architectが都度実測値を報告する）で解消可能であり、過去に繰り返し発生している既知のパターンのため、本チケットのために追加で人間確認を挟まず、architectへ「実測値を正とする」運用を明示した上で設計へ進める。Unknown 3・4はarchitectの設計裁量範囲内。
