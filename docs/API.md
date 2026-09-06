# API Documentation

## Base URL

All API endpoints are relative to the application base URL (default: `http://127.0.0.1:5000`).

## Authentication

No authentication is required for local development. For production, configure `APP_SECRET_KEY` and implement appropriate authentication middleware.

## Response Format

Successful responses use a `status: "ok"` envelope. Deterministic tool endpoints (loads, design, analysis) return their payload under `results`:

```json
{
  "status": "ok",
  "results": { ... }
}
```

Some endpoints return additional top-level keys alongside `status` (e.g. `method`, `combinations`, `projects`, `sections`, `history`, `applied`, `warnings`, `model`, `report_markdown`).

Error responses use a `status: "error"` envelope with a `message` (and, for Pydantic validation failures, a `details` array of field errors):

```json
{
  "status": "error",
  "message": "Invalid beam selection inputs",
  "details": [ { "loc": ["moment_kn_m"], "msg": "..." } ]
}
```

Common HTTP status codes: `400` (bad/invalid body), `404` (not found), `422` (schema validation on analyze/chat), `500` (analysis/server error), `503` (health degraded / LLM unavailable).

> The full, machine-readable spec is generated from the live routes at `GET /api/openapi.json`, with an interactive page at `GET /api/docs`.

---

## Pages, Health & Docs

### GET /

Serves the main application page (`app/static/index.html`).

**Response**: `text/html`

### GET /health

Enhanced health check — verifies the SQLite DB and NumPy/OpenSees availability.

**Response** (200 when healthy, 503 when degraded):

```json
{
  "status": "ok",
  "checks": { "db": "ok", "numpy": "ok", "opensees": "ok" }
}
```

### GET /api/openapi.json

Returns the auto-generated OpenAPI 3.0 specification (introspected from live Flask routes + Pydantic models).

**Response**: `application/json` — OpenAPI 3.0 document.

### GET /api/docs

Serves a self-contained interactive API documentation page (no external CDN).

**Response**: `text/html`

---

## Chat & Analysis

### POST /api/analyze

Run structural analysis from a natural language prompt.

**Request Body**:

```json
{ "prompt": "Analyze a simply supported beam with 10m span and 5 kN/m UDL" }
```

**Response**: an `AnalyzeResponse` object:

```json
{
  "status": "ok",
  "analysis_type": "beam",
  "assumptions": ["Preliminary elastic analysis only."],
  "warnings": ["Not a substitute for licensed engineering review."],
  "traces": [ { "agent": "intent", "summary": "...", "data": {} } ],
  "results": { "max_moment_kn_m": 62.5, "max_deflection_mm": 6.51 },
  "report_markdown": "# Beam Analysis Report\n\n...",
  "diagrams": { "positions": [], "shear_kn": [], "moment_kn_m": [], "deflection_mm": [] }
}
```

### POST /api/chat

Chat with the structural assistant. Supports conversation, context-aware queries, canvas actions, and analysis requests.

**Request Body**:

