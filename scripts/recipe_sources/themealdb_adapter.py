"""TheMealDB API adapter for recipe import pipeline.

LLM-free (rule 10). Thin wrapper around TheMealDB free API (themealdb.com).
No API key required. Fetches by category, maps to RawRecipe format.
"""

import asyncio
import logging

import httpx

from scripts.recipe_sources.base import (
    RawRecipe,
    RecipeSource,
    parse_measure,
    translate_ingredient,
)

logger = logging.getLogger(__name__)

THEMEALDB_BASE = "https://www.themealdb.com/api/json/v1/1"

# Categories worth importing
RELEVANT_CATEGORIES = {
    "Beef",
    "Chicken",
    "Lamb",
    "Pasta",
    "Pork",
    "Seafood",
    "Vegan",
    "Vegetarian",
    "Breakfast",
}

CATEGORY_TO_MEAL_TYPE: dict[str, str] = {
    "Breakfast": "petit-dejeuner",
}


class TheMealDBSource(RecipeSource):
    """Fetch recipes from TheMealDB free API."""

    @property
    def name(self) -> str:
        return "themealdb"

    @property
    def requires_api_key(self) -> bool:
        return False

    async def fetch_recipes(
        self,
        client: httpx.AsyncClient,
        limit: int = 50,
        **filters: str | int | float,
    ) -> list[RawRecipe]:
        """Fetch recipes from TheMealDB by category.

        Supported filters:
            meal_type (str): dejeuner/diner/petit-dejeuner
            diet_type (str): omnivore/vegetarien/vegan
        """
        try:
            resp = await client.get(f"{THEMEALDB_BASE}/categories.php")
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as e:
            logger.error(f"TheMealDB categories fetch failed: {e}")
            return []

        categories = [
            c["strCategory"]
            for c in data.get("categories", [])
            if c["strCategory"] in RELEVANT_CATEGORIES
        ]

        # Filter by diet_type if requested
        diet_filter = str(filters.get("diet_type", ""))
        if diet_filter == "vegan":
            categories = [c for c in categories if c == "Vegan"]
        elif diet_filter in ("végétarien", "vegetarien"):
            categories = [c for c in categories if c in ("Vegetarian", "Vegan")]

        # Filter by meal_type
        meal_type_filter = str(filters.get("meal_type", ""))
        if meal_type_filter == "petit-dejeuner":
            categories = [c for c in categories if c == "Breakfast"]
        elif meal_type_filter in ("dejeuner", "diner"):
            categories = [c for c in categories if c != "Breakfast"]

        if not categories:
            logger.info("TheMealDB: no matching categories")
            return []

        # Collect meal IDs across categories
        all_meals: list[tuple[dict, str]] = []
        for category in categories:
            try:
                resp = await client.get(
                    f"{THEMEALDB_BASE}/filter.php", params={"c": category}
                )
                resp.raise_for_status()
                meals = resp.json().get("meals") or []
                for m in meals:
                    all_meals.append((m, category))
            except (httpx.HTTPError, ValueError) as e:
                logger.warning(f"TheMealDB category '{category}' fetch failed: {e}")

            await asyncio.sleep(0.3)

        # Limit evenly across categories
        if len(all_meals) > limit:
            per_cat = max(1, limit // len(categories))
            limited: list[tuple[dict, str]] = []
            cat_counts: dict[str, int] = {}
            for m, cat in all_meals:
                cat_counts.setdefault(cat, 0)
                if cat_counts[cat] < per_cat and len(limited) < limit:
                    limited.append((m, cat))
                    cat_counts[cat] += 1
            all_meals = limited

        logger.info(f"TheMealDB: fetching details for {len(all_meals)} meals")

        recipes: list[RawRecipe] = []
        for meal_summary, category in all_meals:
            meal_id = meal_summary.get("idMeal")
            try:
                resp = await client.get(
                    f"{THEMEALDB_BASE}/lookup.php", params={"i": meal_id}
                )
                resp.raise_for_status()
                meal_data = resp.json().get("meals")
                if not meal_data:
                    continue
                meal = meal_data[0]

                raw = self._parse_meal(meal, category, meal_type_filter)
                if raw:
                    recipes.extend(raw)

            except (httpx.HTTPError, ValueError) as e:
                logger.warning(
                    f"TheMealDB detail fetch failed for {meal_summary.get('strMeal', '?')}: {e}"
                )

            await asyncio.sleep(0.3)

        return recipes

    def _parse_meal(
        self, meal: dict, category: str, meal_type_filter: str
    ) -> list[RawRecipe]:
        """Parse TheMealDB meal into RawRecipe(s)."""
        name = meal.get("strMeal", "")
        if not name:
            return []

        # Extract ingredients (strIngredient1..20 + strMeasure1..20)
        ingredients = []
        for i in range(1, 21):
            ing_name = (meal.get(f"strIngredient{i}") or "").strip()
            measure = (meal.get(f"strMeasure{i}") or "").strip()
            if not ing_name:
                break
            quantity, unit = parse_measure(measure)
            ingredients.append(
                {
                    "name": translate_ingredient(ing_name),
                    "quantity": round(quantity, 1),
                    "unit": unit,
                }
            )

        if not ingredients:
            return []

        instructions = meal.get("strInstructions") or ""
        tags = [t.strip() for t in (meal.get("strTags") or "").split(",") if t.strip()]
        cuisine = (meal.get("strArea") or "internationale").lower()

        # Diet type from category
        diet_type = "omnivore"
        if category == "Vegan":
            diet_type = "vegan"
        elif category == "Vegetarian":
            diet_type = "végétarien"

        # Meal types
        if meal_type_filter:
            meal_types = [meal_type_filter]
        elif category in CATEGORY_TO_MEAL_TYPE:
            meal_types = [CATEGORY_TO_MEAL_TYPE[category]]
        else:
            meal_types = ["dejeuner", "diner"]

        return [
            RawRecipe(
                name=name,
                ingredients=ingredients,
                instructions=instructions,
                meal_type=mt,
                cuisine_type=cuisine,
                diet_type=diet_type,
                prep_time_minutes=30,
                tags=tags,
                source="themealdb",
                source_url=f"https://www.themealdb.com/meal/{meal.get('idMeal', '')}",
            )
            for mt in meal_types
        ]
