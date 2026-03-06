"""
Helper functions for meal plan generation workflow.

Provides prompt building, daily total calculations, and response formatting.
"""

import logging
import json
from src.nutrition.quantity_rounding import round_quantity_smart

from src.nutrition.meal_distribution import MEAL_STRUCTURES  # noqa: F401 — re-export

logger = logging.getLogger(__name__)


def calculate_daily_totals(meals: list[dict]) -> dict:
    """
    Sum nutritional totals from all meals in a day.

    Args:
        meals: List of meal dicts with nutrition field

    Returns:
        Dict with calories, protein_g, carbs_g, fat_g totals

    Example:
        >>> meals = [
        ...     {"nutrition": {"calories": 500, "protein_g": 30, "carbs_g": 50, "fat_g": 15}},
        ...     {"nutrition": {"calories": 600, "protein_g": 35, "carbs_g": 60, "fat_g": 20}}
        ... ]
        >>> totals = calculate_daily_totals(meals)
        >>> totals["calories"]
        1100
    """
    totals = {"calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0}

    for meal in meals:
        nutrition = meal.get("nutrition", {})
        totals["calories"] += nutrition.get("calories", 0)
        totals["protein_g"] += nutrition.get("protein_g", 0)
        totals["carbs_g"] += nutrition.get("carbs_g", 0)
        totals["fat_g"] += nutrition.get("fat_g", 0)

    logger.debug(f"Daily totals calculated: {totals}")
    return totals


def format_meal_plan_response(meal_plan: dict, store_success: bool) -> str:
    """
    Format meal plan for user-friendly JSON return.

    Args:
        meal_plan: Generated meal plan dict
        store_success: Whether database storage succeeded

    Returns:
        Formatted JSON string with meal plan and metadata

    Example:
        >>> plan = {"meal_plan_id": "plan_2024-12-23", "days": []}
        >>> response = format_meal_plan_response(plan, True)
        >>> "success" in response
        True
    """
    response = {
        "success": True,
        "message": "Meal plan generated successfully",
        "stored_in_database": store_success,
        "meal_plan": meal_plan,
        "summary": {
            "total_days": len(meal_plan.get("days", [])),
            "start_date": meal_plan.get("start_date", "N/A"),
            "meal_structure": meal_plan.get("meal_structure", "N/A"),
            "weekly_summary": meal_plan.get("weekly_summary", {}),
        },
    }

    logger.info(
        f"Response formatted: {len(meal_plan.get('days', []))} days, stored: {store_success}"
    )
    return json.dumps(response, indent=2, ensure_ascii=False)


# ============================================================================
# Shopping List Helper Functions
# ============================================================================

# Category keyword mappings for ingredient categorization
INGREDIENT_CATEGORIES = {
    "produce": [
        "tomate",
        "oignon",
        "ail",
        "carotte",
        "pomme",
        "banane",
        "orange",
        "citron",
        "salade",
        "laitue",
        "épinard",
        "brocoli",
        "courgette",
        "poivron",
        "concombre",
        "champignon",
        "avocat",
        "fruits",
        "légumes",
        "légume",
        "fruit",
    ],
    "proteins": [
        "poulet",
        "boeuf",
        "porc",
        "viande",
        "poisson",
        "thon",
        "saumon",
        "oeuf",
        "oeufs",
        "tofu",
        "tempeh",
        "lentille",
        "pois chiche",
        "haricot",
        "protéine",
    ],
    "grains": [
        "riz",
        "pâtes",
        "pain",
        "farine",
        "quinoa",
        "avoine",
        "céréale",
        "blé",
        "semoule",
        "couscous",
    ],
    "dairy": [
        "lait",
        "fromage",
        "yaourt",
        "yogurt",
        "beurre",
        "crème",
        "cream",
    ],
    "pantry": [
        "huile",
        "sel",
        "poivre",
        "épice",
        "sauce",
        "miel",
        "sucre",
        "vinaigre",
        "moutarde",
        "mayonnaise",
    ],
}


def extract_ingredients_from_meal_plan(
    meal_plan_data: dict, selected_days: list[int] | None = None
) -> list[dict]:
    """
    Extract ingredients from meal plan for selected days.

    Args:
        meal_plan_data: Meal plan JSONB data (plan_data from database)
        selected_days: List of day indices to include (0-6), or None for all days

    Returns:
        List of ingredient dicts with name, quantity, unit

    Example:
        >>> plan_data = {"days": [{"meals": [{"ingredients": [...]}]}]}
        >>> ingredients = extract_ingredients_from_meal_plan(plan_data, [0, 1])
        >>> len(ingredients) > 0
        True
    """
    if selected_days is None:
        selected_days = list(range(7))  # All 7 days

    ingredients_list = []
    days = meal_plan_data.get("days", [])

    for day_idx in selected_days:
        if day_idx >= len(days):
            logger.warning(
                f"Day index {day_idx} out of range (plan has {len(days)} days)"
            )
            continue

        day = days[day_idx]
        meals = day.get("meals", [])

        for meal in meals:
            meal_ingredients = meal.get("ingredients", [])
            ingredients_list.extend(meal_ingredients)

    logger.info(
        f"Extracted {len(ingredients_list)} ingredients from {len(selected_days)} days"
    )
    return ingredients_list


def aggregate_ingredients(
    ingredients_list: list[dict], servings_multiplier: float = 1.0
) -> dict:
    """
    Aggregate ingredient quantities by name+unit, apply servings multiplier.

    Args:
        ingredients_list: List of ingredient dicts with name, quantity, unit
        servings_multiplier: Multiplier for all quantities (e.g., 2.0 for double portions)

    Returns:
        Dict mapping "ingredient_name|unit" to total quantity

    Example:
        >>> ingredients = [
        ...     {"name": "riz", "quantity": 200, "unit": "g"},
        ...     {"name": "riz", "quantity": 150, "unit": "g"},
        ...     {"name": "riz", "quantity": 1, "unit": "tasse"}
        ... ]
        >>> result = aggregate_ingredients(ingredients, servings_multiplier=1.5)
        >>> result["riz|g"]
        525.0
    """
    aggregated: dict[str, float] = {}

    for ingredient in ingredients_list:
        name = ingredient.get("name", "").strip().lower()
        quantity = ingredient.get("quantity", 0)
        unit = ingredient.get("unit", "").strip().lower()

        if not name or not unit:
            logger.warning(f"Skipping invalid ingredient: {ingredient}")
            continue

        # Create unique key: ingredient_name|unit
        key = f"{name}|{unit}"

        # Apply servings multiplier and aggregate
        adjusted_quantity = quantity * servings_multiplier

        if key in aggregated:
            aggregated[key] += adjusted_quantity
        else:
            aggregated[key] = adjusted_quantity

    logger.info(
        f"Aggregated {len(ingredients_list)} ingredients into {len(aggregated)} unique items"
    )
    return aggregated


def categorize_ingredients(aggregated_ingredients: dict) -> dict:
    """
    Categorize aggregated ingredients into food groups.

    Uses keyword matching against INGREDIENT_CATEGORIES.
    Ingredients not matching any category go into "other".

    Args:
        aggregated_ingredients: Dict mapping "name|unit" to quantity

    Returns:
        Dict with category names as keys, each containing list of
        {"name": str, "quantity": float, "unit": str} dicts

    Example:
        >>> agg = {"riz|g": 500, "poulet|g": 600, "unknown_item|kg": 2}
        >>> categorized = categorize_ingredients(agg)
        >>> "grains" in categorized
        True
        >>> "proteins" in categorized
        True
    """
    categorized: dict[str, list[dict]] = {
        "produce": [],
        "proteins": [],
        "grains": [],
        "dairy": [],
        "pantry": [],
        "other": [],
    }

    for key, quantity in aggregated_ingredients.items():
        # Parse key: "ingredient_name|unit"
        parts = key.split("|")
        if len(parts) != 2:
            logger.warning(f"Invalid aggregated key format: {key}")
            continue

        name, unit = parts
        rounded_qty = round_quantity_smart(quantity, unit, name)
        ingredient_item = {"name": name, "quantity": rounded_qty, "unit": unit}

        # Find matching category
        matched_category = None
        for category, keywords in INGREDIENT_CATEGORIES.items():
            if any(keyword in name for keyword in keywords):
                matched_category = category
                break

        if matched_category:
            categorized[matched_category].append(ingredient_item)
        else:
            categorized["other"].append(ingredient_item)

    # Log category counts
    category_counts = {cat: len(items) for cat, items in categorized.items()}
    logger.info(f"Categorized ingredients: {category_counts}")

    return categorized


def flatten_categorized_to_items(categorized: dict[str, list[dict]]) -> list[dict]:
    """Convert categorized shopping list to flat items list for DB storage.

    Args:
        categorized: Dict with category keys mapping to lists of
            {"name": str, "quantity": float, "unit": str} dicts

    Returns:
        Flat list of items with category and checked fields added

    Example:
        >>> cat = {"produce": [{"name": "tomate", "quantity": 500, "unit": "g"}]}
        >>> items = flatten_categorized_to_items(cat)
        >>> items[0]["category"]
        'produce'
        >>> items[0]["checked"]
        False
    """
    items: list[dict] = []
    for category, category_items in categorized.items():
        for item in category_items:
            items.append(
                {
                    "name": item["name"],
                    "quantity": item["quantity"],
                    "unit": item["unit"],
                    "category": category,
                    "checked": False,
                }
            )
    return items
