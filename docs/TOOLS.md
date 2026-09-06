# Tools Documentation

## app/tools/__init__.py - Tools Package

Package marker for the deterministic engineering tool layer. Tool functions are imported directly from their modules (e.g. `from app.tools.beam import ...`).

## app/tools/beam.py - Beam Analysis Tool

Closed-form beam analysis with 4 support types and superposition-based calculations.

**Supported Support Types**:
- simply_supported: Simply supported beam
- cantilever: Cantilever beam (fixed-free)
- fixed_fixed: Fixed-fixed beam
- propped_cantilever: Propped cantilever (fixed-simple)

**Functions**:

- `analyze_beam(inputs: BeamInputs) -> dict`: Main entry point for beam analysis
- `analyze_simply_supported_udl(inputs: BeamInputs) -> dict`: Convenience path for the simply-supported UDL case
- `_validate_beam_inputs(inputs)`: Validate inputs and collect warnings
- `_simply_supported_udl / _point`, `_cantilever_udl / _point`, `_fixed_fixed_udl / _point`, `_propped_cantilever_udl / _point`: Per-support-type reaction/shear/moment/deflection equations
- `_deflection_closed_form`, `_point_load_deflection`: Closed-form deflection
- `_compute_beam_diagrams(inputs, e_pa)`: Build SFD/BMD/deflection diagram data

**Closed-Form Equations**:

Each support type has specific equations for:
- Reactions at supports
- Shear force V(x) along the beam
- Bending moment M(x) along the beam
- Deflection y(x) along the beam
- Maximum values and their positions

**Output**:

Returns dict with:
- reactions: Support reactions (RA, RB, MA, MB)
- shear_force: Array of (x, V) values
- bending_moment: Array of (x, M) values
- deflection: Array of (x, y) values
- max_shear: Maximum shear force and position
- max_moment: Maximum bending moment and position
- max_deflection: Maximum deflection and position
- max_bending_stress: Maximum bending stress
- max_shear_stress: Maximum shear stress
- warnings: List of engineering warnings

## app/tools/opensees_beam.py - OpenSeesPy Beam Solver

Finite element beam analysis using OpenSeesPy for complex loading and support conditions.

**Functions**:

- `analyze_beam_opensees(inputs: BeamInputs) -> dict`: Main solver entry point
- `analyze_simply_supported_udl_opensees(inputs: BeamInputs) -> dict`: Convenience path for the simply-supported UDL case
- `_build_node_positions`, `_find_nearest_node`: Discretize the span and map point loads to nodes

**Model Setup**:

- Uses ElasticBeam2d elements with specified E and I
- Linear elastic material
- Static plain analysis with PARDISO solver
- Load patterns with point and distributed loads

**Output**:

Returns dict with:
- node_displacements: Node displacement vectors
- element_forces: Element end forces
- shear_force: Shear force diagram data
- bending_moment: Bending moment diagram data
- deflection: Deflection diagram data
- reactions: Support reactions

## app/tools/truss.py - Truss Analysis Tool

Planar truss analysis with an OpenSeesPy path and a direct-stiffness fallback.

**Functions**:

- `analyze_truss(inputs: TrussInputs) -> dict`: Main entry point (OpenSeesPy, falls back to direct stiffness)
- `_analyze_truss_opensees(inputs)`: OpenSeesPy truss solve
- `_analyze_truss_direct_stiffness(inputs, fallback_reason)`: Direct stiffness fallback (assembles K, applies BCs, solves, back-substitutes member forces and reactions)

**Algorithm**:

1. Build element stiffness matrices in global coordinates
2. Assemble global stiffness matrix K
3. Apply boundary conditions (remove constrained DOFs)
4. Solve K_reduced * u = F_reduced for displacements
5. Back-substitute to get full displacement vector
6. Calculate member forces: F = EA/L * [-1 1] * u_member
7. Calculate support reactions

**Output**:

Returns dict with:
- node_displacements: Node displacement vectors (ux, uy)
- member_forces: Axial force in each member (positive = tension)
- member_stresses: Axial stress in each member
- support_reactions: Reaction forces at supports
- stability_check: Determinacy status (statically determinate, indeterminate, unstable)
- warnings: List of engineering warnings

## app/tools/frame.py - Frame Analysis Tool

