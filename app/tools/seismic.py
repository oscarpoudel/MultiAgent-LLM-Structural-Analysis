"""ASCE 7-22 seismic base shear (equivalent static force procedure).

Deterministic closed-form calculations. No LLM involvement.

References:
- ASCE 7-22, Section 11 (Seismic Design Requirements)
- ASCE 7-22, Section 12.8 (Equivalent Lateral Force System)

Procedure:
1. Ss = (2/3) * Sa(0.2s); S1 = (2/3) * Sa(1s)
2. Site coefficients Fa, Fv by bilinear interpolation (Tables 11.4-1/2)
3. SDS = Fa * Ss; SD1 = Fv * S1
4. Ts = SDS / SD1
5. Period T (given, or T = Ca*Tu)
6. Cs = SDS/(R/Ie), bounded
7. V = Cs * W
8. Story forces by vertical distribution
"""
from __future__ import annotations

from app.models import SeismicInputs

# Site coefficients Fa (ASCE 7-22 Table 11.4-1)
# Ss breakpoints and Fa per site class
_SS_BREAKS = [0.00, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00, 1.25, 1.50, 2.00, 2.50, 3.00]
_FA = {
    "A": [0.80] * 15,
    "B": [1.00] * 15,
    "C": [1.60, 1.45, 1.35, 1.25, 1.15, 1.05, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00],
    "D": [1.70, 1.55, 1.45, 1.35, 1.25, 1.15, 1.10, 1.05, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00],
    "E": [1.90, 1.70, 1.55, 1.45, 1.35, 1.25, 1.20, 1.15, 1.10, 1.05, 1.00, 1.00, 1.00, 1.00, 1.00],
    "F": [2.00, 1.80, 1.65, 1.55, 1.45, 1.35, 1.30, 1.25, 1.20, 1.15, 1.10, 1.05, 1.00, 1.00, 1.00],
}

# Site coefficients Fv (ASCE 7-22 Table 11.4-2)
_S1_BREAKS = [0.00, 0.10, 0.20, 0.30, 0.40, 0.50]
_FV = {
    "A": [0.70] * 6,
    "B": [1.00] * 6,
    "C": [1.70, 1.60, 1.50, 1.40, 1.30, 1.20],
    "D": [1.90, 1.80, 1.70, 1.60, 1.50, 1.40],
    "E": [2.10, 2.00, 1.90, 1.80, 1.70, 1.60],
    "F": [2.40, 2.30, 2.20, 2.10, 2.00, 1.90],
}

# Importance factor Ie (ASCE 7-22 Table 1.5-1)
IMPORTANCE_FACTORS = {"I": 1.0, "II": 1.0, "III": 1.25, "IV": 1.5}

# Structural system: (R, Cd) defaults (ASCE 7-22 Table 12.2-1)
STRUCTURAL_SYSTEMS = {
    "moment_frame": (8.0, 5.5),
    "braced_frame": (6.0, 4.0),
    "shear_wall": (8.0, 5.0),
    "dual_system": (7.0, 4.5),
}


def _interp(x: float, breaks: list[float], values: list[float]) -> float:
    """Bilinear interpolation; clamps outside range."""
    if x <= breaks[0]:
        return values[0]
    if x >= breaks[-1]:
        return values[-1]
    for i in range(len(breaks) - 1):
        if breaks[i] <= x <= breaks[i + 1]:
            f = (x - breaks[i]) / (breaks[i + 1] - breaks[i])
            return values[i] + f * (values[i + 1] - values[i])
    return values[-1]


