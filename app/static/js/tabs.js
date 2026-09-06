import { byId, $$ } from './dom.js';
import { switchLoadTab } from './loads.js';
import { switchSectionTab } from './sections.js';
import { loadHistory } from './history.js';

const LOAD_TOOLS = ['wind', 'seismic', 'spectrum', 'snow', 'pdelta', 'sensitivity', 'multihazard'];
const DESIGN_TOOLS = ['library', 'select', 'concrete', 'timber', 'foundation', 'fatigue', 'cost'];

let onDrawTab = () => {};

export function initTools({ onDrawTab: onDraw } = {}) {
  if (onDraw) onDrawTab = onDraw;

  const wrap = byId('toolsWrap');
  const btn = byId('toolsBtn');
  const menu = byId('toolsMenu');

  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    const willOpen = menu.classList.contains('hidden');
    menu.classList.toggle('hidden', !willOpen);
    wrap.classList.toggle('open', willOpen);
  });

  document.addEventListener('click', (e) => {
    if (!wrap.contains(e.target)) {
      menu.classList.add('hidden');
      wrap.classList.remove('open');
    }
  });

  $$('.tools-item').forEach((item) => {
    item.addEventListener('click', () => {
      menu.classList.add('hidden');
      wrap.classList.remove('open');
      openTool(item.dataset.tool);
    });
  });

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

function openTool(tool) {
  if (tool === 'history') {
    openPopup('modal-history');
    loadHistory();
    return;
  }
  if (LOAD_TOOLS.includes(tool)) {
    openPopup('modal-loads');
    switchLoadTab(tool);
    return;
  }
  if (DESIGN_TOOLS.includes(tool)) {
    openPopup('modal-sections');
    switchSectionTab(tool);
  }
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
