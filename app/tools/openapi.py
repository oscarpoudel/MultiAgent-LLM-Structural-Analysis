"""OpenAPI 3.0 specification generator for the StructAgent API.

The spec is built by introspecting the live Flask application so it always
reflects the actually-registered routes. Endpoints that validate their body
with a Pydantic model are documented with that model's schema; the remaining
endpoints are documented with a free-form object body. This is deterministic
and requires no extra dependencies.
"""
from __future__ import annotations

from flask import Flask

# Endpoints whose JSON body is validated by a Pydantic model. The value is the
# model class name in app.models.
BODY_MODELS: dict[str, str] = {
    "POST /api/analyze": "AnalyzeRequest",
    "POST /api/chat": "ChatRequest",
    "POST /api/chat/evaluate": "EvaluateRequest",
    "POST /api/loads/wind": "WindInputs",
    "POST /api/loads/seismic": "SeismicInputs",
    "POST /api/loads/slab": "SlabInputs",
    "POST /api/loads/snow": "SnowInputs",
    "POST /api/design/beam": "BeamSelectionInputs",
    "POST /api/design/column": "ColumnSelectionInputs",
    "POST /api/design/concrete-beam": "ConcreteBeamInputs",
    "POST /api/design/concrete-column": "ConcreteColumnInputs",
    "POST /api/design/timber-beam": "TimberBeamInputs",
    "POST /api/design/spread-footing": "SpreadFootingInputs",
    "POST /api/design/pile": "PileInputs",
    "POST /api/design/fatigue": "FatigueInputs",
    "POST /api/analyze/sensitivity": "SensitivityInputs",
    "POST /api/analyze/multi-hazard": "MultiHazardInputs",
}

# Endpoints that take a model + load inputs (free-form body).
FREEFORM_BODY = {
    "POST /api/analyze/structure",
    "POST /api/analyze/structure-with-loads",
    "POST /api/loads/apply-story-forces",
    "POST /api/loads/response-spectrum",
    "POST /api/loads/pdelta-amplify",
    "POST /api/loads/pdelta-forces",
    "POST /api/loads/cross-validation",
    "POST /api/design/cost",
    "POST /api/load-combinations",
    "POST /api/validate",
    "POST /api/export/csv",
    "POST /api/export/report",
    "POST /api/export/pdf",
    "PUT /api/projects/<project_id>",
}

_DESCRIPTIONS: dict[str, str] = {
    "GET /": "Serve the web UI.",
    "GET /health": "Liveness probe.",
    "POST /api/analyze": "Run a structural analysis from a natural-language prompt.",
    "POST /api/chat": "Conversational analysis with canvas tool routing.",
    "POST /api/chat/evaluate": "Evaluate or explain analysis results.",
    "POST /api/analyze/structure": "Analyze a drawn structure (nodes, members, loads).",
    "POST /api/analyze/structure-with-loads": "Apply wind/seismic story forces to a 3D model and analyze.",
    "POST /api/loads/wind": "ASCE 7-22 wind load determination.",
    "POST /api/loads/seismic": "ASCE 7-22 seismic base shear (equivalent static force).",
    "POST /api/loads/slab": "ACI 318 two-way slab analysis.",
    "POST /api/loads/snow": "ASCE 7-22 snow load determination.",
    "POST /api/loads/apply-story-forces": "Map wind/seismic story forces onto a drawn 3D model.",
    "POST /api/loads/response-spectrum": "Lumped-mass modal response-spectrum analysis.",
    "POST /api/loads/pdelta-amplify": "ASCE 7 stability-coefficient drift amplification.",
    "POST /api/loads/pdelta-forces": "P-delta equivalent lateral forces on a 3D model.",
    "POST /api/loads/cross-validation": "Run the independent-solver cross-validation suite.",
    "POST /api/design/beam": "AISC 360 steel beam section selection.",
    "POST /api/design/column": "AISC 360 steel column section selection.",
    "POST /api/design/concrete-beam": "ACI 318 concrete beam design.",
    "POST /api/design/concrete-column": "ACI 318 concrete column design.",
    "POST /api/design/cost": "Steel cost estimate from a member takeoff.",
    "GET /api/design/timber-species": "List timber species with NDS reference design values.",
    "POST /api/design/timber-beam": "NDS timber beam design (ASD: flexure, shear, stability, deflection).",
    "POST /api/design/spread-footing": "ACI 318 spread footing design (bearing, shear, flexure).",
    "POST /api/design/pile": "Static pile capacity (skin friction + end bearing) and group efficiency.",
    "GET /api/design/fatigue-categories": "List AISC 360 fatigue categories with S-N parameters.",
    "POST /api/design/fatigue": "AISC 360 fatigue check (S-N curve) for a detail and design life.",
    "POST /api/analyze/sensitivity": "OAT parametric sensitivity study on a beam (moment/deflection/stress).",
    "POST /api/analyze/multi-hazard": "Multi-hazard load combination optimizer (rank combinations, find worst case).",
    "POST /api/load-combinations": "ASCE 7 factored load combinations.",
    "POST /api/validate": "Validate a structural model payload.",
    "GET /api/sections": "List or search the steel section library.",
    "GET /api/sections/{name}": "Fetch a single section by name.",
    "GET /api/history": "List analysis history.",
    "GET /api/history/{id}": "Fetch one history item.",
    "POST /api/export/csv": "Export analysis results as CSV.",
    "POST /api/export/report": "Export the markdown report.",
    "POST /api/export/pdf": "Export the report as PDF.",
    "GET /api/llm-status": "LLM connectivity status.",
    "GET /api/projects": "List saved projects.",
    "GET /api/projects/{id}": "Fetch one saved project.",
    "PUT /api/projects/{id}": "Save a project snapshot.",
    "DELETE /api/projects/{id}": "Delete a saved project.",
    "GET /api/openapi.json": "This OpenAPI specification (JSON).",
    "GET /api/docs": "Swagger UI for the API.",
}


