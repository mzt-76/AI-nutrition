"""Unit tests for src/nutrition/portion_scaler.py.

Tests mathematical portion scaling — pure functions, no I/O.
"""

import pytest
from src.nutrition.portion_scaler import (
    calculate_scale_factor,
    scale_ingredients,
    calculate_scaled_nutrition,
    scale_recipe_to_targets,
)
from src.nutrition.meal_plan_optimizer import MIN_SCALE_FACTOR, MAX_SCALE_FACTOR


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_recipe():
    """Sample recipe with standard nutrition per serving."""
    return {
        "name": "Omelette protéinée",
        "meal_type": "petit-dejeuner",
        "calories_per_serving": 400.0,
        "protein_g_per_serving": 28.0,
        "carbs_g_per_serving": 10.0,
        "fat_g_per_serving": 28.0,
        "ingredients": [
            {"name": "oeufs", "quantity": 3, "unit": "pièces"},
            {"name": "épinards", "quantity": 50, "unit": "g"},
            {"name": "huile d'olive", "quantity": 10, "unit": "ml"},
            {"name": "sel", "quantity": 2, "unit": "g"},
        ],
    }


@pytest.fixture
def high_calorie_recipe():
    """Recipe with 800 kcal for testing downscaling."""
    return {
        "name": "Riz poulet",
        "calories_per_serving": 800.0,
        "protein_g_per_serving": 50.0,
        "carbs_g_per_serving": 90.0,
        "fat_g_per_serving": 25.0,
        "ingredients": [
            {"name": "poulet", "quantity": 200, "unit": "g"},
            {"name": "riz", "quantity": 150, "unit": "g"},
        ],
    }


# ---------------------------------------------------------------------------
# Test: calculate_scale_factor
# ---------------------------------------------------------------------------


class TestCalculateScaleFactor:
    def test_basic_scale_up(self):
        """Scale from 400 to 600 kcal → factor 1.5."""
        factor = calculate_scale_factor(400, 600)
        assert abs(factor - 1.5) < 0.001

    def test_basic_scale_down(self):
        """Scale from 600 to 300 kcal → factor 0.5."""
        factor = calculate_scale_factor(600, 300)
        assert abs(factor - 0.5) < 0.001

    def test_no_scale_needed(self):
        """Same calories → factor 1.0."""
        factor = calculate_scale_factor(500, 500)
        assert abs(factor - 1.0) < 0.001

    def test_clamped_to_max(self):
        """Target >> actual → clamped to MAX_SCALE_FACTOR."""
        factor = calculate_scale_factor(200, 10000)
        assert factor == MAX_SCALE_FACTOR

    def test_clamped_to_min(self):
        """Target << actual → clamped to MIN_SCALE_FACTOR."""
        factor = calculate_scale_factor(2000, 1)
        assert factor == MIN_SCALE_FACTOR

    def test_zero_actual_calories_returns_1(self):
        """Avoid division by zero — return 1.0."""
        factor = calculate_scale_factor(0, 500)
        assert factor == 1.0

    def test_bounds_are_respected(self):
        """Scale factor is always within [MIN, MAX]."""
        for actual, target in [(100, 1000), (1000, 10), (300, 300)]:
            factor = calculate_scale_factor(actual, target)
            assert MIN_SCALE_FACTOR <= factor <= MAX_SCALE_FACTOR


# ---------------------------------------------------------------------------
# Test: scale_ingredients
# ---------------------------------------------------------------------------


class TestScaleIngredients:
    def test_grams_scale_to_integer(self):
        """Grams should scale and round to integer."""
        ingredients = [{"name": "poulet", "quantity": 100, "unit": "g"}]
        scaled = scale_ingredients(ingredients, 1.5)
        assert scaled[0]["quantity"] == 150
        assert isinstance(scaled[0]["quantity"], int)

    def test_eggs_stay_integer(self):
        """Countable units (pièces) must be whole numbers."""
        ingredients = [{"name": "oeufs", "quantity": 3, "unit": "pièces"}]
        scaled = scale_ingredients(ingredients, 1.3)
        assert isinstance(scaled[0]["quantity"], int)
        # 3 * 1.3 = 3.9 → rounds to 4
        assert scaled[0]["quantity"] == 4

    def test_small_spice_keeps_decimal(self):
        """Small spice quantities (<10g) keep 1 decimal."""
        ingredients = [{"name": "sel", "quantity": 2.0, "unit": "g"}]
        scaled = scale_ingredients(ingredients, 1.5)
        # 2.0 * 1.5 = 3.0 → round to 1 decimal
        assert scaled[0]["quantity"] == 3.0

    def test_preserves_other_fields(self):
        """Scaling should not drop other ingredient fields."""
        ingredients = [
            {
                "name": "quinoa",
                "quantity": 80,
                "unit": "g",
                "nutrition_per_100g": {"calories": 368},
            }
        ]
        scaled = scale_ingredients(ingredients, 1.0)
        assert "nutrition_per_100g" in scaled[0]

    def test_empty_ingredients(self):
        """Empty list returns empty list."""
        assert scale_ingredients([], 1.5) == []

    def test_scale_factor_1_no_change(self):
        """Scale factor 1.0 → quantities unchanged."""
        ingredients = [{"name": "riz", "quantity": 100, "unit": "g"}]
        scaled = scale_ingredients(ingredients, 1.0)
        assert scaled[0]["quantity"] == 100

    def test_multiple_ingredients_scaled_proportionally(self):
        """All ingredients scaled by same factor."""
        ingredients = [
            {"name": "poulet", "quantity": 100, "unit": "g"},
            {"name": "riz", "quantity": 80, "unit": "g"},
        ]
        scaled = scale_ingredients(ingredients, 1.5)
        assert scaled[0]["quantity"] == 150
        assert scaled[1]["quantity"] == 120


