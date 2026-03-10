"""Spoonacular API adapter for recipe import pipeline.

LLM-free (rule 10). Fetches recipes from api.spoonacular.com using
complexSearch with macro filters. Requires SPOONACULAR_API_KEY env var.
"""

import asyncio
import logging
import os

import httpx

from scripts.recipe_sources.base import (
    RawRecipe,
    RecipeSource,
    normalize_unit,
    translate_ingredient,
)

logger = logging.getLogger(__name__)

SPOONACULAR_BASE = "https://api.spoonacular.com"


class SpoonacularSource(RecipeSource):
    """Fetch recipes from the Spoonacular API."""

    @property
    def name(self) -> str:
        return "spoonacular"

    @property
    def requires_api_key(self) -> bool:
        return True

    async def fetch_recipes(
        self,
        client: httpx.AsyncClient,
        limit: int = 50,
        **filters: str | int | float,
    ) -> list[RawRecipe]:
        """Fetch recipes from Spoonacular complexSearch.

        Supported filters:
            query (str): search keywords
            meal_type (str): dejeuner/diner/petit-dejeuner/collation
            diet_type (str): omnivore/vegetarien/vegan
            min_protein_pct (int): minimum protein %
            max_fat_pct (int): maximum fat %
        """
        api_key = os.environ.get("SPOONACULAR_API_KEY", "")
        if not api_key:
            logger.warning("SPOONACULAR_API_KEY not set — skipping Spoonacular")
            return []

        params: dict[str, str | int] = {
            "apiKey": api_key,
            "number": min(limit, 100),
            "addRecipeNutrition": "true",
            "addRecipeInstructions": "true",
            "instructionsRequired": "true",
            "fillIngredients": "true",
        }

        # Query
        query = filters.get("query", "")
        if query:
            params["query"] = str(query)

        # Macro filters
        min_prot = filters.get("min_protein_pct")
        if min_prot:
            params["minProteinPercent"] = int(min_prot)
        max_fat = filters.get("max_fat_pct")
        if max_fat:
            params["maxFatPercent"] = int(max_fat)

        # Diet type mapping
        diet_type = str(filters.get("diet_type", ""))
        if diet_type in ("vegan",):
            params["diet"] = "vegan"
        elif diet_type in ("végétarien", "vegetarien"):
            params["diet"] = "vegetarian"

        # Meal type mapping
        meal_type_filter = str(filters.get("meal_type", ""))
        spoon_type_map = {
            "petit-dejeuner": "breakfast",
            "dejeuner": "main course",
            "diner": "main course",
            "collation": "snack",
        }
        if meal_type_filter in spoon_type_map:
            params["type"] = spoon_type_map[meal_type_filter]

        try:
            resp = await client.get(
                f"{SPOONACULAR_BASE}/recipes/complexSearch", params=params
            )
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as e:
            logger.error(f"Spoonacular search failed: {e}")
            return []

        results = data.get("results", [])
        logger.info(f"Spoonacular: fetched {len(results)} recipes")

        recipes: list[RawRecipe] = []
        for item in results:
            try:
                raw = self._parse_recipe(item, meal_type_filter)
                if raw:
                    recipes.append(raw)
            except Exception as e:
                logger.warning(
                    f"Spoonacular parse error for '{item.get('title', '?')}': {e}"
                )

            # Rate limit
            await asyncio.sleep(0.5)

        return recipes

    def _parse_recipe(self, item: dict, meal_type_filter: str) -> RawRecipe | None:
        """Parse a Spoonacular recipe result into RawRecipe."""
        title = item.get("title", "")
        if not title:
            return None

        # Parse ingredients
        ingredients = []
        for ing in item.get("extendedIngredients", []):
            metric = ing.get("measures", {}).get("metric", {})
            qty = metric.get("amount", ing.get("amount", 100))
            unit_str = metric.get("unitShort", ing.get("unit", "g"))
            name_en = ing.get("name", "")
            if not name_en:
                continue

            # Normalize unit
            unit_norm = normalize_unit(unit_str) if unit_str else "g"
            # Convert if unit is a volume/weight conversion
            from scripts.recipe_sources.base import UNIT_CONVERSIONS

            unit_lower = unit_str.lower().strip() if unit_str else ""
            if unit_lower in UNIT_CONVERSIONS:
                factor, metric_unit = UNIT_CONVERSIONS[unit_lower]
                qty = qty * factor
                unit_norm = metric_unit

            ingredients.append(
                {
                    "name": translate_ingredient(name_en),
                    "quantity": round(float(qty), 1),
                    "unit": unit_norm,
                }
            )

        if not ingredients:
            return None

        # Instructions
        instructions = ""
        analyzed = item.get("analyzedInstructions", [])
        if analyzed:
            steps = analyzed[0].get("steps", [])
            instructions = " ".join(s.get("step", "") for s in steps)
        if not instructions:
            instructions = item.get("instructions") or ""

        # Determine meal type
        meal_type = meal_type_filter or "dejeuner"
        dish_types = [dt.lower() for dt in item.get("dishTypes", [])]
        if not meal_type_filter:
            if "breakfast" in dish_types:
                meal_type = "petit-dejeuner"
            elif "snack" in dish_types or "appetizer" in dish_types:
                meal_type = "collation"
            else:
                meal_type = "dejeuner"

        # Diet type
        diet_type = "omnivore"
        if item.get("vegan"):
            diet_type = "vegan"
        elif item.get("vegetarian"):
            diet_type = "végétarien"

        # Cuisine
        cuisines = item.get("cuisines", [])
        cuisine_type = cuisines[0].lower() if cuisines else "internationale"

        return RawRecipe(
            name=title,
            ingredients=ingredients,
            instructions=instructions,
            meal_type=meal_type,
            cuisine_type=cuisine_type,
            diet_type=diet_type,
            prep_time_minutes=item.get("readyInMinutes", 30),
            tags=[t.lower() for t in item.get("dishTypes", [])],
            source="spoonacular",
            source_url=item.get("sourceUrl", ""),
        )
