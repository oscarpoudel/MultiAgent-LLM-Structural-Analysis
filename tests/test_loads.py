"""Tests for ASCE 7-22 wind and seismic load determination tools."""
from app.models import SeismicInputs, WindInputs
from app.tools.seismic import _interp, calculate_seismic_base_shear
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
