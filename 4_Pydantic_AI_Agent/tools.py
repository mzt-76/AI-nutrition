"""
Tool implementations for AI Nutrition Assistant.

This module contains all the tools that the agent can use:
- calculate_nutritional_needs: BMR, TDEE, macro calculations
- calculate_weekly_adjustments: Adaptive feedback analysis
- retrieve_relevant_documents: RAG knowledge base search
- web_search: Brave API web search
- fetch_my_profile: Supabase profile retrieval
- image_analysis: GPT-4 Vision for body composition

All tools include type hints, validation, and error handling.
"""

from supabase import Client
from openai import AsyncOpenAI
from httpx import AsyncClient
import json
import logging

from nutrition.calculations import (
    mifflin_st_jeor_bmr,
    calculate_tdee,
    infer_goals_from_context,
    calculate_protein_target,
    calculate_macros
)

logger = logging.getLogger(__name__)


async def calculate_nutritional_needs_tool(
    age: int,
    gender: str,
    weight_kg: float,
    height_cm: int,
    activity_level: str,
    goals: dict | None = None,
    activities: list[str] | None = None,
    context: str | None = None
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
        logger.info(f"Calculating nutritional needs: age={age}, gender={gender}, weight={weight_kg}kg")

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
        protein_g, protein_per_kg, protein_range = calculate_protein_target(weight_kg, primary_goal)

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
            "inference_rationale": []
        }

        # Add rationale
        if activities:
            result["inference_rationale"].append(f"Activities: {', '.join(activities)}")
        if "muscle_gain" in primary_goal:
            result["inference_rationale"].append("Goal: Muscle gain detected → +300 kcal surplus")
        if "weight_loss" in primary_goal:
            result["inference_rationale"].append("Goal: Weight loss detected → -500 kcal deficit")

        logger.info(f"Nutrition calculation complete: {target_calories} kcal, {protein_g}g protein")

        return json.dumps(result, indent=2)

    except ValueError as e:
        logger.error(f"Validation error in nutritional needs calculation: {e}")
        return json.dumps({"error": str(e), "code": "VALIDATION_ERROR"})
    except Exception as e:
        logger.error(f"Unexpected error in nutritional needs calculation: {e}", exc_info=True)
        return json.dumps({"error": "Internal calculation error", "code": "CALCULATION_ERROR"})


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
            required_fields = ["age", "gender", "weight_kg", "height_cm", "activity_level"]
            has_data = any(profile.get(field) is not None for field in required_fields)

            if not has_data:
                logger.warning("Profile exists but is incomplete (missing required fields)")
                return json.dumps({
                    "error": "Profile incomplete",
                    "code": "PROFILE_INCOMPLETE",
                    "message": "Le profil existe mais n'a pas encore de données. Les champs requis (âge, genre, poids, taille, niveau d'activité) sont vides.",
                    "name": profile.get("name"),
                    "existing_data": {
                        "max_prep_time": profile.get("max_prep_time"),
                        "favorite_foods": profile.get("favorite_foods"),
                        "disliked_foods": profile.get("disliked_foods"),
                        "allergies": profile.get("allergies")
                    }
                })

            logger.info(f"Profile loaded: {profile.get('name', 'Unknown')}")
            return json.dumps(profile, indent=2)
        else:
            logger.warning("No profile found in database")
            return json.dumps({"error": "No profile found", "code": "PROFILE_NOT_FOUND"})

    except Exception as e:
        logger.error(f"Error fetching profile: {e}", exc_info=True)
        return json.dumps({"error": "Database error", "code": "DB_ERROR"})


async def retrieve_relevant_documents_tool(
    supabase: Client,
    embedding_client: AsyncOpenAI,
    user_query: str
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
            model="text-embedding-3-small",
            input=user_query
        )
        query_embedding = response.data[0].embedding

        # Query Supabase vectorstore
        result = supabase.rpc("match_documents", {
            "query_embedding": query_embedding,
            "match_count": 10,  # Get more results, filter by threshold later
            "filter": {}
        }).execute()

        if not result.data:
            logger.warning("No relevant documents found")
            return "No relevant documents found in knowledge base."

        # Filter by similarity threshold (0.5 for cross-language queries) and take top 4
        MIN_SIMILARITY = 0.5
        relevant_docs = [
            doc for doc in result.data
            if doc.get('similarity', 0) >= MIN_SIMILARITY
        ][:4]

        if not relevant_docs:
            logger.warning(f"No documents above similarity threshold {MIN_SIMILARITY}")
            return f"No sufficiently relevant documents found (threshold: {MIN_SIMILARITY})."

        # Format results
        formatted_docs = []
        for i, doc in enumerate(relevant_docs, 1):
            similarity = doc.get('similarity', 0)
            content = doc.get('content', '')
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
    searxng_base_url: str | None
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
            "X-Subscription-Token": brave_api_key
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
    image_url: str,
    query: str,
    openai_client: AsyncOpenAI
) -> str:
    """
    Analyze images using GPT-4 Vision.

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
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": query},
                        {"type": "image_url", "image_url": {"url": image_url}}
                    ]
                }
            ],
            max_tokens=500
        )

        result = response.choices[0].message.content

        logger.info("Image analysis complete")

        return result

    except Exception as e:
        logger.error(f"Image analysis error: {e}", exc_info=True)
        return f"Image analysis error: {str(e)}"
