import { byId, downloadBlob } from './dom.js';
import { exportPdf } from './api.js';
import { S } from './state.js';

export function renderResults(data) {
  const content = byId('rpContent');
  content.innerHTML = '';
  const results = data.results;

  const metricsDef = [
    ['Solver', results.solver, ''],
    ['Load Combo', results.load_combination, ''],
    ['Diaphragm', results.rigid_diaphragms ? 'Rigid' : 'None', ''],
    ['Nodes', results.num_nodes, ''],
    ['Members', results.num_members, ''],
    ['Max Displacement', results.max_displacement_mm, 'mm'],
    ['Max Translation', results.max_translation_mm, 'mm'],
    ['Max Reaction', results.max_reaction_kn, 'kN'],
    ['Base Fx', results.base_reactions?.Fx_kn, 'kN'],
    ['Base Fy', results.base_reactions?.Fy_kn, 'kN'],
    ['Base Fz', results.base_reactions?.Fz_kn, 'kN'],
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
  renderCombinationSummary(content, results);
  renderReactions(content, data);
  renderMemberForces(content, data);
  renderStoryResponse(content, results);
  renderDisplacements(content, results);
  renderReport(content, data.report_markdown);
  S._lastExport = data;
}

function renderCombinationSummary(content, results) {
  if (!results.combination_results) return;
  const section = document.createElement('details');
  section.open = true;
  let html = '<summary>Load Combination Summary</summary><div class="rp-table"><table><tr><th>Combination</th><th>Max Translation (mm)</th><th>Base Fx (kN)</th><th>Base Fy (kN)</th><th>Base Fz (kN)</th></tr>';
  Object.entries(results.combination_results).forEach(([name, combo]) => {
    const active = name === results.load_combination ? ' <strong>(active)</strong>' : '';
    html += `<tr><td>${name}${active}</td><td>${(combo.max_translation_mm || 0).toFixed(4)}</td><td>${(combo.base_reactions?.Fx_kn || 0).toFixed(2)}</td><td>${(combo.base_reactions?.Fy_kn || 0).toFixed(2)}</td><td>${(combo.base_reactions?.Fz_kn || 0).toFixed(2)}</td></tr>`;
  });
  html += '</table></div>';
  section.innerHTML = html;
  content.appendChild(section);
}

function renderStoryResponse(content, results) {
  if (!results.story_response || !results.story_response.levels?.length) return;
  const section = document.createElement('details');
  section.open = true;
  let html = '<summary>Story Response</summary><div class="rp-table"><table><tr><th>Level Elev. (m)</th><th>Max Ux (mm)</th><th>Max Uy (mm)</th><th>Max Lateral (mm)</th></tr>';
  results.story_response.levels.forEach((level) => {
    html += `<tr><td>${(level.elevation_m || 0).toFixed(2)}</td><td>${(level.max_ux_mm || 0).toFixed(4)}</td><td>${(level.max_uy_mm || 0).toFixed(4)}</td><td>${(level.max_lateral_mm || 0).toFixed(4)}</td></tr>`;
  });
  html += '</table></div>';

  if (results.story_response.story_drifts?.length) {
    html += '<div class="rp-table"><table><tr><th>Story</th><th>Height (m)</th><th>Drift (mm)</th><th>Drift Ratio</th></tr>';
    results.story_response.story_drifts.forEach((story) => {
      const ratio = story.drift_ratio ? `1/${story.drift_ratio.toFixed(0)}` : '-';
      html += `<tr><td>${(story.from_m || 0).toFixed(2)}-${(story.to_m || 0).toFixed(2)}</td><td>${(story.height_m || 0).toFixed(2)}</td><td>${(story.drift_mm || 0).toFixed(4)}</td><td>${ratio}</td></tr>`;
    });
    html += '</table></div>';
  }

  section.innerHTML = html;
  content.appendChild(section);
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
  
  const layout = {
    plot_bgcolor: bg,
    paper_bgcolor: bg,
    margin: { t: 24, r: plotData.y2Title ? 48 : 12, b: 42, l: 48 },
    height: plotData.is3D ? 400 : 230,
    font: { family: 'Inter,sans-serif', color: textColor, size: 10 },
    legend: { x: 0, y: 1.2, orientation: 'h' },
  };

  if (plotData.is3D) {
    layout.scene = {
      xaxis: { title: plotData.xTitle, gridcolor: gridColor, color: textColor, backgroundcolor: bg },
      yaxis: { title: plotData.yTitle, gridcolor: gridColor, color: textColor, backgroundcolor: bg },
      zaxis: { title: 'Z (m)', gridcolor: gridColor, color: textColor, backgroundcolor: bg }
    };
    layout.margin = { t: 0, r: 0, b: 0, l: 0 };
  } else {
    layout.xaxis = { title: plotData.xTitle, gridcolor: gridColor, color: textColor };
    layout.yaxis = { title: plotData.yTitle, gridcolor: gridColor, color: textColor };
    if (plotData.y2Title) {
      layout.yaxis2 = { title: plotData.y2Title, overlaying: 'y', side: 'right', color: textColor };
    }
  }

  Plotly.newPlot(plot, plotData.traces, layout, { responsive: true, displayModeBar: false });
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
  if (data.analysis_type === '3d_frame') return make3DFramePlot(data.results);
  return makeFrameMemberPlot(data.results);
}

function make3DFramePlot(results) {
  if (!results.geometry) return null;

  const nodes = results.geometry.nodes;
  const members = results.geometry.members;

  const x = [];
  const y = [];
  const z = [];

  // Build line segments for 3D plot
  members.forEach(m => {
    const start = nodes.find(n => n.id === m.start_node);
    const end = nodes.find(n => n.id === m.end_node);
    if (start && end) {
      x.push(start.x, end.x, null);
      y.push(start.y, end.y, null);
      z.push(start.z, end.z, null);
    }
  });

  return {
    xTitle: 'X (m)',
    yTitle: 'Y (m)',
    is3D: true,
    traces: [
      {
        type: 'scatter3d',
        mode: 'lines+markers',
        x: x,
        y: y,
        z: z,
        line: { color: '#2563eb', width: 4 },
        marker: { size: 4, color: '#dc2626' },
        name: 'Structure'
      }
    ],
  };
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
  let html = '<summary>Reactions</summary><div class="rp-table"><table>';
  
  if (data.analysis_type === '3d_frame') {
    html += '<tr><th>Node</th><th>Fx (kN)</th><th>Fy (kN)</th><th>Fz (kN)</th><th>Mx (kNm)</th><th>My (kNm)</th><th>Mz (kNm)</th></tr>';
    Object.entries(results.reactions).forEach(([nodeId, r]) => {
      html += `<tr><td>${nodeId}</td><td>${(r.Fx_kn || 0).toFixed(2)}</td><td>${(r.Fy_kn || 0).toFixed(2)}</td><td>${(r.Fz_kn || 0).toFixed(2)}</td><td>${(r.Mx_kn_m || 0).toFixed(2)}</td><td>${(r.My_kn_m || 0).toFixed(2)}</td><td>${(r.Mz_kn_m || 0).toFixed(2)}</td></tr>`;
    });
  } else {
    html += '<tr><th>Node</th><th>Rx (kN)</th><th>Ry (kN)</th>';
    if (data.analysis_type === 'frame') html += '<th>Mz (kN-m)</th>';
    html += '</tr>';
    Object.entries(results.reactions).forEach(([nodeId, reaction]) => {
      html += `<tr><td>${nodeId}</td><td>${(reaction.rx_kn || 0).toFixed(2)}</td><td>${(reaction.ry_kn || 0).toFixed(2)}</td>`;
      if (data.analysis_type === 'frame') html += `<td>${(reaction.mz_kn_m || 0).toFixed(2)}</td>`;
      html += '</tr>';
    });
  }
  
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
  
  if (data.analysis_type === '3d_frame') {
    if (results.member_force_summary) {
      html += '<tr><th>Member</th><th>Group</th><th>|P|max</th><th>|Vy|max</th><th>|Vz|max</th><th>|My|max</th><th>|Mz|max</th><th>|T|max</th></tr>';
      Object.entries(results.member_force_summary).forEach(([memberId, f]) => {
        html += `<tr><td>${memberId}</td><td>${f.group || ''}</td><td>${(f.max_abs_axial_kn || 0).toFixed(1)}</td><td>${(f.max_abs_shear_y_kn || 0).toFixed(1)}</td><td>${(f.max_abs_shear_z_kn || 0).toFixed(1)}</td><td>${(f.max_abs_moment_y_kn_m || 0).toFixed(1)}</td><td>${(f.max_abs_moment_z_kn_m || 0).toFixed(1)}</td><td>${(f.max_abs_torsion_kn_m || 0).toFixed(1)}</td></tr>`;
      });
      html += '</table></div><div class="rp-table"><table>';
    }
    html += '<tr><th>Member</th><th>P_i</th><th>Vy_i</th><th>Vz_i</th><th>T_i</th><th>My_i</th><th>Mz_i</th><th>P_j</th><th>Vy_j</th><th>Vz_j</th><th>T_j</th><th>My_j</th><th>Mz_j</th></tr>';
    Object.entries(results.member_forces).forEach(([memberId, f]) => {
      // f is array of 12 elements
      html += `<tr><td>${memberId}</td>`;
      f.forEach(val => {
        html += `<td>${(val || 0).toFixed(1)}</td>`;
      });
      html += `</tr>`;
    });
  } else if (data.analysis_type === 'truss') {
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
  // Try 3d_frame 'displacements' first, then default 'node_displacements'
  if (results.displacements) {
    const section = document.createElement('details');
    let html = '<summary>Nodal Displacements (3D)</summary><div class="rp-table"><table><tr><th>Node</th><th>dx (mm)</th><th>dy (mm)</th><th>dz (mm)</th><th>rx (rad)</th><th>ry (rad)</th><th>rz (rad)</th></tr>';
    Object.entries(results.displacements).forEach(([nodeId, d]) => {
      html += `<tr><td>${nodeId}</td><td>${(d[0] || 0).toFixed(4)}</td><td>${(d[1] || 0).toFixed(4)}</td><td>${(d[2] || 0).toFixed(4)}</td><td>${(d[3] || 0).toFixed(4)}</td><td>${(d[4] || 0).toFixed(4)}</td><td>${(d[5] || 0).toFixed(4)}</td></tr>`;
    });
    html += '</table></div>';
    section.innerHTML = html;
    content.appendChild(section);
  } else if (results.node_displacements) {
    const section = document.createElement('details');
    let html = '<summary>Nodal Displacements</summary><div class="rp-table"><table><tr><th>Node</th><th>dx (mm)</th><th>dy (mm)</th><th>Total (mm)</th></tr>';
    Object.entries(results.node_displacements).forEach(([nodeId, displacement]) => {
      html += `<tr><td>${nodeId}</td><td>${(displacement.dx_mm || 0).toFixed(4)}</td><td>${(displacement.dy_mm || 0).toFixed(4)}</td><td>${(displacement.total_mm || 0).toFixed(4)}</td></tr>`;
    });
    html += '</table></div>';
    section.innerHTML = html;
    content.appendChild(section);
  }
}

function renderReport(content, reportMarkdown) {
  if (!reportMarkdown) return;
  const section = document.createElement('details');
  section.innerHTML = `<summary>Full Report</summary><pre class="rp-pre">${reportMarkdown}</pre>`;
  content.appendChild(section);
}

const EXPORT_UNITS = {
  max_translation_mm: 'mm',
  max_displacement_mm: 'mm',
  elevation_m: 'm',
  height_m: 'm',
  drift_mm: 'mm',
  avg_ux_mm: 'mm',
  avg_uy_mm: 'mm',
  max_ux_mm: 'mm',
  max_uy_mm: 'mm',
  max_lateral_mm: 'mm',
  Fx_kn: 'kN',
  Fy_kn: 'kN',
  Fz_kn: 'kN',
  Mx_kn_m: 'kN-m',
  My_kn_m: 'kN-m',
  Mz_kn_m: 'kN-m',
  max_abs_axial_kn: 'kN',
  max_abs_shear_y_kn: 'kN',
  max_abs_shear_z_kn: 'kN',
  max_abs_torsion_kn_m: 'kN-m',
  max_abs_moment_y_kn_m: 'kN-m',
  max_abs_moment_z_kn_m: 'kN-m',
};

function exportValueUnit(path) {
  const field = path.split('.').pop().replace(/\[\d+\]/g, '');
  return EXPORT_UNITS[field] || '';
}

function flattenRows(value, path = 'results', rows = []) {
  if (Array.isArray(value)) {
    value.forEach((item, index) => flattenRows(item, `${path}[${index}]`, rows));
    return rows;
  }
  if (value && typeof value === 'object') {
    Object.entries(value).forEach(([key, item]) => flattenRows(item, `${path}.${key}`, rows));
    return rows;
  }
  rows.push(['results', path.replace(/^results\.?/, ''), value ?? '', exportValueUnit(path)]);
  return rows;
}

function csvCell(value) {
  const text = String(value ?? '');
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function buildCsvExport(analysis) {
  const rows = [['Section', 'Item', 'Value', 'Unit'], ...flattenRows(analysis.results || {})];
  return rows.map((row) => row.map(csvCell).join(',')).join('\n');
}

function fmt(value, digits = 3) {
  if (value === undefined || value === null) return 'N/A';
  if (typeof value === 'number') return value.toFixed(digits);
  return String(value);
}

function build3DReport(analysis) {
  const results = analysis.results || {};
  const lines = [
    '# Preliminary 3D Frame Analysis Report',
    '',
    '## Request',
    'Canvas-drawn 3D frame structure',
    '',
    '## Analysis Type',
    '3D Space Frame Analysis',
    '',
    '## Assumptions',
  ];
  const assumptions = analysis.assumptions?.length ? analysis.assumptions : ['Preliminary elastic 3D analysis.', 'Rigid beam-column connections.'];
  lines.push(...assumptions.map((item) => `- ${item}`));
  const factors = results.load_factors || {};
  const factorText = Object.entries(factors).map(([key, value]) => `${key}=${value}`).join(', ') || 'N/A';
  lines.push(
    '',
    '## Model Summary',
    `- Solver: ${results.solver || 'N/A'}`,
    `- Number of nodes: ${fmt(results.num_nodes, 0)}`,
    `- Number of members: ${fmt(results.num_members, 0)}`,
    `- Active load combination: ${results.load_combination || 'N/A'}`,
    `- Load factors: ${factorText}`,
    `- Rigid diaphragms: ${results.rigid_diaphragms ? 'Yes' : 'No'}`,
    `- Maximum translation: ${fmt(results.max_translation_mm, 4)} mm`,
    '',
  );

  if (results.combination_results) {
    lines.push('## Load Combination Summary', '| Combination | Max translation (mm) | Base Fx (kN) | Base Fy (kN) | Base Fz (kN) |', '|---|---:|---:|---:|---:|');
    Object.entries(results.combination_results).forEach(([name, combo]) => {
      const base = combo.base_reactions || {};
      lines.push(`| ${name} | ${fmt(combo.max_translation_mm, 4)} | ${fmt(base.Fx_kn)} | ${fmt(base.Fy_kn)} | ${fmt(base.Fz_kn)} |`);
    });
    lines.push('');
  }

  if (results.base_reactions) {
    const base = results.base_reactions;
    lines.push('## Base Reactions', `- Fx: ${fmt(base.Fx_kn)} kN`, `- Fy: ${fmt(base.Fy_kn)} kN`, `- Fz: ${fmt(base.Fz_kn)} kN`, `- Mx: ${fmt(base.Mx_kn_m)} kN-m`, `- My: ${fmt(base.My_kn_m)} kN-m`, `- Mz: ${fmt(base.Mz_kn_m)} kN-m`, '');
  }

  const story = results.story_response || {};
  if (story.levels?.length) {
    lines.push('## Story Displacements', '| Elevation (m) | Avg Ux (mm) | Avg Uy (mm) | Max Ux (mm) | Max Uy (mm) | Max lateral (mm) |', '|---:|---:|---:|---:|---:|---:|');
    story.levels.forEach((level) => lines.push(`| ${fmt(level.elevation_m, 2)} | ${fmt(level.avg_ux_mm, 4)} | ${fmt(level.avg_uy_mm, 4)} | ${fmt(level.max_ux_mm, 4)} | ${fmt(level.max_uy_mm, 4)} | ${fmt(level.max_lateral_mm, 4)} |`));
    lines.push('');
  }
  if (story.story_drifts?.length) {
    lines.push('## Story Drift Summary', '| Story | Height (m) | Drift (mm) | Drift ratio |', '|---|---:|---:|---:|');
    story.story_drifts.forEach((drift) => {
      const ratio = typeof drift.drift_ratio === 'number' ? `1/${drift.drift_ratio.toFixed(0)}` : 'N/A';
      lines.push(`| ${fmt(drift.from_m, 2)}-${fmt(drift.to_m, 2)} | ${fmt(drift.height_m, 2)} | ${fmt(drift.drift_mm, 4)} | ${ratio} |`);
    });
    lines.push('');
  }

  if (results.member_force_summary) {
    lines.push('## Member Force Envelopes', '| Member | Group | |P|max (kN) | |Vy|max (kN) | |Vz|max (kN) | |My|max (kN-m) | |Mz|max (kN-m) | |T|max (kN-m) |', '|---:|---|---:|---:|---:|---:|---:|---:|');
    Object.entries(results.member_force_summary).forEach(([memberId, force]) => {
      lines.push(`| ${memberId} | ${force.group || ''} | ${fmt(force.max_abs_axial_kn)} | ${fmt(force.max_abs_shear_y_kn)} | ${fmt(force.max_abs_shear_z_kn)} | ${fmt(force.max_abs_moment_y_kn_m)} | ${fmt(force.max_abs_moment_z_kn_m)} | ${fmt(force.max_abs_torsion_kn_m)} |`);
    });
    lines.push('');
  }

  if (results.reactions) {
    lines.push('## Support Reactions');
    Object.entries(results.reactions).forEach(([nodeId, reaction]) => {
      lines.push(`- Node ${nodeId}: Fx=${fmt(reaction.Fx_kn)} kN, Fy=${fmt(reaction.Fy_kn)} kN, Fz=${fmt(reaction.Fz_kn)} kN, Mx=${fmt(reaction.Mx_kn_m)} kN-m, My=${fmt(reaction.My_kn_m)} kN-m, Mz=${fmt(reaction.Mz_kn_m)} kN-m`);
    });
    lines.push('');
  }

  if (results.displacements) {
    lines.push('## Nodal Displacements', '| Node | Ux (mm) | Uy (mm) | Uz (mm) | Rx (rad) | Ry (rad) | Rz (rad) |', '|---:|---:|---:|---:|---:|---:|---:|');
    Object.entries(results.displacements).forEach(([nodeId, displacement]) => {
      const values = [...displacement, 0, 0, 0, 0, 0, 0];
      lines.push(`| ${nodeId} | ${fmt(values[0], 4)} | ${fmt(values[1], 4)} | ${fmt(values[2], 4)} | ${fmt(values[3], 6)} | ${fmt(values[4], 6)} | ${fmt(values[5], 6)} |`);
    });
    lines.push('');
  }

  const warnings = analysis.warnings?.length ? analysis.warnings : ['None'];
  lines.push('## Warnings', ...warnings.map((item) => `- ${item}`), '', '## Engineering Note', 'This is a preliminary linear elastic 3D frame analysis. A licensed engineer should review load cases, diaphragm assumptions, member releases, second-order effects, code combinations, member design, connection details, and model calibration against ETABS or another validated solver.');
  return lines.join('\n');
}

function buildReportExport(analysis) {
  const stale = !analysis.report_markdown || /Beam Analysis|Span: None/.test(analysis.report_markdown);
  const report = analysis.analysis_type === '3d_frame' && stale ? build3DReport(analysis) : analysis.report_markdown;
  return `${(report || '').trim()}\n\n## Detailed Analysis Data\n\n\`\`\`json\n${JSON.stringify(analysis.results || {}, null, 2)}\n\`\`\`\n`;
}

export function initExports() {
  byId('exportCsvBtn').addEventListener('click', async () => {
    if (!S._lastExport) return;
    try {
      downloadBlob(new Blob([buildCsvExport(S._lastExport)], { type: 'text/csv' }), 'results.csv');
    } catch (error) {
      alert('Export failed');
    }
  });

  byId('exportMdBtn').addEventListener('click', async () => {
    if (!S._lastExport) return;
    try {
      downloadBlob(new Blob([buildReportExport(S._lastExport)], { type: 'text/markdown' }), 'report.md');
    } catch (error) {
      alert('Export failed');
    }
  });

  byId('exportPdfBtn').addEventListener('click', async () => {
    if (!S._lastExport) return;
    try {
      const response = await exportPdf(buildReportExport(S._lastExport));
      if (!response.ok) throw new Error('PDF export failed');
      downloadBlob(await response.blob(), 'analysis_report.pdf');
    } catch (error) {
      alert('PDF export failed');
    }
  });
}
