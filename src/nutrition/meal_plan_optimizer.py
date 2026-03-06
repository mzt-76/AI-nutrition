"""Meal plan macro calculation and portion optimization using OpenFoodFacts.

This module provides:
1. Precise macro calculation using OpenFoodFacts-validated ingredient data
2. Portion scaling optimization (±25% max) to hit targets
3. Complement food addition as fallback (minimal usage)

References:
    Helms et al. (2014): Portion scaling maintains adherence better than artificial supplements
    ISSN (2017): Protein requirements for muscle gain
"""

import asyncio
import logging
from typing import Any

from supabase import Client

from src.nutrition.openfoodfacts_client import match_ingredient
from src.nutrition.macro_adjustments import (
    calculate_macro_deficit,
    needs_adjustment,
    select_complement_food,
)
from src.nutrition.quantity_rounding import round_quantity_smart  # noqa: F401 — re-exported
from src.nutrition.fat_rebalancer import (  # noqa: F401 — re-exported
    rebalance_high_fat_day as _rebalance_high_fat_day,
    FAT_SURPLUS_THRESHOLD,
)

logger = logging.getLogger(__name__)

# Portion scaling constraints
# 2.5x allows a 340 kcal recipe to reach 850 kcal (muscle gain targets)
# Smart rounding keeps portions natural (whole eggs, rounded grams)
MIN_SCALE_FACTOR = 0.50  # Don't scale down more than 50%
MAX_SCALE_FACTOR = 2.50  # "Double serving + a bit" — reasonable for high-cal targets

# Maximum complements to add per day (prefer scaling over complements)
MAX_COMPLEMENTS_PER_DAY = 2


async def calculate_meal_plan_macros(
    meal_plan: dict[str, Any],
    supabase: Client,
) -> dict[str, Any]:
    """Calculate precise macros for entire meal plan using OpenFoodFacts.

    Workflow:
    1. For each day → for each meal → for each ingredient
    2. Match ingredient to OpenFoodFacts database (with caching)
    3. Calculate macros for given quantity
    4. Accumulate to meal totals → daily totals

    Args:
        meal_plan: Meal plan dict with days, meals, ingredients
        supabase: Supabase client for caching and database access

    Returns:
        Meal plan with precise nutrition data added to each meal and day

    Raises:
        ValueError: If critical ingredients missing (logs warning, continues)

    Example:
        >>> plan = await calculate_meal_plan_macros(meal_plan, supabase)
        >>> print(plan["days"][0]["daily_totals"]["calories"])
        2540

    References:
        - OpenFoodFacts local database for per-100g nutrition data
        - Cache hit rate: 0% (first plan) → 70%+ (subsequent plans)
    """
    logger.info("🔧 Calculating precise macros via OpenFoodFacts...")

    cache_stats = {"hits": 0, "misses": 0}

    for day in meal_plan.get("days", []):
        day_name = day.get("day", "Unknown")
        daily_totals = {"calories": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0}

        for meal in day.get("meals", []):
            meal_totals = {
                "calories": 0.0,
                "protein_g": 0.0,
                "carbs_g": 0.0,
                "fat_g": 0.0,
            }

            ingredients = meal.get("ingredients", [])

            # Collect valid ingredients for parallel matching
            valid_ingredients = [
                ing
                for ing in ingredients
                if ing.get("name") and ing.get("quantity", 0) != 0
            ]
            for ing in ingredients:
                if not ing.get("name") or ing.get("quantity", 0) == 0:
                    logger.warning(f"Skipping invalid ingredient: {ing}")

            # Parallel match all ingredients in this meal
            async def _match_one(ingredient: dict) -> dict | None:
                try:
                    return await match_ingredient(
                        ingredient_name=ingredient["name"],
                        quantity=ingredient.get("quantity", 0),
                        unit=ingredient.get("unit", "g"),
                        supabase=supabase,
                    )
                except ValueError as e:
                    logger.warning(
                        f"⚠️ Could not match ingredient '{ingredient['name']}': {e}"
                    )
                    ingredient["openfoodfacts_error"] = str(e)
                    return None
                except Exception as e:
                    logger.error(
                        f"❌ Error processing ingredient '{ingredient['name']}': {e}",
                        exc_info=True,
                    )
                    ingredient["openfoodfacts_error"] = str(e)
                    return None

            match_results = await asyncio.gather(
                *[_match_one(ing) for ing in valid_ingredients]
            )

            for ingredient, ingredient_macros in zip(valid_ingredients, match_results):
                if ingredient_macros is None:
                    continue

                if ingredient_macros["cache_hit"]:
                    cache_stats["hits"] += 1
                else:
                    cache_stats["misses"] += 1

                ingredient["openfoodfacts_code"] = ingredient_macros[
                    "openfoodfacts_code"
                ]
                ingredient["matched_name"] = ingredient_macros["matched_name"]
                ingredient["nutrition"] = {
                    "calories": ingredient_macros["calories"],
                    "protein_g": ingredient_macros["protein_g"],
                    "carbs_g": ingredient_macros["carbs_g"],
                    "fat_g": ingredient_macros["fat_g"],
                }
                ingredient["confidence"] = ingredient_macros["confidence"]

                meal_totals["calories"] += ingredient_macros["calories"]
                meal_totals["protein_g"] += ingredient_macros["protein_g"]
                meal_totals["carbs_g"] += ingredient_macros["carbs_g"]
                meal_totals["fat_g"] += ingredient_macros["fat_g"]

            # Round and store meal totals
            meal["nutrition"] = {
                "calories": round(meal_totals["calories"], 1),
                "protein_g": round(meal_totals["protein_g"], 1),
                "carbs_g": round(meal_totals["carbs_g"], 1),
                "fat_g": round(meal_totals["fat_g"], 1),
            }

            # Add to daily totals
            daily_totals["calories"] += meal_totals["calories"]
            daily_totals["protein_g"] += meal_totals["protein_g"]
            daily_totals["carbs_g"] += meal_totals["carbs_g"]
            daily_totals["fat_g"] += meal_totals["fat_g"]

        # Round and store daily totals
        day["daily_totals"] = {
            "calories": round(daily_totals["calories"], 1),
            "protein_g": round(daily_totals["protein_g"], 1),
            "carbs_g": round(daily_totals["carbs_g"], 1),
            "fat_g": round(daily_totals["fat_g"], 1),
        }

        logger.info(
            f"{day_name}: {day['daily_totals']['calories']:.0f} kcal, "
            f"{day['daily_totals']['protein_g']:.0f}g protein"
        )

    # Log cache performance
    total_ingredients = cache_stats["hits"] + cache_stats["misses"]
    if total_ingredients > 0:
        hit_rate = (cache_stats["hits"] / total_ingredients) * 100
        logger.info(
            f"📊 Cache hit rate: {hit_rate:.1f}% ({cache_stats['hits']}/{total_ingredients} ingredients)"
        )
    else:
        logger.warning("No ingredients processed successfully")

    logger.info("✅ Macros calculated for all days via OpenFoodFacts")
    return meal_plan


