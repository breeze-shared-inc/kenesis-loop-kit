# KLK-018 レビュー報告（reviewer）

対象: `fix/KLK-018-shell-expansion-bypass`（worktree `/home/bzg55/workspace/breeze/kenesis-loop-kit.wt/KLK-018`）
設計書§4-1〜§4-4・実装レポート・テストレポート・実コード差分（`git diff develop...HEAD`）を確認したうえで、tester申し送り2件に加え、独自の実機PoC検証で新規のCritical Issueを検出した。

## 1. Critical Issues
- `_brace_combination_count`（`guard_bash_writes.py` KLK-018新設）は隣接（非入れ子）ブレース群が連続すると`suffix`方向の再帰でdepthを増やさず呼び出しを重ねるため、約1000個連続でPython既定の再帰上限(1000)に達し`RecursionError`を送出することを実機PoCで確認（実測: 997個で発生）。
- `main()`は`find_violation`全体を`except Exception: allow()`で包むため、この`RecursionError`は**deny方向ではなくallow方向へフェイルオープン**し、`rm tickets/active/APP-001.md`のような本来明確にdenyされるべき既存ケースすら、同一コマンド中に大量の隣接ブレースが含まれるだけで丸ごとallowになることをPoCで確認済み。
- MAX_BRACE_DEPTHは「ネストの深さ」のみを制限し「隣接ブレースの個数」を制限しないことは実装コメント自身が明記しており、代替のはずのMAX_BRACE_COMBINATIONS事前見積り関数自体が同じ非有界再帰で実装されているため安全網が機能しない。
- 誤りの向きが常にallow方向（危険）に倒れる構造的欠陥であり、設計書§4-1・P8原則（曖昧な位置は安全側=deny）・AC4の「向き」原則に反する。KLK-018新設分だけでなく`find_violation`全体（既存の言及ゲート含む）が同一コマンド内でバイパスされるためRegression上も重大。

### 再現手順・実測値
```python
import sys
sys.path.insert(0, ".claude/hooks")
import guard_bash_writes as guard

candidate = "a" + "{x,y}" * 2000 + "b"
guard._brace_combination_count(candidate)  # -> RecursionError（実測: N=997で発生。sys.getrecursionlimit()=1000）

# noise(隣接ブレース997個超) + 既存の明確なdeny対象語（"rm " + 分断・非表示で構成した
# "tickets/active/APP-001.md" 相当の語）を同一コマンドに含めた場合:
# guard.find_violation(cmd) は RecursionError を送出する（main()側は
# `except Exception: allow()` で捕捉するため、実運用ではこの入力に対し
# guard_bash_writes.py 全体がallowへフェイルオープンする）。
```

根本原因: `_brace_combination_count`が`suffix`（直積・兄弟ブレース）方向の再帰でdepth引数を増やさないため、MAX_BRACE_DEPTH（=4）の早期リターンに到達せず、隣接ブレース数に比例したPythonコールスタックを消費し続ける。MAX_BRACE_COMBINATIONS（=512）による安全側フォールバックも、それを計算する関数自体がこの再帰でクラッシュするため機能しない。

## 2. High Risks
- 上記Critical Issueは、設計・実装・tester各段階の境界値テスト（N=4,5、直積243,729）がいずれも小さいNに留まり、再帰段数がPython上限に達する規模（N≈1000）を一度も検証していなかったために見逃された。テスト観点の「境界値」がMAX_BRACE_DEPTH/COMBINATIONSの値そのものの境界のみを見ており、独立した「隣接兄弟ブレース数」という次元の境界（実装コメントが自認する次元）を見落としていた。
- この欠陥は`guarded_paths_after_shell_expansion`を経由する7呼び出し箇所すべて（`statement_violation`／`redirect_violation`／`guarded_write_target`／`degraded_violation`×3／`subst_violation`）に共通して影響するため、影響範囲は広い。

## 3. Medium Risks
- tester申し送り(2): MAX_BRACE_DEPTH/MAX_BRACE_COMBINATIONS超過時のフォールバックが`tickets/`等の語を一切含まない候補にも作用し、設計書§9 AC4のN1〜N4閉列挙の文言（「保護対象パスとなる語を含み」）を字面上満たさない新しいdeny経路であることに同意。ただし誤りの向きは常にdeny方向（安全側）であり、発生条件（隣接ブレース6個以上・直積729通り等）も通常のチケット操作では非現実的なため、これ単独ではブロッカーとしない。設計書§9 AC4へN5として明文化する追記を推奨。
- Critical Issue修正（try/except RecursionError等）を実装した後、この安全側フォールバック自体の妥当性判断は変わらない（引き続きMedium・許容範囲の判断を維持）。

