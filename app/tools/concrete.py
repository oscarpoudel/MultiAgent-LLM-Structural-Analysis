"""Reinforced concrete design (ACI 318-19).

Deterministic closed-form calculations. No LLM involvement.

References:
- ACI 318-19, Section 9 (Reinforced Concrete) -- beam flexure and shear
- ACI 318-19, Section 22 (Axially Loaded Members) -- tied and spiral columns

All internal calculations in mm and MPa (N/mm^2); outputs converted to kN / kN-m.
"""
from __future__ import annotations

import math

from app.models import ConcreteBeamInputs, ConcreteColumnInputs

PHI_FLEX = 0.90
PHI_SHEAR = 0.75
PHI_TIED = 0.65
PHI_SPIRAL = 0.75
CLEAR_COVER_MM = 40.0


def _beam_design_reinforcement(
    mu_kn_m: float,
    b_mm: float,
    d_mm: float,
    fck_mpa: float,
    fy_mpa: float,
) -> dict:
    """Rectangular section flexural design (ACI 318). Returns required As, rho, and capacity."""
    mu_nmm2 = mu_kn_m * 1e6  # N-mm
    rn = mu_nmm2 / (PHI_FLEX * b_mm * d_mm**2)  # MPa
    term = 1.0 - (2.0 * rn / (0.85 * fck_mpa))

    rho_min = max(0.25 * (200.0**0.5) / fy_mpa, 0.0018)
    rho_max = 0.75 * 0.85 * fck_mpa / fy_mpa * (0.003 / (0.003 + fy_mpa / (200.0e3)))

    if term < 0.0:
        # Demand exceeds the section's ultimate capacity -> over-reinforced / inadequate.
        rho_required = float("inf")
        rho_design = rho_max
        rho_ok = False
    else:
        # Required ratio (may be negative when the section has excess capacity).
        rho_required = (0.85 * fck_mpa / fy_mpa) * (1.0 - term**0.5)
        # Always provide at least the minimum reinforcement.
        rho_design = max(rho_required, rho_min)
        rho_ok = True

    as_req = rho_design * b_mm * d_mm  # mm^2

    # Nominal moment capacity with the design reinforcement
    as_design = rho_design * b_mm * d_mm  # mm^2
    a = (as_design * fy_mpa) / (0.85 * fck_mpa * b_mm)  # mm
    mn = as_design * fy_mpa * (d_mm - a / 2.0) / 1e6  # kN-m
    phi_mn = PHI_FLEX * mn

    over_reinforced = (not rho_ok) or rho_required > rho_max
    return {
        "required_as_mm2": round(as_req, 1),
        "rho_required": round(rho_required, 5) if math.isfinite(rho_required) else None,
        "rho_design": round(rho_design, 5),
        "rho_min": round(rho_min, 5),
        "rho_max": round(rho_max, 5),
        "rho_ok": rho_ok,
        "over_reinforced": over_reinforced,
        "rn_mpa": round(rn, 3),
        "phi_mn_kn_m": round(phi_mn, 2),
        "flex_util": round(mu_kn_m / phi_mn, 3) if phi_mn > 0 else None,
    }


def _beam_design_shear(
    vu_kn: float,
    b_mm: float,
    d_mm: float,
    fck_mpa: float,
    stirrup_dia_mm: float,
) -> dict:
    """One-way shear design (ACI 318). Returns Vc, Vu/Vc, and required stirrup spacing."""
    if vu_kn <= 0:
        return {"vc_kn": 0.0, "vu_over_vc": 0.0, "stirrup_required": False, "spacing_mm": None}

    vc = 0.17 * (fck_mpa**0.5) * b_mm * d_mm / 1000.0  # kN
    phi_vc = PHI_SHEAR * vc
    vu_over_vc = vu_kn / phi_vc if phi_vc > 0 else float("inf")
    stirrup_required = vu_kn > phi_vc

    spacing_mm = None
    if stirrup_required:
        as_stirrup = 2.0 * (math.pi / 4.0) * stirrup_dia_mm**2  # 2 legs, mm^2
        vs_req = (vu_kn - vc) * 1000.0 / (b_mm * d_mm)  # MPa
        vs_max = 0.33 * (fck_mpa**0.5)  # MPa
        vs = min(max(vs_req, 0.0), vs_max)
        if vs > 0:
            spacing_mm = as_stirrup * 420.0 * d_mm / (vs * b_mm)
            spacing_mm = min(spacing_mm, d_mm / 2.0, 600.0)
    return {
        "vc_kn": round(vc, 2),
        "phi_vc_kn": round(phi_vc, 2),
        "vu_over_vc": round(vu_over_vc, 3),
        "stirrup_required": stirrup_required,
        "spacing_mm": round(spacing_mm, 1) if spacing_mm is not None else None,
    }


