# StructAgent - Architecture Overview

## Project Summary

**StructAgent** is a Flask-based structural analysis assistant that combines multi-agent LLM workflows with deterministic engineering solvers (closed-form equations and OpenSeesPy FEM). It provides a web UI for conversational structural analysis, interactive 3D canvas drawing, context-aware chat, project persistence, and automated engineering reports.

**Scope:** Preliminary elastic analysis only. Not for licensed professional design.

**License:** PolyForm Noncommercial 1.0.0

## High-Level Architecture

The application follows a layered architecture with clear separation between frontend, backend routing, agent orchestration, and deterministic solvers.

```
Frontend (Vanilla JS)
  Chat | 3D Canvas | Results | Sections
  State Manager (state.js -> S object)
  Modules: analysis.js, main.js, projects.js, api.js, dom.js
  canvas3d/{index,scene,render,interaction,ui}.js
        |
        | HTTP/JSON
        v
Backend (Flask)
  Routes:        pages.py, analyze.py, design.py, loads.py,
                 projects.py, history.py, sections.py
  Agent System:  agents.py (context summarizer + canvas tool router)
  LLM Clients:   llm.py (Ollama / PydanticAI / disabled)
  Tools:         beam, opensees_beam, truss, frame, column, opensees_3d,
                 sections, section_select, wind, seismic, snow, slab,
                 story_forces, response_spectrum, pdelta, concrete, timber,
                 foundation, fatigue, cost, sensitivity, multi_hazard,
                 cross_validation, load_combinations, report, pdf_export,
                 openapi
  Data:          analysis_history.db (SQLite: history + projects tables)
  Logging:       logging_config.py
```

## Component Map

| Layer | File(s) | Responsibility |
|-------|---------|----------------|
| **Entry** | `app/main.py` | Flask app factory, DB schema, blueprint wiring, LLM status check |
| **Routes** | `app/routes/pages.py` | `GET /`, `GET /health`, `GET /api/openapi.json`, `GET /api/docs` |
| **Routes** | `app/routes/analyze.py` | `POST /api/analyze`, `POST /api/chat`, `POST /api/chat/evaluate`, `POST /api/analyze/structure`, `POST /api/analyze/structure-with-loads`, `POST /api/analyze/sensitivity`, `POST /api/analyze/multi-hazard`, `POST /api/load-combinations`, `POST /api/validate`, `GET /api/llm-status` |
| **Routes** | `app/routes/design.py` | Steel/concrete/timber/foundation/fatigue/cost design endpoints |
| **Routes** | `app/routes/loads.py` | Wind/seismic/snow/slab/response-spectrum/P-delta/story-forces/cross-validation endpoints |
| **Routes** | `app/routes/projects.py` | `CRUD /api/projects` (SQLite-backed project persistence) |
| **Routes** | `app/routes/history.py` | `GET /api/history`, `GET /api/history/<id>`, `POST /api/export/csv\|report\|pdf` |
| **Routes** | `app/routes/sections.py` | `GET /api/sections`, `GET /api/sections/<name>` |
| **Agents** | `app/agents.py` | Multi-agent orchestration, context summarizer, intent detection, canvas tool router |
| **Models** | `app/models.py` | Pydantic schemas for all inputs/outputs |
| **LLM** | `app/llm.py` | Ollama, PydanticAI (OpenAI-compatible), and disabled LLM clients |
| **Config** | `app/config.py` | PydanticSettings from .env |
| **Logging** | `app/logging_config.py` | Structured logging setup |
| **Beam Solver** | `app/tools/beam.py` | Closed-form beam analysis (4 support types) |
| **Beam FEM** | `app/tools/opensees_beam.py` | OpenSeesPy beam with cross-validation |
| **Truss** | `app/tools/truss.py` | OpenSeesPy truss + direct stiffness fallback |
| **Frame** | `app/tools/frame.py` | OpenSeesPy frame + direct stiffness fallback |
| **Column** | `app/tools/column.py` | Euler buckling + AISC Chapter E |
| **3D Frame** | `app/tools/opensees_3d.py` | OpenSeesPy 3D (ndm=3, ndf=6) |
| **Load Combos** | `app/tools/load_combinations.py` | ASCE 7-22 load combination generator |
| **Reports** | `app/tools/report.py` | Markdown engineering report formatter |
| **PDF Export** | `app/tools/pdf_export.py` | Dependency-free Markdown → PDF writer |
| **Sections** | `app/tools/sections.py` | AISC W-shape, HSS, Angle database |
| **Section Select** | `app/tools/section_select.py` | AISC 360 steel beam/column selection (incl. LTB) |
| **Wind** | `app/tools/wind.py` | ASCE 7-22 wind loads (MWFRS) |
| **Seismic** | `app/tools/seismic.py` | ASCE 7-22 seismic base shear |
| **Snow** | `app/tools/snow.py` | ASCE 7-22 snow loads |
| **Slab** | `app/tools/slab.py` | ACI 318 two-way slab |
| **Story Forces** | `app/tools/story_forces.py` | Map wind/seismic story forces onto a 3D model |
| **Response Spectrum** | `app/tools/response_spectrum.py` | Multi-mode response-spectrum analysis |
| **P-Delta** | `app/tools/pdelta.py` | P-delta drift amplification + equivalent lateral forces |
| **Concrete** | `app/tools/concrete.py` | ACI 318 concrete beam/column design |
| **Timber** | `app/tools/timber.py` | NDS timber beam design |
| **Foundation** | `app/tools/foundation.py` | Spread footing + pile capacity |
| **Fatigue** | `app/tools/fatigue.py` | AISC 360 fatigue S-N check |
| **Cost** | `app/tools/cost.py` | Steel cost estimation |
| **Sensitivity** | `app/tools/sensitivity.py` | OAT parametric sensitivity study |
| **Multi-Hazard** | `app/tools/multi_hazard.py` | Multi-hazard load-combination optimizer |
| **Cross-Validation** | `app/tools/cross_validation.py` | Independent-solver cross-validation suite |
| **OpenAPI** | `app/tools/openapi.py` | OpenAPI 3.0 spec generator |
| **Frontend** | `app/static/` | HTML, CSS, vanilla JS modules |
| **Scripts** | `scripts/debug_chat.py` | CLI debug tool for testing chat/analysis |

