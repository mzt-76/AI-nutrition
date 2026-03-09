"""Import recipes from TheMealDB into Supabase with OFF validation.

LLM-free (rule 10) — uses only src.nutrition.*, src.clients, httpx, and stdlib.

Pipeline:
    1. Fetch categories from TheMealDB API
    2. For each relevant category, fetch recipe list then full details
    3. Map TheMealDB format → DB schema (ingredients, meal_type, etc.)
    4. OFF-validate each recipe for real nutrition data
    5. Upsert into recipes table (same table as manual recipes)

Usage:
    PYTHONPATH=. python scripts/import_themealdb.py [--limit 200] [--dry-run]
"""

import argparse
import asyncio
import logging
import unicodedata
from pathlib import Path

import httpx

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)

from src.clients import get_supabase_client  # noqa: E402
from src.nutrition.openfoodfacts_client import off_validate_recipe  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

THEMEALDB_BASE = "https://www.themealdb.com/api/json/v1/1"

# TheMealDB recipes are multi-portion — divide quantities by this to get per-serving
DEFAULT_SERVINGS = 4

# Categories worth importing (skip Dessert, Miscellaneous, Starter, Side, Goat)
RELEVANT_CATEGORIES = {
    "Beef",
    "Chicken",
    "Lamb",
    "Pasta",
    "Pork",
    "Seafood",
    "Vegan",
    "Vegetarian",
    "Breakfast",
}

# Map TheMealDB category → our meal_type
CATEGORY_TO_MEAL_TYPE: dict[str, str] = {
    "Breakfast": "petit-dejeuner",
    # All others default to dejeuner/diner (alternating)
}

# Common ingredient translations EN → FR
INGREDIENT_FR: dict[str, str] = {
    "chicken": "poulet",
    "chicken breast": "blanc de poulet",
    "chicken thighs": "cuisses de poulet",
    "beef": "boeuf",
    "pork": "porc",
    "lamb": "agneau",
    "salmon": "saumon",
    "tuna": "thon",
    "shrimp": "crevettes",
    "prawns": "crevettes",
    "rice": "riz",
    "pasta": "pâtes",
    "spaghetti": "spaghetti",
    "penne": "penne",
    "egg": "oeuf",
    "eggs": "oeufs",
    "onion": "oignon",
    "onions": "oignons",
    "garlic": "ail",
    "garlic clove": "gousse d'ail",
    "garlic cloves": "gousses d'ail",
    "tomato": "tomate",
    "tomatoes": "tomates",
    "tomato puree": "purée de tomates",
    "tomato paste": "concentré de tomates",
    "potato": "pomme de terre",
    "potatoes": "pommes de terre",
    "carrot": "carotte",
    "carrots": "carottes",
    "olive oil": "huile d'olive",
    "vegetable oil": "huile végétale",
    "butter": "beurre",
    "milk": "lait",
    "cream": "crème",
    "flour": "farine",
    "sugar": "sucre",
    "salt": "sel",
    "pepper": "poivre",
    "black pepper": "poivre noir",
    "water": "eau",
    "lemon": "citron",
    "lemon juice": "jus de citron",
    "lime": "citron vert",
    "ginger": "gingembre",
    "cumin": "cumin",
    "paprika": "paprika",
    "chili powder": "piment en poudre",
    "cinnamon": "cannelle",
    "parsley": "persil",
    "basil": "basilic",
    "thyme": "thym",
    "oregano": "origan",
    "bay leaf": "feuille de laurier",
    "bay leaves": "feuilles de laurier",
    "soy sauce": "sauce soja",
    "coconut milk": "lait de coco",
    "broccoli": "brocoli",
    "spinach": "épinards",
    "mushrooms": "champignons",
    "mushroom": "champignon",
    "bell pepper": "poivron",
    "red pepper": "poivron rouge",
    "green pepper": "poivron vert",
    "celery": "céleri",
    "zucchini": "courgette",
    "avocado": "avocat",
    "cheese": "fromage",
    "parmesan": "parmesan",
    "mozzarella": "mozzarella",
    "feta": "feta",
    "bread": "pain",
    "chickpeas": "pois chiches",
    "lentils": "lentilles",
    "black beans": "haricots noirs",
    "kidney beans": "haricots rouges",
    "honey": "miel",
    "vinegar": "vinaigre",
    "mustard": "moutarde",
    "worcestershire sauce": "sauce Worcestershire",
    "stock": "bouillon",
    "chicken stock": "bouillon de poulet",
    "beef stock": "bouillon de boeuf",
    "vegetable stock": "bouillon de légumes",
    "plain flour": "farine",
    "self-raising flour": "farine avec levure",
    "coriander": "coriandre",
    "spring onions": "oignons verts",
    "red onion": "oignon rouge",
    "red onions": "oignons rouges",
    "green beans": "haricots verts",
    "sweetcorn": "maïs",
    "peas": "petits pois",
    "pine nuts": "pignons de pin",
    "almonds": "amandes",
    "walnuts": "noix",
    "sesame oil": "huile de sésame",
    "fish sauce": "sauce de poisson",
    "chili": "piment",
    "chilli": "piment",
    "turmeric": "curcuma",
}

