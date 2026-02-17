"""
Unit tests for meal_distribution.py module.

Tests macro distribution logic across different meal structures:
- 3_meals_2_snacks (75/25 split)
- 4_meals (equal distribution)
- 3_consequent_meals (equal distribution)
- 3_meals_1_preworkout (75/25 split)
"""

import pytest
from src.nutrition.meal_distribution import (
    calculate_meal_macros_distribution,
    MEAL_STRUCTURES,
)


def test_calculate_meal_macros_distribution_with_snacks():
    """Test distribution with snacks (75/25 split)."""
    result = calculate_meal_macros_distribution(
        daily_calories=3300,
        daily_protein_g=174,
        daily_carbs_g=413,
        daily_fat_g=92,
        meal_structure="3_meals_2_snacks",
    )

    # Should have 5 meals
    assert len(result["meals"]) == 5

    # Check daily totals are preserved
    assert result["daily_totals"]["calories"] == 3300
    assert result["daily_totals"]["protein_g"] == 174
    assert result["daily_totals"]["carbs_g"] == 413
    assert result["daily_totals"]["fat_g"] == 92

    # Main meals should get ~75% of calories
    main_meals = [
        m for m in result["meals"] if "collation" not in m["meal_type"].lower()
    ]
    snacks = [m for m in result["meals"] if "collation" in m["meal_type"].lower()]

    assert len(main_meals) == 3
    assert len(snacks) == 2

    # Each main meal should get approximately 3300 * 0.75 / 3 = 825 calories
    for meal in main_meals:
        assert 800 <= meal["target_calories"] <= 850

    # Each snack should get approximately 3300 * 0.25 / 2 = 412 calories
    for snack in snacks:
        assert 400 <= snack["target_calories"] <= 420


def test_calculate_meal_macros_distribution_without_snacks():
    """Test equal distribution without snacks."""
    result = calculate_meal_macros_distribution(
        daily_calories=2700,
        daily_protein_g=150,
        daily_carbs_g=300,
        daily_fat_g=75,
        meal_structure="3_consequent_meals",
    )

    # Should have 3 meals
    assert len(result["meals"]) == 3

    # Each meal should get approximately equal macros
    for meal in result["meals"]:
        # 2700 / 3 = 900 calories per meal
        assert meal["target_calories"] == 900
        # 150 / 3 = 50g protein per meal
        assert meal["target_protein_g"] == 50
        # 300 / 3 = 100g carbs per meal
        assert meal["target_carbs_g"] == 100
        # 75 / 3 = 25g fat per meal
        assert meal["target_fat_g"] == 25


def test_calculate_meal_macros_distribution_4_meals():
    """Test 4 equal meals distribution."""
    result = calculate_meal_macros_distribution(
        daily_calories=3200,
        daily_protein_g=160,
        daily_carbs_g=400,
        daily_fat_g=80,
        meal_structure="4_meals",
    )

    # Should have 4 meals
    assert len(result["meals"]) == 4

    # Each meal should get equal distribution
    for meal in result["meals"]:
        # 3200 / 4 = 800 calories per meal
        assert meal["target_calories"] == 800
        # 160 / 4 = 40g protein per meal
        assert meal["target_protein_g"] == 40


def test_calculate_meal_macros_distribution_preworkout():
    """Test 3 meals + 1 preworkout snack (75/25 split)."""
    result = calculate_meal_macros_distribution(
        daily_calories=3000,
        daily_protein_g=180,
        daily_carbs_g=375,
        daily_fat_g=83,
        meal_structure="3_meals_1_preworkout",
    )

    # Should have 4 meals (3 main + 1 snack)
    assert len(result["meals"]) == 4

    # Find the preworkout snack
    preworkout = [
        m for m in result["meals"] if "pré-entraînement" in m["meal_type"].lower()
    ]
    assert len(preworkout) == 1

    # Main meals get 75%, snack gets 25%
    main_meals = [
        m for m in result["meals"] if "pré-entraînement" not in m["meal_type"].lower()
    ]
    assert len(main_meals) == 3

    # Preworkout snack should get ~25% of calories
    # 3000 * 0.25 = 750 calories total for snacks, but only 1 snack
    assert 700 <= preworkout[0]["target_calories"] <= 800


def test_meal_type_and_time_extraction():
    """Test that meal types and times are correctly extracted."""
    result = calculate_meal_macros_distribution(
        daily_calories=2400,
        daily_protein_g=120,
        daily_carbs_g=300,
        daily_fat_g=60,
        meal_structure="3_consequent_meals",
    )

    # Check meal types are extracted correctly
    meal_types = [m["meal_type"] for m in result["meals"]]
    assert "Petit-déjeuner" in meal_types
    assert "Déjeuner" in meal_types
    assert "Dîner" in meal_types

    # Check times are extracted
    times = [m["time"] for m in result["meals"]]
    assert "08:00" in times
    assert "13:00" in times
    assert "19:00" in times


def test_invalid_meal_structure_raises_error():
    """Test that invalid meal structure raises ValueError."""
    with pytest.raises(ValueError, match="Invalid meal_structure"):
        calculate_meal_macros_distribution(
            daily_calories=3000,
            daily_protein_g=150,
            daily_carbs_g=375,
            daily_fat_g=83,
            meal_structure="invalid_structure",  # type: ignore
        )


def test_all_meal_structures_have_correct_format():
    """Test that all meal structures are properly defined."""
    for structure_name, structure_info in MEAL_STRUCTURES.items():
        assert "description" in structure_info
        assert "meals" in structure_info
        assert len(structure_info["meals"]) > 0

        # Each meal should have format "Name (HH:MM)"
        for meal in structure_info["meals"]:
            assert "(" in meal
            assert ")" in meal


def test_protein_distribution_80_20_with_snacks():
    """Test that protein follows 80/20 rule with snacks."""
    result = calculate_meal_macros_distribution(
        daily_calories=3300,
        daily_protein_g=200,  # Easy to calculate
        daily_carbs_g=413,
        daily_fat_g=92,
        meal_structure="3_meals_2_snacks",
    )

    main_meals = [
        m for m in result["meals"] if "collation" not in m["meal_type"].lower()
    ]
    snacks = [m for m in result["meals"] if "collation" in m["meal_type"].lower()]

    # Main meals should get 80% = 160g protein total / 3 = 53g each
    total_main_protein = sum(m["target_protein_g"] for m in main_meals)
    assert 155 <= total_main_protein <= 165  # Allow rounding tolerance

    # Snacks should get 20% = 40g protein total / 2 = 20g each
    total_snack_protein = sum(m["target_protein_g"] for m in snacks)
    assert 35 <= total_snack_protein <= 45  # Allow rounding tolerance


def test_zero_macros_edge_case():
    """Test handling of edge case with zero macros (shouldn't happen but defensive)."""
    result = calculate_meal_macros_distribution(
        daily_calories=1,
        daily_protein_g=1,
        daily_carbs_g=1,
        daily_fat_g=1,
        meal_structure="3_consequent_meals",
    )

    # Should not crash and should return 3 meals
    assert len(result["meals"]) == 3


def test_high_calorie_distribution():
    """Test distribution with very high calorie target (bulking athlete)."""
    result = calculate_meal_macros_distribution(
        daily_calories=5000,
        daily_protein_g=250,
        daily_carbs_g=625,
        daily_fat_g=139,
        meal_structure="4_meals",
    )

    assert len(result["meals"]) == 4

    # Each meal should get approximately 1250 calories
    for meal in result["meals"]:
        assert meal["target_calories"] == 1250
