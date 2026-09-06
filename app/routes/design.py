"""Element design routes: steel section selection (AISC 360) and concrete design (ACI 318)."""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from pydantic import ValidationError

from app.models import (
    BeamSelectionInputs,
    ColumnSelectionInputs,
    ConcreteBeamInputs,
    ConcreteColumnInputs,
    TimberBeamInputs,
)
from app.tools.concrete import design_concrete_beam, design_concrete_column
from app.tools.cost import estimate_cost
from app.tools.section_select import select_beam, select_column
from app.tools.timber import design_timber_beam, list_species

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


@bp.post("/api/design/cost")
def cost_estimate():
    """Estimate steel cost from a member takeoff (section + length per group).

    Body:
    - members: list of {"section": str, "length_m": float}
    - price_per_kg (optional), fab_factor (optional), erect_factor (optional),
      currency (optional)
    """
    data = request.get_json(force=True, silent=True) or {}
    try:
        members = data.get("members") or []
        if not isinstance(members, list):
            raise ValueError("members must be a list of {section, length_m}")
        result = estimate_cost(
            members,
            price_per_kg=float(data.get("price_per_kg", 2.5)),
            fab_factor=float(data.get("fab_factor", 1.0)),
            erect_factor=float(data.get("erect_factor", 1.0)),
            currency=str(data.get("currency", "USD")),
        )
    except (TypeError, ValueError) as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400
    return jsonify({"status": "ok", "results": result})


@bp.get("/api/design/timber-species")
def timber_species():
    """List available timber species with NDS reference design values (MPa)."""
    return jsonify({"status": "ok", "results": {"species": list_species()}})


@bp.post("/api/design/timber-beam")
def timber_beam_design():
    """Design a rectangular timber beam (NDS, ASD)."""
    try:
        data = request.get_json(force=True, silent=True) or {}
        inputs = TimberBeamInputs.model_validate(data)
    except ValidationError as exc:
        return jsonify({"status": "error", "message": "Invalid timber beam inputs", "details": exc.errors()}), 400
    try:
        result = design_timber_beam(inputs)
    except ValueError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400
    return jsonify({"status": "ok", "results": result})
