from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from app.llm import OllamaClient
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


@dataclass(frozen=True)
class ManagedAgent:
    name: str
    instructions: str
    fallback: dict[str, Any]


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


# ---------------------------------------------------------------------------
# Detect analysis type from user prompt
# ---------------------------------------------------------------------------

_TRUSS_KEYWORDS = ["truss", "truss analysis", "truss structure", "bar element", "axial only"]
_FRAME_KEYWORDS = ["frame", "portal frame", "portal", "multi-story", "rigid frame", "moment frame"]
_COLUMN_KEYWORDS = ["column", "buckling", "euler", "slenderness", "compression member", "axial capacity"]
_BEAM_KEYWORDS = ["beam", "span", "udl", "uniform load", "point load", "deflection", "moment", "shear"]
_3D_KEYWORDS = ["3d", "three-dimensional", "space frame", "space truss"]

_CANTILEVER_KEYWORDS = ["cantilever", "cantilevered", "fixed-free", "fixed free"]
_FIXED_FIXED_KEYWORDS = ["fixed-fixed", "fixed fixed", "both ends fixed", "encastre"]
_PROPPED_KEYWORDS = ["propped cantilever", "propped", "fixed-pinned", "fixed pinned"]


def detect_analysis_type(text: str) -> str:
    """Detect the type of structural analysis requested."""
    lower = text.lower()
    if any(kw in lower for kw in _3D_KEYWORDS):
        return "3d_frame"
    if any(kw in lower for kw in _TRUSS_KEYWORDS):
        return "truss"
    if any(kw in lower for kw in _FRAME_KEYWORDS):
        return "frame"
    if any(kw in lower for kw in _COLUMN_KEYWORDS):
        return "column"
    return "beam"


def detect_support_type(text: str) -> str:
    """Detect beam support conditions from text."""
    lower = text.lower()
    if any(kw in lower for kw in _CANTILEVER_KEYWORDS):
        return "cantilever"
    if any(kw in lower for kw in _FIXED_FIXED_KEYWORDS):
        return "fixed_fixed"
    if any(kw in lower for kw in _PROPPED_KEYWORDS):
        return "propped_cantilever"
    return "simply_supported"


