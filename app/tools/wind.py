"""ASCE 7-22 wind load determination (simplified procedure).

Deterministic closed-form calculations. No LLM involvement.

References:
- ASCE 7-22, Section 26 (Wind Loads)
- Velocity pressure: qz = 0.613 * G * Kz * Kzt * Kd * Ke * V^2  (N/m^2, V in m/s)
- Exposure coefficients Kz per ASCE 7-22 Table 26.11-1 (power law, z in m)
- MWFRS external pressures per ASCE 7-22 Section 26.7-26.8
"""
from __future__ import annotations

from app.models import WindInputs

# Gust effect factor (ASCE 7-22, Eq. 26.7-1)
GUST_EFFECT_FACTOR = 0.85

# Directionality factor (ASCE 7-22, Table 26.6-1)
DIRECTIONALITY_FACTOR = 0.85

# Air density factor (ASCE 7-22, Eq. 26.3-1) -- default 1.0
AIR_DENSITY_FACTOR = 1.0

# Exposure coefficients: Kz = (z/9.144)^[2*alpha] for 9.144 m <= z <= 195.1 m
# alpha values per ASCE 7-22 Table 26.11-1 (z in meters)
EXPOSURE_ALPHA = {
    "A": 0.61,
    "B": 0.55,
    "C": 0.49,
    "D": 0.37,
}

# Internal pressure coefficients (ASCE 7-22, Table 26.13-1)
INTERNAL_PRESSURE_COEFFICIENTS = {
    "no_openings": -0.18,
    "minor_openings": -0.18,
    "major_openings": 0.18,
    "all_openings": 0.00,
}

# Height lower bound for Kz power law (m)
KZ_MIN_HEIGHT_M = 9.144


def _velocity_pressure(
    z_m: float,
    v_ms: float,
    exposure: str,
    kzt: float = 1.0,
    kd: float = 1.0,
    ke: float = 1.0,
) -> float:
    """Velocity pressure qz in kPa at height z (m). ASCE 7-22 Eq. 26.3-1."""
    alpha = EXPOSURE_ALPHA[exposure]
    z_eff = max(z_m, KZ_MIN_HEIGHT_M)
    kz = (z_eff / 9.144) ** (2.0 * alpha)
    qz = 0.613 * GUST_EFFECT_FACTOR * kz * kzt * kd * ke * (v_ms ** 2) / 1000.0
    return qz


def _windward_cp(length_m: float) -> float:
    """Windward wall external pressure coefficient (ASCE 7-22, Fig. 26.7-1)."""
    if length_m <= 9.14:
        return 0.80
    if length_m <= 18.29:
        return 0.70
    if length_m <= 30.48:
        return 0.60
    if length_m <= 45.72:
        return 0.50
    return 0.40


def _leeward_cp(length_m: float) -> float:
    """Leeward wall external pressure coefficient (ASCE 7-22, Fig. 26.8-1)."""
    if length_m <= 9.14:
        return -0.50
    if length_m <= 18.29:
        return -0.40
    if length_m <= 30.48:
        return -0.30
    if length_m <= 45.72:
        return -0.20
    return -0.10


def _roof_cp(length_m: float, width_m: float) -> float:
    """Roof external pressure coefficient (ASCE 7-22, Fig. 26.7-3, simplified).

    Uses the average of the negative-zone pressures for a flat roof.
    """
    x_over_l = min(length_m, width_m) / max(length_m, width_m)
    if x_over_l <= 0.1:
        return -0.80
    if x_over_l <= 0.2:
        return -0.70
    if x_over_l <= 0.4:
        return -0.60
    if x_over_l <= 0.8:
        return -0.50
    return -0.40


