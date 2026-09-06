"""Sensitivity analysis: one-at-a-time (OAT) parametric study on a beam.

Deterministic closed-form calculations. No LLM involvement.

The study takes a base beam case (simply supported, uniform load) and sweeps
each selected parameter from its minimum to maximum while holding the others
at their base values. For every response (moment, deflection, stress) it
reports the swept values and an elasticity sensitivity coefficient:

    S_(p,r) = (dr/dp) * (p_base / r_base)

which is the percent change in response r per percent change in parameter p
(approximated by a central/finite difference over the sweep). A coefficient of
1.0 means a 1% change in p produces a 1% change in r.

References:
- Roark's Formulas for Stress and Strain (simply supported beam, uniform load)
- Standard elasticity (log-log) sensitivity definition
"""
from __future__ import annotations

import math

from app.models import SensitivityInputs

# Responses computed for a simply supported beam under uniform load w (kN/m):
#   M  = w L^2 / 8            (kN-m)
#   d  = 5 w L^4 / (384 E I)  (m)
#   s  = M / S                (kPa)


def _responses(w: float, L: float, E: float, I: float, S: float) -> dict:
    m = w * L**2 / 8.0  # kN-m
    d = (5.0 * w * L**4) / (384.0 * E * I) if E * I > 0 else 0.0  # m
    s = m / S if S > 0 else 0.0  # kPa
    return {"moment_kn_m": m, "deflection_m": d, "stress_kpa": s}


def _sweep_value(base: float, lo: float, hi: float) -> list[float]:
    """Build a monotonic sweep from lo to hi that always includes the base value."""
    if lo > hi:
        lo, hi = hi, lo
    if hi == lo:
        return [hi]
    n = 5
    values = [lo + (hi - lo) * i / (n - 1) for i in range(n)]
    # Insert the base value so the reference point is always evaluated.
    if not any(math.isclose(v, base, rel_tol=1e-9, abs_tol=1e-12) for v in values):
        values.append(base)
        values.sort()
    return values


def run_sensitivity(inputs: SensitivityInputs) -> dict:
    """Run an OAT parametric study and return swept responses + sensitivity coefficients."""
    warnings: list[str] = []

    base = {
        "w": inputs.load_kn_m,
        "L": inputs.span_m,
        "E": inputs.modulus_gpa * 1e6,  # GPa -> kPa (consistent with kN/m, m)
        "I": inputs.inertia_m4,
        "S": inputs.section_modulus_m3,
    }
    base_resp = _responses(base["w"], base["L"], base["E"], base["I"], base["S"])

    param_meta = {
        "w": ("load_kn_m", "w"),
        "L": ("span_m", "L"),
        "E": ("modulus_gpa", "E"),
        "I": ("inertia_m4", "I"),
        "S": ("section_modulus_m3", "S"),
    }

    # Map each requested parameter to its base/lo/hi (in the response units above).
    ranges = {
        "w": (inputs.load_kn_m, inputs.load_min_kn_m, inputs.load_max_kn_m),
        "L": (inputs.span_m, inputs.span_min_m, inputs.span_max_m),
        "E": (base["E"], inputs.modulus_min_gpa * 1e6, inputs.modulus_max_gpa * 1e6),
        "I": (inputs.inertia_m4, inputs.inertia_min_m4, inputs.inertia_max_m4),
        "S": (inputs.section_modulus_m3, inputs.section_min_m3, inputs.section_max_m3),
    }

    study: dict[str, dict] = {}
    for key in inputs.parameters:
        field, label = param_meta[key]
        base_val, lo, hi = ranges[key]
        sweep = _sweep_value(base_val, lo, hi)

        rows = []
        for v in sweep:
            trial = dict(base)
            trial[key] = v
            resp = _responses(trial["w"], trial["L"], trial["E"], trial["I"], trial["S"])
            rows.append({"param_value": round(v, 6), **{k: round(val, 6) for k, val in resp.items()}})

        # Elasticity (log-log) sensitivity at the base point:
        #   S = (d ln r / d ln p) = (dr/dp) * (p_base / r_base)
        # dr/dp is a central finite difference at the base value.
        coeffs: dict[str, float | None] = {}
        if base_val == 0:
            for rname in ("moment_kn_m", "deflection_m", "stress_kpa"):
                coeffs[rname] = None
        else:
            h = 0.01 * base_val  # 1% perturbation
            trial_p = dict(base)
            trial_p[key] = base_val + h
            resp_p = _responses(trial_p["w"], trial_p["L"], trial_p["E"], trial_p["I"], trial_p["S"])
            trial_m = dict(base)
            trial_m[key] = base_val - h
            resp_m = _responses(trial_m["w"], trial_m["L"], trial_m["E"], trial_m["I"], trial_m["S"])
            for rname in ("moment_kn_m", "deflection_m", "stress_kpa"):
                rb = base_resp[rname]
                if rb == 0:
                    coeffs[rname] = None
                    continue
                slope = (resp_p[rname] - resp_m[rname]) / (2.0 * h)  # dr/dp at base
                coeffs[rname] = round(slope * (base_val / rb), 4)

        study[field] = {
            "label": label,
            "base": round(base_val, 6),
            "min": round(lo, 6),
            "max": round(hi, 6),
            "sweep": rows,
            "sensitivity": coeffs,
        }

    # Rank parameters by their maximum |sensitivity| across responses.
    ranking = []
    for field, data in study.items():
        vals = [abs(v) for v in data["sensitivity"].values() if v is not None]
        ranking.append({"parameter": field, "max_abs_sensitivity": max(vals) if vals else 0.0})
    ranking.sort(key=lambda x: x["max_abs_sensitivity"], reverse=True)

    if not inputs.parameters:
        warnings.append("No parameters selected; returning the base case only.")

    return {
        "method": "One-at-a-time parametric study with elasticity sensitivity coefficients",
        "code_reference": "Roark's (simply supported beam, uniform load); elasticity sensitivity",
        "inputs": {
            "load_kn_m": inputs.load_kn_m,
            "span_m": inputs.span_m,
            "modulus_gpa": inputs.modulus_gpa,
            "inertia_m4": inputs.inertia_m4,
            "section_modulus_m3": inputs.section_modulus_m3,
            "parameters": inputs.parameters,
        },
        "base_response": {k: round(v, 6) for k, v in base_resp.items()},
        "study": study,
        "ranking": ranking,
        "warnings": warnings,
    }
