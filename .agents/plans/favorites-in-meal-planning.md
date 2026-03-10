# Feature: Favoris dans le meal-planning pipeline

The following plan should be complete, but validate documentation and codebase patterns before implementing.

Pay special attention to naming of existing utils, types, and models. Import from the right files.

## Feature Description

Integrate user favorite recipes into the meal-planning pipeline at two levels:
1. **Niveau 1 (implicite)** — Favorite recipes get a scoring boost in `score_recipe_variety()`, making them surface naturally in generated meal plans
2. **Niveau 2 (custom request)** — When a user requests a specific recipe by name (custom_request), the pipeline checks favorites first before falling back to LLM generation

## User Story

As a user with saved favorite recipes
I want my favorites to appear more often in my meal plans, and to be able to request them by name
So that my meal plans reflect my actual preferences and I don't get a newly generated recipe when I already have a saved version

## Problem Statement

Favorites are currently passive bookmarks — they don't influence meal plan generation at all. The `search_recipes()` and `score_recipe_variety()` functions have no awareness of user favorites. When a user requests a specific recipe via custom_request, the pipeline always generates a new one via LLM, even if the user has a matching favorite.

## Solution Statement

- **Niveau 1**: Add a `favorite_recipe_ids` parameter to `score_recipe_variety()` that applies a bonus (new constant `VARIETY_WEIGHT_FAVORITE`). Thread `user_id` from `generate_week_plan` → `generate_day_plan` → scoring calls.
- **Niveau 2**: In `_select_recipe_for_slot()`, before the LLM custom recipe generation block, query `favorite_recipes` with `ilike` on the recipe name. If a match is found, use it directly. If not, fall back to LLM generation (current behavior unchanged).

## Feature Metadata

**Feature Type**: Enhancement
**Estimated Complexity**: Low-Medium
**Primary Systems Affected**: `src/nutrition/recipe_db.py`, `src/nutrition/constants.py`, `skills/meal-planning/scripts/generate_day_plan.py`, `skills/meal-planning/scripts/generate_week_plan.py`
**Dependencies**: None (uses existing Supabase client and `favorite_recipes` table)

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ BEFORE IMPLEMENTING

- `src/nutrition/recipe_db.py` (lines 447-505) — `score_recipe_variety()`: 4-factor scoring, this is where the favorite bonus goes
- `src/nutrition/recipe_db.py` (lines 82-95) — `search_recipes()` signature: needs no changes (scoring happens downstream)
- `src/nutrition/constants.py` (lines 14-30) — `VARIETY_WEIGHT_*` constants: the 4 weights that must sum to 1.0. Adding a 5th requires rebalancing.
- `skills/meal-planning/scripts/generate_day_plan.py` (lines 227-237) — `_select_recipe_for_slot()` signature: where `user_id` must be threaded
- `skills/meal-planning/scripts/generate_day_plan.py` (lines 264-287) — Custom request → LLM block: insert favorite lookup BEFORE this
- `skills/meal-planning/scripts/generate_day_plan.py` (lines 371-384) — DB recipe scoring: where `score_recipe_variety()` is called with `preferred_cuisines`
- `skills/meal-planning/scripts/generate_day_plan.py` (lines 412-505) — `select_recipes()`: orchestrator that calls `_select_recipe_for_slot` per meal
- `skills/meal-planning/scripts/generate_day_plan.py` (lines 861-900) — `execute()`: receives kwargs including `user_profile`
- `skills/meal-planning/scripts/generate_week_plan.py` (lines 206-208) — `user_id = kwargs.get("user_id")`: already available
- `skills/meal-planning/scripts/generate_week_plan.py` (lines 354-365) — Day plan call: where `user_id` must be forwarded
- `tests/test_recipe_db.py` — Test patterns for `score_recipe_variety()` and `search_recipes()` (mock Supabase)
- `tests/test_generate_day_plan.py` — Test patterns for day plan pipeline (mock Supabase + Anthropic)

