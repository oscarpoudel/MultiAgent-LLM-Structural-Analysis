"""Timber beam design (NDS - National Design Specification for Wood Construction).

Deterministic closed-form calculations using Allowable Stress Design (ASD).
No LLM involvement.

References:
- NDS 2024 (AWC), Section 3.7 (Bending Members)
- NDS Supplement, Table 4A (Reference Design Values for Visually Graded Lumber)
- NDS Table 2.3.2 (Duration-of-Load Factor CD)

All internal calculations in MPa, mm, kN, kN-m. Reference design values are
stored in psi (the NDS native unit) and converted to MPa.
"""
from __future__ import annotations

import math

from app.models import TimberBeamInputs

PSI_TO_MPA = 0.00689476
MM_PER_INCH = 25.4

# NDS reference design values (Supplement Table 4A), stored in psi.
# Fb = bending, Fv = shear, E_min = minimum modulus of elasticity.
SPECIES: dict[str, dict[str, float]] = {
    "douglas-fir-larch-select-structural": {"Fb_psi": 2400.0, "Fv_psi": 325.0, "E_psi": 1_800_000.0},
    "southern-pine-no1": {"Fb_psi": 1500.0, "Fv_psi": 215.0, "E_psi": 1_600_000.0},
    "spf-no1": {"Fb_psi": 875.0, "Fv_psi": 150.0, "E_psi": 1_400_000.0},
    "spf-select-structural": {"Fb_psi": 1900.0, "Fv_psi": 235.0, "E_psi": 1_800_000.0},
    "hem-fir-select-structural": {"Fb_psi": 2050.0, "Fv_psi": 235.0, "E_psi": 1_800_000.0},
    "eastern-white-pine-no1": {"Fb_psi": 1000.0, "Fv_psi": 170.0, "E_psi": 1_300_000.0},
}

# NDS duration-of-load factor CD (Table 2.3.2).
DURATION_CD: dict[str, float] = {
    "permanent": 0.90,
    "long_term": 0.90,
    "normal": 1.00,
    "short_term": 1.09,
    "temporary": 1.16,
    "momentary": 1.32,
}


def list_species() -> list[dict]:
    """Return the available species with their NDS reference design values (MPa)."""
    out = []
    for name, vals in SPECIES.items():
        out.append(
            {
                "name": name,
                "Fb_mpa": round(vals["Fb_psi"] * PSI_TO_MPA, 3),
                "Fv_mpa": round(vals["Fv_psi"] * PSI_TO_MPA, 3),
                "E_mpa": round(vals["E_psi"] * PSI_TO_MPA, 1),
            }
        )
    return out


def _duration_cd(duration: str) -> float:
    return DURATION_CD.get(duration, DURATION_CD["normal"])


def _wet_cm(moisture_pct: float) -> float:
    """NDS wet-service factor CM: 1.0 for MC <= 19%, 0.85 for 19% < MC <= 30%."""
    if moisture_pct <= 19.0:
        return 1.0
    if moisture_pct <= 30.0:
        return 0.85
    return 0.85


def _temp_ct(temperature_c: float) -> float:
    """NDS temperature factor Ct: 1.0 at or below 100 F (37.8 C)."""
    if temperature_c <= 37.8:
        return 1.0
    # Elevated-temperature reduction (NDS Table 2.3.3), linearized for 100-200 F.
    t_f = temperature_c * 9.0 / 5.0 + 32.0
    if t_f <= 100.0:
        return 1.0
    if t_f <= 150.0:
        return 0.85
    if t_f <= 200.0:
        return 0.70
    return 0.60


def _size_cf(depth_mm: float) -> float:
    """NDS size factor CF for bending (sawn lumber): CF = (3.0/d_in)^(1/9) for 2 < d_in < 15."""
    d_in = depth_mm / MM_PER_INCH
    if d_in <= 2.0 or d_in >= 15.0:
        return 1.0
    return (3.0 / d_in) ** (1.0 / 9.0)


def _beam_stability_cl(fbb: float, e_mpa: float, depth_mm: float, le_mm: float) -> float:
    """NDS beam stability factor CL (Section 3.7.4).

    fbb is the adjusted bending stress excluding CL (Fb * CD * CM * Ct * CF).
    le_mm is the effective unbraced length of the compression flange (mm).
    Returns 1.0 when fully braced (le_mm <= 0).
    """
    if le_mm <= 0.0 or fbb <= 0.0:
        return 1.0
    rb = 12.0 * fbb * depth_mm / (le_mm**2)
    fbe = 0.74 * e_mpa * (depth_mm / le_mm) ** 2
    if rb >= 1.0:
        return 0.0
    ratio = fbe / fbb
    if ratio >= 1.0:
        return 0.0
    cl = math.sqrt(rb / (1.0 - rb)) * math.sqrt(1.0 - ratio**2)
    return min(1.0, cl)


