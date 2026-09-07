import { byId, $$ } from './dom.js';

let onDrawTab = () => {};

// Popup manager for the large tool windows (Loads / Sections / History).
// The ribbon (ribbon.js) and history panel open these; this module owns the
// open/close/escape/overlay-click behavior.
export function initPopups({ onDrawTab: onDraw } = {}) {
  if (onDraw) onDrawTab = onDraw;

  $$('.modal-close').forEach((b) => {
    b.addEventListener('click', () => closePopup(b.dataset.close));
  });

  ['modal-loads', 'modal-sections', 'modal-history'].forEach((id) => {
    const ov = byId(id);
    if (ov) ov.addEventListener('click', (e) => { if (e.target === ov) closePopup(id); });
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeAllPopups();
  });
}

export function openPopup(id) {
  const el = byId(id);
  if (el) el.classList.remove('hidden');
}

export function closePopup(id) {
  const el = byId(id);
  if (el) {
    el.classList.add('hidden');
    onDrawTab();
  }
}

function closeAllPopups() {
  ['modal-loads', 'modal-sections', 'modal-history'].forEach(closePopup);
}
