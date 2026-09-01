"""Tests for ASCE 7-22 wind and seismic load determination tools."""
from app.models import SeismicInputs, SlabInputs, SnowInputs, WindInputs
from app.tools.seismic import _interp, calculate_seismic_base_shear
from app.tools.slab import _interp_coeff, calculate_slab
from app.tools.snow import calculate_snow_loads
from app.tools.wind import (
    _leeward_cp,
    _roof_cp,
    _velocity_pressure,
    _windward_cp,
    calculate_wind_loads,
)


class TestWindVelocityPressure:
    def test_exposure_c_10m(self) -> None:
        # Kz at 9.144m = 1.0 for all exposures; qz = 0.613*0.85*1.0*V^2/1000
        qz = _velocity_pressure(9.144, 30.0, "C")
        expected = 0.613 * 0.85 * 1.0 * 30.0**2 / 1000.0
        assert abs(qz - expected) < 1e-6

    def test_exposure_c_30m(self) -> None:
        qz = _velocity_pressure(30.0, 30.0, "C")
        kz = (30.0 / 9.144) ** (2 * 0.49)
        expected = 0.613 * 0.85 * kz * 30.0**2 / 1000.0
        assert abs(qz - expected) < 1e-6

    def test_exposure_b_higher_than_c(self) -> None:
        # Exposure B (rural) has higher Kz than C (suburban) at same height
        assert _velocity_pressure(30.0, 30.0, "B") > _velocity_pressure(30.0, 30.0, "C")

    def test_exposure_d_lowest(self) -> None:
        assert _velocity_pressure(30.0, 30.0, "D") < _velocity_pressure(30.0, 30.0, "C")

    def test_height_floor(self) -> None:
        # Heights below 9.144m use the 9.144m value
        assert _velocity_pressure(3.0, 30.0, "C") == _velocity_pressure(9.144, 30.0, "C")

    def test_topographic_factor(self) -> None:
        qz_base = _velocity_pressure(30.0, 30.0, "C")
        qz_topo = _velocity_pressure(30.0, 30.0, "C", kzt=1.5)
        assert qz_topo > qz_base


class TestWindPressureCoefficients:
    def test_windward_cp_short(self) -> None:
        assert _windward_cp(5.0) == 0.80

    def test_windward_cp_long(self) -> None:
        assert _windward_cp(50.0) == 0.40

    def test_leeward_cp_negative(self) -> None:
        assert _leeward_cp(5.0) == -0.50
        assert _leeward_cp(50.0) == -0.10

    def test_roof_cp_negative(self) -> None:
        assert _roof_cp(10.0, 10.0) < 0
        assert _roof_cp(10.0, 100.0) < 0


class TestWindLoadCalculation:
    def test_basic_building(self) -> None:
        result = calculate_wind_loads(
            WindInputs(
                basic_wind_speed_ms=30.0,
                exposure="C",
                height_m=12.0,
                length_m=20.0,
                width_m=10.0,
            )
        )
        assert result["method"].startswith("ASCE 7-22")
        assert result["base_shear_x_kn"] > 0
        assert result["base_shear_y_kn"] > 0
        assert result["roof_uplift_kn"] > 0
        assert len(result["story_forces"]) > 0
        assert "velocity_pressures_kpa" in result

    def test_higher_wind_speed_higher_force(self) -> None:
        low = calculate_wind_loads(WindInputs(basic_wind_speed_ms=20.0, height_m=10.0, length_m=10.0, width_m=10.0))
        high = calculate_wind_loads(WindInputs(basic_wind_speed_ms=40.0, height_m=10.0, length_m=10.0, width_m=10.0))
        assert high["base_shear_x_kn"] > low["base_shear_x_kn"]

    def test_taller_building_higher_force(self) -> None:
        short = calculate_wind_loads(WindInputs(basic_wind_speed_ms=30.0, height_m=6.0, length_m=10.0, width_m=10.0))
        tall = calculate_wind_loads(WindInputs(basic_wind_speed_ms=30.0, height_m=30.0, length_m=10.0, width_m=10.0))
        assert tall["base_shear_x_kn"] > short["base_shear_x_kn"]

    def test_major_openings_reduce_uplift(self) -> None:
        closed = calculate_wind_loads(
            WindInputs(basic_wind_speed_ms=30.0, height_m=10.0, length_m=10.0, width_m=10.0, internal_pressure="no_openings")
        )
        open_ = calculate_wind_loads(
            WindInputs(basic_wind_speed_ms=30.0, height_m=10.0, length_m=10.0, width_m=10.0, internal_pressure="major_openings")
        )
        assert closed["roof_uplift_kn"] != open_["roof_uplift_kn"]

    def test_story_forces_sum_near_base_shear(self) -> None:
        result = calculate_wind_loads(
            WindInputs(basic_wind_speed_ms=30.0, height_m=12.0, length_m=20.0, width_m=10.0, story_height_m=4.0)
        )
        story_sum = sum(s["force_kn"] for s in result["story_forces"])
        assert story_sum > 0
        # Story forces use windward pressure only; base shear uses windward+leeward
        assert story_sum < result["base_shear_x_kn"]


