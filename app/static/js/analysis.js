import { analyzeStructure } from './api.js';
import { byId } from './dom.js';
import { fitModelToCanvas } from './canvas3d/index.js';
import { showProp } from './canvas3d/render.js';
import { canvas3d, triggerRedraw } from './canvas3d/scene.js';
import { renderResults } from './results.js';
import { resetModel, S } from './state.js';

export function initAnalysis() {
  byId('runBtn').addEventListener('click', runAnalysis);
  const clearAnalysisBtn = byId('clearAnalysisBtn');
  if (clearAnalysisBtn) clearAnalysisBtn.addEventListener('click', clearAnalysisResults);
  byId('clearBtn').addEventListener('click', () => clearCurrentModel({ confirmFirst: true }));
  // File import lives in the ribbon (Model tab); only the hidden file input
  // change handler is needed here.
  const importJsonFile = byId('importJsonFile');
  if (importJsonFile) importJsonFile.addEventListener('change', importModelJson);
  init3DAnalysisControls();
  window.StructAgentDebug = {
    getState: () => JSON.parse(JSON.stringify(S)),
    drawSimpleBeam,
    drawThreeByThreeThreeStoryFrame,
    clearCurrentModel,
    buildCurrentAnalysisPayload,
  };
}

function init3DAnalysisControls() {
  const comboSelect = byId('loadComboSelect');
  if (comboSelect) {
    comboSelect.innerHTML = S.loadCombinations.map((combo) => (
      `<option value="${combo.name}" ${combo.name === S.activeLoadCombination ? 'selected' : ''}>${combo.name}</option>`
    )).join('');
    comboSelect.addEventListener('change', () => {
      S.activeLoadCombination = comboSelect.value;
    });
  }

  const diaphragmToggle = byId('rigidDiaphragmToggle');
  if (diaphragmToggle) {
    diaphragmToggle.checked = S.rigidDiaphragms !== false;
    diaphragmToggle.addEventListener('change', () => {
      S.rigidDiaphragms = diaphragmToggle.checked;
    });
  }
}

export async function runAnalysis() {
  if (S.nodes.length < 2 || S.members.length < 1) {
    alert('Draw at least 2 nodes and 1 member.');
    return;
  }

  const button = byId('runBtn');
  const statusEl = byId('canvasStatus');
  button.textContent = 'Analyzing...';
  button.disabled = true;
  if (statusEl) statusEl.textContent = 'Running analysis...';

  const payload = buildCurrentAnalysisPayload();
  console.log('[StructAgent] Analysis payload:', JSON.stringify(payload, null, 2));

  try {
    const data = await analyzeStructure(payload);
    console.log('[StructAgent] Analysis response:', data);

    if (data.status === 'ok') {
      S.results = data.results;
      byId('showDeformed').checked = true;
      byId('showForces').checked = true;
      renderResults(data);
      triggerRedraw();
      if (statusEl) statusEl.textContent = `Analysis complete: ${data.analysis_type} (${data.results.solver || 'unknown'})`;
    } else {
      const errMsg = data.message || JSON.stringify(data.errors || data);
      console.error('[StructAgent] Analysis failed:', errMsg);
      alert(`Analysis error: ${errMsg}`);
      if (statusEl) statusEl.textContent = 'Analysis failed — check console for details';
    }
  } catch (error) {
    console.error('[StructAgent] Network error during analysis:', error);
    alert(`Network error: ${error.message}. Is the server running?`);
    if (statusEl) statusEl.textContent = 'Network error — is server running?';
  }

  button.textContent = '\u25B6 Analyze';
  button.disabled = false;
}

export function buildCurrentAnalysisPayload() {
  const analysisType = byId('analysisType').value;
  return { analysis_type: analysisType, model: buildModel(analysisType) };
}

