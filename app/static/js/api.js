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

export function exportCsv(analysis) {
  return fetch('/api/export/csv', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ analysis, results: analysis?.results || analysis }),
  });
}

export function exportReport(analysis) {
  return fetch('/api/export/report', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      analysis,
      analysis_type: analysis?.analysis_type,
      report_markdown: analysis?.report_markdown || analysis,
      results: analysis?.results,
    }),
  });
}

export function exportPdf(reportMarkdown) {
  return fetch('/api/export/pdf', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ report_markdown: reportMarkdown }),
  });
}

export function calculateWindLoads(inputs) {
  return jsonRequest('/api/loads/wind', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(inputs),
  });
}

export function calculateSeismicLoads(inputs) {
  return jsonRequest('/api/loads/seismic', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(inputs),
  });
}

export function calculateResponseSpectrum(inputs) {
  return jsonRequest('/api/loads/response-spectrum', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(inputs),
  });
}

export function calculateSnowLoads(inputs) {
  return jsonRequest('/api/loads/snow', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(inputs),
  });
}

export function applyStoryForces(payload) {
  return jsonRequest('/api/loads/apply-story-forces', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export function analyzeStructureWithLoads(payload) {
  return jsonRequest('/api/analyze/structure-with-loads', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export function selectBeam(inputs) {
  return jsonRequest('/api/design/beam', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(inputs),
  });
}

export function selectColumn(inputs) {
  return jsonRequest('/api/design/column', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(inputs),
  });
}

export function designConcreteBeam(inputs) {
  return jsonRequest('/api/design/concrete-beam', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(inputs),
  });
}

export function designConcreteColumn(inputs) {
  return jsonRequest('/api/design/concrete-column', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(inputs),
  });
}

export function estimateCost(payload) {
  return jsonRequest('/api/design/cost', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export function designTimberBeam(inputs) {
  return jsonRequest('/api/design/timber-beam', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(inputs),
  });
}

export function fetchTimberSpecies() {
  return jsonRequest('/api/design/timber-species');
}

export function pdeltaAmplify(payload) {
  return jsonRequest('/api/loads/pdelta-amplify', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export function pdeltaForces(payload) {
  return jsonRequest('/api/loads/pdelta-forces', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}