### New Files to Create

None — all changes are in existing files.

### Patterns to Follow

**Constant naming** (from `constants.py`):
```python
# SECTION_HEADER comment, then constant with docstring
VARIETY_WEIGHT_FAVORITE = 0.15  # value
```

**Scoring pattern** (from `score_recipe_variety`):
```python
# Each factor is a float in [0.0, 1.0], multiplied by its weight
return (
    VARIETY_WEIGHT_MACRO_FIT * macro_score
    + VARIETY_WEIGHT_FRESHNESS * freshness_score
    + ...
)
```

**Threading kwargs** (from `generate_day_plan.py`):
```python
# extract from kwargs, pass to downstream functions
user_id = kwargs.get("user_id")
```

**Supabase query pattern** (from `recipe_db.py`):
```python
result = supabase.table("favorite_recipes").select("recipe_id").eq("user_id", user_id).execute()
```

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation — Constants + helper function

Add the favorite boost constant and a helper to fetch user's favorite recipe IDs.

### Phase 2: Niveau 1 — Implicit favorite boost in scoring

Modify `score_recipe_variety()` to accept `favorite_recipe_ids` and apply a bonus. Thread `user_id` through the pipeline so favorite IDs are available at scoring time.

### Phase 3: Niveau 2 — Favorite lookup on custom requests

In `_select_recipe_for_slot()`, before the LLM generation block, query favorites by name. If found, return the favorite recipe directly.

### Phase 4: Testing

Unit tests for the new scoring behavior and favorite lookup.

---

## STEP-BY-STEP TASKS

### Task 1: ADD constant `VARIETY_WEIGHT_FAVORITE` in `src/nutrition/constants.py`

- **IMPLEMENT**: Add a new constant in the RECIPE SCORING section:
  ```python
  # Bonus when recipe is in user's favorites (promotes recipes the user explicitly saved)
  VARIETY_WEIGHT_FAVORITE = 0.15
  ```
- **SCORING APPROACH**: Additive bonus — keep existing 4 weights as-is (sum = 1.0), add favorite bonus on top. Score can exceed 1.0 but that's fine: it's only used for `sort()` ranking, never compared to an absolute threshold. A favorite recipe scoring 1.15 vs a non-favorite at 0.95 just means the favorite ranks higher. Users without favorites get bonus = 0, so their scoring is identical to today — zero regression risk.
- **VALIDATE**: `python -c "from src.nutrition.constants import VARIETY_WEIGHT_FAVORITE; print(VARIETY_WEIGHT_FAVORITE)"`

### Task 2: ADD `get_user_favorite_ids()` in `src/nutrition/recipe_db.py`

- **IMPLEMENT**: New function after `search_recipes()`:
  ```python
  def get_user_favorite_ids(supabase: Client, user_id: str | None) -> set[str]:
      """Fetch the set of recipe IDs favorited by a user.

      Returns empty set if user_id is None (CLI mode, no favorites).
      """
      if not user_id:
          return set()
      result = (
          supabase.table("favorite_recipes")
          .select("recipe_id")
          .eq("user_id", user_id)
          .execute()
      )
      return {row["recipe_id"] for row in (result.data or [])}
  ```
- **PATTERN**: Follow `get_recipe_by_id()` style (sync Supabase query, returns data)
- **NOTE**: Sync, not async — matches all other Supabase queries in this file. Called once per week plan, cached for the entire generation.
- **VALIDATE**: `python -m pytest tests/test_recipe_db.py -x -q`

### Task 3: UPDATE `score_recipe_variety()` in `src/nutrition/recipe_db.py`

- **IMPLEMENT**: Add optional `favorite_recipe_ids` parameter:
  ```python
  def score_recipe_variety(
      recipe: dict,
      meal_target: dict,
      preferred_cuisines: list[str] | None = None,
      now: datetime | None = None,
      favorite_recipe_ids: set[str] | None = None,  # NEW
  ) -> float:
  ```
