"""Multi-agent structural analysis system.

Architecture
------------
A small team of specialist agents, each backed by the LLM and constrained by
native tool-calling (typed JSON schemas), coordinated by a router:

- **Router Agent**        - classifies the user's intent (canvas action,
                            analysis request, or conversation) and dispatches.
- **Conversation Agent**  - free-form structural Q&A, with live model context.
- **Intent Agent**        - extracts a structured structural intent.
- **Planner Agent**       - selects the solver and required inputs.
- **Extractor Agent**     - extracts typed solver inputs (beam/truss/frame/
                            column/3D) from the prompt.
- **Critic Agent**        - reviews solver results for sanity and code limits.
- **Reporter Agent**      - writes the engineering report.

The deterministic *solvers* (OpenSeesPy, closed-form beam, etc.) are unchanged
and remain the source of every number. The deterministic *routing brain* that
previously keyword-matched prompts has been removed: routing, extraction, and
review are now LLM-driven, with a compact deterministic fallback used only
when no LLM is reachable so the app still works offline.
"""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError

from app.llm import LLMReply
from app.logging_config import get_logger
from app.models import (
    AgentTrace,
    BeamInputs,
    CanvasToolDecision,
    ColumnInputs,
    FrameInputs,
    FrameLoad,
    FrameMember,
    FrameMemberLoad,
    FrameNode,
    Load3D,
    Member3D,
    Node3D,
    PointLoad,
    Structure3DInputs,
    Support3D,
    TrussInputs,
    TrussLoad,
    TrussMember,
    TrussNode,
)
from app.tools.column import analyze_column
from app.tools.frame import analyze_frame
from app.tools.opensees_3d import analyze_3d_structure_opensees
from app.tools.opensees_beam import analyze_beam_opensees
from app.tools.report import format_engineering_report
from app.tools.truss import analyze_truss

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------

@dataclass
class AgentResult:
    analysis_type: str
    assumptions: list[str]
    warnings: list[str]
    traces: list[AgentTrace]
    results: dict[str, Any]
    report_markdown: str


@dataclass
class ConversationResult:
    message: str
    source: str


@dataclass
class Intent:
    structure_type: str = "beam"
    analysis_type: str = "static_elastic"
    material: str = "steel"
    boundary_conditions: str = "simply_supported"
    loads: list[str] = field(default_factory=list)
    missing_data: list[str] = field(default_factory=list)
    summary: str = ""


@dataclass
class Plan:
    solver: str = "openseespy_beam"
    required_inputs: list[str] = field(default_factory=list)
    summary: str = ""


# ---------------------------------------------------------------------------
# Tool schemas (native tool-calling)
# ---------------------------------------------------------------------------

class CanvasActionArgs(BaseModel):
    action: str = "none"
    arguments: dict[str, Any] = field(default_factory=dict)
    message: str = ""
    confidence: float = 0.0


class IntentArgs(BaseModel):
    structure_type: str = "beam"
    analysis_type: str = "static_elastic"
    material: str = "steel"
    boundary_conditions: str = "simply_supported"
    loads: list[str] = field(default_factory=list)
    missing_data: list[str] = field(default_factory=list)
    summary: str = ""


class PlanArgs(BaseModel):
    solver: str = "openseespy_beam"
    required_inputs: list[str] = field(default_factory=list)
    summary: str = ""


class BeamArgs(BaseModel):
    span_m: float = 6.0
    udl_kn_per_m: float = 0.0
    point_loads: list[dict[str, float]] = field(default_factory=list)
    elastic_modulus_gpa: float = 200.0
    inertia_m4: float | None = None
    area_m2: float = 1.0
    section_modulus_m3: float | None = None
    deflection_limit_ratio: float = 360.0
    support_type: str = "simply_supported"


class ColumnArgs(BaseModel):
    length_m: float = 4.0
    area_m2: float = 0.01
    inertia_m4: float = 1e-4
    elastic_modulus_gpa: float = 200.0
    yield_stress_mpa: float = 250.0
    end_condition: str = "pinned_pinned"
    axial_load_kn: float = 500.0


class CriticArgs(BaseModel):
    ok: bool = True
    warnings: list[str] = field(default_factory=list)
    summary: str = ""


def _tool(name: str, description: str, schema_model: type[BaseModel]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": schema_model.model_json_schema(),
        },
    }


def _normalize_enum(value: Any, valid: set[str]) -> str:
    """Map a free-text enum value onto the closest valid option."""
    if value is None:
        return ""
    candidate = str(value).strip().lower().replace(" ", "_").replace("-", "_")
    if candidate in valid:
        return candidate
    for option in valid:
        if option in candidate or candidate in option:
            return option
    return candidate


def _extract_json_object(text: str) -> dict[str, Any] | None:
    """Pull the first JSON object out of a model's text output.

    Smaller local models frequently emit the structured result as a JSON string
    (optionally wrapped in markdown fences) instead of a native tool call. This
    recovers the object so the agents keep working across backends.
    """
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Specialist agent base
# ---------------------------------------------------------------------------

class _Agent:
    """A named specialist with a system prompt and a typed tool schema."""

    name: str = "agent"
    system: str = ""
    tool: dict[str, Any] | None = None

    def __init__(self, llm: Any, timeout_s: float) -> None:
        self.llm = llm
        self.timeout_s = timeout_s

    def run(self, user: str) -> LLMReply | None:
        """Run the LLM with a bounded timeout. Returns None on any failure."""
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    self.llm.chat,
                    system=self.system,
                    messages=[{"role": "user", "content": user}],
                    tools=[self.tool] if self.tool else None,
                    tool_choice="auto" if self.tool else None,
                )
                try:
                    return future.result(timeout=self.timeout_s)
                except TimeoutError:
                    log.warning("agent_timeout", extra={"agent": self.name, "timeout_s": self.timeout_s})
                    raise
        except Exception as error:
            log.warning("agent_error", extra={"agent": self.name, "error": str(error)})
            return None

    def run_tool(self, user: str) -> dict[str, Any] | None:
        """Run and return the tool-call arguments.

        Handles both native tool calls and models that emit the JSON as text
        (common with smaller local models), so the multi-agent system works
        across a wide range of backends.
        """
        raw = self.run_raw(user)
        if raw is None:
            return None
        # Some models emit the tool call as {"name":..., "arguments":{...}}.
        if isinstance(raw.get("arguments"), dict):
            return raw["arguments"]
        return raw

    def run_raw(self, user: str) -> dict[str, Any] | None:
        """Run and return the raw JSON object (native call or text), unwrapped.

        Returns the innermost object: for a native tool call the arguments; for
        text output the first JSON object found. Used by the router, which must
        see the ``name``/``action`` field to disambiguate the model's format.
        """
        reply = self.run(user)
        if reply is None:
            return None
        call = reply.first_tool
        if call is not None:
            args = call.get("arguments") or {}
            if args:
                return args
        if reply.text:
            return _extract_json_object(reply.text)
        return None


# ---------------------------------------------------------------------------
# Agent definitions
# ---------------------------------------------------------------------------

