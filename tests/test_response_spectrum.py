import math

import pytest
from app.main import create_app
from app.models import Member3D, Node3D, Structure3DInputs, Support3D
from app.tools.response_spectrum import design_spectral_acceleration, response_spectrum_analysis


def cantilever_model(*, rigid_diaphragms: bool = False) -> Structure3DInputs:
    return Structure3DInputs(
        nodes=[
            Node3D(
                id=1,
                x=0,
                y=0,
                z=0,
                support=Support3D(ux=True, uy=True, uz=True, rx=True, ry=True, rz=True),
            ),
            Node3D(id=2, x=0, y=0, z=3),
        ],
        members=[
            Member3D(
                id=1,
                start_node=1,
                end_node=2,
                elastic_modulus_gpa=200,
                iy_m4=2e-4,
                iz_m4=2e-4,
            )
        ],
        rigid_diaphragms=rigid_diaphragms,
    )


def test_asce_design_spectrum_regions_are_continuous() -> None:
    sds = 1.0
    sd1 = 0.5
    ts = sd1 / sds
    t0 = 0.2 * ts

    assert design_spectral_acceleration(0.0, sds, sd1) == pytest.approx(0.4)
    assert design_spectral_acceleration(t0, sds, sd1) == pytest.approx(sds)
    assert design_spectral_acceleration(ts, sds, sd1) == pytest.approx(sds)
    assert design_spectral_acceleration(1.0, sds, sd1) == pytest.approx(0.5)
    assert design_spectral_acceleration(8.0, sds, sd1, long_period_s=8.0) == pytest.approx(sd1 / 8.0)
    assert design_spectral_acceleration(16.0, sds, sd1, long_period_s=8.0) == pytest.approx(
        sd1 * 8.0 / 16.0**2
    )


def test_single_story_cantilever_period_matches_closed_form() -> None:
    model = cantilever_model()
    weight_kn = 100.0
    result = response_spectrum_analysis(model, weight_kn, sds=1.0, sd1=0.5, num_modes=1)

    mass = weight_kn / 9.80665
    stiffness = 3.0 * 200e6 * 2e-4 / 3.0**3
    expected_period = 2.0 * math.pi * math.sqrt(mass / stiffness)

    assert result["modes"][0]["period_s"] == pytest.approx(expected_period, rel=1e-5)
    assert result["modes"][0]["effective_mass_ratio"] == pytest.approx(1.0)
    assert result["cumulative_mass_ratio"] == pytest.approx(1.0)
    assert result["base_shear_kn"] > 0
    assert result["story_drifts"][0]["drift_mm"] > 0


def test_rigid_diaphragm_story_stiffness_shortens_period() -> None:
    free = response_spectrum_analysis(cantilever_model(), 100.0, sds=1.0, sd1=0.5, num_modes=1)
    rigid = response_spectrum_analysis(
        cantilever_model(rigid_diaphragms=True), 100.0, sds=1.0, sd1=0.5, num_modes=1
    )

    assert rigid["modes"][0]["period_s"] == pytest.approx(
        free["modes"][0]["period_s"] / 2.0, rel=1e-5
    )


def test_response_spectrum_rejects_invalid_or_unmodelled_inputs() -> None:
    with pytest.raises(ValueError, match="direction"):
        response_spectrum_analysis(cantilever_model(), 100, 1.0, 0.5, direction="z")
    with pytest.raises(ValueError, match="weight"):
        response_spectrum_analysis(cantilever_model(), 0, 1.0, 0.5)
    with pytest.raises(ValueError, match="elevation"):
        response_spectrum_analysis(Structure3DInputs(nodes=[], members=[]), 100, 1.0, 0.5)


def test_response_spectrum_route() -> None:
    client = create_app().test_client()
    response = client.post(
        "/api/loads/response-spectrum",
        json={
            "model": cantilever_model().model_dump(mode="json"),
            "building_weight_kn": 100,
            "sds": 1.0,
            "sd1": 0.5,
            "direction": "x",
            "num_modes": 1,
        },
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert data["results"]["method"].startswith("Lumped-mass")
    assert data["results"]["base_shear_kn"] > 0


def test_response_spectrum_route_validates_payload() -> None:
    client = create_app().test_client()
    response = client.post("/api/loads/response-spectrum", json={})

    assert response.status_code == 400
    assert response.get_json()["status"] == "error"
