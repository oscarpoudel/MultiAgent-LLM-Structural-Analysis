import { byId } from './dom.js';
import { openPopup } from './tabs.js';
import { switchLoadTab } from './loads.js';
import { switchSectionTab } from './sections.js';
import { loadHistory } from './history.js';
import {
  runAnalysis,
  clearCurrentModel,
  clearAnalysisResults,
  drawSimpleBeam,
  drawThreeByThreeThreeStoryFrame,
  applyMemberGroupSections,
  exportModelJson,
} from './analysis.js';
import { toggleTree } from './modelTree.js';

let open = false;
let items = [];
let filtered = [];
let cursor = 0;

const COMMANDS = [
  { id: 'run', label: 'Run analysis', hint: 'Analyze', run: () => runAnalysis() },
  { id: 'clear-model', label: 'Clear model', hint: 'Model', run: () => clearCurrentModel({ confirmFirst: true }) },
  { id: 'clear-results', label: 'Clear analysis results', hint: 'Model', run: () => clearAnalysisResults() },
  { id: 'frame-333', label: 'Insert 3x3 three-story frame', hint: 'Template', run: () => drawThreeByThreeThreeStoryFrame() },
  { id: 'beam', label: 'Insert simple beam', hint: 'Template', run: () => drawSimpleBeam({}) },
  { id: 'sections', label: 'Apply beam/column sections', hint: 'Model', run: () => applyMemberGroupSections() },
  { id: 'export', label: 'Export model (JSON)', hint: 'File', run: () => exportModelJson() },
  { id: 'import', label: 'Import model (JSON)', hint: 'File', run: () => byId('importJsonFile')?.click() },

  { id: 'view-plan', label: 'View: Plan', hint: 'View', run: () => byId('viewPlanBtn')?.click() },
  { id: 'view-elev', label: 'View: Elevation', hint: 'View', run: () => byId('viewElevBtn')?.click() },
  { id: 'view-3d', label: 'View: 3D perspective', hint: 'View', run: () => byId('view3DBtn')?.click() },

  { id: 't-grid', label: 'Toggle grid', hint: 'Display', run: () => toggle('showGrid') },
  { id: 't-labels', label: 'Toggle labels', hint: 'Display', run: () => toggle('showLabels') },
  { id: 't-deformed', label: 'Toggle deformed shape', hint: 'Display', run: () => toggle('showDeformed') },
  { id: 't-forces', label: 'Toggle member forces', hint: 'Display', run: () => toggle('showForces') },
  { id: 't-drift', label: 'Toggle story drift', hint: 'Display', run: () => toggle('showDrift') },

  { id: 'l-wind', label: 'Wind load (ASCE 7-22)', hint: 'Loads', run: () => openLoad('wind') },
  { id: 'l-seismic', label: 'Seismic load', hint: 'Loads', run: () => openLoad('seismic') },
  { id: 'l-snow', label: 'Snow load', hint: 'Loads', run: () => openLoad('snow') },
  { id: 'l-spectrum', label: 'Response spectrum', hint: 'Loads', run: () => openLoad('spectrum') },
  { id: 'l-pdelta', label: 'P-delta analysis', hint: 'Loads', run: () => openLoad('pdelta') },
  { id: 'l-sens', label: 'Sensitivity study', hint: 'Loads', run: () => openLoad('sensitivity') },
  { id: 'l-multi', label: 'Multi-hazard optimizer', hint: 'Loads', run: () => openLoad('multihazard') },

  { id: 'd-library', label: 'Steel section library', hint: 'Design', run: () => openDesign('library') },
  { id: 'd-select', label: 'Steel section selection', hint: 'Design', run: () => openDesign('select') },
  { id: 'd-concrete', label: 'Concrete design', hint: 'Design', run: () => openDesign('concrete') },
  { id: 'd-timber', label: 'Timber design', hint: 'Design', run: () => openDesign('timber') },
  { id: 'd-foundation', label: 'Foundation design', hint: 'Design', run: () => openDesign('foundation') },
  { id: 'd-fatigue', label: 'Fatigue check', hint: 'Design', run: () => openDesign('fatigue') },
  { id: 'd-cost', label: 'Cost estimate', hint: 'Design', run: () => openDesign('cost') },

  { id: 'history', label: 'Open history', hint: 'Tools', run: () => { openPopup('modal-history'); loadHistory(); } },
  { id: 'tree', label: 'Toggle model tree', hint: 'Tools', run: () => toggleTree() },
  { id: 'settings', label: 'Open settings', hint: 'Tools', run: () => byId('settingsBtn')?.click() },
  { id: 'theme', label: 'Toggle light/dark theme', hint: 'Tools', run: () => byId('themeBtn')?.click() },
];

