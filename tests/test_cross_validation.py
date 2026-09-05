"""Tests for the independent-solver cross-validation suite."""
from app.main import create_app
from app.tools.cross_validation import REL_TOL, _compare, _rel_diff, run_cross_validation


def test_rel_diff_is_symmetric_and_scaled() -> None:
    assert _rel_diff(10.0, 10.0) == 0.0
    assert _rel_diff(10.0, 10.5) == _rel_diff(10.5, 10.0)
    assert _rel_diff(0.0, 0.0) == 0.0
    assert _rel_diff(100.0, 0.0) == 1.0


def test_compare_flags_out_of_tolerance() -> None:
    ok = _compare("q", {"a": 10.0, "b": 10.1})
    bad = _compare("q", {"a": 10.0, "b": 15.0})
    assert ok["pass"] is True
    assert bad["pass"] is False
    assert bad["max_rel_diff"] > REL_TOL


def test_all_benchmarks_pass() -> None:
    result = run_cross_validation()
    assert result["total_checks"] > 0
    assert result["passed_checks"] == result["total_checks"]
    assert result["all_pass"] is True
    for checks in result["benchmarks"].values():
        for check in checks:
            assert check["pass"] is True


def test_truss_member_forces_agree_in_sign() -> None:
    # Regression: the OpenSees truss force extraction once reported tension as
    # compression. The cross-validation compares signed axial forces, so a sign
    # flip fails the suite.
    result = run_cross_validation()
    truss_axial = [
        c for c in result["benchmarks"]["truss"]
        if c["quantity"].startswith("truss: member")
    ]
    assert len(truss_axial) >= 7
    for check in truss_axial:
        values = check["values"]
        assert values["opensees"] == values["direct_stiffness"]


def test_frame_member_moments_agree() -> None:
    # Regression: the direct-stiffness frame member forces omitted the
    # fixed-end force contribution, so moments were off by wL^2/12.
    result = run_cross_validation()
    frame_moment = [
        c for c in result["benchmarks"]["frame"]
        if c["quantity"].startswith("frame: member")
    ]
    assert frame_moment
    for check in frame_moment:
        assert check["pass"] is True


def test_cross_validation_route() -> None:
    client = create_app().test_client()
    response = client.post("/api/loads/cross-validation")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert data["results"]["all_pass"] is True
    assert data["results"]["total_checks"] > 0
