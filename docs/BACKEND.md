# Backend Documentation

## Project Structure

```
app/
├── __init__.py
├── main.py              # Flask app factory, DB init, blueprint wiring
├── config.py            # PydanticSettings from .env
├── models.py            # Pydantic v2 request/response schemas
├── agents.py            # Multi-agent orchestration, context summarizer, canvas router
├── llm.py               # LLM client implementations (Ollama, PydanticAI, disabled)
├── logging_config.py    # Structured logging setup
├── routes/
│   ├── __init__.py
│   ├── pages.py         # Static page routes (/ , /health), OpenAPI spec + docs page
│   ├── analyze.py       # Analysis & chat API routes (+ load-combos, sensitivity, multi-hazard, validate)
│   ├── design.py        # Steel/concrete/timber/foundation/fatigue/cost design routes
│   ├── loads.py         # Wind/seismic/snow/slab/response-spectrum/P-delta/story-forces/cross-validation
│   ├── projects.py      # Project CRUD API routes
│   ├── history.py       # History & export (CSV/report/PDF) API routes
│   └── sections.py      # Steel section database API routes
├── tools/
│   ├── __init__.py
│   ├── beam.py          # Closed-form beam analysis
│   ├── opensees_beam.py # OpenSeesPy beam solver
│   ├── truss.py         # Truss analysis (OpenSeesPy + direct stiffness)
│   ├── frame.py         # 2D frame analysis (OpenSeesPy + direct stiffness)
│   ├── column.py        # Column buckling analysis
│   ├── opensees_3d.py   # 3D structure analysis
│   ├── sections.py      # Steel section database
│   ├── section_select.py# AISC 360 steel section selection (incl. LTB)
│   ├── report.py        # Report formatter
│   ├── pdf_export.py    # Markdown -> PDF writer
│   ├── load_combinations.py  # ASCE 7-22 load combination generator
│   ├── wind.py          # ASCE 7-22 wind loads
│   ├── seismic.py       # ASCE 7-22 seismic base shear
│   ├── snow.py          # ASCE 7-22 snow loads
│   ├── slab.py          # ACI 318 two-way slab
│   ├── story_forces.py  # Map wind/seismic story forces onto a 3D model
│   ├── response_spectrum.py  # Multi-mode response-spectrum analysis
│   ├── pdelta.py        # P-delta drift amplification + equivalent lateral forces
│   ├── concrete.py      # ACI 318 concrete beam/column design
│   ├── timber.py        # NDS timber beam design
│   ├── foundation.py    # Spread footing + pile capacity
│   ├── fatigue.py       # AISC 360 fatigue S-N check
│   ├── cost.py          # Steel cost estimation
│   ├── sensitivity.py   # OAT parametric sensitivity study
│   ├── multi_hazard.py  # Multi-hazard load-combination optimizer
│   ├── cross_validation.py  # Independent-solver cross-validation suite
│   └── openapi.py       # OpenAPI 3.0 spec generator
└── static/              # Frontend assets
```

## app/main.py - Flask Application Entry Point

The Flask application factory that initializes all components.

### Key Components

- **Flask app factory**: `get_app()` creates and configures the Flask instance
- **SQLite database**: a single `analysis_history.db` file (project root) holding two tables:
  - `history` - analysis results: id, timestamp (epoch), analysis_type, prompt, results_json, report_markdown
  - `projects` - user projects: id (UUID), updated_at (epoch), project_json (full payload)
- **Blueprint registration**: Registers route blueprints from `routes/pages.py`, `routes/analyze.py`, `routes/design.py`, `routes/loads.py`, `routes/projects.py`, `routes/history.py`, `routes/sections.py`
- **LLM status check**: `_check_llm_status()` pings Ollama `/api/tags` to verify provider reachability
- **LLM client**: `_get_llm_client()` creates the configured LLM client based on `AGENT_LLM_PROVIDER`

### Database Schema

Both tables live in a single SQLite file (`analysis_history.db` at the project root).

```sql
-- Analysis history
CREATE TABLE history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    analysis_type TEXT NOT NULL,
    prompt TEXT NOT NULL,
    results_json TEXT NOT NULL,
    report_markdown TEXT NOT NULL
);

-- Projects (full project payload stored as JSON)
CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    updated_at REAL NOT NULL,
    project_json TEXT NOT NULL
);
```

## app/routes/analyze.py - Analysis & Chat Routes

The main API routes for analysis and chat functionality.

