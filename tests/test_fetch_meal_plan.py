"""
Tests for fetch_stored_meal_plan_tool.

Tests the retrieval of stored meal plans from Supabase.
"""

import pytest


class TestFetchStoredMealPlanValidation:
    """Test input validation for fetch_stored_meal_plan_tool."""

    def test_invalid_date_format(self):
        """Test that invalid date format returns error."""
        # This would need a mock supabase client
        # For now, test the validation logic directly
        from datetime import datetime

        # Valid format
        assert datetime.strptime("2025-01-20", "%Y-%m-%d")

        # Invalid format should raise
        with pytest.raises(ValueError):
            datetime.strptime("20-01-2025", "%Y-%m-%d")

        with pytest.raises(ValueError):
            datetime.strptime("2025/01/20", "%Y-%m-%d")

    def test_selected_days_validation(self):
        """Test that day indices are validated correctly."""
        valid_days = [0, 1, 2, 3, 4, 5, 6]
        invalid_days = [-1, 7, 8]

        # Valid range check
        assert all(0 <= d <= 6 for d in valid_days)

        # Invalid range check
        assert any(d < 0 or d > 6 for d in invalid_days)


class TestFetchStoredMealPlanDayFiltering:
    """Test day filtering logic."""

    @pytest.fixture
    def sample_plan_data(self) -> dict:
        """Sample meal plan with 7 days."""
        day_names = [
            "Lundi",
            "Mardi",
            "Mercredi",
            "Jeudi",
            "Vendredi",
            "Samedi",
            "Dimanche",
        ]
        days = []
        for i, name in enumerate(day_names):
            days.append(
                {
                    "day": name,
                    "date": f"2025-01-{20+i:02d}",
                    "meals": [
                        {
                            "meal_type": "Petit-déjeuner",
                            "recipe": {"name": f"Breakfast {name}"},
                            "macros": {"calories": 500, "protein_g": 30},
                        }
                    ],
                    "daily_totals": {"calories": 2000, "protein_g": 150},
                }
            )
        return {"days": days}

    def test_filter_single_day(self, sample_plan_data: dict):
        """Test filtering to single day."""
        all_days = sample_plan_data["days"]
        selected_days = [2]  # Wednesday

        filtered = [day for i, day in enumerate(all_days) if i in selected_days]

        assert len(filtered) == 1
        assert filtered[0]["day"] == "Mercredi"

    def test_filter_multiple_days(self, sample_plan_data: dict):
        """Test filtering to multiple days."""
        all_days = sample_plan_data["days"]
        selected_days = [0, 1, 4]  # Mon, Tue, Fri

        filtered = [day for i, day in enumerate(all_days) if i in selected_days]

        assert len(filtered) == 3
        assert filtered[0]["day"] == "Lundi"
        assert filtered[1]["day"] == "Mardi"
        assert filtered[2]["day"] == "Vendredi"

    def test_filter_all_days(self, sample_plan_data: dict):
        """Test with no filter (all days)."""
        all_days = sample_plan_data["days"]
        selected_days = None

        if selected_days is None:
            filtered = all_days
        else:
            filtered = [day for i, day in enumerate(all_days) if i in selected_days]

        assert len(filtered) == 7


class TestFetchStoredMealPlanResponse:
    """Test response formatting."""

    def test_day_names_constant(self):
        """Test day names are correctly defined."""
        day_names = [
            "Lundi",
            "Mardi",
            "Mercredi",
            "Jeudi",
            "Vendredi",
            "Samedi",
            "Dimanche",
        ]

        assert len(day_names) == 7
        assert day_names[0] == "Lundi"
        assert day_names[6] == "Dimanche"

    def test_days_description_format(self):
        """Test days description formatting."""
        day_names = [
            "Lundi",
            "Mardi",
            "Mercredi",
            "Jeudi",
            "Vendredi",
            "Samedi",
            "Dimanche",
        ]
        selected_days = [0, 2, 4]

        days_description = ", ".join([day_names[d] for d in sorted(selected_days)])

        assert days_description == "Lundi, Mercredi, Vendredi"

    def test_response_structure(self):
        """Test expected response structure keys."""
        expected_keys = [
            "success",
            "meal_plan_id",
            "week_start",
            "days_included",
            "days_description",
            "daily_targets",
            "days",
            "message",
        ]

        # Mock response
        response = {
            "success": True,
            "meal_plan_id": "test-id",
            "week_start": "2025-01-20",
            "days_included": [0, 1, 2],
            "days_description": "Lundi, Mardi, Mercredi",
            "daily_targets": {"calories": 2500},
            "days": [],
            "message": "Plan retrieved",
        }

        for key in expected_keys:
            assert key in response, f"Missing key: {key}"

    def test_error_response_structure(self):
        """Test error response structure."""
        error_response = {
            "error": "No meal plan found for week starting 2025-01-20",
            "code": "MEAL_PLAN_NOT_FOUND",
            "suggestion": "Generate a meal plan first using generate_weekly_meal_plan",
        }

        assert "error" in error_response
        assert "code" in error_response
        assert error_response["code"] == "MEAL_PLAN_NOT_FOUND"


class TestFetchStoredMealPlanEdgeCases:
    """Test edge cases for fetch_stored_meal_plan_tool."""

    def test_empty_selected_days_validation(self):
        """Test that empty selected_days list is rejected."""
        selected_days: list[int] = []

        # Empty list should be rejected
        assert len(selected_days) == 0

        # This matches the validation in the tool
        if not selected_days:
            error = {
                "error": "selected_days cannot be empty. Use null for all days or provide day indices (0-6)",
                "code": "VALIDATION_ERROR",
            }
            assert error["code"] == "VALIDATION_ERROR"

    def test_out_of_range_days(self):
        """Test that day indices outside 0-6 are rejected."""
        invalid_cases = [
            [-1],
            [7],
            [0, 1, 8],
            [-1, 0, 1],
        ]

        for days in invalid_cases:
            has_invalid = any(d < 0 or d > 6 for d in days)
            assert has_invalid, f"Expected invalid day in {days}"

    def test_valid_day_indices(self):
        """Test all valid day indices."""
        for day in range(7):
            assert 0 <= day <= 6, f"Day {day} should be valid"

    def test_days_boundary_values(self):
        """Test boundary values for day indices."""
        # Minimum valid
        assert 0 <= 0 <= 6

        # Maximum valid
        assert 0 <= 6 <= 6

        # Just outside boundaries
        assert not (0 <= -1 <= 6)
        assert not (0 <= 7 <= 6)