# Known allergen mappings
ALLERGEN_KEYWORDS: dict[str, list[str]] = {
    "gluten": ["flour", "bread", "pasta", "spaghetti", "penne", "noodles", "wheat"],
    "lactose": [
        "milk",
        "cream",
        "butter",
        "cheese",
        "parmesan",
        "mozzarella",
        "feta",
        "yogurt",
    ],
    "fruits_a_coque": [
        "almonds",
        "walnuts",
        "pine nuts",
        "cashews",
        "peanuts",
        "pecans",
    ],
    "crustaces": ["shrimp", "prawns", "crab", "lobster"],
    "poisson": ["salmon", "tuna", "cod", "fish sauce", "anchovy"],
    "oeufs": ["egg", "eggs"],
    "soja": ["soy sauce", "tofu", "soy"],
}


def _normalize_name(name: str) -> str:
    """Lowercase + strip accents for deduplication."""
    nfkd = unicodedata.normalize("NFKD", name.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _parse_measure(measure_str: str) -> tuple[float, str]:
    """Parse TheMealDB measure string into (quantity_grams, unit).

    Best-effort conversion — defaults to 100g for unparseable measures.
    """
    if not measure_str:
        return 100.0, "g"

    s = measure_str.strip().lower()

    # Direct gram/ml matches
    for suffix in ("g", "ml"):
        if s.endswith(suffix):
            num_part = s[: -len(suffix)].strip().rstrip("/")
            try:
                return float(num_part), suffix
            except ValueError:
                pass

    # "kg" → convert to g
    if s.endswith("kg"):
        num_part = s[:-2].strip()
        try:
            return float(num_part) * 1000, "g"
        except ValueError:
            pass

    # Tablespoon/teaspoon approximations
    tbsp_words = ("tbsp", "tbs", "tablespoon", "tablespoons")
    tsp_words = ("tsp", "teaspoon", "teaspoons")
    cup_words = ("cup", "cups")

    for word in tbsp_words:
        if word in s:
            num = _extract_number(s, word)
            return num * 15, "g"  # 1 tbsp ≈ 15g
    for word in tsp_words:
        if word in s:
            num = _extract_number(s, word)
            return num * 5, "g"  # 1 tsp ≈ 5g
    for word in cup_words:
        if word in s:
            num = _extract_number(s, word)
            return num * 240, "g"  # 1 cup ≈ 240g

    # Fractions
    if "/" in s:
        parts = s.split()
        for part in parts:
            if "/" in part:
                try:
                    num, den = part.split("/")
                    return float(num) / float(den) * 100, "g"
                except (ValueError, ZeroDivisionError):
                    pass

    # Plain number → assume grams or pieces
    try:
        val = float(s.split()[0])
        if val < 10:
            return val * 100, "g"  # "2" → 200g (2 pieces)
        return val, "g"
    except (ValueError, IndexError):
        pass

    return 100.0, "g"


def _extract_number(text: str, keyword: str) -> float:
    """Extract numeric part before a keyword in a measure string."""
    idx = text.find(keyword)
    if idx <= 0:
        return 1.0
    num_part = text[:idx].strip()
    if not num_part:
        return 1.0
    # Handle fractions like "1/2"
    if "/" in num_part:
        parts = num_part.split()
        total = 0.0
        for p in parts:
            if "/" in p:
                try:
                    n, d = p.split("/")
                    total += float(n) / float(d)
                except (ValueError, ZeroDivisionError):
                    pass
            else:
                try:
                    total += float(p)
                except ValueError:
                    pass
        return total if total > 0 else 1.0
    try:
        return float(num_part)
    except ValueError:
        return 1.0


def _translate_ingredient(name: str) -> str:
    """Translate ingredient name EN → FR using lookup table."""
    key = name.lower().strip()
    return INGREDIENT_FR.get(key, name)


def _detect_allergens(ingredients: list[dict]) -> list[str]:
    """Detect allergen tags from ingredient names."""
    allergens = set()
    for ing in ingredients:
        name_lower = ing.get("name", "").lower()
        for allergen, keywords in ALLERGEN_KEYWORDS.items():
            if any(kw in name_lower for kw in keywords):
                allergens.add(allergen)
    return sorted(allergens)


def _detect_diet_type(category: str, ingredients: list[dict]) -> str:
    """Infer diet_type from category and ingredients."""
    if category == "Vegan":
        return "vegan"
    if category == "Vegetarian":
        return "végétarien"
    return "omnivore"


def _get_meal_types(category: str) -> list[str]:
    """Return meal_types for a category. Main courses → both dejeuner AND diner."""
    if category in CATEGORY_TO_MEAL_TYPE:
        return [CATEGORY_TO_MEAL_TYPE[category]]
    # Main courses work for both lunch and dinner
    return ["dejeuner", "diner"]


def _extract_ingredients(meal: dict) -> list[dict]:
    """Extract ingredients from TheMealDB strIngredient1..20 + strMeasure1..20.

    Keeps raw quantities — _auto_correct_portions() fixes after OFF validation.
    """
    ingredients = []
    for i in range(1, 21):
        name = (meal.get(f"strIngredient{i}") or "").strip()
        measure = (meal.get(f"strMeasure{i}") or "").strip()
        if not name:
            break
        quantity, unit = _parse_measure(measure)
        ingredients.append(
            {
                "name": _translate_ingredient(name),
                "quantity": round(quantity, 1),
                "unit": unit,
            }
        )
    return ingredients


# Sane per-serving calorie range — anything outside triggers auto-correction
MIN_SANE_CALORIES = 150
MAX_SANE_CALORIES = 900
TARGET_CALORIES_PER_SERVING = 500  # target to normalize to


def _auto_correct_portions(row: dict) -> dict:
    """If OFF-validated macros are aberrant, divide ingredient quantities to normalize.

    Detects multi-portion recipes by checking if calories > MAX_SANE_CALORIES,
    computes the correction factor, and scales all ingredient quantities down.
    Then recalculates macros from the corrected quantities.

    Returns the corrected row (or unchanged if already in range).
    """
    cal = float(row.get("calories_per_serving", 0) or 0)

    if cal <= MAX_SANE_CALORIES:
        return row  # already fine

    # How many portions were in the "single serving"?
    correction_factor = cal / TARGET_CALORIES_PER_SERVING

    logger.info(
        f"  Auto-correct: {cal:.0f} kcal → ÷{correction_factor:.1f} "
        f"→ ~{cal / correction_factor:.0f} kcal"
    )

    # Scale down all ingredient quantities
    ingredients = row.get("ingredients", [])
    for ing in ingredients:
        old_qty = ing.get("quantity", 0) or 0
        ing["quantity"] = round(old_qty / correction_factor, 1)

    # Recalculate macros from scaled ingredients (using nutrition_per_100g)
    totals = {"calories": 0.0, "protein_g": 0.0, "fat_g": 0.0, "carbs_g": 0.0}
    for ing in ingredients:
        n = ing.get("nutrition_per_100g")
        if not n:
            continue
        qty = ing.get("quantity", 0) or 0
        factor = qty / 100.0
        totals["calories"] += (n.get("calories", 0) or 0) * factor
        totals["protein_g"] += (n.get("protein_g", 0) or 0) * factor
        totals["fat_g"] += (n.get("fat_g", 0) or 0) * factor
        totals["carbs_g"] += (n.get("carbs_g", 0) or 0) * factor

    row["ingredients"] = ingredients
    row["calories_per_serving"] = round(totals["calories"], 2)
    row["protein_g_per_serving"] = round(totals["protein_g"], 2)
    row["fat_g_per_serving"] = round(totals["fat_g"], 2)
    row["carbs_g_per_serving"] = round(totals["carbs_g"], 2)

    return row


# Acceptable macro ratio ranges (caloric proportion)
# ~25% protein, ~50% carbs, ~25% fat — with wide tolerance for recipe diversity
MAX_FAT_RATIO = 0.45  # >45% fat = too greasy (e.g. deep-fried, all-cheese)
MIN_PROTEIN_RATIO = (
    0.08  # <8% protein = dessert/pure-carb (not useful for meal planning)
)
MAX_PROTEIN_RATIO = 0.65  # >65% protein = data error (pure protein powder)


def _has_sane_macro_ratios(row: dict) -> bool:
    """Check if macro ratios are within acceptable bounds for meal planning.

    Returns True if the recipe is usable, False if it should be skipped.
    """
    cal = float(row.get("calories_per_serving", 0) or 0)
    if cal < MIN_SANE_CALORIES:
        logger.info(f"  Ratio check: {cal:.0f} kcal < {MIN_SANE_CALORIES} → skip")
        return False

    prot = float(row.get("protein_g_per_serving", 0) or 0)
    fat = float(row.get("fat_g_per_serving", 0) or 0)

    prot_ratio = (prot * 4) / cal
    fat_ratio = (fat * 9) / cal

    if fat_ratio > MAX_FAT_RATIO:
        logger.info(f"  Ratio check: fat={fat_ratio:.0%} > {MAX_FAT_RATIO:.0%} → skip")
        return False
    if prot_ratio < MIN_PROTEIN_RATIO:
        logger.info(
            f"  Ratio check: protein={prot_ratio:.0%} < {MIN_PROTEIN_RATIO:.0%} → skip"
        )
        return False
    if prot_ratio > MAX_PROTEIN_RATIO:
        logger.info(
            f"  Ratio check: protein={prot_ratio:.0%} > {MAX_PROTEIN_RATIO:.0%} → skip"
        )
        return False

    return True


def _build_recipe_rows(meal: dict, category: str) -> list[dict]:
    """Convert a TheMealDB meal to DB rows. Main courses → 2 rows (dejeuner + diner)."""
    ingredients = _extract_ingredients(meal)
    meal_types = _get_meal_types(category)

    base = {
        "name": meal["strMeal"],
        "name_normalized": _normalize_name(meal["strMeal"]),
        "cuisine_type": (meal.get("strArea") or "internationale").lower(),
        "diet_type": _detect_diet_type(category, ingredients),
        "tags": [
            t.strip() for t in (meal.get("strTags") or "").split(",") if t.strip()
        ],
        "ingredients": ingredients,
        "instructions": meal.get("strInstructions") or "",
        "prep_time_minutes": 30,  # TheMealDB doesn't provide this
        "allergen_tags": _detect_allergens(ingredients),
        "source": "themealdb",
        # Placeholder macros — will be replaced by OFF validation
        "calories_per_serving": 0.0,
        "protein_g_per_serving": 0.0,
        "carbs_g_per_serving": 0.0,
        "fat_g_per_serving": 0.0,
        "off_validated": False,
    }

    return [{**base, "meal_type": mt} for mt in meal_types]


async def fetch_categories(client: httpx.AsyncClient) -> list[str]:
    """Fetch and filter relevant categories from TheMealDB."""
    resp = await client.get(f"{THEMEALDB_BASE}/categories.php")
    resp.raise_for_status()
    data = resp.json()
    categories = [
        c["strCategory"]
        for c in data.get("categories", [])
        if c["strCategory"] in RELEVANT_CATEGORIES
    ]
    logger.info(f"Fetched {len(categories)} relevant categories: {categories}")
    return categories


async def fetch_meals_by_category(
    client: httpx.AsyncClient, category: str
) -> list[dict]:
    """Fetch list of meals in a category (ID + name only)."""
    resp = await client.get(f"{THEMEALDB_BASE}/filter.php", params={"c": category})
    resp.raise_for_status()
    data = resp.json()
    return data.get("meals") or []


async def fetch_meal_details(client: httpx.AsyncClient, meal_id: str) -> dict | None:
    """Fetch full meal details by ID."""
    resp = await client.get(f"{THEMEALDB_BASE}/lookup.php", params={"i": meal_id})
    resp.raise_for_status()
    data = resp.json()
    meals = data.get("meals")
    return meals[0] if meals else None


async def import_recipes(limit: int = 200, dry_run: bool = False) -> None:
    """Main import pipeline."""
    supabase = get_supabase_client()

    counts: dict[str, int] = {
        "fetched": 0,
        "validated": 0,
        "upserted": 0,
        "skipped": 0,
        "failed": 0,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        categories = await fetch_categories(client)

        all_meals: list[tuple[dict, str]] = []  # (meal_summary, category)

        for category in categories:
            meal_list = await fetch_meals_by_category(client, category)
            for meal_summary in meal_list:
                all_meals.append((meal_summary, category))

        logger.info(f"Total meals across categories: {len(all_meals)}")

        # Limit to avoid importing everything
        if len(all_meals) > limit:
            # Distribute evenly across categories
            per_cat = max(1, limit // len(categories))
            limited: list[tuple[dict, str]] = []
            cat_counts: dict[str, int] = {}
            for meal_summary, category in all_meals:
                cat_counts.setdefault(category, 0)
                if cat_counts[category] < per_cat and len(limited) < limit:
                    limited.append((meal_summary, category))
                    cat_counts[category] += 1
            all_meals = limited
            logger.info(f"Limited to {len(all_meals)} meals (≤{per_cat}/category)")

        for idx, (meal_summary, category) in enumerate(all_meals):
            meal_id = meal_summary.get("idMeal")
            meal_name = meal_summary.get("strMeal", "?")

            try:
                meal = await fetch_meal_details(client, meal_id)
                if not meal:
                    logger.warning(f"  Could not fetch details for {meal_name}")
                    counts["skipped"] += 1
                    continue

                counts["fetched"] += 1
                rows = _build_recipe_rows(meal, category)

                # OFF validate on first row (ingredients are identical across meal_types)
                validated_row = await off_validate_recipe(rows[0], supabase)

                if not validated_row.get("off_validated"):
                    logger.info(f"  SKIP {meal_name} — OFF validation failed")
                    counts["skipped"] += 1
                    continue

                # Auto-correct portions if calories are aberrant (multi-portion recipe)
                validated_row = _auto_correct_portions(validated_row)

                # Check macro ratios — skip nutritionally unbalanced recipes
                if not _has_sane_macro_ratios(validated_row):
                    logger.info(f"  SKIP {meal_name} — aberrant macro ratios")
                    counts["skipped"] += 1
                    continue

                counts["validated"] += 1

                # Apply OFF data to all rows (dejeuner + diner share same macros)
                for row in rows:
                    row["ingredients"] = validated_row["ingredients"]
                    row["calories_per_serving"] = validated_row["calories_per_serving"]
                    row["protein_g_per_serving"] = validated_row[
                        "protein_g_per_serving"
                    ]
                    row["carbs_g_per_serving"] = validated_row["carbs_g_per_serving"]
                    row["fat_g_per_serving"] = validated_row["fat_g_per_serving"]
                    row["off_validated"] = True
                    row["allergen_tags"] = validated_row.get(
                        "allergen_tags", row.get("allergen_tags", [])
                    )

                meal_types_str = "+".join(r["meal_type"] for r in rows)

                if dry_run:
                    logger.info(
                        f"  [DRY] {validated_row['name']} | {meal_types_str} | "
                        f"{validated_row['calories_per_serving']:.0f} kcal | "
                        f"{validated_row['protein_g_per_serving']:.0f}p/"
                        f"{validated_row['fat_g_per_serving']:.0f}f/"
                        f"{validated_row['carbs_g_per_serving']:.0f}c"
                    )
                    continue

                # Upsert all rows (1 for breakfast, 2 for main courses)
                for row in rows:
                    supabase.table("recipes").upsert(
                        row, on_conflict="name_normalized,meal_type"
                    ).execute()
                    counts["upserted"] += 1

                logger.info(
                    f"  OK {validated_row['name']} | {meal_types_str} | "
                    f"{validated_row['calories_per_serving']:.0f} kcal | "
                    f"{validated_row['protein_g_per_serving']:.0f}p/"
                    f"{validated_row['fat_g_per_serving']:.0f}f/"
                    f"{validated_row['carbs_g_per_serving']:.0f}c"
                )

            except Exception as e:
                logger.error(f"  FAIL {meal_name}: {e}")
                counts["failed"] += 1

    logger.info(
        f"\nDone: fetched={counts['fetched']}, validated={counts['validated']}, "
        f"upserted={counts['upserted']}, skipped={counts['skipped']}, failed={counts['failed']}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Import TheMealDB recipes")
    parser.add_argument("--limit", type=int, default=300, help="Max recipes to import")
    parser.add_argument(
        "--dry-run", action="store_true", help="Validate but don't upsert"
    )
    args = parser.parse_args()

    asyncio.run(import_recipes(limit=args.limit, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
