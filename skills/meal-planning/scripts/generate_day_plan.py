"""Generate a complete meal plan for a single day.

Orchestrates: select_recipes → scale_portions → validate_day.
If recipe DB doesn't cover a meal slot, falls back to LLM generation.
Includes retry logic (max 2 retries per day).

Source: Refactored from src/tools.py generate_weekly_meal_plan_tool
"""

import copy
import importlib.util
import json
import logging
from pathlib import Path

from src.nutrition.portion_scaler import scale_recipe_to_targets
from src.nutrition.recipe_db import search_recipes, increment_usage
from src.nutrition.meal_plan_optimizer import (
    calculate_meal_plan_macros,
    optimize_meal_plan_portions,
)
from src.nutrition.validators import validate_allergens, validate_daily_macros

logger = logging.getLogger(__name__)


def _score_recipe_macro_fit(recipe: dict, target: dict) -> float:
    """Score how well recipe's macro RATIOS match target ratios.

    Compares protein/cal, carbs/cal, fat/cal ratios of recipe vs target.
    Lower score = better fit. Protein match is weighted 2x.

    Args:
        recipe: Recipe dict with calories_per_serving, protein_g_per_serving, etc.
        target: Meal slot target dict with target_calories, target_protein_g, etc.

    Returns:
        Float score >= 0. Lower is better.
    """
    recipe_cal = recipe.get("calories_per_serving", 1) or 1
    recipe_prot_ratio = recipe.get("protein_g_per_serving", 0) * 4 / recipe_cal
    recipe_carb_ratio = recipe.get("carbs_g_per_serving", 0) * 4 / recipe_cal
    recipe_fat_ratio = recipe.get("fat_g_per_serving", 0) * 9 / recipe_cal

    target_cal = target.get("target_calories", 1) or 1
    target_prot_ratio = target.get("target_protein_g", 0) * 4 / target_cal
    target_carb_ratio = target.get("target_carbs_g", 0) * 4 / target_cal
    target_fat_ratio = target.get("target_fat_g", 0) * 9 / target_cal

    score = (
        2 * abs(recipe_prot_ratio - target_prot_ratio)
        + abs(recipe_carb_ratio - target_carb_ratio)
        + abs(recipe_fat_ratio - target_fat_ratio)
    )
    return score


# Day names in French
DAY_NAMES_FR = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]

# Max retries when validation fails
MAX_RETRIES = 2

# Warn when more than half the slots use LLM fallback
LLM_FALLBACK_WARN_THRESHOLD = 0.5

# Project root for sibling script imports
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# Meal type normalization map (same as select_recipes.py)
_MEAL_TYPE_MAP = {
    "petit-déjeuner": "petit-dejeuner",
    "petit-dejeuner": "petit-dejeuner",
    "déjeuner": "dejeuner",
    "dejeuner": "dejeuner",
    "dîner": "diner",
    "diner": "diner",
    "collation": "collation",
}


def _normalize_meal_type_inline(meal_type_display: str) -> str:
    """Map display meal type to DB meal_type key (without importing sibling script)."""
    meal_lower = meal_type_display.lower()
    for key, value in _MEAL_TYPE_MAP.items():
        if key in meal_lower:
            return value
    if "petit" in meal_lower or "breakfast" in meal_lower:
        return "petit-dejeuner"
    if "djeuner" in meal_lower or "lunch" in meal_lower:
        return "dejeuner"
    if "dner" in meal_lower or "dinner" in meal_lower or "soir" in meal_lower:
        return "diner"
    if "collation" in meal_lower or "snack" in meal_lower:
        return "collation"
    return "dejeuner"


