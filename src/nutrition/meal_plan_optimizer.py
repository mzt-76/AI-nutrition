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

from src.nutrition.openfoodfacts_client import match_ingredient
from src.nutrition.macro_adjustments import (
    calculate_macro_deficit,
    needs_adjustment,
    select_complement_food,
)

logger = logging.getLogger(__name__)

# Portion scaling constraints
# 2.5x allows a 340 kcal recipe to reach 850 kcal (muscle gain targets)
# Smart rounding keeps portions natural (whole eggs, rounded grams)
MIN_SCALE_FACTOR = 0.50  # Don't scale down more than 50%
MAX_SCALE_FACTOR = 2.50  # "Double serving + a bit" — reasonable for high-cal targets

# Maximum complements to add per day (prefer scaling over complements)
MAX_COMPLEMENTS_PER_DAY = 2

# Aggressive scaling for high-fat ingredients when fat is way over target
FAT_INGREDIENT_MIN_SCALE = 0.25  # Can scale oils/fats down to 25%
FAT_SURPLUS_THRESHOLD = 0.20  # Trigger selective fat reduction at >20% over target

# High-fat ingredient categories (fat_ratio = typical fat percentage)
HIGH_FAT_INGREDIENTS = {
    # Pure fats - can be reduced aggressively
    "oil": {"fat_ratio": 1.0, "min_scale": 0.15},  # olive oil, vegetable oil
    "huile": {"fat_ratio": 1.0, "min_scale": 0.15},
    "butter": {"fat_ratio": 0.81, "min_scale": 0.20},
    "beurre": {"fat_ratio": 0.81, "min_scale": 0.20},
    # High-fat dairy
    "cheese": {"fat_ratio": 0.33, "min_scale": 0.30},
    "fromage": {"fat_ratio": 0.33, "min_scale": 0.30},
    "cream": {"fat_ratio": 0.35, "min_scale": 0.30},
    "crème": {"fat_ratio": 0.35, "min_scale": 0.30},
    # High-fat proteins
    "bacon": {"fat_ratio": 0.42, "min_scale": 0.40},
    "sausage": {"fat_ratio": 0.30, "min_scale": 0.40},
    "saucisse": {"fat_ratio": 0.30, "min_scale": 0.40},
    # High-fat plants
    "avocado": {"fat_ratio": 0.15, "min_scale": 0.40},
    "avocat": {"fat_ratio": 0.15, "min_scale": 0.40},
    "nut": {"fat_ratio": 0.55, "min_scale": 0.35},
    "noix": {"fat_ratio": 0.55, "min_scale": 0.35},
    "almond": {"fat_ratio": 0.50, "min_scale": 0.35},
    "amande": {"fat_ratio": 0.50, "min_scale": 0.35},
    "peanut": {"fat_ratio": 0.50, "min_scale": 0.35},
    "cacahuète": {"fat_ratio": 0.50, "min_scale": 0.35},
    # Fatty fish (moderate reduction)
    "salmon": {"fat_ratio": 0.13, "min_scale": 0.50},
    "saumon": {"fat_ratio": 0.13, "min_scale": 0.50},
}


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


def _is_high_fat_ingredient(ingredient_name: str) -> tuple[bool, str, dict]:
    """Check if ingredient is high-fat and return its fat profile.

    Args:
        ingredient_name: Name of the ingredient

    Returns:
        Tuple of (is_high_fat, matched_keyword, fat_profile)
    """
    name_lower = ingredient_name.lower()
    for keyword, profile in HIGH_FAT_INGREDIENTS.items():
        if keyword in name_lower:
            return True, keyword, profile
    return False, "", {}


