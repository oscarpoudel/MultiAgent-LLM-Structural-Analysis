from typing import Any

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    prompt: str = Field(..., min_length=5)


class BeamInputs(BaseModel):
    span_m: float
    udl_kn_per_m: float
    elastic_modulus_gpa: float = 200.0
    inertia_m4: float | None = None
    section_modulus_m3: float | None = None
    deflection_limit_ratio: float = 360.0


class AgentTrace(BaseModel):
    agent: str
    summary: str
    data: dict[str, Any] = Field(default_factory=dict)


class AnalyzeResponse(BaseModel):
    status: str
    assumptions: list[str]
    warnings: list[str]
    traces: list[AgentTrace]
    results: dict[str, Any]
    report_markdown: str
