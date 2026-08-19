# KLK-016 review.md

## 事前確認（reviewer.md Responsibilities準拠）

1. **設計書§4実装Phase表とAC1〜AC6の対応**: Phase1→AC4（基盤・サイドカーhook自動生成）、Phase2→AC1・AC2・AC3（ドリフト検知本体）、Phase3→AC4（README記載）・AC5・AC6。全AC1〜AC6がPhase表でカバー済みであることを確認した。§4の例外（reviewer自身の確認行為で完結するAC）は本チケットには該当しない。
2. `docs/.spec_state.json`はhook（`record_spec_state`）のみが書き込み、`.gitignore`/`.gitignore.public`/`.gitignore.private`の3ファイルいずれにも追加されていることを確認した（grep済み）。README.md「メトリクスの運用」節にも直接編集禁止の明記あり。実効性は確保されている。
3. `is_project_spec`（`.claude/hooks/_ticket_lib.py`）はネストした`docs/foo/SPEC.md`を絶対形・相対形いずれも偽と判定し、設計書D3（プロジェクト直下1件限定）と一致。`tests/test_ticket_lib.py::TestSpecDriftPureFunctions`と`tests/test_spec_drift.py::test_nested_spec_not_recorded`の双方で確認済み。
4. `record_metrics.py`の`main()`変更は`git diff`で確認した限り、早期return条件の書き換えのみで、`tickets_dir = lib.tickets_dir_for(path)`以下の既存ticket処理ロジックは1行も変更されていない。最小差分の原則は守られている。
5. `guard_spec_writes.py`・`guard_bash_writes.py`は`git diff`でそれぞれ4行・3行のみの変更で、いずれもdocstring内の文章置換のみ（判定ロジック・関数本体は無変更）であることを確認した。

## Required Output Format

**1. Critical Issues**
- なし。

**2. High Risks**
- なし。

**3. Medium Risks**
- `check_loop_integrity.py`の`check_spec_drift(cwd)`呼び出しが`if not os.path.isdir(active_dir): sys.exit(0)`（`tickets/active`不在チェック）より**後**にあるため、`tickets/active`が存在しない環境ではSPEC.mdドリフト検知自体が実行されない。設計書D2の「`tickets/`ディレクトリの有無から疎結合にできる」という明示的な設計理由と実際のコード配置（§4-2の一意な引用文字列どおりの箇所）が矛盾している。
- 本Kit運用下では`tickets/active/.gitkeep`が常在するため実害は低いが、この結合は§6リスク表に未記載・無テストであり、implementer実装メモにのみ「軽微な設計上の前提」として記録されている。
- develop側に並行マージ済みのKLK-029が`guard_bash_writes.py`の同一docstring節（「既知の限界」段落）を変更しているため、次回developマージ時に当該パラグラフでコンフリクトが想定される（implementerも実装メモで既に言及済み。ブロッカーではなくマージ時対応事項）。

**4. Missing Tests**
- `tickets/active`不在＋`docs/SPEC.md`改変が同時に発生するケースの回帰テストが無い（上記Medium Riskの実際の挙動を固定する意味で有用）。
- `is_project_spec`の相対パス一致分岐（文字列`"docs/SPEC.md"`そのものとの一致）は`tests/test_ticket_lib.py`の純粋関数テストのみで検証され、`record_metrics.py`/`check_loop_integrity.py`のサブプロセス統合テスト（`tests/test_spec_drift.py`）では絶対パスのみが使われており、この分岐の統合経路が未検証。

**5. Spec Violations**
- AC1〜AC6はいずれも設計書§9のテスト対応・grep確認により充足を確認した。チケットのAC自体への違反は無い。
- 設計書§3 D2「`tickets/`ディレクトリの有無から疎結合にできる」という記述は、§4-2で確定した実装（`check_spec_drift`呼び出しがtickets/active存在チェック後）と整合しておらず、設計書の記述精度に懸念が残る（Medium Risk 1と同一事象）。

