"""Generate a complete meal plan for a single day.

Pipeline: select_recipes → scale_portions → validate_day → repair (if needed).
DB recipes are pre-validated via OFF (Phase 0) so no runtime OFF calls needed.

Source: Refactored from monolithic generate_day_plan.py
"""

import importlib.util
import json
import logging
import re
import time
from pathlib import Path

from src.nutrition.constants import (
    DEFAULT_PREP_TIME_MINUTES,
    MACRO_RATIO_TOLERANCE_STRICT,
    MACRO_RATIO_TOLERANCE_WIDE,
    MACRO_TOLERANCE_CALORIES,
    MACRO_TOLERANCE_CARBS,
    MACRO_TOLERANCE_FAT,
    MACRO_TOLERANCE_PROTEIN,
)
from src.nutrition.portion_optimizer_v2 import (
    apply_ingredient_scale_factors,
    optimize_day_portions_v2,
)
from src.nutrition.portion_scaler import scale_recipe_to_targets
from src.nutrition.recipe_db import (
    get_recipe_by_id,
    get_user_favorite_ids,
    increment_usage,
    score_recipe_variety,
    search_recipes,
)
from src.nutrition.meal_type_utils import normalize_meal_type
from src.nutrition.validators import (
    find_worst_meal,
    validate_allergens,
    validate_daily_macros,
)

logger = logging.getLogger(__name__)


# Day names in French
DAY_NAMES_FR = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]

# Max retries when validation fails (1 retry = 1 swap)
MAX_RETRIES = 2

# Warn when more than half the slots use LLM fallback
LLM_FALLBACK_WARN_THRESHOLD = 0.5

# Recipe selection calorie range: target/DIVISOR to target*MULTIPLIER
CALORIE_RANGE_MIN_DIVISOR = 3
CALORIE_RANGE_MAX_MULTIPLIER = 2

# Project root for sibling script imports
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


# ---------------------------------------------------------------------------
# Structured pipeline logging
# ---------------------------------------------------------------------------


def _log_step(
    step: str,
    day_index: int,
    duration_ms: float,
    status: str = "ok",
    input_summary: dict | None = None,
    output_summary: dict | None = None,
    error: str | None = None,
):
    """Log a structured dict for pipeline traceability."""
    extra = {
        "step": step,
        "day_index": day_index,
        "duration_ms": round(duration_ms, 1),
        "status": status,
    }
    if input_summary:
        extra["input_summary"] = input_summary
    if output_summary:
        extra["output_summary"] = output_summary
    if error:
        extra["error"] = error

    if status == "error":
        logger.error("pipeline_step %s", json.dumps(extra, ensure_ascii=False))
    else:
        logger.info("pipeline_step %s", json.dumps(extra, ensure_ascii=False))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _import_sibling_script(script_name: str):
    """Import a sibling skill script by name."""
    script_path = Path(__file__).parent / f"{script_name}.py"
    spec = importlib.util.spec_from_file_location(
        f"meal_planning.{script_name}", script_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _build_meal_from_scaled_recipe(scaled_recipe: dict, meal_slot: dict) -> dict:
    """Build a meal dict from a scaled recipe, matching the Output Format Contract."""
    nutrition = scaled_recipe.get("scaled_nutrition", {})
    return {
        "meal_type": meal_slot.get("meal_type", "Repas"),
        "name": scaled_recipe.get("name", ""),
        "ingredients": scaled_recipe.get("ingredients", []),
        "instructions": scaled_recipe.get("instructions", ""),
        "prep_time_minutes": scaled_recipe.get(
            "prep_time_minutes", DEFAULT_PREP_TIME_MINUTES
        ),
        "nutrition": {
            "calories": nutrition.get("calories", 0.0),
            "protein_g": nutrition.get("protein_g", 0.0),
            "carbs_g": nutrition.get("carbs_g", 0.0),
            "fat_g": nutrition.get("fat_g", 0.0),
        },
    }


def _compute_daily_totals(meals: list[dict]) -> dict:
    """Sum nutrition across all meals for the day."""
    totals = {"calories": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0}
    for meal in meals:
        nutrition = meal.get("nutrition", {})
        for key in totals:
            totals[key] = round(totals[key] + nutrition.get(key, 0.0), 2)
    return totals


def _find_custom_request(custom_requests: dict, meal_slot: dict) -> str | None:
    """Find a custom recipe request matching the given meal slot, if any."""
    meal_type_display = meal_slot.get("meal_type", "")
    norm_display = normalize_meal_type(meal_type_display)
    for key, val in custom_requests.items():
        if normalize_meal_type(key) == norm_display:
            return val
    return None


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
            s["recipe_ratios"].get(macro, 0) * s["cal_share"] for s in consumed_slots
        )
        raw = (daily_target_ratios.get(macro, 0) - consumed_weighted) / remaining_share
        required[macro] = max(0.0, raw)

    return required


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


