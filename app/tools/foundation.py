"""Foundation design: spread footing (ACI 318) and pile static capacity.

Deterministic closed-form calculations. No LLM involvement.

References:
- ACI 318-19, Section 15 (Footings) -- bearing, one-way and two-way (punching) shear, flexure
- Standard geotechnical static pile capacity (skin friction + end bearing)
- Converse-Labarre group efficiency

All internal calculations in mm, MPa (N/mm^2), kN, kN-m, kPa (kN/m^2).
"""
from __future__ import annotations

import math

from app.models import PileInputs, SpreadFootingInputs

PHI_SHEAR = 0.75
PHI_FLEX = 0.90
CLEAR_COVER_MM = 75.0


# ---------------------------------------------------------------------------
# Spread footing (isolated, ACI 318)
# ---------------------------------------------------------------------------

def _required_area_m2(service_load_kn: float, allowable_bearing_kpa: float) -> float:
    return service_load_kn / allowable_bearing_kpa


def _round_up_to(value_mm: float, step_mm: float = 50.0) -> float:
    return math.ceil(value_mm / step_mm) * step_mm


def design_spread_footing(inputs: SpreadFootingInputs) -> dict:
    """Size and check a square spread footing (bearing, shear, flexure) per ACI 318."""
    warnings: list[str] = []

    p_service = inputs.axial_load_kn
    p_factored = inputs.factored_axial_kn if inputs.factored_axial_kn else 1.4 * p_service
    q_all = inputs.allowable_bearing_kpa

    # Effective depth: from footing depth minus cover and bar.
    d = inputs.footing_depth_mm - CLEAR_COVER_MM - inputs.bar_dia_mm / 2.0
    if d <= 0:
        warnings.append("Footing depth too small for the bar size; increase depth.")
        d = max(d, 50.0)

    # Required footprint area from service load and allowable bearing.
    a_req = _required_area_m2(p_service, q_all)
    b_req_mm = math.sqrt(a_req) * 1000.0
    b_mm = _round_up_to(b_req_mm)
    if inputs.footing_width_mm:
        b_mm = max(b_mm, inputs.footing_width_mm)

    b = b_mm / 1000.0  # m
    a_foot = b * b  # m^2

    # Bearing check (service).
    q_service = p_service / a_foot  # kPa
    bearing_ok = q_service <= q_all
    if not bearing_ok:
        warnings.append(f"Bearing pressure {q_service:.1f} kPa exceeds allowable {q_all:.1f} kPa. Increase footing size.")

    # Factored net pressure (kPa) for shear and flexure.
    q_u = p_factored / a_foot

    # --- One-way (beam) shear: critical section at d from column face. ---
    b_col = inputs.column_width_mm / 1000.0
    d_m = d / 1000.0
    # Width of the footing strip beyond the critical section (per side), full width b.
    # Force on the critical area (one side strip of width b):
    v_u_ow = q_u * (b - b_col) * b / 2.0  # kN
    phi_v_ow = PHI_SHEAR * 0.17 * (inputs.concrete_fck_mpa**0.5) * (b * 1000.0) * d / 1000.0  # kN
    ow_util = v_u_ow / phi_v_ow if phi_v_ow > 0 else float("inf")
    ow_ok = v_u_ow <= phi_v_ow
    if not ow_ok:
        warnings.append(f"One-way shear governs: Vu {v_u_ow:.1f} kN > phi*Vc {phi_v_ow:.1f} kN. Increase depth.")

    # --- Two-way (punching) shear: critical section at d/2 from column face. ---
    d_col = inputs.column_depth_mm / 1000.0
    # Perimeter of the critical section (rectangular column).
    perim = 2.0 * (b_col + d_m) + 2.0 * (d_col + d_m)  # m
    a_crit = (b_col + d_m) * (d_col + d_m)  # m^2 (area inside critical section)
    a_out = a_foot - a_crit
    v_u_pw = q_u * a_out  # kN
    phi_v_pw = PHI_SHEAR * 0.17 * (inputs.concrete_fck_mpa**0.5) * (perim * 1000.0) * d / 1000.0  # kN
    pw_util = v_u_pw / phi_v_pw if phi_v_pw > 0 else float("inf")
    pw_ok = v_u_pw <= phi_v_pw
    if not pw_ok:
        warnings.append(f"Punching shear governs: Vu {v_u_pw:.1f} kN > phi*Vc {phi_v_pw:.1f} kN. Increase depth.")

    # --- Flexure: critical section at column face. ---
    # Moment on the projection (strip of width b), square footing:
    m_u = q_u * b * (b - b_col) ** 2 / 8.0  # kN-m
    # Required steel (iterate for the stress-block depth a).
    b_strip = b * 1000.0  # mm
    d_mm = d
    as_req = m_u * 1e6 / (PHI_FLEX * inputs.steel_fy_mpa * d_mm)  # initial (N-mm)
    for _ in range(5):
        a = (as_req * inputs.steel_fy_mpa) / (0.85 * inputs.concrete_fck_mpa * b_strip)  # mm
        as_req = m_u * 1e6 / (PHI_FLEX * inputs.steel_fy_mpa * (d_mm - a / 2.0))
    as_min = 0.0018 * b_strip * d_mm  # mm^2
    as_design = max(as_req, as_min)
    min_governs = as_design > as_req
    if min_governs:
        warnings.append("Minimum reinforcement governs flexure.")

    # Suggested bar count (single layer, each direction).
    as_bar = math.pi / 4.0 * inputs.bar_dia_mm**2
    n_bars = math.ceil(as_design / as_bar) if as_design > 0 else 0
    # Clear spacing for n_bars across the footing width.
    if n_bars > 1:
        clear_spacing = (b_mm - 2.0 * CLEAR_COVER_MM - n_bars * inputs.bar_dia_mm) / (n_bars - 1)
        spacing_ok = clear_spacing >= max(inputs.bar_dia_mm, 100.0)
        if not spacing_ok:
            warnings.append(f"Bar spacing {clear_spacing:.0f} mm is below the minimum; use a larger bar or two layers.")
    else:
        clear_spacing = None
        spacing_ok = True

    return {
        "method": "ACI 318-19 spread footing design (bearing, one-way & punching shear, flexure)",
        "code_reference": "ACI 318-19 Section 15",
        "inputs": {
            "axial_load_kn": inputs.axial_load_kn,
            "factored_axial_kn": p_factored,
            "allowable_bearing_kpa": inputs.allowable_bearing_kpa,
            "column_size_mm": [inputs.column_width_mm, inputs.column_depth_mm],
            "concrete_fck_mpa": inputs.concrete_fck_mpa,
            "steel_fy_mpa": inputs.steel_fy_mpa,
            "footing_depth_mm": inputs.footing_depth_mm,
        },
        "footing": {
            "width_mm": b_mm,
            "area_m2": round(a_foot, 3),
            "effective_depth_mm": round(d, 1),
        },
        "bearing": {
            "pressure_kpa": round(q_service, 2),
            "allowable_kpa": q_all,
            "util": round(q_service / q_all, 3),
            "ok": bearing_ok,
        },
        "one_way_shear": {
            "vu_kn": round(v_u_ow, 2),
            "phi_vc_kn": round(phi_v_ow, 2),
            "util": round(ow_util, 3),
            "ok": ow_ok,
        },
        "punching_shear": {
            "vu_kn": round(v_u_pw, 2),
            "phi_vc_kn": round(phi_v_pw, 2),
            "util": round(pw_util, 3),
            "ok": pw_ok,
        },
        "flexure": {
            "mu_kn_m": round(m_u, 2),
            "required_as_mm2": round(as_req, 1),
            "min_as_mm2": round(as_min, 1),
            "design_as_mm2": round(as_design, 1),
            "min_governs": min_governs,
        },
        "suggested_bars": {
            "bar_dia_mm": inputs.bar_dia_mm,
            "count_each_direction": n_bars,
            "clear_spacing_mm": round(clear_spacing, 1) if clear_spacing is not None else None,
            "spacing_ok": spacing_ok,
        },
        "pass": bearing_ok and ow_ok and pw_ok,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Pile static capacity
# ---------------------------------------------------------------------------

def design_pile_capacity(inputs: PileInputs) -> dict:
    """Static pile capacity (skin friction + end bearing) and group efficiency."""
    warnings: list[str] = []

    d = inputs.pile_diameter_mm / 1000.0  # m
    l = inputs.pile_length_m
    a_p = math.pi / 4.0 * d**2  # m^2 (end area)
    perim = math.pi * d  # m (shaft perimeter)

    # Skin friction: Qs = alpha * f_avg * A_shaft
    a_shaft = perim * l  # m^2
    q_s = inputs.skin_friction_alpha * inputs.skin_friction_kpa * a_shaft  # kN

    # End bearing: Qp = q_p * A_p
    q_p = inputs.end_bearing_kpa * a_p  # kN

    q_ult = q_s + q_p  # kN
    q_allow = q_ult / inputs.factor_of_safety  # kN

    # Group efficiency (Converse-Labarre): n = piles per row, m = number of rows.
    n = inputs.piles_per_row
    m = inputs.rows_in_group
    total_piles = n * m
    eta = 1.0
    if total_piles > 1 and inputs.center_to_center_spacing_m > 0:
        s = inputs.center_to_center_spacing_m
        theta_deg = math.degrees(math.atan(d / s))
        eta = 1.0 - (theta_deg / 90.0) * ((n - 1) / m + (m - 1) / n)
        eta = max(0.0, min(1.0, eta))
        if eta < 1.0:
            warnings.append(
                f"Group efficiency eta = {eta:.3f} (Converse-Labarre) for {n} x {m} piles at "
                f"{s:.2f} m c/c spacing. Use >= 2.5D spacing to approach eta = 1.0."
            )

    group_capacity = eta * total_piles * q_allow  # kN

    # Contribution breakdown.
    skin_fraction = q_s / q_ult if q_ult > 0 else 0.0

    return {
        "method": "Static pile capacity (skin friction + end bearing) + Converse-Labarre group efficiency",
        "code_reference": "Standard static pile capacity; Converse-Labarre (1897)",
        "inputs": {
            "pile_diameter_mm": inputs.pile_diameter_mm,
            "pile_length_m": inputs.pile_length_m,
            "skin_friction_kpa": inputs.skin_friction_kpa,
            "skin_friction_alpha": inputs.skin_friction_alpha,
            "end_bearing_kpa": inputs.end_bearing_kpa,
            "factor_of_safety": inputs.factor_of_safety,
            "piles_per_row": inputs.piles_per_row,
            "rows_in_group": inputs.rows_in_group,
            "total_piles": total_piles,
            "center_to_center_spacing_m": inputs.center_to_center_spacing_m,
        },
        "pile": {
            "diameter_m": round(d, 4),
            "end_area_m2": round(a_p, 4),
            "shaft_area_m2": round(a_shaft, 4),
        },
        "capacity_kn": {
            "skin_friction": round(q_s, 1),
            "end_bearing": round(q_p, 1),
            "ultimate": round(q_ult, 1),
            "allowable": round(q_allow, 1),
            "skin_fraction": round(skin_fraction, 3),
        },
        "group": {
            "efficiency": round(eta, 3),
            "piles": total_piles,
            "allowable_capacity": round(group_capacity, 1),
        },
        "warnings": warnings,
    }
