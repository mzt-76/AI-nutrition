"""Marmiton scraping adapter for recipe import pipeline.

LLM-free (rule 10). Scrapes recipes from marmiton.org using BeautifulSoup.
No API key required. Rate-limited to 1 req / 2 sec.
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
)

logger = logging.getLogger(__name__)

MARMITON_BASE = "https://www.marmiton.org"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Meal type inference from title/tags keywords
BREAKFAST_KEYWORDS = [
    "petit-déjeuner",
    "petit déjeuner",
    "breakfast",
    "brunch",
    "pancake",
    "crêpe",
    "porridge",
    "granola",
    "muesli",
]
SNACK_KEYWORDS = [
    "collation",
    "snack",
    "goûter",
    "encas",
    "smoothie",
    "barre",
    "energy ball",
]


class MarmitonSource(RecipeSource):
    """Scrape recipes from Marmiton.org."""

    @property
    def name(self) -> str:
        return "marmiton"

    @property
    def requires_api_key(self) -> bool:
        return False

    async def fetch_recipes(
        self,
        client: httpx.AsyncClient,
        limit: int = 50,
        **filters: str | int | float,
    ) -> list[RawRecipe]:
        """Fetch recipes from Marmiton via search + page scraping.

        Supported filters:
            query (str): search keywords (default: "recette saine")
            meal_type (str): target meal type for categorization
            diet_type (str): filter hint for diet categorization
        """
        query = str(filters.get("query", "recette saine protéinée"))
        meal_type_filter = str(filters.get("meal_type", ""))
        diet_type_filter = str(filters.get("diet_type", ""))

        headers = {"User-Agent": USER_AGENT}

        # Search for recipes
        search_url = f"{MARMITON_BASE}/recettes/recherche.aspx"
        try:
            resp = await client.get(search_url, params={"aqt": query}, headers=headers)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.error(f"Marmiton search failed: {e}")
            return []

        soup = BeautifulSoup(resp.text, "lxml")

        # Extract recipe links from search results
        links: list[str] = []
        for a in soup.select("a[href*='/recettes/recette_']"):
            href = a.get("href", "")
            if href and href not in links:
                full_url = href if href.startswith("http") else f"{MARMITON_BASE}{href}"
                links.append(full_url)
            if len(links) >= limit:
                break

        logger.info(f"Marmiton: found {len(links)} recipe links for '{query}'")

        recipes: list[RawRecipe] = []
        for url in links[:limit]:
            try:
                raw = await self._scrape_recipe(
                    client, url, headers, meal_type_filter, diet_type_filter
                )
                if raw:
                    recipes.append(raw)
            except Exception as e:
                logger.warning(f"Marmiton scrape error for {url}: {e}")

            # Rate limit: 1 req / 2 sec
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
        """Scrape a single recipe page from Marmiton."""
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

        # Ingredients — Marmiton uses various selectors
        ingredients = self._parse_ingredients(soup)
        if not ingredients:
            return None

        # Instructions
        instructions = self._parse_instructions(soup)

        # Prep time
        prep_time = self._parse_prep_time(soup)

        # Determine meal type
        meal_type = meal_type_filter or self._infer_meal_type(title, url)

        # Determine diet type
        diet_type = diet_type_filter or self._infer_diet_type(title, ingredients)

        return RawRecipe(
            name=title,
            ingredients=ingredients,
            instructions=instructions,
            meal_type=meal_type,
            cuisine_type="française",
            diet_type=diet_type,
            prep_time_minutes=prep_time,
            tags=[],
            source="marmiton",
            source_url=url,
        )

    def _parse_ingredients(self, soup: BeautifulSoup) -> list[dict]:
        """Extract ingredients from a Marmiton recipe page."""
        ingredients: list[dict] = []

        # Try multiple selectors for ingredient blocks
        ing_items = soup.select(".card-ingredient") or soup.select(
            "[class*='ingredient']"
        )

        for item in ing_items:
            text = item.get_text(" ", strip=True)
            if not text or len(text) < 2:
                continue
            parsed = self._parse_ingredient_text(text)
            if parsed:
                ingredients.append(parsed)

        return ingredients

    def _parse_ingredient_text(self, text: str) -> dict | None:
        """Parse a French ingredient text string."""
        text = text.strip()
        if not text:
            return None

        # Try to extract quantity from the text
        m = re.match(r"^([\d.,/]+)\s*(.*)", text)
        if m:
            qty_str = m.group(1).replace(",", ".")
            rest = m.group(2).strip()

            # Parse quantity
            try:
                if "/" in qty_str:
                    parts = qty_str.split("/")
                    qty = float(parts[0]) / float(parts[1])
                else:
                    qty = float(qty_str)
            except (ValueError, ZeroDivisionError):
                qty = 1.0

            # Check for unit at start of rest
            quantity, unit = parse_measure(f"{qty} {rest}")
            name = re.sub(
                r"^(g|ml|kg|cl|l|c\.\s*à\s*soupe|c\.\s*à\s*café|cuillères?)\s*(de|d')?\s*",
                "",
                rest,
                flags=re.IGNORECASE,
            ).strip()

            if not name:
                name = rest

            return {"name": name, "quantity": round(quantity, 1), "unit": unit}

        # No quantity — assume 100g
        return {"name": text, "quantity": 100.0, "unit": "g"}

    def _parse_instructions(self, soup: BeautifulSoup) -> str:
        """Extract instructions from a Marmiton recipe page."""
        steps: list[str] = []

        # Try structured step selectors
        step_items = soup.select(".recipe-step-list__container p") or soup.select(
            "[class*='step'] p"
        )

        for item in step_items:
            text = item.get_text(strip=True)
            if text:
                steps.append(text)

        return " ".join(steps) if steps else "Voir la recette originale."

    def _parse_prep_time(self, soup: BeautifulSoup) -> int:
        """Extract prep time in minutes from a Marmiton recipe page."""
        time_tag = soup.select_one("[class*='time']")
        if time_tag:
            text = time_tag.get_text(strip=True)
            m = re.search(r"(\d+)", text)
            if m:
                return int(m.group(1))
        return 30

    def _infer_meal_type(self, title: str, url: str) -> str:
        """Infer meal type from title/URL keywords."""
        text = f"{title} {url}".lower()
        if any(kw in text for kw in BREAKFAST_KEYWORDS):
            return "petit-dejeuner"
        if any(kw in text for kw in SNACK_KEYWORDS):
            return "collation"
        return "dejeuner"

    def _infer_diet_type(self, title: str, ingredients: list[dict]) -> str:
        """Infer diet type from title and ingredients."""
        text = title.lower()
        all_ings = " ".join(i.get("name", "").lower() for i in ingredients)

        if "vegan" in text or "végétalien" in text:
            return "vegan"
        if "végétarien" in text:
            return "végétarien"

        meat_keywords = [
            "poulet",
            "boeuf",
            "porc",
            "agneau",
            "dinde",
            "canard",
            "veau",
            "saumon",
            "thon",
            "crevette",
            "poisson",
            "jambon",
            "bacon",
            "saucisse",
        ]
        if any(kw in all_ings for kw in meat_keywords):
            return "omnivore"

        return "omnivore"
