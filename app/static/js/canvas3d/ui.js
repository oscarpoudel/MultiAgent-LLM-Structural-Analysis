import { byId, $$ } from '../dom.js';
import { S } from '../state.js';
import { canvas3d, triggerRedraw } from './scene.js';
import { getElevOffset } from './render.js';

export function initUI() {
  initToolButtons();
  initViewButtons();
  initDisplayToggles();
  initSettings();
  updateStatus();
}

function initToolButtons() {
  $$('.tool-btn').forEach((button) => {
    button.addEventListener('click', () => {
      $$('.tool-btn').forEach((item) => item.classList.remove('active'));
      button.classList.add('active');
      S.tool = button.dataset.tool;
      S.memberStart = null;
      S.slabCorners = [];
      canvas3d.canvas.style.cursor = S.tool === 'select' ? 'default' : 'crosshair';
      updateStatus();
    });
  });
}

function getStructureSize() {
  const minX = canvas3d.gridLinesX.length ? Math.min(...canvas3d.gridLinesX) - 2 : -2;
  const maxX = canvas3d.gridLinesX.length ? Math.max(...canvas3d.gridLinesX) + 2 : 12;
  const minY = canvas3d.gridLinesY.length ? Math.min(...canvas3d.gridLinesY) - 2 : -2;
  const maxY = canvas3d.gridLinesY.length ? Math.max(...canvas3d.gridLinesY) + 2 : 12;
  const maxZ = canvas3d.levels.length ? Math.max(...canvas3d.levels.map(l => l.elevation)) : 10;
  return { minX, maxX, minY, maxY, maxZ, cx: (minX + maxX) / 2, cy: (minY + maxY) / 2 };
}

function updatePlanCamera() {
  canvas3d.camera.up.set(0, 1, 0);
  const size = getStructureSize();
  canvas3d.camera.position.set(size.cx, size.cy, size.maxZ + 40);
  canvas3d.camera.lookAt(size.cx, size.cy, canvas3d.currentPlanZ);
  canvas3d.controls.target.set(size.cx, size.cy, canvas3d.currentPlanZ);
}

function updateElevationCamera() {
  const size = getStructureSize();
  const midZ = size.maxZ / 2;
  const cx = (size.minX + size.maxX) / 2;
  const cy = (size.minY + size.maxY) / 2;
  const isXAxis = canvas3d.elevType === 'xAxis';

  canvas3d.camera.up.set(0, 0, 1);
  canvas3d.camera.near = 0.1;
  canvas3d.camera.far = 500;
  canvas3d.camera.updateProjectionMatrix();

  canvas3d.controls.enabled = true;
  canvas3d.controls.enableRotate = false;
  canvas3d.controls.enablePan = false;
  canvas3d.controls.enableZoom = true;
  canvas3d.controls.minDistance = 5;
  canvas3d.controls.maxDistance = 200;

  if (isXAxis) {
    // X-axis elevation: look straight at XZ plane from +Y direction
    canvas3d.camera.position.set(0, -cy + 50, midZ);
    canvas3d.camera.lookAt(0, -cy, midZ);
  } else {
    // Y-axis elevation: look straight at YZ plane from +X direction
    canvas3d.camera.position.set(-cx + 50, 0, midZ);
    canvas3d.camera.lookAt(-cx, 0, midZ);
  }

  canvas3d.controls.target.set(
    isXAxis ? 0 : -cx,
    isXAxis ? -cy : 0,
    midZ
  );
  canvas3d.controls.update();
}

function update3DCamera() {
  const size = getStructureSize();
  const span = Math.max(size.maxX - size.minX, size.maxY - size.minY, size.maxZ) || 20;
  canvas3d.camera.up.set(0, 0, 1);
  canvas3d.camera.position.set(size.cx - span * 1.2, size.cy - span * 1.2, span * 0.7);
  canvas3d.camera.lookAt(size.cx, size.cy, size.maxZ * 0.4);
  canvas3d.controls.target.set(size.cx, size.cy, size.maxZ * 0.4);
}

