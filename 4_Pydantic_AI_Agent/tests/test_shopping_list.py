"""
Tests for shopping list generation functions.

Tests ingredient extraction, aggregation, categorization, and servings multiplier.
"""

from nutrition.meal_planning import (
    extract_ingredients_from_meal_plan,
    aggregate_ingredients,
    categorize_ingredients,
    INGREDIENT_CATEGORIES,
)


def test_extract_ingredients_all_days():
    """Test extracting ingredients from all 7 days."""
    meal_plan = {
        "days": [
            {
                "meals": [
                    {
                        "ingredients": [
                            {"name": "riz", "quantity": 200, "unit": "g"},
                            {"name": "poulet", "quantity": 150, "unit": "g"},
                        ]
                    }
                ]
            },
            {
                "meals": [
                    {
                        "ingredients": [
                            {"name": "tomate", "quantity": 2, "unit": "pièces"}
                        ]
                    }
                ]
            },
        ]
    }

    ingredients = extract_ingredients_from_meal_plan(meal_plan, selected_days=None)

    assert len(ingredients) == 3
    assert {"name": "riz", "quantity": 200, "unit": "g"} in ingredients
    assert {"name": "poulet", "quantity": 150, "unit": "g"} in ingredients
    assert {"name": "tomate", "quantity": 2, "unit": "pièces"} in ingredients


def test_extract_ingredients_selected_days():
    """Test extracting ingredients from specific days only."""
    meal_plan = {
        "days": [
            {
                "meals": [
                    {"ingredients": [{"name": "riz", "quantity": 200, "unit": "g"}]}
                ]
            },
            {
                "meals": [
                    {"ingredients": [{"name": "pâtes", "quantity": 100, "unit": "g"}]}
                ]
            },
            {
                "meals": [
                    {"ingredients": [{"name": "quinoa", "quantity": 150, "unit": "g"}]}
                ]
            },
        ]
    }

    # Only days 0 and 2 (skip day 1)
    ingredients = extract_ingredients_from_meal_plan(meal_plan, selected_days=[0, 2])

    assert len(ingredients) == 2
    assert {"name": "riz", "quantity": 200, "unit": "g"} in ingredients
    assert {"name": "quinoa", "quantity": 150, "unit": "g"} in ingredients
    # pâtes should NOT be included
    assert not any(ing["name"] == "pâtes" for ing in ingredients)


def test_aggregate_ingredients_same_unit():
    """Test aggregation of same ingredient with same unit."""
    ingredients = [
        {"name": "riz", "quantity": 200, "unit": "g"},
        {"name": "riz", "quantity": 150, "unit": "g"},
        {"name": "riz", "quantity": 100, "unit": "g"},
    ]

    aggregated = aggregate_ingredients(ingredients, servings_multiplier=1.0)

    assert "riz|g" in aggregated
    assert aggregated["riz|g"] == 450.0  # 200 + 150 + 100


def test_aggregate_ingredients_different_units():
    """Test that same ingredient with different units stays separate."""
    ingredients = [
        {"name": "riz", "quantity": 200, "unit": "g"},
        {"name": "riz", "quantity": 1, "unit": "tasse"},
    ]

    aggregated = aggregate_ingredients(ingredients, servings_multiplier=1.0)

    assert "riz|g" in aggregated
    assert "riz|tasse" in aggregated
    assert aggregated["riz|g"] == 200.0
    assert aggregated["riz|tasse"] == 1.0


def test_aggregate_ingredients_with_multiplier():
    """Test servings multiplier doubles all quantities."""
    ingredients = [
        {"name": "poulet", "quantity": 200, "unit": "g"},
        {"name": "riz", "quantity": 150, "unit": "g"},
    ]

    aggregated = aggregate_ingredients(ingredients, servings_multiplier=2.0)

    assert aggregated["poulet|g"] == 400.0  # 200 * 2
    assert aggregated["riz|g"] == 300.0  # 150 * 2


def test_aggregate_ingredients_half_portions():
    """Test servings multiplier can halve quantities."""
    ingredients = [
        {"name": "saumon", "quantity": 300, "unit": "g"},
    ]

    aggregated = aggregate_ingredients(ingredients, servings_multiplier=0.5)

    assert aggregated["saumon|g"] == 150.0  # 300 * 0.5


def test_categorize_ingredients_produce():
    """Test that produce items are categorized correctly."""
    aggregated = {
        "tomate|g": 500,
        "oignon|g": 200,
        "banane|pièces": 7,
        "carotte|g": 300,
    }

    categorized = categorize_ingredients(aggregated)

    assert len(categorized["produce"]) == 4
    assert any(item["name"] == "tomate" for item in categorized["produce"])
    assert any(item["name"] == "oignon" for item in categorized["produce"])
    assert any(item["name"] == "banane" for item in categorized["produce"])
    assert any(item["name"] == "carotte" for item in categorized["produce"])


def test_categorize_ingredients_proteins():
    """Test that protein items are categorized correctly."""
    aggregated = {
        "poulet|g": 1200,
        "saumon|g": 600,
        "oeuf|pièces": 12,
        "lentille|g": 300,
    }

    categorized = categorize_ingredients(aggregated)

    assert len(categorized["proteins"]) == 4
    assert any(item["name"] == "poulet" for item in categorized["proteins"])
    assert any(item["name"] == "saumon" for item in categorized["proteins"])
    assert any(item["name"] == "oeuf" for item in categorized["proteins"])
    assert any(item["name"] == "lentille" for item in categorized["proteins"])


