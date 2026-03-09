"""Batch recipe seeder — reads JSON and upserts into Supabase with OFF validation.

LLM-free (rule 10) — uses only src.nutrition.* and src.clients.

Reads recipe definitions from scripts/data/low_fat_recipes.json,
OFF-validates each one, and upserts into the recipes table.

Usage:
    PYTHONPATH=. python scripts/seed_recipes_batch.py
"""

import asyncio
import json
import logging
import sys
import unicodedata
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)

from src.clients import get_supabase_client  # noqa: E402
from src.nutrition.calculations import calculate_macros  # noqa: E402
from src.nutrition.openfoodfacts_client import off_validate_recipe  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DATA_FILE = (
    Path(sys.argv[1])
    if len(sys.argv) > 1
    else Path(__file__).resolve().parent / "data" / "low_fat_recipes.json"
)


def normalize(name: str) -> str:
    """Lowercase + strip accents for deduplication."""
    nfkd = unicodedata.normalize("NFKD", name.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def build_recipe_row(recipe: dict) -> dict:
    """Build a DB row from a JSON recipe object."""
    calories = recipe["calories"]
    protein_g = recipe["protein_g"]
    macros = calculate_macros(calories, protein_g, goal_type="maintenance")

    return {
        "name": recipe["name"],
        "name_normalized": normalize(recipe["name"]),
        "description": f"{recipe['name']} — recette équilibrée.",
        "meal_type": recipe["meal_type"],
        "cuisine_type": recipe.get("cuisine_type", "française"),
        "diet_type": recipe.get("diet_type", "omnivore"),
        "prep_time_minutes": recipe.get("prep_time_minutes", 20),
        "ingredients": recipe.get("ingredients", []),
        "instructions": recipe.get("instructions", ""),
        "tags": recipe.get("tags", []),
        "allergen_tags": recipe.get("allergen_tags", []),
        "calories_per_serving": float(calories),
        "protein_g_per_serving": float(protein_g),
        "carbs_g_per_serving": float(macros["carbs_g"]),
        "fat_g_per_serving": float(macros["fat_g"]),
        "source": "batch",
        "off_validated": False,
    }


async def seed() -> None:
    """Load recipes from JSON, OFF-validate, and upsert into DB."""
    supabase = get_supabase_client()

    if not DATA_FILE.exists():
        logger.error(f"Data file not found: {DATA_FILE}")
        return

    with open(DATA_FILE, encoding="utf-8") as f:
        recipes_data = json.load(f)

    logger.info(f"Loaded {len(recipes_data)} recipes from {DATA_FILE.name}")

    counts: dict[str, int] = {}
    failed = 0
    validated = 0

    for recipe_data in recipes_data:
        row = build_recipe_row(recipe_data)
        try:
            row = await off_validate_recipe(row, supabase)
            if row.get("off_validated"):
                validated += 1

            supabase.table("recipes").upsert(
                row, on_conflict="name_normalized,meal_type"
            ).execute()
            meal_type = row["meal_type"]
            counts[meal_type] = counts.get(meal_type, 0) + 1
            logger.info(
                f"  ✓ {row['name']} ({row['calories_per_serving']:.0f} kcal, "
                f"OFF={'✓' if row.get('off_validated') else '✗'})"
            )
        except Exception as e:
            logger.error(f"  ✗ {row['name']}: {e}")
            failed += 1

    total = sum(counts.values())
    logger.info(
        f"\nDone: {total} upserted, {failed} failed, {validated} OFF-validated."
    )
    logger.info(f"Coverage: {counts}")


if __name__ == "__main__":
    asyncio.run(seed())