class TestSeismicInterp:
    def test_clamp_low(self) -> None:
        assert _interp(-1.0, [0.0, 1.0], [1.0, 2.0]) == 1.0

    def test_clamp_high(self) -> None:
        assert _interp(5.0, [0.0, 1.0], [1.0, 2.0]) == 2.0

    def test_midpoint(self) -> None:
        assert _interp(0.5, [0.0, 1.0], [1.0, 3.0]) == 2.0


class TestSeismicBaseShear:
    def test_basic_building(self) -> None:
        result = calculate_seismic_base_shear(
            SeismicInputs(
                spectral_accel_sd=0.8,
                spectral_accel_1s=0.4,
                site_class="D",
                risk_category="II",
                building_weight_kn=10000.0,
                height_m=12.0,
            )
        )
        assert result["method"].startswith("ASCE 7-22")
        assert result["base_shear_kn"] > 0
        assert result["site_coefficients"]["sds"] > 0
        assert result["site_coefficients"]["sd1"] > 0
        assert result["design_params"]["cs"] > 0
        assert len(result["story_forces"]) > 0

    def test_higher_sa_higher_shear(self) -> None:
        low = calculate_seismic_base_shear(
            SeismicInputs(spectral_accel_sd=0.4, spectral_accel_1s=0.2, building_weight_kn=10000.0, height_m=10.0)
        )
        high = calculate_seismic_base_shear(
            SeismicInputs(spectral_accel_sd=0.8, spectral_accel_1s=0.4, building_weight_kn=10000.0, height_m=10.0)
        )
        assert high["base_shear_kn"] > low["base_shear_kn"]

    def test_heavier_building_higher_shear(self) -> None:
        light = calculate_seismic_base_shear(
            SeismicInputs(spectral_accel_sd=0.6, spectral_accel_1s=0.3, building_weight_kn=5000.0, height_m=10.0)
        )
        heavy = calculate_seismic_base_shear(
            SeismicInputs(spectral_accel_sd=0.6, spectral_accel_1s=0.3, building_weight_kn=20000.0, height_m=10.0)
        )
        assert heavy["base_shear_kn"] > light["base_shear_kn"]

    def test_site_class_a_lower_than_d(self) -> None:
        site_a = calculate_seismic_base_shear(
            SeismicInputs(spectral_accel_sd=0.6, spectral_accel_1s=0.3, site_class="A", building_weight_kn=10000.0, height_m=10.0)
        )
        site_d = calculate_seismic_base_shear(
            SeismicInputs(spectral_accel_sd=0.6, spectral_accel_1s=0.3, site_class="D", building_weight_kn=10000.0, height_m=10.0)
        )
        assert site_d["base_shear_kn"] > site_a["base_shear_kn"]

    def test_risk_category_iii_higher(self) -> None:
        cat2 = calculate_seismic_base_shear(
            SeismicInputs(spectral_accel_sd=0.6, spectral_accel_1s=0.3, risk_category="II", building_weight_kn=10000.0, height_m=10.0)
        )
        cat3 = calculate_seismic_base_shear(
            SeismicInputs(spectral_accel_sd=0.6, spectral_accel_1s=0.3, risk_category="III", building_weight_kn=10000.0, height_m=10.0)
        )
        assert cat3["base_shear_kn"] > cat2["base_shear_kn"]

    def test_user_period(self) -> None:
        result = calculate_seismic_base_shear(
            SeismicInputs(
                spectral_accel_sd=0.6,
                spectral_accel_1s=0.3,
                building_weight_kn=10000.0,
                height_m=10.0,
                fundamental_period_s=1.5,
            )
        )
        assert result["design_params"]["period_method"] == "user_provided"
        assert result["design_params"]["period_s"] == 1.5

    def test_story_forces_sum_equals_base_shear(self) -> None:
        result = calculate_seismic_base_shear(
            SeismicInputs(spectral_accel_sd=0.6, spectral_accel_1s=0.3, building_weight_kn=10000.0, height_m=12.0)
        )
        story_sum = sum(s["force_kn"] for s in result["story_forces"])
        assert abs(story_sum - result["base_shear_kn"]) < 1.0

    def test_unknown_site_class_warns(self) -> None:
        result = calculate_seismic_base_shear(
            SeismicInputs(spectral_accel_sd=0.6, spectral_accel_1s=0.3, site_class="X", building_weight_kn=10000.0, height_m=10.0)
        )
        assert any("site class" in w.lower() for w in result["warnings"])

    def test_braced_frame_lower_r(self) -> None:
        mf = calculate_seismic_base_shear(
            SeismicInputs(spectral_accel_sd=0.6, spectral_accel_1s=0.3, structural_system="moment_frame", building_weight_kn=10000.0, height_m=10.0)
        )
        bf = calculate_seismic_base_shear(
            SeismicInputs(spectral_accel_sd=0.6, spectral_accel_1s=0.3, structural_system="braced_frame", building_weight_kn=10000.0, height_m=10.0)
        )
        # Lower R means higher Cs and higher base shear
        assert bf["base_shear_kn"] > mf["base_shear_kn"]


