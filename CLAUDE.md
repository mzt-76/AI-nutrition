# AI Nutrition Assistant - Development Guide

**Stack:** Python 3.11+ | Pydantic AI | React 18 | TypeScript 5 | Supabase
**Status:** Active Development

**⚠️ Read `.claude/reference/dependency-safety-rules.md` before modifying code.**

---

## 1. Core Principles & Rules

1. **Science-First**: Nutrition calculations use Mifflin-St Jeor for BMR. Fat macros = 20-25% of **total** calories (goal-dependent). Cite sources in docstrings.
2. **Type Safety**: Full type hints in Python (args + return). No `any` in TypeScript. Strict mode. Use precise types for agent tool parameters — e.g. `dict[str, int] | None` not bare `dict` (bare `dict` generates a weak JSON schema; the LLM may pass a list instead of a dict).
3. **Safety Constraints** (hardcoded, never bypass):
   ```python
   MIN_CALORIES_WOMEN = 1200
   MIN_CALORIES_MEN = 1500
   ALLERGEN_ZERO_TOLERANCE = True
   DISLIKED_FOODS_FILTERED = True  # recipe_db excludes disliked foods
   ```
4. **Async by Default**: All I/O must be async with proper error handling.
5. **No docs unless asked**: Do not create documentation files unless explicitly requested.
6. **Never grow `src/agent.py`**: It has 6 fixed tools. New functionality → new skill scripts only.
7. **Skill scripts are orchestrators, not reimplementers**: Calculation/domain logic lives in `src/nutrition/` — import it, never rewrite it. Other imports (`src.tools`, `src.clients`, stdlib, third-party) are fine. The rule is about duplication, not import restriction.
8. **Test all calculation functions**: Happy path + error cases. Nutrition logic is critical.
9. **Run linters before committing**: `ruff format src/ tests/ && ruff check src/ tests/ && mypy src/`
10. **`scripts/` are LLM-free**: Scripts in `scripts/` must never import `anthropic`, `openai`, or any LLM client. They may only use `src.nutrition.*`, `src.clients.get_supabase_client()`, and stdlib. If a task requires an LLM, it belongs in `skills/` as a skill script instead. This is enforced by `tests/test_scripts_no_llm.py`.
11. **`tests/` vs `evals/` — one rule**: Ask "is a real LLM making a decision here?" — Yes → `evals/`. No → `tests/`.
    - `tests/`: deterministic logic only — calculations, validators, formatters, DB operations, agent structure with `FunctionModel`. Always passes. Runs on every commit.
    - `evals/`: real LLM behaviour — does the agent call the right skill? extract the right params? respond in the expected range? Scored not asserted. Run on demand before releases.
    - **Always define a `TEST_USER_PROFILE` constant** at the top of every eval file with ALL required fields (age, gender, height_cm, weight_kg, activity_level, goals). Never rely on implicit profile data mid-file.

---

## 2. Tech Stack

**Backend:** Pydantic AI, OpenAI API, Supabase (PostgreSQL + pgvector), mem0, httpx, Brave Search
**Frontend:** React 18, TypeScript 5, Vite 5, shadcn/ui, Tailwind, React Query, Zod
**Dev:** pytest + pytest-asyncio, ruff, mypy, ESLint

---

## 3. Architecture

**Structure:** `src/` (agent, tools, api, db_utils, nutrition/, RAG_Pipeline/) | `skills/` | `frontend/` | `evals/` | `tests/` | `sql/`
**Imports:** Always use `src.` prefix (e.g., `from src.agent import agent`)

**Key patterns:**
- Agent calls `load_skill(name)` → reads SKILL.md → calls `run_skill_script(skill, script, params)`
- `run_skill_script` injects all shared clients (supabase, anthropic, etc.) + `user_id` automatically
- Skill scripts: `async def execute(**kwargs) -> str` — take what they need via `kwargs.get()`
- Each skill dir: `SKILL.md` (metadata + script interface docs) + `scripts/` + `references/`
- Adding a new skill = only touch files inside `skills/<name>/`
- **Multi-user**: `AgentDeps.user_id` set → profile tools query `user_profiles`; `None` → `my_profile` (CLI fallback)

**Interfaces:** CLI (`src/cli.py`) | Streamlit (`src/streamlit_ui.py`) | **FastAPI** (`src/api.py`)

**Frontend** (`frontend/`): React 18 + TypeScript 5 + Vite 5 + shadcn/ui + Tailwind
- Supabase Auth (email/password + Google OAuth) → JWT session → `user.id` sent to backend
- Streaming: `POST /api/agent` with NDJSON response, parsed in `src/lib/api.ts`
- Conversations: loaded from Supabase `conversations`/`messages` tables via JS client
- Design: green glass-morphism dark theme, French localization
- Types: `src/types/database.types.ts` must match actual Supabase schema
- Run: `cd frontend && npm run dev` (port 8080), needs `frontend/.env` with Supabase keys
- **Do not use lovable-tagger** — it was removed from the project

**Skills:** `nutrition-calculating` | `meal-planning` | `weekly-coaching` | `knowledge-searching` | `body-analyzing` | `skill-creator`

**Run commands:** See `.claude/reference/dev-commands.md`

---

## 4. References

- **`coding-standards.md`** — naming, docstrings, logging, pytest patterns
- **`api-contracts.md`** — Python ↔ TypeScript type matching
- **`code-patterns.md`** — copy-paste Pydantic AI, Supabase RAG, React Hook examples
- **`dev-commands.md`** — setup, run, test, lint commands
- **`dependency-safety-rules.md`** — breaking change prevention
- **`meal-planning-workflow.md`** — full technical reference for the meal-planning skill (pipeline, data contracts, how to modify)
- **`archon-mcp-reference.md`** — task management (only if Archon MCP is active)
- **`status.md`** — current completed work & next tasks

---

## 5. Archon MCP

Before starting work, try `find_tasks()`. If successful → use Archon for task management (not TodoWrite). If error → proceed without it. See `archon-mcp-reference.md` for details.

---

**Version:** 3.5 | **Updated:** 2026-02-25
