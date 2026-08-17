# KLK-021 調査詳細

生成: investigator（代筆: orchestrator） / 最終更新: 2026-08-17
対象: scripts/list_tickets.pyのcwd依存・相対root指定による無言0件の是正
要点はチケット `KLK-021` の「調査メモ」を参照。本ファイルは全文。

## Findings

- **M2（相対root指定で0件）は既に解消済み**。KLK-012の`is_ticket()`修正（develop mergeコミット`ffaf02b`）で相対パスも判定されるようになったため、実機で`main(root=".")`・`collect(Path("tickets/active"))`を試したところ、絶対パス指定と同じ14件を返した（旧チケット記載の共通原因は現状のコードには当てはまらない）。
- **H1（worktreeからの実行で0件）は現在も再現する**。ただし根因はis_ticket()ではなく、`main()`のroot既定値`Path(__file__).resolve().parents[1]`が「スクリプトの起動パス（cwd依存で解決される`__file__`）」に自己解決される点。worktreeは`scripts/list_tickets.py`のフル複製と、gitignore対象で空の`tickets/active/`（`.gitkeep`のみ）を持つため、"存在するがたまたま空のディレクトリ"を正しく（しかし意図と異なる場所を）参照してしまう。M2とH1は別機序であり、チケット本文の「共通原因」記述は現状のコードに対しては不正確。
- T1（guard_bash_writes allow固定テスト）・T3（相対root実証テスト）・T4（引数なし制約の固定テスト）は`tests/`に未着手（存在しない）。T1指定ペイロードは実機投入でexit=0・無出力＝allowを確認。
- T2（policy-registry.md表の最終行チェック）は`test_closing_sentence_still_after_table`が「締め文より前」しか検証しておらず、チケットの指摘どおり表途中への誤挿入は検出不能。参照先はKLK-005で`docs/policy-registry.md`へ変更済み。
- start-loop.md・orchestrator.mdに「list_tickets.pyはメインworktreeで実行する」という明示の1文は現状なし。ファイルモードは`list_tickets.py`=100644、`batch_loop.py`=100755（不一致）。全テストは実測**581件**全通過（461件は陳腐化した数値）。

## Evidence

1. `.claude/hooks/_ticket_lib.py`（codebase, high）: `is_ticket()`が`_normalize_path`/`_under_dir`経由で`tickets/active/X.md`（先頭スラッシュ無し）にも`startswith`でTrueを返すことを確認。KLK-012設計書§4-1の実装案と一致。
2. worktree(`kenesis-loop-kit.wt/KLK-015`)からの実行（empirical, 2026-08-17）: `python3 scripts/list_tickets.py`が「計0件（エラー0件）」exit=0を返す。worktree内`tickets/active/`は`.gitkeep`のみ（gitignore対象）。同時点メインツリー側は14件。
3. リポジトリルートでの`main(root=".")`実行（empirical）: ABS root/REL root='.'とも14件・エラー0件で完全一致。M2は現状のコードでは再現しない。
4. `guard_bash_writes.py`へのT1ペイロード投入（empirical）: `{"tool_name":"Bash","tool_input":{"command":"python3 scripts/list_tickets.py"}}`投入で無出力・exit=0（allow）を確認。
5. `tests/test_list_tickets.py`（codebase, high）: `TestBuildRow`/`TestCollect`/`TestMain`の3クラスのみ。`run_main`は常に絶対パスのPathオブジェクトを渡しており、相対パス文字列でのroot指定テストは皆無（T3未着手）。`argparse`・`sys.argv`という文字列は本体・テストいずれにも出現しない（T4は本体は要件充足済みだが固定テストなし）。
6. `tests/test_klk003_doc_wiring.py::TestClaudeMdPolicyTable.test_closing_sentence_still_after_table`（codebase, high）: 「該当行インデックス < 締め文インデックス」の順序制約のみ。表途中への誤挿入は検出不能（T2の指摘どおり）。
7. ファイルモード実測（empirical）: `git ls-files -s`で`scripts/list_tickets.py`=100644、`scripts/batch_loop.py`=100755。gitインデックス上も不一致確定。
8. `orchestrator.md`25行目（codebase, high）: 「メインworktree書き込み限定」規約はあるが、**読み取り専用**のlist_tickets.pyの実行場所については言及なし。`start-loop.md`も同様に未言及。
9. テストスイート実測（empirical）: `python3 -m unittest discover -s tests` で581件全通過。KLK-012完了時点の558件からKLK-014・KLK-023等の追加で581件に増加したことと整合。

## Dependency Graph

