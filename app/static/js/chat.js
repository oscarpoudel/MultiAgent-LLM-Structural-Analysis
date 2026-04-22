import { sendChat } from './api.js';
import { buildCurrentAnalysisPayload, clearCurrentModel, drawSimpleBeam } from './analysis.js';
import { byId } from './dom.js';
import { renderResults } from './results.js';
import { S } from './state.js';

const EXAMPLES = {
  ss: 'Analyze a simply supported steel beam. Span is 6 m, uniform load is 20 kN/m, E is 200 GPa, I is 8e-6 m4. Check deflection against L/360.',
  cant: 'Analyze a cantilever beam with span 4 m, UDL 15 kN/m, E 200 GPa, I 5e-5 m4. Check deflection against L/180.',
  pt: 'Analyze a simply supported beam with span 8 m and a point load of 100 kN at 4 m. E is 200 GPa, I is 3e-5 m4.',
  truss: 'Analyze a 2D truss with span 8 m, height 3 m, and a load of 100 kN at the top node.',
  frame: 'Analyze a portal frame with bay width 6 m, column height 4 m, gravity load 20 kN/m on beam, and lateral load 15 kN.',
  col: 'Check a column for buckling. Length 5 m, pinned-pinned, area 0.008 m2, I 6e-5 m4, E 200 GPa, Fy 345 MPa, axial load 800 kN.',
};

export function initChat() {
  initFloatingChat();

  byId('exSel').addEventListener('change', (event) => {
    if (EXAMPLES[event.target.value]) byId('chatInput').value = EXAMPLES[event.target.value];
    event.target.value = '';
  });

  byId('chatForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    const input = byId('chatInput');
    const message = input.value.trim();
    if (!message) return;

    addMsg('user', message);
    input.value = '';
    const pending = addMsg('bot', 'Responding...');

    try {
      const data = await sendChat({ message, ...buildCurrentAnalysisPayload() });
      pending.querySelector('p').textContent = data.message || 'Done.';
      if (data.response_type === 'canvas_action' && data.canvas_action) {
        runCanvasAction(data.canvas_action, pending);
      }
      if (data.response_type === 'analysis' && data.analysis) {
        S.results = data.analysis.results;
        renderResults(data.analysis);
      }
    } catch (error) {
      pending.querySelector('p').textContent = 'Error reaching server.';
    }
  });
}

function runCanvasAction(canvasAction, pendingMessage) {
  if (canvasAction.action === 'clear_canvas') {
    clearCurrentModel();
    pendingMessage.querySelector('p').textContent = 'Canvas cleared.';
  } else if (canvasAction.action === 'draw_simple_beam') {
    drawSimpleBeam(canvasAction.arguments);
    const span = Number(canvasAction.arguments?.span_m) || 2;
    pendingMessage.querySelector('p').textContent = `I drew a ${span.toFixed(2).replace(/\.?0+$/, '')} m simply supported beam on the canvas.`;
  }
}

export function setChatPrompt(prompt) {
  byId('chatInput').value = prompt || '';
  byId('floatingChat').classList.remove('hidden');
}

function initFloatingChat() {
  const chat = byId('floatingChat');
  const handle = byId('floatingChatHandle');
  let drag = null;

  handle.addEventListener('mousedown', (event) => {
    drag = {
      x: event.clientX,
      y: event.clientY,
      left: chat.offsetLeft,
      top: chat.offsetTop,
    };
    event.preventDefault();
  });

  window.addEventListener('mousemove', (event) => {
    if (!drag) return;
    const parent = chat.parentElement.getBoundingClientRect();
    const maxLeft = Math.max(0, parent.width - chat.offsetWidth - 8);
    const maxTop = Math.max(0, parent.height - chat.offsetHeight - 8);
    const nextLeft = Math.max(8, Math.min(maxLeft, drag.left + event.clientX - drag.x));
    const nextTop = Math.max(8, Math.min(maxTop, drag.top + event.clientY - drag.y));
    chat.style.left = `${nextLeft}px`;
    chat.style.top = `${nextTop}px`;
  });

  window.addEventListener('mouseup', () => {
    drag = null;
  });
}

function addMsg(role, text) {
  const messages = byId('messages');
  const article = document.createElement('article');
  article.className = `msg msg-${role === 'user' ? 'user' : 'bot'}`;
  const paragraph = document.createElement('p');
  paragraph.textContent = text;
  article.appendChild(paragraph);
  messages.appendChild(article);
  messages.scrollTop = messages.scrollHeight;
  return article;
}
