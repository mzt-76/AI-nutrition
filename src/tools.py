"""
Tool implementations for AI Nutrition Assistant.

This module contains core agent tools that do not belong to a specific skill domain:
- fetch_my_profile_tool: Supabase user profile retrieval
- update_my_profile_tool: Supabase user profile update

Meal-planning tools have been fully migrated to skill scripts:
- generate_weekly_meal_plan → skills/meal-planning/scripts/generate_week_plan.py
- generate_shopping_list   → skills/meal-planning/scripts/generate_shopping_list.py
- fetch_stored_meal_plan   → skills/meal-planning/scripts/fetch_stored_meal_plan.py

Other skill domains:
- calculate_nutritional_needs → skills/nutrition-calculating/scripts/
- retrieve_relevant_documents → skills/knowledge-searching/scripts/
- web_search                  → skills/knowledge-searching/scripts/
- image_analysis              → skills/body-analyzing/scripts/
- calculate_weekly_adjustments → skills/weekly-coaching/scripts/
"""

import json
import logging

from supabase import Client

logger = logging.getLogger(__name__)


async def fetch_my_profile_tool(supabase: Client) -> str:
    """
    Fetch user profile from Supabase my_profile table.

    Args:
        supabase: Supabase client

    Returns:
        JSON string with profile data or error

    Example:
        >>> profile = await fetch_my_profile_tool(supabase_client)
    """
    try:
        logger.info("Fetching user profile from database")

        response = supabase.table("my_profile").select("*").limit(1).execute()

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

            logger.info(f"Profile loaded: {profile.get('name', 'Unknown')}")
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
    supabase: Client,
    age: int = None,
    gender: str = None,
    weight_kg: float = None,
    height_cm: int = None,
    activity_level: str = None,
    goals: dict = None,
    allergies: list[str] = None,
    diet_type: str = None,
    disliked_foods: list[str] = None,
    favorite_foods: list[str] = None,
    max_prep_time: int = None,
    preferred_cuisines: list[str] = None,
) -> str:
    """
    Update user profile in Supabase my_profile table.

    Only updates fields that are provided (not None).
    Automatically updates the updated_at timestamp.

    Args:
        supabase: Supabase client
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

        if not update_data:
            return json.dumps(
                {"error": "No data provided to update", "code": "NO_DATA"}
            )

        # Always update the timestamp
        update_data["updated_at"] = "now()"

        # Check if profile exists
        check_response = supabase.table("my_profile").select("id").limit(1).execute()

        if check_response.data:
            # Update existing profile
            profile_id = check_response.data[0]["id"]
            response = (
                supabase.table("my_profile")
                .update(update_data)
                .eq("id", profile_id)
                .execute()
            )
            logger.info(f"Profile updated: {len(update_data)} fields")
        else:
            # Create new profile
            response = supabase.table("my_profile").insert(update_data).execute()
            logger.info("New profile created")

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
        return json.dumps({"error": f"Database error: {str(e)}", "code": "DB_ERROR"})


