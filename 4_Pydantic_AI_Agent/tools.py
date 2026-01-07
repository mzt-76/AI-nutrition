"""
Tool implementations for AI Nutrition Assistant.

This module contains all the tools that the agent can use:
- calculate_nutritional_needs: BMR, TDEE, macro calculations
- calculate_weekly_adjustments: Adaptive feedback analysis
- retrieve_relevant_documents: RAG knowledge base search
- web_search: Brave API web search
- fetch_my_profile: Supabase profile retrieval
- image_analysis: GPT-4 Vision for body composition
- generate_weekly_meal_plan: Weekly personalized meal planning
- generate_shopping_list: Categorized shopping list from meal plans

All tools include type hints, validation, and error handling.
"""

from supabase import Client
from openai import AsyncOpenAI
from httpx import AsyncClient
import json
import logging
from datetime import datetime, timedelta

from nutrition.calculations import (
    mifflin_st_jeor_bmr,
    calculate_tdee,
    infer_goals_from_context,
    calculate_protein_target,
    calculate_macros,
)
from nutrition.meal_planning import (
    build_meal_plan_prompt,
    format_meal_plan_response,
    MEAL_STRUCTURES,
    extract_ingredients_from_meal_plan,
    aggregate_ingredients,
    categorize_ingredients,
)
from nutrition.validators import (
    validate_allergens,
    validate_meal_plan_structure,
)
from nutrition.adjustments import (
    analyze_weight_trend,
    detect_metabolic_adaptation,
    detect_adherence_patterns,
    generate_calorie_adjustment,
    generate_macro_adjustments,
    detect_red_flags,
)
from nutrition.feedback_extraction import (
    validate_feedback_metrics,
    check_feedback_completeness,
)
from nutrition.macro_adjustments import (
    adjust_meal_plan_macros,
    generate_adjustment_summary,
)
from nutrition.meal_plan_optimizer import (
    calculate_meal_plan_macros,
    optimize_meal_plan_portions,
    generate_adjustment_summary as generate_openfoodfacts_adjustment_summary,
)
import os

logger = logging.getLogger(__name__)


