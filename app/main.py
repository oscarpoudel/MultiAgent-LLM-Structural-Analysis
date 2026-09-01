"""Flask application factory."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from flask import Flask

from app.agents import StructuralAgentSystem
from app.config import get_settings
from app.llm import DisabledLLMClient, OllamaClient, PydanticAIClient
from app.logging_config import configure_logging, get_logger
from app.models import (
    AnalyzeResponse,
    FrameInputs,
    Structure3DInputs,
    TrussInputs,
)
from app.tools.report import format_engineering_report

configure_logging()
log = get_logger(__name__)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR.parent / "analysis_history.db"


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _init_db() -> None:
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL NOT NULL,
            analysis_type TEXT NOT NULL,
            prompt TEXT NOT NULL,
            results_json TEXT NOT NULL,
            report_markdown TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            updated_at REAL NOT NULL,
            project_json TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def _save_history(analysis_type: str, prompt: str, results: dict, report: str) -> int:
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.execute(
        "INSERT INTO history (timestamp, analysis_type, prompt, results_json, report_markdown) VALUES (?, ?, ?, ?, ?)",
        (time.time(), analysis_type, prompt, json.dumps(results, default=str), report),
    )
    row_id = cur.lastrowid
    conn.commit()
    conn.close()
    return row_id


def _get_history(limit: int = 50) -> list[dict]:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, timestamp, analysis_type, prompt, results_json, report_markdown "
        "FROM history ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _get_history_item(item_id: int) -> dict | None:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT id, timestamp, analysis_type, prompt, results_json, report_markdown "
        "FROM history WHERE id = ?",
        (item_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def _get_projects() -> list[dict]:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT project_json FROM projects ORDER BY updated_at DESC"
    ).fetchall()
    conn.close()
    projects = []
    for row in rows:
        try:
            projects.append(json.loads(row["project_json"]))
        except json.JSONDecodeError:
            continue
    return projects


def _get_project(project_id: str) -> dict | None:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT project_json FROM projects WHERE id = ?",
        (project_id,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    try:
        return json.loads(row["project_json"])
    except json.JSONDecodeError:
        return None


def _save_project(project: dict) -> str:
    project_id = str(project.get("id") or "").strip()
    if not project_id:
        raise ValueError("Project id is required")
    updated_at = float(project.get("updatedAt") or time.time() * 1000)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        """
        INSERT INTO projects (id, updated_at, project_json)
        VALUES (?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            updated_at = excluded.updated_at,
            project_json = excluded.project_json
        """,
        (project_id, updated_at, json.dumps(project, default=str)),
    )
    conn.commit()
    conn.close()
    return project_id


def _delete_project(project_id: str) -> None:
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Agent / analysis helpers
# ---------------------------------------------------------------------------

def _get_llm_client() -> OllamaClient | DisabledLLMClient | PydanticAIClient:
    settings = get_settings()
    provider = settings.agent_llm_provider.lower()
    if provider == "none":
        return DisabledLLMClient()
    elif provider == "pydanticai":
        try:
            return PydanticAIClient(settings.ollama_base_url, settings.ollama_model)
        except Exception:
            return OllamaClient(settings.ollama_base_url, settings.ollama_model, settings.agent_llm_timeout_s)
    else:
        return OllamaClient(settings.ollama_base_url, settings.ollama_model, settings.agent_llm_timeout_s)


def _get_agent_system() -> StructuralAgentSystem:
    return StructuralAgentSystem(_get_llm_client(), agent_timeout_s=get_settings().agent_llm_timeout_s)


def _check_llm_status() -> dict:
    settings = get_settings()
    provider = settings.agent_llm_provider.lower()
    if provider == "none":
        return {"connected": False, "provider": "none", "message": "LLM disabled"}
    try:
        llm = _get_llm_client()
        llm.generate(system="Respond with only the word ok.", prompt="ping")
        return {"connected": True, "provider": provider, "message": "Connected"}
    except Exception as exc:
        return {"connected": False, "provider": provider, "message": str(exc)}


def _build_analysis_response(prompt: str) -> AnalyzeResponse:
    t0 = time.perf_counter()
    log.info("analysis_start", extra={"prompt_len": len(prompt)})
    result = _get_agent_system().analyze(prompt)
    diagrams = getattr(result, "_diagrams", None)
    response = AnalyzeResponse(
        status="ok",
        analysis_type=result.analysis_type,
        assumptions=result.assumptions,
        warnings=result.warnings,
        traces=result.traces,
        results=result.results,
        report_markdown=result.report_markdown,
        diagrams=diagrams,
    )
    _save_history(result.analysis_type, prompt, result.results, result.report_markdown)
    log.info("analysis_done", extra={"type": result.analysis_type, "elapsed_s": round(time.perf_counter() - t0, 3)})
    return response


def _analyze_structure_model(analysis_type: str, model: dict) -> tuple[dict, str]:
    # Convert string support to Support3D objects for 3d_frame
    if analysis_type == "3d_frame" and "nodes" in model:
        import copy
        model = copy.deepcopy(model)
        for node in model.get("nodes", []):
            s = node.get("support", "free")
            if isinstance(s, str):
                if s == "free":
                    node["support"] = None
                elif s == "roller":
                    node["support"] = {"ux": False, "uy": False, "uz": True, "rx": False, "ry": False, "rz": False}
                elif s == "pin":
                    node["support"] = {"ux": True, "uy": True, "uz": True, "rx": False, "ry": False, "rz": False}
                else:  # fixed
                    node["support"] = {"ux": True, "uy": True, "uz": True, "rx": True, "ry": True, "rz": True}
    if analysis_type == "truss":
        from app.tools.truss import analyze_truss as run_truss
        inputs = TrussInputs.model_validate(model)
        results = run_truss(inputs)
        report_md = format_engineering_report(
            "Canvas-drawn truss structure",
            ["Preliminary elastic analysis.", "All joints pin-connected."],
            [], results, analysis_type="truss",
        )
    elif analysis_type == "3d_frame":
        from app.tools.opensees_3d import analyze_3d_structure_opensees as run_3d
        inputs = Structure3DInputs.model_validate(model)
        results = run_3d(inputs)
        report_md = format_engineering_report(
            "Canvas-drawn 3D frame structure",
            ["Preliminary elastic 3D analysis.", "Rigid beam-column connections."],
            [], results, analysis_type="3d_frame",
        )
    else:
        from app.tools.frame import analyze_frame as run_frame
        inputs = FrameInputs.model_validate(model)
        results = run_frame(inputs)
        report_md = format_engineering_report(
            "Canvas-drawn frame structure",
            ["Preliminary elastic analysis.", "Rigid beam-column connections."],
            [], results, analysis_type="frame",
        )
    _save_history(analysis_type, f"Canvas {analysis_type}", results, report_md)
    return results, report_md


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app() -> Flask:
    settings = get_settings()
    _init_db()

    app = Flask(
        __name__,
        static_folder=str(BASE_DIR / "static"),
        static_url_path="/static",
    )
    app.config["JSON_SORT_KEYS"] = False
    app.secret_key = settings.app_secret_key

    # Wire blueprint dependencies before registering
    from app.routes import analyze as analyze_bp_mod
    analyze_bp_mod._get_agent_system = _get_agent_system
    analyze_bp_mod._save_history = _save_history
    analyze_bp_mod._build_analysis_response = _build_analysis_response
    analyze_bp_mod._analyze_structure_model = _analyze_structure_model
    analyze_bp_mod._check_llm_status = _check_llm_status

    from app.routes import history as history_bp_mod
    history_bp_mod._get_history = _get_history
    history_bp_mod._get_history_item = _get_history_item

    from app.routes import projects as projects_bp_mod
    projects_bp_mod._get_projects = _get_projects
    projects_bp_mod._get_project = _get_project
    projects_bp_mod._save_project = _save_project
    projects_bp_mod._delete_project = _delete_project

    from app.routes import pages as pages_bp_mod
    pages_bp_mod._db_path = DB_PATH
    pages_bp_mod._static_dir = BASE_DIR / "static"

    # Register blueprints
    from app.routes.analyze import bp as analyze_bp
    from app.routes.history import bp as history_bp
    from app.routes.loads import bp as loads_bp
    from app.routes.pages import bp as pages_bp
    from app.routes.projects import bp as projects_bp
    from app.routes.sections import bp as sections_bp

    app.register_blueprint(analyze_bp)
    app.register_blueprint(history_bp)
    app.register_blueprint(loads_bp)
    app.register_blueprint(sections_bp)
    app.register_blueprint(pages_bp)
    app.register_blueprint(projects_bp)

    log.info("struct_agent_starting", extra={"env": settings.app_env})
    print("\nStructAgent running on http://127.0.0.1:5000\n", flush=True)
    return app


# Expose a module-level app instance for Waitress / legacy `flask run`
app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