class StructuralAgentSystem:
    def __init__(self, llm: OllamaClient, agent_timeout_s: float = 3.0) -> None:
        self.llm = llm
        self.agent_timeout_s = agent_timeout_s
        self.managed_agents = {
            "conversation": ManagedAgent(
                name="Structural Conversation Agent",
                instructions=(
                    "You are a structural analysis expert assistant. Reply conversationally and briefly. "
                    "When greeted, introduce yourself as a structural analysis expert. Mention that you can help "
                    "with beam analysis (simply supported, cantilever, fixed-fixed, propped cantilever), "
                    "2D truss analysis, 2D frame analysis, column buckling checks, AISC section lookups, "
                    "and 3D space frames. "
                    "You support point loads, UDL, and combined loading. Do not claim licensed approval."
                ),
                fallback={
                    "summary": (
                        "Hi, I am your structural analysis assistant. I can help with:\n"
                        "- Beam analysis (simply supported, cantilever, fixed-fixed, propped cantilever)\n"
                        "- Point loads, uniform loads, and combined loading\n"
                        "- 2D truss analysis (axial forces, displacements, reactions)\n"
                        "- 2D frame analysis (portal frames, multi-story frames)\n"
                        "- Column buckling checks (Euler + AISC Chapter E)\n"
                        "- AISC steel section property lookups\n"
                        "- 3D Structural Analysis\n"
                        "- SFD, BMD, and deflection diagrams\n"
                        "All results include engineering reports with assumptions and warnings."
                    )
                },
            ),
            "intent": ManagedAgent(
                name="Structural Intent Agent",
                instructions="You extract structural engineering intent. Return compact JSON only.",
                fallback={
                    "summary": "Detected a preliminary beam analysis request.",
                    "structure_type": "beam",
                    "analysis_type": "static_elastic",
                    "boundary_conditions": "simply_supported",
                },
            ),
            "planning": ManagedAgent(
                name="Analysis Planning Agent",
                instructions="You plan structural analysis tool execution. Return compact JSON only.",
                fallback={
                    "summary": "Use the OpenSeesPy simply_supported_udl_beam solver when inertia is available.",
                    "solver": "openseespy_beam",
                    "required_inputs": ["span_m", "udl_kn_per_m", "elastic_modulus_gpa", "inertia_m4"],
                },
            ),
            "canvas_router": ManagedAgent(
                name="Canvas Tool Router Agent",
                instructions=(
                    "You route user chat to canvas tools. Return compact JSON only with keys: "
                    "action, arguments, message, confidence. Available actions: none, clear_canvas, "
                    "clear_analysis, draw_simple_beam, draw_3d_frame_template, apply_member_group_sections, "
                    "set_rigid_diaphragm, set_load_combination. Use none for ordinary conversation or conceptual questions. "
                    "Use clear_canvas only when the user wants the drawing/canvas/model cleared or reset. "
                    "Use clear_analysis when the user wants only analysis results cleared. "
                    "Use draw_simple_beam when the user asks to draw/create a simply supported beam. "
                    "Use draw_3d_frame_template when the user asks to create/model a 3D, 3-story, or 3x3 frame. "
                    "Use apply_member_group_sections when the user asks to assign/apply beam and column sections. "
                    "Use set_rigid_diaphragm with {enabled: true/false} when the user asks to toggle rigid diaphragms. "
                    "Use set_load_combination with {name: string} when the user asks to change load combination. "
                    "For draw_simple_beam arguments use: span_m number, udl_kn_per_m number if present, "
                    "point_loads array of {magnitude_kn, position_m}. Convert midpoint/middle to span_m/2."
                ),
                fallback={"action": "none", "arguments": {}, "message": "", "confidence": 0.0},
            ),
        }

    def chat(self, message: str) -> ConversationResult:
        agent = self.managed_agents["conversation"]
        task = (
            "User message:\n"
            f"{message}\n\n"
            "Respond as the assistant. Keep it useful, direct, and no more than 4 sentences."
        )
        try:
            response = self._generate_with_timeout(agent.instructions, task).strip()
            return ConversationResult(message=response or agent.fallback["summary"], source="llm")
        except Exception:
            return ConversationResult(message=agent.fallback["summary"], source="fallback")

    def chat_with_context(self, message: str, context: dict[str, Any]) -> ConversationResult:
        agent = self.managed_agents["conversation"]
        context_summary = self._summarize_canvas_context(context)
        fallback_message = self._contextual_fallback_answer(message, context_summary)
        task = (
            "You are helping with the user's current structural model and analysis results.\n\n"
            f"Current context:\n{context_summary}\n\n"
            f"User question: {message}\n\n"
            "Answer using only the current context when referring to model/results. Be specific with numbers. "
            "If the user asks for a modeling action, briefly state what action they can ask you to perform. "
            "Keep the answer concise and practical."
        )
        try:
            response = self._generate_with_timeout(agent.instructions, task).strip()
            return ConversationResult(message=response or fallback_message, source="llm")
        except Exception:
            return ConversationResult(message=fallback_message, source="fallback")

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
            floor_count = len(z_levels)
            lines.append(f"Building: {floor_count} floor levels at z = {', '.join(f'{z:.2f}' for z in z_levels)} m")
            xs = [n.get("x", 0) for n in nodes]
            ys = [n.get("y", 0) for n in nodes]
            if xs and ys:
                lines.append(f"Dimensions: x-range [{min(xs):.2f}, {max(xs):.2f}] m, y-range [{min(ys):.2f}, {max(ys):.2f}] m")
            if members:
                groups = {}
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
            "I can use the current model context to answer questions about geometry, loads, analysis results, "
            "story drift, base reactions, and member forces. I can also help modify the canvas by drawing a 3D frame template, "
            "applying beam/column sections, clearing analysis, changing load combinations, or toggling rigid diaphragms."
        )

    def evaluate_results(
        self, message: str, results: dict[str, Any], analysis_type: str, original_prompt: str
    ) -> ConversationResult:
        """Evaluate or explain analysis results with engineering context."""
        agent = self.managed_agents["conversation"]
        results_summary = self._summarize_results(results, analysis_type)
        task = (
            f"You are reviewing structural analysis results.\n\n"
            f"Original request: {original_prompt}\n"
            f"Analysis type: {analysis_type}\n\n"
            f"Results summary:\n{results_summary}\n\n"
            f"User question: {message}\n\n"
            "Answer the user's question based on the results. Be specific with numbers from the results. "
            "If asking whether results are good, evaluate against typical engineering criteria: "
            "- Deflection limits (L/360 for live load, L/240 for total load)\n"
            "- Utilization ratios (axial, bending, shear)\n"
            "- Stability and serviceability\n"
            "- Code compliance indicators\n"
            "Use bullet points for clarity. Keep it under 8 sentences. "
            "If the question is about code compliance, reference AISC/ASCE/IBC where relevant. "
            "Always note this is preliminary and not a substitute for licensed engineering review."
        )
        try:
            response = self._generate_with_timeout(agent.instructions, task).strip()
            return ConversationResult(
                message=response or "Unable to evaluate results at this time.",
                source="llm"
            )
        except Exception:
            return ConversationResult(
                message=f"Results summary for {analysis_type}:\n{results_summary}\n\n"
                "I cannot provide a detailed evaluation without the LLM. Check the numbers against your design criteria.",
                source="fallback"
            )

    def _summarize_results(self, results: dict[str, Any], analysis_type: str) -> str:
        """Create a concise text summary of results for the LLM."""
        lines = []
        solver = results.get("solver", "unknown")
        lines.append(f"Solver: {solver}")
        is_finite = results.get("is_finite", True)
        lines.append(f"All results finite: {is_finite}")

        if analysis_type == "beam":
            lines.append(f"Span: {results.get('span_m', 'N/A')} m")
            lines.append(f"Max moment: {results.get('max_moment_kn_m', 'N/A')} kN-m")
            lines.append(f"Max shear: {results.get('max_shear_kn', 'N/A')} kN")
            lines.append(f"Max deflection: {results.get('max_deflection_mm', 'N/A')} mm")
            lines.append(f"Deflection OK: {results.get('deflection_ok', 'N/A')}")
            lines.append(f"Stress OK: {results.get('stress_ok', 'N/A')}")
            lines.append(f"Utilization: {results.get('utilization_ratio', 'N/A')}")
        elif analysis_type == "3d_frame":
            lines.append(f"Load combination: {results.get('load_combination', 'N/A')}")
            lines.append(f"Rigid diaphragms: {results.get('rigid_diaphragms', 'N/A')}")
            lines.append(f"Max translation: {results.get('max_translation_mm', 'N/A')} mm")
            base = results.get("base_reactions", {})
            if base:
                lines.append(
                    f"Base reactions: Fx={base.get('Fx_kn', 'N/A')} kN, Fy={base.get('Fy_kn', 'N/A')} kN, "
                    f"Fz={base.get('Fz_kn', 'N/A')} kN"
                )
            story = results.get("story_response", {})
            drifts = story.get("story_drifts", []) if isinstance(story, dict) else []
            if drifts:
                drift_values = [
                    float(d.get("drift_mm"))
                    for d in drifts
                    if isinstance(d, dict) and isinstance(d.get("drift_mm"), (int, float))
                ]
                if drift_values:
                    lines.append(f"Maximum story drift: {max(drift_values)} mm")
            summary = results.get("member_force_summary", {})
            lines.append(f"Member force envelopes: {len(summary)} members")
        elif analysis_type == "frame":
            lines.append(f"Max displacement: {results.get('max_displacement_mm', 'N/A')} mm")
            nd = results.get("node_displacements", {})
            lines.append(f"Node displacements: {len(nd)} nodes")
            reactions = results.get("reactions", {})
            lines.append(f"Reactions: {len(reactions)} supports")
            mf = results.get("member_forces", {})
            lines.append(f"Member forces: {len(mf)} members")
            for mid, forces in mf.items():
                lines.append(
                    f"  Member {mid}: P={forces.get('axial_start_kn', 'N/A')} kN, "
                    f"V={forces.get('shear_start_kn', 'N/A')} kN, "
                    f"M={forces.get('moment_start_kn_m', 'N/A')} kN-m"
                )
        elif analysis_type == "truss":
            mf = results.get("member_forces", {})
            lines.append(f"Member forces: {len(mf)} members")
            for mid, forces in mf.items():
                lines.append(
                    f"  Member {mid}: {forces.get('axial_kn', 'N/A')} kN "
                    f"({forces.get('tension_or_compression', 'N/A')})"
                )
            reactions = results.get("reactions", {})
            lines.append(f"Reactions: {len(reactions)} supports")
        elif analysis_type == "column":
            lines.append(f"Slenderness ratio: {results.get('slenderness_ratio', 'N/A')}")
            lines.append(f"Pn (design capacity): {results.get('design_capacity_kn', 'N/A')} kN")
            lines.append(f"Applied load: {results.get('axial_load_kn', 'N/A')} kN")
            lines.append(f"Utilization: {results.get('utilization_ratio', 'N/A')}")
            lines.append(f"OK: {results.get('ok', 'N/A')}")

        return "\n".join(lines)

    def route_canvas_tool(self, message: str, context: dict[str, Any] | None = None) -> tuple[CanvasToolDecision, str]:
        agent = self.managed_agents["canvas_router"]
        fallback = self._fallback_canvas_tool_decision(message)
        task = (
            f"User message:\n{message}\n\n"
            f"Current context summary:\n{self._summarize_canvas_context(context or {})}\n\n"
            "Return JSON for the best canvas tool decision. Do not include markdown."
        )
        try:
            raw = self._generate_with_timeout(agent.instructions, task)
            match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
            if not match:
                return fallback, "fallback"
            decision = CanvasToolDecision.model_validate(json.loads(match.group(0)))
            if decision.action not in {
                "none", "clear_canvas", "clear_analysis", "draw_simple_beam", "draw_3d_frame_template",
                "apply_member_group_sections", "set_rigid_diaphragm", "set_load_combination",
            }:
                return fallback, "fallback"
            if decision.action == "set_rigid_diaphragm" and not isinstance(decision.arguments.get("enabled"), bool):
                return fallback, "fallback"
            if decision.action == "set_load_combination" and not str(decision.arguments.get("name") or "").strip():
                return fallback, "fallback"
            return decision, "llm"
        except Exception:
            return fallback, "fallback"

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
            return CanvasToolDecision(
                action="clear_canvas",
                message="I cleared the drawing canvas.",
                confidence=0.9,
            )

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

    def analyze(self, prompt: str) -> AgentResult:
        log.info("agent_analyze_start", extra={"prompt_len": len(prompt)})
        traces: list[AgentTrace] = []
        assumptions = [
            "Preliminary elastic analysis only.",
            "Units are interpreted from the prompt where possible.",
            "Agent planning uses deterministic fallbacks by default; live LLM routing can be enabled in settings.",
        ]
        warnings = [
            "Not a substitute for licensed engineering review or full code compliance.",
        ]

        # Detect analysis type
        analysis_type = detect_analysis_type(prompt)

        intent = self._intent_agent(prompt)
        traces.append(AgentTrace(agent="Structural Intent Agent", summary=intent["summary"], data=intent))

        plan = self._planning_agent(prompt, intent)
        traces.append(AgentTrace(agent="Analysis Planning Agent", summary=plan["summary"], data=plan))

        if analysis_type == "3d_frame":
            return self._run_3d_analysis(prompt, traces, assumptions, warnings)
        elif analysis_type == "truss":
            return self._run_truss_analysis(prompt, traces, assumptions, warnings)
        elif analysis_type == "frame":
            return self._run_frame_analysis(prompt, traces, assumptions, warnings)
        elif analysis_type == "column":
            return self._run_column_analysis(prompt, traces, assumptions, warnings)
        else:
            return self._run_beam_analysis(prompt, plan, traces, assumptions, warnings)

    # ------------------------------------------------------------------
    # 3D Frame analysis pipeline
    # ------------------------------------------------------------------

    def _run_3d_analysis(
        self, prompt: str, traces: list, assumptions: list, warnings: list
    ) -> AgentResult:
        structure_inputs = self._extract_3d_inputs(prompt)
        assumptions.append("Rigid connections assumed for 3D frame elements.")
        assumptions.append("Linear elastic material behavior in 3D space.")

        traces.append(AgentTrace(
            agent="Solver Tool Agent",
            summary=f"Running 3D frame analysis with {len(structure_inputs.nodes)} nodes and {len(structure_inputs.members)} members.",
            data=structure_inputs.model_dump(),
        ))

        results = analyze_3d_structure_opensees(structure_inputs)

        # Critic
        frame_warnings = []
        if not results.get("is_finite"):
            frame_warnings.append("One or more results are not finite. Check 3D model stability (e.g., torsional releases or constraints).")
        warnings.extend(frame_warnings)
        traces.append(AgentTrace(
            agent="Results Critic Agent",
            summary="Checked 3D frame result sanity.",
            data={"warnings": frame_warnings},
        ))

        report = format_engineering_report(prompt, assumptions, warnings, results, analysis_type="3d_frame")
        traces.append(AgentTrace(agent="Report Agent", summary="Generated 3D analysis report.", data={}))

        return AgentResult("3d_frame", assumptions, warnings, traces, results, report)

    # ------------------------------------------------------------------
    # Beam analysis pipeline
    # ------------------------------------------------------------------

    def _run_beam_analysis(
        self, prompt: str, plan: dict, traces: list, assumptions: list, warnings: list
    ) -> AgentResult:
        beam_inputs = self._extract_beam_inputs(prompt, plan)
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

        # Extract diagram data before removing from results
        diagrams = results.pop("_diagrams", None)

        critic = self._critic_agent(results)
        warnings.extend(critic["warnings"])
        traces.append(AgentTrace(agent="Results Critic Agent", summary=critic["summary"], data=critic))

        if beam_inputs.inertia_m4 is None:
            warnings.append("Moment and shear were computed, but deflection needs a valid moment of inertia.")
        if beam_inputs.section_modulus_m3 is None:
            warnings.append("Bending stress was not computed because section modulus was not provided.")

        report = format_engineering_report(prompt, assumptions, warnings, results, analysis_type="beam")
        traces.append(AgentTrace(agent="Report Agent", summary="Generated preliminary engineering report.", data={}))

        result = AgentResult("beam", assumptions, warnings, traces, results, report)
        result._diagrams = diagrams
        return result

    # ------------------------------------------------------------------
    # Truss analysis pipeline
    # ------------------------------------------------------------------

    def _run_truss_analysis(
        self, prompt: str, traces: list, assumptions: list, warnings: list
    ) -> AgentResult:
        truss_inputs = self._extract_truss_inputs(prompt)
        assumptions.append("All joints are assumed pin-connected (truss assumption).")
        assumptions.append("Members carry axial forces only.")

        traces.append(AgentTrace(
            agent="Solver Tool Agent",
            summary=f"Running 2D truss analysis with {len(truss_inputs.nodes)} nodes and {len(truss_inputs.members)} members.",
            data=truss_inputs.model_dump(),
        ))

        results = analyze_truss(truss_inputs)

        # Critic
        truss_warnings = []
        if not results.get("is_finite"):
            truss_warnings.append("One or more results are not finite. Check model stability.")
        member_forces = results.get("member_forces", {})
        for mid, mf in member_forces.items():
            if mf.get("tension_or_compression") == "compression":
                truss_warnings.append(f"Member {mid} is in compression ({mf.get('axial_kn')} kN). Check buckling capacity.")
        warnings.extend(truss_warnings)
        traces.append(AgentTrace(
            agent="Results Critic Agent",
            summary="Checked truss result sanity and compression member warnings.",
            data={"warnings": truss_warnings},
        ))

        report = format_engineering_report(prompt, assumptions, warnings, results, analysis_type="truss")
        traces.append(AgentTrace(agent="Report Agent", summary="Generated truss analysis report.", data={}))

        return AgentResult("truss", assumptions, warnings, traces, results, report)

    # ------------------------------------------------------------------
    # Frame analysis pipeline
    # ------------------------------------------------------------------

    def _run_frame_analysis(
        self, prompt: str, traces: list, assumptions: list, warnings: list
    ) -> AgentResult:
        frame_inputs = self._extract_frame_inputs(prompt)
        assumptions.append("Rigid connections assumed at all beam-column joints.")
        assumptions.append("Linear elastic material behavior.")

        traces.append(AgentTrace(
            agent="Solver Tool Agent",
            summary=f"Running 2D frame analysis with {len(frame_inputs.nodes)} nodes and {len(frame_inputs.members)} members.",
            data=frame_inputs.model_dump(),
        ))

        results = analyze_frame(frame_inputs)

        # Critic
        frame_warnings = []
        if not results.get("is_finite"):
            frame_warnings.append("One or more results are not finite. Check model stability.")
        if results.get("max_displacement_mm", 0) > 50:
            frame_warnings.append(f"Maximum displacement ({results.get('max_displacement_mm')} mm) is large. Check serviceability.")
        warnings.extend(frame_warnings)
        traces.append(AgentTrace(
            agent="Results Critic Agent",
            summary="Checked frame result sanity and serviceability.",
            data={"warnings": frame_warnings},
        ))

        report = format_engineering_report(prompt, assumptions, warnings, results, analysis_type="frame")
        traces.append(AgentTrace(agent="Report Agent", summary="Generated frame analysis report.", data={}))

        return AgentResult("frame", assumptions, warnings, traces, results, report)

    # ------------------------------------------------------------------
    # Column analysis pipeline
    # ------------------------------------------------------------------

    def _run_column_analysis(
        self, prompt: str, traces: list, assumptions: list, warnings: list
    ) -> AgentResult:
        col_inputs = self._extract_column_inputs(prompt)
        assumptions.append("Column is prismatic (constant cross-section).")
        assumptions.append("Analysis per AISC Chapter E (compression members).")

        traces.append(AgentTrace(
            agent="Solver Tool Agent",
            summary=f"Running column buckling analysis ({col_inputs.end_condition}).",
            data=col_inputs.model_dump(),
        ))

        results = analyze_column(col_inputs)

        # Column solver includes its own warnings
        col_warnings = results.pop("warnings", [])
        warnings.extend(col_warnings)
        traces.append(AgentTrace(
            agent="Results Critic Agent",
            summary="Checked column capacity and slenderness.",
            data={"warnings": col_warnings},
        ))

        report = format_engineering_report(prompt, assumptions, warnings, results, analysis_type="column")
        traces.append(AgentTrace(agent="Report Agent", summary="Generated column analysis report.", data={}))

        return AgentResult("column", assumptions, warnings, traces, results, report)

    # ------------------------------------------------------------------
    # Intent and Planning agents
    # ------------------------------------------------------------------

    def _intent_agent(self, prompt: str) -> dict[str, Any]:
        agent = self.managed_agents["intent"]
        analysis_type = detect_analysis_type(prompt)

        # Update fallback based on detected type
        fallback = {
            "summary": f"Detected a preliminary {analysis_type} analysis request.",
            "structure_type": analysis_type,
            "analysis_type": "static_elastic",
            "boundary_conditions": detect_support_type(prompt) if analysis_type == "beam" else "N/A",
        }

        task = (
            "Identify structure type, analysis type, material, loads, boundary conditions, "
            f"and missing data from this request:\n{prompt}"
        )
        try:
            raw = self._generate_with_timeout(agent.instructions, task)
            match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
            if not match:
                return fallback
            data = json.loads(match.group(0))
            if "summary" not in data:
                data["summary"] = fallback["summary"]
            return data
        except Exception:
            return fallback

    def _planning_agent(self, prompt: str, intent: dict[str, Any]) -> dict[str, Any]:
        agent = self.managed_agents["planning"]
        analysis_type = detect_analysis_type(prompt)

        solver_map = {
            "beam": "openseespy_beam",
            "truss": "openseespy_truss",
            "frame": "openseespy_frame",
            "3d_frame": "openseespy_3d_frame",
            "column": "column_euler_aisc",
        }

        fallback = {
            "summary": f"Use the {solver_map.get(analysis_type, 'openseespy_beam')} solver.",
            "solver": solver_map.get(analysis_type, "openseespy_beam"),
        }

        task = (
            "Choose a solver and required structured inputs. "
            f"Available solvers: beam, truss, frame, 3d_frame, column. "
            f"Intent JSON: {json.dumps(intent)}\nUser request: {prompt}"
        )
        try:
            raw = self._generate_with_timeout(agent.instructions, task)
            match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
            if not match:
                return fallback
            data = json.loads(match.group(0))
            if "summary" not in data:
                data["summary"] = fallback["summary"]
            return data
        except Exception:
            return fallback

    def _json_agent(self, agent: ManagedAgent, task: str) -> dict[str, Any]:
        try:
            raw = self._generate_with_timeout(agent.instructions, task)
            match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
            if not match:
                return agent.fallback
            data = json.loads(match.group(0))
            if "summary" not in data:
                data["summary"] = agent.fallback["summary"]
            return data
        except Exception:
            return agent.fallback

    def _generate_with_timeout(self, system: str, task: str) -> str:
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(self.llm.generate, system=system, prompt=task)
        try:
            result = future.result(timeout=self.agent_timeout_s)
            return result
        except TimeoutError as error:
            log.warning("llm_timeout", extra={"timeout_s": self.agent_timeout_s})
            future.cancel()
            executor.shutdown(wait=False, cancel_futures=True)
            raise RuntimeError("Agent LLM call timed out") from error
        except Exception as error:
            log.warning("llm_error", extra={"error": str(error)})
            raise
        finally:
            if future.done():
                executor.shutdown(wait=False, cancel_futures=True)

    # ------------------------------------------------------------------
    # Input extraction: 3D Frame
    # ------------------------------------------------------------------

    def _extract_3d_inputs(self, prompt: str) -> Structure3DInputs:
        """Extract 3D structure inputs or use a default simple 3D frame."""
        json_match = re.search(r"\{.*\}", prompt, flags=re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(0))
                return Structure3DInputs.model_validate(data)
            except (json.JSONDecodeError, ValidationError):
                pass

        # Default simple 3D cantilever column if couldn't parse
        nodes = [
            Node3D(id=1, x=0.0, y=0.0, z=0.0, support=Support3D(ux=True, uy=True, uz=True, rx=True, ry=True, rz=True)),
            Node3D(id=2, x=0.0, y=5.0, z=0.0, support=None)
        ]
        members = [
            Member3D(id=1, start_node=1, end_node=2)
        ]
        nodal_loads = [
            Load3D(node_id=2, fx_kn=10.0, fy_kn=-50.0, fz_kn=5.0)
        ]

        return Structure3DInputs(nodes=nodes, members=members, nodal_loads=nodal_loads)

    # ------------------------------------------------------------------
    # Input extraction: Beam
    # ------------------------------------------------------------------

    def _extract_beam_inputs(self, prompt: str, plan: dict[str, Any]) -> BeamInputs:
        del plan
        normalized = prompt.lower().replace(",", " ")
        support_type = detect_support_type(prompt)

        # Extract point loads: "point load 50 kN at 3 m" or "50 kN at 3m"
        point_loads = []
        pl_patterns = [
            r"point load[s]?\s+(?:of\s+)?([0-9.]+)\s*kn\s+at\s+([0-9.]+)\s*m",
            r"([0-9.]+)\s*kn\s+(?:point load\s+)?at\s+([0-9.]+)\s*m",
            r"concentrated load[s]?\s+(?:of\s+)?([0-9.]+)\s*kn\s+at\s+([0-9.]+)\s*m",
        ]
        for pattern in pl_patterns:
            for match in re.finditer(pattern, normalized):
                try:
                    mag = float(match.group(1))
                    pos = float(match.group(2))
                    point_loads.append(PointLoad(magnitude_kn=mag, position_m=pos))
                except (ValueError, IndexError):
                    pass

        values = {
            "span_m": self._find_number(normalized, [r"span(?: is)? ([0-9.]+)\s*m", r"([0-9.]+)\s*m span", r"([0-9.]+)\s*m\s+(?:long|length)"], 6.0),
            "udl_kn_per_m": self._find_number(
                normalized,
                [r"(?:udl|uniform load|distributed load|load)(?: is)? ([0-9.]+)\s*kn/?m", r"([0-9.]+)\s*kn/?m"],
                10.0 if not point_loads else 0.0,
            ),
            "elastic_modulus_gpa": self._find_number(
                normalized,
                [r"(?:e|elastic modulus)(?: is)? ([0-9.]+)\s*gpa", r"([0-9.]+)\s*gpa"],
                200.0,
            ),
            "inertia_m4": self._find_optional_number(normalized, [r"(?:i|inertia)(?: is)? ([0-9.eE+-]+)\s*m4"]),
            "area_m2": self._find_number(
                normalized,
                [r"(?:a|area)(?: is)? ([0-9.eE+-]+)\s*m2", r"([0-9.eE+-]+)\s*m2 area"],
                1.0,
            ),
            "section_modulus_m3": self._find_optional_number(
                normalized,
                [r"(?:s|section modulus)(?: is)? ([0-9.eE+-]+)\s*m3"],
            ),
            "deflection_limit_ratio": self._find_number(normalized, [r"l/([0-9.]+)"], 360.0),
            "point_loads": point_loads,
            "support_type": support_type,
        }
        try:
            return BeamInputs(**values)
        except ValidationError:
            return BeamInputs(span_m=6.0, udl_kn_per_m=10.0, elastic_modulus_gpa=200.0, support_type=support_type)

    # ------------------------------------------------------------------
    # Input extraction: Truss
    # ------------------------------------------------------------------

    def _extract_truss_inputs(self, prompt: str) -> TrussInputs:
        """Extract truss inputs from prompt, or use a default example truss."""
        normalized = prompt.lower().replace(",", " ")

        # Try to parse JSON-like truss definition from the prompt
        json_match = re.search(r"\{.*\}", prompt, flags=re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(0))
                return TrussInputs.model_validate(data)
            except (json.JSONDecodeError, ValidationError):
                pass

        # Default: simple Warren truss
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
        loads = [
            TrussLoad(node_id=4, fy_kn=-load),
        ]

        return TrussInputs(nodes=nodes, members=members, loads=loads)

    # ------------------------------------------------------------------
    # Input extraction: Frame
    # ------------------------------------------------------------------

    def _extract_frame_inputs(self, prompt: str) -> FrameInputs:
        """Extract frame inputs or use a default portal frame."""
        normalized = prompt.lower().replace(",", " ")

        # Try JSON parse
        json_match = re.search(r"\{.*\}", prompt, flags=re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(0))
                return FrameInputs.model_validate(data)
            except (json.JSONDecodeError, ValidationError):
                pass

        # Default: portal frame
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
            FrameMember(id=1, start_node=1, end_node=2),   # left column
            FrameMember(id=2, start_node=2, end_node=3),   # beam
            FrameMember(id=3, start_node=3, end_node=4),   # right column
        ]
        nodal_loads = []
        if lateral_load > 0:
            nodal_loads.append(FrameLoad(node_id=2, fx_kn=lateral_load))
        member_loads = []
        if gravity_load > 0:
            member_loads.append(FrameMemberLoad(member_id=2, udl_kn_per_m=gravity_load))

        return FrameInputs(
            nodes=nodes, members=members,
            nodal_loads=nodal_loads, member_loads=member_loads,
        )

    # ------------------------------------------------------------------
    # Input extraction: Column
    # ------------------------------------------------------------------

    def _extract_column_inputs(self, prompt: str) -> ColumnInputs:
        normalized = prompt.lower().replace(",", " ")

        # Detect end condition
        end_condition = "pinned_pinned"
        if "fixed" in normalized and "free" in normalized:
            end_condition = "fixed_free"
        elif "fixed" in normalized and ("pin" in normalized or "pinned" in normalized):
            end_condition = "fixed_pinned"
        elif normalized.count("fixed") >= 2 or "both ends fixed" in normalized or "fixed-fixed" in normalized:
            end_condition = "fixed_fixed"

        length = self._find_number(
            normalized,
            [r"(?:length|height|column)(?: is)? ([0-9.]+)\s*m", r"([0-9.]+)\s*m\s+(?:long|tall|column|height)"],
            4.0,
        )
        area = self._find_number(
            normalized,
            [r"(?:area|a)(?: is)? ([0-9.eE+-]+)\s*m2", r"([0-9.eE+-]+)\s*m2"],
            0.01,
        )
        inertia = self._find_number(
            normalized,
            [r"(?:inertia|i)(?: is)? ([0-9.eE+-]+)\s*m4", r"([0-9.eE+-]+)\s*m4"],
            1e-4,
        )
        e_mod = self._find_number(
            normalized,
            [r"(?:e|elastic modulus)(?: is)? ([0-9.]+)\s*gpa", r"([0-9.]+)\s*gpa"],
            200.0,
        )
        fy = self._find_number(
            normalized,
            [r"(?:fy|yield)(?: is)? ([0-9.]+)\s*mpa", r"([0-9.]+)\s*mpa"],
            250.0,
        )
        axial = self._find_number(
            normalized,
            [r"(?:axial|load|force|p)(?: is)? ([0-9.]+)\s*kn", r"([0-9.]+)\s*kn"],
            500.0,
        )

        try:
            return ColumnInputs(
                length_m=length,
                area_m2=area,
                inertia_m4=inertia,
                elastic_modulus_gpa=e_mod,
                yield_stress_mpa=fy,
                end_condition=end_condition,
                axial_load_kn=axial,
            )
        except ValidationError:
            return ColumnInputs(
                length_m=4.0, area_m2=0.01, inertia_m4=1e-4,
                elastic_modulus_gpa=200.0, yield_stress_mpa=250.0,
                end_condition="pinned_pinned", axial_load_kn=500.0,
            )

    # ------------------------------------------------------------------
    # Critic agent
    # ------------------------------------------------------------------

    def _critic_agent(self, results: dict[str, Any]) -> dict[str, Any]:
        warnings: list[str] = []
        if not results.get("is_finite"):
            warnings.append("One or more numeric inputs were not finite.")
        if results.get("deflection_ok") is False:
            warnings.append("Deflection exceeds the selected serviceability limit.")
        if results.get("span_m", 0) <= 0:
            warnings.append("Span must be positive.")
        udl = results.get("udl_kn_per_m", 0)
        if udl is not None and udl < 0:
            warnings.append("Uniform load should be entered as a positive gravity load magnitude.")
        return {
            "summary": "Checked basic result sanity, unit-sensitive fields, and deflection status.",
            "warnings": warnings,
        }

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
