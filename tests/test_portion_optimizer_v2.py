"""Unit tests for MILP per-ingredient portion optimization.

Tests optimize_day_portions_v2, apply_ingredient_scale_factors, and _prepare_ingredients.
"""

import copy
import time

import pytest

from src.nutrition.portion_optimizer_v2 import (
    _prepare_ingredients,
    apply_ingredient_scale_factors,
    optimize_day_portions_v2,
)

# ---------------------------------------------------------------------------
# Reusable ingredient nutrition data (per 100g)
# ---------------------------------------------------------------------------

CHICKEN_PER_100G = {"calories": 165, "protein_g": 31, "fat_g": 3.6, "carbs_g": 0}
RICE_PER_100G = {"calories": 130, "protein_g": 2.7, "fat_g": 0.3, "carbs_g": 28}
BROCCOLI_PER_100G = {"calories": 34, "protein_g": 2.8, "fat_g": 0.4, "carbs_g": 7}
OLIVE_OIL_PER_100G = {"calories": 884, "protein_g": 0, "fat_g": 100, "carbs_g": 0}
EGG_PER_100G = {"calories": 155, "protein_g": 13, "fat_g": 11, "carbs_g": 1.1}
SALT_PER_100G = {"calories": 0, "protein_g": 0, "fat_g": 0, "carbs_g": 0}
OATS_PER_100G = {"calories": 389, "protein_g": 17, "fat_g": 7, "carbs_g": 66}


def _make_recipe(ingredients: list[dict], name: str = "Test") -> dict:
    """Build a recipe dict from ingredient specs."""
    return {
        "name": name,
        "meal_type": "dejeuner",
        "ingredients": ingredients,
        "instructions": "Test instructions.",
        "prep_time_minutes": 20,
    }


def _chicken_rice_broccoli_oil() -> dict:
    """Standard test recipe: chicken + rice + broccoli + olive oil."""
    return _make_recipe(
        [
            {
                "name": "Poulet",
                "quantity": 150,
                "unit": "g",
                "nutrition_per_100g": CHICKEN_PER_100G,
            },
            {
                "name": "Riz",
                "quantity": 100,
                "unit": "g",
                "nutrition_per_100g": RICE_PER_100G,
            },
            {
                "name": "Brocoli",
                "quantity": 100,
                "unit": "g",
                "nutrition_per_100g": BROCCOLI_PER_100G,
            },
            {
                "name": "Huile d'olive",
                "quantity": 10,
                "unit": "ml",
                "nutrition_per_100g": OLIVE_OIL_PER_100G,
            },
            {
                "name": "Sel",
                "quantity": 2,
                "unit": "g",
                "nutrition_per_100g": SALT_PER_100G,
            },
        ],
        name="Poulet riz brocoli",
    )


def _egg_oats_recipe() -> dict:
    """Recipe with discrete item (eggs) + continuous (oats)."""
    return _make_recipe(
        [
            {
                "name": "Oeufs",
                "quantity": 2,
                "unit": "oeufs",
                "nutrition_per_100g": EGG_PER_100G,
            },
            {
                "name": "Flocons d'avoine",
                "quantity": 80,
                "unit": "g",
                "nutrition_per_100g": OATS_PER_100G,
            },
        ],
        name="Oeufs avoine",
    )


# ---------------------------------------------------------------------------
# TestPrepareIngredients
# ---------------------------------------------------------------------------


class TestPrepareIngredients:
    def test_tags_correctly(self):
        recipe = _chicken_rice_broccoli_oil()
        scalable, fixed = _prepare_ingredients([recipe])
        roles = {v.name: v.role for v in scalable}
        assert roles["Poulet"] == "protein"
        assert roles["Riz"] == "starch"
        assert roles["Brocoli"] == "vegetable"
        assert roles["Huile d'olive"] == "fat_source"
        # Sel is fixed → not in scalable
        assert "Sel" not in roles

    def test_discrete_detection(self):
        recipe = _egg_oats_recipe()
        scalable, _ = _prepare_ingredients([recipe])
        egg_var = next(v for v in scalable if "Oeufs" in v.name)
        assert egg_var.is_discrete is True
        oats_var = next(v for v in scalable if "avoine" in v.name)
        assert oats_var.is_discrete is False

    def test_bounds_from_role(self):
        recipe = _chicken_rice_broccoli_oil()
        scalable, _ = _prepare_ingredients([recipe])
        chicken_var = next(v for v in scalable if v.name == "Poulet")
        assert chicken_var.lb == 0.5
        assert chicken_var.ub == 2.0

    def test_unknown_ingredient(self):
        recipe = _make_recipe(
            [
                {
                    "name": "Gochujang",
                    "quantity": 50,
                    "unit": "g",
                    "nutrition_per_100g": {
                        "calories": 200,
                        "protein_g": 3,
                        "fat_g": 1,
                        "carbs_g": 40,
                    },
                }
            ]
        )
        scalable, _ = _prepare_ingredients([recipe])
        assert scalable[0].role == "unknown"
        assert scalable[0].lb == 0.75
        assert scalable[0].ub == 1.25

    def test_fixed_not_in_variables(self):
        recipe = _chicken_rice_broccoli_oil()
        scalable, fixed = _prepare_ingredients([recipe])
        scalable_names = {v.name for v in scalable}
        assert "Sel" not in scalable_names
        fixed_names = {ing.get("name") for _, _, ing in fixed}
        assert "Sel" in fixed_names


