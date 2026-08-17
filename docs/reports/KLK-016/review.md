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
