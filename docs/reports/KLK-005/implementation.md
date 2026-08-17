# KLK-005 実装レポート（implementer）

## 実施内容

### Phase 1: `docs/policy-registry.md` 新設 + `CLAUDE.md` 編集
- `docs/policy-registry.md` を新規作成。既存CLAUDE.md 159-190行目（ヘッダ+区切り+データ28行+締め文）を、`grep '^|'` で抽出したテーブル行同士を`diff`で突き合わせて検証しながら移設した。差分は設計書§4-1で指定された9箇所のみで、いずれも「本ファイル」→「CLAUDE.md」の置換（cancelledステータス行／チケット状態の不変条件行／SPEC.md書き込みの人間承認行／チケット・SPEC.mdのBash書き換え禁止行／done/20件超のアーカイブ提案行／チケット書き込みのorchestrator専任行／worktree分離行(4列目)／プロジェクト略称の確定行／CLAUDE.md＝インデックス＋共通定義の維持行）。
- CLAUDE.md 6行目のポインタ文を `docs/policy-registry.md` 参照へ更新。
- 「## スラッシュコマンド一覧」節（旧10-33行目、表14行+説明2行）を、README.md「スラッシュコマンド」節へのポインタ3行に圧縮。
- 「## ポリシー管理の原則」節（旧150-191行目）を、見出し＋イントロ文（`docs/policy-registry.md`参照に更新）＋原則文（154-158行目相当、無変更）＋手順1・2（手順2の参照先のみ`docs/policy-registry.md`へ更新）＋1行ポインタ文のみに圧縮。見出し自体は削除していない。
- 任意項目(d)として「## ドキュメント管理ルール」表へ`docs/policy-registry.md`の1行を追加（`docs/security-policy.md`行の直前）。

### Phase 2: 回帰テスト2ファイルの改訂
- `tests/test_klk003_doc_wiring.py`: `CLAUDE_MD`定数を削除し`POLICY_REGISTRY_MD = os.path.join(_util.REPO, "docs", "policy-registry.md")`を追加。`TestClaudeMdPolicyTable`のdocstringを「docs/policy-registry.md ポリシー管理表への1行追加（KLK-005でCLAUDE.mdから分離）」に変更、`setUp`を`extract_section(read(POLICY_REGISTRY_MD), "ポリシー一覧")`に変更。4つのtestメソッド本体は無変更。
- `tests/test_klk004_doc_wiring.py`: 同様に`CLAUDE_MD`削除・`POLICY_REGISTRY_MD`追加、`TestClaudeMdPolicyRow`のdocstring・`setUp`を同様に変更。3つのtestメソッド本体は無変更。

## 実測結果

- `wc -c CLAUDE.md`: **12,785バイト**（着手時基準21,252バイトから約39.85%削減。AC3の閾値13,813.8バイトを大きく下回り達成）。
- `python3 -m unittest tests.test_klk003_doc_wiring tests.test_klk004_doc_wiring -v`: 25件中25件pass（うちKLK-005関連7アサーション: `TestClaudeMdPolicyTable`4件+`TestClaudeMdPolicyRow`3件、全てpass）。
- `python3 -m unittest discover -s tests -p "test_*.py" -v`: 全558件pass、巻き添え不合格なし（実行環境にpytestが未インストールのため`python3 -m unittest`で代替実施。設計書§9のテスト観点も「またはunittest実行で確認」と明記されているため許容範囲内と判断）。
- `docs/policy-registry.md`の28データ行を`grep '^|'`で抽出し、移設元CLAUDE.mdの該当行と`diff`で突き合わせ、9箇所の意図した置換以外に差異がないことを確認済み（上記Phase1参照）。

## コミット

- `8707692` `[KLK-005] Phase 1: docs/policy-registry.md新設+CLAUDE.md編集`
- `a75d5d6` `[KLK-005] Phase 2: テスト参照先改訂`

## 残存リスク

- 実行環境にpytestが未インストールのため、tester側での`-v`実行時にpytest形式の出力（テスト名の表示形式等）がunittestと異なる可能性がある。挙動自体（pass/fail判定）に差異はない想定だが、tester環境でpytestが利用可能か要確認。
- README.md「## スラッシュコマンド」節の将来的なドリフトは設計書のリスクとして許容済み（本チケットの対応範囲外）。
