import { $$ } from './dom.js';

const TAB_PAGES = ['tab-draw', 'tab-loads', 'tab-sections', 'tab-history'];

export function initTabs({ onDrawTab }) {
  $$('.tab').forEach((tab) => {
    tab.addEventListener('click', () => {
      $$('.tab').forEach((button) => button.classList.remove('active'));
      TAB_PAGES.forEach(id => {
        const page = document.getElementById(id);
        if (page) {
          page.classList.add('hidden');
          page.classList.remove('active');
        }
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
