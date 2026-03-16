"""Tests for get_daily_summary skill script.

Tests: mock Supabase, verify consumed/remaining calculation and edge cases.
"""

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Load module from hyphenated path (skills/food-tracking/scripts/)
_SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent
    / "skills"
    / "food-tracking"
    / "scripts"
    / "get_daily_summary.py"
)
_spec = importlib.util.spec_from_file_location("get_daily_summary", _SCRIPT_PATH)
assert _spec and _spec.loader
get_daily_summary = importlib.util.module_from_spec(_spec)
sys.modules["get_daily_summary"] = get_daily_summary
_spec.loader.exec_module(get_daily_summary)

execute = get_daily_summary.execute


def _mock_supabase(
    profile_data: list[dict] | None = None,
    log_data: list[dict] | None = None,
) -> MagicMock:
    """Build a mock Supabase client with configurable profile and log responses."""
    client = MagicMock()

    profile_table = MagicMock()
    profile_table.select.return_value.eq.return_value.execute = AsyncMock(
        return_value=MagicMock(data=profile_data)
    )

    log_table = MagicMock()
    log_table.select.return_value.eq.return_value.eq.return_value.execute = AsyncMock(
        return_value=MagicMock(data=log_data)
    )

    def table_router(name: str) -> MagicMock:
        if name == "user_profiles":
            return profile_table
        return log_table

    client.table.side_effect = table_router
    return client


SAMPLE_PROFILE = {
    "target_calories": 2200,
    "target_protein_g": 165,
    "target_carbs_g": 250,
    "target_fat_g": 65,
}

SAMPLE_LOG = [
    {
        "food_name": "flocons d'avoine",
        "quantity": 80,
        "unit": "g",
        "calories": 500,
        "protein_g": 40,
        "carbs_g": 60,
        "fat_g": 15,
        "meal_type": "petit-dejeuner",
    },
    {
        "food_name": "poulet grille",
        "quantity": 200,
        "unit": "g",
        "calories": 700,
        "protein_g": 50,
        "carbs_g": 80,
        "fat_g": 20,
        "meal_type": "dejeuner",
    },
    {
        "food_name": "riz basmati",
        "quantity": 150,
        "unit": "g",
        "calories": 250,
        "protein_g": 20,
        "carbs_g": 30,
        "fat_g": 5,
        "meal_type": "dejeuner",
    },
]


@pytest.mark.asyncio
async def test_happy_path_consumed_and_remaining():
    """Consumed macros are summed correctly, remaining = targets - consumed."""
    sb = _mock_supabase(profile_data=[SAMPLE_PROFILE], log_data=SAMPLE_LOG)
    raw = await execute(supabase=sb, user_id="user-123", log_date="2026-03-06")
    result = json.loads(raw)

    assert result["targets"] == {
        "calories": 2200,
        "protein_g": 165,
        "carbs_g": 250,
        "fat_g": 65,
    }
    assert result["consumed"] == {
        "calories": 1450.0,
        "protein_g": 110.0,
        "carbs_g": 170.0,
        "fat_g": 40.0,
    }
    assert result["remaining"] == {
        "calories": 750.0,
        "protein_g": 55.0,
        "carbs_g": 80.0,
        "fat_g": 25.0,
    }
    assert result["entries_count"] == 3
    assert result["meals_logged"] == ["dejeuner", "petit-dejeuner"]


@pytest.mark.asyncio
async def test_meals_detail_groups_items_by_meal_type():
    """meals_detail returns individual food items grouped by meal_type."""
    sb = _mock_supabase(profile_data=[SAMPLE_PROFILE], log_data=SAMPLE_LOG)
    raw = await execute(supabase=sb, user_id="user-123", log_date="2026-03-06")
    result = json.loads(raw)

    assert "meals_detail" in result
    detail = result["meals_detail"]

    # petit-dejeuner has 1 item
    assert len(detail["petit-dejeuner"]) == 1
    breakfast_item = detail["petit-dejeuner"][0]
    assert breakfast_item["food_name"] == "flocons d'avoine"
    assert breakfast_item["quantity"] == 80
    assert breakfast_item["unit"] == "g"
    assert breakfast_item["calories"] == 500

    # dejeuner has 2 items
    assert len(detail["dejeuner"]) == 2
    dejeuner_names = {item["food_name"] for item in detail["dejeuner"]}
    assert dejeuner_names == {"poulet grille", "riz basmati"}


