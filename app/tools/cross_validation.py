"""Cross-validation suite: compare independent solvers on benchmark models.

Each benchmark model is solved with two or more independent implementations
(closed-form, OpenSeesPy FEM, and direct-stiffness fallback) and the key
results are compared. A benchmark "passes" when every compared quantity
agrees within a relative tolerance. All values are deterministic solver
outputs; nothing here is LLM-generated.

This is a QA/regression tool: it surfaces solver regressions and sign or
unit-convention bugs (e.g. a truss force sign flip) that single-solver tests
miss because they only check one implementation.
"""
from __future__ import annotations

from app.models import (
    BeamInputs,
    FrameInputs,
    FrameLoad,
    FrameMember,
    FrameMemberLoad,
    FrameNode,
    TrussInputs,
    TrussLoad,
    TrussMember,
    TrussNode,
)

# Relative tolerance for solver agreement. Independent linear-elastic solvers
# should agree to well within 1%; 2% leaves headroom for FEM discretization.
REL_TOL = 0.02


def _rel_diff(a: float, b: float) -> float:
    denom = max(abs(a), abs(b), 1e-12)
    return abs(a - b) / denom


def _compare(name: str, values: dict[str, float]) -> dict:
    """Compare a set of solver values; return the max relative difference."""
    items = list(values.items())
    max_diff = 0.0
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            max_diff = max(max_diff, _rel_diff(items[i][1], items[j][1]))
    return {
        "quantity": name,
        "values": {k: round(v, 4) for k, v in values.items()},
        "max_rel_diff": round(max_diff, 6),
        "pass": max_diff <= REL_TOL,
    }


def _beam_benchmarks() -> list[dict]:
    # UDL-only so the closed-form and FEM results are directly comparable
    # (the FEM snaps point loads to the nearest node, which shifts their
    # position slightly and makes point-load cases non-exact).
    from app.tools.beam import analyze_beam
    from app.tools.opensees_beam import analyze_beam_opensees

    checks: list[dict] = []
    for support in ("simply_supported", "cantilever", "fixed_fixed", "propped_cantilever"):
        inputs = BeamInputs(
            span_m=6.0,
            udl_kn_per_m=10.0,
            inertia_m4=2e-4,
            support_type=support,
        )
        closed = analyze_beam(inputs)
        fem = analyze_beam_opensees(inputs)
        checks.append(_compare(f"{support}: max_deflection_mm", {
            "closed_form": closed["max_deflection_mm"] or 0.0,
            "opensees": fem["max_deflection_mm"],
        }))
        checks.append(_compare(f"{support}: left_reaction_kn", {
            "closed_form": closed["left_reaction_kn"],
            "opensees": fem["left_reaction_kn"],
        }))
    return checks


def _truss_benchmarks() -> list[dict]:
    from app.tools.truss import _analyze_truss_direct_stiffness, analyze_truss

    inputs = TrussInputs(
        nodes=[
            TrussNode(id=1, x=0.0, y=0.0, support="pin"),
            TrussNode(id=2, x=3.0, y=0.0, support="free"),
            TrussNode(id=3, x=6.0, y=0.0, support="roller_x"),
            TrussNode(id=4, x=1.5, y=2.0, support="free"),
            TrussNode(id=5, x=4.5, y=2.0, support="free"),
        ],
        members=[
            TrussMember(id=1, start_node=1, end_node=2, area_m2=0.002),
            TrussMember(id=2, start_node=2, end_node=3, area_m2=0.002),
            TrussMember(id=3, start_node=1, end_node=4, area_m2=0.002),
            TrussMember(id=4, start_node=4, end_node=2, area_m2=0.002),
            TrussMember(id=5, start_node=2, end_node=5, area_m2=0.002),
            TrussMember(id=6, start_node=5, end_node=3, area_m2=0.002),
            TrussMember(id=7, start_node=4, end_node=5, area_m2=0.002),
        ],
        loads=[
            TrussLoad(node_id=4, fx_kn=0.0, fy_kn=-30.0),
            TrussLoad(node_id=5, fx_kn=0.0, fy_kn=-30.0),
        ],
    )
    fem = analyze_truss(inputs)
    direct = _analyze_truss_direct_stiffness(inputs)

    checks: list[dict] = []
    checks.append(_compare("truss: max_displacement_mm", {
        "opensees": fem["max_displacement_mm"],
        "direct_stiffness": direct["max_displacement_mm"],
    }))
    # Member axial forces must agree in magnitude AND sign (tension vs compression).
    for mid in sorted(fem["member_forces"], key=int):
        checks.append(_compare(f"truss: member {mid} axial_kn", {
            "opensees": fem["member_forces"][mid]["axial_kn"],
            "direct_stiffness": direct["member_forces"][mid]["axial_kn"],
        }))
    return checks


def _frame_benchmarks() -> list[dict]:
    from app.tools.frame import _analyze_frame_direct_stiffness, analyze_frame

    inputs = FrameInputs(
        nodes=[
            FrameNode(id=1, x=0.0, y=0.0, support="fixed"),
            FrameNode(id=2, x=6.0, y=0.0, support="fixed"),
            FrameNode(id=3, x=0.0, y=4.0, support="free"),
            FrameNode(id=4, x=6.0, y=4.0, support="free"),
        ],
        members=[
            FrameMember(id=1, start_node=1, end_node=3, area_m2=0.01, inertia_m4=1e-4),
            FrameMember(id=2, start_node=2, end_node=4, area_m2=0.01, inertia_m4=1e-4),
            FrameMember(id=3, start_node=3, end_node=4, area_m2=0.01, inertia_m4=1e-4),
        ],
        nodal_loads=[FrameLoad(node_id=4, fx_kn=20.0, fy_kn=-10.0)],
        member_loads=[FrameMemberLoad(member_id=3, udl_kn_per_m=5.0)],
    )
    fem = analyze_frame(inputs)
    direct = _analyze_frame_direct_stiffness(inputs)

    checks: list[dict] = [_compare("frame: max_displacement_mm", {
        "opensees": fem["max_displacement_mm"],
        "direct_stiffness": direct["max_displacement_mm"],
    })]
    for mid in sorted(fem["member_forces"], key=int):
        f = fem["member_forces"][mid]
        d = direct["member_forces"][mid]
        checks.append(_compare(f"frame: member {mid} moment_end_kn_m", {
            "opensees": f["moment_end_kn_m"],
            "direct_stiffness": d["moment_end_kn_m"],
        }))
    return checks


def run_cross_validation() -> dict:
    """Run all benchmark cross-validation checks and summarize agreement."""
    benchmarks: dict[str, list[dict]] = {
        "beam": _beam_benchmarks(),
        "truss": _truss_benchmarks(),
        "frame": _frame_benchmarks(),
    }

    total = 0
    passed = 0
    for checks in benchmarks.values():
        for check in checks:
            total += 1
            if check["pass"]:
                passed += 1

    return {
        "method": "Independent-solver cross-validation on benchmark models",
        "relative_tolerance": REL_TOL,
        "benchmarks": benchmarks,
        "total_checks": total,
        "passed_checks": passed,
        "all_pass": passed == total,
    }
