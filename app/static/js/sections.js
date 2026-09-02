import { fetchSection, searchSections, selectBeam, selectColumn } from './api.js';
import { byId, $$ } from './dom.js';

export function initSections() {
  byId('secSearch').addEventListener('click', runSectionSearch);

  $$('.sec-subtab[data-sectab]').forEach((tab) => {
    tab.addEventListener('click', () => switchSectionTab(tab.dataset.sectab));
  });
  $$('.sec-subtab[data-selkind]').forEach((btn) => {
    btn.addEventListener('click', () => switchSelectionKind(btn.dataset.selkind));
  });
  byId('beamSelForm').addEventListener('submit', (e) => {
    e.preventDefault();
    runBeamSelection();
  });
  byId('columnSelForm').addEventListener('submit', (e) => {
    e.preventDefault();
    runColumnSelection();
  });
}

function switchSectionTab(name) {
  $$('.sec-subtab[data-sectab]').forEach((t) => t.classList.toggle('active', t.dataset.sectab === name));
  const isSelect = name === 'select';
  $$('[data-secrow]').forEach((row) => row.classList.toggle('hidden', row.dataset.secrow !== name));
  byId('secSelectForms').classList.toggle('hidden', !isSelect);
  byId('secResults').closest('.sec-body').classList.toggle('with-forms', isSelect);
}

function switchSelectionKind(kind) {
  $$('.sec-subtab[data-selkind]').forEach((b) => b.classList.toggle('active', b.dataset.selkind === kind));
  $$('.sec-sel-form').forEach((f) => f.classList.toggle('hidden', f.dataset.selform !== kind));
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
  content.innerHTML = `<div class="loads-error"><strong>Error</strong><p>${data.message || 'Selection failed.'}</p></div>`;
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
