"""
Unit tests for meal_plan_formatter.py module.

Tests Markdown generation with various meal plan structures.
"""

from src.nutrition.meal_plan_formatter import format_meal_plan_as_markdown


def test_format_meal_plan_basic_structure():
    """Test basic Markdown structure with minimal meal plan."""
    meal_plan = {
        "days": [
            {
                "day": "Lundi",
                "date": "2024-12-23",
                "meals": [],
                "daily_totals": {
                    "calories": 3000,
                    "protein_g": 180,
                    "carbs_g": 375,
                    "fat_g": 83,
                },
            }
        ],
        "start_date": "2024-12-23",
        "end_date": "2024-12-29",
        "meal_structure": "3_meals_2_snacks",
        "weekly_totals": {
            "calories": 21000,
            "protein_g": 1260,
            "carbs_g": 2625,
            "fat_g": 581,
        },
    }

    markdown = format_meal_plan_as_markdown(meal_plan, 123)

    # Check header elements
    assert "# Plan de Repas Hebdomadaire" in markdown
    assert "**ID:** 123" in markdown
    assert "**Période:** 2024-12-23 → 2024-12-29" in markdown
    assert "**Structure:** 3_meals_2_snacks" in markdown

    # Check day section
    assert "## Lundi (2024-12-23)" in markdown
    assert "**Total du jour:** 3000 kcal" in markdown

    # Check summary table
    assert "## Récapitulatif Hebdomadaire" in markdown
    assert (
        "| Jour | Calories | Protéines (g) | Glucides (g) | Lipides (g) |" in markdown
    )


def test_format_meal_plan_with_meals():
    """Test Markdown with complete meal details."""
    meal_plan = {
        "days": [
            {
                "day": "Lundi",
                "date": "2024-12-23",
                "meals": [
                    {
                        "meal_type": "Petit-déjeuner",
                        "time": "07:30",
                        "recipe_name": "Omelette protéinée",
                        "ingredients": [
                            {"name": "Eggs", "quantity": 3, "unit": "units"},
                            {"name": "Cheese", "quantity": 30, "unit": "g"},
                        ],
                        "instructions": [
                            "Beat eggs in a bowl",
                            "Cook in pan",
                            "Add cheese",
                        ],
                        "macros": {
                            "calories": 400,
                            "protein_g": 30,
                            "carbs_g": 5,
                            "fat_g": 28,
                        },
                    }
                ],
                "daily_totals": {
                    "calories": 3000,
                    "protein_g": 180,
                    "carbs_g": 375,
                    "fat_g": 83,
                },
            }
        ],
        "start_date": "2024-12-23",
        "end_date": "2024-12-29",
        "meal_structure": "3_consequent_meals",
        "weekly_totals": {
            "calories": 21000,
            "protein_g": 1260,
            "carbs_g": 2625,
            "fat_g": 581,
        },
    }

    markdown = format_meal_plan_as_markdown(meal_plan, 456)

    # Check meal details
    assert "### Petit-déjeuner (07:30) - Omelette protéinée" in markdown
    assert "**Ingrédients:**" in markdown
    assert "- Eggs: 3 units" in markdown
    assert "- Cheese: 30 g" in markdown
    assert "**Instructions:**" in markdown
    assert "1. Beat eggs in a bowl" in markdown
    assert "2. Cook in pan" in markdown
    assert "3. Add cheese" in markdown
    assert "**Macros:** 400 kcal" in markdown
    assert "Protéines: 30g" in markdown


def test_format_meal_plan_pipe_escaping():
    """Test that pipes in ingredient names are escaped for markdown tables."""
    meal_plan = {
        "days": [
            {
                "day": "Mardi",
                "date": "2024-12-24",
                "meals": [
                    {
                        "meal_type": "Déjeuner",
                        "time": "12:30",
                        "recipe_name": "Test Recipe",
                        "ingredients": [
                            {
                                "name": "Ingredient | with | pipes",
                                "quantity": 100,
                                "unit": "g",
                            }
                        ],
                        "instructions": [],
                        "macros": {
                            "calories": 500,
                            "protein_g": 40,
                            "carbs_g": 50,
                            "fat_g": 15,
                        },
                    }
                ],
                "daily_totals": {
                    "calories": 2500,
                    "protein_g": 150,
                    "carbs_g": 300,
                    "fat_g": 70,
                },
            }
        ],
        "start_date": "2024-12-24",
        "end_date": "2024-12-30",
    }

    markdown = format_meal_plan_as_markdown(meal_plan, 789)

    # Pipes should be escaped
    assert "Ingredient \\| with \\| pipes" in markdown


