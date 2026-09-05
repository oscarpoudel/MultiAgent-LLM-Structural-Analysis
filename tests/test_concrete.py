"""Tests for ACI 318 concrete beam and column design (deterministic)."""
import math

from app.models import ConcreteBeamInputs, ConcreteColumnInputs
from app.tools.concrete import (
    _beam_design_reinforcement,
    _beam_design_shear,
    design_concrete_beam,
    design_concrete_column,
)


def test_beam_reinforcement_requires_positive_as_and_capacity() -> None:
    out = _beam_design_reinforcement(mu_kn_m=150.0, b_mm=300.0, d_mm=440.0, fck_mpa=25.0, fy_mpa=420.0)

    assert out["required_as_mm2"] > 0
    assert out["rho_ok"] is True
    # The design ratio honors the minimum even when the raw rho is below it.
    assert out["rho_design"] >= out["rho_min"]
    assert out["rho_design"] <= out["rho_max"]
    # Capacity must exceed the demand (utilization < 1 for an adequate section)
    assert out["phi_mn_kn_m"] > 150.0
    assert 0 < out["flex_util"] < 1.0


def test_beam_reinforcement_overreinforced_section_fails() -> None:
    # A tiny section for a huge moment -> Rn exceeds 0.85*f'c -> no real rho.
    out = _beam_design_reinforcement(mu_kn_m=5000.0, b_mm=200.0, d_mm=200.0, fck_mpa=25.0, fy_mpa=420.0)

    assert out["rho_ok"] is False
    assert out["over_reinforced"] is True
    assert out["rho_required"] is None  # infinite -> reported as None


def test_beam_shear_below_capacity_needs_no_stirrups() -> None:
    out = _beam_design_shear(vu_kn=50.0, b_mm=300.0, d_mm=440.0, fck_mpa=25.0, stirrup_dia_mm=10.0)

    assert out["stirrup_required"] is False
    assert out["spacing_mm"] is None
    assert out["vc_kn"] > 0


def test_beam_shear_above_capacity_computes_spacing() -> None:
    out = _beam_design_shear(vu_kn=250.0, b_mm=300.0, d_mm=440.0, fck_mpa=25.0, stirrup_dia_mm=10.0)

    assert out["stirrup_required"] is True
    assert out["spacing_mm"] is not None
    # Spacing is capped at d/2 and 600 mm.
    assert out["spacing_mm"] <= 440.0 / 2.0
    assert out["spacing_mm"] <= 600.0


def test_beam_shear_zero_demand() -> None:
    out = _beam_design_shear(vu_kn=0.0, b_mm=300.0, d_mm=440.0, fck_mpa=25.0, stirrup_dia_mm=10.0)

    assert out["stirrup_required"] is False
    assert out["vu_over_vc"] == 0.0


def test_design_concrete_beam_full_result() -> None:
    result = design_concrete_beam(
        ConcreteBeamInputs(moment_kn_m=150.0, shear_kn=80.0, width_mm=300.0, depth_mm=500.0)
    )

    assert result["code_reference"].startswith("ACI 318")
    # Effective depth = h - cover - stirrup - bar/2 = 500 - 40 - 10 - 10 = 440
    assert result["effective_depth_mm"] == 440.0
    assert result["flexure"]["phi_mn_kn_m"] > 150.0
    assert result["suggested_bars"]["count"] >= 1
    assert result["suggested_bars"]["spacing_ok"] is True


def test_design_concrete_beam_explicit_effective_depth() -> None:
    result = design_concrete_beam(
        ConcreteBeamInputs(
            moment_kn_m=150.0, shear_kn=80.0, width_mm=300.0, depth_mm=500.0, effective_depth_mm=450.0
        )
    )

    assert result["effective_depth_mm"] == 450.0


def test_design_concrete_beam_large_shear_warns() -> None:
    result = design_concrete_beam(
        ConcreteBeamInputs(moment_kn_m=150.0, shear_kn=250.0, width_mm=300.0, depth_mm=500.0)
    )

    assert result["shear"]["stirrup_required"] is True
    assert any("too small for the shear demand" in w for w in result["warnings"])


