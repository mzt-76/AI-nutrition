"""Unit tests for recipe source adapters — base utilities and parsing.

Tests parsing, translation, filtering, and dataclass construction.
No network calls, no DB access, no LLM.
"""

import json
from pathlib import Path

import pytest

from scripts.recipe_sources.base import (
    RawRecipe,
    auto_correct_portions,
    build_recipe_row,
    detect_allergens,
    has_sane_macro_ratios,
    normalize_name,
    normalize_unit,
    parse_measure,
    translate_ingredient,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def translations() -> dict[str, str]:
    """Load the ingredient translations JSON."""
    path = (
        Path(__file__).resolve().parent.parent
        / "scripts"
        / "data"
        / "ingredient_translations.json"
    )
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def balanced_row() -> dict:
    """A recipe row with balanced macros: ~500 kcal, 30% protein, 25% fat, 45% carbs."""
    return {
        "name": "Poulet grillé aux légumes",
        "calories_per_serving": 500.0,
        "protein_g_per_serving": 37.5,  # 150 cal = 30%
        "fat_g_per_serving": 13.9,  # 125 cal = 25%
        "carbs_g_per_serving": 56.3,  # 225 cal = 45%
    }


@pytest.fixture
def high_fat_row() -> dict:
    """A recipe row with high fat: 50% fat calories."""
    return {
        "name": "Fondue au fromage",
        "calories_per_serving": 600.0,
        "protein_g_per_serving": 20.0,  # 80 cal = 13%
        "fat_g_per_serving": 33.3,  # 300 cal = 50%
        "carbs_g_per_serving": 55.0,  # 220 cal = 37%
    }


@pytest.fixture
def low_protein_row() -> dict:
    """A recipe row with very low protein: 5% protein calories."""
    return {
        "name": "Gâteau au chocolat",
        "calories_per_serving": 400.0,
        "protein_g_per_serving": 5.0,  # 20 cal = 5%
        "fat_g_per_serving": 15.0,  # 135 cal = 34%
        "carbs_g_per_serving": 61.3,  # 245 cal = 61%
    }


@pytest.fixture
def oversized_row() -> dict:
    """A recipe row with > 900 kcal (needs auto-correction)."""
    return {
        "name": "Pasta carbonara familiale",
        "calories_per_serving": 1200.0,
        "protein_g_per_serving": 45.0,
        "fat_g_per_serving": 40.0,
        "carbs_g_per_serving": 120.0,
        "ingredients": [
            {
                "name": "spaghetti",
                "quantity": 400.0,
                "unit": "g",
                "nutrition_per_100g": {
                    "calories": 150,
                    "protein_g": 5,
                    "fat_g": 1,
                    "carbs_g": 30,
                },
            },
            {
                "name": "bacon",
                "quantity": 200.0,
                "unit": "g",
                "nutrition_per_100g": {
                    "calories": 250,
                    "protein_g": 15,
                    "fat_g": 20,
                    "carbs_g": 0,
                },
            },
        ],
    }


@pytest.fixture
def sample_raw_recipe() -> RawRecipe:
    """A sample RawRecipe for testing build_recipe_row."""
    return RawRecipe(
        name="Grilled Chicken Salad",
        ingredients=[
            {"name": "blanc de poulet", "quantity": 150.0, "unit": "g"},
            {"name": "laitue romaine", "quantity": 100.0, "unit": "g"},
            {"name": "tomates cerises", "quantity": 80.0, "unit": "g"},
            {"name": "huile d'olive", "quantity": 15.0, "unit": "ml"},
        ],
        instructions="Griller le poulet. Assembler la salade.",
        meal_type="dejeuner",
        cuisine_type="américaine",
        diet_type="omnivore",
        prep_time_minutes=20,
        tags=["healthy", "high-protein"],
        source="allrecipes",
        source_url="https://allrecipes.com/recipe/12345",
    )


# ---------------------------------------------------------------------------
# parse_measure tests
# ---------------------------------------------------------------------------


class TestParseMeasure:
    def test_grams(self):
        qty, unit = parse_measure("200 g de poulet")
        assert qty == 200.0
        assert unit == "g"

    def test_grams_no_space(self):
        qty, unit = parse_measure("200g")
        assert qty == 200.0
        assert unit == "g"

    def test_ml(self):
        qty, unit = parse_measure("150 ml")
        assert qty == 150.0
        assert unit == "ml"

    def test_kg(self):
        qty, unit = parse_measure("1.5 kg")
        assert qty == 1500.0
        assert unit == "g"

    def test_pieces(self):
        qty, unit = parse_measure("3 tomates")
        assert qty == 3.0
        assert unit == "pièces"

    def test_cups(self):
        qty, unit = parse_measure("1 cup flour")
        assert qty == 240.0
        assert unit == "ml"

    def test_tbsp(self):
        qty, unit = parse_measure("2 tbsp oil")
        assert qty == 30.0
        assert unit == "ml"

    def test_tsp(self):
        qty, unit = parse_measure("1 tsp salt")
        assert qty == 5.0
        assert unit == "ml"

    def test_french_tablespoon(self):
        qty, unit = parse_measure("1 c. à soupe")
        assert qty == 15.0
        assert unit == "ml"

    def test_french_teaspoon(self):
        qty, unit = parse_measure("2 c. à café")
        assert qty == 10.0
        assert unit == "ml"

    def test_empty_string(self):
        qty, unit = parse_measure("")
        assert qty == 100.0
        assert unit == "g"

    def test_vague_pinch(self):
        qty, unit = parse_measure("a pinch of salt")
        assert qty == 5.0
        assert unit == "g"

    def test_vague_french(self):
        qty, unit = parse_measure("un peu de sel")
        assert qty == 5.0
        assert unit == "g"

    def test_plain_small_number(self):
        """Small number without context -> multiply by 100 (pieces)."""
        qty, unit = parse_measure("2")
        assert qty == 200.0
        assert unit == "g"

    def test_plain_large_number(self):
        """Large number without context -> grams."""
        qty, unit = parse_measure("250")
        assert qty == 250.0
        assert unit == "g"


# ---------------------------------------------------------------------------
# translate_ingredient tests
# ---------------------------------------------------------------------------


class TestTranslateIngredient:
    def test_known_ingredient(self, translations):
        result = translate_ingredient("chicken breast", translations)
        assert result == "blanc de poulet"

    def test_case_insensitive(self, translations):
        result = translate_ingredient("Olive Oil", translations)
        assert result == "huile d'olive"

    def test_unknown_ingredient(self, translations):
        result = translate_ingredient("gochujang", translations)
        assert result == "gochujang"

    def test_with_whitespace(self, translations):
        result = translate_ingredient("  garlic  ", translations)
        assert result == "ail"

    def test_default_translations(self):
        """Uses bundled JSON when no translations dict provided."""
        result = translate_ingredient("chicken breast")
        assert result == "blanc de poulet"


# ---------------------------------------------------------------------------
# normalize_unit tests
# ---------------------------------------------------------------------------


class TestNormalizeUnit:
    def test_tablespoon(self):
        assert normalize_unit("tablespoon") == "ml"

    def test_ounce(self):
        assert normalize_unit("ounce") == "g"

    def test_cup(self):
        assert normalize_unit("cup") == "ml"

    def test_tsp(self):
        assert normalize_unit("tsp") == "ml"

    def test_already_metric_g(self):
        assert normalize_unit("g") == "g"

    def test_already_metric_ml(self):
        assert normalize_unit("ml") == "ml"

    def test_unknown_unit(self):
        """Unknown units are returned as-is."""
        assert normalize_unit("bunch") == "bunch"


# ---------------------------------------------------------------------------
# build_recipe_row tests
# ---------------------------------------------------------------------------


class TestBuildRecipeRow:
    def test_all_fields_present(self, sample_raw_recipe):
        row = build_recipe_row(sample_raw_recipe)

        assert row["name"] == "Grilled Chicken Salad"
        assert row["name_normalized"] == "grilled chicken salad"
        assert row["meal_type"] == "dejeuner"
        assert row["cuisine_type"] == "américaine"
        assert row["diet_type"] == "omnivore"
        assert row["tags"] == ["healthy", "high-protein"]
        assert row["source"] == "allrecipes"
        assert row["prep_time_minutes"] == 20
        assert len(row["ingredients"]) == 4
        assert row["instructions"] == "Griller le poulet. Assembler la salade."

        # Macros should be zero (filled by OFF later)
        assert row["calories_per_serving"] == 0.0
        assert row["protein_g_per_serving"] == 0.0
        assert row["fat_g_per_serving"] == 0.0
        assert row["carbs_g_per_serving"] == 0.0
        assert row["off_validated"] is False

    def test_allergen_detection(self, sample_raw_recipe):
        row = build_recipe_row(sample_raw_recipe)
        # "blanc de poulet" doesn't match allergens, but "huile d'olive" doesn't either
        # No allergens expected for this recipe
        assert isinstance(row["allergen_tags"], list)

    def test_name_normalized_strips_accents(self):
        raw = RawRecipe(
            name="Crêpe protéinée à la banane",
            ingredients=[{"name": "banane", "quantity": 1, "unit": "pièces"}],
            instructions="Mélanger.",
            meal_type="petit-dejeuner",
            cuisine_type="française",
            diet_type="omnivore",
            prep_time_minutes=10,
            source="test",
        )
        row = build_recipe_row(raw)
        assert row["name_normalized"] == "crepe proteinee a la banane"


# ---------------------------------------------------------------------------
# has_sane_macro_ratios tests
# ---------------------------------------------------------------------------


class TestHasSaneMacroRatios:
    def test_accepts_balanced(self, balanced_row):
        assert has_sane_macro_ratios(balanced_row) is True

    def test_rejects_high_fat(self, high_fat_row):
        assert has_sane_macro_ratios(high_fat_row) is False

    def test_rejects_low_protein(self, low_protein_row):
        assert has_sane_macro_ratios(low_protein_row) is False

    def test_rejects_low_calories(self):
        row = {
            "calories_per_serving": 100.0,
            "protein_g_per_serving": 10.0,
            "fat_g_per_serving": 3.0,
            "carbs_g_per_serving": 5.0,
        }
        assert has_sane_macro_ratios(row) is False

    def test_custom_thresholds(self, balanced_row):
        """With strict thresholds, even balanced recipes can be rejected."""
        # balanced_row has fat at 25% — reject if max is 20%
        assert has_sane_macro_ratios(balanced_row, max_fat_ratio=0.20) is False

    def test_accepts_with_loose_thresholds(self, high_fat_row):
        """With loose thresholds, high-fat passes."""
        assert has_sane_macro_ratios(high_fat_row, max_fat_ratio=0.60) is True


# ---------------------------------------------------------------------------
# auto_correct_portions tests
# ---------------------------------------------------------------------------


class TestAutoCorrectPortions:
    def test_no_change_within_range(self, balanced_row):
        result = auto_correct_portions(balanced_row)
        assert result["calories_per_serving"] == 500.0

    def test_divides_oversized(self, oversized_row):
        result = auto_correct_portions(oversized_row)
        # 1200 / 500 = 2.4 correction factor
        assert result["calories_per_serving"] < 900
        # Ingredient quantities should be reduced
        for ing in result["ingredients"]:
            assert ing["quantity"] < 400.0  # Was 400 for spaghetti

    def test_recalculates_macros(self, oversized_row):
        result = auto_correct_portions(oversized_row)
        # Macros should be recalculated from nutrition_per_100g
        assert result["protein_g_per_serving"] > 0
        assert result["fat_g_per_serving"] > 0
        assert result["carbs_g_per_serving"] > 0


# ---------------------------------------------------------------------------
# detect_allergens tests
# ---------------------------------------------------------------------------


class TestDetectAllergens:
    def test_peanut_butter(self):
        ingredients = [{"name": "beurre de cacahuète", "quantity": 30, "unit": "g"}]
        allergens = detect_allergens(ingredients)
        assert "arachides" in allergens

    def test_gluten_from_flour(self):
        ingredients = [{"name": "farine de blé", "quantity": 200, "unit": "g"}]
        allergens = detect_allergens(ingredients)
        assert "gluten" in allergens

    def test_lactose_from_cheese(self):
        ingredients = [{"name": "fromage gruyère", "quantity": 100, "unit": "g"}]
        allergens = detect_allergens(ingredients)
        assert "lactose" in allergens

    def test_multiple_allergens(self):
        ingredients = [
            {"name": "farine", "quantity": 200, "unit": "g"},
            {"name": "oeufs", "quantity": 2, "unit": "pièces"},
            {"name": "lait", "quantity": 250, "unit": "ml"},
        ]
        allergens = detect_allergens(ingredients)
        assert "gluten" in allergens
        assert "oeufs" in allergens
        assert "lactose" in allergens

    def test_no_allergens(self):
        ingredients = [
            {"name": "riz", "quantity": 200, "unit": "g"},
            {"name": "courgette", "quantity": 150, "unit": "g"},
        ]
        allergens = detect_allergens(ingredients)
        assert allergens == []

    def test_english_allergens(self):
        """Also detects allergens from English ingredient names."""
        ingredients = [{"name": "peanut butter", "quantity": 30, "unit": "g"}]
        allergens = detect_allergens(ingredients)
        assert "arachides" in allergens


# ---------------------------------------------------------------------------
# RawRecipe dataclass tests
# ---------------------------------------------------------------------------


class TestRawRecipe:
    def test_creation(self, sample_raw_recipe):
        assert sample_raw_recipe.name == "Grilled Chicken Salad"
        assert sample_raw_recipe.meal_type == "dejeuner"
        assert sample_raw_recipe.source == "allrecipes"
        assert len(sample_raw_recipe.ingredients) == 4

    def test_default_tags(self):
        raw = RawRecipe(
            name="Test",
            ingredients=[],
            instructions="",
            meal_type="dejeuner",
            cuisine_type="test",
            diet_type="omnivore",
            prep_time_minutes=10,
        )
        assert raw.tags == []
        assert raw.source == ""
        assert raw.source_url == ""


# ---------------------------------------------------------------------------
# normalize_name tests
# ---------------------------------------------------------------------------


class TestNormalizeName:
    def test_lowercase(self):
        assert normalize_name("Poulet Grillé") == "poulet grille"

    def test_strips_accents(self):
        assert normalize_name("crêpe protéinée") == "crepe proteinee"

    def test_strips_whitespace(self):
        assert normalize_name("  test  ") == "test"
