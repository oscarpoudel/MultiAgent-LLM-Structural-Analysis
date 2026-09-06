"""Page + health routes blueprint."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from flask import Blueprint, current_app, jsonify, send_from_directory

from app.tools.openapi import build_openapi_spec

bp = Blueprint("pages", __name__)

# Set by app factory
_db_path: Path | None = None
_static_dir: Path | None = None


@bp.get("/")
def index():
    return send_from_directory(_static_dir, "index.html")


@bp.get("/health")
def health():
    """Enhanced health check — verifies DB and numpy/opensees availability."""
    checks: dict[str, str] = {}

    try:
        conn = sqlite3.connect(str(_db_path))
        conn.execute("SELECT 1")
        conn.close()
        checks["db"] = "ok"
    except Exception as exc:
        checks["db"] = f"error: {exc}"

    try:
        import numpy as np  # noqa: F401
        checks["numpy"] = "ok"
    except ImportError:
        checks["numpy"] = "unavailable"

    try:
        import openseespy.opensees  # noqa: F401
        checks["opensees"] = "ok"
    except Exception:
        checks["opensees"] = "unavailable"

    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return jsonify({"status": overall, "checks": checks}), (200 if overall == "ok" else 503)


@bp.get("/api/openapi.json")
def openapi_spec():
    """Return the auto-generated OpenAPI 3.0 specification."""
    return jsonify(build_openapi_spec(current_app._get_current_object()))


@bp.get("/api/docs")
def api_docs():
    """Serve a self-contained API documentation page (no external CDN)."""
    return _DOCS_HTML, 200, {"Content-Type": "text/html; charset=utf-8"}


_DOCS_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>StructAgent API</title>
<style>
  :root { --bg:#0f1419; --panel:#161d26; --border:#2a3542; --text:#e6edf3; --muted:#8b98a5; --accent:#3b82f6; }
  * { box-sizing: border-box; }
  body { margin:0; font-family: Inter, system-ui, -apple-system, Segoe UI, sans-serif; background:var(--bg); color:var(--text); }
  header { padding:20px 28px; border-bottom:1px solid var(--border); background:var(--panel); }
  header h1 { margin:0 0 4px; font-size:20px; }
  header p { margin:0; color:var(--muted); font-size:13px; }
  .toolbar { padding:12px 28px; border-bottom:1px solid var(--border); display:flex; gap:10px; align-items:center; }
  .toolbar input { flex:1; padding:8px 12px; border:1px solid var(--border); border-radius:8px; background:var(--bg); color:var(--text); }
  .toolbar button { padding:8px 14px; border:1px solid var(--border); border-radius:8px; background:var(--panel); color:var(--text); cursor:pointer; }
  main { padding:8px 28px 60px; }
  .tag { margin-top:22px; }
  .tag > h2 { font-size:14px; text-transform:uppercase; letter-spacing:.05em; color:var(--accent); border-bottom:1px solid var(--border); padding-bottom:6px; }
  .op { border:1px solid var(--border); border-radius:10px; margin:10px 0; background:var(--panel); overflow:hidden; }
  .op-head { display:flex; align-items:center; gap:12px; padding:12px 14px; cursor:pointer; }
  .method { font-weight:700; font-size:12px; padding:4px 10px; border-radius:6px; min-width:56px; text-align:center; }
  .get { background:#0e4429; color:#4ade80; } .post { background:#082f49; color:#38bdf8; }
  .put { background:#422006; color:#fbbf24; } .delete { background:#450a0a; color:#f87171; }
  .path { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size:13px; }
  .op-head .summary { color:var(--muted); font-size:13px; margin-left:auto; }
  .op-body { display:none; padding:0 14px 14px; border-top:1px solid var(--border); }
  .op.open .op-body { display:block; }
  .op-body h4 { margin:14px 0 6px; font-size:12px; color:var(--muted); text-transform:uppercase; letter-spacing:.04em; }
  pre { background:var(--bg); border:1px solid var(--border); border-radius:8px; padding:12px; overflow:auto; font-size:12px; }
  .count { color:var(--muted); font-size:12px; }
</style>
</head>
<body>
<header>
  <h1>StructAgent API</h1>
  <p>Deterministic-first structural engineering assistant &mdash; auto-generated OpenAPI 3.0 spec.</p>
</header>
<div class="toolbar">
  <input id="filter" type="search" placeholder="Filter by path, method, or summary..."/>
  <button id="expandAll">Expand all</button>
  <button id="collapseAll">Collapse all</button>
  <span class="count" id="count"></span>
</div>
<main id="spec"></main>
<script>
let SPEC = null;
async function load() {
  const res = await fetch('/api/openapi.json');
  SPEC = await res.json();
  render();
}
function esc(s) { return String(s).replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }
function methodClass(m) { return m.toLowerCase(); }
function render() {
  const root = document.getElementById('spec');
  root.innerHTML = '';
  const byTag = {};
  for (const [path, item] of Object.entries(SPEC.paths)) {
    for (const [method, op] of Object.entries(item)) {
      if (!['get','post','put','delete'].includes(method)) continue;
      const tag = (op.tags && op.tags[0]) || 'other';
      (byTag[tag] = byTag[tag] || []).push({path, method, op});
    }
  }
  const tagDesc = {};
  (SPEC.tags || []).forEach(t => tagDesc[t.name] = t.description);
  let total = 0;
  for (const [tag, ops] of Object.entries(byTag)) {
    const section = document.createElement('div');
    section.className = 'tag';
    section.dataset.tag = tag;
    section.innerHTML = '<h2>' + esc(tag) + (tagDesc[tag] ? ' <span class="count">&mdash; ' + esc(tagDesc[tag]) + '</span>' : '') + '</h2>';
    for (const {path, method, op} of ops) {
      total++;
      section.appendChild(buildOp(path, method, op));
    }
    root.appendChild(section);
  }
  document.getElementById('count').textContent = total + ' operations';
}
function buildOp(path, method, op) {
  const el = document.createElement('div');
  el.className = 'op';
  const body = [];
  if (op.requestBody) {
    body.push('<h4>Request body</h4><pre>' + esc(JSON.stringify(op.requestBody.content['application/json'].schema, null, 2)) + '</pre>');
  }
  const resp = op.responses || {};
  const respHtml = Object.entries(resp).map(([code, r]) =>
    '<div style="margin:4px 0"><span class="method ' + methodClass(method) + '">' + esc(code) + '</span> ' + esc(r.description || '') + '</div>'
  ).join('');
  body.push('<h4>Responses</h4>' + respHtml);
  el.innerHTML =
    '<div class="op-head"><span class="method ' + methodClass(method) + '">' + esc(method.toUpperCase()) + '</span>' +
    '<span class="path">' + esc(path) + '</span>' +
    '<span class="summary">' + esc(op.summary || '') + '</span></div>' +
    '<div class="op-body">' + body.join('') + '</div>';
  el.querySelector('.op-head').addEventListener('click', () => el.classList.toggle('open'));
  el.dataset.search = (method + ' ' + path + ' ' + (op.summary || '')).toLowerCase();
  return el;
}
function applyFilter() {
  const q = document.getElementById('filter').value.trim().toLowerCase();
  let visible = 0;
  document.querySelectorAll('.op').forEach(op => {
    const show = !q || op.dataset.search.includes(q);
    op.style.display = show ? '' : 'none';
    if (show) visible++;
  });
  document.querySelectorAll('.tag').forEach(t => {
    const any = t.querySelectorAll('.op:not([style*="display: none"])').length > 0;
    t.style.display = any ? '' : 'none';
  });
  document.getElementById('count').textContent = visible + ' operations';
}
document.getElementById('filter').addEventListener('input', applyFilter);
document.getElementById('expandAll').addEventListener('click', () => document.querySelectorAll('.op').forEach(o => o.classList.add('open')));
document.getElementById('collapseAll').addEventListener('click', () => document.querySelectorAll('.op').forEach(o => o.classList.remove('open')));
load();
</script>
</body>
</html>
"""
