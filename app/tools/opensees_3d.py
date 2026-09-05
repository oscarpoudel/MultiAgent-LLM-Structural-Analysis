from __future__ import annotations

import copy
from itertools import pairwise

from app.models import Structure3DInputs

_SUPPORT_PRESETS = {
    "roller": {"ux": False, "uy": False, "uz": True, "rx": False, "ry": False, "rz": False},
    "pin": {"ux": True, "uy": True, "uz": True, "rx": False, "ry": False, "rz": False},
    "fixed": {"ux": True, "uy": True, "uz": True, "rx": True, "ry": True, "rz": True},
}


def convert_3d_support_strings(model: dict) -> dict:
    """Convert canvas-style string supports ("free"/"roller"/"pin"/"fixed") to Support3D dicts."""
    model = copy.deepcopy(model)
    for node in model.get("nodes", []):
        support = node.get("support", "free")
        if isinstance(support, str):
            node["support"] = None if support == "free" else _SUPPORT_PRESETS.get(support, _SUPPORT_PRESETS["fixed"])
    return model


def _is_parallel(a: tuple[float, float, float], b: tuple[float, float, float]) -> bool:
    cx = a[1] * b[2] - a[2] * b[1]
    cy = a[2] * b[0] - a[0] * b[2]
    cz = a[0] * b[1] - a[1] * b[0]
    return (cx * cx + cy * cy + cz * cz) < 1e-12


def _member_axis(start, end) -> tuple[float, float, float]:
    dx = end.x - start.x
    dy = end.y - start.y
    dz = end.z - start.z
    length = (dx * dx + dy * dy + dz * dz) ** 0.5
    if length <= 1e-12:
        return (1.0, 0.0, 0.0)
    return (dx / length, dy / length, dz / length)


def _safe_vecxz(start, end) -> tuple[float, float, float]:
    axis = _member_axis(start, end)
    for candidate in ((0.0, 0.0, 1.0), (0.0, 1.0, 0.0), (1.0, 0.0, 0.0)):
        if not _is_parallel(axis, candidate):
            return candidate
    return (0.0, 0.0, 1.0)


def _story_response(inputs: Structure3DInputs, nodal_displacements: dict[int, list[float]]) -> dict:
    elevations = sorted({round(node.z, 9) for node in inputs.nodes})
    if not elevations:
        return {"levels": [], "story_drifts": []}

    levels = []
    nodes_by_elevation = {}
    for elevation in elevations:
        nodes_at_level = [node for node in inputs.nodes if abs(node.z - elevation) < 1e-6]
        nodes_by_elevation[elevation] = nodes_at_level
        ux_values = [nodal_displacements[node.id][0] for node in nodes_at_level if node.id in nodal_displacements]
        uy_values = [nodal_displacements[node.id][1] for node in nodes_at_level if node.id in nodal_displacements]
        resultant_values = [(ux * ux + uy * uy) ** 0.5 for ux, uy in zip(ux_values, uy_values, strict=True)]
        levels.append({
            "elevation_m": elevation,
            "avg_ux_mm": sum(ux_values) / len(ux_values) if ux_values else 0.0,
            "avg_uy_mm": sum(uy_values) / len(uy_values) if uy_values else 0.0,
            "max_ux_mm": max((abs(v) for v in ux_values), default=0.0),
            "max_uy_mm": max((abs(v) for v in uy_values), default=0.0),
            "max_lateral_mm": max(resultant_values, default=0.0),
        })

    story_drifts = []
    for lower, upper in pairwise(levels):
        height = upper["elevation_m"] - lower["elevation_m"]
        paired_drifts = []
        lower_nodes_by_xy = {
            (round(node.x, 6), round(node.y, 6)): node
            for node in nodes_by_elevation[lower["elevation_m"]]
            if node.id in nodal_displacements
        }
        for upper_node in nodes_by_elevation[upper["elevation_m"]]:
            lower_node = lower_nodes_by_xy.get((round(upper_node.x, 6), round(upper_node.y, 6)))
            if lower_node is None or upper_node.id not in nodal_displacements:
                continue
            upper_disp = nodal_displacements[upper_node.id]
            lower_disp = nodal_displacements[lower_node.id]
            dux = upper_disp[0] - lower_disp[0]
            duy = upper_disp[1] - lower_disp[1]
            paired_drifts.append((dux * dux + duy * duy) ** 0.5)

        if paired_drifts:
            drift = max(paired_drifts)
        else:
            dux = upper["avg_ux_mm"] - lower["avg_ux_mm"]
            duy = upper["avg_uy_mm"] - lower["avg_uy_mm"]
            drift = (dux * dux + duy * duy) ** 0.5
        story_drifts.append({
            "from_m": lower["elevation_m"],
            "to_m": upper["elevation_m"],
            "height_m": height,
            "drift_mm": drift,
            "drift_ratio": (height * 1000.0 / drift) if drift > 1e-9 else None,
            "drift_ratio_delta_over_h": drift / (height * 1000.0) if height > 0 else None,
        })

    return {"levels": levels, "story_drifts": story_drifts}


