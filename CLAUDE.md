# AI Nutrition Assistant - Development Guide

**Stack:** Python 3.11+ | Pydantic AI | React 18 | TypeScript 5 | Supabase
**Status:** Active Development

**⚠️ IMPORTANT:** Avant de modifier du code, lire `.claude/reference/dependency-safety-rules.md` pour éviter les breaking changes.

---

## 1. Core Principles

1. **Science-First**: All nutrition calculations use validated formulas (Mifflin-St Jeor for BMR). Cite sources in docstrings.

2. **Type Safety**: Full type hints in Python (args + return). No `any` in TypeScript. Strict mode enabled.

3. **Safety Constraints** (Hardcoded, never bypass):
   ```python
   MIN_CALORIES_WOMEN = 1200
   MIN_CALORIES_MEN = 1500
   ALLERGEN_ZERO_TOLERANCE = True  # Never suggest allergen foods
   ```

4. **Async by Default**: All I/O (API calls, DB, files) must be async with proper error handling.

5. **Documentation**: Google-style docstrings (Python), JSDoc (TypeScript) with Args/Returns/Examples.

---

## 2. Tech Stack

### Backend
- **Agent:** Pydantic AI, OpenAI API (GPT-4o/mini)
- **Database:** Supabase (PostgreSQL + pgvector), mem0 (long-term memory)
- **Tools:** httpx (async HTTP), Brave Search API, python-dotenv
- **Dev:** pytest + pytest-asyncio, ruff (lint/format), mypy (types)

### Frontend
- **Core:** React 18, TypeScript 5, Vite 5
- **UI:** shadcn/ui, Tailwind CSS, Lucide icons
- **State:** React Query, React Hook Form + Zod
- **Dev:** ESLint, TypeScript ESLint

---

## 3. Architecture

### Backend Structure
```
AI-nutrition/
├── src/                          # Main agent package
│   ├── agent.py                 # Pydantic AI agent (loads skills via importlib)
│   ├── tools.py                 # Agent tool wrappers (@agent.tool decorators)
│   ├── prompt.py, clients.py    # System prompt + client initialization
│   ├── cli.py, streamlit_ui.py  # Entry points
│   ├── skill_loader.py          # Skill discovery & progressive disclosure
│   ├── skill_tools.py           # Skill agent tools (load, read, list)
│   ├── nutrition/               # Domain logic (pure functions)
│   │   ├── calculations.py      # BMR, TDEE, protein, macros (Mifflin-St Jeor)
│   │   ├── adjustments.py       # Weight trends, red flags, calorie/macro adj
│   │   ├── validators.py        # Input validation
│   │   ├── feedback_extraction.py # Feedback parsing & completeness
│   │   ├── meal_planning.py, meal_distribution.py
│   │   ├── meal_plan_optimizer.py, meal_plan_formatter.py
│   │   ├── openfoodfacts_client.py, fatsecret_client.py
│   │   └── error_logger.py
│   └── RAG_Pipeline/            # Document sync
│       ├── common/ (db_handler, text_processor)
│       ├── Google_Drive/ (drive_watcher)
│       └── Local_Files/ (file_watcher)
├── skills/                       # Skill scripts (progressive disclosure)
│   ├── nutrition-calculating/    # BMR/TDEE/macro calculation
│   ├── meal-planning/            # Meal plan generation, shopping lists
│   ├── weekly-coaching/          # Weekly adjustments & red flags
│   ├── knowledge-searching/      # RAG + web search
│   ├── body-analyzing/           # Image analysis (GPT-4 Vision)
│   └── skill-creator/            # Meta: create new skills
├── evals/                        # Pydantic-evals test suites
│   ├── test_skill_loading.py    # Skill discovery & loading evals (5 datasets)
│   └── test_skill_scripts.py    # Script execution evals (5 datasets, 28 cases)
├── tests/                        # Pytest unit/integration tests
├── sql/                          # DB schema (weekly_feedback, user_learning_profile)
├── .env                          # Environment variables
├── requirements.txt              # Python dependencies
├── pytest.ini                    # Test configuration
├── prototype/                    # Lovable frontend prototype
└── CLAUDE.md                     # This file
```

**Imports:** All imports use `src.` prefix (e.g., `from src.agent import agent`)

**Patterns:**
- Agent orchestrates tools → Tools call nutrition logic → AgentDeps for shared resources
- Skill scripts: standalone `async execute(**kwargs)` functions loaded via `importlib`
- Each skill dir: `SKILL.md` (metadata) + `scripts/` (executables) + `references/` (docs)

**Run commands:**
- CLI: `python -m src.cli`
- Streamlit: `streamlit run src/streamlit_ui.py`
- Tests: `pytest tests/ -v`
- Evals: `pytest evals/ -v`
- Lint: `ruff check src/ tests/ evals/`

