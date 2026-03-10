"""Return today's consumed macros vs targets for a user.

Read-only script — queries daily_food_log and user_profiles to build
a consumed/remaining summary the agent can use to answer questions like
"combien il me reste ?" or suggest foods to fill the gap.
"""

import json
import logging
from datetime import date

logger = logging.getLogger(__name__)


async def execute(**kwargs) -> str:
    """Get daily macro summary (consumed vs targets).

    Args (via kwargs):
        supabase: Supabase client
        user_id: User UUID
        log_date: str (YYYY-MM-DD), defaults to today

    Returns:
        JSON with targets, consumed, remaining, entries_count, meals_logged
    """
    supabase = kwargs["supabase"]
    user_id = kwargs["user_id"]
    log_date = kwargs.get("log_date") or kwargs.get("date") or date.today().isoformat()

    if not user_id:
        return json.dumps({"error": "No user_id provided", "code": "NO_USER"})

    try:
        # 1. Fetch user targets
        profile_resp = await (
            supabase.table("user_profiles")
            .select("target_calories, target_protein_g, target_carbs_g, target_fat_g")
            .eq("id", user_id)
            .execute()
        )
        if not profile_resp.data:
            return json.dumps({"error": "No profile found", "code": "NO_PROFILE"})
        profile = profile_resp.data[0]

        targets = {
            "calories": profile.get("target_calories") or 0,
            "protein_g": profile.get("target_protein_g") or 0,
            "carbs_g": profile.get("target_carbs_g") or 0,
            "fat_g": profile.get("target_fat_g") or 0,
        }

        # If no targets have been calculated yet, tell the agent to redirect
        if all(v == 0 for v in targets.values()):
            return json.dumps(
                {
                    "error": "Aucune cible nutritionnelle configuree. "
                    "Calcule d'abord les besoins avec nutrition-calculating.",
                    "code": "NO_TARGETS",
                }
            )

        # 2. Fetch all log entries for the date
        log_resp = await (
            supabase.table("daily_food_log")
            .select("calories, protein_g, carbs_g, fat_g, meal_type")
            .eq("user_id", user_id)
            .eq("log_date", log_date)
            .execute()
        )
        entries = log_resp.data or []

        # 3. Sum consumed macros
        consumed = {"calories": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0}
        meals_seen: set[str] = set()
        for entry in entries:
            consumed["calories"] += entry.get("calories") or 0
            consumed["protein_g"] += entry.get("protein_g") or 0
            consumed["carbs_g"] += entry.get("carbs_g") or 0
            consumed["fat_g"] += entry.get("fat_g") or 0
            meal = entry.get("meal_type")
            if meal:
                meals_seen.add(meal)

        # Round consumed values
        consumed = {k: round(v, 1) for k, v in consumed.items()}

        # 4. Calculate remaining
        remaining = {
            "calories": round(targets["calories"] - consumed["calories"], 1),
            "protein_g": round(targets["protein_g"] - consumed["protein_g"], 1),
            "carbs_g": round(targets["carbs_g"] - consumed["carbs_g"], 1),
            "fat_g": round(targets["fat_g"] - consumed["fat_g"], 1),
        }

        logger.info(
            f"Daily summary for user {user_id} on {log_date}: "
            f"{consumed['calories']}/{targets['calories']} kcal, "
            f"{len(entries)} entries"
        )

        return json.dumps(
            {
                "log_date": log_date,
                "targets": targets,
                "consumed": consumed,
                "remaining": remaining,
                "entries_count": len(entries),
                "meals_logged": sorted(meals_seen),
            },
            ensure_ascii=False,
        )

    except Exception as e:
        logger.error(f"Error fetching daily summary: {e}", exc_info=True)
        return json.dumps(
            {"error": "Failed to fetch daily summary", "code": "SCRIPT_ERROR"}
        )
