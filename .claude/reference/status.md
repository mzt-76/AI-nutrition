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
- Bug fix: `run_skill_script` param renamed `params` → `parameters` with precise type
- **Production frontend** (Module 5): migrated from course template to `frontend/` — Supabase Auth (email + Google OAuth), conversation sidebar, streaming NDJSON, markdown rendering, admin dashboard
- Frontend: green glass-morphism design, French localization, 4 suggested question cards on empty state
- Frontend tech: React 18, TypeScript 5, Vite 5, shadcn/ui, Tailwind, react-markdown, Supabase JS client
- Frontend types: `database.types.ts` regenerated from actual schema (`user_profiles`, `conversations` with `session_id` PK, `messages` with auto-increment `id`)
- Frontend `.env`: `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `VITE_AGENT_ENDPOINT`, `VITE_ENABLE_STREAMING`

**Database State (verified 2026-02-25):**
- `recipes`: 123 rows (seeded)
- `ingredient_mapping`: 546 rows (auto-growing cache)
- `openfoodfacts_products`: 275,000 rows (French products with nutrition data)
- `user_profiles`: 1 row (dev user with nutrition data populated, RLS enabled)
- `conversations`: 8 rows (RLS enabled, FK to user_profiles)
- `messages`: 24 rows (RLS enabled, FK to conversations)
- `requests`: 8 rows (RLS enabled)
- `meal_plans`: 52 rows (**no user_id column, no RLS**)
- `weekly_feedback`: 10 rows (**no user_id column, no RLS**)
- `user_learning_profile`: 0 rows (**no user_id column, no RLS**)
- `my_profile`: 0 rows (legacy, to be dropped)

**Current Phase:**
- **Module 5** of AI Agent Mastery course — FastAPI backend + React frontend DONE, auth partially wired (frontend has Supabase Auth, backend JWT verification not yet implemented)

**Next Tasks (Priority Order):**
1. **Multi-user DB migration** — see `.agents/plans/multi-user-database-migration.md` (19 tasks):
   - Wire JWT verification in `src/api.py` (verify token via Supabase Auth API, reject user_id mismatch)
   - Add `user_id` FK + RLS to `meal_plans`, `weekly_feedback`, `user_learning_profile`
   - RLS on global reference tables (`recipes`, `ingredient_mapping`, etc.)
   - Fix function search_path warnings
   - Update 2 skill scripts missing `user_id` filter (`fetch_stored_meal_plan`, `generate_shopping_list`)
   - Fix CLI/Streamlit `user_id` passthrough
   - Drop `my_profile`
2. **Batch cooking / recipe variety** — agent should ask user preference; currently repeats same recipes
3. **Profile target caching** — auto-calculate BMR/TDEE on first fetch, cache in `user_profiles`