**6. Suggested Fixes**
- `problems.extend(check_spec_drift(cwd))`の呼び出しを`os.path.isdir(active_dir)`チェックより前（`main()`冒頭付近）に移動し、D2の設計意図（ticket機構からの疎結合）を実コードで満たす。
- `tickets/active`不在時のSPEC.mdドリフト検出（tamperありのケース）を確認する回帰テストを追加する。
- `is_project_spec`の相対パス分岐を、`record_metrics.py`/`check_loop_integrity.py`の統合テストにも最低1件追加する。
- developマージ時は`guard_bash_writes.py`「既知の限界」節でKLK-029との内容コンフリクトを想定し、両チケットの追記文をいずれも残す形で解消する。

**7. Approval Status: approved**
- 上記Medium Risksはいずれもブロッカーではなくフォローアップ推奨事項として付記する（AC1〜AC6の充足には影響しない。実運用では`.gitkeep`により`tickets/active`が常在するため実害は限定的）。
- tester Quality Gate（644件全pass、既存639件＋純粋関数境界テスト5件）をorchestrator独立再実行含め確認済み。
- 設計書Phase表による全AC1〜AC6のカバレッジ、最小差分原則（record_metrics.py）、docstring-only変更（guard_spec_writes.py/guard_bash_writes.py）、`.gitignore`3ファイル同期をいずれも確認済み。

## 参照ファイル（絶対パス）
- `/home/bzg55/workspace/breeze/kenesis-loop-kit.wt/KLK-016/docs/designs/KLK-016.md`
- `/home/bzg55/workspace/breeze/kenesis-loop-kit.wt/KLK-016/.claude/hooks/check_loop_integrity.py`
- `/home/bzg55/workspace/breeze/kenesis-loop-kit.wt/KLK-016/.claude/hooks/_ticket_lib.py`
- `/home/bzg55/workspace/breeze/kenesis-loop-kit.wt/KLK-016/.claude/hooks/record_metrics.py`
- `/home/bzg55/workspace/breeze/kenesis-loop-kit.wt/KLK-016/.claude/hooks/guard_spec_writes.py`
- `/home/bzg55/workspace/breeze/kenesis-loop-kit.wt/KLK-016/.claude/hooks/guard_bash_writes.py`
- `/home/bzg55/workspace/breeze/kenesis-loop-kit.wt/KLK-016/tests/test_spec_drift.py`
- `/home/bzg55/workspace/breeze/kenesis-loop-kit.wt/KLK-016/tests/test_ticket_lib.py`
- `/home/bzg55/workspace/breeze/kenesis-loop-kit.wt/KLK-016/docs/reports/KLK-016/implementation.md`
- `/home/bzg55/workspace/breeze/kenesis-loop-kit.wt/KLK-016/docs/reports/KLK-016/test-report.md`

---

## 第2版レビュー（改善ループ・フォローアップ対応、2026-08-17）

第1版で指摘したMedium Risks 2件・Missing Tests 2件（呼び出し位置の設計意図不一致・回帰テスト2件）への対応を、人間指示による改善ループ（architect設計改訂→implementer実装Phase F1/F2→tester Quality Gate pass）を経て再レビューした。

### Critical Issues / High Risks / Medium Risks
なし。第1版で指摘した3件（呼び出し位置の設計意図不一致・回帰テスト2件）はいずれも本ラウンドで解消を確認した。KLK-029とのマージコンフリクト想定は第1版マージ時（2026-08-17 17:27）に既に解消済みで、本ラウンドの差分には現れない。残存する軽微な観測: `docs/reports/KLK-016/implementation.md`が「650件想定→662件」の差異を明記済みで、原因（developの並行マージによるテスト増）も妥当。実害なし。

