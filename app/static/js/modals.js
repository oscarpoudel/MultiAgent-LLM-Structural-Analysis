import { byId } from './dom.js';
import { S } from './state.js';

let draw;

export function initModals(canvasDraw) {
  draw = canvasDraw;
}

function openModal(title, bodyHtml, onOk) {
  const overlay = byId('modalOverlay');
  const modal = byId('modal');
  byId('modalTitle').textContent = title;
  byId('modalBody').innerHTML = bodyHtml;
  overlay.classList.remove('hidden');
  byId('modalOk').onclick = () => {
    onOk(modal);
    overlay.classList.add('hidden');
    draw();
  };
  byId('modalCancel').onclick = () => overlay.classList.add('hidden');
}

export function showSupportModal(node) {
  openModal(`Set Support - Node ${node.id}`, `
    <div class="modal-opts">
      <label class="modal-opt"><input type="radio" name="sup" value="free" ${node.support === 'free' ? 'checked' : ''}/> Free</label>
      <label class="modal-opt"><input type="radio" name="sup" value="pin" ${node.support === 'pin' ? 'checked' : ''}/> Pin</label>
      <label class="modal-opt"><input type="radio" name="sup" value="roller" ${node.support === 'roller' || node.support === 'roller_x' ? 'checked' : ''}/> Roller</label>
      <label class="modal-opt"><input type="radio" name="sup" value="fixed" ${node.support === 'fixed' ? 'checked' : ''}/> Fixed</label>
    </div>`, (modal) => {
    const selected = modal.querySelector('input[name=sup]:checked');
    if (selected) node.support = selected.value;
  });
}

export function showLoadModal(node) {
  const existing = S.loads.find((load) => load.nodeId === node.id) || { fx: 0, fy: 0, moment: 0 };
  openModal(`Apply Load - Node ${node.id}`, `
    <div class="pf"><label>Fx (kN, +right)</label><input type="number" value="${existing.fx}" step="1" id="lfx"/></div>
    <div class="pf"><label>Fy (kN, +up)</label><input type="number" value="${existing.fy}" step="1" id="lfy"/></div>
    <div class="pf"><label>Moment (kN-m)</label><input type="number" value="${existing.moment}" step="1" id="lm"/></div>
  `, (modal) => {
    const fx = parseFloat(modal.querySelector('#lfx').value) || 0;
    const fy = parseFloat(modal.querySelector('#lfy').value) || 0;
    const moment = parseFloat(modal.querySelector('#lm').value) || 0;
    S.loads = S.loads.filter((load) => load.nodeId !== node.id);
    if (Math.abs(fx) > 0.001 || Math.abs(fy) > 0.001 || Math.abs(moment) > 0.001) {
      S.loads.push({ nodeId: node.id, fx, fy, moment });
    }
  });
}

export function showMemberLoadModal(member) {
  const existing = S.memberLoads.find((memberLoad) => memberLoad.memberId === member.id) || { udl: 0 };
  openModal(`Distributed Load - Member ${member.id}`, `
    <div class="pf"><label>UDL (kN/m, +down)</label><input type="number" value="${existing.udl}" step="1" id="mudl"/></div>
  `, (modal) => {
    const udl = parseFloat(modal.querySelector('#mudl').value) || 0;
    S.memberLoads = S.memberLoads.filter((memberLoad) => memberLoad.memberId !== member.id);
    if (Math.abs(udl) > 0.001) S.memberLoads.push({ memberId: member.id, udl });
  });
}