export function buildModel(analysisType) {
  if (analysisType === 'truss') {
    return {
      nodes: S.nodes.map((node) => ({ id: node.id, x: node.x, y: node.y, support: node.support === 'roller' ? 'roller_x' : (node.support || 'free') })),
      members: S.members.map((member) => ({ id: member.id, start_node: member.n1, end_node: member.n2, area_m2: member.A, elastic_modulus_gpa: member.E })),
      loads: S.loads.map((load) => ({ node_id: load.nodeId, fx_kn: load.fx, fy_kn: load.fy })),
    };
  }

  if (analysisType === '3d_frame') {
    // Convert slab area loads to nodal loads
    const slabLoads = [];
    if (S.slabs) {
      S.slabs.forEach((slab) => {
        if (!slab.areaLoad || !slab.nodeIds || slab.nodeIds.length < 3) return;
        const slabNodes = slab.nodeIds.map((id) => S.nodes.find((node) => node.id === id)).filter(Boolean);
        const area = polygonAreaXY(slabNodes);
        if (area <= 0) return;
        const loadPerNode = -Math.abs(slab.areaLoad) * area / slabNodes.length; // +down input maps to global -Z
        slab.nodeIds.forEach((nid) => {
          slabLoads.push({ node_id: nid, case: slab.loadCase || 'D', fx_kn: 0, fy_kn: 0, fz_kn: loadPerNode, mx_kn_m: 0, my_kn_m: 0, mz_kn_m: 0 });
        });
      });
    }
    return {
      nodes: S.nodes.map((node) => ({
        id: node.id,
        x: node.x,
        y: node.y,
        z: node.z || 0,
        support: node.support || 'free',
      })),
      members: S.members.map((member) => ({
        id: member.id,
        start_node: member.n1,
        end_node: member.n2,
        area_m2: member.A,
        iy_m4: member.Iy || member.I || 1e-4,
        iz_m4: member.Iz || member.I || 1e-4,
        j_m4: (member.I || 1e-4) * 0.1,
        elastic_modulus_gpa: member.E,
        shear_modulus_gpa: member.E / (2 * (1 + 0.3)),
        group: member.group || inferMemberGroup(member),
      })),
      nodal_loads: S.loads.map((load) => ({
        node_id: load.nodeId,
        case: load.case || 'D',
        fx_kn: load.fx,
        fy_kn: load.fy,
        fz_kn: load.fz || 0,
        mx_kn_m: 0,
        my_kn_m: 0,
        mz_kn_m: load.moment || 0
      })).concat(slabLoads),
      member_loads: S.memberLoads.map((memberLoad) => ({
        member_id: memberLoad.memberId,
        case: memberLoad.case || 'D',
        wy_kn_per_m: 0,
        wz_kn_per_m: -Math.abs(memberLoad.udl || 0)
      })),
      load_combinations: S.loadCombinations,
      active_load_combination: S.activeLoadCombination,
      rigid_diaphragms: S.rigidDiaphragms !== false,
    };
  }

  return {
    nodes: S.nodes.map((node) => ({ id: node.id, x: node.x, y: node.y, support: node.support === 'roller' ? 'roller' : (node.support || 'free') })),
    members: S.members.map((member) => ({ id: member.id, start_node: member.n1, end_node: member.n2, area_m2: member.A, inertia_m4: member.I, elastic_modulus_gpa: member.E })),
    nodal_loads: S.loads.map((load) => ({ node_id: load.nodeId, fx_kn: load.fx, fy_kn: load.fy, moment_kn_m: load.moment || 0 })),
    member_loads: S.memberLoads.map((memberLoad) => ({ member_id: memberLoad.memberId, udl_kn_per_m: memberLoad.udl })),
  };
}

function polygonAreaXY(nodes) {
  if (!nodes || nodes.length < 3) return 0;
  let twiceArea = 0;
  for (let i = 0; i < nodes.length; i += 1) {
    const current = nodes[i];
    const next = nodes[(i + 1) % nodes.length];
    twiceArea += current.x * next.y - next.x * current.y;
  }
  return Math.abs(twiceArea) / 2;
}

function inferMemberGroup(member) {
  const n1 = S.nodes.find((node) => node.id === member.n1);
  const n2 = S.nodes.find((node) => node.id === member.n2);
  if (!n1 || !n2) return 'member';
  const dx = Math.abs(n2.x - n1.x);
  const dy = Math.abs(n2.y - n1.y);
  const dz = Math.abs((n2.z || 0) - (n1.z || 0));
  if (dz > 0.01 && dx < 0.01 && dy < 0.01) return 'column';
  if (dz < 0.01) return 'beam';
  return 'brace';
}

