"""Base classes and shared utilities for recipe source adapters.

LLM-free (rule 10). Provides:
- RawRecipe dataclass (source-agnostic recipe format)
- RecipeSource ABC (interface for all adapters)
- Utility functions extracted from import_themealdb.py:
  auto_correct_portions, has_sane_macro_ratios, detect_allergens,
  parse_measure, build_recipe_row, translate_ingredient, normalize_unit.
"""

import json
import logging
import re
import unicodedata
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MIN_SANE_CALORIES = 150
MAX_SANE_CALORIES = 900
TARGET_CALORIES_PER_SERVING = 500

MAX_FAT_RATIO = 0.45
MIN_PROTEIN_RATIO = 0.08
MAX_PROTEIN_RATIO = 0.65

# Allergen keywords — keys = allergen tag, values = ingredient substrings
ALLERGEN_KEYWORDS: dict[str, list[str]] = {
    "gluten": [
        "farine",
        "pain",
        "pâtes",
        "spaghetti",
        "penne",
        "nouilles",
        "blé",
        "flour",
        "bread",
        "pasta",
        "noodles",
        "wheat",
        "couscous",
        "boulgour",
        "semoule",
        "chapelure",
    ],
    "lactose": [
        "lait",
        "crème",
        "beurre",
        "fromage",
        "parmesan",
        "mozzarella",
        "feta",
        "yaourt",
        "yogurt",
        "milk",
        "cream",
        "butter",
        "cheese",
        "ricotta",
        "mascarpone",
        "gruyère",
    ],
    "fruits_a_coque": [
        "amande",
        "noix",
        "cajou",
        "noisette",
        "pistache",
        "pécan",
        "macadamia",
        "pignon",
        "almonds",
        "walnuts",
        "cashews",
        "hazelnuts",
        "pecans",
        "pine nuts",
        "pistachios",
    ],
    "arachides": [
        "cacahuète",
        "arachide",
        "peanut",
        "peanuts",
        "beurre de cacahuète",
        "peanut butter",
    ],
    "crustaces": [
        "crevette",
        "crabe",
        "homard",
        "shrimp",
        "prawns",
        "crab",
        "lobster",
    ],
    "poisson": [
        "saumon",
        "thon",
        "cabillaud",
        "sardine",
        "anchois",
        "maquereau",
        "truite",
        "bar",
        "salmon",
        "tuna",
        "cod",
        "fish",
        "anchovy",
    ],
    "oeufs": ["oeuf", "oeufs", "egg", "eggs"],
    "soja": ["soja", "tofu", "tempeh", "soy", "edamame", "sauce soja"],
}

# Unit conversions to metric (ml or g)
UNIT_CONVERSIONS: dict[str, tuple[float, str]] = {
    "tbsp": (15.0, "ml"),
    "tbs": (15.0, "ml"),
    "tablespoon": (15.0, "ml"),
    "tablespoons": (15.0, "ml"),
    "tsp": (5.0, "ml"),
    "teaspoon": (5.0, "ml"),
    "teaspoons": (5.0, "ml"),
    "cup": (240.0, "ml"),
    "cups": (240.0, "ml"),
    "oz": (28.35, "g"),
    "ounce": (28.35, "g"),
    "ounces": (28.35, "g"),
    "lb": (453.6, "g"),
    "lbs": (453.6, "g"),
    "pound": (453.6, "g"),
    "pounds": (453.6, "g"),
    "kg": (1000.0, "g"),
    "c. à soupe": (15.0, "ml"),
    "c. à café": (5.0, "ml"),
    "cuillère à soupe": (15.0, "ml"),
    "cuillère à café": (5.0, "ml"),
    "verre": (250.0, "ml"),
}

# Load translations from JSON file
_TRANSLATIONS_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "ingredient_translations.json"
)
_TRANSLATIONS: dict[str, str] = {}


def _load_translations() -> dict[str, str]:
    """Load ingredient translations lazily."""
    global _TRANSLATIONS  # noqa: PLW0603
    if not _TRANSLATIONS and _TRANSLATIONS_PATH.exists():
        with open(_TRANSLATIONS_PATH, encoding="utf-8") as f:
            _TRANSLATIONS = json.load(f)
    return _TRANSLATIONS


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass
class RawRecipe:
    """Recipe as fetched from source, before OFF validation."""

    name: str
    ingredients: list[dict]  # [{"name": str, "quantity": float, "unit": str}]
    instructions: str
    meal_type: str  # "dejeuner" | "diner" | "petit-dejeuner" | "collation"
    cuisine_type: str  # "française", "italienne", etc.
    diet_type: str  # "omnivore" | "végétarien" | "vegan"
    prep_time_minutes: int
    tags: list[str] = field(default_factory=list)
    source: str = ""  # "spoonacular", "marmiton", etc.
    source_url: str = ""  # URL originale pour traçabilité


# ---------------------------------------------------------------------------
# ABC
# ---------------------------------------------------------------------------