2D frame analysis for rigid-jointed frames, with an OpenSeesPy path and a direct-stiffness fallback.

**Functions**:

- `analyze_frame(inputs: FrameInputs) -> dict`: Main entry point (OpenSeesPy, falls back to direct stiffness)
- `_analyze_frame_opensees(inputs)`: OpenSeesPy frame solve
- `_analyze_frame_direct_stiffness(inputs, fallback_reason)`: Direct stiffness fallback

**Model Setup**:

- Uses ElasticBeamColumn2d elements
- 3 DOF per node (ux, uy, theta)
- Linear elastic material with specified E, A, I
- Static plain analysis with PARDISO solver

**Output**:

Returns dict with:
- node_displacements: Node displacement vectors (ux, uy, theta)
- member_end_forces: Element end forces (axial, shear, moment)
- support_reactions: Reaction forces and moments at supports
- diagram_data: Shear, moment, and axial force diagram data
- warnings: List of engineering warnings

## app/tools/column.py - Column Analysis Tool

Euler buckling and AISC column design checks.

**Functions**:

- `analyze_column(inputs: ColumnInputs) -> dict`: Main entry point — computes Euler critical load, slenderness ratio, radius of gyration, AISC 360 Chapter E design strength, and axial stress

**Calculations**:

- **Euler critical load**: P_cr = pi^2 * E * I / (K*L)^2
  - K = effective length factor based on end conditions
  - End conditions: pinned-pinned (1.0), fixed-fixed (0.5), fixed-free (2.0), fixed-pinned (0.7)
- **Slenderness ratio**: lambda = K*L / r, where r = sqrt(I/A)
- **AISC check**: Compare actual stress to allowable stress per AISC 360
- **Safety factor**: FS = P_cr / P_actual

**Output**:

Returns dict with:
- euler_critical_load_kn: Euler buckling load
- slenderness_ratio: Slenderness ratio
- radius_of_gyration_m: Radius of gyration
- safety_factor: Factor of safety against buckling
- axial_stress_mpa: Actual axial stress
- aisc_check: Pass/fail status per AISC
- warnings: List of engineering warnings

## app/tools/opensees_3d.py - 3D Structure Analysis Tool

3D frame analysis using OpenSeesPy for spatial structures.

**Functions**:

- `analyze_3d_structure_opensees(inputs: Structure3DInputs) -> dict`: Main entry point
- `convert_3d_support_strings(model: dict) -> dict`: Convert string support specs to boolean DOF constraints
- `_story_response(inputs, nodal_displacements)`: Compute story displacements and drift ratios
- `_default_combinations(inputs)`: Build the default load combinations
- `_apply_rigid_diaphragms(ops, inputs)`: Apply rigid floor diaphragm constraints
- `_run_static_combo(ops, inputs, combo)`: Run one load combination and extract results

**Model Setup**:

- Uses ElasticBeam3d elements
- 6 DOF per node (ux, uy, uz, rx, ry, rz)
- Linear elastic material with E and G
- Static plain analysis with PARDISO solver

**Output**:

Returns dict with:
- node_displacements: Node displacement vectors (6 DOF)
- member_end_forces: Element end forces (axial, shear, torsion, moment)
- support_reactions: Reaction forces and moments at supports
- max_displacement: Maximum displacement magnitude and location
- warnings: List of engineering warnings

## app/tools/story_forces.py - Story-Force Application

Deterministically maps wind/seismic story forces onto a drawn 3D model as nodal loads.

**Function**:

- `apply_story_forces(inputs, story_forces, *, case, direction, distribution) -> dict`
  - `story_forces`: list of `{"z_m": float, "force_kn": float}` (from the wind/seismic tools)
  - `case`: load case name for new loads (e.g. `"W"`, `"EQ"`)
  - `direction`: `"x"` or `"y"`
  - `distribution`: `"equal"` (all nodes at the nearest level) or `"windward"` (face with the minimum coordinate along `direction`)

**Behavior**:

- Each story force is snapped to the model level (elevation) nearest its `z_m`.
- The force is split evenly across the target nodes at that level.
- Existing nodal loads are preserved; the original inputs are not mutated.
- A warning is emitted when a story force is far (>2.5 m) from the nearest level.

**Output**: dict with `inputs` (augmented `Structure3DInputs`), `applied` (per-story assignment), and `warnings`.

