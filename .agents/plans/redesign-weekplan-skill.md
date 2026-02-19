# Feature: Redesign Weekplan Skill — Recipe DB + Day-by-Day Generation

The following plan should be complete, but its important that you validate documentation and codebase patterns and task sanity before you start implementing.

Pay special attention to naming of existing utils types and models. Import from the right files etc.

## Feature Description

Refonte complète du skill `meal-planning` : passer d'une génération monolithique (7 jours en 1 appel LLM) à une architecture **Recipe DB + génération jour par jour** avec scaling mathématique des portions. Le LLM sert de fallback créatif quand une recette spécifique n'est pas dans la DB.

## User Story

As a user who wants a weekly meal plan
I want recipes selected from a validated database with mathematically precise macros
So that my meal plan is generated faster, with reliable nutrition data, and I can request custom recipes when needed

## Problem Statement

Le système actuel souffre de 3 problèmes majeurs :

1. **Fiabilité macros** : Le LLM génère des recettes sans macros → OpenFoodFacts match les ingrédients → optimiseur de portions tente de converger → pas de garantie de convergence
2. **Temps de génération** : 3-4 minutes (1 gros appel GPT-4o + 50-100 lookups OFF)
3. **Architecture** : 400+ lignes dans `src/tools.py`, les scripts dans `skills/meal-planning/scripts/` sont des placeholders non utilisés, code dupliqué entre `build_meal_plan_prompt` et `build_meal_plan_prompt_simple`

## Solution Statement

**Recipe DB + Day-by-Day + LLM Fallback** :

1. **Recipe DB** (table `recipes` Supabase) : Recettes pré-validées avec macros calculés via OFF par portion
2. **Génération jour par jour** : Pour chaque jour, sélectionner des recettes DB → scaler mathématiquement les portions → valider → passer au jour suivant
3. **LLM Fallback** : Si l'utilisateur demande une recette spécifique non couverte par la DB → le LLM la génère → macros calculés via OFF → sauvegardée dans la DB pour réutilisation
4. **Scaling mathématique** : `scale_factor = target_calories / recipe_calories` → toutes les quantités d'ingrédients × scale_factor → macros exactes par calcul

## Feature Metadata

**Feature Type**: Refactor (architecture) + Enhancement (recipe DB)
**Estimated Complexity**: High
**Primary Systems Affected**: `skills/meal-planning/`, `src/tools.py`, `src/agent.py`, `src/nutrition/`, `sql/`
**Dependencies**: Supabase (PostgreSQL), Anthropic API (Claude Sonnet 4.5 — `claude-sonnet-4-5-20250929`), OpenFoodFacts client
**LLM Strategy**: All skill-level LLM calls (recipe generation, seeding) use **Claude Sonnet 4.5** via `anthropic.AsyncAnthropic`. The Pydantic AI agent itself remains on its configured model. `AgentDeps` gains a new `anthropic_client` field.

---

## CONTEXT REFERENCES

### Relevant Codebase Files — MUST READ BEFORE IMPLEMENTING

- `src/tools.py` (lines 306-702) — Why: Current `generate_weekly_meal_plan_tool()` orchestrator to refactor. Contains the 10-step pipeline to decompose
- `src/agent.py` (lines 83-101) — Why: `_import_skill_script()` pattern for loading skill scripts via importlib
- `src/agent.py` (lines 390-434) — Why: Current `generate_weekly_meal_plan` tool wrapper to update
- `src/nutrition/meal_planning.py` (lines 847-1087) — Why: `build_meal_plan_prompt_simple()` to reuse for LLM fallback
- `src/nutrition/meal_planning.py` (lines 690-844) — Why: Shopping list helpers (`extract_ingredients_from_meal_plan`, `aggregate_ingredients`, `categorize_ingredients`) to keep intact
- `src/nutrition/meal_distribution.py` — Why: `calculate_meal_macros_distribution()` to reuse as-is
- `src/nutrition/meal_plan_optimizer.py` (lines 1-68) — Why: `round_quantity_smart()` and HIGH_FAT_INGREDIENTS to reuse
- `src/nutrition/openfoodfacts_client.py` — Why: `match_ingredient()` interface (cache-first, returns macros per quantity)
- `src/nutrition/validators.py` — Why: `validate_allergens()`, `validate_meal_plan_structure()`, `validate_meal_plan_complete()` to reuse
- `src/nutrition/meal_plan_formatter.py` — Why: `format_meal_plan_as_markdown()` to reuse as-is
- `src/nutrition/macro_adjustments.py` (lines 33-90) — Why: `COMPLEMENT_FOODS` list to reuse as fallback
- `sql/create_ingredient_mapping_table.sql` — Why: Schema pattern to follow for new `recipes` table. Note: columns still named `fatsecret_*` — needs migration
- `skills/nutrition-calculating/scripts/calculate_nutritional_needs.py` — Why: Reference skill script pattern (`async def execute(**kwargs) -> str`)
- `skills/nutrition-calculating/SKILL.md` — Why: Reference SKILL.md format (YAML frontmatter + sections)
- `.claude/reference/skill-creation-guide.md` — Why: Script pattern rules, eval pattern, mocking strategy
- `src/clients.py` — Why: Client factory functions. Add `get_anthropic_client()` for Claude Sonnet 4.5
- `conftest.py` — Why: Shared test fixtures (`sample_profile`, `sample_meal_plan`)
- `evals/test_skill_scripts.py` — Why: Eval pattern to add new cases

### Output Format Contract (MUST PRESERVE)

The `plan_data` JSONB stored in `meal_plans` must keep this exact structure for compatibility with `fetch_stored_meal_plan` and `generate_shopping_list`:

```
Ingredient (minimum): {"name": str, "quantity": float, "unit": str}
Meal: {"meal_type": str, "name": str, "ingredients": [Ingredient], "instructions": str, "prep_time_minutes": int, "nutrition": {"calories": float, "protein_g": float, "carbs_g": float, "fat_g": float}}
Day: {"day": str, "date": str, "meals": [Meal], "daily_totals": {"calories": float, "protein_g": float, "carbs_g": float, "fat_g": float}}
Top-level: {"days": [Day], "weekly_summary": {"average_calories": float, "average_protein_g": float, "average_carbs_g": float, "average_fat_g": float}}
```