# ---------------------------------------------------------------------------
# Test: calculate_scaled_nutrition
# ---------------------------------------------------------------------------


class TestCalculateScaledNutrition:
    def test_proportional_scaling(self):
        """All macros scale proportionally."""
        recipe = {
            "calories_per_serving": 400.0,
            "protein_g_per_serving": 30.0,
            "carbs_g_per_serving": 40.0,
            "fat_g_per_serving": 15.0,
        }
        result = calculate_scaled_nutrition(recipe, 1.5)
        assert result["calories"] == pytest.approx(600.0)
        assert result["protein_g"] == pytest.approx(45.0)
        assert result["carbs_g"] == pytest.approx(60.0)
        assert result["fat_g"] == pytest.approx(22.5)

    def test_scale_down(self):
        """Downscaling reduces all macros proportionally."""
        recipe = {
            "calories_per_serving": 800.0,
            "protein_g_per_serving": 50.0,
            "carbs_g_per_serving": 90.0,
            "fat_g_per_serving": 25.0,
        }
        result = calculate_scaled_nutrition(recipe, 0.5)
        assert result["calories"] == pytest.approx(400.0)
        assert result["protein_g"] == pytest.approx(25.0)
        assert result["carbs_g"] == pytest.approx(45.0)
        assert result["fat_g"] == pytest.approx(12.5)

    def test_scale_1_returns_original(self):
        """Scale factor 1.0 returns original values."""
        recipe = {
            "calories_per_serving": 500.0,
            "protein_g_per_serving": 35.0,
            "carbs_g_per_serving": 55.0,
            "fat_g_per_serving": 18.0,
        }
        result = calculate_scaled_nutrition(recipe, 1.0)
        assert result["calories"] == pytest.approx(500.0)
        assert result["protein_g"] == pytest.approx(35.0)


# ---------------------------------------------------------------------------
# Test: scale_recipe_to_targets
# ---------------------------------------------------------------------------


class TestScaleRecipeToTargets:
    def test_happy_path(self, sample_recipe):
        """Recipe scaled correctly to target calories."""
        result = scale_recipe_to_targets(
            sample_recipe, target_calories=600, target_protein_g=42
        )
        assert "scaled_nutrition" in result
        assert "scale_factor" in result
        # 600 / 400 = 1.5 → scaled = 600
        assert result["scaled_nutrition"]["calories"] == pytest.approx(600.0)

    def test_ingredients_scaled(self, sample_recipe):
        """Ingredients quantities are scaled in output."""
        result = scale_recipe_to_targets(
            sample_recipe, target_calories=800, target_protein_g=56
        )
        # 800 / 400 = 2.0 — within MAX_SCALE_FACTOR (2.5)
        # oeufs: 3 * 2.0 = 6
        eggs = next(i for i in result["ingredients"] if i["unit"] == "pièces")
        assert isinstance(eggs["quantity"], int)
        assert eggs["quantity"] == 6

    def test_returns_new_recipe_dict(self, sample_recipe):
        """Original recipe is not mutated."""
        original_qty = sample_recipe["ingredients"][0]["quantity"]
        scale_recipe_to_targets(sample_recipe, target_calories=600, target_protein_g=42)
        assert sample_recipe["ingredients"][0]["quantity"] == original_qty

    def test_raises_on_empty_recipe(self):
        """Empty recipe raises ValueError."""
        with pytest.raises(ValueError, match="recipe cannot be None or empty"):
            scale_recipe_to_targets({}, target_calories=500, target_protein_g=30)

    def test_raises_on_zero_calories_target(self, sample_recipe):
        """Zero target calories raises ValueError."""
        with pytest.raises(ValueError, match="target_calories must be positive"):
            scale_recipe_to_targets(
                sample_recipe, target_calories=0, target_protein_g=30
            )

    def test_clamped_scale_factor(self, sample_recipe):
        """Extreme targets are clamped to MAX/MIN_SCALE_FACTOR."""
        # Target 10000 kcal → clamped to MAX
        result = scale_recipe_to_targets(
            sample_recipe, target_calories=10000, target_protein_g=200
        )
        assert result["scale_factor"] == MAX_SCALE_FACTOR

    def test_nutrition_proportionality(self, sample_recipe):
        """All macros scale by exactly the same factor."""
        result = scale_recipe_to_targets(
            sample_recipe, target_calories=600, target_protein_g=42
        )
        scale = result["scale_factor"]
        expected_protein = sample_recipe["protein_g_per_serving"] * scale
        assert result["scaled_nutrition"]["protein_g"] == pytest.approx(
            expected_protein, rel=0.01
        )
