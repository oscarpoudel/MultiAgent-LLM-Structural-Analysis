export const $ = (selector, root = document) => root.querySelector(selector);
export const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

export function byId(id) {
  return document.getElementById(id);
}

export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