async def optimize_meal_plan_portions(
    meal_plan: dict[str, Any],
    target_totals: dict[str, float],
    user_allergens: list[str],
) -> dict[str, Any]:
    """Optimize meal plan portions to hit target macros.

    Strategy:
    1. Selective fat reduction - targets high-fat ingredients when fat >20% over target
    2. Try portion scaling (±50% max) - preserves recipe naturalness
    3. If insufficient, add complement foods (max 2 per day)

    Args:
        meal_plan: Meal plan with calculated macros
        target_totals: Target daily macros (calories, protein_g, carbs_g, fat_g)
        user_allergens: List of user allergens (lowercase)

    Returns:
        Optimized meal plan with adjusted portions and/or complements

    Example:
        >>> optimized = await optimize_meal_plan_portions(plan, targets, allergens)
        >>> print(optimized["days"][0]["optimization_summary"])
        "Portions scaled by 1.11x to hit targets"

    References:
        - Helms et al. (2014): Portion scaling maintains adherence
        - ISSN (2017): ±5% tolerance for competitive athletes
    """
    logger.info("🔧 Optimizing portions to hit targets...")

    for day in meal_plan.get("days", []):
        day_name = day.get("day", "Unknown")
        daily_totals = day.get("daily_totals", {})

        # Step 1: Calculate deficit
        deficit = calculate_macro_deficit(daily_totals, target_totals)
        needs = needs_adjustment(deficit, target_totals)

        # Step 2: Check if within tolerance
        if not any(needs.values()):
            logger.info(f"✅ {day_name}: Already within tolerance (±5%)")
            day["optimization_summary"] = "No adjustment needed (within ±5% tolerance)"
            continue

        # Step 2.5: SELECTIVE FAT REDUCTION (before uniform scaling)
        # When fat is significantly over target, reduce high-fat ingredients first
        target_fat = target_totals.get("fat_g", 0)
        actual_fat = daily_totals.get("fat_g", 0)
        fat_surplus_ratio = (
            (actual_fat - target_fat) / target_fat if target_fat > 0 else 0
        )

        optimization_notes = []
        if fat_surplus_ratio > FAT_SURPLUS_THRESHOLD:
            target_calories = target_totals.get("calories", 0)
            day, fat_removed = _rebalance_high_fat_day(
                day, target_fat, day_name, target_calories
            )
            if fat_removed > 0:
                optimization_notes.append(
                    f"fat reduced {fat_removed:.0f}g via selective reduction"
                )
                # Update daily_totals reference after modification
                daily_totals = day.get("daily_totals", {})
                # Recalculate deficit after fat reduction
                deficit = calculate_macro_deficit(daily_totals, target_totals)
                needs = needs_adjustment(deficit, target_totals)

                # Check if we're now within tolerance
                if not any(needs.values()):
                    logger.info(f"✅ {day_name}: Within tolerance after fat reduction")
                    day[
                        "optimization_summary"
                    ] = "Fat reduced via selective ingredient scaling"
                    continue

        # Step 3: Try portion scaling
        actual_calories = daily_totals.get("calories", 0)
        target_calories = target_totals.get("calories", 0)

        if actual_calories > 0:
            scale_factor = target_calories / actual_calories
            scale_factor = max(MIN_SCALE_FACTOR, min(MAX_SCALE_FACTOR, scale_factor))

            logger.info(f"🔧 {day_name}: Scaling portions by {scale_factor:.2f}x")

            # Apply scaling to all meals (skip complements)
            for meal in day.get("meals", []):
                # Skip meals already tagged as complements
                if "complement" in meal.get("tags", []):
                    continue

                # Scale ingredients
                for ingredient in meal.get("ingredients", []):
                    if "quantity" in ingredient:
                        scaled_qty = ingredient["quantity"] * scale_factor
                        ingredient["quantity"] = round_quantity_smart(
                            scaled_qty,
                            ingredient.get("unit", "g"),
                            ingredient.get("name", ""),
                        )

                    if "nutrition" in ingredient:
                        ingredient["nutrition"]["calories"] = round(
                            ingredient["nutrition"]["calories"] * scale_factor, 1
                        )
                        ingredient["nutrition"]["protein_g"] = round(
                            ingredient["nutrition"]["protein_g"] * scale_factor, 1
                        )
                        ingredient["nutrition"]["carbs_g"] = round(
                            ingredient["nutrition"]["carbs_g"] * scale_factor, 1
                        )
                        ingredient["nutrition"]["fat_g"] = round(
                            ingredient["nutrition"]["fat_g"] * scale_factor, 1
                        )

                # Scale meal nutrition
                if "nutrition" in meal:
                    meal["nutrition"]["calories"] = round(
                        meal["nutrition"]["calories"] * scale_factor, 1
                    )
                    meal["nutrition"]["protein_g"] = round(
                        meal["nutrition"]["protein_g"] * scale_factor, 1
                    )
                    meal["nutrition"]["carbs_g"] = round(
                        meal["nutrition"]["carbs_g"] * scale_factor, 1
                    )
                    meal["nutrition"]["fat_g"] = round(
                        meal["nutrition"]["fat_g"] * scale_factor, 1
                    )

            # Scale daily totals
            daily_totals["calories"] = round(daily_totals["calories"] * scale_factor, 1)
            daily_totals["protein_g"] = round(
                daily_totals["protein_g"] * scale_factor, 1
            )
            daily_totals["carbs_g"] = round(daily_totals["carbs_g"] * scale_factor, 1)
            daily_totals["fat_g"] = round(daily_totals["fat_g"] * scale_factor, 1)

            # Recalculate deficit after scaling
            deficit = calculate_macro_deficit(daily_totals, target_totals)
            needs = needs_adjustment(deficit, target_totals)

            optimization_notes.append(f"portions scaled {scale_factor:.2f}x")
            day["optimization_summary"] = ", ".join(optimization_notes)

        # Step 4: Add complements if scaling insufficient AND there's a deficit
        # IMPORTANT: Only add complements for DEFICITS (negative), never for SURPLUSES (positive)
        # SPECIAL CASE: If calories are already OVER target, don't add complements
        # even if protein is low (adding protein also adds calories, worsening the surplus)
        has_calorie_deficit = deficit.get("calories", 0) < 0
        has_protein_deficit = deficit.get("protein_g", 0) < 0

        # Only add complements if:
        # 1. There's a calorie deficit (can safely add calories+protein), OR
        # 2. Protein deficit AND calories within tolerance (won't push over limit)
        calorie_tolerance = target_totals.get("calories", 1) * 0.05
        calories_within_tolerance = abs(deficit.get("calories", 0)) <= calorie_tolerance

        has_deficit = has_calorie_deficit or (
            has_protein_deficit and calories_within_tolerance
        )

        logger.debug(
            f"{day_name} deficit check: cal_deficit={has_calorie_deficit}, "
            f"prot_deficit={has_protein_deficit}, cal_ok={calories_within_tolerance}, "
            f"will_add_complements={has_deficit}"
        )

        complements_added = 0
        iterations = 0
        max_iterations = MAX_COMPLEMENTS_PER_DAY
        used_complements: set[str] = set()

        while any(needs.values()) and has_deficit and iterations < max_iterations:
            complement_food = select_complement_food(
                deficit, user_allergens, timing_preference="collation"
            )

            if not complement_food:
                logger.warning(f"⚠️ {day_name}: No safe complement foods available")
                break

            # Avoid adding the same complement twice
            if complement_food["name"] in used_complements:
                logger.debug(
                    f"{day_name}: Complement '{complement_food['name']}' already used, stopping"
                )
                break
            used_complements.add(complement_food["name"])

            # Find an existing snack to add the complement to (prefer Collation PM)
            target_meal = None
            snack_keywords = ["collation", "snack", "goûter", "encas"]

            for meal in day.get("meals", []):
                meal_name = meal.get("name", "").lower()
                meal_type = meal.get("meal_type", "").lower()
                if any(kw in meal_name or kw in meal_type for kw in snack_keywords):
                    target_meal = meal
                    break

            # If no snack found, use the last meal of the day
            if target_meal is None and day.get("meals"):
                target_meal = day["meals"][-1]

            if target_meal is None:
                logger.warning(f"⚠️ {day_name}: No meal found to add complement")
                break

            # Add complement as additional ingredient to existing meal
            complement_ingredient = {
                "name": complement_food["name"],
                "quantity": 1,
                "unit": "portion",
                "nutrition": complement_food["nutrition"],
                "is_complement": True,
            }
            target_meal.setdefault("ingredients", []).append(complement_ingredient)

            # Update meal nutrition totals
            if "nutrition" in target_meal:
                target_meal["nutrition"]["calories"] += complement_food["nutrition"][
                    "calories"
                ]
                target_meal["nutrition"]["protein_g"] += complement_food["nutrition"][
                    "protein_g"
                ]
                target_meal["nutrition"]["carbs_g"] += complement_food["nutrition"][
                    "carbs_g"
                ]
                target_meal["nutrition"]["fat_g"] += complement_food["nutrition"][
                    "fat_g"
                ]

            # Mark meal as having complements
            target_meal.setdefault("tags", []).append("complement_added")

            # Update daily totals
            daily_totals["calories"] += complement_food["nutrition"]["calories"]
            daily_totals["protein_g"] += complement_food["nutrition"]["protein_g"]
            daily_totals["carbs_g"] += complement_food["nutrition"]["carbs_g"]
            daily_totals["fat_g"] += complement_food["nutrition"]["fat_g"]

            logger.info(
                f"  → Added {complement_food['name']} "
                f"(+{complement_food['nutrition']['calories']} kcal, +{complement_food['nutrition']['protein_g']}g protein)"
            )

            # Recalculate deficit
            deficit = calculate_macro_deficit(daily_totals, target_totals)
            needs = needs_adjustment(deficit, target_totals)

            complements_added += 1
            iterations += 1

        # Update summary
        if complements_added > 0:
            day["optimization_summary"] += f", {complements_added} complement(s) added"

        # Final status
        if any(needs.values()):
            logger.warning(f"⚠️ {day_name}: Still outside tolerance after optimization")
        else:
            logger.info(f"✅ {day_name}: Within tolerance after optimization")

    logger.info("✅ Optimization complete for all days")
    return meal_plan