Shopping list functions (`aggregate_ingredients`, `categorize_ingredients`) only read `name`, `quantity`, `unit` from ingredients — enriched keys are optional.

### New Files to Create

```
skills/meal-planning/
├── SKILL.md                              # REWRITE with new workflow
├── scripts/
│   ├── generate_day_plan.py              # NEW: Core orchestrator — 1 day at a time
│   ├── select_recipes.py                 # NEW: Query recipe DB with filtering
│   ├── scale_portions.py                 # NEW: Mathematical portion scaling
│   ├── generate_custom_recipe.py         # NEW: LLM fallback for custom requests
│   ├── validate_day.py                   # NEW: Single-day validation
│   ├── seed_recipe_db.py                 # NEW: Populate recipe DB via LLM + OFF
│   ├── generate_shopping_list.py         # KEEP existing (works well)
│   └── fetch_stored_meal_plan.py         # KEEP existing (works well)
└── references/
    ├── allergen_families.md              # KEEP
    ├── presentation_format.md            # KEEP
    ├── shopping_list_format.md           # KEEP
    └── recipe_schema.md                  # NEW: Recipe data model documentation

sql/
├── create_recipes_table.sql              # NEW: Recipe DB schema
├── migrate_ingredient_mapping.sql        # NEW: Rename fatsecret → openfoodfacts columns
└── create_ingredient_mapping_table.sql   # EXISTING

src/nutrition/
├── recipe_db.py                          # NEW: Recipe DB CRUD operations
└── portion_scaler.py                     # NEW: Mathematical portion scaling (pure functions)

tests/
├── test_recipe_db.py                     # NEW: Recipe DB tests
├── test_portion_scaler.py                # NEW: Portion scaling tests
└── test_generate_day_plan.py             # NEW: Day plan generation tests
```

### Files to Modify

- `src/clients.py` — Add `get_anthropic_client()` for Claude Sonnet 4.5
- `src/agent.py` — Add `anthropic_client` to `AgentDeps`, update tool registrations
- `src/tools.py` — Remove old `generate_weekly_meal_plan_tool()` (400 lines), replace with thin wrapper calling skill scripts
- `skills/meal-planning/SKILL.md` — Full rewrite with new workflow
- `sql/create_ingredient_mapping_table.sql` — Update column names to match live DB (if already migrated)

### Files to Delete

- `src/nutrition/fatsecret_client.py` (568 lines) — Deprecated, replaced by openfoodfacts_client.py
- `skills/meal-planning/scripts/generate_weekly_meal_plan.py` — Current placeholder, replaced by new scripts

### Relevant Documentation — READ BEFORE IMPLEMENTING

- `.claude/reference/skill-creation-guide.md` — Script pattern, SKILL.md format, eval pattern
- `.claude/reference/dependency-safety-rules.md` — Breaking change prevention rules
- `skills/meal-planning/references/allergen_families.md` — Allergen family mappings for validation

### Patterns to Follow

**Skill Script Pattern** (from `skills/nutrition-calculating/scripts/calculate_nutritional_needs.py`):

```python
"""One-line description.

Utility script — can be imported by agent tool wrapper or run standalone.
Source: <origin>
"""
import json
import logging
from src.nutrition.<module> import <functions>

logger = logging.getLogger(__name__)

async def execute(**kwargs) -> str:
    """What this does.
    Args:
        param: description.
    Returns:
        JSON string with result.
    """
    param = kwargs["required_param"]
    optional = kwargs.get("optional_param", "default")
    try:
        result = do_something(param)
        return json.dumps(result, indent=2)
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return json.dumps({"error": str(e), "code": "VALIDATION_ERROR"})
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return json.dumps({"error": "Internal error", "code": "SCRIPT_ERROR"})
```

**SKILL.md Format** (YAML frontmatter):

```yaml
---
name: meal-planning
description: <one-line>
category: planning
---
```

**Agent Tool Wrapper Pattern** (from `src/agent.py`):

```python
async def tool_name(ctx: RunContext[AgentDeps], param: str) -> str:
    """Docstring."""
    logger.info("Tool called: tool_name")
    module = _import_skill_script("meal-planning", "script_name")
    return await module.execute(supabase=ctx.deps.supabase, **params)
```

**Error Handling**: ValueError → `VALIDATION_ERROR`, Exception → `SCRIPT_ERROR`

**Logging**: `logger.info(f"context: key={value}")` with structured fields

**DB Pattern** (Supabase):
```python
response = supabase.table("table_name").select("*").eq("field", value).execute()
```

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation — Database & Domain Logic

Créer les tables DB, les modules de domain logic purs (recipe_db, portion_scaler), et les migrations SQL.

