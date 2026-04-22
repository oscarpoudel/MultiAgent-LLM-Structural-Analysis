import { $$ } from './dom.js';

export function initTabs({ onDrawTab }) {
  $$('.tab').forEach((tab) => {
    tab.addEventListener('click', () => {
      $$('.tab').forEach((button) => button.classList.remove('active'));
      $$('.page').forEach((page) => {
        page.classList.add('hidden');
        page.classList.remove('active');
      });

      tab.classList.add('active');
      const page = document.getElementById(`tab-${tab.dataset.tab}`);
      if (page) {
        page.classList.remove('hidden');
        page.classList.add('active');
      }
      if (tab.dataset.tab === 'draw') onDrawTab();
    });
  });
}
