"""Tests for remove_favorite_recipe skill script."""

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Load module from hyphenated path (skills/meal-planning/scripts/)
_SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent
    / "skills"
    / "meal-planning"
    / "scripts"
    / "remove_favorite_recipe.py"
)
_spec = importlib.util.spec_from_file_location("remove_favorite_recipe", _SCRIPT_PATH)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
sys.modules["remove_favorite_recipe"] = _mod
_spec.loader.exec_module(_mod)

execute = _mod.execute

USER_ID = "1111-2222-3333-4444"
FAV_ID = "fav-aaaa-bbbb"


def _mock_supabase_for_id_delete(
    ownership_data: list | None = None,
) -> MagicMock:
    """Mock for delete-by-favorite_id flow: ownership check + delete."""
    sb = MagicMock()
    call_count = {"favorite_recipes": 0}

    # Ownership check chain (select)
    ownership_chain = MagicMock()
    ownership_chain.select.return_value = ownership_chain
    ownership_chain.eq.return_value = ownership_chain
    ownership_chain.execute = AsyncMock(
        return_value=MagicMock(data=ownership_data or [])
    )

    # Delete chain
    delete_chain = MagicMock()
    delete_chain.delete.return_value = delete_chain
    delete_chain.eq.return_value = delete_chain
    delete_chain.execute = AsyncMock(return_value=MagicMock(data=[]))

    def table_router(name: str) -> MagicMock:
        if name == "favorite_recipes":
            call_count["favorite_recipes"] += 1
            # 1st call = ownership select, 2nd = delete
            if call_count["favorite_recipes"] == 1:
                return ownership_chain
            return delete_chain
        return MagicMock()

    sb.table = table_router
    sb._delete_chain = delete_chain
    return sb


def _mock_supabase_for_name_delete(
    search_data: list | None = None,
    ownership_data: list | None = None,
) -> MagicMock:
    """Mock for delete-by-name flow: name search + ownership check + delete."""
    sb = MagicMock()
    call_count = {"favorite_recipes": 0}

    # Name search chain
    search_chain = MagicMock()
    search_chain.select.return_value = search_chain
    search_chain.eq.return_value = search_chain
    search_chain.execute = AsyncMock(return_value=MagicMock(data=search_data or []))

    # Ownership check chain
    ownership_chain = MagicMock()
    ownership_chain.select.return_value = ownership_chain
    ownership_chain.eq.return_value = ownership_chain
    ownership_chain.execute = AsyncMock(
        return_value=MagicMock(data=ownership_data or [])
    )

    # Delete chain
    delete_chain = MagicMock()
    delete_chain.delete.return_value = delete_chain
    delete_chain.eq.return_value = delete_chain
    delete_chain.execute = AsyncMock(return_value=MagicMock(data=[]))

    def table_router(name: str) -> MagicMock:
        if name == "favorite_recipes":
            call_count["favorite_recipes"] += 1
            if call_count["favorite_recipes"] == 1:
                return search_chain
            if call_count["favorite_recipes"] == 2:
                return ownership_chain
            return delete_chain
        return MagicMock()

    sb.table = table_router
    sb._delete_chain = delete_chain
    return sb


class TestRemoveFavoriteHappyPath:
    @pytest.mark.asyncio
    async def test_removes_by_favorite_id(self):
        sb = _mock_supabase_for_id_delete(
            ownership_data=[
                {
                    "id": FAV_ID,
                    "user_id": USER_ID,
                    "recipe_id": "recipe-1",
                    "recipes": {"name": "Poulet grillé"},
                }
            ]
        )
        result = json.loads(
            await execute(supabase=sb, user_id=USER_ID, favorite_id=FAV_ID)
        )
        assert result["status"] == "removed"
        assert result["recipe_name"] == "Poulet grillé"

    @pytest.mark.asyncio
    async def test_removes_by_recipe_name(self):
        sb = _mock_supabase_for_name_delete(
            search_data=[
                {
                    "id": FAV_ID,
                    "recipe_id": "recipe-1",
                    "recipes": {"name": "Poulet grillé aux herbes"},
                }
            ],
            ownership_data=[
                {
                    "id": FAV_ID,
                    "user_id": USER_ID,
                    "recipe_id": "recipe-1",
                    "recipes": {"name": "Poulet grillé aux herbes"},
                }
            ],
        )
        result = json.loads(
            await execute(supabase=sb, user_id=USER_ID, recipe_name="poulet grillé")
        )
        assert result["status"] == "removed"
        assert result["recipe_name"] == "Poulet grillé aux herbes"


class TestRemoveFavoriteErrors:
    @pytest.mark.asyncio
    async def test_missing_user_id(self):
        sb = MagicMock()
        result = json.loads(await execute(supabase=sb, user_id=None))
        assert result["code"] == "NO_USER"

    @pytest.mark.asyncio
    async def test_no_identifier(self):
        sb = MagicMock()
        result = json.loads(await execute(supabase=sb, user_id=USER_ID))
        assert result["code"] == "NO_IDENTIFIER"

    @pytest.mark.asyncio
    async def test_favorite_not_found_by_name(self):
        sb = _mock_supabase_for_name_delete(search_data=[])
        result = json.loads(
            await execute(
                supabase=sb, user_id=USER_ID, recipe_name="recette inexistante"
            )
        )
        assert result["code"] == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_favorite_not_found_by_id(self):
        sb = _mock_supabase_for_id_delete(ownership_data=[])
        result = json.loads(
            await execute(supabase=sb, user_id=USER_ID, favorite_id="nonexistent")
        )
        assert result["code"] == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_not_owner(self):
        sb = _mock_supabase_for_id_delete(
            ownership_data=[
                {
                    "id": FAV_ID,
                    "user_id": "other-user-id",
                    "recipe_id": "recipe-1",
                    "recipes": {"name": "Poulet grillé"},
                }
            ]
        )
        result = json.loads(
            await execute(supabase=sb, user_id=USER_ID, favorite_id=FAV_ID)
        )
        assert result["code"] == "NOT_OWNER"

    @pytest.mark.asyncio
    async def test_ambiguous_name_match(self):
        sb = _mock_supabase_for_name_delete(
            search_data=[
                {
                    "id": "fav-1",
                    "recipe_id": "recipe-1",
                    "recipes": {"name": "Poulet grillé aux herbes"},
                },
                {
                    "id": "fav-2",
                    "recipe_id": "recipe-2",
                    "recipes": {"name": "Poulet grillé au citron"},
                },
            ]
        )
        result = json.loads(
            await execute(supabase=sb, user_id=USER_ID, recipe_name="poulet grillé")
        )
        assert result["status"] == "ambiguous"
        assert len(result["matches"]) == 2