### Missing Tests
なし。AC-F1〜AC-F3はいずれも新規3ケースで検証されており、tester側の追加テストは不要と判断した根拠も妥当。`test_matching_hash_allows_without_tickets_active_dir`は単体では「呼ばれたが[]だった」のか「呼ばれなかった」のかを区別できないが、`test_bash_edit_detected_without_tickets_active_dir`とのペアでAC-F1を実証できている（blockできた事実がcheck_spec_drift実行の証拠になる）。

### Spec Violations
なし。`docs/designs/KLK-016.md`§4-7・§4-8の「一意な引用文字列」どおりに`.claude/hooks/check_loop_integrity.py`・`tests/test_spec_drift.py`が変更されていることを`git diff develop...HEAD`で確認した。Phase表（F1/F2）でAC-F1〜AC-F3が全て網羅されており、§4の例外に該当するACはない。

### 検証詳細

1. **呼び出し位置の是正（AC-F1本体）**: `git diff develop...HEAD -- .claude/hooks/check_loop_integrity.py`を確認。`problems = []` の直後に `problems.extend(check_spec_drift(cwd))` が移動し、`tickets/active`存在チェック（`if os.path.isdir(active_dir):`）は`check_ticket`/`check_done_ticket_drift`のループのみを包む形に変わっている。`check_ticket`・`check_done_ticket_drift`の関数定義自体は差分に一切現れず、設計書§4-7「既存ロジックは1行も変更しない」との記述と一致する。振る舞いの等価性も確認: 旧コードは`active_dir`不在時に`sys.exit(0)`で即終了しticket系ループが実行されなかったが、新コードでも`if os.path.isdir(active_dir):`ブロックがfalseなら同ループは実行されない（等価）。唯一の違いは`check_spec_drift`が`active_dir`の有無に関係なく必ず実行される点で、これがAC-F1のfixそのもの。

2. **新規テスト3件の実効性確認**（形だけでないか）: `TestSpecDriftIndependentOfTicketsDir`の2ケースは`setUp`で意図的に`tickets/active`を作らず、`.claude/hooks/check_loop_integrity.py`をサブプロセスとして実際に起動する統合テスト（`run_stop()`経由）。`test_bash_edit_detected_without_tickets_active_dir`は`decision: block`と`reason`への`"docs/SPEC.md"`包含を両方assertしており、AC-F2の文言と一致。`test_records_hash_with_relative_file_path`は`tool_input.file_path`に相対文字列`"docs/SPEC.md"`を直接指定し、`record_metrics.py`をサブプロセス起動（`cwd=self.cwd`）することで`is_project_spec`の相対分岐（`n == "docs/SPEC.md"`）を実際に経由させている。`_util.spec_hash`は実装の`sha256_file`を呼ばず独立算出のためタウトロジーでもない。3件とも`python3 -m unittest tests.test_spec_drift -v`（13件、既存10件＋新規3件）で実行し全passを確認した。

3. **既存ロジックへの回帰確認**: `git diff develop...HEAD -- tests/test_loop_integrity.py`・`tests/test_metrics.py`はいずれも0行（差分なし）。`git diff develop...HEAD --stat`は変更対象を`.claude/hooks/README.md`（1行）・`.claude/hooks/check_loop_integrity.py`（docstring+main()のみ）・`tests/test_spec_drift.py`・レポート2件の5ファイルに限定しており、`guard_spec_writes.py`・`guard_bash_writes.py`・`_ticket_lib.py`・`record_metrics.py`は無変更（第1版で確定した実装に手を加えていない）。フルスイート`python3 -m unittest discover -s tests -v`を独立実行し662件全pass（既存AC1〜AC6を検証する既存テスト群を含め後退なし）を確認した。

4. **設計書・チケット整合性**: `docs/designs/KLK-016.md`第2版§9 AC-F1〜AC-F3・§4実装Phase表（F1/F2）を確認し、フォローアップAC全てがPhase表でカバーされていることを確認した。

### Approval Status: **approved**
Critical/High/Medium Risksともになし。フォローアップAC-F1〜AC-F3は全て実装・テストで充足を確認、既存AC1〜AC6への後退なし。
