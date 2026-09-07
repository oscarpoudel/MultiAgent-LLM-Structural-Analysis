import { byId } from '../dom.js';
import { S } from '../state.js';
import { canvas3d, triggerRedraw } from './scene.js';
import { colorForRatioHex } from './colorScale.js';

// Transient legend data for the on-canvas result legend. Cleared each draw.
let activeLegend = null;
export function getActiveLegend() {
  return activeLegend;
}

function getLevelNodes() {
  const mode = canvas3d.viewMode;
  if (mode !== 'plan') return S.nodes;
  const currentZ = canvas3d.currentPlanZ;
  const snap = 0.3;
  return S.nodes.filter(n => Math.abs((n.z || 0) - currentZ) < snap);
}

function getElevNodes() {
  if (canvas3d.viewMode !== 'elevation') return S.nodes;

  const isXAxis = canvas3d.elevType === 'xAxis';
  const gridIdx = canvas3d.selectedElevGrid;
  const snap = 0.5;

  // X-axis elevation: Y is the perpendicular axis (grid lines 1',2',3'...)
  // Y-axis elevation: X is the perpendicular axis (grid lines 1,2,3...)
  const cutLines = isXAxis ? canvas3d.gridLinesY : canvas3d.gridLinesX;
  const cutVal = cutLines[gridIdx] ?? 0;

  return S.nodes.filter(n => {
    const nPos = isXAxis ? (n.y || 0) : (n.x || 0);
    return Math.abs(nPos - cutVal) < snap;
  });
}

function getElevMembers() {
  if (canvas3d.viewMode !== 'elevation') return S.members;
  const elevNodeIds = new Set(getElevNodes().map(n => n.id));
  // Show members where at least one end is on the cut grid line
  // This includes vertical, horizontal and inclined members
  return S.members.filter(m => elevNodeIds.has(m.n1) || elevNodeIds.has(m.n2));
}

function getLevelMembers() {
  if (canvas3d.viewMode !== 'plan') return S.members;
  const levelNodeIds = new Set(getLevelNodes().map(n => n.id));
  return S.members.filter(m => levelNodeIds.has(m.n1) && levelNodeIds.has(m.n2));
}

export function draw() {
  if (!canvas3d.scene) return;
  activeLegend = null;
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  canvas3d.scene.background = new THREE.Color(isDark ? '#0f1419' : '#f8fafb');

  const showGrid = byId('showGrid');
  canvas3d.gridGroup.visible = showGrid ? showGrid.checked : true;
  const showLabels = byId('showLabels');
  canvas3d.labelsGroup.visible = showLabels ? showLabels.checked : true;

  clearGroup(canvas3d.nodesGroup);
  clearGroup(canvas3d.membersGroup);
  clearGroup(canvas3d.slabsGroup);
  clearGroup(canvas3d.loadsGroup);
  clearGroup(canvas3d.supportsGroup);
  clearGroup(canvas3d.gridGroup);
  clearGroup(canvas3d.levelLinesGroup);
  clearGroup(canvas3d.labelsGroup);

  drawGroundSlab(isDark);
  drawGridLines();
  drawLevelLines();
  drawGridLabels();
  drawMembers3D(isDark);
  drawNodes3D(isDark);
  drawSupports3D(isDark);
  drawSlabs3D(isDark);
  drawLoads3D(isDark);
  drawMemberLoads3D(isDark);

  const showForces = byId('showForces');
  if (showForces && showForces.checked && S.results && S.results.member_force_summary) {
    drawMemberForceOverlay3D();
  }

  const showDrift = byId('showDrift');
  if (showDrift && showDrift.checked && S.results && S.results.story_response?.story_drifts) {
    drawStoryDriftOverlay3D();
  }

  const showDeformed = byId('showDeformed');
  if (showDeformed && showDeformed.checked && S.results && (S.results.node_displacements || S.results.displacements)) {
    drawDeformedShape3D(isDark);
  }

  updateLegendDom();
}

function updateLegendDom() {
  const legend = byId('canvasLegend');
  if (!legend) return;
  if (!activeLegend) {
    legend.classList.add('hidden');
    return;
  }
  legend.classList.remove('hidden');
  const title = byId('legendTitle');
  const minEl = byId('legendMin');
  const maxEl = byId('legendMax');
  const unitEl = byId('legendUnit');
  if (title) title.textContent = activeLegend.title;
  if (minEl) minEl.textContent = formatLegendNum(activeLegend.min);
  if (maxEl) maxEl.textContent = formatLegendNum(activeLegend.max);
  if (unitEl) unitEl.textContent = activeLegend.unit || '';
}

function formatLegendNum(value) {
  if (value === undefined || value === null || !Number.isFinite(value)) return '0';
  if (value >= 100) return value.toFixed(0);
  if (value >= 10) return value.toFixed(1);
  return value.toFixed(2);
}

function clearGroup(group) {
  while (group.children.length > 0) {
    const child = group.children[0];
    try {
      if (child.geometry) child.geometry.dispose();
      if (child.material && !Array.isArray(child.material)) child.material.dispose();
      if (child.material && Array.isArray(child.material)) child.material.forEach(m => m.dispose());
    } catch(e) {}
    group.remove(child);
  }
}

