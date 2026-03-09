# Feature: v2b — Inter-Meal Macro Compensation (Sliding Budget)

## Problem

Recipe selection treats each meal independently with identical macro ratio targets. The LP scales whole recipes by a single factor — it cannot boost protein in one meal without also boosting fat/carbs. Result: low-protein breakfasts can't be compensated, fatty custom recipes leave no room to adjust.

## Solution

Make recipe selection **sequential with a sliding ratio budget**. After each recipe is selected, compute what macro ratios the remaining slots need to hit the daily target. Pass these adjusted ratios to `search_recipes()`. The LP solver stays unchanged — better candidates in → better optimization out.

**Why ratios, not grams:** The LP scales recipes (factor 0.5–3.0), changing absolute grams. But a recipe's macro RATIOS (e.g., 40% fat) are preserved by scaling. Ratios are the right tracking unit.

**Why calorie-weighted:** A collation at 10% of daily calories barely shifts ratios; a main meal at 35% has high impact. Weighting by `slot_target_calories / daily_calories` captures this correctly.

## Scope

- **1 file modified**: `generate_day_plan.py` — 3 pure helpers + `select_recipes()` loop refactor
- **1 file created**: `tests/test_sliding_budget.py`
- **0 changes** to LP solver, recipe_db, API, data structures

---

## MUST READ BEFORE IMPLEMENTING

- `skills/meal-planning/scripts/generate_day_plan.py` — entire file, especially `select_recipes()` (lines 341-390) and `_select_recipe_for_slot()` (lines 151-338)
- `src/nutrition/recipe_db.py` (lines 72-241) — `search_recipes()` with `target_macro_ratios` param
- `src/nutrition/meal_type_utils.py` — `normalize_meal_type()` already imported

---

## The Math

```
Daily target ratios: protein_ratio=0.25, fat_ratio=0.25, carb_ratio=0.50
Slot calorie shares (from meal_distribution, FIXED):
  petit-déj: 500/2000 = 0.25
  déjeuner:  700/2000 = 0.35
  dîner:     600/2000 = 0.30
  collation: 200/2000 = 0.10

Slot 1 selected (déjeuner, share=0.35) → recipe fat_ratio = 0.40

Required fat_ratio for remaining slots:
  consumed_weighted = 0.40 × 0.35 = 0.14
  remaining_share = 0.25 + 0.30 + 0.10 = 0.65
  required = (0.25 - 0.14) / 0.65 = 0.169

→ search_recipes(target_macro_ratios = {fat_ratio: 0.169, ...})
```

If required ratio goes negative (extreme overshoot), clamp to 0 — the LP handles the rest.

---

## Selection Order

Process **fixed-macro slots first** (batch reuse, custom requests), then flexible DB slots by **target_calories descending** (larger meals = more room to compensate).

**Batch cooking**: On Jour 1 of a batch block, déjeuner is selected freely, then dîner is selected with adjusted ratios that compensate the déjeuner. On Jours 2+, forced recipes are processed first as "fixed" slots, and flexible slots (collations, varied breakfast) compensate.

**Custom recipes**: User-requested custom recipes are treated as "fixed" (processed first, ratios tracked). LLM fallback (no DB match) gets the slot's original targets — no special adjustment needed, the compensation happens on the other slots.

**Repair loop**: Unchanged. It re-runs `scale_portions()` globally after swapping. The sliding budget improves initial selection quality so repair is needed less often. Complementary, not dependent.

---

## STEP-BY-STEP TASKS

### Task 1: ADD `_recipe_macro_ratios()` in `generate_day_plan.py`

After the existing helpers section (around line 144).

```python
def _recipe_macro_ratios(recipe: dict) -> dict[str, float]:
    """Extract caloric macro ratios from a recipe's per-serving values.

    Ratios are invariant to LP scaling (proportional scaling preserves ratios).
    """
    cal = recipe.get("calories_per_serving", 0) or 1
    return {
        "protein_ratio": (recipe.get("protein_g_per_serving", 0) * 4) / cal,
        "fat_ratio": (recipe.get("fat_g_per_serving", 0) * 9) / cal,
        "carb_ratio": (recipe.get("carbs_g_per_serving", 0) * 4) / cal,
    }
```

### Task 2: ADD `_compute_required_ratios()` in `generate_day_plan.py`

