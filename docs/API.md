# API Documentation

## Base URL

All API endpoints are relative to the application base URL (default: `http://localhost:5000`).

## Authentication

No authentication is required for local development. For production, configure `APP_SECRET_KEY` and implement appropriate authentication middleware.

## Response Format

All API responses return JSON with consistent structure:

```json
{
  "status": "success",
  "data": { ... }
}
```

Error responses include:

```json
{
  "status": "error",
  "error": "Error message",
  "details": "Additional context"
}
```

---

## Endpoints

### GET /

Returns the main application page.

**Response**: `text/html` - Serves `app/static/index.html`

---

### GET /health

Health check endpoint for monitoring and load balancers.

**Response**:

```json
{
  "status": "healthy",
  "timestamp": "2026-05-02T12:00:00Z"
}
```

---

### GET /api/llm-status

Check if the LLM provider (Ollama) is reachable.

**Response**:

```json
{
  "status": "success",
  "llm_available": true,
  "provider": "ollama",
  "model": "gemma4:latest"
}
```

**503 Response** (LLM unreachable):

```json
{
  "status": "error",
  "error": "LLM provider unavailable"
}
```

---

### POST /api/analyze

Run structural analysis from a natural language prompt.

**Request Body**:

```json
{
  "prompt": "Analyze a simply supported beam with 10m span and 5 kN/m UDL"
}
```

**Response**:

```json
{
  "status": "success",
  "analysis_type": "beam",
  "assumptions": [
    "Steel material (E=200 GPa)",
    "Simply supported boundary conditions",
    "Linear elastic analysis"
  ],
  "warnings": [
    "Deflection exceeds L/360 limit"
  ],
  "traces": [
    {
      "agent": "intent",
      "summary": "Detected beam analysis request",
      "data": {
        "structure_type": "beam",
        "analysis_type": "static"
      }
    }
  ],
  "results": {
    "reactions": {
      "RA_kn": 25.0,
      "RB_kn": 25.0
    },
    "max_shear_kn": 25.0,
    "max_moment_kn_m": 62.5,
    "max_deflection_mm": 6.51,
    "max_bending_stress_mpa": 95.2
  },
  "report_markdown": "# Beam Analysis Report\n\n...",
  "diagrams": {
    "shear_kn": [0, 25, -25, 0],
    "moment_kn_m": [0, 62.5, 0],
    "deflection_mm": [0, 6.51, 0]
  }
}
```

---

### POST /api/chat

Chat with the structural analysis assistant. Supports conversation, canvas actions, context-aware queries, and analysis requests.

**Request Body**:

```json
{
  "message": "What is the maximum moment on this frame?",
  "analysis_type": "frame",
  "model": {
    "nodes": [...],
    "members": [...],
    "loads": [...]
  },
  "results": {
    "max_moment_kn_m": 62.5,
    "max_shear_kn": 25.0
  },
  "context": {
    "structure_type": "3d_frame",
    "model_summary": "3-story, 3-bay frame with 9 beam members..."
  }
}
```

**Parameters**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| message | string | Yes | User message (min 1 character) |
| analysis_type | string | No | Analysis type: beam, truss, frame, column, 3d_frame |
| model | object | No | Canvas structure model with nodes, members, loads |
| results | object | No | Previous analysis results for follow-up questions |
| context | object | No | Frontend context (model_summary, structure_type) |

**Response**:

```json
{
  "status": "success",
  "response_type": "conversation",
  "message": "The maximum bending moment on this frame is 62.5 kN-m...",
  "source": "conversation_agent",
  "analysis": null,
  "canvas_action": null
}
```

**Response Types**:

- `conversation`: General chat response or context-aware answer
- `analysis`: Analysis results with diagrams
- `canvas_action`: Canvas manipulation instruction
- `evaluation`: Evaluation of existing analysis results

---

### POST /api/chat/evaluate

Evaluate existing analysis results through the critic agent.

**Request Body**:

```json
{
  "results": {
    "max_moment_kn_m": 62.5,
    "max_shear_kn": 25.0
  },
  "analysis_type": "beam"
}
```

**Response**:

