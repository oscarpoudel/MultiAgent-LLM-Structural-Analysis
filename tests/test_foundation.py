"""Tests for foundation design (spread footing + pile capacity)."""
import math

import pytest
from app.main import create_app
from app.tools.foundation import design_pile_capacity, design_spread_footing

# ---------------------------------------------------------------------------
# Spread footing
# ---------------------------------------------------------------------------

def test_spread_footing_bearing_size() -> None:
    # P = 1000 kN, allowable 200 kPa -> required area 5 m^2 -> b = 2.236 m -> round up to 2250 mm.
    result = design_spread_footing(_footing(axial_load_kn=1000, allowable_bearing_kpa=200))
    assert result["footing"]["width_mm"] >= 2236.0
    assert result["footing"]["area_m2"] >= 5.0
    assert result["bearing"]["ok"] is True
    assert result["bearing"]["pressure_kpa"] <= 200


def test_spread_footing_bearing_utilization() -> None:
    result = design_spread_footing(_footing(axial_load_kn=1000, allowable_bearing_kpa=200))
    area = result["footing"]["area_m2"]
    assert result["bearing"]["pressure_kpa"] == pytest.approx(1000 / area, rel=1e-3)
    assert result["bearing"]["util"] == pytest.approx((1000 / area) / 200, rel=1e-3)


def test_spread_footing_shear_checks_present() -> None:
    result = design_spread_footing(_footing(axial_load_kn=1000, allowable_bearing_kpa=200))
    assert result["one_way_shear"]["vu_kn"] > 0
    assert result["punching_shear"]["vu_kn"] > 0
    assert result["one_way_shear"]["phi_vc_kn"] > 0
    assert result["punching_shear"]["phi_vc_kn"] > 0


def test_spread_footing_punching_greater_than_oneway() -> None:
    # Punching shear acts over the perimeter (larger area) so Vu is typically larger.
    result = design_spread_footing(_footing(axial_load_kn=1000, allowable_bearing_kpa=200))
    assert result["punching_shear"]["vu_kn"] > result["one_way_shear"]["vu_kn"]


def test_spread_footing_flexure_as_positive() -> None:
    result = design_spread_footing(_footing(axial_load_kn=1000, allowable_bearing_kpa=200))
    assert result["flexure"]["mu_kn_m"] > 0
    assert result["flexure"]["design_as_mm2"] >= result["flexure"]["min_as_mm2"]
    assert result["suggested_bars"]["count_each_direction"] >= 1


def test_spread_footing_weak_soil_flags_bearing() -> None:
    # Very low bearing capacity -> huge footing; still should size up and pass bearing.
    result = design_spread_footing(_footing(axial_load_kn=1000, allowable_bearing_kpa=50))
    assert result["footing"]["width_mm"] > 2000
    assert result["bearing"]["ok"] is True


def test_spread_footing_width_override() -> None:
    result = design_spread_footing(_footing(axial_load_kn=1000, allowable_bearing_kpa=200, footing_width_mm=3000))
    assert result["footing"]["width_mm"] == 3000


