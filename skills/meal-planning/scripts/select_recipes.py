"""Select recipes from database for a single day's meals.

Queries the recipe DB with allergen exclusion, variety tracking,
and preference filtering. Returns candidate recipes for each meal slot.

Source: New script for day-by-day meal planning workflow
"""

import json
import logging

from src.nutrition.recipe_db import search_recipes, score_recipe_variety

logger = logging.getLogger(__name__)

# Meal type mapping from display names to DB keys
MEAL_TYPE_MAP = {
    "Petit-déjeuner": "petit-dejeuner",
    "Déjeuner": "dejeuner",
    "Dîner": "diner",
    "Collation AM": "collation",
    "Collation PM": "collation",
    "Collation": "collation",
    "Repas 1": "dejeuner",
    "Repas 2": "dejeuner",
    "Repas 3": "diner",
    "Repas 4": "diner",
}


def _normalize_meal_type(meal_type_display: str) -> str:
    """Map display meal type to DB meal_type key."""
    for key, value in MEAL_TYPE_MAP.items():
        if key.lower() in meal_type_display.lower():
            return value
    # Default fallback based on common keywords
    meal_lower = meal_type_display.lower()
    if "dejeuner" in meal_lower or "déjeuner" in meal_lower:
        return "dejeuner"
    if "diner" in meal_lower or "dîner" in meal_lower:
        return "diner"
    if "petit" in meal_lower or "breakfast" in meal_lower:
        return "petit-dejeuner"
    if "collation" in meal_lower or "snack" in meal_lower:
        return "collation"
    return "dejeuner"  # Safe fallback


async def execute(**kwargs) -> str:
    """Select recipes for one day.

    Args:
        supabase: Supabase client
        meal_targets: List of meal slot targets from meal_distribution
            [{"meal_type": "Petit-déjeuner", "time": "08:00",
              "target_calories": 750, "target_protein_g": 40, ...}]
        user_allergens: Allergen list from profile (default [])
        diet_type: User diet type (default "omnivore")
        preferred_cuisines: List of preferred cuisines (default None)
        max_prep_time: Max prep time in minutes (default None)
        exclude_recipe_ids: Recipe IDs already used this week (default [])
        favorite_foods: User's favorite foods — not used for filtering yet

    Returns:
        JSON with selected recipes per meal slot:
        {
            "day_recipes": [
                {"meal_slot": {...targets}, "recipe": {...}, "source": "db"},
                {"meal_slot": {...targets}, "recipe": null, "source": "no_match"}
            ],
            "unmatched_slots": 0
        }
    """
    supabase = kwargs["supabase"]
    meal_targets = kwargs["meal_targets"]
    user_allergens = kwargs.get("user_allergens", [])
    diet_type = kwargs.get("diet_type", "omnivore")
    preferred_cuisines = kwargs.get("preferred_cuisines")
    max_prep_time = kwargs.get("max_prep_time")
    exclude_recipe_ids = list(kwargs.get("exclude_recipe_ids", []))
    disliked_foods = kwargs.get("disliked_foods", [])

    try:
        logger.info(
            f"Selecting recipes for {len(meal_targets)} meal slots, "
            f"diet_type={diet_type}, exclude_allergens={user_allergens}"
        )

        day_recipes = []
        used_ids_this_day: list[str] = []

        for meal_slot in meal_targets:
            meal_type_display = meal_slot.get("meal_type", "Déjeuner")
            db_meal_type = _normalize_meal_type(meal_type_display)

            target_calories = meal_slot.get("target_calories", 600)

            # Build a calorie range: ±40% around target (wider to get more candidates)
            calorie_range = (
                int(target_calories * 0.6),
                int(target_calories * 1.4),
            )

            # Combine weekly exclude + already used today
            all_excluded = exclude_recipe_ids + used_ids_this_day

            candidates = await search_recipes(
                supabase=supabase,
                meal_type=db_meal_type,
                exclude_allergens=user_allergens if user_allergens else None,
                exclude_recipe_ids=all_excluded if all_excluded else None,
                exclude_ingredients=disliked_foods if disliked_foods else None,
                diet_type=diet_type,
                cuisine_types=preferred_cuisines,
                max_prep_time=max_prep_time,
                calorie_range=calorie_range,
                limit=5,
            )

            if candidates:
                # Sort by multi-factor variety score (higher = better)
                candidates.sort(
                    key=lambda r: score_recipe_variety(
                        r, meal_slot, preferred_cuisines
                    ),
                    reverse=True,
                )
                recipe = candidates[0]
                used_ids_this_day.append(recipe["id"])
                day_recipes.append(
                    {
                        "meal_slot": meal_slot,
                        "recipe": recipe,
                        "source": "db",
                    }
                )
                logger.info(
                    f"  {meal_type_display}: selected '{recipe['name']}' "
                    f"({recipe['calories_per_serving']} kcal, target={target_calories})"
                )
            else:
                day_recipes.append(
                    {
                        "meal_slot": meal_slot,
                        "recipe": None,
                        "source": "no_match",
                    }
                )
                logger.warning(
                    f"  {meal_type_display}: NO recipe found in DB "
                    f"(meal_type={db_meal_type}, target={target_calories} kcal)"
                )

        unmatched = sum(1 for r in day_recipes if r["source"] == "no_match")

        if unmatched > 0:
            logger.warning(
                f"{unmatched}/{len(meal_targets)} meal slots have no DB match — "
                "will require LLM fallback"
            )

        return json.dumps(
            {"day_recipes": day_recipes, "unmatched_slots": unmatched},
            indent=2,
            ensure_ascii=False,
        )

    except ValueError as e:
        logger.error(f"Validation error in select_recipes: {e}")
        return json.dumps({"error": str(e), "code": "VALIDATION_ERROR"})
    except Exception as e:
        logger.error(f"Unexpected error in select_recipes: {e}", exc_info=True)
        return json.dumps({"error": "Internal error", "code": "SCRIPT_ERROR"})