```python
def _compute_required_ratios(
    daily_target_ratios: dict[str, float],
    consumed_slots: list[dict],
    remaining_cal_shares: list[float],
) -> dict[str, float] | None:
    """Compute required macro ratios for remaining slots via calorie-weighted compensation.

    Args:
        daily_target_ratios: {protein_ratio, fat_ratio, carb_ratio} (kcal/kcal)
        consumed_slots: [{"cal_share": float, "recipe_ratios": {protein_ratio, ...}}]
        remaining_cal_shares: [0.25, 0.30, 0.10] — calorie shares of unprocessed slots

    Returns:
        {protein_ratio, fat_ratio, carb_ratio} for remaining slots, or None if empty.
    """
    if not remaining_cal_shares:
        return None

    remaining_share = sum(remaining_cal_shares)
    if remaining_share <= 0:
        return None

    required = {}
    for macro in ("protein_ratio", "fat_ratio", "carb_ratio"):
        consumed_weighted = sum(
            s["recipe_ratios"].get(macro, 0) * s["cal_share"]
            for s in consumed_slots
        )
        raw = (daily_target_ratios.get(macro, 0) - consumed_weighted) / remaining_share
        required[macro] = max(0.0, raw)

    return required
```

**Simplification vs previous plan**: removed `daily_calories` param (unused in ratio math), `remaining_slots` simplified to `remaining_cal_shares` (just a list of floats — no need for dicts).

### Task 3: ADD `_determine_selection_order()` in `generate_day_plan.py`

```python
def _determine_selection_order(
    meal_targets: list[dict],
    custom_requests: dict,
    batch_recipe_ids: dict[str, str] | None,
) -> list[int]:
    """Fixed-macro slots first, then by target_calories descending."""
    fixed = []
    flexible = []

    for i, slot in enumerate(meal_targets):
        meal_type = normalize_meal_type(slot.get("meal_type", ""))
        is_batch = batch_recipe_ids and meal_type in batch_recipe_ids
        is_custom = any(
            normalize_meal_type(k) == meal_type for k in (custom_requests or {})
        )
        if is_batch or is_custom:
            fixed.append(i)
        else:
            flexible.append(i)

    flexible.sort(key=lambda i: meal_targets[i].get("target_calories", 0), reverse=True)
    return fixed + flexible
```

### Task 4: UPDATE `select_recipes()` — sliding budget loop

**CURRENT** (lines 341-390): iterates `meal_targets` in order, each slot gets same ratios.

**NEW**: compute daily target ratios, determine processing order, track consumed ratios, pass adjusted `target_macro_ratios` to `_select_recipe_for_slot()`.

Key changes to `_select_recipe_for_slot()`:
- Add optional param `target_macro_ratios_override: dict[str, float] | None = None`
- If provided, use it instead of computing ratios from `meal_slot` (lines 216-226)
- Everything else stays the same (calorie_range, fallback cascade, LLM fallback)

