"""AllRecipes scraping adapter for recipe import pipeline.

LLM-free (rule 10). Scrapes recipes from allrecipes.com using BeautifulSoup.
Prefers JSON-LD structured data when available. No API key required.
Rate-limited to 1 req / 2 sec. Translates English ingredients to French.
"""

import asyncio
import json
import logging
import re

import httpx
from bs4 import BeautifulSoup

from scripts.recipe_sources.base import (
    RawRecipe,
    RecipeSource,
    parse_measure,
    translate_ingredient,
)

logger = logging.getLogger(__name__)

ALLRECIPES_BASE = "https://www.allrecipes.com"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class AllRecipesSource(RecipeSource):
    """Scrape recipes from AllRecipes.com using JSON-LD when available."""

    @property
    def name(self) -> str:
        return "allrecipes"

    @property
    def requires_api_key(self) -> bool:
        return False

    async def fetch_recipes(
        self,
        client: httpx.AsyncClient,
        limit: int = 50,
        **filters: str | int | float,
    ) -> list[RawRecipe]:
        """Fetch recipes from AllRecipes via search + page scraping.

        Supported filters:
            query (str): search keywords (default: "lean protein meals")
            meal_type (str): target meal type
            diet_type (str): diet type hint
        """
        query = str(filters.get("query", "lean protein meals"))
        meal_type_filter = str(filters.get("meal_type", ""))
        diet_type_filter = str(filters.get("diet_type", ""))

        headers = {"User-Agent": USER_AGENT}

        try:
            resp = await client.get(
                f"{ALLRECIPES_BASE}/search",
                params={"q": query},
                headers=headers,
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.error(f"AllRecipes search failed: {e}")
            return []

        soup = BeautifulSoup(resp.text, "lxml")

        # Extract recipe links
        links: list[str] = []
        for a in soup.select("a[href*='/recipe/']"):
            href = a.get("href", "")
            if href and href not in links and "/recipe/" in href:
                full = href if href.startswith("http") else f"{ALLRECIPES_BASE}{href}"
                links.append(full)
            if len(links) >= limit:
                break

        logger.info(f"AllRecipes: found {len(links)} recipe links for '{query}'")

        recipes: list[RawRecipe] = []
        for url in links[:limit]:
            try:
                raw = await self._scrape_recipe(
                    client, url, headers, meal_type_filter, diet_type_filter
                )
                if raw:
                    recipes.append(raw)
            except Exception as e:
                logger.warning(f"AllRecipes scrape error for {url}: {e}")

            await asyncio.sleep(2.0)

        return recipes

    async def _scrape_recipe(
        self,
        client: httpx.AsyncClient,
        url: str,
        headers: dict[str, str],
        meal_type_filter: str,
        diet_type_filter: str,
    ) -> RawRecipe | None:
        """Scrape a single recipe page — prefer JSON-LD, fallback to HTML."""
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # Try JSON-LD first (more reliable)
        raw = self._parse_json_ld(soup, url, meal_type_filter, diet_type_filter)
        if raw:
            return raw

        # Fallback to HTML parsing
        return self._parse_html(soup, url, meal_type_filter, diet_type_filter)

    def _parse_json_ld(
        self,
        soup: BeautifulSoup,
        url: str,
        meal_type_filter: str,
        diet_type_filter: str,
    ) -> RawRecipe | None:
        """Parse recipe from JSON-LD script tag."""
        for script in soup.select('script[type="application/ld+json"]'):
            try:
                data = json.loads(script.string or "")
            except (json.JSONDecodeError, TypeError):
                continue

            # Handle both single object and array
            items = data if isinstance(data, list) else [data]
            for item in items:
                if item.get("@type") == "Recipe":
                    return self._build_from_jsonld(
                        item, url, meal_type_filter, diet_type_filter
                    )

        return None

    def _build_from_jsonld(
        self,
        data: dict,
        url: str,
        meal_type_filter: str,
        diet_type_filter: str,
    ) -> RawRecipe | None:
        """Build RawRecipe from JSON-LD Recipe data."""
        name = data.get("name", "")
        if not name:
            return None

        servings = 1
        yield_str = data.get("recipeYield", "")
        if isinstance(yield_str, list):
            yield_str = yield_str[0] if yield_str else ""
        m = re.search(r"(\d+)", str(yield_str))
        if m:
            servings = max(int(m.group(1)), 1)

        # Ingredients
        ingredients = []
        for line in data.get("recipeIngredient", []):
            parsed = self._parse_ingredient_line(str(line))
            if parsed:
                # Divide by servings
                parsed["quantity"] = round(parsed["quantity"] / servings, 1)
                ingredients.append(parsed)

        if not ingredients:
            return None

        # Instructions
        instructions_data = data.get("recipeInstructions", [])
        steps: list[str] = []
        for item in instructions_data:
            if isinstance(item, str):
                steps.append(item)
            elif isinstance(item, dict):
                steps.append(item.get("text", ""))
        instructions = " ".join(s for s in steps if s)
        if not instructions:
            instructions = "See original recipe."

        # Prep time from ISO 8601 duration
        prep_time = self._parse_iso_duration(data.get("prepTime", ""))
        cook_time = self._parse_iso_duration(data.get("cookTime", ""))
        total_time = prep_time + cook_time or 30

        # Meal type
        meal_type = meal_type_filter or self._infer_meal_type(name, url)

        # Diet type
        diet_type = diet_type_filter or self._infer_diet_type(name, ingredients)

        # Category/cuisine
        category = data.get("recipeCategory", "")
        cuisine_list = data.get("recipeCuisine", [])
        if isinstance(cuisine_list, str):
            cuisine_list = [cuisine_list]
        cuisine = cuisine_list[0].lower() if cuisine_list else "américaine"

        tags = []
        if isinstance(category, list):
            tags = [c.lower() for c in category]
        elif category:
            tags = [category.lower()]

        return RawRecipe(
            name=name,
            ingredients=ingredients,
            instructions=instructions,
            meal_type=meal_type,
            cuisine_type=cuisine,
            diet_type=diet_type,
            prep_time_minutes=total_time,
            tags=tags,
            source="allrecipes",
            source_url=url,
        )

    def _parse_html(
        self,
        soup: BeautifulSoup,
        url: str,
        meal_type_filter: str,
        diet_type_filter: str,
    ) -> RawRecipe | None:
        """Fallback HTML parsing for AllRecipes."""
        title_tag = soup.select_one("h1")
        if not title_tag:
            return None
        title = title_tag.get_text(strip=True)
        if not title:
            return None

        # Ingredients
        ingredients: list[dict] = []
        ing_items = soup.select(
            "ul.mntl-structured-ingredients__list li"
        ) or soup.select("[class*='ingredient'] li")
        for item in ing_items:
            text = item.get_text(" ", strip=True)
            if text:
                parsed = self._parse_ingredient_line(text)
                if parsed:
                    ingredients.append(parsed)

        if not ingredients:
            return None

        # Instructions
        steps: list[str] = []
        step_items = soup.select("[class*='step'] p") or soup.select(
            ".recipe__steps li"
        )
        for item in step_items:
            text = item.get_text(strip=True)
            if text:
                steps.append(text)
        instructions = " ".join(steps) if steps else "See original recipe."

        meal_type = meal_type_filter or self._infer_meal_type(title, url)
        diet_type = diet_type_filter or self._infer_diet_type(title, ingredients)

        return RawRecipe(
            name=title,
            ingredients=ingredients,
            instructions=instructions,
            meal_type=meal_type,
            cuisine_type="américaine",
            diet_type=diet_type,
            prep_time_minutes=30,
            tags=[],
            source="allrecipes",
            source_url=url,
        )

    def _parse_ingredient_line(self, line: str) -> dict | None:
        """Parse an English ingredient line and translate to French."""
        line = line.strip()
        if not line:
            return None

        # Extract number + rest
        m = re.match(r"^([\d.,/½¼¾⅓⅔]+(?:\s+[\d.,/½¼¾⅓⅔]+)?)\s+(.*)", line)
        if m:
            qty_str = m.group(1)
            rest = m.group(2).strip()

            qty = self._parse_qty(qty_str)
            quantity, unit = parse_measure(f"{qty} {rest}")

            # Clean name
            name = re.sub(
                r"^(g|ml|kg|oz|lb|cups?|tbsp|tsp|tablespoons?|teaspoons?|ounces?|pounds?)\s*(of)?\s*",
                "",
                rest,
                flags=re.IGNORECASE,
            ).strip()
            name = re.sub(
                r",?\s*(finely |roughly |freshly |thinly )?(chopped|diced|sliced|minced|grated|crushed|peeled|trimmed).*$",
                "",
                name,
                flags=re.IGNORECASE,
            ).strip()
            # Remove parenthetical notes
            name = re.sub(r"\(.*?\)", "", name).strip()

            if not name:
                return None

            translated = translate_ingredient(name)
            return {
                "name": translated,
                "quantity": round(quantity, 1),
                "unit": unit,
            }

        # No quantity
        translated = translate_ingredient(line)
        return {"name": translated, "quantity": 100.0, "unit": "g"}

    @staticmethod
    def _parse_qty(s: str) -> float:
        """Parse quantity with Unicode fractions."""
        frac_map = {"½": 0.5, "¼": 0.25, "¾": 0.75, "⅓": 0.333, "⅔": 0.667}
        for char, val in frac_map.items():
            if char in s:
                s = s.replace(char, "")
                try:
                    return float(s.strip() or "0") + val
                except ValueError:
                    return val

        s = s.replace(",", ".")
        parts = s.split()
        total = 0.0
        for part in parts:
            if "/" in part:
                try:
                    n, d = part.split("/")
                    total += float(n) / float(d)
                except (ValueError, ZeroDivisionError):
                    pass
            else:
                try:
                    total += float(part)
                except ValueError:
                    pass
        return total if total > 0 else 1.0

    @staticmethod
    def _parse_iso_duration(s: str) -> int:
        """Parse ISO 8601 duration (PT30M, PT1H30M) to minutes."""
        if not s:
            return 0
        hours = 0
        minutes = 0
        m_h = re.search(r"(\d+)H", s)
        m_m = re.search(r"(\d+)M", s)
        if m_h:
            hours = int(m_h.group(1))
        if m_m:
            minutes = int(m_m.group(1))
        return hours * 60 + minutes

    def _infer_meal_type(self, title: str, url: str) -> str:
        """Infer meal type from title/URL."""
        text = f"{title} {url}".lower()
        if any(kw in text for kw in ["breakfast", "brunch", "pancake"]):
            return "petit-dejeuner"
        if any(kw in text for kw in ["snack", "appetizer"]):
            return "collation"
        return "dejeuner"

    def _infer_diet_type(self, title: str, ingredients: list[dict]) -> str:
        """Infer diet type."""
        t = title.lower()
        if "vegan" in t:
            return "vegan"
        if "vegetarian" in t or "veggie" in t:
            return "végétarien"

        all_ings = " ".join(i.get("name", "").lower() for i in ingredients)
        meat = [
            "poulet",
            "boeuf",
            "porc",
            "agneau",
            "dinde",
            "canard",
            "saumon",
            "thon",
            "crevette",
            "poisson",
            "chicken",
            "beef",
            "pork",
            "lamb",
            "salmon",
            "tuna",
        ]
        if any(kw in all_ings for kw in meat):
            return "omnivore"
        return "omnivore"