- **IMPLEMENT**: After the 4 existing factors (before the `return`), add:
  ```python
  # Factor 5: Favorite bonus (additive, not weighted against others)
  favorite_bonus = VARIETY_WEIGHT_FAVORITE if (
      favorite_recipe_ids and recipe.get("id") in favorite_recipe_ids
  ) else 0.0
  ```
- **IMPLEMENT**: Update return:
  ```python
  return (
      VARIETY_WEIGHT_MACRO_FIT * macro_score
      + VARIETY_WEIGHT_FRESHNESS * freshness_score
      + VARIETY_WEIGHT_CUISINE * cuisine_score
      + VARIETY_WEIGHT_USAGE * usage_score
      + favorite_bonus
  )
  ```
- **IMPORTS**: Add `VARIETY_WEIGHT_FAVORITE` to the constants import
- **GOTCHA**: The new parameter is optional with default `None` — all existing callers (tests, repair step) work unchanged. Zero regression risk.
- **VALIDATE**: `python -m pytest tests/test_recipe_db.py -x -q`

### Task 4: UPDATE `generate_day_plan.py` — Thread `user_id` and `favorite_ids`

This is the main wiring task. Several sub-steps:

**4a. `execute()` (line ~886)**: Extract `user_id` from kwargs
```python
user_id = kwargs.get("user_id")  # NEW — for favorite recipe lookup
```

**4b. `execute()` (~line 916)**: Fetch favorite IDs once, before the pipeline runs
```python
from src.nutrition.recipe_db import get_user_favorite_ids
favorite_ids = get_user_favorite_ids(supabase, user_id)
```

**4c. `select_recipes()` (line ~412)**: Add `favorite_ids` parameter
```python
async def select_recipes(
    supabase,
    anthropic_client,
    meal_targets: list[dict],
    user_profile: dict,
    exclude_recipe_ids: list[str],
    custom_requests: dict,
    batch_recipe_ids: dict[str, str] | None = None,
    user_id: str | None = None,          # NEW
    favorite_ids: set[str] | None = None,  # NEW
) -> list[dict]:
```

**4d. `_select_recipe_for_slot()` (line ~227)**: Add `user_id` and `favorite_ids` parameters
```python
async def _select_recipe_for_slot(
    supabase,
    anthropic_client,
    meal_slot: dict,
    user_profile: dict,
    used_ids: list[str],
    custom_request: str | None,
    generate_custom_recipe_module,
    batch_recipe_id: str | None = None,
    target_macro_ratios_override: dict[str, float] | None = None,
    user_id: str | None = None,          # NEW
    favorite_ids: set[str] | None = None,  # NEW
) -> tuple[dict | None, bool, list[dict]]:
```

**4e. Scoring calls** (lines ~372-374 and ~381): Pass `favorite_ids` to `score_recipe_variety()`
```python
candidates.sort(
    key=lambda r: score_recipe_variety(r, meal_slot, preferred_cuisines, favorite_recipe_ids=favorite_ids),
    reverse=True,
)
```
Also update the logging line (~381) that calls `score_recipe_variety` for display.

**4f. `select_recipes()` call to `_select_recipe_for_slot()`** (~line 472): Forward params
```python
recipe, is_llm, runner_ups = await _select_recipe_for_slot(
    ...
    user_id=user_id,
    favorite_ids=favorite_ids,
)
```

**4g. `execute()` call to `select_recipes()`** (~line 916): Forward params
```python
assignments = await select_recipes(
    ...
    user_id=user_id,
    favorite_ids=favorite_ids,
)
```

**4h. Repair step** (`_repair_worst_meal`, ~line 714): Also pass `favorite_ids` — it calls `_select_recipe_for_slot` internally. Add param to function signature and forward it.

- **GOTCHA**: All new params are optional with `None` defaults — existing tests that don't pass them will work unchanged.
- **VALIDATE**: `python -m pytest tests/test_generate_day_plan.py -x -q`