function drawGroundSlab(isDark) {
  const mode = canvas3d.viewMode;
  if (mode === 'elevation') return; // No ground slab in elevation

  const minX = canvas3d.gridLinesX.length ? Math.min(...canvas3d.gridLinesX) : 0;
  const maxX = canvas3d.gridLinesX.length ? Math.max(...canvas3d.gridLinesX) : 10;
  const minY = canvas3d.gridLinesY.length ? Math.min(...canvas3d.gridLinesY) : 0;
  const maxY = canvas3d.gridLinesY.length ? Math.max(...canvas3d.gridLinesY) : 10;
  const pad = 4;
  const slabW = (maxX - minX) + pad * 2;
  const slabD = (maxY - minY) + pad * 2;
  const cx = (minX + maxX) / 2;
  const cy = (minY + maxY) / 2;

  const geo = new THREE.PlaneGeometry(slabW, slabD);
  const mat = new THREE.MeshStandardMaterial({
    color: isDark ? 0x1a222d : 0xe5e7eb,
    roughness: 0.9, transparent: true, opacity: 0.5, side: THREE.DoubleSide
  });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.position.set(cx, cy, 0.01);
  mesh.receiveShadow = true;
  canvas3d.gridGroup.add(mesh);

  const borderGeo = new THREE.EdgesGeometry(geo);
  const borderMat = new THREE.LineBasicMaterial({ color: isDark ? 0x374151 : 0x9ca3af, transparent: true, opacity: 0.6 });
  const border = new THREE.LineSegments(borderGeo, borderMat);
  border.position.set(cx, cy, 0.02);
  canvas3d.gridGroup.add(border);
}

export function getElevOffset() {
  if (canvas3d.viewMode !== 'elevation') return null;
  const minX = canvas3d.gridLinesX.length ? Math.min(...canvas3d.gridLinesX) : 0;
  const maxX = canvas3d.gridLinesX.length ? Math.max(...canvas3d.gridLinesX) : 10;
  const minY = canvas3d.gridLinesY.length ? Math.min(...canvas3d.gridLinesY) : 0;
  const maxY = canvas3d.gridLinesY.length ? Math.max(...canvas3d.gridLinesY) : 10;
  return { cx: (minX + maxX) / 2, cy: (minY + maxY) / 2 };
}

function drawGridLines() {
  const dark = document.documentElement.getAttribute('data-theme') === 'dark';
  const userColor = canvas3d.gridColor;
  const color = userColor ? parseInt(userColor.replace('#', ''), 16) : (dark ? 0x334155 : 0xcbd5e1);
  const topZ = canvas3d.levels.length ? Math.max(...canvas3d.levels.map(l => l.elevation)) : 10;
  const minX = canvas3d.gridLinesX.length ? Math.min(...canvas3d.gridLinesX) - 2 : -2;
  const maxX = canvas3d.gridLinesX.length ? Math.max(...canvas3d.gridLinesX) + 2 : 12;
  const minY = canvas3d.gridLinesY.length ? Math.min(...canvas3d.gridLinesY) - 2 : -2;
  const maxY = canvas3d.gridLinesY.length ? Math.max(...canvas3d.gridLinesY) + 2 : 12;
  const mode = canvas3d.viewMode;

  if (mode === 'plan') {
    canvas3d.gridLinesX.forEach((x) => {
      const geo = new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(x, minY, canvas3d.currentPlanZ),
        new THREE.Vector3(x, maxY, canvas3d.currentPlanZ)
      ]);
      canvas3d.gridGroup.add(new THREE.Line(geo, new THREE.LineBasicMaterial({ color })));
    });
    canvas3d.gridLinesY.forEach((y) => {
      const geo = new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(minX, y, canvas3d.currentPlanZ),
        new THREE.Vector3(maxX, y, canvas3d.currentPlanZ)
      ]);
      canvas3d.gridGroup.add(new THREE.Line(geo, new THREE.LineBasicMaterial({ color })));
    });
  } else if (mode === 'elevation') {
    const isXAxis = canvas3d.elevType === 'xAxis';
    const selectedIdx = canvas3d.selectedElevGrid;
    const offset = getElevOffset();
    const cx = offset.cx;
    const cy = offset.cy;

    if (isXAxis) {
      // X-axis elevation: vertical grid lines for X axis (1,2,3...)
      canvas3d.gridLinesX.forEach((x, i) => {
        const geo = new THREE.BufferGeometry().setFromPoints([
          new THREE.Vector3(x - cx, -cy, 0),
          new THREE.Vector3(x - cx, -cy, topZ)
        ]);
        const mat = new THREE.LineBasicMaterial({
          color, transparent: true,
          opacity: i === selectedIdx ? 1.0 : 0.35
        });
        canvas3d.gridGroup.add(new THREE.Line(geo, mat));
      });
    } else {
      // Y-axis elevation: vertical grid lines for Y axis (1',2',3'...)
      canvas3d.gridLinesY.forEach((y, i) => {
        const geo = new THREE.BufferGeometry().setFromPoints([
          new THREE.Vector3(-cx, y - cy, 0),
          new THREE.Vector3(-cx, y - cy, topZ)
        ]);
        const mat = new THREE.LineBasicMaterial({
          color, transparent: true,
          opacity: i === selectedIdx ? 1.0 : 0.35
        });
        canvas3d.gridGroup.add(new THREE.Line(geo, mat));
      });
    }
  } else {
    // 3D
    const baseMat = new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.35 });
    canvas3d.levels.forEach((level) => {
      canvas3d.gridLinesX.forEach((x) => {
        canvas3d.gridGroup.add(new THREE.Line(
          new THREE.BufferGeometry().setFromPoints([
            new THREE.Vector3(x, minY, level.elevation),
            new THREE.Vector3(x, maxY, level.elevation)
          ]),
          baseMat.clone()
        ));
      });
      canvas3d.gridLinesY.forEach((y) => {
        canvas3d.gridGroup.add(new THREE.Line(
          new THREE.BufferGeometry().setFromPoints([
            new THREE.Vector3(minX, y, level.elevation),
            new THREE.Vector3(maxX, y, level.elevation)
          ]),
          baseMat.clone()
        ));
      });
    });
    canvas3d.gridLinesX.forEach((x) => {
      canvas3d.gridLinesY.forEach((y) => {
        canvas3d.gridGroup.add(new THREE.Line(
          new THREE.BufferGeometry().setFromPoints([
            new THREE.Vector3(x, y, 0),
            new THREE.Vector3(x, y, topZ)
          ]),
          baseMat.clone()
        ));
      });
    });
  }
}