```json
{
  "status": "success",
  "response_type": "evaluation",
  "message": "The analysis results appear reasonable...",
  "analysis": null,
  "canvas_action": null
}
```

---

### POST /api/analyze/structure

Analyze a drawn structure model from the 2D or 3D canvas.

**Request Body**:

```json
{
  "structure_type": "truss",
  "nodes": [
    {
      "id": 1,
      "x": 0.0,
      "y": 0.0,
      "support": "pin"
    },
    {
      "id": 2,
      "x": 5.0,
      "y": 0.0,
      "support": "roller"
    }
  ],
  "members": [
    {
      "id": 1,
      "start_node": 1,
      "end_node": 2,
      "area_m2": 0.001,
      "elastic_modulus_gpa": 200.0
    }
  ],
  "loads": [
    {
      "node_id": 2,
      "fx_kn": 0.0,
      "fy_kn": -10.0
    }
  ]
}
```

**Response**:

```json
{
  "status": "success",
  "analysis_type": "truss",
  "results": {
    "node_displacements": [
      {"node_id": 1, "ux_mm": 0.0, "uy_mm": 0.0},
      {"node_id": 2, "ux_mm": 0.5, "uy_mm": -2.3}
    ],
    "member_forces": [
      {"member_id": 1, "force_kn": 10.0, "status": "tension"}
    ],
    "support_reactions": [
      {"node_id": 1, "rx_kn": -10.0, "ry_kn": 10.0},
      {"node_id": 2, "ry_kn": 0.0}
    ]
  },
  "diagrams": {
    "positions": [...],
    "deflection_mm": [...]
  }
}
```

---

## Load Determination (deterministic, no LLM)

### POST /api/loads/wind

ASCE 7-22 wind loads (simplified MWFRS procedure): velocity pressures, MWFRS pressures, base shear, story forces.

**Request Body**:

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

**Response**: `status: "ok"` with `results` containing `velocity_pressures_kpa`, `mwfrs_pressures`, `base_shear_x_kn`, `base_shear_y_kn`, `roof_uplift_kn`, and `story_forces` (`[{story, z_m, force_kn}]`).

---

### POST /api/loads/seismic

ASCE 7-22 equivalent static force procedure: site coefficients, SDS/SD1, Cs, base shear V, story forces.

**Request Body**:

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

**Response**: `status: "ok"` with `results` containing `site_coefficients`, `design_params`, `base_shear_kn`, and `story_forces` (`[{story, z_m, force_kn}]`).

---

### POST /api/loads/snow

ASCE 7-22 roof snow loads (flat/sloped ps, drift).

**Request Body**:

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

**Response**: `status: "ok"` with `results` containing `flat_roof_ps_kpa`, `sloped_roof_ps_kpa`, `drift_load_kpa`, and `total_design_snow_kpa`.

---

### POST /api/loads/slab

ACI 318 two-way slab analysis (coefficients, reinforcement, deflection).

**Request Body**: `SlabInputs` (span, thickness, loads, reinforcement).

**Response**: `status: "ok"` with `results` containing flexure, deflection, and minimum-thickness checks.

---

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

---

### POST /api/analyze/structure-with-loads

End-to-end: compute wind/seismic story forces, apply them to the drawn 3D model as nodal loads, run the 3D analysis, and report story drifts.

**Request Body**: Same as `/api/loads/apply-story-forces`.

**Response**: `status: "ok"` with `load_results`, `applied`, `warnings`, `model`, `results` (full 3D analysis including `story_response.story_drifts`), and `report_markdown`.

---

### GET /api/projects

List all saved projects.

**Response**:

```json
{
  "status": "success",
  "projects": [
    {
      "id": "uuid-1",
      "name": "My Project",
      "model": { ... },
      "results": { ... },
      "created_at": "2026-05-02T12:00:00Z",
      "updated_at": "2026-05-02T14:00:00Z"
    }
  ]
}
```

### POST /api/projects

Create a new project.

**Request Body**:

```json
{
  "name": "My Project",
  "model": { "nodes": [], "members": [] },
  "results": {}
}
```