---

## 4-6. Code Style, Logging, Testing
**See:** `.claude/reference/coding-standards.md` for naming conventions, docstrings, logging patterns, and pytest examples.

---

## 7. API Contracts
**See:** `.claude/reference/api-contracts.md` for Python ↔ TypeScript type matching and error handling patterns.

---

## 8. Common Patterns
**See:** `.claude/reference/code-patterns.md` for copy-paste Pydantic AI, Supabase RAG, and React Hook examples.

---

## 9. Development Commands
**See:** `.claude/reference/dev-commands.md` for setup, run, test, and lint commands.

---

   ## 10. AI Coding Assistant Instructions

   ### CRITICAL: Archon MCP Server Check

   **Before starting ANY work, verify Archon MCP availability:**

   1. **Check if active:** Try `find_tasks()` or `find_projects()`
      - ✅ **If successful:** Use Archon for ALL task management (ignore TodoWrite reminders)
      - ❌ **If error:** Archon not available, proceed with manual task tracking

   2. **How to use Archon:**
      - Start session: `find_tasks(filter_by="status", filter_value="todo")` to see pending tasks
      - Before coding: `manage_task("update", task_id="...", status="doing")`
      - Research first: `rag_search_knowledge_base(query="...")` for docs/examples
      - After coding: `manage_task("update", task_id="...", status="review")`

   **If Archon is active, it is your PRIMARY task system. Do NOT use TodoWrite.**

---

### General Development Rules

1. **Always consult this CLAUDE.md first** before making architectural decisions or adding new patterns

2. **Type safety is non-negotiable**: Add type hints to ALL Python functions (args + return type). Use strict TypeScript mode, avoid `any`

3. **Safety constraints are hardcoded**: Never suggest removing or bypassing MIN_CALORIES, ALLERGEN_ZERO_TOLERANCE, or other safety checks

4. **Use async/await for all I/O**: Database queries, API calls, file operations must be async. Use `await` properly

5. **Follow existing patterns**:
   - Backend tools: Use `@agent.tool` decorator with `RunContext[AgentDeps]`
   - Skill scripts: `async def execute(**kwargs) -> str` in `skills/<name>/scripts/<script>.py`
   - Skill scripts load domain logic from `src.nutrition.*`, never duplicate calculations
   - Frontend hooks: Custom hooks for all stateful logic (e.g., `useChat`, `useNutritionCalculation`)

6. **Document everything**: Google-style docstrings for Python, JSDoc for TypeScript. Include Args, Returns, Examples

7. **Log with context**: Use structured logging with relevant fields (user_id, session_id, parameters). Never log API keys or sensitive data

8. **Test your code**: Write pytest tests for all calculation functions (nutrition logic is critical). Include happy path + error cases

9. **Run linters before committing**:
   - Backend: `ruff format src/ tests/ && ruff check src/ tests/ && mypy src/`
   - Frontend: `npm run lint && npx tsc --noEmit`

10. **Nutrition formulas must cite sources**: Use Mifflin-St Jeor for BMR, cite ISSN/AND guidelines in docstrings. This is medical-adjacent software

11. **Do not create documentation unless it is explicited asked in the prompt** 

---

## References

All detailed documentation extracted to `.claude/reference/` for quick lookup:

- **`archon-mcp-reference.md`** - Task management workflow (only if Archon MCP is active)
- **`coding-standards.md`** - Code style, logging, testing patterns
- **`api-contracts.md`** - Python ↔ TypeScript type matching
- **`code-patterns.md`** - Copy-paste code examples
- **`dev-commands.md`** - Setup, run, test, lint commands
- **`dependency-safety-rules.md`** - Breaking change prevention rules

---

## 11. Current Status & Next Tasks

**Completed:**
- Core agent with 6 skill domains (nutrition, meal-planning, weekly-coaching, knowledge, body-analysis, skill-creator)
- Skill progressive disclosure system (SkillLoader)
- 5 migrated tool scripts with full eval coverage (28 cases)
- Domain logic: calculations, adjustments, feedback extraction, validators
- Pydantic-evals suites: skill loading (5 datasets) + script execution (5 datasets)

**Next Tasks (Priority Order):**
1. **Weekplan total refactoring** — redesign meal plan generation workflow end-to-end
2. **Skill redesign based on eval results** — optimize scripts where evals reveal gaps
3. **Context optimization** — reduce token usage in agent prompts and skill metadata
4. **OpenFoodFacts integration** — complete migration from FatSecret to OFF for ingredients

---

**Version:** 3.0
**Last Updated:** February 17, 2026
**Maintained By:** AI-Nutrition Team