def design_concrete_beam(inputs: ConcreteBeamInputs) -> dict:
    """Design a singly reinforced concrete beam (flexure + shear) per ACI 318."""
    warnings: list[str] = []
    d = inputs.effective_depth_mm
    if d is None:
        d = inputs.depth_mm - CLEAR_COVER_MM - inputs.stirrup_dia_mm - inputs.bar_dia_mm / 2.0
    if d <= 0:
        warnings.append("Effective depth is non-positive; increase beam depth.")
        d = max(d, 10.0)

    flex = _beam_design_reinforcement(inputs.moment_kn_m, inputs.width_mm, d, inputs.concrete_fck_mpa, inputs.steel_fy_mpa)
    if flex["over_reinforced"]:
        warnings.append("Section is over-reinforced for the given moment; increase depth or width.")

    shear = _beam_design_shear(inputs.shear_kn, inputs.width_mm, d, inputs.concrete_fck_mpa, inputs.stirrup_dia_mm)
    if shear["vu_over_vc"] and shear["vu_over_vc"] > 2.0:
        warnings.append("Vu > 2*phi*Vc; section is too small for the shear demand. Increase depth/width.")

    # Bar spacing suggestion (single layer)
    as_bar = math.pi / 4.0 * inputs.bar_dia_mm**2
    n_bars = math.ceil(flex["required_as_mm2"] / as_bar) if flex["required_as_mm2"] > 0 else 0
    if n_bars > 1:
        clear_spacing = (inputs.width_mm - 2.0 * CLEAR_COVER_MM - 2.0 * inputs.stirrup_dia_mm - n_bars * inputs.bar_dia_mm) / (n_bars - 1)
        spacing_ok = clear_spacing >= max(inputs.bar_dia_mm, 25.0)
        if not spacing_ok:
            warnings.append(f"Bar spacing {clear_spacing:.0f} mm is below the minimum; use two layers or a wider beam.")
    else:
        clear_spacing = None
        spacing_ok = True

    return {
        "method": "ACI 318-19 singly reinforced beam design (flexure + shear)",
        "code_reference": "ACI 318-19 Sections 9, 22",
        "inputs": {
            "moment_kn_m": inputs.moment_kn_m,
            "shear_kn": inputs.shear_kn,
            "width_mm": inputs.width_mm,
            "depth_mm": inputs.depth_mm,
            "concrete_fck_mpa": inputs.concrete_fck_mpa,
            "steel_fy_mpa": inputs.steel_fy_mpa,
        },
        "effective_depth_mm": round(d, 1),
        "flexure": flex,
        "shear": shear,
        "suggested_bars": {
            "bar_dia_mm": inputs.bar_dia_mm,
            "count": n_bars,
            "clear_spacing_mm": round(clear_spacing, 1) if clear_spacing is not None else None,
            "spacing_ok": spacing_ok,
        },
        "warnings": warnings,
    }


def design_concrete_column(inputs: ConcreteColumnInputs) -> dict:
    """Design a circular tied or spiral concrete column (axial) per ACI 318."""
    warnings: list[str] = []
    phi = PHI_SPIRAL if not inputs.tied else PHI_TIED
    a_g = math.pi / 4.0 * inputs.diameter_mm**2  # mm^2

    # Slenderness check (ACI 318 22.2): beta2 = 0.85 (tied) or 1.0 (spiral).
    # Capacity below is the short-column (no second-order) value; a warning is
    # raised when kl/r exceeds the short-column limit.
    slenderness_ok = True
    if inputs.kl_r > 0:
        beta2 = 1.0 if not inputs.tied else 0.85
        pu_over_ag_fc = (inputs.axial_load_kn * 1000.0) / (a_g * inputs.concrete_fck_mpa)
        limit = 34.0 - 12.0 * pu_over_ag_fc / beta2
        if inputs.kl_r > limit:
            slenderness_ok = False
            warnings.append(
                f"Slenderness kl/r = {inputs.kl_r:.1f} exceeds the short-column limit {limit:.1f}; "
                "the reported capacity is the short-column value and second-order (P-delta) effects "
                "must be considered separately."
            )

    # Required total steel area. Solve Pu = phi * 0.85 * (Ag - As) * f'c + As * fy
    # => As = (Pu/(phi*0.85) - Ag*f'c) / (fy - 0.85*f'c)
    pu_nmm2 = inputs.axial_load_kn * 1000.0  # N
    denom = inputs.steel_fy_mpa - 0.85 * inputs.concrete_fck_mpa
    as_req = (pu_nmm2 / (phi * 0.85) - a_g * inputs.concrete_fck_mpa) / denom
    as_req = max(as_req, 0.0)

    rho_min_tied = 0.01
    rho_min_spiral = 0.03
    rho_max = 0.08
    rho_min = rho_min_spiral if not inputs.tied else rho_min_tied
    as_min = rho_min * a_g
    as_design = max(as_req, as_min)
    as_max = rho_max * a_g
    if as_design > as_max:
        warnings.append("Required steel exceeds 8% of gross area; increase column size.")
        as_design = as_max

    # Nominal capacity with the design steel (short column)
    pn = 0.85 * (a_g - as_design) * inputs.concrete_fck_mpa + as_design * inputs.steel_fy_mpa  # N
    phi_pn = phi * pn / 1000.0  # kN
    util = inputs.axial_load_kn / phi_pn if phi_pn > 0 else float("inf")

    # Suggested bar count (20 mm bars)
    bar_dia = 20.0
    as_bar = math.pi / 4.0 * bar_dia**2
    n_bars = math.ceil(as_design / as_bar) if as_design > 0 else 0

    return {
        "method": "ACI 318-19 circular column design (tied/spiral, axial)",
        "code_reference": "ACI 318-19 Section 22",
        "inputs": {
            "axial_load_kn": inputs.axial_load_kn,
            "diameter_mm": inputs.diameter_mm,
            "concrete_fck_mpa": inputs.concrete_fck_mpa,
            "steel_fy_mpa": inputs.steel_fy_mpa,
            "tied": inputs.tied,
            "kl_r": inputs.kl_r,
        },
        "gross_area_mm2": round(a_g, 1),
        "phi": phi,
        "slenderness_ok": slenderness_ok,
        "required_as_mm2": round(as_req, 1),
        "min_as_mm2": round(as_min, 1),
        "design_as_mm2": round(as_design, 1),
        "rho_design": round(as_design / a_g, 4),
        "rho_min": rho_min,
        "rho_max": rho_max,
        "phi_pn_kn": round(phi_pn, 1),
        "util": round(util, 3),
        "suggested_bars": {"bar_dia_mm": bar_dia, "count": n_bars},
        "warnings": warnings,
    }
