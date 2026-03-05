"""
AI Nutrition Assistant - Main Agent Setup

This module creates and configures the Pydantic AI agent with:
- OpenAI model configuration
- Agent dependencies (Supabase, OpenAI, mem0, HTTP client)
- Content-based progressive disclosure (skills provide context, tools always registered)
- Core tools: skill management (load/read/list/run), profile (fetch/update)
- System prompt with memory integration

Skill execution pattern:
  1. Agent calls load_skill(skill_name) to read SKILL.md
  2. SKILL.md documents which script to run and what params to pass
  3. Agent calls run_skill_script(skill_name, script_name, params)
  No per-skill wrappers — adding a new skill never requires touching this file.
"""

from pydantic_ai import Agent, RunContext
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.toolsets import FunctionToolset
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv
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
    get_anthropic_client,
)
from src.tools import (
    fetch_my_profile_tool,
    update_my_profile_tool,
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

    Provider is auto-detected from the model name:
    - "claude-*" → Anthropic (requires ANTHROPIC_API_KEY)
    - anything else → OpenAI-compatible (requires LLM_API_KEY)

    Environment Variables:
        LLM_CHOICE: Model name (default: gpt-4o-mini)
            OpenAI example:    gpt-4o-mini
            Anthropic example: claude-haiku-4-5-20251001
        LLM_API_KEY: OpenAI API key (required for OpenAI models)
        LLM_BASE_URL: OpenAI-compatible base URL (default: https://api.openai.com/v1)
        ANTHROPIC_API_KEY: Anthropic API key (required for claude-* models)
    """
    model_name = os.getenv("LLM_CHOICE", "gpt-4o-mini")

    if model_name.startswith("claude-"):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment variables")
        logger.info(f"Initializing LLM (Anthropic): {model_name}")
        return AnthropicModel(model_name)

    # OpenAI-compatible (OpenAI, OpenRouter, Ollama, etc.)
    api_key = os.getenv("LLM_API_KEY")
    base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    if not api_key:
        raise ValueError("LLM_API_KEY not found in environment variables")
    logger.info(f"Initializing LLM (OpenAI): {model_name} at {base_url}")
    return OpenAIChatModel(
        model_name, provider=OpenAIProvider(base_url=base_url, api_key=api_key)
    )


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
        anthropic_client: Anthropic client for skill-level LLM calls (Claude Sonnet 4.5)
    """

    supabase: any  # Supabase Client
    openai_client: any  # AsyncOpenAI (general)
    embedding_client: any  # AsyncOpenAI (embeddings)
    http_client: any  # AsyncClient
    brave_api_key: str | None
    searxng_base_url: str | None
    memories: str
    skill_loader: SkillLoader | None = None
    anthropic_client: any = None  # AsyncAnthropic (skills)
    user_id: str | None = None


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

    Call this BEFORE executing a skill to get the full context
    (workflow steps, script names, parameters, business rules, examples).

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


async def run_skill_script(
    ctx: RunContext[AgentDeps],
    skill_name: str,
    script_name: str,
    parameters: dict[str, str | int | float | bool | list | dict | None] | None = None,
) -> str:
    """Execute a script from a skill's scripts/ folder.

    Use this after load_skill() — SKILL.md tells you which script to run
    and what parameters to pass. All shared clients are injected automatically.

    Args:
        ctx: Run context
        skill_name: Skill directory name (e.g., "meal-planning", "nutrition-calculating")
        script_name: Script filename without .py (e.g., "generate_week_plan")
        parameters: Business parameters for the script (dates, targets, etc.)
            See the skill's SKILL.md for the full parameter list per script.

    Examples:
        run_skill_script("nutrition-calculating", "calculate_nutritional_needs",
            {"age": 30, "gender": "male", "weight_kg": 80, "height_cm": 178,
             "activity_level": "moderate"})

        run_skill_script("meal-planning", "generate_week_plan",
            {"start_date": "2026-02-23", "target_calories_daily": 2800})

        run_skill_script("meal-planning", "generate_shopping_list",
            {"week_start": "2026-02-23"})
    """
    logger.info(
        f"Tool called: run_skill_script(skill={skill_name}, script={script_name})"
    )
    module = _import_skill_script(skill_name, script_name)

    # Inject all shared clients — scripts take only what they need via kwargs.get()
    all_params = {
        "supabase": ctx.deps.supabase,
        "openai_client": ctx.deps.openai_client,
        "embedding_client": ctx.deps.embedding_client,
        "http_client": ctx.deps.http_client,
        "brave_api_key": ctx.deps.brave_api_key,
        "searxng_base_url": ctx.deps.searxng_base_url,
        "anthropic_client": ctx.deps.anthropic_client,
        "user_id": ctx.deps.user_id,
    }
    if parameters:
        all_params.update(parameters)

    return await module.execute(**all_params)


# --- Profile tools (core, not skill-specific) ---


async def fetch_my_profile(ctx: RunContext[AgentDeps]) -> str:
    """Retrieve user profile from database."""
    logger.info("Tool called: fetch_my_profile")
    return await fetch_my_profile_tool(ctx.deps.supabase, user_id=ctx.deps.user_id)


async def update_my_profile(
    ctx: RunContext[AgentDeps],
    age: int = None,
    gender: str = None,
    weight_kg: float = None,
    height_cm: int = None,
    activity_level: str = None,
    goals: dict[str, int] | None = None,
    allergies: list[str] = None,
    diet_type: str = None,
    disliked_foods: list[str] = None,
    favorite_foods: list[str] = None,
    max_prep_time: int = None,
    preferred_cuisines: list[str] = None,
    bmr: float = None,
    tdee: float = None,
    target_calories: float = None,
    target_protein_g: float = None,
    target_carbs_g: float = None,
    target_fat_g: float = None,
) -> str:
    """Update user profile. Only provide fields that changed.

    Args:
        ctx: Run context
        age: Age in years (18-100)
        gender: "male" or "female"
        weight_kg: Weight in kg
        height_cm: Height in cm
        activity_level: sedentary, light, moderate, active, very_active
        goals: Integer scores 0-10 per goal key, e.g. {"muscle_gain": 8, "weight_loss": 0}
        allergies: Allergen list (e.g., ["arachides", "lactose"])
        diet_type: omnivore, végétarien, vegan, etc.
        disliked_foods: Foods to avoid
        favorite_foods: Preferred foods
        max_prep_time: Max cooking time in minutes
        preferred_cuisines: Cuisine types (e.g., ["méditerranéenne", "asiatique"])
        bmr: Basal Metabolic Rate in kcal (calculated)
        tdee: Total Daily Energy Expenditure in kcal (calculated)
        target_calories: Daily calorie target in kcal
        target_protein_g: Daily protein target in grams
        target_carbs_g: Daily carbohydrate target in grams
        target_fat_g: Daily fat target in grams
    """
    logger.info("Tool called: update_my_profile")
    return await update_my_profile_tool(
        ctx.deps.supabase,
        user_id=ctx.deps.user_id,
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
        bmr=bmr,
        tdee=tdee,
        target_calories=target_calories,
        target_protein_g=target_protein_g,
        target_carbs_g=target_carbs_g,
        target_fat_g=target_fat_g,
    )


# =============================================================================
# Register tools in core_tools
# =============================================================================

# Skill management (progressive disclosure)
core_tools.add_function(load_skill)
core_tools.add_function(read_skill_file)
core_tools.add_function(list_skill_files)
core_tools.add_function(run_skill_script)

# Profile (core, not skill-specific)
core_tools.add_function(fetch_my_profile)
core_tools.add_function(update_my_profile)


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
            "detaillees (workflow, scripts disponibles, parametres). "
            "Execute ensuite avec `run_skill_script(skill_name, script_name, params)`.\n\n"
            f"{skill_metadata}"
        )

    if ctx.deps.memories:
        sections.append(
            f"\n\n## User Memories (Long-Term Context)\n{ctx.deps.memories}"
        )

    return "".join(sections)


def create_agent_deps(memories: str = "", user_id: str | None = None) -> AgentDeps:
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
        anthropic_client=get_anthropic_client(),
        user_id=user_id,
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
