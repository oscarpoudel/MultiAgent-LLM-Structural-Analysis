from __future__ import annotations

import math

from app.models import BeamInputs


def analyze_simply_supported_udl(inputs: BeamInputs) -> dict[str, float | bool | None]:
    """Elastic simply supported beam under full-span uniform load."""
    span = inputs.span_m
    load_n_per_m = inputs.udl_kn_per_m * 1_000.0
    e_pa = inputs.elastic_modulus_gpa * 1_000_000_000.0
    inertia = inputs.inertia_m4

    max_reaction_kn = inputs.udl_kn_per_m * span / 2.0
    max_shear_kn = inputs.udl_kn_per_m * span / 2.0
    max_moment_kn_m = inputs.udl_kn_per_m * span**2 / 8.0

    deflection_m = None
    deflection_limit_m = span / inputs.deflection_limit_ratio
    deflection_ok = None
    if inertia and inertia > 0:
        deflection_m = 5.0 * load_n_per_m * span**4 / (384.0 * e_pa * inertia)
        deflection_ok = deflection_m <= deflection_limit_m

    stress_mpa = None
    if inputs.section_modulus_m3 and inputs.section_modulus_m3 > 0:
        moment_n_m = max_moment_kn_m * 1_000.0
        stress_mpa = moment_n_m / inputs.section_modulus_m3 / 1_000_000.0

    return {
        "span_m": span,
        "udl_kn_per_m": inputs.udl_kn_per_m,
        "max_reaction_kn": max_reaction_kn,
        "max_shear_kn": max_shear_kn,
        "max_moment_kn_m": max_moment_kn_m,
        "max_deflection_mm": None if deflection_m is None else deflection_m * 1_000.0,
        "deflection_limit_mm": deflection_limit_m * 1_000.0,
        "deflection_ok": deflection_ok,
        "bending_stress_mpa": stress_mpa,
        "elastic_modulus_gpa": inputs.elastic_modulus_gpa,
        "inertia_m4": inertia,
        "section_modulus_m3": inputs.section_modulus_m3,
        "deflection_limit_ratio": inputs.deflection_limit_ratio,
        "is_finite": all(
            math.isfinite(value)
            for value in [span, inputs.udl_kn_per_m, inputs.elastic_modulus_gpa]
        ),
    }
