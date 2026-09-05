"""Deterministic lumped-mass response-spectrum analysis for 3D building models.

The drawn frame is reduced to one lateral translation degree of freedom at
each elevated level. Story stiffness is assembled from vertical members, and
the seismic weight is distributed equally between elevated levels. This is a
transparent cantilever/shear-building idealization, not a full 3D modal FEM.

References:
- ASCE 7-22, Section 11.4.6 (design response spectrum)
- ASCE 7-22, Section 12.9 (modal response spectrum analysis)
"""
from __future__ import annotations

import math
from itertools import pairwise

import numpy as np

from app.models import Structure3DInputs

GRAVITY_M_S2 = 9.80665
_LEVEL_TOL_M = 1e-6


def design_spectral_acceleration(
    period_s: float,
    sds: float,
    sd1: float,
    *,
    long_period_s: float = 8.0,
) -> float:
    """Return the ASCE 7 design spectral acceleration ``Sa(T)`` in units of g."""
    if period_s < 0.0:
        raise ValueError("period_s must be nonnegative")
    if sds <= 0.0 or sd1 <= 0.0:
        raise ValueError("sds and sd1 must be positive")
    if long_period_s <= 0.0:
        raise ValueError("long_period_s must be positive")

    ts = sd1 / sds
    t0 = 0.2 * ts
    if period_s < t0:
        return sds * (0.4 + 0.6 * period_s / t0)
    if period_s <= ts:
        return sds
    if period_s <= long_period_s:
        return sd1 / period_s
    return sd1 * long_period_s / period_s**2


def _story_stiffnesses(inputs: Structure3DInputs, direction: str) -> tuple[list[float], list[float]]:
    elevations = sorted({round(node.z, 9) for node in inputs.nodes})
    if len(elevations) < 2:
        raise ValueError("At least two distinct elevation levels are required")

    nodes = {node.id: node for node in inputs.nodes}
    stiffnesses: list[float] = []
    coefficient = 12.0 if inputs.rigid_diaphragms else 3.0

    for lower, upper in pairwise(elevations):
        height = upper - lower
        stiffness = 0.0
        for member in inputs.members:
            start = nodes.get(member.start_node)
            end = nodes.get(member.end_node)
            if start is None or end is None:
                continue
            member_levels = sorted((start.z, end.z))
            connects_story = (
                abs(member_levels[0] - lower) <= _LEVEL_TOL_M
                and abs(member_levels[1] - upper) <= _LEVEL_TOL_M
            )
            if not connects_story:
                continue
            horizontal_offset = math.hypot(end.x - start.x, end.y - start.y)
            if horizontal_offset > max(height * 0.05, _LEVEL_TOL_M):
                continue

            inertia = member.iy_m4 if direction == "x" else member.iz_m4
            elastic_modulus_kn_m2 = member.elastic_modulus_gpa * 1e6
            stiffness += coefficient * elastic_modulus_kn_m2 * inertia / height**3

        if stiffness <= 0.0:
            raise ValueError(
                f"No vertical lateral-resisting members connect elevation {lower:g} m to {upper:g} m"
            )
        stiffnesses.append(stiffness)

    return elevations, stiffnesses


def _assemble_shear_building(stiffnesses: list[float]) -> np.ndarray:
    count = len(stiffnesses)
    matrix = np.zeros((count, count), dtype=float)
    for story, stiffness in enumerate(stiffnesses):
        matrix[story, story] += stiffness
        if story > 0:
            matrix[story - 1, story - 1] += stiffness
            matrix[story - 1, story] -= stiffness
            matrix[story, story - 1] -= stiffness
    return matrix


