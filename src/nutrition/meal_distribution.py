"""
Calculate meal-by-meal macro distribution based on daily targets and meal structure.

This module separates macro calculation from LLM generation, ensuring precise targets
before meal plan creation. Uses adaptive snack distribution: 10% per snack (max 25%),
remaining budget split evenly across main meals.

References:
- ISSN Position Stand (2017): Meal timing and frequency
- Schoenfeld et al. (2018): Meal frequency and body composition
"""

from typing import Literal, TypedDict
import logging

logger = logging.getLogger(__name__)


class MealMacros(TypedDict):
    """Macro targets for a single meal."""

    meal_type: str
    time: str
    target_calories: int
    target_protein_g: int
    target_carbs_g: int
    target_fat_g: int


class MealDistributionResult(TypedDict):
    """Complete meal distribution with daily totals."""

    meals: list[MealMacros]
    daily_totals: dict[str, int]


# Meal structure definitions — single source of truth
MEAL_STRUCTURES = {
    "3_meals_2_snacks": {
        "description": "3 main meals + 2 snacks",
        "meals": [
            "Petit-déjeuner (07:30)",
            "Collation AM (10:00)",
            "Déjeuner (12:30)",
            "Collation PM (16:00)",
            "Dîner (19:30)",
        ],
    },
    "4_meals": {
        "description": "4 equal meals",
        "meals": [
            "Repas 1 (08:00)",
            "Repas 2 (12:00)",
            "Repas 3 (16:00)",
            "Repas 4 (20:00)",
        ],
    },
    "3_consequent_meals": {
        "description": "3 consecutive main meals (no snacks)",
        "meals": ["Petit-déjeuner (08:00)", "Déjeuner (13:00)", "Dîner (19:00)"],
    },
    "3_meals_1_preworkout": {
        "description": "3 meals + 1 snack before training",
        "meals": [
            "Petit-déjeuner (07:30)",
            "Déjeuner (12:30)",
            "Collation pré-entraînement (16:30)",
            "Dîner (20:00)",
        ],
    },
}


