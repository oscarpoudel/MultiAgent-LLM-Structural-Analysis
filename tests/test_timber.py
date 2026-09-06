"""Tests for NDS timber beam design."""
import pytest
from app.main import create_app
from app.tools.timber import SPECIES, design_timber_beam, list_species


def test_species_listing() -> None:
    species = list_species()
    assert len(species) == len(SPECIES)
    for entry in species:
        assert entry["Fb_mpa"] > 0
        assert entry["E_mpa"] > 0


def test_timber_beam_passes_when_undersized_demand() -> None:
    # Large, strong member with a small moment -> should pass all checks.
    result = design_timber_beam(
        _inputs(species="douglas-fir-larch-select-structural", width_mm=150, depth_mm=350,
                moment_kn_m=30, shear_kn=30, span_m=4.0)
    )
    assert result["pass"] is True
    assert result["flexure"]["ok"] is True
    assert result["shear"]["ok"] is True
    assert result["deflection"]["total_ok"] is True


def test_timber_beam_flexure_utilization() -> None:
    # Verify f_b = M/S and utilization = f_b / Fb_adj by hand for a braced, dry, normal beam.
    inputs = _inputs(species="spf-no1", width_mm=90, depth_mm=240, moment_kn_m=20, shear_kn=0, span_m=3.0)
    result = design_timber_beam(inputs)
    s = 90 * 240**2 / 6.0  # mm^3
    fb = SPECIES["spf-no1"]["Fb_psi"] * 0.00689476
    # braced (CL=1), dry (CM=1), normal (CD=1), temp 20C (Ct=1), d_in=9.45 -> CF applies
    cf = (3.0 / (240 / 25.4)) ** (1.0 / 9.0)
    fb_adj = fb * 1.0 * 1.0 * 1.0 * cf
    f_b = 20e6 / s
    assert result["flexure"]["f_b_mpa"] == pytest.approx(f_b, rel=1e-3)
    assert result["flexure"]["Fb_adj_mpa"] == pytest.approx(fb_adj, rel=1e-3)
    assert result["flexure"]["util"] == pytest.approx(f_b / fb_adj, rel=1e-3)


def test_timber_beam_beam_stability_reduces_capacity() -> None:
    braced = design_timber_beam(_inputs(unbraced_length_m=0.0, moment_kn_m=30))
    unbraced = design_timber_beam(_inputs(unbraced_length_m=4.0, moment_kn_m=30))
    assert unbraced["adjustment_factors"]["CL"] < 1.0
    assert unbraced["flexure"]["Fb_adj_mpa"] < braced["flexure"]["Fb_adj_mpa"]
    assert unbraced["flexure"]["util"] > braced["flexure"]["util"]


def test_timber_beam_wet_service_reduces_capacity() -> None:
    dry = design_timber_beam(_inputs(moisture_pct=15.0))
    wet = design_timber_beam(_inputs(moisture_pct=25.0))
    assert wet["adjustment_factors"]["CM"] == 0.85
    assert wet["flexure"]["Fb_adj_mpa"] < dry["flexure"]["Fb_adj_mpa"]


def test_timber_beam_duration_factor() -> None:
    permanent = design_timber_beam(_inputs(duration="permanent"))
    momentary = design_timber_beam(_inputs(duration="momentary"))
    assert permanent["adjustment_factors"]["CD"] == 0.90
    assert momentary["adjustment_factors"]["CD"] == 1.32
    assert momentary["flexure"]["Fb_adj_mpa"] > permanent["flexure"]["Fb_adj_mpa"]


def test_timber_beam_deflection_limit() -> None:
    # Short span, deep beam -> deflection should be OK; shallow/long -> flag.
    ok = design_timber_beam(_inputs(span_m=3.0, depth_mm=350, moment_kn_m=20))
    assert ok["deflection"]["total_ok"] is True
    # Very shallow, long span -> likely exceeds L/240.
    bad = design_timber_beam(_inputs(span_m=6.0, depth_mm=120, moment_kn_m=60))
    assert bad["deflection"]["total_ok"] is False
    assert any("deflection" in w.lower() for w in bad["warnings"])


def test_timber_beam_unknown_species_raises() -> None:
    with pytest.raises(ValueError, match="Unknown species"):
        design_timber_beam(_inputs(species="not-a-species"))


def test_timber_beam_governs_and_pass_flag() -> None:
    # Overload the beam so flexure governs and pass is False.
    result = design_timber_beam(_inputs(moment_kn_m=200, shear_kn=200))
    assert result["pass"] is False
    assert result["governs"] in ("flexure", "shear")
    assert result["max_util"] > 1.0


def test_timber_beam_route() -> None:
    client = create_app().test_client()
    response = client.post(
        "/api/design/timber-beam",
        json={
            "species": "spf-no1",
            "width_mm": 90,
            "depth_mm": 240,
            "moment_kn_m": 20,
            "shear_kn": 15,
            "span_m": 3.0,
        },
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert data["results"]["code_reference"].startswith("NDS")


def test_timber_species_route() -> None:
    client = create_app().test_client()
    response = client.get("/api/design/timber-species")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert len(data["results"]["species"]) == len(SPECIES)


def test_timber_beam_route_unknown_species() -> None:
    client = create_app().test_client()
    response = client.post(
        "/api/design/timber-beam",
        json={
            "species": "bogus",
            "width_mm": 90,
            "depth_mm": 240,
            "moment_kn_m": 20,
            "span_m": 3.0,
        },
    )
    assert response.status_code == 400
    assert response.get_json()["status"] == "error"


def _inputs(**overrides) -> dict:
    base = {
        "species": "spf-no1",
        "width_mm": 90,
        "depth_mm": 240,
        "moment_kn_m": 20.0,
        "shear_kn": 15.0,
        "span_m": 3.0,
        "unbraced_length_m": 0.0,
        "duration": "normal",
        "moisture_pct": 19.0,
        "temperature_c": 20.0,
        "live_load_fraction": 0.5,
    }
    base.update(overrides)
    from app.models import TimberBeamInputs

    return TimberBeamInputs.model_validate(base)