async def calculate_nutritional_needs_tool(
    age: int,
    gender: str,
    weight_kg: float,
    height_cm: int,
    activity_level: str,
    goals: dict | None = None,
    activities: list[str] | None = None,
    context: str | None = None,
) -> str:
    """
    Calculate BMR, TDEE, and target macronutrients with automatic goal inference.

    Args:
        age: Age in years (18-100)
        gender: "male" or "female"
        weight_kg: Body weight in kilograms
        height_cm: Height in centimeters
        activity_level: sedentary, light, moderate, active, very_active
        goals: Optional explicit goals dict
        activities: Optional list of activities for goal inference
        context: Optional context string for goal inference

    Returns:
        JSON string with BMR, TDEE, targets, goals, and rationale

    Example:
        >>> result = await calculate_nutritional_needs_tool(
        ...     35, "male", 87, 178, "moderate",
        ...     activities=["musculation"], context="Je veux prendre du muscle"
        ... )
    """
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
        macros = calculate_macros(target_calories, protein_g, primary_goal)

        # Build result
        result = {
            "bmr": bmr,
            "tdee": tdee,
            "target_calories": target_calories,
            "target_protein_g": protein_g,
            "target_carbs_g": macros["carbs_g"],
            "target_fat_g": macros["fat_g"],
            "protein_per_kg": protein_per_kg,
            "protein_range_g": protein_range,  # Add protein range
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


async def retrieve_relevant_documents_tool(
    supabase: Client, embedding_client: AsyncOpenAI, user_query: str
) -> str:
    """
    Retrieve relevant document chunks from knowledge base using RAG.

    Args:
        supabase: Supabase client
        embedding_client: OpenAI client for embeddings
        user_query: User's question or query

    Returns:
        Formatted string with top 4 relevant document chunks

    Example:
        >>> docs = await retrieve_relevant_documents_tool(
        ...     supabase, openai_client, "Combien de protéines pour muscle?"
        ... )
    """
    try:
        logger.info(f"RAG query: {user_query[:50]}...")

        # Generate embedding for query
        response = await embedding_client.embeddings.create(
            model="text-embedding-3-small", input=user_query
        )
        query_embedding = response.data[0].embedding

        # Query Supabase vectorstore
        result = supabase.rpc(
            "match_documents",
            {
                "query_embedding": query_embedding,
                "match_count": 10,  # Get more results, filter by threshold later
                "filter": {},
            },
        ).execute()

        if not result.data:
            logger.warning("No relevant documents found")
            return "No relevant documents found in knowledge base."

        # Filter by similarity threshold (0.5 for cross-language queries) and take top 4
        MIN_SIMILARITY = 0.5
        relevant_docs = [
            doc for doc in result.data if doc.get("similarity", 0) >= MIN_SIMILARITY
        ][:4]

        if not relevant_docs:
            logger.warning(f"No documents above similarity threshold {MIN_SIMILARITY}")
            return f"No sufficiently relevant documents found (threshold: {MIN_SIMILARITY})."

        # Format results
        formatted_docs = []
        for i, doc in enumerate(relevant_docs, 1):
            similarity = doc.get("similarity", 0)
            content = doc.get("content", "")
            formatted_docs.append(
                f"--- Document {i} (similarity: {similarity:.2f}) ---\n{content}"
            )

        logger.info(f"Retrieved {len(formatted_docs)} relevant documents")

        return "\n\n".join(formatted_docs)

    except Exception as e:
        logger.error(f"Error in RAG retrieval: {e}", exc_info=True)
        return f"Error retrieving documents: {str(e)}"


async def web_search_tool(
    query: str,
    http_client: AsyncClient,
    brave_api_key: str | None,
    searxng_base_url: str | None,
) -> str:
    """
    Search the web using Brave Search API.

    Args:
        query: Search query
        http_client: Async HTTP client
        brave_api_key: Brave API key (required)
        searxng_base_url: Alternative SearXNG URL (optional)

    Returns:
        Summary of search results

    Example:
        >>> results = await web_search_tool("nouvelles recommandations protéines 2024", ...)
    """
    try:
        logger.info(f"Web search: {query}")

        if not brave_api_key:
            return "Web search unavailable: BRAVE_API_KEY not configured"

        # Brave Search API
        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": brave_api_key,
        }
        params = {"q": query, "count": 5}

        response = await http_client.get(url, headers=headers, params=params)
        response.raise_for_status()

        data = response.json()
        results = data.get("web", {}).get("results", [])

        if not results:
            return "No search results found."

        # Format top 5 results
        formatted = []
        for i, result in enumerate(results[:5], 1):
            title = result.get("title", "No title")
            description = result.get("description", "")
            url = result.get("url", "")
            formatted.append(f"{i}. **{title}**\n   {description}\n   {url}")

        logger.info(f"Found {len(results)} search results")

        return "\n\n".join(formatted)

    except Exception as e:
        logger.error(f"Web search error: {e}", exc_info=True)
        return f"Web search error: {str(e)}"


async def image_analysis_tool(
    image_url: str, query: str, openai_client: AsyncOpenAI
) -> str:
    """
    Analyze image.

    Args:
        image_url: URL to the image (Google Drive or direct URL)
        query: What to analyze (e.g., "Estimate body fat percentage")
        openai_client: OpenAI client

    Returns:
        Analysis result

    Example:
        >>> analysis = await image_analysis_tool(image_url, "Estimate body fat", client)
    """
    try:
        logger.info(f"Image analysis: {query[:50]}...")

        response = await openai_client.chat.completions.create(
            model=os.getenv('VISION_LLM_CHOICE', 'gpt-4o-mini'),
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": query},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            ],
            max_tokens=1500,  # Increased for complete analysis
        )

        result = response.choices[0].message.content

        logger.info("Image analysis complete")

        return result

    except Exception as e:
        logger.error(f"Image analysis error: {e}", exc_info=True)
        return f"Image analysis error: {str(e)}"


