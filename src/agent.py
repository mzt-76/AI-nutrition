"""
AI Nutrition Assistant - Main Agent Setup

This module creates and configures the Pydantic AI agent with:
- OpenAI model configuration
- Agent dependencies (Supabase, OpenAI, mem0, HTTP client)
- Content-based progressive disclosure (skills provide context, tools always registered)
- Core tools always available (profile, skill management, domain tools)
- System prompt with memory integration
"""

from pydantic_ai import Agent, RunContext
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.toolsets import FunctionToolset
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime, timedelta
import importlib.util
import os
import logging

from src.prompt import AGENT_SYSTEM_PROMPT
from src.clients import (
    get_supabase_client,
    get_openai_client,
    get_embedding_client,
    get_http_client,
    get_brave_api_key,
    get_searxng_base_url,
)
from src.tools import (
    fetch_my_profile_tool,
    update_my_profile_tool,
    generate_weekly_meal_plan_tool,
    generate_shopping_list_tool,
    fetch_stored_meal_plan_tool,
)
from src.skill_loader import SkillLoader
from src.skill_tools import (
    load_skill as load_skill_fn,
    read_skill_file as read_skill_file_fn,
    list_skill_files as list_skill_files_fn,
)

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables
project_root = Path(__file__).resolve().parent.parent
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


