from __future__ import annotations

import math

from app.models import BeamInputs, DiagramData


def analyze_beam(inputs: BeamInputs) -> dict:
    """Closed-form beam analysis supporting multiple load types and boundary conditions."""
    span = inputs.span_m
    w = inputs.udl_kn_per_m
    e_pa = inputs.elastic_modulus_gpa * 1e9
    inertia = inputs.inertia_m4
    support = inputs.support_type

    # ------------------------------------------------------------------
    # Reactions, shear, moment from UDL
    # ------------------------------------------------------------------
    if support == "cantilever":
        udl_results = _cantilever_udl(span, w)
    elif support == "fixed_fixed":
        udl_results = _fixed_fixed_udl(span, w)
    elif support == "propped_cantilever":
        udl_results = _propped_cantilever_udl(span, w)
    else:
        udl_results = _simply_supported_udl(span, w)

    # ------------------------------------------------------------------
    # Add point load contributions via superposition
    # ------------------------------------------------------------------
    for pl in inputs.point_loads:
        p = pl.magnitude_kn
        a = pl.position_m
        if support == "cantilever":
            pl_results = _cantilever_point(span, p, a)
        elif support == "fixed_fixed":
            pl_results = _fixed_fixed_point(span, p, a)
        else:
            pl_results = _simply_supported_point(span, p, a)

        udl_results["left_reaction_kn"] += pl_results["left_reaction_kn"]
        udl_results["right_reaction_kn"] += pl_results["right_reaction_kn"]
        udl_results["max_shear_kn"] = max(
            udl_results["max_shear_kn"], abs(pl_results["max_shear_kn"])
        )
        udl_results["max_moment_kn_m"] += pl_results["max_moment_kn_m"]

    max_reaction_kn = max(
        abs(udl_results["left_reaction_kn"]), abs(udl_results["right_reaction_kn"])
    )

    # ------------------------------------------------------------------
    # Deflection (UDL component only for closed-form)
    # ------------------------------------------------------------------
    deflection_m = None
    deflection_limit_m = span / inputs.deflection_limit_ratio
    deflection_ok = None
    if inertia and inertia > 0:
        deflection_m = _deflection_closed_form(support, span, w, e_pa, inertia)
        if deflection_m is not None:
            deflection_ok = deflection_m <= deflection_limit_m

    # ------------------------------------------------------------------
    # Bending stress
    # ------------------------------------------------------------------
    stress_mpa = None
    if inputs.section_modulus_m3 and inputs.section_modulus_m3 > 0:
        moment_n_m = udl_results["max_moment_kn_m"] * 1_000.0
        stress_mpa = moment_n_m / inputs.section_modulus_m3 / 1e6

    # ------------------------------------------------------------------
    # Diagram data
    # ------------------------------------------------------------------
    diagrams = _compute_beam_diagrams(inputs, e_pa)

    result = {
        "solver": "closed_form",
        "support_type": support,
        "span_m": span,
        "udl_kn_per_m": w,
        "num_point_loads": len(inputs.point_loads),
        "left_reaction_kn": round(udl_results["left_reaction_kn"], 4),
        "right_reaction_kn": round(udl_results["right_reaction_kn"], 4),
        "max_reaction_kn": round(max_reaction_kn, 4),
        "max_shear_kn": round(udl_results["max_shear_kn"], 4),
        "max_moment_kn_m": round(udl_results["max_moment_kn_m"], 4),
        "max_deflection_mm": None if deflection_m is None else round(deflection_m * 1_000.0, 4),
        "deflection_limit_mm": round(deflection_limit_m * 1_000.0, 4),
        "deflection_ok": deflection_ok,
        "bending_stress_mpa": stress_mpa,
        "elastic_modulus_gpa": inputs.elastic_modulus_gpa,
        "inertia_m4": inertia,
        "section_modulus_m3": inputs.section_modulus_m3,
        "deflection_limit_ratio": inputs.deflection_limit_ratio,
        "is_finite": all(
            math.isfinite(v) for v in [span, w, inputs.elastic_modulus_gpa]
        ),
    }
    if diagrams:
        result["_diagrams"] = diagrams

    return result


