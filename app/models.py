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
