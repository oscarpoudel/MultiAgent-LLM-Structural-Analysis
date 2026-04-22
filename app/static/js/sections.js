import { fetchSection, searchSections } from './api.js';
import { byId } from './dom.js';

export function initSections() {
  byId('secSearch').addEventListener('click', runSectionSearch);
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
