import { byId, $$ } from './dom.js';
import { buildModel } from './analysis.js';
import { S } from './state.js';
import { triggerRedraw } from './canvas3d/scene.js';
import {
  calculateWindLoads,
  calculateSeismicLoads,
  calculateResponseSpectrum,
  calculateSnowLoads,
  analyzeStructureWithLoads,
  pdeltaAmplify,
  runSensitivityStudy,
} from './api.js';

export function initLoads() {
  $$('.loads-subtab').forEach((tab) => {
    tab.addEventListener('click', () => switchLoadTab(tab.dataset.loadtab));
  });
  byId('windForm').addEventListener('submit', (e) => {
    e.preventDefault();
    runWind();
  });
  byId('seismicForm').addEventListener('submit', (e) => {
    e.preventDefault();
    runSeismic();
  });
  byId('snowForm').addEventListener('submit', (e) => {
    e.preventDefault();
    runSnow();
  });
  byId('spectrumForm').addEventListener('submit', (e) => {
    e.preventDefault();
    runSpectrum();
  });
  byId('pdeltaForm').addEventListener('submit', (e) => {
    e.preventDefault();
    runPdelta();
  });
  byId('sensitivityForm').addEventListener('submit', (e) => {
    e.preventDefault();
    runSensitivity();
  });
}

function switchLoadTab(name) {
  $$('.loads-subtab').forEach((t) => t.classList.toggle('active', t.dataset.loadtab === name));
  $$('.loads-form').forEach((f) => f.classList.toggle('hidden', f.dataset.loadform !== name));
}

function num(id) {
  const v = parseFloat(byId(id).value);
  return Number.isFinite(v) ? v : 0;
}
function str(id) {
  return byId(id).value;
}

async function runWind() {
  const inputs = {
    basic_wind_speed_ms: num('windSpeed'),
    exposure: str('windExposure'),
    height_m: num('windHeight'),
    length_m: num('windLength'),
    width_m: num('windWidth'),
    story_height_m: num('windStory'),
    internal_pressure: str('windInternal'),
  };
  const data = await calculateWindLoads(inputs);
  if (data.status !== 'ok') return renderError(data);
  renderWind(data.results);
}

async function runSeismic() {
  const inputs = {
    spectral_accel_sd: num('seisSa02'),
    spectral_accel_1s: num('seisSa1'),
    site_class: str('seisSite'),
    risk_category: str('seisRisk'),
    building_weight_kn: num('seisWeight'),
    height_m: num('seisHeight'),
    structural_system: str('seisSystem'),
  };
  const data = await calculateSeismicLoads(inputs);
  if (data.status !== 'ok') return renderError(data);
  renderSeismic(data.results);
}

async function runSnow() {
  const inputs = {
    ground_snow_load_kpa: num('snowPg'),
    exposure: str('snowExposure'),
    thermal: str('snowThermal'),
    risk_category: str('snowRisk'),
    roof_slope_deg: num('snowSlope'),
    drift: str('snowDrift') === 'true',
  };
  const data = await calculateSnowLoads(inputs);
  if (data.status !== 'ok') return renderError(data);
  renderSnow(data.results);
}

async function runSpectrum() {
  const el = byId('loadsResults');
  const model = buildModel('3d_frame');
  if (!model.nodes || model.nodes.length < 2) {
    el.innerHTML = '<div class="loads-error"><strong>No 3D model</strong><p>Draw a multi-level 3D frame first.</p></div>';
    return;
  }
  el.innerHTML = '<p class="placeholder">Solving modal response spectrum…</p>';
  const data = await calculateResponseSpectrum({
    model,
    building_weight_kn: num('rsWeight'),
    sds: num('rsSds'),
    sd1: num('rsSd1'),
    direction: str('rsDirection'),
    num_modes: Math.max(1, Math.round(num('rsModes'))),
    long_period_s: num('rsTl'),
  });
  if (data.status !== 'ok') return renderError(data);
  S.results = {
    ...(S.results || {}),
    story_response: { story_drifts: data.results.story_drifts || [] },
  };
  const showDrift = byId('showDrift');
  if (showDrift) showDrift.checked = true;
  triggerRedraw();
  renderSpectrum(data.results);
}

