from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Request / Response
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    prompt: str = Field(..., min_length=5)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    analysis_type: str | None = None
    model: dict[str, Any] | None = None
    results: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Beam inputs
# ---------------------------------------------------------------------------

class PointLoad(BaseModel):
    """A single concentrated load on a beam."""
    magnitude_kn: float
    position_m: float


class BeamInputs(BaseModel):
    span_m: float
    udl_kn_per_m: float = 0.0
    point_loads: list[PointLoad] = Field(default_factory=list)
    elastic_modulus_gpa: float = 200.0
    inertia_m4: float | None = None
    area_m2: float = 1.0
    section_modulus_m3: float | None = None
    deflection_limit_ratio: float = 360.0
    support_type: str = "simply_supported"  # simply_supported | cantilever | fixed_fixed | propped_cantilever


# ---------------------------------------------------------------------------
# Truss inputs
# ---------------------------------------------------------------------------

class TrussNode(BaseModel):
    id: int
    x: float
    y: float
    support: str = "free"  # free | pin | roller_x | roller_y | fixed


class TrussMember(BaseModel):
    id: int
    start_node: int
    end_node: int
    area_m2: float = 0.001
    elastic_modulus_gpa: float = 200.0


class TrussLoad(BaseModel):
    node_id: int
    fx_kn: float = 0.0
    fy_kn: float = 0.0


class TrussInputs(BaseModel):
    nodes: list[TrussNode]
    members: list[TrussMember]
    loads: list[TrussLoad]


# ---------------------------------------------------------------------------
# Frame inputs
# ---------------------------------------------------------------------------

class FrameNode(BaseModel):
    id: int
    x: float
    y: float
    support: str = "free"  # free | pin | roller | fixed


class FrameMember(BaseModel):
    id: int
    start_node: int
    end_node: int
    area_m2: float = 0.01
    inertia_m4: float = 1e-4
    elastic_modulus_gpa: float = 200.0


class FrameLoad(BaseModel):
    """Nodal load on a frame node."""
    node_id: int
    fx_kn: float = 0.0
    fy_kn: float = 0.0
    moment_kn_m: float = 0.0


class FrameMemberLoad(BaseModel):
    """Distributed load on a frame member."""
    member_id: int
    udl_kn_per_m: float = 0.0


class FrameInputs(BaseModel):
    nodes: list[FrameNode]
    members: list[FrameMember]
    nodal_loads: list[FrameLoad] = Field(default_factory=list)
    member_loads: list[FrameMemberLoad] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Column inputs
# ---------------------------------------------------------------------------

class ColumnInputs(BaseModel):
    length_m: float
    area_m2: float
    inertia_m4: float
    elastic_modulus_gpa: float = 200.0
    yield_stress_mpa: float = 250.0
    end_condition: str = "pinned_pinned"  # pinned_pinned | fixed_free | fixed_pinned | fixed_fixed
    axial_load_kn: float = 0.0


# ---------------------------------------------------------------------------
# 3D Structure inputs
# ---------------------------------------------------------------------------

class Support3D(BaseModel):
    ux: bool = False
    uy: bool = False
    uz: bool = False
    rx: bool = False
    ry: bool = False
    rz: bool = False


class Node3D(BaseModel):
    id: int
    x: float
    y: float
    z: float
    support: Support3D | None = None


class Member3D(BaseModel):
    id: int
    start_node: int
    end_node: int
    area_m2: float = 0.01
    iy_m4: float = 1e-4
    iz_m4: float = 1e-4
    j_m4: float = 1e-4
    elastic_modulus_gpa: float = 200.0
    shear_modulus_gpa: float = 77.0
    group: str = "member"


class Load3D(BaseModel):
    node_id: int
    case: str = "D"
    fx_kn: float = 0.0
    fy_kn: float = 0.0
    fz_kn: float = 0.0
    mx_kn_m: float = 0.0
    my_kn_m: float = 0.0
    mz_kn_m: float = 0.0


class MemberLoad3D(BaseModel):
    member_id: int
    case: str = "D"
    wy_kn_per_m: float = 0.0
    wz_kn_per_m: float = 0.0


