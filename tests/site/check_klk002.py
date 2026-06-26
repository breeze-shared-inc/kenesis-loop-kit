#!/usr/bin/env python3
"""
KLK-002 acceptance-condition checker (static / no browser required).

Verifies the statically-checkable acceptance conditions from
docs/designs/KLK-002.md §9 (改訂版 / 2026-06-26 確定) against
site/index.html, site/css/style.css, site/js/main.js and site/assets/.

Source of truth = 確定§9（設計書）。実装の現状ではなく設計を正としてチェックする。
（背景: commit c038e6d でテスト期待値が実装と同時に書き換えられ、現物に対する独立
検証証跡が無いと指摘された。今回は §9 を正として再設定し直したもの。）

Run: python3 tests/site/check_klk002.py
Exit code 0 = all static checks pass, 1 = at least one fail.

This is a tester-owned check script. It does NOT modify production code
under site/. Browser-only conditions (Lighthouse, visual rendering,
reduced-motion 実機) are out of scope here and reported as
"未実測（環境制約）" by the tester. Python3 標準ライブラリのみ・ネットワーク非使用。
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SITE = os.path.join(ROOT, "site")
HTML = open(os.path.join(SITE, "index.html"), encoding="utf-8").read()
CSS = open(os.path.join(SITE, "css", "style.css"), encoding="utf-8").read()
JS = open(os.path.join(SITE, "js", "main.js"), encoding="utf-8").read()


results = []  # (group, name, passed: bool, detail)


def check(group, name, passed, detail):
    results.append((group, name, bool(passed), detail))


# ---------------------------------------------------------------------------
# Contrast helpers (WCAG 2.x relative luminance)
# ---------------------------------------------------------------------------
def _lin(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hexstr):
    h = hexstr.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contrast(fg, bg):
    l1, l2 = luminance(fg), luminance(bg)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


# Resolve :root tokens from CSS so we cross-check the actual declared values.
def token(name):
    m = re.search(re.escape(name) + r"\s*:\s*(#[0-9a-fA-F]{3,6})", CSS)
    return m.group(1) if m else None


TOK = {n: token(n) for n in [
    "--color-bg", "--color-surface", "--color-primary", "--color-primary-dark",
    "--color-primary-light", "--color-accent", "--color-text",
    "--color-text-muted", "--color-on-primary",
]}

# Common derived structures reused across checks
section_ids = re.findall(r'<section[^>]*id="([^"]+)"', HTML)
footer_present = bool(re.search(r"<footer", HTML))
fv_block = re.search(r'<section id="fv".*?</section>', HTML, re.S)
fv_html = fv_block.group(0) if fv_block else ""


# ===========================================================================
# B群（構成の改訂・確定§9）— 新構成を §9 に対して検証
# ===========================================================================

# B1. Section structure & order:
#     fv -> business -> recruit -> company -> news -> contact (+ footer)
#     results は廃止（存在しないこと）。company / news は存在すること。
expected_sections = ["fv", "business", "recruit", "company", "news", "contact"]
order_ok = section_ids == expected_sections and footer_present
results_absent = "results" not in section_ids
company_present = "company" in section_ids
news_present = "news" in section_ids
b1_ok = order_ok and results_absent and company_present and news_present
check(
    "B群", "B1 セクション構成と順序 (fv→business→recruit→company→news→contact→footer / results廃止)",
    b1_ok,
    f"section順={section_ids}, footer={'有' if footer_present else '無'}, "
    f"results非存在={results_absent}, company存在={company_present}, news存在={news_present}",
)

# B2. New sections structure:
#     #company = h2 + lead + CTA + visual
#     #news    = h2 + 一覧リンク + <li>×3（各 <time datetime>）
company_block = re.search(r'<section id="company".*?</section>', HTML, re.S)
cb = company_block.group(0) if company_block else ""
company_h2 = bool(re.search(r"<h2[ >]", cb))
company_lead = "section__lead" in cb
company_cta = bool(re.search(r'class="btn[^"]*"', cb))
company_visual = "media-photo" in cb or "company__visual" in cb
company_ok = bool(company_block) and company_h2 and company_lead and company_cta and company_visual

news_block = re.search(r'<section id="news".*?</section>', HTML, re.S)
nb = news_block.group(0) if news_block else ""
news_h2 = bool(re.search(r"<h2[ >]", nb))
news_more = bool(re.search(r'class="news__more"', nb)) or "お知らせ一覧" in nb
news_items = len(re.findall(r'class="news__item"', nb))
news_times = len(re.findall(r"<time[^>]*datetime=", nb))
news_ok = bool(news_block) and news_h2 and news_more and news_items == 3 and news_times == 3

b2_ok = company_ok and news_ok
check(
    "B群", "B2 新規セクション構造 (#company: h2+lead+CTA+visual / #news: h2+一覧リンク+li×3+<time datetime>)",
    b2_ok,
    f"company[h2={company_h2},lead={company_lead},cta={company_cta},visual={company_visual}], "
    f"news[h2={news_h2},一覧リンク={news_more},li×{news_items},<time datetime>×{news_times}]",
)

# B3. Header nav consistency: お知らせ/事業内容/採用情報/会社案内/お問い合わせ
nav_block = re.search(r'<nav class="primary-nav".*?</nav>', HTML, re.S)
nav_html = nav_block.group(0) if nav_block else ""
nav_links = re.findall(r'<a[^>]*href="(#[^"]+)"[^>]*>([^<]+)</a>', nav_html)
nav_pairs = [(href, txt.strip()) for href, txt in nav_links]
expected_nav = [
    ("#news", "お知らせ"),
    ("#business", "事業内容"),
    ("#recruit", "採用情報"),
    ("#company", "会社案内"),
    ("#contact", "お問い合わせ"),
]
nav_ok = nav_pairs == expected_nav
check(
    "B群", "B3 ヘッダーナビ整合 (お知らせ/事業内容/採用情報/会社案内/お問い合わせ)",
    nav_ok,
    f"nav={nav_pairs}",
)

# B4. Heading hierarchy: h1 x1 (in FV, static) -> non-FV section h2 -> card h3
h1s = re.findall(r"<h1[ >]", HTML)
h1_in_fv = bool(fv_block and re.search(r"<h1[ >]", fv_html))
h2_count = len(re.findall(r"<h2[ >]", HTML))
biz_h3 = len(re.findall(r'class="biz-card__title"', HTML))
non_fv_sections = len([s for s in section_ids if s != "fv"])
b4_ok = len(h1s) == 1 and h1_in_fv and h2_count == non_fv_sections and biz_h3 == 2
check(
    "B群", "B4 見出し階層 (h1×1=FV内, 非FVセクション=h2, カード h3×2)",
    b4_ok,
    f"h1={len(h1s)}(FV内={h1_in_fv}), h2={h2_count}(非FVセクション数={non_fv_sections}), "
    f"biz-card__title(h3)={biz_h3}",
)


# ===========================================================================
# A群（既存の中核要件・継続）
# ===========================================================================

# A1. FV 2CTA juxtaposition + 44px tap target + :focus-visible
cta_contact = 'data-cta="contact"' in fv_html
cta_recruit = 'data-cta="recruit"' in fv_html
btn_block = re.search(r"\.btn\s*\{([^}]*)\}", CSS)
btn_css = btn_block.group(1) if btn_block else ""
min_h = bool(re.search(r"min-height:\s*44px", btn_css))
min_w = bool(re.search(r"min-width:\s*44px", btn_css))
focus_visible = bool(re.search(r":focus-visible\s*\{", CSS))
a1_ok = cta_contact and cta_recruit and min_h and min_w and focus_visible
check(
    "A群", "A1 FV 2CTA並置 (data-cta=contact/recruit) + 44px + :focus-visible",
    a1_ok,
    f"contact={cta_contact}, recruit={cta_recruit}, min-height44={min_h}, "
    f"min-width44={min_w}, :focus-visible={focus_visible}",
)

# A2. Two businesses equal: same .biz-card class x2, dims via CSS vars
biz_cards = len(re.findall(r'class="biz-card"', HTML))
card_pad_var = bool(re.search(r"\.biz-card\s*\{[^}]*padding:\s*var\(--card-pad\)", CSS, re.S))
card_radius_var = bool(re.search(r"border-radius:\s*var\(--card-radius\)", CSS))
icon_var = bool(re.search(r"width:\s*var\(--card-icon\)", CSS))
has_infra = "ITインフラ事業" in HTML
has_ses = "SES事業" in HTML
a2_ok = biz_cards == 2 and card_pad_var and card_radius_var and icon_var and has_infra and has_ses
check(
    "A群", "A2 2事業対等 (.biz-card×2 同一構造, 寸法=CSS変数共通)",
    a2_ok,
    f".biz-card数={biz_cards}, padding=var(--card-pad):{card_pad_var}, "
    f"radius=var:{card_radius_var}, icon=var:{icon_var}, ITインフラ={has_infra}, SES={has_ses}",
)

# A3. Color tokens: white bg + green primary + single accent; no external URL/img
bg_white = TOK["--color-bg"] and TOK["--color-bg"].lower() in ("#ffffff", "#fff")


def is_greenish(hexstr):
    h = hexstr.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return g > r and g >= b  # green channel dominant


primary_green = TOK["--color-primary"] and is_greenish(TOK["--color-primary"])
accent_defined = TOK["--color-accent"] is not None
ext_urls = []
for fn in ["index.html", "css/style.css", "js/main.js", "assets/favicon.svg",
           "assets/logo-placeholder.svg"]:
    txt = open(os.path.join(SITE, fn), encoding="utf-8").read()
    for m in re.findall(r'https?://[^\s"\')]+', txt):
        if m.startswith("http://www.w3.org/2000/svg"):
            continue
        ext_urls.append(f"{fn}:{m}")
no_ext = len(ext_urls) == 0
a3_ok = bool(bg_white and primary_green and accent_defined and no_ext)
check(
    "A群", "A3 カラー要件 (白背景+緑メイン+アクセント1色, 外部URL0)",
    a3_ok,
    f"bg={TOK['--color-bg']}(白={bool(bg_white)}), primary={TOK['--color-primary']}"
    f"(緑={primary_green}), accent={TOK['--color-accent']}, 外部URL={ext_urls or 0}",
)

# A4. Contrast >= 4.5:1 (large headings >= 3:1)
white = TOK["--color-bg"]
surface = TOK["--color-surface"]
primary = TOK["--color-primary"]
accent = TOK["--color-accent"]
text = TOK["--color-text"]
muted = TOK["--color-text-muted"]
primary_light = TOK["--color-primary-light"]
primary_dark = TOK["--color-primary-dark"]

contrast_targets = [
    ("本文 text / 白", text, white, 4.5),
    ("muted / 白", muted, white, 4.5),
    ("緑ボタン白文字 (on primary)", "#ffffff", primary, 4.5),
    ("アクセントボタン白文字", "#ffffff", accent, 4.5),
    ("緑リンク / カード面 surface", primary, surface, 4.5),
    ("eyebrow primary-dark / primary-light", primary_dark, primary_light, 4.5),
    ("フッター文字 #e8efe9 / footer bg(=text)", "#e8efe9", text, 4.5),
    ("フッター copy #aebfb5 / footer bg", "#aebfb5", text, 4.5),
]
contrast_rows = []
a4_ok = True
for label, fg, bg, threshold in contrast_targets:
    ratio = contrast(fg, bg)
    ok = ratio >= threshold
    if not ok:
        a4_ok = False
    contrast_rows.append(f"{label}: {ratio:.2f}:1 (>= {threshold}) {'OK' if ok else 'NG'}")
check(
    "A群", "A4 主要テキストのコントラスト >= 4.5:1",
    a4_ok,
    " | ".join(contrast_rows),
)

# A5. 360px horizontal-scroll defenses (code-level)
overflow_x = bool(re.search(r"overflow-x:\s*hidden", CSS))
img_max = bool(re.search(r"img,\s*svg\s*\{[^}]*max-width:\s*100%", CSS, re.S))
clamp_pad = bool(re.search(r"padding-inline:\s*clamp\(", CSS))
fluid_grid = "grid-template-columns: 1fr" in CSS
a5_ok = overflow_x and img_max and clamp_pad and fluid_grid
check(
    "A群", "A5 360px横スクロール対策 (overflow-x, img/svg max-width, clamp pad, 流動grid)",
    a5_ok,
    f"overflow-x:hidden={overflow_x}, img/svg max-width100%={img_max}, "
    f"clamp padding={clamp_pad}, 1fr流動grid={fluid_grid}",
)

# A6. No secrets
secret_re = re.compile(r"api[_-]?key|secret|password|token|private[_ ]key|BEGIN .*PRIVATE", re.I)
secret_hits = []
for dirpath, _, files in os.walk(SITE):
    for f in files:
        p = os.path.join(dirpath, f)
        try:
            t = open(p, encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        for ln, line in enumerate(t.splitlines(), 1):
            if secret_re.search(line):
                secret_hits.append(f"{os.path.relpath(p, ROOT)}:{ln}")
check(
    "A群", "A6 機密情報なし (api_key|secret|password|token|private_key 0件)",
    len(secret_hits) == 0,
    f"hits={secret_hits or 0}",
)

# A7. FV DOM order text -> visual -> cta
order_text = fv_html.find("fv__text")
order_visual = fv_html.find("fv__visual")
order_cta = fv_html.find("fv__cta")
a7_ok = 0 <= order_text < order_visual < order_cta
check(
    "A群", "A7 FV DOM順 (text→visual→cta)",
    a7_ok,
    f"text={order_text}, visual={order_visual}, cta={order_cta}",
)

# A8. Decorative SVG aria-hidden (MVモチーフ・過度装飾なし)
dec_svgs = re.findall(r'<svg class="fv__accent"[^>]*>', HTML)
accent_aria = all('aria-hidden="true"' in s for s in dec_svgs) if dec_svgs else False
check(
    "A群", "A8 装飾SVG aria-hidden (.fv__accent)",
    accent_aria,
    f"fv__accent数={len(dec_svgs)}, 全てaria-hidden={accent_aria}",
)


# ===========================================================================
# C群（カルーセル a11y・D2）
# ===========================================================================

# C1. Persistent pause/play control (WCAG 2.2.2):
#     [data-fv-playpause] in FV, aria-pressed, 44px tap target, :focus-visible
playpause_in_fv = "data-fv-playpause" in fv_html
playpause_btn = re.search(r"<button[^>]*data-fv-playpause[^>]*>", fv_html)
playpause_aria_pressed = bool(playpause_btn and "aria-pressed" in playpause_btn.group(0))
pp_block = re.search(r"\.fv__playpause\s*\{([^}]*)\}", CSS)
pp_css = pp_block.group(1) if pp_block else ""
pp_min_h = bool(re.search(r"min-height:\s*44px", pp_css))
pp_min_w = bool(re.search(r"min-width:\s*44px", pp_css))
# JS: toggling userPaused stops/starts the autoplay (恒常停止)
js_playpause_toggle = ("userPaused = !userPaused" in JS) and ("stop()" in JS) and ("start()" in JS)
# :focus-visible は全インタラクティブ要素に適用される共通定義（ボタンも対象）
c1_ok = (playpause_in_fv and playpause_aria_pressed and pp_min_h and pp_min_w
         and focus_visible and js_playpause_toggle)
check(
    "C群", "C1 恒常的な一時停止/再生コントロール (WCAG2.2.2: [data-fv-playpause], aria-pressed, 44px, 恒常停止)",
    c1_ok,
    f"FV内ボタン={playpause_in_fv}, aria-pressed={playpause_aria_pressed}, "
    f"CSS min-h44={pp_min_h}/min-w44={pp_min_w}, :focus-visible={focus_visible}, "
    f"JS恒常停止トグル={js_playpause_toggle}",
)

# C2. Dot ARIA validity:
#     no invalid aria-selected on <button>; dots use aria-pressed; each has アクセシブルネーム
aria_selected_count = HTML.count("aria-selected")
dot_buttons = re.findall(r"<button[^>]*class=\"fv__dot[^\"]*\"[^>]*>", fv_html)
dots_have_pressed = bool(dot_buttons) and all("aria-pressed" in d for d in dot_buttons)
dots_have_label = bool(dot_buttons) and all("aria-label" in d for d in dot_buttons)
dots_group = bool(re.search(r'class="fv__dots"[^>]*role="group"[^>]*aria-label=', fv_html))
c2_ok = aria_selected_count == 0 and dots_have_pressed and dots_have_label and dots_group
check(
    "C群", "C2 ドットARIAの妥当性 (aria-selected 0件, 各ドット aria-pressed + アクセシブルネーム, role=group)",
    c2_ok,
    f"aria-selected件数={aria_selected_count}, ドット数={len(dot_buttons)}, "
    f"全aria-pressed={dots_have_pressed}, 全aria-label={dots_have_label}, dots role=group={dots_group}",
)

# C3. h1 stability: h1 not rewritten by carousel JS; switch region has aria-live
#     - main.js が h1 / .fv__title へ innerHTML/textContent 代入を行わない
#     - FV_SLIDES に title キーが無い
#     - 切替テキスト領域(.fv__copy) に aria-live="polite"
js_h1_write = bool(re.search(r"(titleEl|\.fv__title|h1)[^\n;]*\.(innerHTML|textContent|innerText)\s*=", JS))
fv_slides_has_title = bool(re.search(r"FV_SLIDES[\s\S]*?\btitle\s*:", JS)) and bool(
    re.search(r"\btitle\s*:", JS[JS.find("FV_SLIDES"):JS.find("function initFvCarousel")])
    if "FV_SLIDES" in JS and "function initFvCarousel" in JS else None
)
copy_block = re.search(r'<div class="fv__copy"[^>]*>', fv_html)
aria_live_ok = bool(copy_block and 'aria-live="polite"' in copy_block.group(0))
c3_ok = (not js_h1_write) and (not fv_slides_has_title) and aria_live_ok
check(
    "C群", "C3 h1の安定性 (JSで h1 を書換えない / FV_SLIDESにtitle無し / 切替領域に aria-live=polite)",
    c3_ok,
    f"h1へのJS書込={js_h1_write}, FV_SLIDESにtitleキー={fv_slides_has_title}, "
    f".fv__copy aria-live=polite={aria_live_ok}",
)

# C4. reduced-motion respected (code-level):
#     - carousel start() が reduce 時に自動送りしない（early return）
#     - scroll-reveal が reduce 時に無効（early return）
reveal_reduce_return = bool(re.search(
    r"matchMedia\('\(prefers-reduced-motion: reduce\)'\)\.matches\)\s*\{\s*return", JS))
carousel_reduce_guard = ("userPaused = reduceMQ.matches" in JS) and bool(
    re.search(r"if\s*\(userPaused\s*\|\|\s*reduceMQ\.matches\)\s*\{\s*return", JS))
css_reveal_reduce = bool(re.search(
    r"@media \(prefers-reduced-motion: reduce\)\s*\{[^}]*\.reveal[^}]*opacity:\s*1", CSS, re.S))
c4_ok = reveal_reduce_return and carousel_reduce_guard and css_reveal_reduce
check(
    "C群", "C4 reduced-motion 尊重 (carousel自動送り停止 / scroll-reveal無効 / CSSフォールバック)",
    c4_ok,
    f"reveal early-return={reveal_reduce_return}, carousel reduce guard={carousel_reduce_guard}, "
    f"CSS reveal reduce fallback={css_reveal_reduce}",
)


# ===========================================================================
# D群（scroll-reveal・D3）
# ===========================================================================

# D1. FOUC回避: .reveal-ready は JS有効時のみ <html> に付与され、
#     初期非表示(opacity:0)は .reveal-ready 配下でのみ適用される。
js_adds_reveal_ready = "documentElement.classList.add('reveal-ready')" in JS or \
    'documentElement.classList.add("reveal-ready")' in JS
# CSS: 初期非表示は ".reveal-ready .reveal { opacity:0 }" の形でゲートされている
gated_hide = bool(re.search(r"\.reveal-ready\s+\.reveal\s*\{[^}]*opacity:\s*0", CSS, re.S))
# bare ".reveal{opacity:0}"（.reveal-ready 無しの初期非表示）が存在しないこと。
# CSSの各ルールブロックを走査し、reveal クラス（.reveal-ready ではない）へ opacity:0 を
# 課しているのに selector が .reveal-ready 配下でないものを検出する。
# コメントは selector 取得を汚染するため事前に除去する（".reveal-ready" を含む説明文の混入回避）。
CSS_NOCOMMENT = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
bare_hide = False
for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", CSS_NOCOMMENT):
    selector, body = m.group(1), m.group(2)
    has_reveal_class = bool(re.search(r"\.reveal(?![\w-])", selector))
    hides = bool(re.search(r"opacity:\s*0\b", body))
    if has_reveal_class and hides and ".reveal-ready" not in selector:
        bare_hide = True
        break
d1_ok = js_adds_reveal_ready and gated_hide and not bare_hide
check(
    "D群", "D1 scroll-reveal FOUC回避 (.reveal-ready はJS有効時のみ付与, 初期非表示はその配下のみ)",
    d1_ok,
    f"JSが.reveal-ready付与={js_adds_reveal_ready}, .reveal-ready配下で初期非表示={gated_hide}, "
    f"ゲート無し初期非表示の存在={bare_hide}",
)


# ===========================================================================
# E群（クリーンアップ・D5）
# ===========================================================================

# E1. Debug UI removed: #bizStack / .biz-toggle absent from all site/ files
debug_hits = []
for dirpath, _, files in os.walk(SITE):
    for f in files:
        p = os.path.join(dirpath, f)
        try:
            t = open(p, encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        if re.search(r"bizStack|biz-toggle", t):
            debug_hits.append(os.path.relpath(p, ROOT))
check(
    "E群", "E1 デバッグUI除去 (#bizStack / .biz-toggle が site/ に 0件)",
    len(debug_hits) == 0,
    f"hits={debug_hits or 0}",
)

# E2. wireframe.html removed from site/
wireframe_exists = os.path.exists(os.path.join(SITE, "wireframe.html"))
check(
    "E群", "E2 wireframe除去 (site/wireframe.html が存在しない)",
    not wireframe_exists,
    f"site/wireframe.html 存在={wireframe_exists}",
)


# ===========================================================================
# Report
# ===========================================================================
print("=" * 78)
print("KLK-002 static acceptance checks  (確定§9 / 2026-06-26 改訂 を正として再設定)")
print("=" * 78)
failed = 0
current_group = None
for group, name, passed, detail in results:
    if group != current_group:
        print(f"\n--- {group} ---")
        current_group = group
    status = "PASS" if passed else "FAIL"
    if not passed:
        failed += 1
    print(f"[{status}] {name}")
    print(f"        {detail}")
print("-" * 78)
print(f"{len(results)} checks, {failed} failed")
print()
print("B群（環境制約で静的検証外 = 未実測）:")
print("  - モバイル Lighthouse Performance >= 90 : 未実測（Lighthouse CLI 無し）")
print("  - 実描画の目視 (360/375/768/1024px)     : 未実測（ヘッドレスブラウザ無し）")
print("  - reduced-motion 実機での自動送り停止/reveal無効 : 未実測（コードレベルはC4で確認）")
sys.exit(1 if failed else 0)
