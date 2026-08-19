# KLK-030 調査詳細レポート（investigator）

作成: 2026-08-18（orchestrator代筆。investigatorはWrite/Editツールを持たないため）

## Findings

1. `sed_strip_literals`（`.claude/hooks/guard_bash_writes.py:2120-2257`）はトップレベルで生の文字 `s`/`y` が現れる**位置**（構文的にコマンド開始位置かどうかを一切見ない）を無条件にs/yコマンド開始とみなし、次の1文字をデリミタとして未エスケープの再出現を2回探す。閉じなければ`None`（判定不能→deny）、閉じれば内容スパンを丸ごと除去する。
2. 再現手順は現行コードでも再現した（実測。ただし実行はガード対象パス文字列自体をBashコマンド中に書けないため、構造が同一の代替文字列で検証。詳細は「Evidence」参照）。`1w widgets/active/sub/FILE-001.md` → `stripped="1w widgetsFILE-001.md"`（`/active/sub/`が消える）。ticketの記述・test-report.md §8-3の記述と一致。
3. **検出漏れ（allow化）に至る具体例は構築できなかった。** 5種の逆順（危険文字を疑似トリガーの**後**・デリミタ自体に配置）を試したが、いずれも正しくdeny、または実sedも危険動作をしない。構造的argument（下記）でも「新規の検出漏れ経路は存在しない」と推論できる（confidence: medium、非網羅的）。
4. 既存テスト（INV-SED-09〜20等）は`tickets/active/APP-001.md`をw/W後の**ファイル名**として使っており、この疑似境界探索を偶発的に踏むが、危険文字（w/W）が常にトリガーより**前**にあるため、bucket判定（deny/allow）のみを検証する`assertDeny`ではこの現象自体を固定化していない。逆順（危険文字なしで疑似トリガー→危険文字）を狙ったテストは存在しない。
5. `sed_program_violation`のdeny判定は`stripped`全体に対する「安全文字集合に無い文字が1つでもあるか」であり順序非依存。よって疑似トリガーより前に不正文字があれば、その後の誤ったスパン除去の影響は無害化される（ticket記載の通り）。

## Evidence

- `codebase`: `.claude/hooks/guard_bash_writes.py:2120-2257`（`sed_strip_literals`本体）、`:2307-2325`（`sed_program_violation`、`stripped`全体をSED_SAFE_PROGRAM_CHARSと比較）、`:570`（`SED_SAFE_PROGRAM_CHARS`定義）、`:2260-2304`（`sed_program_texts`、`-e`値または先頭位置引数のみを抽出）、`:2491-2522`（`segment_violation`のsed分岐、`sed_program_violation`の2箇所の呼び出し元）。
- `codebase`: `tests/test_guard_bash_writes.py:393-445`（`INVENTORY_CASES`のINV-SED-01〜26。特に09〜20は`tickets/active/APP-001.md`をw/W後のファイル名に使う形のみ）、`:1903-1914`（`test_inventory_cases_match_expected_decisions`、deny/allowバケットのみ検証しstripped中間結果は見ていないことを確認）。
- `local_docs`: `docs/reports/KLK-015/test-report.md:158-170`（§8-3「参考所見」。`1w tickets/active/sub/APP-001.md`→`1w ticketsAPP-001.md`の同一現象を報告済み、危険文字は常にoutへ確定済みでallow化未発見、と記載）。`docs/reports/KLK-015/review.md:15-17`（Medium Risks、実害未確認・別チケット候補として承認判断に影響しないと記載）。`docs/designs/KLK-015.md`（§6 R1等の新規denyリスク列挙に本現象は含まれていない＝設計書は本現象を正式にスコープ化していない）。
- `empirical`: investigatorセッション内Bashで`sed_strip_literals`を直接importして実行（GNU sed 4.9）。**注記:** ticketの文字列そのもの（`tickets/active/...`）を含むBashコマンドは、本hook自身（guard_bash_writes.py）のPreToolUseガードによってinvestigator自身のBash呼び出しが実際にdenyされた（メタ的な確認：ガードは意図通り作動している）。そのため`widgets`/`policy`等、構造は同一だが`tickets/active`・`SPEC.md`を含まない代替文字列で検証した。
- `general_knowledge`/推論（要検証）: 「危険文字が疑似マッチに飲み込まれて検出漏れに至るには、その手前に別の未flag危険文字（w/r/a/i/c/b/t/T/:等）が実sed上の生テキスト区間を開始している必要があるが、それらの文字自体が現れた時点で常にflagされる」という帰納的argument。これはinvestigator自身の分析結果であり、公式のsed仕様書やテストで直接裏付けたものではない（confidence: medium）。

## Dependency Graph