class RouterAgent(_Agent):
    name = "Router Agent"
    system = (
        "You route a structural-engineering chat message to EXACTLY ONE canvas action. "
        "Pick the action that matches the user's request. Actions and when to use them: "
        "draw_simple_beam - user asks to draw/create/sketch a (simply supported) beam; "
        "arguments: span_m (number), udl_kn_per_m (number, 0 if none), point_loads (array of "
        "{magnitude_kn, position_m}; midpoint/middle = span_m/2). "
        "draw_3d_frame_template - user asks to create/model a 3D, 3-story, or 3x3 frame. "
        "clear_canvas - user wants the drawing/model cleared or reset. "
        "clear_analysis - user wants ONLY analysis results cleared. "
        "apply_member_group_sections - user asks to assign/apply beam and column sections. "
        "set_rigid_diaphragm - arguments {enabled: bool}. "
        "set_load_combination - arguments {name: string}. "
        "apply_story_forces - arguments {load_type: 'wind'|'seismic', direction: 'x'|'y', "
        "distribution: 'equal'|'windward', wind: {basic_wind_speed_ms, exposure, height_m, "
        "length_m, width_m, story_height_m, internal_pressure}, seismic: {spectral_accel_sd, "
        "spectral_accel_1s, site_class, risk_category, building_weight_kn, height_m, "
        "structural_system}}. "
        "none - ONLY when the user is asking a question, explaining a concept, or requesting an "
        "analysis (not a canvas modification). "
        "Examples: 'draw a beam 4 m span 10 kN at middle' -> draw_simple_beam "
        "(span_m 4, point_loads [{magnitude_kn 10, position_m 2}]). "
        "'how do I calculate wind load?' -> none. "
        "Return only the structured action."
    )
    tool = _tool("route_canvas_action", "Route the message to a canvas action or none.", CanvasActionArgs)


class ConversationAgent(_Agent):
    name = "Conversation Agent"
    system = (
        "You are a structural analysis expert assistant. Reply conversationally, briefly, and "
        "accurately. When greeted, introduce yourself as a structural analysis expert and mention "
        "you can help with beam, truss, 2D frame, column buckling, AISC section lookups, 3D space "
        "frames, and load determination (wind, seismic, snow). When a current model context is "
        "provided, answer using only that context and be specific with numbers. Never claim "
        "licensed engineering approval. Keep answers under 6 sentences."
    )


class IntentAgent(_Agent):
    name = "Intent Agent"
    system = (
        "You extract structural engineering intent from a request. Identify the structure type "
        "(beam, truss, frame, column, 3d_frame), analysis type, material, boundary conditions, "
        "the loads mentioned, and any missing data needed to run the analysis. Return only the "
        "structured intent."
    )
    tool = _tool("extract_intent", "Extract structured structural intent.", IntentArgs)


class PlannerAgent(_Agent):
    name = "Planner Agent"
    system = (
        "You plan structural analysis tool execution. Given the intent, choose the solver from "
        "{openseespy_beam, openseespy_truss, openseespy_frame, openseespy_3d_frame, "
        "column_euler_aisc} and list the required structured inputs. Return only the structured plan."
    )
    tool = _tool("plan_analysis", "Choose solver and required inputs.", PlanArgs)


class BeamExtractorAgent(_Agent):
    name = "Beam Extractor Agent"
    system = (
        "You extract beam analysis inputs from a natural-language request. Interpret units "
        "(m, kN, kN/m, GPa, m4, m2, m3). support_type is one of: simply_supported, cantilever, "
        "fixed_fixed, propped_cantilever. point_loads is an array of {magnitude_kn, position_m}. "
        "If a value is not stated, use the schema default. Return only the structured inputs."
    )
    tool = _tool("extract_beam_inputs", "Extract typed beam inputs.", BeamArgs)


class ColumnExtractorAgent(_Agent):
    name = "Column Extractor Agent"
    system = (
        "You extract column buckling inputs from a natural-language request. end_condition is one "
        "of: pinned_pinned, fixed_free, fixed_pinned, fixed_fixed. Interpret units (m, m2, m4, GPa, "
        "MPa, kN). If a value is not stated, use the schema default. Return only the structured inputs."
    )
    tool = _tool("extract_column_inputs", "Extract typed column inputs.", ColumnArgs)


class CriticAgent(_Agent):
    name = "Results Critic Agent"
    system = (
        "You review structural analysis results for sanity and serviceability. Flag non-finite "
        "values, deflection beyond typical limits (L/360 live, L/240 total), high utilization, "
        "compression members that may buckle, and large drifts. Be specific. Return only the "
        "structured review."
    )
    tool = _tool("review_results", "Review results and list warnings.", CriticArgs)


class ReporterAgent(_Agent):
    name = "Report Agent"
    system = (
        "You write a concise engineering results summary for a structural analysis. Use the "
        "provided numbers. Keep it to a short paragraph plus key bullet points. Always note the "
        "result is preliminary and not a substitute for licensed engineering review."
    )