class RecipeSource(ABC):
    """Base class for recipe source adapters."""

    @abstractmethod
    async def fetch_recipes(
        self,
        client: httpx.AsyncClient,
        limit: int = 50,
        **filters: str | int | float,
    ) -> list[RawRecipe]:
        """Fetch recipes from this source."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Source identifier (e.g., 'spoonacular', 'marmiton')."""
        ...

    @property
    def requires_api_key(self) -> bool:
        """Whether this source needs an API key."""
        return False


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


def normalize_name(name: str) -> str:
    """Lowercase + strip accents for deduplication."""
    nfkd = unicodedata.normalize("NFKD", name.lower().strip())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def translate_ingredient(name: str, translations: dict[str, str] | None = None) -> str:
    """Translate ingredient name EN -> FR using lookup table.

    Falls back to the bundled translations JSON if no dict is provided.
    Returns the original name if no translation is found.
    """
    trans = translations or _load_translations()
    key = name.lower().strip()
    return trans.get(key, name)


def normalize_unit(unit: str) -> str:
    """Normalize an English/French unit string to metric (g or ml).

    Returns the canonical unit string. For conversion factors, use
    UNIT_CONVERSIONS directly.
    """
    key = unit.lower().strip()
    if key in UNIT_CONVERSIONS:
        return UNIT_CONVERSIONS[key][1]
    # Already metric
    if key in ("g", "ml", "kg", "l"):
        return key
    return key


def _extract_number(text: str, keyword: str) -> float:
    """Extract numeric part before a keyword in a measure string."""
    idx = text.find(keyword)
    if idx <= 0:
        return 1.0
    num_part = text[:idx].strip()
    if not num_part:
        return 1.0
    if "/" in num_part:
        parts = num_part.split()
        total = 0.0
        for p in parts:
            if "/" in p:
                try:
                    n, d = p.split("/")
                    total += float(n) / float(d)
                except (ValueError, ZeroDivisionError):
                    pass
            else:
                try:
                    total += float(p)
                except ValueError:
                    pass
        return total if total > 0 else 1.0
    try:
        return float(num_part)
    except ValueError:
        return 1.0


def parse_measure(measure_str: str) -> tuple[float, str]:
    """Parse a measure string into (quantity, unit).

    Handles grams, ml, kg, cups, tablespoons, teaspoons, French measures,
    fractions, and plain numbers. Falls back to (100, 'g') for unparseable.

    Examples:
        "200 g" -> (200.0, "g")
        "3 tomates" -> (3.0, "pièces")
        "1 cup flour" -> (240.0, "ml")
        "2 tbsp oil" -> (30.0, "ml")
        "1 c. à soupe" -> (15.0, "ml")
    """
    if not measure_str:
        return 100.0, "g"

    s = measure_str.strip().lower()

    # Direct gram/ml/kg matches: "200g", "150 ml"
    m = re.match(r"^([\d.]+)\s*(g|ml|kg|l)\b", s)
    if m:
        val = float(m.group(1))
        unit = m.group(2)
        if unit == "kg":
            return val * 1000, "g"
        if unit == "l":
            return val * 1000, "ml"
        return val, unit

    # Trailing unit: "de poulet 200g" — try suffix
    m_suffix = re.search(r"([\d.]+)\s*(g|ml|kg)\s*$", s)
    if m_suffix:
        val = float(m_suffix.group(1))
        unit = m_suffix.group(2)
        if unit == "kg":
            return val * 1000, "g"
        return val, unit

    # French measures: "c. à soupe", "c. à café", "cuillère à soupe"
    for fr_unit, (factor, metric) in UNIT_CONVERSIONS.items():
        if fr_unit in s:
            num = _extract_number(s, fr_unit)
            return num * factor, metric

    # English unit words: tbsp, cup, oz, etc.
    for en_unit, (factor, metric) in UNIT_CONVERSIONS.items():
        if en_unit in s:
            num = _extract_number(s, en_unit)
            return num * factor, metric

    # Fractions: "1/2", "3/4 cup" (cup already handled above)
    frac_match = re.search(r"(\d+)\s*/\s*(\d+)", s)
    if frac_match:
        try:
            val = float(frac_match.group(1)) / float(frac_match.group(2))
            return val * 100, "g"
        except ZeroDivisionError:
            pass

    # Plain number at start
    num_match = re.match(r"^([\d.]+)", s)
    if num_match:
        val = float(num_match.group(1))
        # Determine if it's a piece count or grams
        # Words indicating pieces
        piece_words = [
            "pièce",
            "piece",
            "tranche",
            "slice",
            "feuille",
            "leaf",
            "brin",
            "sprig",
            "gousse",
            "clove",
            "tomate",
            "carotte",
            "oignon",
            "oeuf",
            "egg",
            "banane",
            "banana",
            "pomme",
            "apple",
        ]
        rest = s[num_match.end() :].strip()
        if rest and any(pw in rest for pw in piece_words):
            return val, "pièces"
        if val < 10:
            return val * 100, "g"  # "2" without context -> 200g (2 pieces)
        return val, "g"

    # Vague quantities: "un peu de", "a pinch of", etc.
    vague_words = [
        "pinch",
        "pincée",
        "un peu",
        "a bit",
        "dash",
        "splash",
        "to taste",
        "au goût",
    ]
    if any(v in s for v in vague_words):
        return 5.0, "g"

    return 100.0, "g"


