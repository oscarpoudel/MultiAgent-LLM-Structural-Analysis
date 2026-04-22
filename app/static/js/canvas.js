import { byId, $$ } from './dom.js';
import { GRID, NODE_R, S, SNAP_R } from './state.js';

let canvas;
let ctx;
let showSupportModal;
let showLoadModal;
let showMemberLoadModal;

export function initCanvas(modals) {
  canvas = byId('canvas');
  ctx = canvas.getContext('2d');
  showSupportModal = modals.showSupportModal;
  showLoadModal = modals.showLoadModal;
  showMemberLoadModal = modals.showMemberLoadModal;

  initToolButtons();
  initCanvasEvents();
  initDisplayToggles();
  updateStatus();

  window.addEventListener('resize', resizeCanvas);
  setTimeout(resizeCanvas, 50);
}

export function resizeCanvas() {
  const wrap = canvas.parentElement;
  canvas.width = wrap.clientWidth;
  canvas.height = wrap.clientHeight;
  draw();
}

export function fitModelToCanvas() {
  if (!S.nodes.length) {
    S.pan = { x: 0, y: 0 };
    S.zoom = 40;
    draw();
    return;
  }

  const xs = S.nodes.map((node) => node.x);
  const ys = S.nodes.map((node) => node.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const widthM = Math.max(maxX - minX, 1);
  const heightM = Math.max(maxY - minY, 1);
  const availableWidth = Math.max(canvas.width - 180, 120);
  const availableHeight = Math.max(canvas.height - 160, 120);

  S.zoom = Math.max(30, Math.min(140, Math.min(availableWidth / widthM, availableHeight / heightM)));
  const centerX = (minX + maxX) / 2;
  const centerY = (minY + maxY) / 2;
  S.pan.x = -centerX * S.zoom;
  S.pan.y = centerY * S.zoom;
  draw();
}

export function draw() {
  const width = canvas.width;
  const height = canvas.height;
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = isDark ? '#0f1419' : '#f8fafb';
  ctx.fillRect(0, 0, width, height);

  if (byId('showGrid').checked) drawGrid(isDark);
  if (byId('showDeformed').checked && S.results) drawDeformed();

  drawMembers(isDark);
  drawMemberLoads();
  drawNodes(isDark);
  drawLoads();
  drawMemberStartHint();
  drawReactions();
}

function worldToScreen(wx, wy) {
  const cx = canvas.width / 2;
  const cy = canvas.height / 2;
  return { x: cx + wx * S.zoom + S.pan.x, y: cy - wy * S.zoom + S.pan.y };
}

function screenToWorld(sx, sy) {
  const cx = canvas.width / 2;
  const cy = canvas.height / 2;
  return { x: (sx - cx - S.pan.x) / S.zoom, y: -(sy - cy - S.pan.y) / S.zoom };
}

function snap(value) {
  return Math.round(value / GRID) * GRID;
}

function snapWorld(wx, wy) {
  return { x: snap(wx), y: snap(wy) };
}

function drawMembers(isDark) {
  S.members.forEach((member) => {
    const n1 = S.nodes.find((node) => node.id === member.n1);
    const n2 = S.nodes.find((node) => node.id === member.n2);
    if (!n1 || !n2) return;

    const p1 = worldToScreen(n1.x, n1.y);
    const p2 = worldToScreen(n2.x, n2.y);
    const isSelected = S.selected && S.selected.type === 'member' && S.selected.id === member.id;

    ctx.beginPath();
    ctx.moveTo(p1.x, p1.y);
    ctx.lineTo(p2.x, p2.y);
    ctx.strokeStyle = isSelected ? '#f59e0b' : isDark ? '#60a5fa' : '#2563eb';
    ctx.lineWidth = isSelected ? 4 : 2.5;
    ctx.stroke();

    if (byId('showForces').checked && S.results) {
      const memberForce = S.results.member_forces && S.results.member_forces[String(member.id)];
      if (memberForce) {
        const midpoint = { x: (p1.x + p2.x) / 2, y: (p1.y + p2.y) / 2 };
        const axial = memberForce.axial_kn || memberForce.axial_start_kn || 0;
        ctx.font = '600 11px Inter,sans-serif';
        ctx.fillStyle = axial > 0.01 ? '#22c55e' : axial < -0.01 ? '#ef4444' : '#888';
        ctx.textAlign = 'center';
        ctx.fillText(`${axial > 0 ? 'T ' : axial < 0 ? 'C ' : ''}${Math.abs(axial).toFixed(1)} kN`, midpoint.x, midpoint.y - 8);
      }
    }

    if (byId('showLabels').checked) {
      const midpoint = { x: (p1.x + p2.x) / 2, y: (p1.y + p2.y) / 2 };
      ctx.font = '500 10px Inter,sans-serif';
      ctx.fillStyle = isDark ? '#64748b' : '#94a3b8';
      ctx.textAlign = 'center';
      ctx.fillText(`M${member.id}`, midpoint.x, midpoint.y + 14);
    }
  });
}

function drawMemberLoads() {
  S.memberLoads.forEach((memberLoad) => {
    const member = S.members.find((item) => item.id === memberLoad.memberId);
    if (!member) return;
    const n1 = S.nodes.find((node) => node.id === member.n1);
    const n2 = S.nodes.find((node) => node.id === member.n2);
    if (!n1 || !n2) return;

    const p1 = worldToScreen(n1.x, n1.y);
    const p2 = worldToScreen(n2.x, n2.y);
    const nArrows = 5;
    for (let i = 0; i <= nArrows; i += 1) {
      const t = i / nArrows;
      const ax = p1.x + (p2.x - p1.x) * t;
      const ay = p1.y + (p2.y - p1.y) * t;
      drawArrow(ax, ay - 25, ax, ay - 5, '#a855f7', 1.5);
    }
    ctx.font = '600 10px Inter,sans-serif';
    ctx.fillStyle = '#a855f7';
    ctx.textAlign = 'center';
    ctx.fillText(`${Math.abs(memberLoad.udl).toFixed(1)} kN/m`, (p1.x + p2.x) / 2, (p1.y + p2.y) / 2 - 30);
  });
}

function drawNodes(isDark) {
  S.nodes.forEach((node) => {
    const p = worldToScreen(node.x, node.y);
    const isSelected = S.selected && S.selected.type === 'node' && S.selected.id === node.id;
    drawSupport(p.x, p.y, node.support, isDark);

    ctx.beginPath();
    ctx.arc(p.x, p.y, NODE_R, 0, Math.PI * 2);
    ctx.fillStyle = isSelected ? '#f59e0b' : isDark ? '#e2e8f0' : '#1e293b';
    ctx.fill();
    ctx.strokeStyle = isDark ? '#334155' : '#cbd5e1';
    ctx.lineWidth = 1.5;
    ctx.stroke();

    if (byId('showLabels').checked) {
      ctx.font = '600 11px Inter,sans-serif';
      ctx.fillStyle = isDark ? '#94a3b8' : '#475569';
      ctx.textAlign = 'center';
      ctx.fillText(node.id, p.x, p.y - 14);
      ctx.font = '400 9px Inter,sans-serif';
      ctx.fillStyle = isDark ? '#64748b' : '#94a3b8';
      ctx.fillText(`(${node.x.toFixed(1)}, ${node.y.toFixed(1)})`, p.x, p.y - 24);
    }
  });
}

function drawLoads() {
  S.loads.forEach((load) => {
    const node = S.nodes.find((item) => item.id === load.nodeId);
    if (!node) return;
    const p = worldToScreen(node.x, node.y);
    const scale = 30;
    if (Math.abs(load.fy) > 0.01) {
      const dir = load.fy < 0 ? 1 : -1;
      drawArrow(p.x, p.y - dir * scale, p.x, p.y, '#ef4444', 2.5);
      ctx.font = '700 11px Inter,sans-serif';
      ctx.fillStyle = '#ef4444';
      ctx.textAlign = 'center';
      ctx.fillText(`${Math.abs(load.fy).toFixed(1)} kN`, p.x, p.y - dir * scale - 6 * dir);
    }
    if (Math.abs(load.fx) > 0.01) {
      const dir = load.fx > 0 ? 1 : -1;
      drawArrow(p.x + dir * scale, p.y, p.x, p.y, '#3b82f6', 2.5);
      ctx.font = '700 11px Inter,sans-serif';
      ctx.fillStyle = '#3b82f6';
      ctx.textAlign = 'center';
      ctx.fillText(`${Math.abs(load.fx).toFixed(1)} kN`, p.x + dir * (scale + 18), p.y - 4);
    }
  });
}

function drawMemberStartHint() {
  if (S.tool !== 'member' || S.memberStart === null) return;
  const node = S.nodes.find((item) => item.id === S.memberStart);
  if (!node) return;
  const p = worldToScreen(node.x, node.y);
  ctx.beginPath();
  ctx.arc(p.x, p.y, NODE_R + 4, 0, Math.PI * 2);
  ctx.strokeStyle = '#22c55e';
  ctx.lineWidth = 2;
  ctx.setLineDash([4, 3]);
  ctx.stroke();
  ctx.setLineDash([]);
}

function drawReactions() {
  if (!byId('showForces').checked || !S.results || !S.results.reactions) return;
  Object.entries(S.results.reactions).forEach(([nodeId, reaction]) => {
    const node = S.nodes.find((item) => item.id === parseInt(nodeId, 10));
    if (!node) return;
    const p = worldToScreen(node.x, node.y);
    const lines = [];
    if (Math.abs(reaction.rx_kn || 0) > 0.01) lines.push(`Rx=${reaction.rx_kn.toFixed(1)} kN`);
    if (Math.abs(reaction.ry_kn || 0) > 0.01) lines.push(`Ry=${reaction.ry_kn.toFixed(1)} kN`);
    if (Math.abs(reaction.mz_kn_m || 0) > 0.01) lines.push(`M=${reaction.mz_kn_m.toFixed(1)} kN-m`);
    ctx.font = '600 10px Inter,sans-serif';
    ctx.fillStyle = '#22c55e';
    ctx.textAlign = 'center';
    lines.forEach((line, index) => ctx.fillText(line, p.x, p.y + 22 + index * 13));
  });
}

function drawGrid(isDark) {
  const minW = screenToWorld(0, canvas.height);
  const maxW = screenToWorld(canvas.width, 0);
  ctx.strokeStyle = isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.05)';
  ctx.lineWidth = 1;
  for (let x = Math.floor(minW.x / GRID) * GRID; x <= maxW.x; x += GRID) {
    const p = worldToScreen(x, 0);
    ctx.beginPath();
    ctx.moveTo(p.x, 0);
    ctx.lineTo(p.x, canvas.height);
    ctx.stroke();
  }
  for (let y = Math.floor(minW.y / GRID) * GRID; y <= maxW.y; y += GRID) {
    const p = worldToScreen(0, y);
    ctx.beginPath();
    ctx.moveTo(0, p.y);
    ctx.lineTo(canvas.width, p.y);
    ctx.stroke();
  }
  const origin = worldToScreen(0, 0);
  ctx.strokeStyle = isDark ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.12)';
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(0, origin.y);
  ctx.lineTo(canvas.width, origin.y);
  ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(origin.x, 0);
  ctx.lineTo(origin.x, canvas.height);
  ctx.stroke();
}

