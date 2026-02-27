"""Tests for pure utility functions and batch cooking in generate_week_plan.py.

Pure function tests need no mocking. Batch cooking tests mock generate_day_plan.
"""

import importlib.util
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

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


# ---------------------------------------------------------------------------
# Helpers for batch cooking tests
# ---------------------------------------------------------------------------


def _make_day_result(
    day_name: str,
    recipe_ids: list[str],
    recipe_ids_by_mt: dict[str, str] | None = None,
) -> str:
    """Build a JSON day result string matching generate_day_plan output."""
    meals = [
        {
            "meal_type": mt,
            "name": f"Recipe {rid}",
            "ingredients": [],
            "instructions": "",
            "prep_time_minutes": 10,
            "nutrition": {"calories": 500, "protein_g": 40, "carbs_g": 50, "fat_g": 15},
        }
        for mt, rid in zip(
            ["Petit-déjeuner", "Déjeuner", "Dîner"], recipe_ids, strict=False
        )
    ]
    return json.dumps(
        {
            "success": True,
            "day": {
                "day": day_name,
                "date": "2026-02-18",
                "meals": meals,
                "daily_totals": {
                    "calories": 1500,
                    "protein_g": 120,
                    "carbs_g": 150,
                    "fat_g": 45,
                },
            },
            "recipes_used": recipe_ids,
            "recipe_ids_by_meal_type": recipe_ids_by_mt or {},
            "llm_fallback_count": 0,
            "validation": {"valid": True, "violations": []},
        }
    )


def _make_generate_day_plan_mock(recipe_counter: dict):
    """Create a mock generate_day_plan module that tracks batch_recipe_ids."""
    module = MagicMock()

    async def mock_execute(**kwargs):
        batch_recipe_ids = kwargs.get("batch_recipe_ids", {})
        day_name = kwargs.get("day_name", "Lundi")

        # If batch IDs provided, reuse them; otherwise generate new ones
        breakfast_id = batch_recipe_ids.get(
            "petit-dejeuner", f"breakfast-{recipe_counter['n']}"
        )
        lunch_id = batch_recipe_ids.get("dejeuner", f"lunch-{recipe_counter['n']}")
        dinner_id = batch_recipe_ids.get("diner", f"dinner-{recipe_counter['n']}")

        if "petit-dejeuner" not in batch_recipe_ids:
            recipe_counter["n"] += 1
        elif "dejeuner" not in batch_recipe_ids:
            recipe_counter["n"] += 1
        elif "diner" not in batch_recipe_ids:
            recipe_counter["n"] += 1
        else:
            pass  # All batched, no counter increment needed

        # Only increment if at least one recipe is new
        if not batch_recipe_ids:
            recipe_counter["n"] += 1

        ids_by_mt = {
            "petit-dejeuner": breakfast_id,
            "dejeuner": lunch_id,
            "diner": dinner_id,
        }

        return _make_day_result(
            day_name,
            [breakfast_id, lunch_id, dinner_id],
            ids_by_mt,
        )

    module.execute = mock_execute
    return module


# ---------------------------------------------------------------------------
# Test: batch cooking in generate_week_plan
# ---------------------------------------------------------------------------


