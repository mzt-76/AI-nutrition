"""BBC Good Food scraping adapter for recipe import pipeline.

LLM-free (rule 10). Scrapes recipes from bbcgoodfood.com using BeautifulSoup.
No API key required. Rate-limited to 1 req / 2 sec.
Translates English ingredients to French.
"""

import asyncio
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

BBC_BASE = "https://www.bbcgoodfood.com"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class BBCGoodFoodSource(RecipeSource):
    """Scrape recipes from BBC Good Food."""

    @property
    def name(self) -> str:
        return "bbcgoodfood"

    @property
    def requires_api_key(self) -> bool:
        return False

    async def fetch_recipes(
        self,
        client: httpx.AsyncClient,
        limit: int = 50,
        **filters: str | int | float,
    ) -> list[RawRecipe]:
        """Fetch recipes from BBC Good Food via search + page scraping.

        Supported filters:
            query (str): search keywords (default: "healthy high protein")
            meal_type (str): target meal type
            diet_type (str): diet type hint
        """
        query = str(filters.get("query", "healthy high protein"))
        meal_type_filter = str(filters.get("meal_type", ""))
        diet_type_filter = str(filters.get("diet_type", ""))

        headers = {"User-Agent": USER_AGENT}

        try:
            resp = await client.get(
                f"{BBC_BASE}/search",
                params={"q": query},
                headers=headers,
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.error(f"BBC Good Food search failed: {e}")
            return []

        soup = BeautifulSoup(resp.text, "lxml")

        # Extract recipe links
        links: list[str] = []
        for a in soup.select("a[href*='/recipes/']"):
            href = a.get("href", "")
            if href and href not in links and "/recipes/" in href:
                full = href if href.startswith("http") else f"{BBC_BASE}{href}"
                links.append(full)
            if len(links) >= limit:
                break

        logger.info(f"BBC Good Food: found {len(links)} recipe links for '{query}'")

        recipes: list[RawRecipe] = []
        for url in links[:limit]:
            try:
                raw = await self._scrape_recipe(
                    client, url, headers, meal_type_filter, diet_type_filter
                )
                if raw:
                    recipes.append(raw)
            except Exception as e:
                logger.warning(f"BBC Good Food scrape error for {url}: {e}")

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
        """Scrape a single recipe page from BBC Good Food."""
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # Title
        title_tag = soup.select_one("h1")
        if not title_tag:
            return None
        title = title_tag.get_text(strip=True)
        if not title:
            return None

        # Ingredients — translate EN -> FR
        ingredients = self._parse_ingredients(soup)
        if not ingredients:
            return None

        # Instructions
        instructions = self._parse_instructions(soup)

        # Prep time
        prep_time = self._parse_prep_time(soup)

        # Meal type
        meal_type = meal_type_filter or self._infer_meal_type(title, url)

        # Diet type
        diet_type = diet_type_filter or self._infer_diet_type(title, ingredients)

        return RawRecipe(
            name=title,
            ingredients=ingredients,
            instructions=instructions,
            meal_type=meal_type,
            cuisine_type="anglaise",
            diet_type=diet_type,
            prep_time_minutes=prep_time,
            tags=[],
            source="bbcgoodfood",
            source_url=url,
        )

    def _parse_ingredients(self, soup: BeautifulSoup) -> list[dict]:
        """Extract and translate ingredients from a BBC Good Food recipe page."""
        ingredients: list[dict] = []

        # BBC Good Food uses structured ingredient lists
        ing_items = soup.select(".recipe__ingredients li") or soup.select(
            "[class*='ingredient'] li"
        )

        for item in ing_items:
            text = item.get_text(" ", strip=True)
            if not text or len(text) < 2:
                continue
            parsed = self._parse_and_translate(text)
            if parsed:
                ingredients.append(parsed)

        return ingredients

    def _parse_and_translate(self, text: str) -> dict | None:
        """Parse an English ingredient line and translate to French."""
        text = text.strip()
        if not text:
            return None

        # Extract quantity + unit + name
        m = re.match(r"^([\d.,/½¼¾⅓⅔]+)\s*(.*)", text)
        if m:
            qty_str = m.group(1)
            rest = m.group(2).strip()

            qty = self._parse_qty(qty_str)
            quantity, unit = parse_measure(f"{qty} {rest}")

            # Extract ingredient name — remove unit words from rest
            name = re.sub(
                r"^(g|ml|kg|oz|lb|cup|cups|tbsp|tsp|tablespoons?|teaspoons?|ounces?|pounds?)\s*(of)?\s*",
                "",
                rest,
                flags=re.IGNORECASE,
            ).strip()
            # Remove prep instructions
            name = re.sub(
                r",?\s*(finely |roughly |freshly |thinly )?(chopped|diced|sliced|minced|grated|crushed|peeled|torn|trimmed|halved|quartered).*$",
                "",
                name,
                flags=re.IGNORECASE,
            ).strip()

            translated = translate_ingredient(name) if name else name
            return {
                "name": translated,
                "quantity": round(quantity, 1),
                "unit": unit,
            }

        # No quantity — translate name, assume 100g
        translated = translate_ingredient(text)
        return {"name": translated, "quantity": 100.0, "unit": "g"}

    @staticmethod
    def _parse_qty(s: str) -> float:
        """Parse quantity string with Unicode fractions."""
        # Replace Unicode fractions
        frac_map = {"½": 0.5, "¼": 0.25, "¾": 0.75, "⅓": 0.333, "⅔": 0.667}
        for char, val in frac_map.items():
            if char in s:
                s = s.replace(char, "")
                try:
                    return float(s.strip() or "0") + val
                except ValueError:
                    return val

        s = s.replace(",", ".")
        if "/" in s:
            try:
                parts = s.split("/")
                return float(parts[0]) / float(parts[1])
            except (ValueError, ZeroDivisionError):
                return 1.0
        try:
            return float(s)
        except ValueError:
            return 1.0

    def _parse_instructions(self, soup: BeautifulSoup) -> str:
        """Extract instructions from a BBC Good Food recipe page."""
        steps: list[str] = []
        step_items = soup.select(".recipe__method-steps li p") or soup.select(
            "[class*='method'] li"
        )
        for item in step_items:
            text = item.get_text(strip=True)
            if text:
                steps.append(text)
        return " ".join(steps) if steps else "See original recipe."

    def _parse_prep_time(self, soup: BeautifulSoup) -> int:
        """Extract prep time in minutes."""
        for tag in soup.select("[class*='time'], [class*='cook-and-prep']"):
            text = tag.get_text(strip=True)
            m = re.search(r"(\d+)\s*min", text)
            if m:
                return int(m.group(1))
            # Hours
            m_hrs = re.search(r"(\d+)\s*hr", text)
            if m_hrs:
                return int(m_hrs.group(1)) * 60
        return 30

    def _infer_meal_type(self, title: str, url: str) -> str:
        """Infer meal type from title/URL."""
        text = f"{title} {url}".lower()
        if any(kw in text for kw in ["breakfast", "brunch", "pancake", "porridge"]):
            return "petit-dejeuner"
        if any(kw in text for kw in ["snack", "energy ball", "bar"]):
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
            "prawn",
        ]
        if any(kw in all_ings for kw in meat):
            return "omnivore"
        return "omnivore"
