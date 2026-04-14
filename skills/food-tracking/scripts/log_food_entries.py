"""Log food items to daily_food_log with OFF-validated macros.

Reuses match_ingredient() from openfoodfacts_client for macro calculation.
Pattern: same parallel asyncio.gather as generate_custom_recipe.py.
"""

import asyncio
import json
import logging
import re
from datetime import date

from src.nutrition.openfoodfacts_client import (
    _calorie_density_plausible,
    _passes_atwater_check,
    _unit_to_multiplier,
    match_ingredient,
    search_food_local,
)

_LLM_MODEL = "claude-haiku-4-5-20251001"

_LLM_SELECT_PROMPT = """L'utilisateur veut logger "{ingredient_name}".
Voici les produits OpenFoodFacts les plus proches :
{candidates_text}

Quel numéro correspond le mieux à "{ingredient_name}" ?
Réponds UNIQUEMENT avec le numéro (ex: 1). Si aucun ne correspond, réponds "0"."""

_LLM_ESTIMATE_PROMPT = """Estime les macronutriments pour 100g de "{ingredient_name}".
Réponds UNIQUEMENT en JSON : {{"calories": X, "protein_g": X, "carbs_g": X, "fat_g": X}}"""

logger = logging.getLogger(__name__)


async def _llm_select_candidate(
    anthropic_client, ingredient_name: str, candidates: list[dict]
) -> dict | None:
    """Ask LLM to pick the best OFF candidate for an ingredient."""
    if not anthropic_client or not candidates:
        return None
    lines = []
    for i, c in enumerate(candidates, 1):
        lines.append(
            f"{i}. {c['name']} — {c['calories_per_100g']:.0f} kcal/100g "
            f"(P:{c['protein_g_per_100g']:.1f} G:{c['carbs_g_per_100g']:.1f} "
            f"L:{c['fat_g_per_100g']:.1f})"
        )
    prompt = _LLM_SELECT_PROMPT.format(
        ingredient_name=ingredient_name,
        candidates_text="\n".join(lines),
    )
    try:
        message = await anthropic_client.messages.create(
            model=_LLM_MODEL,
            max_tokens=10,
            temperature=0.0,
            messages=[{"role": "user", "content": prompt}],
        )
        choice = message.content[0].text.strip()
        m = re.search(r"\d+", choice)
        if not m:
            return None
        idx = int(m.group()) - 1
        if 0 <= idx < len(candidates):
            logger.info(
                "LLM selected candidate #%d '%s' for '%s'",
                idx + 1,
                candidates[idx]["name"],
                ingredient_name,
            )
            return candidates[idx]
        return None  # LLM said "0" or out of range
    except Exception as e:
        logger.warning("LLM select failed for '%s': %s", ingredient_name, e)
        return None


