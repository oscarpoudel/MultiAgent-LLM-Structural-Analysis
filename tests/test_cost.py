"""Tests for steel cost estimation."""
import pytest
from app.main import create_app
from app.tools.cost import estimate_cost


def test_cost_basic_takeoff() -> None:
    result = estimate_cost(
        [
            {"section": "W200X36", "length_m": 10.0},
            {"section": "W250X45", "length_m": 20.0},
        ],
        price_per_kg=2.0,
    )
    # W200X36 = 36 kg/m * 10 = 360 kg; W250X45 = 45 kg/m * 20 = 900 kg
    assert result["total_weight_kg"] == pytest.approx(1260.0)
    assert result["total_weight_t"] == pytest.approx(1.26)
    assert result["material_cost"] == pytest.approx(2520.0)
    assert result["total_cost"] == pytest.approx(2520.0)
    assert result["num_groups"] == 2


def test_cost_factors_increase_total() -> None:
    base = estimate_cost([{"section": "W200X36", "length_m": 10.0}], price_per_kg=2.0)
    factored = estimate_cost(
        [{"section": "W200X36", "length_m": 10.0}],
        price_per_kg=2.0,
        fab_factor=1.2,
        erect_factor=1.1,
    )
    assert factored["total_cost"] == pytest.approx(base["total_cost"] * 1.2 * 1.1)


def test_cost_skips_unknown_section_with_warning() -> None:
    result = estimate_cost(
        [
            {"section": "W200X36", "length_m": 10.0},
            {"section": "NOT_A_SECTION", "length_m": 5.0},
        ]
    )
    assert result["num_groups"] == 1
    assert any("NOT_A_SECTION" in w for w in result["warnings"])


def test_cost_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="price_per_kg"):
        estimate_cost([{"section": "W200X36", "length_m": 1.0}], price_per_kg=-1.0)
    with pytest.raises(ValueError, match="factor"):
        estimate_cost([{"section": "W200X36", "length_m": 1.0}], fab_factor=0.5)


def test_cost_empty_takeoff() -> None:
    result = estimate_cost([])
    assert result["total_weight_kg"] == 0.0
    assert result["total_cost"] == 0.0
    assert result["cost_per_ton"] == 0.0


def test_cost_route() -> None:
    client = create_app().test_client()
    response = client.post(
        "/api/design/cost",
        json={
            "members": [{"section": "W200X36", "length_m": 10.0}],
            "price_per_kg": 2.0,
            "currency": "EUR",
        },
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert data["results"]["currency"] == "EUR"
    assert data["results"]["total_weight_kg"] == pytest.approx(360.0)


def test_cost_route_rejects_invalid() -> None:
    client = create_app().test_client()
    response = client.post("/api/design/cost", json={"members": "not-a-list"})
    assert response.status_code == 400
    assert response.get_json()["status"] == "error"
