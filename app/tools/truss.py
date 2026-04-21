from __future__ import annotations

import math

from app.models import TrussInputs


def analyze_truss(inputs: TrussInputs) -> dict:
    """2D truss analysis using OpenSeesPy or direct stiffness method fallback."""
    try:
        return _analyze_truss_opensees(inputs)
    except Exception as e:
        return _analyze_truss_direct_stiffness(inputs, fallback_reason=str(e))


def _analyze_truss_opensees(inputs: TrussInputs) -> dict:
    """OpenSeesPy 2D truss analysis."""
    try:
        import openseespy.opensees as ops
    except ImportError as error:
        raise RuntimeError(f"OpenSeesPy not available: {error}") from error

    ops.wipe()
    try:
        ops.model("basic", "-ndm", 2, "-ndf", 2)

        # Create nodes
        for node in inputs.nodes:
            ops.node(node.id, node.x, node.y)

        # Boundary conditions
        for node in inputs.nodes:
            if node.support == "pin":
                ops.fix(node.id, 1, 1)
            elif node.support == "roller_x":
                ops.fix(node.id, 0, 1)
            elif node.support == "roller_y":
                ops.fix(node.id, 1, 0)
            elif node.support == "fixed":
                ops.fix(node.id, 1, 1)

        # Create truss elements
        for i, member in enumerate(inputs.members):
            e_pa = member.elastic_modulus_gpa * 1e9
            mat_tag = i + 1
            ops.uniaxialMaterial("Elastic", mat_tag, e_pa)
            ops.element("Truss", member.id, member.start_node, member.end_node, member.area_m2, mat_tag)

        # Apply loads
        ops.timeSeries("Linear", 1)
        ops.pattern("Plain", 1, 1)
        for load in inputs.loads:
            ops.load(load.node_id, load.fx_kn * 1_000.0, load.fy_kn * 1_000.0)

        # Solve
        ops.system("BandGeneral")
        ops.numberer("RCM")
        ops.constraints("Plain")
        ops.integrator("LoadControl", 1.0)
        ops.algorithm("Linear")
        ops.analysis("Static")
        status = ops.analyze(1)
        ops.reactions()

        # Extract nodal displacements
        node_displacements = {}
        max_displacement_mm = 0.0
        for node in inputs.nodes:
            dx = ops.nodeDisp(node.id, 1) * 1_000.0
            dy = ops.nodeDisp(node.id, 2) * 1_000.0
            total = math.sqrt(dx**2 + dy**2)
            node_displacements[str(node.id)] = {
                "dx_mm": round(dx, 4),
                "dy_mm": round(dy, 4),
                "total_mm": round(total, 4),
            }
            if total > max_displacement_mm:
                max_displacement_mm = total

        # Extract reactions
        reactions = {}
        for node in inputs.nodes:
            if node.support != "free":
                rx = ops.nodeReaction(node.id, 1) / 1_000.0
                ry = ops.nodeReaction(node.id, 2) / 1_000.0
                reactions[str(node.id)] = {
                    "rx_kn": round(rx, 4),
                    "ry_kn": round(ry, 4),
                }

        # Extract member forces (axial)
        member_forces = {}
        for member in inputs.members:
            forces = ops.eleForce(member.id)
            # For truss: forces = [fx1, fy1, fx2, fy2]
            # Axial force magnitude
            n1 = inputs.nodes[0]  # placeholder
            n2 = inputs.nodes[0]
            for n in inputs.nodes:
                if n.id == member.start_node:
                    n1 = n
                if n.id == member.end_node:
                    n2 = n
            dx = n2.x - n1.x
            dy = n2.y - n1.y
            length = math.sqrt(dx**2 + dy**2)
            cos_a = dx / length if length > 0 else 0
            sin_a = dy / length if length > 0 else 0
            # Project local force
            axial_n = forces[0] * cos_a + forces[1] * sin_a
            axial_kn = axial_n / 1_000.0

            member_forces[str(member.id)] = {
                "axial_kn": round(axial_kn, 4),
                "length_m": round(length, 4),
                "tension_or_compression": "tension" if axial_kn > 0.001 else ("compression" if axial_kn < -0.001 else "zero"),
            }

    finally:
        ops.wipe()

    return {
        "solver": "openseespy_truss",
        "opensees_status": status,
        "num_nodes": len(inputs.nodes),
        "num_members": len(inputs.members),
        "num_loads": len(inputs.loads),
        "max_displacement_mm": round(max_displacement_mm, 4),
        "node_displacements": node_displacements,
        "reactions": reactions,
        "member_forces": member_forces,
        "is_finite": True,
    }


