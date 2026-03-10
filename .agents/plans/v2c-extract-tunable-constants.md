# Feature: v2c — Extract All Tunable Parameters as Named Constants

## User Story

As a **developer tuning the meal-planning pipeline**,
I want to **find all tunable parameters in one documented file**,
So that **I can understand what each lever does, where it's used, and change it in one place**.

## Problem Statement

The meal-planning pipeline contains ~18 inline magic numbers scattered across 6 files. These numbers control scoring weights, LLM parameters, search heuristics, calorie goal adjustments, and protein targets. When tuning the pipeline, developers must grep for bare floats/ints and guess their meaning.

## Solution Statement

Create a **single centralized file** `src/nutrition/constants.py` that contains ALL tunable parameters, organized by domain, with clear documentation for each constant: what it does, where it's used, and why it has that value.

All other files import from `constants.py`. No duplicates. One place to read, one place to change.

## Feature Metadata

**Feature Type**: Refactor
**Estimated Complexity**: Low
**Primary Systems Affected**: `src/nutrition/`, `skills/meal-planning/`, `skills/nutrition-calculating/`, `src/api.py`
**Dependencies**: None (pure refactor, no new libraries)
**Risk**: Zero — no logic changes, no API changes, no data changes.

---

## CONTEXT REFERENCES

### Relevant Codebase Files — MUST READ BEFORE IMPLEMENTING

- `src/nutrition/recipe_db.py` (lines 72-84, 148, 386-416, 419-477) — Why: Contains 8 of the 18 magic numbers (scoring weights, macro tolerance, fetch limit)
- `src/nutrition/calculations.py` (lines 223-281, 284-355) — Why: Contains protein intermediate targets (2.5, 2.0) and fat floor (0.6)
- `skills/nutrition-calculating/scripts/calculate_nutritional_needs.py` (lines 60-87) — Why: Contains calorie surplus/deficit values (+300, -500)
- `src/api.py` (lines 1230-1242) — Why: Contains duplicate calorie_adjustments dict
- `skills/meal-planning/scripts/generate_custom_recipe.py` (lines 39, 167-173, 251, 309) — Why: Contains LLM params (temperature, max_tokens) and prep time fallback
- `skills/meal-planning/scripts/generate_day_plan.py` (line 116) — Why: Contains prep time fallback (30)

### New Files to Create

- `src/nutrition/constants.py` — Single source of truth for all 18 tunable parameters

### Patterns to Follow

**Naming Convention:** `UPPER_SNAKE_CASE` at module level — matches existing pattern (`FRESHNESS_CAP_DAYS`, `WEIGHT_PROTEIN`, `MACRO_TOLERANCE_PROTEIN`, etc.)

**Import Convention:** Always use `src.` prefix — e.g., `from src.nutrition.constants import VARIETY_WEIGHT_MACRO_FIT`

**Comment Style:** One-line comment above each constant explaining what/where/why — matches `FRESHNESS_CAP_DAYS = 30.0  # Freshness decay caps at this many days` pattern

**Logging Pattern:** No logging needed (constants are passive values, not functions)

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation
Create `src/nutrition/constants.py` with all 18 constants, documented by domain.

### Phase 2: Core Implementation
Replace inline magic numbers with imports in all 6 consumer files.

### Phase 3: Integration
No integration needed — pure refactor, no new APIs or endpoints.

### Phase 4: Testing & Validation
Run existing test suite (no new tests needed), lint, type check, grep for leftover magic numbers.

---

## STEP-BY-STEP TASKS

### Task 1: CREATE `src/nutrition/constants.py`