# ======================================================================
# Simply Supported helpers
# ======================================================================

def _simply_supported_udl(span: float, w: float) -> dict:
    r = w * span / 2.0
    return {
        "left_reaction_kn": r,
        "right_reaction_kn": r,
        "max_shear_kn": r,
        "max_moment_kn_m": w * span**2 / 8.0,
    }


def _simply_supported_point(span: float, p: float, a: float) -> dict:
    b = span - a
    r_left = p * b / span
    r_right = p * a / span
    return {
        "left_reaction_kn": r_left,
        "right_reaction_kn": r_right,
        "max_shear_kn": max(abs(r_left), abs(r_right)),
        "max_moment_kn_m": p * a * b / span,
    }


# ======================================================================
# Cantilever helpers (fixed at left, free at right)
# ======================================================================

def _cantilever_udl(span: float, w: float) -> dict:
    return {
        "left_reaction_kn": w * span,
        "right_reaction_kn": 0.0,
        "max_shear_kn": w * span,
        "max_moment_kn_m": w * span**2 / 2.0,
    }


def _cantilever_point(span: float, p: float, a: float) -> dict:
    """Point load at distance a from fixed end."""
    return {
        "left_reaction_kn": p,
        "right_reaction_kn": 0.0,
        "max_shear_kn": p,
        "max_moment_kn_m": p * a,
    }


# ======================================================================
# Fixed-Fixed helpers
# ======================================================================

def _fixed_fixed_udl(span: float, w: float) -> dict:
    r = w * span / 2.0
    return {
        "left_reaction_kn": r,
        "right_reaction_kn": r,
        "max_shear_kn": r,
        "max_moment_kn_m": w * span**2 / 12.0,  # midspan moment = wL^2/24, end moments = wL^2/12
    }


def _fixed_fixed_point(span: float, p: float, a: float) -> dict:
    b = span - a
    r_left = p * b**2 * (3 * a + b) / span**3
    r_right = p * a**2 * (a + 3 * b) / span**3
    m_max = p * a * b**2 / span**2  # fixed-end moment at left
    return {
        "left_reaction_kn": r_left,
        "right_reaction_kn": r_right,
        "max_shear_kn": max(abs(r_left), abs(r_right)),
        "max_moment_kn_m": abs(m_max),
    }


# ======================================================================
# Propped Cantilever helpers (fixed left, simply supported right)
# ======================================================================

def _propped_cantilever_udl(span: float, w: float) -> dict:
    r_right = 3 * w * span / 8.0
    r_left = w * span - r_right
    m_max = w * span**2 / 8.0  # max moment at fixed end = wL^2/8
    return {
        "left_reaction_kn": r_left,
        "right_reaction_kn": r_right,
        "max_shear_kn": max(abs(r_left), abs(r_right)),
        "max_moment_kn_m": m_max,
    }


# ======================================================================
# Deflection (closed-form, UDL only)
# ======================================================================

def _deflection_closed_form(
    support: str, span: float, w: float, e_pa: float, inertia: float
) -> float | None:
    load_n_per_m = w * 1_000.0
    if support == "simply_supported":
        return 5.0 * load_n_per_m * span**4 / (384.0 * e_pa * inertia)
    elif support == "cantilever":
        return load_n_per_m * span**4 / (8.0 * e_pa * inertia)
    elif support == "fixed_fixed":
        return load_n_per_m * span**4 / (384.0 * e_pa * inertia)
    elif support == "propped_cantilever":
        return load_n_per_m * span**4 / (185.0 * e_pa * inertia)
    return None


# ======================================================================
# Diagram generation (SFD / BMD / Deflection along beam)
# ======================================================================

