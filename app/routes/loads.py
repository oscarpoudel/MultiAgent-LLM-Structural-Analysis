"""Load determination routes: wind, seismic, snow (deterministic)."""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from pydantic import ValidationError

from app.models import SeismicInputs, SlabInputs, WindInputs
from app.tools.seismic import calculate_seismic_base_shear
from app.tools.slab import calculate_slab
from app.tools.wind import calculate_wind_loads

bp = Blueprint("loads", __name__)


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


@bp.post("/api/loads/slab")
def slab_loads():
    try:
        data = request.get_json(force=True, silent=True) or {}
        inputs = SlabInputs.model_validate(data)
    except ValidationError as exc:
        return jsonify({"status": "error", "message": "Invalid slab inputs", "details": exc.errors()}), 400
    result = calculate_slab(inputs)
    return jsonify({"status": "ok", "results": result})
