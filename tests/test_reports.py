"""Tests for report formatters (truss, frame, column, beam)."""
from app.models import (
    BeamInputs,
    ColumnInputs,
    FrameInputs,
    FrameLoad,
    FrameMember,
    FrameNode,
    TrussInputs,
    TrussLoad,
    TrussMember,
    TrussNode,
)
from app.tools.beam import analyze_beam
from app.tools.column import analyze_column
from app.tools.frame import analyze_frame
from app.tools.report import format_engineering_report
from app.tools.truss import analyze_truss


def _truss_results() -> dict:
    inputs = TrussInputs(
        nodes=[
            TrussNode(id=1, x=0.0, y=0.0, support="pin"),
            TrussNode(id=2, x=3.0, y=0.0, support="roller_x"),
            TrussNode(id=3, x=1.5, y=2.0, support="free"),
        ],
        members=[
            TrussMember(id=1, start_node=1, end_node=3, area_m2=0.002),
            TrussMember(id=2, start_node=2, end_node=3, area_m2=0.002),
            TrussMember(id=3, start_node=1, end_node=2, area_m2=0.002),
        ],
        loads=[TrussLoad(node_id=3, fx_kn=0.0, fy_kn=-20.0)],
    )
    return analyze_truss(inputs)


def _frame_results() -> dict:
    inputs = FrameInputs(
        nodes=[
            FrameNode(id=1, x=0.0, y=0.0, support="fixed"),
            FrameNode(id=2, x=6.0, y=0.0, support="fixed"),
            FrameNode(id=3, x=0.0, y=4.0, support="free"),
            FrameNode(id=4, x=6.0, y=4.0, support="free"),
        ],
        members=[
            FrameMember(id=1, start_node=1, end_node=3, area_m2=0.01, inertia_m4=1e-4),
            FrameMember(id=2, start_node=2, end_node=4, area_m2=0.01, inertia_m4=1e-4),
            FrameMember(id=3, start_node=3, end_node=4, area_m2=0.01, inertia_m4=1e-4),
        ],
        nodal_loads=[FrameLoad(node_id=4, fx_kn=20.0, fy_kn=-10.0)],
    )
    return analyze_frame(inputs)


def test_truss_report() -> None:
    results = _truss_results()
    report = format_engineering_report(
        "Analyze a simple truss",
        ["Pin-connected joints"],
        ["Warning: check buckling"],
        results,
        analysis_type="truss",
    )
    assert "# Preliminary Truss Analysis Report" in report
    assert "2D Truss Analysis" in report
    assert "## Support Reactions" in report
    assert "## Member Forces" in report
    assert "## Warnings" in report
    assert "Warning: check buckling" in report
    assert "## Engineering Note" in report


def test_frame_report() -> None:
    results = _frame_results()
    report = format_engineering_report(
        "Analyze a portal frame",
        ["Fixed bases"],
        [],
        results,
        analysis_type="frame",
    )
    assert "# Preliminary Frame Analysis Report" in report
    assert "2D Frame Analysis" in report
    assert "## Support Reactions" in report
    assert "## Member End Forces" in report
    assert "## Engineering Note" in report


def test_column_report() -> None:
    results = analyze_column(
        ColumnInputs(
            length_m=4.0,
            area_m2=0.01,
            inertia_m4=1e-4,
            elastic_modulus_gpa=200.0,
            yield_stress_mpa=345.0,
            end_condition="pinned_pinned",
            axial_load_kn=500.0,
        )
    )
    report = format_engineering_report(
        "Check a column",
        ["Pinned ends"],
        [],
        results,
        analysis_type="column",
    )
    assert "# Preliminary Column Analysis Report" in report
    assert "Column Buckling / Capacity Check" in report
    assert "## Results" in report
    assert "## Engineering Note" in report


def test_beam_report_default() -> None:
    results = analyze_beam(BeamInputs(span_m=6.0, udl_kn_per_m=20.0))
    report = format_engineering_report(
        "Analyze a beam",
        ["Simply supported"],
        [],
        results,
        analysis_type="beam",
    )
    assert "Beam" in report
    assert "## Engineering Note" in report or "Note" in report


def test_report_handles_missing_keys() -> None:
    report = format_engineering_report("x", [], [], {}, analysis_type="truss")
    assert "# Preliminary Truss Analysis Report" in report
    report = format_engineering_report("x", [], [], {}, analysis_type="frame")
    assert "# Preliminary Frame Analysis Report" in report
