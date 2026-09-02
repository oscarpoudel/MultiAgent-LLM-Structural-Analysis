"""P-delta second-order effects (deterministic).

Two complementary, code-based approaches are provided:

1. **Stability-coefficient amplification** (ASCE 7-22, Section 12.8.7.3):
   the second-order story drift is approximated from the first-order drift by
   the amplification factor ``1 / (1 - theta)`` where ``theta = V*h / W`` is the
   stability coefficient (first-order base shear V, story height h, total
   gravity load W). This is the standard, closed-form estimate used in code.

2. **P-delta equivalent lateral forces**: the overturning moment produced by
   gravity load acting through the first-order drift is converted to an
   equivalent lateral force at each story, which can be applied to the model
   and re-analyzed for an iterative second-order solution.

All values are computed deterministically. No LLM involvement.
"""
from __future__ import annotations

from app.models import Load3D, Structure3DInputs

# Upper bound on the stability coefficient for the closed-form amplification.
# Beyond this the 1/(1-theta) factor becomes unphysical (theta -> 1 is the
# buckling limit); results are flagged and the factor is capped.
THETA_LIMIT = 0.90


def stability_coefficient(base_shear_kn: float, height_m: float, gravity_load_kn: float) -> float:
    """ASCE 7 stability coefficient theta = V*h / W."""
    if gravity_load_kn <= 0.0:
        return 0.0
    return (base_shear_kn * height_m) / gravity_load_kn


def amplification_factor(theta: float) -> float:
    """Second-order amplification factor 1/(1-theta), capped at theta_limit."""
    if theta >= 1.0:
        return float("inf")
    theta_eff = min(theta, THETA_LIMIT)
    return 1.0 / (1.0 - theta_eff)


def amplify_story_drifts(
    story_drifts: list[dict],
    base_shear_kn: float,
    height_m: float,
    gravity_load_kn: float,
) -> dict:
    """Amplify first-order story drifts using the ASCE 7 stability coefficient.

    Args:
        story_drifts: First-order drifts, each ``{"drift_mm": float, ...}``.
        base_shear_kn: First-order base shear V (kN).
        height_m: Total building height h (m).
        gravity_load_kn: Total gravity load W (kN).

    Returns:
        dict with theta, amplification factor, stability flag, and per-story
        first-order / second-order drifts.
    """
    theta = stability_coefficient(base_shear_kn, height_m, gravity_load_kn)
    amp = amplification_factor(theta)
    stable = theta < 1.0
    warnings: list[str] = []
    if not stable:
        warnings.append(
            f"Stability coefficient theta = {theta:.3f} >= 1.0; the structure is at or beyond "
            "its elastic buckling limit. Second-order results are not meaningful."
        )
    elif theta > THETA_LIMIT:
        warnings.append(
            f"Stability coefficient theta = {theta:.3f} exceeds {THETA_LIMIT}; the amplification "
            f"factor was capped at {amplification_factor(THETA_LIMIT):.2f}. Use an iterative "
            "second-order (P-delta) analysis for accuracy."
        )

    amplified = []
    for d in story_drifts:
        drift1 = float(d.get("drift_mm", 0.0))
        drift2 = drift1 * amp if stable else float("inf")
        amplified.append({
            "from_m": d.get("from_m"),
            "to_m": d.get("to_m"),
            "height_m": d.get("height_m"),
            "drift1_mm": round(drift1, 3),
            "drift2_mm": round(drift2, 3) if stable else None,
            "amplification": round(amp, 4) if stable else None,
        })

    return {
        "method": "ASCE 7-22 stability coefficient (theta = V*h/W)",
        "code_reference": "ASCE 7-22 Section 12.8.7.3",
        "theta": round(theta, 4),
        "amplification_factor": round(amp, 4) if stable else None,
        "stable": stable,
        "story_drifts": amplified,
        "max_drift1_mm": round(max((d.get("drift_mm", 0.0) for d in story_drifts), default=0.0), 3),
        "max_drift2_mm": round(max((a["drift2_mm"] for a in amplified if a["drift2_mm"] is not None), default=0.0), 3) if stable else None,
        "warnings": warnings,
    }


def pdelta_equivalent_lateral_forces(
    inputs: Structure3DInputs,
    story_drifts: list[dict],
    gravity_load_kn: float,
    *,
    direction: str = "x",
    case: str = "PD",
) -> dict:
    """Compute P-delta equivalent lateral forces from first-order drifts.

    For each story the overturning moment ``M = W_above * drift`` is converted
    to an equivalent lateral force ``F = M / h_story`` and distributed equally
    to the nodes at that story level.

    Args:
        inputs: The drawn 3D structure.
        story_drifts: First-order drifts, each ``{"from_m", "to_m", "drift_mm"}``.
        gravity_load_kn: Total gravity load W (kN).
        direction: Lateral direction, "x" or "y".
        case: Load case name for the new nodal loads.

    Returns:
        dict with the augmented inputs, per-story force summary, and warnings.
    """
    if direction not in ("x", "y"):
        raise ValueError("direction must be 'x' or 'y'")

    augmented = inputs.model_copy(deep=True)
    warnings: list[str] = []
    if not story_drifts or not inputs.nodes or gravity_load_kn <= 0.0:
        return {"inputs": augmented, "applied": [], "warnings": warnings}

    elevations = sorted({round(node.z, 9) for node in inputs.nodes})
    nodes_by_elevation: dict[float, list] = {}
    for node in inputs.nodes:
        nodes_by_elevation.setdefault(round(node.z, 9), []).append(node)

    # Gravity load per level (assume evenly distributed over the levels).
    gravity_per_level = gravity_load_kn / len(elevations)

    new_loads: list[Load3D] = []
    applied: list[dict] = []

    for drift in story_drifts:
        to_m = float(drift.get("to_m", 0.0))
        from_m = float(drift.get("from_m", 0.0))
        drift_mm = float(drift.get("drift_mm", 0.0))
        h_story = to_m - from_m
        if h_story <= 0.0 or drift_mm == 0.0:
            continue

        # Gravity load above the story (levels at or above the story top).
        levels_above = [e for e in elevations if e >= to_m - 1e-6]
        w_above = gravity_per_level * len(levels_above)
        if w_above <= 0.0:
            continue

        # Overturning moment (kN-m) and equivalent lateral force (kN).
        drift_m = drift_mm / 1000.0
        moment_kn_m = w_above * drift_m
        force_kn = moment_kn_m / h_story

        # Assign to the nodes at the story top elevation.
        target_elevation = min(elevations, key=lambda e: abs(e - to_m))
        level_nodes = nodes_by_elevation[target_elevation]
        share = force_kn / len(level_nodes)
        for node in level_nodes:
            if direction == "x":
                new_loads.append(Load3D(node_id=node.id, case=case, fx_kn=share))
            else:
                new_loads.append(Load3D(node_id=node.id, case=case, fy_kn=share))

        applied.append({
            "to_m": to_m,
            "drift_mm": drift_mm,
            "w_above_kn": round(w_above, 2),
            "moment_kn_m": round(moment_kn_m, 3),
            "force_kn": round(force_kn, 3),
            "num_nodes": len(level_nodes),
            "force_per_node_kn": round(share, 4),
        })

    augmented.nodal_loads.extend(new_loads)
    return {"inputs": augmented, "applied": applied, "warnings": warnings}
