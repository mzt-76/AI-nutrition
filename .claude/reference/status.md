# Current Status & Next Tasks

**Completed:**
- Core agent with 6 skill domains (nutrition, meal-planning, weekly-coaching, knowledge, body-analysis, skill-creator)
- Skill progressive disclosure system (SkillLoader)
- `run_skill_script` universal executor — skills are fully self-contained, no per-skill wrappers
- Weekplan refactoring — Recipe DB + day-by-day generation + LLM fallback (Claude Sonnet 4.5)
- Domain logic: calculations, adjustments, feedback extraction, validators, portion_scaler, recipe_db
- Pydantic-evals suites: skill loading (5 datasets) + script execution (5 datasets)

**Next Tasks (Priority Order):**
1. **Seed recipe DB** — run `seed_recipe_db.py` (prerequisite for new meal planning system)
2. **Skill redesign based on eval results** — optimize scripts where evals reveal gaps
3. **Context optimization** — reduce token usage in agent prompts and skill metadata
4. **OpenFoodFacts integration** — complete migration (SQL column rename fatsecret → openfoodfacts)