function drawSupport(px, py, type, isDark) {
  const size = 14;
  ctx.save();
  ctx.strokeStyle = isDark ? '#34d399' : '#059669';
  ctx.fillStyle = isDark ? 'rgba(52,211,153,0.15)' : 'rgba(5,150,105,0.1)';
  ctx.lineWidth = 2;
  if (type === 'pin') {
    ctx.beginPath();
    ctx.moveTo(px, py);
    ctx.lineTo(px - size, py + size);
    ctx.lineTo(px + size, py + size);
    ctx.closePath();
    ctx.stroke();
    ctx.fill();
    for (let i = -1; i <= 1; i += 1) {
      ctx.beginPath();
      ctx.moveTo(px + i * size - 3, py + size);
      ctx.lineTo(px + i * size - 8, py + size + 6);
      ctx.stroke();
    }
  } else if (type === 'roller' || type === 'roller_x') {
    ctx.beginPath();
    ctx.moveTo(px, py);
    ctx.lineTo(px - size, py + size);
    ctx.lineTo(px + size, py + size);
    ctx.closePath();
    ctx.stroke();
    ctx.fill();
    ctx.beginPath();
    ctx.arc(px - size / 2, py + size + 5, 4, 0, Math.PI * 2);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(px + size / 2, py + size + 5, 4, 0, Math.PI * 2);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(px - size - 2, py + size + 10);
    ctx.lineTo(px + size + 2, py + size + 10);
    ctx.stroke();
  } else if (type === 'fixed') {
    ctx.fillStyle = isDark ? 'rgba(52,211,153,0.2)' : 'rgba(5,150,105,0.15)';
    ctx.fillRect(px - size - 2, py - size, 6, size * 2);
    ctx.beginPath();
    ctx.moveTo(px - size + 4, py - size);
    ctx.lineTo(px - size + 4, py + size);
    ctx.stroke();
    for (let i = -2; i <= 2; i += 1) {
      ctx.beginPath();
      ctx.moveTo(px - size + 4, py + i * 6);
      ctx.lineTo(px - size - 4, py + i * 6 + 6);
      ctx.stroke();
    }
  }
  ctx.restore();
}

