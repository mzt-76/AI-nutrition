"""Tests for add_favorite_recipe skill script."""

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
    / "add_favorite_recipe.py"
)
_spec = importlib.util.spec_from_file_location("add_favorite_recipe", _SCRIPT_PATH)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
sys.modules["add_favorite_recipe"] = _mod
_spec.loader.exec_module(_mod)

execute = _mod.execute


def _mock_supabase(
    recipe_data: list | None = None,
    existing_fav: list | None = None,
) -> MagicMock:
    """Build a mock supabase client with chained query methods."""
    sb = MagicMock()

    # recipes table mock
    recipe_chain = MagicMock()
    recipe_chain.select.return_value = recipe_chain
    recipe_chain.eq.return_value = recipe_chain
    recipe_chain.limit.return_value = recipe_chain
    recipe_chain.execute = AsyncMock(
        return_value=MagicMock(data=recipe_data if recipe_data is not None else [])
    )

    # favorite_recipes table mock
    fav_select_chain = MagicMock()
    fav_select_chain.select.return_value = fav_select_chain
    fav_select_chain.eq.return_value = fav_select_chain
    fav_select_chain.limit.return_value = fav_select_chain
    fav_select_chain.execute = AsyncMock(
        return_value=MagicMock(data=existing_fav if existing_fav is not None else [])
    )

    fav_insert_chain = MagicMock()
    fav_insert_chain.insert.return_value = fav_insert_chain
    fav_insert_chain.execute = AsyncMock(return_value=MagicMock(data=[]))

    # Route .table() calls
    call_count = {"favorite_recipes": 0}

    def table_router(name: str) -> MagicMock:
        if name == "recipes":
            return recipe_chain
        if name == "favorite_recipes":
            call_count["favorite_recipes"] += 1
            # First call = select (duplicate check), second = insert
            if call_count["favorite_recipes"] == 1:
                return fav_select_chain
            return fav_insert_chain
        return MagicMock()

    sb.table = table_router
    sb._fav_insert_chain = fav_insert_chain
    return sb


RECIPE_ID = "aaaa-bbbb-cccc-dddd"
USER_ID = "1111-2222-3333-4444"


class TestAddFavoriteRecipeHappyPath:
    @pytest.mark.asyncio
    async def test_adds_favorite_successfully(self):
        sb = _mock_supabase(
            recipe_data=[{"id": RECIPE_ID, "name": "Escalope sauce citron"}],
            existing_fav=[],
        )
        result = json.loads(
            await execute(supabase=sb, user_id=USER_ID, recipe_id=RECIPE_ID)
        )
        assert result["status"] == "added"
        assert result["recipe_name"] == "Escalope sauce citron"
        assert result["recipe_id"] == RECIPE_ID

    @pytest.mark.asyncio
    async def test_adds_favorite_with_notes(self):
        sb = _mock_supabase(
            recipe_data=[{"id": RECIPE_ID, "name": "Poulet grillé"}],
            existing_fav=[],
        )
        result = json.loads(
            await execute(
                supabase=sb,
                user_id=USER_ID,
                recipe_id=RECIPE_ID,
                notes="Ma recette préférée",
            )
        )
        assert result["status"] == "added"


class TestAddFavoriteRecipeErrors:
    @pytest.mark.asyncio
    async def test_missing_recipe_id(self):
        sb = MagicMock()
        result = json.loads(await execute(supabase=sb, user_id=USER_ID))
        assert result["code"] == "NO_RECIPE_ID"

    @pytest.mark.asyncio
    async def test_missing_user_id(self):
        sb = MagicMock()
        result = json.loads(
            await execute(supabase=sb, user_id=None, recipe_id=RECIPE_ID)
        )
        assert result["code"] == "NO_USER"

    @pytest.mark.asyncio
    async def test_recipe_not_found(self):
        sb = _mock_supabase(recipe_data=[], existing_fav=[])
        result = json.loads(
            await execute(supabase=sb, user_id=USER_ID, recipe_id=RECIPE_ID)
        )
        assert result["code"] == "RECIPE_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_already_favorited(self):
        sb = _mock_supabase(
            recipe_data=[{"id": RECIPE_ID, "name": "Escalope sauce citron"}],
            existing_fav=[{"id": "existing-fav-id"}],
        )
        result = json.loads(
            await execute(supabase=sb, user_id=USER_ID, recipe_id=RECIPE_ID)
        )
        assert result["status"] == "already_exists"
        assert result["recipe_name"] == "Escalope sauce citron"
