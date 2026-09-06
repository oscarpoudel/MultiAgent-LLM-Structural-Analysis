import { checkFatigue, designConcreteBeam, designConcreteColumn, designPile, designSpreadFooting, designTimberBeam, estimateCost, fetchSection, searchSections, selectBeam, selectColumn } from './api.js';
import { byId, $$ } from './dom.js';

export function initSections() {
  byId('secSearch').addEventListener('click', runSectionSearch);

  $$('.sec-subtab[data-sectab]').forEach((tab) => {
    tab.addEventListener('click', () => switchSectionTab(tab.dataset.sectab));
  });
  $$('.sec-subtab[data-selkind]').forEach((btn) => {
    btn.addEventListener('click', () => switchSelectionKind(btn.dataset.selkind));
  });
  $$('.sec-subtab[data-cek]').forEach((btn) => {
    btn.addEventListener('click', () => switchConcreteKind(btn.dataset.cek));
  });
  $$('.sec-subtab[data-fnd]').forEach((btn) => {
    btn.addEventListener('click', () => switchFoundationKind(btn.dataset.fnd));
  });
  byId('beamSelForm').addEventListener('submit', (e) => {
    e.preventDefault();
    runBeamSelection();
  });
  byId('columnSelForm').addEventListener('submit', (e) => {
    e.preventDefault();
    runColumnSelection();
  });
  byId('concreteBeamForm').addEventListener('submit', (e) => {
    e.preventDefault();
    runConcreteBeam();
  });
  byId('concreteColumnForm').addEventListener('submit', (e) => {
    e.preventDefault();
    runConcreteColumn();
  });
  byId('costForm').addEventListener('submit', (e) => {
    e.preventDefault();
    runCost();
  });
  byId('timberForm').addEventListener('submit', (e) => {
    e.preventDefault();
    runTimber();
  });
  byId('footingForm').addEventListener('submit', (e) => {
    e.preventDefault();
    runFooting();
  });
  byId('pileForm').addEventListener('submit', (e) => {
    e.preventDefault();
    runPile();
  });
  byId('fatigueForm').addEventListener('submit', (e) => {
    e.preventDefault();
    runFatigue();
  });
}

function switchSectionTab(name) {
  $$('.sec-subtab[data-sectab]').forEach((t) => t.classList.toggle('active', t.dataset.sectab === name));
  $$('[data-secrow]').forEach((row) => row.classList.toggle('hidden', row.dataset.secrow !== name));
  const showSteel = name === 'select';
  const showConcrete = name === 'concrete';
  const showTimber = name === 'timber';
  const showFoundation = name === 'foundation';
  const showFatigue = name === 'fatigue';
  const showCost = name === 'cost';
  byId('secSelectForms').classList.toggle('hidden', !showSteel);
  byId('secConcreteForms').classList.toggle('hidden', !showConcrete);
  byId('secTimberForms').classList.toggle('hidden', !showTimber);
  byId('secFoundationForms').classList.toggle('hidden', !showFoundation);
  byId('secFatigueForms').classList.toggle('hidden', !showFatigue);
  byId('secCostForms').classList.toggle('hidden', !showCost);
  byId('secResults').closest('.sec-body').classList.toggle('with-forms', showSteel || showConcrete || showTimber || showFoundation || showFatigue || showCost);
}

function switchSelectionKind(kind) {
  $$('.sec-subtab[data-selkind]').forEach((b) => b.classList.toggle('active', b.dataset.selkind === kind));
  $$('.sec-sel-form[data-selform]').forEach((f) => f.classList.toggle('hidden', f.dataset.selform !== kind));
}

function switchConcreteKind(kind) {
  $$('.sec-subtab[data-cek]').forEach((b) => b.classList.toggle('active', b.dataset.cek === kind));
  $$('.sec-sel-form[data-ccform]').forEach((f) => f.classList.toggle('hidden', f.dataset.ccform !== kind));
}

function switchFoundationKind(kind) {
  $$('.sec-subtab[data-fnd]').forEach((b) => b.classList.toggle('active', b.dataset.fnd === kind));
  $$('.sec-sel-form[data-fndform]').forEach((f) => f.classList.toggle('hidden', f.dataset.fndform !== kind));
}

function num(id) {
  const v = parseFloat(byId(id).value);
  return Number.isFinite(v) ? v : 0;
}

