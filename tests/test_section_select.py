"""Tests for AISC 360 steel section selection tools."""
from app.models import BeamSelectionInputs, ColumnSelectionInputs
from app.tools.section_select import (
    _column_capacity,
    _ltb_capacity,
    _shear_capacity,
    select_beam,
    select_column,
)
from app.tools.sections import get_section


class TestCapacityFunctions:
    def test_ltb_fully_braced_gives_mp(self) -> None:
        s = get_section("W250X58")
        assert s is not None
        mn = _ltb_capacity(s, 345.0, 0.0)
        mp = 345.0 * s.zx_m3 * 1e9 / 1e6  # kN-m
        assert abs(mn - mp) < 1e-6

    def test_ltb_longer_span_lower_capacity(self) -> None:
        s = get_section("W250X58")
        mn_short = _ltb_capacity(s, 345.0, 2.0)
        mn_long = _ltb_capacity(s, 345.0, 10.0)
        assert mn_long < mn_short

    def test_shear_capacity_positive(self) -> None:
        s = get_section("W250X58")
        vn = _shear_capacity(s, 345.0)
        assert vn > 0

    def test_column_capacity_positive(self) -> None:
        s = get_section("W250X58")
        pn = _column_capacity(s, 345.0, 4.0)
        assert pn > 0

    def test_column_capacity_longer_kl_lower(self) -> None:
        s = get_section("W250X58")
        pn_short = _column_capacity(s, 345.0, 3.0)
        pn_long = _column_capacity(s, 345.0, 8.0)
        assert pn_long < pn_short


class TestBeamSelection:
    def test_small_moment_selects_light_section(self) -> None:
        result = select_beam(BeamSelectionInputs(moment_kn_m=50.0, shear_kn=20.0, unbraced_length_m=0.0))
        assert result["selected"] is not None
        assert result["selected"]["name"].startswith("W")
        assert result["selected"]["flex_util"] <= 1.0
        assert result["selected"]["shear_util"] <= 1.0

    def test_higher_moment_selects_heavier(self) -> None:
        light = select_beam(BeamSelectionInputs(moment_kn_m=50.0, unbraced_length_m=0.0))
        heavy = select_beam(BeamSelectionInputs(moment_kn_m=500.0, unbraced_length_m=0.0))
        assert heavy["selected"]["weight_kg_per_m"] >= light["selected"]["weight_kg_per_m"]

    def test_unbraced_length_increases_weight(self) -> None:
        braced = select_beam(BeamSelectionInputs(moment_kn_m=200.0, unbraced_length_m=0.0))
        unbraced = select_beam(BeamSelectionInputs(moment_kn_m=200.0, unbraced_length_m=8.0))
        assert unbraced["selected"]["weight_kg_per_m"] >= braced["selected"]["weight_kg_per_m"]

    def test_huge_moment_no_candidate(self) -> None:
        result = select_beam(BeamSelectionInputs(moment_kn_m=1e6, unbraced_length_m=0.0))
        assert result["selected"] is None
        assert any("No W-shape" in w for w in result["warnings"])

    def test_candidates_sorted_by_weight(self) -> None:
        result = select_beam(BeamSelectionInputs(moment_kn_m=100.0, unbraced_length_m=0.0))
        weights = [c["weight_kg_per_m"] for c in result["candidates"]]
        assert weights == sorted(weights)

    def test_shear_governs_for_high_shear(self) -> None:
        result = select_beam(BeamSelectionInputs(moment_kn_m=10.0, shear_kn=1000.0, unbraced_length_m=0.0))
        assert result["selected"] is not None
        assert result["selected"]["shear_util"] <= 1.0


class TestColumnSelection:
    def test_small_load_selects_light_section(self) -> None:
        result = select_column(ColumnSelectionInputs(axial_load_kn=500.0, kl_m=4.0))
        assert result["selected"] is not None
        assert result["selected"]["util"] <= 1.0

    def test_higher_load_selects_heavier(self) -> None:
        light = select_column(ColumnSelectionInputs(axial_load_kn=500.0, kl_m=4.0))
        heavy = select_column(ColumnSelectionInputs(axial_load_kn=3000.0, kl_m=4.0))
        assert heavy["selected"]["weight_kg_per_m"] >= light["selected"]["weight_kg_per_m"]

    def test_longer_kl_selects_heavier(self) -> None:
        short = select_column(ColumnSelectionInputs(axial_load_kn=2000.0, kl_m=3.0))
        long_ = select_column(ColumnSelectionInputs(axial_load_kn=2000.0, kl_m=8.0))
        assert long_["selected"]["weight_kg_per_m"] >= short["selected"]["weight_kg_per_m"]

    def test_huge_load_no_candidate(self) -> None:
        result = select_column(ColumnSelectionInputs(axial_load_kn=1e6, kl_m=4.0))
        assert result["selected"] is None
        assert any("No W-shape" in w for w in result["warnings"])