## Load Determination & Design Tools

These tools are deterministic (no LLM) and expose a single `calculate_*` function each.

### app/tools/wind.py - ASCE 7-22 Wind Loads

`calculate_wind_loads(inputs: WindInputs) -> dict`

Simplified MWFRS procedure: velocity pressure `qz`, exposure, gust/directionality/internal-pressure factors, MWFRS external pressures, base shear (x/y), roof uplift, and story forces.

### app/tools/seismic.py - ASCE 7-22 Seismic Base Shear

`calculate_seismic_base_shear(inputs: SeismicInputs) -> dict`

Equivalent static force procedure: site coefficients (Fa/Fv), SDS/SD1, Ts, period, Cs (bounded), base shear V, and vertical story-force distribution.

### app/tools/snow.py - ASCE 7-22 Snow Loads

`calculate_snow_loads(inputs: SnowInputs) -> dict`

Ground snow load, exposure/thermal/importance factors, flat and sloped roof snow load, and simplified drift load.

### app/tools/slab.py - ACI 318 Two-Way Slab

`calculate_slab(inputs: SlabInputs) -> dict`

Two-way slab coefficients, reinforcement, and deflection checks.

### app/tools/section_select.py - AISC 360 Section Selection

`select_beam(inputs: BeamSelectionInputs) -> dict` / `select_column(inputs: ColumnSelectionInputs) -> dict`

Iterates W-shapes from the section database to find the lightest adequate section for flexure/shear (beam) or axial (column, AISC E3). The beam path performs a full AISC 360 F2 lateral-torsional buckling check (`_ltb_capacity`: yield, inelastic, and elastic LTB with Cb, J, Cw, h0, rts, Lp, Lr) in addition to flexure and shear.

### app/tools/concrete.py - ACI 318 Concrete Design

`design_concrete_beam(inputs: ConcreteBeamInputs) -> dict` / `design_concrete_column(inputs: ConcreteColumnInputs) -> dict`

Singly-reinforced concrete beam (flexure As/ρ/φMn, one-way shear Vc and stirrup spacing, bar count) and circular tied/spiral column (As, ρ limits, φPn, slenderness check). Deterministic.

### app/tools/timber.py - NDS Timber Design

`design_timber_beam(inputs: TimberBeamInputs) -> dict` / `list_species() -> list[dict]`

Rectangular timber beam design per NDS (ASD) with reference design values for 6 species and adjustment factors CD/CM/Ct/CF/CL; checks flexure, shear, lateral-torsional stability, and deflection.

### app/tools/foundation.py - Foundation Design

`design_spread_footing(inputs: SpreadFootingInputs) -> dict` / `design_pile_capacity(inputs: PileInputs) -> dict`

ACI 318 square spread footing (bearing sizing, one-way and punching shear, flexure with an iterated stress block, bar count/spacing) and static pile capacity (skin friction + end bearing, factor of safety, Converse-Labarre group efficiency). Deterministic.

### app/tools/fatigue.py - AISC 360 Fatigue

`check_fatigue(inputs: FatigueInputs) -> dict` / `list_fatigue_categories() -> list[dict]`

AISC 360 S-N curve check for fatigue categories A–E (Table 16.5, SI): N = C/f³, infinite life below the limit, allowable stress range, utilization check, and a recommended-category suggestion. Deterministic.

### app/tools/cost.py - Cost Estimation

`estimate_cost(members, *, price_per_kg, fab_factor, erect_factor, currency) -> dict`

Steel cost takeoff from a list of `{section, length_m}` members using section unit weight, with fabrication/erection factors and currency. Deterministic.

### app/tools/sensitivity.py - Sensitivity Study

`run_sensitivity(inputs: SensitivityInputs) -> dict`

