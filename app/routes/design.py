"""Element design routes: steel section selection (AISC 360) and concrete design (ACI 318)."""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from pydantic import ValidationError

from app.models import BeamSelectionInputs, ColumnSelectionInputs, ConcreteBeamInputs, ConcreteColumnInputs
from app.tools.concrete import design_concrete_beam, design_concrete_column
from app.tools.section_select import select_beam, select_column

bp = Blueprint("design", __name__)


@bp.post("/api/design/beam")
def beam_selection():
    try:
        data = request.get_json(force=True, silent=True) or {}
        inputs = BeamSelectionInputs.model_validate(data)
    except ValidationError as exc:
        return jsonify({"status": "error", "message": "Invalid beam selection inputs", "details": exc.errors()}), 400
    result = select_beam(inputs)
    return jsonify({"status": "ok", "results": result})


@bp.post("/api/design/column")
def column_selection():
    try:
        data = request.get_json(force=True, silent=True) or {}
        inputs = ColumnSelectionInputs.model_validate(data)
    except ValidationError as exc:
        return jsonify({"status": "error", "message": "Invalid column selection inputs", "details": exc.errors()}), 400
    result = select_column(inputs)
    return jsonify({"status": "ok", "results": result})


@bp.post("/api/design/concrete-beam")
def concrete_beam_design():
    try:
        data = request.get_json(force=True, silent=True) or {}
        inputs = ConcreteBeamInputs.model_validate(data)
    except ValidationError as exc:
        return jsonify({"status": "error", "message": "Invalid concrete beam inputs", "details": exc.errors()}), 400
    result = design_concrete_beam(inputs)
    return jsonify({"status": "ok", "results": result})


@bp.post("/api/design/concrete-column")
def concrete_column_design():
    try:
        data = request.get_json(force=True, silent=True) or {}
        inputs = ConcreteColumnInputs.model_validate(data)
    except ValidationError as exc:
        return jsonify({"status": "error", "message": "Invalid concrete column inputs", "details": exc.errors()}), 400
    result = design_concrete_column(inputs)
    return jsonify({"status": "ok", "results": result})
