import { fetchHistory } from './api.js';
import { byId, showTab } from './dom.js';
import { setChatPrompt } from './chat.js';

export function initHistory() {
  byId('histRefresh').addEventListener('click', loadHistory);
}

async function loadHistory() {
  const content = byId('histList');
  content.innerHTML = '<p class="placeholder">Loading...</p>';
  try {
    const data = await fetchHistory(50);
    content.innerHTML = '';
    if (data.history && data.history.length) {
      data.history.forEach((item) => content.appendChild(makeHistoryCard(item)));
    } else {
      content.innerHTML = '<p class="placeholder">No history yet.</p>';
    }
  } catch (error) {
    content.innerHTML = '<p class="placeholder">Failed to load.</p>';
  }
}

function makeHistoryCard(item) {
  const card = document.createElement('div');
  card.className = 'hist-card';
  const date = new Date(item.timestamp * 1000).toLocaleString();
  card.innerHTML = `<div class="hist-hdr"><span class="hist-type">${(item.analysis_type || 'beam').toUpperCase()}</span><span class="hist-date">${date}</span></div><p class="hist-prompt">${(item.prompt || '').substring(0, 120)}</p>`;
  card.addEventListener('click', () => {
    setChatPrompt(item.prompt);
    showTab('draw');
  });
  return card;
}