def _default_combinations(inputs: Structure3DInputs) -> list[dict]:
    if inputs.load_combinations:
        return [{"name": combo.name, "factors": combo.factors} for combo in inputs.load_combinations]

    cases = {load.case for load in inputs.nodal_loads} | {load.case for load in inputs.member_loads}
    if not cases:
        cases = {"D"}
    return [{"name": " + ".join(sorted(cases)), "factors": {case: 1.0 for case in cases}}]


def _apply_rigid_diaphragms(ops, inputs: Structure3DInputs) -> None:
    elevations = sorted({round(node.z, 9) for node in inputs.nodes})
    if len(elevations) <= 1:
        return

    base = elevations[0]
    for elevation in elevations:
        if abs(elevation - base) < 1e-6:
            continue
        level_nodes = [node for node in inputs.nodes if abs(node.z - elevation) < 1e-6]
        if len(level_nodes) <= 1:
            continue
        cx = sum(node.x for node in level_nodes) / len(level_nodes)
        cy = sum(node.y for node in level_nodes) / len(level_nodes)
        master = min(level_nodes, key=lambda node: (node.x - cx) ** 2 + (node.y - cy) ** 2)
        slaves = [node.id for node in level_nodes if node.id != master.id]
        if slaves:
            ops.rigidDiaphragm(3, master.id, *slaves)