function drawLevelLines() {
  const dark = document.documentElement.getAttribute('data-theme') === 'dark';
  const color = dark ? 0x475569 : 0x94a3b8;
  const minX = canvas3d.gridLinesX.length ? Math.min(...canvas3d.gridLinesX) - 2 : -2;
  const maxX = canvas3d.gridLinesX.length ? Math.max(...canvas3d.gridLinesX) + 2 : 12;
  const minY = canvas3d.gridLinesY.length ? Math.min(...canvas3d.gridLinesY) - 2 : -2;
  const maxY = canvas3d.gridLinesY.length ? Math.max(...canvas3d.gridLinesY) + 2 : 12;

  if (canvas3d.viewMode !== 'elevation') return;

  const isXAxis = canvas3d.elevType === 'xAxis';
  const offset = getElevOffset();
  const cx = offset.cx;
  const cy = offset.cy;

  if (isXAxis) {
    // X-axis elevation: horizontal lines across X at each level
    canvas3d.levels.forEach((level) => {
      const geo = new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(minX - cx, -cy, level.elevation),
        new THREE.Vector3(maxX - cx, -cy, level.elevation)
      ]);
      canvas3d.levelLinesGroup.add(new THREE.Line(geo, new THREE.LineBasicMaterial({ color })));
    });
  } else {
    // Y-axis elevation: horizontal lines across Y at each level
    canvas3d.levels.forEach((level) => {
      const geo = new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(-cx, minY - cy, level.elevation),
        new THREE.Vector3(-cx, maxY - cy, level.elevation)
      ]);
      canvas3d.levelLinesGroup.add(new THREE.Line(geo, new THREE.LineBasicMaterial({ color })));
    });
  }
}

function drawGridLabels() {
  const showLabels = byId('showLabels');
  if (!showLabels || !showLabels.checked) return;

  const mode = canvas3d.viewMode;
  const topZ = canvas3d.levels.length ? Math.max(...canvas3d.levels.map(l => l.elevation)) + 0.5 : 10.5;
  const minX = canvas3d.gridLinesX.length ? Math.min(...canvas3d.gridLinesX) - 2 : -2;
  const maxX = canvas3d.gridLinesX.length ? Math.max(...canvas3d.gridLinesX) + 2 : 12;
  const minY = canvas3d.gridLinesY.length ? Math.min(...canvas3d.gridLinesY) - 2 : -2;
  const maxY = canvas3d.gridLinesY.length ? Math.max(...canvas3d.gridLinesY) + 2 : 12;

  if (mode === 'plan') {
    canvas3d.gridLinesX.forEach((x, i) => {
      createTextSprite(String(i + 1), x, maxY, canvas3d.currentPlanZ, 0x3b82f6);
    });
    canvas3d.gridLinesY.forEach((y, i) => {
      createTextSprite(`${i + 1}'`, minX, y, canvas3d.currentPlanZ, 0x059669);
    });
  } else if (mode === 'elevation') {
    const isXAxis = canvas3d.elevType === 'xAxis';
    const offset = getElevOffset();
    const cx = offset.cx;
    const cy = offset.cy;

    if (isXAxis) {
      // X-axis elevation: X grid numbers (1,2,3...) across top, level labels on left
      const gx = canvas3d.gridLinesX[canvas3d.selectedElevGrid];
      canvas3d.gridLinesX.forEach((x, i) => {
        createTextSprite(String(i + 1), x - cx, -cy, topZ, x === gx ? 0x3b82f6 : 0x9ca3af);
      });
      canvas3d.levels.forEach((level) => {
        createTextSprite(`${level.name} (${level.elevation}m)`, minX - cx - 3.5, -cy, level.elevation + 0.3, 0x059669);
      });
    } else {
      // Y-axis elevation: Y grid numbers (1',2',3'...) across top, level labels on left
      const gy = canvas3d.gridLinesY[canvas3d.selectedElevGrid];
      canvas3d.gridLinesY.forEach((y, i) => {
        createTextSprite(`${i + 1}'`, -cx, y - cy, topZ, y === gy ? 0x3b82f6 : 0x9ca3af);
      });
      canvas3d.levels.forEach((level) => {
        createTextSprite(`${level.name} (${level.elevation}m)`, -cx - 3.5, minY - cy, level.elevation + 0.3, 0x059669);
      });
    }
  } else {
    canvas3d.gridLinesX.forEach((x, i) => {
      createTextSprite(String(i + 1), x, maxY, topZ, 0x3b82f6);
    });
    canvas3d.gridLinesY.forEach((y, i) => {
      createTextSprite(`${i + 1}'`, minX, y, topZ, 0x059669);
    });
  }
}

