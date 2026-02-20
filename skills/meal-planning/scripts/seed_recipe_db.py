"""Seed the recipe database with validated recipes.

Generates recipes via Claude Sonnet 4.5, validates macros via OpenFoodFacts,
and inserts into the recipes table. Run once or periodically.

PREREQUISITE: Run this script before first use of the new meal planning system.
Minimum: 10 recipes per meal_type (40 total) for the system to work without
excessive LLM fallback. Target: 30 per type (120 total).
"""

import json
import logging

from src.nutrition.openfoodfacts_client import match_ingredient
from src.nutrition.recipe_db import save_recipe, count_recipes_by_meal_type

logger = logging.getLogger(__name__)

RECIPE_MODEL = "claude-haiku-4-5-20251001"

# Default meal types to seed
DEFAULT_MEAL_TYPES = ["petit-dejeuner", "dejeuner", "diner", "collation"]

# Default cuisine types for variety
DEFAULT_CUISINES = ["française", "méditerranéenne", "italienne", "asiatique"]

# Batch size for LLM generation (5 recipes per call for quality)
BATCH_SIZE = 5

_SEED_PROMPT_TEMPLATE = """Tu es un nutritionniste expert et chef cuisinier français.
Génère {batch_size} recettes originales et variées pour le type de repas: {meal_type}

Cuisine: {cuisine_type}
Type de régime: {diet_type}
Temps de préparation max: {max_prep_time} minutes

Génère un tableau JSON avec exactement {batch_size} recettes, chacune avec cette structure:
{{
  "name": "Nom de la recette en français",
  "description": "Description courte (1-2 phrases)",
  "meal_type": "{meal_type}",
  "cuisine_type": "{cuisine_type}",
  "diet_type": "{diet_type}",
  "prep_time_minutes": 25,
  "ingredients": [
    {{"name": "Ingrédient", "quantity": 150, "unit": "g"}},
    {{"name": "Ingrédient 2", "quantity": 2, "unit": "pièces"}}
  ],
  "instructions": "Instructions détaillées en français.",
  "tags": ["high-protein", "quick"],
  "allergen_tags": []
}}

RÈGLES CRITIQUES:
- Ingrédients courants et facilement trouvables en supermarché
- Quantités réalistes pour 1 personne
- Instructions claires, étape par étape
- Noms de recettes variés et appétissants
- Chaque recette doit être DIFFÉRENTE des autres
- Type {diet_type}: pas de viande/poisson si végétarien/vegan
- Réponds UNIQUEMENT avec le tableau JSON, sans texte avant/après"""


async def _generate_and_validate_batch(
    anthropic_client,
    supabase,
    meal_type: str,
    cuisine_type: str,
    diet_type: str,
    max_prep_time: int,
    batch_size: int,
) -> tuple[int, int]:
    """Generate a batch of recipes and validate each via OFF.

    Returns:
        (saved_count, failed_count)
    """
    prompt = _SEED_PROMPT_TEMPLATE.format(
        batch_size=batch_size,
        meal_type=meal_type,
        cuisine_type=cuisine_type,
        diet_type=diet_type,
        max_prep_time=max_prep_time,
    )

    try:
        message = await anthropic_client.messages.create(
            model=RECIPE_MODEL,
            max_tokens=4000,
            temperature=0.8,
            messages=[{"role": "user", "content": prompt}],
        )

        raw_content = message.content[0].text.strip()

        # Strip markdown code blocks if present
        if raw_content.startswith("```"):
            lines = raw_content.split("\n")
            raw_content = "\n".join(lines[1:-1])

        recipes = json.loads(raw_content)
        if not isinstance(recipes, list):
            logger.error("LLM returned non-list JSON")
            return 0, batch_size

    except json.JSONDecodeError as e:
        logger.error(f"LLM returned invalid JSON: {e}")
        return 0, batch_size
    except Exception as e:
        logger.error(f"LLM call failed: {e}", exc_info=True)
        return 0, batch_size

    saved_count = 0
    failed_count = 0

    for recipe_dict in recipes:
        try:
            # Calculate macros via OpenFoodFacts
            total_calories = 0.0
            total_protein = 0.0
            total_carbs = 0.0
            total_fat = 0.0
            matched_count = 0
            ingredients = recipe_dict.get("ingredients", [])

            for ingredient in ingredients:
                macros = await match_ingredient(
                    ingredient_name=ingredient.get("name", ""),
                    quantity=ingredient.get("quantity", 0),
                    unit=ingredient.get("unit", "g"),
                    supabase=supabase,
                )
                if macros:
                    total_calories += macros.get("calories", 0)
                    total_protein += macros.get("protein_g", 0)
                    total_carbs += macros.get("carbs_g", 0)
                    total_fat += macros.get("fat_g", 0)
                    matched_count += 1

            off_validated = matched_count == len(ingredients) and len(ingredients) > 0

            recipe_to_save = {
                "name": recipe_dict.get("name", ""),
                "description": recipe_dict.get("description", ""),
                "meal_type": recipe_dict.get("meal_type", meal_type),
                "cuisine_type": recipe_dict.get("cuisine_type", cuisine_type),
                "diet_type": recipe_dict.get("diet_type", diet_type),
                "tags": recipe_dict.get("tags", []),
                "ingredients": ingredients,
                "instructions": recipe_dict.get("instructions", ""),
                "prep_time_minutes": recipe_dict.get("prep_time_minutes", 30),
                "calories_per_serving": round(total_calories, 2),
                "protein_g_per_serving": round(total_protein, 2),
                "carbs_g_per_serving": round(total_carbs, 2),
                "fat_g_per_serving": round(total_fat, 2),
                "allergen_tags": recipe_dict.get("allergen_tags", []),
                "source": "llm_generated",
                "off_validated": off_validated,
            }

            await save_recipe(supabase, recipe_to_save)
            saved_count += 1
            logger.info(
                f"  Saved: '{recipe_dict.get('name')}' "
                f"({total_calories:.0f} kcal, OFF={off_validated})"
            )

        except Exception as e:
            logger.error(f"Failed to save recipe '{recipe_dict.get('name')}': {e}")
            failed_count += 1

    return saved_count, failed_count