function drawArrow(x1, y1, x2, y2, color, lineWidth) {
  const dx = x2 - x1;
  const dy = y2 - y1;
  const length = Math.sqrt(dx * dx + dy * dy);
  if (length < 2) return;
  const ux = dx / length;
  const uy = dy / length;
  ctx.beginPath();
  ctx.moveTo(x1, y1);
  ctx.lineTo(x2, y2);
  ctx.strokeStyle = color;
  ctx.lineWidth = lineWidth;
  ctx.stroke();
  const headLength = 8;
  const headWidth = 4;
  ctx.beginPath();
  ctx.moveTo(x2, y2);
  ctx.lineTo(x2 - ux * headLength + uy * headWidth, y2 - uy * headLength - ux * headWidth);
  ctx.lineTo(x2 - ux * headLength - uy * headWidth, y2 - uy * headLength + ux * headWidth);
  ctx.closePath();
  ctx.fillStyle = color;
  ctx.fill();
}

function drawDeformed() {
  if (!S.results || !S.results.node_displacements) return;
  const scale = 200;
  ctx.save();
  ctx.globalAlpha = 0.5;
  S.members.forEach((member) => {
    const n1 = S.nodes.find((node) => node.id === member.n1);
    const n2 = S.nodes.find((node) => node.id === member.n2);
    if (!n1 || !n2) return;
    const d1 = S.results.node_displacements[String(n1.id)];
    const d2 = S.results.node_displacements[String(n2.id)];
    if (!d1 || !d2) return;
    const p1 = worldToScreen(n1.x + ((d1.dx_mm || 0) / 1000) * scale, n1.y + ((d1.dy_mm || 0) / 1000) * scale);
    const p2 = worldToScreen(n2.x + ((d2.dx_mm || 0) / 1000) * scale, n2.y + ((d2.dy_mm || 0) / 1000) * scale);
    ctx.beginPath();
    ctx.moveTo(p1.x, p1.y);
    ctx.lineTo(p2.x, p2.y);
    ctx.strokeStyle = '#f97316';
    ctx.lineWidth = 2;
    ctx.setLineDash([6, 4]);
    ctx.stroke();
    ctx.setLineDash([]);
  });
  ctx.restore();
}

