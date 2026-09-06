"""Tests for the multi-hazard load combination optimizer."""
import pytest
from app.main import create_app
from app.models import MultiHazardInputs
from app.tools.load_combinations import run_all_load_combinations
from app.tools.multi_hazard import evaluate_combinations, optimize_multi_hazard


def _inputs(**overrides) -> MultiHazardInputs:
    base = {
        "dead_load_kn": 100.0,
        "live_load_kn": 50.0,
        "wind_load_kn": 30.0,
        "snow_load_kn": 20.0,
        "earthquake_load_kn": 40.0,
        "response_factor": 1.0,
        "capacity": 300.0,
        "method": "lrfd",
        "dead_min_kn": 50.0,
        "dead_max_kn": 150.0,
        "live_min_kn": 0.0,
        "live_max_kn": 100.0,
        "wind_min_kn": 0.0,
        "wind_max_kn": 100.0,
        "snow_min_kn": 0.0,
        "snow_max_kn": 50.0,
        "earthquake_min_kn": 0.0,
        "earthquake_max_kn": 80.0,
        "components": ["dl_kn", "ll_kn", "wl_kn", "sl_kn", "el_kn"],
    }
    base.update(overrides)
    return MultiHazardInputs.model_validate(base)


def test_base_case_governing_matches_max_combination() -> None:
    result = optimize_multi_hazard(_inputs())
    base = result["base_case"]
    # The governing combination must be the one with the largest factored load.
    all_combos = run_all_load_combinations(100, 50, 30, 20, 40, method="lrfd")
    expected_max = max(c["factored_load_kn"] for c in all_combos)
    assert base["governing"]["factored_load_kn"] == pytest.approx(expected_max, rel=1e-9)
    assert base["governing_utilization"] == pytest.approx(expected_max / 300.0, rel=1e-3)


def test_utilization_is_response_over_capacity() -> None:
    result = optimize_multi_hazard(_inputs(response_factor=2.0, capacity=500.0))
    base = result["base_case"]
    for row in base["combinations"]:
        assert row["response"] == pytest.approx(row["factored_load_kn"] * 2.0, rel=1e-9)
        assert row["utilization"] == pytest.approx(row["response"] / 500.0, rel=1e-9)
        assert row["ok"] == (row["utilization"] <= 1.0)


def test_combinations_sorted_by_utilization() -> None:
    result = optimize_multi_hazard(_inputs())
    utils = [abs(r["utilization"]) for r in result["base_case"]["combinations"]]
    assert utils == sorted(utils, reverse=True)
    assert result["base_case"]["num_combinations"] == 7  # LRFD set


def test_all_ok_flag_and_warning() -> None:
    safe = optimize_multi_hazard(_inputs(capacity=1000.0))
    assert safe["base_case"]["all_ok"] is True
    assert safe["warnings"] == []

    unsafe = optimize_multi_hazard(_inputs(capacity=100.0))
    assert unsafe["base_case"]["all_ok"] is False
    assert any("NOT safe" in w for w in unsafe["warnings"])


def test_sweep_worst_wind_at_max() -> None:
    result = optimize_multi_hazard(_inputs(components=["wl_kn"]))
    sweep = result["sweeps"]["wl_kn"]
    assert sweep["worst_value"] == pytest.approx(100.0, rel=1e-9)
    # Utilization must increase monotonically as wind grows (wind only adds load).
    utils = [row["governing_utilization"] for row in sweep["sweep"]]
    assert utils == sorted(utils)


def test_sweep_includes_base_value() -> None:
    result = optimize_multi_hazard(_inputs(components=["dl_kn"]))
    sweep = result["sweeps"]["dl_kn"]
    values = [row["value"] for row in sweep["sweep"]]
    assert any(abs(v - 100.0) < 1e-9 for v in values)
    assert values == sorted(values)


def test_overall_worst_component_selection() -> None:
    result = optimize_multi_hazard(_inputs())
    overall = result["overall_worst"]
    # The overall worst component must be the argmax of the per-component worst utilizations.
    max_util = max(s["worst_utilization"] for s in result["sweeps"].values())
    assert overall["governing_utilization"] == pytest.approx(max_util, rel=1e-3)
    assert result["sweeps"][overall["component"]]["worst_utilization"] == pytest.approx(max_util, rel=1e-3)
    # Overall worst utilization must be >= the base-case utilization.
    assert overall["governing_utilization"] >= result["base_case"]["governing_utilization"]
    assert overall["governing_combination"]


def test_asd_method() -> None:
    result = optimize_multi_hazard(_inputs(method="asd", components=["dl_kn"]))
    assert result["base_case"]["num_combinations"] == 8  # ASD set
    assert "ASD" in result["method"]


def test_response_factor_scales_governing() -> None:
    r1 = optimize_multi_hazard(_inputs(response_factor=1.0))
    r2 = optimize_multi_hazard(_inputs(response_factor=3.0))
    assert r2["base_case"]["governing_utilization"] == pytest.approx(
        r1["base_case"]["governing_utilization"] * 3.0, rel=1e-3
    )


def test_evaluate_combinations_direct() -> None:
    ev = evaluate_combinations(100, 50, 30, 20, 40, response_factor=1.0, capacity=300.0, method="lrfd")
    assert len(ev["combinations"]) == 7
    assert ev["governing"] == ev["combinations"][0]


def test_multi_hazard_route() -> None:
    client = create_app().test_client()
    response = client.post(
        "/api/analyze/multi-hazard",
        json={
            "dead_load_kn": 100,
            "live_load_kn": 50,
            "wind_load_kn": 30,
            "snow_load_kn": 20,
            "earthquake_load_kn": 40,
            "response_factor": 1.0,
            "capacity": 300,
            "wind_min_kn": 0,
            "wind_max_kn": 100,
            "components": ["wl_kn"],
        },
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert "base_case" in data["results"]
    assert "sweeps" in data["results"]
    assert "overall_worst" in data["results"]


def test_multi_hazard_route_validation() -> None:
    client = create_app().test_client()
    response = client.post("/api/analyze/multi-hazard", json={"dead_load_kn": -5, "capacity": 100})
    assert response.status_code == 400
    assert response.get_json()["status"] == "error"