### API Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/api/chat` | POST | Chat with structural assistant |
| `/api/chat/evaluate` | POST | Evaluate existing analysis results |
| `/api/analyze` | POST | Run analysis from natural language prompt |
| `/api/analyze/structure` | POST | Analyze a drawn structure model |
| `/api/analyze/structure-with-loads` | POST | Apply wind/seismic story forces to a drawn 3D model and analyze |
| `/api/analyze/sensitivity` | POST | OAT parametric sensitivity study (beam) |
| `/api/analyze/multi-hazard` | POST | Multi-hazard load-combination optimizer |
| `/api/load-combinations` | POST | ASCE 7-22 factored load combinations |
| `/api/validate` | POST | Validate a model payload without running analysis |
| `/api/llm-status` | GET | Check LLM provider connectivity |

### Chat Request Classification

- `_is_structural_analysis_request()` - Checks if message requests structural analysis (keywords: analyze, calculate, solve, etc.)
- `_is_context_question()` - Detects questions about the current canvas model (keywords: moment, stress, deflection, reaction, floor, story, height, dimension, bay, grid, etc.)
- `_has_real_context()` - Validates that frontend context contains meaningful model data (not empty defaults)
- `_summarize_canvas_context()` - Extracts engineering summary from model data: floor levels from Z-coordinates, building dimensions, member group counts (beams/columns/braces), active load combination, rigid diaphragm status

### Context Summarizer

`_summarize_canvas_context(context)` produces a structured summary including:

- **Floor levels**: Unique Z-coordinates of nodes (sorted)
- **Dimensions**: X and Y extents of the model
- **Member groups**: Counts of beams, columns, and braces
- **Load combination**: Active load combination name
- **Rigid diaphragm**: Whether enabled
- **Model summary**: Additional details from `model_summary` field

### Canvas Action Router

The `CanvasRouterAgent` routes chat messages to canvas tool actions:

- `clear_analysis` - Clear analysis results from canvas
- `draw_3d_frame_template` - Draw a 3D frame template (3-bay, 3-story)
- `apply_member_group_sections` - Apply steel sections to member groups
- `set_rigid_diaphragm` - Toggle rigid diaphragm option
- `set_load_combination` - Set active load combination
- `clear_canvas` - Clear entire canvas
- `draw_simple_beam` - Draw a simple beam
- `run_current_analysis` - Run analysis on current model
- `apply_story_forces` - Apply wind/seismic story forces to the drawn 3D model and analyze

## app/routes/design.py - Element Design Routes

Deterministic code design checks (no LLM). Each route validates a Pydantic input model and returns `{"status": "ok", "results": ...}`.

| Route | Method | Description |
|-------|--------|-------------|
| `/api/design/beam` | POST | AISC 360 steel beam section selection (incl. LTB) |
| `/api/design/column` | POST | AISC 360 steel column section selection |
| `/api/design/concrete-beam` | POST | ACI 318 singly-reinforced concrete beam design |
| `/api/design/concrete-column` | POST | ACI 318 circular tied/spiral column design |
| `/api/design/timber-species` | GET | List timber species with NDS design values |
| `/api/design/timber-beam` | POST | NDS rectangular timber beam design |
| `/api/design/spread-footing` | POST | ACI 318 square spread footing sizing + checks |
| `/api/design/pile` | POST | Static pile capacity + group efficiency |
| `/api/design/fatigue-categories` | GET | List AISC 360 fatigue categories (A–E) |
| `/api/design/fatigue` | POST | AISC 360 fatigue S-N check |
| `/api/design/cost` | POST | Steel cost estimation from a member takeoff |

## app/routes/loads.py - Load Determination Routes

Deterministic load tools and second-order/advanced analysis (no LLM).

| Route | Method | Description |
|-------|--------|-------------|
| `/api/loads/wind` | POST | ASCE 7-22 wind loads (MWFRS) |
| `/api/loads/seismic` | POST | ASCE 7-22 seismic base shear |
| `/api/loads/snow` | POST | ASCE 7-22 snow loads |
| `/api/loads/slab` | POST | ACI 318 two-way slab analysis |
| `/api/loads/response-spectrum` | POST | Multi-mode response-spectrum analysis on a 3D model |
| `/api/loads/apply-story-forces` | POST | Map wind/seismic story forces onto a drawn 3D model |
| `/api/loads/pdelta-amplify` | POST | P-delta drift amplification (ASCE 7 stability coefficient) |
| `/api/loads/pdelta-forces` | POST | P-delta equivalent lateral forces on a drawn 3D model |
| `/api/loads/cross-validation` | POST | Independent-solver cross-validation suite |

## app/routes/projects.py - Project Persistence

CRUD API for server-backed project storage.

| Route | Method | Description |
|-------|--------|-------------|
| `/api/projects` | GET | List all projects |
| `/api/projects` | POST | Create a new project |
| `/api/projects/<id>` | PUT | Update an existing project |
| `/api/projects/<id>` | DELETE | Delete a project |

Projects store the full model state and analysis results, enabling cross-browser continuity through server-side SQLite storage.

