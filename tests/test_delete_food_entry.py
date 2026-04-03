"""Tests for delete_food_entry skill script."""

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
    / "delete_food_entry.py"
)
_spec = importlib.util.spec_from_file_location("delete_food_entry", _SCRIPT_PATH)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
sys.modules["delete_food_entry"] = _mod
_spec.loader.exec_module(_mod)

execute = _mod.execute

USER_ID = "1111-2222-3333-4444"

ENTRY_1 = {
    "id": "entry-1",
    "food_name": "poulet grillé",
    "quantity": 200,
    "unit": "g",
    "calories": 330,
    "protein_g": 62,
    "carbs_g": 0,
    "fat_g": 7.2,
    "meal_type": "dejeuner",
    "user_id": USER_ID,
}

ENTRY_2 = {
    "id": "entry-2",
    "food_name": "riz basmati",
    "quantity": 150,
    "unit": "g",
    "calories": 195,
    "protein_g": 4.5,
    "carbs_g": 42,
    "fat_g": 0.5,
    "meal_type": "dejeuner",
    "user_id": USER_ID,
}

ENTRY_3 = {
    "id": "entry-3",
    "food_name": "poulet tikka",
    "quantity": 250,
    "unit": "g",
    "calories": 400,
    "protein_g": 50,
    "carbs_g": 10,
    "fat_g": 18,
    "meal_type": "diner",
    "user_id": USER_ID,
}


def _mock_supabase(
    select_data: list | None = None,
    entry_by_id: dict | None = None,
) -> MagicMock:
    """Build a mock supabase client.

    select_data: data returned by broad queries (food_name search)
    entry_by_id: data returned by .eq("id", ...) lookup
    """
    sb = MagicMock()

    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.limit.return_value = chain
    chain.delete.return_value = chain

    # Route different .execute() calls based on context
    # For simplicity, use side_effect on execute
    if entry_by_id is not None:
        # First execute = select by id, second = delete
        chain.execute = AsyncMock(
            side_effect=[
                MagicMock(data=[entry_by_id] if entry_by_id else []),
                MagicMock(data=[]),  # delete result
            ]
        )
    elif select_data is not None:
        # First execute = select by date/user, second = delete
        chain.execute = AsyncMock(
            side_effect=[
                MagicMock(data=select_data),
                MagicMock(data=[]),  # delete result
            ]
        )
    else:
        chain.execute = AsyncMock(return_value=MagicMock(data=[]))

    sb.table = lambda name: chain
    return sb


class TestDeleteByEntryId:
    @pytest.mark.asyncio
    async def test_delete_by_id_success(self):
        sb = _mock_supabase(entry_by_id=ENTRY_1)
        result = json.loads(
            await execute(supabase=sb, user_id=USER_ID, entry_id="entry-1")
        )
        assert result["success"] is True
        assert result["deleted"]["food_name"] == "poulet grillé"
        assert result["deleted"]["entry_id"] == "entry-1"

    @pytest.mark.asyncio
    async def test_delete_by_id_not_found(self):
        sb = MagicMock()
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.limit.return_value = chain
        chain.execute = AsyncMock(return_value=MagicMock(data=[]))
        sb.table = lambda name: chain

        result = json.loads(
            await execute(supabase=sb, user_id=USER_ID, entry_id="nonexistent")
        )
        assert result["code"] == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_delete_by_id_wrong_user(self):
        entry_other_user = {**ENTRY_1, "user_id": "other-user-id"}
        sb = _mock_supabase(entry_by_id=entry_other_user)
        result = json.loads(
            await execute(supabase=sb, user_id=USER_ID, entry_id="entry-1")
        )
        assert result["code"] == "FORBIDDEN"


class TestDeleteByFoodName:
    @pytest.mark.asyncio
    async def test_delete_by_name_single_match(self):
        sb = _mock_supabase(select_data=[ENTRY_1, ENTRY_2])
        result = json.loads(
            await execute(supabase=sb, user_id=USER_ID, food_name="riz")
        )
        assert result["success"] is True
        assert result["deleted"]["food_name"] == "riz basmati"

    @pytest.mark.asyncio
    async def test_delete_by_name_ambiguous(self):
        sb = _mock_supabase(select_data=[ENTRY_1, ENTRY_3])
        result = json.loads(
            await execute(supabase=sb, user_id=USER_ID, food_name="poulet")
        )
        assert result["code"] == "AMBIGUOUS"
        assert len(result["matches"]) == 2

    @pytest.mark.asyncio
    async def test_delete_by_name_not_found(self):
        sb = _mock_supabase(select_data=[ENTRY_1, ENTRY_2])
        result = json.loads(
            await execute(supabase=sb, user_id=USER_ID, food_name="saumon")
        )
        assert result["code"] == "NOT_FOUND"
        assert len(result["available_entries"]) == 2


class TestDeleteEdgeCases:
    @pytest.mark.asyncio
    async def test_missing_params(self):
        sb = MagicMock()
        result = json.loads(await execute(supabase=sb, user_id=USER_ID))
        assert result["code"] == "MISSING_PARAMS"

    @pytest.mark.asyncio
    async def test_missing_user_id(self):
        sb = MagicMock()
        result = json.loads(await execute(supabase=sb, user_id=None))
        assert result["code"] == "NO_USER"
