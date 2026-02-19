# AI Nutrition Assistant - Development Guide

**Stack:** Python 3.11+ | Pydantic AI | React 18 | TypeScript 5 | Supabase
**Status:** Active Development

**⚠️ Read `.claude/reference/dependency-safety-rules.md` before modifying code.**

---

## 1. Core Principles & Rules

1. **Science-First**: Nutrition calculations use Mifflin-St Jeor for BMR. Cite sources in docstrings.
2. **Type Safety**: Full type hints in Python (args + return). No `any` in TypeScript. Strict mode.
3. **Safety Constraints** (hardcoded, never bypass):
   ```python
   MIN_CALORIES_WOMEN = 1200
   MIN_CALORIES_MEN = 1500
   ALLERGEN_ZERO_TOLERANCE = True
   ```
4. **Async by Default**: All I/O must be async with proper error handling.
5. **No docs unless asked**: Do not create documentation files unless explicitly requested.
6. **Never grow `src/agent.py`**: It has 6 fixed tools. New functionality → new skill scripts only.
7. **Skill scripts import from `src.nutrition.*`**: Never duplicate calculation logic.
8. **Test all calculation functions**: Happy path + error cases. Nutrition logic is critical.
9. **Run linters before committing**: `ruff format src/ tests/ && ruff check src/ tests/ && mypy src/`

---

## 2. Tech Stack

**Backend:** Pydantic AI, OpenAI API, Supabase (PostgreSQL + pgvector), mem0, httpx, Brave Search
**Frontend:** React 18, TypeScript 5, Vite 5, shadcn/ui, Tailwind, React Query, Zod
**Dev:** pytest + pytest-asyncio, ruff, mypy, ESLint

---

## 3. Architecture

**Structure:** `src/` (agent, tools, nutrition/, RAG_Pipeline/) | `skills/` | `evals/` | `tests/` | `sql/`
**Imports:** Always use `src.` prefix (e.g., `from src.agent import agent`)

**Key patterns:**
- Agent calls `load_skill(name)` → reads SKILL.md → calls `run_skill_script(skill, script, params)`
- `run_skill_script` injects all shared clients (supabase, anthropic, etc.) automatically
- Skill scripts: `async def execute(**kwargs) -> str` — take what they need via `kwargs.get()`
- Each skill dir: `SKILL.md` (metadata + script interface docs) + `scripts/` + `references/`
- Adding a new skill = only touch files inside `skills/<name>/`

**Skills:** `nutrition-calculating` | `meal-planning` | `weekly-coaching` | `knowledge-searching` | `body-analyzing` | `skill-creator`

**Run commands:** See `.claude/reference/dev-commands.md`

---

## 4. References

- **`coding-standards.md`** — naming, docstrings, logging, pytest patterns
- **`api-contracts.md`** — Python ↔ TypeScript type matching
- **`code-patterns.md`** — copy-paste Pydantic AI, Supabase RAG, React Hook examples
- **`dev-commands.md`** — setup, run, test, lint commands
- **`dependency-safety-rules.md`** — breaking change prevention
- **`archon-mcp-reference.md`** — task management (only if Archon MCP is active)
- **`status.md`** — current completed work & next tasks

---

## 5. Archon MCP

Before starting work, try `find_tasks()`. If successful → use Archon for task management (not TodoWrite). If error → proceed without it. See `archon-mcp-reference.md` for details.

---

**Version:** 3.2 | **Updated:** 2026-02-19
