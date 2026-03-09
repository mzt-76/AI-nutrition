"""Calculate BMR, TDEE, and target macronutrients.

Utility script — can be imported by agent tool wrapper or run standalone.
Uses Mifflin-St Jeor formula for BMR and applies activity multipliers
to determine TDEE. Automatically infers goals from user context and
calculates optimal macro targets.

Source: Extracted from src/tools.py calculate_nutritional_needs_tool
"""

import json
import logging

from src.tools import update_my_profile_tool
from src.nutrition.calculations import (
    mifflin_st_jeor_bmr,
    calculate_tdee,
    infer_goals_from_context,
    calculate_protein_target,
    calculate_macros,
)

logger = logging.getLogger(__name__)


async def execute(**kwargs) -> str:
    """Calculate BMR, TDEE, and target macronutrients with automatic goal inference.

    Args:
        age: Age in years (18-100).
        gender: "male" or "female".
        weight_kg: Body weight in kilograms (40-300 kg).
        height_cm: Height in centimeters (100-250 cm).
        activity_level: sedentary, light, moderate, active, very_active.
        goals: Optional explicit goals dict with weights.
        activities: Optional list of activities for goal inference.
        context: Optional natural language context for goal inference.

    Returns:
        JSON string with complete nutritional profile.
    """
    age = kwargs["age"]
    gender = kwargs["gender"]
    weight_kg = kwargs["weight_kg"]
    height_cm = kwargs["height_cm"]
    activity_level = kwargs["activity_level"]
    goals = kwargs.get("goals")
    activities = kwargs.get("activities")
    context = kwargs.get("context")

    try:
        logger.info(
            f"Calculating nutritional needs: age={age}, gender={gender}, weight={weight_kg}kg"
        )

        # Step 1: Calculate BMR
        bmr = mifflin_st_jeor_bmr(age, gender, weight_kg, height_cm)

        # Step 2: Calculate TDEE
        tdee = calculate_tdee(bmr, activity_level)

        # Step 3: Infer goals
        inferred_goals = infer_goals_from_context(activities, context, goals)

        # Step 4: Determine primary goal
        primary_goal = max(inferred_goals, key=inferred_goals.get)
        if primary_goal == "maintenance" and inferred_goals[primary_goal] == 3:
            # Default to muscle_gain if no clear goal
            primary_goal = "muscle_gain"

        # Step 5: Calculate calorie target
        if primary_goal == "muscle_gain":
            target_calories = tdee + 300  # Moderate surplus
        elif primary_goal == "weight_loss":
            target_calories = tdee - 500  # Moderate deficit
        else:
            target_calories = tdee

        # Step 6: Calculate protein target with adaptive range
        protein_g, protein_per_kg, protein_range = calculate_protein_target(
            weight_kg, primary_goal
        )

        # Step 7: Calculate carbs and fat
        macros = calculate_macros(
            target_calories, protein_g, primary_goal, weight_kg=weight_kg
        )

        # Build result
        result = {
            "bmr": bmr,
            "tdee": tdee,
            "target_calories": target_calories,
            "target_protein_g": protein_g,
            "target_carbs_g": macros["carbs_g"],
            "target_fat_g": macros["fat_g"],
            "protein_per_kg": protein_per_kg,
            "protein_range_g": protein_range,
            "goals_used": inferred_goals,
            "primary_goal": primary_goal,
            "inference_rationale": [],
        }

        # Add rationale
        if activities:
            result["inference_rationale"].append(f"Activities: {', '.join(activities)}")
        if "muscle_gain" in primary_goal:
            result["inference_rationale"].append(
                "Goal: Muscle gain detected → +300 kcal surplus"
            )
        if "weight_loss" in primary_goal:
            result["inference_rationale"].append(
                "Goal: Weight loss detected → -500 kcal deficit"
            )

        logger.info(
            f"Nutrition calculation complete: {target_calories} kcal, {protein_g}g protein"
        )

        # Auto-persist nutrition targets to user profile
        user_id = kwargs.get("user_id")
        supabase = kwargs.get("supabase")
        if user_id and supabase:
            try:
                await update_my_profile_tool(
                    supabase,
                    user_id=user_id,
                    bmr=bmr,
                    tdee=tdee,
                    target_calories=target_calories,
                    target_protein_g=protein_g,
                    target_carbs_g=macros["carbs_g"],
                    target_fat_g=macros["fat_g"],
                )
                logger.info("Nutrition targets auto-persisted to user profile")
            except Exception as e:
                logger.warning(f"Failed to auto-persist nutrition targets: {e}")

        return json.dumps(result, indent=2)

    except ValueError as e:
        logger.error(f"Validation error in nutritional needs calculation: {e}")
        return json.dumps({"error": str(e), "code": "VALIDATION_ERROR"})
    except Exception as e:
        logger.error(
            f"Unexpected error in nutritional needs calculation: {e}", exc_info=True
        )
        return json.dumps(
            {"error": "Internal calculation error", "code": "CALCULATION_ERROR"}
        )
