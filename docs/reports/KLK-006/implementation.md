# KLK-006 実装レポート（implementer）

worktree: `/home/bzg55/workspace/breeze/kenesis-loop-kit.wt/KLK-006`
ブランチ: `feature/KLK-006-extract-spec-section`

## Phase 1（コミット: 40dd60a）

- 新規: `.claude/skills/spec-interview/scripts/extract_spec_section.py`
  設計書 `docs/designs/KLK-006.md` §4のコードをそのまま配置（`check_spec_structure.py`
  を `sys.path.insert` 経由でimportし、`split_sections`/`split_subsections`/
  `table_key_ids` を流用）。`classify()`（REQ/SCR/IF判定、桁数不一致・EH/NFR/OQ・
  非ID文字列の区別）と `find_id()`（小見出し単位抽出＋旧形式フォールバック＋
  複数一致時の全件返却）、CLI `main()`（exit 0=正常/該当なし共通、exit 2=引数
  不足・ファイルなし・デコード失敗）を実装。書き込み経路は一切持たない。
- 新規: `tests/test_extract_spec_section.py`（19テスト）
  - 動的import（`importlib.util.spec_from_file_location`）は
    `test_check_spec_structure.py` と同型のパターンを踏襲。
  - フィクスチャは本テスト専用の自己完結フィクスチャ3種を新規定義し、
    `test_check_spec_structure.CONFORMANT` には依存しない（設計書§5の指示どおり）。
    - `FIXTURE`: §5(Must/Should/Could各1件のREQ)・§6(画面一覧のSCR、提供IF一覧の
      IF)を含む正常系フィクスチャ
    - `LEGACY_FIXTURE`: 小見出しの無い旧形式§5（セクション全体フォールバック検証用）
    - `DUPLICATE_FIXTURE`: 同一ID(REQ-777)がMust/Should両方に定義された非準拠SPEC
      （複数件返却の検証用）
  - `TestClassify`（9件）: REQ/SCR/IF正常判定、桁数不一致（REQ-1・REQ-0001）の
    invalid_format判定、EH/NFR/OQのunsupported_prefix判定、非ID文字列("abc")の
    invalid_format判定
  - `TestFindId`（8件）: REQ Must/Should/Could各正常抽出、SCR/IF正常抽出、該当なし
    (空リスト)、legacy fallback、重複2件返却
  - `TestCli`（2件）: subprocess経由のexit code契約（正常0・該当なしも0・引数なし2・
    ファイルなし2・SJISデコード失敗2）、unsupported_prefix/invalid_formatが
    exit 0のまま出力に理由が含まれることの確認

## Phase 2（コミット: 7d304a3）

- `.claude/hooks/guard_bash_writes.py`: `READONLY_SCRIPTS` タプルへ
  `.claude/skills/spec-interview/scripts/extract_spec_section.py` を1行追加
  （設計書§4の差分どおり）。`is_readonly_script_call()` 等の判定ロジックは無変更。
- `tests/test_guard_bash_writes.py`: 設計書§4記載の3テストを
  `test_disguised_directory_prefix_absolute_deny` の直後にそのまま追加
  （`test_extract_spec_section_allow` / `test_extract_spec_section_wrong_script_deny`
  / `test_extract_spec_section_disguised_directory_prefix_deny`）。

## Phase 3（コミット: efd0144）

- `.claude/agents/investigator.md` / `.claude/agents/reviewer.md` /
  `.claude/agents/architect.md`: 設計書§4「エージェント定義差分」記載の文言を
  一字一句そのまま、指定の直後行へ追加。既存行は無変更。
- `docs/policy-registry.md`: 設計書§4記載の1行を19行目（SPEC構造の機械チェック行）
  の直後へ追加。4列書式を保持。CLAUDE.md本体は無編集。

## テスト実行結果

- 各Phase完了時点、および全Phase完了後に
  `cd /home/bzg55/workspace/breeze/kenesis-loop-kit.wt/KLK-006 && python3 -m unittest discover -s tests -v`
  を実行し、いずれも `OK`。
  - Phase1完了時点: 614件成功（ベース595件 + `test_extract_spec_section.py` 19件新規）
  - Phase2完了時点: 617件成功（614件 + `test_guard_bash_writes.py` 3件新規）
  - Phase3完了時点: 617件成功（ドキュメント・エージェント定義のみの変更のためテスト件数に変化なし）

## セルフレビュー時の確認事項

- `git diff` で3コミットそれぞれの差分を確認し、APIキー・パスワード・接続文字列
  等の機密情報が含まれていないことを確認済み。
- 設計書§4の実装詳細・エージェント定義差分・guard_bash_writes.py差分・
  policy-registry.md差分は、記載された文言・old_string/new_stringをそのまま
  適用し、独自の解釈・変更は加えていない。
