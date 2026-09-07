import { byId } from './dom.js';
import { S } from './state.js';
import { showProp } from './canvas3d/render.js';
import { triggerRedraw } from './canvas3d/scene.js';

let lastSig = '';
let open = false;

export function initModelTree() {
  const panel = byId('modelTree');
  if (!panel) return;
  const toggleBtn = byId('modelTreeBtn');
  if (toggleBtn) toggleBtn.addEventListener('click', toggleTree);
  const closeBtn = byId('modelTreeClose');
  if (closeBtn) closeBtn.addEventListener('click', () => setTreeOpen(false));
  panel.addEventListener('click', onTreeClick);
}

export function setTreeOpen(value) {
  open = value;
  const panel = byId('modelTree');
  const btn = byId('modelTreeBtn');
  if (panel) panel.classList.toggle('hidden', !open);
  if (btn) btn.classList.toggle('active', open);
  if (open) updateTree();
}

export function toggleTree() {
  setTreeOpen(!open);
}

// Called from the status bar poll. Re-renders only when the model or selection
// actually changes (signature-based), so it never fights the user's hover/click.
export function updateTree() {
  if (!open) return;
  const sig = signature();
  if (sig === lastSig) return;
  lastSig = sig;
  render();
}

function signature() {
  const nodes = S.nodes.map((n) => `${n.id}:${n.x},${n.y},${n.z || 0},${n.support || 'free'}`).join(';');
  const members = S.members.map((m) => `${m.id}:${m.n1}-${m.n2}:${m.group || ''}`).join(';');
  const slabs = (S.slabs || []).map((s) => `${s.id}:${(s.nodeIds || []).join('.')}`).join(';');
  const sel = S.selected ? `${S.selected.type}${S.selected.id}` : 'none';
  return `${nodes}|${members}|${slabs}|${sel}`;
}

function render() {
  const body = byId('modelTreeBody');
  if (!body) return;
  const selId = S.selected ? S.selected.id : null;

  const nodeRows = S.nodes.map((n) => `
    <div class="tree-row ${selId === n.id ? 'active' : ''}" data-type="node" data-id="${n.id}">
      <span class="tree-ico node">&#9679;</span>
      <span class="tree-label">Node ${n.id}</span>
      <span class="tree-meta">(${n.x}, ${n.y}, ${n.z || 0}) &middot; ${n.support || 'free'}</span>
    </div>`).join('');

  const memberRows = S.members.map((m) => `
    <div class="tree-row ${selId === m.id ? 'active' : ''}" data-type="member" data-id="${m.id}">
      <span class="tree-ico member">&#8212;</span>
      <span class="tree-label">Member ${m.id}</span>
      <span class="tree-meta">${m.n1}&ndash;${m.n2} &middot; ${m.group || 'member'}</span>
    </div>`).join('');

  const slabRows = (S.slabs || []).map((s) => `
    <div class="tree-row ${selId === s.id ? 'active' : ''}" data-type="slab" data-id="${s.id}">
      <span class="tree-ico slab">&#9632;</span>
      <span class="tree-label">Slab ${s.id}</span>
      <span class="tree-meta">${(s.nodeIds || []).length} nodes</span>
    </div>`).join('');

  body.innerHTML = `
    <div class="tree-section">
      <div class="tree-head"><span>Nodes</span><span class="tree-count">${S.nodes.length}</span></div>
      <div class="tree-rows">${nodeRows || '<div class="tree-empty">No nodes</div>'}</div>
    </div>
    <div class="tree-section">
      <div class="tree-head"><span>Members</span><span class="tree-count">${S.members.length}</span></div>
      <div class="tree-rows">${memberRows || '<div class="tree-empty">No members</div>'}</div>
    </div>
    <div class="tree-section">
      <div class="tree-head"><span>Slabs</span><span class="tree-count">${(S.slabs || []).length}</span></div>
      <div class="tree-rows">${slabRows || '<div class="tree-empty">No slabs</div>'}</div>
    </div>`;
}

function onTreeClick(e) {
  const row = e.target.closest('.tree-row');
  if (!row) return;
  const type = row.dataset.type;
  const id = Number(row.dataset.id);
  S.selected = { type, id };
  showProp();
  triggerRedraw();
  updateTree();
}
