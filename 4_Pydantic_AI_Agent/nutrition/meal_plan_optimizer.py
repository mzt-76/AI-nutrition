"""Meal plan macro calculation and portion optimization using OpenFoodFacts.

This module provides:
1. Precise macro calculation using OpenFoodFacts-validated ingredient data
2. Portion scaling optimization (±25% max) to hit targets
3. Complement food addition as fallback (minimal usage)

References:
    Helms et al. (2014): Portion scaling maintains adherence better than artificial supplements
    ISSN (2017): Protein requirements for muscle gain
"""

import logging
from typing import Any

from supabase import Client

from nutrition.openfoodfacts_client import match_ingredient
from nutrition.macro_adjustments import (
    calculate_macro_deficit,
    needs_adjustment,
    select_complement_food,
)

logger = logging.getLogger(__name__)

# Portion scaling constraints
# Increased from ±25% to ±50% for better macro accuracy
# Still maintains recipe naturalness while giving optimizer more flexibility
MIN_SCALE_FACTOR = 0.50  # Don't scale down more than 50%
MAX_SCALE_FACTOR = 1.50  # Don't scale up more than 50%

# Maximum complements to add per day (prefer scaling over complements)
MAX_COMPLEMENTS_PER_DAY = 2


def round_quantity_smart(
    quantity: float, unit: str, ingredient_name: str = ""
) -> float:
    """
    Round quantity intelligently based on unit and ingredient type.

    Args:
        quantity: Raw quantity value
        unit: Unit of measurement (g, ml, pièces, etc.)
        ingredient_name: Name of ingredient (for context)

    Returns:
        Rounded quantity following UX guidelines

    Rules:
        - Countable items (pièces, oeufs, tranches): Always whole numbers
        - Grams (g): Round to integer
        - Milliliters (ml): Round to integer
        - Small spices/seasonings (< 10g): Keep 1 decimal
    """
    unit_lower = unit.lower().strip()
    name_lower = ingredient_name.lower().strip()

    # Countable units: always whole numbers
    countable_units = [
        "pièces",
        "piece",
        "pieces",
        "pièce",
        "tranche",
        "tranches",
        "slice",
        "oeuf",
        "oeufs",
        "egg",
        "eggs",
    ]
    if any(u in unit_lower for u in countable_units):
        return round(quantity)

    # Grams and milliliters
    if unit_lower in [
        "g",
        "gram",
        "gramme",
        "grammes",
        "grams",
        "ml",
        "millilitre",
        "millilitres",
        "milliliter",
        "milliliters",
    ]:
        # Exception: small quantities of spices/seasonings (< 10)
        spice_keywords = [
            "sel",
            "salt",
            "poivre",
            "pepper",
            "épice",
            "spice",
            "herbe",
            "herb",
            "cannelle",
            "cinnamon",
        ]
        if quantity < 10 and any(keyword in name_lower for keyword in spice_keywords):
            return round(quantity, 1)

        # Default: round to integer
        return round(quantity)

    # Other units: keep 1 decimal as fallback
    return round(quantity, 1)


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

            for ingredient in ingredients:
                ingredient_name = ingredient.get("name", "")
                quantity = ingredient.get("quantity", 0)
                unit = ingredient.get("unit", "g")

                if not ingredient_name or quantity == 0:
                    logger.warning(f"Skipping invalid ingredient: {ingredient}")
                    continue

                try:
                    # Match ingredient via OpenFoodFacts (with caching)
                    ingredient_macros = await match_ingredient(
                        ingredient_name=ingredient_name,
                        quantity=quantity,
                        unit=unit,
                        supabase=supabase,
                    )

                    # Track cache stats
                    if ingredient_macros["cache_hit"]:
                        cache_stats["hits"] += 1
                    else:
                        cache_stats["misses"] += 1

                    # Store OpenFoodFacts data in ingredient
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

                    # Accumulate to meal totals
                    meal_totals["calories"] += ingredient_macros["calories"]
                    meal_totals["protein_g"] += ingredient_macros["protein_g"]
                    meal_totals["carbs_g"] += ingredient_macros["carbs_g"]
                    meal_totals["fat_g"] += ingredient_macros["fat_g"]

                except ValueError as e:
                    # Ingredient not found in OpenFoodFacts - log and skip
                    logger.warning(
                        f"⚠️ Could not match ingredient '{ingredient_name}': {e}"
                    )
                    ingredient["openfoodfacts_error"] = str(e)
                    continue

                except Exception as e:
                    # Unexpected error - log and skip
                    logger.error(
                        f"❌ Error processing ingredient '{ingredient_name}': {e}",
                        exc_info=True,
                    )
                    ingredient["openfoodfacts_error"] = str(e)
                    continue

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
    1. Try portion scaling (±25% max) - preserves recipe naturalness
    2. If insufficient, add complement foods (max 2 per day)

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

            day["optimization_summary"] = f"Portions scaled by {scale_factor:.2f}x"

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

        while any(needs.values()) and has_deficit and iterations < max_iterations:
            complement_food = select_complement_food(
                deficit, user_allergens, timing_preference="collation"
            )

            if not complement_food:
                logger.warning(f"⚠️ {day_name}: No safe complement foods available")
                break

            # Create complement meal
            complement_meal = {
                "name": complement_food["name"],
                "time": "16:00",  # Default snack time
                "ingredients": [
                    {
                        "name": complement_food["name"],
                        "quantity": 1,
                        "unit": "portion",
                        "nutrition": complement_food["nutrition"],
                    }
                ],
                "nutrition": complement_food["nutrition"],
                "instructions": complement_food["prep_note"],
                "tags": ["complement", "optimisé"],
            }

            # Add to meals
            day["meals"].append(complement_meal)

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