class LoadCombination3D(BaseModel):
    name: str
    factors: dict[str, float]


class Structure3DInputs(BaseModel):
    nodes: list[Node3D]
    members: list[Member3D]
    nodal_loads: list[Load3D] = Field(default_factory=list)
    member_loads: list[MemberLoad3D] = Field(default_factory=list)
    load_combinations: list[LoadCombination3D] = Field(default_factory=list)
    active_load_combination: str | None = None
    rigid_diaphragms: bool = False


# ---------------------------------------------------------------------------
# Wind inputs (ASCE 7-22 simplified procedure)
# ---------------------------------------------------------------------------

class WindInputs(BaseModel):
    basic_wind_speed_ms: float = Field(..., gt=0, description="Basic wind speed V (m/s), 3-sec gust, 1 yr recurrence")
    exposure: str = "C"  # A | B | C | D (ASCE 7-22 Table 26.11-1)
    height_m: float = Field(..., gt=0, description="Building height h (m)")
    length_m: float = Field(..., gt=0, description="Building length in wind direction (m)")
    width_m: float = Field(..., gt=0, description="Building width perpendicular to wind (m)")
    story_height_m: float = Field(4.0, gt=0, description="Average story height for story-force distribution (m)")
    internal_pressure: str = "minor_openings"  # no_openings | minor_openings | major_openings | all_openings
    topographic_factor: float = Field(1.0, ge=1.0, le=2.0, description="Topographic factor Kzt")
    air_density_factor: float = Field(1.0, ge=0.5, le=1.5, description="Air density factor Ke")


# ---------------------------------------------------------------------------
# Seismic inputs (ASCE 7-22 equivalent static force procedure)
# ---------------------------------------------------------------------------

class SeismicInputs(BaseModel):
    spectral_accel_sd: float = Field(..., gt=0, description="Mapped spectral acceleration at short period Sa(0.2s) (g)")
    spectral_accel_1s: float = Field(..., gt=0, description="Mapped spectral acceleration at 1s Sa(1s) (g)")
    site_class: str = "D"  # A | B | C | D | E | F (ASCE 7-22 Table 11.3-1)
    risk_category: str = "II"  # I | II | III | IV
    building_weight_kn: float = Field(..., gt=0, description="Seismic weight W (kN)")
    fundamental_period_s: float | None = Field(None, gt=0, description="Fundamental period T (s); if None, use Ca*Tu")
    height_m: float = Field(..., gt=0, description="Effective height for period estimate (m)")
    structural_system: str = "moment_frame"  # moment_frame | braced_frame | shear_wall | dual_system
    importance_factor: float | None = None  # Rho override; default from risk_category
    response_modification: float | None = None  # R override; default from structural_system
    deflection_amplifier: float | None = None  # Cd override; default from structural_system


# ---------------------------------------------------------------------------
# Slab inputs (two-way slab, ACI 318)
# ---------------------------------------------------------------------------

class SlabInputs(BaseModel):
    span_x_m: float = Field(..., gt=0, description="Span in X direction (clear, m)")
    span_y_m: float = Field(..., gt=0, description="Span in Y direction (clear, m)")
    thickness_m: float = Field(..., gt=0, description="Slab thickness h (m)")
    dead_load_kpa: float = Field(0.0, ge=0, description="Superimposed dead load (kPa)")
    live_load_kpa: float = Field(..., gt=0, description="Live load (kPa)")
    concrete_fck_mpa: float = Field(25.0, gt=0, description="Specified compressive strength f'c (MPa)")
    steel_fy_mpa: float = Field(420.0, gt=0, description="Yield strength of reinforcement fy (MPa)")
    support_condition: str = "continuous"  # simply_supported | continuous
    deflection_limit_ratio: float = 360.0


# ---------------------------------------------------------------------------
# Snow inputs (ASCE 7-22)
# ---------------------------------------------------------------------------

