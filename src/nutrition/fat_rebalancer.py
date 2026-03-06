"""Selective fat reduction for meal plan optimization.

When daily fat exceeds target by >20%, this module identifies high-fat ingredients
(oils, cheese, fatty meats) and scales them down proportionally while preserving
low-fat ingredients.

Extracted from meal_plan_optimizer.py for modularity.
"""

import copy
import logging
from typing import Any

from src.nutrition.quantity_rounding import round_quantity_smart

logger = logging.getLogger(__name__)

# Aggressive scaling for high-fat ingredients when fat is way over target
FAT_INGREDIENT_MIN_SCALE = 0.25  # Can scale oils/fats down to 25%
FAT_SURPLUS_THRESHOLD = 0.20  # Trigger selective fat reduction at >20% over target

# High-fat ingredient categories (fat_ratio = typical fat percentage)
HIGH_FAT_INGREDIENTS = {
    # Pure fats - can be reduced aggressively
    "oil": {"fat_ratio": 1.0, "min_scale": 0.15},
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


def rebalance_high_fat_day(
    day: dict[str, Any],
    target_fat: float,
    day_name: str,
    target_calories: float = 0,
) -> tuple[dict[str, Any], float]:
    """Selectively reduce high-fat ingredients in a day's meals.

    Works on a deep copy of the day to avoid mutation side-effects.

    When fat is significantly over target (>20%), this function:
    1. Identifies high-fat ingredients (oils, cheese, fatty meats)
    2. Calculates how much fat needs to be removed
    3. Scales down high-fat ingredients proportionally
    4. Preserves low-fat ingredients (proteins, carbs)
    5. Protects calories from dropping below 60% of target

    Args:
        day: Day dict with meals and daily_totals (not mutated)
        target_fat: Target daily fat in grams
        day_name: Day name for logging
        target_calories: Target daily calories (for protection against over-reduction)

    Returns:
        Tuple of (modified_day_copy, fat_removed)
    """
    day = copy.deepcopy(day)
    daily_totals = day.get("daily_totals", {})
    actual_fat = daily_totals.get("fat_g", 0)

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

    # Goal: get to target fat + 10% buffer
    target_with_buffer = target_fat * 1.10
    fat_to_remove = actual_fat - target_with_buffer
    fat_removed_total = 0.0

    # CALORIE PROTECTION: Limit fat removal so calories stay recoverable
    actual_calories = daily_totals.get("calories", 0)
    if target_calories > 0 and actual_calories > 0:
        min_calories = target_calories * 0.60
        max_calorie_reduction = actual_calories - min_calories
        max_fat_removal = max_calorie_reduction / 12

        if fat_to_remove > max_fat_removal and max_fat_removal > 0:
            logger.info(
                f"  ⚠️ Capping fat removal to protect calories: "
                f"{fat_to_remove:.0f}g → {max_fat_removal:.0f}g "
                f"(floor: {min_calories:.0f} kcal)"
            )
            fat_to_remove = max(0, max_fat_removal)

    # Collect all high-fat ingredients across meals
    high_fat_items: list[tuple[dict, dict, str, dict]] = []

    for meal in day.get("meals", []):
        for ingredient in meal.get("ingredients", []):
            name = ingredient.get("name", "")
            is_high_fat, keyword, profile = _is_high_fat_ingredient(name)
            if is_high_fat and "nutrition" in ingredient:
                high_fat_items.append((ingredient, meal, keyword, profile))

    if not high_fat_items:
        logger.warning(f"⚠️ {day_name}: No high-fat ingredients found to reduce")
        return day, 0.0

    # Sort by fat contribution (highest first)
    high_fat_items.sort(
        key=lambda x: x[0].get("nutrition", {}).get("fat_g", 0),
        reverse=True,
    )

    logger.info(f"  Found {len(high_fat_items)} high-fat ingredients to reduce")

    total_high_fat = sum(
        item[0].get("nutrition", {}).get("fat_g", 0) for item in high_fat_items
    )

    # Distribute fat reduction proportionally
    for ingredient, meal, keyword, profile in high_fat_items:
        if fat_removed_total >= fat_to_remove:
            break

        nutrition = ingredient.get("nutrition", {})
        ingredient_fat = nutrition.get("fat_g", 0)

        if ingredient_fat <= 0:
            continue

        reduction_share = (ingredient_fat / total_high_fat) * fat_to_remove
        min_scale = profile.get("min_scale", FAT_INGREDIENT_MIN_SCALE)
        ideal_scale = max(0, (ingredient_fat - reduction_share) / ingredient_fat)
        scale_factor = max(min_scale, ideal_scale)

        new_fat = ingredient_fat * scale_factor
        fat_reduction = ingredient_fat - new_fat
        fat_removed_total += fat_reduction

        old_qty = ingredient.get("quantity", 0)
        ingredient["quantity"] = round_quantity_smart(
            old_qty * scale_factor,
            ingredient.get("unit", "g"),
            ingredient.get("name", ""),
        )

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

    # Recalculate daily totals from scratch
    new_daily_totals = {"calories": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0}
    for meal in day.get("meals", []):
        for ingredient in meal.get("ingredients", []):
            nutrition = ingredient.get("nutrition", {})
            new_daily_totals["calories"] += nutrition.get("calories", 0)
            new_daily_totals["protein_g"] += nutrition.get("protein_g", 0)
            new_daily_totals["carbs_g"] += nutrition.get("carbs_g", 0)
            new_daily_totals["fat_g"] += nutrition.get("fat_g", 0)

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
