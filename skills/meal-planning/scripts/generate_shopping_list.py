"""Generate a categorized shopping list from a stored meal plan.

Fetches the meal plan from DB, extracts all ingredients, aggregates by
ingredient+unit, and categorizes by food group.

Source: Refactored from src/tools.py generate_shopping_list_tool
"""

import json
import logging
from datetime import datetime

from src.nutrition.meal_planning import (
    extract_ingredients_from_meal_plan,
    aggregate_ingredients,
    categorize_ingredients,
)

logger = logging.getLogger(__name__)

_DAY_NAMES = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]


async def execute(**kwargs) -> str:
    """Generate categorized shopping list from meal plan.

    Args:
        supabase: Supabase client
        week_start: Meal plan start date in YYYY-MM-DD format
        selected_days: List of day indices to include (0-6), None for all 7 days
        servings_multiplier: Multiplier for all quantities (default: 1.0)

    Returns:
        JSON with categorized shopping list:
        {
            "success": true,
            "shopping_list": {
                "Proteines": [{"name": "poulet", "quantity": 700, "unit": "g"}],
                "Feculents": [...],
                ...
            },
            "metadata": {
                "week_start": "2026-02-18",
                "days_included": [0, 1, 2, ...],
                "total_items": 42
            }
        }
    """
    supabase = kwargs["supabase"]
    week_start = kwargs["week_start"]
    selected_days = kwargs.get("selected_days")
    servings_multiplier = kwargs.get("servings_multiplier", 1.0)

    try:
        logger.info(
            f"Generating shopping list: week={week_start}, days={selected_days}, "
            f"multiplier={servings_multiplier}"
        )

        # Step 1: Validate date format
        try:
            datetime.strptime(week_start, "%Y-%m-%d")
        except ValueError:
            return json.dumps(
                {
                    "error": "Invalid date format. Use YYYY-MM-DD (e.g., 2024-12-23)",
                    "code": "VALIDATION_ERROR",
                }
            )

        # Step 2: Validate servings multiplier
        if servings_multiplier <= 0:
            return json.dumps(
                {
                    "error": "Servings multiplier must be greater than 0",
                    "code": "VALIDATION_ERROR",
                }
            )

        # Step 3: Validate selected_days if provided
        if selected_days is not None:
            if not selected_days:
                return json.dumps(
                    {
                        "error": "selected_days cannot be empty. Use null for all days or provide day indices (0-6)",
                        "code": "VALIDATION_ERROR",
                    }
                )
            if any(day < 0 or day > 6 for day in selected_days):
                return json.dumps(
                    {
                        "error": "Day indices must be between 0 and 6",
                        "code": "VALIDATION_ERROR",
                    }
                )

        # Step 4: Fetch meal plan from database
        meal_plan_response = (
            supabase.table("meal_plans")
            .select("*")
            .eq("week_start", week_start)
            .limit(1)
            .execute()
        )

        if not meal_plan_response.data:
            return json.dumps(
                {
                    "error": f"No meal plan found for week starting {week_start}",
                    "code": "MEAL_PLAN_NOT_FOUND",
                    "suggestion": "Generate a meal plan first using generate_weekly_meal_plan",
                }
            )

        meal_plan_record = meal_plan_response.data[0]
        plan_data = meal_plan_record.get("plan_data")

        if not plan_data:
            return json.dumps(
                {
                    "error": "Meal plan data is empty or invalid",
                    "code": "INVALID_MEAL_PLAN",
                }
            )

        logger.info(
            f"Meal plan retrieved: {len(plan_data.get('days', []))} days available"
        )

        # Step 5: Extract ingredients from selected days
        ingredients_list = extract_ingredients_from_meal_plan(plan_data, selected_days)

        if not ingredients_list:
            return json.dumps(
                {
                    "error": "No ingredients found in selected days",
                    "code": "NO_INGREDIENTS",
                    "selected_days": selected_days,
                }
            )

        logger.info(f"Extracted {len(ingredients_list)} total ingredients")

        # Step 6: Aggregate and categorize
        aggregated = aggregate_ingredients(ingredients_list, servings_multiplier)
        categorized = categorize_ingredients(aggregated)

        # Step 7: Build response with metadata
        days_included = selected_days if selected_days else list(range(7))
        days_description = ", ".join(
            [_DAY_NAMES[d] for d in sorted(days_included)]
        )
        total_items = sum(len(items) for items in categorized.values())

        response = {
            "success": True,
            "shopping_list": categorized,
            "metadata": {
                "week_start": week_start,
                "days_included": days_included,
                "days_description": days_description,
                "servings_multiplier": servings_multiplier,
                "total_items": total_items,
                "categories": {
                    cat: len(items) for cat, items in categorized.items() if items
                },
            },
            "message": f"Shopping list generated for {len(days_included)} days",
        }

        logger.info(
            f"Shopping list: {total_items} items across "
            f"{len([c for c in categorized.values() if c])} categories"
        )
        return json.dumps(response, indent=2, ensure_ascii=False)

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return json.dumps({"error": str(e), "code": "VALIDATION_ERROR"})
    except Exception as e:
        logger.error(f"Unexpected error generating shopping list: {e}", exc_info=True)
        return json.dumps(
            {
                "error": "Internal error generating shopping list",
                "code": "GENERATION_ERROR",
            }
        )
