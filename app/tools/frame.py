from __future__ import annotations

import math

from app.models import FrameInputs


def analyze_frame(inputs: FrameInputs) -> dict:
    """2D frame analysis using OpenSeesPy or direct stiffness fallback."""
    try:
        return _analyze_frame_opensees(inputs)
    except Exception as e:
        return _analyze_frame_direct_stiffness(inputs, fallback_reason=str(e))


def _analyze_frame_opensees(inputs: FrameInputs) -> dict:
    """OpenSeesPy 2D frame analysis with beam-column elements."""
    try:
        import openseespy.opensees as ops
    except ImportError as error:
        raise RuntimeError(f"OpenSeesPy not available: {error}") from error

    ops.wipe()
    try:
        ops.model("basic", "-ndm", 2, "-ndf", 3)

        # Create nodes
        for node in inputs.nodes:
            ops.node(node.id, node.x, node.y)

        # Boundary conditions
        for node in inputs.nodes:
            if node.support == "pin":
                ops.fix(node.id, 1, 1, 0)
            elif node.support == "roller":
                ops.fix(node.id, 0, 1, 0)
            elif node.support == "fixed":
                ops.fix(node.id, 1, 1, 1)

        # Geometric transformation
        ops.geomTransf("Linear", 1)

        # Create frame elements
        for member in inputs.members:
            e_pa = member.elastic_modulus_gpa * 1e9
            ops.element(
                "elasticBeamColumn",
                member.id,
                member.start_node,
                member.end_node,
                member.area_m2,
                e_pa,
                member.inertia_m4,
                1,
            )

        # Apply loads
        ops.timeSeries("Linear", 1)
        ops.pattern("Plain", 1, 1)

        # Nodal loads
        for load in inputs.nodal_loads:
            ops.load(load.node_id, load.fx_kn * 1_000.0, load.fy_kn * 1_000.0, load.moment_kn_m * 1_000.0)

        # Member distributed loads
        for ml in inputs.member_loads:
            if ml.udl_kn_per_m != 0:
                ops.eleLoad("-ele", ml.member_id, "-type", "-beamUniform", -ml.udl_kn_per_m * 1_000.0)

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
        max_rotation_rad = 0.0
        for node in inputs.nodes:
            dx = ops.nodeDisp(node.id, 1) * 1_000.0
            dy = ops.nodeDisp(node.id, 2) * 1_000.0
            rz = ops.nodeDisp(node.id, 3)
            total = math.sqrt(dx**2 + dy**2)
            node_displacements[str(node.id)] = {
                "dx_mm": round(dx, 4),
                "dy_mm": round(dy, 4),
                "rotation_rad": round(rz, 6),
                "total_mm": round(total, 4),
            }
            if total > max_displacement_mm:
                max_displacement_mm = total
            if abs(rz) > max_rotation_rad:
                max_rotation_rad = abs(rz)

        # Extract reactions
        reactions = {}
        for node in inputs.nodes:
            if node.support != "free":
                rx = ops.nodeReaction(node.id, 1) / 1_000.0
                ry = ops.nodeReaction(node.id, 2) / 1_000.0
                mz = ops.nodeReaction(node.id, 3) / 1_000.0
                reactions[str(node.id)] = {
                    "rx_kn": round(rx, 4),
                    "ry_kn": round(ry, 4),
                    "mz_kn_m": round(mz, 4),
                }

        # Extract member end forces
        member_forces = {}
        for member in inputs.members:
            forces = ops.eleForce(member.id)
            # forces: [N1, V1, M1, N2, V2, M2] in local coordinates
            n1 = n2 = None
            for n in inputs.nodes:
                if n.id == member.start_node:
                    n1 = n
                if n.id == member.end_node:
                    n2 = n

            length = 0.0
            if n1 and n2:
                length = math.sqrt((n2.x - n1.x) ** 2 + (n2.y - n1.y) ** 2)

            member_forces[str(member.id)] = {
                "axial_start_kn": round(forces[0] / 1_000.0, 4),
                "shear_start_kn": round(forces[1] / 1_000.0, 4),
                "moment_start_kn_m": round(forces[2] / 1_000.0, 4),
                "axial_end_kn": round(forces[3] / 1_000.0, 4),
                "shear_end_kn": round(forces[4] / 1_000.0, 4),
                "moment_end_kn_m": round(forces[5] / 1_000.0, 4),
                "length_m": round(length, 4),
            }

    finally:
        ops.wipe()

    return {
        "solver": "openseespy_frame",
        "opensees_status": status,
        "num_nodes": len(inputs.nodes),
        "num_members": len(inputs.members),
        "num_nodal_loads": len(inputs.nodal_loads),
        "num_member_loads": len(inputs.member_loads),
        "max_displacement_mm": round(max_displacement_mm, 4),
        "max_rotation_rad": round(max_rotation_rad, 6),
        "node_displacements": node_displacements,
        "reactions": reactions,
        "member_forces": member_forces,
        "is_finite": True,
    }