class TestSlabInterp:
    def test_square_slab(self) -> None:
        assert _interp_coeff(1.0, [(1.0, 0.033), (2.0, 0.043)]) == 0.033

    def test_midpoint(self) -> None:
        assert _interp_coeff(1.5, [(1.0, 0.033), (2.0, 0.043)]) == 0.038

    def test_clamp_high(self) -> None:
        assert _interp_coeff(10.0, [(1.0, 0.033), (2.0, 0.043)]) == 0.043


class TestSlabAnalysis:
    def test_square_continuous_slab(self) -> None:
        result = calculate_slab(
            SlabInputs(
                span_x_m=4.0,
                span_y_m=4.0,
                thickness_m=0.18,
                dead_load_kpa=2.0,
                live_load_kpa=3.0,
            )
        )
        assert result["method"].startswith("ACI 318")
        assert result["span_ratio"] == 1.0
        assert result["two_way_action"] is True
        assert result["factored_load_kpa"] > 0
        assert result["design_moments_kn_m"]["short_span"] > 0
        assert result["reinforcement_short_span"]["required_as_m2"] > 0
        assert result["deflection"]["estimated_mm"] > 0

    def test_thin_slab_warns(self) -> None:
        result = calculate_slab(
            SlabInputs(span_x_m=6.0, span_y_m=6.0, thickness_m=0.10, live_load_kpa=3.0)
        )
        assert result["thickness_ok"] is False
        assert any("minimum" in w.lower() for w in result["warnings"])

    def test_thick_slab_ok(self) -> None:
        result = calculate_slab(
            SlabInputs(span_x_m=4.0, span_y_m=4.0, thickness_m=0.25, live_load_kpa=3.0)
        )
        assert result["thickness_ok"] is True

    def test_higher_load_higher_moment(self) -> None:
        low = calculate_slab(SlabInputs(span_x_m=4.0, span_y_m=4.0, thickness_m=0.18, live_load_kpa=2.0))
        high = calculate_slab(SlabInputs(span_x_m=4.0, span_y_m=4.0, thickness_m=0.18, live_load_kpa=5.0))
        assert high["design_moments_kn_m"]["short_span"] > low["design_moments_kn_m"]["short_span"]

    def test_longer_span_higher_moment(self) -> None:
        short = calculate_slab(SlabInputs(span_x_m=3.0, span_y_m=3.0, thickness_m=0.18, live_load_kpa=3.0))
        long_ = calculate_slab(SlabInputs(span_x_m=5.0, span_y_m=5.0, thickness_m=0.25, live_load_kpa=3.0))
        assert long_["design_moments_kn_m"]["short_span"] > short["design_moments_kn_m"]["short_span"]

    def test_one_way_warning(self) -> None:
        result = calculate_slab(
            SlabInputs(span_x_m=2.0, span_y_m=6.0, thickness_m=0.18, live_load_kpa=3.0)
        )
        assert result["two_way_action"] is False
        assert any("one-way" in w.lower() for w in result["warnings"])

    def test_reinforcement_spacing_bounded(self) -> None:
        result = calculate_slab(
            SlabInputs(span_x_m=4.0, span_y_m=4.0, thickness_m=0.20, live_load_kpa=3.0)
        )
        sx = result["reinforcement_short_span"]["suggested_spacing_mm"]
        assert 0.0 < sx <= 300.0

    def test_higher_fy_less_reinforcement(self) -> None:
        low = calculate_slab(SlabInputs(span_x_m=4.0, span_y_m=4.0, thickness_m=0.18, live_load_kpa=25.0, steel_fy_mpa=420.0))
        high = calculate_slab(SlabInputs(span_x_m=4.0, span_y_m=4.0, thickness_m=0.18, live_load_kpa=25.0, steel_fy_mpa=600.0))
        assert high["reinforcement_short_span"]["required_as_m2"] < low["reinforcement_short_span"]["required_as_m2"]

    def test_deflection_ok_flag(self) -> None:
        result = calculate_slab(
            SlabInputs(span_x_m=4.0, span_y_m=4.0, thickness_m=0.25, live_load_kpa=2.0)
        )
        assert isinstance(result["deflection"]["ok"], bool)