def _import_skill_script(skill_name: str, script_name: str):
    """Import a script module from a skill directory.

    Uses importlib to load from hyphenated skill directory paths.

    Args:
        skill_name: Skill directory name (e.g., "nutrition-calculating").
        script_name: Script file name without extension (e.g., "calculate_nutritional_needs").

    Returns:
        Loaded module with execute() function.
    """
    script_path = project_root / "skills" / skill_name / "scripts" / f"{script_name}.py"
    spec = importlib.util.spec_from_file_location(
        f"skill_script.{script_name}", script_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@dataclass
class AgentDeps:
    """
    Agent dependencies container.

    Attributes:
        supabase: Supabase client for database operations
        openai_client: OpenAI client for general use (chat, vision)
        embedding_client: OpenAI client for embeddings (RAG)
        http_client: HTTP client for web searches
        brave_api_key: Brave Search API key (optional)
        searxng_base_url: SearXNG base URL (optional)
        memories: String containing user memories for context
        skill_loader: Loader for progressive disclosure skills
    """

    supabase: any  # Supabase Client
    openai_client: any  # AsyncOpenAI (general)
    embedding_client: any  # AsyncOpenAI (embeddings)
    http_client: any  # AsyncClient
    brave_api_key: str | None
    searxng_base_url: str | None
    memories: str
    skill_loader: SkillLoader | None = None


# =============================================================================
# All Tools — Single static FunctionToolset
# =============================================================================

core_tools = FunctionToolset()


# --- Skill management tools (progressive disclosure) ---


async def load_skill(
    ctx: RunContext[AgentDeps],
    skill_name: str,
) -> str:
    """Load detailed instructions for a skill domain.

    Call this BEFORE executing a complex workflow to get the full context
    (workflow steps, parameters, business rules, examples).

    Args:
        ctx: Run context
        skill_name: Name of the skill to load (e.g., "meal-planning", "weekly-coaching")
    """
    logger.info(f"Tool called: load_skill(skill_name={skill_name})")
    return await load_skill_fn(ctx, skill_name)


async def read_skill_file(
    ctx: RunContext[AgentDeps],
    skill_name: str,
    file_path: str,
) -> str:
    """Read a reference file from a skill's directory (Level 3 progressive disclosure).

    Args:
        ctx: Run context
        skill_name: Name of the skill containing the file
        file_path: Relative path within the skill directory (e.g., "references/formulas.md")
    """
    logger.info(
        f"Tool called: read_skill_file(skill_name={skill_name}, file_path={file_path})"
    )
    return await read_skill_file_fn(ctx, skill_name, file_path)


async def list_skill_files(
    ctx: RunContext[AgentDeps],
    skill_name: str,
    directory: str = "",
) -> str:
    """List files available in a skill's directory.

    Args:
        ctx: Run context
        skill_name: Name of the skill to explore
        directory: Optional subdirectory (e.g., "references", "scripts")
    """
    logger.info(f"Tool called: list_skill_files(skill_name={skill_name})")
    return await list_skill_files_fn(ctx, skill_name, directory)


# --- Profile tools ---


async def fetch_my_profile(ctx: RunContext[AgentDeps]) -> str:
    """Retrieve user profile from database."""
    logger.info("Tool called: fetch_my_profile")
    return await fetch_my_profile_tool(ctx.deps.supabase)


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
    """Update user profile. Only provide fields that changed.

    Args:
        ctx: Run context
        age: Age in years (18-100)
        gender: "male" or "female"
        weight_kg: Weight in kg
        height_cm: Height in cm
        activity_level: sedentary, light, moderate, active, very_active
        goals: Goal scores dict (0-10 for weight_loss, muscle_gain, performance, maintenance)
        allergies: Allergen list (e.g., ["arachides", "lactose"])
        diet_type: omnivore, végétarien, vegan, etc.
        disliked_foods: Foods to avoid
        favorite_foods: Preferred foods
        max_prep_time: Max cooking time in minutes
        preferred_cuisines: Cuisine types (e.g., ["méditerranéenne", "asiatique"])
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


# --- Domain tools (delegate to skill scripts) ---


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
    """Calculate BMR, TDEE, and target macros.

    Args:
        ctx: Run context
        age: Age in years (18-100)
        gender: "male" or "female"
        weight_kg: Body weight in kg
        height_cm: Height in cm
        activity_level: sedentary, light, moderate, active, very_active
        goals: Goal scores dict (0-10 for muscle_gain, weight_loss, performance, maintenance)
        activities: List of activities (e.g., ["musculation", "basket"])
        context: User's goal statement for automatic goal inference (e.g., "prise de masse")
    """
    logger.info("Tool called: calculate_nutritional_needs")
    module = _import_skill_script(
        "nutrition-calculating", "calculate_nutritional_needs"
    )
    return await module.execute(
        age=age,
        gender=gender,
        weight_kg=weight_kg,
        height_cm=height_cm,
        activity_level=activity_level,
        goals=goals,
        activities=activities,
        context=context,
    )


async def retrieve_relevant_documents(
    ctx: RunContext[AgentDeps], user_query: str
) -> str:
    """Search nutritional knowledge base via RAG.

    Args:
        ctx: Run context
        user_query: Natural language question or topic (French or English)
    """
    logger.info("Tool called: retrieve_relevant_documents")
    module = _import_skill_script("knowledge-searching", "retrieve_relevant_documents")
    return await module.execute(
        supabase=ctx.deps.supabase,
        embedding_client=ctx.deps.embedding_client,
        user_query=user_query,
    )


async def web_search(ctx: RunContext[AgentDeps], query: str) -> str:
    """Search the web for recent nutritional information.

    Args:
        ctx: Run context
        query: Search query in natural language
    """
    logger.info("Tool called: web_search")
    module = _import_skill_script("knowledge-searching", "web_search")
    return await module.execute(
        query=query,
        http_client=ctx.deps.http_client,
        brave_api_key=ctx.deps.brave_api_key,
        searxng_base_url=ctx.deps.searxng_base_url,
    )


async def image_analysis(
    ctx: RunContext[AgentDeps], image_url: str, analysis_prompt: str
) -> str:
    """Analyze images via GPT-4 Vision.

    Args:
        ctx: Run context
        image_url: URL to the image (Google Drive or direct URL)
        analysis_prompt: What to analyze (e.g., "Estimate body fat percentage")
    """
    logger.info("Tool called: image_analysis")
    module = _import_skill_script("body-analyzing", "image_analysis")
    return await module.execute(
        image_url=image_url,
        analysis_prompt=analysis_prompt,
        openai_client=ctx.deps.openai_client,
    )


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
    """Analyze weekly check-in and generate adjustments.

    Args:
        ctx: Run context
        weight_start_kg: Weight at start of week (kg)
        weight_end_kg: Weight at end of week (kg)
        adherence_percent: Plan adherence (0-100%)
        hunger_level: low, medium, high
        energy_level: low, medium, high
        sleep_quality: poor, fair, good, excellent
        cravings: List of cravings if any
        notes: Free-text observations
    """
    logger.info("Tool called: calculate_weekly_adjustments")
    module = _import_skill_script("weekly-coaching", "calculate_weekly_adjustments")
    return await module.execute(
        supabase=ctx.deps.supabase,
        embedding_client=ctx.deps.embedding_client,
        weight_start_kg=weight_start_kg,
        weight_end_kg=weight_end_kg,
        adherence_percent=adherence_percent,
        hunger_level=hunger_level,
        energy_level=energy_level,
        sleep_quality=sleep_quality,
        cravings=cravings,
        notes=notes,
    )


# --- Meal-planning tools (still import from src/tools.py — will be migrated later) ---


async def generate_weekly_meal_plan(
    ctx: RunContext[AgentDeps],
    start_date: str | None = None,
    target_calories_daily: int = None,
    target_protein_g: int = None,
    target_carbs_g: int = None,
    target_fat_g: int = None,
    meal_structure: str = "3_consequent_meals",
    notes: str = None,
) -> str:
    """Generate 7-day meal plan with recipes.

    Args:
        ctx: Run context
        start_date: YYYY-MM-DD format (defaults to current week Monday)
        target_calories_daily: Daily kcal target (None = use profile)
        target_protein_g: Daily protein grams
        target_carbs_g: Daily carbs grams
        target_fat_g: Daily fat grams
        meal_structure: 3_consequent_meals, 3_meals_2_snacks, 4_meals, 3_meals_1_preworkout
        notes: Extra preferences (e.g., "pas de viande rouge cette semaine")
    """
    logger.info("Tool called: generate_weekly_meal_plan")

    # Calculate current week's Monday if start_date not provided
    if start_date is None:
        today = datetime.now().date()
        monday = today - timedelta(days=today.weekday())
        start_date = monday.strftime("%Y-%m-%d")
        logger.info(
            f"No start_date provided, using current week's Monday: {start_date}"
        )
    return await generate_weekly_meal_plan_tool(
        ctx.deps.supabase,
        ctx.deps.openai_client,
        ctx.deps.http_client,
        start_date,
        target_calories_daily,
        target_protein_g,
        target_carbs_g,
        target_fat_g,
        meal_structure,
        notes,
    )


async def fetch_stored_meal_plan(
    ctx: RunContext[AgentDeps],
    week_start: str | None = None,
    selected_days: list[int] | None = None,
) -> str:
    """Retrieve existing meal plan from database (fast, no regeneration).

    Args:
        ctx: Run context
        week_start: YYYY-MM-DD format (defaults to current week Monday)
        selected_days: Day indices to retrieve (0=Mon to 6=Sun), None for all
    """
    logger.info("Tool called: fetch_stored_meal_plan")

    # Calculate current week's Monday if week_start not provided
    if week_start is None:
        today = datetime.now().date()
        monday = today - timedelta(days=today.weekday())
        week_start = monday.strftime("%Y-%m-%d")
        logger.info(
            f"No week_start provided, using current week's Monday: {week_start}"
        )

    return await fetch_stored_meal_plan_tool(
        ctx.deps.supabase, week_start, selected_days
    )


async def generate_shopping_list(
    ctx: RunContext[AgentDeps],
    week_start: str | None = None,
    selected_days: list[int] | None = None,
    servings_multiplier: float = 1.0,
) -> str:
    """Generate categorized shopping list from meal plan.

    Args:
        ctx: Run context
        week_start: YYYY-MM-DD format (defaults to current week Monday)
        selected_days: Day indices to include (0=Mon to 6=Sun), None for all
        servings_multiplier: Quantity multiplier (default 1.0)
    """
    logger.info("Tool called: generate_shopping_list")

    # Calculate current week's Monday if week_start not provided
    if week_start is None:
        today = datetime.now().date()
        monday = today - timedelta(days=today.weekday())
        week_start = monday.strftime("%Y-%m-%d")
        logger.info(
            f"No week_start provided, using current week's Monday: {week_start}"
        )

    return await generate_shopping_list_tool(
        ctx.deps.supabase, week_start, selected_days, servings_multiplier
    )


# =============================================================================
# Register ALL tools in core_tools
# =============================================================================

# Skill management
core_tools.add_function(load_skill)
core_tools.add_function(read_skill_file)
core_tools.add_function(list_skill_files)

# Profile
core_tools.add_function(fetch_my_profile)
core_tools.add_function(update_my_profile)

# Domain tools (delegate to skill scripts)
core_tools.add_function(calculate_nutritional_needs)
core_tools.add_function(retrieve_relevant_documents)
core_tools.add_function(web_search)
core_tools.add_function(image_analysis)
core_tools.add_function(calculate_weekly_adjustments)

# Meal-planning (still from src/tools.py)
core_tools.add_function(generate_weekly_meal_plan)
core_tools.add_function(fetch_stored_meal_plan)
core_tools.add_function(generate_shopping_list)


# =============================================================================
# Agent Creation
# =============================================================================

agent = Agent(
    get_model(),
    system_prompt=AGENT_SYSTEM_PROMPT,
    deps_type=AgentDeps,
    retries=2,
    toolsets=[core_tools],
)


@agent.system_prompt
def add_dynamic_context(ctx: RunContext[AgentDeps]) -> str:
    """
    Add skill metadata and user memories to system prompt.

    Injects Level 1 progressive disclosure (skill names + descriptions)
    and user memories into the system prompt.

    Args:
        ctx: Run context with dependencies

    Returns:
        Formatted string with skill metadata and memories
    """
    sections: list[str] = []

    if ctx.deps.skill_loader and ctx.deps.skill_loader.skills:
        skill_metadata = ctx.deps.skill_loader.get_skill_metadata_prompt()
        sections.append(
            "\n\n## Skills Disponibles (Progressive Disclosure)\n"
            "Charge un skill avec `load_skill(skill_name)` pour obtenir les instructions "
            "detaillees (workflow, parametres, regles metier) AVANT d'utiliser ses outils.\n\n"
            f"{skill_metadata}"
        )

    if ctx.deps.memories:
        sections.append(
            f"\n\n## User Memories (Long-Term Context)\n{ctx.deps.memories}"
        )

    return "".join(sections)


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

    # Initialize skill loader
    skills_dir = project_root / "skills"
    skill_loader = SkillLoader(skills_dir)
    discovered = skill_loader.discover_skills()
    logger.info(f"Skills loaded: {len(discovered)} skills discovered")

    return AgentDeps(
        supabase=get_supabase_client(),
        openai_client=get_openai_client(),
        embedding_client=get_embedding_client(),
        http_client=get_http_client(),
        brave_api_key=get_brave_api_key(),
        searxng_base_url=get_searxng_base_url(),
        memories=memories,
        skill_loader=skill_loader,
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
