from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from pydantic import ValidationError

from app.agents import StructuralAgentSystem
from app.config import get_settings
from app.llm import DisabledLLMClient, OllamaClient, PydanticAIClient
from app.models import AnalyzeRequest, AnalyzeResponse, ChatRequest, ChatResponse

BASE_DIR = Path(__file__).resolve().parent

app = Flask(
    __name__,
    static_folder=str(BASE_DIR / "static"),
    static_url_path="/static",
)
app.config["JSON_SORT_KEYS"] = False


def get_agent_system() -> StructuralAgentSystem:
    settings = get_settings()
    provider = settings.agent_llm_provider.lower()
    if provider == "none":
        llm = DisabledLLMClient()
    elif provider == "pydanticai":
        try:
            llm = PydanticAIClient(settings.ollama_base_url, settings.ollama_model)
        except Exception:
            llm = OllamaClient(settings.ollama_base_url, settings.ollama_model, settings.agent_llm_timeout_s)
    else:
        llm = OllamaClient(settings.ollama_base_url, settings.ollama_model, settings.agent_llm_timeout_s)
    return StructuralAgentSystem(llm, agent_timeout_s=settings.agent_llm_timeout_s)


def build_analysis_response(prompt: str) -> AnalyzeResponse:
    result = get_agent_system().analyze(prompt)
    return AnalyzeResponse(
        status="ok",
        assumptions=result.assumptions,
        warnings=result.warnings,
        traces=result.traces,
        results=result.results,
        report_markdown=result.report_markdown,
    )


def is_structural_analysis_request(message: str) -> bool:
    text = message.lower()
    analysis_terms = [
        "analyze",
        "beam",
        "column",
        "frame",
        "truss",
        "load",
        "span",
        "moment",
        "shear",
        "deflection",
        "stress",
        "opensees",
        "kN".lower(),
        "gpa",
        "m4",
        "l/",
    ]
    return any(term in text for term in analysis_terms)


@app.get("/")
def index():
    return send_from_directory(BASE_DIR / "static", "index.html")


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/api/analyze")
def analyze():
    try:
        analysis_request = AnalyzeRequest.model_validate(request.get_json(silent=True) or {})
    except ValidationError as error:
        return jsonify({"status": "error", "errors": error.errors()}), 422

    response = build_analysis_response(analysis_request.prompt)
    return jsonify(response.model_dump(mode="json"))


@app.post("/api/chat")
def chat():
    try:
        chat_request = ChatRequest.model_validate(request.get_json(silent=True) or {})
    except ValidationError as error:
        return jsonify({"status": "error", "errors": error.errors()}), 422

    if not is_structural_analysis_request(chat_request.message):
        chat_result = get_agent_system().chat(chat_request.message)
        response = ChatResponse(
            status="ok",
            response_type="conversation",
            message=chat_result.message,
            source=chat_result.source,
        )
        return jsonify(response.model_dump(mode="json"))

    analysis = build_analysis_response(chat_request.message)
    response = ChatResponse(
        status="ok",
        response_type="analysis",
        message="I ran the preliminary OpenSeesPy analysis and summarized the key checks below.",
        source="openseespy",
        analysis=analysis,
    )
    return jsonify(response.model_dump(mode="json"))


if __name__ == "__main__":
    app.run(debug=True)
