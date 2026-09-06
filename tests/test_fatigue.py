"""Tests for AISC 360 fatigue design (S-N curves)."""
import math

import pytest
from app.main import create_app
from app.models import FatigueInputs
from app.tools.fatigue import (
    FATIGUE_CATEGORIES,
    allowable_stress_range,
    check_fatigue,
    cycles_to_failure,
    list_fatigue_categories,
)


def _inputs(**overrides) -> FatigueInputs:
    base = {"category": "C", "stress_range_mpa": 100.0, "num_cycles": 1.0e6}
    base.update(overrides)
    return FatigueInputs.model_validate(base)


def test_list_categories() -> None:
    cats = list_fatigue_categories()
    assert len(cats) == 5
    assert [c["category"] for c in cats] == ["A", "B", "C", "D", "E"]
    # Fatigue limits decrease from A to E.
    limits = [c["fatigue_limit_mpa"] for c in cats]
    assert limits == sorted(limits, reverse=True)


def test_cycles_to_failure_category_c() -> None:
    # Category C: C = 0.68e12, limit 90 MPa. f_f = 100 MPa -> N = 0.68e12/1e6 = 6.8e5
    n = cycles_to_failure(100.0, "C")
    assert n == pytest.approx(0.68e12 / 100.0**3, rel=1e-9)
    assert n == pytest.approx(6.8e5, rel=1e-9)


def test_infinite_life_below_limit() -> None:
    # Category C limit is 90 MPa; a stress range of 50 MPa is below -> infinite life.
    assert math.isinf(cycles_to_failure(50.0, "C"))
    # At exactly the limit, also infinite.
    assert math.isinf(cycles_to_failure(90.0, "C"))


def test_allowable_stress_range() -> None:
    # N = 1e6, category C: f = (0.68e12/1e6)^(1/3) = (6.8e5)^(1/3) ~ 87.9, capped at 90.
    f = allowable_stress_range(1.0e6, "C")
    assert f == pytest.approx((0.68e12 / 1.0e6) ** (1.0 / 3.0), rel=1e-9)
    assert f <= FATIGUE_CATEGORIES["C"]["fatigue_limit_mpa"]
    # A very long life gives a lower allowable stress range.
    assert allowable_stress_range(1.0e8, "C") < allowable_stress_range(1.0e6, "C")


def test_check_fatigue_passes() -> None:
    # f_f = 100 MPa (cat C) -> N_f = 6.8e5. Demand 1e5 cycles -> utilization 0.147 -> pass.
    result = check_fatigue(_inputs(stress_range_mpa=100.0, num_cycles=1.0e5))
    assert result["result"]["pass"] is True
    assert result["result"]["infinite_life"] is False
    assert result["result"]["utilization"] == pytest.approx(1.0e5 / 6.8e5, rel=1e-3)


def test_check_fatigue_fails() -> None:
    # Demand 1e6 cycles > N_f = 6.8e5 -> fail.
    result = check_fatigue(_inputs(stress_range_mpa=100.0, num_cycles=1.0e6))
    assert result["result"]["pass"] is False
    assert result["result"]["utilization"] > 1.0
    assert any("FAILS" in w for w in result["warnings"])


def test_check_fatigue_infinite_life_passes() -> None:
    # Below the fatigue limit -> infinite life, always passes.
    result = check_fatigue(_inputs(stress_range_mpa=50.0, num_cycles=1.0e8))
    assert result["result"]["infinite_life"] is True
    assert result["result"]["pass"] is True
    assert result["result"]["utilization"] == 0.0


def test_required_category_selection() -> None:
    # At a moderate stress range, a higher (more resistant) category may be required.
    # f_f = 100 MPa: cat C N_f=6.8e5, cat B N_f=1.6e12/1e6=1.6e6. For N=1e6, C fails, B passes.
    result = check_fatigue(_inputs(category="C", stress_range_mpa=100.0, num_cycles=1.0e6))
    assert result["result"]["pass"] is False
    assert result["required_category"] == "B"


def test_required_category_none_when_impossible() -> None:
    # Extremely high stress range -> no category passes a long design life.
    result = check_fatigue(_inputs(category="E", stress_range_mpa=500.0, num_cycles=1.0e9))
    assert result["result"]["pass"] is False
    assert result["required_category"] is None
    assert any("redesigned" in w for w in result["warnings"])


def test_unknown_category_raises() -> None:
    with pytest.raises(ValueError, match="Unknown fatigue category"):
        check_fatigue(_inputs(category="Z"))


def test_fatigue_route() -> None:
    client = create_app().test_client()
    response = client.post(
        "/api/design/fatigue",
        json={"category": "C", "stress_range_mpa": 100.0, "num_cycles": 1.0e5},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert data["results"]["code_reference"].startswith("AISC 360")


def test_fatigue_categories_route() -> None:
    client = create_app().test_client()
    response = client.get("/api/design/fatigue-categories")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert len(data["results"]["categories"]) == 5


def test_fatigue_route_unknown_category() -> None:
    client = create_app().test_client()
    response = client.post("/api/design/fatigue", json={"category": "Z", "stress_range_mpa": 100.0, "num_cycles": 1e5})
    assert response.status_code == 400
    assert response.get_json()["status"] == "error"