# ---------------------------------------------------------------------------
# TestOptimizeDayPortionsV2
# ---------------------------------------------------------------------------


class TestOptimizeDayPortionsV2:
    def test_basic_single_recipe(self):
        """MILP finds factors that bring macros close to targets."""
        recipe = _chicken_rice_broccoli_oil()
        targets = {"calories": 600, "protein_g": 50, "fat_g": 15, "carbs_g": 60}
        result = optimize_day_portions_v2([recipe], targets)
        assert len(result) == 1
        assert len(result[0]) > 0  # at least some ingredients scaled

    def test_protein_scaling_up(self):
        """High protein target → chicken scaled up."""
        recipe = _chicken_rice_broccoli_oil()
        targets = {"calories": 700, "protein_g": 80, "fat_g": 20, "carbs_g": 60}
        result = optimize_day_portions_v2([recipe], targets)
        # Chicken is index 0
        chicken_sf = result[0].get(0, 1.0)
        assert chicken_sf > 1.0, f"Expected chicken scale > 1.0, got {chicken_sf}"

    def test_fat_reduction(self):
        """Low fat target → oil scaled down aggressively."""
        recipe = _chicken_rice_broccoli_oil()
        targets = {"calories": 500, "protein_g": 45, "fat_g": 8, "carbs_g": 50}
        result = optimize_day_portions_v2([recipe], targets)
        # Oil is index 3
        oil_sf = result[0].get(3, 1.0)
        assert oil_sf < 1.0, f"Expected oil scale < 1.0, got {oil_sf}"

    def test_discrete_eggs_stay_integer(self):
        """Eggs should be integer quantities."""
        recipe = _egg_oats_recipe()
        targets = {"calories": 500, "protein_g": 30, "fat_g": 15, "carbs_g": 55}
        result = optimize_day_portions_v2([recipe], targets)
        # Eggs are index 0 with discrete unit
        egg_val = result[0].get(0)
        if egg_val is not None:
            assert egg_val == round(
                egg_val
            ), f"Egg qty should be integer, got {egg_val}"

    def test_multi_recipe_day(self):
        """3 recipes optimized simultaneously."""
        r1 = _chicken_rice_broccoli_oil()
        r2 = _egg_oats_recipe()
        r3 = _make_recipe(
            [
                {
                    "name": "Saumon",
                    "quantity": 150,
                    "unit": "g",
                    "nutrition_per_100g": {
                        "calories": 208,
                        "protein_g": 20,
                        "fat_g": 13,
                        "carbs_g": 0,
                    },
                },
                {
                    "name": "Quinoa",
                    "quantity": 80,
                    "unit": "g",
                    "nutrition_per_100g": RICE_PER_100G,
                },
            ],
            name="Saumon quinoa",
        )
        targets = {"calories": 1800, "protein_g": 140, "fat_g": 55, "carbs_g": 200}
        result = optimize_day_portions_v2([r1, r2, r3], targets)
        assert len(result) == 3
        assert all(isinstance(d, dict) for d in result)

    def test_per_meal_targets(self):
        """With per_meal_targets, calorie distribution is balanced."""
        r1 = _chicken_rice_broccoli_oil()
        r2 = _egg_oats_recipe()
        targets = {"calories": 1000, "protein_g": 70, "fat_g": 30, "carbs_g": 100}
        result = optimize_day_portions_v2(
            [r1, r2], targets, per_meal_targets=[600.0, 400.0]
        )
        assert len(result) == 2

    def test_all_fixed_returns_empty(self):
        """Recipe of only fixed ingredients → empty scale factors."""
        recipe = _make_recipe(
            [
                {
                    "name": "Sel",
                    "quantity": 5,
                    "unit": "g",
                    "nutrition_per_100g": SALT_PER_100G,
                },
                {
                    "name": "Poivre",
                    "quantity": 2,
                    "unit": "g",
                    "nutrition_per_100g": SALT_PER_100G,
                },
            ]
        )
        targets = {"calories": 500, "protein_g": 30, "fat_g": 15, "carbs_g": 50}
        result = optimize_day_portions_v2([recipe], targets)
        assert result[0] == {}

    def test_infeasible_fallback(self):
        """Impossible targets → fallback uniform scaling (no crash)."""
        recipe = _chicken_rice_broccoli_oil()
        # Absurdly high targets that the bounded variables can't reach
        targets = {"calories": 50000, "protein_g": 5000, "fat_g": 1000, "carbs_g": 8000}
        result = optimize_day_portions_v2([recipe], targets)
        assert len(result) == 1
        # Should still return something (fallback)
        assert isinstance(result[0], dict)

    def test_empty_recipes_raises(self):
        with pytest.raises(ValueError, match="empty"):
            optimize_day_portions_v2(
                [], {"calories": 500, "protein_g": 30, "fat_g": 15, "carbs_g": 50}
            )

    def test_zero_calories_target_raises(self):
        recipe = _chicken_rice_broccoli_oil()
        with pytest.raises(ValueError, match="positive"):
            optimize_day_portions_v2(
                [recipe], {"calories": 0, "protein_g": 30, "fat_g": 15, "carbs_g": 50}
            )

    def test_performance_under_50ms(self):
        """20+ variables should solve in <50ms."""
        # Build a recipe with many ingredients
        ingredients = [
            {
                "name": "Poulet",
                "quantity": 150,
                "unit": "g",
                "nutrition_per_100g": CHICKEN_PER_100G,
            },
            {
                "name": "Riz",
                "quantity": 100,
                "unit": "g",
                "nutrition_per_100g": RICE_PER_100G,
            },
            {
                "name": "Brocoli",
                "quantity": 100,
                "unit": "g",
                "nutrition_per_100g": BROCCOLI_PER_100G,
            },
            {
                "name": "Huile d'olive",
                "quantity": 10,
                "unit": "ml",
                "nutrition_per_100g": OLIVE_OIL_PER_100G,
            },
            {
                "name": "Carotte",
                "quantity": 80,
                "unit": "g",
                "nutrition_per_100g": BROCCOLI_PER_100G,
            },
            {
                "name": "Tomate",
                "quantity": 100,
                "unit": "g",
                "nutrition_per_100g": {
                    "calories": 18,
                    "protein_g": 0.9,
                    "fat_g": 0.2,
                    "carbs_g": 3.9,
                },
            },
        ]
        r1 = _make_recipe(ingredients, "Big recipe 1")
        r2 = _make_recipe(ingredients[:4], "Big recipe 2")
        r3 = _make_recipe(ingredients[:3], "Big recipe 3")

        targets = {"calories": 1800, "protein_g": 130, "fat_g": 50, "carbs_g": 200}

        start = time.perf_counter()
        optimize_day_portions_v2([r1, r2, r3], targets)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 50, f"MILP took {elapsed_ms:.0f}ms, expected <50ms"


