"""
Tests for nutrition validators module.

Tests allergen validation, macro validation, and meal plan structure validation.
"""

import pytest
from nutrition.validators import (
    validate_allergens,
    validate_daily_macros,
    validate_meal_plan_structure,
)


def test_validate_allergens_no_violations():
    """Test clean meal plan with no allergen violations."""
    meal_plan = {
        "days": [
            {
                "meals": [
                    {
                        "recipe_name": "Poulet grillé",
                        "ingredients": [
                            {"name": "poulet", "quantity": 200, "unit": "g"},
                            {"name": "riz", "quantity": 100, "unit": "g"},
                        ],
                    }
                ]
            }
        ]
    }
    user_allergens = ["arachides", "lactose"]
    violations = validate_allergens(meal_plan, user_allergens)
    assert violations == []


def test_validate_allergens_direct_match():
    """Test direct allergen match detection."""
    meal_plan = {
        "days": [
            {
                "meals": [
                    {
                        "recipe_name": "Salade",
                        "ingredients": [
                            {"name": "beurre de cacahuète", "quantity": 30, "unit": "g"}
                        ],
                    }
                ]
            }
        ]
    }
    user_allergens = ["arachides"]
    violations = validate_allergens(meal_plan, user_allergens)
    assert len(violations) > 0
    assert "cacahuète" in violations[0].lower()


def test_validate_allergens_family_matching():
    """Test allergen family matching (arachides -> peanut butter)."""
    meal_plan = {
        "days": [
            {
                "meals": [
                    {
                        "recipe_name": "Toast",
                        "ingredients": [
                            {"name": "peanut butter", "quantity": 20, "unit": "g"}
                        ],
                    }
                ]
            }
        ]
    }
    user_allergens = ["arachides"]
    violations = validate_allergens(meal_plan, user_allergens)
    assert len(violations) > 0


def test_validate_allergens_false_positive_coconut():
    """Test false positive: noix de coco should NOT trigger fruits à coque allergy."""
    meal_plan = {
        "days": [
            {
                "meals": [
                    {
                        "recipe_name": "Curry",
                        "ingredients": [
                            {"name": "noix de coco", "quantity": 50, "unit": "g"}
                        ],
                    }
                ]
            }
        ]
    }
    user_allergens = ["fruits à coque"]
    violations = validate_allergens(meal_plan, user_allergens)
    assert len(violations) == 0  # Coconut is NOT a tree nut


def test_validate_allergens_case_insensitive():
    """Test case-insensitive allergen matching."""
    meal_plan = {
        "days": [
            {
                "meals": [
                    {
                        "recipe_name": "Dessert",
                        "ingredients": [
                            {"name": "AMANDES", "quantity": 30, "unit": "g"}
                        ],
                    }
                ]
            }
        ]
    }
    user_allergens = ["Fruits À Coque"]  # Mixed case
    violations = validate_allergens(meal_plan, user_allergens)
    assert len(violations) > 0


def test_validate_allergens_empty_allergens():
    """Test that empty allergen list returns no violations."""
    meal_plan = {
        "days": [
            {
                "meals": [
                    {
                        "recipe_name": "Any meal",
                        "ingredients": [
                            {"name": "anything", "quantity": 100, "unit": "g"}
                        ],
                    }
                ]
            }
        ]
    }
    user_allergens = []
    violations = validate_allergens(meal_plan, user_allergens)
    assert violations == []


def test_validate_daily_macros_within_tolerance():
    """Test macro validation passes when within ±10% tolerance."""
    daily_totals = {"calories": 2950, "protein_g": 170, "carbs_g": 340, "fat_g": 80}
    targets = {"calories": 3000, "protein_g": 180, "carbs_g": 350, "fat_g": 85}
    result = validate_daily_macros(daily_totals, targets)
    assert result["valid"] is True
    assert len(result["violations"]) == 0


def test_validate_daily_macros_outside_tolerance():
    """Test macro validation fails when outside ±10% tolerance."""
    daily_totals = {
        "calories": 2600,  # -13.3% from target (outside tolerance)
        "protein_g": 180,
        "carbs_g": 350,
        "fat_g": 85,
    }
    targets = {"calories": 3000, "protein_g": 180, "carbs_g": 350, "fat_g": 85}
    result = validate_daily_macros(daily_totals, targets)
    assert result["valid"] is False
    assert len(result["violations"]) > 0
    assert "calories" in result["violations"][0]


def test_validate_meal_plan_structure_valid():
    """Test meal plan structure validation passes for valid plan."""
    meal_plan = {
        "meal_plan_id": "plan_2024-12-23",
        "start_date": "2024-12-23",
        "days": [
            {
                "day": "Lundi 2024-12-23",
                "meals": [
                    {
                        "meal_type": "Petit-déjeuner",
                        "recipe_name": "Omelette",
                        "ingredients": [
                            {"name": "oeufs", "quantity": 3, "unit": "pièces"}
                        ],
                        "nutrition": {
                            "calories": 300,
                            "protein_g": 20,
                            "carbs_g": 10,
                            "fat_g": 15,
                        },
                    }
                ],
            }
        ],
    }
    result = validate_meal_plan_structure(meal_plan)
    assert result["valid"] is True
    assert len(result["missing_fields"]) == 0


def test_validate_meal_plan_structure_missing_fields():
    """Test meal plan structure validation fails when required fields missing."""
    meal_plan = {
        "start_date": "2024-12-23"
        # Missing meal_plan_id and days
    }
    result = validate_meal_plan_structure(meal_plan)
    assert result["valid"] is False
    assert "meal_plan.meal_plan_id" in result["missing_fields"]
    assert "meal_plan.days" in result["missing_fields"]


def test_validate_meal_plan_structure_empty_days():
    """Test meal plan structure validation fails for empty days array."""
    meal_plan = {
        "meal_plan_id": "plan_2024-12-23",
        "start_date": "2024-12-23",
        "days": [],
    }
    result = validate_meal_plan_structure(meal_plan)
    assert result["valid"] is False
    assert "meal_plan.days (empty array)" in result["missing_fields"]


@pytest.mark.parametrize(
    "allergen,ingredient,should_reject",
    [
        ("arachides", "beurre de cacahuète", True),
        ("arachides", "sauce satay", True),
        ("fruits à coque", "amandes", True),
        ("fruits à coque", "noix de cajou", True),
        ("fruits à coque", "noix de coco", False),  # False positive
        ("fruits à coque", "muscade", False),  # False positive
        ("lactose", "lait", True),
        ("lactose", "lait d'amande", False),  # Plant-based, no lactose
        ("gluten", "pain", True),
        ("gluten", "riz", False),
    ],
)
def test_allergen_edge_cases(allergen, ingredient, should_reject):
    """Test allergen edge cases with parametrized inputs."""
    meal_plan = {
        "days": [
            {
                "meals": [
                    {
                        "recipe_name": "Test",
                        "ingredients": [
                            {"name": ingredient, "quantity": 100, "unit": "g"}
                        ],
                    }
                ]
            }
        ]
    }
    violations = validate_allergens(meal_plan, [allergen])
    if should_reject:
        assert (
            len(violations) > 0
        ), f"Expected {ingredient} to be rejected for {allergen} allergy"
    else:
        assert (
            len(violations) == 0
        ), f"Expected {ingredient} to be allowed for {allergen} allergy"
