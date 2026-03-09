"""Clean up corrupted entries in ingredient_mapping using Atwater sanity check.

Scans all cached ingredient→OFF mappings and removes entries where
|calories - (P*4 + G*4 + L*9)| > 30% of max(calories, atwater).

After cleanup, re-validates affected recipes via validate_all_recipes.

LLM-free (rule 10) — uses only src.nutrition.* and src.clients.

Usage:
    PYTHONPATH=. python scripts/cleanup_ingredient_mapping.py
    PYTHONPATH=. python scripts/cleanup_ingredient_mapping.py --dry-run
"""

import argparse
import asyncio
import logging

from src.clients import get_supabase_client
from src.nutrition.openfoodfacts_client import _passes_atwater_check

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def cleanup_ingredient_mapping(dry_run: bool = False) -> None:
    """Scan and remove corrupted ingredient_mapping entries."""
    supabase = get_supabase_client()

    # Fetch all entries
    result = supabase.table("ingredient_mapping").select("*").execute()
    entries = result.data or []
    logger.info("Scanning %d ingredient_mapping entries...", len(entries))

    bad_entries: list[dict] = []
    for entry in entries:
        if not _passes_atwater_check(entry):
            cal = float(entry.get("calories_per_100g", 0) or 0)
            prot = float(entry.get("protein_g_per_100g", 0) or 0)
            carbs = float(entry.get("carbs_g_per_100g", 0) or 0)
            fat = float(entry.get("fat_g_per_100g", 0) or 0)
            atwater = prot * 4 + carbs * 4 + fat * 9
            bad_entries.append(entry)
            logger.warning(
                "  BAD: '%s' → '%s' (code=%s): "
                "cal=%.0f, atwater=%.0f (P=%.1f G=%.1f L=%.1f)",
                entry["ingredient_name"],
                entry.get("openfoodfacts_name", "?"),
                entry.get("openfoodfacts_code", "?"),
                cal,
                atwater,
                prot,
                carbs,
                fat,
            )

    if not bad_entries:
        logger.info("No corrupted entries found.")
        return

    logger.info(
        "Found %d corrupted entries (out of %d total, %.1f%%)",
        len(bad_entries),
        len(entries),
        len(bad_entries) / len(entries) * 100,
    )

    if dry_run:
        logger.info("DRY RUN — no changes made. Run without --dry-run to delete.")
        return

    # Delete bad entries
    deleted = 0
    for entry in bad_entries:
        try:
            supabase.table("ingredient_mapping").delete().eq(
                "id", entry["id"]
            ).execute()
            deleted += 1
        except Exception as e:
            logger.error("Failed to delete entry '%s': %s", entry["ingredient_name"], e)

    logger.info("Deleted %d corrupted entries.", deleted)

    # Find affected recipes (those with ingredients matching deleted mappings)
    bad_names = {e["ingredient_name"].lower() for e in bad_entries}
    recipes_result = supabase.table("recipes").select("id, name, ingredients").execute()
    affected_ids: list[str] = []

    for recipe in recipes_result.data or []:
        ingredients = recipe.get("ingredients", [])
        if isinstance(ingredients, str):
            import json

            ingredients = json.loads(ingredients)
        for ing in ingredients:
            name = (ing.get("name") or "").lower()
            if name in bad_names:
                affected_ids.append(recipe["id"])
                logger.info(
                    "  Recipe '%s' (id=%s) uses corrupted ingredient '%s'",
                    recipe["name"],
                    recipe["id"],
                    name,
                )
                break

    if affected_ids:
        logger.info(
            "%d recipes need re-validation. Run:\n"
            "  PYTHONPATH=. python scripts/validate_all_recipes.py",
            len(affected_ids),
        )
        # Mark affected recipes as needing re-validation
        for rid in affected_ids:
            try:
                supabase.table("recipes").update({"off_validated": False}).eq(
                    "id", rid
                ).execute()
            except Exception as e:
                logger.warning("Failed to mark recipe %s for re-validation: %s", rid, e)
        logger.info("Marked %d recipes as off_validated=false.", len(affected_ids))
    else:
        logger.info("No recipes affected by the deleted entries.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Clean up corrupted ingredient_mapping entries"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only report corrupted entries, don't delete",
    )
    args = parser.parse_args()
    asyncio.run(cleanup_ingredient_mapping(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