function initToolButtons() {
  $$('.tool-btn').forEach((button) => {
    button.addEventListener('click', () => {
      $$('.tool-btn').forEach((item) => item.classList.remove('active'));
      button.classList.add('active');
      S.tool = button.dataset.tool;
      S.memberStart = null;
      canvas.style.cursor = S.tool === 'select' ? 'default' : 'crosshair';
      updateStatus();
    });
  });
}

function updateStatus() {
  const el = byId('canvasStatus');
  const messages = {
    select: 'Click a node or member to select. Drag to move nodes. Right-click + drag to pan.',
    node: 'Click on canvas to place a node. Snaps to 0.5m grid.',
    member: S.memberStart ? `Click a second node to finish member (from node ${S.memberStart}).` : 'Click first node to start a member.',
    support: 'Click a node to set its support type.',
    load: 'Click a node to apply a load.',
    delete: 'Click a node or member to delete it.',
  };
  el.textContent = messages[S.tool] || 'Ready';
}

function findNodeAt(sx, sy) {
  let best = null;
  let bestDistance = SNAP_R;
  S.nodes.forEach((node) => {
    const p = worldToScreen(node.x, node.y);
    const distance = Math.sqrt((p.x - sx) ** 2 + (p.y - sy) ** 2);
    if (distance < bestDistance) {
      bestDistance = distance;
      best = node;
    }
  });
  return best;
}

