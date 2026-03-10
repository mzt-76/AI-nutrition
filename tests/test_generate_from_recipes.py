"""Unit tests for shopping-list generate_from_recipes script.

Tests the script with mock Supabase client — no real DB or LLM needed.
"""

import importlib.util
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Skill directories use hyphens — load via importlib like the agent does
_SCRIPT_PATH = Path("skills/shopping-list/scripts/generate_from_recipes.py")
_spec = importlib.util.spec_from_file_location("generate_from_recipes", _SCRIPT_PATH)
assert _spec and _spec.loader
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
execute = _module.execute


def _mock_supabase(recipes: list[dict] | None = None) -> MagicMock:
    """Build a mock Supabase client that returns given recipes on .in_() query."""
    sb = MagicMock()
    result = MagicMock()
    result.data = recipes if recipes is not None else []

    sb.table.return_value.select.return_value.in_.return_value.execute = AsyncMock(
        return_value=result
    )

    # Mock insert for shopping_lists
    insert_result = MagicMock()
    insert_result.data = [{"id": "shopping-list-uuid-123"}]
    sb.table.return_value.insert.return_value.execute = AsyncMock(
        return_value=insert_result
    )

    return sb


SAMPLE_RECIPE = {
    "id": "recipe-uuid-1",
    "name": "Poulet grille aux legumes",
    "ingredients": [
        {"name": "poulet", "quantity": 300, "unit": "g"},
        {"name": "brocoli", "quantity": 200, "unit": "g"},
        {"name": "huile d'olive", "quantity": 15, "unit": "ml"},
        {"name": "riz", "quantity": 150, "unit": "g"},
    ],
}

SAMPLE_RECIPE_2 = {
    "id": "recipe-uuid-2",
    "name": "Salade de thon",
    "ingredients": [
        {"name": "thon", "quantity": 150, "unit": "g"},
        {"name": "tomate", "quantity": 100, "unit": "g"},
        {"name": "huile d'olive", "quantity": 10, "unit": "ml"},
    ],
}


@pytest.mark.asyncio
async def test_single_recipe_success():
    """Valid recipe_ids → categorized shopping list returned."""
    sb = _mock_supabase([SAMPLE_RECIPE])
    result = json.loads(
        await execute(
            supabase=sb,
            user_id="test-user",
            recipe_ids=["recipe-uuid-1"],
        )
    )

    assert result["success"] is True
    assert result["shopping_list_id"] == "shopping-list-uuid-123"
    assert result["metadata"]["total_items"] > 0
    assert result["metadata"]["recipe_names"] == ["Poulet grille aux legumes"]

    # Check that ingredients were categorized
    shopping_list = result["shopping_list"]
    all_items = []
    for items in shopping_list.values():
        all_items.extend(items)
    item_names = [i["name"] for i in all_items]
    assert "poulet" in item_names
    assert "riz" in item_names


@pytest.mark.asyncio
async def test_multiple_recipes_aggregation():
    """Multiple recipes with shared ingredients → quantities aggregated."""
    sb = _mock_supabase([SAMPLE_RECIPE, SAMPLE_RECIPE_2])
    result = json.loads(
        await execute(
            supabase=sb,
            user_id="test-user",
            recipe_ids=["recipe-uuid-1", "recipe-uuid-2"],
        )
    )

    assert result["success"] is True
    # huile d'olive appears in both recipes (15ml + 10ml = 25ml)
    all_items = []
    for items in result["shopping_list"].values():
        all_items.extend(items)
    olive_oil = [i for i in all_items if i["name"] == "huile d'olive"]
    assert len(olive_oil) == 1
    assert olive_oil[0]["quantity"] == 25


@pytest.mark.asyncio
async def test_servings_multiplier():
    """servings_multiplier doubles all quantities."""
    sb = _mock_supabase([SAMPLE_RECIPE])
    result = json.loads(
        await execute(
            supabase=sb,
            user_id="test-user",
            recipe_ids=["recipe-uuid-1"],
            servings_multiplier=2.0,
        )
    )

    assert result["success"] is True
    all_items = []
    for items in result["shopping_list"].values():
        all_items.extend(items)
    poulet = [i for i in all_items if i["name"] == "poulet"]
    assert len(poulet) == 1
    assert poulet[0]["quantity"] == 600


@pytest.mark.asyncio
async def test_empty_recipe_ids():
    """Empty recipe_ids → validation error."""
    sb = _mock_supabase()
    result = json.loads(await execute(supabase=sb, user_id="test-user", recipe_ids=[]))

    assert "error" in result
    assert result["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_none_recipe_ids():
    """None recipe_ids → validation error."""
    sb = _mock_supabase()
    result = json.loads(
        await execute(supabase=sb, user_id="test-user", recipe_ids=None)
    )

    assert "error" in result
    assert result["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_recipe_not_found():
    """recipe_ids pointing to non-existent recipes → error."""
    sb = _mock_supabase([])  # No recipes found
    result = json.loads(
        await execute(
            supabase=sb,
            user_id="test-user",
            recipe_ids=["nonexistent-uuid"],
        )
    )

    assert "error" in result
    assert result["code"] == "RECIPES_NOT_FOUND"


@pytest.mark.asyncio
async def test_partial_recipe_ids_found():
    """Some recipe_ids found, some missing → succeeds with missing_recipe_ids reported."""
    sb = _mock_supabase([SAMPLE_RECIPE])
    result = json.loads(
        await execute(
            supabase=sb,
            user_id="test-user",
            recipe_ids=["recipe-uuid-1", "nonexistent-uuid"],
        )
    )

    assert result["success"] is True
    assert "nonexistent-uuid" in result["metadata"]["missing_recipe_ids"]


@pytest.mark.asyncio
async def test_invalid_servings_multiplier():
    """servings_multiplier <= 0 → validation error."""
    sb = _mock_supabase()
    result = json.loads(
        await execute(
            supabase=sb,
            user_id="test-user",
            recipe_ids=["recipe-uuid-1"],
            servings_multiplier=-1.0,
        )
    )

    assert "error" in result
    assert result["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_no_user_id_skips_db_save():
    """No user_id → shopping list generated but not persisted."""
    sb = _mock_supabase([SAMPLE_RECIPE])
    result = json.loads(
        await execute(
            supabase=sb,
            user_id="",
            recipe_ids=["recipe-uuid-1"],
        )
    )

    assert result["success"] is True
    assert result["shopping_list_id"] is None
    # insert should not have been called
    sb.table.return_value.insert.assert_not_called()


@pytest.mark.asyncio
async def test_custom_title():
    """Custom title is passed to DB insert."""
    sb = _mock_supabase([SAMPLE_RECIPE])
    result = json.loads(
        await execute(
            supabase=sb,
            user_id="test-user",
            recipe_ids=["recipe-uuid-1"],
            title="Mon diner special",
        )
    )

    assert result["success"] is True
    # Verify the title was passed to the insert call
    insert_call = sb.table.return_value.insert.call_args
    assert insert_call is not None
    assert insert_call[0][0]["title"] == "Mon diner special"
