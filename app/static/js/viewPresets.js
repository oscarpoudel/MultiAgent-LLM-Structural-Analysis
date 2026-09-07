import { byId } from './dom.js';
import { S } from './state.js';
import { canvas3d, triggerRedraw } from './canvas3d/scene.js';

const PRESETS = [
  { id: 'front', label: 'Front', icon: '&#9650;' },
  { id: 'back', label: 'Back', icon: '&#9660;' },
  { id: 'left', label: 'Left', icon: '&#9664;' },
  { id: 'right', label: 'Right', icon: '&#9654;' },
  { id: 'top', label: 'Top', icon: '&#9632;' },
  { id: 'bottom', label: 'Bottom', icon: '&#9633;' },
  { id: 'fit', label: 'Fit to view', icon: '&#8982;' },
];

export function initViewPresets() {
  buildWidget();
  byId('viewPresetBtns')?.querySelectorAll('.vp-btn').forEach((btn) => {
    btn.addEventListener('click', () => applyPreset(btn.dataset.vp));
  });
}

function buildWidget() {
  if (byId('viewPresetWidget')) return;
  const wrap = byId('canvas')?.parentElement;
  if (!wrap) return;
  const widget = document.createElement('div');
  widget.id = 'viewPresetWidget';
  widget.className = 'vp-widget';
  widget.title = 'Camera presets';
  widget.innerHTML = `
    <div class="vp-grid" id="viewPresetBtns">
      ${PRESETS.map((p) => `<button class="vp-btn" data-vp="${p.id}" title="${p.label}"><span>${p.icon}</span></button>`).join('')}
    </div>`;
  wrap.appendChild(widget);
}

function ensure3DMode() {
  const btn3d = byId('view3DBtn');
  if (btn3d && !btn3d.classList.contains('active')) btn3d.click();
}

function getBounds() {
  if (!S.nodes.length) return { cx: 0, cy: 0, cz: 0, span: 20 };
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity, minZ = Infinity, maxZ = -Infinity;
  S.nodes.forEach((n) => {
    const z = n.z || 0;
    if (n.x < minX) minX = n.x;
    if (n.x > maxX) maxX = n.x;
    if (n.y < minY) minY = n.y;
    if (n.y > maxY) maxY = n.y;
    if (z < minZ) minZ = z;
    if (z > maxZ) maxZ = z;
  });
  return {
    cx: (minX + maxX) / 2,
    cy: (minY + maxY) / 2,
    cz: (minZ + maxZ) / 2,
    span: Math.max(maxX - minX, maxY - minY, maxZ - minZ, 10),
  };
}

function setCamera(pos, target, up) {
  if (!canvas3d.camera || !canvas3d.controls) return;
  canvas3d.camera.up.set(up[0], up[1], up[2]);
  canvas3d.camera.position.set(pos[0], pos[1], pos[2]);
  canvas3d.camera.lookAt(target[0], target[1], target[2]);
  canvas3d.controls.target.set(target[0], target[1], target[2]);
  canvas3d.controls.update();
  triggerRedraw();
}

export function applyPreset(id) {
  ensure3DMode();
  const { cx, cy, cz, span } = getBounds();
  const d = span * 1.5 + 6;
  const center = [cx, cy, cz];
  switch (id) {
    case 'front':    setCamera([cx, cy + d, cz], center, [0, 0, 1]); break;
    case 'back':     setCamera([cx, cy - d, cz], center, [0, 0, 1]); break;
    case 'left':     setCamera([cx - d, cy, cz], center, [0, 0, 1]); break;
    case 'right':    setCamera([cx + d, cy, cz], center, [0, 0, 1]); break;
    case 'top':      setCamera([cx, cy, cz + d], center, [0, -1, 0]); break;
    case 'bottom':   setCamera([cx, cy, cz - d], center, [0, 1, 0]); break;
    case 'fit':
    default:
      setCamera([cx - span * 0.8, cy - span * 0.8, cz + span * 0.6], center, [0, 0, 1]);
      break;
  }
}
