"""
Unit tests for OpenFoodFacts client.

Tests:
- search_food_local: Database search functionality
- match_ingredient: Cache-first matching strategy
- normalize_ingredient_name: String normalization
"""

import os

import pytest

from src.clients import get_async_supabase_client

requires_real_db = pytest.mark.skipif(
    os.getenv("SUPABASE_URL", "").startswith("https://fake"),
    reason="Requires real Supabase DB (skipped in CI)",
)
from src.nutrition.openfoodfacts_client import (
    _calorie_density_plausible,
    _get_ingredient_category,
    _passes_atwater_check,
    _pick_best_candidate,
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


class TestAtwaterCheck:
    """Tests for _passes_atwater_check Atwater sanity check."""

    def test_correct_egg_passes(self):
        product = {
            "name": "Oeuf",
            "calories_per_100g": 145,
            "protein_g_per_100g": 12.3,
            "carbs_g_per_100g": 0.7,
            "fat_g_per_100g": 10.3,
        }
        assert _passes_atwater_check(product) is True

    def test_corrupted_egg_fails(self):
        product = {
            "name": "Oeufs",
            "code": "3273020001242",
            "calories_per_100g": 142,
            "protein_g_per_100g": 12.6,
            "carbs_g_per_100g": 0.8,
            "fat_g_per_100g": 36.0,  # corrupted — should be ~10
        }
        assert _passes_atwater_check(product) is False

    def test_zero_macros_with_calories_fails(self):
        product = {
            "name": "Almond flour",
            "calories_per_100g": 629,
            "protein_g_per_100g": 0,
            "carbs_g_per_100g": 0,
            "fat_g_per_100g": 0,
        }
        assert _passes_atwater_check(product) is False

    def test_spice_low_cal_passes(self):
        product = {
            "name": "Sel",
            "calories_per_100g": 0,
            "protein_g_per_100g": 0,
            "carbs_g_per_100g": 0,
            "fat_g_per_100g": 0,
        }
        assert _passes_atwater_check(product) is True

    def test_normal_chicken_passes(self):
        product = {
            "name": "Poulet",
            "calories_per_100g": 165,
            "protein_g_per_100g": 31,
            "carbs_g_per_100g": 0,
            "fat_g_per_100g": 3.6,
        }
        assert _passes_atwater_check(product) is True

    def test_oats_passes_with_fiber_tolerance(self):
        # Oats: cal=375, P=11, G=60, L=8 → Atwater=356. Diff=5% (fiber)
        product = {
            "name": "Flocons d'avoine",
            "calories_per_100g": 375,
            "protein_g_per_100g": 11,
            "carbs_g_per_100g": 60,
            "fat_g_per_100g": 8,
        }
        assert _passes_atwater_check(product) is True


class TestCalorieDensityGuard:
    """Tests for calorie density plausibility checks."""

    def test_fresh_vegetable_plausible(self):
        assert _calorie_density_plausible("poivron", 30) is True

    def test_fresh_vegetable_implausible(self):
        """Dried pepper mapped as fresh — should be rejected."""
        assert _calorie_density_plausible("poivron", 275) is False

    def test_fresh_fruit_plausible(self):
        assert _calorie_density_plausible("pomme", 52) is True

    def test_fresh_fruit_implausible(self):
        """Dried apple chips mapped as fresh — should be rejected."""
        assert _calorie_density_plausible("pomme", 352) is False

    def test_meat_plausible(self):
        assert _calorie_density_plausible("poulet", 165) is True

    def test_unknown_ingredient_always_passes(self):
        """Unknown categories should not be rejected."""
        assert _calorie_density_plausible("quinoa", 368) is True
        assert _calorie_density_plausible("huile d'olive", 884) is True

    def test_liquid_bouillon_plausible(self):
        """Bouillon liquide réel à 2-5 kcal/100g → passe."""
        assert _calorie_density_plausible("bouillon de légumes", 2) is True
        assert _calorie_density_plausible("bouillon de poulet", 4) is True

    def test_liquid_bouillon_implausible(self):
        """Bouillon poudre à 200 kcal/100g mappé comme liquide → rejeté."""
        assert _calorie_density_plausible("bouillon de légumes", 200) is False
        assert _calorie_density_plausible("bouillon de poulet", 154) is False

    def test_liquid_sauce_soja_plausible(self):
        """Sauce soja liquide réelle à 34 kcal/100g → passe."""
        assert _calorie_density_plausible("sauce soja", 34) is True

    def test_liquid_sauce_soja_implausible(self):
        """Sauce soja concentrée à 225 kcal/100g → rejeté."""
        assert _calorie_density_plausible("sauce soja", 225) is False

    def test_liquid_dashi_implausible(self):
        """Dashi poudre à 312 kcal/100g → rejeté."""
        assert _calorie_density_plausible("dashi", 312) is False

    def test_liquid_vinegar_plausible(self):
        """Vinaigre réel à 1-4 kcal/100g → passe."""
        assert _calorie_density_plausible("vinaigre de vin rouge", 4) is True
        assert _calorie_density_plausible("vinaigre blanc", 1) is True

    def test_liquid_vinegar_implausible(self):
        """Vinaigre mislabel à 86-118 kcal/100g → rejeté."""
        assert _calorie_density_plausible("vinaigre de vin rouge", 118) is False
        assert _calorie_density_plausible("vinaigre blanc", 86) is False

    def test_dense_liquid_not_in_aqueous_category(self):
        """Liquides légitimement denses ne sont PAS dans liquide_aqueux → passent."""
        assert _calorie_density_plausible("mirin", 218) is True
        assert _calorie_density_plausible("sauce teriyaki", 133) is True
        assert _calorie_density_plausible("vinaigre balsamique", 88) is True

    def test_category_lookup(self):
        assert _get_ingredient_category("poivron rouge") == "légume"
        assert _get_ingredient_category("épinards frais") == "légume"
        assert _get_ingredient_category("pomme verte") == "fruit"
        assert _get_ingredient_category("blanc de poulet") == "viande_crue"
        assert _get_ingredient_category("quinoa") is None

    def test_liquid_category_lookup(self):
        assert _get_ingredient_category("bouillon de légumes") == "liquide_aqueux"
        assert _get_ingredient_category("sauce soja") == "liquide_aqueux"
        assert _get_ingredient_category("dashi") == "liquide_aqueux"
        assert _get_ingredient_category("vinaigre de vin rouge") == "liquide_aqueux"
        # NOT liquide_aqueux
        assert _get_ingredient_category("mirin") is None
        assert _get_ingredient_category("sauce teriyaki") is None


class TestPickBestCandidate:
    """Tests for _pick_best_candidate preferring fresh products."""

    def test_prefers_fresh_over_dried(self):
        """When confidence is similar, should pick lower calorie density."""
        candidates = [
            {
                "name": "Poivron séché",
                "confidence": 0.95,
                "calories_per_100g": 275,
                "protein_g_per_100g": 11,
                "carbs_g_per_100g": 35,
                "fat_g_per_100g": 3.3,
                "code": "111",
            },
            {
                "name": "Poivrons frais",
                "confidence": 0.90,
                "calories_per_100g": 35,
                "protein_g_per_100g": 0.8,
                "carbs_g_per_100g": 3.2,
                "fat_g_per_100g": 1.5,
                "code": "222",
            },
        ]
        best = _pick_best_candidate(candidates, "poivron")
        assert best["name"] == "Poivrons frais"

    def test_rejects_all_implausible(self):
        """If all candidates fail density check, returns None."""
        candidates = [
            {
                "name": "Poivron séché",
                "confidence": 0.95,
                "calories_per_100g": 275,
                "protein_g_per_100g": 11,
                "carbs_g_per_100g": 35,
                "fat_g_per_100g": 3.3,
                "code": "111",
            },
        ]
        best = _pick_best_candidate(candidates, "poivron")
        assert best is None

    def test_unknown_category_keeps_first(self):
        """For unknown categories, just picks the first valid candidate."""
        candidates = [
            {
                "name": "Quinoa",
                "confidence": 0.95,
                "calories_per_100g": 368,
                "protein_g_per_100g": 14,
                "carbs_g_per_100g": 64,
                "fat_g_per_100g": 6,
                "code": "111",
            },
        ]
        best = _pick_best_candidate(candidates, "quinoa")
        assert best["name"] == "Quinoa"

    def test_empty_candidates(self):
        assert _pick_best_candidate([], "poulet") is None

    def test_low_confidence_rejected(self):
        candidates = [
            {
                "name": "Something",
                "confidence": 0.3,
                "calories_per_100g": 50,
                "protein_g_per_100g": 2,
                "carbs_g_per_100g": 8,
                "fat_g_per_100g": 1,
                "code": "111",
            },
        ]
        assert _pick_best_candidate(candidates, "tomate") is None


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


@requires_real_db
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
    supabase = get_async_supabase_client()
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


@requires_real_db
@pytest.mark.asyncio
async def test_match_ingredient_basic():
    """Test basic ingredient matching with nutrition calculation."""
    supabase = get_async_supabase_client()

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


@requires_real_db
@pytest.mark.asyncio
async def test_match_ingredient_cache():
    """Test cache-first strategy.

    Expected:
        - First call: cache miss, search database
        - Second call: cache hit, retrieve from cache
        - Cache hit should have usage_count incremented
    """
    supabase = get_async_supabase_client()
    # Use a real ingredient that will match confidently
    test_ingredient = "poulet_cache_test"

    # Clean up any existing cache entry
    await (
        supabase.table("ingredient_mapping")
        .delete()
        .eq("ingredient_name", test_ingredient)
        .execute()
    )

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
    await (
        supabase.table("ingredient_mapping")
        .delete()
        .eq("ingredient_name", test_ingredient)
        .execute()
    )


@pytest.mark.asyncio
async def test_match_ingredient_no_match():
    """Test behavior when no confident match is found."""
    supabase = get_async_supabase_client()

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
    supabase = get_async_supabase_client()

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
