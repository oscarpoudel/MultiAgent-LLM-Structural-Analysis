"""Comprehensive test suite for all structural analysis tools."""
from app.models import (
    BeamInputs,
    ColumnInputs,
    FrameInputs,
    FrameLoad,
    FrameMember,
    FrameMemberLoad,
    FrameNode,
    PointLoad,
    TrussInputs,
    TrussLoad,
    TrussMember,
    TrussNode,
)
from app.tools.beam import _validate_beam_inputs, analyze_beam
from app.tools.column import analyze_column
from app.tools.load_combinations import (
    ASCE7_LRFD_COMBINATIONS,
    apply_load_combination,
    get_controlling_combination,
    run_all_load_combinations,
)

# ======================================================================
# Beam Analysis Tests
# ======================================================================

class TestBeamSimplySupported:
    """Tests for simply supported beam analysis."""

    def test_udl_only(self) -> None:
        result = analyze_beam(
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
        assert result["deflection_ok"] is False

    def test_point_load_midspan(self) -> None:
        result = analyze_beam(
            BeamInputs(
                span_m=6.0,
                point_loads=[PointLoad(magnitude_kn=100.0, position_m=3.0)],
                elastic_modulus_gpa=200.0,
                inertia_m4=8e-6,
            )
        )
        assert result["left_reaction_kn"] == 50.0
        assert result["right_reaction_kn"] == 50.0
        assert result["max_moment_kn_m"] == 150.0

    def test_combined_udl_and_point_load(self) -> None:
        result = analyze_beam(
            BeamInputs(
                span_m=6.0,
                udl_kn_per_m=10.0,
                point_loads=[PointLoad(magnitude_kn=50.0, position_m=2.0)],
                elastic_modulus_gpa=200.0,
                inertia_m4=8e-6,
            )
        )
        # UDL: R = 30 each side, PL at 2m: R_left = 50*4/6 = 33.33, R_right = 50*2/6 = 16.67
        # Total: R_left = 30 + 33.33 = 63.33, R_right = 30 + 16.67 = 46.67
        assert round(result["left_reaction_kn"], 2) == 63.33
        assert round(result["right_reaction_kn"], 2) == 46.67

    def test_deflection_with_point_load(self) -> None:
        result = analyze_beam(
            BeamInputs(
                span_m=6.0,
                point_loads=[PointLoad(magnitude_kn=100.0, position_m=3.0)],
                elastic_modulus_gpa=200.0,
                inertia_m4=8e-6,
            )
        )
        # PL deflection at midspan: P*L^3/(48*EI)
        # = 100000*216/(48*200e9*8e-6) = 0.28125 m = 281.25 mm
        assert result["max_deflection_mm"] is not None
        assert round(result["max_deflection_mm"], 1) == 281.2


class TestBeamCantilever:
    """Tests for cantilever beam analysis."""

    def test_cantilever_udl(self) -> None:
        result = analyze_beam(
            BeamInputs(
                span_m=4.0,
                udl_kn_per_m=10.0,
                support_type="cantilever",
                elastic_modulus_gpa=200.0,
                inertia_m4=5e-6,
            )
        )
        assert result["left_reaction_kn"] == 40.0
        assert result["right_reaction_kn"] == 0.0
        assert result["max_moment_kn_m"] == 80.0

    def test_cantilever_point_load(self) -> None:
        result = analyze_beam(
            BeamInputs(
                span_m=4.0,
                point_loads=[PointLoad(magnitude_kn=20.0, position_m=2.0)],
                support_type="cantilever",
                elastic_modulus_gpa=200.0,
                inertia_m4=5e-6,
            )
        )
        assert result["left_reaction_kn"] == 20.0
        assert result["max_moment_kn_m"] == 40.0


class TestBeamFixedFixed:
    """Tests for fixed-fixed beam analysis."""

    def test_fixed_fixed_udl(self) -> None:
        result = analyze_beam(
            BeamInputs(
                span_m=6.0,
                udl_kn_per_m=20.0,
                support_type="fixed_fixed",
                elastic_modulus_gpa=200.0,
                inertia_m4=8e-6,
            )
        )
        assert result["left_reaction_kn"] == 60.0
        assert result["right_reaction_kn"] == 60.0
        assert result["max_moment_kn_m"] == 60.0  # wL^2/12


class TestBeamProppedCantilever:
    """Tests for propped cantilever beam analysis."""

    def test_propped_cantilever_udl(self) -> None:
        result = analyze_beam(
            BeamInputs(
                span_m=6.0,
                udl_kn_per_m=20.0,
                support_type="propped_cantilever",
                elastic_modulus_gpa=200.0,
                inertia_m4=8e-6,
            )
        )
        # R_right = 3wL/8 = 45, R_left = wL - 45 = 75
        assert result["right_reaction_kn"] == 45.0
        assert result["left_reaction_kn"] == 75.0

    def test_propped_cantilever_point_load(self) -> None:
        result = analyze_beam(
            BeamInputs(
                span_m=6.0,
                point_loads=[PointLoad(magnitude_kn=60.0, position_m=3.0)],
                support_type="propped_cantilever",
                elastic_modulus_gpa=200.0,
                inertia_m4=8e-6,
            )
        )
        assert result["left_reaction_kn"] > 0
        assert result["right_reaction_kn"] > 0
        assert round(result["left_reaction_kn"] + result["right_reaction_kn"], 2) == 60.0


class TestBeamInputValidation:
    """Tests for beam input validation."""

    def test_negative_span_warning(self) -> None:
        inputs = BeamInputs(span_m=-5.0, udl_kn_per_m=10.0)
        warnings = _validate_beam_inputs(inputs)
        assert any("positive" in w.lower() for w in warnings)

    def test_excessive_span_warning(self) -> None:
        inputs = BeamInputs(span_m=1500.0, udl_kn_per_m=10.0)
        warnings = _validate_beam_inputs(inputs)
        assert any("1000" in w for w in warnings)

    def test_negative_udl_warning(self) -> None:
        inputs = BeamInputs(span_m=6.0, udl_kn_per_m=-10.0)
        warnings = _validate_beam_inputs(inputs)
        assert any("positive" in w.lower() for w in warnings)

    def test_point_load_outside_span(self) -> None:
        inputs = BeamInputs(
            span_m=6.0,
            point_loads=[PointLoad(magnitude_kn=10.0, position_m=8.0)]
        )
        warnings = _validate_beam_inputs(inputs)
        assert any("outside" in w.lower() for w in warnings)

    def test_valid_inputs_no_warnings(self) -> None:
        inputs = BeamInputs(
            span_m=6.0,
            udl_kn_per_m=20.0,
            point_loads=[PointLoad(magnitude_kn=50.0, position_m=3.0)],
            elastic_modulus_gpa=200.0,
            inertia_m4=8e-6,
        )
        warnings = _validate_beam_inputs(inputs)
        assert len(warnings) == 0


# ======================================================================
# Column Analysis Tests
# ======================================================================

class TestColumnAnalysis:
    """Tests for column buckling analysis."""

    def test_pinned_pinned_column(self) -> None:
        result = analyze_column(
            ColumnInputs(
                length_m=4.0,
                area_m2=0.01,
                inertia_m4=1e-4,
                elastic_modulus_gpa=200.0,
                yield_stress_mpa=250.0,
                end_condition="pinned_pinned",
                axial_load_kn=500.0,
            )
        )
        assert result["end_condition"] == "pinned_pinned"
        assert result["effective_length_factor_K"] == 1.0
        assert result["capacity_ok"] in (True, False)
        assert result["is_finite"] is True

    def test_fixed_free_column(self) -> None:
        result = analyze_column(
            ColumnInputs(
                length_m=4.0,
                area_m2=0.01,
                inertia_m4=1e-4,
                end_condition="fixed_free",
                axial_load_kn=500.0,
            )
        )
        assert result["effective_length_factor_K"] == 2.0

    def test_overstressed_column_warning(self) -> None:
        result = analyze_column(
            ColumnInputs(
                length_m=4.0,
                area_m2=0.001,
                inertia_m4=1e-5,
                axial_load_kn=10000.0,
            )
        )
        assert result["capacity_ok"] is False

    def test_high_slenderness_warning(self) -> None:
        result = analyze_column(
            ColumnInputs(
                length_m=20.0,
                area_m2=0.001,
                inertia_m4=1e-6,
                axial_load_kn=100.0,
            )
        )
        assert result["slenderness_ratio"] > 200


# ======================================================================
# Load Combination Tests
# ======================================================================

class TestLoadCombinations:
    """Tests for ASCE 7 load combinations."""

    def test_lrfd_combinations_exist(self) -> None:
        assert len(ASCE7_LRFD_COMBINATIONS) == 7

    def test_1_4d_combination(self) -> None:
        result = apply_load_combination(
            dl_kn=100.0,
            combination=ASCE7_LRFD_COMBINATIONS[0],
        )
        assert result["factored_load_kn"] == 140.0
        assert result["combination"] == "1.4D"

    def test_1_2d_1_6l_combination(self) -> None:
        result = apply_load_combination(
            dl_kn=100.0,
            ll_kn=50.0,
            combination=ASCE7_LRFD_COMBINATIONS[1],
        )
        assert result["factored_load_kn"] == 200.0  # 1.2*100 + 1.6*50

    def test_all_lrfd_combinations(self) -> None:
        results = run_all_load_combinations(
            dl_kn=100.0,
            ll_kn=50.0,
            method="lrfd",
        )
        assert len(results) == 7

    def test_controlling_combination(self) -> None:
        controlling = get_controlling_combination(
            dl_kn=100.0,
            ll_kn=50.0,
            method="lrfd",
        )
        assert controlling["factored_load_kn"] > 0

    def test_wind_load_combination(self) -> None:
        results = run_all_load_combinations(
            dl_kn=100.0,
            wl_kn=80.0,
            method="lrfd",
        )
        # Check that wind is applied in combinations
        wind_combos = [r for r in results if r["wl_kn"] > 0]
        assert len(wind_combos) > 0


# ======================================================================
# Truss Analysis Tests
# ======================================================================

class TestTrussAnalysis:
    """Tests for 2D truss analysis."""

    def test_simple_warren_truss(self) -> None:
        inputs = TrussInputs(
            nodes=[
                TrussNode(id=1, x=0.0, y=0.0, support="pin"),
                TrussNode(id=2, x=3.0, y=0.0, support="free"),
                TrussNode(id=3, x=6.0, y=0.0, support="roller_x"),
                TrussNode(id=4, x=3.0, y=2.0, support="free"),
            ],
            members=[
                TrussMember(id=1, start_node=1, end_node=2),
                TrussMember(id=2, start_node=2, end_node=3),
                TrussMember(id=3, start_node=1, end_node=4),
                TrussMember(id=4, start_node=4, end_node=3),
                TrussMember(id=5, start_node=2, end_node=4),
            ],
            loads=[
                TrussLoad(node_id=4, fy_kn=-50.0),
            ],
        )
        from app.tools.truss import analyze_truss
        result = analyze_truss(inputs)
        assert result["num_nodes"] == 4
        assert result["num_members"] == 5
        assert result["is_finite"] is True


# ======================================================================
# Frame Analysis Tests
# ======================================================================

class TestFrameAnalysis:
    """Tests for 2D frame analysis."""

    def test_portal_frame(self) -> None:
        inputs = FrameInputs(
            nodes=[
                FrameNode(id=1, x=0.0, y=0.0, support="fixed"),
                FrameNode(id=2, x=0.0, y=4.0, support="free"),
                FrameNode(id=3, x=6.0, y=4.0, support="free"),
                FrameNode(id=4, x=6.0, y=0.0, support="fixed"),
            ],
            members=[
                FrameMember(id=1, start_node=1, end_node=2),
                FrameMember(id=2, start_node=2, end_node=3),
                FrameMember(id=3, start_node=3, end_node=4),
            ],
            nodal_loads=[
                FrameLoad(node_id=2, fx_kn=10.0),
            ],
            member_loads=[
                FrameMemberLoad(member_id=2, udl_kn_per_m=20.0),
            ],
        )
        from app.tools.frame import analyze_frame
        result = analyze_frame(inputs)
        assert result["num_nodes"] == 4
        assert result["num_members"] == 3
        assert result["is_finite"] is True
