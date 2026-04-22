export const $ = (selector, root = document) => root.querySelector(selector);
export const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

export function byId(id) {
  return document.getElementById(id);
}

export function showTab(tabName) {
  $$('.tab').forEach((button) => button.classList.remove('active'));
  $$('.page').forEach((page) => {
    page.classList.add('hidden');
    page.classList.remove('active');
  });

  const tab = $(`.tab[data-tab="${tabName}"]`);
  const page = byId(`tab-${tabName}`);
  if (tab) tab.classList.add('active');
  if (page) {
    page.classList.remove('hidden');
    page.classList.add('active');
  }
}

export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