### Task 5: UPDATE `generate_week_plan.py` — Forward `user_id` to day plan

- **IMPLEMENT**: In the daily loop (~line 354), add `user_id` to the `generate_day_plan.execute()` call:
  ```python
  day_result_str = await generate_day_plan.execute(
      supabase=supabase,
      anthropic_client=anthropic_client,
      ...
      user_id=user_id,  # NEW — for favorite recipe boost
  )
  ```
- **NOTE**: `user_id` is already extracted at line 208. Just needs forwarding.
- **VALIDATE**: `python -m pytest tests/test_generate_week_plan.py -x -q`

### Task 6: IMPLEMENT Niveau 2 — Favorite lookup on custom request

In `_select_recipe_for_slot()`, **before** the existing custom request block (line 264):

```python
# Custom request → check favorites first, then LLM fallback
if custom_request:
    # Niveau 2: Try to match a favorite recipe by name
    if user_id:
        fav_result = (
            supabase.table("favorite_recipes")
            .select("recipe_id, recipes(*)")
            .eq("user_id", user_id)
            .execute()
        )
        if fav_result.data:
            # Case-insensitive substring match on recipe name
            query_lower = custom_request.lower()
            for fav in fav_result.data:
                recipe_data = fav.get("recipes")
                if recipe_data and query_lower in recipe_data.get("name", "").lower():
                    logger.info(
                        f"  {meal_type_display}: favorite match '{recipe_data['name']}' "
                        f"for custom request '{custom_request}'"
                    )
                    return recipe_data, False, []

    # No favorite match → LLM generation (existing behavior)
    logger.info(
        f"  {meal_type_display}: custom recipe requested '{custom_request}'"
    )
    ...existing LLM code...
```