function findMemberAt(sx, sy) {
  let best = null;
  let bestDistance = 10;
  S.members.forEach((member) => {
    const n1 = S.nodes.find((node) => node.id === member.n1);
    const n2 = S.nodes.find((node) => node.id === member.n2);
    if (!n1 || !n2) return;
    const p1 = worldToScreen(n1.x, n1.y);
    const p2 = worldToScreen(n2.x, n2.y);
    const distance = distPointToSeg(sx, sy, p1.x, p1.y, p2.x, p2.y);
    if (distance < bestDistance) {
      bestDistance = distance;
      best = member;
    }
  });
  return best;
}

function distPointToSeg(px, py, ax, ay, bx, by) {
  const dx = bx - ax;
  const dy = by - ay;
  const l2 = dx * dx + dy * dy;
  if (l2 === 0) return Math.sqrt((px - ax) ** 2 + (py - ay) ** 2);
  const t = Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / l2));
  return Math.sqrt((px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2);
}

function initCanvasEvents() {
  canvas.addEventListener('mousedown', (event) => {
    const rect = canvas.getBoundingClientRect();
    const sx = event.clientX - rect.left;
    const sy = event.clientY - rect.top;

    if (event.button === 2) {
      S.dragging = true;
      S.dragStart = { x: event.clientX, y: event.clientY, px: S.pan.x, py: S.pan.y };
      canvas.style.cursor = 'grabbing';
      return;
    }

    const world = screenToWorld(sx, sy);
    const snapped = snapWorld(world.x, world.y);

    if (S.tool === 'select') {
      selectElement(sx, sy);
    } else if (S.tool === 'node') {
      addNode(snapped);
    } else if (S.tool === 'member') {
      addMember(sx, sy);
    } else if (S.tool === 'support') {
      const node = findNodeAt(sx, sy);
      if (node) showSupportModal(node);
    } else if (S.tool === 'load') {
      const node = findNodeAt(sx, sy);
      if (node) showLoadModal(node);
      else {
        const member = findMemberAt(sx, sy);
        if (member) showMemberLoadModal(member);
      }
    } else if (S.tool === 'delete') {
      deleteElement(sx, sy);
    }
  });

  canvas.addEventListener('mousemove', (event) => {
    if (S.dragging && S.dragStart) {
      S.pan.x = S.dragStart.px + (event.clientX - S.dragStart.x);
      S.pan.y = S.dragStart.py + (event.clientY - S.dragStart.y);
      draw();
      return;
    }
    if (S.dragNode !== null && S.tool === 'select') {
      const rect = canvas.getBoundingClientRect();
      const world = screenToWorld(event.clientX - rect.left, event.clientY - rect.top);
      const snapped = snapWorld(world.x, world.y);
      const node = S.nodes.find((item) => item.id === S.dragNode);
      if (node) {
        node.x = snapped.x;
        node.y = snapped.y;
        draw();
      }
    }
  });

  canvas.addEventListener('mouseup', () => {
    S.dragging = false;
    S.dragStart = null;
    S.dragNode = null;
    if (S.tool === 'select') canvas.style.cursor = 'default';
  });

  canvas.addEventListener('contextmenu', (event) => event.preventDefault());
  canvas.addEventListener('wheel', (event) => {
    event.preventDefault();
    const factor = event.deltaY < 0 ? 1.1 : 0.9;
    S.zoom = Math.max(10, Math.min(200, S.zoom * factor));
    draw();
  }, { passive: false });
}

function selectElement(sx, sy) {
  const node = findNodeAt(sx, sy);
  if (node) {
    S.selected = { type: 'node', id: node.id };
    S.dragNode = node.id;
    showProp();
    draw();
    return;
  }

  const member = findMemberAt(sx, sy);
  if (member) {
    S.selected = { type: 'member', id: member.id };
    showProp();
    draw();
    return;
  }

  S.selected = null;
  showProp();
  draw();
}

function addNode(snapped) {
  const duplicate = S.nodes.find((node) => Math.abs(node.x - snapped.x) < 0.01 && Math.abs(node.y - snapped.y) < 0.01);
  if (!duplicate) {
    S.nodes.push({ id: S.nextNodeId, x: snapped.x, y: snapped.y, support: 'free' });
    S.nextNodeId += 1;
    draw();
  }
}

