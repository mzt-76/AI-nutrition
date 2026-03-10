"""Diagnostic: test ingredient resolution rate for recipe import sources.

LLM-free (rule 10). Fetches recipes from a source, attempts to match each
ingredient individually via OFF, and produces a report showing:
- Which ingredients match / fail
- Match confidence scores
- Ingredient roles (fixed ingredients = low nutritional impact)
- Summary stats: match rate, top blockers

Usage:
    PYTHONPATH=. python scripts/diagnose_import_ingredients.py --source themealdb --limit 10
    PYTHONPATH=. python scripts/diagnose_import_ingredients.py --source marmiton --limit 5 --csv report.csv
"""

import argparse
import asyncio
import csv
import logging
from collections import Counter
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)

from src.clients import get_supabase_client  # noqa: E402
from src.nutrition.ingredient_roles import get_ingredient_role  # noqa: E402
from src.nutrition.openfoodfacts_client import match_ingredient  # noqa: E402

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
from scripts.recipe_sources.base import build_recipe_row  # noqa: E402

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

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


async def diagnose_source(
    source: RecipeSource,
    client: httpx.AsyncClient,
    supabase: object,
    limit: int,
) -> list[dict]:
    """Fetch recipes and test each ingredient's OFF resolution.

    Returns list of dicts: recipe_name, ingredient, role, matched, matched_to, confidence
    """
    rows: list[dict] = []

    try:
        raw_recipes = await source.fetch_recipes(client, limit=limit)
    except Exception as e:
        print(f"ERROR: {source.name} fetch failed — {e}")
        return rows

    print(f"\nFetched {len(raw_recipes)} recipes from {source.name}")
    print("=" * 70)

    for raw in raw_recipes:
        recipe_row = build_recipe_row(raw)
        ingredients = recipe_row.get("ingredients", [])
        recipe_results: list[dict] = []

        for ing in ingredients:
            name = ing.get("name", "")
            qty = ing.get("quantity", 100)
            unit = ing.get("unit", "g")

            if not name:
                continue

            role = get_ingredient_role(name)

            try:
                result = await match_ingredient(
                    ingredient_name=name,
                    quantity=qty,
                    unit=unit,
                    supabase=supabase,
                )
                matched = result.get("matched_name") is not None
                matched_to = result.get("matched_name", "")
                confidence = result.get("confidence", 0)
            except Exception as e:
                matched = False
                matched_to = f"ERROR: {e}"
                confidence = 0

            row = {
                "recipe": raw.name,
                "ingredient": name,
                "role": role,
                "qty": qty,
                "unit": unit,
                "matched": matched,
                "matched_to": matched_to or "",
                "confidence": round(confidence, 2),
            }
            recipe_results.append(row)
            rows.append(row)

        # Print per-recipe summary
        n_matched = sum(1 for r in recipe_results if r["matched"])
        n_total = len(recipe_results)
        status = "OK" if n_matched == n_total else "PARTIAL"
        if n_matched == 0 and n_total > 0:
            status = "FAIL"

        failed = [r for r in recipe_results if not r["matched"]]
        failed_str = ", ".join(f"{r['ingredient']}({r['role']})" for r in failed)

        print(f"\n[{status}] {raw.name} — {n_matched}/{n_total} matched")
        if failed:
            print(f"  Missing: {failed_str}")

    return rows


def print_summary(rows: list[dict], source_name: str) -> None:
    """Print aggregate statistics."""
    if not rows:
        print("\nNo data to analyze.")
        return

    total = len(rows)
    matched = sum(1 for r in rows if r["matched"])
    failed = [r for r in rows if not r["matched"]]

    print(f"\n{'=' * 70}")
    print(f"DIAGNOSTIC SUMMARY — {source_name}")
    print(f"{'=' * 70}")
    print(f"  Total ingredients tested:  {total}")
    print(f"  Matched:                   {matched} ({matched/total:.0%})")
    print(f"  Failed:                    {len(failed)} ({len(failed)/total:.0%})")

    # By role
    roles = Counter(r["role"] for r in rows)
    role_matched = Counter(r["role"] for r in rows if r["matched"])
    print("\n  By role:")
    for role in sorted(roles.keys()):
        t = roles[role]
        m = role_matched.get(role, 0)
        print(f"    {role:12s}: {m}/{t} matched ({m/t:.0%})")

    # Top failed ingredients
    if failed:
        fail_counter = Counter(r["ingredient"] for r in failed)
        print("\n  Top failed ingredients:")
        for ing, count in fail_counter.most_common(20):
            role = next(r["role"] for r in failed if r["ingredient"] == ing)
            print(f"    {ing:30s} ({role:10s}) × {count}")

    # Impact of levier B (tolerate fixed)
    fixed_fails = [r for r in failed if r["role"] == "fixed"]
    non_fixed_fails = [r for r in failed if r["role"] != "fixed"]
    print("\n  LEVIER B impact (tolerate fixed ingredients):")
    print(f"    Fixed fails that would be tolerated:     {len(fixed_fails)}")
    print(f"    Non-fixed fails still blocking:          {len(non_fixed_fails)}")
    if failed:
        new_rate = (matched + len(fixed_fails)) / total
        print(
            f"    New match rate with levier B:            {new_rate:.0%} (was {matched/total:.0%})"
        )

    # Recipes that would pass with levier B
    recipes = {}
    for r in rows:
        recipes.setdefault(r["recipe"], []).append(r)

    total_recipes = len(recipes)
    pass_now = sum(1 for ings in recipes.values() if all(r["matched"] for r in ings))
    pass_with_b = sum(
        1
        for ings in recipes.values()
        if all(r["matched"] or r["role"] == "fixed" for r in ings)
    )
    print("\n  Recipe pass rate:")
    print(
        f"    Current:      {pass_now}/{total_recipes} ({pass_now/total_recipes:.0%})"
    )
    print(
        f"    With levier B: {pass_with_b}/{total_recipes} ({pass_with_b/total_recipes:.0%})"
    )


def save_csv(rows: list[dict], path: str) -> None:
    """Save diagnostic results to CSV."""
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nCSV saved to: {path}")


async def main_async(args: argparse.Namespace) -> None:
    supabase = get_supabase_client()

    if args.source == "all":
        source_names = list(SOURCE_REGISTRY.keys())
    else:
        source_names = [args.source]

    all_rows: list[dict] = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        for source_name in source_names:
            adapter_cls = SOURCE_REGISTRY.get(source_name)
            if not adapter_cls:
                print(f"Unknown source: {source_name}")
                continue
            adapter = adapter_cls()
            rows = await diagnose_source(adapter, client, supabase, args.limit)
            all_rows.extend(rows)

    print_summary(all_rows, args.source)

    if args.csv:
        save_csv(all_rows, args.csv)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Diagnose ingredient OFF resolution rate for recipe sources"
    )
    parser.add_argument(
        "--source",
        default="themealdb",
        choices=["all"] + list(SOURCE_REGISTRY.keys()),
    )
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--csv", type=str, default=None, help="Save results to CSV")
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