function positionDrawingPlane() {
  if (!canvas3d.groundPlane) return;
  const size = getStructureSize();
  const mode = canvas3d.viewMode;
  const isXAxis = canvas3d.elevType === 'xAxis';

  canvas3d.groundPlane.geometry.dispose();

  if (mode === 'plan') {
    const planeW = Math.max(size.maxX - size.minX, 20);
    const planeD = Math.max(size.maxY - size.minY, 20);
    canvas3d.groundPlane.geometry = new THREE.PlaneGeometry(planeW, planeD);
    canvas3d.groundPlane.rotation.set(0, 0, 0);
    canvas3d.groundPlane.position.set(size.cx, size.cy, canvas3d.currentPlanZ);
  } else if (mode === 'elevation') {
    const offset = getElevOffset();
    const cx = offset.cx;
    const cy = offset.cy;
    if (isXAxis) {
      // X-axis elevation: XZ plane at Y = -cy (matches node/grid offset position)
      const planeW = Math.max(size.maxX - size.minX, 20);
      const planeH = Math.max(size.maxZ, 20);
      canvas3d.groundPlane.geometry = new THREE.PlaneGeometry(planeW, planeH);
      canvas3d.groundPlane.rotation.set(-Math.PI / 2, 0, 0);
      canvas3d.groundPlane.position.set(0, -cy, size.maxZ / 2);
    } else {
      // Y-axis elevation: YZ plane at X = -cx (matches node/grid offset position)
      const planeD = Math.max(size.maxY - size.minY, 20);
      const planeH = Math.max(size.maxZ, 20);
      canvas3d.groundPlane.geometry = new THREE.PlaneGeometry(planeD, planeH);
      canvas3d.groundPlane.rotation.set(-Math.PI / 2, Math.PI / 2, 0);
      canvas3d.groundPlane.position.set(-cx, 0, size.maxZ / 2);
    }
  } else {
    const planeW = Math.max(size.maxX - size.minX, 20);
    const planeH = Math.max(size.maxZ, 20);
    canvas3d.groundPlane.geometry = new THREE.PlaneGeometry(planeW, planeH);
    canvas3d.groundPlane.rotation.set(-Math.PI / 2, 0, 0);
    canvas3d.groundPlane.position.set(size.cx, 0, size.maxZ / 2);
  }
}

function updateElevBtnsVisibility() {
  const elevGridControls = byId('elevGridControls');
  if (elevGridControls) {
    elevGridControls.style.display = canvas3d.viewMode === 'elevation' ? 'flex' : 'none';
  }
}

export function initCameraPosition() {
  positionDrawingPlane();
  if (canvas3d.viewMode === 'elevation') {
    updateElevationCamera();
  } else {
    update3DCamera();
  }
  canvas3d.controls.update();
  triggerRedraw();
}

function buildElevGridOptions() {
  const sel = byId('elevGridSelect');
  if (!sel) return;
  sel.innerHTML = '';
  const isXAxis = canvas3d.elevType === 'xAxis';

  // For X-axis elevation, show Y grid lines (1', 2', 3'...) as cut options
  // For Y-axis elevation, show X grid lines (1, 2, 3...) as cut options
  const lines = isXAxis ? canvas3d.gridLinesY : canvas3d.gridLinesX;
  lines.forEach((val, i) => {
    const opt = document.createElement('option');
    opt.value = i;
    const suffix = isXAxis ? "'" : '';
    opt.textContent = `${i + 1}${suffix}`;
    sel.appendChild(opt);
  });

  if (canvas3d.selectedElevGrid === 0) sel.value = '0';
}

function initViewButtons() {
  const elevTypeSelect = byId('elevTypeSelect');
  const elevGridSelect = byId('elevGridSelect');

  // Wire elevation type selector
  if (elevTypeSelect) {
    elevTypeSelect.addEventListener('change', () => {
      canvas3d.elevType = elevTypeSelect.value;
      canvas3d.selectedElevGrid = 0;
      buildElevGridOptions();
      elevGridSelect.value = '0';
      if (canvas3d.viewMode === 'elevation') {
        positionDrawingPlane();
        updateElevationCamera();
        canvas3d.controls.update();
        triggerRedraw();
      }
    });
  }

  if (elevGridSelect) {
    elevGridSelect.addEventListener('change', () => {
      canvas3d.selectedElevGrid = parseInt(elevGridSelect.value);
      if (canvas3d.viewMode === 'elevation') {
        positionDrawingPlane();
        updateElevationCamera();
        canvas3d.controls.update();
        triggerRedraw();
      }
    });
  }

  const planBtn = byId('viewPlanBtn');
  const elevBtn = byId('viewElevBtn');
  const btn3D = byId('view3DBtn');
  const viewBtns = [planBtn, elevBtn, btn3D];

  function setViewMode(btnId) {
    viewBtns.forEach(b => b && b.classList.remove('active'));
    const btn = byId(btnId);
    if (btn) btn.classList.add('active');
    const planLevelSelect = byId('planLevelSelect');

    if (btnId === 'viewPlanBtn') {
      canvas3d.viewMode = 'plan';
      canvas3d.controls.enableRotate = false;
      updatePlanCamera();
      if (planLevelSelect) planLevelSelect.style.display = 'block';
    } else if (btnId === 'viewElevBtn') {
      canvas3d.viewMode = 'elevation';
      canvas3d.controls.enableRotate = false;
      buildElevGridOptions();
      updateElevationCamera();
      if (planLevelSelect) planLevelSelect.style.display = 'none';
    } else {
      canvas3d.viewMode = '3d';
      canvas3d.controls.enableRotate = true;
      update3DCamera();
      if (planLevelSelect) planLevelSelect.style.display = 'none';
    }
    positionDrawingPlane();
    canvas3d.controls.update();
    updateElevBtnsVisibility();
    triggerRedraw();
  }

  viewBtns.forEach(btn => {
    if (btn) btn.addEventListener('click', () => setViewMode(btn.id));
  });

  updateElevBtnsVisibility();
}

