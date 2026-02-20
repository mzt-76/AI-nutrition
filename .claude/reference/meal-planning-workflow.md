# Meal Planning Workflow — Technical Reference

**Last updated:** 2026-02-20
**Applies to:** `skills/meal-planning/`, `src/nutrition/recipe_db.py`, `src/nutrition/portion_scaler.py`, `src/nutrition/meal_plan_optimizer.py`

---

## 1. Architecture Overview

The meal planning system follows the project's three-layer architecture:

```
Agent (LLM)
  │  calls run_skill_script("meal-planning", "generate_week_plan", {...})
  ▼
skills/meal-planning/scripts/          ← orchestrators
  ├── generate_week_plan.py            ← entry point (N-day loop)
  ├── generate_day_plan.py             ← 1-day pipeline
  ├── select_recipes.py                ← DB query wrapper
  ├── scale_portions.py                ← scaling wrapper
  ├── validate_day.py                  ← allergen + macro check
  ├── generate_custom_recipe.py        ← LLM fallback via Claude Sonnet 4.6
  ├── seed_recipe_db.py                ← DB population via LLM (run once)
  ├── generate_shopping_list.py        ← list from stored plan
  └── fetch_stored_meal_plan.py        ← retrieve existing plan
  │
  │  import from
  ▼
src/nutrition/                         ← domain logic (pure / DB CRUD)
  ├── recipe_db.py                     ← Supabase CRUD for recipes table
  ├── portion_scaler.py                ← pure math, no I/O
  ├── meal_plan_optimizer.py           ← OFF macro recalc + portion optimization
  ├── validators.py                    ← allergen + macro checks
  ├── meal_distribution.py             ← distribute daily macros across meals
  ├── meal_plan_formatter.py           ← markdown generation
  └── openfoodfacts_client.py          ← ingredient → macros (cache-first)
```

**Dependency direction is strictly downward.** No `src/nutrition/` module imports from skills. No skill imports from `src/agent.py`.

---

## 2. The Full Pipeline (generate_week_plan)

```
User request → Agent → run_skill_script("meal-planning", "generate_week_plan", params)
                                    │
                         generate_week_plan.py
                                    │
          ┌─────────────────────────┼─────────────────────────┐
          │                         │                         │
    1. Validate inputs        2. Fetch profile         3. Resolve targets
    (meal_structure,          (fetch_my_profile_tool)  (args || profile)
     date format)
          │
    4. Auto-detect meal structure (if not specified)
    (≥2500 kcal → 3_meals_1_preworkout, else → 3_consequent_meals)
          │
    5. Calculate meal distribution
    (calculate_meal_macros_distribution)
    → meal_targets: [{meal_type, target_calories, target_protein_g, ...}]
          │
    6. Parse notes → custom_requests
    {"Mardi": {"dejeuner": "risotto aux champignons"}}
          │
    7. Loop N days ─────────────────────────────────────────────────────┐
          │                                                               │
    generate_day_plan.execute(                                           │
        day_name, day_date, meal_targets,                                │
        user_profile, exclude_recipe_ids,     ◄── accumulates across days│
        custom_requests.get(day_name, {})                                │
    )                                                                    │
          │                                                              │
    8. Assemble {"days": [...], "weekly_summary": {...}}                 │
          │                                          used_recipe_ids ────┘
    9. Store in meal_plans table (Supabase)
          │
    10. Generate Markdown file (tempfile)
          │
    11. Return JSON response
```

**Sequential day generation is intentional.** `exclude_recipe_ids` accumulates across days — day 2 cannot select recipes already used on day 1. Parallelising would break variety tracking.

**Auto-detect meal structure:** When `meal_structure` is not specified by the agent, `generate_week_plan.py` picks the best structure based on calorie target. High-calorie plans (≥2500 kcal, typical for muscle gain) get `3_meals_1_preworkout` (3 main meals + 1 pre-workout snack) to better distribute macros. Lower-calorie plans get `3_consequent_meals`.

---

## 3. Day Pipeline (generate_day_plan)

For each day, three private functions do the work:

