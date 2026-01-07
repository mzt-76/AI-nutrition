"""
AI Nutrition Assistant - Main Agent Setup

This module creates and configures the Pydantic AI agent with:
- OpenAI model configuration
- Agent dependencies (Supabase, OpenAI, mem0, HTTP client)
- Tool registration
- System prompt
- Memory integration
"""

from pydantic_ai import Agent, RunContext
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.models.openai import OpenAIModel
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv
import os
import logging

from prompt import AGENT_SYSTEM_PROMPT
from clients import (
    get_supabase_client,
    get_embedding_client,
    get_http_client,
    get_brave_api_key,
    get_searxng_base_url,
)
from tools import (
    calculate_nutritional_needs_tool,
    fetch_my_profile_tool,
    update_my_profile_tool,
    retrieve_relevant_documents_tool,
    web_search_tool,
    image_analysis_tool,
    generate_weekly_meal_plan_tool,
    generate_shopping_list_tool,
    calculate_weekly_adjustments_tool,
)

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables
project_root = Path(__file__).resolve().parent
dotenv_path = project_root / ".env"
load_dotenv(dotenv_path, override=True)


def get_model():
    """
    Get configured LLM model from environment variables.

    Returns:
        OpenAIModel: Configured model instance

    Environment Variables:
        LLM_CHOICE: Model name (default: gpt-4o-mini)
        LLM_BASE_URL: API base URL (default: https://api.openai.com/v1)
        LLM_API_KEY: API key (required)
    """
    llm = os.getenv("LLM_CHOICE", "gpt-4o-mini")
    base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    api_key = os.getenv("LLM_API_KEY")

    if not api_key:
        raise ValueError("LLM_API_KEY not found in environment variables")

    logger.info(f"Initializing LLM: {llm} at {base_url}")

    return OpenAIModel(llm, provider=OpenAIProvider(base_url=base_url, api_key=api_key))


@dataclass
class AgentDeps:
    """
    Agent dependencies container.

    Attributes:
        supabase: Supabase client for database operations
        embedding_client: OpenAI client for embeddings (RAG)
        http_client: HTTP client for web searches
        brave_api_key: Brave Search API key (optional)
        searxng_base_url: SearXNG base URL (optional)
        memories: String containing user memories for context
    """

    supabase: any  # Supabase Client
    embedding_client: any  # AsyncOpenAI
    http_client: any  # AsyncClient
    brave_api_key: str | None
    searxng_base_url: str | None
    memories: str


# Create the Pydantic AI agent
agent = Agent(
    get_model(), system_prompt=AGENT_SYSTEM_PROMPT, deps_type=AgentDeps, retries=2
)


@agent.system_prompt
def add_memories(ctx: RunContext[AgentDeps]) -> str:
    """
    Add user memories to system prompt for context.

    Args:
        ctx: Run context with dependencies

    Returns:
        Formatted memory string for system prompt
    """
    if ctx.deps.memories:
        return f"\n\n## User Memories (Long-Term Context)\n{ctx.deps.memories}"
    return ""


@agent.tool
async def calculate_nutritional_needs(
    ctx: RunContext[AgentDeps],
    age: int,
    gender: str,
    weight_kg: float,
    height_cm: int,
    activity_level: str,
    goals: dict = None,
    activities: list[str] = None,
    context: str = None,
) -> str:
    """
    Calculate BMR, TDEE, and target macronutrients with automatic goal inference.

    Args:
        ctx: Run context (not used directly, required by Pydantic AI)
        age: Age in years (18-100)
        gender: "male" or "female"
        weight_kg: Body weight in kilograms
        height_cm: Height in centimeters
        activity_level: sedentary, light, moderate, active, very_active
        goals: Optional explicit goals dict (0-10 scores)
        activities: Optional list of activities for goal inference
        context: Optional context string for goal inference

    Returns:
        JSON string with calculation results

    Example:
        User: "Je fais 87kg, 178cm, 35 ans, objectif prise de masse"
        Agent calls: calculate_nutritional_needs(
            age=35, gender="male", weight_kg=87, height_cm=178,
            activity_level="moderate", context="objectif prise de masse"
        )
    """
    logger.info("Tool called: calculate_nutritional_needs")
    return await calculate_nutritional_needs_tool(
        age, gender, weight_kg, height_cm, activity_level, goals, activities, context
    )


