from app.main import app


class StubAgentSystem:
    def chat(self, message: str):
        from app.agents import ConversationResult

        return ConversationResult(message=f"LLM replied to: {message}", source="llm")


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
