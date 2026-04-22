# Multi-Agent LLM Structural Analysis

A Flask-based structural analysis assistant that combines conversational agent workflows with deterministic engineering tools and OpenSeesPy. The current implementation focuses on preliminary elastic beam checks and provides a foundation for adding more advanced OpenSees models, report generation, and multi-agent planning.

This software is intended for research, education, experimentation, and early-stage engineering assistance. It is not a substitute for review, approval, or design work by a licensed professional engineer.

## Features

- Chat interface for greetings, capability questions, and engineering requests
- Optional Ollama or PydanticAI LLM routing with deterministic fallbacks
- Flask web API and browser UI
- OpenSeesPy-backed simply supported beam analysis for uniform loads
- Closed-form beam calculations for fallback and cross-checking
- Basic result critic for deflection limits, finite-value checks, and missing design inputs
- Markdown report generation with assumptions, warnings, and key results
- Python 3.12 conda environment
- Noncommercial software license for research and educational use

## Current Scope

The current solver path supports a simply supported elastic beam under a full-span uniform distributed load. Given span, load, modulus of elasticity, moment of inertia, and serviceability limit, the assistant reports:

- support reactions
- maximum shear
- maximum moment
- midspan deflection
- deflection limit check
- solver status and agent trace

Future solver extensions may include point loads, cantilever beams, 2D frames, trusses, load combinations, section libraries, and richer OpenSees model generation.

## Safety Notice

All outputs are preliminary and depend on the assumptions and units provided by the user. The assistant does not perform code compliance checks, load path validation, constructability review, connection design, detailing, or licensed engineering approval.

## Project Layout

```text
app/
  agents.py            Agent orchestration and analysis workflow
  config.py            Environment-driven settings
  llm.py               Ollama, PydanticAI, and fallback LLM clients
  main.py              Flask routes and API endpoints
  models.py            Pydantic request and response models
  static/              Browser chat UI
  tools/
    beam.py            Closed-form beam calculations
    opensees_beam.py   OpenSeesPy beam analysis tool
    report.py          Markdown report formatter
tests/
  test_beam_tool.py
  test_flask_app.py
```

## Setup

Create and activate the conda environment:

```powershell
conda env create -f environment.yml
conda activate struct-agent
```

Create a local environment file:

```powershell
Copy-Item .env.example .env
```

Edit `.env` if your Ollama endpoint, model, or timeout settings differ:

```env
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=your-model-name
AGENT_LLM_PROVIDER=ollama
AGENT_LLM_TIMEOUT_S=8.0
```

Supported `AGENT_LLM_PROVIDER` values:

- `ollama`: use the configured Ollama model for conversational responses and agent routing
- `pydanticai`: use the PydanticAI adapter where available
- `none`: skip live LLM calls and use deterministic fallbacks

Chat responses include a `source` field. `source: "llm"` means the model answered. `source: "fallback"` means the model timed out or was unavailable.

## Run Locally

```powershell
python -m flask --app app.main run --debug
```

Open the browser UI:

```text
http://127.0.0.1:5000
```

## Example Prompt

```text
Analyze a simply supported steel beam. Span is 6 m, uniform load is 20 kN/m, E is 200 GPa, I is 8e-6 m4. Check deflection against L/360.
```

## API

Chat endpoint:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:5000/api/chat `
  -ContentType 'application/json' `
  -Body '{"message":"hi"}'
```

Analysis through chat:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:5000/api/chat `
  -ContentType 'application/json' `
  -Body '{"message":"Analyze a simply supported steel beam. Span is 6 m, uniform load is 20 kN/m, E is 200 GPa, I is 8e-6 m4. Check deflection against L/360."}'
```

Direct analysis endpoint:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:5000/api/analyze `
  -ContentType 'application/json' `
  -Body '{"prompt":"Analyze a simply supported steel beam. Span is 6 m, uniform load is 20 kN/m, E is 200 GPa, I is 8e-6 m4. Check deflection against L/360."}'
```

## Testing

```powershell
python -m pytest -p no:cacheprovider
```

## Debug Chat Routing

Use the local CLI debugger to see how chat messages are routed before opening the browser:

```powershell
python scripts/debug_chat.py "draw a simply supported beam with 2m length and 10 kN load at middle"
```

Interactive mode:

```powershell
python scripts/debug_chat.py
```

The debugger prints:

- `canvas-router`: the canvas tool decision (`none`, `clear_canvas`, `draw_simple_beam`)
- `chat-response`: the final `/api/chat` response type
- `canvas-action`: tool payload sent to the browser
- `analysis-traces`: solver/agent traces when an analysis is run

If `source` is `fallback`, the live LLM router was unavailable, disabled, or timed out and the deterministic parser handled the prompt. If `source` is `llm`, the configured LLM produced the routing decision.

## Deployment Notes

For production-like local hosting, use Waitress:

```powershell
waitress-serve --listen=127.0.0.1:5000 app.main:app
```

Keep `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, and `APP_SECRET_KEY` in the host environment, not in source control.

## License

This project is licensed under the PolyForm Noncommercial License 1.0.0.

Research, experimentation, testing, personal study, educational use, and noncommercial public-interest use are permitted. Commercial use is not permitted without separate written permission from the copyright holder.