## Data Flow

### Analysis Request Flow
1. User types prompt in chat or uses quick-prompt buttons
2. Frontend sends `POST /api/chat` with message + optional model/analysis context
3. `analyze.py` validates request with Pydantic schemas
4. If a canvas model exists and question is context-related, context summarizer extracts floor levels, dimensions, member groups, load combo
5. `agents.py` routes through intent → planning → execution (or canvas tool, or conversation)
6. Intent agent extracts parameters from natural language
7. Planning agent selects solver
8. Solver tool runs (OpenSeesPy or closed-form) with fallback chain
9. Critic agent validates results
10. Report formatter generates markdown
11. Results saved to SQLite history
12. Response returned to frontend with analysis data and diagrams

### Context-Aware Chat Flow
1. User has a 3D structure on canvas (with model data in frontend state)
2. User asks "What is the maximum moment on this frame?"
3. Frontend sends `POST /api/chat` with `message` + `model` + `results` + `context`
4. `_is_context_question()` detects context keywords (moment, stress, floor, story, deflection, etc.)
5. `_has_real_context()` validates that the context is non-trivial
6. `_summarize_canvas_context()` extracts floor levels from Z-coordinates, building X/Y dimensions, member group counts, active load combo, rigid diaphragm status
7. LLM receives the summarized context + user question and answers based on it
8. If the user asks for an analysis change, the canvas action router decides which action to take

### Canvas Tool Routing Flow
1. User message is classified as needing a canvas action
2. `CanvasRouterAgent` selects from available actions:
   - `clear_analysis` - Clear analysis results
   - `draw_3d_frame_template` - Draw a 3D frame template
   - `apply_member_group_sections` - Apply steel sections to member groups
   - `set_rigid_diaphragm` - Toggle rigid diaphragm
   - `set_load_combination` - Set active load combination
   - `clear_canvas` - Clear entire canvas
   - `draw_simple_beam` - Draw a simple beam
   - `run_current_analysis` - Run analysis on current model
3. Action is validated and returned as `canvas_action` in response

### Project Persistence Flow
1. On page load, frontend fetches existing projects via `GET /api/projects`
2. Autosave timer (2s debounce) + beforeunload event save model/results to server
3. `PUT /api/projects/<id>` sends model snapshot and analysis results
4. New IndexedDB projects auto-migrate to server database on first load
5. Projects are cross-browser via server SQLite

### LLM Status Check Flow
1. On page load + every 30s, frontend calls `GET /api/llm-status`
2. Backend pings Ollama `/api/tags` to check reachability
3. Green dot = LLM reachable, yellow = checking, red = offline
4. Chat header shows current status; LLM-unavailable routes return 503

## Key Design Decisions

1. **Deterministic-first:** Solvers use closed-form equations and FEM, not LLM-generated numbers
2. **LLM for routing only:** LLM handles intent detection, parameter extraction, and conversation
3. **Context-aware LLM:** Chat responses include summarized building model data (floors, dimensions, member groups) so the agent can answer questions about the current structure
4. **Canvas tool router:** Specialized agent for converting chat messages into modeling/analysis actions on the 3D canvas
5. **Fallback chains:** OpenSeesPy -> direct stiffness -> closed-form, ensuring analysis always runs
6. **Pydantic validation:** All inputs validated before reaching solvers
7. **SQLite history:** All analyses persisted for traceability
8. **Server-backed projects:** Projects stored in server SQLite for cross-browser continuity
9. **Autosave:** Automatic project save (2s debounce + beforeunload) prevents data loss
10. **Canvas integration:** Drawing produces analyzable models, bridging visual and computational workflows
11. **Lightweight LLM health check:** Simple ping endpoint avoids expensive model loading for status monitoring
12. **Quick-prompt buttons:** Replace example dropdown for faster access to common analysis starters