function toggle(id) {
  const el = byId(id);
  if (el) { el.checked = !el.checked; el.dispatchEvent(new Event('change')); }
}

function openLoad(name) {
  openPopup('modal-loads');
  switchLoadTab(name);
}

function openDesign(name) {
  openPopup('modal-sections');
  switchSectionTab(name);
}

export function initCommandPalette() {
  buildDom();
  document.addEventListener('keydown', onKey);
}

function buildDom() {
  if (byId('cmdPalette')) return;
  const overlay = document.createElement('div');
  overlay.id = 'cmdPalette';
  overlay.className = 'cmd-palette hidden';
  overlay.innerHTML = `
    <div class="cmd-box">
      <div class="cmd-input-row">
        <span class="cmd-ico">&#8982;</span>
        <input id="cmdInput" type="text" placeholder="Type a command… (e.g. wind, run, plan)" autocomplete="off" spellcheck="false"/>
        <kbd>esc</kbd>
      </div>
      <div class="cmd-list" id="cmdList"></div>
      <div class="cmd-foot"><span>&uarr;&darr; navigate</span><span>&crarr; run</span><span>ctrl+K open</span></div>
    </div>`;
  document.body.appendChild(overlay);

  overlay.addEventListener('click', (e) => { if (e.target === overlay) closePalette(); });
  const input = byId('cmdInput');
  input.addEventListener('input', () => { cursor = 0; filter(input.value); });
  input.addEventListener('keydown', onInputKey);
}

function onKey(e) {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault();
    openPalette();
  }
}

function openPalette() {
  open = true;
  const overlay = byId('cmdPalette');
  overlay.classList.remove('hidden');
  const input = byId('cmdInput');
  input.value = '';
  filter('');
  setTimeout(() => input.focus(), 0);
}

function closePalette() {
  open = false;
  byId('cmdPalette')?.classList.add('hidden');
}

function filter(query) {
  const q = query.trim().toLowerCase();
  filtered = !q
    ? COMMANDS
    : COMMANDS.filter((c) =>
        c.label.toLowerCase().includes(q) ||
        c.hint.toLowerCase().includes(q) ||
        c.id.includes(q));
  cursor = 0;
  renderList();
}

function renderList() {
  const list = byId('cmdList');
  if (!list) return;
  if (!filtered.length) {
    list.innerHTML = '<div class="cmd-empty">No matching commands</div>';
    return;
  }
  list.innerHTML = filtered.map((c, i) => `
    <div class="cmd-item ${i === cursor ? 'active' : ''}" data-idx="${i}">
      <span class="cmd-label">${c.label}</span>
      <span class="cmd-hint">${c.hint}</span>
    </div>`).join('');
  list.querySelectorAll('.cmd-item').forEach((el) => {
    el.addEventListener('mousedown', (e) => { e.preventDefault(); runItem(Number(el.dataset.idx)); });
  });
  const active = list.querySelector('.cmd-item.active');
  if (active) active.scrollIntoView({ block: 'nearest' });
}

function onInputKey(e) {
  if (e.key === 'ArrowDown') { e.preventDefault(); cursor = Math.min(cursor + 1, filtered.length - 1); renderList(); }
  else if (e.key === 'ArrowUp') { e.preventDefault(); cursor = Math.max(cursor - 1, 0); renderList(); }
  else if (e.key === 'Enter') { e.preventDefault(); runItem(cursor); }
  else if (e.key === 'Escape') { e.preventDefault(); closePalette(); }
}

function runItem(idx) {
  const cmd = filtered[idx];
  if (!cmd) return;
  closePalette();
  cmd.run();
}
