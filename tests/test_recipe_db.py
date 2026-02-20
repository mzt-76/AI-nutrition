"""Unit tests for src/nutrition/recipe_db.py.

Tests use mocked Supabase client — no real DB connections.
"""

import pytest
from unittest.mock import MagicMock

from src.nutrition.recipe_db import (
    search_recipes,
    get_recipe_by_id,
    save_recipe,
    count_recipes_by_meal_type,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_supabase_mock(data: list[dict], count: int | None = None):
    """Create a mock Supabase client that returns given data."""
    mock = MagicMock()
    execute_result = MagicMock()
    execute_result.data = data
    execute_result.count = count

    # Chain: .table().select().eq().order().limit().execute()
    mock.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = execute_result
    mock.table.return_value.select.return_value.eq.return_value.lte.return_value.gte.return_value.lte.return_value.order.return_value.limit.return_value.execute.return_value = execute_result
    mock.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = execute_result
    mock.table.return_value.insert.return_value.execute.return_value = execute_result
    mock.table.return_value.update.return_value.eq.return_value.execute.return_value = execute_result
    mock.table.return_value.select.return_value.eq.return_value.execute.return_value = execute_result

    return mock


def make_recipe(
    recipe_id: str = "uuid-1",
    name: str = "Poulet grillé",
    meal_type: str = "dejeuner",
    allergen_tags: list | None = None,
    diet_type: str = "omnivore",
    usage_count: int = 5,
    cuisine_type: str = "française",
    calories_per_serving: float = 650.0,
) -> dict:
    """Create a minimal recipe dict for testing."""
    return {
        "id": recipe_id,
        "name": name,
        "name_normalized": name.lower(),
        "meal_type": meal_type,
        "allergen_tags": allergen_tags or [],
        "diet_type": diet_type,
        "usage_count": usage_count,
        "cuisine_type": cuisine_type,
        "calories_per_serving": calories_per_serving,
        "protein_g_per_serving": 45.0,
        "carbs_g_per_serving": 55.0,
        "fat_g_per_serving": 20.0,
        "ingredients": [{"name": "poulet", "quantity": 150, "unit": "g"}],
        "instructions": "Griller le poulet.",
        "prep_time_minutes": 25,
        "off_validated": True,
        "source": "llm_generated",
        "tags": [],
    }


# ---------------------------------------------------------------------------
# Test: search_recipes_basic
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_recipes_basic():
    """Returns recipes matching meal_type."""
    recipes = [make_recipe(meal_type="dejeuner")]
    mock = make_supabase_mock(data=recipes)

    results = await search_recipes(mock, meal_type="dejeuner")

    assert len(results) == 1
    assert results[0]["meal_type"] == "dejeuner"


@pytest.mark.asyncio
async def test_search_recipes_empty_db():
    """Returns empty list when no recipes in DB."""
    mock = make_supabase_mock(data=[])
    results = await search_recipes(mock, meal_type="dejeuner")
    assert results == []


@pytest.mark.asyncio
async def test_search_recipes_allergen_exclusion():
    """Filters out recipes with matching allergen tags."""
    recipes = [
        make_recipe(recipe_id="uuid-1", allergen_tags=["lactose"]),
        make_recipe(recipe_id="uuid-2", allergen_tags=[]),
        make_recipe(recipe_id="uuid-3", allergen_tags=["gluten", "lactose"]),
    ]
    mock = make_supabase_mock(data=recipes)

    results = await search_recipes(mock, "dejeuner", exclude_allergens=["lactose"])

    # Only uuid-2 should remain
    assert len(results) == 1
    assert results[0]["id"] == "uuid-2"


@pytest.mark.asyncio
async def test_search_recipes_variety():
    """Excludes already-used recipe IDs for variety."""
    recipes = [
        make_recipe(recipe_id="uuid-1"),
        make_recipe(recipe_id="uuid-2"),
        make_recipe(recipe_id="uuid-3"),
    ]
    mock = make_supabase_mock(data=recipes)

    results = await search_recipes(
        mock, "dejeuner", exclude_recipe_ids=["uuid-1", "uuid-3"]
    )

    assert len(results) == 1
    assert results[0]["id"] == "uuid-2"


@pytest.mark.asyncio
async def test_search_recipes_no_allergens_returns_all():
    """No allergen filter → all recipes returned (up to limit)."""
    recipes = [make_recipe(recipe_id=f"uuid-{i}", allergen_tags=["gluten"]) for i in range(5)]
    mock = make_supabase_mock(data=recipes)

    results = await search_recipes(mock, "dejeuner", exclude_allergens=None)
    assert len(results) == 5


@pytest.mark.asyncio
async def test_search_recipes_cuisine_preference_ordering():
    """Preferred cuisine types appear before others."""
    recipes = [
        make_recipe(recipe_id="uuid-1", cuisine_type="asiatique"),
        make_recipe(recipe_id="uuid-2", cuisine_type="française"),
        make_recipe(recipe_id="uuid-3", cuisine_type="asiatique"),
    ]
    mock = make_supabase_mock(data=recipes)

    results = await search_recipes(
        mock, "dejeuner", cuisine_types=["asiatique"]
    )

    # Asiatique recipes should come first
    assert results[0]["cuisine_type"] == "asiatique"
    assert results[1]["cuisine_type"] == "asiatique"
    assert results[2]["cuisine_type"] == "française"


# ---------------------------------------------------------------------------
# Test: get_recipe_by_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_recipe_by_id_found():
    """Returns recipe when found."""
    recipe = make_recipe(recipe_id="some-uuid")
    mock = make_supabase_mock(data=[recipe])

    result = await get_recipe_by_id(mock, "some-uuid")
    assert result is not None
    assert result["id"] == "some-uuid"


@pytest.mark.asyncio
async def test_get_recipe_by_id_not_found():
    """Returns None when recipe not found."""
    mock = make_supabase_mock(data=[])
    result = await get_recipe_by_id(mock, "nonexistent-uuid")
    assert result is None


# ---------------------------------------------------------------------------
# Test: save_recipe
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_recipe_success():
    """Inserts recipe and returns with ID."""
    recipe = {
        "name": "Salade de quinoa",
        "meal_type": "dejeuner",
        "ingredients": [{"name": "quinoa", "quantity": 80, "unit": "g"}],
        "instructions": "Cuire le quinoa.",
        "calories_per_serving": 350.0,
        "protein_g_per_serving": 15.0,
        "carbs_g_per_serving": 60.0,
        "fat_g_per_serving": 8.0,
    }
    saved = {"id": "new-uuid", **recipe, "name_normalized": "salade de quinoa"}
    mock = make_supabase_mock(data=[saved])

    result = await save_recipe(mock, recipe)
    assert "id" in result
    assert result["id"] == "new-uuid"


@pytest.mark.asyncio
async def test_save_recipe_missing_field():
    """Raises ValueError when required field is missing."""
    recipe = {
        "name": "Salade",
        "meal_type": "dejeuner",
        # Missing: ingredients, instructions, macros
    }
    mock = make_supabase_mock(data=[])

    with pytest.raises(ValueError, match="Missing required field"):
        await save_recipe(mock, recipe)


@pytest.mark.asyncio
async def test_save_recipe_normalizes_name():
    """name_normalized is added before saving."""
    recipe = {
        "name": "Omelette Protéinée",
        "meal_type": "petit-dejeuner",
        "ingredients": [],
        "instructions": "Cuire.",
        "calories_per_serving": 300.0,
        "protein_g_per_serving": 20.0,
        "carbs_g_per_serving": 5.0,
        "fat_g_per_serving": 22.0,
    }
    mock = MagicMock()
    execute_result = MagicMock()
    execute_result.data = [{"id": "uuid", **recipe, "name_normalized": "omelette proteinee"}]
    mock.table.return_value.insert.return_value.execute.return_value = execute_result

    await save_recipe(mock, recipe)
    # Verify insert was called (name_normalized was passed)
    insert_call = mock.table.return_value.insert.call_args
    insert_data = insert_call[0][0]
    assert "name_normalized" in insert_data
    assert insert_data["name_normalized"] == "omelette proteinee"


# ---------------------------------------------------------------------------
# Test: count_recipes_by_meal_type
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_count_recipes_by_meal_type():
    """Returns counts per meal type using a single DB query."""
    mock = MagicMock()

    # New implementation: single .select("meal_type").execute()
    execute_result = MagicMock()
    execute_result.data = (
        [{"meal_type": "petit-dejeuner"}] * 30
        + [{"meal_type": "dejeuner"}] * 28
        + [{"meal_type": "diner"}] * 32
        + [{"meal_type": "collation"}] * 15
    )
    mock.table.return_value.select.return_value.execute.return_value = execute_result

    counts = await count_recipes_by_meal_type(mock)

    assert counts["petit-dejeuner"] == 30
    assert counts["dejeuner"] == 28
    assert counts["diner"] == 32
    assert counts["collation"] == 15
