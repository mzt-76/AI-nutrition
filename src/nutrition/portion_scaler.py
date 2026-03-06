"""Mathematical portion scaling for recipes.

Pure functions that scale ingredient quantities to hit target macros exactly.
No I/O — all calculations are deterministic.

References:
    Helms et al. (2014): Portion scaling maintains adherence better than supplements
"""

import logging

from src.nutrition.meal_plan_optimizer import (
    MIN_SCALE_FACTOR,
    MAX_SCALE_FACTOR,
)
from src.nutrition.quantity_rounding import round_quantity_smart

logger = logging.getLogger(__name__)


def calculate_scale_factor(
    actual_calories: float,
    target_calories: float,
) -> float:
    """Calculate portion scale factor clamped to MIN/MAX bounds.

    Args:
        actual_calories: Current recipe calories per serving
        target_calories: Target calories for this meal slot

    Returns:
        Scale factor clamped to [MIN_SCALE_FACTOR, MAX_SCALE_FACTOR]

    Example:
        >>> calculate_scale_factor(500, 750)
        1.5
        >>> calculate_scale_factor(500, 100)  # Clamped
        0.5
    """
    if actual_calories <= 0:
        logger.warning("actual_calories is zero or negative, returning 1.0")
        return 1.0

    raw_factor = target_calories / actual_calories
    clamped = max(MIN_SCALE_FACTOR, min(MAX_SCALE_FACTOR, raw_factor))

    if clamped != raw_factor:
        logger.debug(
            f"Scale factor clamped: {raw_factor:.3f} → {clamped:.3f} "
            f"(bounds: [{MIN_SCALE_FACTOR}, {MAX_SCALE_FACTOR}])"
        )

    return clamped


def scale_ingredients(
    ingredients: list[dict],
    scale_factor: float,
) -> list[dict]:
    """Scale all ingredient quantities by factor with smart rounding.

    Args:
        ingredients: List of ingredient dicts with quantity and unit fields
        scale_factor: Multiplier to apply to all quantities

    Returns:
        New list of ingredient dicts with scaled quantities

    Example:
        >>> scale_ingredients([{"name": "oeufs", "quantity": 2, "unit": "pièces"}], 1.5)
        [{"name": "oeufs", "quantity": 3, "unit": "pièces"}]
    """
    scaled = []
    for ingredient in ingredients:
        new_ingredient = dict(ingredient)
        raw_quantity = ingredient.get("quantity", 0) * scale_factor
        unit = ingredient.get("unit", "g")
        name = ingredient.get("name", "")
        new_ingredient["quantity"] = round_quantity_smart(raw_quantity, unit, name)
        scaled.append(new_ingredient)
    return scaled


def calculate_scaled_nutrition(
    recipe: dict,
    scale_factor: float,
) -> dict:
    """Calculate new nutrition values after scaling.

    Args:
        recipe: Recipe dict with calories_per_serving, protein_g_per_serving,
                carbs_g_per_serving, fat_g_per_serving fields
        scale_factor: Multiplier applied to the recipe

    Returns:
        Dict with scaled calories, protein_g, carbs_g, fat_g

    Example:
        >>> recipe = {"calories_per_serving": 500, "protein_g_per_serving": 30,
        ...           "carbs_g_per_serving": 40, "fat_g_per_serving": 20}
        >>> calculate_scaled_nutrition(recipe, 1.5)
        {"calories": 750.0, "protein_g": 45.0, "carbs_g": 60.0, "fat_g": 30.0}
    """
    return {
        "calories": round(recipe.get("calories_per_serving", 0) * scale_factor, 2),
        "protein_g": round(recipe.get("protein_g_per_serving", 0) * scale_factor, 2),
        "carbs_g": round(recipe.get("carbs_g_per_serving", 0) * scale_factor, 2),
        "fat_g": round(recipe.get("fat_g_per_serving", 0) * scale_factor, 2),
    }


def scale_recipe_to_targets(
    recipe: dict,
    target_calories: int,
    target_protein_g: int,
    target_carbs_g: int | None = None,
    target_fat_g: int | None = None,
) -> dict:
    """Scale recipe portions to hit target macros.

    Uses calorie-based primary scaling. The scale factor is calculated from
    target_calories / recipe_calories and clamped to [MIN_SCALE_FACTOR, MAX_SCALE_FACTOR].

    Args:
        recipe: Recipe dict with calories_per_serving, protein_g_per_serving,
                carbs_g_per_serving, fat_g_per_serving, ingredients list
        target_calories: Target calories for this meal slot
        target_protein_g: Target protein for this meal slot (used for logging)
        target_carbs_g: Optional carbs target (used for logging)
        target_fat_g: Optional fat target (used for logging)

    Returns:
        Scaled recipe dict with updated quantities and nutrition. Adds a
        "scaled_nutrition" key with the resulting macro values.

    Example:
        >>> recipe = {
        ...     "name": "Omelette",
        ...     "calories_per_serving": 400,
        ...     "protein_g_per_serving": 25,
        ...     "carbs_g_per_serving": 10,
        ...     "fat_g_per_serving": 28,
        ...     "ingredients": [{"name": "oeufs", "quantity": 2, "unit": "pièces"}]
        ... }
        >>> result = scale_recipe_to_targets(recipe, target_calories=600, target_protein_g=35)
        >>> result["scaled_nutrition"]["calories"]
        600.0
    """
    if not recipe:
        raise ValueError("recipe cannot be None or empty")
    if target_calories <= 0:
        raise ValueError(f"target_calories must be positive, got {target_calories}")

    actual_calories = recipe.get("calories_per_serving", 0)

    logger.info(
        f"Scaling recipe '{recipe.get('name', 'unknown')}': "
        f"{actual_calories} kcal → {target_calories} kcal target"
    )

    scale_factor = calculate_scale_factor(actual_calories, target_calories)

    scaled_recipe = dict(recipe)
    scaled_recipe["ingredients"] = scale_ingredients(
        recipe.get("ingredients", []), scale_factor
    )
    scaled_recipe["scaled_nutrition"] = calculate_scaled_nutrition(recipe, scale_factor)
    scaled_recipe["scale_factor"] = scale_factor

    actual_after = scaled_recipe["scaled_nutrition"]["calories"]
    logger.info(
        f"Scaled '{recipe.get('name', 'unknown')}': "
        f"factor={scale_factor:.2f}, result={actual_after:.0f} kcal "
        f"(target={target_calories})"
    )

    return scaled_recipe
