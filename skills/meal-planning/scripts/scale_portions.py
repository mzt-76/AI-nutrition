"""Scale recipe portions to match meal slot macro targets.

Takes a recipe and target macros, returns the recipe with scaled
ingredient quantities and updated nutrition.

Source: Extracted from src/nutrition/meal_plan_optimizer.py
"""

import json
import logging

from src.nutrition.portion_scaler import scale_recipe_to_targets

logger = logging.getLogger(__name__)


async def execute(**kwargs) -> str:
    """Scale recipe to targets.

    Args:
        recipe: Recipe dict from select_recipes or generate_custom_recipe.
                Must have calories_per_serving, protein_g_per_serving,
                carbs_g_per_serving, fat_g_per_serving, ingredients.
        target_calories: Target kcal for this meal slot
        target_protein_g: Target protein in grams
        target_carbs_g: Target carbs in grams (optional)
        target_fat_g: Target fat in grams (optional)

    Returns:
        JSON with scaled recipe + nutrition delta summary:
        {
            "scaled_recipe": {...recipe with scaled ingredients...},
            "scale_factor": 1.25,
            "nutrition_before": {"calories": 400, "protein_g": 28, ...},
            "nutrition_after": {"calories": 500, "protein_g": 35, ...},
            "delta": {"calories": +100, "protein_g": +7, ...}
        }
    """
    recipe = kwargs["recipe"]
    target_calories = kwargs["target_calories"]
    target_protein_g = kwargs["target_protein_g"]
    target_carbs_g = kwargs.get("target_carbs_g")
    target_fat_g = kwargs.get("target_fat_g")

    try:
        logger.info(
            f"Scaling recipe '{recipe.get('name', 'unknown')}': "
            f"target {target_calories} kcal, {target_protein_g}g protein"
        )

        nutrition_before = {
            "calories": recipe.get("calories_per_serving", 0),
            "protein_g": recipe.get("protein_g_per_serving", 0),
            "carbs_g": recipe.get("carbs_g_per_serving", 0),
            "fat_g": recipe.get("fat_g_per_serving", 0),
        }

        scaled_recipe = scale_recipe_to_targets(
            recipe=recipe,
            target_calories=target_calories,
            target_protein_g=target_protein_g,
            target_carbs_g=target_carbs_g,
            target_fat_g=target_fat_g,
        )

        nutrition_after = scaled_recipe["scaled_nutrition"]
        scale_factor = scaled_recipe["scale_factor"]

        delta = {
            macro: round(nutrition_after[macro] - nutrition_before[macro], 2)
            for macro in ["calories", "protein_g", "carbs_g", "fat_g"]
        }

        result = {
            "scaled_recipe": scaled_recipe,
            "scale_factor": round(scale_factor, 3),
            "nutrition_before": nutrition_before,
            "nutrition_after": nutrition_after,
            "delta": delta,
        }

        logger.info(
            f"Scaled '{recipe.get('name')}': "
            f"{nutrition_before['calories']:.0f} → {nutrition_after['calories']:.0f} kcal "
            f"(factor={scale_factor:.2f})"
        )

        return json.dumps(result, indent=2, ensure_ascii=False)

    except ValueError as e:
        logger.error(f"Validation error in scale_portions: {e}")
        return json.dumps({"error": str(e), "code": "VALIDATION_ERROR"})
    except Exception as e:
        logger.error(f"Unexpected error in scale_portions: {e}", exc_info=True)
        return json.dumps({"error": "Internal error", "code": "SCRIPT_ERROR"})
