"""
Integration tests for the refactored meal plan generation workflow.

Tests the complete pipeline:
1. Macro distribution across meals
2. Meal plan validation
3. Markdown document generation
4. Error logging
"""

import pytest

from nutrition.meal_distribution import (
    MEAL_STRUCTURES,
    calculate_meal_macros_distribution,
)
from nutrition.meal_plan_formatter import (
    format_meal_plan_as_markdown,
    generate_meal_plan_document,
)
from nutrition.error_logger import MealPlanErrorLogger


# ============================================================================
# Test Data Fixtures
# ============================================================================


@pytest.fixture
def sample_daily_targets() -> dict:
    """Sample daily macro targets for testing."""
    return {
        "calories": 2000,
        "protein": 150,
        "carbs": 200,
        "fat": 67,
    }


@pytest.fixture
def sample_user_profile() -> dict:
    """Sample user profile for testing."""
    return {
        "user_id": "test-user-123",
        "age": 30,
        "gender": "male",
        "weight_kg": 80,
        "height_cm": 180,
        "activity_level": "moderate",
        "goals": "maintenance",
        "allergies": ["peanuts", "shellfish"],
        "disliked_foods": ["liver"],
    }


@pytest.fixture
def sample_valid_meal_plan() -> dict:
    """Sample valid 7-day meal plan for testing."""
    days = []
    day_names = [
        "Lundi",
        "Mardi",
        "Mercredi",
        "Jeudi",
        "Vendredi",
        "Samedi",
        "Dimanche",
    ]

    for i, day_name in enumerate(day_names):
        day = {
            "day": day_name,
            "date": f"2025-01-{20 + i:02d}",
            "meals": [
                {
                    "meal_type": "Petit-déjeuner",
                    "time": "08:00",
                    "recipe": {
                        "name": f"Omelette du {day_name}",
                        "ingredients": [
                            {"name": "oeufs", "quantity": 3, "unit": "pièces"},
                            {"name": "épinards", "quantity": 50, "unit": "g"},
                        ],
                        "instructions": "Battre les oeufs. Cuire avec les épinards.",
                        "prep_time_minutes": 15,
                    },
                    "macros": {
                        "calories": 400,
                        "protein_g": 30,
                        "carbs_g": 10,
                        "fat_g": 28,
                    },
                },
                {
                    "meal_type": "Déjeuner",
                    "time": "13:00",
                    "recipe": {
                        "name": f"Poulet grillé du {day_name}",
                        "ingredients": [
                            {"name": "poulet", "quantity": 150, "unit": "g"},
                            {"name": "riz", "quantity": 100, "unit": "g"},
                        ],
                        "instructions": "Griller le poulet. Cuire le riz.",
                        "prep_time_minutes": 30,
                    },
                    "macros": {
                        "calories": 700,
                        "protein_g": 55,
                        "carbs_g": 80,
                        "fat_g": 15,
                    },
                },
                {
                    "meal_type": "Dîner",
                    "time": "19:00",
                    "recipe": {
                        "name": f"Saumon du {day_name}",
                        "ingredients": [
                            {"name": "saumon", "quantity": 150, "unit": "g"},
                            {"name": "légumes", "quantity": 200, "unit": "g"},
                        ],
                        "instructions": "Cuire le saumon au four. Rôtir les légumes.",
                        "prep_time_minutes": 35,
                    },
                    "macros": {
                        "calories": 600,
                        "protein_g": 45,
                        "carbs_g": 30,
                        "fat_g": 32,
                    },
                },
            ],
            "daily_totals": {
                "calories": 1700,
                "protein_g": 130,
                "carbs_g": 120,
                "fat_g": 75,
            },
        }
        days.append(day)

    return {
        "meal_plan_id": "test_plan_001",
        "start_date": "2025-01-20",
        "end_date": "2025-01-26",
        "user_id": "test-user-123",
        "meal_structure": "3_consequent_meals",
        "days": days,
    }


@pytest.fixture
def sample_invalid_meal_plan_missing_day() -> dict:
    """Sample invalid meal plan with missing days."""
    return {
        "meal_plan_id": "test_plan_invalid",
        "start_date": "2025-01-20",
        "end_date": "2025-01-26",
        "user_id": "test-user-123",
        "meal_structure": "3_consequent_meals",
        "days": [
            {
                "day": "Lundi",
                "date": "2025-01-20",
                "meals": [],
                "daily_totals": {
                    "calories": 0,
                    "protein_g": 0,
                    "carbs_g": 0,
                    "fat_g": 0,
                },
            }
        ],
    }


# ============================================================================
# Integration Tests: Macro Distribution → Validation
# ============================================================================


