# Current Status & Next Tasks

**Completed:**
- Core agent with 6 skill domains (nutrition, meal-planning, weekly-coaching, knowledge, body-analysis, skill-creator)
- Skill progressive disclosure system (SkillLoader)
- `run_skill_script` universal executor — skills are fully self-contained, no per-skill wrappers
- Weekplan refactoring — Recipe DB + day-by-day generation + LLM fallback
- Domain logic: calculations, adjustments, feedback extraction, validators, portion_scaler, recipe_db
- Model upgrade: `claude-sonnet-4-5-20250929` → `claude-sonnet-4-6` (generate_custom_recipe, seed_recipe_db)
- pydantic-ai API alignment: `OpenAIModel` → `OpenAIChatModel`, `result.output` confirmed correct in 1.39.0
- pytest warnings fixed: removed `asyncio_default_fixture_loop_scope` (invalid in pytest-asyncio 0.26)
- New test files: `test_generate_week_plan.py` (9 tests), `test_generate_custom_recipe.py` (6 tests)
- `test_generate_day_plan.py` extended: `TestFindCustomRequest` (3 tests) + custom-request integration test
- E2E test architecture: 3 `FunctionModel` unit tests + 22 `@pytest.mark.integration` real-LLM tests
- Bug fix: `goals: dict` → `dict[str, int] | None` — prevents LLM passing a list instead of a dict
- Bug fix: Supabase mock in E2E tests now returns JSON-serializable dicts (was MagicMock → TypeError)
- Seed recipe DB — `scripts/seed_recipes_manual.py` (120 recipes) + `seed_recipe_db.py` (LLM-powered). DB has 121 recipes.
- Pydantic-evals: **13 datasets, 50 cases** — all 17 skill scripts now covered (added fetch_stored_meal_plan, generate_shopping_list, generate_week_plan)
- Context optimization — progressive disclosure lean (prompt ~1400 tokens, metadata ~200 tokens); `skill-creator` SKILL.md bloated but non-blocking
- OpenFoodFacts migration **COMPLETE**: 275K products imported, columns renamed, 543 cached ingredient mappings (374 high confidence, 169 medium, 0 low)
- Test suite: **350 unit tests passing, 0 failures** (`pytest tests/ evals/ -m "not integration"`)
- Project shared with AI Agent Mastery community (Module 4 exercise) — repo public on GitHub
- **FastAPI backend API** (Module 5): `src/api.py` with streaming NDJSON endpoint, conversation management, rate limiting
- Multi-user support: `user_id` added to `AgentDeps`, profile tools query `user_profiles` (API) or `my_profile` (CLI)
- Multi-user DB tables applied with RLS: `user_profiles`, `conversations`, `messages`, `requests`
- New files: `src/db_utils.py`, `src/api.py`, `tests/test_db_utils.py`, `tests/test_api.py`
- API entry point: `python -m src api` or `uvicorn src.api:app --port 8001`
- Test suite: **375 tests passing** (358 existing + 17 new API/db_utils tests)
- API architecture docs: `docs/api-architecture-explained.md`

**Database State (verified 2026-02-24):**
- `recipes`: 121 rows (seeded)
- `ingredient_mapping`: 543 rows (openfoodfacts_* columns, auto-growing cache)
- `openfoodfacts_products`: 275,000 rows (French products with nutrition data)
- `user_profiles`: 1 row (dev user with nutrition data populated)
- `conversations`: active (FK to user_profiles)
- `messages`: active (FK to conversations)
- `requests`: active (rate limiting)

- **React prototype connected to FastAPI backend** (NDJSON streaming): replaced n8n webhook with `streamAgentResponse()` in `useChat.ts`, tokens stream progressively in browser
- Frontend files changed: `src/lib/api.ts` (new), `src/hooks/useChat.ts`, `src/types/chat.types.ts`, `src/utils/sessionManager.ts`, `.env.example`
- Bug fix: `run_skill_script` param renamed `params` → `parameters` with precise type `dict[str, str | int | float | bool | None] | None` — GPT-4o-mini was generating `parameters` instead of `params`, causing Pydantic validation error
- Quick E2E test via browser: nutrition calculation, meal plan generation (1-day) — streaming works, session reuse works
- **Observed issue**: meal planner repeats the same recipes across different days (e.g. Monday and Tuesday identical). Need batch cooking vs variety preference.

**Current Phase:**
- **Module 5** of AI Agent Mastery course — FastAPI backend API + React frontend integration done, auth not yet wired

**Next Tasks (Priority Order):**
1. **Batch cooking / recipe variety** — agent should ask user if they want batch cooking (same meals for convenience) or varied recipes each day; currently repeats same recipes by default
2. **Profile target caching** — when `user_profiles` has empty BMR/TDEE/target columns, auto-calculate on first fetch, update the row, and reuse cached values on subsequent requests
3. **User authentication** — wire `verify_token()` with Supabase Auth JWT, add `Depends(verify_token)` to endpoints, replace hardcoded `VITE_USER_ID`
4. **Full multi-user DB migration** — add `user_id` FK + RLS to `meal_plans`, `weekly_feedback`, `user_learning_profile` tables
5. **Load conversation history from DB** — add `GET /api/conversations/{session_id}/messages` endpoint, replace localStorage persistence