@agent.tool
async def fetch_my_profile(ctx: RunContext[AgentDeps]) -> str:
    """
    Retrieve user profile from database.

    Args:
        ctx: Run context with Supabase client

    Returns:
        JSON string with profile data

    Example:
        Agent automatically calls this on first message to load user context
    """
    logger.info("Tool called: fetch_my_profile")
    return await fetch_my_profile_tool(ctx.deps.supabase)


@agent.tool
async def update_my_profile(
    ctx: RunContext[AgentDeps],
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
    Update user profile in database with new information.

    Use this tool when the user provides their personal information like age, weight, height,
    activity level, food preferences, allergies, or any profile-related data.

    Only provide the fields that need to be updated - all parameters are optional.

    Args:
        ctx: Run context with Supabase client
        age: User age in years (18-100)
        gender: "male"/"homme" or "female"/"femme"
        weight_kg: Weight in kilograms (for BMR/TDEE calculations)
        height_cm: Height in centimeters (for BMR/TDEE calculations)
        activity_level: "sédentaire"/"sedentary", "léger"/"light", "modéré"/"moderate",
                       "actif"/"active", "très actif"/"very_active"
        goals: User's fitness/health goals as dict with weights 0-10 for each goal:
               - "weight_loss": Perte de poids (0-10)
               - "muscle_gain": Prise de muscle/musculation (0-10)
               - "performance": Performance sportive (0-10)
               - "maintenance": Santé/maintenance (0-10)
               Example: {"weight_loss": 8, "maintenance": 3} for primary weight loss goal
        allergies: List of allergen foods (e.g., ["arachides", "lactose"])
        diet_type: Diet type (e.g., "omnivore", "végétarien", "vegan")
        disliked_foods: List of foods to avoid (e.g., ["brocoli", "chou-fleur"])
        favorite_foods: List of preferred foods
        max_prep_time: Maximum cooking time in minutes
        preferred_cuisines: List of cuisine types (e.g., ["méditerranéenne", "asiatique"])

    Returns:
        JSON string with success message and updated profile

    Examples:
        User: "J'ai 23 ans, je suis un homme de 86kg pour 1m91, sédentaire"
        Agent: update_my_profile(age=23, gender="homme", weight_kg=86, height_cm=191, activity_level="sédentaire")

        User: "Mon objectif principal est la prise de muscle"
        Agent: update_my_profile(goals={"muscle_gain": 8, "maintenance": 2})
    """
    logger.info("Tool called: update_my_profile")
    return await update_my_profile_tool(
        ctx.deps.supabase,
        age=age,
        gender=gender,
        weight_kg=weight_kg,
        height_cm=height_cm,
        activity_level=activity_level,
        goals=goals,
        allergies=allergies,
        diet_type=diet_type,
        disliked_foods=disliked_foods,
        favorite_foods=favorite_foods,
        max_prep_time=max_prep_time,
        preferred_cuisines=preferred_cuisines,
    )


@agent.tool
async def retrieve_relevant_documents(
    ctx: RunContext[AgentDeps], user_query: str
) -> str:
    """
    Search the nutritional knowledge base using RAG (semantic search).

    Args:
        ctx: Run context with Supabase and embedding client
        user_query: User's question or topic

    Returns:
        Formatted string with relevant document chunks

    Example:
        User: "Combien de protéines pour prendre du muscle?"
        Agent calls: retrieve_relevant_documents("protein requirements muscle gain")
    """
    logger.info("Tool called: retrieve_relevant_documents")
    return await retrieve_relevant_documents_tool(
        ctx.deps.supabase, ctx.deps.embedding_client, user_query
    )


@agent.tool
async def web_search(ctx: RunContext[AgentDeps], query: str) -> str:
    """
    Search the web for recent nutritional information.

    Args:
        ctx: Run context with HTTP client and API keys
        query: Search query

    Returns:
        Summary of search results

    Example:
        User: "Nouvelles recommandations sur les oméga-3 en 2024?"
        Agent calls: web_search("omega-3 recommendations 2024")
    """
    logger.info("Tool called: web_search")
    return await web_search_tool(
        query, ctx.deps.http_client, ctx.deps.brave_api_key, ctx.deps.searxng_base_url
    )


@agent.tool
async def image_analysis(
    ctx: RunContext[AgentDeps], image_url: str, analysis_prompt: str
) -> str:
    """
    Analyze images using GPT-4 Vision (for body composition analysis).

    Args:
        ctx: Run context with embedding client (reused for vision)
        image_url: URL to the image
        analysis_prompt: What to analyze

    Returns:
        Analysis result from GPT-4 Vision

    Example:
        User uploads body photo
        Agent calls: image_analysis(url, "Estimate body fat percentage, provide feedback")
    """
    logger.info("Tool called: image_analysis")
    return await image_analysis_tool(
        image_url, analysis_prompt, ctx.deps.embedding_client
    )


@agent.tool
async def generate_weekly_meal_plan(
    ctx: RunContext[AgentDeps],
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

    Creates a weekly meal plan based on user profile, nutritional targets, allergies,
    and preferences. Includes complete recipes with ingredients, quantities, instructions,
    and nutritional information for each meal.

    Args:
        ctx: Run context with Supabase and OpenAI clients
        start_date: Start date in YYYY-MM-DD format (Monday preferred), e.g. "2024-12-23"
        target_calories_daily: Daily calorie target (if None, uses profile target)
        target_protein_g: Daily protein target in grams
        target_carbs_g: Daily carbs target in grams
        target_fat_g: Daily fat target in grams
        meal_structure: Meal distribution pattern:
            - "3_meals_2_snacks": Breakfast, AM snack, Lunch, PM snack, Dinner (default)
            - "4_meals": 4 equal meals throughout day
            - "3_consequent_meals": 3 consecutive main meals (no snacks)
            - "3_meals_1_preworkout": 3 meals + 1 snack before training
        notes: Additional preferences (e.g., "pas de viande rouge cette semaine")

    Returns:
        JSON string with complete meal plan including all recipes, ingredients,
        nutritional information, and weekly summary

    Example:
        User: "Crée-moi un plan pour cette semaine avec 3 repas + collation pré-training"
        Agent: generate_weekly_meal_plan(
            start_date="2024-12-23",
            meal_structure="3_meals_1_preworkout"
        )
    """
    logger.info("Tool called: generate_weekly_meal_plan")
    return await generate_weekly_meal_plan_tool(
        ctx.deps.supabase,
        ctx.deps.embedding_client,
        ctx.deps.http_client,
        start_date,
        target_calories_daily,
        target_protein_g,
        target_carbs_g,
        target_fat_g,
        meal_structure,
        notes,
    )


@agent.tool
async def generate_shopping_list(
    ctx: RunContext[AgentDeps],
    week_start: str,
    selected_days: list[int] | None = None,
    servings_multiplier: float = 1.0,
) -> str:
    """
    Generate categorized shopping list from existing meal plan.

    Extracts ingredients from a meal plan, aggregates quantities, and organizes
    them by category (produce, proteins, grains, dairy, pantry, other).
    Supports selecting specific days and adjusting quantities with a multiplier.

    Args:
        ctx: Run context with Supabase client
        week_start: Meal plan start date in YYYY-MM-DD format (e.g., "2024-12-23")
        selected_days: List of day indices to include (0=Monday to 6=Sunday),
                      or None for all 7 days. Example: [0, 1, 2] for Mon-Wed
        servings_multiplier: Multiplier for all quantities (default: 1.0).
                           Use 2.0 for double portions, 0.5 for half portions

    Returns:
        JSON string with categorized shopping list, metadata, and total item count

    Example:
        User: "Génère la liste de courses pour cette semaine"
        Agent: generate_shopping_list(week_start="2024-12-23")

        User: "Liste de courses seulement pour lundi à mercredi, portions doubles"
        Agent: generate_shopping_list(
            week_start="2024-12-23",
            selected_days=[0, 1, 2],
            servings_multiplier=2.0
        )
    """
    logger.info("Tool called: generate_shopping_list")
    return await generate_shopping_list_tool(
        ctx.deps.supabase, week_start, selected_days, servings_multiplier
    )


@agent.tool
async def calculate_weekly_adjustments(
    ctx: RunContext[AgentDeps],
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

    Use this tool at the end of each week to analyze how the user did, detect patterns
    in their response to nutrition, and generate personalized recommendations for
    the next week. The tool stores weekly data for continuous learning.

    Args:
        ctx: Run context with Supabase and embedding clients
        weight_start_kg: Weight at start of week (kg)
        weight_end_kg: Weight at end of week (kg)
        adherence_percent: Percentage of plan followed (0-100%)
        hunger_level: Reported hunger level ("low", "medium", "high")
        energy_level: Reported energy level ("low", "medium", "high")
        sleep_quality: Sleep quality ("poor", "fair", "good", "excellent")
        cravings: List of cravings if any (e.g., ["sweets", "carbs"])
        notes: Free-text observations from the week

    Returns:
        JSON string with:
        - Weight trend analysis against goal targets
        - Detected patterns (metabolic, adherence, energy)
        - Suggested adjustments (calories, macros) with scientific rationale
        - Red flag alerts if concerning patterns detected
        - Confidence level for recommendations
        - Data stored for continuous learning

    Examples:
        User: "Cette semaine j'ai pesé 86.4kg au lieu de 87kg en début de semaine.
               L'adhérence a été de 85%, j'avais pas mal d'énergie, bonne récupération"
        Agent: calculate_weekly_adjustments(
            weight_start_kg=87.0,
            weight_end_kg=86.4,
            adherence_percent=85,
            hunger_level="medium",
            energy_level="high",
            sleep_quality="good",
            notes="Bonne adhérence, bien récupéré"
        )

        User: "Semaine difficile, j'ai lutté avec la faim, seulement 60% adhérence"
        Agent: calculate_weekly_adjustments(
            weight_start_kg=85.2,
            weight_end_kg=85.0,
            adherence_percent=60,
            hunger_level="high",
            energy_level="low",
            notes="Semaine difficile, beaucoup de faim"
        )
    """
    logger.info("Tool called: calculate_weekly_adjustments")
    return await calculate_weekly_adjustments_tool(
        ctx.deps.supabase,
        ctx.deps.embedding_client,
        weight_start_kg,
        weight_end_kg,
        adherence_percent,
        hunger_level,
        energy_level,
        sleep_quality,
        cravings,
        notes,
    )


def create_agent_deps(memories: str = "") -> AgentDeps:
    """
    Create agent dependencies with all initialized clients.

    Args:
        memories: Optional memory string for context

    Returns:
        AgentDeps instance with all clients initialized

    Example:
        >>> deps = create_agent_deps(memories="User prefers Mediterranean cuisine")
    """
    logger.info("Initializing agent dependencies...")

    return AgentDeps(
        supabase=get_supabase_client(),
        embedding_client=get_embedding_client(),
        http_client=get_http_client(),
        brave_api_key=get_brave_api_key(),
        searxng_base_url=get_searxng_base_url(),
        memories=memories,
    )


# For testing
if __name__ == "__main__":
    import asyncio

    async def test_agent():
        """Test agent with a simple query."""
        deps = create_agent_deps()

        result = await agent.run(
            "Calcule mes besoins nutritionnels: 35 ans, homme, 87kg, 178cm, activité modérée",
            deps=deps,
        )

        print("\n=== Agent Response ===")
        print(result.data)

    asyncio.run(test_agent())