One-at-a-time parametric study on a simply-supported beam (Roark's moment/deflection/stress). Computes elasticity sensitivity coefficients via central difference and ranks parameters by influence. Deterministic.

### app/tools/multi_hazard.py - Multi-Hazard Optimizer

`optimize_multi_hazard(inputs: MultiHazardInputs) -> dict`

Evaluates all ASCE 7-22 LRFD/ASD load combinations against a member capacity, ranks them by utilization, and sweeps each D/L/W/S/E component to find the worst-case scenario. Deterministic.

### app/tools/response_spectrum.py - Response Spectrum Analysis

`response_spectrum_analysis(model, building_weight_kn, sds, sd1, *, direction, num_modes, long_period_s) -> dict`

Deterministic lumped-mass multi-mode (Cantilever) response-spectrum analysis of a 3D model using an ASCE 7-22 design spectrum and SRSS combination, with story stiffness derived from vertical members.

### app/tools/pdelta.py - P-Delta Second-Order Effects

`amplify_story_drifts(story_drifts, base_shear_kn, height_m, gravity_load_kn) -> dict` / `pdelta_equivalent_lateral_forces(model, story_drifts, gravity_load_kn, *, direction) -> dict`

ASCE 7-22 stability coefficient (θ = V·h/W) drift amplification and P-delta equivalent lateral forces mapped onto a drawn 3D model for iterative second-order analysis. Deterministic.

### app/tools/cross_validation.py - Cross-Validation Suite

`run_cross_validation() -> dict`

Compares the closed-form, OpenSeesPy FEM, and direct-stiffness fallback solvers on benchmark beam/truss/frame models and reports per-quantity agreement. Deterministic.

### app/tools/openapi.py - OpenAPI Spec Generator

`build_openapi_spec(app) -> dict`

Introspects live Flask routes and Pydantic models to produce an OpenAPI 3.0 specification. Maps POST routes to request-body models, assigns tags, and handles Flask path converters (e.g. `<int:item_id>` → `{item_id}`).

### app/tools/pdf_export.py - PDF Export

`markdown_report_to_pdf(markdown: str) -> bytes`

Dependency-free PDF 1.4 writer that renders a Markdown engineering report to a downloadable PDF.

## app/tools/load_combinations.py - Load Combination Generator

Generates ASCE 7-22 load combinations for structural design.

**Functions**:

- `apply_load_combination(dl_kn, ll_kn, wl_kn, sl_kn, el_kn, combination=None) -> dict`: Apply a combination's factors to the load components (returns the factored load and details)
- `run_all_load_combinations(dl, ll, wl, sl, el, *, method) -> list[dict]`: Generate all applicable load combinations (LRFD or ASD)
- `get_controlling_combination(dl, ll, wl, sl, el, *, method) -> dict`: Return the combination with the largest factored total

**Supported Load Types**:

- Dead load (D)
- Live load (L)
- Wind load (W)
- Seismic load (E)
- Snow load (S)

**Output**:

`run_all_load_combinations` returns a list of combination dicts (name, per-load factors, factored total); `get_controlling_combination` returns the single combination with the largest factored total.

## app/tools/report.py - Report Formatter

Generates markdown engineering reports from analysis results.

**Functions**:

- `format_engineering_report(title, assumptions, warnings, results, *, analysis_type) -> str`: Generate the full markdown report
- `_format_3d_frame_report`, `_format_beam_report`, `_format_truss_report`, `_format_frame_report`, `_format_column_report`: Per-analysis-type report bodies

**Report Sections**:

1. **Header**: Analysis type, timestamp, tool version
2. **Input Summary**: Structure geometry, material properties, loading
3. **Results**: Key results with units and significant figures
4. **Diagrams Reference**: References to generated diagrams
5. **Warnings**: Engineering warnings and assumptions
6. **Disclaimer**: Safety notice and scope limitations

## app/tools/sections.py - Steel Section Database

AISC steel section properties database (W-shapes, HSS, and angles).

### SteelSection Class

**Properties** (SI units): `name`, `weight_kg_per_m`, `area_m2`, `d_mm` (depth), `bf_mm` (flange width), `tf_mm` (flange thickness), `tw_mm` (web thickness), `ix_m4`, `iy_m4` (moment of inertia), `sx_m3`, `sy_m3` (elastic section modulus), `zx_m3`, `zy_m3` (plastic section modulus), `rx_m`, `ry_m` (radius of gyration).

**Functions**:

- `get_section(name: str) -> SteelSection | None`: Get a section by exact name
- `list_sections(section_type: str = "all") -> list[str]`: List section names (optionally filtered by type)
- `search_sections(query: str) -> list[SteelSection]`: Search sections by name
- `section_to_dict(section: SteelSection) -> dict`: Serialize a section for the API

**Database**:

Contains AISC W-shape, HSS, and angle sections with properties from the AISC Steel Construction Manual.
