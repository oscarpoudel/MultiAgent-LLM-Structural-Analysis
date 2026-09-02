import { byId, $$ } from './dom.js';
import { buildModel } from './analysis.js';
import {
  calculateWindLoads,
  calculateSeismicLoads,
  calculateSnowLoads,
  analyzeStructureWithLoads,
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
