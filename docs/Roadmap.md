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

## Phase 4 — Analysis Integration (IN PROGRESS)
- [x] **Wind/seismic on drawn 3D model** — Apply computed story forces as nodal loads on canvas model (equal or windward distribution), run 3D analysis, report story drifts. `app/tools/story_forces.py` + `/api/loads/apply-story-forces` + `/api/analyze/structure-with-loads`.
- [x] **Story forces via chat/agent** — `apply_story_forces` canvas action (LLM + deterministic fallback) wired through `/api/chat` so users can ask the assistant to apply wind/seismic story forces to the drawn model and analyze.
- [ ] **P-delta second-order analysis** — Story drift, P-delta moment amplification for frames.
- [ ] **Response spectrum analysis** — Multi-mode (Cantilever) method for 3D structures.

## Phase 5 — Frontend & UX
- [x] **Load determination UI** — Loads tab: wind/seismic/snow forms, results panels with code references, story-force tables, and apply-to-3D-model + analyze.
- [x] **Section selection UI** — Sections tab "Section Selection" subtab: beam (Mu/Vu/Lb/Cb/fy) and column (Pu/KL/fy) forms, recommended section + top-5 candidates.
- [ ] **Story drift visualization** — Color-code members by drift/utilization.
- [ ] **Export to PDF** — Render markdown report to PDF.

## Phase 6 — Quality & Ops
- [x] **Test coverage to 80%+** — Overall 80.12%; 3D solver (opensees_3d) 94%, frame 93%, truss 95%.
- [ ] **Cross-validation suite** — Compare OpenSeesPy vs closed-form vs direct stiffness on benchmark models.
- [ ] **API docs auto-generation** — OpenAPI/Swagger from Pydantic models.
- [ ] **CI coverage gate** — Block PRs below threshold.

## Backlog Ideas
- [ ] Concrete beam/column design (ACI 318)
- [ ] Timber design (NDS)
- [ ] Foundation design (footing, pile)
- [ ] Fatigue analysis
- [ ] Stability (lateral-torsional buckling) checks
- [ ] Multi-hazard load combination optimizer
- [ ] Cost estimation from section selection
- [ ] Sensitivity analysis (parametric study)
