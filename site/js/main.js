/* ============================================================
   Kenesis トップページ  main.js
   - ハンバーガーメニュー開閉（aria-expanded トグル）
   - CTAクリック計測フックの雛形（data-cta を読むだけ。実送信はしない）
   - 依存ライブラリなし / defer 読み込み
   ============================================================ */
(function () {
  'use strict';

  /* ---------- ハンバーガーメニュー開閉 ---------- */
  function initNavToggle() {
    var toggle = document.querySelector('.nav-toggle');
    var nav = document.getElementById('primary-nav');
    if (!toggle || !nav) { return; }

    function setOpen(open) {
      toggle.setAttribute('aria-expanded', String(open));
      toggle.setAttribute('aria-label', open ? 'メニューを閉じる' : 'メニューを開く');
      nav.classList.toggle('is-open', open);
    }

    toggle.addEventListener('click', function () {
      var isOpen = toggle.getAttribute('aria-expanded') === 'true';
      setOpen(!isOpen);
    });

    // ナビ内リンクをタップしたら閉じる（モバイル時の使い勝手）
    nav.addEventListener('click', function (e) {
      if (e.target.closest('a')) { setOpen(false); }
    });

    // Esc で閉じる
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && toggle.getAttribute('aria-expanded') === 'true') {
        setOpen(false);
        toggle.focus();
      }
    });
  }

  /* ---------- CTAクリック計測フック（雛形のみ） ----------
     data-cta 属性を持つ要素のクリックを拾い、計測キーを読み取る。
     本実装では実送信せず、フック関数を呼ぶ骨子のみ提供する
     （GA4等の本実装は別チケット）。 */
  function trackCtaClick(ctaKey, el) {
    // ここに将来 GA4 / 計測SDK への送信を実装する（別チケット）。
    // 現状は副作用なし。デバッグ確認用に dataset を読むだけに留める。
    if (window.__ctaHook && typeof window.__ctaHook === 'function') {
      window.__ctaHook(ctaKey, el);
    }
  }

  function initCtaTracking() {
    document.addEventListener('click', function (e) {
      var el = e.target.closest('[data-cta]');
      if (!el) { return; }
      var ctaKey = el.getAttribute('data-cta');
      if (ctaKey) { trackCtaClick(ctaKey, el); }
    });
  }

  /* ---------- 初期化 ---------- */
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      initNavToggle();
      initCtaTracking();
    });
  } else {
    initNavToggle();
    initCtaTracking();
  }
})();