## 4. Missing Tests
- 隣接（非入れ子）ブレース群が数百〜1000個規模に達する入力の回帰テストが皆無（既存境界値テストはN=5,6のみ、Critical Issue該当）。
- `RecursionError`が発生しないこと・発生した場合でも安全側(deny)へ倒れることを固定するテスト（修正後に必須）。
- `main()`レベル（`except Exception: allow()`）を経由したend-to-endのfail-open挙動を検証する統合テストが無く、`find_violation`直呼びのみで検証されている。

## 5. Spec Violations
- 設計書§9 AC2の`cat docs/SPEC*.md`deny例示: `cat`が`segment_violation`の追加規則を持たない読み取り専用headであるため実装は正しくallowで固定。既存`test_read_commands_allow`と同型であり、設計書側の記述誤りと判断（tester/implementerの申し送りに同意）。設計書修正を推奨するが実装起因の問題ではない。
- 設計書§9 AC4のN1〜N4閉列挙とMAX_BRACE_*フォールバックの不整合（上記Medium Risks参照）。
- Critical Issueの`RecursionError`起因fail-open allowは、設計書§4-1「上限超過時は候補全体を保護対象一致とみなす」という**安全側**の意図に実装が反しており、設計不備ではなく実装不備と判断（設計は正しい意図を明記していたが、事前見積り関数自体の再帰安全性を検証していなかった）。

## 6. Suggested Fixes
- `guarded_paths_after_shell_expansion`内で`_brace_combination_count`（および`expand_braces`）の呼び出しを`try/except RecursionError`で囲み、例外時はMAX_BRACE_COMBINATIONS超過と同じ安全側フォールバック（候補を無条件一致とみなす＝deny方向）へ倒す。`main()`の広域except-allowより手前（`guard_bash_writes.py`内）で捕捉することが必須。
- 恒久対応として`_brace_combination_count`／`expand_braces`の`suffix`方向再帰をループ化する、または候補中の`{`出現数に軽量な事前上限（例: 50個程度）を設け、超過時は再帰前に即フォールバックする。
- 修正後、隣接ブレース900〜1500個規模の回帰テストを追加し、`RecursionError`が発生しないこと・安全側(deny)に倒れることを固定する。
- AC4のN1〜N4列挙にフォールバック由来のdeny(N5)を明文化し、`cat docs/SPEC*.md`例示は設計書§9から削除するかhead依存の注記を追加する（tester/implementer申し送り2件を設計書へ反映）。

## 7. Approval Status: rejected
- 却下理由: Critical Issueの`RecursionError`起因fail-open allow（実装起因のバグ。安全側フォールバックの設計意図を実装が達成できていない）。既存共有シンボル無変更・7箇所置換・AC1/AC3/AC5/AC6/AC7自体は設計通り良好に実装されており、当該再帰安全性の修正のみで解消可能と判断。
- 差し戻し先: **implementer**（investigatorへの差し戻しは不要。原因は特定済みで設計の大枠変更も不要）。
- 併せてtester申し送り2件（cat例示・AC4列挙不整合）への設計書修正もimplementerフェーズで対応可能な軽微な追加作業として依頼を推奨。
- ロールバック容易性自体は良好（`git merge --no-ff`後の単一マージコミットrevertで戻せる。docs/worktree-policy.md準拠）が、今回はマージ前の差し戻しのため該当なし。

---

# 再レビュー結果（2026-08-17・implementer修正後）

対象: `fix/KLK-018-shell-expansion-bypass`（worktree同上、HEAD `ca69804`）。前回Critical Issueの修正確認と、testerが発見した「テスト検証漏れ」の妥当性確認を、tester申告を鵜呑みにせず独立PoCで再実施した。

## 1. Critical Issues（再検証）
なし。前回検出した`_brace_combination_count`のRecursionError→`main()`の広域except経由allow方向フェイルオープンは解消を独立PoCで確認した。修正前(`d094c82`)/修正後(`ca69804`)双方を`find_violation`直呼びで比較し、修正前は`RecursionError`が実際に送出、修正後は隣接997〜5000個・両語順・カンマ有無いずれも例外なくdeny文字列が返ることを確認した。