- **IMPLEMENT**: Create the centralized constants file with ALL 18 constants, organized by domain section. Each constant gets a `UPPER_SNAKE_CASE` name and a comment explaining **what** it controls, **where** it's used (file + function), and **why** it has that value.
- **PATTERN**: Follow existing naming from `recipe_db.py:383` (`FRESHNESS_CAP_DAYS = 30.0`) and `portion_optimizer.py` (`WEIGHT_PROTEIN = 2.0`)
- **IMPORTS**: None (this file has no dependencies — only stdlib `dict` type hint)
- **GOTCHA**: `GOAL_CALORIE_ADJUSTMENTS` dict must reference the individual constants (`-WEIGHT_LOSS_DEFICIT_KCAL`, not `-500`) to stay DRY. Also `VARIETY_WEIGHT_*` values must sum to exactly 1.0.
- **VALIDATE**: `python -c "from src.nutrition.constants import VARIETY_WEIGHT_MACRO_FIT, GOAL_CALORIE_ADJUSTMENTS; print('OK')"`

Full file content:

```python
"""Tunable parameters for the nutrition pipeline.

Single source of truth for all configurable constants used across the meal-planning
and nutrition calculation pipeline. Organized by domain.

Each constant documents:
- What it controls
- Where it's used (file → function)
- Why it has that value (scientific reference or design rationale)

To tune the pipeline, modify values here — all dependent modules import from this file.
"""

# =============================================================================
# RECIPE SCORING — used by recipe_db.py → score_recipe_variety()
# =============================================================================
# These weights control how recipes are ranked when building a meal plan.
# They must sum to 1.0. Higher weight = more influence on recipe selection.

# How closely recipe macros match the target (protein/carb/fat ratios)
VARIETY_WEIGHT_MACRO_FIT = 0.40

# How recently the recipe was used (older = higher score, promotes variety)
VARIETY_WEIGHT_FRESHNESS = 0.30

# Whether the recipe matches user's preferred cuisine types
VARIETY_WEIGHT_CUISINE = 0.20

# How many times the recipe has been used overall (less used = higher score)
VARIETY_WEIGHT_USAGE = 0.10

# =============================================================================
# MACRO FIT SCORING — used by recipe_db.py → score_macro_fit()
# =============================================================================
# Protein deviation is weighted higher than carbs/fat because hitting protein
# targets is the #1 priority for all goals (muscle gain, weight loss, etc.)

# Multiplier for protein ratio deviation in macro fit score (1.0 = same as carbs/fat)
MACRO_FIT_PROTEIN_WEIGHT = 2.0

# =============================================================================
# RECIPE SEARCH — used by recipe_db.py → search_recipes()
# =============================================================================
# When searching for recipes, we fetch more than needed because Python-side
# filtering (allergens, disliked foods, variety scoring) reduces the pool.

# Default tolerance for macro ratio deviation (0.25 = ±25% from target ratios)
DEFAULT_MACRO_RATIO_TOLERANCE = 0.25

# fetch_limit = (limit × MULTIPLIER) + len(exclude_ids) + PADDING
FETCH_LIMIT_MULTIPLIER = 3
FETCH_LIMIT_PADDING = 10

# =============================================================================
# CALORIE GOAL ADJUSTMENTS — used by:
#   - skills/nutrition-calculating/scripts/calculate_nutritional_needs.py
#   - src/api.py → calculate endpoint
# =============================================================================
# Applied to TDEE to get target daily calories based on the user's goal.
# Conservative values chosen for sustainability and adherence.

# Caloric surplus for muscle gain (kcal/day above TDEE)
# 300 kcal = moderate surplus for lean gains without excessive fat
MUSCLE_GAIN_SURPLUS_KCAL = 300

# Caloric deficit for weight loss (kcal/day below TDEE)
# 500 kcal ≈ ~0.45 kg/week loss — sustainable without muscle wasting
WEIGHT_LOSS_DEFICIT_KCAL = 500

# Caloric surplus for performance goals (kcal/day above TDEE)
# 200 kcal = mild surplus to fuel training without weight gain focus
PERFORMANCE_SURPLUS_KCAL = 200

# Full mapping used by api.py for quick lookup
GOAL_CALORIE_ADJUSTMENTS: dict[str, int] = {
    "weight_loss": -WEIGHT_LOSS_DEFICIT_KCAL,
    "muscle_gain": MUSCLE_GAIN_SURPLUS_KCAL,
    "maintenance": 0,
    "performance": PERFORMANCE_SURPLUS_KCAL,
}

# =============================================================================
# PROTEIN TARGETS — used by calculations.py → calculate_protein_target()
# =============================================================================
# "Intermediate" starting values within the ISSN ranges. Used by default
# instead of the range maximum for more realistic initial recommendations.

# Weight loss: middle of 2.3–3.1 range — better adherence than jumping to 3.1
PROTEIN_INTERMEDIATE_WEIGHT_LOSS = 2.5  # g/kg body weight

# Muscle gain: high-middle of 1.6–2.2 range — evidence shows diminishing returns above 2.0
PROTEIN_INTERMEDIATE_MUSCLE_GAIN = 2.0  # g/kg body weight

# =============================================================================
# FAT FLOOR — used by calculations.py → calculate_macros()
# =============================================================================
# Minimum fat intake regardless of calorie target. Below this threshold,
# hormonal function is impaired (testosterone, estrogen synthesis).

# ISSN guideline: minimum 0.6 g/kg body weight for hormonal health
MIN_FAT_G_PER_KG = 0.6

# =============================================================================
# LLM RECIPE GENERATION — used by generate_custom_recipe.py
# =============================================================================
# Parameters for the Anthropic API call that generates custom recipes
# when no existing recipe matches the user's request.

# Max tokens for recipe generation response (typical recipe = ~800 tokens)
RECIPE_MAX_TOKENS = 2000

# Temperature controls creativity vs consistency (0.0 = deterministic, 1.0 = creative)
# 0.7 = balanced: enough variation for diverse recipes, enough consistency for valid JSON
RECIPE_TEMPERATURE = 0.7

# =============================================================================
# DEFAULT PREP TIME — used by:
#   - skills/meal-planning/scripts/generate_custom_recipe.py
#   - skills/meal-planning/scripts/generate_day_plan.py → _build_meal_from_scaled_recipe()
# =============================================================================
# Fallback when a recipe has no prep_time_minutes field.
# 30 min = reasonable average for a home-cooked meal.

DEFAULT_PREP_TIME_MINUTES = 30
```