def _analyze_truss_direct_stiffness(inputs: TrussInputs, fallback_reason: str = "") -> dict:
    """Direct stiffness method fallback for 2D truss analysis."""
    import numpy as np

    nodes = {n.id: (n.x, n.y) for n in inputs.nodes}
    n_nodes = len(inputs.nodes)
    n_dof = 2 * n_nodes
    node_ids = [n.id for n in inputs.nodes]
    id_to_idx = {nid: i for i, nid in enumerate(node_ids)}

    # Global stiffness matrix
    K = np.zeros((n_dof, n_dof))

    member_data = []
    for member in inputs.members:
        i = id_to_idx[member.start_node]
        j = id_to_idx[member.end_node]
        x1, y1 = nodes[member.start_node]
        x2, y2 = nodes[member.end_node]
        dx = x2 - x1
        dy = y2 - y1
        L = math.sqrt(dx**2 + dy**2)
        c = dx / L
        s = dy / L
        e_pa = member.elastic_modulus_gpa * 1e9
        k_local = e_pa * member.area_m2 / L

        # Element stiffness in global coords
        ke = k_local * np.array([
            [c*c,  c*s, -c*c, -c*s],
            [c*s,  s*s, -c*s, -s*s],
            [-c*c, -c*s, c*c,  c*s],
            [-c*s, -s*s, c*s,  s*s],
        ])

        dofs = [2*i, 2*i+1, 2*j, 2*j+1]
        for a in range(4):
            for b in range(4):
                K[dofs[a], dofs[b]] += ke[a, b]

        member_data.append({
            "member": member,
            "i": i, "j": j,
            "L": L, "c": c, "s": s,
        })

    # Force vector
    F = np.zeros(n_dof)
    for load in inputs.loads:
        idx = id_to_idx[load.node_id]
        F[2*idx] += load.fx_kn * 1_000.0
        F[2*idx + 1] += load.fy_kn * 1_000.0

    # Apply boundary conditions (penalty method)
    penalty = 1e20
    for node in inputs.nodes:
        idx = id_to_idx[node.id]
        if node.support == "pin" or node.support == "fixed":
            K[2*idx, 2*idx] += penalty
            K[2*idx+1, 2*idx+1] += penalty
        elif node.support == "roller_x":
            K[2*idx+1, 2*idx+1] += penalty
        elif node.support == "roller_y":
            K[2*idx, 2*idx] += penalty

    # Solve
    try:
        U = np.linalg.solve(K, F)
    except np.linalg.LinAlgError:
        return {
            "solver": "direct_stiffness_truss_failed",
            "solver_warning": "Singular stiffness matrix - check supports and connectivity",
            "is_finite": False,
        }

    # Extract results
    node_displacements = {}
    max_displacement_mm = 0.0
    for node in inputs.nodes:
        idx = id_to_idx[node.id]
        dx_mm = U[2*idx] * 1_000.0
        dy_mm = U[2*idx+1] * 1_000.0
        total = math.sqrt(dx_mm**2 + dy_mm**2)
        node_displacements[str(node.id)] = {
            "dx_mm": round(dx_mm, 4),
            "dy_mm": round(dy_mm, 4),
            "total_mm": round(total, 4),
        }
        if total > max_displacement_mm:
            max_displacement_mm = total

    # Reactions
    reactions = {}
    for node in inputs.nodes:
        if node.support != "free":
            idx = id_to_idx[node.id]
            # R = K_orig * U - F (but we used penalty, so R ≈ penalty * U for constrained DOFs)
            rx = 0.0
            ry = 0.0
            if node.support in ("pin", "fixed"):
                rx = penalty * U[2*idx] / 1_000.0
                ry = penalty * U[2*idx+1] / 1_000.0
            elif node.support == "roller_x":
                ry = penalty * U[2*idx+1] / 1_000.0
            elif node.support == "roller_y":
                rx = penalty * U[2*idx] / 1_000.0
            reactions[str(node.id)] = {
                "rx_kn": round(rx, 4),
                "ry_kn": round(ry, 4),
            }

    # Member forces
    member_forces = {}
    for md in member_data:
        i = md["i"]
        j = md["j"]
        c = md["c"]
        s = md["s"]
        L = md["L"]
        m = md["member"]
        e_pa = m.elastic_modulus_gpa * 1e9

        u = np.array([U[2*i], U[2*i+1], U[2*j], U[2*j+1]])
        # Axial deformation
        delta = (-c * u[0] - s * u[1] + c * u[2] + s * u[3])
        axial_n = e_pa * m.area_m2 / L * delta
        axial_kn = axial_n / 1_000.0

        member_forces[str(m.id)] = {
            "axial_kn": round(axial_kn, 4),
            "length_m": round(L, 4),
            "tension_or_compression": "tension" if axial_kn > 0.001 else ("compression" if axial_kn < -0.001 else "zero"),
        }

    return {
        "solver": "direct_stiffness_truss",
        "solver_warning": fallback_reason if fallback_reason else None,
        "num_nodes": len(inputs.nodes),
        "num_members": len(inputs.members),
        "num_loads": len(inputs.loads),
        "max_displacement_mm": round(max_displacement_mm, 4),
        "node_displacements": node_displacements,
        "reactions": reactions,
        "member_forces": member_forces,
        "is_finite": all(math.isfinite(v) for v in U),
    }
