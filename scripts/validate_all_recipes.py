"""Batch-validate all recipes in DB against OpenFoodFacts.

For each recipe:
1. Match each ingredient to OFF → store nutrition_per_100g + matched_name + off_code
2. Recalculate recipe-level macros from real OFF data
3. Mark recipe off_validated = true if ALL ingredients matched

LLM-free (rule 10) — uses only src.nutrition.* and src.clients.

Usage:
    PYTHONPATH=. python scripts/validate_all_recipes.py
"""

import asyncio
import logging

from src.clients import get_supabase_client
from src.nutrition.openfoodfacts_client import off_validate_recipe

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def validate_recipe(supabase, recipe: dict) -> dict:
    """Validate a single recipe's ingredients against OFF.

    Delegates to off_validate_recipe() which handles:
    - Parallel ingredient matching via OFF
    - Per-100g back-calculation and storage
    - Recipe-level macro recalculation

    Returns:
        Dict with validation results and enriched recipe.
    """
    enriched = await off_validate_recipe(recipe, supabase)
    ingredients = enriched.get("ingredients", [])
    matched = sum(1 for i in ingredients if i.get("nutrition_per_100g"))
    unmatched = [
        i["name"]
        for i in ingredients
        if not i.get("nutrition_per_100g") and i.get("name")
    ]
    return {
        "recipe_id": recipe.get("id", "unknown"),
        "recipe_name": recipe.get("name", "unknown"),
        "total_ingredients": len(ingredients),
        "matched": matched,
        "unmatched": unmatched,
        "off_validated": enriched.get("off_validated", False),
        "enriched_recipe": enriched,
    }


async def main():
    supabase = get_supabase_client()

    # Fetch all recipes
    logger.info("Fetching all recipes from DB...")
    response = supabase.table("recipes").select("*").execute()
    recipes = response.data or []
    logger.info(f"Found {len(recipes)} recipes to validate")

    stats = {
        "total": len(recipes),
        "fully_matched": 0,
        "partially_matched": 0,
        "failed": 0,
    }

    for i, recipe in enumerate(recipes):
        recipe_name = recipe.get("name", "unknown")
        recipe_id = recipe.get("id", "unknown")

        logger.info(f"[{i + 1}/{len(recipes)}] Validating: {recipe_name}")

        try:
            result = await validate_recipe(supabase, recipe)

            total = result["total_ingredients"]
            matched = result["matched"]
            match_rate = matched / total if total > 0 else 0

            # Build DB update from enriched recipe
            enriched = result["enriched_recipe"]
            update_data: dict = {
                "ingredients": enriched.get("ingredients", []),
                "off_validated": result["off_validated"],
            }

            # Update per-serving macros if we have good OFF data
            if (
                enriched.get("calories_per_serving")
                and enriched["calories_per_serving"] > 0
            ):
                update_data["calories_per_serving"] = enriched["calories_per_serving"]
                update_data["protein_g_per_serving"] = enriched["protein_g_per_serving"]
                update_data["carbs_g_per_serving"] = enriched["carbs_g_per_serving"]
                update_data["fat_g_per_serving"] = enriched["fat_g_per_serving"]

            supabase.table("recipes").update(update_data).eq("id", recipe_id).execute()

            if matched == total:
                stats["fully_matched"] += 1
                logger.info(f"  ✅ All {total} ingredients matched")
            elif match_rate >= 0.8:
                stats["partially_matched"] += 1
                logger.info(
                    f"  ⚠️ {matched}/{total} ingredients matched "
                    f"(unmatched: {result['unmatched']})"
                )
            else:
                stats["failed"] += 1
                logger.warning(
                    f"  ❌ Only {matched}/{total} ingredients matched "
                    f"(unmatched: {result['unmatched']})"
                )

        except Exception as e:
            stats["failed"] += 1
            logger.error(f"  ❌ Validation failed: {e}")

    # Summary
    logger.info("=" * 60)
    logger.info("VALIDATION SUMMARY")
    logger.info(f"  Total recipes:      {stats['total']}")
    logger.info(f"  Fully matched:      {stats['fully_matched']}")
    logger.info(f"  Partially matched:  {stats['partially_matched']}")
    logger.info(f"  Failed:             {stats['failed']}")


if __name__ == "__main__":
    asyncio.run(main())