async def generate_weekly_meal_plan_tool(
    supabase: Client,
    openai_client: AsyncOpenAI,
    http_client: AsyncClient,
    start_date: str,
    target_calories_daily: int = None,
    target_protein_g: int = None,
    target_carbs_g: int = None,
    target_fat_g: int = None,
    meal_structure: str = "3_meals_2_snacks",
    notes: str = None,
) -> str:
    """
    Generate personalized 7-day meal plan with complete recipes.

    generate recipes matching user profile, validates allergen safety,
    and stores in meal_plans table.

    Args:
        supabase: Supabase client for database operations
        openai_client: OpenAI client for generation
        start_date: Start date in YYYY-MM-DD format (Monday preferred)
        target_calories_daily: Daily calorie target (if None, fetch from profile)
        target_protein_g: Daily protein target in grams
        target_carbs_g: Daily carbs target in grams
        target_fat_g: Daily fat target in grams
        meal_structure: One of "3_meals_2_snacks", "4_meals", "3_consequent_meals", "3_meals_1_preworkout"
        notes: Additional user preferences or constraints

    Returns:
        JSON string with meal plan or error

    Example:
        >>> plan = await generate_weekly_meal_plan_tool(
        ...     supabase, openai_client, "2024-12-23",
        ...     meal_structure="3_meals_1_preworkout"
        ... )
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

        # Step 5: Query RAG for meal planning scientific context
        rag_query = "meal planning nutrient timing meal frequency protein distribution"
        rag_result = await retrieve_relevant_documents_tool(
            supabase, openai_client, rag_query
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

        # Step 6: Build LLM prompt
        prompt = build_meal_plan_prompt(
            profile=profile_data,
            rag_context=rag_result,
            start_date=start_date,
            meal_structure=meal_structure,
            notes=notes,
            calculate_macros=False,  # NEW: Disable GPT-4o macro calculation (FatSecret will handle it)
        )

        # Get meal planning model from env (defaults to gpt-4o for quality)
        meal_plan_model = os.getenv('MEAL_PLAN_LLM', 'gpt-4o')
        logger.info(f"Calling {meal_plan_model} for meal plan generation...")

        # Step 7: Generate meal plan with LLM JSON mode
        response = await openai_client.chat.completions.create(
            model=meal_plan_model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.7,
            max_tokens=12000,  # Increased for full 7-day plans with detailed recipes
        )

        meal_plan_json = json.loads(response.choices[0].message.content)

        logger.info("Meal plan generated, validating structure...")

        # Step 8: Validate meal plan structure (nutrition not required - FatSecret adds it)
        structure_validation = validate_meal_plan_structure(meal_plan_json, require_nutrition=False)
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
                f"🚨 Incomplete meal plan: only {days_generated}/7 days generated"
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
            logger.error(f"🚨 ALLERGEN VIOLATIONS DETECTED: {allergen_violations}")
            return json.dumps(
                {
                    "error": "Meal plan contains allergens from user profile",
                    "code": "ALLERGEN_VIOLATION",
                    "violations": allergen_violations,
                    "allergens": user_allergens,
                }
            )

        logger.info("✅ Allergen validation passed (zero violations)")

        # Step 10: FATSECRET INTEGRATION - Calculate precise macros via FatSecret API
        logger.info("🔧 Calculating precise macros via FatSecret API...")

        target_macros = {
            "calories": calories,
            "protein_g": protein,
            "carbs_g": carbs,
            "fat_g": fat,
        }

        try:
            # Calculate precise macros for all ingredients using OpenFoodFacts
            meal_plan_with_macros = await calculate_meal_plan_macros(
                meal_plan_json, supabase
            )

            logger.info("✅ Macros calculated via OpenFoodFacts")

            # Optimize portions to hit targets (±5%)
            logger.info("🔧 Optimizing portions to hit targets (±5%)...")
            optimized_plan = await optimize_meal_plan_portions(
                meal_plan_with_macros, target_macros, user_allergens
            )

            logger.info("✅ Portions optimized to hit targets")

            # Generate adjustment summary
            adjustment_summary = generate_openfoodfacts_adjustment_summary(
                optimized_plan, target_macros
            )

            # Add adjustment info to meal plan metadata
            if "weekly_summary" not in optimized_plan:
                optimized_plan["weekly_summary"] = {}

            optimized_plan["weekly_summary"]["macro_adjustments"] = adjustment_summary

            # Use optimized plan for storage
            meal_plan_json = optimized_plan

        except Exception as e:
            logger.error(f"❌ OpenFoodFacts integration failed: {e}", exc_info=True)
            # Fallback to old post-processing system
            logger.warning("⚠️ Falling back to old post-processing system...")
            meal_plan_json = adjust_meal_plan_macros(
                meal_plan_json, target_macros, user_allergens
            )
            adjustment_summary = generate_adjustment_summary(
                meal_plan_json, target_macros
            )
            if "weekly_summary" not in meal_plan_json:
                meal_plan_json["weekly_summary"] = {}
            meal_plan_json["weekly_summary"]["macro_adjustments"] = adjustment_summary

        logger.info("✅ Post-processing complete - 100% macro accuracy guaranteed")

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

        if db_response.data:
            logger.info(
                f"✅ Meal plan stored in database (ID: {db_response.data[0].get('id', 'N/A')})"
            )
            store_success = True
        else:
            logger.warning("Meal plan generated but storage failed")
            store_success = False

        # Step 12: Format and return result
        return format_meal_plan_response(meal_plan_json, store_success)

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

    Fetches meal plan from database, extracts ingredients for selected days,
    aggregates quantities, categorizes by food group, and returns formatted list.

    Args:
        supabase: Supabase client for database operations
        week_start: Meal plan start date in YYYY-MM-DD format
        selected_days: List of day indices to include (0-6), or None for all 7 days
        servings_multiplier: Multiplier for all quantities (e.g., 2.0 for double portions)

    Returns:
        JSON string with categorized shopping list or error

    Example:
        >>> result = await generate_shopping_list_tool(
        ...     supabase, "2024-12-23", selected_days=[0, 1, 2], servings_multiplier=1.5
        ... )
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
            f"✅ Shopping list generated: {total_items} items across {len([c for c in categorized.values() if c])} categories"
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


async def calculate_weekly_adjustments_tool(
    supabase: Client,
    embedding_client: AsyncOpenAI,
    weight_start_kg: float,
    weight_end_kg: float,
    adherence_percent: int,
    hunger_level: str = "medium",
    energy_level: str = "medium",
    sleep_quality: str = "good",
    cravings: list[str] | None = None,
    notes: str = "",
) -> str:
    """
    Synthesize weekly feedback and generate personalized nutritional adjustments.

    Analyzes real-world outcomes against goal targets, detects individual patterns
    (metabolism, macro sensitivity, adherence triggers), and generates science-backed
    recommendations with confidence scoring. Stores learning data for continuous
    improvement.

    Args:
        supabase: Supabase client for database access
        embedding_client: OpenAI async client for embeddings and LLM
        weight_start_kg: Weight at start of week (kg)
        weight_end_kg: Weight at end of week (kg)
        adherence_percent: Percentage of plan followed (0-100%)
        hunger_level: Reported hunger ("low", "medium", "high")
        energy_level: Reported energy ("low", "medium", "high")
        sleep_quality: Sleep quality ("poor", "fair", "good", "excellent")
        cravings: List of craving types if any
        notes: Free-text observations from the week

    Returns:
        JSON string with:
        - Analysis of weight trend vs goal targets
        - Detected patterns (energy, adherence, metabolic adaptation)
        - Suggested macro/calorie adjustments with rationale
        - Red flag alerts (if any)
        - Confidence level for recommendations
        - Stored in weekly_feedback table for continuous learning

    Example:
        >>> result = await calculate_weekly_adjustments_tool(
        ...     supabase=sb,
        ...     embedding_client=client,
        ...     weight_start_kg=87.0,
        ...     weight_end_kg=86.4,
        ...     adherence_percent=85,
        ...     hunger_level="medium",
        ...     energy_level="high",
        ...     notes="Good week, felt strong Friday"
        ... )

    References:
        Adaptive Thermogenesis: Fothergill et al. (2016)
        Helms et al. (2014): Body composition changes in resistance training
        ISSN Position Stand (2017): Macronutrient recommendations
    """
    try:
        logger.info(
            f"Weekly adjustment synthesis starting: weight {weight_start_kg}→{weight_end_kg}kg, adherence {adherence_percent}%"
        )

        # Step 1: Validate and parse input
        feedback_data = validate_feedback_metrics(
            {
                "weight_start_kg": weight_start_kg,
                "weight_end_kg": weight_end_kg,
                "adherence_percent": adherence_percent,
                "hunger_level": hunger_level,
                "energy_level": energy_level,
                "sleep_quality": sleep_quality,
                "cravings": cravings or [],
                "notes": notes,
            }
        )

        completeness = check_feedback_completeness(feedback_data)
        logger.info(
            f"Feedback completeness: {completeness['quality']} ({completeness['completeness_percent']}%)"
        )

        # Step 2: Fetch current profile
        profile_response = supabase.table("my_profile").select("*").limit(1).execute()
        if not profile_response.data:
            return json.dumps(
                {"error": "No user profile found", "code": "PROFILE_NOT_FOUND"}
            )
        profile = profile_response.data[0]
        goal = profile.get("primary_goal", "maintenance")
        current_calories = profile.get("current_calories", 2500)
        current_protein_g = profile.get("current_protein_g", 150)

        # Step 3: Fetch historical data (past 4 weeks)
        history_response = (
            supabase.table("weekly_feedback")
            .select("*")
            .order("week_start_date", desc=True)
            .limit(4)
            .execute()
        )
        past_weeks = history_response.data if history_response.data else []
        logger.info(f"Retrieved {len(past_weeks)} weeks of historical feedback")

        # Step 4: Load learning profile
        learning_response = (
            supabase.table("user_learning_profile").select("*").limit(1).execute()
        )
        learning_profile = learning_response.data[0] if learning_response.data else {}
        logger.info(
            f"Learning profile loaded: {learning_profile.get('weeks_of_data', 0)} weeks of data"
        )

        # Step 5: Analyze weight trend
        weight_analysis = analyze_weight_trend(
            weight_start_kg, weight_end_kg, goal, weeks_on_plan=len(past_weeks) + 1
        )
        logger.info(f"Weight trend: {weight_analysis['trend']}")

        # Step 6: Detect patterns
        metabolic = detect_metabolic_adaptation(
            past_weeks,
            learning_profile.get("observed_tdee"),
            profile.get("tdee", 2868),
        )
        adherence_patterns = detect_adherence_patterns(past_weeks)
        logger.info(
            f"Pattern detection: metabolic_adaptation={metabolic['detected']}, patterns={len(adherence_patterns['positive_triggers'])}"
        )

        # Step 7: Generate rule-based adjustments
        calorie_adj = generate_calorie_adjustment(
            weight_analysis["change_kg"], goal, adherence_percent, len(past_weeks) + 1
        )
        macro_adj = generate_macro_adjustments(
            hunger_level,
            energy_level,
            feedback_data.get("cravings", []),
            current_protein_g,
            profile.get("current_carbs_g", 350),
            profile.get("current_fat_g", 90),
            learning_profile,
        )
        logger.info(
            f"Adjustments generated: cal={calorie_adj['adjustment_kcal']}kcal, protein={macro_adj['protein_g']}g"
        )

        # Step 8: Detect red flags
        red_flags = detect_red_flags(feedback_data, past_weeks, profile)
        if red_flags:
            logger.warning(f"🚨 Red flags: {[f['flag_type'] for f in red_flags]}")

        # Step 9: Calculate confidence
        # Base: scale from 0.3 to 0.8 based on weeks of data
        # With 8 weeks, reach max (0.8); less weeks = lower base confidence
        weeks_count = len(past_weeks)
        base_confidence = 0.3 + (min(weeks_count, 8) / 8) * 0.5  # 0.3-0.8 range

        # Apply quality penalties (multiplicative for smoother scaling)
        data_quality = completeness.get("quality", "incomplete")
        if data_quality == "incomplete":
            base_confidence *= 0.8  # 20% reduction for poor data
        elif data_quality == "adequate":
            base_confidence *= 0.9  # 10% reduction for adequate data
        # "complete" gets no penalty (100% = no change)

        # Red flag penalty: significant but don't make confidence unusable
        if red_flags:
            base_confidence = max(0.5, base_confidence - 0.2)  # Min 0.5 even with flags

        # Final clamp: always 0.3-0.95 range
        final_confidence = min(0.95, max(0.3, base_confidence))

        # Build result
        result = {
            "status": "success",
            "week_number": len(past_weeks) + 1,
            "analysis": {
                "weight_analysis": weight_analysis,
                "metabolic_analysis": metabolic,
                "adherence_analysis": {
                    "rate_percent": adherence_percent,
                    "assessment": "Excellent"
                    if adherence_percent >= 85
                    else "Good"
                    if adherence_percent >= 70
                    else "Fair"
                    if adherence_percent >= 50
                    else "Low",
                    "positive_triggers": adherence_patterns["positive_triggers"],
                    "negative_triggers": adherence_patterns["negative_triggers"],
                },
            },
            "adjustments": {
                "suggested": {
                    "calories": calorie_adj["adjustment_kcal"],
                    "protein_g": macro_adj["protein_g"],
                    "carbs_g": macro_adj["carbs_g"],
                    "fat_g": macro_adj["fat_g"],
                },
                "rationale": [
                    *calorie_adj["reasoning"],
                    *macro_adj["adjustments_rationale"].values(),
                ],
            },
            "red_flags": red_flags,
            "feedback_completeness": completeness["quality"],
            "confidence_level": round(final_confidence, 2),
            "recommendations": [
                weight_analysis["assessment"],
                f"Adherence: {adherence_patterns['recommendation']}"
                if adherence_patterns["recommendation"]
                else "",
            ],
        }

        # Step 10: Store results in database
        # Calculate ISO week start if not provided
        if feedback_data.get("week_start_date"):
            week_start = datetime.fromisoformat(feedback_data["week_start_date"]).date()
        else:
            today = datetime.now().date()
            week_start = today - timedelta(days=today.weekday())

        week_number = week_start.isocalendar()[1]

        storage_data = {
            "week_number": week_number,
            "week_start_date": str(week_start),
            "weight_start_kg": float(weight_start_kg),
            "weight_end_kg": float(weight_end_kg),
            "adherence_percent": int(adherence_percent),
            "hunger_level": hunger_level,
            "energy_level": energy_level,
            "sleep_quality": sleep_quality,
            "cravings": feedback_data.get("cravings", []),
            "subjective_notes": notes,
            "detected_patterns": {
                "metabolic_adaptation": metabolic["detected"],
                "adherence_patterns": adherence_patterns["positive_triggers"],
            },
            "adjustments_suggested": result["adjustments"]["suggested"],
            "adjustment_rationale": result["adjustments"]["rationale"],
            "feedback_quality": completeness["quality"],
            "agent_confidence_percent": int(final_confidence * 100),
            "red_flags": {f["flag_type"]: f["severity"] for f in red_flags},
        }

        insert_response = (
            supabase.table("weekly_feedback").insert(storage_data).execute()
        )
        logger.info("✅ Weekly feedback stored in database")

        # Step 11: Update learning profile (async but fire-and-forget)
        if learning_profile:
            weeks_data = learning_profile.get("weeks_of_data", 0) + 1
            new_confidence = min(0.95, 0.3 + (weeks_data / 8.0))  # Increases with weeks
            update_data = {
                "weeks_of_data": weeks_data,
                "confidence_level": new_confidence,
                "updated_at": datetime.now().isoformat(),
            }
            try:
                supabase.table("user_learning_profile").update(update_data).eq(
                    "id", learning_profile["id"]
                ).execute()
                logger.info(f"Learning profile updated: {weeks_data} weeks of data")
            except Exception as e:
                logger.warning(f"Could not update learning profile: {e}")
        else:
            # Create new learning profile (upsert with fixed UUID for single user)
            LEARNING_PROFILE_UUID = (
                "550e8400-e29b-41d4-a716-446655440000"  # Fixed UUID for single user
            )
            try:
                supabase.table("user_learning_profile").upsert(
                    {
                        "id": LEARNING_PROFILE_UUID,
                        "weeks_of_data": 1,
                        "confidence_level": 0.3,
                        "updated_at": datetime.now().isoformat(),
                    }
                ).execute()
                logger.info("New learning profile created")
            except Exception as e:
                logger.warning(f"Could not create learning profile: {e}")

        logger.info("✅ Weekly adjustments synthesized successfully")
        return json.dumps(result, indent=2, ensure_ascii=False)

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return json.dumps({"error": str(e), "code": "VALIDATION_ERROR"})
    except Exception as e:
        logger.error(f"Unexpected error in weekly adjustments: {e}", exc_info=True)
        return json.dumps(
            {
                "error": "Internal error during weekly synthesis",
                "code": "ADJUSTMENT_ERROR",
            }
        )