def _import_sibling_script(script_name: str):
    """Import a sibling skill script by name.

    Args:
        script_name: Script filename without .py (e.g., "generate_custom_recipe")

    Returns:
        Loaded module with execute() function
    """
    script_path = Path(__file__).parent / f"{script_name}.py"
    spec = importlib.util.spec_from_file_location(
        f"meal_planning.{script_name}", script_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _build_meal_from_scaled_recipe(
    scaled_recipe: dict,
    meal_slot: dict,
) -> dict:
    """Build a meal dict from a scaled recipe, matching the Output Format Contract.

    Args:
        scaled_recipe: Recipe dict with scaled_nutrition and scaled ingredients
        meal_slot: Meal slot target dict with meal_type

    Returns:
        Meal dict with all required fields
    """
    nutrition = scaled_recipe.get("scaled_nutrition", {})

    return {
        "meal_type": meal_slot.get("meal_type", "Repas"),
        "name": scaled_recipe.get("name", ""),
        "ingredients": scaled_recipe.get("ingredients", []),
        "instructions": scaled_recipe.get("instructions", ""),
        "prep_time_minutes": scaled_recipe.get("prep_time_minutes", 30),
        "nutrition": {
            "calories": nutrition.get("calories", 0.0),
            "protein_g": nutrition.get("protein_g", 0.0),
            "carbs_g": nutrition.get("carbs_g", 0.0),
            "fat_g": nutrition.get("fat_g", 0.0),
        },
    }


def _compute_daily_totals(meals: list[dict]) -> dict:
    """Sum nutrition across all meals for the day.

    Args:
        meals: List of meal dicts with nutrition dicts

    Returns:
        Dict with calories, protein_g, carbs_g, fat_g totals
    """
    totals = {"calories": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0}
    for meal in meals:
        nutrition = meal.get("nutrition", {})
        for key in totals:
            totals[key] = round(totals[key] + nutrition.get(key, 0.0), 2)
    return totals


def _find_custom_request(custom_requests: dict, meal_slot: dict) -> str | None:
    """Find a custom recipe request matching the given meal slot, if any.

    Checks both exact key match and substring match against meal_type display name.

    Args:
        custom_requests: Dict of {meal_type_key: recipe_request} from notes parsing
        meal_slot: Meal slot dict with "meal_type" display name

    Returns:
        Recipe request string or None
    """
    meal_type_display = meal_slot.get("meal_type", "")
    # Exact key match (normalised)
    normalised = meal_type_display.lower().replace("-", "")
    if normalised in custom_requests:
        return custom_requests[normalised]
    # Substring match
    for key, val in custom_requests.items():
        if key.lower() in meal_type_display.lower():
            return val
    return None


async def _get_recipe_for_slot(
    supabase,
    anthropic_client,
    meal_slot: dict,
    user_profile: dict,
    used_ids: list[str],
    custom_request: str | None,
    attempt: int,
    generate_custom_recipe_module,
) -> tuple[dict | None, bool]:
    """Resolve a single recipe for a meal slot — from DB or LLM fallback.

    Args:
        supabase: Supabase client
        anthropic_client: Anthropic client for LLM fallback
        meal_slot: Meal slot target dict
        user_profile: User profile dict (allergens, diet_type, preferences)
        used_ids: Recipe IDs already used this day/week (variety exclusion)
        custom_request: Explicit recipe request from user notes, or None
        attempt: Current retry attempt number (0-indexed)
        generate_custom_recipe_module: Pre-loaded sibling script module

    Returns:
        (recipe dict | None, is_llm_fallback: bool)
    """
    meal_type_display = meal_slot.get("meal_type", "Déjeuner")
    target_calories = meal_slot.get("target_calories", 600)
    target_protein_g = meal_slot.get("target_protein_g", 40)
    user_allergens = user_profile.get("allergies", [])
    disliked_foods = user_profile.get("disliked_foods", [])
    diet_type = user_profile.get("diet_type", "omnivore")
    preferred_cuisines = user_profile.get("preferred_cuisines")
    max_prep_time = user_profile.get("max_prep_time")

    if custom_request:
        logger.info(
            f"  {meal_type_display}: custom recipe requested '{custom_request}'"
        )
        result_str = await generate_custom_recipe_module.execute(
            anthropic_client=anthropic_client,
            supabase=supabase,
            recipe_request=custom_request,
            meal_type=meal_type_display.lower().replace("é", "e").replace("î", "i"),
            target_calories=target_calories,
            target_protein_g=target_protein_g,
            user_allergens=user_allergens,
            diet_type=diet_type,
            max_prep_time=max_prep_time or 60,
            save_to_db=True,
        )
        result = json.loads(result_str)
        if "error" not in result:
            return result.get("recipe"), True
        logger.error(f"Custom recipe generation failed: {result.get('error')}")
        return None, False

    # Try DB first
    # NOTE: calorie_range filter intentionally omitted — scale_recipe_to_targets adjusts
    # portions to match any calorie target. Filtering by range would exclude valid recipes
    # (e.g. a 400 kcal breakfast when target is 988 kcal) causing unnecessary LLM fallback.
    db_meal_type = _normalize_meal_type_inline(meal_type_display)

    candidates = await search_recipes(
        supabase=supabase,
        meal_type=db_meal_type,
        exclude_allergens=user_allergens if user_allergens else None,
        exclude_recipe_ids=used_ids or None,
        exclude_ingredients=disliked_foods if disliked_foods else None,
        diet_type=diet_type,
        cuisine_types=preferred_cuisines,
        max_prep_time=max_prep_time,
        limit=5,
    )

    if candidates:
        candidates.sort(key=lambda r: _score_recipe_macro_fit(r, meal_slot))
        recipe = candidates[0]
        logger.info(
            f"  {meal_type_display}: DB recipe '{recipe['name']}' "
            f"({recipe['calories_per_serving']:.0f} kcal, "
            f"macro_score={_score_recipe_macro_fit(recipe, meal_slot):.3f})"
        )
        return recipe, False

    # No DB match → LLM fallback
    logger.warning(
        f"  {meal_type_display}: no DB match → LLM fallback (attempt {attempt + 1})"
    )
    result_str = await generate_custom_recipe_module.execute(
        anthropic_client=anthropic_client,
        supabase=supabase,
        recipe_request=f"Un repas de type {meal_type_display} équilibré et savoureux",
        meal_type=db_meal_type,
        target_calories=target_calories,
        target_protein_g=target_protein_g,
        user_allergens=user_allergens,
        diet_type=diet_type,
        max_prep_time=max_prep_time or 45,
        save_to_db=True,
    )
    result = json.loads(result_str)
    if "error" not in result:
        return result.get("recipe"), True

    logger.error(f"LLM fallback failed for {meal_type_display}: {result.get('error')}")
    return None, False


async def _select_and_scale_meals(
    supabase,
    anthropic_client,
    meal_targets: list[dict],
    user_profile: dict,
    exclude_recipe_ids: list[str],
    custom_requests: dict,
    attempt: int,
    failed_recipe_ids: list[str] | None = None,
) -> tuple[list[dict], list[str], int]:
    """Resolve, scale and assemble meals for all slots in one day.

    For each meal slot: find a recipe (DB or LLM) → scale to targets → build meal dict.

    Returns:
        (meals, recipe_ids_used, llm_fallback_count)
    """
    generate_custom_recipe_module = _import_sibling_script("generate_custom_recipe")

    meals: list[dict] = []
    recipe_ids_used: list[str] = []
    llm_fallback_count = 0
    used_ids_this_attempt = list(exclude_recipe_ids) + list(failed_recipe_ids or [])

    for meal_slot in meal_targets:
        meal_type_display = meal_slot.get("meal_type", "Déjeuner")
        custom_request = _find_custom_request(custom_requests, meal_slot)

        recipe, is_llm = await _get_recipe_for_slot(
            supabase=supabase,
            anthropic_client=anthropic_client,
            meal_slot=meal_slot,
            user_profile=user_profile,
            used_ids=used_ids_this_attempt,
            custom_request=custom_request,
            attempt=attempt,
            generate_custom_recipe_module=generate_custom_recipe_module,
        )

        if not recipe:
            logger.error(f"Could not get any recipe for {meal_type_display}")
            continue

        if is_llm:
            llm_fallback_count += 1

        try:
            scaled = scale_recipe_to_targets(
                recipe=recipe,
                target_calories=meal_slot.get("target_calories", 600),
                target_protein_g=meal_slot.get("target_protein_g", 40),
                target_carbs_g=meal_slot.get("target_carbs_g"),
                target_fat_g=meal_slot.get("target_fat_g"),
            )
            meals.append(_build_meal_from_scaled_recipe(scaled, meal_slot))

            if "id" in recipe:
                recipe_ids_used.append(recipe["id"])
                used_ids_this_attempt.append(recipe["id"])
                try:
                    await increment_usage(supabase, recipe["id"])
                except Exception:
                    pass  # Non-critical
        except Exception as scale_err:
            logger.error(
                f"Scaling failed for {meal_type_display}: {scale_err}", exc_info=True
            )

    return meals, recipe_ids_used, llm_fallback_count


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
    supabase = kwargs["supabase"]
    anthropic_client = kwargs["anthropic_client"]
    day_index = kwargs.get("day_index", 0)
    day_name = kwargs.get("day_name", DAY_NAMES_FR[day_index % 7])
    day_date = kwargs.get("day_date", "")
    meal_targets = kwargs["meal_targets"]
    user_profile = kwargs.get("user_profile", {})
    exclude_recipe_ids = list(kwargs.get("exclude_recipe_ids", []))
    custom_requests = kwargs.get("custom_requests", {})

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

        best_day = None
        best_validation = None
        best_recipe_ids: list[str] = []
        best_llm_count = 0
        failed_recipe_ids: list[str] = []

        for attempt in range(MAX_RETRIES + 1):
            if attempt > 0:
                logger.info(f"Retry {attempt}/{MAX_RETRIES} for {day_name}")

            meals, recipe_ids_used, llm_fallback_count = await _select_and_scale_meals(
                supabase=supabase,
                anthropic_client=anthropic_client,
                meal_targets=meal_targets,
                user_profile=user_profile,
                exclude_recipe_ids=exclude_recipe_ids,
                custom_requests=custom_requests,
                attempt=attempt,
                failed_recipe_ids=failed_recipe_ids,
            )

            if not meals:
                logger.error(f"No meals generated for {day_name} (attempt {attempt})")
                continue

            # Warn on high LLM fallback rate
            fallback_ratio = llm_fallback_count / len(meal_targets)
            if fallback_ratio >= LLM_FALLBACK_WARN_THRESHOLD:
                logger.warning(
                    f"Recipe DB coverage low for {day_name}: "
                    f"{llm_fallback_count}/{len(meal_targets)} slots used LLM fallback. "
                    "Consider running seed_recipe_db."
                )

            # Build day dict
            daily_totals = _compute_daily_totals(meals)
            day_plan = {
                "day": day_name,
                "date": day_date,
                "meals": meals,
                "daily_totals": daily_totals,
            }

            # Recalculate macros from ingredients via OpenFoodFacts
            try:
                scaled_totals = dict(daily_totals)
                day_plan_backup = copy.deepcopy(day_plan)
                wrapped = {"days": [day_plan]}
                await calculate_meal_plan_macros(wrapped, supabase)
                # calculate_meal_plan_macros updates nutrition and daily_totals in place
                daily_totals = day_plan["daily_totals"]
                logger.info(
                    f"OFF recalc for {day_name}: "
                    f"{daily_totals['calories']:.0f} kcal, "
                    f"{daily_totals['protein_g']:.0f}g protein "
                    f"(was {scaled_totals['calories']:.0f} kcal from scaling)"
                )
            except Exception as off_err:
                # Restore from backup — calculate_meal_plan_macros modifies in place
                day_plan.update(day_plan_backup)
                daily_totals = day_plan["daily_totals"]
                logger.warning(
                    f"OFF recalc failed for {day_name}, using scaled macros: {off_err}"
                )

            # Optimize portions (selective fat reduction + calorie adjustment)
            try:
                user_allergens_opt = user_profile.get("allergies", [])
                wrapped_for_opt = {"days": [day_plan]}
                optimized = await optimize_meal_plan_portions(
                    wrapped_for_opt, target_macros, user_allergens_opt
                )
                day_plan = optimized["days"][0]
                daily_totals = day_plan["daily_totals"]
                logger.info(
                    f"Optimization for {day_name}: "
                    f"{daily_totals['calories']:.0f} kcal, "
                    f"{daily_totals['fat_g']:.0f}g fat"
                )
            except Exception as opt_err:
                logger.warning(f"Optimization failed for {day_name}: {opt_err}")

            # Validate the day
            user_allergens = user_profile.get("allergies", [])

            # Allergen check (zero tolerance)
            allergen_violations = validate_allergens(
                {"days": [day_plan]}, user_allergens
            )

            # Macro check — tolerances account for OFF recalc variance
            protein_check = validate_daily_macros(
                {"protein_g": daily_totals.get("protein_g", 0)},
                {"protein_g": target_macros.get("protein_g", 0)},
                tolerance=0.10,
            )
            calorie_carb_check = validate_daily_macros(
                {
                    "calories": daily_totals.get("calories", 0),
                    "carbs_g": daily_totals.get("carbs_g", 0),
                },
                {
                    "calories": target_macros.get("calories", 0),
                    "carbs_g": target_macros.get("carbs_g", 0),
                },
                tolerance=0.15,
            )
            fat_check = validate_daily_macros(
                {"fat_g": daily_totals.get("fat_g", 0)},
                {"fat_g": target_macros.get("fat_g", 0)},
                tolerance=0.20,
            )

            all_violations = (
                allergen_violations
                + protein_check.get("violations", [])
                + calorie_carb_check.get("violations", [])
                + fat_check.get("violations", [])
            )
            validation = {
                "valid": len(all_violations) == 0,
                "violations": all_violations,
                "allergen_violations": allergen_violations,
            }

            if validation["valid"] or attempt == MAX_RETRIES:
                best_day = day_plan
                best_validation = validation
                best_recipe_ids = recipe_ids_used
                best_llm_count = llm_fallback_count
                break

            # Track recipe IDs from failed attempts so retries pick different recipes
            failed_recipe_ids.extend(recipe_ids_used)

            logger.warning(
                f"Day {day_name} validation failed (attempt {attempt}): "
                f"{len(all_violations)} violations"
            )

        if best_day is None:
            return json.dumps(
                {
                    "success": False,
                    "error": f"Could not generate valid day plan for {day_name}",
                    "code": "GENERATION_FAILED",
                },
                ensure_ascii=False,
            )

        logger.info(
            f"✅ Day {day_name} complete: {len(best_day['meals'])} meals, "
            f"{best_day['daily_totals']['calories']:.0f} kcal, "
            f"validation={'PASS' if best_validation['valid'] else 'WARN'}"
        )

        return json.dumps(
            {
                "success": True,
                "day": best_day,
                "recipes_used": best_recipe_ids,
                "llm_fallback_count": best_llm_count,
                "validation": best_validation,
            },
            indent=2,
            ensure_ascii=False,
        )

    except ValueError as e:
        logger.error(f"Validation error in generate_day_plan: {e}")
        return json.dumps({"error": str(e), "code": "VALIDATION_ERROR"})
    except Exception as e:
        logger.error(f"Unexpected error in generate_day_plan: {e}", exc_info=True)
        return json.dumps({"error": "Internal error", "code": "SCRIPT_ERROR"})