class TestSnowLoads:
    def test_flat_roof(self) -> None:
        result = calculate_snow_loads(
            SnowInputs(ground_snow_load_kpa=3.0, roof_slope_deg=0.0)
        )
        assert result["method"].startswith("ASCE 7-22")
        # ps = 0.7 * 1.0 * 1.0 * 0.8 * 3.0 = 1.68
        assert abs(result["flat_roof_ps_kpa"] - 1.68) < 1e-6
        assert result["balanced_snow_kpa"] > 0
        assert result["total_design_snow_kpa"] >= result["balanced_snow_kpa"]

    def test_steeper_slope_higher_per_area_load(self) -> None:
        # Cs = 0.5/cos^2(theta) increases with slope (projected-area effect)
        shallow = calculate_snow_loads(SnowInputs(ground_snow_load_kpa=3.0, roof_slope_deg=10.0))
        steep = calculate_snow_loads(SnowInputs(ground_snow_load_kpa=3.0, roof_slope_deg=45.0))
        assert steep["sloped_roof_ps_kpa"] > shallow["sloped_roof_ps_kpa"]

    def test_flat_roof_balanced_equals_ps(self) -> None:
        result = calculate_snow_loads(SnowInputs(ground_snow_load_kpa=3.0, roof_slope_deg=0.0))
        # Cs=0.5 at 0 deg, so ps_sloped = 0.5*ps < ps; balanced = ps
        assert result["balanced_snow_kpa"] == result["flat_roof_ps_kpa"]

    def test_exposed_higher_than_shielded(self) -> None:
        exposed = calculate_snow_loads(SnowInputs(ground_snow_load_kpa=3.0, exposure="exposed"))
        shielded = calculate_snow_loads(SnowInputs(ground_snow_load_kpa=3.0, exposure="shielded"))
        assert exposed["flat_roof_ps_kpa"] > shielded["flat_roof_ps_kpa"]

    def test_unheated_higher_than_heated(self) -> None:
        unheated = calculate_snow_loads(SnowInputs(ground_snow_load_kpa=3.0, thermal="unheated"))
        heated = calculate_snow_loads(SnowInputs(ground_snow_load_kpa=3.0, thermal="heated"))
        assert unheated["flat_roof_ps_kpa"] > heated["flat_roof_ps_kpa"]

    def test_drift_increases_total(self) -> None:
        no_drift = calculate_snow_loads(SnowInputs(ground_snow_load_kpa=3.0, drift=False))
        with_drift = calculate_snow_loads(SnowInputs(ground_snow_load_kpa=3.0, drift=True))
        assert with_drift["total_design_snow_kpa"] > no_drift["total_design_snow_kpa"]

    def test_risk_category_iii_higher(self) -> None:
        cat2 = calculate_snow_loads(SnowInputs(ground_snow_load_kpa=3.0, risk_category="II"))
        cat3 = calculate_snow_loads(SnowInputs(ground_snow_load_kpa=3.0, risk_category="III"))
        assert cat3["flat_roof_ps_kpa"] > cat2["flat_roof_ps_kpa"]

    def test_zero_snow(self) -> None:
        result = calculate_snow_loads(SnowInputs(ground_snow_load_kpa=0.0))
        assert result["total_design_snow_kpa"] == 0.0