class SnowInputs(BaseModel):
    ground_snow_load_kpa: float = Field(..., ge=0, description="Ground snow load pg (kPa)")
    exposure: str = "partially_shielded"  # exposed | partially_shielded | shielded
    thermal: str = "heated"  # heated | unheated
    risk_category: str = "II"  # I | II | III | IV
    roof_slope_deg: float = Field(0.0, ge=0, le=90, description="Roof slope from horizontal (deg)")
    drift: bool = Field(False, description="Include simplified drift load")


# ---------------------------------------------------------------------------
# Section selection inputs (AISC 360)
# ---------------------------------------------------------------------------

class BeamSelectionInputs(BaseModel):
    moment_kn_m: float = Field(..., gt=0, description="Factored bending moment Mu (kN-m)")
    shear_kn: float = Field(0.0, ge=0, description="Factored shear Vu (kN)")
    unbraced_length_m: float = Field(0.0, ge=0, description="Unbraced length Lb (m); 0 = fully braced")
    cb: float = Field(1.0, ge=1.0, le=3.0, description="Lateral-torsional buckling modification Cb")
    fy_mpa: float = Field(345.0, gt=0, description="Yield stress fy (MPa)")


class ColumnSelectionInputs(BaseModel):
    axial_load_kn: float = Field(..., gt=0, description="Factored axial load Pu (kN)")
    kl_m: float = Field(..., gt=0, description="Effective length KL (m)")
    fy_mpa: float = Field(345.0, gt=0, description="Yield stress fy (MPa)")


# ---------------------------------------------------------------------------
# Concrete design inputs (ACI 318)
# ---------------------------------------------------------------------------

class ConcreteBeamInputs(BaseModel):
    moment_kn_m: float = Field(..., gt=0, description="Factored bending moment Mu (kN-m)")
    shear_kn: float = Field(0.0, ge=0, description="Factored shear Vu (kN)")
    width_mm: float = Field(..., gt=0, description="Beam width b (mm)")
    depth_mm: float = Field(..., gt=0, description="Total beam depth h (mm)")
    effective_depth_mm: float | None = Field(None, gt=0, description="Effective depth d (mm); defaults to h - cover - stirrup - bar/2")
    concrete_fck_mpa: float = Field(25.0, gt=0, description="Specified compressive strength f'c (MPa)")
    steel_fy_mpa: float = Field(420.0, gt=0, description="Yield strength of reinforcement fy (MPa)")
    bar_dia_mm: float = Field(20.0, gt=0, description="Main bar diameter (mm) for spacing suggestion")
    stirrup_dia_mm: float = Field(10.0, gt=0, description="Stirrup diameter (mm) for shear design")


class ConcreteColumnInputs(BaseModel):
    axial_load_kn: float = Field(..., gt=0, description="Factored axial load Pu (kN)")
    diameter_mm: float = Field(..., gt=0, description="Column diameter (mm)")
    concrete_fck_mpa: float = Field(25.0, gt=0, description="Specified compressive strength f'c (MPa)")
    steel_fy_mpa: float = Field(420.0, gt=0, description="Yield strength of reinforcement fy (MPa)")
    tied: bool = Field(True, description="True for tied column, False for spiral column")
    kl_r: float = Field(0.0, ge=0, description="Effective slenderness ratio kl/r; 0 = short column (no reduction)")


# ---------------------------------------------------------------------------
# Timber design inputs (NDS)
# ---------------------------------------------------------------------------

class TimberBeamInputs(BaseModel):
    species: str = Field("spf-no1", description="Species key (see GET /api/sections/timber)")
    width_mm: float = Field(..., gt=0, description="Beam width b (mm)")
    depth_mm: float = Field(..., gt=0, description="Beam depth d (mm)")
    moment_kn_m: float = Field(..., gt=0, description="Service bending moment M (kN-m)")
    shear_kn: float = Field(0.0, ge=0, description="Service shear V (kN)")
    span_m: float = Field(..., gt=0, description="Span L (m) for deflection")
    unbraced_length_m: float = Field(0.0, ge=0, description="Unbraced length of compression flange (m); 0 = fully braced")
    duration: str = Field("normal", description="Load duration: permanent/long_term/normal/short_term/temporary/momentary")
    moisture_pct: float = Field(19.0, ge=0, le=100, description="Moisture content (%) for wet-service factor")
    temperature_c: float = Field(20.0, description="Service temperature (C) for temperature factor")
    live_load_fraction: float = Field(0.5, ge=0.0, le=1.0, description="Fraction of total deflection attributable to live load")