def generate_adjustment_summary(
    meal_plan: dict[str, Any],
    target_totals: dict[str, float],
) -> str:
    """Generate user-friendly summary of macro adjustments.

    Args:
        meal_plan: Optimized meal plan
        target_totals: Target macros

    Returns:
        Formatted summary string

    Example:
        >>> summary = generate_adjustment_summary(plan, targets)
        >>> print(summary)
        "7/7 days within ±5% tolerance. Average: 2955 kcal, 156g protein"
    """
    days_within_tolerance = 0
    total_days = len(meal_plan.get("days", []))

    avg_calories = 0.0
    avg_protein = 0.0

    for day in meal_plan.get("days", []):
        daily_totals = day.get("daily_totals", {})

        # Check tolerance
        deficit = calculate_macro_deficit(daily_totals, target_totals)
        needs = needs_adjustment(deficit, target_totals)

        if not any(needs.values()):
            days_within_tolerance += 1

        avg_calories += daily_totals.get("calories", 0)
        avg_protein += daily_totals.get("protein_g", 0)

    if total_days > 0:
        avg_calories /= total_days
        avg_protein /= total_days

    summary = (
        f"✅ {days_within_tolerance}/{total_days} days within ±5% tolerance.\n"
        f"Average: {avg_calories:.0f} kcal, {avg_protein:.0f}g protein\n"
        f"Target: {target_totals['calories']:.0f} kcal, {target_totals['protein_g']:.0f}g protein"
    )

    return summary
