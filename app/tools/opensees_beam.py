from __future__ import annotations

import math

from app.models import BeamInputs
from app.tools.beam import analyze_beam


def analyze_beam_opensees(inputs: BeamInputs) -> dict:
    """OpenSeesPy beam model supporting multiple support types and load types."""
    if inputs.inertia_m4 is None or inputs.inertia_m4 <= 0:
        result = analyze_beam(inputs)
        result["solver"] = "closed_form_no_inertia"
        return result

    try:
        import openseespy.opensees as ops
    except Exception as error:
        result = analyze_beam(inputs)
        result["solver"] = "closed_form_opensees_import_failed"
        result["solver_warning"] = str(error)
        return result

    span = inputs.span_m
    e_pa = inputs.elastic_modulus_gpa * 1e9
    area = inputs.area_m2
    inertia = inputs.inertia_m4
    support = inputs.support_type

    # Build model with enough nodes for point load positions + midspan
    node_positions = _build_node_positions(span, inputs.point_loads)

    ops.wipe()
    try:
        ops.model("basic", "-ndm", 2, "-ndf", 3)

        # Create nodes
        for i, x in enumerate(node_positions):
            ops.node(i + 1, x, 0.0)

        # Boundary conditions
        n_first = 1
        n_last = len(node_positions)
        if support == "simply_supported":
            ops.fix(n_first, 1, 1, 0)  # pin
            ops.fix(n_last, 0, 1, 0)   # roller
        elif support == "cantilever":
            ops.fix(n_first, 1, 1, 1)  # fixed
            # free end: no constraints
        elif support == "fixed_fixed":
            ops.fix(n_first, 1, 1, 1)
            ops.fix(n_last, 1, 1, 1)
        elif support == "propped_cantilever":
            ops.fix(n_first, 1, 1, 1)  # fixed
            ops.fix(n_last, 0, 1, 0)   # roller

        # Geometric transformation
        ops.geomTransf("Linear", 1)

        # Create elements between consecutive nodes
        for i in range(len(node_positions) - 1):
            ops.element("elasticBeamColumn", i + 1, i + 1, i + 2, area, e_pa, inertia, 1)

        # Loads
        ops.timeSeries("Linear", 1)
        ops.pattern("Plain", 1, 1)

        # UDL on all elements
        if inputs.udl_kn_per_m != 0:
            load_n_per_m = inputs.udl_kn_per_m * 1_000.0
            for i in range(len(node_positions) - 1):
                ops.eleLoad("-ele", i + 1, "-type", "-beamUniform", -load_n_per_m)

        # Point loads as nodal loads
        for pl in inputs.point_loads:
            # Find the node closest to this position
            node_id = _find_nearest_node(node_positions, pl.position_m)
            ops.load(node_id, 0.0, -pl.magnitude_kn * 1_000.0, 0.0)

        # Analysis
        ops.system("BandGeneral")
        ops.numberer("RCM")
        ops.constraints("Plain")
        ops.integrator("LoadControl", 1.0)
        ops.algorithm("Linear")
        ops.analysis("Static")
        status = ops.analyze(1)
        ops.reactions()

        # Extract results
        # Find midspan node
        mid_idx = len(node_positions) // 2
        mid_node = mid_idx + 1
        mid_deflection_mm = ops.nodeDisp(mid_node, 2) * 1_000.0

        # Max deflection across all nodes
        max_defl_mm = 0.0
        for i in range(len(node_positions)):
            d = abs(ops.nodeDisp(i + 1, 2) * 1_000.0)
            if d > max_defl_mm:
                max_defl_mm = d

        # Reactions
        left_reaction_kn = ops.nodeReaction(n_first, 2) / 1_000.0
        right_reaction_kn = 0.0
        if support != "cantilever":
            right_reaction_kn = ops.nodeReaction(n_last, 2) / 1_000.0

        # Extract SFD/BMD from element forces
        positions_diag = []
        shear_diag = []
        moment_diag = []
        deflection_diag = []

        for i in range(len(node_positions)):
            node_id = i + 1
            positions_diag.append(node_positions[i])
            deflection_diag.append(round(ops.nodeDisp(node_id, 2) * 1_000.0, 4))

            # Get element forces for shear/moment
            if i < len(node_positions) - 1:
                forces = ops.eleForce(i + 1)
                # forces: [N1, V1, M1, N2, V2, M2]
                shear_diag.append(round(forces[1] / 1_000.0, 4))
                moment_diag.append(round(forces[2] / 1_000.0, 4))
            else:
                # Last node: use end of last element
                forces = ops.eleForce(len(node_positions) - 1)
                shear_diag.append(round(-forces[4] / 1_000.0, 4))
                moment_diag.append(round(-forces[5] / 1_000.0, 4))

    finally:
        ops.wipe()

    # Cross-validate with closed-form
    closed_form = analyze_beam(inputs)
    deflection_limit_mm = closed_form["deflection_limit_mm"]
    deflection_ok = max_defl_mm <= float(deflection_limit_mm)

    result = {
        **closed_form,
        "solver": "openseespy_elastic_beam",
        "opensees_status": status,
        "support_type": support,
        "left_reaction_kn": round(left_reaction_kn, 4),
        "right_reaction_kn": round(right_reaction_kn, 4),
        "max_reaction_kn": round(max(abs(left_reaction_kn), abs(right_reaction_kn)), 4),
        "max_deflection_mm": round(max_defl_mm, 4),
        "signed_midspan_deflection_mm": round(mid_deflection_mm, 4),
        "deflection_ok": deflection_ok,
        "is_finite": closed_form["is_finite"]
        and all(math.isfinite(v) for v in [left_reaction_kn, right_reaction_kn, mid_deflection_mm]),
    }

    # Replace closed-form diagrams with OpenSees diagrams
    from app.models import DiagramData
    result["_diagrams"] = DiagramData(
        positions=positions_diag,
        shear_kn=shear_diag,
        moment_kn_m=moment_diag,
        deflection_mm=deflection_diag,
    )

    return result


def _build_node_positions(span: float, point_loads: list) -> list[float]:
    """Build sorted list of node positions including endpoints, midspan, and point load locations."""
    positions = {0.0, span / 2.0, span}

    # Add intermediate nodes for better resolution
    for i in range(1, 10):
        positions.add(i * span / 10.0)

    # Add point load positions
    for pl in point_loads:
        if 0 < pl.position_m < span:
            positions.add(pl.position_m)

    return sorted(positions)


def _find_nearest_node(positions: list[float], target: float) -> int:
    """Find the 1-indexed node ID closest to target position."""
    min_dist = float("inf")
    best = 1
    for i, x in enumerate(positions):
        d = abs(x - target)
        if d < min_dist:
            min_dist = d
            best = i + 1
    return best


# Legacy wrapper
def analyze_simply_supported_udl_opensees(inputs: BeamInputs) -> dict:
    """Backward-compatible wrapper."""
    return analyze_beam_opensees(inputs)
