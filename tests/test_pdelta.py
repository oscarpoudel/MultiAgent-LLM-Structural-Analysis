"""Tests for P-delta second-order analysis (deterministic)."""
import pytest
from app.models import Node3D, Structure3DInputs
from app.tools.pdelta import (
    amplification_factor,
    amplify_story_drifts,
    pdelta_equivalent_lateral_forces,
    stability_coefficient,
)


def _two_story_model() -> Structure3DInputs:
    nodes = []
    nid = 1
    for z in (0.0, 4.0, 8.0):
        for x in (0.0, 6.0):
            for y in (0.0, 6.0):
                nodes.append(Node3D(id=nid, x=x, y=y, z=z))
                nid += 1
    return Structure3DInputs(nodes=nodes, members=[])


def test_stability_coefficient_theta_equals_vh_over_w() -> None:
    # V = 100 kN, h = 8 m, W = 8000 kN -> theta = 100*8/8000 = 0.1
    assert stability_coefficient(100.0, 8.0, 8000.0) == pytest.approx(0.1)


def test_stability_coefficient_zero_gravity_is_zero() -> None:
    assert stability_coefficient(100.0, 8.0, 0.0) == 0.0


def test_amplification_factor_is_inverse_one_minus_theta() -> None:
    assert amplification_factor(0.1) == pytest.approx(1.0 / 0.9)
    assert amplification_factor(0.0) == 1.0


def test_amplification_factor_capped_near_limit() -> None:
    # theta beyond the cap uses the capped value; theta >= 1 is infinite.
    assert amplification_factor(0.95) == pytest.approx(1.0 / (1.0 - 0.90))
    assert amplification_factor(1.0) == float("inf")
    assert amplification_factor(1.5) == float("inf")


def test_amplify_story_drifts_scales_drift_by_factor() -> None:
    drifts = [
        {"from_m": 0.0, "to_m": 4.0, "height_m": 4.0, "drift_mm": 10.0},
        {"from_m": 4.0, "to_m": 8.0, "height_m": 4.0, "drift_mm": 12.0},
    ]
    out = amplify_story_drifts(drifts, base_shear_kn=100.0, height_m=8.0, gravity_load_kn=8000.0)

    assert out["theta"] == pytest.approx(0.1)
    assert out["stable"] is True
    # Reported factor is rounded to 4 decimals.
    assert out["amplification_factor"] == pytest.approx(1.0 / 0.9, abs=5e-5)
    # Second-order drift = first-order * 1/(1-theta); values rounded to 3 dp.
    assert out["story_drifts"][0]["drift2_mm"] == pytest.approx(10.0 / 0.9, abs=5e-4)
    assert out["story_drifts"][1]["drift2_mm"] == pytest.approx(12.0 / 0.9, abs=5e-4)
    assert out["max_drift2_mm"] == pytest.approx(12.0 / 0.9, abs=5e-4)
    assert out["warnings"] == []


def test_amplify_story_drifts_unstable_when_theta_ge_1() -> None:
    drifts = [{"from_m": 0.0, "to_m": 4.0, "height_m": 4.0, "drift_mm": 10.0}]
    # V*h/W = 1000*8/8000 = 1.0 -> at the buckling limit.
    out = amplify_story_drifts(drifts, base_shear_kn=1000.0, height_m=8.0, gravity_load_kn=8000.0)

    assert out["stable"] is False
    assert out["amplification_factor"] is None
    assert out["story_drifts"][0]["drift2_mm"] is None
    assert any("buckling" in w for w in out["warnings"])


def test_amplify_story_drifts_caps_and_warns_near_limit() -> None:
    drifts = [{"from_m": 0.0, "to_m": 4.0, "height_m": 4.0, "drift_mm": 10.0}]
    # theta = 0.95 > 0.90 cap -> factor capped, warning raised.
    out = amplify_story_drifts(drifts, base_shear_kn=950.0, height_m=8.0, gravity_load_kn=8000.0)

    assert out["stable"] is True
    assert out["amplification_factor"] == pytest.approx(1.0 / 0.10)
    assert any("capped" in w for w in out["warnings"])


