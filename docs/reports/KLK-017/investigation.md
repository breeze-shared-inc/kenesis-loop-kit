# KLK-017 調査詳細（investigator）

調査日: 2026-08-17
モード: Mode A（Ticket-driven）

## Findings

1. **C10未反映を確認**: 設計書 `docs/designs/KLK-010.md` は第7版のまま。C10（`prev_regex`によるAWL-2開始条件判定）・H6・H7・INV-AWKLEX-14は本文に一切登場しない（`grep -n "C10"` 0件）。実装は`prev_regex`で対応済み（`.claude/hooks/guard_bash_writes.py`）。§4-1但し書き（1382行目）・R36/R37（3109-3110・3315行目）はいずれもC10の内容を含まないまま。
2. **INV-SED-09に重大なID競合**: チケットはH7を新規IDとして「INV-SED-09」を指定しているが、このIDは既にKLK-015が使用済み（`tests/test_guard_bash_writes.py` 392行目、`sed -n '1w tickets/active/APP-001.md' in.md` → 期待値`deny`、KLK-015のSED-7対応の一部）。H7（アドレス前置きw/W）は現に`sed_program_violation`のホワイトリスト方式によりKLK-015で構造的に解消済みと判断できる（w/Wが`SED_SAFE_PROGRAM_CHARS`から除外されているため位置に関わらず全て`unsafe`判定）。
3. **KLK-014・KLK-015は両方完了済み**: `tickets/done/`に存在。チケット自身の指示（「先にKLK-014/KLK-015が完了した場合は`deny`で登録」）が適用される局面。H6についても`INV-SH-22`はコード中に未存在（最大`INV-SH-21`）だが、KLK-014の修正（`_extract_degraded_substs`によるdegradedの再帰評価）でH6の再現コマンドは既に`deny`化されている可能性が高い（`test_h6_*`系のunittestメソッドで固定されているが、`INVENTORY_CASES`への行としては未登録）。
4. **SV-22の前提が変化**: README.md・モジュールdocstringの現在のsed w/W記述は、SED-7導入後の条件付きで正確な説明（`w`/`W`/`r`/`R`/`e`/`a`/`i`/`c`/`b`/`t`/`T`等を許可せず読み取り系のみ許可）になっており、「無条件の主張」ではない。チケットが想定する「アドレス前置き形は未対応」という注記を追加すると、現状（既に対応済み）と矛盾する誤った記述になるリスクがある。
5. **LEGACY_DENY_COMMANDS件数は3者で不一致**: 設計書=122、チケット本文=126、実測（AST解析）=**130**。126はKLK-010完了直後（コミット`2671d11`）の値で、その後KLK-013が4件追記して130になっている。件数はKLK-010完了後も他チケットの影響で変化し続けている。

## Evidence

- `docs/designs/KLK-010.md` 1382行目（§4-1但し書き）・849-880行目（§3-6 D11・AWL-2定義に`prev_regex`記述なし）・3109-3110行目（R36/R37）・2939-2940行目（Phase14/15「未実施」）・3020行目（V-13定義）・3030行目（§4-9分類1の判定手順）（kind: local_docs）
- `.claude/hooks/guard_bash_writes.py` 1390・1447・1493・1511・1517行目（`prev_regex`実装、C10修正本体）・1838-1856行目（`sed_program_violation`、w/W除外の仕組み）・2229-2318行目（`degraded_violation`、P9形式の構造化ブロックなし）・456行目（`SED_WRITE_RE`、P9形式なし）（kind: codebase）
- `tests/test_guard_bash_writes.py` 392-407行目（INV-SED-09〜16、既存・期待値deny）・486行目（INV-SH-21が最大）・323-533行目（INVENTORY_CASES、AST実測80件）・63-292行目（LEGACY_DENY_COMMANDS、AST実測130件）（kind: codebase/empirical）
- `git log`（`2671d11`・`25dcce5`・`fd7d561`・`0a42478`・`e26fcf4`のコミットメッセージ実測）（kind: empirical、2026-08-17実行）
- `python3 -m unittest tests.test_guard_bash_writes`（223件）・`python3 -m unittest discover -s tests`（629件）（kind: empirical、2026-08-17実行、pytest未インストールのためunittestで実行）
- `tickets/done/KLK-014_*.md`・`tickets/done/KLK-015_*.md`（status: done確認）（kind: local_docs）

