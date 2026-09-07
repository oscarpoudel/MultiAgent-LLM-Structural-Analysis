import { byId, $$ } from './dom.js';
import { createProject, deleteProject, getAllProjects, getProject, saveProject } from './projects.js';
import { S, resetModel } from './state.js';
import { canvas3d, draw, initCanvas, resizeCanvas } from './canvas3d/index.js';
import { triggerRedraw } from './canvas3d/scene.js';
import { initAnalysis } from './analysis.js';
import { initChat } from './chat.js';
import { initHistory } from './history.js';
import { initModals, showLoadModal, showMemberLoadModal, showSupportModal, showSlabModal } from './modals.js';
import { initExports } from './results.js';
import { initSections } from './sections.js';
import { initLoads } from './loads.js';
import { initRibbon, measureRibbon } from './ribbon.js';
import { initPopups } from './tabs.js';
import { initModelTree } from './modelTree.js';
import { initViewPresets } from './viewPresets.js';
import { initCommandPalette } from './commandPalette.js';
import { initTheme } from './theme.js';
import { initShortcuts } from './shortcuts.js';
import { initStatusbar } from './statusbar.js';
import { initCameraPosition, updateStatus } from './canvas3d/ui.js';

let currentProject = null;
let drawPageInitialized = false;
let autosaveTimer = null;
let lastSavedSnapshot = '';

initTheme();
initLandingPage();
initSetupPage();
initCommandPalette();

function initLandingPage() {
  byId('newProjectBtn').addEventListener('click', async () => {
    currentProject = createProject({ name: 'New Project' });
    await saveProject(currentProject);
    showSetupPage();
  });

  loadProjectGrid();
}

async function loadProjectGrid() {
  const grid = byId('projectGrid');
  try {
    const projects = await getAllProjects();
    if (projects.length === 0) {
      grid.innerHTML = '<p class="placeholder">No projects yet. Create one to get started.</p>';
      return;
    }
    grid.innerHTML = '';
    projects.forEach(proj => {
      const card = document.createElement('div');
      card.className = 'project-card';
      const date = new Date(proj.updatedAt).toLocaleDateString();
      const nodeCount = (proj.nodes || []).length;
      const memberCount = (proj.members || []).length;
      const levelCount = (proj.levels || []).length;
      card.innerHTML = `
        <h3>${proj.name}</h3>
        <div class="project-card-stats">
          <span>${nodeCount} nodes</span>
          <span>${memberCount} members</span>
          <span>${levelCount} levels</span>
        </div>
        <div class="project-card-date">${date}</div>
        <div class="project-card-actions">
          <button class="btn-xs" data-action="open">Open</button>
          <button class="btn-xs danger" data-action="delete">Delete</button>
        </div>
      `;
      card.querySelector('[data-action="open"]').addEventListener('click', (e) => {
        e.stopPropagation();
        openProject(proj.id);
      });
      card.querySelector('[data-action="delete"]').addEventListener('click', async (e) => {
        e.stopPropagation();
        if (confirm(`Delete "${proj.name}"?`)) {
          await deleteProject(proj.id);
          loadProjectGrid();
        }
      });
      grid.appendChild(card);
    });
  } catch (err) {
    console.error('Failed to load projects:', err);
    grid.innerHTML = '<p class="placeholder">Error loading projects</p>';
  }
}

async function openProject(id) {
  try {
    const proj = await getProject(id);
    if (!proj) return;
    currentProject = proj;
    loadProjectIntoState(proj);
    showDrawPage();
  } catch (err) {
    console.error('Failed to open project:', err);
  }
}

