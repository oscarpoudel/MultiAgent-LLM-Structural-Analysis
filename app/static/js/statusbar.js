import { byId } from './dom.js';
import { S } from './state.js';
import { updateTree } from './modelTree.js';

let timer = null;

function setText(id, value) {
  const el = byId(id);
  if (el) el.textContent = value;
}

function sync() {
  setText('sbNodes', String(S.nodes.length));
  setText('sbMembers', String(S.members.length));
  const loadCount = (S.loads || []).length + (S.memberLoads || []).length;
  setText('sbLoads', String(loadCount));
  setText('sbCombo', S.activeLoadCombination || '—');
  setText('sbTool', S.tool || 'select');

  // Show the friendly empty-state overlay only when the model has no geometry.
  const empty = byId('canvasEmpty');
  if (empty) empty.classList.toggle('show', S.nodes.length === 0 && S.members.length === 0);

  // Keep the model tree in sync (signature-guarded, cheap when unchanged).
  updateTree();

  const statusEl = byId('sbStatus');
  if (statusEl) {
    const canvasStatus = byId('canvasStatus');
    if (canvasStatus) statusEl.textContent = canvasStatus.textContent || 'Ready';
  }

  const solverEl = byId('sbSolver');
  if (solverEl && S.results && S.results.solver) {
    solverEl.textContent = S.results.solver;
  }

  // Mirror the chat header LLM indicator into the status bar.
  const dot = byId('sbLlmDot');
  const label = byId('sbLlm');
  const chatDot = byId('llmDot');
  if (dot && chatDot) {
    dot.className = 'sb-dot' + (chatDot.className.includes('off') ? ' off' : chatDot.className.includes('checking') ? ' checking' : '');
  }
  if (label && chatDot) {
    if (chatDot.className.includes('off')) { label.textContent = 'offline'; label.className = 'sb-v err'; }
    else if (chatDot.className.includes('checking')) { label.textContent = 'checking'; label.className = 'sb-v warn'; }
    else { label.textContent = 'online'; label.className = 'sb-v ok'; }
  }
}

export function initStatusbar() {
  if (timer) return;
  sync();
  timer = window.setInterval(sync, 600);
}

export function refreshStatusbar() {
  sync();
}