class TestMacroDistributionToValidation:
    """Test the flow from macro distribution to validation."""

    def test_distributed_macros_meet_validation_targets(
        self, sample_daily_targets: dict
    ) -> None:
        """Distributed macros should sum to daily targets within tolerance."""
        result = calculate_meal_macros_distribution(
            daily_calories=sample_daily_targets["calories"],
            daily_protein_g=sample_daily_targets["protein"],
            daily_carbs_g=sample_daily_targets["carbs"],
            daily_fat_g=sample_daily_targets["fat"],
            meal_structure="3_consequent_meals",
        )

        meals = result["meals"]
        daily_totals = result["daily_totals"]

        # Daily totals should match input
        assert daily_totals["calories"] == sample_daily_targets["calories"]
        assert daily_totals["protein_g"] == sample_daily_targets["protein"]
        assert daily_totals["carbs_g"] == sample_daily_targets["carbs"]
        assert daily_totals["fat_g"] == sample_daily_targets["fat"]

        # Sum of meal macros should match daily totals
        total_cal = sum(m["target_calories"] for m in meals)
        total_prot = sum(m["target_protein_g"] for m in meals)

        assert abs(total_cal - sample_daily_targets["calories"]) < 5
        assert abs(total_prot - sample_daily_targets["protein"]) < 2

    def test_all_structures_produce_valid_distributions(
        self, sample_daily_targets: dict
    ) -> None:
        """All meal structures should produce valid distributions."""
        for structure in MEAL_STRUCTURES.keys():
            result = calculate_meal_macros_distribution(
                daily_calories=sample_daily_targets["calories"],
                daily_protein_g=sample_daily_targets["protein"],
                daily_carbs_g=sample_daily_targets["carbs"],
                daily_fat_g=sample_daily_targets["fat"],
                meal_structure=structure,
            )

            meals = result["meals"]

            # Each structure should have correct number of meals
            expected_count = len(MEAL_STRUCTURES[structure]["meals"])
            assert len(meals) == expected_count

            # Each meal should have all required macros
            for meal in meals:
                assert "meal_type" in meal
                assert "time" in meal
                assert "target_calories" in meal
                assert "target_protein_g" in meal
                assert "target_carbs_g" in meal
                assert "target_fat_g" in meal
                assert all(v >= 0 for k, v in meal.items() if k.startswith("target_"))


# ============================================================================
# Integration Tests: Meal Plan Validation
# ============================================================================


class TestMealPlanValidation:
    """Test meal plan validation functionality."""

    def test_structure_validation_passes_for_valid_plan(self) -> None:
        """A properly structured meal plan should pass structure validation."""
        from nutrition.validators import validate_meal_plan_structure

        # Create a fully complete meal plan with all required fields
        valid_plan = {
            "meal_plan_id": "test_001",
            "start_date": "2025-01-20",
            "days": [
                {
                    "day": f"Day {i}",
                    "date": f"2025-01-{20+i:02d}",
                    "meals": [
                        {
                            "meal_type": "Petit-déjeuner",
                            "recipe_name": "Test Recipe",
                            "ingredients": [
                                {"name": "test", "quantity": 100, "unit": "g"}
                            ],
                            "nutrition": {
                                "calories": 500,
                                "protein_g": 30,
                                "carbs_g": 50,
                                "fat_g": 20,
                            },
                        },
                        {
                            "meal_type": "Déjeuner",
                            "recipe_name": "Test Recipe 2",
                            "ingredients": [
                                {"name": "test2", "quantity": 100, "unit": "g"}
                            ],
                            "nutrition": {
                                "calories": 700,
                                "protein_g": 50,
                                "carbs_g": 80,
                                "fat_g": 25,
                            },
                        },
                        {
                            "meal_type": "Dîner",
                            "recipe_name": "Test Recipe 3",
                            "ingredients": [
                                {"name": "test3", "quantity": 100, "unit": "g"}
                            ],
                            "nutrition": {
                                "calories": 600,
                                "protein_g": 40,
                                "carbs_g": 60,
                                "fat_g": 22,
                            },
                        },
                    ],
                    "daily_totals": {
                        "calories": 1800,
                        "protein_g": 120,
                        "carbs_g": 190,
                        "fat_g": 67,
                    },
                }
                for i in range(7)
            ],
        }

        result = validate_meal_plan_structure(valid_plan)
        assert result["valid"] is True

    def test_structure_validation_fails_for_missing_days(self) -> None:
        """A meal plan with missing days should fail structure validation."""
        from nutrition.validators import validate_meal_plan_structure

        invalid_plan = {
            "meal_plan_id": "test_invalid",
            "start_date": "2025-01-20",
            "days": [
                {"day": "Lundi", "meals": [], "daily_totals": {}},
            ],
        }

        result = validate_meal_plan_structure(invalid_plan)
        assert result["valid"] is False

    def test_allergen_validation_detects_allergens(self) -> None:
        """Allergen validation should detect ingredients matching user allergens."""
        from nutrition.validators import validate_allergens

        meal_plan = {
            "days": [
                {
                    "day": "Lundi",
                    "meals": [
                        {
                            "recipe_name": "Test Recipe",
                            "ingredients": [
                                {"name": "poulet", "quantity": 150},
                                {"name": "cacahuètes", "quantity": 20},
                            ],
                        }
                    ],
                }
            ]
        }

        # validate_allergens returns a list of violation strings
        violations = validate_allergens(
            meal_plan, ["peanuts", "arachides", "cacahuètes"]
        )
        assert len(violations) > 0  # Should detect cacahuètes as an allergen


