import builtins

from app.models import Load3D, LoadCombination3D, Member3D, MemberLoad3D, Node3D, Structure3DInputs, Support3D
from app.tools.opensees_3d import (
    _apply_rigid_diaphragms,
    _default_combinations,
    _member_axis,
    _run_static_combo,
    _safe_vecxz,
    _story_response,
    analyze_3d_structure_opensees,
)
from app.tools.report import format_engineering_report


def test_safe_vecxz_avoids_member_axis_parallel_vectors() -> None:
    origin = Node3D(id=1, x=0, y=0, z=0)

    assert _safe_vecxz(origin, Node3D(id=2, x=6, y=0, z=0)) == (0.0, 0.0, 1.0)
    assert _safe_vecxz(origin, Node3D(id=3, x=0, y=6, z=0)) == (0.0, 0.0, 1.0)
    assert _safe_vecxz(origin, Node3D(id=4, x=0, y=0, z=3)) == (0.0, 1.0, 0.0)


def test_story_response_reports_level_displacements_and_drift_ratios() -> None:
    inputs = Structure3DInputs(
        nodes=[
            Node3D(id=1, x=0, y=0, z=0),
            Node3D(id=2, x=6, y=0, z=0),
            Node3D(id=3, x=0, y=0, z=3),
            Node3D(id=4, x=6, y=0, z=3),
        ],
        members=[],
    )
    displacements = {
        1: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        2: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        3: [6.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        4: [8.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    }

    response = _story_response(inputs, displacements)

    assert response["levels"][0]["max_lateral_mm"] == 0.0
    assert response["levels"][1]["max_ux_mm"] == 8.0
    assert response["story_drifts"][0]["height_m"] == 3
    assert response["story_drifts"][0]["drift_mm"] == 8.0
    assert response["story_drifts"][0]["drift_ratio"] == 375.0


def test_story_response_uses_absolute_interstory_drift() -> None:
    inputs = Structure3DInputs(
        nodes=[Node3D(id=1, x=0, y=0, z=0), Node3D(id=2, x=0, y=0, z=3)],
        members=[],
    )
    displacements = {
        1: [10.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        2: [4.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    }

    response = _story_response(inputs, displacements)

    assert response["story_drifts"][0]["drift_mm"] == 6.0


def test_story_response_preserves_displacement_direction_for_paired_nodes() -> None:
    inputs = Structure3DInputs(
        nodes=[Node3D(id=1, x=0, y=0, z=0), Node3D(id=2, x=0, y=0, z=3)],
        members=[],
    )
    displacements = {
        1: [-10.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        2: [4.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    }

    response = _story_response(inputs, displacements)

    assert response["story_drifts"][0]["drift_mm"] == 14.0


def test_story_response_handles_empty_models_and_zero_length_members() -> None:
    assert _story_response(Structure3DInputs(nodes=[], members=[]), {}) == {"levels": [], "story_drifts": []}
    node = Node3D(id=1, x=0, y=0, z=0)

    assert _member_axis(node, node) == (1.0, 0.0, 0.0)


def test_default_combinations_use_defined_combos_or_detect_load_cases() -> None:
    explicit = Structure3DInputs(
        nodes=[],
        members=[],
        load_combinations=[LoadCombination3D(name="Strength", factors={"D": 1.2, "L": 1.6})],
    )
    detected = Structure3DInputs(
        nodes=[],
        members=[],
        nodal_loads=[Load3D(node_id=1, case="EX", fx_kn=5)],
        member_loads=[MemberLoad3D(member_id=1, case="D", wy_kn_per_m=-2)],
    )

    assert _default_combinations(explicit) == [{"name": "Strength", "factors": {"D": 1.2, "L": 1.6}}]
    assert _default_combinations(detected) == [{"name": "D + EX", "factors": {"D": 1.0, "EX": 1.0}}]
    assert _default_combinations(Structure3DInputs(nodes=[], members=[])) == [{"name": "D", "factors": {"D": 1.0}}]


def test_apply_rigid_diaphragms_skips_base_and_uses_nearest_centroid_master() -> None:
    class FakeOps:
        def __init__(self):
            self.calls = []

        def rigidDiaphragm(self, direction, master, *slaves):  # noqa: N802 - mirrors OpenSeesPy API method name
            self.calls.append((direction, master, slaves))

    ops = FakeOps()
    inputs = Structure3DInputs(
        nodes=[
            Node3D(id=1, x=0, y=0, z=0),
            Node3D(id=2, x=6, y=0, z=0),
            Node3D(id=3, x=0, y=0, z=3),
            Node3D(id=4, x=6, y=0, z=3),
            Node3D(id=5, x=3, y=3, z=3),
        ],
        members=[],
    )

    _apply_rigid_diaphragms(ops, inputs)

    assert ops.calls == [(3, 5, (3, 4))]


def test_story_response_falls_back_to_average_drift_when_no_paired_nodes() -> None:
    # Upper level has a node at a (x, y) not present at the lower level, so no
    # paired drifts exist and the average-displacement drift is used instead.
    inputs = Structure3DInputs(
        nodes=[
            Node3D(id=1, x=0, y=0, z=0),
            Node3D(id=2, x=5, y=5, z=3),
        ],
        members=[],
    )
    displacements = {
        1: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        2: [12.0, 16.0, 0.0, 0.0, 0.0, 0.0],
    }

    response = _story_response(inputs, displacements)

    # No paired nodes -> drift from level averages: sqrt(12^2 + 16^2) = 20.0
    assert response["story_drifts"][0]["drift_mm"] == 20.0


def test_story_response_zero_drift_has_none_ratio() -> None:
    inputs = Structure3DInputs(
        nodes=[Node3D(id=1, x=0, y=0, z=0), Node3D(id=2, x=0, y=0, z=3)],
        members=[],
    )
    displacements = {
        1: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        2: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    }

    response = _story_response(inputs, displacements)

    assert response["story_drifts"][0]["drift_mm"] == 0.0
    assert response["story_drifts"][0]["drift_ratio"] is None


def test_apply_rigid_diaphragms_noop_with_single_level() -> None:
    class FakeOps:
        def __init__(self):
            self.calls = []

        def rigidDiaphragm(self, direction, master, *slaves):  # noqa: N802
            self.calls.append((direction, master, slaves))

    ops = FakeOps()
    inputs = Structure3DInputs(
        nodes=[Node3D(id=1, x=0, y=0, z=0), Node3D(id=2, x=6, y=0, z=0)],
        members=[],
    )

    _apply_rigid_diaphragms(ops, inputs)

    assert ops.calls == []


def test_apply_rigid_diaphragms_skips_single_node_level() -> None:
    class FakeOps:
        def __init__(self):
            self.calls = []

        def rigidDiaphragm(self, direction, master, *slaves):  # noqa: N802
            self.calls.append((direction, master, slaves))

    ops = FakeOps()
    inputs = Structure3DInputs(
        nodes=[
            Node3D(id=1, x=0, y=0, z=0),
            Node3D(id=2, x=6, y=0, z=0),
            Node3D(id=3, x=3, y=0, z=3),  # single node at upper level
        ],
        members=[],
    )

    _apply_rigid_diaphragms(ops, inputs)

    assert ops.calls == []


def test_run_static_combo_applies_loads_and_skips_zero_factor_cases() -> None:
    class FakeOps:
        def __init__(self):
            self.calls = []
            self.diaphragms = []

        def wipe(self):
            self.calls.append(("wipe",))

        def model(self, *a):
            self.calls.append(("model", a))

        def node(self, nid, x, y, z):
            self.calls.append(("node", nid))

        def fix(self, nid, *dofs):
            self.calls.append(("fix", nid, dofs))

        def rigidDiaphragm(self, direction, master, *slaves):  # noqa: N802
            self.diaphragms.append((direction, master, slaves))

        def geomTransf(self, *a):  # noqa: N802 - mirrors OpenSeesPy API method name
            self.calls.append(("geomTransf", a))

        def element(self, *a):
            self.calls.append(("element", a))

        def timeSeries(self, *a):  # noqa: N802 - mirrors OpenSeesPy API method name
            self.calls.append(("timeSeries", a))

        def pattern(self, *a):
            self.calls.append(("pattern", a))

        def load(self, nid, *forces):
            self.calls.append(("load", nid, forces))

        def eleLoad(self, *a):  # noqa: N802 - mirrors OpenSeesPy API method name
            self.calls.append(("eleLoad", a))

        def system(self, *a):
            self.calls.append(("system", a))

        def numberer(self, *a):
            self.calls.append(("numberer", a))

        def constraints(self, *a):
            self.calls.append(("constraints", a))

        def integrator(self, *a):
            self.calls.append(("integrator", a))

        def algorithm(self, *a):
            self.calls.append(("algorithm", a))

        def analysis(self, *a):
            self.calls.append(("analysis", a))

        def analyze(self, steps):
            return 0

        def reactions(self):
            return None

        def nodeDisp(self, nid):  # noqa: N802 - mirrors OpenSeesPy API method name
            return [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

        def nodeReaction(self, nid):  # noqa: N802 - mirrors OpenSeesPy API method name
            return [1.0, 2.0, 3.0, 0.0, 0.0, 0.0]

        def eleForce(self, mid):  # noqa: N802 - mirrors OpenSeesPy API method name
            return [1.0] * 12

    inputs = Structure3DInputs(
        nodes=[
            Node3D(id=1, x=0, y=0, z=0, support=Support3D(ux=True, uy=True, uz=True, rx=True, ry=True, rz=True)),
            Node3D(id=2, x=0, y=0, z=3),
            Node3D(id=3, x=3, y=0, z=3),
        ],
        members=[
            Member3D(id=1, start_node=1, end_node=2, group="column"),
            Member3D(id=2, start_node=2, end_node=3, group="beam"),
            Member3D(id=99, start_node=1, end_node=999),  # dangling end node -> skipped
        ],
        nodal_loads=[
            Load3D(node_id=2, case="EX", fx_kn=10.0),
            Load3D(node_id=2, case="L", fz_kn=-5.0),  # factor 0 in combo -> skipped
        ],
        member_loads=[
            MemberLoad3D(member_id=2, case="EX", wy_kn_per_m=-2.0),
            MemberLoad3D(member_id=2, case="L", wz_kn_per_m=-1.0),  # factor 0 -> skipped
        ],
        rigid_diaphragms=True,
    )
    combo = {"name": "EX only", "factors": {"EX": 1.0}}

    ops = FakeOps()
    result = _run_static_combo(ops, inputs, combo)

    load_calls = [c for c in ops.calls if c[0] == "load"]
    ele_calls = [c for c in ops.calls if c[0] == "eleLoad"]
    # Only the EX nodal load is applied (L skipped with factor 0).
    assert len(load_calls) == 1
    assert load_calls[0][1] == 2
    # Only the EX member load is applied (L skipped).
    assert len(ele_calls) == 1
    # Dangling member (end_node 999) is skipped -> only 2 elements created.
    element_calls = [c for c in ops.calls if c[0] == "element"]
    assert len(element_calls) == 2
    # Rigid diaphragm applied at the upper level (nodes 2 and 3).
    assert ops.diaphragms == [(3, 2, (3,))]
    # Constraints use Transformation when diaphragms are on.
    assert ("constraints", ("Transformation",)) in ops.calls
    assert result["is_finite"] is True
    assert result["num_members"] == 3
    assert result["base_reactions"]["Fx_kn"] == 0.001


def test_analyze_3d_reports_import_error_when_openseespy_unavailable(monkeypatch) -> None:
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "openseespy.opensees":
            raise ImportError("missing opensees")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    result = analyze_3d_structure_opensees(Structure3DInputs(nodes=[], members=[]))

    assert result["status"] == "error"
    assert result["solver"] == "openseespy_3d_import_failed"
    assert "missing opensees" in result["solver_warning"]


def test_canvas_3d_model_converts_support_strings_before_solving(monkeypatch) -> None:
    import app.main as main_mod
    import app.tools.opensees_3d as opensees_3d_mod

    captured = {}

    def fake_run_3d(inputs):
        captured["inputs"] = inputs
        return {"solver": "fake_3d"}

    monkeypatch.setattr(opensees_3d_mod, "analyze_3d_structure_opensees", fake_run_3d)
    monkeypatch.setattr(main_mod, "format_engineering_report", lambda *args, **kwargs: "report")
    monkeypatch.setattr(main_mod, "_save_history", lambda *args, **kwargs: 1)

    results, report = main_mod._analyze_structure_model(
        "3d_frame",
        {
            "nodes": [
                {"id": 1, "x": 0, "y": 0, "z": 0, "support": "roller"},
                {"id": 2, "x": 0, "y": 0, "z": 3, "support": "fixed"},
                {"id": 3, "x": 0, "y": 3, "z": 3, "support": "free"},
            ],
            "members": [],
        },
    )

    assert results == {"solver": "fake_3d"}
    assert report == "report"
    assert captured["inputs"].nodes[0].support.uz is True
    assert captured["inputs"].nodes[0].support.ux is False
    assert captured["inputs"].nodes[1].support.rz is True
    assert captured["inputs"].nodes[2].support is None


def test_3d_frame_report_uses_3d_sections_not_beam_template() -> None:
    report = format_engineering_report(
        "Canvas-drawn 3D frame structure",
        ["Preliminary elastic 3D analysis."],
        [],
        {
            "solver": "openseespy_3d_frame",
            "num_nodes": 2,
            "num_members": 1,
            "load_combination": "1.2D + 1.0EX + 0.5L",
            "load_factors": {"D": 1.2, "EX": 1.0, "L": 0.5},
            "combination_results": {
                "1.2D + 1.0EX + 0.5L": {
                    "max_translation_mm": 12.3456,
                    "base_reactions": {"Fx_kn": -5.0, "Fy_kn": 0.0, "Fz_kn": 20.0},
                }
            },
            "rigid_diaphragms": True,
            "max_translation_mm": 12.3456,
            "base_reactions": {"Fx_kn": -5.0, "Fy_kn": 0.0, "Fz_kn": 20.0, "Mx_kn_m": 1.0, "My_kn_m": 2.0, "Mz_kn_m": 3.0},
            "story_response": {
                "levels": [{"elevation_m": 3.5, "avg_ux_mm": 1.0, "avg_uy_mm": 0.0, "max_ux_mm": 1.2, "max_uy_mm": 0.1, "max_lateral_mm": 1.3}],
                "story_drifts": [{"from_m": 0.0, "to_m": 3.5, "height_m": 3.5, "drift_mm": 1.3, "drift_ratio": 2692.0}],
            },
            "member_force_summary": {"1": {"group": "beam", "max_abs_axial_kn": 1.0, "max_abs_shear_y_kn": 2.0, "max_abs_shear_z_kn": 3.0, "max_abs_moment_y_kn_m": 4.0, "max_abs_moment_z_kn_m": 5.0, "max_abs_torsion_kn_m": 6.0}},
            "reactions": {"1": {"Fx_kn": -5.0, "Fy_kn": 0.0, "Fz_kn": 20.0, "Mx_kn_m": 1.0, "My_kn_m": 2.0, "Mz_kn_m": 3.0}},
            "displacements": {"2": [1.0, 2.0, 3.0, 0.01, 0.02, 0.03]},
        },
        analysis_type="3d_frame",
    )

    assert "# Preliminary 3D Frame Analysis Report" in report
    assert "3D Space Frame Analysis" in report
    assert "Beam Analysis" not in report
    assert "## Load Combination Summary" in report
    assert "## Base Reactions" in report
    assert "## Story Drift Summary" in report
    assert "## Member Force Envelopes" in report
    assert "1.2D + 1.0EX + 0.5L" in report
