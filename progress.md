# Progress

## Current Goal
Build StructAgent into a full deterministic-first structural engineering software system: load determination (wind/seismic/snow), element design (section selection, slabs), analysis integration, and frontend UX.

## Agent Rules
- Do not ask questions unless truly blocked.
- Make reasonable assumptions and continue.
- Work on unfinished TODOs in order.
- Mark completed TODOs with [x].
- Add new bugs, ideas, and follow-up work as TODOs.
- Run tests, lint, or build when available.
- Do not run destructive commands, force pushes, production deploys, or database resets.
- Never fabricate engineering results; all numbers come from deterministic solvers.

## Active TODO
- [ ] Improve test coverage for 3d solver (opensees_3d now ~79%; frame 93%, truss 95%).

## Completed
- [x] Created progress.md.
- [x] Checkpoint: lint/import-ordering pass (all tests green).
- [x] Wrote docs/Roadmap.md with prioritized roadmap.
- [x] ASCE 7-22 wind load tool (velocity pressure, MWFRS pressures, base shear, story forces) + route + tests.
- [x] ASCE 7-22 seismic base shear tool (site coefficients, SDS/SD1, Cs, V, story forces) + route + tests.
- [x] ASCE 7-22 snow load tool (flat/sloped ps, drift) + route + tests.
- [x] ACI 318 two-way slab analysis tool (coefficients, reinforcement, deflection) + route + tests.
- [x] AISC 360 steel beam section selection (LTB + shear) + route + tests.
- [x] AISC 360 steel column section selection (E3) + route + tests.
- [x] Fix reaction sign in direct-stiffness frame/truss fallbacks (R = -penalty*U); add fallback + report tests.
- [x] Integrate wind/seismic story forces onto drawn 3D model: app/tools/story_forces.py (equal/windward nodal distribution) + POST /api/loads/apply-story-forces + POST /api/analyze/structure-with-loads (end-to-end 3D analysis + story drifts) + tests.
- [x] Test count 117 -> 156; coverage 68.1% -> 78.92%.
- [x] Load-determination UI: Loads tab with Wind/Seismic/Snow subtabs, input forms, results panels (factors, story-force tables, warnings), and "Apply to 3D Model & Analyze" button wired to /api/analyze/structure-with-loads. app/static/js/loads.js + api.js + index.html + styles.css. Verified: 156 tests pass, all 3 endpoints return ok, page serves Loads tab.
- [x] Section-selection UI: Sections tab gains a "Section Selection" subtab with Beam (Mu/Vu/Lb/Cb/fy) and Column (Pu/KL/fy) forms wired to /api/design/beam + /api/design/column. Renders selected section, properties, utilization, and top-5 candidate table. sections.js + api.js + index.html + styles.css. Verified: 156 tests pass, both endpoints return ok (W310X39 / W200X36), page serves selection UI.
- [x] Wire story-force application into chat/canvas agent path: new `apply_story_forces` canvas action (LLM prompt + deterministic fallback in agents.py), chat route passes it through, frontend runCanvasAction -> analyzeStructureWithLoads -> renderResults. 4 new tests (route passthrough + wind/seismic/sections fallback routing). Test count 156 -> 160; coverage 78.92% -> 79.70%.

## Backlog Ideas
- [ ] Concrete beam/column design (ACI 318).
- [ ] P-delta second-order analysis.
- [ ] Response spectrum (Cantilever) analysis.
- [ ] Story drift visualization on canvas.
- [ ] Export report to PDF.
- [ ] OpenAPI/Swagger auto-generation.

## Blocked
- None.