# ---------------------------------------------------------------------------
# Step 2: select_recipes — find one recipe per meal slot
# ---------------------------------------------------------------------------


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
    user_id: str | None = None,
    favorite_ids: set[str] | None = None,
) -> tuple[dict | None, bool, list[dict]]:
    """Resolve a single recipe for a meal slot — from DB or LLM fallback.

    Returns:
        (recipe, is_llm_fallback, runner_up_candidates)
    """
    meal_type_display = meal_slot.get("meal_type", "Déjeuner")
    target_calories = meal_slot.get("target_calories", 600)
    target_protein_g = meal_slot.get("target_protein_g", 40)
    user_allergens = user_profile.get("allergies", [])
    disliked_foods = user_profile.get("disliked_foods", [])
    diet_type = user_profile.get("diet_type") or "omnivore"
    preferred_cuisines = user_profile.get("preferred_cuisines")
    max_prep_time = user_profile.get("max_prep_time")

    # Batch cooking: force-reuse a specific recipe by ID
    if batch_recipe_id:
        recipe = await get_recipe_by_id(supabase, batch_recipe_id)
        if recipe:
            logger.info(
                f"  {meal_type_display}: batch reuse '{recipe['name']}' (ID={batch_recipe_id})"
            )
            return recipe, False, []
        logger.warning(
            f"  {meal_type_display}: batch recipe {batch_recipe_id} not found, falling back"
        )

    # Custom request → check favorites first, then LLM fallback
    if custom_request:
        # Niveau 2: Try to match a favorite recipe by name
        if user_id:
            fav_result = await (
                supabase.table("favorite_recipes")
                .select("recipe_id, recipes(*)")
                .eq("user_id", user_id)
                .execute()
            )
            if fav_result.data:
                # Normalize: lowercase, strip punctuation for fuzzy matching
                query_words = set(
                    re.sub(r"[^\w\s]", "", custom_request.lower()).split()
                )
                for fav in fav_result.data:
                    recipe_data = fav.get("recipes")
                    if not recipe_data:
                        continue
                    name_words = set(
                        re.sub(
                            r"[^\w\s]", "", recipe_data.get("name", "").lower()
                        ).split()
                    )
                    # Match if all query words appear in the recipe name
                    if query_words and query_words.issubset(name_words):
                        logger.info(
                            f"  {meal_type_display}: favorite match '{recipe_data['name']}' "
                            f"for custom request '{custom_request}'"
                        )
                        return recipe_data, False, []

        # No favorite match → LLM generation
        logger.info(
            f"  {meal_type_display}: custom recipe requested '{custom_request}'"
        )
        result_str = await generate_custom_recipe_module.execute(
            anthropic_client=anthropic_client,
            supabase=supabase,
            recipe_request=custom_request,
            meal_type=normalize_meal_type(meal_type_display),
            target_calories=target_calories,
            target_protein_g=target_protein_g,
            target_fat_g=meal_slot.get("target_fat_g", 24),
            target_carbs_g=meal_slot.get("target_carbs_g", 80),
            user_allergens=user_allergens,
            diet_type=diet_type,
            max_prep_time=max_prep_time or 60,
            save_to_db=True,
        )
        result = json.loads(result_str)
        if "error" not in result:
            return result.get("recipe"), True, []
        logger.error(f"Custom recipe generation failed: {result.get('error')}")
        return None, False, []

    # DB search with progressive fallback
    db_meal_type = normalize_meal_type(meal_type_display)

    # Compute target macro ratios for filtering
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

    # Calorie range: select recipes in the right ballpark so LP solver
    # doesn't need extreme scale factors.
    calorie_range = (
        (
            max(50, int(target_calories / CALORIE_RANGE_MIN_DIVISOR)),
            int(target_calories * CALORIE_RANGE_MAX_MULTIPLIER),
        )
        if target_calories > 0
        else None
    )

    # Attempt 1: Full filters (cuisine + macro ratio tolerance 0.20)
    fallback_level = 1
    candidates = await search_recipes(
        supabase=supabase,
        meal_type=db_meal_type,
        exclude_allergens=user_allergens if user_allergens else None,
        exclude_recipe_ids=used_ids or None,
        exclude_ingredients=disliked_foods if disliked_foods else None,
        diet_type=diet_type,
        cuisine_types=preferred_cuisines,
        max_prep_time=max_prep_time,
        calorie_range=calorie_range,
        limit=5,
        target_macro_ratios=target_macro_ratios,
        macro_ratio_tolerance=MACRO_RATIO_TOLERANCE_STRICT,
    )

    # Attempt 2: Drop cuisine filter, widen macro tolerance + calorie range
    if not candidates:
        fallback_level = 2
        logger.info(
            f"  {meal_type_display}: widening search (no cuisine filter, "
            f"tolerance {MACRO_RATIO_TOLERANCE_WIDE})"
        )
        candidates = await search_recipes(
            supabase=supabase,
            meal_type=db_meal_type,
            exclude_allergens=user_allergens if user_allergens else None,
            exclude_recipe_ids=used_ids or None,
            exclude_ingredients=disliked_foods if disliked_foods else None,
            diet_type=diet_type,
            cuisine_types=None,  # No cuisine filter
            max_prep_time=max_prep_time,
            calorie_range=None,  # Drop calorie range too
            limit=5,
            target_macro_ratios=target_macro_ratios,
            macro_ratio_tolerance=MACRO_RATIO_TOLERANCE_WIDE,
        )

    # Attempt 3: Drop macro ratio filter entirely
    if not candidates:
        fallback_level = 3
        logger.info(f"  {meal_type_display}: widening search (no macro filter)")
        candidates = await search_recipes(
            supabase=supabase,
            meal_type=db_meal_type,
            exclude_allergens=user_allergens if user_allergens else None,
            exclude_recipe_ids=used_ids or None,
            exclude_ingredients=disliked_foods if disliked_foods else None,
            diet_type=diet_type,
            cuisine_types=None,
            max_prep_time=None,
            limit=5,
        )

    if candidates:
        candidates.sort(
            key=lambda r: score_recipe_variety(
                r, meal_slot, preferred_cuisines, favorite_recipe_ids=favorite_ids
            ),
            reverse=True,
        )
        recipe = candidates[0]
        runner_ups = candidates[1:] if len(candidates) > 1 else []
        fav_tag = (
            " [FAVORI]" if (favorite_ids and recipe.get("id") in favorite_ids) else ""
        )
        base_score = score_recipe_variety(recipe, meal_slot, preferred_cuisines)
        full_score = score_recipe_variety(
            recipe, meal_slot, preferred_cuisines, favorite_recipe_ids=favorite_ids
        )
        logger.info(
            f"  {meal_type_display}: DB recipe '{recipe['name']}'{fav_tag} "
            f"({recipe['calories_per_serving']:.0f} kcal, "
            f"score={full_score:.3f}, base={base_score:.3f}, "
            f"fav_bonus={full_score - base_score:.3f}, "
            f"fallback_level={fallback_level})"
        )
        return recipe, False, runner_ups

    # No DB match → LLM fallback (fallback_level=4)
    logger.warning(
        f"  {meal_type_display}: no DB match after 3 attempts → LLM fallback (fallback_level=4)"
    )
    result_str = await generate_custom_recipe_module.execute(
        anthropic_client=anthropic_client,
        supabase=supabase,
        recipe_request=f"Un repas de type {meal_type_display} équilibré et savoureux",
        meal_type=db_meal_type,
        target_calories=target_calories,
        target_protein_g=target_protein_g,
        target_fat_g=meal_slot.get("target_fat_g", 24),
        target_carbs_g=meal_slot.get("target_carbs_g", 80),
        user_allergens=user_allergens,
        diet_type=diet_type,
        max_prep_time=max_prep_time or 45,
        save_to_db=True,
    )
    result = json.loads(result_str)
    if "error" not in result:
        return result.get("recipe"), True, []

    logger.error(f"LLM fallback failed for {meal_type_display}: {result.get('error')}")
    return None, False, []


