"""
Tool implementations for AI Nutrition Assistant.

This module contains tools that remain in the core package:
- fetch_my_profile: Supabase profile retrieval
- update_my_profile: Supabase profile update
- generate_weekly_meal_plan: Weekly personalized meal planning
- generate_shopping_list: Categorized shopping list from meal plans
- fetch_stored_meal_plan: Retrieve stored meal plan

Migrated to skill scripts (skills/*/scripts/*.py):
- calculate_nutritional_needs → skills/nutrition-calculating/scripts/
- retrieve_relevant_documents → skills/knowledge-searching/scripts/
- web_search → skills/knowledge-searching/scripts/
- image_analysis → skills/body-analyzing/scripts/
- calculate_weekly_adjustments → skills/weekly-coaching/scripts/
"""

from supabase import Client
from openai import AsyncOpenAI
from httpx import AsyncClient
import json
import logging
import tempfile
from datetime import datetime

from src.nutrition.meal_planning import (
    build_meal_plan_prompt_simple,
    format_meal_plan_response,
    MEAL_STRUCTURES,
    extract_ingredients_from_meal_plan,
    aggregate_ingredients,
    categorize_ingredients,
)
from src.nutrition.validators import (
    validate_allergens,
    validate_meal_plan_structure,
    validate_meal_plan_complete,
)
from src.nutrition.meal_distribution import calculate_meal_macros_distribution
from src.nutrition.meal_plan_formatter import format_meal_plan_as_markdown
from src.nutrition.error_logger import log_meal_plan_validation_error
from src.nutrition.macro_adjustments import (
    adjust_meal_plan_macros,
    generate_adjustment_summary,
)
from src.nutrition.meal_plan_optimizer import (
    calculate_meal_plan_macros,
    optimize_meal_plan_portions,
    generate_adjustment_summary as generate_openfoodfacts_adjustment_summary,
)
import os

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


