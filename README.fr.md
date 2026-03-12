# AI Nutrition Assistant

> Try it: [ai-nutrition-frontend-78p7.onrender.com](https://ai-nutrition-frontend-78p7.onrender.com)

---

## About

This project started as a way to learn how to build an AI agent from scratch — backend, frontend, and deployment. The idea: a French-speaking nutrition assistant that calculates your caloric needs, generates personalized meal plans with real recipes, and tracks your daily macros.

It's a first version, built as part of Cole Medin's [AI Agent Mastery](https://dynamous.ai/) course. The app is functional and deployed — you can try it directly via the link above.

---

## What you can do

### Chat — Talk nutrition with the AI

The main tab. Ask your questions in French, the assistant responds with science-backed advice. It can calculate your needs (calories, protein, carbs, fat), generate a weekly meal plan, create a shopping list, or simply answer nutrition questions.

Responses include interactive visual components directly in the chat: nutrition summaries, macro gauges, recipe cards.

<p align="center">
  <img src="e2e-screenshots/01-after-login.png" width="70%" alt="Chat — home page" />
</p>
<p align="center">
  <img src="e2e-screenshots/10-mobile-chat.png" width="30%" alt="Chat — mobile" />
</p>

### Daily Tracking — Monitor your macros

The Tracking tab shows what you've eaten today vs. your goals. A circular gauge for calories, progress bars for protein/carbs/fat.

To add a food, just type "j'ai mangé..." (I ate...) — the assistant looks up macros from a database of 264,000 French products (OpenFoodFacts) and updates your totals.

<p align="center">
  <img src="e2e-screenshots/02-daily-tracking.png" width="70%" alt="Daily Tracking — desktop" />
</p>
<p align="center">
  <img src="e2e-screenshots/11-mobile-tracking.png" width="30%" alt="Daily Tracking — mobile" />
</p>

### Library — Plans, recipes and shopping lists

The Library tab gathers everything the assistant has generated for you:

- **Plans** — your weekly meal plans, with day-by-day details (recipes, ingredients, macros per meal)
- **Recipes** — your favorite recipes saved from the chat
- **Shopping** — shopping lists generated from your plans

<p align="center">
  <img src="e2e-screenshots/07-meal-plan-detail.png" width="70%" alt="Meal plan detail" />
</p>
<p align="center">
  <img src="e2e-screenshots/05-bibliotheque-recettes.png" width="70%" alt="Favorite recipes" />
</p>

---

## How it's built

### Architecture

```
Frontend (React 18 + TypeScript + Vite)
  │  3 tabs: Chat · Daily Tracking · Library
  │  Supabase Auth · Generative UI · NDJSON streaming
  │
  ↕  HTTPS / JWT
  │
Backend (FastAPI)
  │  NDJSON streaming · JWT auth · Rate limiting
  │
  ↕
  │
Pydantic AI Agent (6 tools, skill system)
  │
  ├── nutrition-calculating/    Needs calculation (Mifflin-St Jeor)
  ├── meal-planning/            Meal plans + MILP optimization
  ├── food-tracking/            Daily food logging
  ├── shopping-list/            Shopping lists
  ├── weekly-coaching/          Adaptive weekly feedback
  ├── knowledge-searching/      RAG + web search
  └── body-analyzing/           Photo analysis (GPT-4 Vision)
  │
  ↕
  │
Data
  ├── Supabase (PostgreSQL + pgvector) — 17 tables, RLS
  ├── OpenFoodFacts — 264K French products
  └── mem0 — cross-session memory
```

The agent contains no business logic. It loads a `SKILL.md` file to discover available scripts, then calls `run_skill_script()` which auto-injects shared clients. Adding a feature = adding a folder in `skills/`.

### Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | React 18, TypeScript 5, Vite 5, shadcn/ui, Tailwind CSS, Recharts, Zod |
| **Backend** | FastAPI, Pydantic AI, Python 3.11+ |
| **LLMs** | Claude Haiku 4.5 (agent) + GPT-4o-mini (vision, embeddings) |
| **Database** | Supabase (PostgreSQL + pgvector), RLS on all 17 tables |
| **Auth** | Supabase Auth (email/password + Google OAuth) |
| **Food data** | OpenFoodFacts (264K products, local search) |
| **Optimization** | SciPy MILP for recipe portion scaling |
| **Testing** | pytest (718 tests) + pydantic-evals (21 files) |
| **CI/CD** | GitHub Actions + Render |

### Some numbers

| | |
|---|---|
| 718 unit tests | 7 skill domains |
| 712 validated recipes | 264,495 OpenFoodFacts products |
| 7 Generative UI components | 17 tables (all with RLS) |

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- A Supabase project (free tier works)
- API keys: Anthropic, OpenAI (embeddings + vision), optionally Brave Search

### Install

```bash
git clone https://github.com/mzt-76/AI-nutrition.git
cd AI-nutrition

# Backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Frontend
cd frontend && npm install && cd ..
```

### Configure

```bash
cp .env.example .env
# Fill in your API keys and Supabase credentials

cp frontend/.env.example frontend/.env
# Fill in your Supabase URL and anon key
```

### Run

```bash
# Backend
uvicorn src.api:app --port 8001 --reload

# Frontend (separate terminal)
cd frontend && npm run dev
```

Frontend runs on `http://localhost:8080`, backend on `http://localhost:8001`.

### Tests

```bash
pytest tests/ -v
ruff format src/ tests/ && ruff check src/ tests/ && mypy src/
```

---

## Acknowledgments

Special thanks to **Cole Medin** for his investment in the [Dynamous AI](https://dynamous.ai/) community and the creation of his **AI Agent Mastery** course, without which this project wouldn't have come to life.

Built in collaboration with **Claude Code** (Anthropic) — from architecture design to debugging, including frontend design with the `frontend-design` skill.

Thanks to the open source projects this app relies on:
- [Pydantic AI](https://github.com/pydantic/pydantic-ai) — agent framework
- [OpenFoodFacts](https://world.openfoodfacts.org/) — open food database
- [shadcn/ui](https://ui.shadcn.com/) — UI components
- [Langfuse](https://langfuse.com/) — LLM observability
- Nutritional science: ISSN, Mifflin et al. (1990), Helms et al. (2014)

---

Created by **Meuz** — a personal project built to learn and share.