### Task 2: UPDATE `src/nutrition/recipe_db.py` — import and replace 8 values

- **IMPLEMENT**: Add import block, replace 8 inline magic numbers:
  1. `0.40`, `0.30`, `0.20`, `0.10` in `score_recipe_variety()` return (lines 472-476)
  2. `2 *` in `score_macro_fit()` (line 412) → `MACRO_FIT_PROTEIN_WEIGHT *`
  3. `0.25` in `search_recipes()` signature (line 84) → `DEFAULT_MACRO_RATIO_TOLERANCE`
  4. `3` and `10` in fetch_limit formula (line 148) → `FETCH_LIMIT_MULTIPLIER`, `FETCH_LIMIT_PADDING`
- **PATTERN**: Existing imports at `recipe_db.py:16-17` — add new import block after them
- **IMPORTS**:
  ```python
  from src.nutrition.constants import (
      DEFAULT_MACRO_RATIO_TOLERANCE,
      FETCH_LIMIT_MULTIPLIER,
      FETCH_LIMIT_PADDING,
      MACRO_FIT_PROTEIN_WEIGHT,
      VARIETY_WEIGHT_CUISINE,
      VARIETY_WEIGHT_FRESHNESS,
      VARIETY_WEIGHT_MACRO_FIT,
      VARIETY_WEIGHT_USAGE,
  )
  ```
- **GOTCHA**: The `2 *` on line 412 is an integer literal — the constant is `2.0` (float). This is fine because Python auto-promotes, but ensure the replacement uses the constant name not a re-typed value. Also don't touch the `4` and `9` in Atwater calorie conversion (lines 402-404) — those are physical constants, not tunable parameters.
- **VALIDATE**: `python -m pytest tests/test_recipe_db.py -x -q`

### Task 3: UPDATE `src/nutrition/calculations.py` — import and replace 3 values

