"""Tests for pure utility functions in generate_week_plan.py.

No mocking needed — all functions under test are pure Python.
"""

import importlib.util
from datetime import datetime
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helper: load script via importlib (same pattern as test_generate_day_plan.py)
# ---------------------------------------------------------------------------


def _load_script(script_name: str):
    """Load a skill script by name."""
    project_root = Path(__file__).resolve().parent.parent
    script_path = (
        project_root / "skills" / "meal-planning" / "scripts" / f"{script_name}.py"
    )
    spec = importlib.util.spec_from_file_location(
        f"meal_planning.{script_name}", script_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Test: _get_current_monday
# ---------------------------------------------------------------------------


class TestGetCurrentMonday:
    def test_returns_monday_in_iso_format(self):
        """_get_current_monday returns a YYYY-MM-DD string whose weekday is Monday (0)."""
        module = _load_script("generate_week_plan")
        result = module._get_current_monday()

        # Must be a valid YYYY-MM-DD string
        dt = datetime.strptime(result, "%Y-%m-%d")
        assert (
            dt.weekday() == 0
        ), f"Expected Monday (weekday=0), got weekday={dt.weekday()} for {result}"


# ---------------------------------------------------------------------------
# Test: _parse_custom_requests
# ---------------------------------------------------------------------------


class TestParseCustomRequests:
    def setup_method(self):
        self.module = _load_script("generate_week_plan")
        self.parse = self.module._parse_custom_requests

    def test_empty_string(self):
        assert self.parse("") == {}

    def test_no_day_name(self):
        """Text with no French day name → empty dict."""
        assert self.parse("je veux des pâtes") == {}

    def test_single_day(self):
        """Day name followed by food → captured as custom request for that day."""
        result = self.parse("mardi risotto")
        assert "Mardi" in result
        assert result["Mardi"]["dejeuner"] == "risotto"

    def test_multiple_days(self):
        """Two day tokens each followed by their food → both days extracted."""
        result = self.parse("vendredi pizza mercredi soupe")
        assert "Vendredi" in result
        assert "Mercredi" in result
        assert result["Vendredi"]["dejeuner"] == "pizza"
        assert result["Mercredi"]["dejeuner"] == "soupe"

    def test_day_text_truncated_at_next_day(self):
        """Text between two day-name tokens is correctly bounded."""
        result = self.parse("risotto mardi soupe mercredi")
        assert "Mardi" in result
        # The text captured for Mardi should not include "mercredi" or "soupe"
        mardi_request = result["Mardi"]["dejeuner"].lower()
        assert "mercredi" not in mardi_request


# ---------------------------------------------------------------------------
# Test: _compute_weekly_summary
# ---------------------------------------------------------------------------


class TestComputeWeeklySummary:
    def setup_method(self):
        self.module = _load_script("generate_week_plan")
        self.compute = self.module._compute_weekly_summary

    def test_seven_days(self):
        """7 identical days → averages equal that day's values."""
        day = {
            "daily_totals": {
                "calories": 2100.0,
                "protein_g": 150.0,
                "carbs_g": 250.0,
                "fat_g": 70.0,
            }
        }
        result = self.compute([day] * 7)
        assert result["average_calories"] == pytest.approx(2100.0, abs=0.1)
        assert result["average_protein_g"] == pytest.approx(150.0, abs=0.1)
        assert result["average_carbs_g"] == pytest.approx(250.0, abs=0.1)
        assert result["average_fat_g"] == pytest.approx(70.0, abs=0.1)

    def test_single_day(self):
        """1 day → average equals that day's values."""
        day = {
            "daily_totals": {
                "calories": 1800.0,
                "protein_g": 120.0,
                "carbs_g": 200.0,
                "fat_g": 60.0,
            }
        }
        result = self.compute([day])
        assert result["average_calories"] == pytest.approx(1800.0, abs=0.1)

    def test_empty_list(self):
        """Empty list → empty dict."""
        assert self.compute([]) == {}