def _rebalance_high_fat_day(
    day: dict[str, Any],
    target_fat: float,
    day_name: str,
    target_calories: float = 0,
) -> tuple[dict[str, Any], float]:
    """Selectively reduce high-fat ingredients in a day's meals.

    When fat is significantly over target (>20%), this function:
    1. Identifies high-fat ingredients (oils, cheese, fatty meats)
    2. Calculates how much fat needs to be removed
    3. Scales down high-fat ingredients proportionally
    4. Preserves low-fat ingredients (proteins, carbs)
    5. Protects calories from dropping below 70% of target

    Args:
        day: Day dict with meals and daily_totals
        target_fat: Target daily fat in grams
        day_name: Day name for logging
        target_calories: Target daily calories (for protection against over-reduction)

    Returns:
        Tuple of (modified_day, fat_removed)

    Example:
        >>> day = {"meals": [...], "daily_totals": {"fat_g": 200}}
        >>> modified, removed = _rebalance_high_fat_day(day, 72, "Lundi", 3000)
        >>> removed > 0
        True
    """
    daily_totals = day.get("daily_totals", {})
    actual_fat = daily_totals.get("fat_g", 0)

    # Check if fat reduction is needed
    if actual_fat <= 0 or target_fat <= 0:
        return day, 0.0

    fat_surplus_ratio = (actual_fat - target_fat) / target_fat
    if fat_surplus_ratio < FAT_SURPLUS_THRESHOLD:
        logger.debug(f"{day_name}: Fat surplus {fat_surplus_ratio:.1%} below threshold")
        return day, 0.0

    logger.info(
        f"🔧 {day_name}: Fat is {fat_surplus_ratio:.1%} over target "
        f"({actual_fat:.0f}g vs {target_fat:.0f}g) - applying selective reduction"
    )

    # Calculate how much fat to remove
    # Goal: get to target fat + 10% buffer (allows uniform scaling to fine-tune)
    target_with_buffer = target_fat * 1.10  # 10% buffer above target
    fat_to_remove = actual_fat - target_with_buffer
    fat_removed_total = 0.0

    # CALORIE PROTECTION: Limit fat removal so calories stay recoverable
    # When reducing high-fat ingredients, we also reduce their protein/carbs
    # Total calorie impact is ~12-15 kcal per gram of fat removed
    actual_calories = daily_totals.get("calories", 0)
    if target_calories > 0 and actual_calories > 0:
        # Allow calories to drop to 60% of target - complements can add the rest
        # This is more aggressive but necessary for extreme fat surpluses
        min_calories = target_calories * 0.60
        max_calorie_reduction = actual_calories - min_calories
        # Use 12 kcal per gram of fat (conservative estimate)
        max_fat_removal = max_calorie_reduction / 12

        if fat_to_remove > max_fat_removal and max_fat_removal > 0:
            logger.info(
                f"  ⚠️ Capping fat removal to protect calories: "
                f"{fat_to_remove:.0f}g → {max_fat_removal:.0f}g "
                f"(floor: {min_calories:.0f} kcal)"
            )
            fat_to_remove = max(0, max_fat_removal)

    # Collect all high-fat ingredients across meals
    high_fat_items: list[
        tuple[dict, dict, str, dict]
    ] = []  # (ingredient, meal, keyword, profile)

    for meal in day.get("meals", []):
        for ingredient in meal.get("ingredients", []):
            name = ingredient.get("name", "")
            is_high_fat, keyword, profile = _is_high_fat_ingredient(name)
            if is_high_fat and "nutrition" in ingredient:
                high_fat_items.append((ingredient, meal, keyword, profile))

    if not high_fat_items:
        logger.warning(f"⚠️ {day_name}: No high-fat ingredients found to reduce")
        return day, 0.0

    # Sort by fat contribution (highest first) for prioritized reduction
    high_fat_items.sort(
        key=lambda x: x[0].get("nutrition", {}).get("fat_g", 0),
        reverse=True,
    )

    logger.info(f"  Found {len(high_fat_items)} high-fat ingredients to reduce")

    # Calculate total fat from high-fat ingredients
    total_high_fat = sum(
        item[0].get("nutrition", {}).get("fat_g", 0) for item in high_fat_items
    )

    # Distribute fat reduction proportionally among high-fat ingredients
    for ingredient, meal, keyword, profile in high_fat_items:
        if fat_removed_total >= fat_to_remove:
            break

        nutrition = ingredient.get("nutrition", {})
        ingredient_fat = nutrition.get("fat_g", 0)

        if ingredient_fat <= 0:
            continue

        # Calculate how much to reduce this ingredient
        # Proportional share of fat to remove
        reduction_share = (ingredient_fat / total_high_fat) * fat_to_remove

        # Calculate scale factor (respect min_scale from profile)
        min_scale = profile.get("min_scale", FAT_INGREDIENT_MIN_SCALE)
        ideal_scale = max(0, (ingredient_fat - reduction_share) / ingredient_fat)
        scale_factor = max(min_scale, ideal_scale)

        # Calculate actual fat reduction
        new_fat = ingredient_fat * scale_factor
        fat_reduction = ingredient_fat - new_fat
        fat_removed_total += fat_reduction

        # Apply scaling to ingredient
        old_qty = ingredient.get("quantity", 0)
        ingredient["quantity"] = round_quantity_smart(
            old_qty * scale_factor,
            ingredient.get("unit", "g"),
            ingredient.get("name", ""),
        )

        # Scale all macros proportionally
        for macro in ["calories", "protein_g", "carbs_g", "fat_g"]:
            if macro in nutrition:
                nutrition[macro] = round(nutrition[macro] * scale_factor, 1)

        # Update meal totals
        meal_nutrition = meal.get("nutrition", {})
        for macro in ["calories", "protein_g", "carbs_g", "fat_g"]:
            if macro in meal_nutrition:
                reduction = (
                    (1 - scale_factor)
                    * ingredient.get("nutrition", {}).get(macro, 0)
                    / scale_factor
                    if scale_factor > 0
                    else 0
                )
                meal_nutrition[macro] = round(meal_nutrition[macro] - reduction, 1)

        logger.info(
            f"  → {ingredient.get('name', 'Unknown')}: "
            f"scaled {scale_factor:.2f}x (qty: {old_qty}→{ingredient['quantity']}, "
            f"fat: {ingredient_fat:.0f}g→{new_fat:.0f}g)"
        )

    # Recalculate daily totals
    new_daily_totals = {"calories": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0}
    for meal in day.get("meals", []):
        for ingredient in meal.get("ingredients", []):
            nutrition = ingredient.get("nutrition", {})
            new_daily_totals["calories"] += nutrition.get("calories", 0)
            new_daily_totals["protein_g"] += nutrition.get("protein_g", 0)
            new_daily_totals["carbs_g"] += nutrition.get("carbs_g", 0)
            new_daily_totals["fat_g"] += nutrition.get("fat_g", 0)

    # Round and update
    day["daily_totals"] = {
        "calories": round(new_daily_totals["calories"], 1),
        "protein_g": round(new_daily_totals["protein_g"], 1),
        "carbs_g": round(new_daily_totals["carbs_g"], 1),
        "fat_g": round(new_daily_totals["fat_g"], 1),
    }

    logger.info(
        f"  ✅ Fat reduced from {actual_fat:.0f}g to {day['daily_totals']['fat_g']:.0f}g "
        f"(removed {fat_removed_total:.0f}g)"
    )

    return day, fat_removed_total


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

        while any(needs.values()) and has_deficit and iterations < max_iterations:
            complement_food = select_complement_food(
                deficit, user_allergens, timing_preference="collation"
            )

            if not complement_food:
                logger.warning(f"⚠️ {day_name}: No safe complement foods available")
                break

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
