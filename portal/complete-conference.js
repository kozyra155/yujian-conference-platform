(() => {
  document.documentElement.classList.add('complete-js');
  const clock = document.querySelector('[data-live-countdown]');
  if (clock) {
    const target = Date.parse(clock.dataset.target);
    const serverNow = Date.parse(clock.dataset.now);
    const started = performance.now();
    let timer;
    function tick() {
      const total = Math.max(0, Math.ceil((target - serverNow - (performance.now() - started)) / 1000));
      const values = {days: Math.floor(total / 86400), hours: Math.floor(total / 3600) % 24,
        minutes: Math.floor(total / 60) % 60, seconds: total % 60};
      for (const [part, value] of Object.entries(values)) {
        clock.querySelector(`[data-countdown-part="${part}"]`).textContent = part === 'days' ? String(value) : String(value).padStart(2, '0');
      }
      clock.querySelector('.complete-clock-running').hidden = total === 0;
      clock.querySelector('.complete-clock-ended').hidden = total !== 0;
      if (!total) clearInterval(timer);
    }
    tick();
    if (target > serverNow) timer = setInterval(tick, 1000);
  }
  const nav = document.querySelector('.complete-navigation');
  function toggle(button, open) {
    button.setAttribute('aria-expanded', String(open));
    const target = document.getElementById(button.getAttribute('aria-controls'));
    if (button.matches('.complete-mobile-toggle')) target?.toggleAttribute('data-open', open);
    else button.closest('.complete-menu-item')?.toggleAttribute('data-open', open);
  }
  nav?.querySelectorAll('button[aria-controls]').forEach(button => {
    button.addEventListener('click', () => toggle(button, button.getAttribute('aria-expanded') !== 'true'));
  });
  const desktop = window.matchMedia('(min-width:901px)');
  nav?.querySelectorAll('.has-children').forEach(item => {
    const button = item.querySelector(':scope > .complete-menu-row > button');
    item.addEventListener('pointerenter', () => { if (desktop.matches) toggle(button, true); });
    item.addEventListener('pointerleave', () => { if (desktop.matches && !item.contains(document.activeElement)) toggle(button, false); });
    item.addEventListener('focusin', event => { if (desktop.matches && event.target.matches('a')) toggle(button, true); });
    item.addEventListener('focusout', event => { if (desktop.matches && !item.contains(event.relatedTarget)) toggle(button, false); });
  });
  nav?.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      const item = event.target.closest('.complete-menu-item[data-open]');
      const button = item?.querySelector(':scope > .complete-menu-row > button') || nav.querySelector('.complete-mobile-toggle');
      if (button) { toggle(button, false); button.focus(); event.preventDefault(); }
    }
    if (event.key === 'ArrowDown' && event.target.matches('.complete-submenu-toggle')) {
      toggle(event.target, true);
      document.getElementById(event.target.getAttribute('aria-controls'))?.querySelector('a,button')?.focus();
      event.preventDefault();
    }
  });
  document.addEventListener('click', event => {
    if (!nav?.contains(event.target)) nav?.querySelectorAll('button[aria-controls]').forEach(button => toggle(button, false));
  });
  function languageChanged() {
    const language = window.MeetPortal?.language || 'zh';
    document.querySelectorAll('[data-complete-language]').forEach(element => {
      const group = element.dataset.completeLanguageGroup || 'introduction';
      const hasEnglish = Array.from(document.querySelectorAll('[data-complete-language="en"]'))
        .some(item => (item.dataset.completeLanguageGroup || 'introduction') === group);
      element.hidden = element.dataset.completeLanguage !== (language === 'en' && hasEnglish ? 'en' : 'zh');
    });
    document.querySelectorAll('[data-image-zh]').forEach(element => {
      element.src = language === 'en' ? element.dataset.imageEn : element.dataset.imageZh;
    });
  }
  window.addEventListener('meet-language-change', languageChanged);
  languageChanged();
})();