async function runSectionSearch() {
  const type = byId('secType').value;
  const query = byId('secQ').value.trim();
  const content = byId('secResults');

  try {
    const data = await searchSections(type, query);
    content.innerHTML = '';
    if (data.sections && Array.isArray(data.sections)) {
      if (typeof data.sections[0] === 'string') {
        renderSectionNames(content, data.sections);
      } else {
        data.sections.forEach((section) => content.appendChild(makeSectionCard(section)));
      }
    }
  } catch (error) {
    content.innerHTML = '<p class="placeholder">Search failed.</p>';
  }
}

async function runBeamSelection() {
  const inputs = {
    moment_kn_m: num('beamMu'),
    shear_kn: num('beamVu'),
    unbraced_length_m: num('beamLb'),
    cb: num('beamCb'),
    fy_mpa: num('beamFy'),
  };
  const content = byId('secResults');
  content.innerHTML = '<p class="placeholder">Selecting beam section…</p>';
  const data = await selectBeam(inputs);
  if (data.status !== 'ok') return renderSelectionError(content, data);
  renderSelection(content, data.results, 'beam');
}

async function runColumnSelection() {
  const inputs = {
    axial_load_kn: num('colPu'),
    kl_m: num('colKl'),
    fy_mpa: num('colFy'),
  };
  const content = byId('secResults');
  content.innerHTML = '<p class="placeholder">Selecting column section…</p>';
  const data = await selectColumn(inputs);
  if (data.status !== 'ok') return renderSelectionError(content, data);
  renderSelection(content, data.results, 'column');
}

function renderSelectionError(content, data) {
  content.innerHTML = `<div class="loads-error"><strong>Error</strong><p>${data.message || 'Design failed.'}</p></div>`;
}

async function runConcreteBeam() {
  const inputs = {
    moment_kn_m: num('cbMu'),
    shear_kn: num('cbVu'),
    width_mm: num('cbB'),
    depth_mm: num('cbH'),
    concrete_fck_mpa: num('cbFc'),
    steel_fy_mpa: num('cbFy'),
  };
  const content = byId('secResults');
  content.innerHTML = '<p class="placeholder">Designing concrete beam…</p>';
  const data = await designConcreteBeam(inputs);
  if (data.status !== 'ok') return renderSelectionError(content, data);
  renderConcrete(content, data.results, 'beam');
}

async function runConcreteColumn() {
  const inputs = {
    axial_load_kn: num('ccPu'),
    diameter_mm: num('ccD'),
    concrete_fck_mpa: num('ccFc'),
    steel_fy_mpa: num('ccFy'),
    tied: byId('ccTied').value === 'true',
    kl_r: num('ccKlr'),
  };
  const content = byId('secResults');
  content.innerHTML = '<p class="placeholder">Designing concrete column…</p>';
  const data = await designConcreteColumn(inputs);
  if (data.status !== 'ok') return renderSelectionError(content, data);
  renderConcrete(content, data.results, 'column');
}

async function runCost() {
  const members = [];
  const sec1 = byId('costSec1').value.trim();
  const len1 = num('costLen1');
  if (sec1 && len1 > 0) members.push({ section: sec1, length_m: len1 });
  const sec2 = byId('costSec2').value.trim();
  const len2 = num('costLen2');
  if (sec2 && len2 > 0) members.push({ section: sec2, length_m: len2 });

  const content = byId('secResults');
  if (!members.length) {
    content.innerHTML = '<div class="loads-error"><strong>No members</strong><p>Enter at least one section and length.</p></div>';
    return;
  }
  content.innerHTML = '<p class="placeholder">Estimating cost…</p>';
  const data = await estimateCost({
    members,
    price_per_kg: num('costPrice'),
    currency: byId('costCurrency').value.trim() || 'USD',
    fab_factor: num('costFab'),
    erect_factor: num('costErect'),
  });
  if (data.status !== 'ok') return renderSelectionError(content, data);
  renderCost(content, data.results);
}

