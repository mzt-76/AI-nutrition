"""Meal plan portion optimization constants and summary generation.

This module provides:
1. Portion scaling constants (MIN/MAX_SCALE_FACTOR)
2. Adjustment summary generation

The heavy runtime functions (calculate_meal_plan_macros, calculate_recipe_macros,
optimize_meal_plan_portions) were removed in the pipeline refactoring — recipes are
now pre-validated via OFF (scripts/validate_all_recipes.py) and scaled mathematically
at generation time, making runtime OFF recalc and post-hoc optimization unnecessary.

References:
    Helms et al. (2014): Portion scaling maintains adherence better than artificial supplements
    ISSN (2017): Protein requirements for muscle gain
"""

import logging
from typing import Any

from src.nutrition.macro_adjustments import (
    calculate_macro_deficit,
    needs_adjustment,
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
MAX_SCALE_FACTOR = 3.00  # Triple serving — covers 300→900 kcal for muscle gain


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
        f"{days_within_tolerance}/{total_days} days within tolerance.\n"
        f"Average: {avg_calories:.0f} kcal, {avg_protein:.0f}g protein\n"
        f"Target: {target_totals['calories']:.0f} kcal, {target_totals['protein_g']:.0f}g protein"
    )

    return summary