# ---------------------------------------------------------------------------
# Foundation design inputs (spread footing + pile)
# ---------------------------------------------------------------------------

class SpreadFootingInputs(BaseModel):
    axial_load_kn: float = Field(..., gt=0, description="Service axial load P (kN)")
    factored_axial_kn: float | None = Field(None, gt=0, description="Factored axial load Pu (kN); defaults to 1.4*P")
    allowable_bearing_kpa: float = Field(..., gt=0, description="Allowable soil bearing capacity (kPa)")
    column_width_mm: float = Field(..., gt=0, description="Column width (mm)")
    column_depth_mm: float = Field(..., gt=0, description="Column depth (mm)")
    concrete_fck_mpa: float = Field(25.0, gt=0, description="Concrete compressive strength f'c (MPa)")
    steel_fy_mpa: float = Field(420.0, gt=0, description="Reinforcement yield strength fy (MPa)")
    footing_depth_mm: float = Field(600.0, gt=0, description="Footing thickness (mm)")
    bar_dia_mm: float = Field(20.0, gt=0, description="Main bar diameter (mm)")
    footing_width_mm: float | None = Field(None, gt=0, description="Override footing width (mm); else sized from bearing")


class PileInputs(BaseModel):
    pile_diameter_mm: float = Field(..., gt=0, description="Pile diameter (mm)")
    pile_length_m: float = Field(..., gt=0, description="Pile length (m)")
    skin_friction_kpa: float = Field(..., gt=0, description="Average skin friction along shaft (kPa)")
    skin_friction_alpha: float = Field(0.5, gt=0, le=1.0, description="Alpha factor (adhesion) for skin friction")
    end_bearing_kpa: float = Field(..., gt=0, description="End-bearing capacity (kPa)")
    factor_of_safety: float = Field(2.5, gt=0, description="Factor of safety on ultimate capacity")
    piles_per_row: int = Field(1, ge=1, description="Number of piles per row")
    rows_in_group: int = Field(1, ge=1, description="Number of rows in the group")
    center_to_center_spacing_m: float = Field(0.0, ge=0, description="Pile center-to-center spacing (m); 0 = single pile")


# ---------------------------------------------------------------------------
# Fatigue design inputs (AISC 360)
# ---------------------------------------------------------------------------

class FatigueInputs(BaseModel):
    category: str = Field("C", description="Fatigue category: A, B, C, D, E (A most resistant)")
    stress_range_mpa: float = Field(..., gt=0, description="Stress range f_f (MPa)")
    num_cycles: float = Field(..., gt=0, description="Design number of cycles N")


# ---------------------------------------------------------------------------
# Multi-hazard load combination optimizer inputs
# ---------------------------------------------------------------------------

class MultiHazardInputs(BaseModel):
    dead_load_kn: float = Field(..., ge=0, description="Dead load D (kN)")
    live_load_kn: float = Field(0.0, ge=0, description="Live load L (kN)")
    wind_load_kn: float = Field(0.0, ge=0, description="Wind load W (kN)")
    snow_load_kn: float = Field(0.0, ge=0, description="Snow load S (kN)")
    earthquake_load_kn: float = Field(0.0, ge=0, description="Earthquake load E (kN)")
    response_factor: float = Field(1.0, gt=0, description="Response per unit factored load (e.g. kN-m per kN)")
    capacity: float = Field(..., gt=0, description="Member capacity in the response units (e.g. kN-m)")
    method: str = Field("lrfd", description="'lrfd' or 'asd'")
    dead_min_kn: float = Field(0.0, ge=0, description="Min dead load for sweep (kN)")
    dead_max_kn: float = Field(0.0, ge=0, description="Max dead load for sweep (kN)")
    live_min_kn: float = Field(0.0, ge=0, description="Min live load for sweep (kN)")
    live_max_kn: float = Field(0.0, ge=0, description="Max live load for sweep (kN)")
    wind_min_kn: float = Field(0.0, ge=0, description="Min wind load for sweep (kN)")
    wind_max_kn: float = Field(0.0, ge=0, description="Max wind load for sweep (kN)")
    snow_min_kn: float = Field(0.0, ge=0, description="Min snow load for sweep (kN)")
    snow_max_kn: float = Field(0.0, ge=0, description="Max snow load for sweep (kN)")
    earthquake_min_kn: float = Field(0.0, ge=0, description="Min earthquake load for sweep (kN)")
    earthquake_max_kn: float = Field(0.0, ge=0, description="Max earthquake load for sweep (kN)")
    components: list[str] = Field(
        default_factory=lambda: ["dl_kn", "ll_kn", "wl_kn", "sl_kn", "el_kn"],
        description="Components to sweep: dl_kn, ll_kn, wl_kn, sl_kn, el_kn",
    )