def test_design_concrete_beam_nonpositive_depth_warns() -> None:
    # depth 50 mm < cover(40) + stirrup(10) + bar/2(10) = 60 mm -> d goes negative.
    result = design_concrete_beam(
        ConcreteBeamInputs(moment_kn_m=50.0, shear_kn=10.0, width_mm=300.0, depth_mm=50.0)
    )

    assert any("non-positive" in w for w in result["warnings"])
    assert result["effective_depth_mm"] == 10.0


def test_design_concrete_beam_overreinforced_warns() -> None:
    # A tiny section for a very large moment -> over-reinforced.
    result = design_concrete_beam(
        ConcreteBeamInputs(moment_kn_m=5000.0, shear_kn=0.0, width_mm=200.0, depth_mm=200.0)
    )

    assert result["flexure"]["rho_ok"] is False
    assert any("over-reinforced" in w for w in result["warnings"])


def test_design_concrete_beam_tight_spacing_warns() -> None:
    # Narrow beam with a large required As -> many bars -> tight clear spacing.
    result = design_concrete_beam(
        ConcreteBeamInputs(moment_kn_m=400.0, shear_kn=0.0, width_mm=200.0, depth_mm=450.0)
    )

    assert result["suggested_bars"]["count"] > 1
    assert result["suggested_bars"]["spacing_ok"] is False
    assert any("below the minimum" in w for w in result["warnings"])


def test_design_concrete_beam_single_bar_no_spacing() -> None:
    # Small section + small moment -> minimum reinforcement fits in a single bar,
    # so no clear-spacing check applies.
    result = design_concrete_beam(
        ConcreteBeamInputs(moment_kn_m=5.0, shear_kn=0.0, width_mm=150.0, depth_mm=200.0)
    )

    assert result["suggested_bars"]["count"] == 1
    assert result["suggested_bars"]["clear_spacing_mm"] is None
    assert result["suggested_bars"]["spacing_ok"] is True


def test_design_concrete_column_tied_capacity_and_steel() -> None:
    result = design_concrete_column(
        ConcreteColumnInputs(axial_load_kn=800.0, diameter_mm=400.0)
    )

    a_g = math.pi / 4.0 * 400.0**2
    assert result["gross_area_mm2"] == round(a_g, 1)
    assert result["phi"] == 0.65
    assert result["slenderness_ok"] is True
    # Design steel at least the 1% minimum for tied columns.
    assert result["design_as_mm2"] >= round(0.01 * a_g, 1)
    assert result["rho_design"] >= 0.01
    # Capacity must exceed the demand.
    assert result["phi_pn_kn"] > 800.0
    assert 0 < result["util"] < 1.0
    assert result["suggested_bars"]["count"] >= 1


def test_design_concrete_column_spiral_higher_phi_and_min_rho() -> None:
    result = design_concrete_column(
        ConcreteColumnInputs(axial_load_kn=800.0, diameter_mm=400.0, tied=False)
    )

    assert result["phi"] == 0.75
    a_g = math.pi / 4.0 * 400.0**2
    # Spiral columns require at least 3% steel.
    assert result["rho_design"] >= 0.03
    assert result["design_as_mm2"] >= round(0.03 * a_g, 1)


def test_design_concrete_column_slender_warns() -> None:
    result = design_concrete_column(
        ConcreteColumnInputs(axial_load_kn=800.0, diameter_mm=400.0, kl_r=40.0)
    )

    assert result["slenderness_ok"] is False
    assert any("second-order" in w for w in result["warnings"])


def test_design_concrete_column_huge_load_exceeds_max_steel() -> None:
    result = design_concrete_column(
        ConcreteColumnInputs(axial_load_kn=20000.0, diameter_mm=400.0)
    )

    assert any("exceeds 8%" in w for w in result["warnings"])
    assert result["rho_design"] <= 0.08 + 1e-9
