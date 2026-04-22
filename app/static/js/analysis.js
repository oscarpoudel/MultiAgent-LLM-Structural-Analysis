import { analyzeStructure } from './api.js';
import { byId } from './dom.js';
import { draw, fitModelToCanvas, showProp } from './canvas.js';
import { renderResults } from './results.js';
import { resetModel, S } from './state.js';

export function initAnalysis() {
  byId('runBtn').addEventListener('click', runAnalysis);
  byId('clearBtn').addEventListener('click', () => clearCurrentModel({ confirmFirst: true }));
  window.StructAgentDebug = {
    getState: () => JSON.parse(JSON.stringify(S)),
    drawSimpleBeam,
    clearCurrentModel,
    buildCurrentAnalysisPayload,
  };
}

async function runAnalysis() {
  if (S.nodes.length < 2 || S.members.length < 1) {
    alert('Draw at least 2 nodes and 1 member.');
    return;
  }

  const button = byId('runBtn');
  button.textContent = 'Analyzing...';
  button.disabled = true;

  try {
    const data = await analyzeStructure(buildCurrentAnalysisPayload());
    if (data.status === 'ok') {
      S.results = data.results;
      byId('showDeformed').checked = true;
      byId('showForces').checked = true;
      renderResults(data);
      draw();
    } else {
      alert(`Analysis error: ${data.message || JSON.stringify(data.errors || data)}`);
    }
  } catch (error) {
    alert(`Network error: ${error.message}`);
  }

  button.textContent = '\u25B6 Analyze';
  button.disabled = false;
}

export function buildCurrentAnalysisPayload() {
  const analysisType = byId('analysisType').value;
  return { analysis_type: analysisType, model: buildModel(analysisType) };
}

function buildModel(analysisType) {
  if (analysisType === 'truss') {
    return {
      nodes: S.nodes.map((node) => ({ id: node.id, x: node.x, y: node.y, support: node.support === 'roller' ? 'roller_x' : node.support })),
      members: S.members.map((member) => ({ id: member.id, start_node: member.n1, end_node: member.n2, area_m2: member.A, elastic_modulus_gpa: member.E })),
      loads: S.loads.map((load) => ({ node_id: load.nodeId, fx_kn: load.fx, fy_kn: load.fy })),
    };
  }

  return {
    nodes: S.nodes.map((node) => ({ id: node.id, x: node.x, y: node.y, support: node.support === 'roller' ? 'roller' : node.support })),
    members: S.members.map((member) => ({ id: member.id, start_node: member.n1, end_node: member.n2, area_m2: member.A, inertia_m4: member.I, elastic_modulus_gpa: member.E })),
    nodal_loads: S.loads.map((load) => ({ node_id: load.nodeId, fx_kn: load.fx, fy_kn: load.fy, moment_kn_m: load.moment || 0 })),
    member_loads: S.memberLoads.map((memberLoad) => ({ member_id: memberLoad.memberId, udl_kn_per_m: memberLoad.udl })),
  };
}

export function clearCurrentModel({ confirmFirst = false } = {}) {
  if (confirmFirst && !confirm('Clear the entire model?')) return false;
  resetModel();
  byId('showDeformed').checked = false;
  byId('showForces').checked = false;
  byId('rpContent').innerHTML = '<p class="placeholder">Draw a structure and run analysis.</p>';
  showProp();
  draw();
  return true;
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
  byId('analysisType').value = 'frame';
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
