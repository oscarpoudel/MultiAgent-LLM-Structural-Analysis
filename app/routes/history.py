"""History routes blueprint."""
from __future__ import annotations

import csv
import io
import json

from flask import Blueprint, Response, jsonify, request

from app.logging_config import get_logger
from app.tools.report import format_engineering_report

bp = Blueprint("history", __name__)
log = get_logger(__name__)

# Set by app factory
_get_history = None
_get_history_item = None


UNIT_MAP = {
    "max_reaction_kn": "kN", "max_shear_kn": "kN", "max_moment_kn_m": "kN-m",
    "max_deflection_mm": "mm", "deflection_limit_mm": "mm",
    "left_reaction_kn": "kN", "right_reaction_kn": "kN",
    "euler_buckling_load_kn": "kN", "nominal_strength_kn": "kN",
    "design_strength_kn": "kN", "applied_load_kn": "kN",
    "axial_stress_mpa": "MPa", "critical_stress_mpa": "MPa",
    "bending_stress_mpa": "MPa", "elastic_buckling_stress_mpa": "MPa",
    "max_displacement_mm": "mm", "max_translation_mm": "mm", "span_m": "m", "length_m": "m",
    "effective_length_m": "m", "radius_of_gyration_m": "m", "elevation_m": "m",
    "height_m": "m", "drift_mm": "mm", "avg_ux_mm": "mm", "avg_uy_mm": "mm",
    "max_ux_mm": "mm", "max_uy_mm": "mm", "max_lateral_mm": "mm",
    "Fx_kn": "kN", "Fy_kn": "kN", "Fz_kn": "kN",
    "Mx_kn_m": "kN-m", "My_kn_m": "kN-m", "Mz_kn_m": "kN-m",
    "max_abs_axial_kn": "kN", "max_abs_shear_y_kn": "kN", "max_abs_shear_z_kn": "kN",
    "max_abs_torsion_kn_m": "kN-m", "max_abs_moment_y_kn_m": "kN-m", "max_abs_moment_z_kn_m": "kN-m",
}


def _write_result_rows(writer, value, section: str = "results", item: str = "") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            next_item = f"{item}.{key}" if item else str(key)
            _write_result_rows(writer, nested, section, next_item)
        return

    if isinstance(value, list):
        for index, nested in enumerate(value):
            next_item = f"{item}[{index}]" if item else f"[{index}]"
            _write_result_rows(writer, nested, section, next_item)
        return

    field = item.split(".")[-1]
    if "[" in field:
        field = field.split("[")[0]
    writer.writerow([section, item, value, UNIT_MAP.get(field, "")])


@bp.get("/api/history")
def history_list():
    limit = request.args.get("limit", 50, type=int)
    items = _get_history(limit)
    for item in items:
        try:
            item["results"] = json.loads(item.pop("results_json"))
        except (json.JSONDecodeError, KeyError):
            item["results"] = {}
    return jsonify({"status": "ok", "history": items})


@bp.get("/api/history/<int:item_id>")
def history_detail(item_id: int):
    item = _get_history_item(item_id)
    if not item:
        return jsonify({"status": "error", "message": "Not found"}), 404
    try:
        item["results"] = json.loads(item.pop("results_json"))
    except (json.JSONDecodeError, KeyError):
        item["results"] = {}
    return jsonify({"status": "ok", "item": item})


@bp.post("/api/export/csv")
def export_csv():
    """Export analysis results as CSV."""
    data = request.get_json(silent=True) or {}
    results = data.get("results") or data.get("analysis", {}).get("results", {})
    if not results:
        return jsonify({"status": "error", "message": "No results to export"}), 400

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Section", "Item", "Value", "Unit"])
    _write_result_rows(writer, results)

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=analysis_results.csv"},
    )


@bp.post("/api/export/report")
def export_report():
    """Export the markdown report as a downloadable .md file."""
    data = request.get_json(silent=True) or {}
    analysis = data.get("analysis", {}) if isinstance(data.get("analysis", {}), dict) else {}
    report = data.get("report_markdown", "")
    results = data.get("results") or analysis.get("results")
    if not report:
        return jsonify({"status": "error", "message": "No report to export"}), 400

    analysis_type = data.get("analysis_type") or analysis.get("analysis_type")
    if analysis_type == "3d_frame" and isinstance(results, dict):
        is_stale_beam_report = "Beam Analysis" in report or "Span: None" in report
        if is_stale_beam_report:
            report = format_engineering_report(
                "Canvas-drawn 3D frame structure",
                analysis.get("assumptions", ["Preliminary elastic 3D analysis.", "Rigid beam-column connections."]),
                analysis.get("warnings", []),
                results,
                analysis_type="3d_frame",
            )

    if results:
        report = f"{report.rstrip()}\n\n## Detailed Analysis Data\n\n```json\n{json.dumps(results, indent=2)}\n```\n"

    return Response(
        report,
        mimetype="text/markdown",
        headers={"Content-Disposition": "attachment; filename=analysis_report.md"},
    )
