"""Tests for the OpenAPI spec generator and docs routes."""
import re

from app.main import create_app
from app.tools.openapi import _model_schema, build_openapi_spec


def _spec(client) -> dict:
    response = client.get("/api/openapi.json")
    assert response.status_code == 200
    return response.get_json()


def test_spec_is_valid_openapi() -> None:
    client = create_app().test_client()
    spec = _spec(client)
    assert spec["openapi"].startswith("3.")
    assert spec["info"]["title"] == "StructAgent API"
    assert spec["paths"]
    # Every path must have at least one operation with a 200 response.
    for path, item in spec["paths"].items():
        for method, op in item.items():
            assert "200" in op["responses"], f"{method} {path} missing 200"


def test_spec_covers_key_endpoints() -> None:
    client = create_app().test_client()
    spec = _spec(client)
    for key in (
        "/api/analyze",
        "/api/loads/wind",
        "/api/loads/seismic",
        "/api/loads/response-spectrum",
        "/api/loads/cross-validation",
        "/api/design/beam",
        "/api/export/pdf",
        "/api/sections/{name}",
        "/api/projects/{project_id}",
    ):
        assert key in spec["paths"], f"missing path {key}"


def test_parameterized_routes_use_clean_param_names() -> None:
    # Flask <int:item_id> must become {item_id}, not {intitem_id}.
    client = create_app().test_client()
    spec = _spec(client)
    assert "/api/history/{item_id}" in spec["paths"]
    assert "/api/projects/{project_id}" in spec["paths"]
    assert "/api/sections/{name}" in spec["paths"]
    # No malformed converter-prefixed params (e.g. {intitem_id}) should leak into the spec.
    for path in spec["paths"]:
        for param in re.findall(r"\{([^}]*)\}", path):
            assert not param.startswith("int") and not param.startswith("float"), f"malformed param {param} in {path}"


def test_pydantic_body_documented() -> None:
    client = create_app().test_client()
    spec = _spec(client)
    wind = spec["paths"]["/api/loads/wind"]["post"]
    assert "requestBody" in wind
    schema = wind["requestBody"]["content"]["application/json"]["schema"]
    assert "basic_wind_speed_ms" in schema["properties"]
    assert "required" in schema
    # ChatRequest nests a DiagramData-free model; its schema is inline.
    chat = spec["paths"]["/api/chat"]["post"]
    assert "message" in chat["requestBody"]["content"]["application/json"]["schema"]["properties"]


def test_model_schema_promotes_nested_defs_to_components() -> None:
    # A model with nested sub-models should inline the $defs into components.
    built = _model_schema("Structure3DInputs")
    assert "nodes" in built["schema"]["properties"]
    assert "Node3D" in built["components"]
    assert "Support3D" in built["components"]


def test_freeform_body_documented() -> None:
    client = create_app().test_client()
    spec = _spec(client)
    cv = spec["paths"]["/api/loads/cross-validation"]["post"]
    assert cv["requestBody"]["content"]["application/json"]["schema"]["type"] == "object"


def test_docs_page_serves_html() -> None:
    client = create_app().test_client()
    response = client.get("/api/docs")
    assert response.status_code == 200
    assert "text/html" in response.headers["Content-Type"]
    body = response.get_data(as_text=True)
    assert "StructAgent API" in body
    assert "openapi.json" in body


def test_build_spec_from_app_object() -> None:
    app = create_app()
    spec = build_openapi_spec(app)
    assert spec["openapi"].startswith("3.")
    assert "/api/loads/wind" in spec["paths"]