def design_timber_beam(inputs: TimberBeamInputs) -> dict:
    """Design a rectangular timber beam (flexure, shear, stability, deflection) per NDS (ASD)."""
    warnings: list[str] = []

    if inputs.species not in SPECIES:
        raise ValueError(f"Unknown species '{inputs.species}'. Available: {', '.join(SPECIES)}")

    ref = SPECIES[inputs.species]
    fb = ref["Fb_psi"] * PSI_TO_MPA
    fv = ref["Fv_psi"] * PSI_TO_MPA
    e_min = ref["E_psi"] * PSI_TO_MPA

    b = inputs.width_mm
    d = inputs.depth_mm
    a = b * d  # mm^2
    s = b * d**2 / 6.0  # mm^3
    i = b * d**3 / 12.0  # mm^4

    cd = _duration_cd(inputs.duration)
    cm = _wet_cm(inputs.moisture_pct)
    ct = _temp_ct(inputs.temperature_c)
    cf = _size_cf(d)

    # Adjusted bending stress excluding CL (used inside the CL formula).
    fbb = fb * cd * cm * ct * cf
    cl = _beam_stability_cl(fbb, e_min, d, inputs.unbraced_length_m * 1000.0)
    fb_adj = fbb * cl
    fv_adj = fv * cd * cm * ct
    e_adj = e_min * ct  # modulus is not duration-adjusted

    if cl < 1.0:
        warnings.append(
            f"Beam stability governs: CL = {cl:.3f} for unbraced length "
            f"{inputs.unbraced_length_m:.2f} m. Add lateral bracing to increase capacity."
        )

    # Flexure (ASD): f_b = M / S  <=  Fb'
    m_nmm = inputs.moment_kn_m * 1e6  # N-mm
    f_b = m_nmm / s  # MPa
    flex_util = f_b / fb_adj if fb_adj > 0 else float("inf")
    mn_kn_m = fb_adj * s / 1e6  # nominal (allowable) moment capacity

    # Shear (ASD): f_v = 1.5 V / A  <=  Fv'
    v_n = inputs.shear_kn * 1000.0  # N
    f_v = 1.5 * v_n / a  # MPa
    shear_util = f_v / fv_adj if fv_adj > 0 else float("inf")
    vn_kn = fv_adj * a / 1.5 / 1000.0  # allowable shear capacity

    # Deflection (simply supported, uniform load): delta_total = 5 M L^2 / (48 E' I)
    l_mm = inputs.span_m * 1000.0
    delta_total_mm = (5.0 * m_nmm * l_mm**2) / (48.0 * e_adj * i) if e_adj * i > 0 else 0.0
    delta_ll_mm = delta_total_mm * inputs.live_load_fraction
    limit_total = l_mm / 240.0
    limit_ll = l_mm / 360.0
    defl_total_ok = delta_total_mm <= limit_total
    defl_ll_ok = delta_ll_mm <= limit_ll
    if not defl_total_ok:
        warnings.append(f"Total deflection {delta_total_mm:.2f} mm exceeds L/240 = {limit_total:.2f} mm. Increase depth.")
    if not defl_ll_ok:
        warnings.append(f"Live-load deflection {delta_ll_mm:.2f} mm exceeds L/360 = {limit_ll:.2f} mm. Increase depth.")

    governs = "flexure"
    max_util = flex_util
    if shear_util > max_util:
        governs, max_util = "shear", shear_util
    if not defl_total_ok and (limit_total / delta_total_mm if delta_total_mm > 0 else float("inf")) > max_util:
        governs = "deflection"

    return {
        "method": "NDS 2024 timber beam design (ASD: flexure, shear, stability, deflection)",
        "code_reference": "NDS 2024 Section 3.7; Supplement Table 4A",
        "inputs": {
            "species": inputs.species,
            "width_mm": inputs.width_mm,
            "depth_mm": inputs.depth_mm,
            "moment_kn_m": inputs.moment_kn_m,
            "shear_kn": inputs.shear_kn,
            "span_m": inputs.span_m,
            "unbraced_length_m": inputs.unbraced_length_m,
            "duration": inputs.duration,
            "moisture_pct": inputs.moisture_pct,
            "temperature_c": inputs.temperature_c,
            "live_load_fraction": inputs.live_load_fraction,
        },
        "section": {
            "area_mm2": round(a, 1),
            "section_modulus_mm3": round(s, 1),
            "moment_of_inertia_mm4": round(i, 1),
        },
        "reference_values_mpa": {"Fb": round(fb, 3), "Fv": round(fv, 3), "E_min": round(e_min, 1)},
        "adjustment_factors": {
            "CD": cd,
            "CM": cm,
            "Ct": ct,
            "CF": round(cf, 4),
            "CL": round(cl, 4),
        },
        "adjusted_values_mpa": {
            "Fb_adj": round(fb_adj, 3),
            "Fv_adj": round(fv_adj, 3),
            "E_adj": round(e_adj, 1),
        },
        "flexure": {
            "f_b_mpa": round(f_b, 3),
            "Fb_adj_mpa": round(fb_adj, 3),
            "util": round(flex_util, 3),
            "allowable_moment_kn_m": round(mn_kn_m, 2),
            "ok": flex_util <= 1.0,
        },
        "shear": {
            "f_v_mpa": round(f_v, 3),
            "Fv_adj_mpa": round(fv_adj, 3),
            "util": round(shear_util, 3),
            "allowable_shear_kn": round(vn_kn, 2),
            "ok": shear_util <= 1.0,
        },
        "deflection": {
            "delta_total_mm": round(delta_total_mm, 3),
            "delta_live_mm": round(delta_ll_mm, 3),
            "limit_total_mm": round(limit_total, 3),
            "limit_live_mm": round(limit_ll, 3),
            "total_ok": defl_total_ok,
            "live_ok": defl_ll_ok,
        },
        "governs": governs,
        "max_util": round(max_util, 3),
        "pass": flex_util <= 1.0 and shear_util <= 1.0 and defl_total_ok and defl_ll_ok,
        "warnings": warnings,
    }