function sectionForGroup(group) {
  const sections = {
    column: { A: 0.022, I: 3.5e-4, Iy: 3.5e-4, Iz: 3.5e-4, E: 200 },
    beam: { A: 0.018, I: 2.5e-4, Iy: 2.2e-4, Iz: 2.5e-4, E: 200 },
    brace: { A: 0.012, I: 8e-5, Iy: 8e-5, Iz: 8e-5, E: 200 },
    member: { A: 0.01, I: 1e-4, Iy: 1e-4, Iz: 1e-4, E: 200 },
  };
  return sections[group] || sections.member;
}

export function applyMemberGroupSections() {
  S.members.forEach((member) => {
    member.group = member.group || inferMemberGroup(member);
    Object.assign(member, sectionForGroup(member.group));
  });
  showProp();
  triggerRedraw();
}

export function clearCurrentModel({ confirmFirst = false } = {}) {
  if (confirmFirst && !confirm('Clear the entire model?')) return false;
  resetModel();
  byId('showDeformed').checked = false;
  byId('showForces').checked = false;
  byId('rpContent').innerHTML = '<p class="placeholder">Draw a structure and run analysis.</p>';
  showProp();
  triggerRedraw();
  byId('analysisType').value = 'frame';
  return true;
}

export function clearAnalysisResults() {
  S.results = null;
  S._lastExport = null;
  const showDeformed = byId('showDeformed');
  const showForces = byId('showForces');
  if (showDeformed) showDeformed.checked = false;
  if (showForces) showForces.checked = false;
  byId('rpContent').innerHTML = '<p class="placeholder">Analysis cleared. Run analysis to see results.</p>';
  const statusEl = byId('canvasStatus');
  if (statusEl) statusEl.textContent = 'Analysis cleared. Model geometry kept.';
  triggerRedraw();
}

export function drawSimpleBeam(args = {}) {
  const span = Number(args.span_m) > 0 ? Number(args.span_m) : 2;
  const pointLoads = Array.isArray(args.point_loads) ? args.point_loads : [];
  const internalLoadPositions = [...new Set(pointLoads
    .map((load) => Number(load.position_m))
    .filter((position) => position > 0 && position < span)
    .map((position) => Number(position.toFixed(6))))].sort((a, b) => a - b);

  resetModel();
  const stations = [0, ...internalLoadPositions, span];
  stations.forEach((x, index) => {
    S.nodes.push({
      id: index + 1,
      x,
      y: 1,
      support: index === 0 ? 'pin' : index === stations.length - 1 ? 'roller' : 'free',
    });
  });

  for (let index = 0; index < S.nodes.length - 1; index += 1) {
    S.members.push({ id: index + 1, n1: S.nodes[index].id, n2: S.nodes[index + 1].id, A: 0.01, I: 1e-4, E: 200 });
  }

  pointLoads.forEach((load) => {
    const magnitude = Math.abs(Number(load.magnitude_kn) || 0);
    const position = Number(load.position_m);
    if (!magnitude || !Number.isFinite(position)) return;
    const node = S.nodes.find((item) => Math.abs(item.x - position) < 1e-6);
    if (node) S.loads.push({ nodeId: node.id, fx: 0, fy: -magnitude, moment: 0 });
  });

  const udl = Number(args.udl_kn_per_m) || 0;
  if (udl) {
    S.memberLoads = S.members.map((member) => ({ memberId: member.id, udl }));
  }

  S.nextNodeId = S.nodes.length + 1;
  S.nextMemberId = S.members.length + 1;
  const selectedType = byId('analysisType').value;
  if (selectedType === '3d_frame') {
    byId('analysisType').value = '3d_frame';
  } else {
    byId('analysisType').value = 'frame';
  }
  byId('showDeformed').checked = false;
  byId('showForces').checked = false;
  byId('rpContent').innerHTML = `
    <div class="rp-metrics">
      <div class="rp-metric"><span>Tool</span><strong>draw_simple_beam</strong></div>
      <div class="rp-metric"><span>Nodes</span><strong>${S.nodes.length}</strong></div>
      <div class="rp-metric"><span>Members</span><strong>${S.members.length}</strong></div>
      <div class="rp-metric"><span>Loads</span><strong>${S.loads.length + S.memberLoads.length}</strong></div>
    </div>
    <p class="placeholder">Beam drawn. Run analysis to see results.</p>`;
  showProp();
  fitModelToCanvas();
  console.info('[StructAgent] draw_simple_beam executed', {
    args,
    nodes: S.nodes,
    members: S.members,
    loads: S.loads,
    memberLoads: S.memberLoads,
    zoom: S.zoom,
    pan: S.pan,
  });
}

