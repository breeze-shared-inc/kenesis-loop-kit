# KLK-017 実装メモ（implementer）

## 前提の確認
- 設計書 `docs/designs/KLK-010.md` は既にコミット済みの状態（第8版・C10 書き戻し・
  INV-SH-22／INV-AWKLEX-14 の §3-11 登録・§10 決着事項2件反映済み）で、実装
  タスクは「設計書側の記述が先に存在する状態で `INVENTORY_CASES` へ対応する
  2行を追加する」ことのみだった（設計 → テストデータの順序を厳守）。
- 着手前にチケット「関連」欄の条件（KLK-014／KLK-015 完了時は `allow` ではなく
  `deny` として登録する）を `tickets/done/` で確認し、両チケットとも完了済みと
  確認したため、委譲プロンプトの指示どおり両方とも期待値 `deny` で登録した。

## 実施内容

### 1. INVENTORY_CASES へ2行追加
- **INV-SH-22**（H6）: `INV-SH-21` の直後（§3-11 の SH 写像表の並びに一致）に
  追加。コマンドは設計書の代表ケース・KLK-014 の `test_h6_subshell_substitution_
  all_write_vectors_deny`（T-H6a）の先頭要素と同一の
  `"ls $(rm docs/SPEC.md) #'"`、期待値 `deny`。
- **INV-AWKLEX-14**（C10）: `INV-AWKLEX-13` の直後（tuple 末尾・§3-11 の
  AWKLEX 写像表の並びに一致）に追加。コマンドは設計書の代表ケース・
  `test_awk_chained_division_after_regex_bypasses_awl4_deny`（T-C10a）の
  先頭要素と同一の `awk 'BEGIN{/x/ / system("rm SPEC.md") / 1}'`、期待値 `deny`。
- 追加順序: 設計書（既にコミット済み）→ `INVENTORY_CASES`。委譲プロンプトの
  「順序が重要」の指示どおり、設計が先に存在する状態でテスト側を追加した。

### 2. INV-SED-09（H7）・SV-22 の確認
- `docs/designs/KLK-010.md` §3-11 の INV-SED 写像表（`INV-SED-01`〜`08`）・
  V-13 行を確認し、`INV-SED-09` 以降は KLK-010 のスコープに含まれない（KLK-015
  管轄）ことを再確認した。コード・設計書とも変更していない。
- `.claude/hooks/README.md` 12行目・モジュール docstring を確認し、SED-7
  （KLK-015）導入後の条件付き記述（アドレス前置き形も含め `w`／`W` を位置に
  関わらず不許可）であることを確認した。変更していない。

### 3. V-13（設計書 INV ID と INVENTORY_CASES の機械照合）
- V-13 用の既存スクリプトの実体ファイルは調査どおり見つからなかったため、
  委譲プロンプトの指示に従い一時diffスクリプトをその場で作成し実行した
  （コミットしていない。`/tmp/claude-1000/.../scratchpad/v13_check.py`）。
- 抽出方法: 設計書 `### 3-11.` セクション本体から
  `INV-(AWK|SED|SH|AWKLEX)-\d+` を正規表現で抽出（64件）。`INVENTORY_CASES`
  タプルの各行の先頭要素（ID）を抽出（92件）。
- 結果: **「設計にあって `INVENTORY_CASES` に無い ID」は0件**（V-13 の
  ブロッカー条件を満たさない＝pass）。「`INVENTORY_CASES` にあって §3-11 に
  無い ID」は28件（`INV-AWK-21`〜`25`＝KLK-013 管轄・`INV-SED-09`〜`31`＝
  KLK-015／KLK-029 管轄）で、いずれも設計書自身が「他チケットの管轄」と
  明記している既知の差分であり欠陥ではない。

### 4. V-16（設計書と実装の1関数ずつの突き合わせ）
対象10件（V-16 行が指定する関数・定数）を `.claude/hooks/guard_bash_writes.py`
の実装と設計書の記述で突き合わせた。
- `awk_strip_literals`: `prev_regex` フラグ（C10・AWL-2 開始条件の修正本体）
  ・改行でのリセットが実装済みで、docstring も設計書 §3-6 D11 と同内容。**乖離なし**。
- `degraded_violation` / `_extract_degraded_substs`: H6 修正本体（置換境界の
  機械的抽出・無条件の内側再帰評価）が実装済みで、docstring が設計書と一致。**乖離なし**。
- `AWK_SAFE_PROGRAM_CHARS`: `\n` を収載済み（D-1）。**乖離なし**。
- `LEGACY_STATEMENT_RE`: `&` を収載済み（H5。648行目相当）。**乖離なし**。
- `_skip_balanced`: バッククォート読み飛ばし分岐（D-2）が実装済み。**乖離なし**。
- `_skip_backtick`・`normalize_line_continuations`・`lex`・
  `awk_program_violation`・`find_violation`: docstring・実装を確認し、
  設計書の対応する記述（§4-2-1・§4-2-2・AW-7）と矛盾する分岐は見つからなかった。
  **乖離なし**。
- 結論: 10件すべてで設計と実装の乖離は検出されなかった。差分報告は不要。

### 5. テスト実行
- `python3 -m unittest tests.test_guard_bash_writes -v` → 226件 OK（追加2件を含む）。
- `python3 -m unittest discover -s tests` → 647件 OK（failures 0・errors 0）。
- stderr に出た `batch_loop.py: error: ...` の2行は既存テストが意図的に異常系
  引数を渡して起動する検証の標準エラー出力であり、失敗ではない（Ran … OK で確認）。

## コード変更の有無
- 本チケットはコード変更を伴わない文書修正チケットであり、
  `.claude/hooks/guard_bash_writes.py` 等の実装ファイルは1行も変更していない。
  変更は `tests/test_guard_bash_writes.py` の `INVENTORY_CASES` への2行追加のみ。
