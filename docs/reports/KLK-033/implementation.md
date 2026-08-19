# KLK-033 実装詳細

> implementerレポートの詳細。チケット本文の実装ノートには要点5行＋本ファイルへのポインタのみを残す。
> 実装日: 2026-08-19 / ブランチ: `fix/KLK-033-negated-class-glob-pathish-fragmentation`
> worktree: `../kenesis-loop-kit.wt/KLK-033/`

## 1. コミット構成

| コミット | 内容 |
|---|---|
| `09af704` | Phase 1: `SHELL_EXPAND_PATHISH_RE` の文字集合拡張 ＋ `is_spec_basename_fnmatch` の和集合形化 ＋ docstring 3箇所（設計書§4-5のとおり**単一コミット**） |
| （Phase 2） | テスト9件の追加 ＋ 本ファイル |

Phase 1を単一コミットにした理由は設計書§3 代替案(F)・§8のとおり。片方だけが入った中間状態では
`rm docs/[!s]PEC.md` の誤allowが到達可能なまま残る（下記§4の実測で確認）。

## 2. 変更内容（Phase 1）

### 2-1. `.claude/hooks/guard_bash_writes.py`: `SHELL_EXPAND_PATHISH_RE`

設計書§4-1のとおり、文字集合の末尾へ `!` を1文字追加した（`\]` の直後）。

```python
SHELL_EXPAND_PATHISH_RE = re.compile(r"[A-Za-z0-9_.\-/{},*?\[\]!]+")
```

直前に設計書§4-1が指定した説明コメント（10行）をそのまま追加した。
Edit前に `grep -cF "SHELL_EXPAND_PATHISH_RE = re.compile"` で現存・一意（=1）を確認済み。

### 2-2. `.claude/hooks/_ticket_lib.py`: `is_spec_basename_fnmatch`

設計書§4-2の最終形をそのまま反映した（シグネチャ無変更）。

```python
    if not isinstance(pattern, str):
        return False
    return (fnmatch.fnmatchcase("SPEC.md", pattern)
            or fnmatch.fnmatchcase("SPEC.MD", pattern.upper()))
```

- `isinstance` を早期returnに変え、非str（`None`・`123`）で `.upper()` に到達しない契約を維持。
- docstringは設計書§4-2の全文（①②の説明・非単調性の経緯・残余の限界・KLK-031ゲートとの
  レイヤー分離の注意）へ全面差し替え。
- `import fnmatch` は既存のため追加なし。

### 2-3. docstring 3箇所（`guard_bash_writes.py`）

設計書§4-3の指定アンカーへ、指定文面をインデントを合わせて挿入した。Edit前に3アンカーすべてを
`grep -cF` で一意（=1）確認済み。

| # | 挿入位置（アンカー） | 内容 |
|---|---|---|
| 1 | `_guarded_paths_from_expanded` docstring ②（`…active／done 側の照合は従来どおり大小を区別する。` の直後） | SPEC.md側の照合が和集合であることの1文（3行） |
| 2 | `guarded_paths_after_shell_expansion` docstring（`（docs/designs/KLK-032.md §3・§9 参照）。` の直後／`RecursionError 安全性` の直前） | 「KLK-033 による精緻化」ブロック（13行） |
| 3 | モジュールdocstring「既知の限界」（KLK-032箇条書きの直後／`` - **`#` コメントの本文は除去しない** `` の直前） | KLK-033箇条書き（22行） |

### 2-4. 無変更であることの確認（Phase 1完了条件）

`git diff -U0` の追加・削除行に対する `grep -c` がすべて0件であることを確認した:
`GLOB_META_CHARS = frozenset` / `has_literal_char` / `fnmatchcase(literal, component)` /
`GUARDED_DIR_NAMES`。すなわち `GLOB_META_CHARS`・KLK-031ゲート・`GUARDED_DIR_NAMES` 側比較は
バイト単位で無変更。

## 3. 追加したテスト（Phase 2・計9件）

設計書§9「テスト観点」の4群をそのまま実装した。既存メソッドは1行も変更していない。

### `tests/test_ticket_lib.py`（`class TestSpecDriftPureFunctions`・KLK-033サブ節、①群）

`test_is_spec_basename_fnmatch_non_str_returns_false` の直後へ追加。

| メソッド | 内容 |
|---|---|
| `test_is_spec_basename_fnmatch_negated_class_monotonic_true` | `[!x]PEC.md`・`[!s]PEC.md` → True（`[!s]` は和集合形の第1項でのみ真＝非単調性の回帰検出器） |
| `test_is_spec_basename_fnmatch_negated_class_excluded_false` | `[!S]PEC.md` → False（無条件Trueでないことの固定） |

### `tests/test_guard_bash_writes.py`（`class TestGuardBashWrites`・KLK-033節、②〜④群）

KLK-032節の末尾メソッド `test_klk032_case_closure_budget_deny` の本体直後へ追加。

