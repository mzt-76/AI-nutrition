# AI Nutrition Assistant

A full-stack AI nutrition coaching app — personalized meal plans, daily macro tracking, and adaptive weekly feedback. Built with **Pydantic AI**, **React 18**, **FastAPI**, and **Supabase**.

> Built as part of the [AI Agent Mastery](https://www.skool.com/ai-agent-mastery) course (Modules 4 & 5).

---

## What It Does

- **Conversational AI coach** — ask anything about nutrition in natural French, get science-backed answers
- **Calculates nutritional needs** using Mifflin-St Jeor (BMR, TDEE, macros) with automatic goal inference
- **Generates weekly meal plans** with recipes from a local database (123 recipes), portion scaling, and allergen validation
- **Creates shopping lists** from meal plans with ingredient aggregation and categorization
- **Tracks daily intake** — log meals via chat or validate your day's plan, see real-time macro gauges
- **Adapts weekly** based on weight trends, hunger, energy, sleep, and adherence rate
- **Searches nutritional knowledge** via RAG (Supabase pgvector) and web search (Brave API)
- **Analyzes body composition** from photos (GPT-4 Vision)
- **Remembers preferences** across sessions (mem0 long-term memory)
- **Generative UI** — rich interactive cards (nutrition summaries, macro gauges, meal cards) rendered inline in chat

---

## Architecture

```
Frontend (React 18 + TypeScript 5)
  │  3 tabs: Chat · Suivi du Jour · Mes Plans
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
  ├── meal-planning/            Week plans, day plans, recipes, shopping lists
  ├── weekly-coaching/          Adaptive weekly adjustments + red flag detection
  ├── knowledge-searching/      RAG (Supabase pgvector) + Brave web search
  ├── body-analyzing/           GPT-4 Vision body composition estimation
  └── skill-creator/            Meta-skill: create new skills
  │
  ↕
  │
Data Layer
  ├── Supabase (PostgreSQL + pgvector) — 13+ tables, RLS on all
  ├── OpenFoodFacts (275K French products for precise macros)
  └── mem0 (cross-session memory)
```

**Key pattern**: The agent never calls domain logic directly. It loads a skill's `SKILL.md` to learn what scripts are available, then calls `run_skill_script()` which auto-injects all shared clients. Adding a new skill = only touching files inside `skills/<name>/`.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | React 18, TypeScript 5, Vite 5, shadcn/ui, Tailwind CSS, Recharts, Zod |
| **Backend** | FastAPI, Pydantic AI 0.0.53, Python 3.11+ |
| **LLMs** | Claude Haiku 4.5 (agent) + Claude Sonnet 4.6 (skill scripts) |
| **Database** | Supabase (PostgreSQL + pgvector), RLS on all tables |
| **Auth** | Supabase Auth (email/password + Google OAuth), JWT verification |
| **Food data** | OpenFoodFacts (275K products, local full-text search) |
| **Memory** | mem0 (cross-session preference tracking) |
| **Web search** | Brave Search API |
| **Testing** | pytest (366 tests) + pydantic-evals (13 datasets, 50 cases) |
| **Linting** | ruff + mypy + ESLint |

---

## Project Numbers

| Metric | Count |
|---|---|
| Unit tests passing | **366** |
| Eval datasets | **13** (50 test cases across all skill scripts) |
| Skill domains | **6** |
| Skill scripts | **17** |
| Generative UI components | **7** |
| Recipes in DB | **123** |
| Cached ingredient mappings | **546** (auto-growing) |
| OpenFoodFacts products | **275,000** (French, with nutrition data) |
| Database tables | **13+** (all RLS-enabled) |

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+ (for frontend)
- A Supabase project (free tier works)
- API keys: Anthropic or OpenAI, optionally Brave Search

### 1. Clone & Install

```bash
git clone https://github.com/YOUR_USERNAME/AI-nutrition.git
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
# Backend
cp .env.example .env
# Edit .env with your API keys and Supabase credentials

# Frontend
cp frontend/.env.example frontend/.env
# Edit frontend/.env with your Supabase URL and anon key
```

### 3. Set Up Database

Run these SQL files in your Supabase SQL Editor (in order):

```
sql/create_ingredient_mapping_table.sql    # Must be first
sql/create_recipes_table.sql
sql/create_user_learning_profile_table.sql
sql/create_weekly_feedback_table.sql
sql/5_add_user_id_columns.sql
sql/6_rls_per_user_tables.sql
sql/7_rls_global_reference_tables.sql
sql/8_fix_function_search_paths.sql
```

**Optional — OpenFoodFacts (precise macro calculation):**

```
sql/create_openfoodfacts_tables.sql
```

Then download the OpenFoodFacts JSONL dump from [openfoodfacts.org/data](https://world.openfoodfacts.org/data) and import:

```bash
python -m src.nutrition.openfoodfacts_import
```

> The agent works fine without OpenFoodFacts — it just won't have local ingredient nutrition data for precise portion scaling.

### 4. Seed Recipe Database

```bash
python scripts/seed_recipes_manual.py
```

Inserts 120 French recipes (30 per meal type) with no LLM calls.

### 5. Run

```bash
# Backend API
uvicorn src.api:app --port 8001 --reload

# Frontend (separate terminal)
cd frontend && npm run dev

# Or CLI only (no frontend needed)
python -m src.cli
```

The frontend runs on `http://localhost:8080`, the backend on `http://localhost:8001`.

### 6. Run Tests

```bash
# All unit tests
pytest tests/ evals/ -m "not integration" -v

# Just the eval suite
pytest evals/test_skill_scripts.py -v

# Linting
ruff format src/ tests/ && ruff check src/ tests/ && mypy src/
```

---

## Project Structure

```
AI-nutrition/
├── src/                           # Backend
│   ├── agent.py                   # Pydantic AI agent (6 tools, never grows)
│   ├── api.py                     # FastAPI (streaming NDJSON, JWT, conversations)
│   ├── tools.py                   # Profile tools (fetch + update)
│   ├── prompt.py                  # System prompt (French nutrition coach)
│   ├── clients.py                 # All API clients
│   ├── db_utils.py                # DB operations (conversations, messages)
│   ├── ui_components.py           # Generative UI marker extraction
│   ├── skill_loader.py            # Skill discovery & progressive disclosure
│   ├── nutrition/                 # Domain logic (pure functions)
│   │   ├── calculations.py        # BMR, TDEE, macros (Mifflin-St Jeor)
│   │   ├── adjustments.py         # Weight trends, weekly adjustments
│   │   ├── recipe_db.py           # Recipe CRUD with allergen filtering
│   │   ├── openfoodfacts_client.py # Local ingredient matching
│   │   └── ...
│   └── RAG_Pipeline/              # Document sync (Google Drive + Local)
│
├── skills/                        # Self-contained skill domains
│   ├── nutrition-calculating/     # SKILL.md + scripts/ + references/
│   ├── meal-planning/             # 9 scripts: week plan, day plan, recipes...
│   ├── weekly-coaching/           # Adaptive feedback + red flag protocol
│   ├── knowledge-searching/       # RAG + web search
│   ├── body-analyzing/            # GPT-4 Vision analysis
│   └── skill-creator/             # Meta-skill
│
├── frontend/                      # React 18 + TypeScript 5 + Vite 5
│   └── src/
│       ├── components/chat/       # Chat UI (streaming, messages, input)
│       ├── components/generative-ui/ # 7 rich UI components
│       ├── components/ui/         # shadcn/ui primitives
│       └── pages/                 # Chat, Login, Admin, MealPlanView
│
├── tests/                         # Deterministic unit tests (366 passing)
├── evals/                         # Pydantic-evals (13 datasets, 50 cases)
├── sql/                           # Database schema + migrations
└── CLAUDE.md                      # Development rules & coding standards
```

---

## Example Conversation

```
User: "Calcule mes besoins nutritionnels: 35 ans, homme, 87kg, 178cm, activité modérée,
       je fais de la musculation"

Agent: [loads skill → runs calculate_nutritional_needs]

       Voici tes besoins nutritionnels:

       - BMR: 1 812 kcal (Mifflin-St Jeor)
       - TDEE: 2 808 kcal (activité modérée × 1.55)
       - Objectif: Prise de masse → 3 108 kcal/jour (+300 surplus)

       Macros:
       - Protéines: 174g (2.0g/kg — ISSN)
       - Lipides: 76g (22% des calories totales)
       - Glucides: 387g (énergie pour l'entraînement)
```

```
User: "Génère un plan repas pour demain"

Agent: [loads skill → runs generate_day_plan]

       → Generates a full day with recipes from DB, scales portions to hit targets,
         validates allergens, renders as interactive DayPlanCard in chat.
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

## Key Design Decisions

1. **Science-first**: All formulas cite peer-reviewed sources (Mifflin-St Jeor, ISSN position stands). Fat macros = 20-25% of total calories (not remainder).

2. **Progressive disclosure**: The agent starts with just skill names. It loads full instructions only when needed, keeping context lean (~1,600 tokens base).

3. **Eval-driven development**: Every skill script has a pydantic-evals dataset with mocked dependencies. Safety constraints are validated in evals.

4. **Skill scripts are orchestrators**: Domain logic lives in `src/nutrition/` — skill scripts import it, never rewrite it.

5. **OpenFoodFacts over APIs**: 275K products stored locally in PostgreSQL with full-text + trigram search. No rate limits, <10ms per lookup.

6. **Generative UI**: Agent emits structured markers in text → backend extracts → frontend renders rich components. Zod validates all props.

---

## License

This project was built for personal use and learning. Feel free to explore the code, use patterns, and adapt for your own projects.

---

## Acknowledgments

- [AI Agent Mastery](https://www.skool.com/ai-agent-mastery) course by Brandon Hancock
- [Pydantic AI](https://github.com/pydantic/pydantic-ai) framework
- [OpenFoodFacts](https://world.openfoodfacts.org/) open food database
- Nutritional science: ISSN, Mifflin et al. (1990), Helms et al. (2014)