function initDisplayToggles() {
  ['showGrid', 'showLabels', 'showDeformed', 'showForces', 'showDrift'].forEach((id) => {
    const el = byId(id);
    if (el) el.addEventListener('change', triggerRedraw);
  });
  const deformScale = byId('deformScale');
  if (deformScale) deformScale.addEventListener('input', triggerRedraw);
}

export function updateStatus() {
  const el = byId('canvasStatus');
  if (!el) return;
  const viewLabel = canvas3d.viewMode === 'plan'
    ? `Plan (XY)`
    : canvas3d.viewMode === 'elevation'
      ? `Elev ${canvas3d.elevType === 'xAxis' ? 'X' : 'Y'} axis, Grid ${canvas3d.selectedElevGrid + 1}`
      : '3D Perspective';
  const messages = {
    select: `Click to select. Scroll to zoom. [${viewLabel}]`,
    node: `Click to place node. Scroll to zoom. [${viewLabel}]`,
    member: S.memberStart ? `Click second node to finish member.` : 'Click first node to start a member.',
    support: 'Click a node to set its support type.',
    load: 'Click a node or member to apply a load.',
    slab: S.slabCorners && S.slabCorners.length > 0
      ? `Select next corner node (${S.slabCorners.length} selected, need 3+).`
      : 'Click corner nodes to define a slab polygon (3+ nodes).',
    delete: 'Click a node, member, or slab to delete it.',
  };
  el.textContent = messages[S.tool] || 'Ready';
}

function initSettings() {
  const settingsBtn = byId('settingsBtn');
  const settingsPanel = byId('settingsPanel');
  const settingsClose = byId('settingsCloseBtn');
  if (!settingsBtn || !settingsPanel) return;

  function toggle() {
    settingsPanel.classList.toggle('hidden');
  }
  settingsBtn.addEventListener('click', toggle);
  if (settingsClose) settingsClose.addEventListener('click', toggle);

  const loadScaleRange = byId('loadScaleRange');
  const loadScaleVal = byId('loadScaleVal');
  if (loadScaleRange) {
    loadScaleRange.addEventListener('input', () => {
      const v = parseFloat(loadScaleRange.value);
      canvas3d.loadScale = v;
      if (loadScaleVal) loadScaleVal.textContent = v.toFixed(1);
      triggerRedraw();
    });
  }

  const nodeSizeRange = byId('nodeSizeRange');
  const nodeSizeVal = byId('nodeSizeVal');
  if (nodeSizeRange) {
    nodeSizeRange.addEventListener('input', () => {
      const v = parseFloat(nodeSizeRange.value);
      canvas3d.nodeSize = v;
      if (nodeSizeVal) nodeSizeVal.textContent = v.toFixed(2);
      triggerRedraw();
    });
  }

  const memberSizeRange = byId('memberSizeRange');
  const memberSizeVal = byId('memberSizeVal');
  if (memberSizeRange) {
    memberSizeRange.addEventListener('input', () => {
      const v = parseFloat(memberSizeRange.value);
      canvas3d.memberSize = v;
      if (memberSizeVal) memberSizeVal.textContent = v.toFixed(2);
      triggerRedraw();
    });
  }

  const gridColorPicker = byId('gridColorPicker');
  if (gridColorPicker) {
    gridColorPicker.addEventListener('input', () => {
      canvas3d.gridColor = gridColorPicker.value;
      triggerRedraw();
    });
  }
}
