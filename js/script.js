// Run in the head before the first paint. Event delegation works while the body
// is still parsing; without JavaScript the existing expanded navigation remains.
(() => {
  const getToggle = () => document.querySelector('[data-menu-toggle]');
  const getNav = () => document.querySelector('[data-nav]');
  const closeMenu = (restoreFocus = false) => {
    const toggle = getToggle(), nav = getNav();
    if (!toggle || !nav) return;
    toggle.setAttribute('aria-expanded', 'false');
    toggle.setAttribute('aria-label', 'メニューを開く');
    nav.classList.remove('is-open');
    document.body.classList.remove('nav-open');
    if (restoreFocus) toggle.focus();
  };
  document.addEventListener('click', e => {
    if (!(e.target instanceof Element)) return;
    const toggle = getToggle(), nav = getNav();
    if (!toggle || !nav) return;
    if (toggle.contains(e.target)) {
      const open = toggle.getAttribute('aria-expanded') === 'true';
      toggle.setAttribute('aria-expanded', String(!open));
      toggle.setAttribute('aria-label', open ? 'メニューを開く' : 'メニューを閉じる');
      nav.classList.toggle('is-open', !open);
      document.body.classList.toggle('nav-open', !open);
    } else if (e.target.closest('[data-nav] a')) closeMenu();
  });
  document.addEventListener('keydown', e => {
    const toggle = getToggle(), nav = getNav();
    if (!toggle || !nav || toggle.getAttribute('aria-expanded') !== 'true') return;
    if (e.key === 'Escape') closeMenu(true);
    if (e.key === 'Tab') {
      const lastLink = nav.querySelector('a:last-child.button');
      if (e.shiftKey && document.activeElement === toggle && lastLink) {
        e.preventDefault();
        lastLink.focus();
      } else if (!e.shiftKey && document.activeElement === lastLink) {
        e.preventDefault();
        toggle.focus();
      }
    }
  });
  window.matchMedia('(max-width: 900px)').addEventListener('change', e => {
    if (!e.matches) closeMenu();
  });
  document.documentElement.classList.add('menu-ready');
})();

document.addEventListener('DOMContentLoaded', () => {
  const reveals = document.querySelectorAll('.reveal');
  if ('IntersectionObserver' in window && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.08, rootMargin: '0px 0px -30px' });
    reveals.forEach(el => observer.observe(el));
    document.documentElement.classList.add('reveal-ready');
  } else {
    reveals.forEach(el => el.classList.add('is-visible'));
  }

  document.querySelectorAll('[data-analytics-event]').forEach(el => {
    el.addEventListener('click', () => {
      if (typeof window.gtag === 'function') {
        const eventName = el.dataset.analyticsEvent;
        const params = {
          link_url: el.href || '',
          page_location: window.location.href,
          destination_type: el.dataset.contactDestination || ''
        };
        window.gtag('event', eventName, params);
        if (eventName === 'contact_page_click' || eventName === 'contact_form_open') {
          window.gtag('event', 'contact_click', params);
        }
      }
    });
  });
});