def calculate_seismic_base_shear(inputs: SeismicInputs) -> dict:
    """Compute ASCE 7-22 equivalent static force base shear and story forces."""
    warnings: list[str] = []

    ss = (2.0 / 3.0) * inputs.spectral_accel_sd
    s1 = (2.0 / 3.0) * inputs.spectral_accel_1s

    if inputs.site_class not in _FA:
        warnings.append(f"Unknown site class '{inputs.site_class}', defaulting to D.")
        site = "D"
    else:
        site = inputs.site_class

    fa = _interp(ss, _SS_BREAKS, _FA[site])
    fv = _interp(s1, _S1_BREAKS, _FV[site])

    sds = fa * ss
    sd1 = fv * s1
    ts = sds / sd1 if sd1 > 0 else 0.0

    ie = IMPORTANCE_FACTORS.get(inputs.risk_category, 1.0)
    if inputs.importance_factor is not None:
        ie = inputs.importance_factor

    r, cd = STRUCTURAL_SYSTEMS.get(inputs.structural_system, (8.0, 5.5))
    if inputs.response_modification is not None:
        r = inputs.response_modification
    if inputs.deflection_amplifier is not None:
        cd = inputs.deflection_amplifier

    # Period
    if inputs.fundamental_period_s is not None:
        t = inputs.fundamental_period_s
        period_method = "user_provided"
    else:
        # Tu = 0.09 * Ts * sqrt(h_roof / SDS)  (SI, Eq. 12.8-1)
        import math
        tu = 0.09 * ts * math.sqrt(inputs.height_m / sds) if sds > 0 else 0.0
        # Ca = SDS / (1 + (7T/Ts - 1)) for T >= Ts else SDS
        if ts > 0 and tu >= ts:
            ca = sds / (1.0 + (7.0 * tu / ts - 1.0))
        else:
            ca = sds
        t = ca * tu
        period_method = "estimated (Ca*Tu, Eq. 12.8-1..3)"

    # Cs
    cs = sds / (r / ie)
    cs_upper = sd1 / (r / ie)
    cs = min(cs, cs_upper)
    if ss >= 0.6:
        cs_lower = 0.044 * sds * ie
    else:
        cs_lower = 0.016 * sds * ie
    cs = max(cs, cs_lower)

    v = cs * inputs.building_weight_kn

    # Story forces: Fx = Cvx * V, Cvx = wx*zx^k / sum(wx*zx^k), k=0.5 if T<0.5s else 1.0
    k = 0.5 if t < 0.5 else 1.0
    n_stories = max(1, int(inputs.height_m / 4.0))
    story_height = inputs.height_m / n_stories
    stories = []
    wx_zk = []
    for i in range(1, n_stories + 1):
        zx = i * story_height
        wx = inputs.building_weight_kn / n_stories
        wx_zk.append(wx * (zx ** k))
    total = sum(wx_zk)
    for i in range(1, n_stories + 1):
        zx = i * story_height
        wx = inputs.building_weight_kn / n_stories
        cvx = (wx * (zx ** k)) / total if total > 0 else 0.0
        fx = cvx * v
        stories.append({
            "story": i,
            "z_m": round(zx, 3),
            "wx_kn": round(wx, 2),
            "cvx": round(cvx, 4),
            "force_kn": round(fx, 2),
        })

    # Drift check (simplified): delta = V * h^3 / (12 * E * I) not available; use empirical
    # Max story drift estimate = (V/n_stories) * story_height / (W/n_stories) * Cd
    drift_ratio = (cs * cd) if cs > 0 else 0.0

    return {
        "method": "ASCE 7-22 equivalent static force procedure",
        "code_reference": "ASCE 7-22 Sections 11, 12.8",
        "inputs": {
            "sa_0p2s_g": inputs.spectral_accel_sd,
            "sa_1s_g": inputs.spectral_accel_1s,
            "site_class": site,
            "risk_category": inputs.risk_category,
            "building_weight_kn": inputs.building_weight_kn,
            "structural_system": inputs.structural_system,
        },
        "site_coefficients": {
            "ss": round(ss, 4),
            "s1": round(s1, 4),
            "fa": round(fa, 4),
            "fv": round(fv, 4),
            "sds": round(sds, 4),
            "sd1": round(sd1, 4),
            "ts": round(ts, 4),
        },
        "design_params": {
            "ie": ie,
            "r": r,
            "cd": cd,
            "period_s": round(t, 4),
            "period_method": period_method,
            "cs": round(cs, 4),
            "cs_lower_bound": round(cs_lower, 4),
            "cs_upper_bound": round(cs_upper, 4),
        },
        "base_shear_kn": round(v, 2),
        "story_forces": stories,
        "estimated_drift_factor": round(drift_ratio, 4),
        "warnings": warnings,
    }