- `docs/worktree-policy.md`（実装ループのworktree分離）→ orchestratorが`cd ../{repo}.wt/{ID}`→ `python3 scripts/list_tickets.py`（相対起動）→ `Path(__file__).resolve()`がworktree内を指す → worktreeの`tickets/active/`（gitignore・空）→ H1発現。
- `scripts/list_tickets.py`は`.claude/hooks/_ticket_lib.py`の`is_ticket`/`parse_frontmatter`を直import。`_ticket_lib.py`はvalidate_ticket_state.py・record_metrics.py・check_loop_integrity.py・guard_bash_writes.pyとも共有される単一の真実源。
- `.claude/hooks/guard_bash_writes.py`はコマンド文字列に`"tickets/active"`が現れない限り`python3 scripts/list_tickets.py`を素通りさせる。この非干渉性はlist_tickets.pyのdocstring記載の設計前提と一致し、実機でも確認済み。
- `tests/test_klk003_doc_wiring.py`は`docs/policy-registry.md`（KLK-005で分離）・`.claude/agents/orchestrator.md`・`.claude/commands/start-loop.md`の文言を検証。KLK-021のH1ドキュメントAC・T2強化はこのファイル群と直接結合する。
- `tests/test_list_tickets.py`は`_util.REPO`経由でリポジトリ実体を参照。T3（相対root実証）はこのファイルへの追加が自然。

## Risk Areas

- 出力ヘッダへ`対象: <絶対パス>`を追加すると`TestMain`等の既存アサーション（`凡例:`/`計 N 件`等の部分一致）自体は影響しないはずだが、start-loop.md/orchestrator.mdのCLI出力読解（LLMによるテキスト解釈）に新しい行が挿入される点は実装時に整合確認が必要。
- `Path(root).resolve()`の導入は明示的なroot指定時のみ挙動が変わる（デフォルトは既に絶対）。H1のヘッダAC実現にはどのみち`.resolve()`相当が必要になるため、M2の症状は既に消えていてもT3・H1双方の実装で`.resolve()`化は避けられない。
- AC本文「現行461件＋追加分」は陳腐化（実測581件）。テスト実行結果の基準値としてarchitect/testerは461ではなく実測581件を起点にする必要がある（誤って「回帰」と判定しないため）。
- KLK-012完了報告（レビューメモ）に「M1・M2はKLK-020への必須入力」との記載があり、KLK-020（hook判定基準統一の再評価、現在status: blocked）との関係整理が必要な可能性がある（本調査ではKLK-020チケット本文までは深掘りしていない＝調査範囲の自制）。

## Assumptions

- worktreeでの再現はKLK-015の1インスタンスのみ実機確認したが、機序（`__file__.resolve()`のcwd依存＋worktreeがフルgit checkoutでscripts/を含む）はコード読解ベースであり、`docs/worktree-policy.md`に従う他の全worktreeでも同様に再現すると推定する（confidence: high、根拠はcodebase）。
- `/batch-loop-inline`のcwd持続挙動（チケット記載の露出窓）自体は本調査で再実証しておらず、CLAUDE.md/orchestrator.mdの記述を根拠として妥当とみなした（confidence: medium、local_docsのみに依拠）。
- ヘッダ行追加の正確な文言・挿入位置（LEGENDの前後どちらか等）はAC例示（`対象: /abs/.../tickets/active`）のみが根拠であり、architectの設計判断に委ねる。

## Unknowns

- ブロッカーとなる真の未確定事項はなし（H1・M2とも実機で再現有無を確定できた）。
- 軽微な公開質問（人間/architect確認推奨、非ブロッキング）: ACが「メインworktree限定」という運用文書化＋ヘッダ可視化のみを是正手段として指定しており、root解決ロジック自体をcwd非依存にする代替案（例: 絶対パス起動への統一）は明示的にスコープ外と読める。architectはこの解釈（観測性向上＋運用規約であり、コード側のcwd依存性そのものは解消しない）が意図どおりか、設計書起草前に確認しておくと手戻りを防げる。

## 次のステップへの推奨（investigator所見）

Unknownsに人間対応を要するブロッカーは無いため、architectへの委譲を推奨する。architectへの申し送り:
1. M2はis_ticket修正により症状として既に消えているが、AC・T3が明示する`Path(root).resolve()`はH1のヘッダAC実装のため引き続き必要
2. H1の是正手段はAC上「観測性向上＋運用文書化」であり「root解決のcwd非依存化」そのものではない点を設計の前提として明記すること
3. テスト基準は461件ではなく実測581件を起点にすること

## 参照した実ファイル

- `scripts/list_tickets.py`
- `.claude/hooks/_ticket_lib.py`
- `.claude/hooks/guard_bash_writes.py`
- `tests/test_list_tickets.py`
- `tests/test_klk003_doc_wiring.py`
- `tests/test_guard_bash_writes.py`
- `.claude/commands/start-loop.md`
- `.claude/agents/orchestrator.md`
- `docs/policy-registry.md`
- `docs/designs/KLK-012.md`
- `tickets/done/KLK-012_状態検証hookとメトリクス集計の堅牢化.md`
- `tickets/active/KLK-021_list_ticketsのcwd依存による無言0件の是正.md`
