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
- Seed recipe DB — `scripts/seed_recipes_manual.py` (120 recipes) + `seed_recipe_db.py` (LLM-powered). DB has 123 recipes.
- Pydantic-evals: **13 datasets, 50 cases** — all 17 skill scripts now covered (added fetch_stored_meal_plan, generate_shopping_list, generate_week_plan)
- Context optimization — progressive disclosure lean (prompt ~1400 tokens, metadata ~200 tokens); `skill-creator` SKILL.md bloated but non-blocking
- OpenFoodFacts migration **COMPLETE**: 275K products imported, columns renamed, 543 cached ingredient mappings (374 high confidence, 169 medium, 0 low)
- Test suite: **366 unit tests passing, 0 failures** (`pytest tests/ evals/ -m "not integration"`)
- Project shared with AI Agent Mastery community (Module 4 exercise) — repo public on GitHub
- **FastAPI backend API** (Module 5): `src/api.py` with streaming NDJSON endpoint, conversation management, rate limiting
- **Production frontend** (Module 5): React 18 + TypeScript 5 + Vite 5, Supabase Auth (email + Google OAuth), green glass-morphism design, French localization
- Frontend: conversation sidebar, streaming NDJSON, markdown rendering, admin dashboard, 4 suggested question cards
- **Multi-user migration COMPLETE** (2026-02-25):
  - JWT verification in `src/api.py` — verifies token via Supabase Auth API, rejects user_id mismatch (403)
  - `user_id` FK column + backfill on `meal_plans` (52 rows), `weekly_feedback` (5 rows), `user_learning_profile` (0 rows)
  - **RLS enabled on ALL 13 public tables** — 0 RLS-disabled errors
  - Function search_path fixed on all 7 functions — 0 security warnings
  - Skill scripts updated: `fetch_stored_meal_plan`, `generate_shopping_list`, `generate_week_plan`, `calculate_weekly_adjustments` all filter/insert with `user_id`
  - CLI passes `NUTRITION_USER_ID` env var (default: `"cli_user"`), Streamlit passes `st.session_state.user_id`
  - `my_profile` table dropped, dual-mode fallback removed from `src/tools.py` and skill scripts
  - Tests updated: API tests cover JWT auth (403 mismatch, no-token backward compat), e2e mock chains updated
  - SQL migration files saved: `sql/5_*` through `sql/9_*`

**Database State (verified 2026-02-25, post multi-user testing):**
- `recipes`: 123 rows (seeded, RLS enabled)
- `ingredient_mapping`: 546 rows (auto-growing cache, RLS enabled)
- `openfoodfacts_products`: 275,000 rows (French products, RLS enabled)
- `user_profiles`: 2 rows (2 auth users, RLS enabled)
- `conversations`: 15 rows (RLS enabled)
- `messages`: 51 rows (RLS enabled)
- `requests`: 23 rows (RLS enabled)
- `meal_plans`: 53 rows (user_id FK, RLS enabled)
- `weekly_feedback`: 11 rows (user_id FK, RLS enabled)
- `user_learning_profile`: 1 row (user_id UNIQUE FK, RLS enabled)
- `documents`, `document_metadata`, `document_rows`: 0 rows (RLS enabled, read-only for authenticated)
- `my_profile`: **DROPPED**
- **Multi-user isolation verified**: 2 users tested, no cross-contamination

**Current Phase:**
- **Module 5** of AI Agent Mastery course — FastAPI backend + React frontend + multi-user migration COMPLETE

**Bug Fixes Applied (2026-02-25):**
- `diet_type` None filter bug — `generate_day_plan.py` line 218: `.get("diet_type", "omnivore")` → `.get("diet_type") or "omnivore"` (None key exists but value is None, so `.get()` returned None instead of default)
- `useAuth.tsx` TypeScript warnings — added `profile &&` null guard, `event` → `_event` unused param

**Improvements Applied (2026-02-27):**
- **Batch cooking / pre-planification questions** — DONE: skill description now includes all pre-generation questions (batch cooking, breakfast variety, days, meal structure) visible in Level 1 metadata. Anti-friction rule in system prompt prevents double-questioning.
- **mem0 memory cleanup** — purged 58 stale/duplicate/contradictory memories (old biometrics, session commands, stale dates). 29 clean long-term preferences remain.
- **mem0 custom_fact_extraction_prompt** — configured to only store personal preferences (food, routine, cooking habits), never commands/requests/biometrics already in profile. Prevents memory pollution.
- **System prompt default enforcement** — "Plan de repas défaut = 1 SEUL JOUR, JAMAIS 7" in anti-friction rules to override LLM bias.

**Next Tasks (Priority Order):**
1. ~~**Batch cooking / recipe variety**~~ — **DONE** (2026-02-27): agent now asks batch cooking preference in pre-planification questions
2. **Profile target caching** — auto-calculate BMR/TDEE on first fetch, cache in `user_profiles` (agent calculates but doesn't call `update_my_profile` to persist `target_calories`, `target_protein_g`, `target_carbs_g`, `target_fat_g`, `bmr`, `tdee`)
3. ~~**Weekly feedback baseline vs check-in**~~ — **DONE** (2026-02-27): `set_baseline.py` script records week_number=0, body tracking columns added, history queries exclude baseline via `.gt("week_number", 0)`
4. ~~**Streamlit auth**~~ — **OBSOLETE**: React frontend with Supabase Auth is now the production UI; Streamlit is legacy MVP dev tool