## app/routes/history.py - History & Export Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/api/history` | GET | Get paginated analysis history |
| `/api/history/<item_id>` | GET | Get specific history record |
| `/api/export/csv` | POST | Export analysis as CSV |
| `/api/export/report` | POST | Export analysis as markdown |
| `/api/export/pdf` | POST | Export analysis report as PDF |

## app/routes/sections.py - Section Database Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/api/sections` | GET | List/search steel sections |
| `/api/sections/<name>` | GET | Get specific section properties |

## app/routes/pages.py - Static Page Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Serve index.html |
| `/health` | GET | Health check (DB + NumPy/OpenSees availability) |
| `/api/openapi.json` | GET | Auto-generated OpenAPI 3.0 spec |
| `/api/docs` | GET | Self-contained interactive API docs page |

## app/agents.py - Multi-Agent System

Orchestrates the analysis pipeline using specialized agents with deterministic fallbacks.

### Managed Agents

1. **Conversation Agent**: Handles greetings, conceptual questions, and context-aware queries about the current model. System prompt defines structural analysis expertise.
2. **Intent Agent**: Extracts structural engineering intent from user prompts. Returns JSON with structure_type, analysis_type, boundary_conditions.
3. **Planning Agent**: Selects appropriate solver based on intent. Maps to openseespy_beam, openseespy_truss, openseespy_frame, openseespy_3d_frame, or column_euler_aisc.
4. **Canvas Router Agent**: Routes chat messages to canvas tool actions (8+ supported actions).
5. **Critic Agent**: Validates analysis results for sanity, deflection limits, compression warnings.

### Analysis Pipeline

`StructuralAgentSystem.analyze(prompt)` executes:

1. **Type detection**: Keyword-based detection of analysis type (beam, truss, frame, column, 3d_frame)
2. **Intent extraction**: LLM call with 3s timeout, falls back to deterministic defaults
3. **Planning**: LLM selects solver, falls back to type-based mapping
4. **Input extraction**: Regex-based parameter extraction from prompt text
5. **Solver execution**: Calls appropriate tool (beam, truss, frame, column, 3d)
6. **Critic validation**: Checks result sanity, deflection limits, compression warnings
7. **Report generation**: Formats markdown engineering report

### Input Extraction Methods

- `_extract_beam_inputs()`: Parses span, UDL, point loads, E, I, A, section modulus, support type via regex
- `_extract_truss_inputs()`: Parses JSON or creates default Warren truss with extracted span/height/load
- `_extract_frame_inputs()`: Parses JSON or creates default portal frame with extracted width/height/loads
- `_extract_column_inputs()`: Parses length, area, inertia, E, Fy, end condition, axial load
- `_extract_3d_inputs()`: Parses JSON or creates default 3D cantilever column

### Support Type Detection

- `detect_analysis_type()`: Keywords for truss, frame, column, 3d; defaults to beam
- `detect_support_type()`: Keywords for cantilever, fixed-fixed, propped cantilever; defaults to simply_supported

## app/models.py - Pydantic Schemas

All request/response models and input schemas using Pydantic v2.

### Request Models

- **AnalyzeRequest**: prompt (min 5 chars)
- **ChatRequest**: message (min 1 char), optional `analysis_type`, optional `model` (canvas structure), optional `results` (previous analysis), optional `context` (frontend context with model_summary)
- **EvaluateRequest**: results (dict), analysis_type, messages (chat history)

### Beam Inputs

- **PointLoad**: magnitude_kn, position_m
- **BeamInputs**: span_m, udl_kn_per_m, point_loads, elastic_modulus_gpa, inertia_m4, area_m2, section_modulus_m3, deflection_limit_ratio, support_type

### Truss Inputs

- **TrussNode**: id, x, y, support (free/pin/roller_x/roller_y/fixed)
- **TrussMember**: id, start_node, end_node, area_m2, elastic_modulus_gpa
- **TrussLoad**: node_id, fx_kn, fy_kn
- **TrussInputs**: nodes, members, loads

### Frame Inputs

- **FrameNode**: id, x, y, support (free/pin/roller/fixed)
- **FrameMember**: id, start_node, end_node, area_m2, inertia_m4, elastic_modulus_gpa
- **FrameLoad**: node_id, fx_kn, fy_kn, moment_kn_m
- **FrameMemberLoad**: member_id, udl_kn_per_m
- **FrameInputs**: nodes, members, nodal_loads, member_loads

### Column Inputs

- **ColumnInputs**: length_m, area_m2, inertia_m4, elastic_modulus_gpa, yield_stress_mpa, end_condition, axial_load_kn

### 3D Structure Inputs

