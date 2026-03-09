"""Generate a custom recipe when not found in recipe DB.

Used when user requests a specific dish or ingredient.
Generates recipe → calculates macros via OpenFoodFacts → optionally saves to DB.

Source: Simplified from src/tools.py generate_weekly_meal_plan_tool
"""

import asyncio
import json
import logging

from pydantic import BaseModel, Field, field_validator

from src.nutrition.openfoodfacts_client import match_ingredient
from src.nutrition.recipe_db import save_recipe

logger = logging.getLogger(__name__)


class _RecipeIngredient(BaseModel):
    name: str = Field(min_length=1)
    quantity: float = Field(gt=0)
    unit: str = Field(min_length=1)


class _LLMRecipe(BaseModel):
    """Validates the JSON structure returned by the LLM."""

    name: str = Field(min_length=1)
    description: str = ""
    meal_type: str = Field(min_length=1)
    cuisine_type: str = "française"
    diet_type: str = "omnivore"
    prep_time_minutes: int = Field(default=30, ge=1, le=180)
    ingredients: list[_RecipeIngredient] = Field(min_length=1)
    instructions: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)

    @field_validator("ingredients")
    @classmethod
    def check_ingredients_not_empty(
        cls, v: list[_RecipeIngredient]
    ) -> list[_RecipeIngredient]:
        if not v:
            raise ValueError("Recipe must have at least one ingredient")
        return v


RECIPE_MODEL = "claude-haiku-4-5-20251001"
MAX_RECIPE_REQUEST_LENGTH = 200

# Patterns that indicate prompt injection attempts in recipe requests
_INJECTION_PATTERNS = (
    "ignore previous",
    "ignore above",
    "disregard",
    "new instructions",
    "system prompt",
    "you are now",
    "forget everything",
    "override",
    "```",
    "<script",
    "{{",
    "{%",
)

_RECIPE_PROMPT_TEMPLATE = """Tu es un nutritionniste expert. Génère une recette complète en JSON.

Demande: {recipe_request}
Type de repas: {meal_type}
Cible calorique approximative: {target_calories} kcal
Cible protéines approximative: {target_protein_g}g
Cible lipides MAXIMUM: {target_fat_g}g — LIMITER les sources de gras (huile, beurre, noix, fromage)
Cible glucides approximative: {target_carbs_g}g — privilégier riz, pâtes, pain, fruits pour les glucides
Allergènes à exclure: {allergens}
Type de régime: {diet_type}
Temps de préparation max: {max_prep_time} minutes

IMPORTANT: Ce repas a un budget lipides strict de {target_fat_g}g.
Si tu utilises des noix ou du chocolat, limiter à 15g max total.
Préférer les protéines maigres (poulet, dinde, poisson blanc, skyr, fromage blanc).

Génère un objet JSON avec exactement cette structure:
{{
  "name": "Nom de la recette en français",
  "description": "Description courte (1-2 phrases)",
  "meal_type": "{meal_type_key}",
  "cuisine_type": "française",
  "diet_type": "{diet_type}",
  "prep_time_minutes": 25,
  "ingredients": [
    {{"name": "Ingrédient", "quantity": 150, "unit": "g"}},
    {{"name": "Ingrédient 2", "quantity": 2, "unit": "pièces"}}
  ],
  "instructions": "Instructions détaillées en français.",
  "tags": ["high-protein", "quick"]
}}

RÈGLES CRITIQUES:
- Utilise UNIQUEMENT des ingrédients simples, courants et facilement trouvables
- Exclure absolument ces allergènes: {allergens}
- Respecter le régime: {diet_type}
- Quantités réalistes pour 1 personne
- Instructions claires et détaillées
- Réponds UNIQUEMENT avec le JSON, sans texte avant/après"""


