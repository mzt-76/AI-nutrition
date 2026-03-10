"""Multi-source recipe import pipeline orchestrator.

LLM-free (rule 10) — uses only src.nutrition.*, src.clients, httpx, and stdlib.

Pipeline:
    1. Load requested source adapters
    2. Fetch raw recipes (RawRecipe) from each source
    3. Build DB-compatible recipe rows
    4. OFF-validate each recipe via off_validate_recipe()
    5. Post-filter macros (fat%, protein%, calorie range)
    6. Auto-correct portions if > 900 kcal
    7. Upsert into Supabase recipes table
    8. Log summary

Usage:
    PYTHONPATH=. python scripts/import_recipes.py --source all --limit 50 --dry-run
    PYTHONPATH=. python scripts/import_recipes.py --source spoonacular --limit 100 --max-fat-pct 30
    PYTHONPATH=. python scripts/import_recipes.py --source marmiton --query "poulet grillé"
"""

import argparse
import asyncio
import logging
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)

from src.clients import get_supabase_client  # noqa: E402
from src.nutrition.openfoodfacts_client import off_validate_recipe  # noqa: E402

from scripts.recipe_sources import (  # noqa: E402
    AllRecipesSource,
    BBCGoodFoodSource,
    CuisineAZSource,
    EdamamSource,
    MarmitonSource,
    RecipeSource,
    SeptCinquanteGSource,
    SpoonacularSource,
    TheMealDBSource,
)
from scripts.recipe_sources.base import (  # noqa: E402
    auto_correct_portions,
    build_recipe_row,
    has_sane_macro_ratios,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Source registry — name -> adapter class
SOURCE_REGISTRY: dict[str, type[RecipeSource]] = {
    "spoonacular": SpoonacularSource,
    "edamam": EdamamSource,
    "themealdb": TheMealDBSource,
    "marmiton": MarmitonSource,
    "750g": SeptCinquanteGSource,
    "cuisineaz": CuisineAZSource,
    "bbcgoodfood": BBCGoodFoodSource,
    "allrecipes": AllRecipesSource,
}


async def import_from_source(
    source: RecipeSource,
    client: httpx.AsyncClient,
    supabase: object,
    limit: int,
    dry_run: bool,
    max_fat_pct: float,
    min_protein_pct: float,
    filters: dict[str, str | int | float],
) -> dict[str, int]:
    """Run the import pipeline for a single source.

    Returns counts dict: fetched, validated, filtered, upserted, failed.
    """
    counts = {
        "fetched": 0,
        "validated": 0,
        "filtered": 0,
        "upserted": 0,
        "failed": 0,
    }

    source_name = source.name
    logger.info(f"\n{'='*60}")
    logger.info(f"Source: {source_name} (limit={limit})")
    logger.info(f"{'='*60}")

    # Step 1: Fetch raw recipes
    try:
        raw_recipes = await source.fetch_recipes(client, limit=limit, **filters)
    except Exception as e:
        logger.error(f"{source_name}: fetch failed — {e}")
        return counts

    counts["fetched"] = len(raw_recipes)
    logger.info(f"{source_name}: fetched {len(raw_recipes)} raw recipes")

    # Step 2-7: Process each recipe
    for raw in raw_recipes:
        try:
            # Build DB row
            row = build_recipe_row(raw)

            # OFF validate
            validated_row = await off_validate_recipe(row, supabase)

            if not validated_row.get("off_validated"):
                logger.info(f"  SKIP {raw.name} — OFF validation failed")
                counts["filtered"] += 1
                continue

            counts["validated"] += 1

            # Auto-correct portions if > 900 kcal
            validated_row = auto_correct_portions(validated_row)

            # Post-filter: macro ratios
            if not has_sane_macro_ratios(
                validated_row,
                max_fat_ratio=max_fat_pct / 100.0,
                min_protein_ratio=min_protein_pct / 100.0,
            ):
                logger.info(f"  SKIP {raw.name} — macro ratios outside target")
                counts["filtered"] += 1
                continue

            cal = float(validated_row.get("calories_per_serving", 0))
            prot = float(validated_row.get("protein_g_per_serving", 0))
            fat = float(validated_row.get("fat_g_per_serving", 0))
            carbs = float(validated_row.get("carbs_g_per_serving", 0))

            if dry_run:
                logger.info(
                    f"  [DRY] {validated_row['name']} | {validated_row['meal_type']} | "
                    f"{cal:.0f} kcal | {prot:.0f}p/{fat:.0f}f/{carbs:.0f}c"
                )
                counts["upserted"] += 1  # Count as would-be upserted
                continue

            # Upsert to Supabase
            supabase.table("recipes").upsert(
                validated_row, on_conflict="name_normalized,meal_type"
            ).execute()
            counts["upserted"] += 1

            logger.info(
                f"  OK {validated_row['name']} | {validated_row['meal_type']} | "
                f"{cal:.0f} kcal | {prot:.0f}p/{fat:.0f}f/{carbs:.0f}c"
            )

        except Exception as e:
            logger.error(f"  FAIL {raw.name}: {e}")
            counts["failed"] += 1

    return counts


async def main_async(args: argparse.Namespace) -> None:
    """Async main — run import pipeline."""
    supabase = get_supabase_client()

    # Determine which sources to use
    if args.source == "all":
        source_names = list(SOURCE_REGISTRY.keys())
    else:
        source_names = [args.source]

    # Build filter dict from CLI args
    filters: dict[str, str | int | float] = {}
    if args.query:
        filters["query"] = args.query
    if args.meal_type:
        filters["meal_type"] = args.meal_type
    if args.diet_type:
        filters["diet_type"] = args.diet_type
    if args.min_protein_pct:
        filters["min_protein_pct"] = args.min_protein_pct
    if args.max_fat_pct:
        filters["max_fat_pct"] = args.max_fat_pct

    # Totals across all sources
    totals = {
        "fetched": 0,
        "validated": 0,
        "filtered": 0,
        "upserted": 0,
        "failed": 0,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        for source_name in source_names:
            adapter_cls = SOURCE_REGISTRY.get(source_name)
            if not adapter_cls:
                logger.warning(f"Unknown source: {source_name} — skipping")
                continue

            adapter = adapter_cls()

            # Check if API key is required but missing
            if adapter.requires_api_key:
                # Each adapter handles missing keys internally with a warning
                pass

            counts = await import_from_source(
                source=adapter,
                client=client,
                supabase=supabase,
                limit=args.limit,
                dry_run=args.dry_run,
                max_fat_pct=args.max_fat_pct,
                min_protein_pct=args.min_protein_pct,
                filters=filters,
            )

            for key in totals:
                totals[key] += counts[key]

    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("IMPORT SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"  Sources:    {', '.join(source_names)}")
    logger.info(f"  Fetched:    {totals['fetched']}")
    logger.info(f"  Validated:  {totals['validated']}")
    logger.info(f"  Filtered:   {totals['filtered']}")
    logger.info(f"  Upserted:   {totals['upserted']}")
    logger.info(f"  Failed:     {totals['failed']}")
    if args.dry_run:
        logger.info("  Mode:       DRY RUN (no DB writes)")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Import recipes from multiple sources with OFF validation"
    )
    parser.add_argument(
        "--source",
        default="all",
        choices=["all"] + list(SOURCE_REGISTRY.keys()),
        help="Source to import from (default: all)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Max recipes per source (default: 50)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate only, no DB writes",
    )
    parser.add_argument(
        "--max-fat-pct",
        type=float,
        default=35.0,
        help="Max fat %% of calories (default: 35)",
    )
    parser.add_argument(
        "--min-protein-pct",
        type=float,
        default=15.0,
        help="Min protein %% of calories (default: 15)",
    )
    parser.add_argument(
        "--meal-type",
        choices=["dejeuner", "diner", "petit-dejeuner", "collation"],
        default=None,
        help="Filter by meal type",
    )
    parser.add_argument(
        "--diet-type",
        choices=["omnivore", "végétarien", "vegan"],
        default=None,
        help="Filter by diet type",
    )
    parser.add_argument(
        "--query",
        type=str,
        default=None,
        help="Search keyword (e.g., 'poulet grillé', 'high protein')",
    )

    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
