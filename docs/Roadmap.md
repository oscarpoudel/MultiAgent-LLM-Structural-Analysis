# StructAgent Roadmap

Deterministic-first structural engineering assistant. LLM handles routing/conversation only; all numbers come from closed-form equations or FEM solvers.

## Guiding Principles
- **Deterministic-first:** No LLM-generated engineering values.
- **Fallback chains:** OpenSeesPy -> direct stiffness -> closed-form.
- **Code references:** ASCE 7, AISC 360, ACI 318 (preliminary elastic analysis only).
- **Every tool ships with tests.**

## Phase 1 — Core Solvers (DONE)
- [x] Beam (4 support types, closed-form + OpenSeesPy cross-validation)
- [x] Truss (matrix stiffness + OpenSeesPy)
- [x] 2D Frame (OpenSeesPy + direct stiffness fallback)
- [x] Column (Euler buckling + AISC Chapter E)
- [x] 3D Frame (OpenSeesPy ndm=3, ndf=6, rigid diaphragms)
- [x] ASCE 7 load combinations (LRFD + ASD)
- [x] Steel section database (W-shapes, HSS, angles)
- [x] Markdown report formatter
- [x] Slab area-load distribution on canvas

## Phase 2 — Load Determination (DONE)
- [x] **Wind load tool** — ASCE 7-22 simplified procedure: velocity pressure qz, exposure, topographic, gust factor, main wind force resisting system (MWFRS) pressures, internal pressure. Deterministic.
- [x] **Seismic base shear tool** — ASCE 7-22 equivalent static force procedure: SDS/SD1 from site class + spectral params, Ri, Rp, T, Cs, base shear V, story forces, drift check. Deterministic.
- [x] **Snow load tool** — ASCE 7-22 ground snow load, balanced/unbalanced roof snow, drift (simplified). Deterministic.

## Phase 3 — Element Design Checks (DONE)
- [x] **Steel beam section selection** — Given M_u, V_u, L_b, C_b: iterate W-shapes from database, check flexure (phi_b*Mn) and shear (phi_v*Vn), compactness, deflection. Return lightest adequate section.
- [x] **Steel column section selection** — Given P_u, K*L: iterate W-shapes, check phi_c*Pn (AISC E3). Return lightest adequate section.
- [x] **Two-way slab analysis** — Given span, thickness, load, reinforcement: check flexure (ACI 318), deflection, minimum thickness. Deterministic.
- [x] **Concrete beam/column design** — Singly reinforced beam (flexure As/rho/phiMn, one-way shear Vc/stirrup spacing, bar count) and circular tied/spiral column (As, rho limits, phiPn, slenderness check). ACI 318, deterministic.

## Phase 4 — Analysis Integration (IN PROGRESS)
- [x] **Wind/seismic on drawn 3D model** — Apply computed story forces as nodal loads on canvas model (equal or windward distribution), run 3D analysis, report story drifts. `app/tools/story_forces.py` + `/api/loads/apply-story-forces` + `/api/analyze/structure-with-loads`.
- [x] **Story forces via chat/agent** — `apply_story_forces` canvas action (LLM + deterministic fallback) wired through `/api/chat` so users can ask the assistant to apply wind/seismic story forces to the drawn model and analyze.
- [x] **P-delta second-order analysis** — ASCE 7-22 stability coefficient (θ = V·h/W) drift amplification + P-delta equivalent lateral forces for iterative analysis. `app/tools/pdelta.py` + `/api/loads/pdelta-amplify` + `/api/loads/pdelta-forces`.
- [x] **Response spectrum analysis** — Multi-mode (Cantilever) method for 3D structures. `app/tools/response_spectrum.py` + `/api/loads/response-spectrum` + Loads tab "Response Spectrum" subtab. ASCE 7-22 design spectrum, lumped-mass modal analysis (SRSS) from vertical-member story stiffness.

## Phase 5 — Frontend & UX
- [x] **Load determination UI** — Loads tab: wind/seismic/snow forms, results panels with code references, story-force tables, and apply-to-3D-model + analyze.
- [x] **Section selection UI** — Sections tab "Section Selection" subtab: beam (Mu/Vu/Lb/Cb/fy) and column (Pu/KL/fy) forms, recommended section + top-5 candidates.
- [x] **Story drift visualization** — Color-code members by drift/utilization vs 2% limit (canvas "Story drift" toggle + legend).
- [x] **Export to PDF** — Render markdown report to PDF (dependency-free PDF 1.4 writer, `/api/export/pdf`).

## Phase 6 — Quality & Ops
- [x] **Test coverage to 80%+** — Overall 82.64%; 3D solver (opensees_3d) 99%, frame 93%, truss 95%, concrete 100%.
- [x] **Cross-validation suite** — Compare OpenSeesPy vs closed-form vs direct stiffness on benchmark models. `app/tools/cross_validation.py` + `/api/loads/cross-validation`. 20 signed checks across beam/truss/frame; caught and fixed a truss force sign bug and a frame fixed-end-force omission.
- [x] **API docs auto-generation** — OpenAPI 3.0 spec from live Flask routes + Pydantic models. `app/tools/openapi.py` + `GET /api/openapi.json` + `GET /api/docs` (self-contained docs page).
- [x] **CI coverage gate** — Block PRs below 80% (pyproject + ci.yml `--cov-fail-under=80`).

## Backlog Ideas
- [x] Concrete beam/column design (ACI 318) — `app/tools/concrete.py` + `/api/design/concrete-beam` + `/api/design/concrete-column` + UI.
- [x] Timber design (NDS) — `app/tools/timber.py` + `/api/design/timber-beam` + `/api/design/timber-species` + UI.
- [x] Foundation design (footing, pile) — `app/tools/foundation.py` + `/api/design/spread-footing` + `/api/design/pile` + UI.
- [ ] Fatigue analysis
- [ ] Stability (lateral-torsional buckling) checks
- [x] Multi-hazard load combination optimizer — `app/tools/multi_hazard.py` + `/api/analyze/multi-hazard` + UI.
- [x] Cost estimation from section selection — `app/tools/cost.py` + `/api/design/cost` + UI.
- [x] Sensitivity analysis (parametric study) — `app/tools/sensitivity.py` + `/api/analyze/sensitivity` + UI.
