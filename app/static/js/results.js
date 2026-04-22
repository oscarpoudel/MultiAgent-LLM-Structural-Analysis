import { exportCsv, exportReport } from './api.js';
import { byId, downloadBlob } from './dom.js';
import { S } from './state.js';

export function renderResults(data) {
  const content = byId('rpContent');
  content.innerHTML = '';
  const results = data.results;

  const metricsDef = [
    ['Solver', results.solver, ''],
    ['Nodes', results.num_nodes, ''],
    ['Members', results.num_members, ''],
    ['Max Displacement', results.max_displacement_mm, 'mm'],
    ['Max Reaction', results.max_reaction_kn, 'kN'],
    ['Max Shear', results.max_shear_kn, 'kN'],
    ['Max Moment', results.max_moment_kn_m, 'kN-m'],
    ['Max Deflection', results.max_deflection_mm, 'mm'],
    ['Deflection OK', formatBoolean(results.deflection_ok), ''],
    ['KL/r', results.slenderness_ratio, ''],
    ['Utilization', results.utilization_ratio, ''],
    ['Capacity OK', formatBoolean(results.capacity_ok), ''],
  ];
  if (results.max_rotation_rad !== undefined) {
    metricsDef.push(['Max Rotation', (results.max_rotation_rad * 1000).toFixed(2), 'mrad']);
  }

  const grid = document.createElement('div');
  grid.className = 'rp-metrics';
  metricsDef.forEach(([label, value, unit]) => {
    if (value === undefined || value === null) return;
    const card = document.createElement('div');
    card.className = 'rp-metric';
    if (value === 'Pass') card.classList.add('pass');
    if (value === 'Fail') card.classList.add('fail');
    card.innerHTML = `<span>${label}</span><strong>${formatMetric(value)} ${unit}</strong>`;
    grid.appendChild(card);
  });
  content.appendChild(grid);

  renderDrawPlot(content, data);
  renderReactions(content, data);
  renderMemberForces(content, data);
  renderDisplacements(content, results);
  renderReport(content, data.report_markdown);
  S._lastExport = data;
}

function formatBoolean(value) {
  if (value === true) return 'Pass';
  if (value === false) return 'Fail';
  return value;
}

function formatMetric(value) {
  if (typeof value !== 'number') return value;
  return Math.abs(value) >= 100 ? value.toFixed(2) : value.toPrecision(4);
}

function renderDrawPlot(content, data) {
  if (!window.Plotly) return;

  const plotData = data.diagrams && data.diagrams.positions && data.diagrams.positions.length
    ? makeBeamPlot(data.diagrams)
    : makeStructurePlot(data);
  if (!plotData) return;

  const section = document.createElement('details');
  section.open = true;
  section.innerHTML = '<summary>Diagram</summary>';
  const plot = document.createElement('div');
  plot.className = 'rp-plot';
  section.appendChild(plot);
  content.appendChild(section);

  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  const bg = isDark ? '#1a2029' : '#fff';
  const textColor = isDark ? '#c8d0da' : '#172026';
  const gridColor = isDark ? '#2d3748' : '#e2e8f0';
  Plotly.newPlot(plot, plotData.traces, {
    xaxis: { title: plotData.xTitle, gridcolor: gridColor, color: textColor },
    yaxis: { title: plotData.yTitle, gridcolor: gridColor, color: textColor },
    yaxis2: plotData.y2Title ? { title: plotData.y2Title, overlaying: 'y', side: 'right', color: textColor } : undefined,
    plot_bgcolor: bg,
    paper_bgcolor: bg,
    margin: { t: 24, r: plotData.y2Title ? 48 : 12, b: 42, l: 48 },
    height: 230,
    font: { family: 'Inter,sans-serif', color: textColor, size: 10 },
    legend: { x: 0, y: 1.2, orientation: 'h' },
  }, { responsive: true, displayModeBar: false });
}

function makeBeamPlot(diagrams) {
  return {
    xTitle: 'Position (m)',
    yTitle: 'Shear (kN)',
    y2Title: 'Moment (kN-m)',
    traces: [
      { x: diagrams.positions, y: diagrams.shear_kn, name: 'Shear', line: { color: '#2563eb' }, fill: 'tozeroy', fillcolor: 'rgba(37,99,235,0.08)' },
      { x: diagrams.positions, y: diagrams.moment_kn_m, name: 'Moment', line: { color: '#dc2626' }, yaxis: 'y2' },
    ],
  };
}

function makeStructurePlot(data) {
  if (data.analysis_type === 'truss') return makeTrussAxialPlot(data.results);
  return makeFrameMemberPlot(data.results);
}

function makeFrameMemberPlot(results) {
  if (!results.member_forces) return null;

  const x = [];
  const shear = [];
  const moment = [];
  const labels = [];
  let station = 0;

  S.members.forEach((member) => {
    const forces = results.member_forces[String(member.id)];
    const length = memberLength(member);
    if (!forces || !Number.isFinite(length) || length <= 0) return;

    x.push(station, station + length, null);
    shear.push(forces.shear_start_kn || 0, -(forces.shear_end_kn || 0), null);
    moment.push(forces.moment_start_kn_m || 0, -(forces.moment_end_kn_m || 0), null);
    labels.push(`M${member.id}`);
    station += length;
  });

  if (!x.length) return null;
  return {
    xTitle: labels.length > 1 ? `Member station (m): ${labels.join(', ')}` : 'Member station (m)',
    yTitle: 'Shear (kN)',
    y2Title: 'Moment (kN-m)',
    traces: [
      { x, y: shear, name: 'Shear', line: { color: '#2563eb' }, fill: 'tozeroy', fillcolor: 'rgba(37,99,235,0.08)' },
      { x, y: moment, name: 'Moment', line: { color: '#dc2626' }, yaxis: 'y2' },
    ],
  };
}