- **Support3D**: ux, uy, uz, rx, ry, rz (boolean DOF constraints)
- **Node3D**: id, x, y, z, support
- **Member3D**: id, start_node, end_node, area_m2, iy_m4, iz_m4, j_m4, elastic_modulus_gpa, shear_modulus_gpa, group
- **Load3D**: node_id, case, fx_kn, fy_kn, fz_kn, mx_kn_m, my_kn_m, mz_kn_m
- **MemberLoad3D**: member_id, case, wy_kn_per_m, wz_kn_per_m
- **LoadCombination3D**: name, factors (dict of load-case factors)
- **Structure3DInputs**: nodes, members, nodal_loads, member_loads, load_combinations, active_load_combination, rigid_diaphragms

### Load Determination Inputs

- **WindInputs**: basic_wind_speed_ms, exposure, height_m, length_m, width_m, story_height_m, internal_pressure, topographic_factor, air_density_factor
- **SeismicInputs**: spectral_accel_sd, spectral_accel_1s, site_class, risk_category, building_weight_kn, fundamental_period_s, height_m, structural_system, importance_factor, response_modification, deflection_amplifier
- **SnowInputs**: ground_snow_load_kpa, exposure, thermal, risk_category, roof_slope_deg, drift
- **SlabInputs**: span_x_m, span_y_m, thickness_m, dead_load_kpa, live_load_kpa, concrete_fck_mpa, steel_fy_mpa, support_condition, deflection_limit_ratio

### Element Design Inputs

- **BeamSelectionInputs**: moment_kn_m, shear_kn, unbraced_length_m, cb, fy_mpa
- **ColumnSelectionInputs**: axial_load_kn, kl_m, fy_mpa
- **ConcreteBeamInputs**: moment_kn_m, shear_kn, width_mm, depth_mm, effective_depth_mm, concrete_fck_mpa, steel_fy_mpa, bar_dia_mm, stirrup_dia_mm
- **ConcreteColumnInputs**: axial_load_kn, diameter_mm, concrete_fck_mpa, steel_fy_mpa, tied, kl_r
- **TimberBeamInputs**: species, width_mm, depth_mm, moment_kn_m, shear_kn, span_m, unbraced_length_m, duration, moisture_pct, temperature_c, live_load_fraction
- **SpreadFootingInputs**: axial_load_kn, factored_axial_kn, allowable_bearing_kpa, column_width_mm, column_depth_mm, concrete_fck_mpa, steel_fy_mpa, footing_depth_mm, bar_dia_mm, footing_width_mm
- **PileInputs**: pile_diameter_mm, pile_length_m, skin_friction_kpa, skin_friction_alpha, end_bearing_kpa, factor_of_safety, piles_per_row, rows_in_group, center_to_center_spacing_m
- **FatigueInputs**: category, stress_range_mpa, num_cycles

### Advanced Analysis Inputs

- **SensitivityInputs**: base + min/max bounds for load/span/modulus/inertia/section, and a `parameters` list (w, L, E, I, S)
- **MultiHazardInputs**: dead/live/wind/snow/earthquake loads, response_factor, capacity, method, per-component sweep bounds, and a `components` list

### Response Models

- **AgentTrace**: agent, summary, data
- **DiagramData**: positions, shear_kn, moment_kn_m, deflection_mm
- **AnalyzeResponse**: status, analysis_type, assumptions, warnings, traces, results, report_markdown, diagrams
- **CanvasAction**: action, arguments
- **CanvasToolDecision**: action, arguments, message, confidence
- **ChatResponse**: status, response_type, message, source, analysis, canvas_action
- **EvaluateResponse**: status, response_type, message, analysis, canvas_action

## app/llm.py - LLM Clients

Three LLM client implementations with a unified `generate(system, prompt)` interface:

1. **DisabledLLMClient**: Raises RuntimeError on any call. Used when `agent_llm_provider=none`.
2. **OllamaClient**: Direct HTTP POST to Ollama `/api/generate` endpoint with temperature=0.1
3. **PydanticAIClient**: Uses the PydanticAI adapter with an OpenAI-compatible client for structured output (falls back to `OllamaClient` if the adapter is unavailable)

## app/config.py - Settings

PydanticSettings loaded from `.env` file with defaults:

| Setting | Default | Description |
|---------|---------|-------------|
| ollama_base_url | http://localhost:11434 | Ollama server URL |
| ollama_model | glm-4.7-flash:latest | Model name |
| agent_llm_provider | ollama | Provider: `ollama`, `pydanticai`, or `none` |
| agent_llm_timeout_s | 8.0 | Timeout for LLM calls |
| app_env | development | Environment |
| app_secret_key | (random 32-byte hex if unset) | Flask secret key |

`get_settings()` is cached with `@lru_cache` for performance. If `app_secret_key` is not set, a random key is generated at startup.

## app/logging_config.py - Logging

Structured logging configuration used across the application. Sets up console and file logging with consistent format including timestamps, log levels, and module names.
