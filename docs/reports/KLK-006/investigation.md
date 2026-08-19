# KLK-006 調査レポート（investigator）

## 1. check_spec_structure.py 見出しパーサの実装方式
- 正規表現ベース。`## N. 見出し`(数字付きセクション、53-60行)と`### 見出し`(小見出し、63-70行)の2階層で本文をスライスする。
- ID検出は2系統: (a) `ids_in(text, prefix)` = `re.findall(rf"{prefix}-\d{{3}}", text)` で本文全体からの緩い抽出(96-97行)、(b) `table_key_ids(body, prefix)` = `re.findall(rf"^\|\s*({prefix}-\d{{3}})\s*\|", body, re.M)` で表の主キー列限定の厳密抽出(100-102行)。ID重複検査やUIなし判定などACの厳密判定は後者を使う。
- `table_rows(body)`(73-84行)はMarkdown表を区切り行を除いてセルリスト化。`column_index(rows, name, default)`(87-93行)は列名からインデックスを解決し、列追加・並び替えに耐える設計。
- 新規抽出スクリプトが流用すべき最有力候補: `split_sections`, `split_subsections`, `table_key_ids`, `ids_in`。ただし新規スクリプトは「該当ID→どのセクション/小見出しの表に含まれるか」を特定する必要があり、`check_spec_structure.py`側にはその逆引き関数は存在しない(新規実装が必要)。

## 2. docs/SPEC.md の実在確認
- 本リポジトリには`docs/SPEC.md`が存在しない(`ls`はexit code 2, "No such file or directory")。KLK-006時点では実SPECでの動作確認ができない。
- 唯一のテンプレート準拠サンプルは`tests/test_check_spec_structure.py`内の`CONFORMANT`定数(20-124行)。これが新規スクリプトのテストフィクスチャの土台になりうる。

## 3. SPEC_TEMPLATE.md のID記法
- REQ-ID: `## 5. 機能要件` 配下、`### Must(必須)` / `### Should(できれば)` / `### Could(余裕があれば)` の3小見出しそれぞれの下に表があり、1列目(`| ID | 要件 | 関連画面 | 備考 |`)がREQ-xxx(76-95行)。
- SCR-ID: `## 6. 画面・インターフェース一覧` > `### 画面一覧` の表(`| ID | 画面名 | ... |`, 107-113行)。
- IF-ID: 同セクション > `### 提供インターフェース一覧` の表(`| ID | 名称 | 種別 | ... |`, 115-122行)。UIなしプロジェクトでは「該当なし」の明記が許容される(check_spec_structure.pyのno_ui判定と対応)。
- したがってチケット概要の「見出し記法(例: `## REQ-001: ...`)」という記載は実物と一致しない。見出しではなく表の主キーで特定する設計が必須。

## 4. tests/ の既存テスト構成
- フレームワーク: Python標準`unittest`のみ。pytest不要、依存追加なし(`tests/README.md` 4行目)。
- 実行方法: `python3 -m unittest discover -s tests -v`(プロジェクトルートから)。
- 命名: `test_<対象名>.py`。動的import(`importlib.util.spec_from_file_location`)でスクリプトファイルをモジュールとして読み込むパターンが`test_check_spec_structure.py`(6-17行)で確立済み。新規スクリプトのテストも同じ手法で対象スクリプトを直接import可能。
- CLI契約は`subprocess.run([sys.executable, SCRIPT, *args], ...)`でexit codeを検証するテスト(281-301行)が前例。新規スクリプトも「該当なしは非エラー」というAC2をこの形式で検証すべき。
- `tests/README.md`(25-28行)には「ルールを変更したら対応するテストを更新して全件パスを確認すること」という運用注記があり、新規テスト追加後は`python3 -m unittest discover -s tests`の全件成功を確認する必要がある。

## 5. エージェント定義への追記箇所
- `investigator.md`: Ticket Integrationの「On start」相当の記述(83行)への追記が候補。
- `architect.md`: Ticket Integration「作業開始時: チケットの概要・受け入れ条件・investigatorの調査結果（実装メモ）を読み取る」(55行)がSPEC参照の起点。ここに「SPECは対象IDのみ抽出スクリプトで読む」を追記するのが自然。
- `reviewer.md`: Ticket Integration「作業開始時: チケットの受け入れ条件・実装メモ・testerのQuality Gate結果を確認してからレビューを開始」(53行)、および概要記述の「docs/SPEC.mdおよびdocs/designs/{ID}.mdとの整合性チェック」(3行目)がSPEC参照箇所。
- 3ファイルとも「全文読みはフォールバック」の一文を明示することがACの要求。

