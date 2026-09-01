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
- [ ] Improve test coverage for frame/truss/3d solvers (currently <50%).
- [ ] Add snow load tool (ASCE 7-22).
- [ ] Integrate wind/seismic loads onto drawn 3D model (apply as nodal loads).
- [ ] Add load-determination UI (wind/seismic/snow forms + results panel).
- [ ] Add section-selection UI (member group -> recommended section).

## Completed
- [x] Created progress.md.
- [x] Checkpoint: lint/import-ordering pass (all tests green).
- [x] Wrote docs/Roadmap.md with prioritized roadmap.
- [x] ASCE 7-22 wind load tool (velocity pressure, MWFRS pressures, base shear, story forces) + route + tests.
- [x] ASCE 7-22 seismic base shear tool (site coefficients, SDS/SD1, Cs, V, story forces) + route + tests.
- [x] ACI 318 two-way slab analysis tool (coefficients, reinforcement, deflection) + route + tests.
- [x] AISC 360 steel beam section selection (LTB + shear) + route + tests.
- [x] AISC 360 steel column section selection (E3) + route + tests.
- [x] Test count 54 -> 117; coverage 63% -> 68.1%.

## Backlog Ideas
- [ ] Concrete beam/column design (ACI 318).
- [ ] P-delta second-order analysis.
- [ ] Response spectrum (Cantilever) analysis.
- [ ] Story drift visualization on canvas.
- [ ] Export report to PDF.
- [ ] OpenAPI/Swagger auto-generation.

## Blocked
- None.