function createTextSprite(text, x, y, z, color) {
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d');
  canvas.width = 256;
  canvas.height = 64;
  ctx.fillStyle = 'transparent';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.font = 'bold 28px Inter, Arial, sans-serif';
  ctx.fillStyle = '#' + color.toString(16).padStart(6, '0');
  ctx.textAlign = 'left';
  ctx.textBaseline = 'middle';
  ctx.fillText(text, 8, 32);

  const texture = new THREE.CanvasTexture(canvas);
  const mat = new THREE.SpriteMaterial({ map: texture, transparent: true, depthTest: false });
  const sprite = new THREE.Sprite(mat);
  sprite.position.set(x, y, z);
  sprite.scale.set(3, 0.75, 1);
  canvas3d.labelsGroup.add(sprite);
}

function drawMembers3D(isDark) {
  const mode = canvas3d.viewMode;
  const members = mode === 'elevation' ? getElevMembers() : getLevelMembers();
  const offset = getElevOffset();

  members.forEach((member) => {
    const n1 = S.nodes.find((n) => n.id === member.n1);
    const n2 = S.nodes.find((n) => n.id === member.n2);
    if (!n1 || !n2) return;

    let v1, v2;
    if (offset) {
      const isXAxis = canvas3d.elevType === 'xAxis';
      v1 = isXAxis
        ? new THREE.Vector3(n1.x - offset.cx, -offset.cy, n1.z || 0)
        : new THREE.Vector3(-offset.cx, n1.y - offset.cy, n1.z || 0);
      v2 = isXAxis
        ? new THREE.Vector3(n2.x - offset.cx, -offset.cy, n2.z || 0)
        : new THREE.Vector3(-offset.cx, n2.y - offset.cy, n2.z || 0);
    } else {
      v1 = new THREE.Vector3(n1.x, n1.y, n1.z || 0);
      v2 = new THREE.Vector3(n2.x, n2.y, n2.z || 0);
    }
    const distance = v1.distanceTo(v2);

    const mSize = canvas3d.memberSize || 0.12;
    const geo = new THREE.CylinderGeometry(mSize, mSize, distance, 8);
    geo.translate(0, distance / 2, 0);
    geo.rotateX(Math.PI / 2);

    const isSelected = S.selected && S.selected.type === 'member' && S.selected.id === member.id;
    const mat = new THREE.MeshStandardMaterial({
      color: isSelected ? 0xf59e0b : (isDark ? 0x60a5fa : 0x2563eb),
      roughness: 0.4
    });

    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.copy(v1);
    mesh.lookAt(v2);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    mesh.userData = { id: member.id };
    canvas3d.membersGroup.add(mesh);
  });
}

function drawNodes3D(isDark) {
  const nodes = canvas3d.viewMode === 'elevation' ? getElevNodes() : getLevelNodes();
  const offset = getElevOffset();
  const nodeR = canvas3d.nodeSize || 0.2;

  nodes.forEach((node) => {
    const isSelected = S.selected && S.selected.type === 'node' && S.selected.id === node.id;
    const mat = new THREE.MeshStandardMaterial({
      color: isSelected ? 0xf59e0b : (isDark ? 0xe2e8f0 : 0x1e293b),
      roughness: 0.2
    });
    const sphere = new THREE.Mesh(new THREE.SphereGeometry(nodeR, 16, 16), mat);
    if (offset) {
      const isXAxis = canvas3d.elevType === 'xAxis';
      if (isXAxis) {
        sphere.position.set(node.x - offset.cx, -offset.cy, node.z || 0);
      } else {
        sphere.position.set(-offset.cx, node.y - offset.cy, node.z || 0);
      }
    } else {
      sphere.position.set(node.x, node.y, node.z || 0);
    }
    sphere.castShadow = true;
    sphere.userData = { id: node.id };
    canvas3d.nodesGroup.add(sphere);
  });
}

