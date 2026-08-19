# KLK-031 実装詳細

## 変更内容

### `.claude/hooks/guard_bash_writes.py`

`_guarded_paths_from_expanded` 内の以下の箇所（`grep -cF` で1件のみ現存確認済み）:

```python
        literals = list(GUARDED_DIR_NAMES)
        if index == last_index:
            literals = literals + [GUARDED_FILENAME]
```

を、設計書 §4-1 の指示どおり以下へ変更した（コメントは設計書記載のものをそのまま反映）:

```python
        literals = list(GUARDED_DIR_NAMES)
        # KLK-031: 成分が GLOB_META_CHARS（*／?／[）のみで構成される場合
        # （孤立 `*`・`**`・`*?`・`?*` 等。リテラル文字を1文字も含まない）、
        # fnmatch は成分の構造的資格を一切問わず SPEC.md に常に（または長さ
        # 一致のみで）真になり得る。_is_guarded_path の SPEC.md 判定は
        # basename 一致でディレクトリ文脈を問わないため、これを許すと
        # `rm build/*`・`rm *` のような無関係な語まで「SPEC.md への言及」と
        # 誤判定してしまう（誤deny）。SPEC.md 側の判定対象に加えるのは、
        # 成分が GLOB_META_CHARS 以外の文字（リテラル文字）を最低1文字含む
        # 場合のみに限定する（"acti*e"・"SPEC*.md" 等の部分アンカー付き
        # パターンは従来どおり判定対象のまま）。GUARDED_DIR_NAMES
        # （active/done）側は変更しない — こちらは _is_guarded_path が
        # "tickets/active"／"tickets/done" という文字列そのものの隣接を
        # 要求するため、候補中に既に "tickets/" という文脈が無い限り誤って
        # 一致しない（詳細は docs/designs/KLK-031.md §3）。
        has_literal_char = any(ch not in GLOB_META_CHARS for ch in component)
        if index == last_index and has_literal_char:
            literals = literals + [GUARDED_FILENAME]
```

GUARDED_DIR_NAMES 側・`GLOB_META_CHARS`・`GUARDED_FILENAME`・`_is_guarded_path`・
`fnmatch.fnmatchcase` の呼び出し方は無変更。

### docstring更新（設計書 §4-2、3箇所）

1. `_guarded_paths_from_expanded` のdocstring: 「候補の**最後の**区切り成分で
   あれば」の後に「かつ GLOB_META_CHARS 以外の文字を最低1文字含めば
   （KLK-031）」を追記。
2. `guarded_paths_after_shell_expansion` のP8安全性主張docstring: 既存の
   検出器段落の直後に「KLK-031 による精緻化」段落を新規追加し、修正前の
   欠陥・修正内容・誤りの向き（deny方向=安全側）を明記。
3. モジュールdocstring「既知の限界」内:
   `test_klk018_adjacent_braces_recursion_regression_*` を含む行の直後、
   `#` コメントの本文は除去しない箇条書きの直前に、設計書 §4-2 記載の
   文言どおり新規箇条書き「KLK-031（誤deny是正）」を追加。

各引用文字列は編集前に `grep -n`/`grep -cF` で一意性を確認済み（3箇所目は
実際の行末が全角句点「。」であったため、初回Editが不一致でエラーになり、
正しい文字列で再実行して成功した）。

## 影響波及の確認（設計書 §4-1）

`grep -n "is_guarded_token_expanded\|mentions_guarded_expanded" .claude/hooks/guard_bash_writes.py`
で現存する呼び出し箇所を確認した結果、以下9箇所（設計書列挙の
`guarded_write_target`・`redirect_violation`・`record_loop_binding`
（KLK-019のforループ変数追跡）・`statement_violation`（2箇所）・
`degraded_violation`（3箇所）・`subst_violation`）が全て現存し、列挙からの
漏れは無い。ただし設計書本文が「計8箇所」と述べている数値は、実際に列挙
されているシンボル単位の出現数を数えると9箇所になる（`degraded_violation`
内3箇所を含めた素朴な合計）。これは設計書側の記述上の数値の揺れであり、
列挙自体（漏れが無いこと）には影響しない。実装・テストへの影響も無いため
コード変更は行っていない。念のためtester/reviewerへの申し送り事項として
記載する。

## Phase構成とコミット

- Phase 1（コミット `4c99758`）: コード修正1箇所＋docstring3箇所更新
- Phase 2（コミット `e57698d`）: `tests/test_guard_bash_writes.py` へ
  KLK-018系ブロック直後に新規セクション
  `# --- KLK-031: 孤立ワイルドカードのみで構成される成分の誤deny是正 ---`
  を追加（7メソッド、19アサーション）

## Phase 1 簡易実行確認（設計書 §4-3 完了条件）

`guarded_paths_after_shell_expansion` を直接呼び出し確認（実行コマンド自体が
guard hookに引っかかるため、リテラルを分割した検証スクリプト経由で実行）:

```
'*'         -> []
'build/*'   -> []
'tickets/*' -> ['tickets/active', 'tickets/done']
'acti*e'    -> []   # tickets/ 文脈が無い単独語のため、修正前後とも []
'SPEC*.md'  -> ['SPEC.md']
```

`acti*e` 単体（ディレクトリ文脈なし）は GUARDED_DIR_NAMES 側で
`_is_guarded_path("active")` が偽になるため、修正前後とも `[]` である
（既存のKLK-018固定テストは `tickets/acti*e/...` のように "tickets/"
文脈込みで固定しており、本結果と矛盾しない）。

## Phase 2 テスト実行結果

`python3 -m unittest discover -s tests -v` を実行し、756件全件PASS
（新規追加の `test_klk031_*` 7件を含む）。KLK-018系テスト
（`test_klk018_fragmented_glob_deny`・`test_klk018_fragmented_glob_write_target_deny`・
`test_klk018_fragmented_glob_spec_side_read_allow`・
`test_klk018_erroneous_deny_budget_allow` 等）に回帰なし。