def test_spread_footing_route() -> None:
    client = create_app().test_client()
    response = client.post(
        "/api/design/spread-footing",
        json={
            "axial_load_kn": 1000,
            "allowable_bearing_kpa": 200,
            "column_width_mm": 400,
            "column_depth_mm": 400,
        },
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert data["results"]["code_reference"].startswith("ACI 318")


def test_spread_footing_route_validation() -> None:
    client = create_app().test_client()
    response = client.post("/api/design/spread-footing", json={"axial_load_kn": -5})
    assert response.status_code == 400
    assert response.get_json()["status"] == "error"


# ---------------------------------------------------------------------------
# Pile capacity
# ---------------------------------------------------------------------------

def test_pile_capacity_breakdown() -> None:
    # D = 0.5 m, L = 10 m, f_avg = 50 kPa, alpha = 0.5, q_p = 1000 kPa, FS = 2.5
    result = design_pile_capacity(_pile())
    d = 0.5
    a_p = math.pi / 4.0 * d**2
    perim = math.pi * d
    a_shaft = perim * 10.0
    q_s = 0.5 * 50.0 * a_shaft
    q_p = 1000.0 * a_p
    assert result["capacity_kn"]["skin_friction"] == pytest.approx(q_s, rel=1e-3)
    assert result["capacity_kn"]["end_bearing"] == pytest.approx(q_p, rel=1e-3)
    assert result["capacity_kn"]["ultimate"] == pytest.approx(q_s + q_p, rel=1e-3)
    assert result["capacity_kn"]["allowable"] == pytest.approx((q_s + q_p) / 2.5, rel=1e-3)


def test_pile_capacity_single_pile_eta_one() -> None:
    result = design_pile_capacity(_pile(piles_per_row=1, rows_in_group=1))
    assert result["group"]["efficiency"] == 1.0
    assert result["group"]["piles"] == 1


def test_pile_capacity_group_efficiency_less_than_one() -> None:
    single = design_pile_capacity(_pile(piles_per_row=1, rows_in_group=1, center_to_center_spacing_m=0))
    group = design_pile_capacity(_pile(piles_per_row=3, rows_in_group=3, center_to_center_spacing_m=1.0))
    assert group["group"]["efficiency"] < 1.0
    assert group["group"]["piles"] == 9
    # Group capacity = eta * 9 * q_allow, where q_allow is the same single-pile value.
    assert group["group"]["allowable_capacity"] == pytest.approx(
        group["group"]["efficiency"] * 9 * single["capacity_kn"]["allowable"], rel=1e-3
    )


def test_pile_capacity_wide_spacing_eta_near_one() -> None:
    result = design_pile_capacity(_pile(piles_per_row=2, rows_in_group=2, center_to_center_spacing_m=5.0))
    assert result["group"]["efficiency"] > 0.9


def test_pile_capacity_skin_fraction() -> None:
    result = design_pile_capacity(_pile())
    assert 0.0 <= result["capacity_kn"]["skin_fraction"] <= 1.0
    assert result["capacity_kn"]["skin_fraction"] == pytest.approx(
        result["capacity_kn"]["skin_friction"] / result["capacity_kn"]["ultimate"], rel=1e-3
    )


def test_pile_route() -> None:
    client = create_app().test_client()
    response = client.post(
        "/api/design/pile",
        json={
            "pile_diameter_mm": 500,
            "pile_length_m": 10,
            "skin_friction_kpa": 50,
            "end_bearing_kpa": 1000,
        },
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert data["results"]["capacity_kn"]["ultimate"] > 0


def test_pile_route_validation() -> None:
    client = create_app().test_client()
    response = client.post("/api/design/pile", json={"pile_diameter_mm": -1, "pile_length_m": 10, "skin_friction_kpa": 50, "end_bearing_kpa": 1000})
    assert response.status_code == 400
    assert response.get_json()["status"] == "error"


def _footing(**overrides) -> dict:
    base = {
        "axial_load_kn": 1000.0,
        "allowable_bearing_kpa": 200.0,
        "column_width_mm": 400.0,
        "column_depth_mm": 400.0,
        "concrete_fck_mpa": 25.0,
        "steel_fy_mpa": 420.0,
        "footing_depth_mm": 600.0,
        "bar_dia_mm": 20.0,
    }
    base.update(overrides)
    from app.models import SpreadFootingInputs

    return SpreadFootingInputs.model_validate(base)


def _pile(**overrides) -> dict:
    base = {
        "pile_diameter_mm": 500.0,
        "pile_length_m": 10.0,
        "skin_friction_kpa": 50.0,
        "skin_friction_alpha": 0.5,
        "end_bearing_kpa": 1000.0,
        "factor_of_safety": 2.5,
        "piles_per_row": 1,
        "rows_in_group": 1,
        "center_to_center_spacing_m": 0.0,
    }
    base.update(overrides)
    from app.models import PileInputs

    return PileInputs.model_validate(base)
