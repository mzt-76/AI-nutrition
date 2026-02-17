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
python -m src.cli                    # CLI chat interface
streamlit run src/streamlit_ui.py    # Streamlit UI

# Test & Lint
pytest tests/ -v                     # Run tests
pytest tests/ --cov=src/nutrition    # Test with coverage
ruff format src/ tests/ && ruff check src/ tests/ && mypy src/  # Format, lint, type check
```

---

## Frontend

```bash
# Setup & Run
cd prototype/loveable_interface
npm install
npm run dev  # http://localhost:5173

# Lint & Type Check
npm run lint && npx tsc --noEmit
```