async def _llm_estimate_macros(anthropic_client, ingredient_name: str) -> dict | None:
    """Ask LLM to estimate macros when OFF has no data at all."""
    if not anthropic_client:
        return None
    prompt = _LLM_ESTIMATE_PROMPT.format(ingredient_name=ingredient_name)
    try:
        message = await anthropic_client.messages.create(
            model=_LLM_MODEL,
            max_tokens=80,
            temperature=0.0,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        if raw.startswith("```"):
            raw = "\n".join(raw.split("\n")[1:-1])
        data = json.loads(raw)
        logger.info("LLM estimated macros for '%s': %s", ingredient_name, data)
        return {
            "calories": float(data.get("calories", 0)),
            "protein_g": float(data.get("protein_g", 0)),
            "carbs_g": float(data.get("carbs_g", 0)),
            "fat_g": float(data.get("fat_g", 0)),
        }
    except Exception as e:
        logger.warning("LLM estimate failed for '%s': %s", ingredient_name, e)
        return None


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
        skipped_items = []
        total_calories = 0.0
        total_protein = 0.0
        total_carbs = 0.0
        total_fat = 0.0

        anthropic_client = kwargs.get("anthropic_client")

        for item, macros in zip(items, macro_results):
            food_name = item.get("name", "")
            confidence = macros.get("confidence", 0) if macros else 0
            source = "openfoodfacts"

            if confidence == 0:
                # --- LLM fallback ---
                resolved = None

                # Tier 1: fetch low-confidence OFF candidates, let LLM pick
                try:
                    raw_candidates = await search_food_local(food_name, supabase)
                    valid_candidates = [
                        c
                        for c in raw_candidates
                        if c["confidence"] >= 0.3
                        and _passes_atwater_check(c)
                        and _calorie_density_plausible(
                            food_name, c["calories_per_100g"]
                        )
                    ]
                except Exception:
                    valid_candidates = []

                if valid_candidates:
                    selected = await _llm_select_candidate(
                        anthropic_client, food_name, valid_candidates[:5]
                    )
                    if selected:
                        multiplier = _unit_to_multiplier(
                            item.get("quantity", 100),
                            item.get("unit", "g"),
                            food_name,
                        )
                        resolved = {
                            "calories": round(
                                selected["calories_per_100g"] * multiplier, 1
                            ),
                            "protein_g": round(
                                selected["protein_g_per_100g"] * multiplier, 1
                            ),
                            "carbs_g": round(
                                selected["carbs_g_per_100g"] * multiplier, 1
                            ),
                            "fat_g": round(selected["fat_g_per_100g"] * multiplier, 1),
                        }
                        confidence = 0.6
                        source = "openfoodfacts"  # macros are still from OFF

                # Tier 2: LLM estimates macros directly
                if not resolved:
                    estimated = await _llm_estimate_macros(anthropic_client, food_name)
                    if estimated:
                        multiplier = _unit_to_multiplier(
                            item.get("quantity", 100),
                            item.get("unit", "g"),
                            food_name,
                        )
                        resolved = {
                            "calories": round(estimated["calories"] * multiplier, 1),
                            "protein_g": round(estimated["protein_g"] * multiplier, 1),
                            "carbs_g": round(estimated["carbs_g"] * multiplier, 1),
                            "fat_g": round(estimated["fat_g"] * multiplier, 1),
                        }
                        confidence = 0.4
                        source = "llm_estimated"

                # Both OFF and LLM failed → skip
                if not resolved:
                    skipped_items.append({"food_name": food_name, "reason": "no_match"})
                    continue

                cal = resolved["calories"]
                prot = resolved["protein_g"]
                carbs = resolved["carbs_g"]
                fat = resolved["fat_g"]
            else:
                # Normal OFF match
                cal = macros.get("calories", 0) if macros else 0
                prot = macros.get("protein_g", 0) if macros else 0
                carbs = macros.get("carbs_g", 0) if macros else 0
                fat = macros.get("fat_g", 0) if macros else 0

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
                "source": source,
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
                    "food_name": food_name,
                    "quantity": item.get("quantity", 100),
                    "unit": item.get("unit", "g"),
                    "calories": round(cal, 1),
                    "protein_g": round(prot, 1),
                    "carbs_g": round(carbs, 1),
                    "fat_g": round(fat, 1),
                    "matched_name": macros.get("matched_name") if macros else None,
                    "confidence": confidence,
                    "source": source,
                }
            )

        logger.info(
            f"Logged {len(logged_items)} food items for user {user_id} "
            f"on {log_date}: {round(total_calories)} kcal"
            + (f" ({len(skipped_items)} skipped)" if skipped_items else "")
        )

        result_data = {
            "success": len(logged_items) > 0,
            "logged_items": logged_items,
            "skipped_items": skipped_items,
            "totals": {
                "calories": round(total_calories, 1),
                "protein_g": round(total_protein, 1),
                "carbs_g": round(total_carbs, 1),
                "fat_g": round(total_fat, 1),
            },
            "log_date": log_date,
            "meal_type": meal_type,
            "item_count": len(logged_items),
        }
        if not logged_items and skipped_items:
            result_data["error"] = "Aucun aliment matché"
            result_data["code"] = "ALL_SKIPPED"

        return json.dumps(result_data, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Error logging food entries: {e}", exc_info=True)
        return json.dumps(
            {"error": "Failed to log food entries", "code": "SCRIPT_ERROR"}
        )
