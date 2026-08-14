# 状態検証 hooks

チケットの状態機械を機械的に強制するための Claude Code hook 群。
登録は `.claude/settings.json` の `hooks` セクションで行う。

| ファイル | イベント | 役割 |
|---|---|---|
| `validate_ticket_state.py` | PreToolUse（Write\|Edit） | 書き込み前に不変条件を検証し違反を `permissionDecision: deny` でブロック（スキーマ・状態遷移・retry上限）。遷移元は `.metrics_state.json` の最終観測値を正とする（ドリフト後も「最後に検証された状態」から検証）。人間の判断に委ねる操作は `ask` に回す — **L2: カウンタ減少（=リトライ予算のリセット。人間承認で正規化）** と **in_progress上限（todo→investigation_done 着手時に他チケットが3件進行中なら確認）** |
| `check_loop_integrity.py` | Stop | 応答終了時に tickets/active/*.md を一括検査し `decision: block` で継続強制。schema・blocker・本文同期に加え **ドリフト検知（`.metrics_state.json` の最終観測値と status / retry_counts を突き合わせ、Write/Edit を経ない書き換えを検出。tickets/done/ もドリフト検知のみ実施）** と **L3: 差し戻し履歴（.metrics.jsonl）とカウンタの整合照合（retry_reset イベントをエポックとして「リセット時の値+以降の差し戻し回数」で照合）** |
| `record_metrics.py` | PostToolUse（Write\|Edit） | ステータス遷移を `tickets/.metrics.jsonl` に追記する（観測性）。人間承認済みのカウンタ減少は `retry_reset` イベントとして記録する（L3のエポック）。最終観測値（status・retry_counts）は `tickets/.metrics_state.json` で保持し、validator の prior と Stop のドリフト検知の基準を提供する |
| `guard_spec_writes.py` | PreToolUse（Write\|Edit） | SPEC.md（basename一致・.claude/配下を除く）への書き込みを `permissionDecision: ask` で人間確認に回す。autoモードでも SPEC 改訂の diff 承認を機械的に担保する（`--dangerously-skip-permissions` は貫通） |
| `guard_bash_writes.py` | PreToolUse（Bash） | tickets/active\|done/・SPEC.md に言及するコマンドのうち、読み取り・移動系ホワイトリスト（cat/grep/ls/cd/awk/mv/git add 等）以外を `permissionDecision: deny` でブロック。リダイレクト・sed -i（全表記）・sed の `w` コマンド・awk のプログラム内リダイレクト・tee・インタプリタワンライナー・find -exec・ヒアドキュメント・コマンド置換/プロセス置換の内側による検証迂回をベストエフォートで遮断する（パス非リテラルの迂回は Stop のドリフト検知が捕捉。ただし SPEC.md 宛てにはドリフト検知のバックストップが無い）。判定は3レイヤ: **L1 字句**（クォート状態を追跡してクォート外の演算子だけを切り出し、語は `shlex.split` でクォート解除。正規表現内の `\|` `<<` `>` `#` を特殊構文と誤認しない）／**L2 パス**（テキストからパス候補を抽出し `os.path.normpath` で正規化してから `.claude` 成分を除外。トークンに埋め込まれたリテラルパスを検出し、パストラバーサルによる除外の悪用を防ぐ）／**L3 構文**（証拠ベース。出力リダイレクトはステートメント単位で判定し、リダイレクト先は保護対象パスか同一コマンド内で保護対象を代入された変数のときのみ deny）。コマンド置換は内側方向（置換の中身が書き込み）と外側方向（置換の結果が外側の書き込み先・引数になる。`rm $(echo docs/SPEC.md)`・`echo x > $(…)`）の両方を評価する。`cd` は作業ディレクトリを追跡し、保護対象配下へ移動した後の相対パス書き込み（`cd tickets/active && rm APP-001.md`）を捕捉する（`cd` 自体は常に許可。`cd "$DIR"` / `cd $(…)` は追跡不能）。字句解析できない入力（未閉じクォート・未閉じバッククォート・未閉じ `$(`・末尾の孤立エスケープの5系統。`don't` のような英文コメントでも成立する）は allow せず、旧版と同じ素朴な分割（ステートメント／パイプ／セグメント）による簡易判定へ落とす（この経路ではクォート内の `\|` を誤ってパイプと解釈する誤denyが旧版と同じく残る）。保護対象の判定は `_ticket_lib.is_ticket`（厳密判定）とは目的が異なるため**意図的に別基準**（詳細はモジュール docstring）。例外: 読み取り専用と確認済みのスクリプト（`READONLY_SCRIPTS`。SPEC構造チェッカー）を `python3 <スクリプトパス> <引数>` の形で実行するセグメントは許可。**既知の未対応**: `sort -o` / `sort --output=`・`uniq INPUT OUTPUT` の第2位置引数・`sed -f SCRIPT`・GNU sed の `e` フラグ（任意コマンド実行）は本 hook の導入当初から遮断できていない（別チケット候補）。ホワイトリスト（`ALLOWED_HEADS`）へコマンドを追加するときは `docs/designs/KLK-010.md` §3-9 の書き込みベクタ棚卸し表へ行を追加し、引数だけで書き込み／任意実行できる経路を列挙してから追加すること |
| `_ticket_lib.py` | -（共有） | frontmatterパーサと検証ルール（status enum・必須キー・遷移表・retry上限）を集約。加えて hook 横断の共有ヘルパを提供する: チケットパス判定（`is_ticket`）・PreToolUse の decision 出力（`emit_pretooluse_decision`）・サイドカー/イベントログ読み込み（`load_state` / `load_events` / `group_events_by_ticket`） |

メトリクスの集計は `.claude/metrics/aggregate.py`（`/metrics` コマンドが実行）が担う。

## メトリクスの運用

- `tickets/.metrics.jsonl`・`tickets/.metrics_state.json` は hook が自動生成する。**LLM・エージェントは直接編集しない**（サイドカーの直接編集はドリフト検知の基準を壊す）
- これらのファイルはデフォルトで `.gitignore` 対象（環境固有のため）。チームで履歴を共有したい場合は `.gitignore` の該当行を解除する
- 記録されるのは「ステータス遷移」のみ。ログ追記や related_files 更新など状態を変えない編集は記録しない

## 設計方針

- **fail-open**: hook内部のエラー（IO・パース不能など）ではループをブロックしない。検知した違反のみ deny する。
- **依存なし**: Python3標準ライブラリのみ。
- **単一の真実**: 検証ルールは `_ticket_lib.py` に集約。CLAUDE.md のステータス定義・orchestrator.md「リトライカウンタ管理」のリトライ上限と定数を同期させること。
- **無限ループ防止**: Stop hook は `stop_hook_active` が真のとき再ブロックしない。

## ローカルでの動作確認

```bash
# PreToolUse: 不正な状態遷移を deny できるか
printf '{"tool_name":"Edit","tool_input":{"file_path":"/abs/path/tickets/active/APP-001.md","old_string":"status: design_done","new_string":"status: done"}}' \
  | python3 .claude/hooks/validate_ticket_state.py

# Stop: active配下の不整合を検出できるか
printf '{"hook_event_name":"Stop","cwd":"'"$PWD"'","stop_hook_active":false}' \
  | python3 .claude/hooks/check_loop_integrity.py
```

exit 0 かつ無出力なら allow、JSON を出力すれば block。

> 注意: 上記のようなペイロードにチケットパスを含むコマンドは、Claude Code の
> Bash ツール経由では `guard_bash_writes.py` に deny される（printf が
> ホワイトリスト外のため）。動作確認は人間のターミナルで直接実行するか、
> `tests/` の自動テストを使うこと。

自動テストは `tests/` にある（`python3 -m unittest discover -s tests -v`）。検証ロジックを変更したら必ず実行すること。

## 注意

- `retry_counts` を持たない旧チケットは検証エラーになる。既存チケットには frontmatter へ `retry_counts` を追加すること
- hook を一時的に無効化したい場合は `.claude/settings.json` の `hooks` セクションを編集する

## ルールを変更するとき

1. `_ticket_lib.py` の定数（`VALID_STATUS` / `REQUIRED_KEYS` / `RETRY_CAPS` / `LEGAL_TRANSITIONS`）を更新する
2. 対応する定義（CLAUDE.md ステータス定義・orchestrator.md リトライカウンタ管理）も合わせて更新する
3. `tests/` のテストを更新し、`python3 -m unittest discover -s tests -v` で全件パスを確認する