function renderCost(content, r) {
  const rows = (r.groups || []).map((g) =>
    `<tr><td>${g.section}</td><td>${g.length_m}</td><td>${g.weight_kg_per_m}</td><td>${g.weight_kg}</td><td>${g.weight_t}</td></tr>`
  ).join('');
  const cur = r.currency;
  let html = `<h3>Steel Cost Estimate — ${r.method}</h3>
    <div class="sec-props">
      ${selRow('Total weight', r.total_weight_t, 't')}
      ${selRow('Material cost', r.material_cost, cur)}
      ${selRow('Total cost', r.total_cost, cur)}
      ${selRow('Cost / ton', r.cost_per_ton, cur)}
      ${selRow('Unit price', r.price_per_kg, cur + '/kg')}
    </div>
    <h4 style="margin:16px 0 6px;font-size:0.85rem;color:var(--text2);">Takeoff</h4>
    <table class="loads-table"><thead><tr><th>Section</th><th>Length (m)</th><th>kg/m</th><th>Weight (kg)</th><th>Weight (t)</th></tr></thead><tbody>${rows}</tbody></table>`;
  if (r.warnings && r.warnings.length) {
    html += `<div class="loads-warn"><ul>${r.warnings.map((w) => `<li>${w}</li>`).join('')}</ul></div>`;
  }
  content.innerHTML = html;
}

async function runTimber() {
  const inputs = {
    species: byId('tbSpecies').value,
    width_mm: num('tbB'),
    depth_mm: num('tbD'),
    moment_kn_m: num('tbM'),
    shear_kn: num('tbV'),
    span_m: num('tbL'),
    unbraced_length_m: num('tbLe'),
    duration: byId('tbDuration').value,
    moisture_pct: num('tbMc'),
    temperature_c: num('tbTemp'),
    live_load_fraction: num('tbLlf'),
  };
  const content = byId('secResults');
  content.innerHTML = '<p class="placeholder">Designing timber beam…</p>';
  const data = await designTimberBeam(inputs);
  if (data.status !== 'ok') return renderSelectionError(content, data);
  renderTimber(content, data.results);
}

function renderTimber(content, r) {
  const f = r.flexure;
  const s = r.shear;
  const d = r.deflection;
  const adj = r.adjustment_factors;
  const pass = r.pass;
  const badge = pass ? '<span style="color:var(--ok,#3fb950)">PASS</span>' : '<span style="color:var(--danger,#f85149)">FAIL</span>';
  let html = `<h3>Timber Beam — ${r.code_reference} ${badge}</h3>
    <div class="sec-props">
      ${selRow('Species', r.inputs.species)}
      ${selRow('Section', `${r.inputs.width_mm} × ${r.inputs.depth_mm}`, 'mm')}
      ${selRow('Governs', r.governs)}
      ${selRow('Max util', r.max_util)}
      ${selRow('Fb adj', r.adjusted_values_mpa.Fb_adj, 'MPa')}
      ${selRow('Fv adj', r.adjusted_values_mpa.Fv_adj, 'MPa')}
      ${selRow('CD/CM/Ct/CF/CL', `${adj.CD}/${adj.CM}/${adj.Ct}/${adj.CF}/${adj.CL}`)}
    </div>
    <h4 style="margin:16px 0 6px;font-size:0.85rem;color:var(--text2);">Checks</h4>
    <table class="loads-table"><thead><tr><th>Check</th><th>Demand</th><th>Capacity</th><th>Util</th><th>OK</th></tr></thead><tbody>
      <tr><td>Flexure</td><td>${f.f_b_mpa} MPa</td><td>${f.Fb_adj_mpa} MPa</td><td>${f.util}</td><td>${f.ok ? '✓' : '✗'}</td></tr>
      <tr><td>Shear</td><td>${s.f_v_mpa} MPa</td><td>${s.Fv_adj_mpa} MPa</td><td>${s.util}</td><td>${s.ok ? '✓' : '✗'}</td></tr>
      <tr><td>Defl (total)</td><td>${d.delta_total_mm} mm</td><td>${d.limit_total_mm} mm</td><td>—</td><td>${d.total_ok ? '✓' : '✗'}</td></tr>
      <tr><td>Defl (live)</td><td>${d.delta_live_mm} mm</td><td>${d.limit_live_mm} mm</td><td>—</td><td>${d.live_ok ? '✓' : '✗'}</td></tr>
    </tbody></table>`;
  if (r.warnings && r.warnings.length) {
    html += `<div class="loads-warn"><ul>${r.warnings.map((w) => `<li>${w}</li>`).join('')}</ul></div>`;
  }
  content.innerHTML = html;
}

