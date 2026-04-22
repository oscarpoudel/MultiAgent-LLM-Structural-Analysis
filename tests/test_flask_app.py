from app.main import app


class StubAgentSystem:
    def chat(self, message: str):
        from app.agents import ConversationResult

        return ConversationResult(message=f"LLM replied to: {message}", source="llm")

    def route_canvas_tool(self, message: str):
        from app.models import CanvasToolDecision

        if "clear" in message.lower():
            return CanvasToolDecision(action="clear_canvas", message="I cleared the drawing canvas.", confidence=0.9), "llm"
        return CanvasToolDecision(), "llm"


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
    assert data["results"]["solver"] == "openseespy_elastic_beam"
    assert round(float(data["results"]["max_moment_kn_m"]), 2) == 90.0


def test_chat_route_answers_greeting_with_llm(monkeypatch) -> None:
    client = app.test_client()

    monkeypatch.setattr("app.main.get_agent_system", lambda: StubAgentSystem())

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

    monkeypatch.setattr("app.main.get_agent_system", lambda: StubAgentSystem())

    response = client.post("/api/chat", json={"message": "what is beam deflection?"})

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
        def route_canvas_tool(self, message: str):
            return CanvasToolDecision(action="clear_canvas", message="I cleared the drawing canvas.", confidence=0.9), "llm"

    monkeypatch.setattr("app.main.get_agent_system", lambda: StubCanvasAgent())

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
        def route_canvas_tool(self, message: str):
            return CanvasToolDecision(
                action="draw_simple_beam",
                arguments={"span_m": 2.0, "point_loads": [{"magnitude_kn": 10, "position_m": 1.0}]},
                message="I drew a simply supported beam on the canvas.",
                confidence=0.9,
            ), "llm"

    monkeypatch.setattr("app.main.get_agent_system", lambda: StubCanvasAgent())

    response = client.post("/api/chat", json={"message": "draw a simply supported beam 2m long with 10kN at middle"})

    assert response.status_code == 200
    data = response.get_json()
    assert data["response_type"] == "canvas_action"
    assert data["canvas_action"]["action"] == "draw_simple_beam"
    assert data["canvas_action"]["arguments"]["span_m"] == 2.0
    assert data["analysis"] is None


def test_chat_route_runs_analysis_for_engineering_request() -> None:
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
    assert "openseespy" in data["source"]
    assert data["analysis"]["results"]["solver"] == "openseespy_elastic_beam"
