# KLK-006 Quality Gate検証レポート（tester）

worktree: `/home/bzg55/workspace/breeze/kenesis-loop-kit.wt/KLK-006`
ブランチ: `feature/KLK-006-extract-spec-section`

## 1. テスト実行結果

- `python3 -m unittest discover -s tests -v` を実施前後2回実行。
- テスト追加前: 617件成功（implementerの自己申告値と一致、OK）。
- テスト追加後: 622件成功（追加した5件を含む、OK）。失敗・エラーなし。

## 2. AC個別検証

### AC1（実装がcheck_spec_structure.pyのパーサを流用し、READONLY_SCRIPTSに登録）
- `extract_spec_section.py` 23-25行目で `sys.path.insert(0, _SCRIPTS_DIR); import check_spec_structure as checker` を確認。`find_id()`内で `checker.split_sections`/`checker.split_subsections`/`checker.table_key_ids` を呼び出しており複製なし。
- REQ/SCR/IFそれぞれについて見出しパス＋本文（表ヘッダ含む）を出力することを`TestFindId`5件・CLI出力の`assertIn`で確認。
- `.claude/hooks/guard_bash_writes.py` 409-412行の`READONLY_SCRIPTS`に`.claude/skills/spec-interview/scripts/extract_spec_section.py`が追加済み。`test_extract_spec_section_allow`でBash経由の実運用可能性を確認。
- 判定: **満たす**

### AC2（該当なし系exit 0限定・複数一致WARN）
- `classify()`で invalid_format（形式不正・桁数不一致）/ unsupported_prefix（EH/NFR/OQ）/ 該当なし（未定義ID）の3系統を`main()`が理由付きでexit 0のまま出力することを`test_cli_unsupported_and_invalid_format_are_exit_zero`・`test_cli_exit_codes`で確認。
- exit 2はファイル不在・引数不足・デコード失敗のみ（`test_cli_exit_codes`で4パターン全て検証: 正常0/該当なし0/引数なし2/ファイルなし2/SJISデコード失敗2）。
- 複数一致は`find_id()`がエラーを投げず全件を配列で返し、`main()`が`[WARN]`+全件出力（`test_duplicate_across_subsections_returns_multiple`でロジックを確認、CLI側の[WARN]出力自体は`main()`コード自体を読んで確認。専用CLIテストはないがロジックは`find_id`テストで検証済み）。
- 判定: **満たす**

### AC3（テストカバレッジ・discoverが全件成功）
- `tests/test_extract_spec_section.py`: 正常系(REQ Must/Should/Could, SCR, IF)、該当なし3パターン(未定義/対象外prefix/形式不正)、複数一致WARN系(find_idレベル)、CLI exit code(0/2、SJISデコード失敗含む)を網羅。
- `tests/test_guard_bash_writes.py`: `test_extract_spec_section_allow`/`test_extract_spec_section_wrong_script_deny`/`test_extract_spec_section_disguised_directory_prefix_deny`の3件を確認（773-792行）。
- `python3 -m unittest discover -s tests` は全件成功（622件）。
- 判定: **満たす**

### AC4（investigator/architect/reviewer.mdへの追記）
- investigator.md 84行目・reviewer.md 54行目・architect.md 56行目に設計書§4の文言と一字一句一致する行を確認（grep突合済み）。
- architectはGrep+Read代替方式の文言であることを確認（Bashツールを持たない前提と整合）。
- CLAUDE.md本体には `git diff 74babfe..3851dcf -- CLAUDE.md` で差分なしを確認。
- 判定: **満たす**

### AC5（policy-registry.mdへの1行追加・4列書式維持）
- docs/policy-registry.md 20行目に該当行を確認。19行目（既存行）と同型の4列書式（ポリシー/定義（正）/実行責任者/転記先・強制）。
- `awk -F'|' 'NF!=6 && NF>1'` でテーブル内の列数崩れがないことを機械確認（該当行なし）。
- CLAUDE.md本体は無編集（AC4検証と同一diffで確認済み）。
- 判定: **満たす**

## 3. 設計書§9末尾「テスト観点」との突合

| テスト観点 | カバー状況 |
|---|---|
| classify()のREQ/SCR/IF正常判定 | `test_req_supported`/`test_scr_supported`/`test_if_supported` |
| 桁数不一致(REQ-1等) | `test_digit_mismatch_too_few_invalid_format`/`_too_many_` |
| EH/NFR/OQのunsupported_prefix | `test_eh/nfr/oq_unsupported_prefix` 3件 |
| 非ID文字列("abc") | `test_non_id_string_invalid_format` |
| find_id() REQ Must/Should/Could各正常抽出 | `test_req_must/should/could_extracted` |
| find_id() SCR/IF正常抽出 | `test_scr_extracted`/`test_if_extracted` |
| legacyフィクスチャでのセクション全体フォールバック | `test_legacy_fallback_to_whole_section` |
| 同一IDが2小見出しに存在する複数件返却 | `test_duplicate_across_subsections_returns_multiple` |
| CLI exit code(0/2、SJISデコード失敗含む) | `test_cli_exit_codes` |
| モック方針: 自己完結フィクスチャ | FIXTURE/LEGACY_FIXTURE/DUPLICATE_FIXTUREを独自定義、CONFORMANT非依存を確認 |
| 回帰: test_guard_bash_writes.py新規3件+既存全件成功 | 622件全件OK（既存check_spec_structure.py関連・KLK-013偽装パターン群含む） |

設計書§9の全項目がカバー済みであることを確認した。

## 4. 追加したエッジケース（テストのみ追加、プロダクションコード無変更）

実装コードを実際に叩いて未カバーの挙動を発見し、以下5件を`tests/test_extract_spec_section.py`へ追加した。

1. `test_lowercase_prefix_invalid_format` — `classify("req-001")` → 実装は`re.fullmatch`が大文字化前のid_全体と照合するため、桁数が正しくてもprefixが小文字だと`invalid_format`になる（`supported`にならない）。この非自明な挙動を固定するリグレッションテスト。
2. `test_mixed_case_prefix_invalid_format` — `classify("Req-001")` も同様に`invalid_format`。
3. `test_id_with_leading_whitespace_invalid_format` / `test_id_with_trailing_whitespace_invalid_format` — ID前後の空白は正規表現アンカー(`^...$`)によりマッチせず`(None, "invalid_format")`。
4. `test_cli_empty_spec_file_no_crash_exit_zero` — 空ファイルをCLIに渡してもクラッシュせずexit 0・「該当なし」を返すことを確認（`split_sections`が空文字列に対して例外を投げないことの回帰防止）。

いずれも実行して事前にactual値を確認した上でテストとして固定した（設計・AC範囲内の受動的な回帰防止であり、新たな仕様要求ではない）。

## 5. 機密情報チェック

- `git diff 74babfe..3851dcf`（KLK-006の全コミット）に対しAPIキー・パスワード・接続文字列等のパターンでgrepし、該当なし（implementerのセルフレビュー記述内の単語一致のみで実データなし）。