function makeTrussAxialPlot(results) {
  if (!results.member_forces) return null;
  const names = [];
  const values = [];

  S.members.forEach((member) => {
    const forces = results.member_forces[String(member.id)];
    if (!forces) return;
    names.push(`M${member.id}`);
    values.push(forces.axial_kn || 0);
  });

  if (!values.length) return null;
  return {
    xTitle: 'Member',
    yTitle: 'Axial force (kN)',
    traces: [{
      type: 'bar',
      x: names,
      y: values,
      name: 'Axial',
      marker: { color: values.map((value) => (value >= 0 ? '#059669' : '#dc2626')) },
    }],
  };
}

function memberLength(member) {
  const start = S.nodes.find((node) => node.id === member.n1);
  const end = S.nodes.find((node) => node.id === member.n2);
  if (!start || !end) return 0;
  return Math.hypot(end.x - start.x, end.y - start.y);
}

function renderReactions(content, data) {
  const results = data.results;
  if (!results.reactions) return;
  const section = document.createElement('details');
  section.open = true;
  let html = '<summary>Reactions</summary><div class="rp-table"><table><tr><th>Node</th><th>Rx (kN)</th><th>Ry (kN)</th>';
  if (data.analysis_type === 'frame') html += '<th>Mz (kN-m)</th>';
  html += '</tr>';
  Object.entries(results.reactions).forEach(([nodeId, reaction]) => {
    html += `<tr><td>${nodeId}</td><td>${(reaction.rx_kn || 0).toFixed(2)}</td><td>${(reaction.ry_kn || 0).toFixed(2)}</td>`;
    if (data.analysis_type === 'frame') html += `<td>${(reaction.mz_kn_m || 0).toFixed(2)}</td>`;
    html += '</tr>';
  });
  html += '</table></div>';
  section.innerHTML = html;
  content.appendChild(section);
}

function renderMemberForces(content, data) {
  const results = data.results;
  if (!results.member_forces) return;
  const section = document.createElement('details');
  section.open = true;
  let html = '<summary>Member Forces</summary><div class="rp-table"><table>';
  if (data.analysis_type === 'truss') {
    html += '<tr><th>Member</th><th>Axial (kN)</th><th>Type</th><th>Length (m)</th></tr>';
    Object.entries(results.member_forces).forEach(([memberId, memberForce]) => {
      const cls = memberForce.tension_or_compression === 'tension' ? 't-green' : memberForce.tension_or_compression === 'compression' ? 't-red' : '';
      html += `<tr><td>${memberId}</td><td class="${cls}">${(memberForce.axial_kn || 0).toFixed(2)}</td><td>${memberForce.tension_or_compression || ''}</td><td>${(memberForce.length_m || 0).toFixed(2)}</td></tr>`;
    });
  } else {
    html += '<tr><th>Member</th><th>N-start</th><th>V-start</th><th>M-start</th><th>N-end</th><th>V-end</th><th>M-end</th></tr>';
    Object.entries(results.member_forces).forEach(([memberId, memberForce]) => {
      html += `<tr><td>${memberId}</td><td>${(memberForce.axial_start_kn || 0).toFixed(1)}</td><td>${(memberForce.shear_start_kn || 0).toFixed(1)}</td><td>${(memberForce.moment_start_kn_m || 0).toFixed(1)}</td><td>${(memberForce.axial_end_kn || 0).toFixed(1)}</td><td>${(memberForce.shear_end_kn || 0).toFixed(1)}</td><td>${(memberForce.moment_end_kn_m || 0).toFixed(1)}</td></tr>`;
    });
  }
  html += '</table></div>';
  section.innerHTML = html;
  content.appendChild(section);
}

function renderDisplacements(content, results) {
  if (!results.node_displacements) return;
  const section = document.createElement('details');
  let html = '<summary>Nodal Displacements</summary><div class="rp-table"><table><tr><th>Node</th><th>dx (mm)</th><th>dy (mm)</th><th>Total (mm)</th></tr>';
  Object.entries(results.node_displacements).forEach(([nodeId, displacement]) => {
    html += `<tr><td>${nodeId}</td><td>${(displacement.dx_mm || 0).toFixed(4)}</td><td>${(displacement.dy_mm || 0).toFixed(4)}</td><td>${(displacement.total_mm || 0).toFixed(4)}</td></tr>`;
  });
  html += '</table></div>';
  section.innerHTML = html;
  content.appendChild(section);
}

function renderReport(content, reportMarkdown) {
  if (!reportMarkdown) return;
  const section = document.createElement('details');
  section.innerHTML = `<summary>Full Report</summary><pre class="rp-pre">${reportMarkdown}</pre>`;
  content.appendChild(section);
}

export function initExports() {
  byId('exportCsvBtn').addEventListener('click', async () => {
    if (!S._lastExport) return;
    try {
      const response = await exportCsv(S._lastExport.results);
      downloadBlob(await response.blob(), 'results.csv');
    } catch (error) {
      alert('Export failed');
    }
  });

  byId('exportMdBtn').addEventListener('click', async () => {
    if (!S._lastExport) return;
    try {
      const response = await exportReport(S._lastExport.report_markdown);
      downloadBlob(await response.blob(), 'report.md');
    } catch (error) {
      alert('Export failed');
    }
  });
}