function loadProjectIntoState(proj) {
  resetModel();
  S.project = proj;
  S.nodes = proj.nodes || [];
  S.members = proj.members || [];
  S.slabs = proj.slabs || [];
  S.loads = proj.loads || [];
  S.memberLoads = proj.memberLoads || [];
  S.loadCombinations = proj.loadCombinations || S.loadCombinations;
  S.activeLoadCombination = proj.activeLoadCombination || S.activeLoadCombination;
  S.rigidDiaphragms = proj.rigidDiaphragms !== undefined ? proj.rigidDiaphragms : S.rigidDiaphragms;
  S.nextNodeId = proj.nextNodeId || 1;
  S.nextMemberId = proj.nextMemberId || 1;
  S.nextSlabId = proj.nextSlabId || 1;

  canvas3d.gridLinesX = proj.gridLinesX || [];
  canvas3d.gridLinesY = proj.gridLinesY || [];
  canvas3d.levels = proj.levels || [];

  if (proj.analysisType) byId('analysisType').value = proj.analysisType;
  const comboSelect = byId('loadComboSelect');
  if (comboSelect) comboSelect.value = S.activeLoadCombination;
  const diaphragmToggle = byId('rigidDiaphragmToggle');
  if (diaphragmToggle) diaphragmToggle.checked = S.rigidDiaphragms !== false;
  byId('projectName').textContent = proj.name;
}

function showLandingPage() {
  byId('landingPage').classList.remove('hidden');
  byId('landingPage').classList.add('active');
  byId('setupPage').classList.add('hidden');
  byId('setupPage').classList.remove('active');
  byId('tab-draw').classList.add('hidden');
  byId('tab-draw').classList.remove('active');
  byId('ribbon').style.display = 'none';
  byId('projectBadge').style.display = 'none';
}

function showSetupPage() {
  byId('landingPage').classList.add('hidden');
  byId('landingPage').classList.remove('active');
  byId('setupPage').classList.remove('hidden');
  byId('setupPage').classList.add('active');
  byId('tab-draw').classList.add('hidden');
  byId('tab-draw').classList.remove('active');
  byId('ribbon').style.display = 'none';
  byId('projectBadge').style.display = 'none';
}

function showDrawPage() {
  byId('landingPage').classList.add('hidden');
  byId('landingPage').classList.remove('active');
  byId('setupPage').classList.add('hidden');
  byId('setupPage').classList.remove('active');
  byId('tab-draw').classList.remove('hidden');
  byId('tab-draw').classList.add('active');
  byId('ribbon').style.display = 'block';
  byId('projectBadge').style.display = 'flex';

  byId('projectName').textContent = currentProject.name;
  updatePlanLevelSelect();

  if (!drawPageInitialized) {
    initModals(draw);
    initCanvas({ showSupportModal, showLoadModal, showMemberLoadModal, showSlabModal });
    initRibbon();
    initPopups({ onDrawTab: resizeCanvas });
    initModelTree();
    initViewPresets();
    initAnalysis();
    initExports();
    initChat();
    initSections();
    initLoads();
    initHistory();
    initShortcuts();
    initStatusbar();
    initProjectAutosave();
    drawPageInitialized = true;
    }

  // Wait for the browser to lay out the tab (it was display:none, now visible)
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      measureRibbon();
      resizeCanvas();
      initCameraPosition();
    });
  });
}

function updatePlanLevelSelect() {
  const sel = byId('planLevelSelect');
  if (!sel) return;
  sel.innerHTML = '';
  canvas3d.levels.forEach(level => {
    const opt = document.createElement('option');
    opt.value = level.elevation;
    opt.textContent = `${level.name} (${level.elevation}m)`;
    sel.appendChild(opt);
  });
  sel.value = canvas3d.currentPlanZ;
  sel.onchange = (e) => {
    canvas3d.currentPlanZ = parseFloat(e.target.value);
    triggerRedraw();
  };
}