export function drawThreeByThreeThreeStoryFrame(args = {}) {
  resetModel();
  const bayX = Number(args.bay_x_m) > 0 ? Number(args.bay_x_m) : 6;
  const bayY = Number(args.bay_y_m) > 0 ? Number(args.bay_y_m) : 6;
  const storyHeight = Number(args.story_height_m) > 0 ? Number(args.story_height_m) : 3.5;
  const gravityKn = Number(args.gravity_node_kn) || 35;
  const lateralKn = Number(args.lateral_node_kn) || 8;
  const xLines = [0, bayX, bayX * 2, bayX * 3];
  const yLines = [0, bayY, bayY * 2, bayY * 3];
  const levels = [0, storyHeight, storyHeight * 2, storyHeight * 3];

  canvas3d.gridLinesX = xLines;
  canvas3d.gridLinesY = yLines;
  canvas3d.levels = levels.map((elevation, index) => ({
    name: index === 0 ? 'Ground' : `Level ${index}`,
    elevation,
  }));
  canvas3d.currentPlanZ = levels[0];

  const nodeIdByKey = new Map();
  levels.forEach((z, levelIndex) => {
    xLines.forEach((x, ix) => {
      yLines.forEach((y, iy) => {
        const id = S.nextNodeId++;
        nodeIdByKey.set(`${ix},${iy},${levelIndex}`, id);
        S.nodes.push({ id, x, y, z, support: levelIndex === 0 ? 'fixed' : 'free' });
      });
    });
  });

  function addMember(n1, n2, props = {}) {
    const group = props.group || inferMemberGroup({ n1, n2 });
    const section = { ...sectionForGroup(group), ...props };
    S.members.push({
      id: S.nextMemberId++,
      n1,
      n2,
      group,
      A: section.A,
      I: section.I,
      Iy: section.Iy,
      Iz: section.Iz,
      E: section.E,
    });
  }

  for (let levelIndex = 0; levelIndex < levels.length - 1; levelIndex += 1) {
    xLines.forEach((_, ix) => {
      yLines.forEach((__, iy) => {
        addMember(nodeIdByKey.get(`${ix},${iy},${levelIndex}`), nodeIdByKey.get(`${ix},${iy},${levelIndex + 1}`), {
          group: 'column',
        });
      });
    });
  }

  for (let levelIndex = 1; levelIndex < levels.length; levelIndex += 1) {
    yLines.forEach((_, iy) => {
      for (let ix = 0; ix < xLines.length - 1; ix += 1) {
        addMember(nodeIdByKey.get(`${ix},${iy},${levelIndex}`), nodeIdByKey.get(`${ix + 1},${iy},${levelIndex}`), { group: 'beam' });
      }
    });
    xLines.forEach((_, ix) => {
      for (let iy = 0; iy < yLines.length - 1; iy += 1) {
        addMember(nodeIdByKey.get(`${ix},${iy},${levelIndex}`), nodeIdByKey.get(`${ix},${iy + 1},${levelIndex}`), { group: 'beam' });
      }
    });
  }

  levels.slice(1).forEach((_, floorOffset) => {
    const levelIndex = floorOffset + 1;
    xLines.forEach((__, ix) => {
      yLines.forEach((___, iy) => {
        const isEdge = ix === 0 || iy === 0 || ix === xLines.length - 1 || iy === yLines.length - 1;
        const tributaryFactor = isEdge ? 0.5 : 1;
        const nodeId = nodeIdByKey.get(`${ix},${iy},${levelIndex}`);
        S.loads.push({ nodeId, case: 'D', fx: 0, fy: 0, fz: -gravityKn * tributaryFactor, moment: 0 });
        if (levelIndex === levels.length - 1) {
          S.loads.push({ nodeId, case: 'EX', fx: lateralKn, fy: 0, fz: 0, moment: 0 });
        }
      });
    });
  });

  byId('analysisType').value = '3d_frame';
  S.rigidDiaphragms = true;
  S.activeLoadCombination = '1.2D + 1.0EX + 0.5L';
  const comboSelect = byId('loadComboSelect');
  if (comboSelect) comboSelect.value = S.activeLoadCombination;
  const diaphragmToggle = byId('rigidDiaphragmToggle');
  if (diaphragmToggle) diaphragmToggle.checked = true;
  byId('showDeformed').checked = false;
  byId('showForces').checked = false;
  byId('rpContent').innerHTML = `
    <div class="rp-metrics">
      <div class="rp-metric"><span>Template</span><strong>3x3 3-story</strong></div>
      <div class="rp-metric"><span>Nodes</span><strong>${S.nodes.length}</strong></div>
      <div class="rp-metric"><span>Members</span><strong>${S.members.length}</strong></div>
      <div class="rp-metric"><span>Nodal Loads</span><strong>${S.loads.length}</strong></div>
    </div>
    <p class="placeholder">Template created with fixed bases, rigid frame members, gravity loads, and top-story lateral loads. Run analysis to compare global displacements, base reactions, and member forces.</p>`;
  showProp();
  fitModelToCanvas();
  triggerRedraw();
}