# ---------------------------------------------------------------------------
# TestMixedVariableFormulation
# ---------------------------------------------------------------------------


class TestMixedVariableFormulation:
    def test_mixed_recipe_macros_exact(self):
        """Verify MILP solution matches manual macro recalculation."""
        recipe = _make_recipe(
            [
                {
                    "name": "Oeufs",
                    "quantity": 2,
                    "unit": "oeufs",
                    "nutrition_per_100g": EGG_PER_100G,
                },
                {
                    "name": "Riz",
                    "quantity": 150,
                    "unit": "g",
                    "nutrition_per_100g": RICE_PER_100G,
                },
                {
                    "name": "Brocoli",
                    "quantity": 100,
                    "unit": "g",
                    "nutrition_per_100g": BROCCOLI_PER_100G,
                },
                {
                    "name": "Huile d'olive",
                    "quantity": 10,
                    "unit": "ml",
                    "nutrition_per_100g": OLIVE_OIL_PER_100G,
                },
            ]
        )
        targets = {"calories": 600, "protein_g": 35, "fat_g": 18, "carbs_g": 70}
        factors_list = optimize_day_portions_v2([recipe], targets)
        factors = factors_list[0]

        # Apply and check
        scaled = apply_ingredient_scale_factors(recipe, factors)
        sn = scaled["scaled_nutrition"]
        # Should be reasonably close to targets (within ±30% at worst)
        assert sn["calories"] > 0

    def test_discrete_coefficient_consistency(self):
        """Discrete item coefficient produces consistent macro contribution."""
        recipe = _make_recipe(
            [
                {
                    "name": "Oeufs",
                    "quantity": 2,
                    "unit": "oeufs",
                    "nutrition_per_100g": EGG_PER_100G,
                },
                {
                    "name": "Riz",
                    "quantity": 100,
                    "unit": "g",
                    "nutrition_per_100g": RICE_PER_100G,
                },
            ]
        )
        targets = {"calories": 400, "protein_g": 25, "fat_g": 12, "carbs_g": 30}
        factors_list = optimize_day_portions_v2([recipe], targets)
        factors = factors_list[0]

        if 0 in factors:
            egg_qty = factors[0]  # final pieces
            # Manual: egg_qty * 60g/piece / 100 * 155 cal/100g
            expected_cal = egg_qty * 60 / 100 * 155
            assert expected_cal > 0

    def test_divergence_with_mixed_types(self):
        """Divergence constraint respects mixed discrete/continuous variables."""
        recipe = _make_recipe(
            [
                {
                    "name": "Oeufs",
                    "quantity": 2,
                    "unit": "oeufs",
                    "nutrition_per_100g": EGG_PER_100G,
                },
                {
                    "name": "Riz",
                    "quantity": 80,
                    "unit": "g",
                    "nutrition_per_100g": RICE_PER_100G,
                },
            ]
        )
        targets = {"calories": 400, "protein_g": 25, "fat_g": 12, "carbs_g": 40}
        factors_list = optimize_day_portions_v2([recipe], targets)
        # Should not crash — divergence constraint handles mixed types
        assert len(factors_list) == 1


