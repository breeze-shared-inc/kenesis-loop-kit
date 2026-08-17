# KLK-005 test-report

生成: tester / 最終更新: 2026-08-17

## 1. テスト実行結果（詳細）

- `python3 -m unittest discover -s tests -p "test_*.py" -v`: 561件実行、全pass（既存558件 + 本チケットで追加した3件）
- `python3 -m unittest tests.test_klk003_doc_wiring tests.test_klk004_doc_wiring -v`: 25件実行、全pass（TestClaudeMdPolicyTable 4件 + TestClaudeMdPolicyRow 3件 + 既存18件）
- `python3 -m unittest tests.test_klk005_doc_wiring -v`: 3件実行、全pass（新規追加分）
- pytestは本環境に未インストール（`No module named pytest`）のためunittestで実行。orchestratorの事前実測（25/25, 558/558）と一致することを独立に確認した
- `test_check_spec_structure.py`由来のResourceWarning（未クローズファイルハンドル）が出力されるが既存の警告でKLK-005の変更とは無関係。テスト結果（OK）には影響なし

## 2. AC別検証結果

- **AC1**: CLAUDE.mdの「## ポリシー管理の原則」節を確認。見出し・原則文（「再肥大化の防止」含む）・手順1,2・1行ポインタ文のみで構成され、表本体・締め文は残っていない。表本体・締め文は`docs/policy-registry.md`「## ポリシー一覧」節に完全移設されている（AC1充足）
- **AC2**: チケットログ（`tickets/active/KLK-005_...md`）2026-08-17 11:30エントリに「AC2の結論: スラッシュコマンド一覧表も分離する」と根拠3点が記録済みであることを確認（読み取りのみ、編集なし）。CLAUDE.md「## スラッシュコマンド一覧」節がREADME.mdへのポインタ3行に置換されている実装を確認（AC2充足）
- **AC3**: `wc -c CLAUDE.md` = 12,785バイト。閾値 21,252×0.65=13,813.8バイト以下を充足（約39.85%削減）。自分で実行し確認済み（AC3充足）
- **AC4**: `.claude/commands/`・`.claude/skills/`・`docs/`（designs/CHANGELOG除く）配下をgrepし「ポリシー管理の原則」「ポリシー管理表」の現行参照が0件であることを確認。docs/policy-registry.md・README.md・.claude/skills・.claude/commandsの各パスの実在をls確認。tests/test_klk003_doc_wiring.py・test_klk004_doc_wiring.pyの計7アサーション全pass（AC4充足）
- **AC5**: docs/policy-registry.md 37行目「CLAUDE.md＝インデックス＋共通定義の維持」行の「定義（正）」列が「CLAUDE.md ポリシー管理の原則（再肥大化の防止）」を指すことを確認。新規追加テスト`TestPolicyRegistrySelfReferenceRow`で機械的に固定（AC5充足）

## 3. エッジケース検証（表内容の完全性・過剰置換なし）

- 移設前CLAUDE.md（コミット8707692の親、`git show 8707692^:CLAUDE.md`）の159-188行目（表28行データ部161-188行目）と、現行`docs/policy-registry.md`11-38行目をdiffで突合
- 差分は9行のみ、いずれも「本ファイル」→「CLAUDE.md」の置換（cancelledステータス行／チケット状態の不変条件行／SPEC.md書き込みの人間承認行／チケット・SPEC.mdのBash書き換え禁止行／done/20件超のアーカイブ提案行／チケット書き込みのorchestrator専任行／worktree分離行(4列目)／プロジェクト略称の確定行／CLAUDE.md＝インデックス＋共通定義の維持行）。設計書§4-1が列挙する9箇所と完全一致
- それ以外の19行は1文字も違わないことを確認（表内容の完全性を確認、想定外の欠落・改変なし）
- 締め文は文言が変更されている（「上記「再肥大化の防止」の2手順に従い」→「`CLAUDE.md`「ポリシー管理の原則」（再肥大化の防止）が定める2手順に従い」）。これは設計書§4-1に明記された意図的なリライトであり、9箇所リストとは別枠（自己参照の明確化目的）

## 4. 過剰置換チェック（154・158行目相当の自己参照）

- 現行CLAUDE.md「## ポリシー管理の原則」節を`awk`で抽出し「本ファイル」の残存箇所を確認
- 2箇所残存: (1) イントロ文直後の「再肥大化の防止（構造維持の原則）:** 本ファイルが本文として持ってよいのは…」、(2) 同文中「新しいポリシー・手続きを追加するときは、本ファイルへ本文セクションを追加せず」
- いずれも設計書が「維持すべき自己参照」と明示した154・158行目相当の文であり、意図どおり書き換えられていないことを確認（過剰置換なし）

## 5. 追加テストの要否判断

- 本チケットはドキュメント分離のみでプロダクションコード変更を伴わないが、AC3（バイト閾値）とAC5（自己参照行の定義列）は将来の編集で無言に後退しうる性質のため、`tests/test_klk005_doc_wiring.py`を新規追加した
- 追加テスト詳細はチケット本文「Added Tests」参照
