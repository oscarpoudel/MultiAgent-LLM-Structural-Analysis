"""Two-way slab analysis (ACI 318, coefficient method).

Deterministic closed-form calculations. No LLM involvement.

References:
- ACI 318-19, Section 13 (One- and Two-Way Slabs)
- ACI 318-19, Section 9 (Reinforced Concrete)
- Minimum thickness: ACI 318 Table 13.3.1
- Moment coefficients: standard two-way slab coefficient tables
"""
from __future__ import annotations

from app.models import SlabInputs

# Moment coefficients for two-way slabs (midspan), l = ly/lx (ly >= lx)
# Continuous slab (all four edges continuous)
_CONTINUOUS_MX = [(1.0, 0.033), (1.2, 0.036), (1.4, 0.038), (1.5, 0.039), (2.0, 0.043), (3.0, 0.046), (4.0, 0.047), (5.0, 0.048)]
_CONTINUOUS_MY = [(1.0, 0.033), (1.2, 0.031), (1.4, 0.029), (1.5, 0.028), (2.0, 0.024), (3.0, 0.020), (4.0, 0.017), (5.0, 0.015)]
# Simply supported slab (all edges simply supported)
_SIMPLE_MX = [(1.0, 0.048), (1.2, 0.050), (1.4, 0.051), (1.5, 0.051), (2.0, 0.052), (3.0, 0.052), (4.0, 0.052), (5.0, 0.052)]
_SIMPLE_MY = [(1.0, 0.048), (1.2, 0.045), (1.4, 0.042), (1.5, 0.041), (2.0, 0.036), (3.0, 0.028), (4.0, 0.022), (5.0, 0.015)]

# Minimum thickness ratios (ACI 318 Table 13.3.1), L = short clear span
_MIN_THICKNESS_RATIO = {
    "continuous": 24.0,
    "simply_supported": 20.0,
}

# Effective depth assumptions (m)
COVER_M = 0.025
BAR_DIA_M = 0.012


def _interp_coeff(l: float, table: list[tuple[float, float]]) -> float:
    """Linear interpolation of moment coefficient by span ratio l."""
    if l <= table[0][0]:
        return table[0][1]
    if l >= table[-1][0]:
        return table[-1][1]
    for i in range(len(table) - 1):
        l0, c0 = table[i]
        l1, c1 = table[i + 1]
        if l0 <= l <= l1:
            f = (l - l0) / (l1 - l0)
            return c0 + f * (c1 - c0)
    return table[-1][1]


def _design_reinforcement(
    moment_kn_m: float,
    b_m: float,
    d_m: float,
    fck_mpa: float,
    fy_mpa: float,
) -> dict:
    """Rectangular section flexural design (ACI 318). Returns required As and rho."""
    phi = 0.9
    # Rn = Mu / (phi * b * d^2)  (in MPa)
    mu_nmm2 = moment_kn_m * 1e6  # N-mm
    rn = mu_nmm2 / (phi * (b_m * 1000.0) * (d_m * 1000.0) ** 2)
    # rho = (0.85*fck/fy) * (1 - sqrt(1 - 2*Rn/(0.85*fck)))
    term = 1.0 - (2.0 * rn / (0.85 * fck_mpa))
    if term < 0.0:
        rho = 0.0
        ok = False
    else:
        rho = (0.85 * fck_mpa / fy_mpa) * (1.0 - term ** 0.5)
        ok = True
    # Limits
    rho_min = max(0.25 * (200.0 ** 0.5) / fy_mpa, 0.0018)
    rho_max = 0.75 * 0.85 * fck_mpa / fy_mpa * (0.003 / (0.003 + fy_mpa / (200.0e3)))
    rho_design = max(rho, rho_min) if ok else rho
    as_req = rho_design * b_m * d_m  # m^2
    return {
        "required_as_m2": round(as_req, 6),
        "rho": round(rho, 5),
        "rho_min": round(rho_min, 5),
        "rho_max": round(rho_max, 5),
        "rho_ok": ok,
        "rn_mpa": round(rn, 3),
    }


