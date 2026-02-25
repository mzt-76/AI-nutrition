# Development Commands

**Purpose:** Quick reference for setup, run, test, and lint commands.

---

## Backend

```bash
# Setup (from project root)
python -m venv venv && source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # Edit with API keys

# Run
python -m src                        # CLI chat interface
python -m src api                    # FastAPI server (port 8001)
uvicorn src.api:app --port 8001 --reload  # FastAPI server (alternative)
streamlit run src/streamlit_ui.py    # Streamlit UI

# Test & Lint
pytest tests/ -v                     # Run tests
pytest tests/ --cov=src/nutrition    # Test with coverage
ruff format src/ tests/ && ruff check src/ tests/ && mypy src/  # Format, lint, type check
```

---

## Frontend

```bash
# Setup
cd frontend
npm install
cp .env.example .env  # Edit with Supabase keys

# Run (requires backend running in another terminal)
npm run dev  # http://localhost:8080

# Build & Type Check
npm run build
npx tsc --noEmit
npm run lint
```

**Env vars (`frontend/.env`):**
- `VITE_SUPABASE_URL` — Supabase project URL
- `VITE_SUPABASE_ANON_KEY` — Supabase anon/publishable key
- `VITE_AGENT_ENDPOINT` — FastAPI agent endpoint (default: `http://localhost:8001/api/agent`)
- `VITE_ENABLE_STREAMING` — Enable NDJSON streaming (`true`)

**CORS:** Backend `.env` must include `http://localhost:8080` in `CORS_ORIGINS`.

---

## Full Stack (both terminals)

```bash
# Terminal 1 — Backend
uvicorn src.api:app --host 0.0.0.0 --port 8001 --reload

# Terminal 2 — Frontend
cd frontend && npm run dev
```

Open http://localhost:8080, login with Supabase Auth credentials.