function renderSpectrum(r) {
  const modeRows = (r.modes || []).map((m) =>
    `<tr><td>${m.mode}</td><td>${m.period_s}</td><td>${m.spectral_acceleration_g}</td><td>${(100 * m.effective_mass_ratio).toFixed(1)}%</td><td>${m.base_shear_kn}</td></tr>`
  ).join('');
  const driftRows = (r.story_drifts || []).map((d) =>
    `<tr><td>${d.story}</td><td>${d.from_m} → ${d.to_m}</td><td>${d.drift_mm}</td><td>${(100 * d.drift_ratio_delta_over_h).toFixed(3)}%</td></tr>`
  ).join('');
  byId('loadsResults').innerHTML = `
    <h3>Response Spectrum — ${r.code_reference}</h3>
    <div class="loads-props">
      ${kv('Base shear', r.base_shear_kn, 'kN')}
      ${kv('Mass captured', (100 * r.cumulative_mass_ratio).toFixed(1), '%')}
      ${kv('Direction', r.direction.toUpperCase())}
      ${kv('Idealization', r.idealization)}
    </div>
    <h4>Modes</h4>
    <table class="loads-table"><thead><tr><th>Mode</th><th>T (s)</th><th>Sa (g)</th><th>Mass</th><th>V (kN)</th></tr></thead><tbody>${modeRows}</tbody></table>
    <h4>SRSS Story Drifts</h4>
    <table class="loads-table"><thead><tr><th>Story</th><th>Elevation (m)</th><th>Drift (mm)</th><th>Δ/h</th></tr></thead><tbody>${driftRows}</tbody></table>
    ${warnings(r.warnings)}`;
}

function lastStoryDrifts() {
  const results = S.results || {};
  const story = results.story_response || {};
  return Array.isArray(story.story_drifts) ? story.story_drifts : [];
}

async function runPdelta() {
  const drifts = lastStoryDrifts();
  const el = byId('loadsResults');
  if (!drifts.length) {
    el.innerHTML = `<div class="loads-error"><strong>No drifts available</strong><p>Run a 3D analysis with story forces first (use the Wind/Seismic "Apply to 3D Model" button), then come back to P-delta.</p></div>`;
    return;
  }
  const payload = {
    story_drifts: drifts,
    base_shear_kn: num('pdV'),
    height_m: num('pdH'),
    gravity_load_kn: num('pdW'),
  };
  el.innerHTML = '<p class="placeholder">Computing P-delta amplification…</p>';
  const data = await pdeltaAmplify(payload);
  if (data.status !== 'ok') return renderError(data);
  renderPdelta(data.results);
}

function renderPdelta(r) {
  const el = byId('loadsResults');
  const rows = (r.story_drifts || []).map((d) =>
    `<tr><td>${d.from_m} → ${d.to_m}</td><td>${d.drift1_mm}</td><td>${d.drift2_mm ?? '—'}</td><td>${d.amplification ?? '—'}</td></tr>`
  ).join('');
  const stable = r.stable;
  el.innerHTML = `
    <h3>P-delta Second-Order — ${r.code_reference}</h3>
    <div class="loads-props">
      ${kv('Stability θ', r.theta)}
      ${kv('Amplification', r.amplification_factor ?? '—')}
      ${kv('Stable', stable ? 'Yes' : 'No')}
      ${kv('Max drift 1st', r.max_drift1_mm, 'mm')}
      ${kv('Max drift 2nd', r.max_drift2_mm ?? '—', 'mm')}
    </div>
    <h4>Story Drifts (1st → 2nd order)</h4>
    <table class="loads-table"><thead><tr><th>Story</th><th>1st (mm)</th><th>2nd (mm)</th><th>Factor</th></tr></thead><tbody>${rows}</tbody></table>
    ${warnings(r.warnings)}`;
}

async function runSensitivity() {
  const parameters = [];
  if (byId('snPW').checked) parameters.push('w');
  if (byId('snPL').checked) parameters.push('L');
  if (byId('snPE').checked) parameters.push('E');
  if (byId('snPI').checked) parameters.push('I');
  if (byId('snPS').checked) parameters.push('S');
  const inputs = {
    load_kn_m: num('snW'),
    span_m: num('snL'),
    modulus_gpa: num('snE'),
    inertia_m4: num('snI'),
    section_modulus_m3: num('snS'),
    load_min_kn_m: num('snWmin'),
    load_max_kn_m: num('snWmax'),
    span_min_m: num('snLmin'),
    span_max_m: num('snLmax'),
    modulus_min_gpa: num('snEmin'),
    modulus_max_gpa: num('snEmax'),
    inertia_min_m4: num('snImin'),
    inertia_max_m4: num('snImax'),
    section_min_m3: num('snSmin'),
    section_max_m3: num('snSmax'),
    parameters,
  };
  const el = byId('loadsResults');
  if (!parameters.length) {
    el.innerHTML = '<div class="loads-error"><strong>No parameters</strong><p>Select at least one parameter to sweep.</p></div>';
    return;
  }
  el.innerHTML = '<p class="placeholder">Running sensitivity study…</p>';
  const data = await runSensitivityStudy(inputs);
  if (data.status !== 'ok') return renderError(data);
  renderSensitivity(data.results);
}

