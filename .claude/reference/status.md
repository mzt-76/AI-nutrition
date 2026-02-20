# Current Status & Next Tasks

**Completed:**
- Core agent with 6 skill domains (nutrition, meal-planning, weekly-coaching, knowledge, body-analysis, skill-creator)
- Skill progressive disclosure system (SkillLoader)
- `run_skill_script` universal executor — skills are fully self-contained, no per-skill wrappers
- Weekplan refactoring — Recipe DB + day-by-day generation + LLM fallback
- Domain logic: calculations, adjustments, feedback extraction, validators, portion_scaler, recipe_db
- Pydantic-evals suites: skill loading (5 datasets) + script execution (10 datasets, Dataset 10 = generate_custom_recipe)
- Model upgrade: `claude-sonnet-4-5-20250929` → `claude-sonnet-4-6` (generate_custom_recipe, seed_recipe_db)
- pydantic-ai API alignment: `OpenAIModel` → `OpenAIChatModel`, `result.output` confirmed correct in 1.39.0
- pytest warnings fixed: removed `asyncio_default_fixture_loop_scope` (invalid in pytest-asyncio 0.26)
- New test files: `test_generate_week_plan.py` (9 tests), `test_generate_custom_recipe.py` (6 tests)
- `test_generate_day_plan.py` extended: `TestFindCustomRequest` (3 tests) + custom-request integration test
- E2E test architecture: 3 `FunctionModel` unit tests + 22 `@pytest.mark.integration` real-LLM tests
- Bug fix: `goals: dict` → `dict[str, int] | None` — prevents LLM passing a list instead of a dict
- Bug fix: Supabase mock in E2E tests now returns JSON-serializable dicts (was MagicMock → TypeError)
- Test suite: **350 unit tests passing, 0 failures** (`pytest tests/ evals/ -m "not integration"`)

**Next Tasks (Priority Order):**
1. **Seed recipe DB** — run `seed_recipe_db.py` (prerequisite for new meal planning system)
2. **Skill redesign based on eval results** — optimize scripts where evals reveal gaps
3. **Context optimization** — reduce token usage in agent prompts and skill metadata
4. **OpenFoodFacts integration** — complete migration (SQL column rename fatsecret → openfoodfacts)