async def execute(**kwargs) -> str:
    """Generate custom recipe via Claude Sonnet 4.5.

    Args:
        anthropic_client: anthropic.AsyncAnthropic client
        supabase: Supabase client (for OFF ingredient matching and DB save)
        recipe_request: Description of requested recipe
        meal_type: Display meal type ("petit-dejeuner", "dejeuner", "diner", "collation")
        target_calories: Approximate calorie target
        target_protein_g: Approximate protein target
        user_allergens: Allergens to exclude (zero tolerance)
        diet_type: Diet constraints (default "omnivore")
        max_prep_time: Max prep time in minutes (default 45)
        save_to_db: Whether to save for future reuse (default True)

    Returns:
        JSON with generated recipe including OFF-validated macros:
        {
            "recipe": {...recipe dict with macros...},
            "off_validated": bool,
            "matched_ingredients": int,
            "total_ingredients": int
        }
    """
    anthropic_client = kwargs["anthropic_client"]
    supabase = kwargs["supabase"]
    raw_request = kwargs["recipe_request"][:MAX_RECIPE_REQUEST_LENGTH]
    # Sanitize against prompt injection
    request_lower = raw_request.lower()
    for pattern in _INJECTION_PATTERNS:
        if pattern in request_lower:
            logger.warning(
                "Prompt injection attempt blocked in recipe_request: %r",
                raw_request[:80],
            )
            return json.dumps({"error": "Requête invalide", "code": "INVALID_REQUEST"})
    recipe_request = raw_request
    meal_type = kwargs.get("meal_type", "dejeuner")
    target_calories = kwargs.get("target_calories", 600)
    target_protein_g = kwargs.get("target_protein_g", 40)
    target_fat_g = kwargs.get("target_fat_g", 24)
    target_carbs_g = kwargs.get("target_carbs_g", 80)
    user_allergens = kwargs.get("user_allergens", [])
    diet_type = kwargs.get("diet_type", "omnivore")
    max_prep_time = kwargs.get("max_prep_time", 45)
    save_to_db = kwargs.get("save_to_db", True)

    try:
        logger.info(
            f"Generating custom recipe : '{recipe_request}' "
            f"(meal_type={meal_type}, target={target_calories} kcal)"
        )

        allergens_str = ", ".join(user_allergens) if user_allergens else "aucun"

        prompt = _RECIPE_PROMPT_TEMPLATE.format(
            recipe_request=recipe_request,
            meal_type=meal_type.replace("-", " "),
            meal_type_key=meal_type,
            target_calories=target_calories,
            target_protein_g=target_protein_g,
            target_fat_g=target_fat_g,
            target_carbs_g=target_carbs_g,
            allergens=allergens_str,
            diet_type=diet_type,
            max_prep_time=max_prep_time,
        )

        # Call Claude model
        message = await anthropic_client.messages.create(
            model=RECIPE_MODEL,
            max_tokens=2000,
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}],
        )

        raw_content = message.content[0].text.strip()

        # Parse JSON (strip markdown code blocks if present)
        if raw_content.startswith("```"):
            lines = raw_content.split("\n")
            raw_content = "\n".join(lines[1:-1])

        recipe_raw = json.loads(raw_content)

        # Validate required fields via Pydantic
        validated_recipe = _LLMRecipe.model_validate(recipe_raw)
        recipe_dict = validated_recipe.model_dump()

        # Validate allergens in generated recipe
        if user_allergens:
            from src.nutrition.validators import validate_allergens

            violations = validate_allergens(
                {
                    "days": [
                        {
                            "day": "generated",
                            "meals": [
                                {
                                    "name": recipe_dict.get("name", ""),
                                    "ingredients": recipe_dict.get("ingredients", []),
                                }
                            ],
                        }
                    ]
                },
                user_allergens,
            )
            if violations:
                logger.error(f"LLM generated recipe with allergens: {violations}")
                return json.dumps(
                    {
                        "error": f"Generated recipe contains allergens: {violations}",
                        "code": "ALLERGEN_VIOLATION",
                    }
                )

        # Calculate macros via OpenFoodFacts — all ingredients in parallel
        total_calories = 0.0
        total_protein = 0.0
        total_carbs = 0.0
        total_fat = 0.0
        matched_count = 0
        ingredients = recipe_dict.get("ingredients", [])

        macro_results = await asyncio.gather(
            *[
                match_ingredient(
                    ingredient_name=ing.get("name", ""),
                    quantity=ing.get("quantity", 0),
                    unit=ing.get("unit", "g"),
                    supabase=supabase,
                )
                for ing in ingredients
            ]
        )

        for ingredient, macros in zip(ingredients, macro_results):
            if macros:
                ingredient["macros_calculated"] = macros
                # Store per-100g nutrition for per-macro scaling
                if macros.get("nutrition_per_100g"):
                    ingredient["nutrition_per_100g"] = macros["nutrition_per_100g"]
                total_calories += macros.get("calories", 0)
                total_protein += macros.get("protein_g", 0)
                total_carbs += macros.get("carbs_g", 0)
                total_fat += macros.get("fat_g", 0)
                matched_count += 1
            else:
                logger.warning(
                    f"No OFF match for ingredient: {ingredient.get('name', '')}"
                )

        off_validated = matched_count == len(ingredients) and len(ingredients) > 0

        # Build the full recipe dict for DB storage
        recipe_to_save = {
            "name": recipe_dict["name"],
            "description": recipe_dict.get("description", ""),
            "meal_type": recipe_dict.get("meal_type", meal_type),
            "cuisine_type": recipe_dict.get("cuisine_type", "française"),
            "diet_type": recipe_dict.get("diet_type", diet_type),
            "tags": recipe_dict.get("tags", []),
            "ingredients": ingredients,
            "instructions": recipe_dict.get("instructions", ""),
            "prep_time_minutes": recipe_dict.get("prep_time_minutes", 30),
            "calories_per_serving": round(total_calories, 2),
            "protein_g_per_serving": round(total_protein, 2),
            "carbs_g_per_serving": round(total_carbs, 2),
            "fat_g_per_serving": round(total_fat, 2),
            "allergen_tags": [],  # Will be empty — validated to have none
            "source": "llm_generated",
            "off_validated": off_validated,
        }

        # Save to DB for future reuse
        if save_to_db:
            try:
                saved = await save_recipe(supabase, recipe_to_save)
                recipe_to_save["id"] = saved.get("id")
                logger.info(f"Custom recipe saved to DB: {recipe_to_save['name']}")
            except Exception as save_err:
                logger.warning(f"Could not save recipe to DB: {save_err}")
                # Duplicate recipe — fetch existing ID so caller can use it
                try:
                    from src.nutrition.recipe_db import normalize_ingredient_name

                    name_norm = normalize_ingredient_name(recipe_to_save["name"])
                    existing = (
                        supabase.table("recipes")
                        .select("id")
                        .eq("name_normalized", name_norm)
                        .eq("meal_type", recipe_to_save.get("meal_type", meal_type))
                        .limit(1)
                        .execute()
                    )
                    if existing.data:
                        recipe_to_save["id"] = existing.data[0]["id"]
                        logger.info(f"Found existing recipe ID: {recipe_to_save['id']}")
                except Exception as fetch_err:
                    logger.warning(f"Could not fetch existing recipe ID: {fetch_err}")

        logger.info(
            f"Custom recipe generated: '{recipe_to_save['name']}', "
            f"{recipe_to_save['calories_per_serving']} kcal, "
            f"OFF validated: {off_validated} ({matched_count}/{len(ingredients)} ingredients)"
        )

        # Build MealCard marker for generative UI
        ingredient_labels = [
            f"{ing['name']} {ing['quantity']}{ing['unit']}" for ing in ingredients
        ]
        mealcard_payload = json.dumps(
            {
                "meal_type": recipe_to_save.get("meal_type", meal_type),
                "recipe_name": recipe_to_save["name"],
                "calories": round(total_calories),
                "macros": {
                    "protein_g": round(total_protein),
                    "carbs_g": round(total_carbs),
                    "fat_g": round(total_fat),
                },
                "prep_time": recipe_to_save.get("prep_time_minutes", 30),
                "ingredients": ingredient_labels,
                "instructions": recipe_to_save.get("instructions", ""),
            },
            ensure_ascii=False,
        )
        ui_marker = f"<!--UI:MealCard:{mealcard_payload}-->"

        return json.dumps(
            {
                "recipe": recipe_to_save,
                "off_validated": off_validated,
                "matched_ingredients": matched_count,
                "total_ingredients": len(ingredients),
                "ui_marker": ui_marker,
            },
            indent=2,
            ensure_ascii=False,
        )

    except json.JSONDecodeError as e:
        logger.error(f"LLM returned invalid JSON for custom recipe: {e}")
        return json.dumps(
            {"error": "LLM returned invalid JSON", "code": "JSON_PARSE_ERROR"}
        )
    except ValueError as e:
        logger.error(f"Validation error in generate_custom_recipe: {e}")
        return json.dumps({"error": str(e), "code": "VALIDATION_ERROR"})
    except Exception as e:
        logger.error(f"Unexpected error in generate_custom_recipe: {e}", exc_info=True)
        return json.dumps({"error": "Internal error", "code": "SCRIPT_ERROR"})
