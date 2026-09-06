# Setup and Configuration Guide

## Prerequisites

- **Python 3.12+** (project uses Python 3.12)
- **Conda** (for environment management) or **pip** (for direct installation)
- **Ollama** (optional, for LLM-powered features) running on accessible server
- **Git** (for cloning the repository)

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd struct_analysis
```

### 2. Create Conda Environment

```bash
conda env create -f environment.yml
conda activate struct_analysis
```

This installs all dependencies including:
- Flask 3.1.2
- OpenSeesPy
- Pydantic 2.13.2
- PydanticAI 1.5.0
- Pydantic-Settings 2.13.1
- NumPy
- httpx 0.28.1
- Waitress 3.0.2
- python-dotenv 1.2.2
- pytest 8.3.4, pytest-cov 6.0.0, pytest-env 1.7.0
- ruff, pre-commit

### 3. Alternative: pip Installation

```bash
python -m venv venv
# On Windows: .\venv\Scripts\activate
pip install flask httpx numpy openseespy pydantic pydantic-ai pydantic-settings python-dotenv waitress pytest pytest-cov pytest-env ruff
```

### 4. Configure Environment

Copy the example environment file and customize:

```bash
cp .env.example .env
```

Edit .env with your settings:

```env
# Ollama Configuration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=glm-4.7-flash:latest

# Agent LLM Provider: ollama, pydanticai, or none
AGENT_LLM_PROVIDER=ollama
AGENT_LLM_TIMEOUT_S=8.0

# Application Settings
APP_ENV=development
APP_SECRET_KEY=change-me-before-deploy
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| OLLAMA_BASE_URL | http://localhost:11434 | URL of Ollama server |
| OLLAMA_MODEL | glm-4.7-flash:latest | Model name |
| AGENT_LLM_PROVIDER | ollama | LLM provider: `ollama`, `pydanticai`, or `none` |
| AGENT_LLM_TIMEOUT_S | 8.0 | Timeout in seconds for LLM calls |
| APP_ENV | development | Application environment |
| APP_SECRET_KEY | (random if unset) | Flask secret key (change for production) |

## Running the Application

### Development Mode

```bash
python -m flask --app app.main run
```

Do NOT use `--debug` flag — the debug reloader may not pick up new route files. The application will be available at `http://localhost:5000`.

### Production Mode with Waitress (Windows)

```bash
waitress-serve --port 5000 app.main:get_app()
```

### Production Mode with Gunicorn (Linux/Mac)

```bash
gunicorn --bind 0.0.0.0:5000 --workers 4 --timeout 120 'app.main:get_app()'
```

### Docker (if Dockerfile exists)

```bash
docker build -t struct_analysis .
docker run -p 5000:5000 --env-file .env struct_analysis
```

## Ollama Setup

### Local Ollama Server

1. Install Ollama from https://ollama.ai
2. Pull the required model:

```bash
ollama pull glm-4.7-flash:latest
```

3. Start the Ollama server (runs on `http://localhost:11434` by default)

### Remote Ollama Server

If using a remote Ollama server:
1. Ensure the server is accessible from your application
2. Set `OLLAMA_BASE_URL` to the remote server address
3. Ensure the required model is pulled on the remote server

### LLM Provider Options

- **ollama**: Direct HTTP calls to Ollama `/api/generate` endpoint
- **pydanticai**: Uses the PydanticAI adapter with an OpenAI-compatible client (better structured output support); falls back to `ollama` if the adapter is unavailable
- **none**: Disables LLM features, uses deterministic fallbacks only

## Running Tests

On Windows, set PYTHONPATH and run pytest:

```powershell
$env:PYTHONPATH='.'; pytest
```

### Test Coverage

The suite (290+ tests) covers the full surface:
- Chat/analysis routes: analysis requests, conversation-only, canvas actions, context-aware queries, evaluate endpoint
- Project persistence: CRUD operations
- LLM status: response format
- Deterministic load tools: wind, seismic, snow, slab
- Element design: steel section selection, concrete, timber, foundation, fatigue, cost
- Advanced analysis: P-delta, response spectrum, story forces, sensitivity, multi-hazard, cross-validation
- 3D frame OpenSeesPy solver and solver fallback chains
- OpenAPI spec generation and PDF export

Run with coverage (the CI gate requires 80%+):

```powershell
$env:PYTHONPATH='.'; pytest --cov=app --cov-report=term --cov-fail-under=80
```

## Project Structure