```python
async def select_recipes(
    supabase,
    anthropic_client,
    meal_targets: list[dict],
    user_profile: dict,
    exclude_recipe_ids: list[str],
    custom_requests: dict,
    batch_recipe_ids: dict[str, str] | None = None,
) -> list[dict]:
    """Step 2: Select one recipe per meal slot with inter-meal macro compensation."""
    generate_custom_recipe_module = _import_sibling_script("generate_custom_recipe")
    used_ids = list(exclude_recipe_ids)

    # Compute daily target ratios from all slots
    daily_calories = sum(m.get("target_calories", 0) for m in meal_targets)
    daily_target_ratios = {
        "protein_ratio": sum(m.get("target_protein_g", 0) for m in meal_targets) * 4
        / max(daily_calories, 1),
        "fat_ratio": sum(m.get("target_fat_g", 0) for m in meal_targets) * 9
        / max(daily_calories, 1),
        "carb_ratio": sum(m.get("target_carbs_g", 0) for m in meal_targets) * 4
        / max(daily_calories, 1),
    }

    # Calorie share per slot (fixed by meal_distribution)
    cal_shares = [
        m.get("target_calories", 0) / max(daily_calories, 1) for m in meal_targets
    ]

    # Process fixed-macro slots first, then flexible by calories desc
    ordered_indices = _determine_selection_order(
        meal_targets, custom_requests, batch_recipe_ids
    )

    consumed_slots: list[dict] = []
    assignments: list[dict | None] = [None] * len(meal_targets)

    for position, idx in enumerate(ordered_indices):
        meal_slot = meal_targets[idx]

        # Compute adjusted ratios from what's been consumed
        remaining_shares = [cal_shares[j] for j in ordered_indices[position:]]
        required_ratios = _compute_required_ratios(
            daily_target_ratios, consumed_slots, remaining_shares
        )
        adjusted_ratios = required_ratios or daily_target_ratios

        logger.info(
            f"  Slot {position + 1}/{len(ordered_indices)} "
            f"({meal_slot.get('meal_type', '?')}): "
            f"target ratios P={adjusted_ratios['protein_ratio']:.2f} "
            f"F={adjusted_ratios['fat_ratio']:.2f} "
            f"C={adjusted_ratios['carb_ratio']:.2f}"
        )

        # Select recipe with adjusted macro ratios
        recipe, is_llm, runner_ups = await _select_recipe_for_slot(
            supabase=supabase,
            anthropic_client=anthropic_client,
            meal_slot=meal_slot,
            user_profile=user_profile,
            used_ids=used_ids,
            custom_request=_find_custom_request(custom_requests, meal_slot),
            generate_custom_recipe_module=generate_custom_recipe_module,
            batch_recipe_id=(batch_recipe_ids or {}).get(
                normalize_meal_type(meal_slot.get("meal_type", ""))
            ),
            target_macro_ratios_override=adjusted_ratios,
        )

        if recipe:
            if "id" in recipe:
                used_ids.append(recipe["id"])
            assignments[idx] = {
                "meal_slot": meal_slot,
                "recipe": recipe,
                "is_llm": is_llm,
                "runner_ups": runner_ups,
            }
            consumed_slots.append({
                "cal_share": cal_shares[idx],
                "recipe_ratios": _recipe_macro_ratios(recipe),
            })
        else:
            logger.error(
                f"Could not get any recipe for {meal_slot.get('meal_type', '?')}"
            )

    return [a for a in assignments if a is not None]
```

**GOTCHA**: `calorie_range` stays from the original `meal_slot["target_calories"]` — slot size is fixed by meal_distribution. Only `target_macro_ratios` changes.

**GOTCHA**: `_select_recipe_for_slot` needs a new optional `target_macro_ratios_override` param. When set, skip the internal ratio computation (lines 216-226) and use the override instead.

### Task 5: UPDATE `_select_recipe_for_slot()` — accept ratio override

Add `target_macro_ratios_override: dict[str, float] | None = None` to the signature.

Replace lines 216-226:
```python
# BEFORE:
target_macro_ratios = None
if target_calories > 0:
    target_fat_g = meal_slot.get("target_fat_g", 0)
    # ...

# AFTER:
target_macro_ratios = target_macro_ratios_override
if target_macro_ratios is None and target_calories > 0:
    target_fat_g = meal_slot.get("target_fat_g", 0)
    target_carbs_g = meal_slot.get("target_carbs_g", 0)
    target_protein_g = meal_slot.get("target_protein_g", 0)
    if target_fat_g and target_carbs_g:
        target_macro_ratios = {
            "fat_ratio": (target_fat_g * 9) / target_calories,
            "carb_ratio": (target_carbs_g * 4) / target_calories,
            "protein_ratio": (target_protein_g * 4) / target_calories,
        }
```

This keeps backward compatibility — if no override, falls back to original behavior.

### Task 6: CREATE `tests/test_sliding_budget.py`