def _run_static_combo(ops, inputs: Structure3DInputs, combo: dict) -> dict:
    ops.wipe()
    ops.model("basic", "-ndm", 3, "-ndf", 6)

    for node in inputs.nodes:
        ops.node(node.id, node.x, node.y, node.z)
        if node.support is not None:
            ops.fix(
                node.id,
                int(node.support.ux), int(node.support.uy), int(node.support.uz),
                int(node.support.rx), int(node.support.ry), int(node.support.rz),
            )

    if inputs.rigid_diaphragms:
        _apply_rigid_diaphragms(ops, inputs)

    nodes_by_id = {node.id: node for node in inputs.nodes}
    for member in inputs.members:
        e_pa = member.elastic_modulus_gpa * 1e9
        g_pa = member.shear_modulus_gpa * 1e9
        start_n = nodes_by_id.get(member.start_node)
        end_n = nodes_by_id.get(member.end_node)
        if start_n is None or end_n is None:
            continue

        transf_tag = member.id
        vecxz = _safe_vecxz(start_n, end_n)
        ops.geomTransf("Linear", transf_tag, *vecxz)
        ops.element(
            "elasticBeamColumn", member.id, member.start_node, member.end_node,
            member.area_m2, e_pa, g_pa, member.j_m4, member.iy_m4, member.iz_m4, transf_tag,
        )

    ops.timeSeries("Linear", 1)
    ops.pattern("Plain", 1, 1)
    factors = combo["factors"]

    for load in inputs.nodal_loads:
        factor = factors.get(load.case, 0.0)
        if abs(factor) < 1e-12:
            continue
        ops.load(
            load.node_id,
            load.fx_kn * factor * 1000.0,
            load.fy_kn * factor * 1000.0,
            load.fz_kn * factor * 1000.0,
            load.mx_kn_m * factor * 1000.0,
            load.my_kn_m * factor * 1000.0,
            load.mz_kn_m * factor * 1000.0,
        )

    for m_load in inputs.member_loads:
        factor = factors.get(m_load.case, 0.0)
        if abs(factor) < 1e-12:
            continue
        ops.eleLoad(
            "-ele", m_load.member_id, "-type", "-beamUniform",
            m_load.wy_kn_per_m * factor * 1000.0,
            m_load.wz_kn_per_m * factor * 1000.0,
        )

    ops.system("BandGeneral")
    ops.numberer("RCM")
    ops.constraints("Transformation" if inputs.rigid_diaphragms else "Plain")
    ops.integrator("LoadControl", 1.0)
    ops.algorithm("Linear")
    ops.analysis("Static")

    status = ops.analyze(1)
    ops.reactions()

    nodal_displacements = {}
    nodal_reactions = {}
    for node in inputs.nodes:
        nid = node.id
        disp = ops.nodeDisp(nid)
        nodal_displacements[nid] = [d * 1000.0 for d in disp[:3]] + disp[3:]
        if node.support is not None:
            react = ops.nodeReaction(nid)
            nodal_reactions[nid] = {
                "Fx_kn": react[0] / 1000.0,
                "Fy_kn": react[1] / 1000.0,
                "Fz_kn": react[2] / 1000.0,
                "Mx_kn_m": react[3] / 1000.0,
                "My_kn_m": react[4] / 1000.0,
                "Mz_kn_m": react[5] / 1000.0,
            }

    member_forces = {}
    member_force_summary = {}
    for member in inputs.members:
        mid = member.id
        forces = ops.eleForce(mid)
        member_forces[mid] = [f / 1000.0 for f in forces]
        member_force_summary[mid] = {
            "group": member.group,
            "max_abs_axial_kn": max(abs(forces[0]), abs(forces[6])) / 1000.0,
            "max_abs_shear_y_kn": max(abs(forces[1]), abs(forces[7])) / 1000.0,
            "max_abs_shear_z_kn": max(abs(forces[2]), abs(forces[8])) / 1000.0,
            "max_abs_torsion_kn_m": max(abs(forces[3]), abs(forces[9])) / 1000.0,
            "max_abs_moment_y_kn_m": max(abs(forces[4]), abs(forces[10])) / 1000.0,
            "max_abs_moment_z_kn_m": max(abs(forces[5]), abs(forces[11])) / 1000.0,
        }

    max_translation_mm = max(
        ((disp[0] ** 2 + disp[1] ** 2 + disp[2] ** 2) ** 0.5 for disp in nodal_displacements.values()),
        default=0.0,
    )
    base_reactions = {
        "Fx_kn": sum(reaction["Fx_kn"] for reaction in nodal_reactions.values()),
        "Fy_kn": sum(reaction["Fy_kn"] for reaction in nodal_reactions.values()),
        "Fz_kn": sum(reaction["Fz_kn"] for reaction in nodal_reactions.values()),
        "Mx_kn_m": sum(reaction["Mx_kn_m"] for reaction in nodal_reactions.values()),
        "My_kn_m": sum(reaction["My_kn_m"] for reaction in nodal_reactions.values()),
        "Mz_kn_m": sum(reaction["Mz_kn_m"] for reaction in nodal_reactions.values()),
    }

    return {
        "solver": "openseespy_3d_frame",
        "opensees_status": status,
        "load_combination": combo["name"],
        "load_factors": factors,
        "rigid_diaphragms": inputs.rigid_diaphragms,
        "num_nodes": len(inputs.nodes),
        "num_members": len(inputs.members),
        "displacements": nodal_displacements,
        "reactions": nodal_reactions,
        "base_reactions": base_reactions,
        "member_forces": member_forces,
        "member_force_summary": member_force_summary,
        "story_response": _story_response(inputs, nodal_displacements),
        "max_translation_mm": max_translation_mm,
        "geometry": {
            "nodes": [{"id": n.id, "x": n.x, "y": n.y, "z": n.z} for n in inputs.nodes],
            "members": [{"id": m.id, "start_node": m.start_node, "end_node": m.end_node, "group": m.group} for m in inputs.members],
        },
        "is_finite": status == 0,
    }


def analyze_3d_structure_opensees(inputs: Structure3DInputs) -> dict:
    """OpenSeesPy 3D structural analysis (ndm=3, ndf=6)."""
    try:
        import openseespy.opensees as ops
    except ImportError as e:
        return {
            "solver": "openseespy_3d_import_failed",
            "solver_warning": str(e),
            "status": "error"
        }

    try:
        combinations = _default_combinations(inputs)
        combo_results = {combo["name"]: _run_static_combo(ops, inputs, combo) for combo in combinations}
        active_name = inputs.active_load_combination if inputs.active_load_combination in combo_results else combinations[0]["name"]
        active_result = dict(combo_results[active_name])
        active_result["combination_results"] = combo_results
        active_result["available_combinations"] = [combo["name"] for combo in combinations]
        return active_result

    finally:
        ops.wipe()