```
struct_analysis/
├── app/
│   ├── __init__.py
│   ├── main.py              # Flask app factory, DB init, blueprint wiring
│   ├── config.py            # Settings and configuration
│   ├── models.py            # Pydantic request/response schemas
│   ├── agents.py            # Multi-agent system orchestration
│   ├── llm.py               # LLM client implementations
│   ├── logging_config.py    # Structured logging setup
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── pages.py         # Static page routes, health, OpenAPI spec + docs
│   │   ├── analyze.py       # Analysis & chat API routes (+ sensitivity, multi-hazard)
│   │   ├── design.py        # Steel/concrete/timber/foundation/fatigue/cost design
│   │   ├── loads.py         # Wind/seismic/snow/slab/response-spectrum/P-delta
│   │   ├── projects.py      # Project CRUD API routes
│   │   ├── history.py       # History & export (CSV/report/PDF) API routes
│   │   └── sections.py      # Steel section database routes
│   ├── tools/               # Engineering analysis tools
│   │   ├── __init__.py
│   │   ├── beam.py          # Closed-form beam analysis
│   │   ├── opensees_beam.py # OpenSeesPy beam solver
│   │   ├── truss.py         # Truss analysis (OpenSeesPy + direct stiffness)
│   │   ├── frame.py         # 2D frame analysis (OpenSeesPy + direct stiffness)
│   │   ├── column.py        # Column buckling analysis
│   │   ├── opensees_3d.py   # 3D structure analysis
│   │   ├── sections.py      # Steel section database
│   │   ├── section_select.py# AISC 360 steel section selection
│   │   ├── load_combinations.py  # ASCE 7-22 load combinations
│   │   ├── wind.py          # ASCE 7-22 wind loads
│   │   ├── seismic.py       # ASCE 7-22 seismic base shear
│   │   ├── snow.py          # ASCE 7-22 snow loads
│   │   ├── slab.py          # ACI 318 two-way slab
│   │   ├── story_forces.py  # Map story forces onto a 3D model
│   │   ├── response_spectrum.py  # Multi-mode response-spectrum analysis
│   │   ├── pdelta.py        # P-delta second-order effects
│   │   ├── concrete.py      # ACI 318 concrete beam/column design
│   │   ├── timber.py        # NDS timber beam design
│   │   ├── foundation.py    # Spread footing + pile capacity
│   │   ├── fatigue.py       # AISC 360 fatigue S-N check
│   │   ├── cost.py          # Steel cost estimation
│   │   ├── sensitivity.py   # OAT parametric sensitivity study
│   │   ├── multi_hazard.py  # Multi-hazard load-combination optimizer
│   │   ├── cross_validation.py  # Independent-solver cross-validation
│   │   ├── report.py        # Report formatter
│   │   ├── pdf_export.py    # Markdown -> PDF writer
│   │   └── openapi.py       # OpenAPI 3.0 spec generator
│   └── static/              # Frontend assets
│       ├── index.html       # Application shell
│       ├── styles.css       # Complete design system
│       └── js/              # JavaScript modules
│           ├── chat.js, analysis.js, main.js, ...
│           └── canvas3d/    # Three.js 3D canvas modules
├── scripts/
│   └── debug_chat.py        # CLI debug tool for chat/analysis
├── docs/                    # Documentation
│   ├── API.md, ARCHITECTURE.md, BACKEND.md, FRONTEND.md, SETUP.md, TOOLS.md
├── demo_images/             # Screenshots for README
├── environment.yml          # Conda environment definition
├── .env.example             # Environment variable template
├── .gitignore               # Git ignore rules
├── LICENSE                  # PolyForm Noncommercial 1.0.0
└── README.md               # Project overview
```

## Troubleshooting

### OpenSeesPy Import Error

If you encounter OpenSeesPy import errors:
1. Ensure OpenSeesPy is installed: `pip install openseespy`
2. On Windows, you may need Visual C++ Redistributable
3. Check that your Python version is compatible (3.12+)

### LLM Connection Timeout

If LLM calls timeout:
1. Verify Ollama server is running: `curl http://localhost:11434/api/tags`
2. Check `OLLAMA_BASE_URL` is correct
3. Increase `AGENT_LLM_TIMEOUT_S` if needed
4. Try switching to the `pydanticai` provider

### SQLite Database Lock

If you encounter database lock errors:
1. Ensure no other process is accessing the database files
2. Delete `analysis_history.db` or `projects.db` to start fresh (history will be lost)
3. In production, consider using a proper database

### Port Already in Use

If port 5000 is already in use:
1. Change the port: `python -m flask --app app.main run --port 8080`
2. Or find and kill the process using the port