```python
"""Tests for v2b sliding budget helpers."""

import sys
from pathlib import Path

import pytest

sys.path.insert(
    0,
    str(Path(__file__).resolve().parent.parent / "skills" / "meal-planning" / "scripts"),
)

from generate_day_plan import (
    _compute_required_ratios,
    _determine_selection_order,
    _recipe_macro_ratios,
)


class TestRecipeMacroRatios:
    def test_balanced_recipe(self):
        recipe = {
            "calories_per_serving": 400,
            "protein_g_per_serving": 25,   # 100 kcal = 25%
            "fat_g_per_serving": 11,       # 99 kcal ~ 25%
            "carbs_g_per_serving": 50,     # 200 kcal = 50%
        }
        ratios = _recipe_macro_ratios(recipe)
        assert ratios["protein_ratio"] == pytest.approx(0.25, abs=0.01)
        assert ratios["fat_ratio"] == pytest.approx(0.25, abs=0.01)

    def test_high_fat_recipe(self):
        recipe = {
            "calories_per_serving": 500,
            "protein_g_per_serving": 20,
            "fat_g_per_serving": 28,       # 252 kcal ~ 50%
            "carbs_g_per_serving": 42,
        }
        assert _recipe_macro_ratios(recipe)["fat_ratio"] > 0.45

    def test_zero_calories_no_crash(self):
        recipe = {"calories_per_serving": 0, "protein_g_per_serving": 0,
                  "fat_g_per_serving": 0, "carbs_g_per_serving": 0}
        assert _recipe_macro_ratios(recipe)["protein_ratio"] == 0


class TestComputeRequiredRatios:
    DAILY = {"protein_ratio": 0.25, "fat_ratio": 0.25, "carb_ratio": 0.50}

    def test_no_consumed_returns_daily_target(self):
        result = _compute_required_ratios(self.DAILY, [], [0.33, 0.33, 0.34])
        assert result["protein_ratio"] == pytest.approx(0.25, abs=0.01)

    def test_fatty_meal_lowers_fat_requirement(self):
        consumed = [{"cal_share": 0.35, "recipe_ratios": {
            "protein_ratio": 0.20, "fat_ratio": 0.40, "carb_ratio": 0.40}}]
        result = _compute_required_ratios(self.DAILY, consumed, [0.25, 0.30, 0.10])
        # (0.25 - 0.40×0.35) / 0.65 = 0.169
        assert result["fat_ratio"] == pytest.approx(0.169, abs=0.01)
        # (0.25 - 0.20×0.35) / 0.65 = 0.276
        assert result["protein_ratio"] == pytest.approx(0.276, abs=0.01)

    def test_collation_low_impact(self):
        consumed = [{"cal_share": 0.10, "recipe_ratios": {
            "protein_ratio": 0.15, "fat_ratio": 0.50, "carb_ratio": 0.35}}]
        result = _compute_required_ratios(self.DAILY, consumed, [0.35, 0.30, 0.25])
        # (0.25 - 0.50×0.10) / 0.90 = 0.222 — barely shifted
        assert result["fat_ratio"] == pytest.approx(0.222, abs=0.01)

    def test_main_meal_high_impact(self):
        consumed = [{"cal_share": 0.35, "recipe_ratios": {
            "protein_ratio": 0.15, "fat_ratio": 0.30, "carb_ratio": 0.55}}]
        result = _compute_required_ratios(self.DAILY, consumed, [0.35, 0.20, 0.10])
        # (0.25 - 0.15×0.35) / 0.65 = 0.304
        assert result["protein_ratio"] == pytest.approx(0.304, abs=0.01)

    def test_overshoot_clamped_to_zero(self):
        consumed = [{"cal_share": 0.60, "recipe_ratios": {
            "protein_ratio": 0.20, "fat_ratio": 0.50, "carb_ratio": 0.30}}]
        result = _compute_required_ratios(self.DAILY, consumed, [0.40])
        assert result["fat_ratio"] == 0.0

    def test_two_consumed_meals(self):
        consumed = [
            {"cal_share": 0.30, "recipe_ratios": {
                "protein_ratio": 0.20, "fat_ratio": 0.35, "carb_ratio": 0.45}},
            {"cal_share": 0.35, "recipe_ratios": {
                "protein_ratio": 0.30, "fat_ratio": 0.20, "carb_ratio": 0.50}},
        ]
        result = _compute_required_ratios(self.DAILY, consumed, [0.25, 0.10])
        # (0.25 - 0.35×0.30 - 0.20×0.35) / 0.35 = 0.214
        assert result["fat_ratio"] == pytest.approx(0.214, abs=0.01)

    def test_empty_remaining_returns_none(self):
        assert _compute_required_ratios(self.DAILY, [], []) is None

    def test_single_remaining_absorbs_all(self):
        consumed = [
            {"cal_share": 0.35, "recipe_ratios": {
                "protein_ratio": 0.20, "fat_ratio": 0.40, "carb_ratio": 0.40}},
            {"cal_share": 0.35, "recipe_ratios": {
                "protein_ratio": 0.22, "fat_ratio": 0.30, "carb_ratio": 0.48}},
        ]
        result = _compute_required_ratios(self.DAILY, consumed, [0.30])
        assert result is not None
        assert result["fat_ratio"] < 0.25


class TestDetermineSelectionOrder:
    def test_fixed_first_then_by_calories(self):
        meals = [
            {"meal_type": "Petit-déjeuner", "target_calories": 500},
            {"meal_type": "Déjeuner", "target_calories": 800},
            {"meal_type": "Dîner", "target_calories": 700},
        ]
        order = _determine_selection_order(meals, {"diner": "burger"}, None)
        assert order[0] == 2   # Dîner first (custom)
        assert order[1] == 1   # Déjeuner (800 kcal)
        assert order[2] == 0   # Petit-déj (500 kcal)

    def test_batch_treated_as_fixed(self):
        meals = [
            {"meal_type": "Petit-déjeuner", "target_calories": 500},
            {"meal_type": "Déjeuner", "target_calories": 800},
        ]
        order = _determine_selection_order(meals, {}, {"petit-dejeuner": "uuid"})
        assert order[0] == 0

    def test_no_fixed_all_by_calories_desc(self):
        meals = [
            {"meal_type": "Collation", "target_calories": 200},
            {"meal_type": "Déjeuner", "target_calories": 800},
            {"meal_type": "Dîner", "target_calories": 700},
        ]
        assert _determine_selection_order(meals, {}, None) == [1, 2, 0]

    def test_collation_last(self):
        meals = [
            {"meal_type": "Collation", "target_calories": 200},
            {"meal_type": "Petit-déjeuner", "target_calories": 500},
            {"meal_type": "Déjeuner", "target_calories": 700},
        ]
        order = _determine_selection_order(meals, {}, None)
        assert order[-1] == 0
```