def detect_allergens(ingredients: list[dict]) -> list[str]:
    """Detect allergen tags from ingredient names.

    Scans both French and English keywords.
    """
    allergens: set[str] = set()
    for ing in ingredients:
        name_lower = ing.get("name", "").lower()
        for allergen, keywords in ALLERGEN_KEYWORDS.items():
            if any(kw in name_lower for kw in keywords):
                allergens.add(allergen)
    return sorted(allergens)


def has_sane_macro_ratios(
    row: dict,
    max_fat_ratio: float = MAX_FAT_RATIO,
    min_protein_ratio: float = MIN_PROTEIN_RATIO,
) -> bool:
    """Check if macro ratios are within acceptable bounds for meal planning.

    Returns True if the recipe is usable, False if it should be skipped.
    """
    cal = float(row.get("calories_per_serving", 0) or 0)
    if cal < MIN_SANE_CALORIES:
        logger.info(f"  Ratio check: {cal:.0f} kcal < {MIN_SANE_CALORIES} -> skip")
        return False

    prot = float(row.get("protein_g_per_serving", 0) or 0)
    fat = float(row.get("fat_g_per_serving", 0) or 0)

    prot_ratio = (prot * 4) / cal
    fat_ratio = (fat * 9) / cal

    if fat_ratio > max_fat_ratio:
        logger.info(f"  Ratio check: fat={fat_ratio:.0%} > {max_fat_ratio:.0%} -> skip")
        return False
    if prot_ratio < min_protein_ratio:
        logger.info(
            f"  Ratio check: protein={prot_ratio:.0%} < {min_protein_ratio:.0%} -> skip"
        )
        return False
    if prot_ratio > MAX_PROTEIN_RATIO:
        logger.info(
            f"  Ratio check: protein={prot_ratio:.0%} > {MAX_PROTEIN_RATIO:.0%} -> skip"
        )
        return False

    return True


def auto_correct_portions(row: dict) -> dict:
    """If OFF-validated macros exceed MAX_SANE_CALORIES, divide to normalize.

    Detects multi-portion recipes and scales ingredient quantities down.
    Recalculates macros from nutrition_per_100g on each ingredient.

    Returns the corrected row (or unchanged if already in range).
    """
    cal = float(row.get("calories_per_serving", 0) or 0)

    if cal <= MAX_SANE_CALORIES:
        return row

    correction_factor = cal / TARGET_CALORIES_PER_SERVING

    logger.info(
        f"  Auto-correct: {cal:.0f} kcal -> /{correction_factor:.1f} "
        f"-> ~{cal / correction_factor:.0f} kcal"
    )

    ingredients = row.get("ingredients", [])
    for ing in ingredients:
        old_qty = ing.get("quantity", 0) or 0
        ing["quantity"] = round(old_qty / correction_factor, 1)

    # Recalculate macros from nutrition_per_100g
    totals = {"calories": 0.0, "protein_g": 0.0, "fat_g": 0.0, "carbs_g": 0.0}
    for ing in ingredients:
        n = ing.get("nutrition_per_100g")
        if not n:
            continue
        qty = ing.get("quantity", 0) or 0
        factor = qty / 100.0
        totals["calories"] += (n.get("calories", 0) or 0) * factor
        totals["protein_g"] += (n.get("protein_g", 0) or 0) * factor
        totals["fat_g"] += (n.get("fat_g", 0) or 0) * factor
        totals["carbs_g"] += (n.get("carbs_g", 0) or 0) * factor

    row["ingredients"] = ingredients
    row["calories_per_serving"] = round(totals["calories"], 2)
    row["protein_g_per_serving"] = round(totals["protein_g"], 2)
    row["fat_g_per_serving"] = round(totals["fat_g"], 2)
    row["carbs_g_per_serving"] = round(totals["carbs_g"], 2)

    return row


def build_recipe_row(raw: RawRecipe) -> dict:
    """Convert a RawRecipe dataclass into a dict matching the DB recipes schema.

    Macros are set to 0 — they will be filled by off_validate_recipe().
    """
    return {
        "name": raw.name,
        "name_normalized": normalize_name(raw.name),
        "meal_type": raw.meal_type,
        "cuisine_type": raw.cuisine_type,
        "diet_type": raw.diet_type,
        "tags": raw.tags,
        "ingredients": raw.ingredients,
        "instructions": raw.instructions,
        "prep_time_minutes": raw.prep_time_minutes,
        "allergen_tags": detect_allergens(raw.ingredients),
        "source": raw.source,
        "calories_per_serving": 0.0,
        "protein_g_per_serving": 0.0,
        "carbs_g_per_serving": 0.0,
        "fat_g_per_serving": 0.0,
        "off_validated": False,
    }
