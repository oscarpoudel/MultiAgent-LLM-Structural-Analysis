from app.main import app


class StubAgentSystem:
    def chat(self, message: str):
        from app.agents import ConversationResult

        return ConversationResult(message=f"LLM replied to: {message}", source="llm")

    def chat_with_context(self, message: str, context: dict):
        from app.agents import ConversationResult

        return ConversationResult(message=f"Context replied to: {message} with {context['analysis_type']}", source="llm")

    def route_canvas_tool(self, message: str, context: dict | None = None):
        from app.models import CanvasToolDecision

        if "clear" in message.lower():
            return CanvasToolDecision(action="clear_canvas", message="I cleared the drawing canvas.", confidence=0.9), "llm"
        return CanvasToolDecision(), "llm"


def test_llm_status_endpoint_returns_ok() -> None:
    client = app.test_client()
    response = client.get("/api/llm-status")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert "connected" in data
    assert "provider" in data


def test_analyze_route_returns_opensees_result() -> None:
    client = app.test_client()

    response = client.post(
        "/api/analyze",
        json={
            "prompt": (
                "Analyze a simply supported steel beam. Span is 6 m, uniform load is 20 kN/m, "
                "E is 200 GPa, I is 8e-6 m4. Check deflection against L/360."
            )
        },
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    # OpenSeesPy may fall back to closed-form on Windows (missing DLLs)
    assert "openseespy" in data["results"]["solver"] or "closed_form" in data["results"]["solver"]
    assert round(float(data["results"]["max_moment_kn_m"]), 2) == 90.0


def test_project_api_persists_project_server_side() -> None:
    client = app.test_client()
    project = {
        "id": "test_project_server_persistence",
        "name": "Server Persistence Test",
        "updatedAt": 123456789,
        "nodes": [{"id": 1, "x": 0, "y": 0, "z": 0}],
        "members": [],
        "levels": [{"name": "Ground", "elevation": 0}],
    }

    save_response = client.put(f"/api/projects/{project['id']}", json=project)
    detail_response = client.get(f"/api/projects/{project['id']}")
    list_response = client.get("/api/projects")
    delete_response = client.delete(f"/api/projects/{project['id']}")

    assert save_response.status_code == 200
    assert detail_response.status_code == 200
    assert detail_response.get_json()["project"]["name"] == "Server Persistence Test"
    assert list_response.status_code == 200
    assert any(item["id"] == project["id"] for item in list_response.get_json()["projects"])
    assert delete_response.status_code == 200


def test_chat_route_answers_greeting_with_llm(monkeypatch) -> None:
    client = app.test_client()

    import app.routes.analyze as analyze_mod
    monkeypatch.setattr(analyze_mod, "_get_agent_system", lambda: StubAgentSystem())

    response = client.post("/api/chat", json={"message": "hi"})

    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert data["response_type"] == "conversation"
    assert data["message"] == "LLM replied to: hi"
    assert data["source"] == "llm"
    assert data["analysis"] is None


def test_chat_route_answers_structural_question_without_running_analysis(monkeypatch) -> None:
    client = app.test_client()

    import app.routes.analyze as analyze_mod
    monkeypatch.setattr(analyze_mod, "_get_agent_system", lambda: StubAgentSystem())

    response = client.post("/api/chat", json={"message": "what is beam deflection?"})

    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert data["response_type"] == "conversation"
    assert data["message"] == "LLM replied to: what is beam deflection?"
    assert data["analysis"] is None


def test_chat_route_ignores_empty_frontend_context_for_conceptual_question(monkeypatch) -> None:
    client = app.test_client()

    import app.routes.analyze as analyze_mod
    monkeypatch.setattr(analyze_mod, "_get_agent_system", lambda: StubAgentSystem())

    response = client.post(
        "/api/chat",
        json={
            "message": "what is beam deflection?",
            "analysis_type": "frame",
            "model": {},
            "results": {},
            "context": {"analysis_type": "frame", "model": {}, "results": {}, "model_summary": {"nodes": 0, "members": 0}},
        },
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert data["response_type"] == "conversation"
    assert data["message"] == "LLM replied to: what is beam deflection?"
    assert data["analysis"] is None


def test_chat_route_returns_canvas_action_for_clear_command(monkeypatch) -> None:
    client = app.test_client()
    from app.models import CanvasToolDecision

    class StubCanvasAgent(StubAgentSystem):
        def route_canvas_tool(self, message: str, context: dict | None = None):
            return CanvasToolDecision(action="clear_canvas", message="I cleared the drawing canvas.", confidence=0.9), "llm"

    import app.routes.analyze as analyze_mod
    monkeypatch.setattr(analyze_mod, "_get_agent_system", lambda: StubCanvasAgent())

    response = client.post("/api/chat", json={"message": "clear the canvas"})

    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert data["response_type"] == "canvas_action"
    assert data["canvas_action"]["action"] == "clear_canvas"
    assert data["analysis"] is None


def test_chat_route_returns_canvas_action_for_draw_beam(monkeypatch) -> None:
    client = app.test_client()
    from app.models import CanvasToolDecision

    class StubCanvasAgent(StubAgentSystem):
        def route_canvas_tool(self, message: str, context: dict | None = None):
            return CanvasToolDecision(
                action="draw_simple_beam",
                arguments={"span_m": 2.0, "point_loads": [{"magnitude_kn": 10, "position_m": 1.0}]},
                message="I drew a simply supported beam on the canvas.",
                confidence=0.9,
            ), "llm"

    import app.routes.analyze as analyze_mod
    monkeypatch.setattr(analyze_mod, "_get_agent_system", lambda: StubCanvasAgent())

    response = client.post("/api/chat", json={"message": "draw a simply supported beam 2m long with 10kN at middle"})

    assert response.status_code == 200
    data = response.get_json()
    assert data["response_type"] == "canvas_action"
    assert data["canvas_action"]["action"] == "draw_simple_beam"
    assert data["canvas_action"]["arguments"]["span_m"] == 2.0
    assert data["analysis"] is None


def test_chat_route_returns_canvas_action_for_3d_frame_template(monkeypatch) -> None:
    client = app.test_client()
    from app.models import CanvasToolDecision

    class StubCanvasAgent(StubAgentSystem):
        def route_canvas_tool(self, message: str, context: dict | None = None):
            return CanvasToolDecision(
                action="draw_3d_frame_template",
                message="I created a 3x3 3-story 3D frame template.",
                confidence=0.9,
            ), "llm"

    import app.routes.analyze as analyze_mod
    monkeypatch.setattr(analyze_mod, "_get_agent_system", lambda: StubCanvasAgent())

    response = client.post("/api/chat", json={"message": "create a 3x3 3-story frame"})

    assert response.status_code == 200
    data = response.get_json()
    assert data["response_type"] == "canvas_action"
    assert data["canvas_action"]["action"] == "draw_3d_frame_template"
    assert data["analysis"] is None


def test_chat_route_returns_canvas_action_for_apply_story_forces(monkeypatch) -> None:
    client = app.test_client()
    from app.models import CanvasToolDecision

    class StubCanvasAgent(StubAgentSystem):
        def route_canvas_tool(self, message: str, context: dict | None = None):
            return CanvasToolDecision(
                action="apply_story_forces",
                arguments={
                    "load_type": "wind",
                    "direction": "x",
                    "distribution": "equal",
                    "wind": {"basic_wind_speed_ms": 30.0, "height_m": 8.0},
                },
                message="I applied wind story forces to the model and ran the 3D analysis.",
                confidence=0.85,
            ), "llm"

    import app.routes.analyze as analyze_mod
    monkeypatch.setattr(analyze_mod, "_get_agent_system", lambda: StubCanvasAgent())

    response = client.post("/api/chat", json={"message": "apply wind story forces to the model"})

    assert response.status_code == 200
    data = response.get_json()
    assert data["response_type"] == "canvas_action"
    assert data["canvas_action"]["action"] == "apply_story_forces"
    assert data["canvas_action"]["arguments"]["load_type"] == "wind"
    assert data["analysis"] is None


def test_fallback_router_detects_wind_story_force_request() -> None:
    from app.agents import StructuralAgentSystem

    class FakeLLM:
        def generate(self, *args, **kwargs):
            return "I cannot determine a structured action."

    agent = StructuralAgentSystem(FakeLLM())
    decision, source = agent.route_canvas_tool("apply wind story forces to the model")

    assert source == "fallback"
    assert decision.action == "apply_story_forces"
    assert decision.arguments["load_type"] == "wind"
    assert decision.arguments["direction"] == "x"
    assert decision.arguments["distribution"] == "equal"
    assert "wind" in decision.arguments


def test_fallback_router_detects_seismic_story_force_request() -> None:
    from app.agents import StructuralAgentSystem

    class FakeLLM:
        def generate(self, *args, **kwargs):
            return "I cannot determine a structured action."

    agent = StructuralAgentSystem(FakeLLM())
    decision, source = agent.route_canvas_tool("apply seismic story forces in the y direction")

    assert source == "fallback"
    assert decision.action == "apply_story_forces"
    assert decision.arguments["load_type"] == "seismic"
    assert decision.arguments["direction"] == "y"
    assert "seismic" in decision.arguments


def test_fallback_router_ignores_non_story_force_apply() -> None:
    from app.agents import StructuralAgentSystem

    class FakeLLM:
        def generate(self, *args, **kwargs):
            return "I cannot determine a structured action."

    agent = StructuralAgentSystem(FakeLLM())
    decision, _ = agent.route_canvas_tool("apply beam/column sections to the frame")

    assert decision.action == "apply_member_group_sections"


def test_chat_route_uses_contextual_chat_for_current_results_question(monkeypatch) -> None:
    client = app.test_client()

    import app.routes.analyze as analyze_mod
    monkeypatch.setattr(analyze_mod, "_get_agent_system", lambda: StubAgentSystem())

    response = client.post(
        "/api/chat",
        json={
            "message": "what is the current max drift?",
            "analysis_type": "3d_frame",
            "model": {"nodes": [{"id": 1}], "members": []},
            "results": {"story_response": {"story_drifts": [{"drift_mm": 8.2}]}},
        },
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["response_type"] == "conversation"
    assert data["message"] == "Context replied to: what is the current max drift? with 3d_frame"
    assert data["source"] == "llm"


def test_agent_context_summary_handles_malformed_client_context() -> None:
    from app.agents import StructuralAgentSystem

    class FakeLLM:
        def generate(self, *args, **kwargs):
            return "{}"

    agent = StructuralAgentSystem(FakeLLM())
    summary = agent._summarize_canvas_context({
        "analysis_type": "3d_frame",
        "model": {"nodes": None, "members": None},
        "results": {"story_response": {"story_drifts": [None, {"drift_mm": "bad"}]}},
    })

    assert "Model: 0 nodes, 0 members" in summary
    assert "Analysis type: 3d_frame" in summary


def test_chat_route_runs_analysis_for_engineering_request(monkeypatch) -> None:
    from app.models import CanvasToolDecision

    # Stub the canvas router so the LLM doesn't hijack analysis prompts
    class StubAgentWithAnalysis(StubAgentSystem):
        def route_canvas_tool(self, message: str, context: dict | None = None):
            return CanvasToolDecision(), "fallback"

    import app.routes.analyze as analyze_mod
    monkeypatch.setattr(analyze_mod, "_get_agent_system", lambda: StubAgentWithAnalysis())

    client = app.test_client()

    response = client.post(
        "/api/chat",
        json={
            "message": (
                "Analyze a simply supported steel beam. Span is 6 m, uniform load is 20 kN/m, "
                "E is 200 GPa, I is 8e-6 m4. Check deflection against L/360."
            )
        },
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["response_type"] == "analysis"


def test_analyze_structure_route_leaves_3d_support_conversion_to_model_builder(monkeypatch) -> None:
    client = app.test_client()
    captured = {}

    def fake_analyze_structure_model(analysis_type, model):
        captured["analysis_type"] = analysis_type
        captured["model"] = model
        return {"solver": "fake_3d"}, "report"

    import app.routes.analyze as analyze_mod
    monkeypatch.setattr(analyze_mod, "_analyze_structure_model", fake_analyze_structure_model)

    response = client.post(
        "/api/analyze/structure",
        json={
            "analysis_type": "3d_frame",
            "model": {
                "nodes": [{"id": 1, "x": 0, "y": 0, "z": 0, "support": "roller"}],
                "members": [],
            },
        },
    )

    assert response.status_code == 200
    assert captured["analysis_type"] == "3d_frame"
    assert captured["model"]["nodes"][0]["support"] == "roller"


def test_export_csv_includes_nested_3d_analysis_results() -> None:
    client = app.test_client()

    response = client.post(
        "/api/export/csv",
        json={
            "analysis": {
                "results": {
                    "load_combination": "1.2D + 1.0EX + 0.5L",
                    "base_reactions": {"Fx_kn": -12.5, "Fz_kn": 120.0},
                    "story_response": {
                        "story_drifts": [{"from_m": 0, "to_m": 3.5, "drift_mm": 8.2}],
                    },
                    "member_force_summary": {
                        "4": {"group": "beam", "max_abs_moment_z_kn_m": 44.0},
                    },
                }
            }
        },
    )

    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "base_reactions.Fx_kn,-12.5,kN" in body
    assert "story_response.story_drifts[0].drift_mm,8.2,mm" in body
    assert "member_force_summary.4.max_abs_moment_z_kn_m,44.0,kN-m" in body


def test_export_report_appends_detailed_results_json() -> None:
    client = app.test_client()

    response = client.post(
        "/api/export/report",
        json={
            "report_markdown": "# Report",
            "results": {"load_combination": "Combo 1", "base_reactions": {"Fx_kn": 1.5}},
        },
    )

    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "## Detailed Analysis Data" in body
    assert '"load_combination": "Combo 1"' in body
    assert '"Fx_kn": 1.5' in body


def test_wind_loads_route_returns_results() -> None:
    client = app.test_client()
    response = client.post(
        "/api/loads/wind",
        json={
            "basic_wind_speed_ms": 30.0,
            "exposure": "C",
            "height_m": 12.0,
            "length_m": 20.0,
            "width_m": 10.0,
        },
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert data["results"]["base_shear_x_kn"] > 0
    assert data["results"]["base_shear_y_kn"] > 0


def test_wind_loads_route_rejects_invalid() -> None:
    client = app.test_client()
    response = client.post("/api/loads/wind", json={"basic_wind_speed_ms": -5.0})
    assert response.status_code == 400
    assert response.get_json()["status"] == "error"


def test_seismic_loads_route_returns_results() -> None:
    client = app.test_client()
    response = client.post(
        "/api/loads/seismic",
        json={
            "spectral_accel_sd": 0.8,
            "spectral_accel_1s": 0.4,
            "site_class": "D",
            "risk_category": "II",
            "building_weight_kn": 10000.0,
            "height_m": 12.0,
        },
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert data["results"]["base_shear_kn"] > 0
    assert data["results"]["design_params"]["cs"] > 0


def test_seismic_loads_route_rejects_invalid() -> None:
    client = app.test_client()
    response = client.post("/api/loads/seismic", json={"spectral_accel_sd": 0.0})
    assert response.status_code == 400
    assert response.get_json()["status"] == "error"


def test_slab_loads_route_returns_results() -> None:
    client = app.test_client()
    response = client.post(
        "/api/loads/slab",
        json={
            "span_x_m": 4.0,
            "span_y_m": 4.0,
            "thickness_m": 0.18,
            "dead_load_kpa": 2.0,
            "live_load_kpa": 3.0,
        },
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert data["results"]["design_moments_kn_m"]["short_span"] > 0
    assert data["results"]["reinforcement_short_span"]["required_as_m2"] > 0


def test_slab_loads_route_rejects_invalid() -> None:
    client = app.test_client()
    response = client.post("/api/loads/slab", json={"span_x_m": -1.0, "live_load_kpa": 3.0})
    assert response.status_code == 400
    assert response.get_json()["status"] == "error"


def test_snow_loads_route_returns_results() -> None:
    client = app.test_client()
    response = client.post(
        "/api/loads/snow",
        json={"ground_snow_load_kpa": 3.0, "roof_slope_deg": 0.0},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert data["results"]["flat_roof_ps_kpa"] > 0


def test_snow_loads_route_rejects_invalid() -> None:
    client = app.test_client()
    response = client.post("/api/loads/snow", json={"ground_snow_load_kpa": -1.0})
    assert response.status_code == 400
    assert response.get_json()["status"] == "error"


def test_beam_selection_route_returns_results() -> None:
    client = app.test_client()
    response = client.post(
        "/api/design/beam",
        json={"moment_kn_m": 100.0, "shear_kn": 50.0, "unbraced_length_m": 0.0},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert data["results"]["selected"] is not None
    assert data["results"]["selected"]["flex_util"] <= 1.0


def test_column_selection_route_returns_results() -> None:
    client = app.test_client()
    response = client.post(
        "/api/design/column",
        json={"axial_load_kn": 1000.0, "kl_m": 4.0},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert data["results"]["selected"] is not None
    assert data["results"]["selected"]["util"] <= 1.0


def test_beam_selection_route_rejects_invalid() -> None:
    client = app.test_client()
    response = client.post("/api/design/beam", json={"moment_kn_m": -1.0})
    assert response.status_code == 400
    assert response.get_json()["status"] == "error"


def test_concrete_beam_route_returns_results() -> None:
    client = app.test_client()
    response = client.post(
        "/api/design/concrete-beam",
        json={"moment_kn_m": 150.0, "shear_kn": 80.0, "width_mm": 300.0, "depth_mm": 500.0},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert data["results"]["flexure"]["phi_mn_kn_m"] > 150.0
    assert data["results"]["suggested_bars"]["count"] >= 1


def test_concrete_column_route_returns_results() -> None:
    client = app.test_client()
    response = client.post(
        "/api/design/concrete-column",
        json={"axial_load_kn": 800.0, "diameter_mm": 400.0},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert data["results"]["phi_pn_kn"] > 800.0
    assert data["results"]["suggested_bars"]["count"] >= 1


def test_concrete_routes_reject_invalid() -> None:
    client = app.test_client()
    assert client.post("/api/design/concrete-beam", json={"moment_kn_m": -1.0}).status_code == 400
    assert client.post("/api/design/concrete-column", json={"axial_load_kn": -1.0}).status_code == 400


def test_export_report_regenerates_stale_3d_beam_template() -> None:
    client = app.test_client()
    stale_report = """# Preliminary Structural Analysis Report

## Request
Canvas-drawn 3D frame structure

## Analysis Type
Beam Analysis (simply_supported)

## Input Summary
- Span: None m
"""

    response = client.post(
        "/api/export/report",
        json={
            "analysis": {
                "analysis_type": "3d_frame",
                "assumptions": ["Preliminary elastic 3D analysis."],
                "warnings": [],
                "report_markdown": stale_report,
                "results": {
                    "solver": "openseespy_3d_frame",
                    "num_nodes": 2,
                    "num_members": 1,
                    "load_combination": "1.2D + 1.0EX + 0.5L",
                    "base_reactions": {"Fx_kn": -5.0, "Fy_kn": 0.0, "Fz_kn": 20.0},
                    "story_response": {"story_drifts": [{"from_m": 0.0, "to_m": 3.5, "height_m": 3.5, "drift_mm": 1.3}]},
                    "member_force_summary": {"1": {"group": "beam", "max_abs_axial_kn": 1.0}},
                },
            },
            "analysis_type": "3d_frame",
            "report_markdown": stale_report,
        },
    )

    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "# Preliminary 3D Frame Analysis Report" in body
    assert "3D Space Frame Analysis" in body
    assert "Beam Analysis" not in body
    assert "Span: None" not in body
    assert "## Base Reactions" in body
    assert "## Detailed Analysis Data" in body


def _two_story_3d_model() -> dict:
    nodes = []
    nid = 1
    for z in (0.0, 4.0, 8.0):
        for x in (0.0, 6.0):
            for y in (0.0, 6.0):
                nodes.append({"id": nid, "x": x, "y": y, "z": z, "support": "fixed" if z == 0 else "free"})
                nid += 1
    members = []
    mid = 1
    # Vertical columns
    for i in range(4):
        members.append({"id": mid, "start_node": i + 1, "end_node": i + 5})
        mid += 1
        members.append({"id": mid, "start_node": i + 5, "end_node": i + 9})
        mid += 1
    # Beams per level
    for base in (1, 5, 9):
        for a, b in ((0, 1), (1, 3), (3, 2), (2, 0)):
            members.append({"id": mid, "start_node": base + a, "end_node": base + b})
            mid += 1
    return {"nodes": nodes, "members": members}


def test_apply_story_forces_route_wind_equal() -> None:
    client = app.test_client()
    response = client.post(
        "/api/loads/apply-story-forces",
        json={
            "load_type": "wind",
            "wind": {
                "basic_wind_speed_ms": 30.0, "exposure": "C", "height_m": 8.0,
                "length_m": 6.0, "width_m": 6.0, "story_height_m": 4.0,
            },
            "model": _two_story_3d_model(),
            "direction": "x",
            "distribution": "equal",
        },
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert data["load_type"] == "wind"
    # Story forces computed and applied
    assert data["load_results"]["story_forces"]
    assert data["applied"]
    # Augmented model carries W-case nodal loads
    w_loads = [l for l in data["model"]["nodal_loads"] if l["case"] == "W"]
    assert w_loads
    assert sum(l["fx_kn"] for l in w_loads) > 0


def test_apply_story_forces_route_seismic_windward() -> None:
    client = app.test_client()
    response = client.post(
        "/api/loads/apply-story-forces",
        json={
            "load_type": "seismic",
            "seismic": {
                "spectral_accel_sd": 0.4, "spectral_accel_1s": 0.2, "site_class": "D",
                "risk_category": "II", "building_weight_kn": 5000.0, "height_m": 8.0,
            },
            "model": _two_story_3d_model(),
            "direction": "x",
            "distribution": "windward",
        },
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert data["load_type"] == "seismic"
    eq_loads = [l for l in data["model"]["nodal_loads"] if l["case"] == "EQ"]
    assert eq_loads
    # Windward: only the x=0 face (2 nodes) per level receives the force
    node_x = {n["id"]: n["x"] for n in data["model"]["nodes"]}
    assert all(node_x[l["node_id"]] == 0.0 for l in eq_loads)
    # 2 levels x 2 windward nodes = 4 loads
    assert len(eq_loads) == 4
    # Total lateral force equals the sum of the story forces
    total_eq = sum(l["fx_kn"] for l in eq_loads)
    total_stories = sum(s["force_kn"] for s in data["load_results"]["story_forces"])
    assert abs(total_eq - total_stories) < 1e-6


def test_apply_story_forces_route_rejects_bad_load_type() -> None:
    client = app.test_client()
    response = client.post(
        "/api/loads/apply-story-forces",
        json={"load_type": "bogus", "model": _two_story_3d_model()},
    )
    assert response.status_code == 400
    assert response.get_json()["status"] == "error"


def test_analyze_structure_with_loads_end_to_end_wind() -> None:
    client = app.test_client()
    response = client.post(
        "/api/analyze/structure-with-loads",
        json={
            "load_type": "wind",
            "wind": {
                "basic_wind_speed_ms": 40.0, "exposure": "C", "height_m": 8.0,
                "length_m": 6.0, "width_m": 6.0, "story_height_m": 4.0,
            },
            "model": _two_story_3d_model(),
            "direction": "x",
            "distribution": "equal",
        },
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert data["results"]["solver"] == "openseespy_3d_frame"
    assert data["results"]["is_finite"] is True
    # Story drifts reported
    drifts = data["results"]["story_response"]["story_drifts"]
    assert drifts
    assert all(d["drift_mm"] > 0 for d in drifts)
    # Report generated
    assert "Preliminary 3D Frame Analysis Report" in data["report_markdown"]