async def select_recipes(
    supabase,
    anthropic_client,
    meal_targets: list[dict],
    user_profile: dict,
    exclude_recipe_ids: list[str],
    custom_requests: dict,
    batch_recipe_ids: dict[str, str] | None = None,
    user_id: str | None = None,
    favorite_ids: set[str] | None = None,
) -> list[dict]:
    """Step 2: Select one recipe per meal slot with inter-meal macro compensation."""
    generate_custom_recipe_module = _import_sibling_script("generate_custom_recipe")
    used_ids = list(exclude_recipe_ids)

    # Compute daily target ratios from all slots
    daily_calories = sum(m.get("target_calories", 0) for m in meal_targets)
    daily_target_ratios = {
        "protein_ratio": sum(m.get("target_protein_g", 0) for m in meal_targets)
        * 4
        / max(daily_calories, 1),
        "fat_ratio": sum(m.get("target_fat_g", 0) for m in meal_targets)
        * 9
        / max(daily_calories, 1),
        "carb_ratio": sum(m.get("target_carbs_g", 0) for m in meal_targets)
        * 4
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
            user_id=user_id,
            favorite_ids=favorite_ids,
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
            consumed_slots.append(
                {
                    "cal_share": cal_shares[idx],
                    "recipe_ratios": _recipe_macro_ratios(recipe),
                }
            )
        else:
            logger.error(
                f"Could not get any recipe for {meal_slot.get('meal_type', '?')}"
            )

    return [a for a in assignments if a is not None]


# ---------------------------------------------------------------------------
# Step 3: scale_portions — scale each recipe to its meal slot targets
# ---------------------------------------------------------------------------


def _scale_one_recipe_fallback(recipe: dict, meal_slot: dict) -> dict:
    """Fallback: scale a single recipe via calorie-based scaling.

    Used only for LLM-generated recipes without OFF nutrition_per_100g data.
    """
    return scale_recipe_to_targets(
        recipe=recipe,
        target_calories=meal_slot.get("target_calories", 600),
        target_protein_g=meal_slot.get("target_protein_g", 40),
        target_carbs_g=meal_slot.get("target_carbs_g", 50),
        target_fat_g=meal_slot.get("target_fat_g", 20),
    )


def scale_portions(assignments: list[dict]) -> list[dict]:
    """Step 3: Scale all recipes simultaneously via LP optimizer.

    Uses optimize_day_portions() to find optimal scale factors for ALL recipes
    at once, minimizing total weighted macro deviation globally.
    Falls back to calorie-based scaling for recipes without OFF data.

    Returns list of ScaledMeal dicts (ready for output).
    """
    if not assignments:
        return []

    # Separate recipes with and without OFF data
    lp_indices = []
    fallback_indices = []
    for i, assignment in enumerate(assignments):
        recipe = assignment["recipe"]
        ingredients = recipe.get("ingredients", [])
        has_per_100g = any(ing.get("nutrition_per_100g") for ing in ingredients)
        if has_per_100g:
            lp_indices.append(i)
        else:
            fallback_indices.append(i)

    # Build daily targets from all meal slots
    daily_targets = {
        "calories": sum(a["meal_slot"].get("target_calories", 0) for a in assignments),
        "protein_g": sum(
            a["meal_slot"].get("target_protein_g", 0) for a in assignments
        ),
        "fat_g": sum(a["meal_slot"].get("target_fat_g", 0) for a in assignments),
        "carbs_g": sum(a["meal_slot"].get("target_carbs_g", 0) for a in assignments),
    }

    # If fallback recipes exist, subtract their estimated macros from LP targets
    fallback_scaled = {}
    for idx in fallback_indices:
        recipe = assignments[idx]["recipe"]
        meal_slot = assignments[idx]["meal_slot"]
        try:
            scaled = _scale_one_recipe_fallback(recipe, meal_slot)
            fallback_scaled[idx] = scaled
            # Subtract fallback nutrition from LP targets (clamp to 0)
            sn = scaled.get("scaled_nutrition", {})
            daily_targets["calories"] = max(
                0, daily_targets["calories"] - sn.get("calories", 0)
            )
            daily_targets["protein_g"] = max(
                0, daily_targets["protein_g"] - sn.get("protein_g", 0)
            )
            daily_targets["fat_g"] = max(0, daily_targets["fat_g"] - sn.get("fat_g", 0))
            daily_targets["carbs_g"] = max(
                0, daily_targets["carbs_g"] - sn.get("carbs_g", 0)
            )
        except Exception as e:
            logger.error(f"Fallback scaling failed for idx {idx}: {e}", exc_info=True)

    # LP optimization for OFF-validated recipes
    lp_scale_factors = {}
    if lp_indices:
        lp_recipes = [assignments[i]["recipe"] for i in lp_indices]
        per_meal_targets = [
            assignments[i]["meal_slot"].get("target_calories", 600) for i in lp_indices
        ]
        try:
            ingredient_factors = optimize_day_portions_v2(
                lp_recipes, daily_targets, per_meal_targets=per_meal_targets
            )
            for i, idx in enumerate(lp_indices):
                lp_scale_factors[idx] = ingredient_factors[i]
        except Exception as e:
            logger.error(
                f"LP optimizer failed: {e}, using uniform scaling", exc_info=True
            )
            # Fallback: uniform calorie scaling per recipe
            for idx in lp_indices:
                recipe = assignments[idx]["recipe"]
                meal_slot = assignments[idx]["meal_slot"]
                try:
                    scaled = _scale_one_recipe_fallback(recipe, meal_slot)
                    fallback_scaled[idx] = scaled
                except Exception as e2:
                    logger.error(f"Uniform fallback also failed for idx {idx}: {e2}")

    # Build final meals list in original order
    scaled_meals: list[dict] = []
    for i, assignment in enumerate(assignments):
        meal_slot = assignment["meal_slot"]
        recipe = assignment["recipe"]

        try:
            if i in lp_scale_factors:
                scaled = apply_ingredient_scale_factors(recipe, lp_scale_factors[i])
            elif i in fallback_scaled:
                scaled = fallback_scaled[i]
            else:
                continue

            meal = _build_meal_from_scaled_recipe(scaled, meal_slot)
            scaled_meals.append(meal)
        except Exception as e:
            logger.error(
                f"Scaling failed for {meal_slot.get('meal_type', '?')}: {e}",
                exc_info=True,
            )

    return scaled_meals


# ---------------------------------------------------------------------------
# Step 4: validate_day — check allergens + macros
# ---------------------------------------------------------------------------


def validate_day(
    meals: list[dict],
    daily_totals: dict,
    target_macros: dict,
    user_allergens: list[str],
) -> dict:
    """Step 4: Validate the day's meals against safety and macro constraints.

    Returns:
        {"valid": bool, "violations": list[str], "allergen_violations": list[str]}
    """
    # Ensure numeric totals
    for key in ("calories", "protein_g", "carbs_g", "fat_g"):
        try:
            daily_totals[key] = float(daily_totals.get(key, 0) or 0)
        except (TypeError, ValueError):
            daily_totals[key] = 0.0

    # Allergen check (zero tolerance)
    allergen_violations = validate_allergens(
        {"days": [{"meals": meals, "daily_totals": daily_totals}]},
        user_allergens,
    )

    # Macro check with tiered tolerances — protein & fat are priority
    protein_check = validate_daily_macros(
        {"protein_g": daily_totals.get("protein_g", 0)},
        {"protein_g": target_macros.get("protein_g", 0)},
        tolerance=MACRO_TOLERANCE_PROTEIN,
    )
    fat_check = validate_daily_macros(
        {"fat_g": daily_totals.get("fat_g", 0)},
        {"fat_g": target_macros.get("fat_g", 0)},
        tolerance=MACRO_TOLERANCE_FAT,
    )
    calorie_check = validate_daily_macros(
        {"calories": daily_totals.get("calories", 0)},
        {"calories": target_macros.get("calories", 0)},
        tolerance=MACRO_TOLERANCE_CALORIES,
    )
    carb_check = validate_daily_macros(
        {"carbs_g": daily_totals.get("carbs_g", 0)},
        {"carbs_g": target_macros.get("carbs_g", 0)},
        tolerance=MACRO_TOLERANCE_CARBS,
    )

    all_violations = (
        allergen_violations
        + protein_check.get("violations", [])
        + calorie_check.get("violations", [])
        + carb_check.get("violations", [])
        + fat_check.get("violations", [])
    )

    if not all_violations:
        logger.info("✅ Daily macros within tolerance")

    return {
        "valid": len(all_violations) == 0,
        "violations": all_violations,
        "allergen_violations": allergen_violations,
    }


# ---------------------------------------------------------------------------
# Step 5: repair — swap worst meal with runner-up, max 1 retry
# ---------------------------------------------------------------------------


async def repair(
    meals: list[dict],
    assignments: list[dict],
    target_macros: dict,
    daily_totals: dict,
    supabase,
    anthropic_client,
    user_profile: dict,
    exclude_recipe_ids: list[str],
    custom_requests: dict,
    batch_recipe_ids: dict[str, str] | None = None,
    user_id: str | None = None,
    favorite_ids: set[str] | None = None,
) -> tuple[list[dict], list[dict]]:
    """Step 5: Swap the worst meal with runner-up or a new DB search.

    Returns:
        (repaired_meals, repaired_assignments)
    """
    worst_idx = find_worst_meal(meals, daily_totals, target_macros)
    worst_type = meals[worst_idx].get("meal_type", "?")
    logger.info(f"  Repair: swapping meal #{worst_idx} ({worst_type})")

    # Try runner-up from step 2 first — skip any already used in this day
    runner_ups = assignments[worst_idx].get("runner_ups", [])
    current_day_ids = {
        a.get("recipe", {}).get("id")
        for i, a in enumerate(assignments)
        if i != worst_idx and a.get("recipe", {}).get("id")
    }
    runner_ups = [r for r in runner_ups if r.get("id") not in current_day_ids]
    if runner_ups:
        replacement = runner_ups[0]
        meal_slot = assignments[worst_idx]["meal_slot"]
        original_assignment = assignments[worst_idx].copy()

        try:
            assignments[worst_idx] = {
                "meal_slot": meal_slot,
                "recipe": replacement,
                "is_llm": False,
                "runner_ups": runner_ups[1:],
            }
            # Re-scale ALL meals with LP solver after swap
            meals = scale_portions(assignments)

            if "id" in replacement:
                try:
                    await increment_usage(supabase, replacement["id"])
                except Exception as e:
                    logger.warning(
                        "Failed to increment usage for recipe %s: %s",
                        replacement.get("id"),
                        e,
                    )

            logger.info(
                f"  Repair: swapped to runner-up '{replacement.get('name', '?')}'"
            )
            return meals, assignments
        except Exception as e:
            assignments[worst_idx] = original_assignment  # rollback
            logger.warning(f"  Repair: runner-up scaling failed: {e}")

    # Runner-up not available or failed — try a new search excluding current recipes
    used_ids = list(exclude_recipe_ids)
    for a in assignments:
        rid = a.get("recipe", {}).get("id")
        if rid and rid not in used_ids:
            used_ids.append(rid)

    meal_slot = assignments[worst_idx]["meal_slot"]
    generate_custom_recipe_module = _import_sibling_script("generate_custom_recipe")

    # Compute compensated ratios from the other (non-swapped) assignments
    daily_calories = sum(a["meal_slot"].get("target_calories", 0) for a in assignments)
    daily_target_ratios = {
        "protein_ratio": sum(
            a["meal_slot"].get("target_protein_g", 0) for a in assignments
        )
        * 4
        / max(daily_calories, 1),
        "fat_ratio": sum(a["meal_slot"].get("target_fat_g", 0) for a in assignments)
        * 9
        / max(daily_calories, 1),
        "carb_ratio": sum(a["meal_slot"].get("target_carbs_g", 0) for a in assignments)
        * 4
        / max(daily_calories, 1),
    }
    other_consumed = []
    for i, a in enumerate(assignments):
        if i != worst_idx:
            cal_share = a["meal_slot"].get("target_calories", 0) / max(
                daily_calories, 1
            )
            other_consumed.append(
                {
                    "cal_share": cal_share,
                    "recipe_ratios": _recipe_macro_ratios(a["recipe"]),
                }
            )
    worst_cal_share = meal_slot.get("target_calories", 0) / max(daily_calories, 1)
    repair_ratios = _compute_required_ratios(
        daily_target_ratios, other_consumed, [worst_cal_share]
    )

    recipe, is_llm, _ = await _select_recipe_for_slot(
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
        target_macro_ratios_override=repair_ratios,
        user_id=user_id,
        favorite_ids=favorite_ids,
    )

    if recipe:
        try:
            assignments[worst_idx] = {
                "meal_slot": meal_slot,
                "recipe": recipe,
                "is_llm": is_llm,
                "runner_ups": [],
            }
            # Re-scale ALL meals with LP solver after swap
            meals = scale_portions(assignments)

            if "id" in recipe:
                try:
                    await increment_usage(supabase, recipe["id"])
                except Exception as e:
                    logger.warning(
                        "Failed to increment usage for recipe %s: %s",
                        recipe.get("id"),
                        e,
                    )

            logger.info(f"  Repair: new recipe '{recipe.get('name', '?')}'")
        except Exception as e:
            logger.warning(f"  Repair: new recipe scaling failed: {e}")

    return meals, assignments


# ---------------------------------------------------------------------------
# Main pipeline: execute()
# ---------------------------------------------------------------------------


async def execute(**kwargs) -> str:
    """Generate meal plan for one day.

    Pipeline:
        Step 1: (targets come pre-resolved from generate_week_plan)
        Step 2: select_recipes — find best DB recipe per slot
        Step 3: scale_portions — scale to macro targets
        Step 4: validate_day — allergens + macros
        Step 5: repair — swap worst meal if validation fails (max 1 retry)

    Args:
        supabase: Supabase client
        anthropic_client: AsyncAnthropic client (for LLM fallback only)
        day_index: 0-6 (Monday-Sunday)
        day_name: "Lundi", "Mardi", etc.
        day_date: "YYYY-MM-DD"
        meal_targets: List of meal slot targets from meal_distribution
        user_profile: Profile dict (allergens, preferences, diet_type)
        exclude_recipe_ids: IDs already used this week (variety)
        custom_requests: Optional dict of meal_type → recipe request string
        batch_recipe_ids: Optional dict of meal_type → forced recipe ID

    Returns:
        JSON with complete day plan
    """
    supabase = kwargs["supabase"]
    anthropic_client = kwargs["anthropic_client"]
    day_index = kwargs.get("day_index", 0)
    day_name = kwargs.get("day_name", DAY_NAMES_FR[day_index % 7])
    day_date = kwargs.get("day_date", "")
    meal_targets = kwargs["meal_targets"]
    if not meal_targets:
        return json.dumps({"error": "meal_targets cannot be empty", "meals": []})
    user_profile = kwargs.get("user_profile", {})
    exclude_recipe_ids = list(kwargs.get("exclude_recipe_ids", []))
    custom_requests = kwargs.get("custom_requests", {})
    batch_recipe_ids = kwargs.get("batch_recipe_ids", {})
    user_id = kwargs.get("user_id")
    favorite_ids = await get_user_favorite_ids(supabase, user_id)

    # Build target macros for validation
    target_macros = {
        "calories": sum(m.get("target_calories", 0) for m in meal_targets),
        "protein_g": sum(m.get("target_protein_g", 0) for m in meal_targets),
        "carbs_g": sum(m.get("target_carbs_g", 0) for m in meal_targets),
        "fat_g": sum(m.get("target_fat_g", 0) for m in meal_targets),
    }

    try:
        logger.info(
            f"Generating day plan: {day_name} ({day_date}), "
            f"{len(meal_targets)} meals, target={target_macros['calories']} kcal"
        )

        # ------------------------------------------------------------------
        # Step 2: Select recipes
        # ------------------------------------------------------------------
        t0 = time.monotonic()
        assignments = await select_recipes(
            supabase=supabase,
            anthropic_client=anthropic_client,
            meal_targets=meal_targets,
            user_profile=user_profile,
            exclude_recipe_ids=exclude_recipe_ids,
            custom_requests=custom_requests,
            batch_recipe_ids=batch_recipe_ids or None,
            user_id=user_id,
            favorite_ids=favorite_ids,
        )
        t_select = (time.monotonic() - t0) * 1000

        llm_fallback_count = sum(1 for a in assignments if a["is_llm"])

        _log_step(
            step="select_recipes",
            day_index=day_index,
            duration_ms=t_select,
            input_summary={
                "meal_slots": len(meal_targets),
                "exclude_ids": len(exclude_recipe_ids),
            },
            output_summary={
                "db_matches": len(assignments) - llm_fallback_count,
                "llm_fallbacks": llm_fallback_count,
            },
        )

        if not assignments:
            _log_step(
                step="select_recipes",
                day_index=day_index,
                duration_ms=t_select,
                status="error",
                error="No recipes found for any slot",
            )
            return json.dumps(
                {
                    "success": False,
                    "error": f"Could not find any recipes for {day_name}",
                    "code": "GENERATION_FAILED",
                },
                ensure_ascii=False,
            )

        # Warn on high LLM fallback rate
        if len(meal_targets) > 0:
            fallback_ratio = llm_fallback_count / len(meal_targets)
            if fallback_ratio >= LLM_FALLBACK_WARN_THRESHOLD:
                logger.warning(
                    f"Recipe DB coverage low for {day_name}: "
                    f"{llm_fallback_count}/{len(meal_targets)} slots used LLM fallback. "
                    "Consider running scripts/validate_all_recipes.py and seeding more recipes."
                )

        # Track recipe usage
        for a in assignments:
            recipe = a["recipe"]
            if "id" in recipe:
                try:
                    await increment_usage(supabase, recipe["id"])
                except Exception as e:
                    logger.warning(
                        "Failed to increment usage for recipe %s: %s",
                        recipe.get("id"),
                        e,
                    )

        # ------------------------------------------------------------------
        # Step 3: Scale portions
        # ------------------------------------------------------------------
        t0 = time.monotonic()
        meals = scale_portions(assignments)
        t_scale = (time.monotonic() - t0) * 1000

        _log_step(
            step="scale_portions",
            day_index=day_index,
            duration_ms=t_scale,
            input_summary={"assignments": len(assignments)},
            output_summary={"scaled_meals": len(meals)},
        )

        if not meals:
            return json.dumps(
                {
                    "success": False,
                    "error": f"Scaling failed for all meals on {day_name}",
                    "code": "GENERATION_FAILED",
                },
                ensure_ascii=False,
            )

        # ------------------------------------------------------------------
        # Step 4: Validate day
        # ------------------------------------------------------------------
        t0 = time.monotonic()
        daily_totals = _compute_daily_totals(meals)
        user_allergens = user_profile.get("allergies", [])
        validation = validate_day(meals, daily_totals, target_macros, user_allergens)
        t_validate = (time.monotonic() - t0) * 1000

        _log_step(
            step="validate_day",
            day_index=day_index,
            duration_ms=t_validate,
            input_summary={
                "meals": len(meals),
                "target_calories": target_macros["calories"],
            },
            output_summary={
                "valid": validation["valid"],
                "violations": len(validation["violations"]),
            },
        )

        # ------------------------------------------------------------------
        # Step 5: Repair (if needed, up to MAX_RETRIES swaps)
        # ------------------------------------------------------------------
        retries = 0
        while not validation["valid"] and retries < MAX_RETRIES:
            retries += 1
            logger.warning(
                f"Day {day_name} validation failed: "
                f"{len(validation['violations'])} violations — repair attempt {retries}/{MAX_RETRIES}"
            )

            t0 = time.monotonic()
            meals, assignments = await repair(
                meals=meals,
                assignments=assignments,
                target_macros=target_macros,
                daily_totals=daily_totals,
                supabase=supabase,
                anthropic_client=anthropic_client,
                user_profile=user_profile,
                exclude_recipe_ids=exclude_recipe_ids,
                custom_requests=custom_requests,
                batch_recipe_ids=batch_recipe_ids or None,
                user_id=user_id,
                favorite_ids=favorite_ids,
            )
            t_repair = (time.monotonic() - t0) * 1000

            # Re-validate after repair
            daily_totals = _compute_daily_totals(meals)
            validation = validate_day(
                meals, daily_totals, target_macros, user_allergens
            )

            _log_step(
                step="repair",
                day_index=day_index,
                duration_ms=t_repair,
                output_summary={
                    "retry": retries,
                    "valid_after_repair": validation["valid"],
                    "violations_remaining": len(validation["violations"]),
                },
            )

        # Surface remaining violations as warnings (4C)
        warnings: list[str] = []
        if not validation["valid"]:
            warnings = list(validation["violations"])
            logger.warning(
                f"Day {day_name} still has {len(warnings)} violations after "
                f"{MAX_RETRIES} repair attempts: {warnings}"
            )

        # ------------------------------------------------------------------
        # Build result
        # ------------------------------------------------------------------
        recipe_ids_used = [
            a["recipe"]["id"] for a in assignments if "id" in a.get("recipe", {})
        ]
        recipe_ids_by_mt = {}
        for a in assignments:
            recipe = a.get("recipe", {})
            slot = a.get("meal_slot", {})
            if "id" in recipe:
                mt = normalize_meal_type(slot.get("meal_type", ""))
                recipe_ids_by_mt[mt] = recipe["id"]

        day_plan = {
            "day": day_name,
            "date": day_date,
            "meals": meals,
            "daily_totals": daily_totals,
        }

        logger.info(
            f"Day {day_name} complete: {len(meals)} meals, "
            f"{daily_totals['calories']:.0f} kcal, "
            f"validation={'PASS' if validation['valid'] else 'WARN'}"
        )

        result_data: dict = {
            "success": True,
            "day": day_plan,
            "recipes_used": recipe_ids_used,
            "recipe_ids_by_meal_type": recipe_ids_by_mt,
            "llm_fallback_count": llm_fallback_count,
            "validation": validation,
        }
        if warnings:
            result_data["warnings"] = warnings

        return json.dumps(
            result_data,
            indent=2,
            ensure_ascii=False,
        )

    except ValueError as e:
        logger.error(f"Validation error in generate_day_plan: {e}")
        return json.dumps({"error": str(e), "code": "VALIDATION_ERROR"})
    except Exception as e:
        logger.error(f"Unexpected error in generate_day_plan: {e}", exc_info=True)
        return json.dumps({"error": "Internal error", "code": "SCRIPT_ERROR"})