```json
{
  "message": "What is the maximum moment on this frame?",
  "analysis_type": "frame",
  "model": { "nodes": [], "members": [] },
  "results": { "max_moment_kn_m": 62.5 },
  "context": { "model_summary": "3-story, 3-bay frame..." }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| message | string | Yes | User message (min 1 character) |
| analysis_type | string | No | beam, truss, frame, column, 3d_frame |
| model | object | No | Canvas structure model (nodes, members, loads) |
| results | object | No | Previous analysis results for follow-up questions |
| context | object | No | Frontend context (model_summary, structure_type) |

**Response**: a `ChatResponse` object. `response_type` is one of:

- `conversation` — general chat or context-aware answer
- `analysis` — analysis results (see `analysis` field, an `AnalyzeResponse`)
- `canvas_action` — canvas manipulation instruction (see `canvas_action`)
- `evaluation` — evaluation of existing results (includes `quick_actions`)

```json
{
  "status": "ok",
  "response_type": "conversation",
  "message": "The maximum bending moment on this frame is 62.5 kN-m...",
  "source": "llm",
  "analysis": null,
  "canvas_action": null
}
```

### POST /api/chat/evaluate

Evaluate or explain existing analysis results using the LLM agent.

**Request Body**:

```json
{
  "message": "Are these results reasonable?",
  "results": { "max_moment_kn_m": 62.5 },
  "analysis_type": "beam",
  "prompt": "original prompt"
}
```

**Response**: `ChatResponse` with `response_type: "evaluation"` and a `quick_actions` list.

### POST /api/analyze/structure

Analyze a drawn structure model from the 2D or 3D canvas.

**Request Body**:

```json
{
  "analysis_type": "frame",
  "model": { "nodes": [], "members": [], "nodal_loads": [], "member_loads": [] }
}
```

**Response**:

```json
{
  "status": "ok",
  "analysis_type": "frame",
  "results": { ... },
  "report_markdown": "# ..."
}
```

### POST /api/analyze/structure-with-loads

End-to-end: compute wind/seismic story forces, apply them to the drawn 3D model as nodal loads, run the 3D analysis, and report story drifts.

**Request Body**: same as `/api/loads/apply-story-forces` (see below).

**Response**: `status: "ok"` with `load_results`, `applied`, `warnings`, `model`, `results` (full 3D analysis including `story_response.story_drifts`), and `report_markdown`.

### POST /api/validate

Validate a structural model payload without running analysis.

**Request Body**:

```json
{ "analysis_type": "frame", "model": { "nodes": [], "members": [] } }
```

**Response** (200 when valid, 400 when errors):

```json
{
  "status": "ok",
  "analysis_type": "frame",
  "errors": [],
  "warnings": []
}
```

### POST /api/load-combinations

Return ASCE 7-22 factored load combinations for the given load components.

**Request Body**:

```json
{
  "dl_kn": 100.0, "ll_kn": 50.0, "wl_kn": 20.0, "sl_kn": 10.0, "el_kn": 30.0,
  "method": "lrfd"
}
```

**Response**:

```json
{
  "status": "ok",
  "method": "lrfd",
  "combinations": [ { "name": "1.2D+1.6L", "factors": { "D": 1.2, "L": 1.6 }, "total_kn": 180.0 } ],
  "controlling": { "name": "1.2D+1.6L", "total_kn": 180.0 }
}
```

### GET /api/llm-status

Check if the LLM provider is reachable.

**Response**:

```json
{ "status": "ok", "connected": true, "provider": "ollama", "message": "Connected" }
```

---

## Load Determination (deterministic, no LLM)

All load endpoints return `status: "ok"` with a `results` object.

### POST /api/loads/wind

ASCE 7-22 wind loads (simplified MWFRS procedure).

**Request Body** (`WindInputs`):

```json
{
  "basic_wind_speed_ms": 30.0,
  "exposure": "C",
  "height_m": 8.0,
  "length_m": 6.0,
  "width_m": 6.0,
  "story_height_m": 4.0,
  "internal_pressure": "minor_openings"
}
```

Optional: `topographic_factor` (1.0–2.0), `air_density_factor` (0.5–1.5).

**Response**: `results` with `velocity_pressures_kpa`, `mwfrs_pressures`, `base_shear_x_kn`, `base_shear_y_kn`, `roof_uplift_kn`, and `story_forces` (`[{story, z_m, force_kn}]`).

### POST /api/loads/seismic

ASCE 7-22 equivalent static force procedure.

**Request Body** (`SeismicInputs`):

```json
{
  "spectral_accel_sd": 0.4,
  "spectral_accel_1s": 0.2,
  "site_class": "D",
  "risk_category": "II",
  "building_weight_kn": 5000.0,
  "height_m": 8.0,
  "structural_system": "moment_frame"
}
```

Optional: `fundamental_period_s`, `importance_factor`, `response_modification`, `deflection_amplifier`.

**Response**: `results` with `site_coefficients`, `design_params`, `base_shear_kn`, and `story_forces`.

### POST /api/loads/snow

ASCE 7-22 roof snow loads.

**Request Body** (`SnowInputs`):

```json
{
  "ground_snow_load_kpa": 2.0,
  "exposure": "partially_shielded",
  "thermal": "heated",
  "risk_category": "II",
  "roof_slope_deg": 0.0,
  "drift": false
}
```

**Response**: `results` with `flat_roof_ps_kpa`, `sloped_roof_ps_kpa`, `drift_load_kpa`, and `total_design_snow_kpa`.

### POST /api/loads/slab

ACI 318 two-way slab analysis.

**Request Body** (`SlabInputs`): `span_x_m`, `span_y_m`, `thickness_m`, `live_load_kpa` (required); optional `dead_load_kpa`, `concrete_fck_mpa`, `steel_fy_mpa`, `support_condition`, `deflection_limit_ratio`.

**Response**: `results` with flexure, deflection, and minimum-thickness checks.

### POST /api/loads/response-spectrum

Deterministic lumped-mass multi-mode (Cantilever) response-spectrum analysis on a 3D model.

**Request Body**:

```json
{
  "model": { "nodes": [], "members": [] },
  "building_weight_kn": 5000.0,
  "sds": 0.4,
  "sd1": 0.2,
  "direction": "x",
  "num_modes": 10,
  "long_period_s": 8.0
}
```

**Response**: `results` with modal periods, modal responses, and SRSS-combined story forces/displacements.

### POST /api/loads/apply-story-forces

Compute wind or seismic story forces and map them onto a drawn 3D model as nodal loads. Returns the augmented model (no analysis run).

**Request Body**:

```json
{
  "load_type": "wind",
  "wind": { "basic_wind_speed_ms": 30.0, "exposure": "C", "height_m": 8.0, "length_m": 6.0, "width_m": 6.0, "story_height_m": 4.0 },
  "model": { "nodes": [ { "id": 1, "x": 0, "y": 0, "z": 0, "support": "fixed" } ], "members": [] },
  "direction": "x",
  "distribution": "equal"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| load_type | string | Yes | `wind` or `seismic` |
| wind / seismic (or inputs) | object | Yes | Load tool inputs (see above) |
| model | object | Yes | Drawn 3D structure (string supports allowed) |
| direction | string | No | `x` (default) or `y` |
| distribution | string | No | `equal` (default) or `windward` |

**Response**: `status: "ok"` with `load_results`, `applied` (per-story assignment), `warnings`, and `model` (augmented with `W`/`EQ` nodal loads).

### POST /api/loads/pdelta-amplify

Amplify first-order story drifts using the ASCE 7 stability coefficient (θ = V·h/W).

**Request Body**:

```json
{
  "story_drifts": [ { "drift_mm": 12.0, "from_m": 0.0, "to_m": 4.0 } ],
  "base_shear_kn": 200.0,
  "height_m": 8.0,
  "gravity_load_kn": 5000.0
}
```

**Response**: `results` with the stability coefficient, amplification factor, and amplified drifts.

### POST /api/loads/pdelta-forces

Compute P-delta equivalent lateral forces from first-order drifts and map them onto a drawn 3D model as nodal loads (for iterative second-order analysis).

**Request Body**:

```json
{
  "model": { "nodes": [], "members": [] },
  "story_drifts": [ { "from_m": 0.0, "to_m": 4.0, "drift_mm": 12.0 } ],
  "gravity_load_kn": 5000.0,
  "direction": "x"
}
```

**Response**: `status: "ok"` with `applied`, `warnings`, and `model` (augmented with P-delta nodal loads).

### POST /api/loads/cross-validation

Run the independent-solver cross-validation suite on benchmark models (closed-form vs OpenSeesPy vs direct stiffness). No request body required.

**Response**: `results` with per-quantity agreement across solvers.

---

## Element Design & Code Checks (deterministic, no LLM)

All design endpoints return `status: "ok"` with a `results` object.

### POST /api/design/beam

AISC 360 steel beam section selection (lightest adequate W-shape for flexure incl. LTB + shear).

**Request Body** (`BeamSelectionInputs`):

```json
{ "moment_kn_m": 250.0, "shear_kn": 120.0, "unbraced_length_m": 6.0, "cb": 1.0, "fy_mpa": 345.0 }
```

**Response**: `results` with the recommended section, its properties, utilization, and top candidate sections.

### POST /api/design/column

AISC 360 steel column section selection (lightest adequate W-shape for axial, AISC E3).

**Request Body** (`ColumnSelectionInputs`):

```json
{ "axial_load_kn": 800.0, "kl_m": 4.0, "fy_mpa": 345.0 }
```

### POST /api/design/concrete-beam

ACI 318 singly-reinforced concrete beam design (flexure As/ρ/φMn, one-way shear, stirrup spacing, bar count).

**Request Body** (`ConcreteBeamInputs`):

```json
{
  "moment_kn_m": 250.0,
  "shear_kn": 120.0,
  "width_mm": 300,
  "depth_mm": 600,
  "concrete_fck_mpa": 25.0,
  "steel_fy_mpa": 420.0
}
```

Optional: `effective_depth_mm`, `bar_dia_mm`, `stirrup_dia_mm`.

### POST /api/design/concrete-column

ACI 318 circular tied/spiral column design (As, ρ limits, φPn, slenderness check).

**Request Body** (`ConcreteColumnInputs`):

```json
{
  "axial_load_kn": 1500.0,
  "diameter_mm": 500,
  "concrete_fck_mpa": 25.0,
  "steel_fy_mpa": 420.0,
  "tied": true,
  "kl_r": 0.0
}
```

### GET /api/design/timber-species

List available timber species with NDS reference design values (MPa).

**Response**: `status: "ok"` with `results.species` (list of species keys and design values).

### POST /api/design/timber-beam

Design a rectangular timber beam (NDS, ASD).

**Request Body** (`TimberBeamInputs`):

```json
{
  "species": "spf-no1",
  "width_mm": 90,
  "depth_mm": 360,
  "moment_kn_m": 30.0,
  "shear_kn": 20.0,
  "span_m": 6.0
}
```

Optional: `unbraced_length_m`, `duration`, `moisture_pct`, `temperature_c`, `live_load_fraction`.

### POST /api/design/spread-footing

Size and check a square spread footing (ACI 318: bearing, one-way + punching shear, flexure).

**Request Body** (`SpreadFootingInputs`):

```json
{
  "axial_load_kn": 1000.0,
  "allowable_bearing_kpa": 200.0,
  "column_width_mm": 400,
  "column_depth_mm": 400,
  "concrete_fck_mpa": 25.0,
  "steel_fy_mpa": 420.0,
  "footing_depth_mm": 600
}
```

Optional: `factored_axial_kn`, `bar_dia_mm`, `footing_width_mm`.

### POST /api/design/pile

Static pile capacity (skin friction + end bearing), factor of safety, and Converse-Labarre group efficiency.

**Request Body** (`PileInputs`):

```json
{
  "pile_diameter_mm": 600,
  "pile_length_m": 20.0,
  "skin_friction_kpa": 50.0,
  "end_bearing_kpa": 4000.0,
  "factor_of_safety": 2.5
}
```

Optional: `skin_friction_alpha`, `piles_per_row`, `rows_in_group`, `center_to_center_spacing_m`.

### GET /api/design/fatigue-categories

List AISC 360 fatigue categories (A–E) with S-N parameters.

**Response**: `status: "ok"` with `results.categories`.

### POST /api/design/fatigue

Check a fatigue detail against the AISC 360 S-N curve for the design life.

**Request Body** (`FatigueInputs`):

```json
{ "category": "C", "stress_range_mpa": 80.0, "num_cycles": 2000000 }
```

**Response**: `results` with the S-N limit, allowable stress range, infinite-life check, utilization, and a recommended category.

### POST /api/design/cost

Estimate steel cost from a member takeoff (section + length per group).

**Request Body**:

```json
{
  "members": [ { "section": "W200x27", "length_m": 12.0 } ],
  "price_per_kg": 2.5,
  "fab_factor": 1.0,
  "erect_factor": 1.0,
  "currency": "USD"
}
```

**Response**: `results` with per-member mass/cost, totals, and applied factors.

---

## Advanced Analysis (deterministic, no LLM)

### POST /api/analyze/sensitivity

OAT parametric sensitivity study on a simply-supported beam (moment/deflection/stress) with elasticity sensitivity coefficients and parameter ranking.

**Request Body** (`SensitivityInputs`):

```json
{
  "load_kn_m": 20.0,
  "span_m": 6.0,
  "modulus_gpa": 200.0,
  "inertia_m4": 8e-06,
  "section_modulus_m3": 1.6e-04,
  "load_min_kn_m": 10.0, "load_max_kn_m": 30.0,
  "span_min_m": 4.0, "span_max_m": 8.0,
  "modulus_min_gpa": 150.0, "modulus_max_gpa": 250.0,
  "inertia_min_m4": 4e-06, "inertia_max_m4": 1.2e-05,
  "section_min_m3": 8e-05, "section_max_m3": 2.4e-04,
  "parameters": ["w", "L", "E", "I", "S"]
}
```

**Response**: `results` with base-case outputs, per-parameter sensitivity coefficients, and a ranked parameter list.

### POST /api/analyze/multi-hazard

Evaluate all ASCE 7 LRFD/ASD combinations against a member capacity and find the worst-case scenario (with per-component sweeps).

**Request Body** (`MultiHazardInputs`):

```json
{
  "dead_load_kn": 100.0,
  "live_load_kn": 50.0,
  "wind_load_kn": 20.0,
  "snow_load_kn": 10.0,
  "earthquake_load_kn": 30.0,
  "response_factor": 1.0,
  "capacity": 250.0,
  "method": "lrfd"
}
```

Optional sweep bounds (`dead_min_kn`/`dead_max_kn`, etc.) and `components` (list of `dl_kn`, `ll_kn`, `wl_kn`, `sl_kn`, `el_kn`).

**Response**: `results` with per-combination utilization, the controlling combination, and worst-case sweep results.

---

## Sections

### GET /api/sections

List or search steel sections from the AISC database.

**Query Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| q | string | No | Search query (filters by section name) |
| type | string | No | Section type filter (default `all`) |

**Response**:

```json
{
  "status": "ok",
  "sections": [ { "name": "W10x33", "depth_mm": 247.1, "area_m2": 0.00627, "Ix_m4": 7.11e-05, "weight_kg_per_m": 49.1 } ]
}
```

### GET /api/sections/<name>

Get properties for a specific steel section.

**Path Parameter**: `name` — section designation (e.g. `W10x33`).

**Response** (SI units):

```json
{
  "status": "ok",
  "section": {
    "name": "W10x33",
    "weight_kg_per_m": 49.1,
    "area_m2": 0.00627,
    "depth_mm": 247.1,
    "flange_width_mm": 202.2,
    "flange_thickness_mm": 11.0,
    "web_thickness_mm": 7.4,
    "Ix_m4": 7.11e-05,
    "Iy_m4": 1.49e-05,
    "Sx_m3": 5.75e-04,
    "Sy_m3": 1.47e-04,
    "Zx_m3": 6.63e-04,
    "Zy_m3": 1.71e-04,
    "rx_m": 0.107,
    "ry_m": 0.0487
  }
}
```

**404** when the section is not found: `{ "status": "error", "message": "Section 'W99x999' not found" }`.

---

## Projects

### GET /api/projects

List all saved projects.

**Response**: `{ "status": "ok", "projects": [ { "id": "uuid-1", "name": "My Project", "model": {}, "results": {}, "updated_at": 0.0 } ] }`

### POST /api/projects

Create a new project.

**Request Body**:

```json
{ "name": "My Project", "model": { "nodes": [], "members": [] }, "results": {} }
```

**Response**: `{ "status": "ok", "id": "uuid-1" }`

### GET /api/projects/<project_id>

Get a single project. **404** when not found.

**Response**: `{ "status": "ok", "project": { ... } }`

### PUT /api/projects/<project_id>

Update an existing project. The payload `id` must match the path parameter.

**Request Body**: `{ "id": "uuid-1", "name": "Updated", "model": {}, "results": {} }`

**Response**: `{ "status": "ok", "id": "uuid-1" }`

### DELETE /api/projects/<project_id>

Delete a project.

**Response**: `{ "status": "ok" }`

---

## History & Export

### GET /api/history

Get analysis history from SQLite.

**Query Parameters**: `limit` (integer, default 50).

**Response**: `{ "status": "ok", "history": [ { "id": 1, "timestamp": 0.0, "analysis_type": "beam", "prompt": "...", "results": {}, "report_markdown": "..." } ] }`

### GET /api/history/<item_id>

Get a specific analysis from history. **404** when not found.

**Response**: `{ "status": "ok", "item": { "id": 1, "timestamp": 0.0, "analysis_type": "beam", "prompt": "...", "results": {}, "report_markdown": "..." } }`

### POST /api/export/csv

Export analysis results as CSV.

**Request Body**: `{ "results": { ... } }` (or `{ "analysis": { "results": { ... } } }`).

**Response**: `text/csv` attachment with rows `[Section, Item, Value, Unit]`.

### POST /api/export/report

Export the markdown report as a downloadable `.md` file.

**Request Body**: `{ "report_markdown": "# ...", "analysis_type": "3d_frame", "results": { ... } }`.

**Response**: `text/markdown` attachment.

### POST /api/export/pdf

Export a Markdown engineering report as a downloadable PDF (dependency-free PDF 1.4 writer).

**Request Body**: `{ "report_markdown": "# ..." }`.

**Response**: `application/pdf` attachment.

---

## Error Codes

| HTTP Status | Description |
|-------------|-------------|
| 400 | Bad Request — invalid request body or parameters |
| 404 | Not Found — resource not found |
| 422 | Unprocessable Entity — schema validation on analyze/chat |
| 500 | Internal Server Error — analysis or server error |
| 503 | Service Unavailable — health degraded / LLM provider unavailable |

## Rate Limiting

No rate limiting is applied in development. For production, consider implementing rate limiting middleware.

## CORS

CORS is enabled for all origins in development. Configure `CORS_ORIGINS` in production to restrict access.
