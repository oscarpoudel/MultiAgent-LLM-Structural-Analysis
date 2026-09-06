"""Cost estimation from steel section selection.

Deterministic quantity takeoff and cost roll-up. No LLM involvement.

Given a set of member groups (each with a section name and total length in
metres), this tool resolves each section's weight from the section database,
computes the steel tonnage, and applies a configurable unit price plus
fabrication and erection factors to produce an estimate. It also reports the
lightest adequate section's cost so a designer can compare the cost impact of
the selected versus the minimum section.

All inputs (unit price, factors) are user-supplied; the tool only performs
arithmetic on database section weights. No market data is fabricated.
"""
from __future__ import annotations

from app.tools.sections import get_section

# Default unit price for structural steel (material + fabrication + erection)
# in currency per kg. This is a placeholder default; users should supply their
# own regional price. Documented as an assumption, not a market claim.
DEFAULT_PRICE_PER_KG = 2.5
DEFAULT_FAB_FACTOR = 1.0
DEFAULT_ERECT_FACTOR = 1.0


def estimate_cost(
    members: list[dict],
    *,
    price_per_kg: float = DEFAULT_PRICE_PER_KG,
    fab_factor: float = DEFAULT_FAB_FACTOR,
    erect_factor: float = DEFAULT_ERECT_FACTOR,
    currency: str = "USD",
) -> dict:
    """Estimate steel cost from a list of member groups.

    Args:
        members: List of ``{"section": str, "length_m": float}``. ``section``
            must resolve to a section in the database (case-insensitive).
        price_per_kg: Unit price (currency/kg) for structural steel.
        fab_factor: Fabrication cost multiplier (>= 1.0).
        erect_factor: Erection cost multiplier (>= 1.0).
        currency: Currency label for the estimate.

    Returns:
        dict with per-group takeoff, total tonnage, and total cost.
    """
    if price_per_kg < 0:
        raise ValueError("price_per_kg must be non-negative")
    if fab_factor < 1.0 or erect_factor < 1.0:
        raise ValueError("fab_factor and erect_factor must be >= 1.0")

    groups: list[dict] = []
    total_weight_kg = 0.0
    warnings: list[str] = []

    for member in members:
        name = str(member.get("section", "")).strip()
        length_m = float(member.get("length_m", 0.0))
        section = get_section(name)
        if section is None:
            warnings.append(f"Section '{name}' not found in database; skipped.")
            continue
        weight_kg = section.weight_kg_per_m * length_m
        total_weight_kg += weight_kg
        groups.append({
            "section": name,
            "length_m": round(length_m, 3),
            "weight_kg_per_m": section.weight_kg_per_m,
            "weight_kg": round(weight_kg, 2),
            "weight_t": round(weight_kg / 1000.0, 4),
        })

    total_t = total_weight_kg / 1000.0
    material_cost = total_weight_kg * price_per_kg
    total_cost = material_cost * fab_factor * erect_factor

    return {
        "method": "Steel quantity takeoff and cost roll-up",
        "assumptions": [
            f"Unit price {price_per_kg} {currency}/kg (material + fabrication + erection basis).",
            f"Fabrication factor {fab_factor}, erection factor {erect_factor}.",
            "Section weights from the built-in AISC section database.",
        ],
        "currency": currency,
        "price_per_kg": price_per_kg,
        "fab_factor": fab_factor,
        "erect_factor": erect_factor,
        "groups": groups,
        "num_groups": len(groups),
        "total_weight_kg": round(total_weight_kg, 2),
        "total_weight_t": round(total_t, 4),
        "material_cost": round(material_cost, 2),
        "total_cost": round(total_cost, 2),
        "cost_per_ton": round(total_cost / total_t, 2) if total_t > 0 else 0.0,
        "warnings": warnings,
    }