def _model_schema(model_name: str) -> dict:
    from app import models as models_mod

    model = getattr(models_mod, model_name)
    schema = model.model_json_schema()
    # Convert the $defs reference style into inline components.
    components = schema.pop("$defs", {})
    return {"schema": schema, "components": components}


def build_openapi_spec(app: Flask) -> dict:
    """Build an OpenAPI 3.0 spec from the live Flask app's routes."""
    paths: dict[str, dict] = {}
    components: dict[str, dict] = {}

    for rule in app.url_map.iter_rules():
        if rule.endpoint == "static":
            continue
        method = next(iter(rule.methods - {"HEAD", "OPTIONS"}), "GET")
        key = f"{method.upper()} {rule.rule}"
        path_key = rule.rule.replace("<", "{").replace(">", "}")
        path_key = path_key.replace(":", "")

        operation: dict = {
            "summary": _DESCRIPTIONS.get(key, rule.endpoint.replace("_", " ").title()),
            "responses": {
                "200": {"description": "Successful response."},
            },
        }

        if method.upper() == "POST":
            if key in BODY_MODELS:
                built = _model_schema(BODY_MODELS[key])
                operation["requestBody"] = {
                    "required": True,
                    "content": {
                        "application/json": {"schema": built["schema"]},
                    },
                }
                if built["components"]:
                    components.update(built["components"])
            elif key in FREEFORM_BODY:
                operation["requestBody"] = {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"type": "object", "description": "Free-form JSON body."},
                        },
                    },
                }
            operation["responses"]["400"] = {"description": "Invalid input."}

        operation["tags"] = [_tag_for(rule.rule)]
        paths.setdefault(path_key, {})[method.lower()] = operation

    spec: dict = {
        "openapi": "3.0.3",
        "info": {
            "title": "StructAgent API",
            "version": "0.1.0",
            "description": (
                "Deterministic-first structural engineering assistant. The LLM handles "
                "routing and conversation only; all engineering values come from "
                "closed-form equations or FEM solvers (OpenSeesPy / direct stiffness). "
                "Preliminary elastic analysis only — not for licensed professional design."
            ),
        },
        "tags": [
            {"name": "analysis", "description": "Analysis and chat."},
            {"name": "loads", "description": "Load determination (wind, seismic, snow, P-delta, spectrum)."},
            {"name": "design", "description": "Element design (steel, concrete)."},
            {"name": "sections", "description": "Steel section library."},
            {"name": "projects", "description": "Project persistence."},
            {"name": "history", "description": "Analysis history and export."},
            {"name": "meta", "description": "Health, status, and API docs."},
        ],
        "paths": paths,
    }
    if components:
        spec["components"] = {"schemas": components}
    return spec


def _tag_for(rule: str) -> str:
    if "/design/" in rule:
        return "design"
    if "/sections" in rule:
        return "sections"
    if "/projects" in rule:
        return "projects"
    if "/history" in rule or "/export" in rule:
        return "history"
    if "/loads/" in rule:
        return "loads"
    if rule in ("/", "/health", "/api/llm-status", "/api/openapi.json", "/api/docs"):
        return "meta"
    return "analysis"
