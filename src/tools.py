"""
Tool implementations for AI Nutrition Assistant.

This module contains core agent tools that do not belong to a specific skill domain:
- fetch_my_profile_tool: Supabase user profile retrieval
- update_my_profile_tool: Supabase user profile update

Meal-planning tools have been fully migrated to skill scripts:
- generate_weekly_meal_plan → skills/meal-planning/scripts/generate_week_plan.py
- fetch_stored_meal_plan   → skills/meal-planning/scripts/fetch_stored_meal_plan.py
- generate_shopping_list   → skills/shopping-list/scripts/generate_shopping_list.py
- log_food_entries         → skills/food-tracking/scripts/log_food_entries.py

Other skill domains:
- calculate_nutritional_needs → skills/nutrition-calculating/scripts/
- retrieve_relevant_documents → skills/knowledge-searching/scripts/
- web_search                  → skills/knowledge-searching/scripts/
- image_analysis              → skills/body-analyzing/scripts/
- calculate_weekly_adjustments → skills/weekly-coaching/scripts/
"""

import json
import logging
from datetime import datetime, timezone

from supabase._async.client import AsyncClient as SupabaseAsyncClient

logger = logging.getLogger(__name__)


async def fetch_my_profile_tool(
    supabase: SupabaseAsyncClient, user_id: str | None = None
) -> str:
    """
    Fetch user profile from Supabase user_profiles table.

    Args:
        supabase: Supabase client
        user_id: User ID to fetch profile for

    Returns:
        JSON string with profile data or error

    Example:
        >>> profile = await fetch_my_profile_tool(supabase_client, user_id="abc-123")
    """
    try:
        if not user_id:
            logger.warning("No user_id provided — cannot fetch profile")
            return json.dumps(
                {
                    "error": "No user_id provided",
                    "code": "NO_USER_ID",
                    "message": "A user_id is required to fetch a profile. Set NUTRITION_USER_ID env var for CLI usage.",
                }
            )

        logger.info(f"Fetching user profile for user_id={user_id}")
        response = await (
            supabase.table("user_profiles")
            .select("*")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )

        if response.data:
            profile = response.data[0]

            # Check if profile has essential data
            required_fields = [
                "age",
                "gender",
                "weight_kg",
                "height_cm",
                "activity_level",
            ]
            has_data = any(profile.get(field) is not None for field in required_fields)

            if not has_data:
                logger.warning(
                    "Profile exists but is incomplete (missing required fields)"
                )
                return json.dumps(
                    {
                        "error": "Profile incomplete",
                        "code": "PROFILE_INCOMPLETE",
                        "message": "Le profil existe mais n'a pas encore de données. Les champs requis (âge, genre, poids, taille, niveau d'activité) sont vides.",
                        "name": profile.get("name"),
                        "existing_data": {
                            "max_prep_time": profile.get("max_prep_time"),
                            "favorite_foods": profile.get("favorite_foods"),
                            "disliked_foods": profile.get("disliked_foods"),
                            "allergies": profile.get("allergies"),
                        },
                    }
                )

            display_name = profile.get("name") or profile.get("full_name") or "Unknown"
            logger.info(f"Profile loaded: {display_name}")
            return json.dumps(profile, indent=2)
        else:
            logger.warning("No profile found in database")
            return json.dumps(
                {"error": "No profile found", "code": "PROFILE_NOT_FOUND"}
            )

    except Exception as e:
        logger.error(f"Error fetching profile: {e}", exc_info=True)
        return json.dumps({"error": "Database error", "code": "DB_ERROR"})