**Response**: Returns the created project with generated UUID.

### PUT /api/projects/<id>

Update an existing project.

**Request Body**:

```json
{
  "name": "Updated Name",
  "model": { "nodes": [...], "members": [...] },
  "results": { "max_moment_kn_m": 62.5 }
}
```

**Response**: Returns the updated project.

### DELETE /api/projects/<id>

Delete a project.

**Response**:

```json
{
  "status": "success",
  "message": "Project deleted"
}
```

---

### GET /api/sections

List or search steel sections from the AISC database.

**Query Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| q | string | No | Search query (filters by section name) |
| min_weight | number | No | Minimum weight (lb/ft) |
| max_weight | number | No | Maximum weight (lb/ft) |
| min_depth | number | No | Minimum depth (in) |
| max_depth | number | No | Maximum depth (in) |

**Response**:

```json
{
  "status": "success",
  "sections": [
    {
      "name": "W10x33",
      "depth_in": 9.73,
      "flange_width_in": 7.96,
      "area_in2": 9.71,
      "ix_in4": 171.0,
      "ix_in3": 35.0,
      "weight_lb_per_ft": 33.0
    }
  ],
  "count": 1
}
```

---

### GET /api/sections/<name>

Get properties for a specific steel section.

**Path Parameter**:

| Parameter | Type | Description |
|-----------|------|-------------|
| name | string | Section designation (e.g., "W10x33") |

**Response**:

```json
{
  "status": "success",
  "section": {
    "name": "W10x33",
    "depth_in": 9.73,
    "flange_width_in": 7.96,
    "flange_thickness_in": 0.435,
    "web_thickness_in": 0.29,
    "area_in2": 9.71,
    "ix_in4": 171.0,
    "ix_in3": 35.0,
    "iy_in4": 36.0,
    "iy_in3": 9.04,
    "weight_lb_per_ft": 33.0
  }
}
```

**Error Response** (section not found):

```json
{
  "status": "error",
  "error": "Section not found: W99x999"
}
```

---

### GET /api/history

Get analysis history from SQLite database.

**Query Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| limit | integer | No | Number of results (default: 50) |
| offset | integer | No | Offset for pagination (default: 0) |
| analysis_type | string | No | Filter by analysis type |

**Response**:

```json
{
  "status": "success",
  "history": [
    {
      "id": 1,
      "timestamp": "2026-05-02T12:00:00Z",
      "analysis_type": "beam",
      "prompt": "Analyze a simply supported beam...",
      "results_summary": "Max moment: 62.5 kN-m, Max deflection: 6.51 mm"
    }
  ],
  "count": 1,
  "total": 1
}
```

---

### GET /api/history/<id>

Get a specific analysis from history.

**Path Parameter**:

| Parameter | Type | Description |
|-----------|------|-------------|
| id | integer | History record ID |

**Response**:

```json
{
  "status": "success",
  "history": {
    "id": 1,
    "timestamp": "2026-05-02T12:00:00Z",
    "analysis_type": "beam",
    "prompt": "Analyze a simply supported beam...",
    "results_json": "{...}",
    "report_markdown": "# Beam Analysis Report\n\n..."
  }
}
```

---

### POST /api/export/csv

Export analysis results as CSV.

**Request Body**:

```json
{
  "history_id": 1,
  "include_diagrams": true
}
```

**Response**: Returns `text/csv` content with results data.

---

### POST /api/export/report

Export analysis results as a markdown report.

**Request Body**:

```json
{
  "history_id": 1,
  "include_assumptions": true,
  "include_warnings": true
}
```

**Response**: Returns `text/markdown` content with formatted engineering report.

---

## Error Codes

| HTTP Status | Description |
|-------------|-------------|
| 400 | Bad Request - Invalid request body or parameters |
| 404 | Not Found - Resource not found |
| 500 | Internal Server Error - Analysis or server error |
| 503 | Service Unavailable - LLM provider unavailable |

## Rate Limiting

No rate limiting is applied in development. For production, consider implementing rate limiting middleware.

## CORS

CORS is enabled for all origins in development. Configure `CORS_ORIGINS` in production to restrict access.
