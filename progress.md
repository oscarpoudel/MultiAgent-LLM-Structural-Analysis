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
- [ ] Multi-hazard load combination optimizer.
- [ ] Sensitivity analysis (parametric study).

## Completed
- [x] Response spectrum (Cantilever) analysis: app/tools/response_spectrum.py — ASCE 7-22 design spectrum (Eq. 11.4-1..6), lumped floor-mass shear-building/cantilever idealization built from vertical members (3EI/L³ free, 12EI/L³ with rigid diaphragms), numpy eigendecomposition, modal participation factors, SRSS combination of modal floor forces/shears/displacements, drift ratios. POST /api/loads/response-spectrum. Loads tab "Response Spectrum" subtab (SDS/SD1/W/direction/modes/TL) wired to the current 3D model. Fixed ASCE 7 Ts bug in seismic.py (was SDS/SD1, now SD1/SDS). 6 tool+route tests. Test count 199 -> 206.
- [x] Story drift visualization: "Story drift" display toggle + legend in canvas toolbar; members color-coded green/amber/red by drift utilization vs 2% limit (drift_ratio_delta_over_h / 0.02). Added explicit drift_ratio_delta_over_h field to opensees_3d story response (kept h/delta drift_ratio for compat). Loads-tab 3D analyses now store results in S.results and auto-enable the overlay.
- [x] Export report to PDF: app/tools/pdf_export.py — dependency-free PDF 1.4 writer (Helvetica, paginated, markdown tables/headings/code stripped, xref offsets verified). POST /api/export/pdf + "PDF" button in results panel. 4 tests. Test count 206 -> 210; coverage 81.33% -> 81.89%.
- [x] Fixed pre-existing lint debt (ruff clean across app+tests: import order, unused var, N802 noqa on OpenSeesPy API mirrors).
- [x] Cross-validation suite: app/tools/cross_validation.py — compares closed-form vs OpenSeesPy FEM vs direct-stiffness fallback on beam/truss/frame benchmarks (20 signed checks, 2% rel tol). POST /api/loads/cross-validation. 6 tests. **Caught and fixed 2 real bugs:** (1) truss OpenSees force extraction had a sign error (tension reported as compression) — eleForce returns global end forces = -member force, so axial = -(fx1·c+fy1·s); (2) frame direct-stiffness member forces omitted the fixed-end force contribution (moments off by wL²/12) — now FEF + k·u. Test count 210 -> 216; coverage 81.89% -> 82.42%.
- [x] OpenAPI/Swagger auto-generation + CI coverage gate: app/tools/openapi.py introspects the live Flask app to emit an OpenAPI 3.0 spec (Pydantic body models inlined, nested $defs promoted to components, free-form bodies for model+load endpoints). GET /api/openapi.json + GET /api/docs (self-contained, offline-capable API docs page, no CDN). CI coverage gate raised 60% -> 80% (pyproject + ci.yml). 7 tests. Test count 216 -> 223; coverage 82.42% -> 82.64%.
- [x] Cost estimation from section selection: app/tools/cost.py — steel cost estimate from a member takeoff (section + length per group), weights resolved from the section database (weight_kg_per_m * length_m), material cost = total_weight_kg * price_per_kg, total = material * fab_factor * erect_factor, cost_per_ton, unknown sections skipped with warnings, input validation. POST /api/design/cost. UI: Sections tab "Cost Estimate" subtab (takeoff form + results table). 7 tests. Test count 223 -> 230; coverage 82.64% -> 82.83%.
- [x] Timber design (NDS): app/tools/timber.py — NDS 2024 ASD timber beam design. Reference design values (Fb/Fv/E) for 6 species (Supplement Table 4A), adjustment factors CD (duration, Table 2.3.2), CM (wet service), Ct (temperature), CF (size, (3/d)^(1/9)), CL (beam stability, Section 3.7.4 with rb/fbe). Checks: flexure (M/S vs Fb'), shear (1.5V/A vs Fv'), deflection (5ML²/48EI vs L/240 total, L/360 live). Routes GET /api/design/timber-species + POST /api/design/timber-beam. UI: Sections tab "Timber Design" subtab (species/section/loads/duration/moisture form + checks table + PASS/FAIL). 12 tests. Test count 230 -> 242; coverage 82.83% -> 82.95%.
- [x] Foundation design (footing + pile): app/tools/foundation.py — ACI 318-19 spread footing (bearing sizing from allowable capacity, one-way & punching shear at critical sections, flexure with iterated stress-block depth, bar count/spacing) + static pile capacity (skin friction alpha*f*A_shaft + end bearing q_p*A_p, FS, Converse-Labarre group efficiency). Routes POST /api/design/spread-footing + POST /api/design/pile. UI: Sections tab "Foundation" subtab (Spread Footing / Pile Capacity forms + checks/capacity tables). 16 tests. Test count 242 -> 258; coverage 82.95% -> 83.35%.
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
- [x] Improve 3D solver test coverage: opensees_3d 79% -> 94% (added _run_static_combo FakeOps test covering load application, zero-factor case skipping, dangling-member skip, rigid-diaphragm constraints, plus story-response average-drift/zero-drift and single-level/single-node diaphragm noops). Test count 160 -> 165; coverage 79.70% -> 80.12% (crossed 80% target).
- [x] Concrete design (ACI 318): app/tools/concrete.py — singly reinforced beam (flexure As/rho/phiMn + one-way shear Vc/stirrup spacing + bar count/spacing) and circular tied/spiral column (As, rho limits, phiPn, slenderness check). Fixed a stress-block-depth bug (a = As*fy/(0.85*f'c*b)) and a min-reinforcement bug (rho_design always >= rho_min). Routes /api/design/concrete-beam + /api/design/concrete-column. UI: Sections tab "Concrete Design" subtab (beam/column forms + results). 16 tool tests + 3 route tests. Test count 165 -> 184; coverage 80.12% -> 80.96%; concrete.py 100%.
- [x] P-delta second-order analysis: app/tools/pdelta.py — ASCE 7-22 stability coefficient (theta = V*h/W) amplification of first-order story drifts (1/(1-theta), capped at theta 0.90, flagged at theta>=1) + P-delta equivalent lateral forces (W_above*drift/h_story) mapped onto the 3D model for iterative analysis. Routes /api/loads/pdelta-amplify + /api/loads/pdelta-forces. UI: Loads tab "P-delta" subtab (auto-uses last 3D drifts). 13 tool tests + 2 route tests. Test count 184 -> 199; coverage 80.96% -> 81.33%; pdelta.py 98%.

## Backlog Ideas
- [x] Concrete beam/column design (ACI 318).
- [x] P-delta second-order analysis.
- [x] Response spectrum (Cantilever) analysis.
- [x] Story drift visualization on canvas.
- [x] Export report to PDF.
- [x] OpenAPI/Swagger auto-generation.
- [x] Timber design (NDS).
- [x] Foundation design (footing, pile).
- [ ] Multi-hazard load combination optimizer.
- [x] Cost estimation from section selection.
- [ ] Sensitivity analysis (parametric study).

## Blocked
- None.
