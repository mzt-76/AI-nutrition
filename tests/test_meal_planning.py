"""
Tests for nutrition meal_planning module.

Tests daily totals calculation, response formatting, and meal structures.
"""

import json
from src.nutrition.meal_planning import (
    calculate_daily_totals,
    format_meal_plan_response,
    MEAL_STRUCTURES,
)


def test_calculate_daily_totals():
    """Test summing nutritional totals from meals."""
    meals = [
        {"nutrition": {"calories": 500, "protein_g": 30, "carbs_g": 50, "fat_g": 15}},
        {"nutrition": {"calories": 600, "protein_g": 35, "carbs_g": 60, "fat_g": 20}},
        {"nutrition": {"calories": 700, "protein_g": 40, "carbs_g": 70, "fat_g": 25}},
    ]

    totals = calculate_daily_totals(meals)

    assert totals["calories"] == 1800
    assert totals["protein_g"] == 105
    assert totals["carbs_g"] == 180
    assert totals["fat_g"] == 60


def test_calculate_daily_totals_empty_meals():
    """Test that empty meals list returns zero totals."""
    meals = []
    totals = calculate_daily_totals(meals)

    assert totals["calories"] == 0
    assert totals["protein_g"] == 0
    assert totals["carbs_g"] == 0
    assert totals["fat_g"] == 0


def test_calculate_daily_totals_missing_nutrition():
    """Test that meals with missing nutrition fields don't crash."""
    meals = [
        {"nutrition": {"calories": 500, "protein_g": 30, "carbs_g": 50, "fat_g": 15}},
        {},  # Missing nutrition field
        {"nutrition": {"calories": 600, "protein_g": 35, "carbs_g": 60, "fat_g": 20}},
    ]

    totals = calculate_daily_totals(meals)

    assert totals["calories"] == 1100
    assert totals["protein_g"] == 65
    assert totals["carbs_g"] == 110
    assert totals["fat_g"] == 35


def test_format_meal_plan_response_success():
    """Test formatting meal plan response with successful storage."""
    meal_plan = {
        "meal_plan_id": "plan_2024-12-23",
        "start_date": "2024-12-23",
        "meal_structure": "3_meals_2_snacks",
        "days": [
            {"day": "Lundi", "meals": []},
            {"day": "Mardi", "meals": []},
            {"day": "Mercredi", "meals": []},
            {"day": "Jeudi", "meals": []},
            {"day": "Vendredi", "meals": []},
            {"day": "Samedi", "meals": []},
            {"day": "Dimanche", "meals": []},
        ],
        "weekly_summary": {"total_unique_recipes": 21, "avg_prep_time_min": 35},
    }

    response = format_meal_plan_response(meal_plan, store_success=True)
    response_data = json.loads(response)

    assert response_data["success"] is True
    assert response_data["stored_in_database"] is True
    assert response_data["summary"]["total_days"] == 7
    assert response_data["summary"]["start_date"] == "2024-12-23"
    assert response_data["meal_plan"]["meal_plan_id"] == "plan_2024-12-23"


def test_format_meal_plan_response_storage_failed():
    """Test formatting meal plan response when storage failed."""
    meal_plan = {
        "meal_plan_id": "plan_2024-12-23",
        "start_date": "2024-12-23",
        "meal_structure": "4_meals",
        "days": [],
    }

    response = format_meal_plan_response(meal_plan, store_success=False)
    response_data = json.loads(response)

    assert response_data["success"] is True  # Plan still generated
    assert response_data["stored_in_database"] is False


def test_meal_structures_completeness():
    """Test that all meal structures have required fields."""
    for structure_name, structure_info in MEAL_STRUCTURES.items():
        assert "description" in structure_info, f"{structure_name} missing description"
        assert "meals" in structure_info, f"{structure_name} missing meals"
        assert isinstance(
            structure_info["meals"], list
        ), f"{structure_name} meals must be list"
        assert (
            len(structure_info["meals"]) > 0
        ), f"{structure_name} meals cannot be empty"


def test_meal_structures_count():
    """Test that meal structures have expected meal counts."""
    assert len(MEAL_STRUCTURES["3_meals_2_snacks"]["meals"]) == 5
    assert len(MEAL_STRUCTURES["4_meals"]["meals"]) == 4
    assert len(MEAL_STRUCTURES["3_consequent_meals"]["meals"]) == 3
    assert len(MEAL_STRUCTURES["3_meals_1_preworkout"]["meals"]) == 4