export function exportModelJson() {
  const modelData = {
    version: 1,
    nodes: S.nodes,
    members: S.members,
    slabs: S.slabs,
    loads: S.loads,
    memberLoads: S.memberLoads,
    loadCombinations: S.loadCombinations,
    activeLoadCombination: S.activeLoadCombination,
    rigidDiaphragms: S.rigidDiaphragms,
    analysisType: byId('analysisType').value,
    levels: {
      numLevels: byId('numLevels')?.value || 4,
      levelHeight: byId('levelHeight')?.value || 3.0
    }
  };
  try {
    const blob = new Blob([JSON.stringify(modelData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `struct_model_${Date.now()}.json`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
    console.info('[StructAgent] Model exported successfully');
  } catch (err) {
    console.error('[StructAgent] Export failed:', err);
    alert('Export failed: ' + err.message);
  }
}

export function importModelJson(e) {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = (event) => {
    try {
      const modelData = JSON.parse(event.target.result);
      if (!modelData.nodes || !Array.isArray(modelData.nodes)) {
        throw new Error('Invalid model format: missing nodes array');
      }
      clearCurrentModel({ confirmFirst: false });
      S.nodes = modelData.nodes || [];
      S.members = modelData.members || [];
      S.slabs = modelData.slabs || [];
      S.loads = modelData.loads || [];
      S.memberLoads = modelData.memberLoads || [];
      S.loadCombinations = modelData.loadCombinations || S.loadCombinations;
      S.activeLoadCombination = modelData.activeLoadCombination || S.activeLoadCombination;
      S.rigidDiaphragms = modelData.rigidDiaphragms !== undefined ? modelData.rigidDiaphragms : S.rigidDiaphragms;
      if (modelData.analysisType) byId('analysisType').value = modelData.analysisType;
      const comboSelect = byId('loadComboSelect');
      if (comboSelect) comboSelect.value = S.activeLoadCombination;
      const diaphragmToggle = byId('rigidDiaphragmToggle');
      if (diaphragmToggle) diaphragmToggle.checked = S.rigidDiaphragms !== false;
      if (modelData.levels) {
        const numEl = byId('numLevels');
        const hEl = byId('levelHeight');
        if (numEl) numEl.value = modelData.levels.numLevels;
        if (hEl) hEl.value = modelData.levels.levelHeight;
      }
      S.nextNodeId = S.nodes.length ? Math.max(...S.nodes.map(n => n.id)) + 1 : 1;
      S.nextMemberId = S.members.length ? Math.max(...S.members.map(m => m.id)) + 1 : 1;
      S.nextSlabId = S.slabs.length ? Math.max(...S.slabs.map(s => s.id)) + 1 : 1;
      fitModelToCanvas();
      showProp();
      triggerRedraw();
      console.info('[StructAgent] Model imported successfully');
    } catch (err) {
      console.error('[StructAgent] Import failed:', err);
      alert('Import failed: ' + err.message);
    }
    e.target.value = '';
  };
  reader.readAsText(file);
}