```
execute()
    │
    ├── Build target_macros (sum of all meal_targets)
    │
    └── Retry loop (max 2 retries):
            │
            _select_and_scale_meals()
                │
                └── For each meal_slot:
                        │
                        _find_custom_request()     ← is there a user request for this slot?
                        │
                        _get_recipe_for_slot()     ← single responsibility: get a recipe
                            │
                            ├── custom_request? → generate_custom_recipe (LLM)
                            ├── DB candidates?  → sort by _score_recipe_macro_fit(), pick best
                            └── no DB match?    → generate_custom_recipe (LLM fallback)
                        │
                        scale_recipe_to_targets()  ← pure math from portion_scaler.py
                        │
                        _build_meal_from_scaled_recipe()
                        │
                        increment_usage()          ← non-critical, fire-and-forget
            │
            Recalculate macros via OpenFoodFacts:
                calculate_meal_plan_macros()
                → replaces scaled macro estimates with real ingredient-based values
                → deepcopy backup: if OFF fails, original scaled macros are restored
            │
            validate:
                ├── validate_allergens()   → allergen_violations
                └── validate_daily_macros() → macro_violations (protein ±5%, rest ±10%)
            │
            if valid OR last attempt → return best_day
            else → track failed_recipe_ids, retry with different recipes
```

### Macro-fitness scoring

Recipe selection uses `_score_recipe_macro_fit()` to pick the best-fitting recipe from DB candidates instead of blindly taking the first one. The score compares protein/cal, carbs/cal, fat/cal ratios between the recipe and the target, with **2x weight on protein**. Lower score = better fit.

### Retry strategy

On validation failure, `failed_recipe_ids` accumulates the IDs from the failed attempt. On retry, these are added to `exclude_recipe_ids`, forcing the system to pick **different recipes**. This prevents retries from producing identical results.

### OpenFoodFacts recalculation

After scaling, `calculate_meal_plan_macros()` from `meal_plan_optimizer.py` recalculates the macros for every ingredient via OpenFoodFacts. This ensures the displayed macros are based on real nutritional data, not on the recipe's stored `calories_per_serving` multiplied by a scale factor (which is approximate). The stored `calories_per_serving` is only used to compute the scale factor itself.

A `deepcopy` backup of the day plan is taken before the OFF call. If `calculate_meal_plan_macros()` fails mid-execution (some ingredients not found in OFF), the plan is restored from backup and the scaled macros are used as fallback.

---

## 4. LLM Fallback (generate_custom_recipe)

Called in two situations:
1. User explicitly requested a recipe ("risotto mardi" in notes)
2. Recipe DB returns 0 candidates for a slot

**Fallback flow:**
```
Claude Sonnet 4.6 (claude-sonnet-4-6)
    │
    ├── Structured JSON prompt → recipe dict (name, ingredients, instructions, ...)
    │
    ├── Parse JSON (strip markdown code fences if present)
    │
    ├── Allergen validation (zero tolerance — before any further processing)
    │   └── If violation → reject, return error
    │
    ├── Macro calculation via OpenFoodFacts (all ingredients in parallel via asyncio.gather)
    │   └── match_ingredient() → cache-first (ingredient_mapping table → OFF API)
    │
    ├── Build full recipe dict with off_validated flag
    │
    └── Save to recipes table (save_to_db=True)
        └── Recipe available for future DB selection → reduces future LLM calls
```

**Security:** `recipe_request` is truncated to 200 characters before prompt interpolation. Python allergen validation is independent of the LLM and provides a hard backstop.

**Limitation:** Ingredient name-based allergen detection (e.g., `validate_allergens` checks ingredient names against user allergen strings). If the user's allergen is "lactose" and the LLM generates a recipe with "fromage", the validator may not catch it unless `allergen_families.md` maps "fromage → lactose". See `references/allergen_families.md` for current mappings.

---

## 5. Portion Scaling (portion_scaler.py)

Pure mathematical module — no I/O, no DB calls, fully deterministic.

```python
scale_factor = clamp(target_calories / recipe_calories, MIN_SCALE_FACTOR, MAX_SCALE_FACTOR)
# MIN_SCALE_FACTOR = 0.50, MAX_SCALE_FACTOR = 1.50 (from meal_plan_optimizer.py)

new_quantity = round_quantity_smart(original_quantity * scale_factor, unit, ingredient_name)
# Countable units (pièces, eggs): rounded to integer
# Spices < 10g: 1 decimal allowed
# Everything else: rounded to integer grams/ml

scaled_nutrition = {macro: original_value * scale_factor for macro in macros}
```

**Why calorie-based primary scaling:** Calories are the most constrained target (safety bounds). The scale factor determines ingredient quantities. After scaling, `calculate_meal_plan_macros()` recalculates the actual macros from the scaled ingredient quantities via OpenFoodFacts — so the scaling factor only needs to be approximately right. The macro-fitness scoring in recipe selection ensures selected recipes have macro ratios similar to the target, minimising the gap between scaled estimates and actual macros.

---

## 6. Recipe DB (recipe_db.py)

### Schema summary

