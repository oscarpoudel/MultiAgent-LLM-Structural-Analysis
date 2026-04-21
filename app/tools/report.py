from __future__ import annotations


def format_engineering_report(
    prompt: str,
    assumptions: list[str],
    warnings: list[str],
    results: dict[str, object],
    analysis_type: str = "beam",
) -> str:
    if analysis_type == "truss":
        return _format_truss_report(prompt, assumptions, warnings, results)
    elif analysis_type == "frame":
        return _format_frame_report(prompt, assumptions, warnings, results)
    elif analysis_type == "column":
        return _format_column_report(prompt, assumptions, warnings, results)
    else:
        return _format_beam_report(prompt, assumptions, warnings, results)


def _format_beam_report(
    prompt: str,
    assumptions: list[str],
    warnings: list[str],
    results: dict[str, object],
) -> str:
    lines = [
        "# Preliminary Structural Analysis Report",
        "",
        "## Request",
        prompt,
        "",
        "## Analysis Type",
        f"Beam Analysis ({results.get('support_type', 'simply_supported')})",
        "",
        "## Assumptions",
    ]
    lines.extend(f"- {item}" for item in assumptions)
    lines.append("")

    # Input summary
    lines.extend([
        "## Input Summary",
        f"- Span: {results.get('span_m')} m",
        f"- UDL: {results.get('udl_kn_per_m')} kN/m",
    ])
    num_pl = results.get("num_point_loads", 0)
    if num_pl:
        lines.append(f"- Point loads: {num_pl}")
    lines.extend([
        f"- Elastic modulus: {results.get('elastic_modulus_gpa')} GPa",
        f"- Moment of inertia: {results.get('inertia_m4')} m4",
        f"- Support type: {results.get('support_type', 'simply_supported')}",
        "",
    ])

    lines.extend([
        "## Results",
        f"- Solver: {results.get('solver')}",
        f"- Maximum reaction: {results.get('max_reaction_kn')} kN",
        f"- Maximum shear: {results.get('max_shear_kn')} kN",
        f"- Maximum moment: {results.get('max_moment_kn_m')} kN-m",
        f"- Maximum deflection: {results.get('max_deflection_mm')} mm",
        f"- Deflection limit: {results.get('deflection_limit_mm')} mm",
        f"- Deflection check: {results.get('deflection_ok')}",
    ])
    if results.get("bending_stress_mpa") is not None:
        lines.append(f"- Bending stress: {results.get('bending_stress_mpa')} MPa")
    if results.get("left_reaction_kn") is not None:
        lines.append(f"- Left reaction: {results.get('left_reaction_kn')} kN")
    if results.get("right_reaction_kn") is not None:
        lines.append(f"- Right reaction: {results.get('right_reaction_kn')} kN")

    lines.extend(["", "## Warnings"])
    lines.extend(f"- {item}" for item in warnings)
    lines.extend([
        "",
        "## Engineering Note",
        "This is a preliminary elastic analysis. A licensed engineer should review "
        "final design decisions, load paths, code requirements, and constructability.",
    ])
    return "\n".join(lines)


def _format_truss_report(
    prompt: str,
    assumptions: list[str],
    warnings: list[str],
    results: dict[str, object],
) -> str:
    lines = [
        "# Preliminary Truss Analysis Report",
        "",
        "## Request",
        prompt,
        "",
        "## Analysis Type",
        "2D Truss Analysis",
        "",
        "## Assumptions",
    ]
    lines.extend(f"- {item}" for item in assumptions)

    lines.extend([
        "",
        "## Model Summary",
        f"- Solver: {results.get('solver')}",
        f"- Number of nodes: {results.get('num_nodes')}",
        f"- Number of members: {results.get('num_members')}",
        f"- Number of loads: {results.get('num_loads')}",
        f"- Maximum displacement: {results.get('max_displacement_mm')} mm",
        "",
    ])

    # Reactions
    reactions = results.get("reactions", {})
    if reactions:
        lines.append("## Support Reactions")
        for node_id, rxn in reactions.items():
            lines.append(f"- Node {node_id}: Rx = {rxn.get('rx_kn')} kN, Ry = {rxn.get('ry_kn')} kN")
        lines.append("")

    # Member forces
    member_forces = results.get("member_forces", {})
    if member_forces:
        lines.append("## Member Forces")
        for mid, mf in member_forces.items():
            state = mf.get("tension_or_compression", "")
            lines.append(
                f"- Member {mid}: Axial = {mf.get('axial_kn')} kN ({state}), "
                f"Length = {mf.get('length_m')} m"
            )
        lines.append("")

    lines.append("## Warnings")
    lines.extend(f"- {item}" for item in warnings)
    lines.extend([
        "",
        "## Engineering Note",
        "This is a preliminary elastic truss analysis assuming pin-connected joints "
        "and axial-only member forces. A licensed engineer should verify connections, "
        "buckling capacity of compression members, and code compliance.",
    ])
    return "\n".join(lines)


