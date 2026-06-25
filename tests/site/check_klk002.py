#!/usr/bin/env python3
"""
KLK-002 acceptance-condition checker (static / no browser required).

Verifies the statically-checkable acceptance conditions from
docs/designs/KLK-002.md §9 against site/index.html, site/css/style.css,
site/js/main.js and site/assets/.

Run: python3 tests/site/check_klk002.py
Exit code 0 = all static checks pass, 1 = at least one fail.

This is a tester-owned check script. It does NOT modify production code
under site/. Browser-only conditions (Lighthouse, visual rendering) are
out of scope here and reported as "未実測（環境制約）" by the tester.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SITE = os.path.join(ROOT, "site")
HTML = open(os.path.join(SITE, "index.html"), encoding="utf-8").read()
CSS = open(os.path.join(SITE, "css", "style.css"), encoding="utf-8").read()


results = []  # (name, passed: bool|None, detail)  None == not measurable here


def check(name, passed, detail):
    results.append((name, passed, detail))


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

# ---------------------------------------------------------------------------
# A1. Section structure & order:
#     fv -> business -> recruit -> company -> news -> contact -> footer
#     (wireframe.html 準拠。実績(results)廃止 / 会社案内(company) / お知らせ(news) 追加)
# ---------------------------------------------------------------------------
section_ids = re.findall(r'<section[^>]*id="([^"]+)"', HTML)
footer_present = bool(re.search(r"<footer", HTML))
expected_sections = ["fv", "business", "recruit", "company", "news", "contact"]
order_ok = section_ids == expected_sections and footer_present
check(
    "A1 セクション構成と順序 (fv→business→recruit→company→news→contact→footer)",
    order_ok,
    f"section順={section_ids}, footer={'有' if footer_present else '無'}",
)

# ---------------------------------------------------------------------------
# A2. Heading hierarchy: h1 x1 (in FV) -> section h2 -> card h3
# ---------------------------------------------------------------------------
h1s = re.findall(r"<h1[ >]", HTML)
# h1 must sit inside #fv
fv_block = re.search(r'<section id="fv".*?</section>', HTML, re.S)
h1_in_fv = bool(fv_block and re.search(r"<h1[ >]", fv_block.group(0)))
h2_count = len(re.findall(r"<h2[ >]", HTML))
h3_count = len(re.findall(r"<h3[ >]", HTML))
biz_h3 = len(re.findall(r'class="biz-card__title"', HTML))
# FVの見出しは h1。残りセクション(business/recruit/company/news/contact)が h2。
# よって h2 は section数 - FV(1) が正（h2_count == non_fv_sections）。カード h3 は 2。
non_fv_sections = len([s for s in section_ids if s != "fv"])
heading_ok = len(h1s) == 1 and h1_in_fv and h2_count == non_fv_sections and biz_h3 == 2
check(
    "A2 見出し階層 (h1×1=FV, 非FVセクション=h2, カード h3×2)",
    heading_ok,
    f"h1={len(h1s)}(FV内={h1_in_fv}), h2={h2_count}(非FVセクション数={non_fv_sections}), "
    f"h3={h3_count}, biz-card__title={biz_h3}",
)

# ---------------------------------------------------------------------------
# A3. FV 2CTA juxtaposition + 44px tap target + :focus-visible
# ---------------------------------------------------------------------------
fv_html = fv_block.group(0) if fv_block else ""
cta_contact = 'data-cta="contact"' in fv_html
cta_recruit = 'data-cta="recruit"' in fv_html
# .btn min-height/min-width 44px
btn_block = re.search(r"\.btn\s*\{([^}]*)\}", CSS)
btn_css = btn_block.group(1) if btn_block else ""
min_h = "min-height: 44px" in btn_css.replace(" ", " ")
min_h = bool(re.search(r"min-height:\s*44px", btn_css))
min_w = bool(re.search(r"min-width:\s*44px", btn_css))
focus_visible = bool(re.search(r":focus-visible\s*\{", CSS))
cta_ok = cta_contact and cta_recruit and min_h and min_w and focus_visible
check(
    "A3 FV 2CTA並置 + 44px + :focus-visible",
    cta_ok,
    f"contact={cta_contact}, recruit={cta_recruit}, min-height44={min_h}, "
    f"min-width44={min_w}, :focus-visible={focus_visible}",
)

# ---------------------------------------------------------------------------
# A4. Two businesses equal: same .biz-card class x2, dims via CSS vars
# ---------------------------------------------------------------------------
biz_cards = len(re.findall(r'class="biz-card"', HTML))
card_pad_var = bool(re.search(r"\.biz-card\s*\{[^}]*padding:\s*var\(--card-pad\)", CSS, re.S))
card_radius_var = bool(re.search(r"border-radius:\s*var\(--card-radius\)", CSS))
icon_var = bool(re.search(r"width:\s*var\(--card-icon\)", CSS))
has_infra = "ITインフラ事業" in HTML
has_ses = "SES事業" in HTML
equal_ok = biz_cards == 2 and card_pad_var and card_radius_var and icon_var and has_infra and has_ses
check(
    "A4 2事業対等 (.biz-card×2, 寸法=CSS変数共通)",
    equal_ok,
    f".biz-card数={biz_cards}, padding=var(--card-pad):{card_pad_var}, "
    f"radius=var:{card_radius_var}, icon=var:{icon_var}, ITインフラ={has_infra}, SES={has_ses}",
)

# ---------------------------------------------------------------------------
# A5. Color tokens: white bg + green primary + single accent; no external URL/img
# ---------------------------------------------------------------------------
bg_white = TOK["--color-bg"] and TOK["--color-bg"].lower() in ("#ffffff", "#fff")


def is_greenish(hexstr):
    h = hexstr.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return g > r and g >= b  # green channel dominant


primary_green = TOK["--color-primary"] and is_greenish(TOK["--color-primary"])
# single accent: exactly one --color-accent base token family
accent_defined = TOK["--color-accent"] is not None
# external CDN/image URL scan (exclude W3C svg namespace)
ext_urls = []
for fn in ["index.html", "css/style.css", "js/main.js", "assets/favicon.svg",
           "assets/logo-placeholder.svg"]:
    txt = open(os.path.join(SITE, fn), encoding="utf-8").read()
    for m in re.findall(r'https?://[^\s"\')]+', txt):
        if m.startswith("http://www.w3.org/2000/svg"):
            continue
        ext_urls.append(f"{fn}:{m}")
no_ext = len(ext_urls) == 0
color_ok = bool(bg_white and primary_green and accent_defined and no_ext)
check(
    "A5 カラー要件 (白背景+緑メイン+アクセント1色, 外部URL0)",
    color_ok,
    f"bg={TOK['--color-bg']}(白={bool(bg_white)}), primary={TOK['--color-primary']}"
    f"(緑={primary_green}), accent={TOK['--color-accent']}, 外部URL={ext_urls or 0}",
)

# ---------------------------------------------------------------------------
# A6. Contrast >= 4.5:1 (large headings >= 3:1)
# ---------------------------------------------------------------------------
white = TOK["--color-bg"]            # #ffffff
surface = TOK["--color-surface"]     # card surface #f6faf7
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
contrast_all_ok = True
for label, fg, bg, threshold in contrast_targets:
    ratio = contrast(fg, bg)
    ok = ratio >= threshold
    if not ok:
        contrast_all_ok = False
    contrast_rows.append(f"{label}: {ratio:.2f}:1 (>= {threshold}) {'OK' if ok else 'NG'}")
check(
    "A6 主要テキストのコントラスト >= 4.5:1",
    contrast_all_ok,
    " | ".join(contrast_rows),
)

# ---------------------------------------------------------------------------
# A7. 360px horizontal-scroll defenses (code-level)
# ---------------------------------------------------------------------------
overflow_x = bool(re.search(r"overflow-x:\s*hidden", CSS))
img_max = bool(re.search(r"img,\s*svg\s*\{[^}]*max-width:\s*100%", CSS, re.S))
clamp_pad = bool(re.search(r"padding-inline:\s*clamp\(", CSS))
fluid_grid = "grid-template-columns: 1fr" in CSS
overflow_ok = overflow_x and img_max and clamp_pad and fluid_grid
check(
    "A7 360px横スクロール対策 (overflow-x, img/svg max-width, clamp pad, 流動grid)",
    overflow_ok,
    f"overflow-x:hidden={overflow_x}, img/svg max-width100%={img_max}, "
    f"clamp padding={clamp_pad}, 1fr流動grid={fluid_grid}",
)

# ---------------------------------------------------------------------------
# A8. No secrets
# ---------------------------------------------------------------------------
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
    "A8 機密情報なし (api_key|secret|password|token|private_key 0件)",
    len(secret_hits) == 0,
    f"hits={secret_hits or 0}",
)

# ---------------------------------------------------------------------------
# Extra: FV DOM order text -> visual -> cta
# ---------------------------------------------------------------------------
order_text = fv_html.find("fv__text")
order_visual = fv_html.find("fv__visual")
order_cta = fv_html.find("fv__cta")
dom_order_ok = 0 <= order_text < order_visual < order_cta
check(
    "Extra FV DOM順 (text→visual→cta)",
    dom_order_ok,
    f"text={order_text}, visual={order_visual}, cta={order_cta}",
)

# Extra: decorative SVG aria-hidden
dec_svgs = re.findall(r'<svg class="fv__accent"[^>]*>', HTML)
accent_aria = all('aria-hidden="true"' in s for s in dec_svgs) if dec_svgs else False
check(
    "Extra 装飾SVG aria-hidden",
    accent_aria,
    f"fv__accent数={len(dec_svgs)}, 全てaria-hidden={accent_aria}",
)

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
print("=" * 72)
print("KLK-002 static acceptance checks")
print("=" * 72)
failed = 0
for name, passed, detail in results:
    status = "PASS" if passed else "FAIL"
    if not passed:
        failed += 1
    print(f"[{status}] {name}")
    print(f"        {detail}")
print("-" * 72)
print(f"{len(results)} checks, {failed} failed")
sys.exit(1 if failed else 0)
