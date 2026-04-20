from __future__ import annotations

import math

from app.models import BeamInputs
from app.tools.beam import analyze_simply_supported_udl


def analyze_simply_supported_udl_opensees(inputs: BeamInputs) -> dict[str, float | bool | None | str]:
    """OpenSeesPy elastic 2D beam model for a simply supported UDL beam."""
    if inputs.inertia_m4 is None or inputs.inertia_m4 <= 0:
        result = analyze_simply_supported_udl(inputs)
        result["solver"] = "closed_form_no_inertia"
        return result

    try:
        import openseespy.opensees as ops
    except Exception as error:
        result = analyze_simply_supported_udl(inputs)
        result["solver"] = "closed_form_opensees_import_failed"
        result["solver_warning"] = str(error)
        return result

    span = inputs.span_m
    half_span = span / 2.0
    load_n_per_m = inputs.udl_kn_per_m * 1_000.0
    e_pa = inputs.elastic_modulus_gpa * 1_000_000_000.0
    area = inputs.area_m2

    ops.wipe()
    try:
        ops.model("basic", "-ndm", 2, "-ndf", 3)
        ops.node(1, 0.0, 0.0)
        ops.node(2, half_span, 0.0)
        ops.node(3, span, 0.0)

        ops.fix(1, 1, 1, 0)
        ops.fix(2, 0, 0, 0)
        ops.fix(3, 0, 1, 0)

        ops.geomTransf("Linear", 1)
        ops.element("elasticBeamColumn", 1, 1, 2, area, e_pa, inputs.inertia_m4, 1)
        ops.element("elasticBeamColumn", 2, 2, 3, area, e_pa, inputs.inertia_m4, 1)

        ops.timeSeries("Linear", 1)
        ops.pattern("Plain", 1, 1)
        ops.eleLoad("-ele", 1, "-type", "-beamUniform", -load_n_per_m)
        ops.eleLoad("-ele", 2, "-type", "-beamUniform", -load_n_per_m)

        ops.system("BandGeneral")
        ops.numberer("RCM")
        ops.constraints("Plain")
        ops.integrator("LoadControl", 1.0)
        ops.algorithm("Linear")
        ops.analysis("Static")
        status = ops.analyze(1)
        ops.reactions()

        left_reaction_kn = ops.nodeReaction(1, 2) / 1_000.0
        right_reaction_kn = ops.nodeReaction(3, 2) / 1_000.0
        mid_deflection_mm = ops.nodeDisp(2, 2) * 1_000.0
    finally:
        ops.wipe()

    closed_form = analyze_simply_supported_udl(inputs)
    deflection_limit_mm = closed_form["deflection_limit_mm"]
    deflection_ok = abs(mid_deflection_mm) <= float(deflection_limit_mm)

    return {
        **closed_form,
        "solver": "openseespy_elastic_beam",
        "opensees_status": status,
        "left_reaction_kn": left_reaction_kn,
        "right_reaction_kn": right_reaction_kn,
        "max_reaction_kn": max(abs(left_reaction_kn), abs(right_reaction_kn)),
        "max_deflection_mm": abs(mid_deflection_mm),
        "signed_midspan_deflection_mm": mid_deflection_mm,
        "deflection_ok": deflection_ok,
        "is_finite": closed_form["is_finite"]
        and all(math.isfinite(value) for value in [left_reaction_kn, right_reaction_kn, mid_deflection_mm]),
    }
