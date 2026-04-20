# Structural Analysis Multi-Agent Prototype

A minimal web-hosted structural engineering assistant. V1 uses a lightweight custom multi-agent workflow, Ollama as the LLM provider, and deterministic Python tools for preliminary beam analysis.

This prototype is for preliminary engineering assistance only. It is not a licensed design approval system.

## What Works In V1

- Web UI served by FastAPI
- Ollama-backed agent calls with graceful fallback if Ollama is unavailable
- Structural intent extraction
- Analysis planning
- Simply supported beam calculator for uniform loads
- Result critic and engineering report generation
- Environment variables for API endpoints and secrets

OpenSeesPy is planned for the next solver layer. V1 keeps the installed environment light and uses deterministic beam formulas first, so the service is easy to run and deploy.

## Setup

```powershell
conda env create -f environment.yml
conda activate struct-agent
Copy-Item .env.example .env
```

Edit `.env` if your Ollama server or model changes.

## Run Locally

```powershell
uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

## Example Prompt

```text
Analyze a simply supported steel beam. Span is 6 m, uniform load is 20 kN/m, E is 200 GPa, I is 8e-6 m4. Check deflection against L/360.
```

## API

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/analyze `
  -ContentType 'application/json' `
  -Body '{"prompt":"Analyze a simply supported steel beam. Span is 6 m, uniform load is 20 kN/m, E is 200 GPa, I is 8e-6 m4. Check deflection against L/360."}'
```

## Project Layout

```text
app/
  main.py              FastAPI app and routes
  agents.py            Lightweight multi-agent orchestration
  config.py            Env-based settings
  llm.py               Ollama client
  models.py            Pydantic request/response models
  static/              Browser UI
  tools/
    beam.py            Structural beam calculator
    report.py          Markdown report formatter
```

## Next Solver Step

After V1 is running, add OpenSeesPy as an optional solver package and route frame or advanced beam tasks to it from `Analysis Planning Agent`. On Windows, verify `import openseespy.opensees` before making it part of the default environment because missing native DLL/runtime dependencies can stop imports.

## Deployment Notes

Render free web service is the simplest backend-oriented deployment path for this stack. Keep `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, and `APP_SECRET_KEY` in the host's environment variable settings, not in git.

If the Ollama server is private or blocked from the hosting provider, deploy Ollama on a reachable machine or swap the LLM client later while keeping the same agent interface.