async def execute(**kwargs) -> str:
    """Seed recipe DB.

    Args:
        anthropic_client: anthropic.AsyncAnthropic client
        supabase: Supabase client
        meal_types: List of meal types to seed (default: all 4)
        recipes_per_type: Number of recipes per meal type (default: 30)
        cuisine_types: Cuisines to generate for (default: 4 main cuisines)
        diet_types: Diet types (default: ["omnivore"])
        max_prep_time: Max prep time for seeded recipes (default: 45)

    Returns:
        JSON: {"total_generated": 120, "off_validated": 108, "failed": 12,
               "coverage": {"petit-dejeuner": 30, ...}}
    """
    anthropic_client = kwargs["anthropic_client"]
    supabase = kwargs["supabase"]
    meal_types = kwargs.get("meal_types", DEFAULT_MEAL_TYPES)
    recipes_per_type = kwargs.get("recipes_per_type", 30)
    cuisine_types = kwargs.get("cuisine_types", DEFAULT_CUISINES)
    diet_types = kwargs.get("diet_types", ["omnivore"])
    max_prep_time = kwargs.get("max_prep_time", 45)

    try:
        logger.info(
            f"Seeding recipe DB: {len(meal_types)} meal types × "
            f"{recipes_per_type} recipes/type = "
            f"{len(meal_types) * recipes_per_type} total target"
        )

        total_generated = 0
        total_failed = 0

        for meal_type in meal_types:
            logger.info(f"Seeding meal_type={meal_type}...")
            type_saved = 0
            type_failed = 0

            # Distribute recipes across cuisine and diet types
            per_cuisine = max(1, recipes_per_type // len(cuisine_types))
            remainder = recipes_per_type - per_cuisine * len(cuisine_types)

            for i, cuisine_type in enumerate(cuisine_types):
                batch_target = per_cuisine + (1 if i < remainder else 0)

                for diet_type in diet_types:
                    # Generate in batches of BATCH_SIZE
                    batches_needed = (batch_target + BATCH_SIZE - 1) // BATCH_SIZE

                    for batch_idx in range(batches_needed):
                        current_batch = min(
                            BATCH_SIZE, batch_target - batch_idx * BATCH_SIZE
                        )
                        if current_batch <= 0:
                            break

                        saved, failed = await _generate_and_validate_batch(
                            anthropic_client=anthropic_client,
                            supabase=supabase,
                            meal_type=meal_type,
                            cuisine_type=cuisine_type,
                            diet_type=diet_type,
                            max_prep_time=max_prep_time,
                            batch_size=current_batch,
                        )
                        type_saved += saved
                        type_failed += failed

            logger.info(
                f"meal_type={meal_type}: {type_saved} saved, {type_failed} failed"
            )
            total_generated += type_saved
            total_failed += type_failed

        # Check coverage
        coverage = await count_recipes_by_meal_type(supabase)

        logger.info(
            f"Seeding complete: {total_generated} saved, {total_failed} failed. "
            f"Coverage: {coverage}"
        )

        return json.dumps(
            {
                "total_generated": total_generated,
                "failed": total_failed,
                "coverage": coverage,
            },
            indent=2,
            ensure_ascii=False,
        )

    except ValueError as e:
        logger.error(f"Validation error in seed_recipe_db: {e}")
        return json.dumps({"error": str(e), "code": "VALIDATION_ERROR"})
    except Exception as e:
        logger.error(f"Unexpected error in seed_recipe_db: {e}", exc_info=True)
        return json.dumps({"error": "Internal error", "code": "SCRIPT_ERROR"})