function drawSupports3D(isDark) {
  const geoFixed = new THREE.BoxGeometry(0.6, 0.6, 0.15);
  const geoPin = new THREE.ConeGeometry(0.3, 0.5, 4);
  const mat = new THREE.MeshStandardMaterial({ color: 0x22c55e });

  const nodes = canvas3d.viewMode === 'elevation' ? getElevNodes() : getLevelNodes();
  const offset = getElevOffset();
  nodes.forEach(node => {
    if (!node.support || node.support === 'free') return;
    let nx, ny, nz;
    if (offset) {
      const isXAxis = canvas3d.elevType === 'xAxis';
      if (isXAxis) {
        nx = node.x - offset.cx;
        ny = -offset.cy;
      } else {
        nx = -offset.cx;
        ny = node.y - offset.cy;
      }
      nz = (node.z || 0);
    } else {
      nx = node.x;
      ny = node.y;
      nz = node.z || 0;
    }
    let mesh;
    if (node.support === 'fixed') {
      mesh = new THREE.Mesh(geoFixed, mat);
      mesh.position.set(nx, ny, nz - 0.1);
    } else {
      mesh = new THREE.Mesh(geoPin, mat);
      mesh.position.set(nx, ny, nz - 0.25);
      mesh.rotation.x = Math.PI;
    }
    canvas3d.supportsGroup.add(mesh);
  });
}

function drawSlabs3D(isDark) {
  if (!S.slabs || !S.slabs.length) return;
  const offset = canvas3d.viewMode === 'elevation' ? getElevOffset() : null;
  const isElev = canvas3d.viewMode === 'elevation';
  const isXAxis = isElev && canvas3d.elevType === 'xAxis';

  S.slabs.forEach((slab) => {
    const pts = slab.nodeIds.map(id => S.nodes.find(n => n.id === id)).filter(Boolean);
    if (pts.length < 3) return;

    // Build ordered polygon shape
    const shape = new THREE.Shape();
    pts.forEach((p, i) => {
      let x, y;
      if (offset) {
        if (isXAxis) {
          x = p.x - offset.cx;
          y = p.z || 0;
        } else {
          x = offset.cx ? 0 : 0;
          y = p.z || 0;
        }
      } else {
        x = p.x;
        y = p.y;
      }
      if (i === 0) shape.moveTo(x, y);
      else shape.lineTo(x, y);
    });
    shape.closePath();

    const geo = new THREE.ShapeGeometry(shape);
    const mat = new THREE.MeshStandardMaterial({
      color: isDark ? 0x1e3a5f : 0x93c5fd,
      transparent: true,
      opacity: 0.35,
      side: THREE.DoubleSide,
      depthWrite: false,
    });
    const mesh = new THREE.Mesh(geo, mat);

    if (offset) {
      if (isXAxis) {
        mesh.position.set(0, -offset.cy, 0);
      } else {
        mesh.position.set(-offset.cx, 0, 0);
      }
    } else {
      mesh.position.set(0, 0, slab.elevation || 0);
    }
    mesh.userData = { id: slab.id };
    canvas3d.slabsGroup.add(mesh);

    // Draw slab border
    const pts3d = pts.map(p => {
      if (offset) {
        if (isXAxis) return new THREE.Vector3(p.x - offset.cx, -offset.cy, p.z || 0);
        return new THREE.Vector3(-offset.cx, p.y - offset.cy, p.z || 0);
      }
      return new THREE.Vector3(p.x, p.y, slab.elevation || 0);
    });
    const borderGeo = new THREE.BufferGeometry().setFromPoints(pts3d.concat(pts3d[0]));
    const borderMat = new THREE.LineBasicMaterial({ color: isDark ? 0x60a5fa : 0x3b82f6, linewidth: 2 });
    const border = new THREE.Line(borderGeo, borderMat);
    border.userData = { id: slab.id };
    canvas3d.slabsGroup.add(border);
  });
}

function drawLoads3D(isDark) {
  const nodes = canvas3d.viewMode === 'elevation' ? getElevNodes() : getLevelNodes();
  const levelNodeIds = new Set(nodes.map(n => n.id));
  const offset = getElevOffset();
  S.loads.filter(l => levelNodeIds.has(l.nodeId)).forEach(load => {
    const node = nodes.find(n => n.id === load.nodeId);
    if (!node) return;
    
    let nx, ny, nz;
    if (offset) {
      const isXAxis = canvas3d.elevType === 'xAxis';
      if (isXAxis) {
        nx = node.x - offset.cx;
        ny = -offset.cy;
      } else {
        nx = -offset.cx;
        ny = node.y - offset.cy;
      }
      nz = node.z || 0;
    } else {
      nx = node.x;
      ny = node.y;
      nz = node.z || 0;
    }
    
    // Project load onto the viewing plane
    let fx = load.fx || 0;
    let fy = load.fy || 0;
    let fz = load.fz || 0;
    
    if (canvas3d.viewMode === 'elevation') {
      if (canvas3d.elevType === 'xAxis') {
        fy = 0; // Y points into screen in X-axis elevation
      } else {
        fx = 0; // X points into screen in Y-axis elevation
      }
    }
    
    const mag = Math.sqrt(fx*fx + fy*fy + fz*fz);
    if (mag < 0.01) return;
    
    const dir = new THREE.Vector3(fx, fy, fz).divideScalar(mag);
    const arrowLen = (canvas3d.loadScale || 3.0);
    const shaftRadius = 0.18;
    const headLength = Math.min(0.7, arrowLen * 0.3);
    const headRadius = 0.4;
    
    // Arrow points toward the node (origin behind the node, shaft ends at node, head extends past)
    const start = new THREE.Vector3(nx, ny, nz).sub(dir.clone().multiplyScalar(arrowLen));
    
    // Shaft
    const shaftGeo = new THREE.CylinderGeometry(shaftRadius, shaftRadius, arrowLen - headLength, 8);
    const shaftMat = new THREE.MeshBasicMaterial({ color: 0xef4444 });
    const shaft = new THREE.Mesh(shaftGeo, shaftMat);
    shaft.position.copy(start);
    shaft.position.add(dir.clone().multiplyScalar((arrowLen - headLength) / 2));
    shaft.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir);
    canvas3d.loadsGroup.add(shaft);
    
    // Head
    const headGeo = new THREE.ConeGeometry(headRadius, headLength, 8);
    const headMat = new THREE.MeshBasicMaterial({ color: 0xef4444 });
    const head = new THREE.Mesh(headGeo, headMat);
    head.position.copy(start);
    head.position.add(dir.clone().multiplyScalar(arrowLen - headLength / 2));
    head.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir);
    canvas3d.loadsGroup.add(head);
  });
}

