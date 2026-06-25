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

  /* ---------- FV カルーセル（MV画像＋キャッチコピーを同期フェード切替） ----------
     スライド: 1=会社全体 / 2=ITインフラ訴求 / 3=SES訴求。
     ビジュアル(.fv__photo)はクロスフェード、テキストはフェードスルーで内容差し替え
     （単一 h1 を維持したまま innerHTML/textContent を更新）。
     - 自動送り（既定 5.5秒）。ホバー/フォーカス中は一時停止。
     - ドットで手動切替。prefers-reduced-motion 時は自動送りせず即時切替。 */
  var FV_SLIDES = [
    {
      eyebrow: '',
      title: '堅実な技術で、<br>事業と人の成長を支える。',
      sub: '止まらないインフラを設計・運用する「ITインフラ事業」と、現場で力を伸ばすエンジニアを支える「SES事業」。2つの軸で、お客様とエンジニア双方の未来を育てます。'
    },
    {
      eyebrow: 'ITインフラ事業',
      title: '止まらない基盤を、<br>設計から運用まで。',
      sub: 'サーバー・ネットワーク・クラウドの設計・構築・運用保守をワンストップで。堅牢なインフラで、お客様のビジネスを足元から支えます。'
    },
    {
      eyebrow: 'SES事業',
      title: 'エンジニアの挑戦を、<br>現場で伸ばす。',
      sub: 'スキルと志向に合うプロジェクトへ。経験豊富なエンジニアが一人ひとりの成長に並走し、技術もキャリアも伸ばします。'
    }
  ];

  function initFvCarousel() {
    var fv = document.getElementById('fv');
    if (!fv) { return; }

    var textBlock = fv.querySelector('.fv__text');
    var eyebrowEl = fv.querySelector('.fv__eyebrow');
    var titleEl = fv.querySelector('.fv__title');
    var subEl = fv.querySelector('.fv__sub');
    var layers = Array.prototype.slice.call(fv.querySelectorAll('.fv__photo'));
    var dots = Array.prototype.slice.call(fv.querySelectorAll('.fv__dot'));
    if (!textBlock || !titleEl || layers.length < 2) { return; }

    var n = FV_SLIDES.length;
    var current = 0;
    var timer = null;
    var swapTimer = null;
    var INTERVAL = 5500;
    var reduceMQ = window.matchMedia('(prefers-reduced-motion: reduce)');

    function applyText(i) {
      if (eyebrowEl) {
        var eb = FV_SLIDES[i].eyebrow;
        eyebrowEl.textContent = eb || '';
        // 空のスライド（スライド1）はタグ自体を非表示にし、余白も残さない
        eyebrowEl.style.display = eb ? '' : 'none';
      }
      titleEl.innerHTML = FV_SLIDES[i].title;
      if (subEl) { subEl.textContent = FV_SLIDES[i].sub; }
    }

    function render(i, animate) {
      i = (i % n + n) % n;
      // ビジュアル: クロスフェード
      for (var k = 0; k < layers.length; k++) {
        layers[k].classList.toggle('is-active', k === i);
      }
      // ドット状態
      for (var d = 0; d < dots.length; d++) {
        var on = d === i;
        dots[d].classList.toggle('is-active', on);
        dots[d].setAttribute('aria-selected', on ? 'true' : 'false');
      }
      // テキスト: フェードスルー（縮退モーション時は即時）
      if (swapTimer) { window.clearTimeout(swapTimer); swapTimer = null; }
      if (animate && !reduceMQ.matches) {
        textBlock.classList.add('is-leaving');
        swapTimer = window.setTimeout(function () {
          applyText(i);
          textBlock.classList.remove('is-leaving');
        }, 400);
      } else {
        applyText(i);
      }
      current = i;
    }

    function next() { render(current + 1, true); }

    function start() {
      stop();
      if (reduceMQ.matches) { return; }   // 自動送りしない（アクセシビリティ）
      timer = window.setInterval(next, INTERVAL);
    }
    function stop() {
      if (timer) { window.clearInterval(timer); timer = null; }
    }

    for (var di = 0; di < dots.length; di++) {
      (function (idx) {
        dots[idx].addEventListener('click', function () {
          render(idx, true);
          start(); // 手動操作後はタイマーをリセット
        });
      })(di);
    }

    // ホバー/フォーカス中は一時停止
    fv.addEventListener('mouseenter', stop);
    fv.addEventListener('mouseleave', start);
    fv.addEventListener('focusin', stop);
    fv.addEventListener('focusout', start);

    render(0, false);
    start();
  }

  /* ---------- スクロール連動「ふわっと」表示（reveal） ----------
     対象要素が画面に入ったら下からフェードイン（IntersectionObserver・1回のみ）。
     FVは対象外（既にカルーセルで動く）。グループ（事業カード/お知らせ）は軽くstagger。
     縮退モーション/IO非対応/JS無効時は通常表示（初期非表示クラスを付けない）。 */
  function initScrollReveal() {
    if (!('IntersectionObserver' in window)) { return; }
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) { return; }

    // 入れ子の二重revealを避けるため、対象はセクション単位で明示指定
    var selectors = [
      '#business .section__title', '#business .section__lead',
      '#business .biz-toggle', '#business .biz-card',
      '.recruit__text', '.recruit__visual',
      '.company__text', '.company__visual',
      '.news__head', '.news__item',
      '#contact .section__title', '#contact .section__lead',
      '#contact .contact__actions', '#contact .contact__note'
    ];

    var els = [];
    for (var s = 0; s < selectors.length; s++) {
      var found = document.querySelectorAll(selectors[s]);
      for (var f = 0; f < found.length; f++) {
        var node = found[f];
        if (node.closest('#fv')) { continue; }
        if (els.indexOf(node) === -1) { els.push(node); }
      }
    }
    if (!els.length) { return; }

    document.documentElement.classList.add('reveal-ready');
    for (var i = 0; i < els.length; i++) { els[i].classList.add('reveal'); }

    // グループ内の出現順stagger（最大360ms）
    function staggerDelay(el) {
      var cls = el.classList.contains('biz-card') ? 'biz-card'
        : (el.classList.contains('news__item') ? 'news__item' : null);
      if (!cls) { return 0; }
      var idx = 0, sib = el.previousElementSibling;
      while (sib) {
        if (sib.classList && sib.classList.contains(cls)) { idx++; }
        sib = sib.previousElementSibling;
      }
      return Math.min(idx * 90, 360);
    }

    var io = new IntersectionObserver(function (entries) {
      for (var e = 0; e < entries.length; e++) {
        var entry = entries[e];
        if (!entry.isIntersecting) { continue; }
        var el = entry.target;
        var d = staggerDelay(el);
        if (d) { el.style.transitionDelay = d + 'ms'; }
        el.classList.add('is-visible');
        io.unobserve(el);
      }
    }, { threshold: 0.15, rootMargin: '0px 0px -10% 0px' });

    for (var o = 0; o < els.length; o++) { io.observe(els[o]); }
  }

  /* ---------- 初期化 ---------- */
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      initNavToggle();
      initCtaTracking();
      initFvCarousel();
      initScrollReveal();
    });
  } else {
    initNavToggle();
    initCtaTracking();
    initFvCarousel();
    initScrollReveal();
  }
})();
