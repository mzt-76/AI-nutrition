# AI Nutrition Assistant - Development Guide

**Stack:** Python 3.11+ | Pydantic AI | React 18 | TypeScript 5 | Supabase
**Status:** Module 4 - Python Backend Development

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
4_Pydantic_AI_Agent/
├── agent.py, tools.py, prompt.py, clients.py    # Core agent
├── nutrition/                                    # Domain logic
│   ├── calculations.py, adjustments.py, validators.py
├── RAG_Pipeline/                                 # Document sync
│   ├── common/ (db_handler, text_processor)
│   ├── Google_Drive/ (drive_watcher)
│   └── Local_Files/ (file_watcher)
├── tests/                                        # Test suite
└── sql/                                          # DB schema
```

**Patterns:** Agent orchestrates tools → Tools call nutrition logic → AgentDeps for shared resources (Supabase, HTTP client)

### Frontend Structure
```
src/
├── components/chat/      # ChatContainer, ChatInput, Message
├── hooks/                # useChat (API logic)
├── pages/                # Index (main page)
├── types/                # TypeScript interfaces
└── utils/                # sessionManager
```

**Patterns:** Feature folders → Custom hooks for logic → Small components → Type-safe interfaces

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
   - Frontend hooks: Custom hooks for all stateful logic (e.g., `useChat`, `useNutritionCalculation`)

6. **Document everything**: Google-style docstrings for Python, JSDoc for TypeScript. Include Args, Returns, Examples

7. **Log with context**: Use structured logging with relevant fields (user_id, session_id, parameters). Never log API keys or sensitive data

8. **Test your code**: Write pytest tests for all calculation functions (nutrition logic is critical). Include happy path + error cases

9. **Run linters before committing**:
   - Backend: `ruff format . && ruff check . && mypy .`
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

---

**Version:** 1.0
**Last Updated:** December 14, 2024
**Maintained By:** AI-Nutrition Team