| メソッド | 群 | 内容 |
|---|---|---|
| `test_klk033_negated_class_glob_deny` | ② | `rm docs/[!x]PEC.md`・`rm docs/[!s]PEC.md` が deny（end-to-end） |
| `test_klk033_negated_class_spec_side_read_allow` | ② | `cat docs/[!x]PEC.md` は allow（読み取りhead対称） |
| `test_klk033_pathish_and_expanded_unit` | ② | `findall` が1トークン `["docs/[!x]PEC.md"]`、`_guarded_paths_from_expanded` が `[!x]`／`[!s]` で `["docs/SPEC.md"]`・`[!S]` で `[]` |
| `test_klk033_degraded_negated_class_deny` | ③ | `rm docs/[!x]PEC.md # don't` が deny（degraded波及の証跡） |
| `test_klk033_degraded_bang_word_allow` | ③ | `rm foo!bar # don't` が allow |
| `test_klk033_bang_words_unchanged_allow` | ④ | `! grep foo bar.txt`・`find . ! -name '*.md'`・`echo foo!bar`・`echo !!`・`rm foo!bar`・`rm a!b/c.md` が全て allow |
| `test_klk033_brace_cost_with_bang_allow` | ④ | `rm a{1,2}!b{3,4}.txt` が allow（ブレース組合せ増でもフォールバックへ倒れない） |

設計書§9③の「任意」項目（degraded側の読み取りhead対称性 `cat docs/[!x]PEC.md # don't`）は
**追加していない**。設計書が「期待値を事前に断定せずtesterが実測値で固定する」と定めているため、
implementer側では期待値を作らずtesterへ委ねた。

## 4. 実測ログ

### 4-1. テスト結果

| 実行 | 結果 |
|---|---|
| `python3 -m unittest tests.test_ticket_lib`（Phase 1直後・既存4件の無変更PASS確認） | Ran 95 tests, OK（`test_is_spec_basename_fnmatch_*` 4件すべて ok） |
| `python3 -m unittest discover -s tests -p "test_*.py"`（Phase 1直後） | Ran 805 tests, OK（baselineと同数・回帰0） |
| `python3 -m unittest tests.test_ticket_lib tests.test_guard_bash_writes`（Phase 2後） | Ran 396 tests, OK（新規9件すべて ok） |
| `python3 -m unittest discover -s tests -p "test_*.py"`（Phase 2後） | **Ran 814 tests, OK**（805 + 新規9件） |

### 4-2. Phase 1の2変更が結合必須であることの実測（設計書§3 D2・§8の裏付け）

リポジトリのコードは変更せず、スクラッチスクリプトで `guard.lib.is_spec_basename_fnmatch` を
実行時のみKLK-032形（`.upper()` 単独）へモンキーパッチして比較した:

```
--- 現状（Phase 1 適用後・和集合形） ---
docs/[!x]PEC.md   findall=['docs/[!x]PEC.md'] expanded=['docs/SPEC.md'] violation="'rm' は許可されていません"
docs/[!s]PEC.md   findall=['docs/[!s]PEC.md'] expanded=['docs/SPEC.md'] violation="'rm' は許可されていません"
docs/[!S]PEC.md   findall=['docs/[!S]PEC.md'] expanded=[]               violation=None
--- is_spec_basename_fnmatch のみ KLK-032 形へ戻した場合 ---
docs/[!x]PEC.md   expanded=['docs/SPEC.md'] violation="'rm' は許可されていません"
docs/[!s]PEC.md   expanded=[]               violation=None   ← 誤allowが復活
docs/[!S]PEC.md   expanded=[]               violation=None
```

和集合形を欠くと `rm docs/[!s]PEC.md` の誤allowが到達可能な状態で残ることを実測で確認した
（設計書が代替案(b)を却下した理由の裏付け、および
`test_klk033_negated_class_glob_deny` の第2アサーションが実効的な回帰検出器であることの確認）。
スクリプトはセッションのスクラッチ領域（リポジトリ外）に置き、コミットしていない。

## 5. 設計からの逸脱

なし。設計書§4-1〜§4-3の文面・§4-5のPhase分割・§9のテストケース一覧をそのまま実装した
（§9③の「任意」ケースのみ、設計の指示どおりtesterへ委ねて未追加）。

## 6. 運用上の注意（実装中に遵守した事項）

設計書§4-4のとおり、`[!...]` を含む文字列は**インラインBashコマンドへ一切書かなかった**
（本hook自身にdenyされるため）。具体的には:
- コード・テストの編集はEdit/Writeツールで行い、`sed`/`heredoc` による書き換えを使わなかった。
- 動作確認はテストファイル経由（`python3 -m unittest ...`）と、Writeツールで作成した
  スクラッチスクリプトの実行のみで行った。
- コミットメッセージに `[!...]` 形の文字列を含めなかった。
- `git diff` の機密情報スキャン（`api_key`／`password`／`secret`／`token`／接続文字列／
  秘密鍵ヘッダ等のパターン）を実施し0件。`git push` は行っていない。
