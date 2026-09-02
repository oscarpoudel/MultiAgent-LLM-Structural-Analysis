"""Cross-validation: direct-stiffness fallbacks vs OpenSeesPy for truss and frame.

These tests call the private fallback functions directly (bypassing the
OpenSeesPy path) and also verify the fallback agrees with the primary solver
on a benchmark model.
"""

from app.models import (
    FrameInputs,
    FrameLoad,
    FrameMember,
    FrameNode,
    TrussInputs,
    TrussLoad,
    TrussMember,
    TrussNode,
)
from app.tools.frame import _analyze_frame_direct_stiffness, analyze_frame
from app.tools.truss import _analyze_truss_direct_stiffness, analyze_truss


def _warren_truss() -> TrussInputs:
    """3-panel Warren truss, pin at left, roller at right, point load at midspan top."""
    return TrussInputs(
        nodes=[
            TrussNode(id=1, x=0.0, y=0.0, support="pin"),
            TrussNode(id=2, x=3.0, y=0.0, support="free"),
            TrussNode(id=3, x=6.0, y=0.0, support="roller_x"),
            TrussNode(id=4, x=1.5, y=2.0, support="free"),
            TrussNode(id=5, x=4.5, y=2.0, support="free"),
        ],
        members=[
            TrussMember(id=1, start_node=1, end_node=2, area_m2=0.002),
            TrussMember(id=2, start_node=2, end_node=3, area_m2=0.002),
            TrussMember(id=3, start_node=1, end_node=4, area_m2=0.002),
            TrussMember(id=4, start_node=4, end_node=2, area_m2=0.002),
            TrussMember(id=5, start_node=2, end_node=5, area_m2=0.002),
            TrussMember(id=6, start_node=5, end_node=3, area_m2=0.002),
            TrussMember(id=7, start_node=4, end_node=5, area_m2=0.002),
        ],
        loads=[
            TrussLoad(node_id=4, fx_kn=0.0, fy_kn=-30.0),
            TrussLoad(node_id=5, fx_kn=0.0, fy_kn=-30.0),
        ],
    )


def _portal_frame() -> FrameInputs:
    """Simple portal frame: fixed base, point load at right top, UDL on beam."""
    return FrameInputs(
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
        nodal_loads=[
            FrameLoad(node_id=4, fx_kn=20.0, fy_kn=-10.0),
        ],
    )


class TestTrussFallback:
    def test_fallback_runs_and_finite(self) -> None:
        result = _analyze_truss_direct_stiffness(_warren_truss())
        assert result["solver"] == "direct_stiffness_truss"
        assert result["is_finite"] is True
        assert result["num_nodes"] == 5
        assert result["num_members"] == 7

    def test_fallback_reactions_balance(self) -> None:
        result = _analyze_truss_direct_stiffness(_warren_truss())
        total_fy = sum(l.fy_kn for l in _warren_truss().loads)
        reactions_fy = sum(r["ry_kn"] for r in result["reactions"].values())
        assert abs(reactions_fy + total_fy) < 1.0  # equilibrium

    def test_fallback_member_forces_present(self) -> None:
        result = _analyze_truss_direct_stiffness(_warren_truss())
        assert len(result["member_forces"]) == 7
        for mf in result["member_forces"].values():
            assert mf["tension_or_compression"] in ("tension", "compression", "zero")

    def test_fallback_matches_opensees(self) -> None:
        inputs = _warren_truss()
        primary = analyze_truss(inputs)
        fallback = _analyze_truss_direct_stiffness(inputs)
        # Compare max displacement
        assert abs(primary["max_displacement_mm"] - fallback["max_displacement_mm"]) < 0.5

    def test_fallback_singular_matrix(self) -> None:
        # Unstable: no supports
        inputs = TrussInputs(
            nodes=[
                TrussNode(id=1, x=0.0, y=0.0, support="free"),
                TrussNode(id=2, x=1.0, y=0.0, support="free"),
            ],
            members=[TrussMember(id=1, start_node=1, end_node=2, area_m2=0.001)],
            loads=[TrussLoad(node_id=2, fx_kn=10.0, fy_kn=0.0)],
        )
        result = _analyze_truss_direct_stiffness(inputs)
        # Penalty method makes it solvable but physically meaningless; just ensure it returns
        assert "solver" in result


class TestFrameFallback:
    def test_fallback_runs_and_finite(self) -> None:
        result = _analyze_frame_direct_stiffness(_portal_frame())
        assert result["solver"] == "direct_stiffness_frame"
        assert result["is_finite"] is True
        assert result["num_nodes"] == 4
        assert result["num_members"] == 3

    def test_fallback_reactions_present(self) -> None:
        result = _analyze_frame_direct_stiffness(_portal_frame())
        assert "reactions" in result
        assert len(result["reactions"]) >= 2

    def test_fallback_member_forces_present(self) -> None:
        result = _analyze_frame_direct_stiffness(_portal_frame())
        assert len(result["member_forces"]) == 3

    def test_fallback_matches_opensees(self) -> None:
        inputs = _portal_frame()
        primary = analyze_frame(inputs)
        fallback = _analyze_frame_direct_stiffness(inputs)
        assert abs(primary["max_displacement_mm"] - fallback["max_displacement_mm"]) < 1.0

    def test_fallback_with_member_loads(self) -> None:
        inputs = _portal_frame()
        from app.models import FrameMemberLoad

        inputs.member_loads = [FrameMemberLoad(member_id=3, udl_kn_per_m=5.0)]
        result = _analyze_frame_direct_stiffness(inputs)
        assert result["is_finite"] is True
