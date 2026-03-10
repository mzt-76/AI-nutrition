"""Record initial baseline measurements for a new coaching user.

Creates a week_number=0 row in weekly_feedback with the user's starting
weight and optional body composition data. This row is excluded from
trend analysis and adjustment calculations.

Usage:
    run_skill_script("weekly-coaching", "set_baseline", {
        "weight_kg": 87.5,
        "body_fat_percent": 22.0,  # optional
        "muscle_mass_kg": 68.5,    # optional
        ...
    })
"""

import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Validation bounds
MIN_WEIGHT_KG = 40.0
MAX_WEIGHT_KG = 300.0


async def execute(**kwargs) -> str:
    """Record baseline measurements (week_number=0) for a new user.

    Args:
        supabase: Supabase client for database access.
        user_id: Authenticated user ID (required).
        weight_kg: Starting weight in kg (required, 40-300).
        body_fat_percent: Body fat percentage (optional, 3-60).
        muscle_mass_kg: Muscle mass in kg (optional, 10-150).
        water_percent: Body water percentage (optional, 30-80).
        waist_cm: Waist circumference (optional, 40-200).
        hips_cm: Hip circumference (optional, 40-200).
        chest_cm: Chest circumference (optional, 40-200).
        arm_cm: Arm circumference (optional, 15-60).
        thigh_cm: Thigh circumference (optional, 30-100).
        measurement_method: How measured (optional): 'smart_scale', 'manual', 'image_analysis', 'calipers'.

    Returns:
        JSON string with status and stored baseline data.
    """
    supabase = kwargs["supabase"]
    user_id = kwargs.get("user_id")

    if not user_id:
        return json.dumps({"error": "No user_id provided", "code": "NO_USER_ID"})

    weight_kg = kwargs.get("weight_kg")
    if weight_kg is None:
        return json.dumps({"error": "weight_kg is required", "code": "MISSING_WEIGHT"})

    try:
        weight_kg = float(weight_kg)
    except (TypeError, ValueError):
        return json.dumps(
            {"error": "weight_kg must be a number", "code": "INVALID_WEIGHT"}
        )

    if not (MIN_WEIGHT_KG <= weight_kg <= MAX_WEIGHT_KG):
        return json.dumps(
            {
                "error": f"weight_kg must be between {MIN_WEIGHT_KG} and {MAX_WEIGHT_KG}",
                "code": "WEIGHT_OUT_OF_RANGE",
            }
        )

    try:
        today = datetime.now().date()

        # Build baseline row with neutral defaults for required CHECK columns
        baseline_data: dict = {
            "user_id": user_id,
            "week_number": 0,
            "week_start_date": str(today),
            "weight_start_kg": weight_kg,
            "weight_end_kg": weight_kg,
            "adherence_percent": 0,
            "hunger_level": "medium",
            "energy_level": "medium",
            "sleep_quality": "good",
            "cravings": [],
            "subjective_notes": "Baseline measurement — initial check-in",
            "feedback_quality": "adequate",
            "agent_confidence_percent": 100,
            "detected_patterns": {},
            "adjustments_suggested": {},
            "red_flags": {},
        }

        # Optional body composition columns
        body_fields = {
            "body_fat_percent": kwargs.get("body_fat_percent"),
            "muscle_mass_kg": kwargs.get("muscle_mass_kg"),
            "water_percent": kwargs.get("water_percent"),
            "waist_cm": kwargs.get("waist_cm"),
            "hips_cm": kwargs.get("hips_cm"),
            "chest_cm": kwargs.get("chest_cm"),
            "arm_cm": kwargs.get("arm_cm"),
            "thigh_cm": kwargs.get("thigh_cm"),
            "measurement_method": kwargs.get("measurement_method"),
        }

        for field, value in body_fields.items():
            if value is not None:
                baseline_data[field] = value

        # Check if baseline already exists for this user
        existing = await (
            supabase.table("weekly_feedback")
            .select("id")
            .eq("user_id", user_id)
            .eq("week_number", 0)
            .limit(1)
            .execute()
        )

        if existing.data:
            # Update existing baseline
            await supabase.table("weekly_feedback").update(baseline_data).eq(
                "id", existing.data[0]["id"]
            ).execute()
        else:
            # Insert new baseline
            await supabase.table("weekly_feedback").insert(baseline_data).execute()

        logger.info(f"Baseline recorded for user {user_id}: {weight_kg}kg")

        result = {
            "status": "success",
            "message": "Baseline enregistré avec succès",
            "week_number": 0,
            "weight_kg": weight_kg,
            "date": str(today),
        }

        # Include body comp fields that were provided
        body_recorded = {k: v for k, v in body_fields.items() if v is not None}
        if body_recorded:
            result["body_composition"] = body_recorded

        return json.dumps(result, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Error recording baseline: {e}", exc_info=True)
        return json.dumps(
            {"error": "Internal error recording baseline", "code": "BASELINE_ERROR"}
        )
