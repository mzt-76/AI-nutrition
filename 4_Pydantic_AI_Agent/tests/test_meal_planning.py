"""
Tests for nutrition meal_planning module.

Tests prompt building, daily totals calculation, and response formatting.
"""

import json
from nutrition.meal_planning import (
    build_meal_plan_prompt,
    calculate_daily_totals,
    format_meal_plan_response,
    MEAL_STRUCTURES,
)


def test_build_meal_plan_prompt_contains_allergies():
    """Test that prompt contains allergy information in multiple places."""
    profile = {
        "allergies": ["arachides", "lactose"],
        "target_calories": 3000,
        "target_protein_g": 180,
        "target_carbs_g": 350,
        "target_fat_g": 85,
    }
    prompt = build_meal_plan_prompt(
        profile=profile,
        rag_context="RAG context here",
        start_date="2024-12-23",
        meal_structure="3_meals_2_snacks",
    )

    # Allergens should appear multiple times
    assert prompt.count("arachides") >= 3
    assert prompt.count("lactose") >= 3
    assert "ALLERGIES" in prompt
    assert "TOLÉRANCE ZÉRO" in prompt


def test_build_meal_plan_prompt_contains_targets():
    """Test that prompt contains nutritional targets."""
    profile = {
        "allergies": [],
        "target_calories": 2500,
        "target_protein_g": 150,
        "target_carbs_g": 300,
        "target_fat_g": 70,
    }
    prompt = build_meal_plan_prompt(
        profile=profile,
        rag_context="RAG context",
        start_date="2024-12-23",
        meal_structure="4_meals",
    )

    assert "2500" in prompt  # Calories
    assert "150" in prompt  # Protein
    assert "300" in prompt  # Carbs
    assert "70" in prompt  # Fat


def test_build_meal_plan_prompt_contains_meal_structure():
    """Test that prompt contains meal structure information."""
    profile = {
        "allergies": [],
        "target_calories": 3000,
        "target_protein_g": 180,
        "target_carbs_g": 350,
        "target_fat_g": 85,
    }
    prompt = build_meal_plan_prompt(
        profile=profile,
        rag_context="RAG context",
        start_date="2024-12-23",
        meal_structure="3_meals_1_preworkout",
    )

    assert "3_meals_1_preworkout" in prompt
    structure_info = MEAL_STRUCTURES["3_meals_1_preworkout"]
    assert structure_info["description"] in prompt


def test_build_meal_plan_prompt_with_notes():
    """Test that prompt includes additional notes."""
    profile = {
        "allergies": [],
        "target_calories": 3000,
        "target_protein_g": 180,
        "target_carbs_g": 350,
        "target_fat_g": 85,
    }
    notes = "Pas de viande rouge cette semaine"
    prompt = build_meal_plan_prompt(
        profile=profile,
        rag_context="RAG context",
        start_date="2024-12-23",
        meal_structure="3_meals_2_snacks",
        notes=notes,
    )

    assert notes in prompt


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
