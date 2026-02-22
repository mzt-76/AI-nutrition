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

**Database State (verified 2026-02-22):**
- `recipes`: 121 rows (seeded)
- `ingredient_mapping`: 543 rows (openfoodfacts_* columns, auto-growing cache)
- `openfoodfacts_products`: 275,000 rows (French products with nutrition data)

**Next Tasks (Priority Order):**
1. **Frontend integration** — connect Loveable React prototype to Python backend API
2. **End-to-end validation** — generate a real 7-day meal plan via the agent to verify full pipeline