def calculate_meal_macros_distribution(
    daily_calories: int,
    daily_protein_g: int,
    daily_carbs_g: int,
    daily_fat_g: int,
    meal_structure: Literal[
        "3_meals_2_snacks", "4_meals", "3_consequent_meals", "3_meals_1_preworkout"
    ],
) -> MealDistributionResult:
    """
    Distribute daily macros across meals according to structure.

    Logic:
    - If snacks present: 10% per snack (max 25%), rest to main meals
    - If no snacks: equal distribution across all meals

    Args:
        daily_calories: Total daily calorie target
        daily_protein_g: Total daily protein target (grams)
        daily_carbs_g: Total daily carbohydrate target (grams)
        daily_fat_g: Total daily fat target (grams)
        meal_structure: Meal structure key

    Returns:
        MealDistributionResult with meals array and daily_totals

    Raises:
        ValueError: If meal_structure is invalid

    Example:
        >>> result = calculate_meal_macros_distribution(
        ...     3300, 174, 413, 92, "3_meals_2_snacks"
        ... )
        >>> len(result["meals"])
        5
        >>> result["meals"][0]["meal_type"]
        'Petit-déjeuner'
        >>> result["daily_totals"]["calories"]
        3300

    References:
        ISSN Position Stand (2017): Optimal protein distribution across meals
    """
    # Validate meal structure
    if meal_structure not in MEAL_STRUCTURES:
        valid_structures = ", ".join(MEAL_STRUCTURES.keys())
        raise ValueError(
            f"Invalid meal_structure '{meal_structure}'. Must be one of: {valid_structures}"
        )

    structure_info = MEAL_STRUCTURES[meal_structure]
    meal_names = structure_info["meals"]
    num_meals = len(meal_names)

    # Classify meals as "main" or "snack" based on keywords
    main_meals = [
        m
        for m in meal_names
        if any(
            word in m.lower()
            for word in ["petit-déjeuner", "déjeuner", "dîner", "repas"]
        )
    ]
    snacks = [m for m in meal_names if "collation" in m.lower()]
    num_main = len(main_meals)
    num_snacks = len(snacks)

    logger.info(
        f"Distributing macros: {daily_calories} kcal, {daily_protein_g}g protein, "
        f"{daily_carbs_g}g carbs, {daily_fat_g}g fat across {meal_structure} "
        f"({num_main} main meals, {num_snacks} snacks)"
    )

    meals: list[MealMacros] = []

    if num_snacks > 0:
        # Adaptive snack ratio: 10% per snack, max 25% total
        # 1 snack → 10% snack / 90% main (snack ≈ 296 kcal for 2964 target)
        # 2 snacks → 20% snack / 80% main (each snack ≈ 296 kcal)
        snack_pct = min(0.10 * num_snacks, 0.25)
        snack_prot_pct = snack_pct  # protein proportional to calories (not boosted)
        main_pct = 1.0 - snack_pct
        main_prot_pct = 1.0 - snack_prot_pct

        calories_main_total = int(daily_calories * main_pct)
        calories_snack_total = daily_calories - calories_main_total
        protein_main_total = int(daily_protein_g * main_prot_pct)
        protein_snack_total = daily_protein_g - protein_main_total
        carbs_main_total = int(daily_carbs_g * main_pct)
        carbs_snack_total = daily_carbs_g - carbs_main_total
        fat_main_total = int(daily_fat_g * main_pct)
        fat_snack_total = daily_fat_g - fat_main_total

        # Distribute evenly within each category
        calories_per_main = calories_main_total // num_main if num_main > 0 else 0
        calories_per_snack = calories_snack_total // num_snacks if num_snacks > 0 else 0
        protein_per_main = protein_main_total // num_main if num_main > 0 else 0
        protein_per_snack = protein_snack_total // num_snacks if num_snacks > 0 else 0
        carbs_per_main = carbs_main_total // num_main if num_main > 0 else 0
        carbs_per_snack = carbs_snack_total // num_snacks if num_snacks > 0 else 0
        fat_per_main = fat_main_total // num_main if num_main > 0 else 0
        fat_per_snack = fat_snack_total // num_snacks if num_snacks > 0 else 0

        for meal_name in meal_names:
            # Extract meal type and time from "Meal Type (HH:MM)"
            if "(" in meal_name:
                meal_type, time_part = meal_name.split("(")
                meal_type = meal_type.strip()
                time = time_part.strip(")")
            else:
                meal_type = meal_name
                time = "00:00"

            is_snack = "collation" in meal_name.lower()

            meals.append(
                MealMacros(
                    meal_type=meal_type,
                    time=time,
                    target_calories=calories_per_snack
                    if is_snack
                    else calories_per_main,
                    target_protein_g=protein_per_snack
                    if is_snack
                    else protein_per_main,
                    target_carbs_g=carbs_per_snack if is_snack else carbs_per_main,
                    target_fat_g=fat_per_snack if is_snack else fat_per_main,
                )
            )

    else:
        # Equal distribution across all meals (no snacks)
        calories_per_meal = daily_calories // num_meals
        protein_per_meal = daily_protein_g // num_meals
        carbs_per_meal = daily_carbs_g // num_meals
        fat_per_meal = daily_fat_g // num_meals

        for meal_name in meal_names:
            # Extract meal type and time
            if "(" in meal_name:
                meal_type, time_part = meal_name.split("(")
                meal_type = meal_type.strip()
                time = time_part.strip(")")
            else:
                meal_type = meal_name
                time = "00:00"

            meals.append(
                MealMacros(
                    meal_type=meal_type,
                    time=time,
                    target_calories=calories_per_meal,
                    target_protein_g=protein_per_meal,
                    target_carbs_g=carbs_per_meal,
                    target_fat_g=fat_per_meal,
                )
            )

    # Log distribution for debugging
    for meal in meals:
        logger.debug(
            f"  {meal['meal_type']} ({meal['time']}): "
            f"{meal['target_calories']} kcal, {meal['target_protein_g']}g protein, "
            f"{meal['target_carbs_g']}g carbs, {meal['target_fat_g']}g fat"
        )

    return MealDistributionResult(
        meals=meals,
        daily_totals={
            "calories": daily_calories,
            "protein_g": daily_protein_g,
            "carbs_g": daily_carbs_g,
            "fat_g": daily_fat_g,
        },
    )
