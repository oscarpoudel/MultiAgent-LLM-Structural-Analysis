"""Apply wind/seismic story forces to a drawn 3D model as nodal loads.

Deterministic mapping. No LLM involvement.

The wind and seismic tools emit story forces as a list of
``{story, z_m, force_kn}`` (lateral force at elevation ``z_m``). This module
maps those forces onto the nodes of a drawn 3D model:

- Each story force is assigned to the model level (elevation) nearest to
  its ``z_m``.
- Within a level the force is distributed either equally to all nodes at
  that elevation (``distribution="equal"``) or to the windward face only
  (``distribution="windward"``: the face with the minimum coordinate along
  the force direction).
- Existing nodal loads are preserved; new loads carry the given load case.
"""
from __future__ import annotations

from app.models import Load3D, Structure3DInputs

_ELEVATION_TOL_M = 1e-6


def _nearest_elevation(z_m: float, elevations: list[float]) -> float:
    return min(elevations, key=lambda e: (abs(e - z_m), e))


def apply_story_forces(
    inputs: Structure3DInputs,
    story_forces: list[dict],
    *,
    case: str = "W",
    direction: str = "x",
    distribution: str = "equal",
) -> dict:
    """Return an augmented copy of ``inputs`` with story forces as nodal loads.

    Args:
        inputs: The drawn 3D structure.
        story_forces: List of ``{"z_m": float, "force_kn": float}`` (extra
            keys such as ``story`` are ignored).
        case: Load case name for the new nodal loads (e.g. "W", "EQ").
        direction: Lateral direction of the forces, "x" or "y".
        distribution: "equal" (all nodes at the level) or "windward"
            (nodes on the face with the minimum coordinate along ``direction``).

    Returns:
        dict with:
        - "inputs": the augmented Structure3DInputs
        - "applied": per-story assignment summary
        - "warnings": list of notes
    """
    if direction not in ("x", "y"):
        raise ValueError("direction must be 'x' or 'y'")
    if distribution not in ("equal", "windward"):
        raise ValueError("distribution must be 'equal' or 'windward'")

    augmented = inputs.model_copy(deep=True)
    warnings: list[str] = []

    if not story_forces or not inputs.nodes:
        return {"inputs": augmented, "applied": [], "warnings": warnings}

    elevations = sorted({round(node.z, 9) for node in inputs.nodes})
    nodes_by_elevation: dict[float, list] = {}
    for node in inputs.nodes:
        nodes_by_elevation.setdefault(round(node.z, 9), []).append(node)

    coord = "x" if direction == "x" else "y"
    new_loads: list[Load3D] = []
    applied: list[dict] = []

    for sf in story_forces:
        z_m = float(sf["z_m"])
        force_kn = float(sf["force_kn"])
        if force_kn == 0.0:
            continue

        elevation = _nearest_elevation(z_m, elevations)
        level_nodes = nodes_by_elevation[elevation]

        if distribution == "windward":
            min_coord = min(getattr(node, coord) for node in level_nodes)
            target_nodes = [
                node for node in level_nodes
                if abs(getattr(node, coord) - min_coord) < _ELEVATION_TOL_M
            ]
        else:
            target_nodes = level_nodes

        share = force_kn / len(target_nodes)
        for node in target_nodes:
            if direction == "x":
                new_loads.append(Load3D(node_id=node.id, case=case, fx_kn=share))
            else:
                new_loads.append(Load3D(node_id=node.id, case=case, fy_kn=share))

        entry = {
            "z_m": z_m,
            "force_kn": round(force_kn, 4),
            "assigned_elevation_m": elevation,
            "num_nodes": len(target_nodes),
            "force_per_node_kn": round(share, 4),
        }
        if "story" in sf:
            entry["story"] = sf["story"]
        applied.append(entry)

        if abs(z_m - elevation) > 2.5:
            warnings.append(
                f"Story force at z={z_m:g} m is far from the nearest model "
                f"level ({elevation:g} m); it was assigned to that level."
            )

    augmented.nodal_loads.extend(new_loads)
    return {"inputs": augmented, "applied": applied, "warnings": warnings}