async function runFooting() {
  const inputs = {
    axial_load_kn: num('ftP'),
    allowable_bearing_kpa: num('ftQ'),
    column_width_mm: num('ftCw'),
    column_depth_mm: num('ftCd'),
    footing_depth_mm: num('ftD'),
    concrete_fck_mpa: num('ftFc'),
    steel_fy_mpa: num('ftFy'),
    bar_dia_mm: num('ftBar'),
  };
  const content = byId('secResults');
  content.innerHTML = '<p class="placeholder">Designing footing…</p>';
  const data = await designSpreadFooting(inputs);
  if (data.status !== 'ok') return renderSelectionError(content, data);
  renderFooting(content, data.results);
}

function renderFooting(content, r) {
  const f = r.footing;
  const b = r.bearing;
  const ow = r.one_way_shear;
  const pw = r.punching_shear;
  const fl = r.flexure;
  const bars = r.suggested_bars;
  const badge = r.pass ? '<span style="color:var(--ok,#3fb950)">PASS</span>' : '<span style="color:var(--danger,#f85149)">FAIL</span>';
  let html = `<h3>Spread Footing — ${r.code_reference} ${badge}</h3>
    <div class="sec-props">
      ${selRow('Size', `${f.width_mm} × ${f.width_mm}`, 'mm')}
      ${selRow('Area', f.area_m2, 'm2')}
      ${selRow('Eff. depth', f.effective_depth_mm, 'mm')}
      ${selRow('Bearing', b.pressure_kpa, 'kPa')}
      ${selRow('Allowable', b.allowable_kpa, 'kPa')}
      ${selRow('As (each dir)', fl.design_as_mm2, 'mm2')}
      ${selRow('Bars', `${bars.count_each_direction} × ${bars.bar_dia_mm} mm`)}
      ${bars.clear_spacing_mm != null ? selRow('Clear spacing', bars.clear_spacing_mm, 'mm') : ''}
    </div>
    <h4 style="margin:16px 0 6px;font-size:0.85rem;color:var(--text2);">Checks</h4>
    <table class="loads-table"><thead><tr><th>Check</th><th>Demand</th><th>Capacity</th><th>Util</th><th>OK</th></tr></thead><tbody>
      <tr><td>Bearing</td><td>${b.pressure_kpa} kPa</td><td>${b.allowable_kpa} kPa</td><td>${b.util}</td><td>${b.ok ? '✓' : '✗'}</td></tr>
      <tr><td>One-way shear</td><td>${ow.vu_kn} kN</td><td>${ow.phi_vc_kn} kN</td><td>${ow.util}</td><td>${ow.ok ? '✓' : '✗'}</td></tr>
      <tr><td>Punching shear</td><td>${pw.vu_kn} kN</td><td>${pw.phi_vc_kn} kN</td><td>${pw.util}</td><td>${pw.ok ? '✓' : '✗'}</td></tr>
    </tbody></table>`;
  if (r.warnings && r.warnings.length) {
    html += `<div class="loads-warn"><ul>${r.warnings.map((w) => `<li>${w}</li>`).join('')}</ul></div>`;
  }
  content.innerHTML = html;
}

async function runPile() {
  const inputs = {
    pile_diameter_mm: num('plD'),
    pile_length_m: num('plL'),
    skin_friction_kpa: num('plF'),
    skin_friction_alpha: num('plA'),
    end_bearing_kpa: num('plQp'),
    factor_of_safety: num('plFs'),
    piles_per_row: Math.round(num('plN')),
    rows_in_group: Math.round(num('plM')),
    center_to_center_spacing_m: num('plS'),
  };
  const content = byId('secResults');
  content.innerHTML = '<p class="placeholder">Computing pile capacity…</p>';
  const data = await designPile(inputs);
  if (data.status !== 'ok') return renderSelectionError(content, data);
  renderPile(content, data.results);
}

function renderPile(content, r) {
  const c = r.capacity_kn;
  const g = r.group;
  let html = `<h3>Pile Capacity — ${r.code_reference}</h3>
    <div class="sec-props">
      ${selRow('Pile', `${r.pile.diameter_m} m dia × ${r.inputs.pile_length_m} m`)}
      ${selRow('Skin friction', c.skin_friction, 'kN')}
      ${selRow('End bearing', c.end_bearing, 'kN')}
      ${selRow('Ultimate', c.ultimate, 'kN')}
      ${selRow('Allowable', c.allowable, 'kN')}
      ${selRow('Skin fraction', c.skin_fraction)}
      ${selRow('Group eff (η)', g.efficiency)}
      ${selRow('Piles', g.piles)}
      ${selRow('Group capacity', g.allowable_capacity, 'kN')}
    </div>`;
  if (r.warnings && r.warnings.length) {
    html += `<div class="loads-warn"><ul>${r.warnings.map((w) => `<li>${w}</li>`).join('')}</ul></div>`;
  }
  content.innerHTML = html;
}