function renderSensitivity(r) {
  const el = byId('loadsResults');
  const base = r.base_response;
  const rankRows = (r.ranking || []).map((x, i) =>
    `<tr><td>${i + 1}</td><td>${x.parameter}</td><td>${x.max_abs_sensitivity}</td></tr>`
  ).join('');
  let studyHtml = '';
  for (const [field, d] of Object.entries(r.study)) {
    const s = d.sensitivity;
    const sweepRows = d.sweep.map((row) =>
      `<tr><td>${row.param_value}</td><td>${row.moment_kn_m}</td><td>${(row.deflection_m * 1000).toFixed(3)}</td><td>${row.stress_kpa}</td></tr>`
    ).join('');
    studyHtml += `
      <h4>${d.label} (base ${d.base}, range ${d.min} → ${d.max})</h4>
      <div class="loads-props">
        ${kv('∂M/∂p', s.moment_kn_m ?? '—')}
        ${kv('∂δ/∂p', s.deflection_m ?? '—')}
        ${kv('∂σ/∂p', s.stress_kpa ?? '—')}
      </div>
      <table class="loads-table"><thead><tr><th>${d.label}</th><th>M (kN-m)</th><th>δ (mm)</th><th>σ (kPa)</th></tr></thead><tbody>${sweepRows}</tbody></table>`;
  }
  el.innerHTML = `
    <h3>Parametric Sensitivity — ${r.code_reference}</h3>
    <div class="loads-props">
      ${kv('Base M', base.moment_kn_m, 'kN-m')}
      ${kv('Base δ', (base.deflection_m * 1000).toFixed(3), 'mm')}
      ${kv('Base σ', base.stress_kpa, 'kPa')}
    </div>
    <h4>Parameter Ranking (by max |sensitivity|)</h4>
    <table class="loads-table"><thead><tr><th>#</th><th>Parameter</th><th>Max |S|</th></tr></thead><tbody>${rankRows}</tbody></table>
    ${studyHtml}
    ${warnings(r.warnings)}`;
}

function renderError(data) {
  const el = byId('loadsResults');
  el.innerHTML = `<div class="loads-error"><strong>Error</strong><p>${data.message || 'Request failed.'}</p></div>`;
}

function kv(label, value, unit = '') {
  return `<div><span>${label}</span><strong>${value}${unit ? ` ${unit}` : ''}</strong></div>`;
}

function storyTable(storyForces) {
  if (!storyForces || !storyForces.length) return '';
  const rows = storyForces.map((s) => `<tr><td>${s.story ?? '—'}</td><td>${s.z_m}</td><td>${s.force_kn}</td></tr>`).join('');
  return `<h4>Story Forces</h4><table class="loads-table"><thead><tr><th>Story</th><th>z (m)</th><th>Force (kN)</th></tr></thead><tbody>${rows}</tbody></table>`;
}

function warnings(w) {
  if (!w || !w.length) return '';
  return `<div class="loads-warn">${w.map((x) => `<li>${x}</li>`).join('')}</div>`;
}

function renderWind(r) {
  const el = byId('loadsResults');
  const vp = Object.entries(r.velocity_pressures_kpa || {})
    .map(([k, v]) => kv(k, v, 'kPa'))
    .join('');
  el.innerHTML = `
    <h3>Wind Loads — ${r.code_reference}</h3>
    <div class="loads-props">
      ${kv('Base shear X', r.base_shear_x_kn, 'kN')}
      ${kv('Base shear Y', r.base_shear_y_kn, 'kN')}
      ${kv('Roof uplift', r.roof_uplift_kn, 'kN')}
      ${kv('Cp windward', r.factors.cp_windward)}
      ${kv('Cp leeward', r.factors.cp_leeward)}
      ${kv('Cp roof', r.factors.cp_roof)}
      ${kv('Kd', r.factors.directionality_Kd)}
      ${kv('Ki', r.factors.internal_pressure_ki)}
    </div>
    <h4>Velocity Pressure qz</h4>
    <div class="loads-props">${vp}</div>
    ${storyTable(r.story_forces)}
    ${warnings(r.warnings)}
    <button class="btn-primary" id="applyWindModelBtn">Apply to 3D Model &amp; Analyze</button>`;
  byId('applyWindModelBtn').addEventListener('click', () => applyToModel('wind', r));
}

