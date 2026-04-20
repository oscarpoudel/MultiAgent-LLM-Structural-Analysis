from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.agents import StructuralAgentSystem
from app.config import get_settings
from app.llm import OllamaClient
from app.models import AnalyzeRequest, AnalyzeResponse

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="Structural Analysis Multi-Agent Prototype",
    version="0.1.0",
    description="Preliminary structural analysis assistant using Ollama and deterministic tools.",
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


def get_agent_system() -> StructuralAgentSystem:
    settings = get_settings()
    llm = OllamaClient(settings.ollama_base_url, settings.ollama_model)
    return StructuralAgentSystem(llm)


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    result = await get_agent_system().analyze(request.prompt)
    return AnalyzeResponse(
        status="ok",
        assumptions=result.assumptions,
        warnings=result.warnings,
        traces=result.traces,
        results=result.results,
        report_markdown=result.report_markdown,
    )
