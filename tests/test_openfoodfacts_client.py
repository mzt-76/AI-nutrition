"""
Unit tests for OpenFoodFacts client.

Tests:
- search_food_local: Database search functionality
- match_ingredient: Cache-first matching strategy
- normalize_ingredient_name: String normalization
"""

import pytest

from src.clients import get_supabase_client
from src.nutrition.openfoodfacts_client import (
    _unit_to_multiplier,
    calculate_similarity,
    match_ingredient,
    normalize_ingredient_name,
    search_food_local,
)


def test_normalize_ingredient_name():
    """Test ingredient name normalization."""
    assert normalize_ingredient_name("Yaourt Grec") == "yaourt grec"
    assert normalize_ingredient_name("Café") == "cafe"
    assert normalize_ingredient_name("  POULET  ") == "poulet"
    assert normalize_ingredient_name("Crème fraîche") == "creme fraiche"


def test_calculate_similarity():
    """Test string similarity calculation."""
    # Exact match
    assert calculate_similarity("poulet", "poulet") == 1.0

    # Partial match
    similarity = calculate_similarity("poulet", "poulet rôti")
    assert 0.7 < similarity < 0.9

    # No match
    similarity = calculate_similarity("poulet", "xyz")
    assert similarity < 0.3


class TestUnitToMultiplier:
    """Tests for _unit_to_multiplier with discrete units (pièces)."""

    def test_grams(self):
        assert _unit_to_multiplier(150, "g", "poulet") == pytest.approx(1.5)

    def test_kg(self):
        assert _unit_to_multiplier(1, "kg", "poulet") == pytest.approx(10.0)

    def test_ml_water(self):
        assert _unit_to_multiplier(200, "ml", "eau") == pytest.approx(2.0)

    def test_ml_oil(self):
        # huile d'olive density = 0.92
        assert _unit_to_multiplier(100, "ml", "huile d'olive") == pytest.approx(0.92)

    def test_pieces_eggs(self):
        # 3 oeufs = 3 × 60g = 180g → multiplier = 1.8
        assert _unit_to_multiplier(3, "pièces", "oeufs") == pytest.approx(1.8)

    def test_pieces_eggs_accent(self):
        # œufs variant
        assert _unit_to_multiplier(2, "pièces", "œufs") == pytest.approx(1.2)

    def test_pieces_banane(self):
        # 1 banane = 120g → multiplier = 1.2
        assert _unit_to_multiplier(1, "pièces", "banane") == pytest.approx(1.2)

    def test_pieces_avocat(self):
        # 1 avocat = 150g → multiplier = 1.5
        assert _unit_to_multiplier(1, "pièces", "avocat") == pytest.approx(1.5)

    def test_pieces_filet_poulet(self):
        # 2 filets de poulet = 2 × 150g = 300g → multiplier = 3.0
        assert _unit_to_multiplier(2, "pièces", "filet de poulet") == pytest.approx(3.0)

    def test_pieces_unknown_fallback(self):
        # Unknown piece — falls back to quantity / 100
        assert _unit_to_multiplier(50, "pièces", "ingrédient inconnu") == pytest.approx(
            0.5
        )

    def test_pieces_muffin_anglais(self):
        # 1 muffin anglais = 57g → multiplier = 0.57
        assert _unit_to_multiplier(1, "pièces", "muffin anglais") == pytest.approx(0.57)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "ingredient,should_match",
    [
        ("poulet", True),
        ("riz basmati", True),
        ("yaourt grec", True),
        ("quinoa", True),
        ("amandes", True),
        ("fake-xyz-999", False),
    ],
)
async def test_search_food_local(ingredient, should_match):
    """Test database search for various ingredients.

    Args:
        ingredient: Ingredient name to search
        should_match: Whether we expect a confident match

    Expected:
        - Common ingredients should match with confidence >= 0.5
        - Fake ingredients should not match or have low confidence
    """
    supabase = get_supabase_client()
    results = await search_food_local(ingredient, supabase)

    if should_match:
        assert len(results) > 0, f"Expected results for '{ingredient}'"
        assert (
            results[0]["confidence"] >= 0.5
        ), f"Expected confidence >= 0.5 for '{ingredient}', got {results[0]['confidence']}"
        assert "name" in results[0]
        assert "calories_per_100g" in results[0]
        assert "protein_g_per_100g" in results[0]
    else:
        assert (
            not results or results[0]["confidence"] < 0.5
        ), f"Expected no confident match for '{ingredient}'"


@pytest.mark.asyncio
async def test_match_ingredient_basic():
    """Test basic ingredient matching with nutrition calculation."""
    supabase = get_supabase_client()

    # Test with a common ingredient
    result = await match_ingredient("poulet", 150, "g", supabase)

    assert result["ingredient_name"] == "poulet"
    assert result["quantity"] == 150
    assert result["unit"] == "g"
    assert result["calories"] > 0
    assert result["protein_g"] > 0
    assert 0 <= result["confidence"] <= 1.0

    # Verify nutrition scaling (150g should be 1.5x per-100g values)
    if result["matched_name"]:
        assert result["calories"] > 100  # Chicken has ~165 kcal per 100g


@pytest.mark.asyncio
async def test_match_ingredient_cache():
    """Test cache-first strategy.

    Expected:
        - First call: cache miss, search database
        - Second call: cache hit, retrieve from cache
        - Cache hit should have usage_count incremented
    """
    supabase = get_supabase_client()
    # Use a real ingredient that will match confidently
    test_ingredient = "poulet_cache_test"

    # Clean up any existing cache entry
    supabase.table("ingredient_mapping").delete().eq(
        "ingredient_name", test_ingredient
    ).execute()

    # First call - should be cache miss
    result1 = await match_ingredient(test_ingredient, 100, "g", supabase)

    # Only test caching if we got a confident match
    if result1["matched_name"] is None:
        pytest.skip("Ingredient did not match confidently, cannot test cache")

    assert result1["cache_hit"] is False, "First call should be cache miss"

    # Second call - should be cache hit
    result2 = await match_ingredient(test_ingredient, 100, "g", supabase)
    assert result2["cache_hit"] is True, "Second call should be cache hit"

    # Results should be consistent
    assert result1["calories"] == result2["calories"]
    assert result1["protein_g"] == result2["protein_g"]

    # Clean up
    supabase.table("ingredient_mapping").delete().eq(
        "ingredient_name", test_ingredient
    ).execute()


@pytest.mark.asyncio
async def test_match_ingredient_no_match():
    """Test behavior when no confident match is found."""
    supabase = get_supabase_client()

    result = await match_ingredient("fake_ingredient_xyz_999", 100, "g", supabase)

    assert result["matched_name"] is None
    assert result["openfoodfacts_code"] is None
    assert result["calories"] == 0
    assert result["protein_g"] == 0
    assert result["confidence"] == 0
    assert "error" in result


@pytest.mark.asyncio
async def test_match_ingredient_quantity_scaling():
    """Test nutrition values scale correctly with quantity."""
    supabase = get_supabase_client()

    # 100g baseline
    result_100g = await match_ingredient("poulet", 100, "g", supabase)

    # 200g should be 2x
    result_200g = await match_ingredient("poulet", 200, "g", supabase)

    if result_100g["matched_name"] and result_200g["matched_name"]:
        assert result_200g["calories"] == pytest.approx(
            result_100g["calories"] * 2, abs=1
        )
        assert result_200g["protein_g"] == pytest.approx(
            result_100g["protein_g"] * 2, abs=1
        )
