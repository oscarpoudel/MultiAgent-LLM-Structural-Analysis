# Structural Analysis Multi-Agent Prototype

A minimal web-hosted structural engineering assistant. V1 uses Flask, deterministic agent fallbacks by default, optional Ollama/PydanticAI LLM calls, and OpenSeesPy tools for preliminary beam analysis.

This prototype is for preliminary engineering assistance only. It is not a licensed design approval system.

## What Works In V1

- Web UI served by Flask
- Chat-style assistant for greetings, capability questions, and analysis requests
- Optional Ollama or PydanticAI-managed agent calls with graceful fallback if Ollama is unavailable
- Structural intent extraction
- Analysis planning
- OpenSeesPy simply supported beam tool for uniform loads
- Result critic and engineering report generation
- Environment variables for API endpoints and secrets
- Python 3.12 environment with OpenSeesPy installed for the next solver layer

OpenSeesPy is installed and wired into the beam solver. Closed-form calculations remain as a fallback and cross-check.

## Setup

```powershell
conda env create -f environment.yml
conda activate struct-agent
Copy-Item .env.example .env
```

Edit `.env` if your Ollama server or model changes.

The default `.env` uses `AGENT_LLM_PROVIDER=ollama`, so casual chat such as `hi` goes through the configured Ollama model. Chat responses include `source: "llm"` when the model answers and `source: "fallback"` when the model times out or is unavailable. Set `AGENT_LLM_PROVIDER=none` for deterministic fallbacks while debugging solver tools, or `pydanticai` to try the PydanticAI adapter.

## Run Locally

```powershell
python -m flask --app app.main run --debug
```

Open:

```text
http://127.0.0.1:5000
```

## Example Prompt

```text
Analyze a simply supported steel beam. Span is 6 m, uniform load is 20 kN/m, E is 200 GPa, I is 8e-6 m4. Check deflection against L/360.
```

## API

Chat with the assistant:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:5000/api/chat `
  -ContentType 'application/json' `
  -Body '{"message":"hi"}'
```

Run an analysis through the chat endpoint:

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

## Project Layout

```text
app/
  main.py              Flask app and routes
  agents.py            PydanticAI-oriented multi-agent orchestration
  config.py            Env-based settings
  llm.py               PydanticAI/Ollama clients
  models.py            Pydantic request/response models
  static/              Browser UI
  tools/
    beam.py            Structural beam calculator
    report.py          Markdown report formatter
```

## Next Solver Step

After V1 is running, route frame or advanced beam tasks to OpenSeesPy from `Analysis Planning Agent`. On Windows, verify `import openseespy.opensees` in the `struct-agent` environment before building higher-level solver tools around it.

## Deployment Notes

Render free web service is the simplest backend-oriented deployment path for this stack. For production-like local hosting, use Waitress:

```powershell
waitress-serve --listen=127.0.0.1:5000 app.main:app
```

Keep `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, and `APP_SECRET_KEY` in the host's environment variable settings, not in git.

If the Ollama server is private or blocked from the hosting provider, deploy Ollama on a reachable machine or swap the LLM client later while keeping the same agent interface.

## License

This project is licensed under the PolyForm Noncommercial License 1.0.0.

Research, experiment, testing, personal study, educational use, and noncommercial public-interest use are permitted. Commercial use is not permitted without separate written permission from the copyright holder.