function initSetupPage() {
  byId('applyGridXBtn').addEventListener('click', () => applyGridAxis('x'));
  byId('applyGridYBtn').addEventListener('click', () => applyGridAxis('y'));

  byId('addLevelBtn').addEventListener('click', addLevelRow);
  byId('setupBackBtn').addEventListener('click', showLandingPage);
  byId('setupDoneBtn').addEventListener('click', finishSetup);

  byId('levelsBody').addEventListener('click', (e) => {
    if (e.target.classList.contains('btn-remove')) {
      const row = e.target.closest('tr');
      if (document.querySelectorAll('#levelsBody tr').length > 1) {
        row.remove();
        updateStoryHeights();
      }
    }
  });

  byId('levelsBody').addEventListener('input', (e) => {
    if (e.target.tagName === 'INPUT') {
      updateStoryHeights();
    }
  });

  document.querySelectorAll('.grid-quick .btn-xs').forEach(btn => {
    btn.addEventListener('click', () => {
      const axis = btn.dataset.axis;
      const spacings = btn.dataset.grid;
      byId(axis === 'x' ? 'gridXSpacings' : 'gridYSpacings').value = spacings;
      applyGridAxis(axis);
    });
  });

  document.querySelectorAll('.levels-quick .btn-xs').forEach(btn => {
    btn.addEventListener('click', () => {
      const count = parseInt(btn.dataset.levels, 10);
      populateLevels(count);
    });
  });

  byId('projectMenuBtn').addEventListener('click', (e) => {
    e.stopPropagation();
    const menu = byId('projectMenu');
    menu.classList.toggle('hidden');
    const rect = e.target.getBoundingClientRect();
    menu.style.top = rect.bottom + 4 + 'px';
    menu.style.right = (window.innerWidth - rect.right) + 'px';
  });

  document.addEventListener('click', () => {
    byId('projectMenu').classList.add('hidden');
  });

  byId('saveProjectBtn').addEventListener('click', async () => {
    if (!currentProject) return;
    await persistCurrentProject({ force: true });
    byId('canvasStatus').textContent = 'Project saved!';
    setTimeout(updateStatus, 2000);
  });

  byId('renameProjectBtn').addEventListener('click', () => {
    if (!currentProject) return;
    const name = prompt('Project name:', currentProject.name);
    if (name) {
      currentProject.name = name;
      byId('projectName').textContent = name;
      persistCurrentProject({ force: true });
    }
  });

  byId('deleteProjectBtn').addEventListener('click', async () => {
    if (!currentProject) return;
    if (confirm(`Delete "${currentProject.name}"? This cannot be undone.`)) {
      await deleteProject(currentProject.id);
      currentProject = null;
      showLandingPage();
      loadProjectGrid();
    }
  });
}

function snapshotCurrentProject() {
  if (!currentProject) return null;
  return {
    ...currentProject,
    nodes: [...S.nodes],
    members: [...S.members],
    slabs: [...S.slabs],
    loads: [...S.loads],
    memberLoads: [...S.memberLoads],
    loadCombinations: [...S.loadCombinations],
    activeLoadCombination: S.activeLoadCombination,
    rigidDiaphragms: S.rigidDiaphragms,
    nextNodeId: S.nextNodeId,
    nextMemberId: S.nextMemberId,
    nextSlabId: S.nextSlabId,
    levels: [...canvas3d.levels],
    gridLinesX: [...canvas3d.gridLinesX],
    gridLinesY: [...canvas3d.gridLinesY],
    analysisType: byId('analysisType').value,
  };
}

async function persistCurrentProject({ force = false } = {}) {
  const snapshot = snapshotCurrentProject();
  if (!snapshot) return;
  const serialized = JSON.stringify(snapshot);
  if (!force && serialized === lastSavedSnapshot) return;
  currentProject = snapshot;
  S.project = currentProject;
  await saveProject(currentProject);
  lastSavedSnapshot = JSON.stringify(currentProject);
}

function initProjectAutosave() {
  if (autosaveTimer) return;
  autosaveTimer = window.setInterval(() => {
    persistCurrentProject().catch(error => console.warn('[StructAgent] Project autosave failed:', error));
  }, 2000);
  window.addEventListener('beforeunload', () => {
    persistCurrentProject({ force: true }).catch(() => {});
  });
}

function applyGridAxis(axis) {
  const inputId = axis === 'x' ? 'gridXSpacings' : 'gridYSpacings';
  const previewId = axis === 'x' ? 'gridXPreview' : 'gridYPreview';
  const raw = byId(inputId).value.trim();
  const spacings = raw.split(',').map(s => parseFloat(s.trim())).filter(n => !isNaN(n) && n > 0);

  if (spacings.length === 0) return;

  const positions = [0];
  spacings.forEach(s => positions.push(positions[positions.length - 1] + s));

  if (axis === 'x') {
    canvas3d.gridLinesX = positions;
  } else {
    canvas3d.gridLinesY = positions;
  }

  const preview = byId(previewId);
  const labels = axis === 'x'
    ? positions.map((_, i) => String(i + 1))
    : positions.map((_, i) => `${i + 1}'`);
  preview.innerHTML = labels.map((l, i) =>
    `<span class="grid-label">${l}: ${positions[i].toFixed(1)}m</span>`
  ).join('');
}

