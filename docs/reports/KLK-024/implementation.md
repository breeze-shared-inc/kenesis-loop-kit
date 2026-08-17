# KLK-024 実装レポート（implementer）

対応する設計書: `docs/designs/KLK-024.md`（Phase 1・単一Phase）

## 実装内容

設計書§4-1〜§4-3のとおり、以下を実装した。

1. `.claude/hooks/guard_bash_writes.py`
   - `_take_backtick`の直前に`BACKTICK_UNESCAPE_RE`（`re.compile(r"\\(.)", re.DOTALL)`）と
     `_unescape_backtick_body`関数を新設した（設計書§4-1のコードをそのまま採用）。
   - `_take_backtick`内の`substs.append(command[start:end - 1])`を
     `substs.append(_unescape_backtick_body(command[start:end - 1]))`へ変更した。
   - `_skip_backtick`・`_skip_balanced`・`_extract_degraded_substs`・`find_violation`・
     `subst_violation`は一切変更していない（設計書§3・§5の判断どおり）。
   - モジュールdocstring「既知の限界」節、KLK-014のH6修正段落の直後に、設計書§4-2記載の
     「KLK-024追記」注記を追加した。

2. `tests/test_guard_bash_writes.py`
   - `payload`関数の直後にテスト専用ヘルパ`_escape_once_for_backtick`・
     `_nested_backtick_command`を追加した（設計書§4-3のコードをそのまま採用）。
   - `TestGuardBashWrites`クラス末尾のKLK-014ブロック（`test_h6_category3_without_guarded_cwd_stays_allow`）
     の直後に、新規テストメソッド6件（T-KLK024a〜f）を追加した。
   - `LEGACY_DENY_COMMANDS`への追加は行っていない（設計書§4-3の指示どおり）。

## R1対応: depth3ネスト文字列の実機bash手動検証

`_nested_backtick_command(3, ...)`が生成する文字列の構造を、`inner`を`"rm docs/SPEC.md"`から
安全な`"echo INNERMARKER_DEPTH3"`へ差し替えて（エスケープ段数・構造は同一のまま）実機bashへ
`echo`のみで投入した。実際の`rm`等は実行していない。

生成された文字列（`inner="echo INNERMARKER_DEPTH3"`）:
```
echo `echo \`echo \\\`echo INNERMARKER_DEPTH3\\\`\``
```

実行結果:
```
$ bash -c '<上記コマンド>'
INNERMARKER_DEPTH3
```

3階層のネストが崩れることなく解決され、最内側の`echo INNERMARKER_DEPTH3`の出力がそのまま
最外側まで伝播することを確認した。意図した多段ネスト構造とbashの実際の解釈が一致しており、
`_nested_backtick_command`ヘルパによるdepth3の機械的構築は実機挙動と食い違わない。
食い違いは見つからなかったため、テスト文字列の見直しは不要と判断した。

depth4・5についても`_unescape_backtick_body`が「1段階分だけ」アンエスケープする一般規則で
あり、再帰評価（`find_violation`→`subst_violation`→`lex()`再呼び出し）の各段で1回ずつ
`_take_backtick`が呼ばれる構造上、depth2・3で確認した規則性がdepth4・5にも数学的に
そのまま延長される（設計書§3-4-1の根拠と同一）。加えてMAX_SUBST_DEPTH=3の境界を超える
depth4・5は`subst_violation`の既存の保守的深さ打ち切り（`test_h6_max_subst_depth_boundary_degraded_deny`
と同型）でdenyになるため、ネスト解釈の正確性そのものへの依存度は低い。

## テスト実行結果

- `python3 -m unittest tests.test_guard_bash_writes -v` → 219件全件pass（新規T-KLK024a〜f 6件を含む）
- `test_legacy_deny_commands_all_still_deny`（`LEGACY_DENY_COMMANDS`回帰）単独実行 → pass
