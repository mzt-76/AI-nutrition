"""Tests for profile target caching — auto-persist nutrition calculations.

Covers:
1. update_my_profile_tool accepts the 6 nutrition fields
2. calculate_nutritional_needs auto-persists to DB
3. No persist when user_id is None
4. Persist failure doesn't break calculation result
"""

import importlib.util
import json
from pathlib import Path
import pytest
from unittest.mock import MagicMock

from src.tools import update_my_profile_tool

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_calc_execute():
    """Import execute() from the hyphenated skill directory."""
    script_path = (
        PROJECT_ROOT
        / "skills"
        / "nutrition-calculating"
        / "scripts"
        / "calculate_nutritional_needs.py"
    )
    spec = importlib.util.spec_from_file_location("calc_needs", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.execute


# ============================================================================
# Helpers
# ============================================================================


def _make_supabase_mock(updated_profile: dict | None = None) -> MagicMock:
    """Build a Supabase mock wired for update chain."""
    mock = MagicMock()
    result = MagicMock()
    result.data = [updated_profile] if updated_profile else []

    chain = mock.table.return_value
    chain.update.return_value.eq.return_value.execute.return_value = result
    return mock


# ============================================================================
# Test 1: update_my_profile_tool accepts nutrition fields
# ============================================================================


class TestUpdateProfileNutritionFields:
    """update_my_profile_tool correctly passes the 6 nutrition fields to Supabase."""

    @pytest.mark.asyncio
    async def test_update_profile_tool_accepts_nutrition_fields(self):
        """All 6 nutrition fields are included in the update dict sent to Supabase."""
        profile_after = {
            "id": "user-1",
            "bmr": 1800.0,
            "tdee": 2500.0,
            "target_calories": 2800.0,
            "target_protein_g": 180.0,
            "target_carbs_g": 350.0,
            "target_fat_g": 70.0,
        }
        mock_sb = _make_supabase_mock(updated_profile=profile_after)

        result_json = await update_my_profile_tool(
            mock_sb,
            user_id="user-1",
            bmr=1800.0,
            tdee=2500.0,
            target_calories=2800.0,
            target_protein_g=180.0,
            target_carbs_g=350.0,
            target_fat_g=70.0,
        )

        result = json.loads(result_json)
        assert result["success"] is True
        assert "bmr" in result["updated_fields"]
        assert "tdee" in result["updated_fields"]
        assert "target_calories" in result["updated_fields"]
        assert "target_protein_g" in result["updated_fields"]
        assert "target_carbs_g" in result["updated_fields"]
        assert "target_fat_g" in result["updated_fields"]

        # Verify Supabase was called with the right data
        update_call = mock_sb.table.return_value.update
        update_dict = update_call.call_args[0][0]
        assert update_dict["bmr"] == 1800.0
        assert update_dict["tdee"] == 2500.0
        assert update_dict["target_calories"] == 2800.0
        assert update_dict["target_protein_g"] == 180.0
        assert update_dict["target_carbs_g"] == 350.0
        assert update_dict["target_fat_g"] == 70.0

    @pytest.mark.asyncio
    async def test_nutrition_fields_mixed_with_biometric(self):
        """Nutrition fields can be sent alongside biometric fields."""
        profile_after = {"id": "user-1", "age": 30, "bmr": 1700.0}
        mock_sb = _make_supabase_mock(updated_profile=profile_after)

        result_json = await update_my_profile_tool(
            mock_sb,
            user_id="user-1",
            age=30,
            bmr=1700.0,
        )

        result = json.loads(result_json)
        assert result["success"] is True
        assert "age" in result["updated_fields"]
        assert "bmr" in result["updated_fields"]


# ============================================================================
# Test 2-4: calculate_nutritional_needs auto-persist behavior
# ============================================================================


class TestCalculateNutritionalNeedsAutoPersist:
    """calculate_nutritional_needs script auto-persists nutrition targets."""

    CALC_KWARGS = {
        "age": 35,
        "gender": "male",
        "weight_kg": 87.0,
        "height_cm": 178,
        "activity_level": "moderate",
    }

    @pytest.mark.asyncio
    async def test_auto_persists_with_user_id(self):
        """When user_id and supabase are provided, nutrition targets are persisted."""
        execute = _load_calc_execute()

        mock_sb = _make_supabase_mock(updated_profile={"id": "user-1"})

        result_json = await execute(
            **self.CALC_KWARGS,
            user_id="user-1",
            supabase=mock_sb,
        )

        result = json.loads(result_json)
        assert "bmr" in result
        assert "tdee" in result
        assert "target_calories" in result

        # Verify update was called
        update_call = mock_sb.table.return_value.update
        update_call.assert_called_once()
        update_dict = update_call.call_args[0][0]
        assert update_dict["bmr"] == result["bmr"]
        assert update_dict["tdee"] == result["tdee"]
        assert update_dict["target_calories"] == result["target_calories"]
        assert update_dict["target_protein_g"] == result["target_protein_g"]
        assert update_dict["target_carbs_g"] == result["target_carbs_g"]
        assert update_dict["target_fat_g"] == result["target_fat_g"]

    @pytest.mark.asyncio
    async def test_no_persist_without_user_id(self):
        """When user_id is None, no DB update is attempted."""
        execute = _load_calc_execute()

        mock_sb = _make_supabase_mock()

        result_json = await execute(
            **self.CALC_KWARGS,
            user_id=None,
            supabase=mock_sb,
        )

        result = json.loads(result_json)
        assert "bmr" in result  # Calculation still works

        # No update call
        mock_sb.table.return_value.update.assert_not_called()

    @pytest.mark.asyncio
    async def test_persist_failure_still_returns_result(self):
        """If Supabase update raises, calculation result is still returned."""
        execute = _load_calc_execute()

        mock_sb = MagicMock()
        mock_sb.table.return_value.update.return_value.eq.return_value.execute.side_effect = Exception(
            "DB connection lost"
        )

        result_json = await execute(
            **self.CALC_KWARGS,
            user_id="user-1",
            supabase=mock_sb,
        )

        result = json.loads(result_json)
        # Calculation succeeded despite DB failure
        assert "bmr" in result
        assert "tdee" in result
        assert "target_calories" in result
        assert "error" not in result