function addLevelRow() {
  const tbody = byId('levelsBody');
  const rows = tbody.querySelectorAll('tr');
  const idx = rows.length;
  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td><input type="text" value="Level ${idx}" class="input-sm"/></td>
    <td><input type="number" value="0" step="0.1" class="input-sm"/></td>
    <td>—</td>
    <td><button class="btn-remove">✕</button></td>
  `;
  tbody.appendChild(tr);
  tr.querySelector('.btn-remove').addEventListener('click', () => {
    if (tbody.querySelectorAll('tr').length > 1) {
      tr.remove();
      updateStoryHeights();
    }
  });
  tr.querySelectorAll('input').forEach(inp => {
    inp.addEventListener('input', updateStoryHeights);
  });
}

function populateLevels(count) {
  const tbody = byId('levelsBody');
  tbody.innerHTML = '';
  const defaultHeight = 3.5;

  const ground = document.createElement('tr');
  ground.innerHTML = `
    <td><input type="text" value="Ground" class="input-sm"/></td>
    <td><input type="number" value="0" step="0.1" class="input-sm"/></td>
    <td>—</td>
    <td><button class="btn-remove">✕</button></td>
  `;
  tbody.appendChild(ground);

  for (let i = 1; i <= count; i++) {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><input type="text" value="Level ${i}" class="input-sm"/></td>
      <td><input type="number" value="${(i * defaultHeight).toFixed(1)}" step="0.1" class="input-sm"/></td>
      <td>${defaultHeight.toFixed(1)}</td>
      <td><button class="btn-remove">✕</button></td>
    `;
    tbody.appendChild(tr);
  }

  tbody.querySelectorAll('.btn-remove').forEach(btn => {
    btn.addEventListener('click', () => {
      const row = btn.closest('tr');
      if (tbody.querySelectorAll('tr').length > 1) {
        row.remove();
        updateStoryHeights();
      }
    });
  });

  tbody.querySelectorAll('input').forEach(inp => {
    inp.addEventListener('input', updateStoryHeights);
  });

  updateStoryHeights();
}

function updateStoryHeights() {
  const rows = byId('levelsBody').querySelectorAll('tr');
  rows.forEach((row, i) => {
    const inputs = row.querySelectorAll('input[type="number"]');
    const heightCell = row.querySelectorAll('td')[2];
    if (i === 0) {
      heightCell.textContent = '—';
    } else {
      const prevInputs = rows[i - 1].querySelectorAll('input[type="number"]');
      const prevElev = parseFloat(prevInputs[0].value) || 0;
      const currElev = parseFloat(inputs[0].value) || 0;
      heightCell.textContent = (currElev - prevElev).toFixed(1);
    }
  });
}

async function finishSetup() {
  const rows = byId('levelsBody').querySelectorAll('tr');
  const levels = [];
  rows.forEach(row => {
    const nameInput = row.querySelectorAll('input[type="text"]')[0];
    const elevInput = row.querySelectorAll('input[type="number"]')[0];
    levels.push({
      name: nameInput.value,
      elevation: parseFloat(elevInput.value) || 0
    });
  });
  levels.sort((a, b) => a.elevation - b.elevation);

  if (canvas3d.gridLinesX.length < 2) {
    canvas3d.gridLinesX = [0, 6, 12, 18];
  }
  if (canvas3d.gridLinesY.length < 2) {
    canvas3d.gridLinesY = [0, 7, 14];
  }

  currentProject.levels = levels;
  currentProject.gridLinesX = canvas3d.gridLinesX;
  currentProject.gridLinesY = canvas3d.gridLinesY;
  canvas3d.levels = levels;

  await saveProject(currentProject);
  lastSavedSnapshot = JSON.stringify(currentProject);
  loadProjectIntoState(currentProject);
  showDrawPage();
}
