"""Edamam API adapter for recipe import pipeline.

LLM-free (rule 10). Fetches recipes from api.edamam.com/api/recipes/v2
with nutritional and dietary filters. Requires EDAMAM_APP_ID + EDAMAM_APP_KEY.
"""

import logging
import os
import re

import httpx

from scripts.recipe_sources.base import (
    UNIT_CONVERSIONS,
    RawRecipe,
    RecipeSource,
    translate_ingredient,
)

logger = logging.getLogger(__name__)

EDAMAM_BASE = "https://api.edamam.com/api/recipes/v2"


class EdamamSource(RecipeSource):
    """Fetch recipes from the Edamam Recipe API v2."""

    @property
    def name(self) -> str:
        return "edamam"

    @property
    def requires_api_key(self) -> bool:
        return True

    async def fetch_recipes(
        self,
        client: httpx.AsyncClient,
        limit: int = 50,
        **filters: str | int | float,
    ) -> list[RawRecipe]:
        """Fetch recipes from Edamam.

        Supported filters:
            query (str): search keywords
            meal_type (str): dejeuner/diner/petit-dejeuner/collation
            diet_type (str): omnivore/vegetarien/vegan
        """
        app_id = os.environ.get("EDAMAM_APP_ID", "")
        app_key = os.environ.get("EDAMAM_APP_KEY", "")
        if not app_id or not app_key:
            logger.warning("EDAMAM_APP_ID/EDAMAM_APP_KEY not set — skipping Edamam")
            return []

        params: dict[str, str] = {
            "type": "public",
            "app_id": app_id,
            "app_key": app_key,
        }

        query = str(filters.get("query", "healthy"))
        params["q"] = query

        # Diet/health filters
        diet_type = str(filters.get("diet_type", ""))
        if diet_type == "vegan":
            params["health"] = "vegan"
        elif diet_type in ("végétarien", "vegetarien"):
            params["health"] = "vegetarian"

        # Meal type mapping
        meal_type_filter = str(filters.get("meal_type", ""))
        edamam_meal_map = {
            "petit-dejeuner": "Breakfast",
            "dejeuner": "Lunch",
            "diner": "Dinner",
            "collation": "Snack",
        }
        if meal_type_filter in edamam_meal_map:
            params["mealType"] = edamam_meal_map[meal_type_filter]

        try:
            resp = await client.get(EDAMAM_BASE, params=params)
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as e:
            logger.error(f"Edamam search failed: {e}")
            return []

        hits = data.get("hits", [])[:limit]
        logger.info(f"Edamam: fetched {len(hits)} recipes")

        recipes: list[RawRecipe] = []
        for hit in hits:
            try:
                raw = self._parse_recipe(hit.get("recipe", {}), meal_type_filter)
                if raw:
                    recipes.append(raw)
            except Exception as e:
                label = hit.get("recipe", {}).get("label", "?")
                logger.warning(f"Edamam parse error for '{label}': {e}")

        return recipes

    def _parse_recipe(self, recipe: dict, meal_type_filter: str) -> RawRecipe | None:
        """Parse an Edamam recipe hit into RawRecipe."""
        label = recipe.get("label", "")
        if not label:
            return None

        servings = max(recipe.get("yield", 4), 1)

        # Parse ingredients from ingredientLines (text) using regex
        ingredients = []
        for line in recipe.get("ingredientLines", []):
            parsed = self._parse_ingredient_line(line)
            if parsed:
                # Divide by servings to get per-serving
                parsed["quantity"] = round(parsed["quantity"] / servings, 1)
                ingredients.append(parsed)

        if not ingredients:
            return None

        # Instructions — Edamam doesn't provide them, use placeholder
        instructions = "Voir la recette originale."

        # Meal type
        meal_type = meal_type_filter or "dejeuner"
        meal_types_raw = recipe.get("mealType", [])
        if not meal_type_filter and meal_types_raw:
            mt = meal_types_raw[0].lower()
            if "breakfast" in mt:
                meal_type = "petit-dejeuner"
            elif "snack" in mt:
                meal_type = "collation"
            elif "lunch" in mt:
                meal_type = "dejeuner"
            elif "dinner" in mt:
                meal_type = "diner"

        # Diet type
        diet_type = "omnivore"
        health_labels = [h.lower() for h in recipe.get("healthLabels", [])]
        if "vegan" in health_labels:
            diet_type = "vegan"
        elif "vegetarian" in health_labels:
            diet_type = "végétarien"

        # Cuisine
        cuisine_types = recipe.get("cuisineType", [])
        cuisine = cuisine_types[0].lower() if cuisine_types else "internationale"

        # Tags from diet/health labels
        tags = [d.lower() for d in recipe.get("dietLabels", [])]

        return RawRecipe(
            name=label,
            ingredients=ingredients,
            instructions=instructions,
            meal_type=meal_type,
            cuisine_type=cuisine,
            diet_type=diet_type,
            prep_time_minutes=int(recipe.get("totalTime", 30)) or 30,
            tags=tags,
            source="edamam",
            source_url=recipe.get("url", ""),
        )

    def _parse_ingredient_line(self, line: str) -> dict | None:
        """Parse a free-text ingredient line into structured dict.

        Examples:
            "2 tablespoons olive oil" -> {"name": "huile d'olive", "quantity": 30, "unit": "ml"}
            "1 cup diced chicken" -> {"name": "poulet", "quantity": 240, "unit": "ml"}
            "3 large eggs" -> {"name": "oeufs", "quantity": 3, "unit": "pièces"}
        """
        line = line.strip()
        if not line:
            return None

        # Try to extract: number [fraction] unit rest
        pattern = r"^([\d./]+(?:\s+[\d./]+)?)\s+(.*)"
        m = re.match(pattern, line)

        if not m:
            # No number — treat as a single item
            name = translate_ingredient(line)
            return {"name": name, "quantity": 100.0, "unit": "g"}

        num_str = m.group(1).strip()
        rest = m.group(2).strip()

        # Parse number (handle fractions like "1/2" or "1 1/2")
        qty = self._parse_number(num_str)

        # Try to match a unit at the start of rest
        unit_found = ""
        unit_metric = "g"
        unit_factor = 1.0

        rest_lower = rest.lower()
        for unit_name, (factor, metric) in sorted(
            UNIT_CONVERSIONS.items(), key=lambda x: -len(x[0])
        ):
            if rest_lower.startswith(unit_name):
                unit_found = unit_name
                unit_factor = factor
                unit_metric = metric
                rest = rest[len(unit_name) :].strip()
                break

        # Also check simple units
        simple_units = {"g": ("g", 1.0), "ml": ("ml", 1.0), "kg": ("g", 1000.0)}
        if not unit_found:
            for u, (met, fac) in simple_units.items():
                if rest_lower.startswith(u + " ") or rest_lower == u:
                    unit_found = u
                    unit_metric = met
                    unit_factor = fac
                    rest = rest[len(u) :].strip()
                    break

        # Clean up the ingredient name — remove "of", "de", leading adjectives
        name = re.sub(r"^(of|de|d')\s+", "", rest.strip())
        # Remove parenthetical notes
        name = re.sub(r"\(.*?\)", "", name).strip()
        # Remove trailing commas/adjectives like "finely chopped"
        name = re.sub(
            r",?\s*(finely |roughly |freshly |thinly )?(chopped|diced|sliced|minced|grated|crushed|peeled|torn|trimmed).*$",
            "",
            name,
            flags=re.IGNORECASE,
        ).strip()

        if not name:
            return None

        translated = translate_ingredient(name)

        if unit_found:
            return {
                "name": translated,
                "quantity": round(qty * unit_factor, 1),
                "unit": unit_metric,
            }

        # No unit found — treat as pieces if small number, else grams
        if qty < 10:
            return {"name": translated, "quantity": round(qty, 1), "unit": "pièces"}
        return {"name": translated, "quantity": round(qty, 1), "unit": "g"}

    @staticmethod
    def _parse_number(s: str) -> float:
        """Parse a number string that may contain fractions."""
        parts = s.split()
        total = 0.0
        for part in parts:
            if "/" in part:
                try:
                    num, den = part.split("/")
                    total += float(num) / float(den)
                except (ValueError, ZeroDivisionError):
                    pass
            else:
                try:
                    total += float(part)
                except ValueError:
                    pass
        return total if total > 0 else 1.0
