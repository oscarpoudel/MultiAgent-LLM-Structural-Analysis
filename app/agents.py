from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from app.llm import OllamaClient
from app.models import AgentTrace, BeamInputs
from app.tools.beam import analyze_simply_supported_udl
from app.tools.report import format_engineering_report


@dataclass
class AgentResult:
    assumptions: list[str]
    warnings: list[str]
    traces: list[AgentTrace]
    results: dict[str, Any]
    report_markdown: str


class StructuralAgentSystem:
    def __init__(self, llm: OllamaClient) -> None:
        self.llm = llm

    async def analyze(self, prompt: str) -> AgentResult:
        traces: list[AgentTrace] = []
        assumptions = [
            "Preliminary elastic analysis only.",
            "Units are interpreted from the prompt where possible.",
        ]
        warnings = [
            "Not a substitute for licensed engineering review or full code compliance.",
        ]

        intent = await self._intent_agent(prompt)
        traces.append(AgentTrace(agent="Structural Intent Agent", summary=intent["summary"], data=intent))

        plan = await self._planning_agent(prompt, intent)
        traces.append(AgentTrace(agent="Analysis Planning Agent", summary=plan["summary"], data=plan))

        beam_inputs = self._extract_beam_inputs(prompt, plan)
        traces.append(
            AgentTrace(
                agent="Solver Tool Agent",
                summary="Running simply supported beam UDL calculator.",
                data=beam_inputs.model_dump(),
            )
        )
        results = analyze_simply_supported_udl(beam_inputs)

        critic = self._critic_agent(results)
        warnings.extend(critic["warnings"])
        traces.append(AgentTrace(agent="Results Critic Agent", summary=critic["summary"], data=critic))

        if beam_inputs.inertia_m4 is None:
            warnings.append("Moment and shear were computed, but deflection needs a valid moment of inertia.")
        if beam_inputs.section_modulus_m3 is None:
            warnings.append("Bending stress was not computed because section modulus was not provided.")

        report = format_engineering_report(prompt, assumptions, warnings, results)
        traces.append(AgentTrace(agent="Report Agent", summary="Generated preliminary engineering report.", data={}))
        return AgentResult(assumptions, warnings, traces, results, report)

    async def _intent_agent(self, prompt: str) -> dict[str, Any]:
        system = "You extract structural engineering intent. Return compact JSON only."
        task = (
            "Identify structure type, analysis type, material, loads, boundary conditions, "
            f"and missing data from this request:\n{prompt}"
        )
        fallback = {
            "summary": "Detected a preliminary beam analysis request.",
            "structure_type": "beam",
            "analysis_type": "static_elastic",
            "boundary_conditions": "simply_supported",
        }
        return await self._json_agent(system, task, fallback)

    async def _planning_agent(self, prompt: str, intent: dict[str, Any]) -> dict[str, Any]:
        system = "You plan structural analysis tool execution. Return compact JSON only."
        task = (
            "Choose a solver and required structured inputs for V1. "
            "Available solver: simply_supported_udl_beam. "
            f"Intent JSON: {json.dumps(intent)}\nUser request: {prompt}"
        )
        fallback = {
            "summary": "Use the deterministic simply_supported_udl_beam solver.",
            "solver": "simply_supported_udl_beam",
            "required_inputs": ["span_m", "udl_kn_per_m", "elastic_modulus_gpa", "inertia_m4"],
        }
        return await self._json_agent(system, task, fallback)

    async def _json_agent(self, system: str, task: str, fallback: dict[str, Any]) -> dict[str, Any]:
        try:
            raw = await self.llm.generate(system=system, prompt=task)
            match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
            if not match:
                return fallback
            data = json.loads(match.group(0))
            if "summary" not in data:
                data["summary"] = fallback["summary"]
            return data
        except Exception:
            return fallback

    def _extract_beam_inputs(self, prompt: str, plan: dict[str, Any]) -> BeamInputs:
        del plan
        normalized = prompt.lower().replace(",", " ")
        values = {
            "span_m": self._find_number(normalized, [r"span(?: is)? ([0-9.]+)\s*m", r"([0-9.]+)\s*m span"], 6.0),
            "udl_kn_per_m": self._find_number(
                normalized,
                [r"(?:udl|uniform load|load)(?: is)? ([0-9.]+)\s*kn/?m", r"([0-9.]+)\s*kn/?m"],
                10.0,
            ),
            "elastic_modulus_gpa": self._find_number(
                normalized,
                [r"(?:e|elastic modulus)(?: is)? ([0-9.]+)\s*gpa", r"([0-9.]+)\s*gpa"],
                200.0,
            ),
            "inertia_m4": self._find_optional_number(normalized, [r"(?:i|inertia)(?: is)? ([0-9.eE+-]+)\s*m4"]),
            "section_modulus_m3": self._find_optional_number(
                normalized,
                [r"(?:s|section modulus)(?: is)? ([0-9.eE+-]+)\s*m3"],
            ),
            "deflection_limit_ratio": self._find_number(normalized, [r"l/([0-9.]+)"], 360.0),
        }
        try:
            return BeamInputs(**values)
        except ValidationError:
            return BeamInputs(span_m=6.0, udl_kn_per_m=10.0, elastic_modulus_gpa=200.0)

    def _critic_agent(self, results: dict[str, Any]) -> dict[str, Any]:
        warnings: list[str] = []
        if not results.get("is_finite"):
            warnings.append("One or more numeric inputs were not finite.")
        if results.get("deflection_ok") is False:
            warnings.append("Deflection exceeds the selected serviceability limit.")
        if results.get("span_m", 0) <= 0:
            warnings.append("Span must be positive.")
        if results.get("udl_kn_per_m", 0) < 0:
            warnings.append("Uniform load should be entered as a positive gravity load magnitude.")
        return {
            "summary": "Checked basic result sanity, unit-sensitive fields, and deflection status.",
            "warnings": warnings,
        }

    @staticmethod
    def _find_number(text: str, patterns: list[str], default: float) -> float:
        value = StructuralAgentSystem._find_optional_number(text, patterns)
        return default if value is None else value

    @staticmethod
    def _find_optional_number(text: str, patterns: list[str]) -> float | None:
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    return None
        return None