def _format_frame_report(
    prompt: str,
    assumptions: list[str],
    warnings: list[str],
    results: dict[str, object],
) -> str:
    lines = [
        "# Preliminary Frame Analysis Report",
        "",
        "## Request",
        prompt,
        "",
        "## Analysis Type",
        "2D Frame Analysis",
        "",
        "## Assumptions",
    ]
    lines.extend(f"- {item}" for item in assumptions)

    lines.extend([
        "",
        "## Model Summary",
        f"- Solver: {results.get('solver')}",
        f"- Number of nodes: {results.get('num_nodes')}",
        f"- Number of members: {results.get('num_members')}",
        f"- Maximum displacement: {results.get('max_displacement_mm')} mm",
        f"- Maximum rotation: {results.get('max_rotation_rad')} rad",
        "",
    ])

    # Reactions
    reactions = results.get("reactions", {})
    if reactions:
        lines.append("## Support Reactions")
        for node_id, rxn in reactions.items():
            lines.append(
                f"- Node {node_id}: Rx = {rxn.get('rx_kn')} kN, "
                f"Ry = {rxn.get('ry_kn')} kN, "
                f"Mz = {rxn.get('mz_kn_m')} kN-m"
            )
        lines.append("")

    # Member forces
    member_forces = results.get("member_forces", {})
    if member_forces:
        lines.append("## Member End Forces")
        for mid, mf in member_forces.items():
            lines.extend([
                f"### Member {mid} (L = {mf.get('length_m')} m)",
                f"  - Start: N = {mf.get('axial_start_kn')} kN, "
                f"V = {mf.get('shear_start_kn')} kN, "
                f"M = {mf.get('moment_start_kn_m')} kN-m",
                f"  - End:   N = {mf.get('axial_end_kn')} kN, "
                f"V = {mf.get('shear_end_kn')} kN, "
                f"M = {mf.get('moment_end_kn_m')} kN-m",
            ])
        lines.append("")

    lines.append("## Warnings")
    lines.extend(f"- {item}" for item in warnings)
    lines.extend([
        "",
        "## Engineering Note",
        "This is a preliminary elastic frame analysis. A licensed engineer should "
        "review member design, connection details, stability (P-delta), and code compliance.",
    ])
    return "\n".join(lines)


def _format_column_report(
    prompt: str,
    assumptions: list[str],
    warnings: list[str],
    results: dict[str, object],
) -> str:
    lines = [
        "# Preliminary Column Analysis Report",
        "",
        "## Request",
        prompt,
        "",
        "## Analysis Type",
        "Column Buckling / Capacity Check (Euler + AISC Chapter E)",
        "",
        "## Assumptions",
    ]
    lines.extend(f"- {item}" for item in assumptions)

    lines.extend([
        "",
        "## Input Summary",
        f"- Length: {results.get('length_m')} m",
        f"- End condition: {results.get('end_condition')}",
        f"- Effective length factor (K): {results.get('effective_length_factor_K')}",
        f"- Effective length (KL): {results.get('effective_length_m')} m",
        f"- Cross-section area: {results.get('area_m2')} m2",
        f"- Moment of inertia: {results.get('inertia_m4')} m4",
        f"- Elastic modulus: {results.get('elastic_modulus_gpa')} GPa",
        f"- Yield stress: {results.get('yield_stress_mpa')} MPa",
        f"- Applied axial load: {results.get('applied_load_kn')} kN",
        "",
        "## Results",
        f"- Radius of gyration: {results.get('radius_of_gyration_m')} m",
        f"- Slenderness ratio (KL/r): {results.get('slenderness_ratio')}",
        f"- Slenderness classification: {results.get('slenderness_class')}",
        f"- Euler buckling load: {results.get('euler_buckling_load_kn')} kN",
        f"- Elastic buckling stress (Fe): {results.get('elastic_buckling_stress_mpa')} MPa",
        f"- Critical stress (Fcr): {results.get('critical_stress_mpa')} MPa",
        f"- Nominal strength (Pn): {results.get('nominal_strength_kn')} kN",
        f"- Design strength (phi*Pn): {results.get('design_strength_kn')} kN",
        f"- Axial stress: {results.get('axial_stress_mpa')} MPa",
        f"- Utilization ratio: {results.get('utilization_ratio')}",
        f"- Capacity OK: {results.get('capacity_ok')}",
        f"- Will buckle (Euler): {results.get('will_buckle')}",
        "",
    ])

    lines.append("## Warnings")
    col_warnings = results.get("warnings", [])
    if isinstance(col_warnings, list):
        lines.extend(f"- {item}" for item in col_warnings)
    lines.extend(f"- {item}" for item in warnings)
    lines.extend([
        "",
        "## Engineering Note",
        "This is a preliminary column buckling analysis based on Euler theory and "
        "AISC Chapter E provisions. A licensed engineer should verify effective length "
        "assumptions, local buckling, connection details, and overall stability.",
    ])
    return "\n".join(lines)