def _analyze_frame_direct_stiffness(inputs: FrameInputs, fallback_reason: str = "") -> dict:
    """Direct stiffness method fallback for 2D frame analysis (3 DOF per node)."""
    import numpy as np

    nodes = {n.id: (n.x, n.y) for n in inputs.nodes}
    node_ids = [n.id for n in inputs.nodes]
    id_to_idx = {nid: i for i, nid in enumerate(node_ids)}
    n_nodes = len(node_ids)
    n_dof = 3 * n_nodes

    K = np.zeros((n_dof, n_dof))
    F = np.zeros(n_dof)

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
        A = member.area_m2
        I = member.inertia_m4

        EA_L = e_pa * A / L
        EI_L3 = e_pa * I / L**3
        EI_L2 = e_pa * I / L**2
        EI_L = e_pa * I / L

        # Local stiffness matrix for beam-column element
        k_local = np.array([
            [EA_L,    0,          0,        -EA_L,   0,          0       ],
            [0,       12*EI_L3,   6*EI_L2,  0,       -12*EI_L3,  6*EI_L2],
            [0,       6*EI_L2,    4*EI_L,   0,       -6*EI_L2,   2*EI_L ],
            [-EA_L,   0,          0,        EA_L,    0,          0       ],
            [0,       -12*EI_L3,  -6*EI_L2, 0,       12*EI_L3,   -6*EI_L2],
            [0,       6*EI_L2,    2*EI_L,   0,       -6*EI_L2,   4*EI_L ],
        ])

        # Transformation matrix
        T = np.array([
            [c,  s,  0,  0,  0,  0],
            [-s, c,  0,  0,  0,  0],
            [0,  0,  1,  0,  0,  0],
            [0,  0,  0,  c,  s,  0],
            [0,  0,  0,  -s, c,  0],
            [0,  0,  0,  0,  0,  1],
        ])

        k_global = T.T @ k_local @ T

        dofs = [3*i, 3*i+1, 3*i+2, 3*j, 3*j+1, 3*j+2]
        for a in range(6):
            for b in range(6):
                K[dofs[a], dofs[b]] += k_global[a, b]

        member_data.append({
            "member": member,
            "i": i, "j": j,
            "L": L, "c": c, "s": s,
            "T": T, "k_local": k_local,
        })

    # Apply nodal loads
    for load in inputs.nodal_loads:
        idx = id_to_idx[load.node_id]
        F[3*idx] += load.fx_kn * 1_000.0
        F[3*idx + 1] += load.fy_kn * 1_000.0
        F[3*idx + 2] += load.moment_kn_m * 1_000.0

    # Apply member loads as equivalent nodal loads
    for ml in inputs.member_loads:
        # Find the member
        for md in member_data:
            if md["member"].id == ml.member_id:
                L = md["L"]
                w_n = ml.udl_kn_per_m * 1_000.0
                c = md["c"]
                s = md["s"]
                i_idx = md["i"]
                j_idx = md["j"]

                # Fixed-end forces in local coords (vertical UDL)
                f_local = np.array([
                    0,
                    -w_n * L / 2.0,
                    -w_n * L**2 / 12.0,
                    0,
                    -w_n * L / 2.0,
                    w_n * L**2 / 12.0,
                ])

                # Transform to global
                T = md["T"]
                f_global = T.T @ f_local

                dofs = [3*i_idx, 3*i_idx+1, 3*i_idx+2, 3*j_idx, 3*j_idx+1, 3*j_idx+2]
                for a in range(6):
                    F[dofs[a]] += f_global[a]
                break

    # Boundary conditions (penalty method)
    penalty = 1e20
    for node in inputs.nodes:
        idx = id_to_idx[node.id]
        if node.support == "fixed":
            K[3*idx, 3*idx] += penalty
            K[3*idx+1, 3*idx+1] += penalty
            K[3*idx+2, 3*idx+2] += penalty
        elif node.support == "pin":
            K[3*idx, 3*idx] += penalty
            K[3*idx+1, 3*idx+1] += penalty
        elif node.support == "roller":
            K[3*idx+1, 3*idx+1] += penalty

    # Solve
    try:
        U = np.linalg.solve(K, F)
    except np.linalg.LinAlgError:
        return {
            "solver": "direct_stiffness_frame_failed",
            "solver_warning": "Singular stiffness matrix - check supports and connectivity",
            "is_finite": False,
        }

    # Extract results
    node_displacements = {}
    max_displacement_mm = 0.0
    max_rotation_rad = 0.0
    for node in inputs.nodes:
        idx = id_to_idx[node.id]
        dx_mm = U[3*idx] * 1_000.0
        dy_mm = U[3*idx + 1] * 1_000.0
        rz = U[3*idx + 2]
        total = math.sqrt(dx_mm**2 + dy_mm**2)
        node_displacements[str(node.id)] = {
            "dx_mm": round(dx_mm, 4),
            "dy_mm": round(dy_mm, 4),
            "rotation_rad": round(rz, 6),
            "total_mm": round(total, 4),
        }
        if total > max_displacement_mm:
            max_displacement_mm = total
        if abs(rz) > max_rotation_rad:
            max_rotation_rad = abs(rz)

    # Reactions
    reactions = {}
    for node in inputs.nodes:
        if node.support != "free":
            idx = id_to_idx[node.id]
            rx = ry = mz = 0.0
            if node.support in ("pin", "fixed"):
                rx = penalty * U[3*idx] / 1_000.0
                ry = penalty * U[3*idx+1] / 1_000.0
            elif node.support == "roller":
                ry = penalty * U[3*idx+1] / 1_000.0
            if node.support == "fixed":
                mz = penalty * U[3*idx+2] / 1_000.0
            reactions[str(node.id)] = {
                "rx_kn": round(rx, 4),
                "ry_kn": round(ry, 4),
                "mz_kn_m": round(mz, 4),
            }

    # Member forces
    member_forces = {}
    for md in member_data:
        i = md["i"]
        j = md["j"]
        T = md["T"]
        k_local = md["k_local"]
        m = md["member"]

        u_global = np.array([
            U[3*i], U[3*i+1], U[3*i+2],
            U[3*j], U[3*j+1], U[3*j+2],
        ])
        u_local = T @ u_global
        f_local = k_local @ u_local

        member_forces[str(m.id)] = {
            "axial_start_kn": round(f_local[0] / 1_000.0, 4),
            "shear_start_kn": round(f_local[1] / 1_000.0, 4),
            "moment_start_kn_m": round(f_local[2] / 1_000.0, 4),
            "axial_end_kn": round(f_local[3] / 1_000.0, 4),
            "shear_end_kn": round(f_local[4] / 1_000.0, 4),
            "moment_end_kn_m": round(f_local[5] / 1_000.0, 4),
            "length_m": round(md["L"], 4),
        }

    return {
        "solver": "direct_stiffness_frame",
        "solver_warning": fallback_reason if fallback_reason else None,
        "num_nodes": len(inputs.nodes),
        "num_members": len(inputs.members),
        "num_nodal_loads": len(inputs.nodal_loads),
        "num_member_loads": len(inputs.member_loads),
        "max_displacement_mm": round(max_displacement_mm, 4),
        "max_rotation_rad": round(max_rotation_rad, 6),
        "node_displacements": node_displacements,
        "reactions": reactions,
        "member_forces": member_forces,
        "is_finite": all(math.isfinite(v) for v in U),
    }
