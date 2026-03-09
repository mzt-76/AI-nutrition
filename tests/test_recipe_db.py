"""Unit tests for src/nutrition/recipe_db.py.

Tests use mocked Supabase client — no real DB connections.
"""

import pytest
from unittest.mock import MagicMock

from datetime import datetime, timedelta, timezone

from src.nutrition.recipe_db import (
    _contains_disliked,
    count_recipes_by_meal_type,
    get_recipe_by_id,
    save_recipe,
    score_macro_fit,
    score_recipe_variety,
    search_recipes,
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
    # Chain for .in_() (dejeuner/diner unified pool)
    mock.table.return_value.select.return_value.in_.return_value.order.return_value.limit.return_value.execute.return_value = execute_result
    mock.table.return_value.select.return_value.in_.return_value.lte.return_value.gte.return_value.lte.return_value.order.return_value.limit.return_value.execute.return_value = execute_result
    mock.table.return_value.select.return_value.in_.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = execute_result
    mock.table.return_value.select.return_value.in_.return_value.eq.return_value.lte.return_value.order.return_value.limit.return_value.execute.return_value = execute_result
    mock.table.return_value.select.return_value.in_.return_value.eq.return_value.lte.return_value.gte.return_value.lte.return_value.order.return_value.limit.return_value.execute.return_value = execute_result
    mock.table.return_value.insert.return_value.execute.return_value = execute_result
    mock.table.return_value.update.return_value.eq.return_value.execute.return_value = (
        execute_result
    )
    mock.table.return_value.select.return_value.eq.return_value.execute.return_value = (
        execute_result
    )

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
    recipes = [
        make_recipe(recipe_id=f"uuid-{i}", allergen_tags=["gluten"]) for i in range(5)
    ]
    mock = make_supabase_mock(data=recipes)

    results = await search_recipes(mock, "dejeuner", exclude_allergens=None)
    assert len(results) == 5


@pytest.mark.asyncio
async def test_search_recipes_disliked_in_name():
    """Excludes recipe when disliked food appears in recipe name."""
    recipes = [
        make_recipe(recipe_id="uuid-1", name="Galette fromage"),
        make_recipe(recipe_id="uuid-2", name="Poulet grillé"),
    ]
    mock = make_supabase_mock(data=recipes)

    results = await search_recipes(mock, "dejeuner", exclude_ingredients=["fromage"])

    assert len(results) == 1
    assert results[0]["id"] == "uuid-2"


@pytest.mark.asyncio
async def test_search_recipes_compound_food_exception():
    """Does NOT exclude 'fromage blanc' when 'fromage' is disliked (compound exception)."""
    recipes = [
        make_recipe(recipe_id="uuid-1", name="Fromage blanc fruits"),
        make_recipe(recipe_id="uuid-2", name="Galette fromage"),
    ]
    mock = make_supabase_mock(data=recipes)

    results = await search_recipes(mock, "dejeuner", exclude_ingredients=["fromage"])

    # "Fromage blanc fruits" should survive, "Galette fromage" should be excluded
    assert len(results) == 1
    assert results[0]["id"] == "uuid-1"


@pytest.mark.asyncio
async def test_disliked_synonym_parmesan():
    """'fromage' disliked excludes recipe with 'parmesan' via synonym mapping."""
    recipes = [
        make_recipe(recipe_id="uuid-1", name="Pâtes au parmesan"),
        make_recipe(recipe_id="uuid-2", name="Poulet grillé"),
    ]
    mock = make_supabase_mock(data=recipes)

    results = await search_recipes(mock, "dejeuner", exclude_ingredients=["fromage"])

    assert len(results) == 1
    assert results[0]["id"] == "uuid-2"


@pytest.mark.asyncio
async def test_disliked_synonym_in_ingredient():
    """'fromage' disliked excludes recipe with 'mozzarella' in ingredients."""
    recipe_mozza = make_recipe(recipe_id="uuid-1", name="Pizza maison")
    recipe_mozza["ingredients"] = [
        {"name": "pâte", "quantity": 200, "unit": "g"},
        {"name": "mozzarella", "quantity": 100, "unit": "g"},
    ]
    recipe_clean = make_recipe(recipe_id="uuid-2", name="Salade verte")
    mock = make_supabase_mock(data=[recipe_mozza, recipe_clean])

    results = await search_recipes(mock, "dejeuner", exclude_ingredients=["fromage"])

    assert len(results) == 1
    assert results[0]["id"] == "uuid-2"


def test_disliked_compound_exception_still_works():
    """'fromage blanc' is NOT excluded when 'fromage' is disliked (compound exception)."""
    assert _contains_disliked("fromage blanc fruits rouges", "fromage") is False
    assert _contains_disliked("gratin au fromage", "fromage") is True
    assert _contains_disliked("pâtes au parmesan", "fromage") is True


@pytest.mark.asyncio
async def test_search_recipes_disliked_in_ingredient():
    """Excludes recipe when disliked food appears in ingredient name."""
    recipe_with_cheese = make_recipe(recipe_id="uuid-1", name="Poulet grillé")
    recipe_with_cheese["ingredients"] = [
        {"name": "poulet", "quantity": 150, "unit": "g"},
        {"name": "fromage râpé", "quantity": 30, "unit": "g"},
    ]
    recipe_clean = make_recipe(recipe_id="uuid-2", name="Salade verte")
    mock = make_supabase_mock(data=[recipe_with_cheese, recipe_clean])

    results = await search_recipes(mock, "dejeuner", exclude_ingredients=["fromage"])

    assert len(results) == 1
    assert results[0]["id"] == "uuid-2"


@pytest.mark.asyncio
async def test_search_recipes_returns_all_cuisines():
    """Cuisine filtering removed from search_recipes — all cuisines returned."""
    recipes = [
        make_recipe(recipe_id="uuid-1", cuisine_type="asiatique"),
        make_recipe(recipe_id="uuid-2", cuisine_type="française"),
        make_recipe(recipe_id="uuid-3", cuisine_type="asiatique"),
    ]
    mock = make_supabase_mock(data=recipes)

    results = await search_recipes(mock, "dejeuner", cuisine_types=["asiatique"])

    # All recipes returned (cuisine ordering is now handled by score_recipe_variety)
    assert len(results) == 3


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
    execute_result.data = [
        {"id": "uuid", **recipe, "name_normalized": "omelette proteinee"}
    ]
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


# ---------------------------------------------------------------------------
# Test: score_macro_fit
# ---------------------------------------------------------------------------


class TestScoreMacroFit:
    def test_perfect_match_scores_zero(self):
        """A recipe whose macro ratios match the target exactly scores 0."""
        recipe = {
            "calories_per_serving": 500,
            "protein_g_per_serving": 40,
            "carbs_g_per_serving": 60,
            "fat_g_per_serving": 10,
        }
        target = {
            "target_calories": 1000,
            "target_protein_g": 80,
            "target_carbs_g": 120,
            "target_fat_g": 20,
        }
        assert abs(score_macro_fit(recipe, target)) < 0.001

    def test_protein_weighted_2x(self):
        """Protein mismatch contributes 2x to score vs carb mismatch."""
        base_target = {
            "target_calories": 500,
            "target_protein_g": 40,
            "target_carbs_g": 50,
            "target_fat_g": 10,
        }
        prot_off = {
            "calories_per_serving": 500,
            "protein_g_per_serving": 20,
            "carbs_g_per_serving": 50,
            "fat_g_per_serving": 10,
        }
        carb_off = {
            "calories_per_serving": 500,
            "protein_g_per_serving": 40,
            "carbs_g_per_serving": 25,
            "fat_g_per_serving": 10,
        }
        assert score_macro_fit(prot_off, base_target) > score_macro_fit(
            carb_off, base_target
        )


# ---------------------------------------------------------------------------
# Test: score_recipe_variety
# ---------------------------------------------------------------------------


class TestScoreRecipeVariety:
    """Tests for the multi-factor recipe variety scoring function."""

    def _make_recipe(self, **overrides) -> dict:
        """Helper to build a recipe dict with overrides."""
        base = {
            "calories_per_serving": 500,
            "protein_g_per_serving": 40,
            "carbs_g_per_serving": 50,
            "fat_g_per_serving": 15,
            "cuisine_type": "française",
            "usage_count": 5,
            "last_used_date": None,
        }
        base.update(overrides)
        return base

    def _target(self) -> dict:
        return {
            "target_calories": 600,
            "target_protein_g": 45,
            "target_carbs_g": 70,
            "target_fat_g": 18,
        }

    def test_never_used_max_freshness(self):
        """last_used_date=None → freshness=1.0 (maximum)."""
        recipe = self._make_recipe(last_used_date=None)
        now = datetime(2026, 2, 26, 12, 0, tzinfo=timezone.utc)
        score = score_recipe_variety(recipe, self._target(), now=now)
        # Freshness component should be 0.30 * 1.0 = 0.30
        assert score > 0

    def test_recent_vs_stale(self):
        """Used 1 day ago scores lower than used 15 days ago."""
        now = datetime(2026, 2, 26, 12, 0, tzinfo=timezone.utc)
        recent = self._make_recipe(last_used_date=(now - timedelta(days=1)).isoformat())
        stale = self._make_recipe(last_used_date=(now - timedelta(days=15)).isoformat())
        score_recent = score_recipe_variety(recent, self._target(), now=now)
        score_stale = score_recipe_variety(stale, self._target(), now=now)
        assert score_stale > score_recent

    def test_freshness_capped_at_30(self):
        """30+ days since use = same freshness as never used."""
        now = datetime(2026, 2, 26, 12, 0, tzinfo=timezone.utc)
        old = self._make_recipe(last_used_date=(now - timedelta(days=60)).isoformat())
        never = self._make_recipe(last_used_date=None)
        score_old = score_recipe_variety(old, self._target(), now=now)
        score_never = score_recipe_variety(never, self._target(), now=now)
        assert abs(score_old - score_never) < 0.001

    def test_cuisine_bonus(self):
        """Preferred cuisine gets +0.20 bonus."""
        recipe_pref = self._make_recipe(cuisine_type="asiatique")
        recipe_other = self._make_recipe(cuisine_type="française")
        now = datetime(2026, 2, 26, 12, 0, tzinfo=timezone.utc)
        score_pref = score_recipe_variety(
            recipe_pref, self._target(), preferred_cuisines=["asiatique"], now=now
        )
        score_other = score_recipe_variety(
            recipe_other, self._target(), preferred_cuisines=["asiatique"], now=now
        )
        assert score_pref > score_other
        # Difference should be approximately 0.20
        assert abs((score_pref - score_other) - 0.20) < 0.01

    def test_usage_inverse(self):
        """usage_count=0 scores higher than usage_count=10."""
        low_usage = self._make_recipe(usage_count=0)
        high_usage = self._make_recipe(usage_count=10)
        now = datetime(2026, 2, 26, 12, 0, tzinfo=timezone.utc)
        score_low = score_recipe_variety(low_usage, self._target(), now=now)
        score_high = score_recipe_variety(high_usage, self._target(), now=now)
        assert score_low > score_high

    def test_composite_ranking(self):
        """3 recipes: verify expected order (fresh+preferred > stale+preferred > stale+other)."""
        now = datetime(2026, 2, 26, 12, 0, tzinfo=timezone.utc)
        fresh_pref = self._make_recipe(
            cuisine_type="asiatique", last_used_date=None, usage_count=0
        )
        stale_pref = self._make_recipe(
            cuisine_type="asiatique",
            last_used_date=(now - timedelta(days=2)).isoformat(),
            usage_count=5,
        )
        stale_other = self._make_recipe(
            cuisine_type="française",
            last_used_date=(now - timedelta(days=2)).isoformat(),
            usage_count=5,
        )

        scores = [
            score_recipe_variety(
                r, self._target(), preferred_cuisines=["asiatique"], now=now
            )
            for r in [fresh_pref, stale_pref, stale_other]
        ]
        assert scores[0] > scores[1] > scores[2]

    def test_now_injectable(self):
        """Deterministic scoring with explicit `now` parameter."""
        now1 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        now2 = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
        recipe = self._make_recipe(
            last_used_date=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc).isoformat()
        )
        score1 = score_recipe_variety(recipe, self._target(), now=now1)
        score2 = score_recipe_variety(recipe, self._target(), now=now2)
        # 2 months later → higher freshness → higher score
        assert score2 > score1
