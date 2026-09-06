"""Multi-hazard load combination optimizer.

Deterministic evaluation of ASCE 7-22 load combinations against a member's
capacity. No LLM involvement.

The optimizer:
1. Evaluates every ASCE 7 combination for the given base hazard components
   (dead, live, wind, snow, earthquake) and computes the factored response
   (response = response_factor * factored_load) and its utilization
   (utilization = response / capacity).
2. Ranks the combinations by utilization and identifies the governing case.
3. Optionally sweeps each hazard component over a range (one-at-a-time) to find
   the worst-case load scenario that maximizes the governing utilization.

References:
- ASCE 7-22, Section 2.3 (Load Combinations)
"""
from __future__ import annotations

from app.models import MultiHazardInputs
from app.tools.load_combinations import (
    ASCE7_ASD_COMBINATIONS,
    ASCE7_LRFD_COMBINATIONS,
    apply_load_combination,
)

COMPONENTS = ("dl_kn", "ll_kn", "wl_kn", "sl_kn", "el_kn")


def _factored_loads(dl: float, ll: float, wl: float, sl: float, el: float, combo) -> dict:
    return apply_load_combination(dl_kn=dl, ll_kn=ll, wl_kn=wl, sl_kn=sl, el_kn=el, combination=combo)


def evaluate_combinations(
    dl_kn: float,
    ll_kn: float,
    wl_kn: float,
    sl_kn: float,
    el_kn: float,
    response_factor: float,
    capacity: float,
    method: str = "lrfd",
) -> dict:
    """Evaluate all combinations for the base case and rank by utilization."""
    combos = ASCE7_LRFD_COMBINATIONS if method == "lrfd" else ASCE7_ASD_COMBINATIONS
    rows = []
    for combo in combos:
        f = _factored_loads(dl_kn, ll_kn, wl_kn, sl_kn, el_kn, combo)
        response = response_factor * f["factored_load_kn"]
        util = response / capacity if capacity != 0 else float("inf")
        rows.append(
            {
                "combination": f["combination"],
                "description": f["description"],
                "factored_load_kn": f["factored_load_kn"],
                "response": round(response, 4),
                "utilization": round(util, 4),
                "ok": util <= 1.0,
            }
        )
    rows.sort(key=lambda r: abs(r["utilization"]), reverse=True)
    governing = rows[0]
    return {
        "combinations": rows,
        "governing": governing,
        "governing_utilization": governing["utilization"],
        "all_ok": all(r["ok"] for r in rows),
        "num_combinations": len(rows),
    }


def _sweep_component(
    key: str,
    lo: float,
    hi: float,
    base: dict,
    response_factor: float,
    capacity: float,
    method: str,
) -> dict:
    """Sweep one hazard component from lo to hi and find the worst-case value."""
    if lo > hi:
        lo, hi = hi, lo
    n = 7
    base_val = base[key]
    values = [lo + (hi - lo) * i / (n - 1) for i in range(n)]
    if not any(abs(v - base_val) < 1e-9 for v in values):
        values.append(base_val)
        values.sort()

    best = None
    sweep_rows = []
    for v in values:
        trial = dict(base)
        trial[key] = v
        ev = evaluate_combinations(
            trial["dl_kn"], trial["ll_kn"], trial["wl_kn"], trial["sl_kn"], trial["el_kn"],
            response_factor, capacity, method,
        )
        sweep_rows.append({"value": round(v, 4), "governing_utilization": ev["governing_utilization"]})
        if best is None or ev["governing_utilization"] > best["governing_utilization"]:
            best = {"value": round(v, 4), **ev}

    return {
        "sweep": sweep_rows,
        "worst_value": best["value"],
        "worst_utilization": best["governing_utilization"],
        "worst_combination": best["governing"]["combination"],
    }


def optimize_multi_hazard(inputs: MultiHazardInputs) -> dict:
    """Evaluate combinations for the base case and sweep each component for the worst case."""
    warnings: list[str] = []
    base = {
        "dl_kn": inputs.dead_load_kn,
        "ll_kn": inputs.live_load_kn,
        "wl_kn": inputs.wind_load_kn,
        "sl_kn": inputs.snow_load_kn,
        "el_kn": inputs.earthquake_load_kn,
    }
    method = inputs.method.lower()
    if method not in ("lrfd", "asd"):
        method = "lrfd"

    base_eval = evaluate_combinations(
        base["dl_kn"], base["ll_kn"], base["wl_kn"], base["sl_kn"], base["el_kn"],
        inputs.response_factor, inputs.capacity, method,
    )
    if not base_eval["all_ok"]:
        warnings.append(
            f"Base case is NOT safe: governing combination '{base_eval['governing']['combination']}' "
            f"has utilization {base_eval['governing_utilization']:.3f} > 1.0."
        )

    # Sweep each component over its range to find the worst-case scenario.
    ranges = {
        "dl_kn": (inputs.dead_min_kn, inputs.dead_max_kn),
        "ll_kn": (inputs.live_min_kn, inputs.live_max_kn),
        "wl_kn": (inputs.wind_min_kn, inputs.wind_max_kn),
        "sl_kn": (inputs.snow_min_kn, inputs.snow_max_kn),
        "el_kn": (inputs.earthquake_min_kn, inputs.earthquake_max_kn),
    }
    sweeps = {}
    for key in inputs.components:
        lo, hi = ranges[key]
        sweeps[key] = _sweep_component(key, lo, hi, base, inputs.response_factor, inputs.capacity, method)

    # Overall worst case: the component sweep that produced the highest utilization.
    worst_key = max(sweeps, key=lambda k: sweeps[k]["worst_utilization"])
    overall_worst = sweeps[worst_key]

    return {
        "method": f"ASCE 7-22 multi-hazard load combination optimizer ({method.upper()})",
        "code_reference": "ASCE 7-22 Section 2.3",
        "inputs": {
            **base,
            "response_factor": inputs.response_factor,
            "capacity": inputs.capacity,
            "method": method,
            "components": inputs.components,
        },
        "base_case": base_eval,
        "sweeps": sweeps,
        "overall_worst": {
            "component": worst_key,
            "value": overall_worst["worst_value"],
            "governing_utilization": overall_worst["worst_utilization"],
            "governing_combination": overall_worst["worst_combination"],
        },
        "warnings": warnings,
    }