### Task 7: RUN validation

```bash
ruff format src/ tests/ skills/ && ruff check src/ tests/ skills/
python -m pytest tests/test_sliding_budget.py -v
python -m pytest tests/ -x -q
```

---

## Design Decisions

1. **Ratios, not grams**: LP scaling preserves ratios — tracking grams would be invalidated after optimization.
2. **Calorie-weighted**: Meals and collations have different daily calorie shares. A 10% collation barely shifts ratios; a 35% main meal shifts them significantly.
3. **Fixed-macro first**: Batch reuse and custom recipes have predetermined macros. Process them first so the budget reflects reality.
4. **LP unchanged**: The sliding budget improves recipe SELECTION. The LP still optimizes globally. Better candidates in → easier LP problem → better results.
5. **Repair unchanged**: Repair re-runs the LP globally after swapping. Sliding budget and repair are complementary.
6. **No budget guards**: User may want a big custom meal. The system compensates on other slots instead of rejecting.
7. **No custom recipe target adjustment**: Custom recipes get the slot's original targets. Compensation happens on OTHER meals.

## Guard Rails

- **Overshoot clamping**: If consumed exceeds target on a macro, required ratio is clamped to 0.0 (not negative). The LP handles residual imbalance.
- **Fallback to daily ratios**: If `_compute_required_ratios` returns `None` (e.g., no remaining slots), use the original `daily_target_ratios`.
- **`_select_recipe_for_slot` backward compat**: The `target_macro_ratios_override` param is optional. Without it, existing behavior is preserved.
- **No mutation of meal_targets**: Calorie shares are stored in a separate list, not injected into the slot dicts.

## Acceptance Criteria

- [ ] `_recipe_macro_ratios()` extracts correct ratios, handles zero-cal
- [ ] `_compute_required_ratios()` produces correct compensated ratios with calorie weighting
- [ ] `_determine_selection_order()` processes fixed slots first, flexible by calories desc
- [ ] `select_recipes()` passes adjusted ratios to each slot sequentially
- [ ] Batch-reused and custom recipes are tracked in `consumed_slots`
- [ ] Overshoot clamps to 0, no crash
- [ ] LP solver is NOT modified
- [ ] All existing tests pass
- [ ] New unit tests pass
- [ ] `ruff format` + `ruff check` pass