## 6. docs/policy-registry.md の表構造
- 列は`| ポリシー | 定義（正） | 実行責任者 | 転記先・強制 |`の4列固定(9行目がヘッダ)。
- 直近の類似行(19行目)がテンプレート:
  `| SPEC構造の機械チェック（テンプレート準拠の受付） | .claude/skills/spec-interview/scripts/check_spec_structure.py（構造の正はSPEC_TEMPLATE.md） | /setup / /interrogate-spec / /spec-interview | setup.md 手順5 診断表 / interrogate-spec SKILL.md Phase 0 構造受付 / spec-interview SKILL.md Step 3・改訂モード手順5 |`
- 新規行はこの書式に倣い、「定義（正）」列に新規スクリプトのパス(+設計書docs/designs/KLK-006.md参照)、「実行責任者」列にinvestigator/architect/reviewer、「転記先・強制」列に3エージェントファイルの追記箇所を列挙する形になる見込み。

## 7. .claude/skills/spec-interview/scripts/ の既存ファイル一覧
- `check_spec_structure.py`(1ファイルのみ)と`__pycache__/`のみ。新規スクリプトはこのディレクトリに単純追加できる(名前衝突なし)。

## 8. 呼び出し経路の手がかり（CLI/Bash）
- `check_spec_structure.py`は一貫して「Bashツールでのpython3直接実行」として使われている(setup.md 58行、interrogate-spec/SKILL.md 54行、spec-interview/SKILL.md 85行、いずれも`python3 .claude/skills/spec-interview/scripts/check_spec_structure.py docs/SPEC.md`の形)。新規スクリプトも同じCLI呼び出し形が前提と推測される。
- **重大な制約**: `.claude/hooks/guard_bash_writes.py`はBashコマンド中に保護対象パス(SPEC.md, tickets/active|done)が引数として現れると原則deny判定する(`guarded_paths()`, 666-673行)。唯一の例外が`READONLY_SCRIPTS`という完全パス一致の許可リスト(406-411行、現在`check_spec_structure.py`のみ登録、1190-1223行の`is_readonly_script_call()`で判定)。
- `scripts/list_tickets.py`のdocstring(16-20行)には「将来パスを引数化する変更を行う場合は、guard_bash_writes.pyのREADONLY_SCRIPTSにこのスクリプトを追加する変更が必須になる」と明記されており、同型の制約が新規抽出スクリプトにもそのまま当てはまる。新規スクリプトはdocs/SPEC.mdをCLI引数に取る設計になる見込みが高く(AC「指定IDの該当セクションを抽出」)、Bash経由で実行させたいなら`READONLY_SCRIPTS`への追加(と`test_guard_bash_writes.py`への対応テスト追加)が実質的な前提条件になる。ticketのAC文言にはこの言及がなく、architectが設計時に明示的にスコープ判断すべき事項。

## 次エージェント（architect）への引き継ぎ推奨事項

1. 最優先で解決すべき設計判断: 新規スクリプトをBashツール経由で実運用可能にするなら、`.claude/hooks/guard_bash_writes.py`の`READONLY_SCRIPTS`への追加と`tests/test_guard_bash_writes.py`への対応回帰テスト追加を設計書のスコープに明示的に含めるか、含めない場合はその理由を明記すること。
2. ID記法はチケット概要の「見出し記法」ではなく実物(`SPEC_TEMPLATE.md`)の「表の主キー列」であることを前提に設計し直すこと。`table_key_ids()`/`table_rows()`をベースに、ID→所属section/subsection→該当行、という逆引きロジックを新規実装する必要がある。
3. 抽出粒度(§全体か、Must/Should/Could等の小見出し単位か、該当表の1行のみか)をAC「該当セクションと見出しパスを出力」の解釈として明確に確定し、設計書に記載すること。
4. テストは`tests/test_check_spec_structure.py`の実証済みパターン(動的import・CONFORMANTフィクスチャ流用・subprocess CLI契約テスト)にそのまま追随可能。

Handoff: 調査完了・Unknownsなし。次エージェントとしてarchitectへの委譲を推奨。
