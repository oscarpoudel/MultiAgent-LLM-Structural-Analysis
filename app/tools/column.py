from __future__ import annotations

import math

from app.models import ColumnInputs


# Effective length factors (K) for different end conditions
EFFECTIVE_LENGTH_FACTORS = {
    "pinned_pinned": 1.0,
    "fixed_free": 2.0,
    "fixed_pinned": 0.7,
    "fixed_fixed": 0.5,
}


def analyze_column(inputs: ColumnInputs) -> dict:
    """Euler buckling analysis and capacity checks for a column."""
    L = inputs.length_m
    A = inputs.area_m2
    I = inputs.inertia_m4
    E = inputs.elastic_modulus_gpa * 1e9  # Pa
    Fy = inputs.yield_stress_mpa * 1e6    # Pa
    P = inputs.axial_load_kn * 1_000.0    # N

    K = EFFECTIVE_LENGTH_FACTORS.get(inputs.end_condition, 1.0)
    Le = K * L  # effective length

    # Radius of gyration
    r = math.sqrt(I / A)

    # Slenderness ratio
    slenderness = Le / r

    # Euler critical buckling load
    P_euler_n = math.pi**2 * E * I / Le**2
    P_euler_kn = P_euler_n / 1_000.0

    # Elastic buckling stress
    Fe = math.pi**2 * E / slenderness**2

    # AISC-style critical stress (Chapter E)
    slenderness_limit = 4.71 * math.sqrt(E / Fy)

    if slenderness <= slenderness_limit:
        # Inelastic buckling
        Fcr = 0.658**(Fy / Fe) * Fy
    else:
        # Elastic buckling
        Fcr = 0.877 * Fe

    # Nominal compressive strength
    Pn_n = Fcr * A
    Pn_kn = Pn_n / 1_000.0

    # Design strength (LRFD, phi = 0.9)
    phi = 0.9
    phi_Pn_kn = phi * Pn_kn

    # Axial stress
    axial_stress_mpa = (P / A) / 1e6 if A > 0 else 0.0

    # Utilization ratio
    utilization = abs(inputs.axial_load_kn) / phi_Pn_kn if phi_Pn_kn > 0 else float("inf")

    # Classification
    if slenderness <= 50:
        slenderness_class = "short (stocky)"
    elif slenderness <= 120:
        slenderness_class = "intermediate"
    elif slenderness <= 200:
        slenderness_class = "long (slender)"
    else:
        slenderness_class = "very slender (KL/r > 200, check code limits)"

    # Buckling mode
    will_buckle = abs(P) >= P_euler_n
    capacity_ok = utilization <= 1.0

    warnings = []
    if slenderness > 200:
        warnings.append("Slenderness ratio exceeds 200. Most codes recommend KL/r <= 200 for compression members.")
    if not capacity_ok:
        warnings.append(f"Utilization ratio {utilization:.2f} > 1.0. Column is overstressed.")
    if will_buckle:
        warnings.append("Applied load exceeds Euler buckling load. Column will buckle.")
    if axial_stress_mpa > inputs.yield_stress_mpa:
        warnings.append("Axial stress exceeds yield stress. Material will yield before buckling.")

    return {
        "solver": "column_euler_aisc",
        "end_condition": inputs.end_condition,
        "effective_length_factor_K": K,
        "length_m": L,
        "effective_length_m": round(Le, 4),
        "area_m2": A,
        "inertia_m4": I,
        "radius_of_gyration_m": round(r, 6),
        "slenderness_ratio": round(slenderness, 2),
        "slenderness_class": slenderness_class,
        "euler_buckling_load_kn": round(P_euler_kn, 4),
        "elastic_buckling_stress_mpa": round(Fe / 1e6, 2),
        "critical_stress_mpa": round(Fcr / 1e6, 2),
        "nominal_strength_kn": round(Pn_kn, 4),
        "design_strength_kn": round(phi_Pn_kn, 4),
        "applied_load_kn": inputs.axial_load_kn,
        "axial_stress_mpa": round(axial_stress_mpa, 2),
        "utilization_ratio": round(utilization, 4),
        "capacity_ok": capacity_ok,
        "will_buckle": will_buckle,
        "elastic_modulus_gpa": inputs.elastic_modulus_gpa,
        "yield_stress_mpa": inputs.yield_stress_mpa,
        "warnings": warnings,
        "is_finite": all(
            math.isfinite(v) for v in [P_euler_kn, Fcr, Pn_kn, slenderness, utilization]
        ),
    }
