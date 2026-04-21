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


class ChatResponse(BaseModel):
    status: str
    response_type: str
    message: str
    source: str
    analysis: AnalyzeResponse | None = None