## Dependency Graph

- KLK-017 → KLK-010（設計負債の起点、done） → KLK-014（H6対処、done）／KLK-015（H7対処、done）
- `INVENTORY_CASES`（tests/test_guard_bash_writes.py）⇄ `docs/designs/KLK-010.md` §3-11（V-13が両者の1:1対応を要求）
- `sed_program_violation` ⇄ `docs/designs/KLK-015.md`（SED-7の正）／`awk_strip_literals` ⇄ `docs/designs/KLK-010.md` §3-6 D11
- KLK-025（active・todo）は`docs/designs/KLK-014.md`のPhase表を対象とし、KLK-017（`docs/designs/KLK-010.md`対象）とはファイルが別で直接競合なし

## Risk Areas

- **ID競合（最重要）**: INV-SED-09を新規登録するとKLK-015が既に使った同一IDと衝突する。architectはH7を別ID（例: INV-SED-27以降）にするか、「既に対応済みとして記録するのみ」に方針転換する判断が必要。
- **SV-22の逆行リスク**: 現状の記述は既に正確なため、チケット文言通りに「未対応」の注記を追加すると新たな誤り（実装より弱い記述）を作る。
- **件数のハードコード非推奨**: LEGACY_DENY_COMMANDSは他チケットの影響で継続的に変動する（122→126→130）。チケット自身が提示する「件数を書かない方式」の採用がより安全。
- **INVENTORY_CASES総数も同様に62→80まで増加**（KLK-014/015が独自に追加）。V-13の「62件」という設計書の数字も同じ構造的ズレを抱える。

## Assumptions

- チケット本文にある「INV-SED-09（H7）」の指定は、KLK-017起票時（2026-08-16）にKLK-015が未着手だった前提で書かれたと推測する（起票同日にKLK-015も完了しているため、時系列の詳細はUnknown扱いとする）。
- 「既存テスト437件」はKLK-010完了時点の`tests/test_guard_bash_writes.py`単体の集計値（ticket本文の記述と整合）と推測するが、集計方法（後述Unknowns）は未確定。

## Unknowns

- **V-13の「設計書全体を走査するスクリプト」の実体ファイルが見つからない**。git履行歴・現行リポジトリのいずれにも該当スクリプトなし。第6版でimplementerが作成と記載されるが、コミット済みアーティファクトとして確認できず（scratchpad等の一時ファイルの可能性があるが検証不能）。
- **「437件」の集計方法が単純なunittest実行と一致しない**。現在の`tests/test_guard_bash_writes.py`はメソッド数223（unittest実測）だが、KLK-010完了時ログは「全スイート437件」対「単体173件」を区別しており、437の内訳（サブテスト展開込みの手計算か、別ツールか）を再現する根拠がない。architectがV-16/受け入れ条件の基準値を再設定する際は、まずこの集計方法を確定させる必要がある。
- **H6（INV-SH-22相当）が現状allowかdenyか、`INVENTORY_CASES`の観点では未登録のため機械的に確認できない**。KLK-014の`test_h6_*`系ユニットテストでは検証済みだが、棚卸し表（INVENTORY_CASES）への行としては存在しないため、V-13の観点での整合は取れていない。

矛盾する記述（SV-22の前提変化、LEGACY_DENY_COMMANDS件数の3者不一致、INV-SED-09のID競合）はfusionせずそのまま報告した。architectの判断を要する。