def test_format_meal_plan_multiple_days():
    """Test Markdown with multiple days."""
    meal_plan = {
        "days": [
            {
                "day": "Lundi",
                "date": "2024-12-23",
                "meals": [],
                "daily_totals": {
                    "calories": 3000,
                    "protein_g": 180,
                    "carbs_g": 375,
                    "fat_g": 83,
                },
            },
            {
                "day": "Mardi",
                "date": "2024-12-24",
                "meals": [],
                "daily_totals": {
                    "calories": 3100,
                    "protein_g": 185,
                    "carbs_g": 380,
                    "fat_g": 85,
                },
            },
            {
                "day": "Mercredi",
                "date": "2024-12-25",
                "meals": [],
                "daily_totals": {
                    "calories": 2900,
                    "protein_g": 175,
                    "carbs_g": 370,
                    "fat_g": 80,
                },
            },
        ],
        "start_date": "2024-12-23",
        "end_date": "2024-12-29",
        "meal_structure": "3_consequent_meals",
    }

    markdown = format_meal_plan_as_markdown(meal_plan, 101)

    # Check all days are present
    assert "## Lundi (2024-12-23)" in markdown
    assert "## Mardi (2024-12-24)" in markdown
    assert "## Mercredi (2024-12-25)" in markdown

    # Check summary table has all days
    assert "| Lundi |" in markdown
    assert "| Mardi |" in markdown
    assert "| Mercredi |" in markdown

    # Check averages row
    assert "| **Moyenne** |" in markdown


def test_format_meal_plan_empty_meal_plan():
    """Test handling of empty meal plan."""
    meal_plan = {"days": [], "start_date": "2024-12-23", "end_date": "2024-12-29"}

    markdown = format_meal_plan_as_markdown(meal_plan, 999)

    # Should still generate valid Markdown
    assert "# Plan de Repas Hebdomadaire" in markdown
    assert "**ID:** 999" in markdown
    assert "## Récapitulatif Hebdomadaire" in markdown


def test_format_meal_plan_footer_notes():
    """Test that footer notes are included."""
    meal_plan = {
        "days": [
            {
                "day": "Lundi",
                "date": "2024-12-23",
                "meals": [],
                "daily_totals": {
                    "calories": 3000,
                    "protein_g": 180,
                    "carbs_g": 375,
                    "fat_g": 83,
                },
            }
        ],
        "start_date": "2024-12-23",
        "end_date": "2024-12-29",
    }

    markdown = format_meal_plan_as_markdown(meal_plan, 111)

    # Check footer elements
    assert "*Généré par AI-Nutrition Assistant*" in markdown
    assert "**Notes:**" in markdown
    assert "Ajustez les quantités selon votre faim et vos besoins" in markdown
    assert "Hydratation: boire 2-3L d'eau par jour" in markdown
    assert "Les macros sont calculées avec OpenFoodFacts" in markdown


def test_format_meal_plan_weekly_totals():
    """Test weekly totals are formatted correctly."""
    meal_plan = {
        "days": [
            {
                "day": "Lundi",
                "date": "2024-12-23",
                "meals": [],
                "daily_totals": {
                    "calories": 3000,
                    "protein_g": 180,
                    "carbs_g": 375,
                    "fat_g": 83,
                },
            }
        ],
        "start_date": "2024-12-23",
        "end_date": "2024-12-29",
        "weekly_totals": {
            "calories": 21000,
            "protein_g": 1260,
            "carbs_g": 2625,
            "fat_g": 581,
        },
    }

    markdown = format_meal_plan_as_markdown(meal_plan, 222)

    # Check weekly totals
    assert "**Total hebdomadaire:** 21000 kcal" in markdown
    assert "Protéines: 1260g" in markdown
    assert "Glucides: 2625g" in markdown
    assert "Lipides: 581g" in markdown


def test_format_meal_plan_missing_optional_fields():
    """Test graceful handling of missing optional fields."""
    meal_plan = {
        "days": [
            {
                "day": "Lundi",
                "meals": [
                    {
                        "meal_type": "Déjeuner",
                        # Missing time, recipe_name, ingredients, instructions, macros
                    }
                ],
                # Missing daily_totals
            }
        ],
        # Missing start_date, end_date, meal_structure, weekly_totals
    }

    markdown = format_meal_plan_as_markdown(meal_plan, 333)

    # Should not crash
    assert "# Plan de Repas Hebdomadaire" in markdown
    assert "**ID:** 333" in markdown
    assert "## Lundi" in markdown
