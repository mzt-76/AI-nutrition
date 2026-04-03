"""Delete a food entry from daily_food_log.

Supports deletion by entry_id (direct) or by food_name + meal_type + log_date
(fuzzy search). Returns ambiguity list when multiple entries match a name search.
"""

import json
import logging
import re
from datetime import date

logger = logging.getLogger(__name__)


def _normalize(text: str) -> str:
    """Lowercase, strip accents-insensitive, collapse whitespace."""
    return re.sub(r"\s+", " ", text.lower().strip())


async def execute(**kwargs) -> str:
    """Delete a food entry from daily_food_log.

    Args (via kwargs):
        supabase: Supabase async client
        user_id: User UUID
        entry_id: UUID of the entry to delete (direct, preferred)
        food_name: Name to search for (fuzzy, if no entry_id)
        meal_type: Filter by meal type (optional, with food_name)
        log_date: YYYY-MM-DD (defaults to today)

    Returns:
        JSON with deleted entry details or ambiguity list
    """
    supabase = kwargs["supabase"]
    user_id = kwargs["user_id"]
    entry_id = kwargs.get("entry_id")
    food_name = kwargs.get("food_name")
    meal_type = kwargs.get("meal_type")
    log_date = kwargs.get("log_date") or kwargs.get("date") or date.today().isoformat()

    if not user_id:
        return json.dumps({"error": "No user_id provided", "code": "NO_USER"})

    if not entry_id and not food_name:
        return json.dumps(
            {
                "error": "Provide entry_id or food_name to identify the entry",
                "code": "MISSING_PARAMS",
            }
        )

    # --- Direct deletion by entry_id ---
    if entry_id:
        existing = await (
            supabase.table("daily_food_log")
            .select(
                "id, food_name, quantity, unit, calories, protein_g, carbs_g, fat_g, meal_type, user_id"
            )
            .eq("id", entry_id)
            .limit(1)
            .execute()
        )
        if not existing.data:
            return json.dumps({"error": "Entry not found", "code": "NOT_FOUND"})
        entry = existing.data[0]
        if entry.get("user_id") != user_id:
            return json.dumps({"error": "Not authorized", "code": "FORBIDDEN"})

        await supabase.table("daily_food_log").delete().eq("id", entry_id).execute()

        logger.info(
            f"Deleted entry {entry_id} ({entry['food_name']}) for user {user_id}"
        )
        return json.dumps(
            {
                "success": True,
                "deleted": {
                    "entry_id": entry["id"],
                    "food_name": entry["food_name"],
                    "quantity": entry.get("quantity"),
                    "unit": entry.get("unit"),
                    "calories": entry.get("calories"),
                    "protein_g": entry.get("protein_g"),
                    "carbs_g": entry.get("carbs_g"),
                    "fat_g": entry.get("fat_g"),
                    "meal_type": entry.get("meal_type"),
                },
            },
            ensure_ascii=False,
        )

    # --- Search by food_name (fuzzy) ---
    query = (
        supabase.table("daily_food_log")
        .select(
            "id, food_name, quantity, unit, calories, protein_g, carbs_g, fat_g, meal_type"
        )
        .eq("user_id", user_id)
        .eq("log_date", log_date)
    )
    if meal_type:
        query = query.eq("meal_type", meal_type)

    result = await query.execute()
    entries = result.data or []

    # Fuzzy match: all entries whose food_name contains the search term
    search_norm = _normalize(food_name)
    matches = [e for e in entries if search_norm in _normalize(e.get("food_name", ""))]

    if not matches:
        return json.dumps(
            {
                "error": f"No entry matching '{food_name}' found on {log_date}",
                "code": "NOT_FOUND",
                "available_entries": [
                    {"food_name": e["food_name"], "meal_type": e.get("meal_type")}
                    for e in entries
                ],
            },
            ensure_ascii=False,
        )

    if len(matches) > 1:
        return json.dumps(
            {
                "error": "Multiple entries match, specify entry_id or be more precise",
                "code": "AMBIGUOUS",
                "matches": [
                    {
                        "entry_id": m["id"],
                        "food_name": m["food_name"],
                        "quantity": m.get("quantity"),
                        "unit": m.get("unit"),
                        "meal_type": m.get("meal_type"),
                        "calories": m.get("calories"),
                    }
                    for m in matches
                ],
            },
            ensure_ascii=False,
        )

    # Exactly one match — delete it
    entry = matches[0]
    await supabase.table("daily_food_log").delete().eq("id", entry["id"]).execute()

    logger.info(
        f"Deleted entry {entry['id']} ({entry['food_name']}) for user {user_id}"
    )
    return json.dumps(
        {
            "success": True,
            "deleted": {
                "entry_id": entry["id"],
                "food_name": entry["food_name"],
                "quantity": entry.get("quantity"),
                "unit": entry.get("unit"),
                "calories": entry.get("calories"),
                "protein_g": entry.get("protein_g"),
                "carbs_g": entry.get("carbs_g"),
                "fat_g": entry.get("fat_g"),
                "meal_type": entry.get("meal_type"),
            },
        },
        ensure_ascii=False,
    )