| Column | Type | Purpose |
|---|---|---|
| `meal_type` | TEXT | "petit-dejeuner", "dejeuner", "diner", "collation" |
| `calories_per_serving` | NUMERIC | Used for scale factor calculation |
| `ingredients` | JSONB | Array of `{name, quantity, unit}` dicts — must be JSONB, not JSON string |
| `allergen_tags` | TEXT[] | Pre-computed at save time, filtered in Python |
| `off_validated` | BOOLEAN | True = all ingredients matched in OpenFoodFacts |
| `usage_count` | INTEGER | Drives ordering — most-used recipes surface first |
| `source` | TEXT | "llm_generated", "manual", "user_validated", "expert_curated" |

### Recipe sources

- **`manual`**: Seeded by `scripts/seed_recipes_manual.py`. Well-balanced macros (300-580 kcal/serving), correct ingredient format. No LLM involved.
- **`llm_generated`**: Created by `generate_custom_recipe.py` or `seed_recipe_db.py`. OFF-validated at creation. May have higher calorie counts.

### Allergen filtering strategy

Allergens are filtered **in Python after DB retrieval**, not via Supabase array operators. This matches all other filtering in the codebase and avoids Supabase client compatibility risk.

```python
# In search_recipes():
results = [
    r for r in results
    if not set(tag.lower() for tag in r.get("allergen_tags", [])) & normalized_allergens
]
```

### Calorie range for queries

`generate_day_plan.py` intentionally omits calorie range filtering. The scale factor (clamped to [0.5, 1.5]) adjusts portions to any target. Filtering by range would exclude valid recipes and cause unnecessary LLM fallback.

---

## 7. Allergen Safety Architecture

Three independent layers ensure zero-tolerance allergen enforcement:

```
Layer 1 — DB query (recipe_db.py)
    Python filters allergen_tags before returning candidates
    → Allergenic recipes never enter the selection pool

Layer 2 — Post-generation validation (generate_day_plan.py)
    validate_allergens() runs on the assembled day plan
    → Catches anything that slipped through Layer 1

Layer 3 — LLM recipe guard (generate_custom_recipe.py)
    validate_allergens() runs on LLM output before save or use
    → LLM-generated recipes checked independently of the LLM's own compliance
```

No single failure can produce an allergenic plan. The Python validator is the final authority — it is not affected by LLM instruction-following quality.

---

## 8. Output Format Contract

The `plan_data` JSONB stored in `meal_plans` keeps this exact structure. **Do not change it** — `fetch_stored_meal_plan` and `generate_shopping_list` depend on it.

```
plan_data
├── days: [Day]
│   ├── day: str          "Lundi"
│   ├── date: str         "2026-02-18"
│   ├── meals: [Meal]
│   │   ├── meal_type: str
│   │   ├── name: str
│   │   ├── ingredients: [Ingredient]
│   │   │   ├── name: str
│   │   │   ├── quantity: float
│   │   │   ├── unit: str
│   │   │   └── nutrition: {calories, protein_g, carbs_g, fat_g}  ← added by OFF recalc
│   │   ├── instructions: str
│   │   ├── prep_time_minutes: int
│   │   └── nutrition: {calories, protein_g, carbs_g, fat_g}
│   └── daily_totals: {calories, protein_g, carbs_g, fat_g}
└── weekly_summary
    ├── average_calories: float
    ├── average_protein_g: float
    ├── average_carbs_g: float
    └── average_fat_g: float
```

`generate_shopping_list` only reads `ingredients[].name`, `.quantity`, `.unit` — enriched keys like `nutrition` or `openfoodfacts_code` are transparent to it.

---

## 9. Known Limitations

### `increment_usage` costs 2 DB calls per recipe
`get_recipe_by_id` then `update` — the Supabase Python SDK doesn't support field increments without a fetch-first. Future fix: create a Postgres stored procedure `increment_recipe_usage(recipe_id UUID)` and call via `supabase.rpc("increment_recipe_usage", {"recipe_id": id})`.

### Ingredient name-based allergen detection has gaps
`validate_allergens` checks ingredient names against allergen strings. It relies on `allergen_families.md` mappings. Ingredients named generically (e.g., "pâte feuilletée" which contains gluten and butter) may be missed if not explicitly mapped. **Update `references/allergen_families.md` whenever new ingredient patterns emerge.**

### 7-day loop is sequential by design
Parallelising would require a different variety-tracking mechanism (e.g., a shared set). Not worth the complexity — each day takes < 2 seconds with a full recipe DB.

