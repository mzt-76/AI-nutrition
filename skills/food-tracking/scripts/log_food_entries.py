"""Log food items to daily_food_log with OFF-validated macros.

Reuses match_ingredient() from openfoodfacts_client for macro calculation.
Pattern: same parallel asyncio.gather as generate_custom_recipe.py.
"""

import asyncio
import json
import logging
from datetime import date

from src.nutrition.openfoodfacts_client import match_ingredient

logger = logging.getLogger(__name__)


async def execute(**kwargs) -> str:
    """Log food items to daily_food_log with OFF-validated macros.

    Args (via kwargs):
        supabase: Supabase client
        user_id: User UUID
        items: list of {name: str, quantity: float, unit: str}
        log_date: str (YYYY-MM-DD), defaults to today
        meal_type: str, defaults to "dejeuner"

    Returns:
        JSON with per-item macros + totals
    """
    supabase = kwargs["supabase"]
    user_id = kwargs["user_id"]

    # --- Normalize keys (LLMs sometimes drift from the documented interface) ---
    # Flat item lists: accept items / entries / foods / food_entries / food_items
    raw_items: list[dict] = (
        kwargs.get("items")
        or kwargs.get("entries")
        or kwargs.get("foods")
        or kwargs.get("food_entries")
        or kwargs.get("food_items")
        or []
    )
    # Handle nested "meals" wrapper: [{meal_type: "...", foods: [...]}]
    meals_wrapper = kwargs.get("meals")
    meal_type = kwargs.get("meal_type")
    if isinstance(meals_wrapper, list) and meals_wrapper and not raw_items:
        first_meal = meals_wrapper[0] if isinstance(meals_wrapper[0], dict) else {}
        raw_items = first_meal.get("foods") or first_meal.get("items") or []
        if not meal_type:
            meal_type = first_meal.get("meal_type")
    # Extract meal_type from individual items if not at top level
    if not meal_type and raw_items:
        for raw_item in raw_items:
            if isinstance(raw_item, dict) and raw_item.get("meal_type"):
                meal_type = raw_item["meal_type"]
                break
    # Normalize item keys: accept "food_name" as alias for "name", skip non-dicts
    items: list[dict] = [
        {
            "name": it.get("name") or it.get("food_name", ""),
            "quantity": it.get("quantity", 100),
            "unit": it.get("unit", "g"),
        }
        for it in raw_items
        if isinstance(it, dict)
    ]
    log_date = kwargs.get("log_date") or kwargs.get("date") or date.today().isoformat()
    # Normalize English → French meal types
    _MEAL_TYPE_ALIASES = {
        "breakfast": "petit-dejeuner",
        "petit_dejeuner": "petit-dejeuner",
        "lunch": "dejeuner",
        "dinner": "diner",
        "snack": "collation",
    }
    meal_type = _MEAL_TYPE_ALIASES.get(meal_type or "", meal_type) or "dejeuner"
    entry_id: str | None = kwargs.get("entry_id")

    if not user_id:
        return json.dumps({"error": "No user_id provided", "code": "NO_USER"})

    # --- Modify existing entry by ID ---
    if entry_id:
        if not items:
            return json.dumps(
                {"error": "No items provided for rename", "code": "EMPTY_ITEMS"}
            )

        new_food_name = items[0].get("name", "")
        if not new_food_name:
            return json.dumps({"error": "No food name provided", "code": "EMPTY_NAME"})

        # Fetch existing entry for quantity/unit
        existing = await (
            supabase.table("daily_food_log")
            .select("quantity, unit, user_id")
            .eq("id", entry_id)
            .limit(1)
            .execute()
        )
        if not existing.data:
            return json.dumps({"error": "Entry not found", "code": "NOT_FOUND"})
        entry_row = existing.data[0]
        if entry_row.get("user_id") != user_id:
            return json.dumps({"error": "Not authorized", "code": "FORBIDDEN"})

        qty = entry_row.get("quantity", 100)
        unit = entry_row.get("unit", "g")

        try:
            macros = await match_ingredient(new_food_name, qty, unit, supabase)
        except Exception as e:
            logger.error(f"match_ingredient failed for '{new_food_name}': {e}")
            return json.dumps(
                {"error": "Failed to match ingredient", "code": "MATCH_ERROR"}
            )

        if macros.get("confidence", 0) == 0:
            return json.dumps({"error": "Aliment non trouvé", "code": "NO_MATCH"})

        update_fields = {
            "food_name": new_food_name,
            "calories": round(macros.get("calories", 0), 1),
            "protein_g": round(macros.get("protein_g", 0), 1),
            "carbs_g": round(macros.get("carbs_g", 0), 1),
            "fat_g": round(macros.get("fat_g", 0), 1),
        }
        await (
            supabase.table("daily_food_log")
            .update(update_fields)
            .eq("id", entry_id)
            .execute()
        )

        logger.info(f"Updated entry {entry_id} to '{new_food_name}' for user {user_id}")
        return json.dumps(
            {
                "success": True,
                "entry_id": entry_id,
                "updated": update_fields,
                "matched_name": macros.get("matched_name"),
                "confidence": macros.get("confidence", 0),
            },
            ensure_ascii=False,
        )

    if not items:
        return json.dumps({"error": "No items provided", "code": "EMPTY_ITEMS"})

    try:
        # Match all ingredients in parallel via OFF
        macro_results = await asyncio.gather(
            *[
                match_ingredient(
                    ingredient_name=item.get("name", ""),
                    quantity=item.get("quantity", 100),
                    unit=item.get("unit", "g"),
                    supabase=supabase,
                )
                for item in items
            ]
        )

        # Build rows and insert
        logged_items = []
        total_calories = 0.0
        total_protein = 0.0
        total_carbs = 0.0
        total_fat = 0.0

        for item, macros in zip(items, macro_results):
            cal = macros.get("calories", 0) if macros else 0
            prot = macros.get("protein_g", 0) if macros else 0
            carbs = macros.get("carbs_g", 0) if macros else 0
            fat = macros.get("fat_g", 0) if macros else 0

            food_name = item.get("name", "")
            row = {
                "user_id": user_id,
                "log_date": log_date,
                "meal_type": meal_type,
                "food_name": food_name,
                "quantity": item.get("quantity", 100),
                "unit": item.get("unit", "g"),
                "calories": round(cal, 1),
                "protein_g": round(prot, 1),
                "carbs_g": round(carbs, 1),
                "fat_g": round(fat, 1),
                "source": "openfoodfacts",
            }

            # Upsert: insert or update if same user/date/meal/food already exists
            await (
                supabase.table("daily_food_log")
                .upsert(row, on_conflict="user_id,log_date,meal_type,food_name")
                .execute()
            )

            total_calories += cal
            total_protein += prot
            total_carbs += carbs
            total_fat += fat

            logged_items.append(
                {
                    "food_name": item.get("name", ""),
                    "quantity": item.get("quantity", 100),
                    "unit": item.get("unit", "g"),
                    "calories": round(cal, 1),
                    "protein_g": round(prot, 1),
                    "carbs_g": round(carbs, 1),
                    "fat_g": round(fat, 1),
                    "matched_name": macros.get("matched_name") if macros else None,
                    "confidence": macros.get("confidence", 0) if macros else 0,
                }
            )

        logger.info(
            f"Logged {len(logged_items)} food items for user {user_id} "
            f"on {log_date}: {round(total_calories)} kcal"
        )

        return json.dumps(
            {
                "success": True,
                "logged_items": logged_items,
                "totals": {
                    "calories": round(total_calories, 1),
                    "protein_g": round(total_protein, 1),
                    "carbs_g": round(total_carbs, 1),
                    "fat_g": round(total_fat, 1),
                },
                "log_date": log_date,
                "meal_type": meal_type,
                "item_count": len(logged_items),
            },
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        logger.error(f"Error logging food entries: {e}", exc_info=True)
        return json.dumps(
            {"error": "Failed to log food entries", "code": "SCRIPT_ERROR"}
        )
