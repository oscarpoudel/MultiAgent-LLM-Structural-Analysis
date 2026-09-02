import { analyzeStructureWithLoads, sendChat } from './api.js';
import {
  applyMemberGroupSections,
  buildCurrentAnalysisPayload,
  buildModel,
  clearAnalysisResults,
  clearCurrentModel,
  drawSimpleBeam,
  drawThreeByThreeThreeStoryFrame,
} from './analysis.js';
import { byId } from './dom.js';
import { renderResults } from './results.js';
import { S } from './state.js';

let lastAnalysisPrompt = '';
let lastAnalysisType = '';

export function initChat() {
  initFloatingChat();
  checkLlmStatus();
  setInterval(checkLlmStatus, 30000);

  byId('chatForm').querySelectorAll('.qp-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      byId('chatInput').value = btn.dataset.prompt;
      byId('chatInput').focus();
    });
  });

  byId('clearChatBtn').addEventListener('click', () => {
    byId('messages').innerHTML = '<article class="msg msg-bot"><p>Describe a beam, truss, frame, or column problem and I\'ll analyze it.</p></article>';
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
      const analysisPayload = buildCurrentAnalysisPayload();
      const payload = {
        message,
        ...analysisPayload,
        results: S.results || {},
        context: buildChatContext(analysisPayload),
      };
      const data = await sendChat(payload);
      pending.querySelector('p').textContent = data.message || 'Done.';
      if (data.quick_actions) {
        addQuickActions(pending, data.quick_actions);
      }
      if (data.response_type === 'canvas_action' && data.canvas_action) {
        runCanvasAction(data.canvas_action, pending);
      }
      if (data.response_type === 'analysis' && data.analysis) {
        S.results = data.analysis.results;
        lastAnalysisPrompt = message;
        lastAnalysisType = data.analysis.analysis_type || 'frame';
        renderResults(data.analysis);
        addAnalysisActions(pending);
      }
      if (data.response_type === 'evaluation') {
        addQuickActions(pending, data.quick_actions || []);
      }
    } catch (error) {
      console.error('[StructAgent] Chat error:', error);
      pending.querySelector('p').textContent = 'Error reaching server. Check console for details.';
    }
  });
}

function buildChatContext(analysisPayload) {
  const model = analysisPayload.model || {};
  return {
    analysis_type: analysisPayload.analysis_type,
    model,
    results: S.results || {},
    model_summary: {
      nodes: model.nodes?.length || 0,
      members: model.members?.length || 0,
      nodal_loads: model.nodal_loads?.length || model.loads?.length || 0,
      member_loads: model.member_loads?.length || 0,
      slabs: S.slabs?.length || 0,
      active_load_combination: S.activeLoadCombination,
      rigid_diaphragms: S.rigidDiaphragms,
    },
  };
}

async function checkLlmStatus() {
  const dot = byId('llmDot');
  if (!dot) return;
  dot.className = 'llm-dot checking';
  dot.title = 'Checking LLM…';
  try {
    const res = await fetch('/api/llm-status');
    const data = await res.json();
    if (data.connected) {
      dot.className = 'llm-dot on';
      dot.title = 'LLM connected (' + (data.provider || 'unknown') + ')';
    } else {
      dot.className = 'llm-dot off';
      dot.title = 'LLM offline: ' + (data.message || '');
    }
  } catch {
    dot.className = 'llm-dot off';
    dot.title = 'LLM offline – server unreachable';
  }
}

async function handleQuickAction(action, messageEl) {
  if (!S.results) {
    const p = messageEl.querySelector('p');
    p.textContent = 'No analysis results to evaluate. Run an analysis first.';
    return;
  }

  const p = messageEl.querySelector('p');
  p.textContent = 'Thinking...';

  const prompts = {
    evaluate: 'Are these analysis results acceptable? Evaluate against typical engineering criteria including deflection limits, utilization ratios, and code compliance.',
    code_check: 'Check these results against AISC/ASCE/IBC code requirements. What code provisions apply? Are there any code violations or concerns?',
    explain: 'Explain these analysis results in plain language. What do the key numbers mean? What should I pay attention to?',
    load_combos: 'What load combinations should I consider for this structure? Show the controlling combination and explain why.',
    compare_limits: 'Compare the key result values against typical design limits. Show pass/fail for each check with the limit values.',
    reanalyze: 'Re-run the analysis with the current model.',
    export: 'Export the current model.',
  };

  const evalPrompt = prompts[action] || prompts.evaluate;

  try {
    const response = await fetch('/api/chat/evaluate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: evalPrompt,
        results: S.results,
        analysis_type: lastAnalysisType,
        prompt: lastAnalysisPrompt,
      }),
    });
    const data = await response.json();
    p.textContent = data.message || 'Unable to evaluate.';
    if (data.quick_actions) {
      addQuickActions(messageEl, data.quick_actions);
    }
  } catch (error) {
    console.error('[StructAgent] Evaluate error:', error);
    p.textContent = 'Error evaluating results: ' + error.message;
  }
}

