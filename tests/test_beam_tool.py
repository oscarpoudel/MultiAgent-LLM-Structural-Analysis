from app.models import BeamInputs
from app.tools.beam import analyze_simply_supported_udl
from app.tools.opensees_beam import analyze_simply_supported_udl_opensees


def test_simply_supported_udl_beam_results() -> None:
    result = analyze_simply_supported_udl(
        BeamInputs(
            span_m=6.0,
            udl_kn_per_m=20.0,
            elastic_modulus_gpa=200.0,
            inertia_m4=8e-6,
            deflection_limit_ratio=360.0,
        )
    )

    assert result["max_reaction_kn"] == 60.0
    assert result["max_shear_kn"] == 60.0
    assert result["max_moment_kn_m"] == 90.0
    assert round(float(result["max_deflection_mm"]), 2) == 210.94
    assert round(float(result["deflection_limit_mm"]), 2) == 16.67
    assert result["deflection_ok"] is False


def test_opensees_simply_supported_udl_beam_results() -> None:
    result = analyze_simply_supported_udl_opensees(
        BeamInputs(
            span_m=6.0,
            udl_kn_per_m=20.0,
            elastic_modulus_gpa=200.0,
            inertia_m4=8e-6,
            deflection_limit_ratio=360.0,
        )
    )

    assert result["solver"] == "openseespy_elastic_beam"
    assert result["opensees_status"] == 0
    assert round(float(result["left_reaction_kn"]), 2) == 60.0
    assert round(float(result["right_reaction_kn"]), 2) == 60.0
    assert round(float(result["max_deflection_mm"]), 2) == 210.94
    assert result["deflection_ok"] is False