### OpenFoodFacts coverage gaps
Some ingredients (specialty items, brand-specific products) may not match in OpenFoodFacts. When `calculate_meal_plan_macros()` can't match an ingredient, it skips it and logs a warning. The day plan falls back to scaled macro estimates for that meal. The `off_validated` flag on recipes indicates whether all ingredients were matched.

### Recipe DB ordering favours old recipes
`search_recipes` orders by `usage_count DESC`. New recipes (usage_count=0) appear last. This is intentional — well-tested recipes should surface first — but it can delay adoption of newly seeded recipes. Running the pipeline a few times naturally increases usage counts.

---

## 10. How to Modify This Workflow

### Add a new step to the day pipeline
1. Create `skills/meal-planning/scripts/your_step.py` with `async def execute(**kwargs) -> str`
2. Import domain logic from `src/nutrition/` — never implement calculations in the script
3. Call it inside `generate_day_plan.py:_select_and_scale_meals()` or `execute()`
4. Update `SKILL.md` to document the new step
5. Add unit tests in `tests/test_your_step.py` and eval cases in `evals/test_skill_scripts.py`

### Change the meal structure
`src/nutrition/meal_distribution.py:MEAL_STRUCTURES` defines the available structures. Add a new key there. `generate_week_plan.py` validates against `MEAL_STRUCTURES` at runtime — it will automatically accept the new structure.

### Add a new recipe source (e.g., user-uploaded recipes)
1. Add a new `source` value to the `recipes` table (`"user_uploaded"`)
2. Create a skill script `skills/meal-planning/scripts/import_user_recipe.py`
3. Call `save_recipe()` from `src/nutrition/recipe_db.py` — it handles normalisation and deduplication
4. No changes to `generate_day_plan.py` needed — DB recipes are source-agnostic

### Modify the scaling bounds
`MIN_SCALE_FACTOR` and `MAX_SCALE_FACTOR` are in `src/nutrition/meal_plan_optimizer.py`. Changing them affects both the optimiser and the portion scaler.

### Populate the recipe DB
**Manual seeder (preferred — no LLM, fast, reliable):**
```bash
PYTHONPATH=. python scripts/seed_recipes_manual.py
```
Adds 40 well-balanced recipes (10 per meal type). Ingredients stored as JSONB arrays.

**LLM seeder (more variety, slower, costs API credits):**
```python
run_skill_script("meal-planning", "seed_recipe_db", {
    "recipes_per_type": 30,
    "meal_types": ["petit-dejeuner", "dejeuner", "diner", "collation"],
    "diet_types": ["omnivore"],
})
```

Minimum viable: 10 recipes per meal type (40 total). Below that, most slots fall back to LLM which is slower.

---

## 11. File Map

| File | Role | Modify when... |
|---|---|---|
| `skills/meal-planning/SKILL.md` | Agent-readable contract | Parameters change, new scripts added, workflow changes |
| `skills/meal-planning/scripts/generate_week_plan.py` | N-day entry point | Adding week-level logic (new summary fields, different DB storage) |
| `skills/meal-planning/scripts/generate_day_plan.py` | 1-day orchestrator | Changing per-day logic (retry policy, validation, macro scoring) |
| `skills/meal-planning/scripts/select_recipes.py` | DB recipe selection | Changing filtering strategy, sort order |
| `skills/meal-planning/scripts/scale_portions.py` | Scaling skill wrapper | Only if script interface changes; math is in portion_scaler.py |
| `skills/meal-planning/scripts/validate_day.py` | Day validation wrapper | Only if script interface changes; logic is in validators.py |
| `skills/meal-planning/scripts/generate_custom_recipe.py` | LLM recipe generation | Changing prompt, model, OFF matching, allergen check |
| `skills/meal-planning/scripts/seed_recipe_db.py` | DB population via LLM | Changing batch size, cuisine coverage, seed strategy |
| `scripts/seed_recipes_manual.py` | DB population manual | Adding new recipes, changing ingredient format |
| `src/nutrition/portion_scaler.py` | Pure scaling math | Changing scaling algorithm or rounding rules |
| `src/nutrition/meal_plan_optimizer.py` | OFF recalc + optimization | Changing macro recalculation, fat rebalancing, complements |
| `src/nutrition/recipe_db.py` | Recipes table CRUD | Adding new query filters, new CRUD operations |
| `sql/create_recipes_table.sql` | DB schema | Schema changes (add column → also update recipe_db.py) |
| `references/allergen_families.md` | Allergen mappings | Adding new allergen families or ingredient mappings |
| `references/recipe_schema.md` | Recipe data model doc | Schema changes to the recipes table |
