"""Retrieve a stored meal plan from the database.

Fast retrieval — no regeneration, no LLM, no external APIs.
Single Supabase query, execution time < 500ms.

Source: Refactored from src/tools.py fetch_stored_meal_plan_tool
"""

import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

_DAY_NAMES = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]


async def execute(**kwargs) -> str:
    """Retrieve stored meal plan from database for display.

    Args:
        supabase: Supabase client
        week_start: Meal plan start date in YYYY-MM-DD format
        selected_days: List of day indices to retrieve (0-6), None for all

    Returns:
        JSON with meal plan data:
        {
            "success": true,
            "meal_plan_id": uuid,
            "week_start": "2026-02-18",
            "days_included": [0, 1, 2, ...],
            "daily_targets": {"calories": int, "protein_g": int, ...},
            "days": [...],
            "message": "Plan retrieved for N day(s)"
        }
    """
    supabase = kwargs["supabase"]
    user_id = kwargs.get("user_id", "")
    week_start = kwargs["week_start"]
    selected_days = kwargs.get("selected_days")

    try:
        logger.info(
            f"Fetching stored meal plan: week={week_start}, days={selected_days}"
        )

        # Step 1: Validate date format
        try:
            datetime.strptime(week_start, "%Y-%m-%d")
        except ValueError:
            return json.dumps(
                {
                    "error": "Invalid date format. Use YYYY-MM-DD (e.g., 2025-01-20)",
                    "code": "VALIDATION_ERROR",
                }
            )

        # Step 2: Validate selected_days if provided
        if selected_days is not None:
            if not selected_days:
                return json.dumps(
                    {
                        "error": "selected_days cannot be empty. Use null for all days or provide day indices (0-6)",
                        "code": "VALIDATION_ERROR",
                    }
                )
            if any(day < 0 or day > 6 for day in selected_days):
                return json.dumps(
                    {
                        "error": "Day indices must be between 0 (Lundi) and 6 (Dimanche)",
                        "code": "VALIDATION_ERROR",
                    }
                )

        # Step 3: Fetch most recent plan for the given week
        query = supabase.table("meal_plans").select("*").eq("week_start", week_start)
        if user_id:
            query = query.eq("user_id", user_id)
        meal_plan_response = query.order("created_at", desc=True).limit(1).execute()

        if not meal_plan_response.data:
            return json.dumps(
                {
                    "error": f"No meal plan found for week starting {week_start}",
                    "code": "MEAL_PLAN_NOT_FOUND",
                    "suggestion": "Generate a meal plan first using generate_weekly_meal_plan",
                }
            )

        meal_plan_record = meal_plan_response.data[0]
        plan_data = meal_plan_record.get("plan_data")

        if not plan_data:
            return json.dumps(
                {
                    "error": "Meal plan data is empty or corrupted",
                    "code": "INVALID_MEAL_PLAN",
                }
            )

        # Step 4: Filter days if requested
        all_days = plan_data.get("days", [])

        if not all_days:
            return json.dumps(
                {
                    "error": "Meal plan has no days data",
                    "code": "INVALID_MEAL_PLAN",
                }
            )

        if selected_days is not None:
            filtered_days = [
                day for i, day in enumerate(all_days) if i in selected_days
            ]
        else:
            filtered_days = all_days
            selected_days = list(range(len(all_days)))

        if not filtered_days:
            return json.dumps(
                {
                    "error": f"No days found for indices {selected_days}",
                    "code": "NO_DAYS_FOUND",
                }
            )

        # Step 5: Build response with metadata
        days_description = ", ".join(
            [_DAY_NAMES[d] for d in sorted(selected_days) if d < len(_DAY_NAMES)]
        )

        response = {
            "success": True,
            "meal_plan_id": meal_plan_record.get("id"),
            "week_start": week_start,
            "days_included": sorted(selected_days),
            "days_description": days_description,
            "daily_targets": {
                "calories": meal_plan_record.get("target_calories_daily"),
                "protein_g": meal_plan_record.get("target_protein_g"),
                "carbs_g": meal_plan_record.get("target_carbs_g"),
                "fat_g": meal_plan_record.get("target_fat_g"),
            },
            "days": filtered_days,
            "total_days_in_plan": len(all_days),
            "days_returned": len(filtered_days),
            "message": f"Plan retrieved for {len(filtered_days)} day(s): {days_description}",
        }

        logger.info(
            f"Meal plan retrieved: {len(filtered_days)} days from plan ID {meal_plan_record.get('id')}"
        )
        return json.dumps(response, indent=2, ensure_ascii=False)

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return json.dumps({"error": str(e), "code": "VALIDATION_ERROR"})
    except Exception as e:
        logger.error(f"Unexpected error fetching meal plan: {e}", exc_info=True)
        return json.dumps(
            {"error": "Internal error fetching meal plan", "code": "FETCH_ERROR"}
        )