function drawMemberLoads3D(isDark) {
  if (!S.memberLoads || !S.memberLoads.length) return;

  const mode = canvas3d.viewMode;
  const members = mode === 'elevation' ? getElevMembers() : S.members;
  const offset = getElevOffset();
  const arrowScale = (canvas3d.loadScale || 3.0) / 3;

  S.memberLoads.forEach((ml) => {
    const member = members.find((m) => m.id === ml.memberId);
    if (!member) return;
    const n1 = S.nodes.find((n) => n.id === member.n1);
    const n2 = S.nodes.find((n) => n.id === member.n2);
    if (!n1 || !n2) return;

    // Get positions in offset coords
    let p1, p2;
    if (offset) {
      const isXAxis = canvas3d.elevType === 'xAxis';
      if (isXAxis) {
        p1 = new THREE.Vector3(n1.x - offset.cx, -offset.cy, n1.z || 0);
        p2 = new THREE.Vector3(n2.x - offset.cx, -offset.cy, n2.z || 0);
      } else {
        p1 = new THREE.Vector3(-offset.cx, n1.y - offset.cy, n1.z || 0);
        p2 = new THREE.Vector3(-offset.cx, n2.y - offset.cy, n2.z || 0);
      }
    } else {
      p1 = new THREE.Vector3(n1.x, n1.y, n1.z || 0);
      p2 = new THREE.Vector3(n2.x, n2.y, n2.z || 0);
    }

    const segDir = new THREE.Vector3().copy(p2).sub(p1);
    const segLen = segDir.length();
    if (segLen < 0.01) return;
    segDir.divideScalar(segLen);

    const numArrows = Math.max(2, Math.floor(segLen / 2));
    const step = segLen / (numArrows + 1);
    const arrowLen = 1.5 * arrowScale;
    const shaftRadius = 0.08 * arrowScale;
    const headLength = Math.min(0.4 * arrowScale, arrowLen * 0.3);
    const headRadius = 0.2 * arrowScale;

    // UDL direction: vertical down (-Z). In elevation mode, project onto viewing plane
    let udlDir = new THREE.Vector3(0, 0, -1);
    if (offset && canvas3d.viewMode === 'elevation') {
      if (canvas3d.elevType === 'xAxis') {
        udlDir = new THREE.Vector3(0, 0, -1); // Still -Z in X-axis elevation
      } else {
        udlDir = new THREE.Vector3(0, 0, -1); // Still -Z in Y-axis elevation
      }
    }

    for (let i = 1; i <= numArrows; i++) {
      const t = i * step;
      const pos = new THREE.Vector3().copy(p1).add(segDir.clone().multiplyScalar(t));

      // Arrow pointing downward from pos
      const start = new THREE.Vector3().copy(pos).sub(udlDir.clone().multiplyScalar(arrowLen));

      const shaftGeo = new THREE.CylinderGeometry(shaftRadius, shaftRadius, arrowLen - headLength, 6);
      const shaftMat = new THREE.MeshBasicMaterial({ color: 0xf97316 });
      const shaft = new THREE.Mesh(shaftGeo, shaftMat);
      shaft.position.copy(start);
      shaft.position.add(udlDir.clone().multiplyScalar((arrowLen - headLength) / 2));
      shaft.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), udlDir);
      canvas3d.loadsGroup.add(shaft);

      const headGeo = new THREE.ConeGeometry(headRadius, headLength, 6);
      const headMat = new THREE.MeshBasicMaterial({ color: 0xf97316 });
      const head = new THREE.Mesh(headGeo, headMat);
      head.position.copy(start);
      head.position.add(udlDir.clone().multiplyScalar(arrowLen - headLength / 2));
      head.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), udlDir);
      canvas3d.loadsGroup.add(head);
    }
  });
}

