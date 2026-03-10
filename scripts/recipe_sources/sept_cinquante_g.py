"""750g.com scraping adapter for recipe import pipeline.

LLM-free (rule 10). Scrapes recipes from 750g.com using BeautifulSoup.
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

SEPT_CINQUANTE_BASE = "https://www.750g.com"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class SeptCinquanteGSource(RecipeSource):
    """Scrape recipes from 750g.com."""

    @property
    def name(self) -> str:
        return "750g"

    @property
    def requires_api_key(self) -> bool:
        return False

    async def fetch_recipes(
        self,
        client: httpx.AsyncClient,
        limit: int = 50,
        **filters: str | int | float,
    ) -> list[RawRecipe]:
        """Fetch recipes from 750g via search + page scraping.

        Supported filters:
            query (str): search keywords
            meal_type (str): target meal type
            diet_type (str): diet type hint
        """
        query = str(filters.get("query", "recette légère protéinée"))
        meal_type_filter = str(filters.get("meal_type", ""))
        diet_type_filter = str(filters.get("diet_type", ""))

        headers = {"User-Agent": USER_AGENT}

        try:
            resp = await client.get(
                f"{SEPT_CINQUANTE_BASE}/recherche/",
                params={"q": query},
                headers=headers,
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.error(f"750g search failed: {e}")
            return []

        soup = BeautifulSoup(resp.text, "lxml")

        # Extract recipe links
        links: list[str] = []
        for a in soup.select("a[href*='/recettes/']"):
            href = a.get("href", "")
            if href and ".htm" in href and href not in links:
                full = (
                    href if href.startswith("http") else f"{SEPT_CINQUANTE_BASE}{href}"
                )
                links.append(full)
            if len(links) >= limit:
                break

        logger.info(f"750g: found {len(links)} recipe links for '{query}'")

        recipes: list[RawRecipe] = []
        for url in links[:limit]:
            try:
                raw = await self._scrape_recipe(
                    client, url, headers, meal_type_filter, diet_type_filter
                )
                if raw:
                    recipes.append(raw)
            except Exception as e:
                logger.warning(f"750g scrape error for {url}: {e}")

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
        """Scrape a single recipe page from 750g."""
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

        # Ingredients
        ingredients = self._parse_ingredients(soup)
        if not ingredients:
            return None

        # Instructions
        instructions = self._parse_instructions(soup)

        # Prep time
        prep_time = self._parse_prep_time(soup)

        # Meal type
        meal_type = meal_type_filter or self._infer_meal_type(title)

        # Diet type
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
            source="750g",
            source_url=url,
        )

    def _parse_ingredients(self, soup: BeautifulSoup) -> list[dict]:
        """Extract ingredients from a 750g recipe page."""
        ingredients: list[dict] = []

        # 750g uses structured ingredient blocks
        ing_items = soup.select(".recipe-ingredients li") or soup.select(
            "[class*='ingredient'] li"
        )

        if not ing_items:
            # Fallback: try any list inside ingredients section
            ing_section = soup.find(string=re.compile(r"ingrédients", re.IGNORECASE))
            if ing_section:
                parent = ing_section.find_parent(["div", "section"])
                if parent:
                    ing_items = parent.select("li")

        for item in ing_items:
            text = item.get_text(" ", strip=True)
            if not text or len(text) < 2:
                continue
            parsed = self._parse_ingredient_text(text)
            if parsed:
                ingredients.append(parsed)

        return ingredients

    def _parse_ingredient_text(self, text: str) -> dict | None:
        """Parse a French ingredient text line."""
        text = text.strip()
        if not text:
            return None

        m = re.match(r"^([\d.,/]+)\s*(.*)", text)
        if m:
            qty_str = m.group(1).replace(",", ".")
            rest = m.group(2).strip()

            try:
                if "/" in qty_str:
                    parts = qty_str.split("/")
                    qty = float(parts[0]) / float(parts[1])
                else:
                    qty = float(qty_str)
            except (ValueError, ZeroDivisionError):
                qty = 1.0

            quantity, unit = parse_measure(f"{qty} {rest}")
            name = re.sub(
                r"^(g|ml|kg|cl|l|c\.\s*à\s*soupe|c\.\s*à\s*café|cuillères?)\s*(de|d')?\s*",
                "",
                rest,
                flags=re.IGNORECASE,
            ).strip()

            return {"name": name or rest, "quantity": round(quantity, 1), "unit": unit}

        return {"name": text, "quantity": 100.0, "unit": "g"}

    def _parse_instructions(self, soup: BeautifulSoup) -> str:
        """Extract instructions from a 750g recipe page."""
        steps: list[str] = []
        step_items = soup.select(".recipe-steps li") or soup.select("[class*='step'] p")
        for item in step_items:
            text = item.get_text(strip=True)
            if text:
                steps.append(text)
        return " ".join(steps) if steps else "Voir la recette originale."

    def _parse_prep_time(self, soup: BeautifulSoup) -> int:
        """Extract prep time in minutes."""
        for tag in soup.select("[class*='time'], [class*='duration']"):
            text = tag.get_text(strip=True)
            m = re.search(r"(\d+)", text)
            if m:
                return int(m.group(1))
        return 30

    def _infer_meal_type(self, title: str) -> str:
        """Infer meal type from title."""
        t = title.lower()
        breakfast = ["petit-déjeuner", "brunch", "pancake", "crêpe", "porridge"]
        snack = ["collation", "snack", "goûter", "smoothie", "barre"]
        if any(kw in t for kw in breakfast):
            return "petit-dejeuner"
        if any(kw in t for kw in snack):
            return "collation"
        return "dejeuner"

    def _infer_diet_type(self, title: str, ingredients: list[dict]) -> str:
        """Infer diet type from title and ingredients."""
        t = title.lower()
        if "vegan" in t or "végétalien" in t:
            return "vegan"
        if "végétarien" in t:
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
            "jambon",
        ]
        if any(kw in all_ings for kw in meat):
            return "omnivore"
        return "omnivore"