def test_pdelta_equivalent_lateral_forces_distribute_to_story_top() -> None:
    inputs = _two_story_model()
    drifts = [
        {"from_m": 0.0, "to_m": 4.0, "height_m": 4.0, "drift_mm": 10.0},
        {"from_m": 4.0, "to_m": 8.0, "height_m": 4.0, "drift_mm": 12.0},
    ]
    out = pdelta_equivalent_lateral_forces(inputs, drifts, gravity_load_kn=12000.0, direction="x")

    pd_loads = [l for l in out["inputs"].nodal_loads if l.case == "PD"]
    # Story 1 (top z=4): W_above = 2 levels * 4000 = 8000 kN, M = 8000*0.010 = 80 kN-m,
    # F = 80/4 = 20 kN over 4 nodes -> 5 kN each.
    story1 = [l for l in pd_loads if l.fx_kn == pytest.approx(5.0)]
    assert len(story1) == 4
    # Story 2 (top z=8): W_above = 1 level * 4000 = 4000 kN, M = 4000*0.012 = 48 kN-m,
    # F = 48/4 = 12 kN over 4 nodes -> 3 kN each.
    story2 = [l for l in pd_loads if l.fx_kn == pytest.approx(3.0)]
    assert len(story2) == 4
    assert len(out["applied"]) == 2
    assert out["applied"][0]["force_kn"] == pytest.approx(20.0)
    assert out["applied"][1]["force_kn"] == pytest.approx(12.0)


def test_pdelta_equivalent_lateral_forces_direction_y() -> None:
    inputs = _two_story_model()
    drifts = [{"from_m": 0.0, "to_m": 4.0, "height_m": 4.0, "drift_mm": 10.0}]
    out = pdelta_equivalent_lateral_forces(inputs, drifts, gravity_load_kn=12000.0, direction="y")

    pd_loads = [l for l in out["inputs"].nodal_loads if l.case == "PD"]
    assert all(l.fy_kn > 0 for l in pd_loads)
    assert all(l.fx_kn == 0.0 for l in pd_loads)


def test_pdelta_equivalent_lateral_forces_no_op_when_no_drift() -> None:
    inputs = _two_story_model()
    out = pdelta_equivalent_lateral_forces(inputs, [], gravity_load_kn=12000.0)

    assert out["applied"] == []
    assert out["inputs"].nodal_loads == []


def test_pdelta_equivalent_lateral_forces_skips_zero_drift_story() -> None:
    inputs = _two_story_model()
    drifts = [
        {"from_m": 0.0, "to_m": 4.0, "height_m": 4.0, "drift_mm": 0.0},  # skipped
        {"from_m": 4.0, "to_m": 8.0, "height_m": 4.0, "drift_mm": 12.0},
    ]
    out = pdelta_equivalent_lateral_forces(inputs, drifts, gravity_load_kn=12000.0)

    assert len(out["applied"]) == 1
    assert out["applied"][0]["to_m"] == 8.0


def test_pdelta_equivalent_lateral_forces_rejects_bad_direction() -> None:
    inputs = _two_story_model()
    with pytest.raises(ValueError):
        pdelta_equivalent_lateral_forces(inputs, [], gravity_load_kn=1.0, direction="z")


def test_pdelta_does_not_mutate_original_inputs() -> None:
    inputs = _two_story_model()
    before = len(inputs.nodal_loads)
    drifts = [{"from_m": 0.0, "to_m": 4.0, "height_m": 4.0, "drift_mm": 10.0}]
    pdelta_equivalent_lateral_forces(inputs, drifts, gravity_load_kn=12000.0)

    assert len(inputs.nodal_loads) == before
