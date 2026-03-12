# AI Nutrition Assistant - Development Guide

**Stack:** Python 3.11+ | Pydantic AI | React 18 | TypeScript 5 | Supabase
**Status:** Production (Render)

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
7b. **Tunable constants in `src/nutrition/constants.py`**: All pipeline-tunable parameters (scoring weights, macro tolerances, calorie adjustments, MILP bounds, LLM params) are centralized in one file. Import from there — never hardcode magic numbers inline. See the file for the full list (27 constants, organized by domain).
8. **Test all calculation functions**: Happy path + error cases. Nutrition logic is critical.
9. **Run linters before committing**: `ruff format src/ tests/ && ruff check src/ tests/ && mypy src/`
10. **`scripts/` are LLM-free**: Scripts in `scripts/` must never import `anthropic`, `openai`, or any LLM client. They may only use `src.nutrition.*`, `src.clients.get_supabase_client()`, and stdlib. If a task requires an LLM, it belongs in `skills/` as a skill script instead. This is enforced by `tests/test_scripts_no_llm.py`.
11. **`tests/` vs `evals/` — one rule**: Ask "is a real LLM making a decision here?" — Yes → `evals/`. No → `tests/`.
    - `tests/`: deterministic logic only — calculations, validators, formatters, DB operations, agent structure with `FunctionModel`. Always passes. Runs on every commit.
    - `evals/`: real LLM behaviour — does the agent call the right skill? extract the right params? respond in the expected range? Scored not asserted. Run on demand before releases.
    - **Always define a `TEST_USER_PROFILE` constant** at the top of every eval file with ALL required fields (age, gender, height_cm, weight_kg, activity_level, goals). Never rely on implicit profile data mid-file.
    - **Evals that test skills needing DB access** (meal-planning, weekly-coaching) must use `create_agent_deps(user_id=...)` with a real user ID from Supabase. Without `user_id`, the skill fails silently and the agent falls back to improvising.
12. **`src/prompt.py` stays generic**: Skill-specific behavior (presentation formats, default params, routing exceptions) belongs in the skill's `SKILL.md` or `references/`, NOT in the system prompt. The system prompt only has rules that apply to ALL skills.
13. **CI-safe code**: Tests must pass in CI where only fake env vars exist. See `.claude/reference/ci-best-practices.md` for the full checklist. Key rules:
    - **New env var?** → add a fake value in `.github/workflows/python-unit-tests.yml` env section.
    - **Test needs real DB/API?** → mark it `@requires_real_db` (defined in `tests/test_openfoodfacts_client.py`). Never let a test hit a real service in CI.
    - **Avoid top-level code that crashes on missing env vars.** Prefer lazy init or guard with `if os.getenv(...)`.
14. **Frontend: design then test visually**: For any frontend task: (1) use `/frontend-design` skill to design the UI, (2) implement it, (3) test with `agent-browser` on both desktop (`1280x720`) and mobile (`390x844`) viewports. Always screenshot and verify before marking complete. See `.claude/reference/frontend-workflow.md` for login credentials, commands, and the full checklist.

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
- **Generative UI**: Agent emits `<!--UI:Component:{json}-->` markers in text → `src/ui_components.py` extracts them → API streams as `ui_component` NDJSON chunks → frontend renders React components via `ComponentRenderer`. Zod validates all props before rendering. 7 components: NutritionSummaryCard, MacroGauges, MealCard, DayPlanCard, WeightTrendIndicator, AdjustmentCard, QuickReplyChips.
- **Meal plan visual page**: `/plans/:id` route fetches from `GET /api/meal-plans/{plan_id}` and renders with DayPlanCard/MacroGauges
- **Do not use lovable-tagger** — it was removed from the project

**Meal-planning pipeline:** select recipes (v2b sliding budget) → MILP per-ingredient optimize (v2f `portion_optimizer_v2.py`) → validate → repair. Tunable constants in `src/nutrition/constants.py`.
**Skills:** `nutrition-calculating` | `meal-planning` | `food-tracking` | `shopping-list` | `weekly-coaching` | `knowledge-searching` | `body-analyzing`

**Run commands:** See `.claude/reference/dev-commands.md`
                      `.claude/reference/frontend-workflow.md`

---

## 4. References

- **`coding-standards.md`** — naming, docstrings, logging, pytest patterns
- **`api-contracts.md`** — Python ↔ TypeScript type matching
- **`code-patterns.md`** — copy-paste Pydantic AI, Supabase RAG, React Hook examples
- **`dev-commands.md`** — setup, run, test, lint commands
- **`dependency-safety-rules.md`** — breaking change prevention
- **`meal-planning-workflow.md`** — full technical reference for the meal-planning skill (pipeline, data contracts, how to modify)
- **`archon-mcp-reference.md`** — task management (only if Archon MCP is active)
- **`frontend-workflow.md`** — frontend design + visual testing workflow with agent-browser (gitignored, contains test credentials)
- **`ci-best-practices.md`** — CI env vars, test separation (unit vs integration), checklist before push
- **`status.md`** — current completed work & next tasks

---

## 5. Archon MCP

Before starting work, try `find_tasks()`. If successful → use Archon for task management (not TodoWrite). If error → proceed without it. See `archon-mcp-reference.md` for details.

---

**Deployment:**
- Frontend: `https://ai-nutrition-frontend-78p7.onrender.com` (static CDN)
- Backend: `https://ai-nutrition-backend-16c2.onrender.com` (Docker)
- DB: Supabase prod `bxmihxyishfvmvswxfby`
- CI/CD: GitHub Actions → auto-deploy on Render
- Config: `render.yaml` (Blueprint), `.env.prod` (gitignored)

**Version:** 3.7 | **Updated:** 2026-03-12