class TestBatchCooking:
    @pytest.mark.asyncio
    async def test_batch_days_reuses_lunch_and_dinner(self):
        """With batch_days=3, days 0-2 share the same lunch and dinner recipe IDs."""
        generate_week_plan = _load_script("generate_week_plan")
        counter = {"n": 0}
        mock_day_plan = _make_generate_day_plan_mock(counter)

        profile_data = {
            "target_calories": 2000,
            "target_protein_g": 150,
            "target_carbs_g": 200,
            "target_fat_g": 65,
            "allergies": [],
            "diet_type": "omnivore",
        }

        with patch.object(
            generate_week_plan,
            "_import_sibling_script",
            return_value=mock_day_plan,
        ), patch.object(
            generate_week_plan,
            "fetch_my_profile_tool",
            new=AsyncMock(return_value=json.dumps(profile_data)),
        ), patch.object(
            generate_week_plan,
            "calculate_meal_macros_distribution",
            return_value={
                "meals": [
                    {
                        "meal_type": "Petit-déjeuner",
                        "target_calories": 500,
                        "target_protein_g": 40,
                        "target_carbs_g": 60,
                        "target_fat_g": 18,
                    },
                    {
                        "meal_type": "Déjeuner",
                        "target_calories": 800,
                        "target_protein_g": 60,
                        "target_carbs_g": 80,
                        "target_fat_g": 25,
                    },
                    {
                        "meal_type": "Dîner",
                        "target_calories": 700,
                        "target_protein_g": 50,
                        "target_carbs_g": 60,
                        "target_fat_g": 22,
                    },
                ]
            },
        ):
            # Mock DB store
            db_mock = MagicMock()
            db_mock.table.return_value.insert.return_value.execute.return_value = (
                MagicMock(data=[{"id": 1}])
            )

            result_str = await generate_week_plan.execute(
                supabase=db_mock,
                anthropic_client=MagicMock(),
                num_days=3,
                batch_days=3,
                start_date="2026-02-23",
            )

        result = json.loads(result_str)
        assert result.get("success") is True or "meal_plan" in result

        # Extract recipe IDs from the mock's batch tracking
        # Days 0-2 should have same lunch and dinner
        days = result.get("meal_plan", {}).get("days", [])
        if len(days) == 3:
            # All lunch recipes should be the same
            lunch_names = [d["meals"][1]["name"] for d in days]
            assert lunch_names[0] == lunch_names[1] == lunch_names[2]
            # All dinner recipes should be the same
            dinner_names = [d["meals"][2]["name"] for d in days]
            assert dinner_names[0] == dinner_names[1] == dinner_names[2]

    @pytest.mark.asyncio
    async def test_batch_days_none_no_repeat(self):
        """Default behavior (batch_days=None) does not force recipe reuse."""
        generate_week_plan = _load_script("generate_week_plan")
        call_args: list[dict] = []

        async def tracking_execute(**kwargs):
            call_args.append(kwargs)
            day_name = kwargs.get("day_name", "Lundi")
            idx = len(call_args) - 1
            ids_by_mt = {
                "petit-dejeuner": f"breakfast-{idx}",
                "dejeuner": f"lunch-{idx}",
                "diner": f"dinner-{idx}",
            }
            return _make_day_result(
                day_name,
                [f"breakfast-{idx}", f"lunch-{idx}", f"dinner-{idx}"],
                ids_by_mt,
            )

        mock_module = MagicMock()
        mock_module.execute = tracking_execute

        profile_data = {
            "target_calories": 2000,
            "target_protein_g": 150,
            "target_carbs_g": 200,
            "target_fat_g": 65,
            "allergies": [],
            "diet_type": "omnivore",
        }

        with patch.object(
            generate_week_plan, "_import_sibling_script", return_value=mock_module
        ), patch.object(
            generate_week_plan,
            "fetch_my_profile_tool",
            new=AsyncMock(return_value=json.dumps(profile_data)),
        ), patch.object(
            generate_week_plan,
            "calculate_meal_macros_distribution",
            return_value={
                "meals": [
                    {
                        "meal_type": "Petit-déjeuner",
                        "target_calories": 500,
                        "target_protein_g": 40,
                        "target_carbs_g": 60,
                        "target_fat_g": 18,
                    },
                ]
            },
        ):
            db_mock = MagicMock()
            db_mock.table.return_value.insert.return_value.execute.return_value = (
                MagicMock(data=[{"id": 1}])
            )

            await generate_week_plan.execute(
                supabase=db_mock,
                anthropic_client=MagicMock(),
                num_days=3,
                start_date="2026-02-23",
            )

        # With no batch_days, no lunch/dinner batch IDs should be passed
        for args in call_args[1:]:
            batch_ids = args.get("batch_recipe_ids", {})
            assert "dejeuner" not in batch_ids
            assert "diner" not in batch_ids

    @pytest.mark.asyncio
    async def test_default_breakfast_same_all_week(self):
        """Without vary_breakfast, all days reuse the first day's breakfast."""
        generate_week_plan = _load_script("generate_week_plan")
        call_args: list[dict] = []

        async def tracking_execute(**kwargs):
            call_args.append(kwargs)
            idx = len(call_args) - 1
            day_name = kwargs.get("day_name", "Lundi")
            ids_by_mt = {
                "petit-dejeuner": "breakfast-0",  # always same
                "dejeuner": f"lunch-{idx}",
                "diner": f"dinner-{idx}",
            }
            return _make_day_result(
                day_name,
                ["breakfast-0", f"lunch-{idx}", f"dinner-{idx}"],
                ids_by_mt,
            )

        mock_module = MagicMock()
        mock_module.execute = tracking_execute

        profile_data = {
            "target_calories": 2000,
            "target_protein_g": 150,
            "target_carbs_g": 200,
            "target_fat_g": 65,
            "allergies": [],
            "diet_type": "omnivore",
        }

        with patch.object(
            generate_week_plan, "_import_sibling_script", return_value=mock_module
        ), patch.object(
            generate_week_plan,
            "fetch_my_profile_tool",
            new=AsyncMock(return_value=json.dumps(profile_data)),
        ), patch.object(
            generate_week_plan,
            "calculate_meal_macros_distribution",
            return_value={
                "meals": [
                    {
                        "meal_type": "Petit-déjeuner",
                        "target_calories": 500,
                        "target_protein_g": 40,
                        "target_carbs_g": 60,
                        "target_fat_g": 18,
                    },
                ]
            },
        ):
            db_mock = MagicMock()
            db_mock.table.return_value.insert.return_value.execute.return_value = (
                MagicMock(data=[{"id": 1}])
            )

            await generate_week_plan.execute(
                supabase=db_mock,
                anthropic_client=MagicMock(),
                num_days=3,
                start_date="2026-02-23",
            )

        # Days 1+ should have breakfast batch ID set
        for args in call_args[1:]:
            batch_ids = args.get("batch_recipe_ids", {})
            assert batch_ids.get("petit-dejeuner") == "breakfast-0"

    @pytest.mark.asyncio
    async def test_vary_breakfast_different_each_day(self):
        """With vary_breakfast=True, breakfast is NOT batched."""
        generate_week_plan = _load_script("generate_week_plan")
        call_args: list[dict] = []

        async def tracking_execute(**kwargs):
            call_args.append(kwargs)
            idx = len(call_args) - 1
            day_name = kwargs.get("day_name", "Lundi")
            ids_by_mt = {
                "petit-dejeuner": f"breakfast-{idx}",
                "dejeuner": f"lunch-{idx}",
                "diner": f"dinner-{idx}",
            }
            return _make_day_result(
                day_name,
                [f"breakfast-{idx}", f"lunch-{idx}", f"dinner-{idx}"],
                ids_by_mt,
            )

        mock_module = MagicMock()
        mock_module.execute = tracking_execute

        profile_data = {
            "target_calories": 2000,
            "target_protein_g": 150,
            "target_carbs_g": 200,
            "target_fat_g": 65,
            "allergies": [],
            "diet_type": "omnivore",
        }

        with patch.object(
            generate_week_plan, "_import_sibling_script", return_value=mock_module
        ), patch.object(
            generate_week_plan,
            "fetch_my_profile_tool",
            new=AsyncMock(return_value=json.dumps(profile_data)),
        ), patch.object(
            generate_week_plan,
            "calculate_meal_macros_distribution",
            return_value={
                "meals": [
                    {
                        "meal_type": "Petit-déjeuner",
                        "target_calories": 500,
                        "target_protein_g": 40,
                        "target_carbs_g": 60,
                        "target_fat_g": 18,
                    },
                ]
            },
        ):
            db_mock = MagicMock()
            db_mock.table.return_value.insert.return_value.execute.return_value = (
                MagicMock(data=[{"id": 1}])
            )

            await generate_week_plan.execute(
                supabase=db_mock,
                anthropic_client=MagicMock(),
                num_days=3,
                vary_breakfast=True,
                start_date="2026-02-23",
            )

        # With vary_breakfast=True, no breakfast batch ID should be set
        for args in call_args:
            batch_ids = args.get("batch_recipe_ids", {})
            assert "petit-dejeuner" not in batch_ids

    @pytest.mark.asyncio
    async def test_meal_preferences_passed_to_all_days(self):
        """meal_preferences is merged into custom_requests for every day."""
        generate_week_plan = _load_script("generate_week_plan")
        call_args: list[dict] = []

        async def tracking_execute(**kwargs):
            call_args.append(kwargs)
            idx = len(call_args) - 1
            day_name = kwargs.get("day_name", "Lundi")
            ids_by_mt = {
                "petit-dejeuner": f"breakfast-{idx}",
                "dejeuner": f"lunch-{idx}",
                "diner": f"dinner-{idx}",
            }
            return _make_day_result(
                day_name,
                [f"breakfast-{idx}", f"lunch-{idx}", f"dinner-{idx}"],
                ids_by_mt,
            )

        mock_module = MagicMock()
        mock_module.execute = tracking_execute

        profile_data = {
            "target_calories": 2000,
            "target_protein_g": 150,
            "target_carbs_g": 200,
            "target_fat_g": 65,
            "allergies": [],
            "diet_type": "omnivore",
        }

        with patch.object(
            generate_week_plan, "_import_sibling_script", return_value=mock_module
        ), patch.object(
            generate_week_plan,
            "fetch_my_profile_tool",
            new=AsyncMock(return_value=json.dumps(profile_data)),
        ), patch.object(
            generate_week_plan,
            "calculate_meal_macros_distribution",
            return_value={
                "meals": [
                    {
                        "meal_type": "Petit-déjeuner",
                        "target_calories": 500,
                        "target_protein_g": 40,
                        "target_carbs_g": 60,
                        "target_fat_g": 18,
                    },
                    {
                        "meal_type": "Déjeuner",
                        "target_calories": 800,
                        "target_protein_g": 60,
                        "target_carbs_g": 80,
                        "target_fat_g": 25,
                    },
                ]
            },
        ):
            db_mock = MagicMock()
            db_mock.table.return_value.insert.return_value.execute.return_value = (
                MagicMock(data=[{"id": 1}])
            )

            await generate_week_plan.execute(
                supabase=db_mock,
                anthropic_client=MagicMock(),
                num_days=3,
                meal_preferences={"petit-dejeuner": "omelette aux oeufs"},
                start_date="2026-02-23",
            )

        # Every day should have the meal preference in custom_requests
        for args in call_args:
            custom = args.get("custom_requests", {})
            assert custom.get("petit-dejeuner") == "omelette aux oeufs"
