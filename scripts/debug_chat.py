from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from pprint import pprint

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import app, get_agent_system  # noqa: E402


DEFAULT_CANVAS_MODEL = {
    "nodes": [
        {"id": 1, "x": 0.0, "y": 0.0, "support": "pin"},
        {"id": 2, "x": 2.0, "y": 0.0, "support": "roller"},
    ],
    "members": [
        {
            "id": 1,
            "start_node": 1,
            "end_node": 2,
            "area_m2": 0.01,
            "inertia_m4": 1e-4,
            "elastic_modulus_gpa": 200.0,
        }
    ],
    "nodal_loads": [],
    "member_loads": [],
}


def build_payload(message: str, include_canvas: bool) -> dict:
    payload = {"message": message}
    if include_canvas:
        payload.update({"analysis_type": "frame", "model": DEFAULT_CANVAS_MODEL})
    return payload


def print_router_debug(message: str) -> None:
    agent_system = get_agent_system()
    decision, source = agent_system.route_canvas_tool(message)
    print("\n[canvas-router]")
    print(f"source: {source}")
    pprint(decision.model_dump())


def print_response(data: dict) -> None:
    print("\n[chat-response]")
    print(f"status: {data.get('status')}")
    print(f"response_type: {data.get('response_type')}")
    print(f"source: {data.get('source')}")
    print(f"message: {data.get('message')}")

    if data.get("canvas_action"):
        print("\n[canvas-action]")
        pprint(data["canvas_action"])

    analysis = data.get("analysis")
    if analysis:
        print("\n[analysis]")
        print(f"analysis_type: {analysis.get('analysis_type')}")
        results = analysis.get("results") or {}
        interesting = {
            key: results.get(key)
            for key in [
                "solver",
                "num_nodes",
                "num_members",
                "max_reaction_kn",
                "max_shear_kn",
                "max_moment_kn_m",
                "max_deflection_mm",
                "max_displacement_mm",
                "is_finite",
            ]
            if key in results
        }
        pprint(interesting)
        traces = analysis.get("traces") or []
        if traces:
            print("\n[analysis-traces]")
            for trace in traces:
                print(f"- {trace.get('agent')}: {trace.get('summary')}")


def run_prompt(message: str, include_canvas: bool, raw_json: bool) -> None:
    print(f"\n[user] {message}")
    print_router_debug(message)
    client = app.test_client()
    response = client.post("/api/chat", json=build_payload(message, include_canvas))
    data = response.get_json()

    print(f"\n[http] {response.status_code}")
    if raw_json:
        print(json.dumps(data, indent=2))
    else:
        print_response(data or {})


def repl(include_canvas: bool, raw_json: bool) -> None:
    print("StructAgent chat debugger. Type 'exit' or 'quit' to stop.")
    print("Canvas model is included." if include_canvas else "Canvas model is not included.")
    while True:
        try:
            message = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if message.lower() in {"exit", "quit"}:
            return
        if not message:
            continue
        run_prompt(message, include_canvas, raw_json)


def main() -> None:
    parser = argparse.ArgumentParser(description="Debug StructAgent chat routing and tool calls.")
    parser.add_argument("message", nargs="*", help="Message to send. Omit for interactive mode.")
    parser.add_argument("--no-canvas", action="store_true", help="Do not include the sample canvas model.")
    parser.add_argument("--raw-json", action="store_true", help="Print the full /api/chat JSON response.")
    args = parser.parse_args()

    include_canvas = not args.no_canvas
    if args.message:
        run_prompt(" ".join(args.message), include_canvas, args.raw_json)
    else:
        repl(include_canvas, args.raw_json)


if __name__ == "__main__":
    main()