async function runFatigue() {
  const inputs = {
    category: byId('fgCat').value,
    stress_range_mpa: num('fgF'),
    num_cycles: num('fgN'),
  };
  const content = byId('secResults');
  content.innerHTML = '<p class="placeholder">Checking fatigue…</p>';
  const data = await checkFatigue(inputs);
  if (data.status !== 'ok') return renderSelectionError(content, data);
  renderFatigue(content, data.results);
}

function renderFatigue(content, r) {
  const res = r.result;
  const badge = res.pass ? '<span style="color:var(--ok,#3fb950)">PASS</span>' : '<span style="color:var(--danger,#f85149)">FAIL</span>';
  const nf = res.infinite_life ? '∞' : res.cycles_to_failure.toExponential(2);
  let html = `<h3>Steel Fatigue — ${r.code_reference} ${badge}</h3>
    <div class="sec-props">
      ${selRow('Category', r.inputs.category)}
      ${selRow('Fatigue limit', r.category_params.fatigue_limit_mpa, 'MPa')}
      ${selRow('Stress range', r.inputs.stress_range_mpa, 'MPa')}
      ${selRow('Design cycles', r.inputs.num_cycles.toExponential(2))}
      ${selRow('Cycles to failure', nf)}
      ${selRow('Utilization', res.utilization)}
      ${selRow('Allowable range', res.allowable_stress_range_mpa, 'MPa')}
      ${selRow('Required category', r.required_category || '—')}
    </div>`;
  if (r.warnings && r.warnings.length) {
    html += `<div class="loads-warn"><ul>${r.warnings.map((w) => `<li>${w}</li>`).join('')}</ul></div>`;
  }
  content.innerHTML = html;
}

function renderConcrete(content, r, kind) {
  let html = `<h3>Concrete ${kind === 'beam' ? 'Beam' : 'Column'} — ${r.code_reference}</h3>`;
  if (kind === 'beam') {
    const f = r.flexure;
    const s = r.shear;
    const bars = r.suggested_bars;
    html += `<div class="sec-props">
      ${selRow('d (eff)', r.effective_depth_mm, 'mm')}
      ${selRow('As req', f.required_as_mm2, 'mm2')}
      ${selRow('ρ design', f.rho_design)}
      ${selRow('ρ min', f.rho_min)}
      ${selRow('φMn', f.phi_mn_kn_m, 'kN-m')}
      ${selRow('Flex util', f.flex_util ?? '—')}
      ${selRow('Vc', s.vc_kn, 'kN')}
      ${selRow('Vu/φVc', s.vu_over_vc)}
      ${selRow('Stirrups', s.stirrup_required ? 'Yes' : 'No')}
      ${s.spacing_mm ? selRow('Spacing', s.spacing_mm, 'mm') : ''}
      ${selRow('Bars', `${bars.count} × ${bars.bar_dia_mm} mm`)}
      ${bars.clear_spacing_mm != null ? selRow('Clear spacing', bars.clear_spacing_mm, 'mm') : ''}
    </div>`;
  } else {
    const bars = r.suggested_bars;
    html += `<div class="sec-props">
      ${selRow('Ag', r.gross_area_mm2, 'mm2')}
      ${selRow('φ', r.phi)}
      ${selRow('As req', r.required_as_mm2, 'mm2')}
      ${selRow('As min', r.min_as_mm2, 'mm2')}
      ${selRow('As design', r.design_as_mm2, 'mm2')}
      ${selRow('ρ design', r.rho_design)}
      ${selRow('ρ min', r.rho_min)}
      ${selRow('φPn', r.phi_pn_kn, 'kN')}
      ${selRow('Util', r.util)}
      ${selRow('Slenderness OK', r.slenderness_ok ? 'Yes' : 'No')}
      ${selRow('Bars', `${bars.count} × ${bars.bar_dia_mm} mm`)}
    </div>`;
  }
  if (r.warnings && r.warnings.length) {
    html += `<div class="loads-warn"><ul>${r.warnings.map((w) => `<li>${w}</li>`).join('')}</ul></div>`;
  }
  content.innerHTML = html;
}

function selRow(label, value, unit = '') {
  return `<div><span>${label}</span><strong>${value}${unit ? ` ${unit}` : ''}</strong></div>`;
}