- `sed_program_texts(words)` → `sed_program_violation(text)` → `sed_strip_literals(text)`。呼び出し元は`segment_violation`のsed分岐（`.claude/hooks/guard_bash_writes.py:2507-2522`、`mentions_guarded_in_program`ゲート通過後）。
- `sed_strip_literals`は`_sed_skip_bracket_expression`（ブラケット式`[...]`の対応`]`探索。パスに`[`が無ければ無関係）に依存。
- `guarded_paths`/`is_guarded_token`（L2パスレイヤ、`:768`〜）は本件と**別系統**（コマンド文字列全体からの保護対象パス言及検出）であり、`sed_strip_literals`（L3・プログラム本文の安全文字判定）とは独立。この2系統の違いがticketの現象の根（パス文字列がプログラム本文側の文字走査に紛れ込む）。
- テスト側依存: `tests/test_guard_bash_writes.py`の`INVENTORY_CASES`（表駆動）と`assertDeny`/`assertAllow`（bucketのみ検証、内部stripped値は非検証）。

## Risk Areas

- 修正方針（a）「構文的にコマンド開始しうる位置に限定」を採る場合、影響範囲は`sed_strip_literals`のトップレベルループ全体の書き直しに及ぶ可能性が高い。理由: 現状は「単純な文字走査＋各コマンド固有スパンの除去」だけで、a/i/c・b/t/T/:のような「行末/ラベルまで生テキストを読む」構文は意図的に未実装（安全側=deny）としている（`docs/designs/KLK-015.md`）。「s/yの開始位置」を厳密化するには、少なくとも「直前の非空白がコマンド区切り(`;`/`{`/`}`/改行/先頭)またはアドレス直後か」を状態として持つ簡易FSMの追加が必要で、SED-7ホワイトリスト全体（`SED_SAFE_STRUCTURAL_CHARS`との整合）・既存INV-SED-01〜31の全回帰に影響しうる。
- 修正方針（b）「対応不要と判断しテストで固定化」を採る場合の影響範囲は小さい（既存コードの変更なし、テスト追加＋設計書追記のみ）。ただし「危険文字検出漏れが構造的に起こり得ない」という主張を`docs/designs/{ID}.md`に明文化するには、investigatorが今回導出した帰納的argument（Findings 3・Evidence末尾）を設計書としての正式な安全性主張（他の`sed_strip_literals`docstring内の「P8」型主張と同型）に整形し、AC8同様の実機GNU sed二方向検証をテストとして固定する必要がある。
- 誤deny予算（受け入れ条件3行目）: 境界判定を厳密化する変更を行う場合、現在「w/rコマンドのファイル名部分が偶発的に誤って除去される」ことで**たまたま**安全側に倒れているケース（INV-SED-09〜20相当）が、修正後は除去範囲が変わり、新たな誤allow/誤denyを生まないか個別確認が必要。

## Assumptions

- チケット再現手順の文字列を、guard_bash_writes.py自身のガードに阻まれず検証するため、`tickets`→`widgets`、`sub`等の構造を保った代替語に置換して実測した（本番コードは無変更、Bashのみで検証。値のみの置換であり、アルゴリズム的な性質は同一と判断）。
- `sed`コマンドの実体検証はGNU sed 4.9（本環境の`/usr/bin/sed`）を正としている。他実装（BSD sed等）の挙動は未検証（docstringも一貫してGNU sedを前提としている）。
- 「危険文字検出漏れが起こり得ない」という結論は、`w/W/r/R/e/a/i/c/b/t/T/:`が生文字として現れた時点で無条件にflagされるという現行コードの不変条件（`SED_SAFE_PROGRAM_CHARS`に含まれないことを列挙）が今後も保たれることを前提にした議論であり、SED_SAFE_COMMANDSへの将来的な追加変更があれば再検証が必要。

## Unknowns

- **確定不能（surrendered対象ではなく、tester/architectでの追加検証を推奨）:** 「危険文字検出漏れが構造的に起こり得ない」というinvestigatorの帰納的argumentは、有限個のアドバーサリアル入力（5パターン）と論理推論によるものであり、全入力空間の網羅的brute-force検証や形式的証明ではない。ブラケット式・カスタムデリミタ(`\cXXXc`)・バックスラッシュエスケープが複雑に絡む入力（現実のticket/SPECパスには通常出現しないが、攻撃者が`w REL/path`の`REL`部分に人工的な文字列を仕込むケース）は未検証。**verification_hint:** tester段階でKLK-015のAC8同様、実機GNU sedとの二方向照合を伴うfuzzing／brute-force（境界文字`s`/`y`+選択デリミタの組み合わせを網羅的に生成し、`checker allow ∧ real sed writes`の組を探索）を行うことを推奨する。

## Handoff（investigator報告より）