def calculate_wind_loads(inputs: WindInputs) -> dict:
    """Compute ASCE 7-22 wind pressures and forces (simplified procedure).

    Returns:
        dict with velocity pressures, MWFRS pressures, and total base shear
        in each principal direction. All forces in kN, pressures in kPa.
    """
    warnings: list[str] = []

    if inputs.basic_wind_speed_ms <= 0:
        warnings.append("Basic wind speed must be positive.")
    if inputs.height_m <= 0:
        warnings.append("Building height must be positive.")

    gc = DIRECTIONALITY_FACTOR
    ki = INTERNAL_PRESSURE_COEFFICIENTS.get(inputs.internal_pressure, -0.18)

    # Velocity pressure at key heights (m)
    heights = [3.0, 6.0, 9.144, 15.0, 24.0, 36.0, 48.0, 60.0, 90.0, 120.0]
    heights = [h for h in heights if h <= max(inputs.height_m, KZ_MIN_HEIGHT_M)]
    if inputs.height_m not in heights:
        heights.append(inputs.height_m)
    heights = sorted(set(heights))

    velocity_pressures = {
        f"z_{h:g}m": round(_velocity_pressure(h, inputs.basic_wind_speed_ms, inputs.exposure), 4)
        for h in heights
    }

    # MWFRS pressures at each height (kPa)
    cp_w = _windward_cp(inputs.length_m)
    cp_l = _leeward_cp(inputs.length_m)
    cp_r = _roof_cp(inputs.length_m, inputs.width_m)

    mwfrs_pressures: list[dict] = []
    for h in heights:
        qz = _velocity_pressure(h, inputs.basic_wind_speed_ms, inputs.exposure)
        mwfrs_pressures.append({
            "z_m": round(h, 3),
            "qz_kpa": round(qz, 4),
            "windward_kpa": round(gc * (cp_w * qz - ki * qz), 4),
            "leeward_kpa": round(gc * (cp_l * qz - ki * qz), 4),
            "roof_kpa": round(gc * (cp_r * qz - ki * qz), 4),
        })

    # Total base shear (kN) using average pressure over wall height
    q_avg = _velocity_pressure(inputs.height_m / 2.0, inputs.basic_wind_speed_ms, inputs.exposure)
    p_windward = gc * (cp_w * q_avg - ki * q_avg)
    p_leeward = gc * (cp_l * q_avg - ki * q_avg)

    # Force on windward + leeward walls (perpendicular to wind direction)
    wall_area = inputs.length_m * inputs.height_m
    base_shear_x = abs(p_windward) * wall_area + abs(p_leeward) * wall_area

    # Wind in Y direction (width is the windward face)
    cp_w_y = _windward_cp(inputs.width_m)
    cp_l_y = _leeward_cp(inputs.width_m)
    q_avg_y = _velocity_pressure(inputs.height_m / 2.0, inputs.basic_wind_speed_ms, inputs.exposure)
    p_windward_y = gc * (cp_w_y * q_avg_y - ki * q_avg_y)
    p_leeward_y = gc * (cp_l_y * q_avg_y - ki * q_avg_y)
    wall_area_y = inputs.width_m * inputs.height_m
    base_shear_y = abs(p_windward_y) * wall_area_y + abs(p_leeward_y) * wall_area_y

    # Roof suction (uplift)
    q_roof = _velocity_pressure(inputs.height_m, inputs.basic_wind_speed_ms, inputs.exposure)
    p_roof = gc * (cp_r * q_roof - ki * q_roof)
    roof_uplift = abs(p_roof) * inputs.length_m * inputs.width_m

    # Story forces (triangular distribution approximation)
    story_forces = []
    n_stories = max(1, int(inputs.height_m / inputs.story_height_m))
    for i in range(1, n_stories + 1):
        z_top = i * inputs.story_height_m
        z_bot = (i - 1) * inputs.story_height_m
        q_top = _velocity_pressure(z_top, inputs.basic_wind_speed_ms, inputs.exposure)
        q_bot = _velocity_pressure(z_bot, inputs.basic_wind_speed_ms, inputs.exposure)
        q_story = (q_top + q_bot) / 2.0
        p_story = gc * (cp_w * q_story - ki * q_story)
        f_story = abs(p_story) * inputs.length_m * inputs.story_height_m
        story_forces.append({
            "story": i,
            "z_m": round(z_top, 3),
            "qz_kpa": round(q_story, 4),
            "force_kn": round(f_story, 2),
        })

    return {
        "method": "ASCE 7-22 simplified procedure (MWFRS)",
        "code_reference": "ASCE 7-22 Section 26",
        "inputs": {
            "basic_wind_speed_ms": inputs.basic_wind_speed_ms,
            "exposure": inputs.exposure,
            "height_m": inputs.height_m,
            "length_m": inputs.length_m,
            "width_m": inputs.width_m,
            "internal_pressure": inputs.internal_pressure,
        },
        "factors": {
            "gust_effect_G": GUST_EFFECT_FACTOR,
            "directionality_Kd": DIRECTIONALITY_FACTOR,
            "internal_pressure_ki": ki,
            "cp_windward": cp_w,
            "cp_leeward": cp_l,
            "cp_roof": cp_r,
        },
        "velocity_pressures_kpa": velocity_pressures,
        "mwfrs_pressures": mwfrs_pressures,
        "base_shear_x_kn": round(base_shear_x, 2),
        "base_shear_y_kn": round(base_shear_y, 2),
        "roof_uplift_kn": round(roof_uplift, 2),
        "story_forces": story_forces,
        "warnings": warnings,
    }