function addQuickActions(container, actions) {
  const bar = document.createElement('div');
  bar.className = 'chat-actions';
  actions.forEach((a) => {
    const btn = document.createElement('button');
    btn.className = 'chat-action-btn';
    btn.textContent = a.label;
    btn.addEventListener('click', () => handleQuickAction(a.action, container));
    bar.appendChild(btn);
  });
  container.appendChild(bar);
}

function addAnalysisActions(container) {
  const bar = document.createElement('div');
  bar.className = 'chat-actions';
  const actions = [
    { label: 'Evaluate', action: 'evaluate' },
    { label: 'Code Check', action: 'code_check' },
    { label: 'Explain', action: 'explain' },
    { label: 'Load Combos', action: 'load_combos' },
    { label: 'Limits', action: 'compare_limits' },
  ];
  actions.forEach((a) => {
    const btn = document.createElement('button');
    btn.className = 'chat-action-btn';
    btn.textContent = a.label;
    btn.addEventListener('click', () => handleQuickAction(a.action, container));
    bar.appendChild(btn);
  });
  container.appendChild(bar);
}

function runCanvasAction(canvasAction, pendingMessage) {
  if (canvasAction.action === 'clear_canvas') {
    clearCurrentModel();
    pendingMessage.querySelector('p').textContent = 'Canvas cleared.';
  } else if (canvasAction.action === 'clear_analysis') {
    clearAnalysisResults();
    pendingMessage.querySelector('p').textContent = 'Analysis results cleared. The model is unchanged.';
  } else if (canvasAction.action === 'draw_simple_beam') {
    drawSimpleBeam(canvasAction.arguments);
    const span = Number(canvasAction.arguments?.span_m) || 2;
    pendingMessage.querySelector('p').textContent = `I drew a ${span.toFixed(2).replace(/\.?0+$/, '')} m simply supported beam on the canvas.`;
  } else if (canvasAction.action === 'draw_3d_frame_template') {
    drawThreeByThreeThreeStoryFrame(canvasAction.arguments || {});
    pendingMessage.querySelector('p').textContent = 'I created a 3x3 3-story 3D frame template.';
  } else if (canvasAction.action === 'apply_member_group_sections') {
    applyMemberGroupSections();
    pendingMessage.querySelector('p').textContent = 'I applied preliminary beam, column, and brace section properties.';
  } else if (canvasAction.action === 'set_rigid_diaphragm') {
    S.rigidDiaphragms = canvasAction.arguments?.enabled !== false;
    const toggle = byId('rigidDiaphragmToggle');
    if (toggle) toggle.checked = S.rigidDiaphragms;
    pendingMessage.querySelector('p').textContent = `Rigid diaphragms ${S.rigidDiaphragms ? 'enabled' : 'disabled'}.`;
  } else if (canvasAction.action === 'set_load_combination') {
    const combo = canvasAction.arguments?.name;
    const select = byId('loadComboSelect');
    if (combo && S.loadCombinations.some((item) => item.name === combo)) {
      S.activeLoadCombination = combo;
      if (select) select.value = combo;
      pendingMessage.querySelector('p').textContent = `Active load combination set to ${combo}.`;
    } else {
      pendingMessage.querySelector('p').textContent = 'I could not find that load combination. Use the Load Combo dropdown or ask for EX/EY/default combo.';
    }
  } else if (canvasAction.action === 'apply_story_forces') {
    runApplyStoryForces(canvasAction.arguments, pendingMessage);
  }
}

async function runApplyStoryForces(args, pendingMessage) {
  const label = pendingMessage.querySelector('p');
  const model = buildModel('3d_frame');
  if (!model.nodes || model.nodes.length < 2) {
    label.textContent = 'No 3D model to apply story forces to. Draw a 3D frame on the canvas first.';
    return;
  }
  const loadType = args?.load_type === 'seismic' ? 'seismic' : 'wind';
  const payload = {
    load_type: loadType,
    [loadType]: args?.[loadType] || {},
    model,
    direction: args?.direction || 'x',
    distribution: args?.distribution || 'equal',
  };
  label.textContent = `Applying ${loadType} story forces and running 3D analysis…`;
  try {
    const data = await analyzeStructureWithLoads(payload);
    if (data.status !== 'ok') {
      label.textContent = `Story-force analysis failed: ${data.message || 'unknown error'}`;
      return;
    }
    S.results = data.results;
    lastAnalysisType = '3d_frame';
    renderResults({ analysis_type: '3d_frame', results: data.results, report_markdown: data.report_markdown });
    const drifts = data.results.story_response?.story_drifts || [];
    const maxDrift = drifts.length ? Math.max(...drifts.map((d) => d.drift_mm || 0)) : 0;
    label.textContent = `${loadType === 'wind' ? 'Wind' : 'Seismic'} story forces applied. Max story drift ${maxDrift.toFixed(2)} mm.`;
  } catch (error) {
    label.textContent = `Story-force analysis failed: ${error.message}`;
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