function renderSeismic(r) {
  const el = byId('loadsResults');
  const sc = r.site_coefficients;
  const dp = r.design_params;
  el.innerHTML = `
    <h3>Seismic Base Shear — ${r.code_reference}</h3>
    <div class="loads-props">
      ${kv('Base shear V', r.base_shear_kn, 'kN')}
      ${kv('SDS', sc.sds)}
      ${kv('SD1', sc.sd1)}
      ${kv('Ts', sc.ts, 's')}
      ${kv('Cs', dp.cs)}
      ${kv('Period T', dp.period_s, 's')}
      ${kv('R', dp.r)}
      ${kv('Cd', dp.cd)}
      ${kv('Ie', dp.ie)}
    </div>
    ${storyTable(r.story_forces)}
    ${warnings(r.warnings)}
    <button class="btn-primary" id="applySeismicModelBtn">Apply to 3D Model &amp; Analyze</button>`;
  byId('applySeismicModelBtn').addEventListener('click', () => applyToModel('seismic', r));
}

function renderSnow(r) {
  const el = byId('loadsResults');
  const f = r.factors;
  el.innerHTML = `
    <h3>Snow Loads — ${r.code_reference}</h3>
    <div class="loads-props">
      ${kv('Flat roof ps', r.flat_roof_ps_kpa, 'kPa')}
      ${kv('Sloped roof ps', r.sloped_roof_ps_kpa, 'kPa')}
      ${kv('Balanced', r.balanced_snow_kpa, 'kPa')}
      ${kv('Drift', r.drift_load_kpa, 'kPa')}
      ${kv('Total design', r.total_design_snow_kpa, 'kPa')}
      ${kv('Ce', f.ce)}
      ${kv('Ct', f.ct)}
      ${kv('Is', f.is)}
      ${kv('Cs', f.cs)}
    </div>
    ${warnings(r.warnings)}`;
}

async function applyToModel(loadType, loadResults) {
  const el = byId('loadsResults');
  const model = buildModel('3d_frame');
  if (!model.nodes || model.nodes.length < 2) {
    el.innerHTML = `<div class="loads-error"><strong>No 3D model</strong><p>Draw a 3D frame on the Draw tab first.</p></div>`;
    return;
  }
  const direction = 'x';
  const distribution = 'equal';
  const payload = {
    load_type: loadType,
    [loadType]: currentInputsFor(loadType),
    model,
    direction,
    distribution,
  };
  el.innerHTML = '<p class="placeholder">Running 3D analysis with applied story forces…</p>';
  const data = await analyzeStructureWithLoads(payload);
  if (data.status !== 'ok') return renderError(data);
  renderModelAnalysis(data);
}

function currentInputsFor(loadType) {
  if (loadType === 'wind') {
    return {
      basic_wind_speed_ms: num('windSpeed'),
      exposure: str('windExposure'),
      height_m: num('windHeight'),
      length_m: num('windLength'),
      width_m: num('windWidth'),
      story_height_m: num('windStory'),
      internal_pressure: str('windInternal'),
    };
  }
  return {
    spectral_accel_sd: num('seisSa02'),
    spectral_accel_1s: num('seisSa1'),
    site_class: str('seisSite'),
    risk_category: str('seisRisk'),
    building_weight_kn: num('seisWeight'),
    height_m: num('seisHeight'),
    structural_system: str('seisSystem'),
  };
}

function renderModelAnalysis(data) {
  const el = byId('loadsResults');
  S.results = data.results;
  const showDrift = byId('showDrift');
  if (showDrift) showDrift.checked = true;
  triggerRedraw();
  const drifts = data.results.story_response?.story_drifts || [];
  const driftRows = drifts.map((d) =>
    `<tr><td>${d.from_m} → ${d.to_m}</td><td>${d.height_m}</td><td>${d.drift_mm?.toFixed(2)}</td><td>${d.drift_ratio ? (1 / d.drift_ratio).toFixed(4) : '—'}</td></tr>`
  ).join('');
  const appliedRows = (data.applied || []).map((a) =>
    `<tr><td>${a.z_m}</td><td>${a.force_kn}</td><td>${a.num_nodes}</td><td>${a.force_per_node_kn}</td></tr>`
  ).join('');
  el.innerHTML = `
    <h3>3D Analysis — ${data.load_type} story forces applied</h3>
    <div class="loads-props">
      ${kv('Max translation', data.results.max_translation_mm?.toFixed(2), 'mm')}
      ${kv('Solver', data.results.solver)}
    </div>
    <h4>Story Drifts</h4>
    <table class="loads-table"><thead><tr><th>Story</th><th>Height (m)</th><th>Drift (mm)</th><th>Drift ratio (Δ/h)</th></tr></thead><tbody>${driftRows}</tbody></table>
    <h4>Applied Story Forces</h4>
    <table class="loads-table"><thead><tr><th>z (m)</th><th>Force (kN)</th><th>Nodes</th><th>Per node (kN)</th></tr></thead><tbody>${appliedRows}</tbody></table>
    ${warnings(data.warnings)}`;
}
