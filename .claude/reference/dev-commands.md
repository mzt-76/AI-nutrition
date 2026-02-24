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

## Frontend (React Prototype)

```bash
# Setup
cd prototype/loveable_interface
npm install
cp .env.example .env  # Set VITE_API_URL and VITE_USER_ID

# Run (requires backend running in another terminal)
npm run dev  # http://localhost:8080

# Lint & Type Check
npm run lint && npx tsc --noEmit
```

**Env vars:**
- `VITE_API_URL` — FastAPI backend URL (default: `http://localhost:8001`)
- `VITE_USER_ID` — Supabase `user_profiles.id` (temporary until auth is wired)
