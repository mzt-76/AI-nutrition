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
    items: list[dict] = kwargs.get("items", [])
    log_date = kwargs.get("log_date", date.today().isoformat())
    meal_type = kwargs.get("meal_type", "dejeuner")
    entry_id: str | None = kwargs.get("entry_id")

    if not user_id:
        return json.dumps({"error": "No user_id provided", "code": "NO_USER"})

    # --- Modify existing entry by ID ---
    if entry_id:
        if not items:
            return json.dumps({"error": "No items provided for rename", "code": "EMPTY_ITEMS"})

        new_food_name = items[0].get("name", "")
        if not new_food_name:
            return json.dumps({"error": "No food name provided", "code": "EMPTY_NAME"})

        # Fetch existing entry for quantity/unit
        existing = (
            supabase.table("daily_food_log")
            .select("quantity, unit, user_id")
            .eq("id", entry_id)
            .single()
            .execute()
        )
        if not existing.data:
            return json.dumps({"error": "Entry not found", "code": "NOT_FOUND"})
        if existing.data.get("user_id") != user_id:
            return json.dumps({"error": "Not authorized", "code": "FORBIDDEN"})

        qty = existing.data.get("quantity", 100)
        unit = existing.data.get("unit", "g")

        try:
            macros = await match_ingredient(new_food_name, qty, unit, supabase)
        except Exception as e:
            logger.error(f"match_ingredient failed for '{new_food_name}': {e}")
            return json.dumps({"error": "Failed to match ingredient", "code": "MATCH_ERROR"})

        if macros.get("confidence", 0) == 0:
            return json.dumps({"error": "Aliment non trouvé", "code": "NO_MATCH"})

        update_fields = {
            "food_name": new_food_name,
            "calories": round(macros.get("calories", 0), 1),
            "protein_g": round(macros.get("protein_g", 0), 1),
            "carbs_g": round(macros.get("carbs_g", 0), 1),
            "fat_g": round(macros.get("fat_g", 0), 1),
        }
        supabase.table("daily_food_log").update(update_fields).eq("id", entry_id).execute()

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

            # Check if this food already exists for the same user/date/meal
            existing = (
                supabase.table("daily_food_log")
                .select("id")
                .eq("user_id", user_id)
                .eq("log_date", log_date)
                .eq("meal_type", meal_type)
                .ilike("food_name", food_name)
                .execute()
            )

            if existing.data:
                # Update existing entry instead of creating a duplicate
                entry_id = existing.data[0]["id"]
                update_fields = {k: v for k, v in row.items() if k != "user_id"}
                supabase.table("daily_food_log").update(update_fields).eq("id", entry_id).execute()
            else:
                supabase.table("daily_food_log").insert(row).execute()

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
