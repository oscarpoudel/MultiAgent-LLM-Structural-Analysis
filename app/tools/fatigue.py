"""Steel fatigue design (AISC 360 S-N curves).

Deterministic closed-form calculations. No LLM involvement.

References:
- AISC 360-16, Section 16 (Fatigue) and Table 16.5 (S-N Curve Coefficients)

For a fatigue category, the S-N curve is:
    N_f = C / f_f^3      for f_f > fatigue_limit
    infinite life        for f_f <= fatigue_limit
where f_f is the stress range (MPa) and N_f is the number of cycles to failure.

The design check compares the design number of cycles N against N_f:
    utilization = N / N_f   (<= 1.0 passes)
The allowable stress range for the design life is:
    f_allow = min(fatigue_limit, (C / N)^(1/3))
"""
from __future__ import annotations

import math

from app.models import FatigueInputs

# AISC 360-16 Table 16.5 (SI units): fatigue limit (MPa) and S-N coefficient C (MPa^3).
# Category A is the most fatigue-resistant detail; E the least.
FATIGUE_CATEGORIES: dict[str, dict[str, float]] = {
    "A": {"fatigue_limit_mpa": 162.0, "c_mpa3": 2.7e12, "description": "Details with no holes or slots (e.g. tension members, unnotched plates)"},
    "B": {"fatigue_limit_mpa": 121.0, "c_mpa3": 1.6e12, "description": "Welds to tension side of flange, fillet welds in tension"},
    "C": {"fatigue_limit_mpa": 90.0, "c_mpa3": 0.68e12, "description": "Welds to compression side of flange, coped beams, stiffened holes"},
    "D": {"fatigue_limit_mpa": 70.0, "c_mpa3": 0.27e12, "description": "Welded attachments, unstiffened holes, bolted splices"},
    "E": {"fatigue_limit_mpa": 48.0, "c_mpa3": 0.11e12, "description": "Most critical details (e.g. welded end connections, unstiffened welded holes)"},
}

CATEGORY_ORDER = ["A", "B", "C", "D", "E"]


def list_fatigue_categories() -> list[dict]:
    """Return the fatigue categories with their AISC 360 S-N parameters."""
    out = []
    for cat in CATEGORY_ORDER:
        vals = FATIGUE_CATEGORIES[cat]
        out.append(
            {
                "category": cat,
                "fatigue_limit_mpa": vals["fatigue_limit_mpa"],
                "c_mpa3": vals["c_mpa3"],
                "description": vals["description"],
            }
        )
    return out


def cycles_to_failure(stress_range_mpa: float, category: str) -> float:
    """Number of cycles to failure at the given stress range (inf if below the limit)."""
    vals = FATIGUE_CATEGORIES[category]
    limit = vals["fatigue_limit_mpa"]
    if stress_range_mpa <= limit:
        return float("inf")
    return vals["c_mpa3"] / stress_range_mpa**3


def allowable_stress_range(num_cycles: float, category: str) -> float:
    """Maximum stress range for the design life (capped at the fatigue limit)."""
    vals = FATIGUE_CATEGORIES[category]
    if num_cycles <= 0:
        return vals["fatigue_limit_mpa"]
    f = (vals["c_mpa3"] / num_cycles) ** (1.0 / 3.0)
    return min(vals["fatigue_limit_mpa"], f)


def check_fatigue(inputs: FatigueInputs) -> dict:
    """Check a fatigue detail against the AISC 360 S-N curve for the design life."""
    warnings: list[str] = []
    category = inputs.category.upper()
    if category not in FATIGUE_CATEGORIES:
        raise ValueError(f"Unknown fatigue category '{inputs.category}'. Available: A, B, C, D, E")

    f_f = inputs.stress_range_mpa
    n_design = inputs.num_cycles
    vals = FATIGUE_CATEGORIES[category]

    n_f = cycles_to_failure(f_f, category)
    infinite = math.isinf(n_f)
    utilization = 0.0 if infinite else n_design / n_f
    f_allow = allowable_stress_range(n_design, category)
    passes = infinite or utilization <= 1.0

    if f_f > vals["fatigue_limit_mpa"]:
        warnings.append(
            f"Stress range {f_f:.1f} MPa exceeds the category {category} fatigue limit "
            f"({vals['fatigue_limit_mpa']:.0f} MPa); finite-life S-N check applies."
        )
    if not passes:
        warnings.append(
            f"Fatigue check FAILS: {n_design:.2e} cycles demanded vs {n_f:.2e} cycles to failure "
            f"(utilization {utilization:.2f}). Reduce the stress range or use a higher category."
        )

    # Find the cheapest (highest-letter) category that still passes the design life.
    adequate = [c for c in CATEGORY_ORDER if (math.isinf(cycles_to_failure(f_f, c)) or n_design / cycles_to_failure(f_f, c) <= 1.0)]
    required_category = adequate[-1] if adequate else None
    if required_category is None:
        warnings.append("No fatigue category passes the design life at this stress range; the detail must be redesigned.")

    return {
        "method": "AISC 360-16 fatigue design (S-N curve, N = C/f^3)",
        "code_reference": "AISC 360-16 Section 16, Table 16.5",
        "inputs": {
            "category": category,
            "stress_range_mpa": f_f,
            "num_cycles": n_design,
        },
        "category_params": {
            "fatigue_limit_mpa": vals["fatigue_limit_mpa"],
            "c_mpa3": vals["c_mpa3"],
            "description": vals["description"],
        },
        "result": {
            "cycles_to_failure": None if infinite else round(n_f, 1),
            "infinite_life": infinite,
            "utilization": round(utilization, 4),
            "allowable_stress_range_mpa": round(f_allow, 3),
            "stress_range_util": round(f_f / f_allow, 4) if f_allow > 0 else None,
            "pass": passes,
        },
        "required_category": required_category,
        "warnings": warnings,
    }
