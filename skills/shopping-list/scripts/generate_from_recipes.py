"""Generate a categorized shopping list from individual recipe IDs.

Fetches recipes from the `recipes` table, extracts their ingredients,
aggregates by ingredient+unit, and categorizes by food group.

Unlike generate_shopping_list (which works from a meal_plan), this script
handles ad-hoc recipe requests — e.g. after generate_custom_recipe.
"""

import json
import logging

from src.nutrition.meal_planning import (
    aggregate_ingredients,
    categorize_ingredients,
    flatten_categorized_to_items,
)

logger = logging.getLogger(__name__)


async def execute(**kwargs) -> str:
    """Generate categorized shopping list from recipe IDs.

    Args:
        supabase: Supabase client (injected)
        user_id: User ID (injected)
        recipe_ids: List of recipe UUIDs from the `recipes` table
        servings_multiplier: Multiplier for all quantities (default: 1.0)
        title: Custom title for the shopping list (optional)

    Returns:
        JSON with categorized shopping list (same format as generate_shopping_list)
    """
    supabase = kwargs["supabase"]
    user_id = kwargs.get("user_id", "")
    recipe_ids: list[str] | None = kwargs.get("recipe_ids")
    servings_multiplier: float = kwargs.get("servings_multiplier", 1.0)
    title: str | None = kwargs.get("title")

    try:
        # Step 1: Validate inputs
        if not recipe_ids:
            return json.dumps(
                {
                    "error": "recipe_ids est requis et ne peut pas etre vide.",
                    "code": "VALIDATION_ERROR",
                }
            )

        if servings_multiplier <= 0:
            return json.dumps(
                {
                    "error": "servings_multiplier doit etre superieur a 0.",
                    "code": "VALIDATION_ERROR",
                }
            )

        logger.info(
            f"Generating shopping list from {len(recipe_ids)} recipe(s), "
            f"multiplier={servings_multiplier}"
        )

        # Step 2: Fetch recipes from DB
        response = (
            supabase.table("recipes")
            .select("id, name, ingredients")
            .in_("id", recipe_ids)
            .execute()
        )

        if not response.data:
            return json.dumps(
                {
                    "error": "Aucune recette trouvee pour les IDs fournis.",
                    "code": "RECIPES_NOT_FOUND",
                    "recipe_ids": recipe_ids,
                }
            )

        found_ids = {r["id"] for r in response.data}
        missing_ids = [rid for rid in recipe_ids if rid not in found_ids]
        if missing_ids:
            logger.warning(f"Some recipe IDs not found: {missing_ids}")

        # Step 3: Extract and normalize ingredients from all recipes
        all_ingredients: list[dict] = []
        recipe_names: list[str] = []

        for recipe in response.data:
            recipe_names.append(recipe["name"])
            ingredients = recipe.get("ingredients")
            if not ingredients:
                logger.warning(f"Recipe {recipe['id']} has no ingredients")
                continue

            # ingredients is JSONB — already parsed as list[dict]
            if isinstance(ingredients, str):
                ingredients = json.loads(ingredients)

            for ing in ingredients:
                # Normalize to {name, quantity, unit} — recipes may have extra fields
                normalized = {
                    "name": ing.get("name", ""),
                    "quantity": ing.get("quantity", 0),
                    "unit": ing.get("unit", ""),
                }
                if normalized["name"] and normalized["unit"]:
                    all_ingredients.append(normalized)

        if not all_ingredients:
            return json.dumps(
                {
                    "error": "Aucun ingredient trouve dans les recettes.",
                    "code": "NO_INGREDIENTS",
                }
            )

        logger.info(
            f"Extracted {len(all_ingredients)} ingredients from {len(response.data)} recipes"
        )

        # Step 4: Aggregate and categorize (reuse meal_planning functions)
        aggregated = aggregate_ingredients(all_ingredients, servings_multiplier)
        categorized = categorize_ingredients(aggregated)

        # Step 5: Persist shopping list to DB
        total_items = sum(len(items) for items in categorized.values())
        flat_items = flatten_categorized_to_items(categorized)
        shopping_list_id: str | None = None

        if not title:
            if len(recipe_names) == 1:
                title = f"Courses - {recipe_names[0]}"
            else:
                title = f"Courses - {len(recipe_names)} recettes"

        if user_id and flat_items:
            try:
                insert_result = (
                    supabase.table("shopping_lists")
                    .insert(
                        {
                            "user_id": user_id,
                            "meal_plan_id": None,
                            "title": title,
                            "items": flat_items,
                        }
                    )
                    .execute()
                )
                if insert_result.data:
                    shopping_list_id = insert_result.data[0].get("id")
                    logger.info(f"Shopping list saved: {shopping_list_id}")
            except Exception as e:
                logger.error(f"Failed to save shopping list: {e}")

        # Step 6: Build response
        result = {
            "success": True,
            "shopping_list": categorized,
            "shopping_list_id": shopping_list_id,
            "metadata": {
                "recipe_ids": recipe_ids,
                "recipe_names": recipe_names,
                "missing_recipe_ids": missing_ids,
                "servings_multiplier": servings_multiplier,
                "total_items": total_items,
                "categories": {
                    cat: len(items) for cat, items in categorized.items() if items
                },
            },
            "message": f"Liste de courses generee pour {len(recipe_names)} recette(s)",
        }

        logger.info(
            f"Shopping list: {total_items} items across "
            f"{len([c for c in categorized.values() if c])} categories"
        )
        return json.dumps(result, indent=2, ensure_ascii=False)

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return json.dumps({"error": str(e), "code": "VALIDATION_ERROR"})
    except Exception as e:
        logger.error(
            f"Unexpected error generating shopping list from recipes: {e}",
            exc_info=True,
        )
        return json.dumps(
            {
                "error": "Erreur interne lors de la generation de la liste de courses.",
                "code": "GENERATION_ERROR",
            }
        )