export function showProp() {
  const panel = byId('propPanel');
  if (!panel) return;

  if (!S.selected) {
    panel.innerHTML = '<p class="prop-hint">Select an element to edit its properties.</p>';
    return;
  }

  if (S.selected.type === 'node') {
    const node = S.nodes.find((item) => item.id === S.selected.id);
    if (!node) { panel.innerHTML = ''; return; }
    panel.innerHTML = `
      <div class="pf"><label>Node ${node.id}</label></div>
      <div class="pf"><label>X (m)</label><input type="number" value="${node.x}" step="0.5" id="px"/></div>
      <div class="pf"><label>Y (m)</label><input type="number" value="${node.y}" step="0.5" id="py"/></div>
      <div class="pf"><label>Z (m)</label><input type="number" value="${node.z||0}" step="0.5" id="pz"/></div>
      <div class="pf"><label>Support</label><select id="pSupp">
        <option value="free" ${node.support === 'free' ? 'selected' : ''}>Free</option>
        <option value="pin" ${node.support === 'pin' ? 'selected' : ''}>Pin</option>
        <option value="roller" ${node.support === 'roller' ? 'selected' : ''}>Roller</option>
        <option value="fixed" ${node.support === 'fixed' ? 'selected' : ''}>Fixed</option>
      </select></div>`;
    panel.querySelector('#px').addEventListener('change', (e) => { node.x = parseFloat(e.target.value); triggerRedraw(); });
    panel.querySelector('#py').addEventListener('change', (e) => { node.y = parseFloat(e.target.value); triggerRedraw(); });
    panel.querySelector('#pz').addEventListener('change', (e) => { node.z = parseFloat(e.target.value); triggerRedraw(); });
    panel.querySelector('#pSupp').addEventListener('change', (e) => { node.support = e.target.value; triggerRedraw(); });
  } else if (S.selected.type === 'member') {
    const member = S.members.find((item) => item.id === S.selected.id);
    if (!member) { panel.innerHTML = ''; return; }
    panel.innerHTML = `
      <div class="pf"><label>Member ${member.id} (${member.n1}-${member.n2})</label></div>
      <div class="pf"><label>Group</label><select id="mGroup">
        <option value="beam" ${(member.group || '') === 'beam' ? 'selected' : ''}>Beam</option>
        <option value="column" ${(member.group || '') === 'column' ? 'selected' : ''}>Column</option>
        <option value="brace" ${(member.group || '') === 'brace' ? 'selected' : ''}>Brace</option>
        <option value="member" ${(member.group || 'member') === 'member' ? 'selected' : ''}>Generic</option>
      </select></div>
      <div class="pf"><label>A (m2)</label><input type="text" value="${member.A}" id="mA"/></div>
      <div class="pf"><label>Iy (m4)</label><input type="text" value="${member.Iy||1e-4}" id="mIy"/></div>
      <div class="pf"><label>Iz (m4)</label><input type="text" value="${member.Iz||1e-4}" id="mIz"/></div>
      <div class="pf"><label>E (GPa)</label><input type="number" value="${member.E}" step="1" id="mE"/></div>`;
    panel.querySelector('#mGroup').addEventListener('change', (e) => { member.group = e.target.value; triggerRedraw(); });
    panel.querySelector('#mA').addEventListener('change', (e) => { member.A = parseFloat(e.target.value); });
    panel.querySelector('#mIy').addEventListener('change', (e) => { member.Iy = parseFloat(e.target.value); });
    panel.querySelector('#mIz').addEventListener('change', (e) => { member.Iz = parseFloat(e.target.value); });
    panel.querySelector('#mE').addEventListener('change', (e) => { member.E = parseFloat(e.target.value); });
  } else if (S.selected.type === 'slab') {
    const slab = S.slabs.find((item) => item.id === S.selected.id);
    if (!slab) { panel.innerHTML = ''; return; }
    panel.innerHTML = `
      <div class="pf"><label>Slab ${slab.id}</label></div>
      <div class="pf"><label>Nodes</label><span>${(slab.nodeIds || []).join(', ')}</span></div>
      <div class="pf"><label>Thickness (m)</label><input type="number" value="${slab.thickness || 0.15}" step="0.01" id="sThk"/></div>
      <div class="pf"><label>Elevation (m)</label><input type="number" value="${slab.elevation || 0}" step="0.1" id="sElev"/></div>
      <div class="pf"><label>Area Load (kN/m²)</label><input type="number" value="${slab.areaLoad || 0}" step="0.5" id="sLoad"/></div>`;
    panel.querySelector('#sThk').addEventListener('change', (e) => { slab.thickness = parseFloat(e.target.value) || 0.15; triggerRedraw(); });
    panel.querySelector('#sElev').addEventListener('change', (e) => { slab.elevation = parseFloat(e.target.value) || 0; triggerRedraw(); });
    panel.querySelector('#sLoad').addEventListener('change', (e) => { slab.areaLoad = parseFloat(e.target.value) || 0; });
  }
}

