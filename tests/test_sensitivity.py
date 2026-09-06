"""Tests for OAT parametric sensitivity analysis."""
import pytest
from app.main import create_app
from app.models import SensitivityInputs
from app.tools.sensitivity import _responses, run_sensitivity


def _base_inputs(**overrides) -> SensitivityInputs:
    base = {
        "load_kn_m": 10.0,
        "span_m": 6.0,
        "modulus_gpa": 200.0,
        "inertia_m4": 0.001,
        "section_modulus_m3": 0.001,
        "load_min_kn_m": 5.0,
        "load_max_kn_m": 15.0,
        "span_min_m": 4.0,
        "span_max_m": 8.0,
        "modulus_min_gpa": 150.0,
        "modulus_max_gpa": 250.0,
        "inertia_min_m4": 0.0005,
        "inertia_max_m4": 0.002,
        "section_min_m3": 0.0005,
        "section_max_m3": 0.002,
        "parameters": ["w", "L", "E", "I", "S"],
    }
    base.update(overrides)
    return SensitivityInputs.model_validate(base)


def test_base_response_values() -> None:
    # w=10 kN/m, L=6 m, E=200 GPa=2e8 kPa, I=0.001 m4, S=0.001 m3
    r = _responses(10.0, 6.0, 200.0e6, 0.001, 0.001)
    assert r["moment_kn_m"] == pytest.approx(10.0 * 36.0 / 8.0, rel=1e-9)  # 45
    assert r["deflection_m"] == pytest.approx(5 * 10.0 * 6.0**4 / (384.0 * 200.0e6 * 0.001), rel=1e-9)
    assert r["stress_kpa"] == pytest.approx(45.0 / 0.001, rel=1e-9)  # 45000


def test_sensitivity_load_is_linear() -> None:
    # Moment, deflection, stress are all linear in w -> sensitivity ~ 1.0
    result = run_sensitivity(_base_inputs(parameters=["w"]))
    s = result["study"]["load_kn_m"]["sensitivity"]
    assert s["moment_kn_m"] == pytest.approx(1.0, rel=1e-2)
    assert s["deflection_m"] == pytest.approx(1.0, rel=1e-2)
    assert s["stress_kpa"] == pytest.approx(1.0, rel=1e-2)


def test_sensitivity_span_is_quartic_for_deflection() -> None:
    # deflection ~ L^4 -> sensitivity ~ 4.0; moment ~ L^2 -> ~2.0
    result = run_sensitivity(_base_inputs(parameters=["L"]))
    s = result["study"]["span_m"]["sensitivity"]
    assert s["deflection_m"] == pytest.approx(4.0, rel=1e-2)
    assert s["moment_kn_m"] == pytest.approx(2.0, rel=1e-2)


def test_sensitivity_e_and_i_inverse() -> None:
    # deflection ~ 1/E and 1/I -> sensitivity ~ -1.0
    result = run_sensitivity(_base_inputs(parameters=["E", "I"]))
    se = result["study"]["modulus_gpa"]["sensitivity"]
    si = result["study"]["inertia_m4"]["sensitivity"]
    assert se["deflection_m"] == pytest.approx(-1.0, rel=1e-2)
    assert si["deflection_m"] == pytest.approx(-1.0, rel=1e-2)
    # E and I do not affect moment
    assert se["moment_kn_m"] == pytest.approx(0.0, abs=1e-2)


def test_sensitivity_section_modulus_inverse_for_stress() -> None:
    # stress = M/S ~ 1/S -> sensitivity ~ -1.0
    result = run_sensitivity(_base_inputs(parameters=["S"]))
    s = result["study"]["section_modulus_m3"]["sensitivity"]
    assert s["stress_kpa"] == pytest.approx(-1.0, rel=1e-2)


def test_sensitivity_sweep_includes_base() -> None:
    result = run_sensitivity(_base_inputs(parameters=["w"]))
    sweep = result["study"]["load_kn_m"]["sweep"]
    values = [row["param_value"] for row in sweep]
    assert any(abs(v - 10.0) < 1e-6 for v in values)
    assert values == sorted(values)


def test_sensitivity_ranking_orders_by_impact() -> None:
    result = run_sensitivity(_base_inputs(parameters=["w", "L", "E", "I", "S"]))
    ranking = result["ranking"]
    # L has the largest max |sensitivity| (deflection ~ L^4 -> 4.0)
    assert ranking[0]["parameter"] == "span_m"
    assert ranking[0]["max_abs_sensitivity"] >= 4.0
    # ranking is sorted descending
    vals = [r["max_abs_sensitivity"] for r in ranking]
    assert vals == sorted(vals, reverse=True)


def test_sensitivity_single_parameter() -> None:
    result = run_sensitivity(_base_inputs(parameters=["w"]))
    assert list(result["study"].keys()) == ["load_kn_m"]


def test_sensitivity_route() -> None:
    client = create_app().test_client()
    response = client.post(
        "/api/analyze/sensitivity",
        json={
            "load_kn_m": 10.0,
            "span_m": 6.0,
            "modulus_gpa": 200.0,
            "inertia_m4": 0.001,
            "section_modulus_m3": 0.001,
            "load_min_kn_m": 5.0,
            "load_max_kn_m": 15.0,
            "span_min_m": 4.0,
            "span_max_m": 8.0,
            "modulus_min_gpa": 150.0,
            "modulus_max_gpa": 250.0,
            "inertia_min_m4": 0.0005,
            "inertia_max_m4": 0.002,
            "section_min_m3": 0.0005,
            "section_max_m3": 0.002,
            "parameters": ["w", "L"],
        },
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert "study" in data["results"]
    assert "ranking" in data["results"]


def test_sensitivity_route_validation() -> None:
    client = create_app().test_client()
    response = client.post("/api/analyze/sensitivity", json={"load_kn_m": -1})
    assert response.status_code == 400
    assert response.get_json()["status"] == "error"