# ============================================================================
# Integration Tests: Markdown Document Generation
# ============================================================================


class TestMarkdownDocumentGeneration:
    """Test markdown document generation from meal plans."""

    def test_format_meal_plan_as_markdown_structure(
        self, sample_valid_meal_plan: dict
    ) -> None:
        """Generated markdown should have proper structure."""
        markdown = format_meal_plan_as_markdown(sample_valid_meal_plan, meal_plan_id=1)

        # Check header
        assert "# Plan de Repas Hebdomadaire" in markdown

        # Check all days are present
        for day_name in [
            "Lundi",
            "Mardi",
            "Mercredi",
            "Jeudi",
            "Vendredi",
            "Samedi",
            "Dimanche",
        ]:
            assert day_name in markdown

    def test_format_meal_plan_includes_ingredients(
        self, sample_valid_meal_plan: dict
    ) -> None:
        """Generated markdown should include ingredient lists."""
        # Add ingredients in the expected format (at meal level, not in recipe)
        sample_valid_meal_plan["days"][0]["meals"][0]["ingredients"] = [
            {"name": "oeufs", "quantity": 3, "unit": "pièces"},
        ]
        sample_valid_meal_plan["days"][0]["meals"][1]["ingredients"] = [
            {"name": "poulet", "quantity": 150, "unit": "g"},
        ]
        sample_valid_meal_plan["days"][0]["meals"][2]["ingredients"] = [
            {"name": "saumon", "quantity": 150, "unit": "g"},
        ]

        markdown = format_meal_plan_as_markdown(sample_valid_meal_plan, meal_plan_id=1)

        # Check some ingredients are present
        assert "oeufs" in markdown.lower() or "œufs" in markdown.lower()
        assert "poulet" in markdown.lower()
        assert "saumon" in markdown.lower()

    def test_format_meal_plan_includes_macros(
        self, sample_valid_meal_plan: dict
    ) -> None:
        """Generated markdown should include macro information."""
        markdown = format_meal_plan_as_markdown(sample_valid_meal_plan, meal_plan_id=1)

        # Check for macro keywords
        assert "kcal" in markdown.lower() or "calories" in markdown.lower()
        assert "protéines" in markdown.lower() or "protein" in markdown.lower()

    def test_generate_meal_plan_document_creates_file(
        self,
        sample_valid_meal_plan: dict,
        tmp_path,
    ) -> None:
        """Document generation should create a file on disk."""
        output_dir = tmp_path / "meal_plans"
        output_dir.mkdir()

        file_path = generate_meal_plan_document(
            meal_plan=sample_valid_meal_plan,
            output_dir=str(output_dir),
        )

        assert file_path is not None
        assert file_path.endswith(".md")

        # Verify file exists and has content
        from pathlib import Path

        path = Path(file_path)
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert len(content) > 100  # Should have meaningful content


# ============================================================================
# Integration Tests: Error Logging
# ============================================================================


class TestErrorLogging:
    """Test error logging functionality."""

    def test_error_logger_creates_log_file(self, tmp_path) -> None:
        """Error logger should create log files in specified directory."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        logger = MealPlanErrorLogger(log_dir=str(log_dir))

        logger.log_generation_error(
            error_type="validation_failed",
            error_message="Test error message",
            context={
                "user_id": "test-user",
                "attempt": 1,
            },
        )

        # Check log file was created
        log_files = list(log_dir.glob("meal_plan_errors_*.json"))
        assert len(log_files) == 1

        # Check content
        import json

        with open(log_files[0], "r") as f:
            log_data = json.load(f)

        assert log_data["error_type"] == "validation_failed"
        assert log_data["error_message"] == "Test error message"
        assert "timestamp" in log_data

    def test_error_logger_captures_validation_failures(self, tmp_path) -> None:
        """Error logger should capture detailed validation failure info."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        logger = MealPlanErrorLogger(log_dir=str(log_dir))

        validation_errors = [
            "Missing day 3",
            "Macro deviation: protein -15%",
            "Allergen found: peanuts",
        ]

        logger.log_validation_failure(
            validation_errors=validation_errors,
            meal_plan_summary={"total_days": 6, "structure": "3_meals"},
            targets={"calories": 2000, "protein": 150},
        )

        log_files = list(log_dir.glob("meal_plan_errors_*.json"))
        assert len(log_files) == 1

        import json

        with open(log_files[0], "r") as f:
            log_data = json.load(f)

        assert log_data["error_type"] == "validation_failure"
        assert len(log_data["validation_errors"]) == 3
        assert "peanuts" in str(log_data["validation_errors"])


