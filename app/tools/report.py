from __future__ import annotations


def format_engineering_report(
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
        "## Assumptions",
    ]
    lines.extend(f"- {item}" for item in assumptions)
    lines.extend(
        [
            "",
            "## Results",
            f"- Maximum reaction: {results.get('max_reaction_kn')} kN",
            f"- Maximum shear: {results.get('max_shear_kn')} kN",
            f"- Maximum moment: {results.get('max_moment_kn_m')} kN-m",
            f"- Maximum deflection: {results.get('max_deflection_mm')} mm",
            f"- Deflection limit: {results.get('deflection_limit_mm')} mm",
            f"- Deflection check: {results.get('deflection_ok')}",
            "",
            "## Warnings",
        ]
    )
    lines.extend(f"- {item}" for item in warnings)
    lines.extend(
        [
            "",
            "## Engineering Note",
            "This is a preliminary elastic analysis. A licensed engineer should review final design decisions, load paths, code requirements, and constructability.",
        ]
    )
    return "\n".join(lines)
