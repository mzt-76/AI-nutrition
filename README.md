# AI Nutrition Assistant

A full-stack AI nutrition coaching app — personalized meal plans, daily macro tracking, and adaptive weekly feedback. Built with **Pydantic AI**, **React 18**, **FastAPI**, and **Supabase**.

> Built as part of the AI Agent Mastery course by Cole Medin and the [Dynamous](https://dynamous.ai/) community.

---

## What It Does

- **Conversational AI coach** — ask anything about nutrition in natural French, get science-backed answers
- **Calculates nutritional needs** using Mifflin-St Jeor (BMR, TDEE, macros) with automatic goal inference
- **Generates weekly meal plans** with 712 recipes, MILP portion optimization, and allergen/preference filtering
- **Creates shopping lists** from meal plans with ingredient aggregation and categorization
- **Tracks daily intake** — log meals via chat, see real-time macro gauges with progress visualization
- **Adapts weekly** based on weight trends, hunger, energy, sleep, and adherence rate
- **Searches nutritional knowledge** via RAG (Supabase pgvector) and web search (Brave API)
- **Analyzes body composition** from photos (GPT-4 Vision)
- **Remembers preferences** across sessions (mem0 long-term memory)
- **Generative UI** — 7 rich interactive components (nutrition summaries, macro gauges, meal cards, day plans) rendered inline in chat

---

## Architecture

```
Frontend (React 18 + TypeScript 5 + Vite 5)
  │  Tabs: Chat · Suivi du Jour · Mes Plans
  │  Supabase Auth · Generative UI · NDJSON streaming
  │
  ↕  HTTPS / JWT
  │
Backend (FastAPI)
  │  Streaming NDJSON · JWT auth · Rate limiting
  │  /api/agent · /api/conversations · /api/meal-plans
  │  /api/daily-log · /api/favorite-recipes · /api/shopping-lists
  │
  ↕
  │
Pydantic AI Agent (6 tools, progressive disclosure)
  │
  ├── nutrition-calculating/    BMR, TDEE, macros (Mifflin-St Jeor + ISSN)
  ├── meal-planning/            Week/day plans, MILP optimizer, recipes
  ├── food-tracking/            Daily food logging, macro summaries
  ├── shopping-list/            Ingredient aggregation from meal plans
  ├── weekly-coaching/          Adaptive adjustments + red flag detection
  ├── knowledge-searching/      RAG (Supabase pgvector) + Brave web search
  └── body-analyzing/           GPT-4 Vision body composition estimation
  │
  ↕
  │
Data Layer
  ├── Supabase (PostgreSQL + pgvector) — 17 tables, RLS on all
  ├── OpenFoodFacts (264K French products for precise macros)
  └── mem0 (cross-session memory)
```

**Key pattern**: The agent never calls domain logic directly. It loads a skill's `SKILL.md` to learn what scripts are available, then calls `run_skill_script()` which auto-injects all shared clients. Adding a new skill = only touching files inside `skills/<name>/`.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | React 18, TypeScript 5, Vite 5, shadcn/ui, Tailwind CSS, Recharts, Zod |
| **Backend** | FastAPI, Pydantic AI, Python 3.11+ |
| **LLMs** | Claude Haiku 4.5 (agent) + GPT-4o-mini (vision, embeddings) |
| **Database** | Supabase (PostgreSQL + pgvector), RLS on all 17 tables |
| **Auth** | Supabase Auth (email/password + Google OAuth), JWT verification |
| **Food data** | OpenFoodFacts (264K products, local full-text search) |
| **Optimization** | SciPy MILP solver for portion scaling |
| **Memory** | mem0 (cross-session preference tracking) |
| **Web search** | Brave Search API |
| **Testing** | pytest (718 tests) + pydantic-evals (21 eval files) |
| **CI/CD** | GitHub Actions + Render (static site + Docker) |
| **Linting** | ruff + mypy + ESLint |

---

## Project Numbers

| Metric | Count |
|---|---|
| Unit tests | **718** |
| Eval files | **21** |
| Skill domains | **7** |
| Skill scripts | **15** |
| Generative UI components | **7** |
| Recipes in DB | **712** (OFF-validated) |
| Ingredient mappings | **1,217** (auto-growing) |
| OpenFoodFacts products | **264,495** (French, with nutrition data) |
| RAG document chunks | **485** |
| Database tables | **17** (all RLS-enabled) |

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+ (for frontend)
- A Supabase project (free tier works)
- API keys: Anthropic, OpenAI (embeddings + vision), optionally Brave Search

### 1. Clone & Install

```bash
git clone https://github.com/mzt-76/AI-nutrition.git
cd AI-nutrition

# Backend
python -m venv venv
source venv/bin/activate   # Linux/Mac
pip install -r requirements.txt

# Frontend
cd frontend
npm install
cd ..
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your API keys and Supabase credentials

cp frontend/.env.example frontend/.env
# Edit frontend/.env with your Supabase URL and anon key
```

### 3. Run

```bash
# Backend API
uvicorn src.api:app --port 8001 --reload

# Frontend (separate terminal)
cd frontend && npm run dev

# Or CLI only (no frontend needed)
python -m src.cli
```

The frontend runs on `http://localhost:8080`, the backend on `http://localhost:8001`.

### 4. Run Tests

```bash
pytest tests/ -v

# Linting
ruff format src/ tests/ && ruff check src/ tests/ && mypy src/
```

---

## Deployment

The project deploys on **Render** with 2 services:
- **Frontend**: Static site (free) — Vite build served via CDN
- **Backend**: Docker web service — FastAPI + Agent + Skills

See `render.yaml` for the Blueprint configuration.

---

## Project Structure

```
AI-nutrition/
├── src/                           # Backend
│   ├── agent.py                   # Pydantic AI agent (6 tools, never grows)
│   ├── api.py                     # FastAPI (streaming NDJSON, JWT, CRUD)
│   ├── tools.py                   # Profile tools (fetch + update)
│   ├── prompt.py                  # System prompt (French nutrition coach)
│   ├── clients.py                 # All API clients
│   ├── db_utils.py                # DB operations (conversations, messages)
│   ├── ui_components.py           # Generative UI marker extraction
│   ├── skill_loader.py            # Skill discovery & progressive disclosure
│   ├── nutrition/                 # Domain logic (11.6K LOC)
│   │   ├── calculations.py        # BMR, TDEE, macros (Mifflin-St Jeor)
│   │   ├── adjustments.py         # Weight trends, weekly adjustments
│   │   ├── recipe_db.py           # Recipe CRUD with allergen filtering
│   │   ├── portion_optimizer_v2.py # MILP per-ingredient optimizer
│   │   ├── openfoodfacts_client.py # Local ingredient matching (264K products)
│   │   └── ...
│   └── RAG_Pipeline/              # Document sync (Google Drive + Local)
│
├── skills/                        # Self-contained skill domains
│   ├── nutrition-calculating/     # SKILL.md + scripts/ + references/
│   ├── meal-planning/             # Week plan, day plan, recipes, favorites
│   ├── food-tracking/             # Daily food logging, summaries
│   ├── shopping-list/             # Ingredient aggregation
│   ├── weekly-coaching/           # Adaptive feedback + red flag protocol
│   ├── knowledge-searching/       # RAG + web search
│   └── body-analyzing/            # GPT-4 Vision analysis
│
├── frontend/                      # React 18 + TypeScript 5 + Vite 5
│   └── src/
│       ├── components/generative-ui/ # 7 rich UI components
│       ├── components/ui/         # shadcn/ui primitives
│       ├── hooks/                 # useDailyTracking, useAuth, etc.
│       └── pages/                 # Chat, DailyTracking, MyPlans, MealPlanView
│
├── tests/                         # 718 unit tests
├── evals/                         # 21 eval files (LLM behavior scoring)
├── sql/                           # Database schema + migrations
├── render.yaml                    # Render Blueprint (2 services)
├── Dockerfile                     # Backend Docker image
└── CLAUDE.md                      # Development rules & coding standards
```

---

## Safety Constraints (Hardcoded)

```python
MIN_CALORIES_WOMEN = 1200
MIN_CALORIES_MEN = 1500
ALLERGEN_ZERO_TOLERANCE = True    # Cross-checks all ingredients against user allergens
DISLIKED_FOODS_FILTERED = True    # Recipe DB excludes disliked foods at query time
```

These are enforced in code, not prompts. The agent cannot bypass them.

---

## Acknowledgments

- AI Agent Mastery course by Cole Medin and the [Dynamous](https://dynamous.ai/) community
- [Pydantic AI](https://github.com/pydantic/pydantic-ai) framework
- [OpenFoodFacts](https://world.openfoodfacts.org/) open food database
- Nutritional science: ISSN, Mifflin et al. (1990), Helms et al. (2014)

---

## License

This project was built for personal use and learning. Feel free to explore the code, use patterns, and adapt for your own projects.
