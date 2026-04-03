"""Tests for get_user_favorites skill script."""

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
    / "get_user_favorites.py"
)
_spec = importlib.util.spec_from_file_location("get_user_favorites", _SCRIPT_PATH)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
sys.modules["get_user_favorites"] = _mod
_spec.loader.exec_module(_mod)

execute = _mod.execute

USER_ID = "1111-2222-3333-4444"

_INGREDIENTS_POULET = [
    {"name": "poulet", "quantity": 200, "unit": "g"},
    {"name": "herbes de provence", "quantity": 5, "unit": "g"},
]

FAV_1 = {
    "id": "fav-1",
    "recipe_id": "recipe-1",
    "user_id": USER_ID,
    "notes": "Très bon",
    "created_at": "2026-03-01T12:00:00Z",
    "recipes": {
        "name": "Poulet grillé aux herbes",
        "meal_type": "dejeuner",
        "calories_per_serving": 550,
        "protein_g_per_serving": 45,
        "carbs_g_per_serving": 30,
        "fat_g_per_serving": 20,
        "ingredients": _INGREDIENTS_POULET,
    },
}

FAV_2 = {
    "id": "fav-2",
    "recipe_id": "recipe-2",
    "user_id": USER_ID,
    "notes": None,
    "created_at": "2026-03-02T12:00:00Z",
    "recipes": {
        "name": "Saumon teriyaki et riz",
        "meal_type": "diner",
        "calories_per_serving": 620,
        "protein_g_per_serving": 40,
        "carbs_g_per_serving": 55,
        "fat_g_per_serving": 18,
        "ingredients": [{"name": "saumon", "quantity": 150, "unit": "g"}],
    },
}

FAV_3 = {
    "id": "fav-3",
    "recipe_id": "recipe-3",
    "user_id": USER_ID,
    "notes": None,
    "created_at": "2026-03-03T12:00:00Z",
    "recipes": {
        "name": "Poulet tikka masala",
        "meal_type": "dejeuner",
        "calories_per_serving": 580,
        "protein_g_per_serving": 42,
        "carbs_g_per_serving": 45,
        "fat_g_per_serving": 22,
        "ingredients": [{"name": "poulet", "quantity": 250, "unit": "g"}],
    },
}

FAV_HYPHEN = {
    "id": "fav-4",
    "recipe_id": "recipe-4",
    "user_id": USER_ID,
    "notes": None,
    "created_at": "2026-03-04T12:00:00Z",
    "recipes": {
        "name": "Bol Petit-Déjeuner Protéiné Équilibré",
        "meal_type": "petit-dejeuner",
        "calories_per_serving": 480,
        "protein_g_per_serving": 35,
        "carbs_g_per_serving": 50,
        "fat_g_per_serving": 12,
        "ingredients": [
            {"name": "flocons d'avoine", "quantity": 80, "unit": "g"},
            {"name": "skyr", "quantity": 150, "unit": "g"},
        ],
    },
}


def _mock_supabase(fav_data: list | None = None) -> MagicMock:
    sb = MagicMock()
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.order.return_value = chain
    chain.execute = AsyncMock(
        return_value=MagicMock(data=fav_data if fav_data is not None else [])
    )
    sb.table = lambda name: chain
    return sb


class TestGetUserFavoritesHappyPath:
    @pytest.mark.asyncio
    async def test_returns_all_favorites(self):
        sb = _mock_supabase(fav_data=[FAV_1, FAV_2])
        result = json.loads(await execute(supabase=sb, user_id=USER_ID))
        assert result["count"] == 2
        assert len(result["favorites"]) == 2
        assert result["favorites"][0]["recipe_name"] == "Poulet grillé aux herbes"
        assert result["favorites"][1]["recipe_name"] == "Saumon teriyaki et riz"

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_favorites(self):
        sb = _mock_supabase(fav_data=[])
        result = json.loads(await execute(supabase=sb, user_id=USER_ID))
        assert result["count"] == 0
        assert result["favorites"] == []

    @pytest.mark.asyncio
    async def test_filters_by_name(self):
        sb = _mock_supabase(fav_data=[FAV_1, FAV_2, FAV_3])
        result = json.loads(await execute(supabase=sb, user_id=USER_ID, name="saumon"))
        assert result["count"] == 1
        assert result["favorites"][0]["recipe_name"] == "Saumon teriyaki et riz"

    @pytest.mark.asyncio
    async def test_fuzzy_name_match(self):
        """'poulet' matches both 'Poulet grillé aux herbes' and 'Poulet tikka masala'."""
        sb = _mock_supabase(fav_data=[FAV_1, FAV_2, FAV_3])
        result = json.loads(await execute(supabase=sb, user_id=USER_ID, name="poulet"))
        assert result["count"] == 2
        names = {f["recipe_name"] for f in result["favorites"]}
        assert names == {"Poulet grillé aux herbes", "Poulet tikka masala"}

    @pytest.mark.asyncio
    async def test_includes_recipe_details(self):
        sb = _mock_supabase(fav_data=[FAV_1])
        result = json.loads(await execute(supabase=sb, user_id=USER_ID))
        fav = result["favorites"][0]
        assert fav["favorite_id"] == "fav-1"
        assert fav["recipe_id"] == "recipe-1"
        assert fav["calories"] == 550
        assert fav["protein_g"] == 45
        assert fav["meal_type"] == "dejeuner"
        assert fav["notes"] == "Très bon"

    @pytest.mark.asyncio
    async def test_includes_ingredients(self):
        sb = _mock_supabase(fav_data=[FAV_1])
        result = json.loads(await execute(supabase=sb, user_id=USER_ID))
        fav = result["favorites"][0]
        assert fav["ingredients"] == _INGREDIENTS_POULET

    @pytest.mark.asyncio
    async def test_hyphenated_name_filter(self):
        """'petit déjeuner' matches 'Bol Petit-Déjeuner Protéiné Équilibré'."""
        sb = _mock_supabase(fav_data=[FAV_1, FAV_HYPHEN])
        result = json.loads(
            await execute(supabase=sb, user_id=USER_ID, name="bol petit")
        )
        assert result["count"] == 1
        assert (
            result["favorites"][0]["recipe_name"]
            == "Bol Petit-Déjeuner Protéiné Équilibré"
        )

    @pytest.mark.asyncio
    async def test_skips_favorites_without_recipe_data(self):
        """Favorites with null recipes join should be skipped."""
        broken_fav = {**FAV_1, "recipes": None}
        sb = _mock_supabase(fav_data=[broken_fav, FAV_2])
        result = json.loads(await execute(supabase=sb, user_id=USER_ID))
        assert result["count"] == 1
        assert result["favorites"][0]["recipe_name"] == "Saumon teriyaki et riz"


class TestGetUserFavoritesErrors:
    @pytest.mark.asyncio
    async def test_missing_user_id(self):
        sb = MagicMock()
        result = json.loads(await execute(supabase=sb, user_id=None))
        assert result["code"] == "NO_USER"