**Tasks:**
- Créer la table `recipes` dans Supabase
- Migrer `ingredient_mapping` (rename fatsecret → openfoodfacts)
- Créer `src/nutrition/recipe_db.py` — CRUD operations pour recipes
- Créer `src/nutrition/portion_scaler.py` — Scaling mathématique pur (pas d'I/O)
- Tests unitaires pour recipe_db et portion_scaler

### Phase 2: Core Skill Scripts

Créer les scripts du pipeline dans `skills/meal-planning/scripts/`.

**Tasks:**
- `select_recipes.py` — Sélection de recettes depuis la DB avec filtrage
- `scale_portions.py` — Wrapper skill autour de portion_scaler
- `validate_day.py` — Validation single-day
- `generate_custom_recipe.py` — LLM fallback
- `generate_day_plan.py` — Orchestrateur principal (1 jour)
- `seed_recipe_db.py` — Peuplement initial de la recipe DB

### Phase 3: Integration & Cleanup

Connecter les nouveaux scripts à l'agent, supprimer le code mort, mettre à jour le SKILL.md.

**Tasks:**
- Réécrire `SKILL.md` avec le nouveau workflow
- Mettre à jour `src/agent.py` — Nouvelles tool registrations
- Refactorer `src/tools.py` — Remplacer l'ancienne implémentation monolithique
- Supprimer `src/nutrition/fatsecret_client.py`
- Supprimer le vieux prompt `build_meal_plan_prompt` (garder `build_meal_plan_prompt_simple` pour le LLM fallback)

### Phase 4: Testing & Validation

Tests unitaires, evals, et validation end-to-end.

**Tasks:**
- Tests unitaires pour chaque script
- Evals pydantic pour les scripts
- Tests d'intégration du pipeline complet
- Validation lint/format

---

## STEP-BY-STEP TASKS

### Task 1: CREATE `sql/create_recipes_table.sql`

- **IMPLEMENT**: Table `recipes` avec schema :

```sql
CREATE TABLE IF NOT EXISTS recipes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identification
    name TEXT NOT NULL,                          -- "Omelette protéinée aux épinards"
    name_normalized TEXT NOT NULL,               -- "omelette proteinee aux epinards"
    description TEXT,                            -- Short description

    -- Classification
    meal_type TEXT NOT NULL,                     -- "petit-dejeuner", "dejeuner", "diner", "collation"
    cuisine_type TEXT DEFAULT 'française',       -- "française", "italienne", "asiatique", etc.
    diet_type TEXT DEFAULT 'omnivore',           -- "omnivore", "végétarien", "vegan", etc.
    tags TEXT[] DEFAULT '{}',                    -- ["high-protein", "quick", "low-carb"]

    -- Recipe Content
    ingredients JSONB NOT NULL,                  -- [{"name": "Eggs", "quantity": 3, "unit": "units", "nutrition_per_100g": {...}}]
    instructions TEXT NOT NULL,                  -- French instructions
    prep_time_minutes INTEGER DEFAULT 30,

    -- Pre-calculated Nutrition (per 1 serving)
    calories_per_serving NUMERIC(7,2) NOT NULL,
    protein_g_per_serving NUMERIC(6,2) NOT NULL,
    carbs_g_per_serving NUMERIC(6,2) NOT NULL,
    fat_g_per_serving NUMERIC(6,2) NOT NULL,

    -- Allergen Safety (pre-computed from ingredients)
    allergen_tags TEXT[] DEFAULT '{}',           -- ["lactose", "gluten", "oeuf"]

    -- Quality & Usage
    source TEXT DEFAULT 'llm_generated',         -- "llm_generated", "user_validated", "expert_curated"
    off_validated BOOLEAN DEFAULT FALSE,          -- All ingredients matched in OpenFoodFacts
    usage_count INTEGER DEFAULT 0,
    rating NUMERIC(2,1) DEFAULT 0.0,             -- 0.0-5.0 user rating

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_recipes_meal_type ON recipes(meal_type);
CREATE INDEX idx_recipes_diet_type ON recipes(diet_type);
CREATE INDEX idx_recipes_allergen_tags ON recipes USING GIN(allergen_tags);
CREATE INDEX idx_recipes_tags ON recipes USING GIN(tags);
CREATE INDEX idx_recipes_name_normalized ON recipes(name_normalized);
CREATE INDEX idx_recipes_calories ON recipes(calories_per_serving);
CREATE INDEX idx_recipes_protein ON recipes(protein_g_per_serving);

-- Trigger
CREATE TRIGGER trigger_update_recipes_timestamp
    BEFORE UPDATE ON recipes
    FOR EACH ROW
    EXECUTE FUNCTION update_ingredient_mapping_updated_at();
```

- **PATTERN**: `sql/create_ingredient_mapping_table.sql` for schema conventions
- **VALIDATE**: Execute SQL in Supabase dashboard — verify table created

### Task 2: VALIDATE & FIX `sql/migrate_ingredient_mapping.sql`

- **PRE-CHECK**: The Python code (`openfoodfacts_client.py`) already uses `openfoodfacts_code` / `openfoodfacts_name` columns. The SQL file still has `fatsecret_*` names. Check the live DB state first:

```sql
SELECT column_name FROM information_schema.columns WHERE table_name = 'ingredient_mapping' ORDER BY ordinal_position;
```

- **IF columns are already `openfoodfacts_*`**: DB was already migrated. Only update `sql/create_ingredient_mapping_table.sql` to reflect current schema (rename columns in the CREATE TABLE statement). No ALTER needed.
- **IF columns are still `fatsecret_*`**: Run the ALTER:

```sql
ALTER TABLE ingredient_mapping RENAME COLUMN fatsecret_food_id TO openfoodfacts_code;
ALTER TABLE ingredient_mapping RENAME COLUMN fatsecret_food_name TO openfoodfacts_name;
```

- **THEN**: Update `sql/create_ingredient_mapping_table.sql` to match current reality
- **VALIDATE**: `SELECT openfoodfacts_code FROM ingredient_mapping LIMIT 1;` succeeds

### Task 3: CREATE `src/nutrition/portion_scaler.py`

- **IMPLEMENT**: Pure functions for mathematical portion scaling. No I/O, no DB calls.

```python
"""Mathematical portion scaling for recipes.

Pure functions that scale ingredient quantities to hit target macros exactly.
No I/O — all calculations are deterministic.

References:
    Helms et al. (2014): Portion scaling maintains adherence better than supplements
"""

import logging
from src.nutrition.meal_plan_optimizer import round_quantity_smart

logger = logging.getLogger(__name__)

def scale_recipe_to_targets(
    recipe: dict,
    target_calories: int,
    target_protein_g: int,
    target_carbs_g: int | None = None,
    target_fat_g: int | None = None,
) -> dict:
    """Scale recipe portions to hit target macros.

    Uses calorie-based primary scaling, then adjusts protein-rich ingredients
    if protein target is off by more than 10%.

    Args:
        recipe: Recipe dict with calories_per_serving, protein_g_per_serving,
                carbs_g_per_serving, fat_g_per_serving, ingredients list
        target_calories: Target calories for this meal slot
        target_protein_g: Target protein for this meal slot
        target_carbs_g: Optional carbs target
        target_fat_g: Optional fat target

    Returns:
        Scaled recipe dict with updated quantities and nutrition
    """
    ...

def calculate_scale_factor(
    actual_calories: float,
    target_calories: float,
) -> float:
    """Calculate portion scale factor clamped to bounds from meal_plan_optimizer."""
    # Uses MIN_SCALE_FACTOR (0.50) and MAX_SCALE_FACTOR (1.50) from meal_plan_optimizer
    ...

def scale_ingredients(
    ingredients: list[dict],
    scale_factor: float,
) -> list[dict]:
    """Scale all ingredient quantities by factor with smart rounding."""
    ...

def calculate_scaled_nutrition(
    recipe: dict,
    scale_factor: float,
) -> dict:
    """Calculate new nutrition values after scaling."""
    ...
```

- **PATTERN**: Pure functions like `src/nutrition/calculations.py` — no side effects, validated inputs, return dicts
- **IMPORTS**: `from src.nutrition.meal_plan_optimizer import round_quantity_smart, MIN_SCALE_FACTOR, MAX_SCALE_FACTOR`
- **GOTCHA**: Must handle countable units (eggs, pieces) differently — round to integers. Use `round_quantity_smart()` from `meal_plan_optimizer.py:71-130`
- **GOTCHA**: Use `MIN_SCALE_FACTOR` (0.50) and `MAX_SCALE_FACTOR` (1.50) from `meal_plan_optimizer.py` — do NOT define separate bounds
- **VALIDATE**: `pytest tests/test_portion_scaler.py -v`

### Task 4: CREATE `tests/test_portion_scaler.py`

- **IMPLEMENT**: Unit tests for portion_scaler :
  - `test_scale_factor_calculation` — basic, clamped min/max
  - `test_scale_recipe_to_targets` — happy path (recipe scales correctly)
  - `test_scale_ingredients_rounding` — eggs stay integer, grams round to int
  - `test_scale_edge_cases` — zero calories, very high targets, very low targets
  - `test_nutrition_proportionality` — if scale 1.5x, all macros are 1.5x
- **PATTERN**: `conftest.py` fixtures (`sample_profile`, `sample_meal_plan`)
- **VALIDATE**: `pytest tests/test_portion_scaler.py -v`

### Task 5: CREATE `src/nutrition/recipe_db.py`

- **IMPLEMENT**: CRUD operations for the `recipes` table :

```python
"""Recipe database operations for meal planning.

Provides CRUD operations for the recipes table in Supabase.
All functions are async and return structured results.
"""

import logging
from supabase import Client
from src.nutrition.openfoodfacts_client import normalize_ingredient_name

logger = logging.getLogger(__name__)

async def search_recipes(
    supabase: Client,
    meal_type: str,
    exclude_allergens: list[str] | None = None,
    exclude_recipe_ids: list[str] | None = None,
    diet_type: str = "omnivore",
    cuisine_types: list[str] | None = None,
    max_prep_time: int | None = None,
    calorie_range: tuple[int, int] | None = None,
    limit: int = 10,
) -> list[dict]:
    """Search recipes with filtering constraints.

    Args:
        supabase: Supabase client
        meal_type: "petit-dejeuner", "dejeuner", "diner", "collation"
        exclude_allergens: Allergen tags to exclude (zero tolerance)
        exclude_recipe_ids: Recipe IDs already used this week (variety)
        diet_type: Diet filter
        cuisine_types: Preferred cuisine types
        max_prep_time: Maximum prep time in minutes
        calorie_range: (min, max) calorie range for the meal slot
        limit: Max results

    Returns:
        List of matching recipe dicts, ordered by usage_count DESC
    """
    ...

async def get_recipe_by_id(supabase: Client, recipe_id: str) -> dict | None:
    ...

async def save_recipe(supabase: Client, recipe: dict) -> dict:
    """Save a new recipe (from LLM generation or user input)."""
    ...

async def increment_usage(supabase: Client, recipe_id: str) -> None:
    ...

async def count_recipes_by_meal_type(supabase: Client) -> dict:
    """Return count of recipes per meal_type for coverage check."""
    ...
```

- **PATTERN**: `src/tools.py:fetch_my_profile_tool()` for Supabase query patterns
- **IMPORTS**: `from supabase import Client`
- **ALLERGEN FILTERING STRATEGY**: Do NOT use Supabase array operators (`.overlaps()`, `.not_()`). The codebase has zero examples of array operations. Instead:
  1. Query DB with simple filters (`meal_type`, `diet_type`, `calorie_range`)
  2. Filter allergens in Python: `[r for r in results if not set(r.get("allergen_tags", [])) & set(exclude_allergens)]`
  3. This matches the codebase's existing pattern (all filtering in Python after retrieval)
- **VALIDATE**: `pytest tests/test_recipe_db.py -v`

### Task 6: CREATE `tests/test_recipe_db.py`

- **IMPLEMENT**: Tests with mocked Supabase :
  - `test_search_recipes_basic` — returns recipes matching meal_type
  - `test_search_recipes_allergen_exclusion` — filters out allergen recipes
  - `test_search_recipes_variety` — excludes already-used recipe IDs
  - `test_save_recipe` — inserts and returns with ID
  - `test_count_recipes_by_meal_type` — coverage check
- **PATTERN**: Mock pattern from `.claude/reference/skill-creation-guide.md` — `MagicMock` with chained `.table().select().execute()`
- **VALIDATE**: `pytest tests/test_recipe_db.py -v`

### Task 7: CREATE `skills/meal-planning/scripts/select_recipes.py`

- **IMPLEMENT**: Skill script that selects recipes for a day's meals :

```python
"""Select recipes from database for a single day's meals.

Queries the recipe DB with allergen exclusion, variety tracking,
and preference filtering. Returns candidate recipes for each meal slot.

Source: New script for day-by-day meal planning workflow
"""

async def execute(**kwargs) -> str:
    """Select recipes for one day.

    Args:
        supabase: Supabase client
        meal_structure: Meal structure key (e.g. "3_consequent_meals")
        meal_targets: List of meal slot targets from meal_distribution
        user_allergens: Allergen list from profile
        diet_type: User diet type
        preferred_cuisines: List of preferred cuisines
        max_prep_time: Max prep time in minutes
        exclude_recipe_ids: Recipe IDs already used this week
        favorite_foods: User's favorite foods (boost matching recipes)

    Returns:
        JSON with selected recipes per meal slot:
        {
            "day_recipes": [
                {"meal_slot": {...targets}, "recipe": {...}, "source": "db"},
                {"meal_slot": {...targets}, "recipe": null, "source": "no_match"}
            ],
            "unmatched_slots": 0
        }
    """
```

- **PATTERN**: `skills/nutrition-calculating/scripts/calculate_nutritional_needs.py` for script structure
- **IMPORTS**: `from src.nutrition.recipe_db import search_recipes`
- **VALIDATE**: `ruff check skills/meal-planning/scripts/select_recipes.py`

### Task 8: CREATE `skills/meal-planning/scripts/scale_portions.py`

- **IMPLEMENT**: Skill script wrapper around `portion_scaler` :

```python
"""Scale recipe portions to match meal slot macro targets.

Takes a recipe and target macros, returns the recipe with scaled
ingredient quantities and updated nutrition.

Source: Extracted from src/nutrition/meal_plan_optimizer.py
"""

async def execute(**kwargs) -> str:
    """Scale recipe to targets.

    Args:
        recipe: Recipe dict from select_recipes or generate_custom_recipe
        target_calories: Target kcal for this meal slot
        target_protein_g: Target protein
        target_carbs_g: Target carbs (optional)
        target_fat_g: Target fat (optional)

    Returns:
        JSON with scaled recipe + nutrition delta summary
    """
```

- **IMPORTS**: `from src.nutrition.portion_scaler import scale_recipe_to_targets`
- **VALIDATE**: `ruff check skills/meal-planning/scripts/scale_portions.py`

### Task 9: CREATE `skills/meal-planning/scripts/validate_day.py`

- **IMPLEMENT**: Single-day validation (allergens + macros + structure) :

```python
"""Validate a single day's meal plan.

Runs allergen check (zero tolerance) and macro validation
for one day. Lighter than the full 4-level validate_meal_plan_complete.

Source: Extracted from src/nutrition/validators.py
"""

async def execute(**kwargs) -> str:
    """Validate one day.

    Args:
        day_plan: Day dict with meals, each with ingredients and nutrition
        user_allergens: List of allergen strings
        target_macros: Dict with calories, protein_g, carbs_g, fat_g
        protein_tolerance: Default 0.05 (±5%)
        other_tolerance: Default 0.10 (±10%)

    Returns:
        JSON: {"valid": bool, "violations": [...], "day": "Lundi"}
    """
```

- **IMPORTS**: `from src.nutrition.validators import validate_allergens, validate_daily_macros`
- **VALIDATE**: `ruff check skills/meal-planning/scripts/validate_day.py`

### Task 10: CREATE `skills/meal-planning/scripts/generate_custom_recipe.py`

- **IMPLEMENT**: LLM fallback for recipes not in DB, using **Claude Sonnet 4.5** :

```python
"""Generate a custom recipe via Claude Sonnet 4.5 when not found in recipe DB.

Used when user requests a specific dish or ingredient.
Generates recipe → calculates macros via OpenFoodFacts → optionally saves to DB.

Source: Simplified from src/tools.py generate_weekly_meal_plan_tool
"""
import anthropic

RECIPE_MODEL = "claude-sonnet-4-5-20250929"

async def execute(**kwargs) -> str:
    """Generate custom recipe via Claude Sonnet 4.5.

    Args:
        anthropic_client: anthropic.AsyncAnthropic client
        supabase: Supabase client (for OFF ingredient matching)
        recipe_request: Description of requested recipe
        meal_type: "petit-dejeuner", "dejeuner", "diner", "collation"
        target_calories: Approximate calorie target
        target_protein_g: Approximate protein target
        user_allergens: Allergens to exclude
        diet_type: Diet constraints
        max_prep_time: Max prep time
        save_to_db: Whether to save for future reuse (default True)

    Returns:
        JSON with generated recipe including OFF-validated macros
    """
```

- **LLM CALL**: Use `anthropic_client.messages.create(model=RECIPE_MODEL, max_tokens=2000, temperature=0.7)`. Prompt asks for structured JSON recipe output.
- **IMPORTS**: `from src.nutrition.openfoodfacts_client import match_ingredient`, `from src.nutrition.recipe_db import save_recipe`
- **GOTCHA**: After LLM generates recipe, loop through ingredients → `match_ingredient()` for each → sum macros → set `off_validated = True` if all match
- **VALIDATE**: `ruff check skills/meal-planning/scripts/generate_custom_recipe.py`

### Task 11: CREATE `skills/meal-planning/scripts/generate_day_plan.py`

- **IMPLEMENT**: Main orchestrator for 1 day. This is the core of the new workflow.

```python
"""Generate a complete meal plan for a single day.

Orchestrates: select_recipes → scale_portions → validate_day.
If recipe DB doesn't cover a meal slot, falls back to LLM generation.
Includes retry logic (max 2 retries per day).

Source: Refactored from src/tools.py generate_weekly_meal_plan_tool
"""

async def execute(**kwargs) -> str:
    """Generate meal plan for one day.

    Args:
        supabase: Supabase client
        anthropic_client: AsyncAnthropic client (for LLM fallback only — Sonnet 4.5)
        day_index: 0-6 (Monday-Sunday)
        day_name: "Lundi", "Mardi", etc.
        day_date: "YYYY-MM-DD"
        meal_targets: List of meal slot targets from meal_distribution
            [{"meal_type": "Petit-déjeuner", "time": "08:00",
              "target_calories": 750, "target_protein_g": 40, ...}]
        user_profile: Profile dict (allergens, preferences, diet_type)
        exclude_recipe_ids: IDs already used this week (variety)
        custom_requests: Optional dict of meal_type → recipe request string
            e.g. {"dejeuner": "risotto aux champignons"}

    Returns:
        JSON with complete day plan:
        {
            "success": true,
            "day": {
                "day": "Lundi",
                "date": "2026-02-18",
                "meals": [...],
                "daily_totals": {"calories": 2800, "protein_g": 175, ...}
            },
            "recipes_used": ["uuid1", "uuid2", "uuid3"],
            "llm_fallback_count": 0,
            "validation": {"valid": true, ...}
        }
    """
```

**Internal workflow per day:**
```
1. Call select_recipes → get candidate recipes for each meal slot
2. For unmatched slots (or custom_requests) → generate_custom_recipe via LLM
3. For each meal slot → scale_portions to hit exact meal-level macros
4. Build day dict with all meals
5. Call validate_day → check allergens + macros
6. If validation fails → retry with different recipes (max 2 retries)
7. Return validated day plan
```

- **IMPORTS**: Domain logic from `src.nutrition.*` (recipe_db, portion_scaler, validators). For sibling scripts (generate_custom_recipe), use `_import_skill_script` pattern.
- **GOTCHA**: Don't import sibling scripts directly — use `_import_skill_script` pattern or import the domain logic from `src.nutrition.*`
- **MACROS COMPUTATION**: DB recipes already have validated macros → skip `calculate_meal_plan_macros()` (no OFF lookups needed). Compute `daily_totals` by summing meal-level `nutrition` dicts directly in this script. LLM fallback recipes get their macros validated in `generate_custom_recipe.py` at generation time.
- **GRACEFUL DEGRADATION**: If 0 DB matches for a day → ALL slots use LLM fallback (system still works, just slower). If >50% slots use LLM fallback → `logger.warning("Recipe DB coverage low for meal_type=X, consider running seed_recipe_db")`.
- **VALIDATE**: `ruff check skills/meal-planning/scripts/generate_day_plan.py`

### Task 12: CREATE `skills/meal-planning/scripts/seed_recipe_db.py`

- **IMPLEMENT**: Script to populate recipe DB using **Claude Sonnet 4.5** :

```python
"""Seed the recipe database with validated recipes.

Generates recipes via Claude Sonnet 4.5, validates macros via OpenFoodFacts,
and inserts into the recipes table. Run once or periodically.
"""
import anthropic

RECIPE_MODEL = "claude-sonnet-4-5-20250929"

async def execute(**kwargs) -> str:
    """Seed recipe DB.

    Args:
        anthropic_client: anthropic.AsyncAnthropic client
        supabase: Supabase client
        meal_types: List of meal types to seed (default: all 4)
        recipes_per_type: Number of recipes per meal type (default: 30)
        cuisine_types: Cuisines to generate for
        diet_types: Diet types (default: ["omnivore"])

    Returns:
        JSON: {"total_generated": 120, "off_validated": 108, "failed": 12}
    """
```

- **MINIMUM VIABLE**: 10 recipes per meal_type (40 total) before the system works without excessive LLM fallback. Target: 30 per type (120 total).
- **LLM CALL**: `anthropic_client.messages.create(model=RECIPE_MODEL, max_tokens=4000, temperature=0.8)`. Generate batches of 5 recipes per call.
- **GOTCHA**: For each recipe, validate ALL ingredients via `match_ingredient()` — only save if `off_validated = True`
- **PREREQUISITE**: Must run this before first use of the new meal planning system.
- **VALIDATE**: `ruff check skills/meal-planning/scripts/seed_recipe_db.py`

### Task 13: UPDATE `src/tools.py` — Replace monolithic tool

- **REFACTOR**: Remove `generate_weekly_meal_plan_tool()` (lines 306-702). Replace with thin wrapper that:
  1. Validates inputs (date, meal_structure)
  2. Fetches profile
  3. Calculates meal distribution
  4. **Parses `notes` into `custom_requests`** (NEW — fixes existing bug where notes was stored but never used)
  5. Loops 7 days calling `generate_day_plan.execute()`
  6. **Computes `weekly_summary`** from all days' `daily_totals`
  7. Assembles full week plan (matching Output Format Contract)
  8. Stores in DB
  9. Generates markdown

```python
async def generate_weekly_meal_plan_tool(
    supabase, anthropic_client, http_client,
    start_date, target_calories_daily=None, target_protein_g=None,
    target_carbs_g=None, target_fat_g=None,
    meal_structure="3_consequent_meals", notes=None,
) -> str:
    """Generate 7-day meal plan day-by-day with recipe DB + LLM fallback."""
    # Step 1-3: Same as before (validate, profile, targets, distribution)

    # Step 4: Parse notes into custom_requests
    # e.g. "risotto aux champignons pour mardi" → {"Mardi": {"dejeuner": "risotto aux champignons"}}
    custom_requests = _parse_custom_requests(notes) if notes else {}

    # Step 5: Loop 7 days
    all_days = []
    used_recipe_ids = []
    for day_idx in range(7):
        day_name = DAY_NAMES[day_idx]
        day_result = await generate_day_plan_module.execute(
            supabase=supabase,
            anthropic_client=anthropic_client,
            day_index=day_idx,
            day_name=day_name,
            meal_targets=meal_macros_distribution["meals"],
            user_profile=profile_data,
            exclude_recipe_ids=used_recipe_ids,
            custom_requests=custom_requests.get(day_name, {}),
        )
        day_data = json.loads(day_result)
        all_days.append(day_data["day"])
        used_recipe_ids.extend(day_data["recipes_used"])

    # Step 6: Compute weekly_summary from daily_totals
    weekly_summary = _compute_weekly_summary(all_days)
    meal_plan_json = {"days": all_days, "weekly_summary": weekly_summary}

    # Step 7-8: Store in DB + generate markdown (same as before)
```

- **`_parse_custom_requests(notes)`**: Simple parser — split on day names, extract recipe requests per meal_type. Does not need to be perfect — unrecognized text passes as general `notes` to the LLM fallback prompt.
- **`_compute_weekly_summary(days)`**: Average `daily_totals` across 7 days → `{"average_calories": float, "average_protein_g": float, ...}`
- **NO `calculate_meal_plan_macros`**: DB recipes already have validated macros. LLM fallback recipes get macros validated at generation time in `generate_custom_recipe.py`. The old OFF-lookup-per-ingredient step is skipped entirely — this is the main performance win.
- **PATTERN**: Keep `fetch_my_profile_tool`, `update_my_profile_tool`, `generate_shopping_list_tool`, `fetch_stored_meal_plan_tool` unchanged
- **GOTCHA**: Output MUST match the Output Format Contract above — `plan_data.days[].meals[].ingredients[]` structure unchanged
- **VALIDATE**: `pytest tests/ -v` (all existing tests must pass)

### Task 14: UPDATE `src/agent.py` and `src/clients.py` — Anthropic client + new tools

- **UPDATE `src/clients.py`**: Add `get_anthropic_client()`:
```python
from anthropic import AsyncAnthropic

def get_anthropic_client() -> AsyncAnthropic:
    """Create Anthropic client for skill-level LLM calls (Sonnet 4.5)."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not found in environment variables")
    return AsyncAnthropic(api_key=api_key)
```

- **UPDATE `AgentDeps`**: Add `anthropic_client: any  # AsyncAnthropic (skills)` field. Initialize in `create_agent_deps()` with `get_anthropic_client()`.

- **UPDATE `generate_weekly_meal_plan`** (lines 390-434): Pass `ctx.deps.anthropic_client` instead of `ctx.deps.openai_client` to the refactored tool.

- **ADD** new tool `generate_custom_recipe`:
```python
async def generate_custom_recipe(
    ctx: RunContext[AgentDeps],
    recipe_request: str,
    meal_type: str = "dejeuner",
) -> str:
    """Generate a specific recipe on demand via Claude Sonnet 4.5."""
    logger.info(f"Tool called: generate_custom_recipe({recipe_request})")
    module = _import_skill_script("meal-planning", "generate_custom_recipe")
    return await module.execute(
        anthropic_client=ctx.deps.anthropic_client,
        supabase=ctx.deps.supabase,
        recipe_request=recipe_request,
        meal_type=meal_type,
    )
```

- **ADD**: Register in `core_tools`: `core_tools.add_function(generate_custom_recipe)`
- **VALIDATE**: `ruff check src/agent.py src/clients.py`

### Task 15: REWRITE `skills/meal-planning/SKILL.md`

- **IMPLEMENT**: Full rewrite with new day-by-day workflow :

```markdown
---
name: meal-planning
description: Generation de plans de repas via recipe DB + scaling mathematique. Generation jour par jour avec LLM fallback pour recettes personnalisees.
category: planning
---

# Meal Planning - Planification de Repas

## Quand utiliser

- L'utilisateur demande un plan de repas hebdomadaire
- L'utilisateur veut voir/récupérer un plan existant
- L'utilisateur demande une recette spécifique
- L'utilisateur demande une liste de courses

## Nouveau Workflow (Recipe DB + Day-by-Day)

### Architecture

Le skill utilise une **base de recettes pré-validées** avec macros calculés via OpenFoodFacts.
Pour chaque jour, le système sélectionne des recettes → scale les portions mathématiquement → valide.
LLM fallback utilise **Claude Sonnet 4.5** via Anthropic API.

### Pipeline par jour

1. `select_recipes` → Cherche recettes dans la DB (filtrage allergènes, variété, préférences)
2. `scale_portions` → Ajuste les quantités pour atteindre les macros cibles exactement
3. `validate_day` → Vérifie allergènes (tolérance zéro) et macros (±5% protéines, ±10% reste)
4. Si validation échoue → retry avec d'autres recettes (max 2 tentatives)

### LLM Fallback

Si l'utilisateur demande une recette spécifique (ex: "risotto aux champignons") :
- `generate_custom_recipe` → LLM génère → macros calculés via OFF → sauvegardé en DB

## Outils disponibles

| Outil | Script | Description |
|-------|--------|-------------|
| generate_weekly_meal_plan | `generate_day_plan.py` (×7) | Plan 7 jours jour par jour |
| generate_custom_recipe | `generate_custom_recipe.py` | Recette sur demande via LLM |
| fetch_stored_meal_plan | `fetch_stored_meal_plan.py` | Récupérer plan existant |
| generate_shopping_list | `generate_shopping_list.py` | Liste de courses |

[... rest of SKILL.md with parameters, examples, presentation format ...]
```

- **VALIDATE**: `pytest evals/test_skill_loading.py -v` (skill discovery must find updated skill)

### Task 16: REMOVE deprecated files

- **REMOVE**: `src/nutrition/fatsecret_client.py` (568 lines)
- **REMOVE**: Old `build_meal_plan_prompt()` function from `src/nutrition/meal_planning.py` (lines 51-537) — keep `build_meal_plan_prompt_simple()` for LLM fallback
- **VALIDATE**: `ruff check src/ && pytest tests/ -v`

### Task 17: CREATE `skills/meal-planning/references/recipe_schema.md`

- **IMPLEMENT**: Document the recipe data model for reference

### Task 18: ADD eval cases to `evals/test_skill_scripts.py`

- **ADD**: Eval cases for new scripts :
  - `select_recipes` — happy path, allergen exclusion, no matches
  - `scale_portions` — scaling up, scaling down, edge cases
  - `validate_day` — valid day, allergen violation, macro violation
  - `generate_day_plan` — full pipeline with mocks
- **PATTERN**: Existing eval pattern in `evals/test_skill_scripts.py`
- **VALIDATE**: `pytest evals/test_skill_scripts.py -v`

### Task 19: CREATE `tests/test_generate_day_plan.py`

- **IMPLEMENT**: Integration tests for the day plan pipeline :
  - `test_day_plan_from_recipe_db` — happy path, all recipes from DB
  - `test_day_plan_with_llm_fallback` — 1 slot falls back to LLM
  - `test_day_plan_allergen_safe` — no allergens in output
  - `test_day_plan_macro_accuracy` — macros within ±5% protein, ±10% rest
  - `test_day_plan_retry_on_failure` — retry logic works
  - `test_weekly_plan_variety` — 7 days, no recipe repetition
- **VALIDATE**: `pytest tests/test_generate_day_plan.py -v`

---

## TESTING STRATEGY

### Unit Tests

- `tests/test_portion_scaler.py` — Pure math scaling, rounding, edge cases
- `tests/test_recipe_db.py` — CRUD operations with mocked Supabase
- All existing tests in `tests/` must continue passing (no regressions)

### Integration Tests

- `tests/test_generate_day_plan.py` — Full pipeline with mocked DB + LLM
- `tests/test_meal_plan_workflow_integration.py` — Existing tests (verify compatibility)

### Edge Cases

- Recipe DB empty → all slots fall back to LLM
- User has many allergens → very few DB matches → LLM fallback heavy
- Extreme calorie targets (1200 kcal vs 4000 kcal) → scaling factor very high/low
- Countable ingredients (eggs) → must stay integer after scaling
- User requests recipe with allergenic ingredients → must reject and explain
- Scale factor > 2.0 or < 0.5 → clamp and warn

### Eval Cases (Pydantic-Evals)

- Added to `evals/test_skill_scripts.py` for each new script
- Minimum: 1 happy path + 1 edge case + 1 validation error per script

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style

```bash
ruff format src/ tests/ evals/ skills/
ruff check src/ tests/ evals/ skills/
```

**Expected**: 0 errors

### Level 2: Unit Tests

```bash
pytest tests/test_portion_scaler.py -v
pytest tests/test_recipe_db.py -v
pytest tests/test_generate_day_plan.py -v
```

**Expected**: All pass

### Level 3: Eval Tests

```bash
pytest evals/test_skill_loading.py -v
pytest evals/test_skill_scripts.py -v
```

**Expected**: All pass, including new eval cases

### Level 4: Full Test Suite (No Regressions)

```bash
pytest tests/ -v
pytest evals/ -v
```

**Expected**: All existing + new tests pass

### Level 5: Lint Everything

```bash
ruff check src/ tests/ evals/ skills/ --no-fix
```

**Expected**: 0 errors

---

## ACCEPTANCE CRITERIA

- [ ] Table `recipes` created in Supabase with proper indexes
- [ ] `ingredient_mapping` columns renamed from fatsecret to openfoodfacts
- [ ] `src/nutrition/portion_scaler.py` — Pure scaling math with tests passing
- [ ] `src/nutrition/recipe_db.py` — CRUD operations with tests passing
- [ ] All 6 new skill scripts in `skills/meal-planning/scripts/` — lint clean
- [ ] `generate_day_plan.py` orchestrates full day pipeline
- [ ] LLM fallback works when recipe not in DB
- [ ] Scaling produces macros within ±5% protein, ±10% carbs/fat
- [ ] Allergen zero tolerance enforced at every level
- [ ] `src/tools.py` refactored — old 400-line function replaced
- [ ] `fatsecret_client.py` deleted
- [ ] Old `build_meal_plan_prompt()` deleted (keep `build_meal_plan_prompt_simple`)
- [ ] SKILL.md rewritten with new workflow
- [ ] All existing tests pass (no regressions)
- [ ] New tests + evals added and passing
- [ ] `ruff check` passes with 0 errors
- [ ] `meal_plans` table output format unchanged (shopping list + fetch compatible)

---

## COMPLETION CHECKLIST

- [ ] Phase 1: Foundation (Tasks 1-6) — DB + domain logic
- [ ] Phase 2: Core Scripts (Tasks 7-12) — skill scripts
- [ ] Phase 3: Integration (Tasks 13-17) — agent + cleanup
- [ ] Phase 4: Testing (Tasks 18-19) — evals + integration tests
- [ ] All validation commands pass
- [ ] All acceptance criteria met

---

## NOTES

### Design Decisions

1. **Recipe DB over pure LLM** : Pre-validated macros eliminate the convergence problem of the optimizer. Mathematical scaling is deterministic — no more "best effort" that sometimes fails validation.

2. **Day-by-day over 7-at-once** : Smaller LLM calls (if needed), easier retry (just 1 day, not 7), progressive results, variety tracking via `exclude_recipe_ids`.

3. **Domain logic in `src/nutrition/`** : `portion_scaler.py` and `recipe_db.py` live in `src/nutrition/` because they are reusable domain logic. Skill scripts in `skills/meal-planning/scripts/` are orchestrators that call these modules.

4. **Keeping `build_meal_plan_prompt_simple`** : Reused by `generate_custom_recipe.py` for LLM fallback. The old `build_meal_plan_prompt` (500 lines) is deleted.

5. **Output format unchanged** : The `plan_data` JSONB stored in `meal_plans` table keeps the same structure (`days[].meals[].ingredients[]`) so `fetch_stored_meal_plan` and `generate_shopping_list` work without changes. Contract explicitly defined in "Output Format Contract" section.

6. **Claude Sonnet 4.5 for skill LLM calls** : All recipe generation (custom recipes, DB seeding) uses `claude-sonnet-4-5-20250929` via `anthropic.AsyncAnthropic`. Better structured output quality and cost-effectiveness vs GPT-4o. The Pydantic AI agent itself stays on its configured model — only skill scripts use Anthropic.

7. **Python-side allergen filtering** : Allergens filtered in Python after DB query, not via PostgreSQL array operators. Matches codebase patterns (zero array operator usage) and avoids Supabase client compatibility risk.

8. **Skip `calculate_meal_plan_macros` for DB recipes** : DB recipes have pre-validated macros → no need for per-ingredient OFF lookups at plan generation time. This is the main performance win (~50-100 OFF calls eliminated). LLM fallback recipes get macros validated at creation time in `generate_custom_recipe.py`.

### Key Risks (all mitigated)

- **Recipe DB cold start** : Mitigated — minimum 40 recipes (10/meal_type) before first use. `seed_recipe_db.py` is a prerequisite step (Task 12). Graceful degradation falls back to LLM if DB is sparse.
- **OFF coverage** : Mitigated — fallback uses cached values from `ingredient_mapping`. Recipes with unmatched ingredients get `off_validated = False` but are still usable.
- **Allergen filtering** : Mitigated — Python-side filtering (no Supabase array operators needed). Matches existing codebase patterns.

### Confidence Score: 10/10

High confidence because:
- Architecture is clear and well-decomposed
- Existing domain logic (validators, OFF client, formatter) is reused extensively
- Pure function approach for scaling eliminates I/O complexity
- Day-by-day approach is inherently more testable
- All previous risk factors resolved:
  - Allergen filtering uses proven Python-side approach (Gap 1 ✓)
  - `notes` → `custom_requests` parsing added to weekly wrapper (Gap 2 ✓)
  - Migration task validates DB state before acting (Gap 3 ✓)
  - Scale factor bounds imported from existing optimizer constants (Gap 4 ✓)
  - `calculate_meal_plan_macros` role clarified — skipped for DB recipes (Gap 5 ✓)
  - Graceful degradation defined for empty/sparse DB (Gap 6 ✓)
  - Output format contract explicitly locked (Gap 7 ✓)
  - LLM switched to Claude Sonnet 4.5 for all skill-level calls ✓