async def update_my_profile_tool(
    supabase: SupabaseAsyncClient,
    user_id: str | None = None,
    age: int | None = None,
    gender: str | None = None,
    weight_kg: float | None = None,
    height_cm: int | None = None,
    activity_level: str | None = None,
    goals: dict[str, int] | None = None,
    allergies: list[str] | None = None,
    diet_type: str | None = None,
    disliked_foods: list[str] | None = None,
    favorite_foods: list[str] | None = None,
    max_prep_time: int | None = None,
    preferred_cuisines: list[str] | None = None,
    bmr: float | None = None,
    tdee: float | None = None,
    target_calories: float | None = None,
    target_protein_g: float | None = None,
    target_carbs_g: float | None = None,
    target_fat_g: float | None = None,
) -> str:
    """
    Update user profile in Supabase user_profiles table.

    Only updates fields that are provided (not None).
    Automatically updates the updated_at timestamp.

    Args:
        supabase: Supabase client
        user_id: User ID to update profile for
        age: User age in years (18-100)
        gender: "male" or "female"
        weight_kg: Weight in kilograms
        height_cm: Height in centimeters
        activity_level: "sedentary", "light", "moderate", "active", "very_active"
        goals: Dict with goal weights (e.g., {"weight_loss": 7, "muscle_gain": 5})
        allergies: List of allergen foods
        diet_type: "omnivore", "vegetarian", "vegan", "pescatarian", etc.
        disliked_foods: List of foods to avoid
        favorite_foods: List of preferred foods
        max_prep_time: Maximum cooking time in minutes
        preferred_cuisines: List of cuisine types
        bmr: Basal Metabolic Rate in kcal (calculated)
        tdee: Total Daily Energy Expenditure in kcal (calculated)
        target_calories: Daily calorie target in kcal
        target_protein_g: Daily protein target in grams
        target_carbs_g: Daily carbohydrate target in grams
        target_fat_g: Daily fat target in grams

    Returns:
        JSON string with updated profile or error

    Example:
        >>> result = await update_my_profile_tool(
        ...     supabase_client,
        ...     age=23,
        ...     gender="male",
        ...     weight_kg=86.0,
        ...     height_cm=191,
        ...     activity_level="sedentary"
        ... )
    """
    PROTECTED_FIELDS = {"is_admin", "id", "email", "created_at"}

    try:
        logger.info("Updating user profile in database")

        # Build update dict with only provided fields
        update_data = {}

        if age is not None:
            if not 18 <= age <= 100:
                return json.dumps(
                    {
                        "error": "Age must be between 18 and 100",
                        "code": "VALIDATION_ERROR",
                    }
                )
            update_data["age"] = age

        if gender is not None:
            gender_normalized = gender.lower()
            if gender_normalized in ["male", "homme", "m", "masculin"]:
                update_data["gender"] = "male"
            elif gender_normalized in ["female", "femme", "f", "féminin"]:
                update_data["gender"] = "female"
            else:
                return json.dumps(
                    {
                        "error": "Gender must be 'male' or 'female'",
                        "code": "VALIDATION_ERROR",
                    }
                )

        if weight_kg is not None:
            if weight_kg < 40 or weight_kg > 300:
                return json.dumps(
                    {
                        "error": "Weight must be between 40 and 300 kg",
                        "code": "VALIDATION_ERROR",
                    }
                )
            update_data["weight_kg"] = weight_kg

        if height_cm is not None:
            if height_cm < 100 or height_cm > 250:
                return json.dumps(
                    {
                        "error": "Height must be between 100 and 250 cm",
                        "code": "VALIDATION_ERROR",
                    }
                )
            update_data["height_cm"] = height_cm

        if activity_level is not None:
            valid_levels = ["sedentary", "light", "moderate", "active", "very_active"]
            # Normalize French to English
            level_map = {
                "sédentaire": "sedentary",
                "léger": "light",
                "modéré": "moderate",
                "actif": "active",
                "très actif": "very_active",
            }
            normalized_level = level_map.get(
                activity_level.lower(), activity_level.lower()
            )
            if normalized_level not in valid_levels:
                return json.dumps(
                    {
                        "error": f"Activity level must be one of: {valid_levels}",
                        "code": "VALIDATION_ERROR",
                    }
                )
            update_data["activity_level"] = normalized_level

        if goals is not None:
            update_data["goals"] = goals

        if allergies is not None:
            update_data["allergies"] = allergies

        if diet_type is not None:
            update_data["diet_type"] = diet_type

        if disliked_foods is not None:
            update_data["disliked_foods"] = disliked_foods

        if favorite_foods is not None:
            update_data["favorite_foods"] = favorite_foods

        if max_prep_time is not None:
            update_data["max_prep_time"] = max_prep_time

        if preferred_cuisines is not None:
            update_data["preferred_cuisines"] = preferred_cuisines

        if bmr is not None:
            update_data["bmr"] = bmr

        if tdee is not None:
            update_data["tdee"] = tdee

        if target_calories is not None:
            update_data["target_calories"] = target_calories

        if target_protein_g is not None:
            update_data["target_protein_g"] = target_protein_g

        if target_carbs_g is not None:
            update_data["target_carbs_g"] = target_carbs_g

        if target_fat_g is not None:
            update_data["target_fat_g"] = target_fat_g

        if not update_data:
            return json.dumps(
                {"error": "No data provided to update", "code": "NO_DATA"}
            )

        # Strip any protected fields that should never be modified via this tool
        for field in PROTECTED_FIELDS:
            update_data.pop(field, None)

        # Always update the timestamp
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()

        if not user_id:
            return json.dumps(
                {
                    "error": "No user_id provided",
                    "code": "NO_USER_ID",
                    "message": "A user_id is required to update a profile. Set NUTRITION_USER_ID env var for CLI usage.",
                }
            )

        response = await (
            supabase.table("user_profiles")
            .update(update_data)
            .eq("id", user_id)
            .execute()
        )
        logger.info(f"Profile updated (user_profiles): {len(update_data)} fields")

        if response.data:
            return json.dumps(
                {
                    "success": True,
                    "message": "Profile mis à jour avec succès",
                    "updated_fields": list(update_data.keys()),
                    "profile": response.data[0],
                },
                indent=2,
            )
        else:
            return json.dumps({"error": "Update failed", "code": "UPDATE_FAILED"})

    except Exception as e:
        logger.error(f"Error updating profile: {e}", exc_info=True)
        return json.dumps({"error": "Erreur base de donnees", "code": "DB_ERROR"})