def calculate_slab(inputs: SlabInputs) -> dict:
    """Two-way slab analysis per ACI 318 (coefficient method)."""
    warnings: list[str] = []

    lx = min(inputs.span_x_m, inputs.span_y_m)
    ly = max(inputs.span_x_m, inputs.span_y_m)
    l_ratio = ly / lx if lx > 0 else 1.0

    # Factored load (kPa)
    wu = 1.2 * inputs.dead_load_kpa + 1.6 * inputs.live_load_kpa

    # Minimum thickness (ACI 318 Table 13.3.1)
    ratio = _MIN_THICKNESS_RATIO.get(inputs.support_condition, 20.0)
    h_min = lx / ratio
    thickness_ok = inputs.thickness_m >= h_min
    if not thickness_ok:
        warnings.append(
            f"Slab thickness {inputs.thickness_m:.3f} m is below minimum {h_min:.3f} m (L/{ratio:.0f})."
        )

    # Effective depth
    d = inputs.thickness_m - COVER_M - BAR_DIA_M / 2.0
    if d <= 0:
        warnings.append("Effective depth is non-positive; increase slab thickness.")
        d = max(d, 0.01)

    # Moment coefficients
    if inputs.support_condition == "continuous":
        cx = _interp_coeff(l_ratio, _CONTINUOUS_MX)
        cy = _interp_coeff(l_ratio, _CONTINUOUS_MY)
    else:
        cx = _interp_coeff(l_ratio, _SIMPLE_MX)
        cy = _interp_coeff(l_ratio, _SIMPLE_MY)

    # Design moments (kN-m per m width)
    mx = cx * wu * lx ** 2
    my = cy * wu * lx ** 2

    # Reinforcement design (per meter width, b = 1.0 m)
    b = 1.0
    rx = _design_reinforcement(mx, b, d, inputs.concrete_fck_mpa, inputs.steel_fy_mpa)
    ry = _design_reinforcement(my, b, d, inputs.concrete_fck_mpa, inputs.steel_fy_mpa)

    # Bar spacing suggestion (12mm bars, As per bar = 1.131e-4 m^2)
    as_bar = 1.131e-4
    sx = 1.0 * as_bar / rx["required_as_m2"] * 1000.0 if rx["required_as_m2"] > 0 else 0.0
    sy = 1.0 * as_bar / ry["required_as_m2"] * 1000.0 if ry["required_as_m2"] > 0 else 0.0
    sx = min(sx, 300.0) if sx > 0 else 0.0
    sy = min(sy, 300.0) if sy > 0 else 0.0

    # Deflection estimate (conservative: short span as simply supported beam)
    # Units: w in kN/m, L in m, E in kN/m^2 (1 MPa = 1000 kN/m^2), I in m^4 -> delta in m
    e_concrete = 4700.0 * (inputs.concrete_fck_mpa ** 0.5)  # MPa (ACI 318)
    e_kn_m2 = e_concrete * 1000.0  # kN/m^2
    i_slab = (1.0 * inputs.thickness_m ** 3) / 12.0  # m^4 per m width
    wu_kn_m = wu * 1.0  # kN/m per m width
    delta_mm = 5.0 * wu_kn_m * (lx ** 4) / (384.0 * e_kn_m2 * i_slab) * 1000.0
    delta_limit_mm = lx * 1000.0 / inputs.deflection_limit_ratio
    deflection_ok = delta_mm <= delta_limit_mm
    if not deflection_ok:
        warnings.append(
            f"Estimated deflection {delta_mm:.1f} mm exceeds limit {delta_limit_mm:.1f} mm (L/{inputs.deflection_limit_ratio:.0f})."
        )

    # Two-way action check
    two_way = l_ratio < 2.0
    if not two_way:
        warnings.append("Span ratio >= 2.0; slab behaves as one-way in the short direction.")

    return {
        "method": "ACI 318 two-way slab (coefficient method)",
        "code_reference": "ACI 318-19 Sections 9, 13",
        "inputs": {
            "span_x_m": inputs.span_x_m,
            "span_y_m": inputs.span_y_m,
            "thickness_m": inputs.thickness_m,
            "dead_load_kpa": inputs.dead_load_kpa,
            "live_load_kpa": inputs.live_load_kpa,
            "concrete_fck_mpa": inputs.concrete_fck_mpa,
            "steel_fy_mpa": inputs.steel_fy_mpa,
            "support_condition": inputs.support_condition,
        },
        "span_ratio": round(l_ratio, 3),
        "two_way_action": two_way,
        "factored_load_kpa": round(wu, 3),
        "minimum_thickness_m": round(h_min, 4),
        "thickness_ok": thickness_ok,
        "effective_depth_m": round(d, 4),
        "moment_coefficients": {"cx": round(cx, 4), "cy": round(cy, 4)},
        "design_moments_kn_m": {"short_span": round(mx, 3), "long_span": round(my, 3)},
        "reinforcement_short_span": {**rx, "suggested_spacing_mm": round(sx, 1)},
        "reinforcement_long_span": {**ry, "suggested_spacing_mm": round(sy, 1)},
        "deflection": {
            "estimated_mm": round(delta_mm, 2),
            "limit_mm": round(delta_limit_mm, 2),
            "ok": deflection_ok,
        },
        "warnings": warnings,
    }