class StructuralAgentSystem:
    """Coordinates the specialist agents into a working multi-agent system."""

    def __init__(self, llm: Any, agent_timeout_s: float = 3.0) -> None:
        self.llm = llm
        self.agent_timeout_s = agent_timeout_s
        self.router = RouterAgent(llm, agent_timeout_s)
        self.conversation = ConversationAgent(llm, agent_timeout_s)
        self.intent_agent = IntentAgent(llm, agent_timeout_s)
        self.planner_agent = PlannerAgent(llm, agent_timeout_s)
        self.beam_extractor = BeamExtractorAgent(llm, agent_timeout_s)
        self.column_extractor = ColumnExtractorAgent(llm, agent_timeout_s)
        self.critic = CriticAgent(llm, agent_timeout_s)
        self.reporter = ReporterAgent(llm, agent_timeout_s)

    # ------------------------------------------------------------------
    # Conversation
    # ------------------------------------------------------------------

    def chat(self, message: str) -> ConversationResult:
        reply = self.conversation.run(message)
        if reply is not None and reply.text:
            return ConversationResult(message=reply.text, source="llm")
        return ConversationResult(
            message=(
                "Hi, I am your structural analysis assistant. I can help with:\n"
                "- Beam analysis (simply supported, cantilever, fixed-fixed, propped cantilever)\n"
                "- Point loads, uniform loads, and combined loading\n"
                "- 2D truss analysis (axial forces, displacements, reactions)\n"
                "- 2D frame analysis (portal frames, multi-story frames)\n"
                "- Column buckling checks (Euler + AISC Chapter E)\n"
                "- AISC steel section property lookups\n"
                "- 3D Structural Analysis\n"
                "- Wind, seismic, and snow load determination\n"
                "All results include engineering reports with assumptions and warnings."
            ),
            source="fallback",
        )

    def chat_with_context(self, message: str, context: dict[str, Any]) -> ConversationResult:
        context_summary = self._summarize_canvas_context(context)
        fallback_message = self._contextual_fallback_answer(message, context_summary)
        task = (
            "You are helping with the user's current structural model and analysis results.\n\n"
            f"Current context:\n{context_summary}\n\n"
            f"User question: {message}\n\n"
            "Answer using only the current context when referring to model/results. Be specific "
            "with numbers. If the user asks for a modeling action, briefly state what action they "
            "can ask you to perform. Keep the answer concise and practical."
        )
        reply = self.conversation.run(task)
        if reply is not None and reply.text:
            return ConversationResult(message=reply.text, source="llm")
        return ConversationResult(message=fallback_message, source="fallback")

    def evaluate_results(
        self, message: str, results: dict[str, Any], analysis_type: str, original_prompt: str
    ) -> ConversationResult:
        results_summary = self._summarize_results(results, analysis_type)
        task = (
            "You are reviewing structural analysis results.\n\n"
            f"Original request: {original_prompt}\n"
            f"Analysis type: {analysis_type}\n\n"
            f"Results summary:\n{results_summary}\n\n"
            f"User question: {message}\n\n"
            "Answer the user's question based on the results. Be specific with numbers from the "
            "results. If asking whether results are good, evaluate against typical engineering "
            "criteria: deflection limits (L/360 live, L/240 total), utilization ratios (axial, "
            "bending, shear), stability and serviceability, and code compliance indicators. Use "
            "bullet points for clarity. Keep it under 8 sentences. If the question is about code "
            "compliance, reference AISC/ASCE/IBC where relevant. Always note this is preliminary "
            "and not a substitute for licensed engineering review."
        )
        reply = self.conversation.run(task)
        if reply is not None and reply.text:
            return ConversationResult(message=reply.text, source="llm")
        return ConversationResult(
            message=(
                f"Results summary for {analysis_type}:\n{results_summary}\n\n"
                "I cannot provide a detailed evaluation without the LLM. Check the numbers "
                "against your design criteria."
            ),
            source="fallback",
        )

    # ------------------------------------------------------------------
    # Canvas tool routing
    # ------------------------------------------------------------------

    def route_canvas_tool(self, message: str, context: dict[str, Any] | None = None) -> tuple[CanvasToolDecision, str]:
        fallback = self._fallback_canvas_tool_decision(message)
        task = (
            f"User message:\n{message}\n\n"
            f"Current context summary:\n{self._summarize_canvas_context(context or {})}\n\n"
            "Route this message to a canvas action (or none). Return only the structured action."
        )
        raw = self.router.run_raw(task)
        if raw is None:
            return fallback, "fallback"
        # The model may return the action directly, or wrap it as
        # {"name": <action>, "arguments": {...}}.
        action = raw.get("action") or raw.get("name") or "none"
        arguments = raw.get("arguments") if isinstance(raw.get("arguments"), dict) else {}
        if not arguments:
            arguments = {k: v for k, v in raw.items() if k not in ("action", "name", "message", "confidence")}
        try:
            decision = CanvasToolDecision(
                action=str(action),
                arguments=arguments,
                message=str(raw.get("message") or ""),
                confidence=float(raw.get("confidence") or 0.0),
            )
        except (TypeError, ValueError, ValidationError):
            return fallback, "fallback"
        if decision.action not in {
            "none", "clear_canvas", "clear_analysis", "draw_simple_beam", "draw_3d_frame_template",
            "apply_member_group_sections", "set_rigid_diaphragm", "set_load_combination",
            "apply_story_forces",
        }:
            return fallback, "fallback"
        if decision.action == "set_rigid_diaphragm" and not isinstance(decision.arguments.get("enabled"), bool):
            return fallback, "fallback"
        if decision.action == "set_load_combination" and not str(decision.arguments.get("name") or "").strip():
            return fallback, "fallback"
        if isinstance(decision.arguments.get("arguments"), dict) and not decision.arguments.get("arguments"):
            decision.arguments.pop("arguments", None)
        if decision.action == "none":
            return CanvasToolDecision(), "llm"
        return decision, "llm"

    # ------------------------------------------------------------------
    # Main analysis pipeline
    # ------------------------------------------------------------------

    def analyze(self, prompt: str) -> AgentResult:
        log.info("agent_analyze_start", extra={"prompt_len": len(prompt)})
        traces: list[AgentTrace] = []
        assumptions = [
            "Preliminary elastic analysis only.",
            "Units are interpreted from the prompt where possible.",
            "A multi-agent system (intent, planner, extractor, critic, reporter) coordinates the run.",
        ]
        warnings = [
            "Not a substitute for licensed engineering review or full code compliance.",
        ]

        intent = self._intent(prompt)
        traces.append(AgentTrace(agent="Intent Agent", summary=intent.summary, data=intent.__dict__))

        analysis_type = intent.structure_type
        # Planner and input extraction both depend only on the intent, so run
        # them concurrently to cut end-to-end latency.
        with ThreadPoolExecutor(max_workers=2) as pool:
            plan_future = pool.submit(self._plan, prompt, intent)
            inputs_future = pool.submit(self._extract_inputs, prompt, analysis_type)
            plan = plan_future.result()
            inputs = inputs_future.result()
        traces.append(AgentTrace(agent="Planner Agent", summary=plan.summary, data=plan.__dict__))

        if analysis_type == "3d_frame":
            return self._run_3d_analysis(prompt, inputs, traces, assumptions, warnings)
        if analysis_type == "truss":
            return self._run_truss_analysis(prompt, inputs, traces, assumptions, warnings)
        if analysis_type == "frame":
            return self._run_frame_analysis(prompt, inputs, traces, assumptions, warnings)
        if analysis_type == "column":
            return self._run_column_analysis(prompt, inputs, traces, assumptions, warnings)
        return self._run_beam_analysis(prompt, inputs, traces, assumptions, warnings)

    def _extract_inputs(self, prompt: str, analysis_type: str) -> Any:
        """Dispatch to the right input extractor for the detected type."""
        if analysis_type == "3d_frame":
            return self._extract_3d_inputs(prompt)
        if analysis_type == "truss":
            return self._extract_truss_inputs(prompt)
        if analysis_type == "frame":
            return self._extract_frame_inputs(prompt)
        if analysis_type == "column":
            return self._extract_column_inputs(prompt)
        return self._extract_beam_inputs(prompt)

    # ------------------------------------------------------------------
    # 3D Frame analysis pipeline
    # ------------------------------------------------------------------

    def _run_3d_analysis(self, prompt: str, structure_inputs: Any, traces: list, assumptions: list, warnings: list) -> AgentResult:
        assumptions.append("Rigid connections assumed for 3D frame elements.")
        assumptions.append("Linear elastic material behavior in 3D space.")

        traces.append(AgentTrace(
            agent="Solver Tool Agent",
            summary=f"Running 3D frame analysis with {len(structure_inputs.nodes)} nodes and {len(structure_inputs.members)} members.",
            data=structure_inputs.model_dump(),
        ))

        results = analyze_3d_structure_opensees(structure_inputs)

        critic = self._critic(results, "3d_frame")
        warnings.extend(critic["warnings"])
        traces.append(AgentTrace(agent="Results Critic Agent", summary=critic["summary"], data=critic))

        report = format_engineering_report(prompt, assumptions, warnings, results, analysis_type="3d_frame")
        traces.append(AgentTrace(agent="Report Agent", summary="Generated 3D analysis report.", data={}))

        return AgentResult("3d_frame", assumptions, warnings, traces, results, report)

    # ------------------------------------------------------------------
    # Beam analysis pipeline
    # ------------------------------------------------------------------

    def _run_beam_analysis(self, prompt: str, beam_inputs: Any, traces: list, assumptions: list, warnings: list) -> AgentResult:
        support = beam_inputs.support_type
        n_pl = len(beam_inputs.point_loads)

        solver_desc = f"Running beam analysis ({support})"
        if n_pl:
            solver_desc += f" with {n_pl} point load(s)"
        if beam_inputs.udl_kn_per_m > 0:
            solver_desc += f" + UDL {beam_inputs.udl_kn_per_m} kN/m"

        traces.append(AgentTrace(
            agent="Solver Tool Agent",
            summary=solver_desc,
            data=beam_inputs.model_dump(),
        ))

        results = analyze_beam_opensees(beam_inputs)
        diagrams = results.pop("_diagrams", None)

        critic = self._critic(results, "beam")
        warnings.extend(critic["warnings"])
        traces.append(AgentTrace(agent="Results Critic Agent", summary=critic["summary"], data=critic))

        if beam_inputs.inertia_m4 is None:
            warnings.append("Moment and shear were computed, but deflection needs a valid moment of inertia.")
        if beam_inputs.section_modulus_m3 is None:
            warnings.append("Bending stress was not computed because section modulus was not provided.")

        report = format_engineering_report(prompt, assumptions, warnings, results, analysis_type="beam")
        traces.append(AgentTrace(agent="Report Agent", summary="Generated preliminary engineering report.", data={}))

        result = AgentResult("beam", assumptions, warnings, traces, results, report)
        result._diagrams = diagrams  # type: ignore[attr-defined]
        return result

    # ------------------------------------------------------------------
    # Truss analysis pipeline
    # ------------------------------------------------------------------

    def _run_truss_analysis(self, prompt: str, truss_inputs: Any, traces: list, assumptions: list, warnings: list) -> AgentResult:
        assumptions.append("All joints are assumed pin-connected (truss assumption).")
        assumptions.append("Members carry axial forces only.")

        traces.append(AgentTrace(
            agent="Solver Tool Agent",
            summary=f"Running 2D truss analysis with {len(truss_inputs.nodes)} nodes and {len(truss_inputs.members)} members.",
            data=truss_inputs.model_dump(),
        ))

        results = analyze_truss(truss_inputs)

        critic = self._critic(results, "truss")
        member_forces = results.get("member_forces", {})
        for mid, mf in member_forces.items():
            if mf.get("tension_or_compression") == "compression":
                critic["warnings"].append(f"Member {mid} is in compression ({mf.get('axial_kn')} kN). Check buckling capacity.")
        warnings.extend(critic["warnings"])
        traces.append(AgentTrace(agent="Results Critic Agent", summary=critic["summary"], data=critic))

        report = format_engineering_report(prompt, assumptions, warnings, results, analysis_type="truss")
        traces.append(AgentTrace(agent="Report Agent", summary="Generated truss analysis report.", data={}))

        return AgentResult("truss", assumptions, warnings, traces, results, report)

    # ------------------------------------------------------------------
    # Frame analysis pipeline
    # ------------------------------------------------------------------

    def _run_frame_analysis(self, prompt: str, frame_inputs: Any, traces: list, assumptions: list, warnings: list) -> AgentResult:
        assumptions.append("Rigid connections assumed at all beam-column joints.")
        assumptions.append("Linear elastic material behavior.")

        traces.append(AgentTrace(
            agent="Solver Tool Agent",
            summary=f"Running 2D frame analysis with {len(frame_inputs.nodes)} nodes and {len(frame_inputs.members)} members.",
            data=frame_inputs.model_dump(),
        ))

        results = analyze_frame(frame_inputs)

        critic = self._critic(results, "frame")
        if results.get("max_displacement_mm", 0) > 50:
            critic["warnings"].append(f"Maximum displacement ({results.get('max_displacement_mm')} mm) is large. Check serviceability.")
        warnings.extend(critic["warnings"])
        traces.append(AgentTrace(agent="Results Critic Agent", summary=critic["summary"], data=critic))

        report = format_engineering_report(prompt, assumptions, warnings, results, analysis_type="frame")
        traces.append(AgentTrace(agent="Report Agent", summary="Generated frame analysis report.", data={}))

        return AgentResult("frame", assumptions, warnings, traces, results, report)

    # ------------------------------------------------------------------
    # Column analysis pipeline
    # ------------------------------------------------------------------

    def _run_column_analysis(self, prompt: str, col_inputs: Any, traces: list, assumptions: list, warnings: list) -> AgentResult:
        assumptions.append("Column is prismatic (constant cross-section).")
        assumptions.append("Analysis per AISC Chapter E (compression members).")

        traces.append(AgentTrace(
            agent="Solver Tool Agent",
            summary=f"Running column buckling analysis ({col_inputs.end_condition}).",
            data=col_inputs.model_dump(),
        ))

        results = analyze_column(col_inputs)
        col_warnings = results.pop("warnings", [])
        critic = self._critic(results, "column")
        critic["warnings"].extend(col_warnings)
        warnings.extend(critic["warnings"])
        traces.append(AgentTrace(agent="Results Critic Agent", summary=critic["summary"], data=critic))

        report = format_engineering_report(prompt, assumptions, warnings, results, analysis_type="column")
        traces.append(AgentTrace(agent="Report Agent", summary="Generated column analysis report.", data={}))

        return AgentResult("column", assumptions, warnings, traces, results, report)

    # ------------------------------------------------------------------
    # Intent / Planning / Critic agents
    # ------------------------------------------------------------------

    def _intent(self, prompt: str) -> Intent:
        task = (
            "Identify structure type, analysis type, material, boundary conditions, loads, and "
            f"missing data from this request:\n{prompt}"
        )
        args = self.intent_agent.run_tool(task)
        if args:
            try:
                intent = Intent(**{k: v for k, v in args.items() if k in Intent.__dataclass_fields__})
                intent.structure_type = _normalize_enum(
                    intent.structure_type, {"beam", "truss", "frame", "column", "3d_frame"}
                )
                return intent
            except (TypeError, ValueError):
                pass
        return Intent(
            structure_type=self._detect_structure_type(prompt),
            boundary_conditions=self._detect_support_type(prompt) if self._detect_structure_type(prompt) == "beam" else "N/A",
            summary=f"Detected a preliminary {self._detect_structure_type(prompt)} analysis request.",
        )

    def _plan(self, prompt: str, intent: Intent) -> Plan:
        solver_map = {
            "beam": "openseespy_beam",
            "truss": "openseespy_truss",
            "frame": "openseespy_frame",
            "3d_frame": "openseespy_3d_frame",
            "column": "column_euler_aisc",
        }
        solver = solver_map.get(intent.structure_type, "openseespy_beam")
        task = (
            "Choose a solver and required structured inputs. "
            f"Available solvers: beam, truss, frame, 3d_frame, column. "
            f"Intent: {json.dumps(intent.__dict__)}\nUser request: {prompt}"
        )
        args = self.planner_agent.run_tool(task)
        if args:
            try:
                return Plan(
                    solver=str(args.get("solver") or solver),
                    required_inputs=list(args.get("required_inputs") or []),
                    summary=str(args.get("summary") or f"Use the {solver} solver."),
                )
            except (TypeError, ValueError):
                pass
        return Plan(solver=solver, summary=f"Use the {solver} solver.")

    def _critic(self, results: dict[str, Any], analysis_type: str) -> dict[str, Any]:
        deterministic: list[str] = []
        if not results.get("is_finite", True):
            deterministic.append("One or more results are not finite. Check model stability.")
        if analysis_type == "beam":
            if results.get("deflection_ok") is False:
                deterministic.append("Deflection exceeds the selected serviceability limit.")
            if results.get("span_m", 0) <= 0:
                deterministic.append("Span must be positive.")
            udl = results.get("udl_kn_per_m", 0)
            if udl is not None and udl < 0:
                deterministic.append("Uniform load should be entered as a positive gravity load magnitude.")

        task = (
            f"Analysis type: {analysis_type}\n\n"
            f"Results summary:\n{self._summarize_results(results, analysis_type)}\n\n"
            "Review these results for sanity and serviceability. Return only the structured review."
        )
        args = self.critic.run_tool(task)
        if args:
            try:
                warnings = [str(w) for w in (args.get("warnings") or [])]
                # merge deterministic safety checks so they are never lost
                for w in deterministic:
                    if w not in warnings:
                        warnings.append(w)
                return {
                    "summary": str(args.get("summary") or "Reviewed results for sanity and serviceability."),
                    "warnings": warnings,
                    "ok": bool(args.get("ok", not warnings)),
                }
            except (TypeError, ValueError):
                pass
        return {
            "summary": "Checked basic result sanity, unit-sensitive fields, and deflection status.",
            "warnings": deterministic,
            "ok": not deterministic,
        }

    # ------------------------------------------------------------------
    # Input extraction: Beam (LLM-driven, deterministic fallback)
    # ------------------------------------------------------------------

    def _extract_beam_inputs(self, prompt: str) -> BeamInputs:
        task = (
            "Extract the beam analysis inputs from this request. Use schema defaults for any "
            f"value not stated.\n\nRequest:\n{prompt}"
        )
        args = self.beam_extractor.run_tool(task)
        if args:
            point_loads = [
                PointLoad(magnitude_kn=float(pl.get("magnitude_kn", 0)), position_m=float(pl.get("position_m", 0)))
                for pl in (args.get("point_loads") or [])
                if isinstance(pl, dict)
            ]
            try:
                return BeamInputs(
                    span_m=float(args.get("span_m", 6.0)),
                    udl_kn_per_m=float(args.get("udl_kn_per_m", 0.0)),
                    point_loads=point_loads,
                    elastic_modulus_gpa=float(args.get("elastic_modulus_gpa", 200.0)),
                    inertia_m4=args.get("inertia_m4"),
                    area_m2=float(args.get("area_m2", 1.0)),
                    section_modulus_m3=args.get("section_modulus_m3"),
                    deflection_limit_ratio=float(args.get("deflection_limit_ratio", 360.0)),
                    support_type=_normalize_enum(
                        args.get("support_type", "simply_supported"),
                        {"simply_supported", "cantilever", "fixed_fixed", "propped_cantilever"},
                    ),
                )
            except (TypeError, ValueError, ValidationError):
                pass
        return self._fallback_beam_inputs(prompt)

    def _fallback_beam_inputs(self, prompt: str) -> BeamInputs:
        normalized = prompt.lower().replace(",", " ")
        support_type = self._detect_support_type(prompt)
        point_loads = []
        pl_patterns = [
            r"point load[s]?\s+(?:of\s+)?([0-9.]+)\s*kn\s+at\s+([0-9.]+)\s*m",
            r"([0-9.]+)\s*kn\s+(?:point load\s+)?at\s+([0-9.]+)\s*m",
            r"concentrated load[s]?\s+(?:of\s+)?([0-9.]+)\s*kn\s+at\s+([0-9.]+)\s*m",
        ]
        for pattern in pl_patterns:
            for match in re.finditer(pattern, normalized):
                try:
                    point_loads.append(PointLoad(magnitude_kn=float(match.group(1)), position_m=float(match.group(2))))
                except (ValueError, IndexError):
                    pass
        values = {
            "span_m": self._find_number(normalized, [r"span(?: is)? ([0-9.]+)\s*m", r"([0-9.]+)\s*m span", r"([0-9.]+)\s*m\s+(?:long|length)"], 6.0),
            "udl_kn_per_m": self._find_number(
                normalized,
                [r"(?:udl|uniform load|distributed load|load)(?: is)? ([0-9.]+)\s*kn/?m", r"([0-9.]+)\s*kn/?m"],
                10.0 if not point_loads else 0.0,
            ),
            "elastic_modulus_gpa": self._find_number(normalized, [r"(?:e|elastic modulus)(?: is)? ([0-9.]+)\s*gpa", r"([0-9.]+)\s*gpa"], 200.0),
            "inertia_m4": self._find_optional_number(normalized, [r"(?:i|inertia)(?: is)? ([0-9.eE+-]+)\s*m4"]),
            "area_m2": self._find_number(normalized, [r"(?:a|area)(?: is)? ([0-9.eE+-]+)\s*m2", r"([0-9.eE+-]+)\s*m2 area"], 1.0),
            "section_modulus_m3": self._find_optional_number(normalized, [r"(?:s|section modulus)(?: is)? ([0-9.eE+-]+)\s*m3"]),
            "deflection_limit_ratio": self._find_number(normalized, [r"l/([0-9.]+)"], 360.0),
            "point_loads": point_loads,
            "support_type": support_type,
        }
        try:
            return BeamInputs(**values)
        except ValidationError:
            return BeamInputs(span_m=6.0, udl_kn_per_m=10.0, elastic_modulus_gpa=200.0, support_type=support_type)

    # ------------------------------------------------------------------
    # Input extraction: Column (LLM-driven, deterministic fallback)
    # ------------------------------------------------------------------

    def _extract_column_inputs(self, prompt: str) -> ColumnInputs:
        task = (
            "Extract the column buckling inputs from this request. Use schema defaults for any "
            f"value not stated.\n\nRequest:\n{prompt}"
        )
        args = self.column_extractor.run_tool(task)
        if args:
            try:
                return ColumnInputs(
                    length_m=float(args.get("length_m", 4.0)),
                    area_m2=float(args.get("area_m2", 0.01)),
                    inertia_m4=float(args.get("inertia_m4", 1e-4)),
                    elastic_modulus_gpa=float(args.get("elastic_modulus_gpa", 200.0)),
                    yield_stress_mpa=float(args.get("yield_stress_mpa", 250.0)),
                    end_condition=_normalize_enum(
                        args.get("end_condition", "pinned_pinned"),
                        {"pinned_pinned", "fixed_free", "fixed_pinned", "fixed_fixed"},
                    ),
                    axial_load_kn=float(args.get("axial_load_kn", 500.0)),
                )
            except (TypeError, ValueError, ValidationError):
                pass
        return self._fallback_column_inputs(prompt)

    def _fallback_column_inputs(self, prompt: str) -> ColumnInputs:
        normalized = prompt.lower().replace(",", " ")
        end_condition = "pinned_pinned"
        if "fixed" in normalized and "free" in normalized:
            end_condition = "fixed_free"
        elif "fixed" in normalized and ("pin" in normalized or "pinned" in normalized):
            end_condition = "fixed_pinned"
        elif normalized.count("fixed") >= 2 or "both ends fixed" in normalized or "fixed-fixed" in normalized:
            end_condition = "fixed_fixed"
        try:
            return ColumnInputs(
                length_m=self._find_number(normalized, [r"(?:length|height|column)(?: is)? ([0-9.]+)\s*m", r"([0-9.]+)\s*m\s+(?:long|tall|column|height)"], 4.0),
                area_m2=self._find_number(normalized, [r"(?:area|a)(?: is)? ([0-9.eE+-]+)\s*m2", r"([0-9.eE+-]+)\s*m2"], 0.01),
                inertia_m4=self._find_number(normalized, [r"(?:inertia|i)(?: is)? ([0-9.eE+-]+)\s*m4", r"([0-9.eE+-]+)\s*m4"], 1e-4),
                elastic_modulus_gpa=self._find_number(normalized, [r"(?:e|elastic modulus)(?: is)? ([0-9.]+)\s*gpa", r"([0-9.]+)\s*gpa"], 200.0),
                yield_stress_mpa=self._find_number(normalized, [r"(?:fy|yield)(?: is)? ([0-9.]+)\s*mpa", r"([0-9.]+)\s*mpa"], 250.0),
                end_condition=end_condition,
                axial_load_kn=self._find_number(normalized, [r"(?:axial|load|force|p)(?: is)? ([0-9.]+)\s*kn", r"([0-9.]+)\s*kn"], 500.0),
            )
        except ValidationError:
            return ColumnInputs(
                length_m=4.0, area_m2=0.01, inertia_m4=1e-4,
                elastic_modulus_gpa=200.0, yield_stress_mpa=250.0,
                end_condition="pinned_pinned", axial_load_kn=500.0,
            )

    # ------------------------------------------------------------------
    # Input extraction: 3D Frame
    # ------------------------------------------------------------------

    def _extract_3d_inputs(self, prompt: str) -> Structure3DInputs:
        json_match = re.search(r"\{.*\}", prompt, flags=re.DOTALL)
        if json_match:
            try:
                return Structure3DInputs.model_validate(json.loads(json_match.group(0)))
            except (json.JSONDecodeError, ValidationError):
                pass
        nodes = [
            Node3D(id=1, x=0.0, y=0.0, z=0.0, support=Support3D(ux=True, uy=True, uz=True, rx=True, ry=True, rz=True)),
            Node3D(id=2, x=0.0, y=5.0, z=0.0, support=None),
        ]
        members = [Member3D(id=1, start_node=1, end_node=2)]
        nodal_loads = [Load3D(node_id=2, fx_kn=10.0, fy_kn=-50.0, fz_kn=5.0)]
        return Structure3DInputs(nodes=nodes, members=members, nodal_loads=nodal_loads)

    # ------------------------------------------------------------------
    # Input extraction: Truss
    # ------------------------------------------------------------------

    def _extract_truss_inputs(self, prompt: str) -> TrussInputs:
        normalized = prompt.lower().replace(",", " ")
        json_match = re.search(r"\{.*\}", prompt, flags=re.DOTALL)
        if json_match:
            try:
                return TrussInputs.model_validate(json.loads(json_match.group(0)))
            except (json.JSONDecodeError, ValidationError):
                pass
        span = self._find_number(normalized, [r"span(?: is)? ([0-9.]+)\s*m", r"([0-9.]+)\s*m"], 6.0)
        height = self._find_number(normalized, [r"height(?: is)? ([0-9.]+)\s*m", r"([0-9.]+)\s*m\s+(?:high|tall|height)"], span / 3)
        load = self._find_number(normalized, [r"(?:load|force)(?: is)? ([0-9.]+)\s*kn", r"([0-9.]+)\s*kn"], 50.0)
        half = span / 2.0
        nodes = [
            TrussNode(id=1, x=0.0, y=0.0, support="pin"),
            TrussNode(id=2, x=half, y=0.0, support="free"),
            TrussNode(id=3, x=span, y=0.0, support="roller_x"),
            TrussNode(id=4, x=half, y=height, support="free"),
        ]
        members = [
            TrussMember(id=1, start_node=1, end_node=2),
            TrussMember(id=2, start_node=2, end_node=3),
            TrussMember(id=3, start_node=1, end_node=4),
            TrussMember(id=4, start_node=4, end_node=3),
            TrussMember(id=5, start_node=2, end_node=4),
        ]
        loads = [TrussLoad(node_id=4, fy_kn=-load)]
        return TrussInputs(nodes=nodes, members=members, loads=loads)

    # ------------------------------------------------------------------
    # Input extraction: Frame
    # ------------------------------------------------------------------

    def _extract_frame_inputs(self, prompt: str) -> FrameInputs:
        normalized = prompt.lower().replace(",", " ")
        json_match = re.search(r"\{.*\}", prompt, flags=re.DOTALL)
        if json_match:
            try:
                return FrameInputs.model_validate(json.loads(json_match.group(0)))
            except (json.JSONDecodeError, ValidationError):
                pass
        width = self._find_number(normalized, [r"(?:width|span|bay)(?: is)? ([0-9.]+)\s*m", r"([0-9.]+)\s*m\s+(?:wide|span|bay)"], 6.0)
        height = self._find_number(normalized, [r"(?:height|column height)(?: is)? ([0-9.]+)\s*m", r"([0-9.]+)\s*m\s+(?:high|tall|height)"], 4.0)
        lateral_load = self._find_number(normalized, [r"(?:lateral|horizontal|wind)\s+(?:load|force)(?: is)? ([0-9.]+)\s*kn", r"([0-9.]+)\s*kn\s+(?:lateral|horizontal)"], 0.0)
        gravity_load = self._find_number(normalized, [r"(?:gravity|vertical|udl|distributed)\s+(?:load)(?: is)? ([0-9.]+)\s*kn/?m", r"([0-9.]+)\s*kn/?m"], 20.0)
        nodes = [
            FrameNode(id=1, x=0.0, y=0.0, support="fixed"),
            FrameNode(id=2, x=0.0, y=height, support="free"),
            FrameNode(id=3, x=width, y=height, support="free"),
            FrameNode(id=4, x=width, y=0.0, support="fixed"),
        ]
        members = [
            FrameMember(id=1, start_node=1, end_node=2),
            FrameMember(id=2, start_node=2, end_node=3),
            FrameMember(id=3, start_node=3, end_node=4),
        ]
        nodal_loads = [FrameLoad(node_id=2, fx_kn=lateral_load)] if lateral_load > 0 else []
        member_loads = [FrameMemberLoad(member_id=2, udl_kn_per_m=gravity_load)] if gravity_load > 0 else []
        return FrameInputs(nodes=nodes, members=members, nodal_loads=nodal_loads, member_loads=member_loads)

    # ------------------------------------------------------------------
    # Structure / support detection (fallback heuristics)
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_structure_type(text: str) -> str:
        lower = text.lower()
        if any(kw in lower for kw in ("3d", "three-dimensional", "space frame", "space truss")):
            return "3d_frame"
        if any(kw in lower for kw in ("truss", "bar element", "axial only")):
            return "truss"
        if any(kw in lower for kw in ("frame", "portal", "multi-story", "rigid frame", "moment frame")):
            return "frame"
        if any(kw in lower for kw in ("column", "buckling", "euler", "slenderness", "compression member")):
            return "column"
        return "beam"

    @staticmethod
    def _detect_support_type(text: str) -> str:
        lower = text.lower()
        if any(kw in lower for kw in ("cantilever", "fixed-free", "fixed free")):
            return "cantilever"
        if any(kw in lower for kw in ("fixed-fixed", "fixed fixed", "both ends fixed", "encastre")):
            return "fixed_fixed"
        if any(kw in lower for kw in ("propped cantilever", "propped", "fixed-pinned", "fixed pinned")):
            return "propped_cantilever"
        return "simply_supported"

    # ------------------------------------------------------------------
    # Context summarization (shared by conversation + router)
    # ------------------------------------------------------------------

    def _summarize_canvas_context(self, context: dict[str, Any]) -> str:
        model = context.get("model") or {}
        results = context.get("results") or {}
        analysis_type = context.get("analysis_type") or "unknown"
        nodes = self._as_list(model.get("nodes"))
        members = self._as_list(model.get("members"))
        slabs = self._as_list(model.get("slabs"))
        loads = self._as_list(model.get("nodal_loads") or model.get("loads"))
        member_loads = self._as_list(model.get("member_loads") or model.get("memberLoads"))
        model_summary = context.get("model_summary") or {}
        lines = [
            f"Analysis type: {analysis_type}",
            f"Model: {len(nodes)} nodes, {len(members)} members, {len(slabs)} slabs, {len(loads)} nodal loads, {len(member_loads)} member loads.",
        ]
        if analysis_type == "3d_frame" and nodes:
            z_levels = sorted(set(round(n.get("z", 0), 4) for n in nodes))
            lines.append(f"Building: {len(z_levels)} floor levels at z = {', '.join(f'{z:.2f}' for z in z_levels)} m")
            xs = [n.get("x", 0) for n in nodes]
            ys = [n.get("y", 0) for n in nodes]
            if xs and ys:
                lines.append(f"Dimensions: x-range [{min(xs):.2f}, {max(xs):.2f}] m, y-range [{min(ys):.2f}, {max(ys):.2f}] m")
            if members:
                groups: dict[str, int] = {}
                for m in members:
                    g = (m.get("group") or "unknown").lower()
                    groups[g] = groups.get(g, 0) + 1
                group_parts = [f"{c} {g}{'s' if c > 1 else ''}" for g, c in sorted(groups.items())]
                if group_parts:
                    lines.append(f"Member groups: {', '.join(group_parts)}")
        combo = model.get("active_load_combination") or model_summary.get("active_load_combination")
        if combo:
            lines.append(f"Active load combination: {combo}")
        rigid = model.get("rigid_diaphragms")
        if rigid is not None:
            lines.append(f"Rigid diaphragms: {'enabled' if rigid else 'disabled'}")
        if results:
            lines.append(self._summarize_results(results, analysis_type))
        else:
            lines.append("No analysis results are currently available.")
        return "\n".join(lines)

    @staticmethod
    def _as_list(value: Any) -> list[Any]:
        return value if isinstance(value, list) else []

    def _contextual_fallback_answer(self, message: str, context_summary: str) -> str:
        text = message.lower()
        if any(term in text for term in ("result", "drift", "reaction", "displacement", "force", "analysis")):
            return f"Here is what I know from the current model/results:\n{context_summary}"
        if any(term in text for term in ("model", "building", "current", "geometry")):
            return f"Current model context:\n{context_summary}"
        return (
            "I can use the current model context to answer questions about geometry, loads, analysis "
            "results, story drift, base reactions, and member forces. I can also help modify the canvas "
            "by drawing a 3D frame template, applying beam/column sections, clearing analysis, changing "
            "load combinations, or toggling rigid diaphragms."
        )

    def _summarize_results(self, results: dict[str, Any], analysis_type: str) -> str:
        lines = [f"Solver: {results.get('solver', 'unknown')}", f"All results finite: {results.get('is_finite', True)}"]
        if analysis_type == "beam":
            lines += [
                f"Span: {results.get('span_m', 'N/A')} m",
                f"Max moment: {results.get('max_moment_kn_m', 'N/A')} kN-m",
                f"Max shear: {results.get('max_shear_kn', 'N/A')} kN",
                f"Max deflection: {results.get('max_deflection_mm', 'N/A')} mm",
                f"Deflection OK: {results.get('deflection_ok', 'N/A')}",
                f"Stress OK: {results.get('stress_ok', 'N/A')}",
                f"Utilization: {results.get('utilization_ratio', 'N/A')}",
            ]
        elif analysis_type == "3d_frame":
            lines.append(f"Load combination: {results.get('load_combination', 'N/A')}")
            lines.append(f"Rigid diaphragms: {results.get('rigid_diaphragms', 'N/A')}")
            lines.append(f"Max translation: {results.get('max_translation_mm', 'N/A')} mm")
            base = results.get("base_reactions", {})
            if base:
                lines.append(f"Base reactions: Fx={base.get('Fx_kn', 'N/A')} kN, Fy={base.get('Fy_kn', 'N/A')} kN, Fz={base.get('Fz_kn', 'N/A')} kN")
            story = results.get("story_response", {})
            drifts = story.get("story_drifts", []) if isinstance(story, dict) else []
            drift_values = [float(d.get("drift_mm")) for d in drifts if isinstance(d, dict) and isinstance(d.get("drift_mm"), (int, float))]
            if drift_values:
                lines.append(f"Maximum story drift: {max(drift_values)} mm")
            lines.append(f"Member force envelopes: {len(results.get('member_force_summary', {}))} members")
        elif analysis_type == "frame":
            lines.append(f"Max displacement: {results.get('max_displacement_mm', 'N/A')} mm")
            lines.append(f"Node displacements: {len(results.get('node_displacements', {}))} nodes")
            lines.append(f"Reactions: {len(results.get('reactions', {}))} supports")
            mf = results.get("member_forces", {})
            lines.append(f"Member forces: {len(mf)} members")
            for mid, forces in mf.items():
                lines.append(f"  Member {mid}: P={forces.get('axial_start_kn', 'N/A')} kN, V={forces.get('shear_start_kn', 'N/A')} kN, M={forces.get('moment_start_kn_m', 'N/A')} kN-m")
        elif analysis_type == "truss":
            mf = results.get("member_forces", {})
            lines.append(f"Member forces: {len(mf)} members")
            for mid, forces in mf.items():
                lines.append(f"  Member {mid}: {forces.get('axial_kn', 'N/A')} kN ({forces.get('tension_or_compression', 'N/A')})")
            lines.append(f"Reactions: {len(results.get('reactions', {}))} supports")
        elif analysis_type == "column":
            lines += [
                f"Slenderness ratio: {results.get('slenderness_ratio', 'N/A')}",
                f"Pn (design capacity): {results.get('design_capacity_kn', 'N/A')} kN",
                f"Applied load: {results.get('axial_load_kn', 'N/A')} kN",
                f"Utilization: {results.get('utilization_ratio', 'N/A')}",
                f"OK: {results.get('ok', 'N/A')}",
            ]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Deterministic fallback canvas router (used only when no LLM is live)
    # ------------------------------------------------------------------

    def _fallback_canvas_tool_decision(self, message: str) -> CanvasToolDecision:
        text = " ".join(message.lower().strip().split())
        question_starts = ("how ", "what ", "why ", "when ", "where ", "can you explain", "tell me")
        if text.startswith(question_starts):
            return CanvasToolDecision()

        clear_phrases = [
            "clear screen", "clear the screen", "clear canvas", "clear the canvas",
            "make canvas empty", "make the canvas empty", "empty canvas", "empty the canvas",
            "reset canvas", "reset the canvas", "delete drawing", "delete the drawing",
            "erase drawing", "erase the drawing", "remove drawing", "remove the drawing",
            "start over", "new drawing", "new model",
        ]
        if any(phrase in text for phrase in clear_phrases):
            return CanvasToolDecision(action="clear_canvas", message="I cleared the drawing canvas.", confidence=0.9)

        if any(phrase in text for phrase in ("clear analysis", "clear results", "remove analysis", "reset analysis")):
            return CanvasToolDecision(action="clear_analysis", message="I cleared the analysis results and kept the model.", confidence=0.9)

        if "rigid diaphragm" in text or "diaphragm" in text:
            enabled = not any(term in text for term in ("off", "disable", "without", "no diaphragm", "remove"))
            return CanvasToolDecision(
                action="set_rigid_diaphragm",
                arguments={"enabled": enabled},
                message=f"I {'enabled' if enabled else 'disabled'} rigid floor diaphragms.",
                confidence=0.85,
            )

        combo_match = re.search(r"(?:set|use|change).*?(1\.[0-9]d[^,.;]*)", text)
        if "load combination" in text or "combo" in text:
            name = combo_match.group(1).upper().replace(" ", "") if combo_match else ""
            aliases = {
                "1.0D+1.0L": "1.0D + 1.0L",
                "1.2D+1.6L": "1.2D + 1.6L",
                "1.2D+1.0EX+0.5L": "1.2D + 1.0EX + 0.5L",
                "1.2D+1.0EY+0.5L": "1.2D + 1.0EY + 0.5L",
            }
            if "ey" in text:
                name = "1.2D + 1.0EY + 0.5L"
            elif "ex" in text or "lateral x" in text:
                name = "1.2D + 1.0EX + 0.5L"
            elif name in aliases:
                name = aliases[name]
            return CanvasToolDecision(action="set_load_combination", arguments={"name": name}, message="I updated the active load combination.", confidence=0.75)

        if any(term in text for term in ("story force", "story forces", "apply wind", "apply seismic", "apply eq", "apply earthquake")):
            return self._story_forces_decision(text)

        if any(phrase in text for phrase in ("apply beam column", "apply beam/column", "assign sections", "apply sections", "beam column sections")):
            return CanvasToolDecision(action="apply_member_group_sections", message="I applied preliminary beam, column, and brace section properties.", confidence=0.9)

        if any(term in text for term in ("3x3", "3 x 3", "three story", "3 story", "3-story", "3d frame")) and any(term in text for term in ("draw", "create", "make", "model", "generate")):
            return CanvasToolDecision(action="draw_3d_frame_template", message="I created a 3x3 3-story 3D frame template.", confidence=0.9)

        draw_terms = ("draw", "create", "make", "model", "sketch")
        if "beam" in text and any(term in text for term in draw_terms):
            span = self._find_number(text, [r"(?:span|length)(?: is| of)?\s*([0-9.]+)\s*m", r"([0-9.]+)\s*m"], 2.0)
            point_loads = []
            for match in re.finditer(r"([0-9.]+)\s*kn(?:\s+point load|\s+load)?(?:\s+at\s+([0-9.]+)\s*m|\s+at\s+(?:midspan|middle|center|centre))?", text):
                magnitude = float(match.group(1))
                position = float(match.group(2)) if match.group(2) else span / 2
                point_loads.append({"magnitude_kn": magnitude, "position_m": position})
            udl = self._find_number(text, [r"(?:udl|uniform load|distributed load)\s*(?:of|is)?\s*([0-9.]+)\s*kn/?m", r"([0-9.]+)\s*kn/?m"], 0.0)
            return CanvasToolDecision(
                action="draw_simple_beam",
                arguments={"span_m": span, "udl_kn_per_m": udl, "point_loads": point_loads},
                message="I drew a simply supported beam on the canvas.",
                confidence=0.8,
            )
        return CanvasToolDecision()

    def _story_forces_decision(self, text: str) -> CanvasToolDecision:
        load_type = "seismic" if any(t in text for t in ("seismic", "earthquake", "eq", "lateral")) else "wind"
        direction = "y" if "y direction" in text or "transverse" in text else "x"
        distribution = "windward" if "windward" in text else "equal"
        arguments: dict[str, Any] = {"load_type": load_type, "direction": direction, "distribution": distribution}
        if load_type == "wind":
            arguments["wind"] = {
                "basic_wind_speed_ms": self._find_number(text, [r"([0-9.]+)\s*m/s"], 30.0),
                "exposure": "C",
                "height_m": self._find_number(text, [r"([0-9.]+)\s*m"], 8.0),
                "length_m": 6.0,
                "width_m": 6.0,
                "story_height_m": 4.0,
                "internal_pressure": "minor_openings",
            }
        else:
            arguments["seismic"] = {
                "spectral_accel_sd": 0.4,
                "spectral_accel_1s": 0.2,
                "site_class": "D",
                "risk_category": "II",
                "building_weight_kn": self._find_number(text, [r"([0-9.]+)\s*kn"], 5000.0),
                "height_m": self._find_number(text, [r"([0-9.]+)\s*m"], 8.0),
                "structural_system": "moment_frame",
            }
        label = "wind" if load_type == "wind" else "seismic"
        return CanvasToolDecision(
            action="apply_story_forces",
            arguments=arguments,
            message=f"I applied {label} story forces to the model and ran the 3D analysis.",
            confidence=0.85,
        )

    # ------------------------------------------------------------------
    # Utility: number extraction from text
    # ------------------------------------------------------------------

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