# ============================================================================
# Integration Tests: Complete Workflow (Mocked)
# ============================================================================


class TestCompleteWorkflowMocked:
    """Test the complete workflow with mocked external dependencies."""

    @pytest.mark.asyncio
    async def test_workflow_happy_path(
        self,
        sample_daily_targets: dict,
    ) -> None:
        """Test the complete workflow succeeds with valid inputs."""
        # Step 1: Distribute macros
        result = calculate_meal_macros_distribution(
            daily_calories=sample_daily_targets["calories"],
            daily_protein_g=sample_daily_targets["protein"],
            daily_carbs_g=sample_daily_targets["carbs"],
            daily_fat_g=sample_daily_targets["fat"],
            meal_structure="3_consequent_meals",
        )

        assert len(result["meals"]) == 3

        # Step 2: Would normally generate meal plan via LLM (mocked)
        # For this test, we simulate a valid response

        # Step 3: Validate the structure
        from nutrition.validators import validate_meal_plan_structure

        # Create a mock meal plan structure with all required fields
        mock_meal_plan = {
            "meal_plan_id": "mock_plan",
            "start_date": "2025-01-20",
            "days": [
                {
                    "day": f"Day {i}",
                    "date": f"2025-01-{20 + i:02d}",
                    "meals": [
                        {
                            "meal_type": "Petit-déjeuner",
                            "time": "08:00",
                            "recipe_name": "Test Breakfast",
                            "ingredients": [
                                {"name": "test", "quantity": 100, "unit": "g"}
                            ],
                            "nutrition": {"calories": 500, "protein_g": 40},
                        },
                        {
                            "meal_type": "Déjeuner",
                            "time": "13:00",
                            "recipe_name": "Test Lunch",
                            "ingredients": [
                                {"name": "test", "quantity": 100, "unit": "g"}
                            ],
                            "nutrition": {"calories": 700, "protein_g": 55},
                        },
                        {
                            "meal_type": "Dîner",
                            "time": "19:00",
                            "recipe_name": "Test Dinner",
                            "ingredients": [
                                {"name": "test", "quantity": 100, "unit": "g"}
                            ],
                            "nutrition": {"calories": 600, "protein_g": 45},
                        },
                    ],
                    "daily_totals": {
                        "calories": sample_daily_targets["calories"],
                        "protein_g": sample_daily_targets["protein"],
                        "carbs_g": sample_daily_targets["carbs"],
                        "fat_g": sample_daily_targets["fat"],
                    },
                }
                for i in range(7)
            ],
        }

        structure_result = validate_meal_plan_structure(mock_meal_plan)
        assert structure_result["valid"] is True

    @pytest.mark.asyncio
    async def test_workflow_handles_validation_failure(
        self,
        sample_daily_targets: dict,
        tmp_path,
    ) -> None:
        """Test that workflow properly handles validation failures."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        logger = MealPlanErrorLogger(log_dir=str(log_dir))

        # Simulate a validation failure
        invalid_plan = {
            "meal_plan_id": "invalid",
            "start_date": "2025-01-20",
            "days": [{"day": "Lundi", "meals": []}],
        }

        from nutrition.validators import validate_meal_plan_structure

        result = validate_meal_plan_structure(invalid_plan)

        if not result["valid"]:
            logger.log_validation_failure(
                validation_errors=["Missing 6 days"],
                meal_plan_summary={"total_days": 1},
                targets=sample_daily_targets,
            )

        # Verify error was logged
        log_files = list(log_dir.glob("meal_plan_errors_*.json"))
        assert len(log_files) == 1


# ============================================================================
# Integration Tests: Structure Display Names
# ============================================================================


class TestStructureDisplayNames:
    """Test meal structure display name functionality."""

    def test_all_structures_have_descriptions(self) -> None:
        """All meal structures should have descriptions."""
        for structure_key, structure_info in MEAL_STRUCTURES.items():
            assert "description" in structure_info
            assert len(structure_info["description"]) > 0
            assert "meals" in structure_info
            assert len(structure_info["meals"]) >= 3


# ============================================================================
# Run tests with: pytest tests/test_meal_plan_workflow_integration.py -v
# ============================================================================
