"""Fix liquid ingredient OFF code mismatches in recipe DB.

Two fix strategies:
- Option A (liquids): swap bad OFF code → correct liquid code
- Option B (concentrates): split "Bouillon (339ml)" → "Cube de bouillon (5g)" + "Eau (339ml)"

LLM-free (rule 10) — uses only src.clients and stdlib.

Usage:
    PYTHONPATH=. python scripts/fix_liquid_off_codes.py
"""

import logging

from src.clients import get_supabase_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# --- Option A: swap OFF code (true liquids) ---
CODE_SWAPS: dict[str, str] = {
    "2002657025588": "3171920000238",  # Sauce soja: concentrated → liquid
    "3547130022382": "3165356050066",  # Vinaigre de vin rouge: mislabel → real
    "8014347005149": "3347439950511",  # Vinaigre blanc: mislabel → real
}

# --- Option B: split concentrate + water ---
# Maps bad_code → (cube_name, cube_off_code, ml_per_10g_cube)
CONCENTRATE_SPLITS: dict[str, tuple[str, str, int]] = {
    "26064529": ("Cube de bouillon de légumes", "26064529", 500),
    "3760149750262": ("Cube de bouillon de poulet", "3760149750262", 500),
    "4513883605201": ("Dashi en poudre", "4513883605201", 500),
}


def _compute_cube_grams(liquid_ml: float, ml_per_10g_cube: int) -> float:
    """Convert liquid volume to equivalent cube/powder weight.

    Standard ratio: 10g cube for 500ml water.
    """
    grams = round(liquid_ml * 10 / ml_per_10g_cube)
    return max(5.0, grams)  # minimum 5g (half a cube)


def main() -> None:
    supabase = get_supabase_client()

    # Step 1: Delete bad ingredient_mapping cache entries
    all_bad_codes = list(CODE_SWAPS.keys()) + list(CONCENTRATE_SPLITS.keys())
    for bad_code in all_bad_codes:
        try:
            result = (
                supabase.table("ingredient_mapping")
                .delete()
                .eq("openfoodfacts_code", bad_code)
                .execute()
            )
            count = len(result.data) if result.data else 0
            if count:
                logger.info(f"Deleted {count} cache entries for code {bad_code}")
        except Exception as e:
            logger.warning(f"Failed to delete cache for {bad_code}: {e}")

    # Step 2: Fetch all recipes
    response = supabase.table("recipes").select("id, name, ingredients").execute()
    recipes = response.data or []

    updated_count = 0
    for recipe in recipes:
        ingredients = recipe.get("ingredients", [])
        new_ingredients = []
        modified = False

        for ing in ingredients:
            off_code = ing.get("off_code")

            # Option A: swap code
            if off_code in CODE_SWAPS:
                old_code = off_code
                new_code = CODE_SWAPS[old_code]
                ing["off_code"] = new_code
                ing.pop("nutrition_per_100g", None)
                ing.pop("confidence", None)
                modified = True
                logger.info(
                    f"  [{recipe['name']}] {ing.get('name', '?')}: "
                    f"swap {old_code} → {new_code}"
                )
                new_ingredients.append(ing)

            # Option B: split into cube + water
            elif off_code in CONCENTRATE_SPLITS:
                cube_name, cube_code, ml_per_cube = CONCENTRATE_SPLITS[off_code]
                original_name = ing.get("name", "Bouillon")
                original_qty = ing.get("quantity", 500)

                # Parse quantity — could be ml or a number
                try:
                    liquid_ml = float(original_qty)
                except (TypeError, ValueError):
                    liquid_ml = 500.0

                cube_g = _compute_cube_grams(liquid_ml, ml_per_cube)

                # Create cube ingredient (keeps the powder OFF code — it's correct for powder)
                cube_ing = {
                    "name": cube_name,
                    "quantity": cube_g,
                    "unit": "g",
                    "off_code": cube_code,
                }

                # Create water ingredient
                water_ing = {
                    "name": "Eau",
                    "quantity": round(liquid_ml),
                    "unit": "ml",
                }

                new_ingredients.append(cube_ing)
                new_ingredients.append(water_ing)
                modified = True
                logger.info(
                    f"  [{recipe['name']}] split '{original_name}' ({liquid_ml}ml) → "
                    f"'{cube_name}' ({cube_g}g) + Eau ({round(liquid_ml)}ml)"
                )
            else:
                new_ingredients.append(ing)

        if modified:
            supabase.table("recipes").update(
                {
                    "ingredients": new_ingredients,
                    "off_validated": False,
                }
            ).eq("id", recipe["id"]).execute()
            updated_count += 1

    logger.info(f"Updated {updated_count} recipes")
    logger.info("Next: PYTHONPATH=. python scripts/validate_all_recipes.py")


if __name__ == "__main__":
    main()
