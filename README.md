# AI Nutrition Assistant

A conversational AI nutrition coach that creates personalized weekly meal plans, tracks progress, and adapts recommendations based on real-world results. Built with **Pydantic AI** and a skill-based progressive disclosure architecture.

> Built as part of the [AI Agent Mastery](https://www.skool.com/ai-agent-mastery) course - Module 4 (Python AI Agent).

---

## What It Does

- **Calculates nutritional needs** using Mifflin-St Jeor (BMR, TDEE, macros) with automatic goal inference from natural language
- **Generates weekly meal plans** with recipes from a local database (121 recipes), portion scaling, and allergen validation
- **Creates shopping lists** from meal plans with ingredient aggregation and categorization
- **Adapts weekly** based on weight trends, hunger, energy, sleep, and adherence rate
- **Searches nutritional knowledge** via RAG (Supabase pgvector) and web search (Brave API)
- **Analyzes body composition** from photos (GPT-4 Vision)
- **Remembers preferences** across sessions (mem0 long-term memory)

The agent speaks French and acts as a warm, science-first nutrition coach.

---

## Architecture

```
User (Streamlit / CLI)
  |
  v
Pydantic AI Agent (Claude Haiku 4.5)
  |-- 6 fixed tools: load_skill, run_skill_script, read_skill_file,
  |                   list_skill_files, fetch_my_profile, update_my_profile
  |
  v
Progressive Disclosure Skills
  |
  |-- nutrition-calculating/    BMR, TDEE, macros (Mifflin-St Jeor + ISSN)
  |-- meal-planning/            Week plans, day plans, recipes, shopping lists
  |-- weekly-coaching/          Adaptive weekly adjustments + red flag detection
  |-- knowledge-searching/      RAG (Supabase pgvector) + Brave web search
  |-- body-analyzing/           GPT-4 Vision body composition estimation
  |-- skill-creator/            Meta-skill: create new skills
  |
  v
Data Layer
  |-- Supabase (PostgreSQL + pgvector)
  |-- OpenFoodFacts (275K French products for precise macros)
  |-- mem0 (cross-session memory)
```

**Key pattern**: The agent never calls domain logic directly. It loads a skill's `SKILL.md` to learn what scripts are available, then calls `run_skill_script()` which auto-injects all shared clients. Adding a new skill = only touching files inside `skills/<name>/`. The agent code (`src/agent.py`) never grows.

---

## Tech Stack

| Component | Technology |
|---|---|
| Agent framework | Pydantic AI 0.0.53 |
| Main LLM | Claude Haiku 4.5 (agent) + Claude Sonnet 4.6 (skill scripts) |
| Database | Supabase (PostgreSQL + pgvector) |
| Ingredient data | OpenFoodFacts (275K products, local full-text search) |
| Memory | mem0 (cross-session preference tracking) |
| Web search | Brave Search API |
| Testing | pytest + pydantic-evals |
| Linting | ruff + mypy |
| Interface | Streamlit (MVP) |

---

## Project Numbers

| Metric | Count |
|---|---|
| Unit tests passing | **365** |
| Eval datasets | **13** (50 test cases across all skill scripts) |
| Skill domains | **6** |
| Skill scripts | **17** |
| Recipes in DB | **121** (30 per meal type) |
| Cached ingredient mappings | **543** (auto-growing) |
| OpenFoodFacts products | **275,000** (French, with nutrition data) |

---

## Quick Start

### Prerequisites

- Python 3.11+
- A Supabase project (free tier works)
- API keys: Anthropic or OpenAI, optionally Brave Search

### 1. Clone & Install

```bash
git clone https://github.com/YOUR_USERNAME/AI-nutrition.git
cd AI-nutrition
python -m venv venv
source venv/bin/activate   # Linux/Mac
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your API keys and Supabase credentials
```

### 3. Set Up Database

Run these SQL files in your Supabase SQL Editor (in this order):

```
sql/create_ingredient_mapping_table.sql    # Must be first (defines shared trigger function)
sql/create_recipes_table.sql
sql/create_user_learning_profile_table.sql
sql/create_weekly_feedback_table.sql
```

**Optional — OpenFoodFacts (precise macro calculation):**

```
sql/create_openfoodfacts_tables.sql
```

Then download the OpenFoodFacts JSONL dump from [openfoodfacts.org/data](https://world.openfoodfacts.org/data) and import it:

```bash
python -m src.nutrition.openfoodfacts_import
```

> The agent works fine without OpenFoodFacts — it just won't have local ingredient nutrition data for precise portion scaling. You can always add it later.

### 4. Seed Recipe Database

```bash
python scripts/seed_recipes_manual.py
```

This inserts 120 French recipes (30 per meal type: petit-dejeuner, dejeuner, diner, collation) with no LLM calls.

### 5. Run

```bash
# Recommended: CLI (no extra dependencies, works immediately)
python -m src.cli

# Optional: Streamlit UI (MVP, requires .streamlit/ config)
streamlit run src/streamlit_ui.py
```

> **Note for quick testing**: Use the CLI (`python -m src.cli`). The Streamlit interface is a work-in-progress MVP and not required to explore the agent capabilities.

### 6. Run Tests

```bash
# All tests (non-integration)
pytest tests/ evals/ -m "not integration" -v

# Just the eval suite
pytest evals/test_skill_scripts.py -v
```

---

## Project Structure

```
AI-nutrition/
├── src/                           # Core agent package
│   ├── agent.py                   # Pydantic AI agent (6 tools, never grows)
│   ├── tools.py                   # Profile tools (fetch + update)
│   ├── prompt.py                  # System prompt (French nutrition coach)
│   ├── clients.py                 # All API clients (Supabase, OpenAI, Anthropic, mem0)
│   ├── skill_loader.py            # Skill discovery & progressive disclosure
│   ├── skill_tools.py             # Skill tools (load, read, list)
│   ├── nutrition/                 # Domain logic (pure functions)
│   │   ├── calculations.py        # BMR, TDEE, protein, macros (Mifflin-St Jeor)
│   │   ├── adjustments.py         # Weight trends, red flags, weekly adjustments
│   │   ├── validators.py          # Allergen + macro validation
│   │   ├── recipe_db.py           # Recipe CRUD with allergen filtering
│   │   ├── meal_distribution.py   # Macro distribution across meals
│   │   ├── meal_plan_optimizer.py # Portion optimization with OpenFoodFacts
│   │   ├── openfoodfacts_client.py # Local ingredient matching (cache-first)
│   │   └── ...
│   └── RAG_Pipeline/              # Document sync (Google Drive + Local Files)
│
├── skills/                        # Self-contained skill domains
│   ├── nutrition-calculating/     # SKILL.md + scripts/ + references/
│   ├── meal-planning/             # 8 scripts: week plan, day plan, recipes, shopping list...
│   ├── weekly-coaching/           # Adaptive feedback + red flag protocol
│   ├── knowledge-searching/       # RAG + web search
│   ├── body-analyzing/            # GPT-4 Vision analysis
│   └── skill-creator/             # Meta-skill for creating new skills
│
├── tests/                         # Deterministic unit tests (365 passing)
├── evals/                         # Pydantic-evals (13 datasets, 50 cases)
├── scripts/                       # LLM-free utilities (recipe seeder)
├── sql/                           # Database schema + migrations
└── CLAUDE.md                      # Development rules & coding standards
```

---

## Example Conversation

```
User: "Calcule mes besoins nutritionnels: 35 ans, homme, 87kg, 178cm, activité modérée,
       je fais de la musculation"

Agent: [calls load_skill("nutrition-calculating")]
       [calls run_skill_script("nutrition-calculating", "calculate_nutritional_needs", {...})]

       Voici tes besoins nutritionnels:

       - BMR: 1 812 kcal (Mifflin-St Jeor)
       - TDEE: 2 808 kcal (activité modérée × 1.55)
       - Objectif: Prise de masse → 3 108 kcal/jour (+300 surplus)

       Macros:
       - Protéines: 174g (2.0g/kg — ISSN recommandation hypertrophie)
       - Lipides: 76g (22% des calories totales)
       - Glucides: 387g (le reste pour l'énergie à l'entraînement)
```

```
User: "Génère un plan repas pour cette semaine"

Agent: [calls load_skill("meal-planning")]
       [calls run_skill_script("meal-planning", "generate_week_plan", {...})]

       → Generates 7 days with recipes from DB, scales portions to hit targets,
         validates allergens, saves to database, outputs Markdown document.
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

3. **Eval-driven development**: Every skill script has a pydantic-evals dataset with mocked dependencies. Safety constraints are validated in evals, not just hoped for.

4. **Skill scripts are orchestrators**: Domain logic lives in `src/nutrition/` — skill scripts import it, never rewrite it. This prevents duplication and ensures testability.

5. **OpenFoodFacts over APIs**: 275K products stored locally in PostgreSQL with full-text + trigram search. No rate limits, <10ms per lookup, 90%+ match rate on French ingredients.

---

## License

This project was built for personal use and learning. Feel free to explore the code, use patterns, and adapt for your own projects.

---

## Acknowledgments

- [AI Agent Mastery](https://www.skool.com/ai-agent-mastery) course by Brandon Hancock
- [Pydantic AI](https://github.com/pydantic/pydantic-ai) framework
- [OpenFoodFacts](https://world.openfoodfacts.org/) open food database
- Nutritional science: ISSN, Mifflin et al. (1990), Helms et al. (2014)
