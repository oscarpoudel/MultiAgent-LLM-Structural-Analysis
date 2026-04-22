import { byId } from './dom.js';

function setTheme(isDark) {
  const themeIco = byId('themeIco');
  document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
  themeIco.textContent = isDark ? '\u2600' : '\u263E';
  localStorage.setItem('theme', isDark ? 'dark' : 'light');
}

export function initTheme() {
  const themeBtn = byId('themeBtn');
  themeBtn.addEventListener('click', () => {
    setTheme(document.documentElement.getAttribute('data-theme') !== 'dark');
  });
  if (localStorage.getItem('theme') === 'dark') setTheme(true);
}
