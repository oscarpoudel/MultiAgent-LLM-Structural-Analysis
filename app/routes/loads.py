"""Load determination routes: wind, seismic, snow (deterministic)."""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from pydantic import ValidationError

from app.models import SeismicInputs, SlabInputs, SnowInputs, Structure3DInputs, WindInputs
from app.tools.pdelta import amplify_story_drifts, pdelta_equivalent_lateral_forces
from app.tools.response_spectrum import response_spectrum_analysis
from app.tools.seismic import calculate_seismic_base_shear
from app.tools.slab import calculate_slab
from app.tools.snow import calculate_snow_loads
from app.tools.story_forces import apply_story_forces
from app.tools.wind import calculate_wind_loads

bp = Blueprint("loads", __name__)


def _compute_story_forces(data: dict) -> tuple[dict, list[dict], list[str], str]:
    """Compute story forces from wind or seismic inputs.

    Returns (load_results, story_forces, warnings, case).
    """
    load_type = str(data.get("load_type", "wind")).lower()
    if load_type in ("seismic", "eq", "el"):
        inputs = SeismicInputs.model_validate(data.get("seismic") or data.get("inputs") or {})
        results = calculate_seismic_base_shear(inputs)
        case = "EQ"
    elif load_type in ("wind", "w"):
        inputs = WindInputs.model_validate(data.get("wind") or data.get("inputs") or {})
        results = calculate_wind_loads(inputs)
        case = "W"
    else:
        raise ValueError(f"Unknown load_type '{load_type}' (expected 'wind' or 'seismic')")
    return results, results["story_forces"], results.get("warnings", []), case


@bp.post("/api/loads/wind")
def wind_loads():
    try:
        data = request.get_json(force=True, silent=True) or {}
        inputs = WindInputs.model_validate(data)
    except ValidationError as exc:
        return jsonify({"status": "error", "message": "Invalid wind inputs", "details": exc.errors()}), 400
    result = calculate_wind_loads(inputs)
    return jsonify({"status": "ok", "results": result})


@bp.post("/api/loads/seismic")
def seismic_loads():
    try:
        data = request.get_json(force=True, silent=True) or {}
        inputs = SeismicInputs.model_validate(data)
    except ValidationError as exc:
        return jsonify({"status": "error", "message": "Invalid seismic inputs", "details": exc.errors()}), 400
    result = calculate_seismic_base_shear(inputs)
    return jsonify({"status": "ok", "results": result})


@bp.post("/api/loads/response-spectrum")
def response_spectrum_loads():
    """Run deterministic lumped-mass response-spectrum analysis on a 3D model."""
    data = request.get_json(force=True, silent=True) or {}
    try:
        from app.tools.opensees_3d import convert_3d_support_strings

        model = Structure3DInputs.model_validate(convert_3d_support_strings(data.get("model") or {}))
        result = response_spectrum_analysis(
            model,
            float(data["building_weight_kn"]),
            float(data["sds"]),
            float(data["sd1"]),
            direction=str(data.get("direction", "x")).lower(),
            num_modes=int(data.get("num_modes", 10)),
            long_period_s=float(data.get("long_period_s", 8.0)),
        )
    except (ValidationError, ValueError, TypeError, KeyError) as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400
    return jsonify({"status": "ok", "results": result})


@bp.post("/api/loads/slab")
def slab_loads():
    try:
        data = request.get_json(force=True, silent=True) or {}
        inputs = SlabInputs.model_validate(data)
    except ValidationError as exc:
        return jsonify({"status": "error", "message": "Invalid slab inputs", "details": exc.errors()}), 400
    result = calculate_slab(inputs)
    return jsonify({"status": "ok", "results": result})


@bp.post("/api/loads/snow")
def snow_loads():
    try:
        data = request.get_json(force=True, silent=True) or {}
        inputs = SnowInputs.model_validate(data)
    except ValidationError as exc:
        return jsonify({"status": "error", "message": "Invalid snow inputs", "details": exc.errors()}), 400
    result = calculate_snow_loads(inputs)
    return jsonify({"status": "ok", "results": result})


@bp.post("/api/loads/apply-story-forces")
def apply_story_forces_route():
    """Compute wind/seismic story forces and map them onto a drawn 3D model.

    Body:
    - load_type: "wind" | "seismic"
    - wind / seismic (or inputs): load tool inputs
    - model: drawn 3D structure (Structure3DInputs)
    - direction: "x" | "y" (default "x")
    - distribution: "equal" | "windward" (default "equal")
    """
    data = request.get_json(force=True, silent=True) or {}
    try:
        from app.tools.opensees_3d import convert_3d_support_strings
        load_results, story_forces, load_warnings, case = _compute_story_forces(data)
        model = Structure3DInputs.model_validate(convert_3d_support_strings(data.get("model") or {}))
        direction = str(data.get("direction", "x"))
        distribution = str(data.get("distribution", "equal"))
        outcome = apply_story_forces(
            model,
            story_forces,
            case=case,
            direction=direction,
            distribution=distribution,
        )
    except (ValidationError, ValueError, KeyError) as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400

    return jsonify({
        "status": "ok",
        "load_type": str(data.get("load_type", "wind")).lower(),
        "load_results": load_results,
        "applied": outcome["applied"],
        "warnings": load_warnings + outcome["warnings"],
        "model": outcome["inputs"].model_dump(mode="json"),
    })


@bp.post("/api/loads/pdelta-amplify")
def pdelta_amplify():
    """Amplify first-order story drifts using the ASCE 7 stability coefficient.

    Body:
    - story_drifts: list of {"drift_mm": float, "from_m"?, "to_m"?, "height_m"?}
    - base_shear_kn: first-order base shear V (kN)
    - height_m: total building height h (m)
    - gravity_load_kn: total gravity load W (kN)
    """
    data = request.get_json(force=True, silent=True) or {}
    try:
        story_drifts = data.get("story_drifts") or []
        base_shear_kn = float(data.get("base_shear_kn", 0.0))
        height_m = float(data.get("height_m", 0.0))
        gravity_load_kn = float(data.get("gravity_load_kn", 0.0))
        result = amplify_story_drifts(story_drifts, base_shear_kn, height_m, gravity_load_kn)
    except (TypeError, ValueError) as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400
    return jsonify({"status": "ok", "results": result})


@bp.post("/api/loads/pdelta-forces")
def pdelta_forces():
    """Compute P-delta equivalent lateral forces from first-order drifts and map
    them onto a drawn 3D model as nodal loads (for iterative second-order analysis).

    Body:
    - model: drawn 3D structure (Structure3DInputs)
    - story_drifts: list of {"from_m", "to_m", "drift_mm"}
    - gravity_load_kn: total gravity load W (kN)
    - direction: "x" | "y" (default "x")
    """
    data = request.get_json(force=True, silent=True) or {}
    try:
        from app.tools.opensees_3d import convert_3d_support_strings
        model = Structure3DInputs.model_validate(convert_3d_support_strings(data.get("model") or {}))
        story_drifts = data.get("story_drifts") or []
        gravity_load_kn = float(data.get("gravity_load_kn", 0.0))
        direction = str(data.get("direction", "x"))
        outcome = pdelta_equivalent_lateral_forces(
            model, story_drifts, gravity_load_kn, direction=direction
        )
    except (ValidationError, ValueError, KeyError) as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400

    return jsonify({
        "status": "ok",
        "applied": outcome["applied"],
        "warnings": outcome["warnings"],
        "model": outcome["inputs"].model_dump(mode="json"),
    })