- **IMPLEMENT**: Add import block, replace 3 inline magic numbers:
  1. `2.5` on line 258 → `PROTEIN_INTERMEDIATE_WEIGHT_LOSS`
  2. `2` on line 261 → `PROTEIN_INTERMEDIATE_MUSCLE_GAIN`
  3. `0.6` on line 335 → `MIN_FAT_G_PER_KG`
- **PATTERN**: Existing imports at `calculations.py:13-14` — add new import after them
- **IMPORTS**:
  ```python
  from src.nutrition.constants import (
      MIN_FAT_G_PER_KG,
      PROTEIN_INTERMEDIATE_MUSCLE_GAIN,
      PROTEIN_INTERMEDIATE_WEIGHT_LOSS,
  )
  ```
- **GOTCHA**: Don't touch `PROTEIN_KCAL = 4`, `CARB_KCAL = 4`, `FAT_KCAL = 9` inside `calculate_macros()` (lines 317-319) — these are physical constants (Atwater factors), not tunable parameters. Also don't touch `FAT_PCT_OF_TOTAL` dict (lines 323-328) — it's already a named constant.
- **VALIDATE**: `python -m pytest tests/test_calculations.py -x -q`

### Task 4: UPDATE `skills/nutrition-calculating/scripts/calculate_nutritional_needs.py` — import and replace 2 values

- **IMPLEMENT**: Add import block, replace 2 inline magic numbers:
  1. `300` on line 73 → `MUSCLE_GAIN_SURPLUS_KCAL`
  2. `500` on line 75 → `WEIGHT_LOSS_DEFICIT_KCAL`
- **PATTERN**: Existing imports at top of file — add new import block
- **IMPORTS**:
  ```python
  from src.nutrition.constants import (
      MUSCLE_GAIN_SURPLUS_KCAL,
      WEIGHT_LOSS_DEFICIT_KCAL,
  )
  ```