function addMember(sx, sy) {
  const node = findNodeAt(sx, sy);
  if (!node) return;
  if (S.memberStart === null) {
    S.memberStart = node.id;
    updateStatus();
    draw();
    return;
  }
  if (node.id === S.memberStart) {
    S.memberStart = null;
    updateStatus();
    return;
  }
  const duplicate = S.members.find((member) => (
    (member.n1 === S.memberStart && member.n2 === node.id) ||
    (member.n1 === node.id && member.n2 === S.memberStart)
  ));
  if (!duplicate) {
    S.members.push({ id: S.nextMemberId, n1: S.memberStart, n2: node.id, A: 0.01, I: 1e-4, E: 200 });
    S.nextMemberId += 1;
  }
  S.memberStart = null;
  updateStatus();
  draw();
}

function deleteElement(sx, sy) {
  const node = findNodeAt(sx, sy);
  if (node) {
    S.members = S.members.filter((member) => member.n1 !== node.id && member.n2 !== node.id);
    S.loads = S.loads.filter((load) => load.nodeId !== node.id);
    S.nodes = S.nodes.filter((item) => item.id !== node.id);
    S.selected = null;
    showProp();
    draw();
    return;
  }

  const member = findMemberAt(sx, sy);
  if (member) {
    S.members = S.members.filter((item) => item.id !== member.id);
    S.memberLoads = S.memberLoads.filter((memberLoad) => memberLoad.memberId !== member.id);
    S.selected = null;
    showProp();
    draw();
  }
}

export function showProp() {
  const panel = byId('propPanel');
  if (!S.selected) {
    panel.innerHTML = '<p class="prop-hint">Select an element to edit.</p>';
    return;
  }

  if (S.selected.type === 'node') {
    const node = S.nodes.find((item) => item.id === S.selected.id);
    if (!node) {
      panel.innerHTML = '';
      return;
    }
    panel.innerHTML = `
      <div class="pf"><label>Node ${node.id}</label></div>
      <div class="pf"><label>X (m)</label><input type="number" value="${node.x}" step="0.5" id="px"/></div>
      <div class="pf"><label>Y (m)</label><input type="number" value="${node.y}" step="0.5" id="py"/></div>
      <div class="pf"><label>Support</label><select id="pSupp">
        <option value="free" ${node.support === 'free' ? 'selected' : ''}>Free</option>
        <option value="pin" ${node.support === 'pin' ? 'selected' : ''}>Pin</option>
        <option value="roller" ${node.support === 'roller' || node.support === 'roller_x' ? 'selected' : ''}>Roller</option>
        <option value="fixed" ${node.support === 'fixed' ? 'selected' : ''}>Fixed</option>
      </select></div>`;
    panel.querySelector('#px').addEventListener('change', (event) => {
      node.x = parseFloat(event.target.value);
      draw();
    });
    panel.querySelector('#py').addEventListener('change', (event) => {
      node.y = parseFloat(event.target.value);
      draw();
    });
    panel.querySelector('#pSupp').addEventListener('change', (event) => {
      node.support = event.target.value;
      draw();
    });
  } else if (S.selected.type === 'member') {
    const member = S.members.find((item) => item.id === S.selected.id);
    if (!member) {
      panel.innerHTML = '';
      return;
    }
    panel.innerHTML = `
      <div class="pf"><label>Member ${member.id} (${member.n1}-${member.n2})</label></div>
      <div class="pf"><label>A (m2)</label><input type="text" value="${member.A}" id="mA"/></div>
      <div class="pf"><label>I (m4)</label><input type="text" value="${member.I}" id="mI"/></div>
      <div class="pf"><label>E (GPa)</label><input type="number" value="${member.E}" step="1" id="mE"/></div>`;
    panel.querySelector('#mA').addEventListener('change', (event) => {
      member.A = parseFloat(event.target.value);
    });
    panel.querySelector('#mI').addEventListener('change', (event) => {
      member.I = parseFloat(event.target.value);
    });
    panel.querySelector('#mE').addEventListener('change', (event) => {
      member.E = parseFloat(event.target.value);
    });
  }
}

function initDisplayToggles() {
  ['showGrid', 'showLabels', 'showDeformed', 'showForces'].forEach((id) => {
    byId(id).addEventListener('change', draw);
  });
}