def response_spectrum_analysis(
    inputs: Structure3DInputs,
    building_weight_kn: float,
    sds: float,
    sd1: float,
    *,
    direction: str = "x",
    num_modes: int = 10,
    long_period_s: float = 8.0,
) -> dict:
    """Run a lumped-mass modal response-spectrum analysis using SRSS combination."""
    if direction not in ("x", "y"):
        raise ValueError("direction must be 'x' or 'y'")
    if building_weight_kn <= 0.0:
        raise ValueError("building_weight_kn must be positive")
    if num_modes < 1:
        raise ValueError("num_modes must be at least 1")

    elevations, stiffnesses = _story_stiffnesses(inputs, direction)
    floor_elevations = elevations[1:]
    story_count = len(floor_elevations)
    modes_requested = min(num_modes, story_count)

    story_weight_kn = building_weight_kn / story_count
    story_mass = story_weight_kn / GRAVITY_M_S2
    mass_matrix = np.eye(story_count) * story_mass
    stiffness_matrix = _assemble_shear_building(stiffnesses)

    mass_root_inverse = np.eye(story_count) / math.sqrt(story_mass)
    dynamic_matrix = mass_root_inverse @ stiffness_matrix @ mass_root_inverse
    eigenvalues, mass_normalized_modes = np.linalg.eigh(dynamic_matrix)
    positive = eigenvalues > 1e-10
    eigenvalues = eigenvalues[positive]
    mass_normalized_modes = mass_normalized_modes[:, positive]
    if not len(eigenvalues):
        raise ValueError("The reduced lateral stiffness matrix has no stable vibration modes")

    eigenvalues = eigenvalues[:modes_requested]
    mode_shapes = mass_root_inverse @ mass_normalized_modes[:, :modes_requested]
    influence = np.ones(story_count)
    total_mass = float(influence @ mass_matrix @ influence)

    modal_floor_forces: list[np.ndarray] = []
    modal_story_shears: list[np.ndarray] = []
    modal_displacements: list[np.ndarray] = []
    mode_rows: list[dict] = []
    cumulative_mass_ratio = 0.0

    for index, eigenvalue in enumerate(eigenvalues):
        omega = math.sqrt(float(eigenvalue))
        period = 2.0 * math.pi / omega
        shape = mode_shapes[:, index]
        modal_mass = float(shape @ mass_matrix @ shape)
        participation = float(shape @ mass_matrix @ influence) / modal_mass
        effective_mass_ratio = participation**2 * modal_mass / total_mass
        cumulative_mass_ratio += effective_mass_ratio
        sa_g = design_spectral_acceleration(period, sds, sd1, long_period_s=long_period_s)
        acceleration = sa_g * GRAVITY_M_S2

        floor_forces = participation * acceleration * (mass_matrix @ shape)
        story_shears = np.array([sum(floor_forces[i:]) for i in range(story_count)])
        displacements = participation * acceleration * shape / eigenvalue

        modal_floor_forces.append(floor_forces)
        modal_story_shears.append(story_shears)
        modal_displacements.append(displacements)
        mode_rows.append({
            "mode": index + 1,
            "period_s": round(period, 6),
            "frequency_hz": round(1.0 / period, 6),
            "participation_factor": round(participation, 6),
            "effective_mass_ratio": round(effective_mass_ratio, 6),
            "cumulative_mass_ratio": round(cumulative_mass_ratio, 6),
            "spectral_acceleration_g": round(sa_g, 6),
            "base_shear_kn": round(abs(float(story_shears[0])), 3),
        })

    combined_floor_forces = np.sqrt(np.sum(np.square(modal_floor_forces), axis=0))
    combined_story_shears = np.sqrt(np.sum(np.square(modal_story_shears), axis=0))
    combined_floor_displacements = np.sqrt(np.sum(np.square(modal_displacements), axis=0))

    story_drifts = []
    lower_displacements = np.zeros(len(modal_displacements))
    for story, (lower, upper) in enumerate(pairwise(elevations)):
        modal_upper = np.array([values[story] for values in modal_displacements])
        modal_drift = modal_upper - lower_displacements
        drift_m = float(np.linalg.norm(modal_drift))
        height = upper - lower
        story_drifts.append({
            "story": story + 1,
            "from_m": lower,
            "to_m": upper,
            "height_m": round(height, 6),
            "drift_mm": round(drift_m * 1000.0, 4),
            "drift_ratio": round(height / drift_m, 3) if drift_m > 1e-12 else None,
            "drift_ratio_delta_over_h": round(drift_m / height, 8),
        })
        lower_displacements = modal_upper

    warnings: list[str] = []
    if cumulative_mass_ratio < 0.90:
        warnings.append(
            f"Selected modes capture {cumulative_mass_ratio:.1%} of lateral mass; ASCE 7 modal analysis "
            "generally requires enough modes to capture at least 90%."
        )
    warnings.append(
        "Floor weights are distributed equally; provide a calibrated dynamic model for final design."
    )

    return {
        "method": "Lumped-mass cantilever response spectrum (SRSS)",
        "code_reference": "ASCE 7-22 Sections 11.4.6 and 12.9",
        "direction": direction,
        "idealization": "rigid-floor shear building" if inputs.rigid_diaphragms else "cantilever stories",
        "spectrum": {
            "sds": sds,
            "sd1": sd1,
            "t0_s": round(0.2 * sd1 / sds, 6),
            "ts_s": round(sd1 / sds, 6),
            "tl_s": long_period_s,
        },
        "building_weight_kn": building_weight_kn,
        "story_weight_kn": round(story_weight_kn, 3),
        "story_stiffness_kn_per_m": [round(value, 3) for value in stiffnesses],
        "modes": mode_rows,
        "cumulative_mass_ratio": round(cumulative_mass_ratio, 6),
        "story_forces": [
            {"story": i + 1, "z_m": floor_elevations[i], "force_kn": round(float(force), 3)}
            for i, force in enumerate(combined_floor_forces)
        ],
        "story_shears": [
            {"story": i + 1, "from_m": elevations[i], "shear_kn": round(float(shear), 3)}
            for i, shear in enumerate(combined_story_shears)
        ],
        "floor_displacements": [
            {"story": i + 1, "z_m": floor_elevations[i], "displacement_mm": round(float(value) * 1000.0, 4)}
            for i, value in enumerate(combined_floor_displacements)
        ],
        "story_drifts": story_drifts,
        "base_shear_kn": round(float(combined_story_shears[0]), 3),
        "warnings": warnings,
    }