- **DESIGN DECISION**: Python-side `in` matching instead of SQL `ilike` because:
  1. The favorites list is small (typically <50 recipes per user)
  2. We already fetched it for niveau 1; we can reuse by passing the full favorites data (or just re-query — it's one small Supabase call)
  3. Avoids complex Supabase join + ilike syntax on nested relations

- **ALTERNATIVE**: If we want to avoid a second Supabase call, we can pass the full favorites data (not just IDs) from `execute()`. But that means changing `favorite_ids: set[str]` to `favorite_recipes: list[dict]` everywhere. Simpler to do a second lightweight query here since custom_requests are rare (most meals have no custom request).

- **GOTCHA**: The `custom_request` flow runs BEFORE the DB search flow. The favorite lookup must also run before the LLM call. The order is: batch_recipe_id → **favorite lookup (NEW)** → LLM custom → DB search → LLM fallback.
- **VALIDATE**: `python -m pytest tests/test_generate_day_plan.py -x -q`

### Task 7: ADD unit tests

**7a. Test favorite bonus in scoring** — `tests/test_recipe_db.py`:
```python
def test_score_variety_favorite_bonus():
    """Favorite recipes get a scoring bonus."""
    recipe = {
        "id": "fav-1",
        "calories_per_serving": 500,
        "protein_g_per_serving": 35,
        "carbs_g_per_serving": 50,
        "fat_g_per_serving": 15,
    }
    meal_target = {"target_calories": 500, "target_protein_g": 35, "target_carbs_g": 50, "target_fat_g": 15}

    score_without = score_recipe_variety(recipe, meal_target)
    score_with = score_recipe_variety(recipe, meal_target, favorite_recipe_ids={"fav-1"})

    assert score_with > score_without
    assert score_with - score_without == pytest.approx(VARIETY_WEIGHT_FAVORITE, abs=0.01)


def test_score_variety_no_bonus_when_not_favorite():
    """Non-favorite recipes are unaffected."""
    recipe = {"id": "other-1", ...}
    meal_target = {...}

    score_without = score_recipe_variety(recipe, meal_target)
    score_with = score_recipe_variety(recipe, meal_target, favorite_recipe_ids={"fav-1"})

    assert score_with == score_without
```

**7b. Test `get_user_favorite_ids()`** — `tests/test_recipe_db.py`:
```python
def test_get_user_favorite_ids_returns_set():
    mock = make_supabase_mock([{"recipe_id": "a"}, {"recipe_id": "b"}])
    result = get_user_favorite_ids(mock, "user-1")
    assert result == {"a", "b"}

def test_get_user_favorite_ids_no_user():
    result = get_user_favorite_ids(MagicMock(), None)
    assert result == set()
```

**7c. Test favorite lookup on custom request** — `tests/test_generate_day_plan.py`:
- Mock Supabase to return a favorite matching the custom_request name
- Verify the favorite recipe is returned (not LLM-generated)
- Test no-match case: LLM fallback is called

- **VALIDATE**: `python -m pytest tests/test_recipe_db.py tests/test_generate_day_plan.py -x -q`

### Task 8: ADD scoring logs in `_select_recipe_for_slot()`

When a recipe is selected from DB, log the favorite bonus impact:

```python
fav_tag = " [FAVORI]" if (favorite_ids and recipe.get("id") in favorite_ids) else ""
base_score = score_recipe_variety(recipe, meal_slot, preferred_cuisines)
full_score = score_recipe_variety(recipe, meal_slot, preferred_cuisines, favorite_recipe_ids=favorite_ids)
logger.info(
    f"  {meal_type_display}: DB recipe '{recipe['name']}'{fav_tag} "
    f"(score={full_score:.3f}, base={base_score:.3f}, "
    f"fav_bonus={full_score - base_score:.3f}, "
    f"fallback_level={fallback_level})"
)
```

This replaces the existing log line (~line 378-383) and makes it easy to verify in logs that favorites are being boosted.

- **VALIDATE**: `python -m pytest tests/test_generate_day_plan.py -x -q`

### Task 9: Lint + type check

- **VALIDATE**: `ruff format src/nutrition/recipe_db.py src/nutrition/constants.py skills/meal-planning/scripts/generate_day_plan.py skills/meal-planning/scripts/generate_week_plan.py tests/test_recipe_db.py tests/test_generate_day_plan.py && ruff check src/nutrition/recipe_db.py src/nutrition/constants.py skills/meal-planning/scripts/generate_day_plan.py skills/meal-planning/scripts/generate_week_plan.py`

### Task 10: Run `/run-eval` — Verify agent behavior with favorites

Create and run evals to validate both levels:

**Eval 1 — Niveau 2 (explicite)**: User asks "Génère-moi un plan de 3 jours, mets mon poulet tikka masala mardi midi". Pre-condition: user has a favorite recipe named "Poulet Tikka Masala". Expected: the plan for Tuesday lunch contains the favorite recipe (not an LLM-generated one). Check logs for `[FAVORI]` tag and `favorite match` log line.

**Eval 2 — Niveau 1 (implicite)**: User asks "Génère-moi un plan de 3 jours". Pre-condition: user has 5+ favorite recipes across meal types. Expected: favorites appear more frequently than non-favorites. Check logs for `fav_bonus=0.150` on favorite recipes vs `fav_bonus=0.000` on non-favorites. The scoring boost should be visible even if not every favorite ends up selected (macro/allergen constraints may override).

Use `/run-eval` skill to create the eval files and run them.

---

## TESTING STRATEGY

### Unit Tests

- `score_recipe_variety()` with and without `favorite_recipe_ids` — verify bonus is applied correctly
- `get_user_favorite_ids()` — happy path + None user_id
- Favorite lookup in `_select_recipe_for_slot()` — match found vs no match

### Integration Tests (existing, must not regress)

- `tests/test_generate_day_plan.py` — full pipeline with mocked clients
- `tests/test_generate_week_plan.py` — week plan generation
- `tests/test_sliding_budget.py` — macro compensation

### Edge Cases

- User with no favorites → `favorite_ids = set()` → no bonus, no lookup, identical to current behavior
- User with favorites but none matching meal_type/constraints → favorites get boost but may still be excluded by allergen/disliked/macro filters
- Custom request matches multiple favorites → first match wins (acceptable — small list)
- CLI mode (no user_id) → `get_user_favorite_ids` returns empty set → no change

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style
```bash
ruff format src/nutrition/recipe_db.py src/nutrition/constants.py skills/meal-planning/scripts/generate_day_plan.py skills/meal-planning/scripts/generate_week_plan.py
ruff check src/nutrition/recipe_db.py src/nutrition/constants.py skills/meal-planning/scripts/generate_day_plan.py skills/meal-planning/scripts/generate_week_plan.py
```

### Level 2: Unit Tests
```bash
python -m pytest tests/test_recipe_db.py tests/test_generate_day_plan.py tests/test_generate_week_plan.py tests/test_sliding_budget.py -x -q
```

### Level 3: Full Test Suite
```bash
python -m pytest tests/ -x -q
```

### Level 4: Evals (`/run-eval`)
- Eval 1 (explicite): user demande une recette favorite par nom → le plan utilise le favori, pas le LLM
- Eval 2 (implicite): user génère un plan normalement → les logs montrent `fav_bonus=0.150` sur les favoris, et ceux-ci remontent dans le classement

---

## ACCEPTANCE CRITERIA

- [ ] `VARIETY_WEIGHT_FAVORITE` constant defined in `constants.py`
- [ ] `get_user_favorite_ids()` function works (with and without user_id)
- [ ] `score_recipe_variety()` applies bonus for favorite recipes
- [ ] `user_id` threaded from `generate_week_plan` → `generate_day_plan` → scoring
- [ ] Custom requests check favorites before LLM fallback
- [ ] No favorite match → falls back to LLM (current behavior preserved)
- [ ] All new params are optional with `None` defaults (zero regression)
- [ ] All existing tests pass unchanged
- [ ] New tests cover bonus scoring, favorite lookup, and edge cases
- [ ] Scoring logs show `[FAVORI]` tag and `fav_bonus` values
- [ ] `/run-eval` passes: explicite (favorite used on custom request) + implicite (bonus visible in logs)
- [ ] Linting passes (`ruff format` + `ruff check`)

---

## COMPLETION CHECKLIST

- [ ] All 10 tasks completed in order
- [ ] Level 1 validation: ruff format + check clean
- [ ] Level 2 validation: targeted tests pass
- [ ] Level 3 validation: full test suite passes
- [ ] Level 4 validation: `/run-eval` — agent uses favorites explicitly + implicitly
- [ ] Scoring logs show `fav_bonus` values in meal plan generation
- [ ] All acceptance criteria met

---

## NOTES

### Design Decisions

1. **Additive bonus**: The favorite bonus (0.15) is added on top of the existing 4-factor score (sum = 1.0). Score can exceed 1.0 — no issue since it's only used for `sort()` ranking, never compared to a threshold. Users without favorites get bonus = 0, identical scoring to today.

2. **Python-side name matching for Niveau 2**: Instead of SQL `ilike` on a Supabase join, we fetch all user favorites and match in Python. The favorites list is small (<50 typically), so this is efficient and avoids complex Supabase query syntax.

3. **Optional params everywhere**: All new parameters default to `None`, ensuring zero changes needed in existing callers (tests, repair step, CLI mode).

4. **One-query cache pattern**: `get_user_favorite_ids()` is called once in `execute()` and the result is passed down the pipeline. Not called per-slot.

### Risk Assessment

- **Low risk**: All changes are additive. Existing behavior is preserved when `favorite_ids` is `None`.
- **Only risk**: Niveau 2 name matching might be too strict ("poulet tikka" won't match "Poulet Tikka Masala with Basmati"). The `in` operator with `.lower()` handles this since "poulet tikka" is contained in "poulet tikka masala with basmati". The real failure mode is reversed: user says "mon poulet" → too vague → no match → LLM generates. This is acceptable (same as current behavior).