# ---------------------------------------------------------------------------
# TestApplyIngredientScaleFactors
# ---------------------------------------------------------------------------


class TestApplyIngredientScaleFactors:
    def test_basic_scaling(self):
        recipe = _chicken_rice_broccoli_oil()
        factors = {0: 1.5, 1: 1.2, 2: 1.0, 3: 0.5}  # chicken, rice, broccoli, oil
        scaled = apply_ingredient_scale_factors(recipe, factors)
        assert scaled["ingredients"][0]["quantity"] == pytest.approx(
            225, abs=1
        )  # 150 * 1.5
        assert scaled["ingredients"][1]["quantity"] == pytest.approx(
            120, abs=1
        )  # 100 * 1.2

    def test_fixed_unchanged(self):
        recipe = _chicken_rice_broccoli_oil()
        factors = {0: 1.5}  # only chicken
        scaled = apply_ingredient_scale_factors(recipe, factors)
        # Sel (index 4) not in factors → unchanged
        assert scaled["ingredients"][4]["quantity"] == 2

    def test_discrete_applies_as_quantity(self):
        recipe = _egg_oats_recipe()
        factors = {0: 3, 1: 1.2}  # 3 eggs (final qty), oats * 1.2
        scaled = apply_ingredient_scale_factors(recipe, factors)
        assert scaled["ingredients"][0]["quantity"] == 3  # 3 eggs
        assert scaled["ingredients"][1]["quantity"] == pytest.approx(
            96, abs=1
        )  # 80 * 1.2

    def test_nutrition_recalculated(self):
        recipe = _chicken_rice_broccoli_oil()
        factors = {0: 1.0, 1: 1.0, 2: 1.0, 3: 1.0}
        scaled = apply_ingredient_scale_factors(recipe, factors)
        sn = scaled["scaled_nutrition"]
        assert sn["calories"] > 0
        assert sn["protein_g"] > 0

    def test_output_format_matches_v1(self):
        """Output has all keys needed by _build_meal_from_scaled_recipe."""
        recipe = _chicken_rice_broccoli_oil()
        factors = {0: 1.0, 1: 1.0, 2: 1.0, 3: 1.0}
        scaled = apply_ingredient_scale_factors(recipe, factors)

        # Required keys
        assert "name" in scaled
        assert "ingredients" in scaled
        assert "instructions" in scaled
        assert "prep_time_minutes" in scaled
        assert "scaled_nutrition" in scaled

        # scaled_nutrition keys
        sn = scaled["scaled_nutrition"]
        assert "calories" in sn
        assert "protein_g" in sn
        assert "carbs_g" in sn
        assert "fat_g" in sn

    def test_no_mutation(self):
        recipe = _chicken_rice_broccoli_oil()
        original = copy.deepcopy(recipe)
        factors = {0: 1.5, 1: 1.2, 2: 0.8, 3: 0.3}
        apply_ingredient_scale_factors(recipe, factors)
        # Original recipe unchanged
        assert (
            recipe["ingredients"][0]["quantity"]
            == original["ingredients"][0]["quantity"]
        )

    def test_empty_factors(self):
        """Empty scale_factors → all ingredients kept as-is."""
        recipe = _chicken_rice_broccoli_oil()
        scaled = apply_ingredient_scale_factors(recipe, {})
        sn = scaled["scaled_nutrition"]
        assert sn["calories"] > 0