@pytest.mark.asyncio
async def test_meals_detail_empty_when_no_entries():
    """meals_detail is empty dict when no entries logged."""
    sb = _mock_supabase(profile_data=[SAMPLE_PROFILE], log_data=[])
    raw = await execute(supabase=sb, user_id="user-123", log_date="2026-03-06")
    result = json.loads(raw)

    assert result["meals_detail"] == {}


@pytest.mark.asyncio
async def test_empty_log_returns_full_targets_as_remaining():
    """No entries logged yet — remaining equals targets."""
    sb = _mock_supabase(profile_data=[SAMPLE_PROFILE], log_data=[])
    raw = await execute(supabase=sb, user_id="user-123", log_date="2026-03-06")
    result = json.loads(raw)

    assert result["consumed"] == {
        "calories": 0.0,
        "protein_g": 0.0,
        "carbs_g": 0.0,
        "fat_g": 0.0,
    }
    assert result["remaining"]["calories"] == 2200.0
    assert result["entries_count"] == 0
    assert result["meals_logged"] == []


@pytest.mark.asyncio
async def test_no_profile_returns_error():
    """Missing profile returns NO_PROFILE error."""
    sb = _mock_supabase(profile_data=[], log_data=[])
    raw = await execute(supabase=sb, user_id="user-123")
    result = json.loads(raw)

    assert result["code"] == "NO_PROFILE"


@pytest.mark.asyncio
async def test_no_targets_returns_error():
    """Profile exists but all targets are 0 — returns NO_TARGETS."""
    zero_profile = {
        "target_calories": 0,
        "target_protein_g": 0,
        "target_carbs_g": 0,
        "target_fat_g": 0,
    }
    sb = _mock_supabase(profile_data=[zero_profile], log_data=[])
    raw = await execute(supabase=sb, user_id="user-123")
    result = json.loads(raw)

    assert result["code"] == "NO_TARGETS"


@pytest.mark.asyncio
async def test_null_targets_treated_as_zero():
    """Profile with null targets → treated as 0 → NO_TARGETS."""
    null_profile = {
        "target_calories": None,
        "target_protein_g": None,
        "target_carbs_g": None,
        "target_fat_g": None,
    }
    sb = _mock_supabase(profile_data=[null_profile], log_data=[])
    raw = await execute(supabase=sb, user_id="user-123")
    result = json.loads(raw)

    assert result["code"] == "NO_TARGETS"


@pytest.mark.asyncio
async def test_no_user_id_returns_error():
    """Missing user_id returns NO_USER error."""
    sb = _mock_supabase()
    raw = await execute(supabase=sb, user_id="")
    result = json.loads(raw)

    assert result["code"] == "NO_USER"


@pytest.mark.asyncio
async def test_supabase_exception_returns_script_error():
    """Supabase crash is caught and returns SCRIPT_ERROR."""
    sb = MagicMock()
    sb.table.side_effect = Exception("connection lost")
    raw = await execute(supabase=sb, user_id="user-123")
    result = json.loads(raw)

    assert result["code"] == "SCRIPT_ERROR"


@pytest.mark.asyncio
async def test_overconsumption_shows_negative_remaining():
    """When consumed > targets, remaining is negative."""
    over_log = [
        {
            "calories": 2500,
            "protein_g": 200,
            "carbs_g": 300,
            "fat_g": 80,
            "meal_type": "dejeuner",
        },
    ]
    sb = _mock_supabase(profile_data=[SAMPLE_PROFILE], log_data=over_log)
    raw = await execute(supabase=sb, user_id="user-123")
    result = json.loads(raw)

    assert result["remaining"]["calories"] == -300.0
    assert result["remaining"]["fat_g"] == -15.0


@pytest.mark.asyncio
async def test_log_date_defaults_to_today():
    """When no log_date provided, defaults to today."""
    sb = _mock_supabase(profile_data=[SAMPLE_PROFILE], log_data=[])
    raw = await execute(supabase=sb, user_id="user-123")
    result = json.loads(raw)

    from datetime import date

    assert result["log_date"] == date.today().isoformat()
