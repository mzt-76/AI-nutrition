# AI Nutrition Assistant - Development Guide

**Stack:** Python 3.11+ | Pydantic AI | React 18 | TypeScript 5 | Supabase
**Status:** Production (Render)

**⚠️ Read `.claude/reference/dependency-safety-rules.md` before modifying code.**

---

## 1. Universal Rules

1. **Type Safety**: Full type hints in Python (args + return). No `any` in TypeScript. Strict mode.
2. **Async by Default**: All I/O must be async with proper error handling.
3. **No docs unless asked**: Do not create documentation files unless explicitly requested.
4. **Imports**: Always use `src.` prefix (e.g., `from src.agent import agent`)
5. **Run linters before committing**: `ruff format src/ tests/ && ruff check src/ tests/ && mypy src/`

> Domain-specific rules auto-load from `.claude/rules/` based on which files you're editing.
> See: `nutrition.md`, `database.md`, `skills.md`, `frontend.md`, `testing.md`, `api.md`, `scripts.md`

---

## 2. Tech Stack

**Backend:** Pydantic AI, OpenAI API, Supabase (PostgreSQL + pgvector), mem0, httpx, Brave Search
**Frontend:** React 18, TypeScript 5, Vite 5, shadcn/ui, Tailwind, React Query, Zod
**Dev:** pytest + pytest-asyncio, ruff, mypy, ESLint

---

## 3. Architecture

**Structure:** `src/` (agent, tools, api, db_utils, nutrition/, RAG_Pipeline/) | `skills/` | `frontend/` | `evals/` | `tests/` | `sql/`

**Key patterns:**
- Agent calls `load_skill(name)` → reads SKILL.md → calls `run_skill_script(skill, script, params)`
- `run_skill_script` injects all shared clients (supabase, anthropic, etc.) + `user_id` automatically
- Skill scripts: `async def execute(**kwargs) -> str`
- Each skill dir: `SKILL.md` + `scripts/` + `references/`
- Adding a new skill = only touch files inside `skills/<name>/`
- **Multi-user**: `AgentDeps.user_id` set → profile tools query `user_profiles`; `None` → `my_profile` (CLI fallback)

**Interfaces:** CLI (`src/cli.py`) | Streamlit (`src/streamlit_ui.py`) | **FastAPI** (`src/api.py`)
**Skills:** `nutrition-calculating` | `meal-planning` | `food-tracking` | `shopping-list` | `weekly-coaching` | `knowledge-searching` | `body-analyzing`

**Run commands:** See `.claude/reference/dev-commands.md`

---

## 4. References (`.claude/reference/`)

- **`coding-standards.md`** — naming, docstrings, logging, pytest patterns
- **`api-contracts.md`** — Python ↔ TypeScript type matching
- **`code-patterns.md`** — copy-paste Pydantic AI, Supabase RAG, React Hook examples
- **`dev-commands.md`** — setup, run, test, lint commands
- **`dependency-safety-rules.md`** — breaking change prevention
- **`meal-planning-workflow.md`** — full technical reference for the meal-planning skill
- **`frontend-workflow.md`** — frontend design + visual testing workflow (gitignored)
- **`ci-best-practices.md`** — CI env vars, test separation, checklist before push
- **`status.md`** — current completed work & next tasks

---

## 5. Archon MCP

Before starting work, try `find_tasks()`. If successful → use Archon for task management (not TodoWrite). If error → proceed without it. See `archon-mcp-reference.md` for details.

---

## 6. Deployment

- Frontend: `https://ai-nutrition-frontend-78p7.onrender.com` (static CDN)
- Backend: `https://ai-nutrition-backend-16c2.onrender.com` (Docker)
- DB: Supabase prod `bxmihxyishfvmvswxfby`
- CI/CD: GitHub Actions → auto-deploy on Render
- Bug workflows: 3 GitHub Actions — see `docs/bug-investigation-workflow.md`
- Config: `render.yaml` (Blueprint), `.env.prod` (gitignored)

**Version:** 3.8 | **Updated:** 2026-03-25
