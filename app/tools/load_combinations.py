from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LoadCombination:
    """ASCE 7 load combination definition."""
    name: str
    description: str
    dl_factor: float = 1.0  # Dead load factor
    ll_factor: float = 0.0  # Live load factor
    wl_factor: float = 0.0  # Wind load factor
    sl_factor: float = 0.0  # Snow load factor
    el_factor: float = 0.0  # Earthquake load factor


# ASCE 7-22 LRFD load combinations
ASCE7_LRFD_COMBINATIONS = [
    LoadCombination(
        name="1.4D",
        description="1.4D - Dead load only",
        dl_factor=1.4,
    ),
    LoadCombination(
        name="1.2D+1.6L+0.5(Lr or S or R)",
        description="1.2D + 1.6L + 0.5(Lr or S or R)",
        dl_factor=1.2,
        ll_factor=1.6,
        sl_factor=0.5,
    ),
    LoadCombination(
        name="1.2D+1.6(Lr or S or R)+{(L or 0.5W)}",
        description="1.2D + 1.6(Lr or S or R) + {(L or 0.5W)}",
        dl_factor=1.2,
        ll_factor=1.0,
        sl_factor=1.6,
        wl_factor=0.5,
    ),
    LoadCombination(
        name="1.2D+1.0W+L+0.5(Lr or S or R)",
        description="1.2D + 1.0W + L + 0.5(Lr or S or R)",
        dl_factor=1.2,
        ll_factor=1.0,
        wl_factor=1.0,
        sl_factor=0.5,
    ),
    LoadCombination(
        name="1.2D+1.0E+L+0.2S",
        description="1.2D + 1.0E + L + 0.2S",
        dl_factor=1.2,
        ll_factor=1.0,
        el_factor=1.0,
        sl_factor=0.2,
    ),
    LoadCombination(
        name="0.9D+1.0W",
        description="0.9D + 1.0W - Uplift/stability check",
        dl_factor=0.9,
        wl_factor=1.0,
    ),
    LoadCombination(
        name="0.9D+1.0E",
        description="0.9D + 1.0E - Uplift/stability check",
        dl_factor=0.9,
        el_factor=1.0,
    ),
]

# ASCE 7-22 ASD load combinations
ASCE7_ASD_COMBINATIONS = [
    LoadCombination(
        name="D",
        description="D - Dead load only",
        dl_factor=1.0,
    ),
    LoadCombination(
        name="D+L",
        description="D + L",
        dl_factor=1.0,
        ll_factor=1.0,
    ),
    LoadCombination(
        name="D+(Lr or S or R)",
        description="D + (Lr or S or R)",
        dl_factor=1.0,
        sl_factor=1.0,
    ),
    LoadCombination(
        name="D+0.75L+0.75(Lr or S or R)",
        description="D + 0.75L + 0.75(Lr or S or R)",
        dl_factor=1.0,
        ll_factor=0.75,
        sl_factor=0.75,
    ),
    LoadCombination(
        name="D+0.6W",
        description="D + 0.6W",
        dl_factor=1.0,
        wl_factor=0.6,
    ),
    LoadCombination(
        name="D+0.75L+0.75(Lr or S or R)+0.6W",
        description="D + 0.75L + 0.75(Lr or S or R) + 0.6W",
        dl_factor=1.0,
        ll_factor=0.75,
        sl_factor=0.75,
        wl_factor=0.6,
    ),
    LoadCombination(
        name="0.6D+0.6W",
        description="0.6D + 0.6W - Uplift/stability check",
        dl_factor=0.6,
        wl_factor=0.6,
    ),
    LoadCombination(
        name="0.6D+0.7E",
        description="0.6D + 0.7E - Uplift/stability check",
        dl_factor=0.6,
        el_factor=0.7,
    ),
]


def apply_load_combination(
    dl_kn: float = 0.0,
    ll_kn: float = 0.0,
    wl_kn: float = 0.0,
    sl_kn: float = 0.0,
    el_kn: float = 0.0,
    combination: LoadCombination | None = None,
) -> dict:
    """Apply a load combination to individual load components.
    
    Returns the factored load and combination details.
    """
    if combination is None:
        return {
            "factored_load_kn": dl_kn + ll_kn + wl_kn + sl_kn + el_kn,
            "combination": "unfactored",
            "description": "Unfactored load sum",
            "dl_kn": dl_kn,
            "ll_kn": ll_kn,
            "wl_kn": wl_kn,
            "sl_kn": sl_kn,
            "el_kn": el_kn,
        }

    factored_dl = dl_kn * combination.dl_factor
    factored_ll = ll_kn * combination.ll_factor
    factored_wl = wl_kn * combination.wl_factor
    factored_sl = sl_kn * combination.sl_factor
    factored_el = el_kn * combination.el_factor

    factored_total = factored_dl + factored_ll + factored_wl + factored_sl + factored_el

    return {
        "factored_load_kn": round(factored_total, 4),
        "combination": combination.name,
        "description": combination.description,
        "dl_kn": round(factored_dl, 4),
        "ll_kn": round(factored_ll, 4),
        "wl_kn": round(factored_wl, 4),
        "sl_kn": round(factored_sl, 4),
        "el_kn": round(factored_el, 4),
    }


def run_all_load_combinations(
    dl_kn: float = 0.0,
    ll_kn: float = 0.0,
    wl_kn: float = 0.0,
    sl_kn: float = 0.0,
    el_kn: float = 0.0,
    method: str = "lrfd",
) -> list[dict]:
    """Run all load combinations for given load components.
    
    Args:
        dl_kn: Dead load (kN)
        ll_kn: Live load (kN)
        wl_kn: Wind load (kN)
        sl_kn: Snow load (kN)
        el_kn: Earthquake load (kN)
        method: 'lrfd' or 'asd'
    
    Returns:
        List of combination results with factored loads.
    """
    combinations = ASCE7_LRFD_COMBINATIONS if method == "lrfd" else ASCE7_ASD_COMBINATIONS

    results = []
    for combo in combinations:
        result = apply_load_combination(
            dl_kn=dl_kn,
            ll_kn=ll_kn,
            wl_kn=wl_kn,
            sl_kn=sl_kn,
            el_kn=el_kn,
            combination=combo,
        )
        results.append(result)

    return results


def get_controlling_combination(
    dl_kn: float = 0.0,
    ll_kn: float = 0.0,
    wl_kn: float = 0.0,
    sl_kn: float = 0.0,
    el_kn: float = 0.0,
    method: str = "lrfd",
    maximize: bool = True,
) -> dict:
    """Find the controlling (maximum absolute) load combination.
    
    Args:
        dl_kn: Dead load (kN)
        ll_kn: Live load (kN)
        wl_kn: Wind load (kN)
        sl_kn: Snow load (kN)
        el_kn: Earthquake load (kN)
        method: 'lrfd' or 'asd'
        maximize: If True, find maximum absolute value. If False, find maximum positive value.
    
    Returns:
        The controlling combination result.
    """
    all_combos = run_all_load_combinations(
        dl_kn=dl_kn,
        ll_kn=ll_kn,
        wl_kn=wl_kn,
        sl_kn=sl_kn,
        el_kn=el_kn,
        method=method,
    )

    if not all_combos:
        return {"factored_load_kn": 0.0, "combination": "none", "description": "No combinations"}

    if maximize:
        controlling = max(all_combos, key=lambda x: abs(x["factored_load_kn"]))
    else:
        controlling = max(all_combos, key=lambda x: x["factored_load_kn"])

    return controlling
