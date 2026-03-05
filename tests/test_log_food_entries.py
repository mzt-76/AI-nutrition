"""Tests for log_food_entries skill script.

Tests: mock Supabase + match_ingredient, verify inserts and return format.
"""

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Load module from hyphenated path (skills/meal-planning/scripts/)
_SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent
    / "skills"
    / "meal-planning"
    / "scripts"
    / "log_food_entries.py"
)
_spec = importlib.util.spec_from_file_location("log_food_entries", _SCRIPT_PATH)
assert _spec and _spec.loader
log_food_entries = importlib.util.module_from_spec(_spec)
sys.modules["log_food_entries"] = log_food_entries
_spec.loader.exec_module(log_food_entries)

execute = log_food_entries.execute
_PATCH_TARGET = "log_food_entries.match_ingredient"


@pytest.fixture
def mock_supabase():
    """Mock Supabase client with insert chain."""
    client = MagicMock()
    table_mock = MagicMock()
    table_mock.insert.return_value.execute.return_value = MagicMock(
        data=[{"id": "abc"}]
    )
    client.table.return_value = table_mock
    return client


def _make_match_result(
    name: str, qty: float, cal: float, prot: float, carbs: float, fat: float
):
    return {
        "ingredient_name": name,
        "matched_name": f"{name} (OFF)",
        "openfoodfacts_code": "12345",
        "quantity": qty,
        "unit": "g",
        "calories": cal,
        "protein_g": prot,
        "carbs_g": carbs,
        "fat_g": fat,
        "confidence": 0.85,
        "cache_hit": True,
    }


@pytest.mark.asyncio
async def test_log_food_entries_basic(mock_supabase):
    """Happy path: 2 items logged with correct macros and totals."""
    with patch(_PATCH_TARGET, new_callable=AsyncMock) as mock_match:
        mock_match.side_effect = [
            _make_match_result("poulet", 200, 330, 62, 0, 7.2),
            _make_match_result("riz", 150, 195, 4.1, 43.5, 0.5),
        ]

        result = await execute(
            supabase=mock_supabase,
            user_id="user-123",
            items=[
                {"name": "poulet", "quantity": 200, "unit": "g"},
                {"name": "riz", "quantity": 150, "unit": "g"},
            ],
            log_date="2026-03-05",
            meal_type="dejeuner",
        )

        data = json.loads(result)
        assert data["success"] is True
        assert data["item_count"] == 2
        assert len(data["logged_items"]) == 2
        assert data["totals"]["calories"] == 525.0
        assert data["totals"]["protein_g"] == 66.1
        assert data["log_date"] == "2026-03-05"
        assert data["meal_type"] == "dejeuner"

        # Verify 2 inserts happened
        assert mock_supabase.table.return_value.insert.call_count == 2


@pytest.mark.asyncio
async def test_log_food_entries_empty_items(mock_supabase):
    """Empty items list returns error."""
    result = await execute(
        supabase=mock_supabase,
        user_id="user-123",
        items=[],
    )
    data = json.loads(result)
    assert data["code"] == "EMPTY_ITEMS"


@pytest.mark.asyncio
async def test_log_food_entries_no_user(mock_supabase):
    """Missing user_id returns error."""
    result = await execute(
        supabase=mock_supabase,
        user_id=None,
        items=[{"name": "poulet", "quantity": 200, "unit": "g"}],
    )
    data = json.loads(result)
    assert data["code"] == "NO_USER"


@pytest.mark.asyncio
async def test_log_food_entries_unmatched_ingredient(mock_supabase):
    """Unmatched ingredient logs with zero macros."""
    with patch(_PATCH_TARGET, new_callable=AsyncMock) as mock_match:
        mock_match.return_value = {
            "ingredient_name": "mystery food",
            "matched_name": None,
            "openfoodfacts_code": None,
            "quantity": 100,
            "unit": "g",
            "calories": 0,
            "protein_g": 0,
            "carbs_g": 0,
            "fat_g": 0,
            "confidence": 0,
            "cache_hit": False,
        }

        result = await execute(
            supabase=mock_supabase,
            user_id="user-123",
            items=[{"name": "mystery food", "quantity": 100, "unit": "g"}],
        )

        data = json.loads(result)
        assert data["success"] is True
        assert data["logged_items"][0]["calories"] == 0
        assert data["logged_items"][0]["confidence"] == 0
        assert mock_supabase.table.return_value.insert.call_count == 1


@pytest.mark.asyncio
async def test_log_food_entries_insert_row_fields(mock_supabase):
    """Verify the exact fields passed to Supabase insert."""
    with patch(_PATCH_TARGET, new_callable=AsyncMock) as mock_match:
        mock_match.return_value = _make_match_result("oeuf", 1, 78, 6.3, 0.6, 5.3)

        await execute(
            supabase=mock_supabase,
            user_id="user-456",
            items=[{"name": "oeuf", "quantity": 1, "unit": "pièces"}],
            log_date="2026-03-05",
            meal_type="petit-dejeuner",
        )

        insert_call = mock_supabase.table.return_value.insert.call_args[0][0]
        assert insert_call["user_id"] == "user-456"
        assert insert_call["log_date"] == "2026-03-05"
        assert insert_call["meal_type"] == "petit-dejeuner"
        assert insert_call["food_name"] == "oeuf"
        assert insert_call["quantity"] == 1
        assert insert_call["unit"] == "pièces"
        assert insert_call["source"] == "openfoodfacts"