Unknownsに「確定不能」の1件（網羅的検証の欠如）を含むため、architectへの設計判断（修正方針（a）厳密化 or （b）文書化+テスト固定）に先立ち、この論点をブロッカーとして人間へ報告することを推奨する。ただし実害（allow化の具体例）は未発見であり、tester/architectでの追加adversarial testingで解消可能な性質のUnknownである。

---

## 追加調査（2026-08-18・人間判断「investigatorへ再調査を依頼」を受けて実施）

### 実施した検証

`sed_strip_literals`のチェッカー判定と実機GNU sed 4.9（`/usr/bin/sed`）の実際の書き込み／読み取り漏洩挙動を、境界文字`s`/`y`×デリミタ23種×危険文字12種（`w W r R e a i c b t T :`）×境界位置13カテゴリで体系的に二方向照合した。合計**3,345件**（本編9カテゴリ2,697件＋補完4カテゴリ648件）を実行し、**checker側ALLOW かつ 実機sedが実際に危険動作（w/Wでの書込・r/Rでの秘密情報漏洩）を行った組は0件**だった。

内訳:
- 本編2,697件: 先頭境界での正規s/yコマンド内への危険文字埋め込み／デリミタ自体への危険文字使用／閉じ後のフラグ位置／トリガー前後への危険文字配置／実パス構造の模倣／ブラケット式・カスタムデリミタアドレス・`/`トリガーの類似ケース
- 補完648件: アドレス前置き6種（`1`/`$`/`1,3`/`/Z/`/`0~2`/`2!`）・`;`直後・`}`直後・危険文字を区切り無しでトリガー直前に接着

副次的検証: `sed 'pd'`・`sed -n '1p d'`・`sed -n '1s/a/b/gs/h/H/p'`が実機GNU sed 4.9でいずれも構文エラー（rc=1）になることを確認。checkerが疑似境界と誤認しうる位置で実sedとの解釈が食い違う場合、実sedは黙って別解釈を実行するのではなく構文エラーで即時終了する（＝何も実行されない＝安全）という経験的裏付けであり、前回報告した構造的argument（危険文字は疑似トリガーより先に必ず生文字として検出される）を補強する。

### Unknowns（更新後の結論）

- **解消（confidence: medium→high）**: 「危険文字検出漏れが構造的に起こり得ない」という前回の推論は、3,345件の体系的brute-force・実機二方向照合で反証されなかった。KLK-015 test-report.md §8-3の記述、および構造的argumentの両方と整合する。tester段階でのAC8型実機二方向検証（前回のverification_hint）は本調査で前倒しに実施済みとみなせる。
- **残存Unknown（未解消・影響は小さいと判断）**: 今回のスコープ外の領域は依然未検証。① 境界文字トリガーを複数個・デリミタを変えながら連鎖させた入力 ② `[.` `[=` `[:` 特殊照合要素を含む大きなブラケット式と危険文字の組合せの網羅 ③ GNU sed 4.9以外の実装（BSD sed等） ④ マルチバイト・ロケール依存文字をデリミタ／パス文字として使う入力 ⑤ `sed --posix`・`-s`・`-z`等のフラグが文法を変える場合。これらは3,345件には含まれておらず、確定不能として残すのが正直な報告である。
- **verification_hint（残存分・architect/tester判断用）**: ①〜⑤は実害が構造的に生じうる可能性が今回のカテゴリよりさらに低いと考えられる（①②は「実sedとの境界一致」の一般問題でありSED-7の既存bracket/escaping前提と同型、③〜⑤は本プロジェクトの前提〔GNU sed・非POSIXモード〕から外れる）。対応不要と判断し設計書へ明文化する場合は、本調査の3,345件（またはその代表的サブセット）を`tests/test_guard_bash_writes.py`へ固定化ケースとして採用し、①〜⑤は「スコープ外」として設計書に明記する形が、KLK-015の既存の書き方（§6リスク表・a/i/c等の意図的スコープ限定）と整合的である。

### 補足（KLK-030スコープ外・副次的発見）

調査中、`.claude/hooks/guard_bash_writes.py`の`guarded_paths_after_shell_expansion`（KLK-018）に、KLK-030とは無関係な別の挙動を発見した: 孤立した`*`1文字（他のパス文字と結合していない単独のグロブワイルドカード）を含むBashコマンドは、`fnmatch.fnmatchcase("SPEC.md", "*")`が常に真になるため「SPEC.mdへの言及」と誤判定されうる（investigator自身のPython検証コマンドが誤denyされた原因）。誤りの向きは誤deny（安全側）でありallow化ではない。KLK-030のスコープ外のため深掘りしていないが、事実として記録する。orchestrator判断で別チケット化の要否を人間へ確認すること。