def test_categorize_ingredients_grains():
    """Test that grain items are categorized correctly."""
    aggregated = {
        "riz|g": 900,
        "pâtes|g": 400,
        "pain|tranches": 10,
        "quinoa|g": 300,
    }

    categorized = categorize_ingredients(aggregated)

    assert len(categorized["grains"]) == 4
    assert any(item["name"] == "riz" for item in categorized["grains"])
    assert any(item["name"] == "pâtes" for item in categorized["grains"])
    assert any(item["name"] == "pain" for item in categorized["grains"])
    assert any(item["name"] == "quinoa" for item in categorized["grains"])


def test_categorize_ingredients_dairy():
    """Test that dairy items are categorized correctly."""
    aggregated = {
        "lait|ml": 500,
        "fromage|g": 150,
        "yaourt|g": 300,
    }

    categorized = categorize_ingredients(aggregated)

    assert len(categorized["dairy"]) == 3
    assert any(item["name"] == "lait" for item in categorized["dairy"])
    assert any(item["name"] == "fromage" for item in categorized["dairy"])
    assert any(item["name"] == "yaourt" for item in categorized["dairy"])


def test_categorize_ingredients_pantry():
    """Test that pantry items are categorized correctly."""
    aggregated = {
        "huile d'olive|ml": 100,
        "sel|g": 20,
        "poivre|g": 10,
    }

    categorized = categorize_ingredients(aggregated)

    assert len(categorized["pantry"]) == 3
    assert any(item["name"] == "huile d'olive" for item in categorized["pantry"])
    assert any(item["name"] == "sel" for item in categorized["pantry"])
    assert any(item["name"] == "poivre" for item in categorized["pantry"])


def test_categorize_ingredients_unknown_to_other():
    """Test that unknown ingredients go to 'other' category."""
    aggregated = {
        "mysterious_ingredient|g": 100,
        "unknown_item|kg": 2,
    }

    categorized = categorize_ingredients(aggregated)

    assert len(categorized["other"]) == 2
    assert any(item["name"] == "mysterious_ingredient" for item in categorized["other"])
    assert any(item["name"] == "unknown_item" for item in categorized["other"])


def test_categorize_ingredients_mixed():
    """Test categorization with mixed ingredient types."""
    aggregated = {
        "tomate|g": 500,  # produce
        "poulet|g": 800,  # proteins
        "riz|g": 400,  # grains
        "lait|ml": 200,  # dairy
        "huile|ml": 50,  # pantry
        "special_powder|g": 30,  # other
    }

    categorized = categorize_ingredients(aggregated)

    assert len(categorized["produce"]) == 1
    assert len(categorized["proteins"]) == 1
    assert len(categorized["grains"]) == 1
    assert len(categorized["dairy"]) == 1
    assert len(categorized["pantry"]) == 1
    assert len(categorized["other"]) == 1


def test_categorize_ingredients_quantity_rounding():
    """Test that gram quantities are rounded to integers (UX design choice)."""
    aggregated = {
        "poulet|g": 456.789,
    }

    categorized = categorize_ingredients(aggregated)

    protein_item = next(
        item for item in categorized["proteins"] if item["name"] == "poulet"
    )
    # round_quantity_smart() rounds grams to integers for cleaner UX
    assert protein_item["quantity"] == 457  # Rounded to integer for g/ml


def test_extract_ingredients_empty_plan():
    """Test extracting from empty meal plan."""
    meal_plan = {"days": []}

    ingredients = extract_ingredients_from_meal_plan(meal_plan, selected_days=[0])

    assert len(ingredients) == 0


def test_aggregate_ingredients_empty_list():
    """Test aggregating empty ingredient list."""
    ingredients = []

    aggregated = aggregate_ingredients(ingredients, servings_multiplier=1.0)

    assert len(aggregated) == 0


def test_aggregate_ingredients_case_insensitive():
    """Test that ingredient names are normalized to lowercase."""
    ingredients = [
        {"name": "Riz", "quantity": 100, "unit": "g"},
        {"name": "RIZ", "quantity": 100, "unit": "g"},
        {"name": "riz", "quantity": 100, "unit": "g"},
    ]

    aggregated = aggregate_ingredients(ingredients, servings_multiplier=1.0)

    assert "riz|g" in aggregated
    assert aggregated["riz|g"] == 300.0  # All three aggregated together


def test_aggregate_ingredients_unit_normalization():
    """Test that units are normalized to lowercase."""
    ingredients = [
        {"name": "poulet", "quantity": 100, "unit": "G"},
        {"name": "poulet", "quantity": 100, "unit": "g"},
    ]

    aggregated = aggregate_ingredients(ingredients, servings_multiplier=1.0)

    assert "poulet|g" in aggregated
    assert aggregated["poulet|g"] == 200.0


def test_ingredient_categories_completeness():
    """Test that INGREDIENT_CATEGORIES has all expected keys."""
    expected_categories = ["produce", "proteins", "grains", "dairy", "pantry"]

    for category in expected_categories:
        assert category in INGREDIENT_CATEGORIES
        assert isinstance(INGREDIENT_CATEGORIES[category], list)
        assert len(INGREDIENT_CATEGORIES[category]) > 0