# ---------------------------------------------------------------------------
# Sensitivity analysis inputs (parametric study)
# ---------------------------------------------------------------------------

class SensitivityInputs(BaseModel):
    load_kn_m: float = Field(..., gt=0, description="Base uniform load w (kN/m)")
    span_m: float = Field(..., gt=0, description="Base span L (m)")
    modulus_gpa: float = Field(..., gt=0, description="Base modulus of elasticity E (GPa)")
    inertia_m4: float = Field(..., gt=0, description="Base moment of inertia I (m^4)")
    section_modulus_m3: float = Field(..., gt=0, description="Base section modulus S (m^3)")
    load_min_kn_m: float = Field(..., ge=0, description="Min load w (kN/m)")
    load_max_kn_m: float = Field(..., ge=0, description="Max load w (kN/m)")
    span_min_m: float = Field(..., ge=0, description="Min span L (m)")
    span_max_m: float = Field(..., ge=0, description="Max span L (m)")
    modulus_min_gpa: float = Field(..., ge=0, description="Min modulus E (GPa)")
    modulus_max_gpa: float = Field(..., ge=0, description="Max modulus E (GPa)")
    inertia_min_m4: float = Field(..., ge=0, description="Min inertia I (m^4)")
    inertia_max_m4: float = Field(..., ge=0, description="Max inertia I (m^4)")
    section_min_m3: float = Field(..., ge=0, description="Min section modulus S (m^3)")
    section_max_m3: float = Field(..., ge=0, description="Max section modulus S (m^3)")
    parameters: list[str] = Field(
        default_factory=lambda: ["w", "L", "E", "I", "S"],
        description="Parameters to sweep: w, L, E, I, S",
    )


# ---------------------------------------------------------------------------
# Agent trace / responses
# ---------------------------------------------------------------------------

class AgentTrace(BaseModel):
    agent: str
    summary: str
    data: dict[str, Any] = Field(default_factory=dict)


class DiagramData(BaseModel):
    """Data points for SFD/BMD/deflection diagrams."""
    positions: list[float] = Field(default_factory=list)
    shear_kn: list[float] = Field(default_factory=list)
    moment_kn_m: list[float] = Field(default_factory=list)
    deflection_mm: list[float] = Field(default_factory=list)


class AnalyzeResponse(BaseModel):
    status: str
    analysis_type: str = "beam"  # beam | truss | frame | column
    assumptions: list[str]
    warnings: list[str]
    traces: list[AgentTrace]
    results: dict[str, Any]
    report_markdown: str
    diagrams: DiagramData | None = None


class CanvasAction(BaseModel):
    action: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class CanvasToolDecision(BaseModel):
    action: str = "none"
    arguments: dict[str, Any] = Field(default_factory=dict)
    message: str = ""
    confidence: float = 0.0


class EvaluateRequest(BaseModel):
    message: str
    results: dict[str, Any] = Field(default_factory=dict)
    analysis_type: str = "frame"
    prompt: str = ""


class ChatResponse(BaseModel):
    status: str
    response_type: str
    message: str
    source: str
    analysis: AnalyzeResponse | None = None
    canvas_action: CanvasAction | None = None
    quick_actions: list[dict[str, Any]] | None = None
