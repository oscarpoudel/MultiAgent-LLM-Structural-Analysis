async function jsonRequest(url, options = {}) {
  const response = await fetch(url, options);
  return response.json();
}

export function analyzeStructure(payload) {
  return jsonRequest('/api/analyze/structure', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export function sendChat(payload) {
  return jsonRequest('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export function searchSections(type, query) {
  let url = `/api/sections?type=${encodeURIComponent(type)}`;
  if (query) url += `&q=${encodeURIComponent(query)}`;
  return jsonRequest(url);
}

export function fetchSection(name) {
  return jsonRequest(`/api/sections/${encodeURIComponent(name)}`);
}

export function fetchHistory(limit = 50) {
  return jsonRequest(`/api/history?limit=${limit}`);
}

export function exportCsv(results) {
  return fetch('/api/export/csv', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ results }),
  });
}

export function exportReport(reportMarkdown) {
  return fetch('/api/export/report', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ report_markdown: reportMarkdown }),
  });
}