- **GOTCHA**: This skill script uses `kwargs.get()` pattern. The import goes at file level, not inside `execute()`. Verify the existing import style of the file before adding.
- **VALIDATE**: `python -m pytest tests/test_calculations.py -x -q` (this file's logic is tested via calculation tests)

### Task 5: UPDATE `src/api.py` — import and replace calorie adjustments dict

- **IMPLEMENT**: Replace the inline `calorie_adjustments` dict (lines 1232-1237) with imported `GOAL_CALORIE_ADJUSTMENTS`. Delete the local dict definition and use the import directly.
- **PATTERN**: `api.py` already has many imports from `src.nutrition.*` at the top — add to existing import block
- **IMPORTS**:
  ```python
  from src.nutrition.constants import GOAL_CALORIE_ADJUSTMENTS
  ```
- **GOTCHA**: The local dict uses string keys `"weight_loss"`, `"muscle_gain"`, `"maintenance"`, `"performance"`. Verify these match exactly with the centralized dict keys. Also check if the variable name `calorie_adjustments` is referenced elsewhere in the same function — if so, assign `calorie_adjustments = GOAL_CALORIE_ADJUSTMENTS` or replace all references.
- **VALIDATE**: `python -m pytest tests/test_api.py -x -q`

### Task 6: UPDATE `skills/meal-planning/scripts/generate_custom_recipe.py` — import and replace 3 values

- **IMPLEMENT**: Add import block, replace 3 inline magic numbers:
  1. `max_tokens=2000` on line ~170 → `max_tokens=RECIPE_MAX_TOKENS`
  2. `temperature=0.7` on line ~171 → `temperature=RECIPE_TEMPERATURE`
  3. `30` in three places (line ~39 Pydantic default, line ~251 dict.get fallback, line ~309 dict.get fallback) → `DEFAULT_PREP_TIME_MINUTES`
- **PATTERN**: File already has constants at top (`RECIPE_MODEL`, `MAX_RECIPE_REQUEST_LENGTH`, `_OFF_CONCURRENCY`) — the new imports replace inline values, not these existing constants
- **IMPORTS**:
  ```python
  from src.nutrition.constants import (
      DEFAULT_PREP_TIME_MINUTES,
      RECIPE_MAX_TOKENS,
      RECIPE_TEMPERATURE,
  )
  ```
- **GOTCHA**: The Pydantic `Field(default=30)` on line ~39 must become `Field(default=DEFAULT_PREP_TIME_MINUTES)`. Pydantic accepts variable references in `default=` — this is safe. Don't confuse with `default_factory` which is for mutable defaults only.
- **VALIDATE**: `python -m pytest tests/test_generate_custom_recipe.py -x -q`

### Task 7: UPDATE `skills/meal-planning/scripts/generate_day_plan.py` — import and replace 1 value

- **IMPLEMENT**: Add import, replace 1 inline magic number:
  1. `30` on line ~116 in `_build_meal_from_scaled_recipe()` → `DEFAULT_PREP_TIME_MINUTES`
- **PATTERN**: File already imports constants at top and defines its own (`CALORIE_RANGE_MIN_DIVISOR`, etc.) — add the new import alongside
- **IMPORTS**:
  ```python
  from src.nutrition.constants import DEFAULT_PREP_TIME_MINUTES
  ```
- **GOTCHA**: Don't touch `CALORIE_RANGE_MIN_DIVISOR`, `MAX_MULTIPLIER`, `MACRO_RATIO_TOLERANCE_STRICT`, `MACRO_RATIO_TOLERANCE_WIDE`, `MAX_RETRIES`, `LLM_FALLBACK_WARN_THRESHOLD` — they're already named constants local to this file and are NOT in scope for v2c.
- **VALIDATE**: `python -m pytest tests/test_generate_day_plan.py -x -q`

### Task 8: CLEANUP v1 LP optimizer — move `_extract_recipe_macros`, delete v1

- **WHY**: `portion_optimizer.py` (v1) is dead code since v2f replaced it with `portion_optimizer_v2.py`. The only active dependency is `_extract_recipe_macros` imported by v2's `_fallback_uniform()`. Cleaning this up during v2c avoids centralizing constants from a dead module.
- **IMPLEMENT**:
  1. **Copy `_extract_recipe_macros`** from `portion_optimizer.py` into `portion_optimizer_v2.py` (it's a small pure function — no external deps beyond dict access)
  2. **Update the import** in `portion_optimizer_v2.py:420`: remove `from src.nutrition.portion_optimizer import _extract_recipe_macros` (now local)
  3. **Move `WEIGHT_PROTEIN/FAT/CALORIES/CARBS/MEAL_BALANCE`** from `portion_optimizer_v2.py` into `constants.py` (they're the MILP objective weights)
  4. **Move `ROLE_BOUNDS`, `MAX_GROUP_DIVERGENCE`, `DIVERGENCE_PAIRS`, `DISCRETE_UNITS`** from `ingredient_roles.py` into `constants.py` (tunable MILP parameters). Keep `INGREDIENT_ROLES`, `ROLE_EXCEPTIONS`, and the matching functions in `ingredient_roles.py` (those are domain data, not tunable numbers).
  5. **Delete `src/nutrition/portion_optimizer.py`** (v1 — all functions dead)
  6. **Delete `tests/test_portion_optimizer.py`** (tests for dead code)
  7. **Update `meal_plan_optimizer.py`** if it still re-exports from v1
- **GOTCHA**: Grep for any remaining `from src.nutrition.portion_optimizer import` (without `_v2`) across the entire codebase before deleting. If any live code still imports v1, fix it first.
- **VALIDATE**:
  ```bash
  # Verify no imports from deleted module
  grep -r "from src.nutrition.portion_optimizer import" src/ skills/ tests/ --include="*.py" | grep -v "_v2"
  # Run all tests
  python -m pytest tests/ -x -q
  ```

### Task 9: Run full validation

```bash
# Format and lint
ruff format src/ tests/ skills/ && ruff check src/ tests/ skills/

# Type check
mypy src/

# All tests (pure refactor — all must pass unchanged)
python -m pytest tests/ -x -q

# Verify no remaining bare magic numbers in modified function bodies
grep -n '\b0\.[0-9]\+\b' src/nutrition/recipe_db.py src/nutrition/calculations.py
grep -n '\b0\.[0-9]\+\b' skills/meal-planning/scripts/generate_custom_recipe.py
grep -n '\b0\.[0-9]\+\b' skills/nutrition-calculating/scripts/calculate_nutritional_needs.py
```

---

## Summary of All Constants

| Constant | Value | Domain | Used in |
|----------|-------|--------|---------|
| `VARIETY_WEIGHT_MACRO_FIT` | 0.40 | Scoring | `recipe_db.py` → `score_recipe_variety()` |
| `VARIETY_WEIGHT_FRESHNESS` | 0.30 | Scoring | `recipe_db.py` → `score_recipe_variety()` |
| `VARIETY_WEIGHT_CUISINE` | 0.20 | Scoring | `recipe_db.py` → `score_recipe_variety()` |
| `VARIETY_WEIGHT_USAGE` | 0.10 | Scoring | `recipe_db.py` → `score_recipe_variety()` |
| `MACRO_FIT_PROTEIN_WEIGHT` | 2.0 | Scoring | `recipe_db.py` → `score_macro_fit()` |
| `DEFAULT_MACRO_RATIO_TOLERANCE` | 0.25 | Search | `recipe_db.py` → `search_recipes()` |
| `FETCH_LIMIT_MULTIPLIER` | 3 | Search | `recipe_db.py` → `search_recipes()` |
| `FETCH_LIMIT_PADDING` | 10 | Search | `recipe_db.py` → `search_recipes()` |
| `MUSCLE_GAIN_SURPLUS_KCAL` | 300 | Calories | `calculate_nutritional_needs.py`, `api.py` |
| `WEIGHT_LOSS_DEFICIT_KCAL` | 500 | Calories | `calculate_nutritional_needs.py`, `api.py` |
| `PERFORMANCE_SURPLUS_KCAL` | 200 | Calories | `api.py` |
| `GOAL_CALORIE_ADJUSTMENTS` | dict | Calories | `api.py` |
| `PROTEIN_INTERMEDIATE_WEIGHT_LOSS` | 2.5 | Protein | `calculations.py` → `calculate_protein_target()` |
| `PROTEIN_INTERMEDIATE_MUSCLE_GAIN` | 2.0 | Protein | `calculations.py` → `calculate_protein_target()` |
| `MIN_FAT_G_PER_KG` | 0.6 | Fat | `calculations.py` → `calculate_macros()` |
| `RECIPE_MAX_TOKENS` | 2000 | LLM | `generate_custom_recipe.py` |
| `RECIPE_TEMPERATURE` | 0.7 | LLM | `generate_custom_recipe.py` |
| `DEFAULT_PREP_TIME_MINUTES` | 30 | Defaults | `generate_custom_recipe.py`, `generate_day_plan.py` |
| `WEIGHT_PROTEIN` | 2.0 | MILP | `portion_optimizer_v2.py` → objective function |
| `WEIGHT_FAT` | 2.0 | MILP | `portion_optimizer_v2.py` → objective function |
| `WEIGHT_CALORIES` | 1.0 | MILP | `portion_optimizer_v2.py` → objective function |
| `WEIGHT_CARBS` | 0.5 | MILP | `portion_optimizer_v2.py` → objective function |
| `WEIGHT_MEAL_BALANCE` | 1.5 | MILP | `portion_optimizer_v2.py` → objective function |
| `ROLE_BOUNDS` | dict | MILP | `ingredient_roles.py` → per-role scaling limits |
| `MAX_GROUP_DIVERGENCE` | 2.0 | MILP | `ingredient_roles.py` → inter-group coherence |
| `DIVERGENCE_PAIRS` | list | MILP | `ingredient_roles.py` → constrained role pairs |
| `DISCRETE_UNITS` | set | MILP | `ingredient_roles.py` → integer variable units |

**Total: 27 named constants, 1 new file (`src/nutrition/constants.py`), 8 files modified, 2 files deleted (`portion_optimizer.py` + its tests).**

---

## Already Named (Do NOT Re-Extract)

These are already proper named constants and need no changes:

- `MACRO_TOLERANCE_PROTEIN/FAT/CALORIES/CARBS` — `validators.py`
- `WEIGHT_PROTEIN/FAT/CALORIES/CARBS/MEAL_BALANCE` — `portion_optimizer_v2.py` → **TO CENTRALIZE in Task 8** (v1 copy deleted in same task)
- `MIN_SCALE_FACTOR / MAX_SCALE_FACTOR` — `meal_plan_optimizer.py`
- `ROLE_BOUNDS` — `ingredient_roles.py` → **TO CENTRALIZE in Task 8**
- `MAX_GROUP_DIVERGENCE` (2.0) — `ingredient_roles.py` → **TO CENTRALIZE in Task 8**
- `DIVERGENCE_PAIRS` — `ingredient_roles.py` → **TO CENTRALIZE in Task 8**
- `DISCRETE_UNITS` — `ingredient_roles.py` → **TO CENTRALIZE in Task 8**
- `FRESHNESS_CAP_DAYS` — `recipe_db.py`
- `SNACK_STRUCTURE_CALORIE_THRESHOLD` — `generate_week_plan.py`
- `CALORIE_RANGE_MIN_DIVISOR / MAX_MULTIPLIER` — `generate_day_plan.py`
- `MACRO_RATIO_TOLERANCE_STRICT / WIDE` — `generate_day_plan.py`
- `MAX_RETRIES / LLM_FALLBACK_WARN_THRESHOLD` — `generate_day_plan.py`
- `RECIPE_MODEL / MAX_RECIPE_REQUEST_LENGTH` — `generate_custom_recipe.py`
- `_OFF_CONCURRENCY` — `generate_custom_recipe.py`
- ~~`FAT_INGREDIENT_MIN_SCALE / FAT_SURPLUS_THRESHOLD` — `fat_rebalancer.py`~~ **DELETED in v2f** — file no longer exists
- `MAX_CALORIE_ADJUSTMENT / MAX_PROTEIN_ADJUSTMENT_G / MAX_CARB_ADJUSTMENT_G / MAX_FAT_ADJUSTMENT_G` — `adjustments.py`
- `ACTIVITY_MULTIPLIERS / PROTEIN_TARGETS / FAT_PCT_OF_TOTAL` — `calculations.py`
- `MIN_CALORIES_WOMEN / MIN_CALORIES_MEN` — safety constraints (hardcoded by design)

**Note:** `FRESHNESS_CAP_DAYS` stays in `recipe_db.py` — it's already well-named and only used locally. Moving it to `constants.py` is optional (future cleanup). Same for the other already-named constants above.

---

## Design Decisions

1. **Single file `src/nutrition/constants.py`** — one place to read everything, one place to change values. No more grepping across 6 files.
2. **No duplicates.** `MUSCLE_GAIN_SURPLUS_KCAL` and `DEFAULT_PREP_TIME_MINUTES` are defined once and imported everywhere.
3. **Documented for newcomers.** Each section has a header explaining the domain, and each constant has a comment explaining what/where/why. A developer reading `constants.py` top-to-bottom understands the full tuning surface.
4. **No logic changes.** Every constant is a direct 1:1 extraction of the inline value.
5. **Existing named constants stay in place.** Only the 18 unnamed magic numbers move. The already-named constants (`FRESHNESS_CAP_DAYS`, `MACRO_TOLERANCE_*`, etc.) stay where they are — moving them is optional future cleanup.

---

## Testing Strategy

Pure refactor with zero behavioral change:

### Unit Tests
**No new tests needed.** All existing tests must pass unchanged — the values are identical, only the source location changed.

### Integration Tests
Not applicable — no new features, APIs, or data flows.

### Edge Cases
- Verify `GOAL_CALORIE_ADJUSTMENTS` dict references the individual constants (not hardcoded ints) so changing `WEIGHT_LOSS_DEFICIT_KCAL` automatically updates the dict
- Verify `VARIETY_WEIGHT_*` values sum to exactly 1.0
- Verify Pydantic `Field(default=DEFAULT_PREP_TIME_MINUTES)` works correctly (not confused with `default_factory`)

---

## Validation Commands

### Level 1: Syntax & Style
```bash
ruff format src/ tests/ skills/ && ruff check src/ tests/ skills/
```

### Level 2: Type Check
```bash
mypy src/
```

### Level 3: Full Test Suite
```bash
python -m pytest tests/ -x -q
```

### Level 4: Grep Verification
```bash
# Verify no remaining bare magic numbers in modified function bodies
grep -n '\b0\.[0-9]\+\b' src/nutrition/recipe_db.py src/nutrition/calculations.py
grep -n '\b0\.[0-9]\+\b' skills/meal-planning/scripts/generate_custom_recipe.py
grep -n '\b0\.[0-9]\+\b' skills/nutrition-calculating/scripts/calculate_nutritional_needs.py
```

---

## Acceptance Criteria

- [ ] `src/nutrition/constants.py` created with all 27 constants, organized by domain
- [ ] Each constant has a clear comment (what it controls, where used, why this value)
- [ ] All 8 consumer files import from `constants.py` instead of using inline values
- [ ] No duplicate constant definitions across files
- [ ] No behavioral changes — all values are identical to the originals
- [ ] `portion_optimizer.py` (v1) deleted, `_extract_recipe_macros` moved to v2
- [ ] `tests/test_portion_optimizer.py` deleted (tested dead code)
- [ ] No remaining `from src.nutrition.portion_optimizer import` (without `_v2`) in live code
- [ ] `ruff format` + `ruff check` pass
- [ ] `mypy src/` passes
- [ ] All existing tests pass (`python -m pytest tests/ -x -q`)
- [ ] 1 new file created (`src/nutrition/constants.py`), 8 files modified, 2 files deleted

---

## Completion Checklist

- [ ] All 9 tasks completed in order
- [ ] Each task validation passed immediately after completion:
  - [ ] Task 1: `python -c "from src.nutrition.constants import ..."` OK
  - [ ] Task 2: `python -m pytest tests/test_recipe_db.py -x -q` OK
  - [ ] Task 3: `python -m pytest tests/test_calculations.py -x -q` OK
  - [ ] Task 4: `python -m pytest tests/test_calculations.py -x -q` OK
  - [ ] Task 5: `python -m pytest tests/test_api.py -x -q` OK
  - [ ] Task 6: `python -m pytest tests/test_generate_custom_recipe.py -x -q` OK
  - [ ] Task 7: `python -m pytest tests/test_generate_day_plan.py -x -q` OK
  - [ ] Task 8: v1 cleanup — no orphan imports, all tests pass
  - [ ] Task 9: Full validation suite passed
- [ ] `ruff format` + `ruff check` — zero errors
- [ ] `mypy src/` — zero errors
- [ ] Full test suite — all pass, zero regressions
- [ ] Grep verification — no remaining bare magic numbers in function bodies
- [ ] All acceptance criteria met

---

## Notes

- Atwater conversion factors (`4` for protein/carbs, `9` for fat) are **physical constants**, not tunable parameters — they must NOT be extracted.
- `MIN_CALORIES_WOMEN = 1200` and `MIN_CALORIES_MEN = 1500` are **safety constraints** hardcoded by design — they must NOT be extracted to a tunable file.
- Future cleanup: move the remaining already-named constants (`FRESHNESS_CAP_DAYS`, `MACRO_TOLERANCE_*`, etc.) into `constants.py` for full centralization. Out of scope for v2c.
- **v2f impact (2026-03-10):** `fat_rebalancer.py` was deleted (replaced by MILP in `portion_optimizer_v2.py`). Its constants `FAT_INGREDIENT_MIN_SCALE` and `FAT_SURPLUS_THRESHOLD` no longer exist. New tunable constants from v2f live in `ingredient_roles.py` (`ROLE_BOUNDS`, `MAX_GROUP_DIVERGENCE`, `DIVERGENCE_PAIRS`, `DISCRETE_UNITS`) and `portion_optimizer_v2.py` (`WEIGHT_*`). These are already well-named but should be centralized in `constants.py` during v2c execution.