def _compute_beam_diagrams(inputs: BeamInputs, e_pa: float) -> DiagramData | None:
    """Compute shear, moment, and deflection at stations along the beam."""
    span = inputs.span_m
    w = inputs.udl_kn_per_m
    inertia = inputs.inertia_m4
    support = inputs.support_type

    n_pts = 51
    positions = [i * span / (n_pts - 1) for i in range(n_pts)]

    # Compute reactions first
    if support == "cantilever":
        r_left = w * span
        for pl in inputs.point_loads:
            r_left += pl.magnitude_kn
        r_right = 0.0
        m_fixed = w * span**2 / 2.0
        for pl in inputs.point_loads:
            m_fixed += pl.magnitude_kn * pl.position_m
    elif support == "fixed_fixed":
        r_left = w * span / 2.0
        r_right = w * span / 2.0
        for pl in inputs.point_loads:
            b = span - pl.position_m
            r_left += pl.magnitude_kn * b**2 * (3 * pl.position_m + b) / span**3
            r_right += pl.magnitude_kn * pl.position_m**2 * (pl.position_m + 3 * b) / span**3
        m_fixed = w * span**2 / 12.0
        for pl in inputs.point_loads:
            b = span - pl.position_m
            m_fixed += pl.magnitude_kn * pl.position_m * b**2 / span**2
    else:  # simply_supported or propped_cantilever
        if support == "propped_cantilever":
            r_right = 3 * w * span / 8.0
            r_left = w * span - r_right
        else:
            r_left = w * span / 2.0
            r_right = w * span / 2.0
        for pl in inputs.point_loads:
            b = span - pl.position_m
            r_left += pl.magnitude_kn * b / span
            r_right += pl.magnitude_kn * pl.position_m / span
        m_fixed = 0.0

    shear_values = []
    moment_values = []
    deflection_values = []

    for x in positions:
        # Shear at x (cutting from left)
        v = r_left - w * x
        for pl in inputs.point_loads:
            if x >= pl.position_m:
                v -= pl.magnitude_kn

        # Moment at x
        if support == "cantilever":
            m = -m_fixed + r_left * x - w * x**2 / 2.0
            for pl in inputs.point_loads:
                if x >= pl.position_m:
                    m -= pl.magnitude_kn * (x - pl.position_m)
        elif support == "fixed_fixed":
            m = -m_fixed + r_left * x - w * x**2 / 2.0
            for pl in inputs.point_loads:
                if x >= pl.position_m:
                    m -= pl.magnitude_kn * (x - pl.position_m)
        else:
            m = r_left * x - w * x**2 / 2.0
            for pl in inputs.point_loads:
                if x >= pl.position_m:
                    m -= pl.magnitude_kn * (x - pl.position_m)

        shear_values.append(round(v, 4))
        moment_values.append(round(m, 4))

        # Deflection (approximate for UDL only, using closed-form shape)
        if inertia and inertia > 0 and w != 0:
            load_n_per_m = w * 1_000.0
            ei = e_pa * inertia
            if support == "simply_supported":
                defl = (load_n_per_m * x / (24.0 * ei)) * (span**3 - 2 * span * x**2 + x**3)
            elif support == "cantilever":
                defl = (load_n_per_m / (24.0 * ei)) * (x**4 - 4 * span * x**3 + 6 * span**2 * x**2)
            elif support == "fixed_fixed":
                defl = (load_n_per_m * x**2 / (24.0 * ei)) * (span - x)**2
            else:
                defl = (load_n_per_m * x / (24.0 * ei)) * (span**3 - 2 * span * x**2 + x**3)
            deflection_values.append(round(defl * 1_000.0, 4))
        else:
            deflection_values.append(0.0)

    return DiagramData(
        positions=positions,
        shear_kn=shear_values,
        moment_kn_m=moment_values,
        deflection_mm=deflection_values,
    )


# ======================================================================
# Legacy wrapper for backward compatibility
# ======================================================================

def analyze_simply_supported_udl(inputs: BeamInputs) -> dict:
    """Backward-compatible wrapper that calls the unified beam analyzer."""
    return analyze_beam(inputs)