async def generate_weekly_meal_plan_tool(
    supabase: Client,
    openai_client: AsyncOpenAI,
    http_client: AsyncClient,
    start_date: str,
    target_calories_daily: int = None,
    target_protein_g: int = None,
    target_carbs_g: int = None,
    target_fat_g: int = None,
    meal_structure: str = "3_consequent_meals",
    notes: str = None,
) -> str:
    """
    Generate personalized 7-day meal plan with complete recipes and macro optimization.

    Args:
        supabase: Supabase client for database operations
        openai_client: AsyncOpenAI client for GPT-4o meal generation
        http_client: AsyncClient for OpenFoodFacts API validation
        start_date: Start date in YYYY-MM-DD format
        target_calories_daily: Daily calorie target in kcal
        target_protein_g: Daily protein target in grams
        target_carbs_g: Daily carbs target in grams
        target_fat_g: Daily fat target in grams
        meal_structure: Meal distribution pattern
        notes: Additional user constraints

    Returns:
        JSON string with complete meal plan or error
    """
    try:
        logger.info(
            f"Generating weekly meal plan starting {start_date}, structure: {meal_structure}"
        )

        # Step 1: Validate meal structure
        if meal_structure not in MEAL_STRUCTURES:
            return json.dumps(
                {
                    "error": f"Invalid meal structure. Must be one of: {list(MEAL_STRUCTURES.keys())}",
                    "code": "VALIDATION_ERROR",
                }
            )

        # Step 2: Validate date format
        try:
            datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            return json.dumps(
                {
                    "error": "Invalid date format. Use YYYY-MM-DD (e.g., 2024-12-23)",
                    "code": "VALIDATION_ERROR",
                }
            )

        # Step 3: Fetch user profile
        profile_result = await fetch_my_profile_tool(supabase)
        profile_data = json.loads(profile_result)

        if "error" in profile_data:
            return json.dumps(
                {
                    "error": "Cannot generate meal plan: user profile incomplete or not found",
                    "code": "PROFILE_ERROR",
                    "details": profile_data,
                }
            )

        # Step 4: Use provided targets or fetch from profile
        calories = target_calories_daily or profile_data.get("target_calories")
        protein = target_protein_g or profile_data.get("target_protein_g")
        carbs = target_carbs_g or profile_data.get("target_carbs_g")
        fat = target_fat_g or profile_data.get("target_fat_g")

        if not all([calories, protein, carbs, fat]):
            return json.dumps(
                {
                    "error": "Missing nutritional targets. Provide targets or complete profile.",
                    "code": "MISSING_TARGETS",
                }
            )

        # Step 3: Calculate meal-by-meal macro distribution
        logger.info(f"Calculating meal macro distribution for {meal_structure}...")
        meal_macros_distribution = calculate_meal_macros_distribution(
            daily_calories=calories,
            daily_protein_g=protein,
            daily_carbs_g=carbs,
            daily_fat_g=fat,
            meal_structure=meal_structure,
        )
        logger.info(
            f"Meal distribution calculated: {len(meal_macros_distribution['meals'])} meals/day"
        )

        # Step 5: Query RAG for meal planning scientific context
        # Import retrieve_relevant_documents from skill script
        import importlib.util
        from pathlib import Path

        project_root = Path(__file__).resolve().parent.parent
        script_path = (
            project_root
            / "skills"
            / "knowledge-searching"
            / "scripts"
            / "retrieve_relevant_documents.py"
        )
        spec = importlib.util.spec_from_file_location("rag_script", script_path)
        rag_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rag_module)

        rag_query = "meal planning nutrient timing meal frequency protein distribution"
        rag_result = await rag_module.execute(
            supabase=supabase,
            embedding_client=openai_client,
            user_query=rag_query,
        )

        # Step 5.5: Fetch learning profile for personalization
        learning_profile = {}
        try:
            learning_response = (
                supabase.table("user_learning_profile").select("*").limit(1).execute()
            )
            if learning_response.data:
                learning_profile = learning_response.data[0]
                logger.info(
                    f"Learning profile loaded: {learning_profile.get('weeks_of_data', 0)} weeks of data"
                )

                # Extract personalization hints
                personalization_notes = []
                if learning_profile.get("meal_preferences"):
                    loved = learning_profile.get("meal_preferences", {}).get(
                        "loved", []
                    )
                    if loved:
                        personalization_notes.append(f"User loves: {', '.join(loved)}")

                if learning_profile.get("energy_patterns"):
                    energy_patterns = learning_profile.get("energy_patterns", {})
                    if energy_patterns.get("friday_drops"):
                        personalization_notes.append(
                            "User has low energy on Fridays - prioritize carbs + easy meals"
                        )

                if learning_profile.get("adherence_triggers"):
                    triggers = learning_profile.get("adherence_triggers", {})
                    positive = triggers.get("positive", [])
                    if positive:
                        personalization_notes.append(
                            f"High adherence with: {', '.join(positive)}"
                        )

                if learning_profile.get("carb_sensitivity"):
                    personalization_notes.append(
                        f"Carb sensitivity: {learning_profile.get('carb_sensitivity')} - adjust portions accordingly"
                    )

                if personalization_notes and notes:
                    notes = notes + "\n" + "\n".join(personalization_notes)
                elif personalization_notes:
                    notes = "\n".join(personalization_notes)

                logger.info(
                    f"Personalization hints added: {len(personalization_notes)} insights"
                )
        except Exception as e:
            logger.warning(f"Could not load learning profile: {e}")

        # Step 6: Build simplified LLM prompt (focus on creativity, not macro calculation)
        logger.info("Building simplified prompt (~100 lines)...")
        prompt = build_meal_plan_prompt_simple(
            profile=profile_data,
            meal_macros_distribution=meal_macros_distribution,
            rag_context=rag_result,
            start_date=start_date,
        )

        # Get meal planning model from env (defaults to gpt-4o for quality)
        meal_plan_model = os.getenv("MEAL_PLAN_LLM", "gpt-4o")
        logger.info(f"Calling {meal_plan_model} for meal plan generation...")

        # Step 7: Generate meal plan with LLM JSON mode (temperature 0.8 for variety)
        response = await openai_client.chat.completions.create(
            model=meal_plan_model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.8,
            max_tokens=12000,
        )

        meal_plan_json = json.loads(response.choices[0].message.content)

        logger.info("Meal plan generated, validating structure...")

        # Step 8: Validate meal plan structure
        structure_validation = validate_meal_plan_structure(
            meal_plan_json, require_nutrition=False
        )
        if not structure_validation["valid"]:
            logger.error(
                f"Invalid meal plan structure: {structure_validation['missing_fields']}"
            )
            return json.dumps(
                {
                    "error": "Generated meal plan has invalid structure",
                    "code": "STRUCTURE_ERROR",
                    "details": structure_validation,
                }
            )

        # Step 8.5: CRITICAL - Validate 7 days were generated
        days_generated = len(meal_plan_json.get("days", []))
        if days_generated < 7:
            logger.error(
                f"Incomplete meal plan: only {days_generated}/7 days generated"
            )
            return json.dumps(
                {
                    "error": f"Meal plan must have exactly 7 days, but only {days_generated} were generated",
                    "code": "INCOMPLETE_PLAN",
                    "days_generated": days_generated,
                    "instruction": "Please generate ALL 7 days as requested",
                }
            )

        # Step 9: CRITICAL - Validate allergen safety
        user_allergens = profile_data.get("allergies", [])
        allergen_violations = validate_allergens(meal_plan_json, user_allergens)

        if allergen_violations:
            logger.error(f"ALLERGEN VIOLATIONS DETECTED: {allergen_violations}")
            return json.dumps(
                {
                    "error": "Meal plan contains allergens from user profile",
                    "code": "ALLERGEN_VIOLATION",
                    "violations": allergen_violations,
                    "allergens": user_allergens,
                }
            )

        logger.info("Allergen validation passed (zero violations)")

        # Step 10: Calculate precise macros via OpenFoodFacts
        logger.info("Calculating precise macros via OpenFoodFacts...")

        target_macros = {
            "calories": calories,
            "protein_g": protein,
            "carbs_g": carbs,
            "fat_g": fat,
        }

        try:
            meal_plan_with_macros = await calculate_meal_plan_macros(
                meal_plan_json, supabase
            )
            logger.info("Macros calculated via OpenFoodFacts")

            logger.info("Optimizing portions to hit targets...")
            optimized_plan = await optimize_meal_plan_portions(
                meal_plan_with_macros, target_macros, user_allergens
            )
            logger.info("Portions optimized to hit targets")

            adjustment_summary = generate_openfoodfacts_adjustment_summary(
                optimized_plan, target_macros
            )

            if "weekly_summary" not in optimized_plan:
                optimized_plan["weekly_summary"] = {}

            optimized_plan["weekly_summary"]["macro_adjustments"] = adjustment_summary
            meal_plan_json = optimized_plan

        except Exception as e:
            logger.error(f"OpenFoodFacts integration failed: {e}", exc_info=True)
            logger.warning("Falling back to old post-processing system...")
            meal_plan_json = adjust_meal_plan_macros(
                meal_plan_json, target_macros, user_allergens
            )
            adjustment_summary = generate_adjustment_summary(
                meal_plan_json, target_macros
            )
            if "weekly_summary" not in meal_plan_json:
                meal_plan_json["weekly_summary"] = {}
            meal_plan_json["weekly_summary"]["macro_adjustments"] = adjustment_summary

        logger.info("Post-processing complete")

        # Step 8 (Final): Comprehensive 4-level validation with logging
        logger.info("Running comprehensive 4-level validation...")
        user_allergens = profile_data.get("allergies", [])
        validation_result = validate_meal_plan_complete(
            meal_plan=meal_plan_json,
            target_macros=target_macros,
            user_allergens=user_allergens,
            meal_structure=meal_structure,
            protein_tolerance=0.05,
            other_tolerance=0.10,
        )

        if not validation_result["valid"]:
            log_path = log_meal_plan_validation_error(
                validation_result=validation_result,
                meal_plan=meal_plan_json,
                target_macros=target_macros,
                user_allergens=user_allergens,
                meal_structure=meal_structure,
            )
            logger.error(f"Meal plan validation failed. Full error log: {log_path}")

            failed_levels = [
                level
                for level, result in validation_result["validations"].items()
                if not result.get("valid", False)
            ]
            return json.dumps(
                {
                    "error": "Meal plan validation failed",
                    "code": "VALIDATION_FAILED",
                    "log_file": str(log_path),
                    "failed_levels": failed_levels,
                    "details": validation_result["validations"],
                },
                indent=2,
                ensure_ascii=False,
            )

        logger.info("All 4 validation levels passed")

        # Step 11: Store meal plan in database
        meal_plan_record = {
            "week_start": start_date,
            "plan_data": meal_plan_json,
            "target_calories_daily": calories,
            "target_protein_g": protein,
            "target_carbs_g": carbs,
            "target_fat_g": fat,
            "notes": notes,
        }

        db_response = supabase.table("meal_plans").insert(meal_plan_record).execute()

        meal_plan_id = None
        if db_response.data:
            meal_plan_id = db_response.data[0].get("id", 0)
            logger.info(f"Meal plan stored in database (ID: {meal_plan_id})")
            store_success = True
        else:
            logger.warning("Meal plan generated but storage failed")
            store_success = False
            meal_plan_id = 0

        # Generate downloadable Markdown document
        logger.info("Generating downloadable Markdown document...")
        markdown_doc = format_meal_plan_as_markdown(meal_plan_json, meal_plan_id)

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".md",
            delete=False,
            encoding="utf-8",
            prefix=f"meal_plan_{meal_plan_id}_",
        ) as f:
            f.write(markdown_doc)
            markdown_path = f.name

        logger.info(f"Markdown document generated: {markdown_path}")

        # Format and return result with Markdown path
        response_data = json.loads(
            format_meal_plan_response(meal_plan_json, store_success)
        )
        response_data["markdown_document"] = markdown_path
        response_data["meal_plan_id"] = meal_plan_id

        return json.dumps(response_data, indent=2, ensure_ascii=False)

    except json.JSONDecodeError as e:
        logger.error(f"LLM returned invalid JSON: {e}")
        return json.dumps(
            {
                "error": "Failed to parse meal plan from LLM (invalid JSON)",
                "code": "JSON_PARSE_ERROR",
            }
        )
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return json.dumps({"error": str(e), "code": "VALIDATION_ERROR"})
    except Exception as e:
        logger.error(f"Unexpected error generating meal plan: {e}", exc_info=True)
        return json.dumps(
            {"error": "Internal error generating meal plan", "code": "GENERATION_ERROR"}
        )