function drawMemberForceOverlay3D() {
  const summaries = S.results.member_force_summary || {};
  const values = Object.values(summaries).map(s => Math.max(s.max_abs_moment_y_kn_m || 0, s.max_abs_moment_z_kn_m || 0, s.max_abs_axial_kn || 0));
  const maxVal = Math.max(...values, 1e-9);

  S.members.forEach((member) => {
    const summary = summaries[String(member.id)] || summaries[member.id];
    if (!summary) return;
    const n1 = S.nodes.find((n) => n.id === member.n1);
    const n2 = S.nodes.find((n) => n.id === member.n2);
    if (!n1 || !n2) return;

    const demand = Math.max(summary.max_abs_moment_y_kn_m || 0, summary.max_abs_moment_z_kn_m || 0, summary.max_abs_axial_kn || 0);
    if (demand <= 0) return;
    const ratio = Math.min(demand / maxVal, 1);
    const color = colorForRatioHex(ratio);
    const radius = 0.08 + ratio * 0.16;

    const v1 = new THREE.Vector3(n1.x, n1.y, n1.z || 0);
    const v2 = new THREE.Vector3(n2.x, n2.y, n2.z || 0);
    const distance = v1.distanceTo(v2);
    if (distance <= 0) return;

    const geo = new THREE.CylinderGeometry(radius, radius, distance, 10);
    geo.translate(0, distance / 2, 0);
    geo.rotateX(Math.PI / 2);
    const mat = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.42, depthWrite: false });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.copy(v1);
    mesh.lookAt(v2);
    canvas3d.membersGroup.add(mesh);
  });

  activeLegend = {
    title: 'Member demand (max |M| / |N|)',
    unit: 'kN·m / kN',
    min: 0,
    max: maxVal,
  };
}

function drawStoryDriftOverlay3D() {
  const drifts = S.results.story_response?.story_drifts || [];
  if (!drifts.length) return;
  const offset = getElevOffset();

  S.members.forEach((member) => {
    const n1 = S.nodes.find((node) => node.id === member.n1);
    const n2 = S.nodes.find((node) => node.id === member.n2);
    if (!n1 || !n2) return;
    const midpointZ = ((n1.z || 0) + (n2.z || 0)) / 2;
    const drift = drifts.find((item) => midpointZ > item.from_m - 1e-6 && midpointZ <= item.to_m + 1e-6);
    if (!drift) return;

    const demandRatio = drift.drift_ratio_delta_over_h ?? (drift.drift_ratio ? 1 / drift.drift_ratio : 0);
    const utilization = Math.max(0, demandRatio / 0.02);
    const color = colorForRatioHex(Math.min(utilization, 1));
    const opacity = 0.35 + Math.min(utilization, 1) * 0.25;

    let v1;
    let v2;
    if (offset) {
      const xAxis = canvas3d.elevType === 'xAxis';
      v1 = xAxis
        ? new THREE.Vector3(n1.x - offset.cx, -offset.cy, n1.z || 0)
        : new THREE.Vector3(-offset.cx, n1.y - offset.cy, n1.z || 0);
      v2 = xAxis
        ? new THREE.Vector3(n2.x - offset.cx, -offset.cy, n2.z || 0)
        : new THREE.Vector3(-offset.cx, n2.y - offset.cy, n2.z || 0);
    } else {
      v1 = new THREE.Vector3(n1.x, n1.y, n1.z || 0);
      v2 = new THREE.Vector3(n2.x, n2.y, n2.z || 0);
    }
    const distance = v1.distanceTo(v2);
    if (distance <= 0) return;

    const geometry = new THREE.CylinderGeometry(0.18, 0.18, distance, 10);
    geometry.translate(0, distance / 2, 0);
    geometry.rotateX(Math.PI / 2);
    const material = new THREE.MeshBasicMaterial({ color, transparent: true, opacity, depthWrite: false });
    const mesh = new THREE.Mesh(geometry, material);
    mesh.position.copy(v1);
    mesh.lookAt(v2);
    mesh.userData = { id: member.id, driftUtilization: utilization };
    canvas3d.membersGroup.add(mesh);
  });

  activeLegend = {
    title: 'Story drift utilization',
    unit: 'Δ/h / 0.02',
    min: 0,
    max: 1,
    marks: [
      { at: 0.5, label: '50%' },
      { at: 1.0, label: '100%' },
    ],
  };
}

function drawDeformedShape3D(isDark) {
  const scaleEl = byId('deformScale');
  const scaleFactor = scaleEl ? parseFloat(scaleEl.value) : 100;
  const scale = scaleFactor / 1000.0;

  const getDefNode = (nodeId) => {
    const node = S.nodes.find(n => n.id === nodeId);
    if (!node) return null;
    let dx = 0, dy = 0, dz = 0;
    if (S.results.displacements && S.results.displacements[nodeId]) {
      const d = S.results.displacements[nodeId];
      dx = d[0]; dy = d[1]; dz = d[2];
    } else if (S.results.node_displacements && S.results.node_displacements[nodeId]) {
      const d = S.results.node_displacements[nodeId];
      dx = d.dx_mm; dy = d.dy_mm;
    }
    return { x: node.x + dx * scale, y: node.y + dy * scale, z: (node.z || 0) + dz * scale };
  };

  S.members.forEach((member) => {
    const n1 = getDefNode(member.n1);
    const n2 = getDefNode(member.n2);
    if (!n1 || !n2) return;

    const v1 = new THREE.Vector3(n1.x, n1.y, n1.z);
    const v2 = new THREE.Vector3(n2.x, n2.y, n2.z);
    const distance = v1.distanceTo(v2);
    if (distance <= 0) return;

    const geo = new THREE.CylinderGeometry(0.05, 0.05, distance, 8);
    geo.translate(0, distance / 2, 0);
    geo.rotateX(Math.PI / 2);

    const mat = new THREE.MeshBasicMaterial({ color: 0xef4444, transparent: true, opacity: 0.6 });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.copy(v1);
    mesh.lookAt(v2);
    canvas3d.membersGroup.add(mesh);
  });
}
