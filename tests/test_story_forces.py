"""Tests for mapping wind/seismic story forces onto a drawn 3D model."""
from app.models import Load3D, Node3D, Structure3DInputs
from app.tools.story_forces import apply_story_forces


def _two_story_model() -> Structure3DInputs:
    """2-story, 2x2 grid frame: 4 base nodes (z=0), 4 mid (z=4), 4 top (z=8)."""
    nodes = []
    nid = 1
    for z in (0.0, 4.0, 8.0):
        for x in (0.0, 6.0):
            for y in (0.0, 6.0):
                nodes.append(Node3D(id=nid, x=x, y=y, z=z))
                nid += 1
    return Structure3DInputs(nodes=nodes, members=[])


def test_equal_distribution_splits_force_across_all_nodes_at_level() -> None:
    inputs = _two_story_model()
    out = apply_story_forces(inputs, [{"z_m": 4.0, "force_kn": 100.0}], case="W", direction="x")

    new = [l for l in out["inputs"].nodal_loads if l.case == "W"]
    assert len(new) == 4
    assert sum(l.fx_kn for l in new) == 100.0
    assert all(l.fx_kn == 25.0 for l in new)
    assert all(l.fy_kn == 0.0 for l in new)


def test_direction_y_loads_fy_not_fx() -> None:
    inputs = _two_story_model()
    out = apply_story_forces(inputs, [{"z_m": 8.0, "force_kn": 50.0}], case="EQ", direction="y")

    new = [l for l in out["inputs"].nodal_loads if l.case == "EQ"]
    assert all(l.fy_kn == 12.5 for l in new)
    assert all(l.fx_kn == 0.0 for l in new)


def test_windward_distribution_targets_min_coord_face_only() -> None:
    inputs = _two_story_model()
    out = apply_story_forces(
        inputs,
        [{"z_m": 4.0, "force_kn": 80.0}],
        case="W",
        direction="x",
        distribution="windward",
    )

    new = [l for l in out["inputs"].nodal_loads if l.case == "W"]
    # Windward face in +x loading is x=0 -> 2 nodes at z=4
    assert len(new) == 2
    assert sum(l.fx_kn for l in new) == 80.0
    assert all(l.fx_kn == 40.0 for l in new)


def test_nearest_elevation_snap_and_warning() -> None:
    inputs = _two_story_model()
    out = apply_story_forces(inputs, [{"z_m": 4.4, "force_kn": 10.0}], case="W", direction="x")

    assert out["applied"][0]["assigned_elevation_m"] == 4.0
    # 0.4 m offset is within tolerance, no warning
    assert out["warnings"] == []

    far = apply_story_forces(inputs, [{"z_m": 20.0, "force_kn": 10.0}], case="W", direction="x")
    assert far["applied"][0]["assigned_elevation_m"] == 8.0
    assert any("far from the nearest model level" in w for w in far["warnings"])


def test_preserves_existing_nodal_loads() -> None:
    inputs = _two_story_model()
    inputs.nodal_loads = [Load3D(node_id=1, case="D", fz_kn=-10.0)]
    out = apply_story_forces(inputs, [{"z_m": 4.0, "force_kn": 40.0}], case="W", direction="x")

    cases = [l.case for l in out["inputs"].nodal_loads]
    assert "D" in cases
    assert cases.count("W") == 4
    # Original load untouched
    assert any(l.case == "D" and l.node_id == 1 and l.fz_kn == -10.0 for l in out["inputs"].nodal_loads)


def test_does_not_mutate_original_inputs() -> None:
    inputs = _two_story_model()
    before = len(inputs.nodal_loads)
    apply_story_forces(inputs, [{"z_m": 4.0, "force_kn": 40.0}], case="W", direction="x")
    assert len(inputs.nodal_loads) == before


def test_zero_force_story_is_skipped() -> None:
    inputs = _two_story_model()
    out = apply_story_forces(inputs, [{"z_m": 4.0, "force_kn": 0.0}], case="W", direction="x")
    assert out["applied"] == []
    assert out["inputs"].nodal_loads == []


def test_empty_inputs_return_unchanged() -> None:
    empty = Structure3DInputs(nodes=[], members=[])
    out = apply_story_forces(empty, [{"z_m": 4.0, "force_kn": 10.0}], case="W", direction="x")
    assert out["applied"] == []
    assert out["inputs"].nodal_loads == []


def test_invalid_direction_and_distribution_raise() -> None:
    inputs = _two_story_model()
    import pytest

    with pytest.raises(ValueError):
        apply_story_forces(inputs, [{"z_m": 4.0, "force_kn": 10.0}], direction="z")
    with pytest.raises(ValueError):
        apply_story_forces(inputs, [{"z_m": 4.0, "force_kn": 10.0}], distribution="diagonal")


def test_multiple_stories_sum_to_total_lateral_force() -> None:
    inputs = _two_story_model()
    forces = [{"z_m": 4.0, "force_kn": 30.0}, {"z_m": 8.0, "force_kn": 70.0}]
    out = apply_story_forces(inputs, forces, case="W", direction="x")

    total = sum(l.fx_kn for l in out["inputs"].nodal_loads if l.case == "W")
    assert total == 100.0
    assert len(out["applied"]) == 2