async def generate_shopping_list_tool(
    supabase: Client,
    week_start: str,
    selected_days: list[int] | None = None,
    servings_multiplier: float = 1.0,
) -> str:
    """
    Generate categorized shopping list from meal plan.

    Args:
        supabase: Supabase client for database operations
        week_start: Meal plan start date in YYYY-MM-DD format
        selected_days: List of day indices to include (0-6), or None for all 7 days
        servings_multiplier: Multiplier for all quantities

    Returns:
        JSON string with categorized shopping list or error
    """
    try:
        logger.info(
            f"Generating shopping list for week {week_start}, days: {selected_days}, multiplier: {servings_multiplier}"
        )

        # Step 1: Validate date format
        try:
            datetime.strptime(week_start, "%Y-%m-%d")
        except ValueError:
            return json.dumps(
                {
                    "error": "Invalid date format. Use YYYY-MM-DD (e.g., 2024-12-23)",
                    "code": "VALIDATION_ERROR",
                }
            )

        # Step 2: Validate servings multiplier
        if servings_multiplier <= 0:
            return json.dumps(
                {
                    "error": "Servings multiplier must be greater than 0",
                    "code": "VALIDATION_ERROR",
                }
            )

        # Step 3: Validate selected_days if provided
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
                        "error": "Day indices must be between 0 and 6",
                        "code": "VALIDATION_ERROR",
                    }
                )

        # Step 4: Fetch meal plan from database
        logger.info(f"Fetching meal plan for week starting {week_start}")
        meal_plan_response = (
            supabase.table("meal_plans")
            .select("*")
            .eq("week_start", week_start)
            .limit(1)
            .execute()
        )

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
                    "error": "Meal plan data is empty or invalid",
                    "code": "INVALID_MEAL_PLAN",
                }
            )

        logger.info(
            f"Meal plan retrieved: {len(plan_data.get('days', []))} days available"
        )

        # Step 5: Extract ingredients from selected days
        ingredients_list = extract_ingredients_from_meal_plan(plan_data, selected_days)

        if not ingredients_list:
            return json.dumps(
                {
                    "error": "No ingredients found in selected days",
                    "code": "NO_INGREDIENTS",
                    "selected_days": selected_days,
                }
            )

        logger.info(f"Extracted {len(ingredients_list)} total ingredients")

        # Step 6: Aggregate ingredients with servings multiplier
        aggregated = aggregate_ingredients(ingredients_list, servings_multiplier)
        logger.info(
            f"Aggregated into {len(aggregated)} unique ingredient+unit combinations"
        )

        # Step 7: Categorize ingredients
        categorized = categorize_ingredients(aggregated)

        # Step 8: Build response with metadata
        days_included = selected_days if selected_days else list(range(7))
        day_names = [
            "Lundi",
            "Mardi",
            "Mercredi",
            "Jeudi",
            "Vendredi",
            "Samedi",
            "Dimanche",
        ]
        days_description = ", ".join([day_names[d] for d in sorted(days_included)])

        # Count total items
        total_items = sum(len(items) for items in categorized.values())

        response = {
            "success": True,
            "shopping_list": categorized,
            "metadata": {
                "week_start": week_start,
                "days_included": days_included,
                "days_description": days_description,
                "servings_multiplier": servings_multiplier,
                "total_items": total_items,
                "categories": {
                    cat: len(items) for cat, items in categorized.items() if items
                },
            },
            "message": f"Shopping list generated for {len(days_included)} days",
        }

        logger.info(
            f"Shopping list generated: {total_items} items across {len([c for c in categorized.values() if c])} categories"
        )
        return json.dumps(response, indent=2, ensure_ascii=False)

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return json.dumps({"error": str(e), "code": "VALIDATION_ERROR"})
    except Exception as e:
        logger.error(f"Unexpected error generating shopping list: {e}", exc_info=True)
        return json.dumps(
            {
                "error": "Internal error generating shopping list",
                "code": "GENERATION_ERROR",
            }
        )


async def fetch_stored_meal_plan_tool(
    supabase: Client,
    week_start: str,
    selected_days: list[int] | None = None,
) -> str:
    """
    Retrieve stored meal plan from database for display.

    Args:
        supabase: Supabase client for database operations
        week_start: Meal plan start date in YYYY-MM-DD format
        selected_days: List of day indices to retrieve (0-6), or None for all

    Returns:
        JSON string with meal plan data or error
    """
    try:
        logger.info(
            f"Fetching stored meal plan for week {week_start}, days: {selected_days}"
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

        # Step 3: Fetch meal plan from database
        logger.info(f"Querying meal_plans table for week_start={week_start}")
        meal_plan_response = (
            supabase.table("meal_plans")
            .select("*")
            .eq("week_start", week_start)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

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
        day_names = [
            "Lundi",
            "Mardi",
            "Mercredi",
            "Jeudi",
            "Vendredi",
            "Samedi",
            "Dimanche",
        ]
        days_description = ", ".join(
            [day_names[d] for d in sorted(selected_days) if d < len(day_names)]
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
            {
                "error": "Internal error fetching meal plan",
                "code": "FETCH_ERROR",
            }
        )
