"""ASCE 7-22 snow load determination.

Deterministic closed-form calculations. No LLM involvement.

References:
- ASCE 7-22, Section 7 (Snow Loads)
- Ground snow load pg, roof snow load ps, drift, and sliding loads
"""
from __future__ import annotations

import math

from app.models import SnowInputs


def calculate_snow_loads(inputs: SnowInputs) -> dict:
    """Compute ASCE 7-22 roof snow loads (balanced + drift)."""
    warnings: list[str] = []

    if inputs.ground_snow_load_kpa < 0:
        warnings.append("Ground snow load must be non-negative.")

    # Exposure factor Ce (ASCE 7-22 Table 7.4-1)
    ce = {
        "exposed": 1.2,
        "partially_shielded": 1.0,
        "shielded": 0.8,
    }.get(inputs.exposure, 1.0)

    # Thermal factor Ct (ASCE 7-22 Table 7.5-1)
    ct = {
        "heated": 1.0,
        "unheated": 1.1,
    }.get(inputs.thermal, 1.0)

    # Importance factor Is (ASCE 7-22 Table 1.5-1)
    is_ = {
        "I": 0.80,
        "II": 0.80,
        "III": 0.95,
        "IV": 1.20,
    }.get(inputs.risk_category, 0.80)

    # Flat roof snow load ps (ASCE 7-22 Eq. 7.4-1)
    ps = 0.7 * ce * ct * is_ * inputs.ground_snow_load_kpa

    # Sloped roof snow load ps (ASCE 7-22 Eq. 7.5-1)
    # Cs = (0.5 / cos^2(theta)) for 0 <= theta <= 70 deg
    theta_rad = math.radians(inputs.roof_slope_deg)
    if inputs.roof_slope_deg <= 70.0:
        cs = 0.5 / (math.cos(theta_rad) ** 2)
    else:
        cs = 0.0
    ps_sloped = cs * ps

    # Balanced snow load
    balanced = max(ps, ps_sloped)

    # Drift load (simplified, ASCE 7-22 Section 7.6)
    # Drift height hd = min(hp, 0.4*(hp+152mm)) simplified
    # For a flat roof, drift = 0.5 * ps (simplified estimate)
    drift = 0.0
    if inputs.drift:
        drift = 0.5 * ps

    # Total design snow load
    total = balanced + drift

    return {
        "method": "ASCE 7-22 snow load determination",
        "code_reference": "ASCE 7-22 Section 7",
        "inputs": {
            "ground_snow_load_kpa": inputs.ground_snow_load_kpa,
            "exposure": inputs.exposure,
            "thermal": inputs.thermal,
            "risk_category": inputs.risk_category,
            "roof_slope_deg": inputs.roof_slope_deg,
            "drift": inputs.drift,
        },
        "factors": {
            "ce": ce,
            "ct": ct,
            "is": is_,
            "cs": round(cs, 4),
        },
        "flat_roof_ps_kpa": round(ps, 4),
        "sloped_roof_ps_kpa": round(ps_sloped, 4),
        "balanced_snow_kpa": round(balanced, 4),
        "drift_load_kpa": round(drift, 4),
        "total_design_snow_kpa": round(total, 4),
        "warnings": warnings,
    }