## 2. High Risks（再検証）
なし。前回Highの原因（境界値テストがN≈1000規模を一度も検証していなかったこと）は今回のテスト追加で解消を確認した。テスト設計上の一般的な罠（`any()`短絡評価による語順依存の検証漏れ）自体は今回のtester発見が正しいことを確認したが、対応（Medium Risksへ記載）で足りると判断する。

## 3. Medium Risks（再検証）
- 前回同様2件（AC2の`cat`例示、AC4のN1〜N4列挙とMAX_BRACE_*フォールバックの不整合）は本ラウンドで設計書無変更（`git diff develop...HEAD -- docs/designs/`差分ゼロ）につきスコープ外・非ブロッカーで据え置き。
- 新規（軽微）: `any()`短絡評価に依存する回帰テストは書き方次第で今回同様の検証漏れが再発しうる一般的な罠。テスト作成規約への反映（語順を変えた対照ケースを常に用意する等）を推奨するが非ブロッカー。

## 4. Missing Tests（再検証）
なし。前回指摘（隣接900〜1500規模の回帰・RecursionError非発生固定・main()経由end-to-end検証）はすべて埋まっている。独自PoCでもn=3000/5000規模・カンマ有無・両語順で追加確認し、全て一致した。

## 5. Spec Violations（再検証）
前回と同一の2件（`cat`例示、AC4列挙不整合）のみで、いずれも設計書側の記述問題（実装起因ではない）として据え置き。新規のSpec Violationはなし。

## 6. Suggested Fixes（再検証）
- (nit・非ブロッカー) `guard_bash_writes.py`コメント内のテスト名参照が実際のテスト名と不一致（コメントのみ、動作影響なし）。
- 前回提案のAC4 N5明文化・`cat`例示の設計書修正は引き続き推奨（改善ループ側で対応可）。

## 7. Approval Status（再検証）: **approved**
- 独立PoC（`find_violation`直呼び・`main()`経由subprocess双方）で、隣接ブレースn=997〜5000・両語順（deny語が先/後）・カンマ有無いずれもdeny・RecursionError非発生を確認。修正前コードでは同条件でRecursionError発生→allowを確認し、修正が真に有効であることを確認した。
- testerが発見した「元の回帰テストが`any()`短絡評価によりmaskingシナリオを実際には検証できていなかった」問題を独立に再現・確認し、tester追加の2件（語順逆転版・カンマ無しリテラル版）が実際にmaskingシナリオを正しく判別できることを検証した。
- 呼び出し経路調査: `_brace_combination_count`／`expand_braces`の外部呼び出しは`guarded_paths_after_shell_expansion`内の2箇所のみで、それを呼ぶのは単一chokepoint`is_guarded_token_expanded`/`mentions_guarded_expanded`経由の全呼び出し元に限られ、バイパス経路は発見されなかった。
- 全678件テストpass（独自実行で確認）。残るMedium Risk 2件は前回同様スコープ外・非ブロッカー。

### 再検証手法の詳細
`git show d094c82:.claude/hooks/guard_bash_writes.py`（修正前）と`git show ca69804:...`（修正後、現HEAD）を複製し、(a) `find_violation()`直接importでの例外型確認、(b) `main()`の広域except込みでsubprocess経由の実際のhook挙動確認、の2系統で独立実施。

**主要な実測結果**:
- 修正前 + decoyfirst（noise語が先、deny対象語が後）n=1200: `find_violation`が`RecursionError`を送出、`main()`経由では空文字列（=allow）。masking実証。
- 修正前 + denyfirst（既存deny語が先、noise語が後。implementerの元テストと同じ語順）n=1200: 正しくdeny。これはtesterの指摘通り、`any()`の短絡評価により危険なnoise語を一度も評価しないため“偶然”denyになっているだけで、修正効果の検証にはなっていないことを確認。
- 修正後: n=997,1000,1200,1500,3000,5000 × {decoyfirst, denyfirst} × {カンマ有, カンマ無} の全組み合わせでdeny・RecursionError非発生を確認（カンマ無しn=1000は修正前コードではallowへフェイルオープンすることも確認、tester第2の追加テストの妥当性を裏付け）。
- 修正後 + `cat`（読み取り専用head）+ noise n=1500: allow（安全側フォールバックが書き込み判定自体を変えないことのsymmetry確認、regressionなし）。
- 全678件のユニットテストを独自実行しpassを確認（tester報告と一致）。