function renderSelection(content, r, kind) {
  const sel = r.selected;
  let html = `<h3>${kind === 'beam' ? 'Beam' : 'Column'} Section Selection — ${r.code_reference}</h3>`;
  if (!sel) {
    html += `<div class="loads-warn"><ul>${(r.warnings || []).map((w) => `<li>${w}</li>`).join('')}</ul></div>`;
    content.innerHTML = html;
    return;
  }
  if (kind === 'beam') {
    html += `<div class="sec-props">
      ${selRow('Selected', sel.name)}
      ${selRow('Weight', sel.weight_kg_per_m, 'kg/m')}
      ${selRow('Depth', sel.depth_mm, 'mm')}
      ${selRow('φMn', sel.phi_mn_kn_m, 'kN-m')}
      ${selRow('φVn', sel.phi_vn_kn, 'kN')}
      ${selRow('Flex util', sel.flex_util)}
      ${selRow('Shear util', sel.shear_util)}
    </div>`;
  } else {
    html += `<div class="sec-props">
      ${selRow('Selected', sel.name)}
      ${selRow('Weight', sel.weight_kg_per_m, 'kg/m')}
      ${selRow('Depth', sel.depth_mm, 'mm')}
      ${selRow('φPn', sel.phi_pn_kn, 'kN')}
      ${selRow('Util', sel.util)}
    </div>`;
  }
  if (r.candidates && r.candidates.length > 1) {
    const rows = r.candidates.map((c) =>
      kind === 'beam'
        ? `<tr><td>${c.name}</td><td>${c.weight_kg_per_m}</td><td>${c.phi_mn_kn_m}</td><td>${c.phi_vn_kn}</td><td>${c.flex_util}</td><td>${c.shear_util}</td></tr>`
        : `<tr><td>${c.name}</td><td>${c.weight_kg_per_m}</td><td>${c.phi_pn_kn}</td><td>${c.util}</td></tr>`
    ).join('');
    const head = kind === 'beam'
      ? '<tr><th>Section</th><th>kg/m</th><th>φMn (kN-m)</th><th>φVn (kN)</th><th>Flex util</th><th>Shear util</th></tr>'
      : '<tr><th>Section</th><th>kg/m</th><th>φPn (kN)</th><th>Util</th></tr>';
    html += `<h4 style="margin:16px 0 6px;font-size:0.85rem;color:var(--text2);">Top Candidates</h4>
      <table class="loads-table"><thead>${head}</thead><tbody>${rows}</tbody></table>`;
  }
  if (r.warnings && r.warnings.length) {
    html += `<div class="loads-warn"><ul>${r.warnings.map((w) => `<li>${w}</li>`).join('')}</ul></div>`;
  }
  content.innerHTML = html;
}

function renderSectionNames(content, names) {
  const grid = document.createElement('div');
  grid.className = 'sec-grid';
  names.forEach((name) => {
    const button = document.createElement('button');
    button.className = 'sec-name';
    button.textContent = name;
    button.addEventListener('click', async () => {
      const data = await fetchSection(name);
      if (data.status === 'ok') {
        content.innerHTML = '';
        content.appendChild(makeSectionCard(data.section));
      }
    });
    grid.appendChild(button);
  });
  content.appendChild(grid);
}

function makeSectionCard(section) {
  const card = document.createElement('div');
  card.className = 'sec-card';
  card.innerHTML = `<h3>${section.name}</h3><div class="sec-props">
    ${[
      ['Weight', section.weight_kg_per_m, 'kg/m'],
      ['Area', section.area_m2.toExponential(3), 'm2'],
      ['Depth', section.depth_mm, 'mm'],
      ['bf', section.flange_width_mm, 'mm'],
      ['tf', section.flange_thickness_mm, 'mm'],
      ['tw', section.web_thickness_mm, 'mm'],
      ['Ix', section.Ix_m4.toExponential(3), 'm4'],
      ['Iy', section.Iy_m4.toExponential(3), 'm4'],
      ['Sx', section.Sx_m3.toExponential(3), 'm3'],
      ['Sy', section.Sy_m3.toExponential(3), 'm3'],
      ['rx', section.rx_m.toFixed(4), 'm'],
      ['ry', section.ry_m.toFixed(4), 'm'],
    ].map(([label, value, unit]) => `<div><span>${label}</span><strong>${value} ${unit}</strong></div>`).join('')}
  </div>`;
  return card;
}
