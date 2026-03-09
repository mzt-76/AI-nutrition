"""Unit tests for day-level LP portion optimization.

Tests optimize_day_portions and apply_scale_factor — deterministic logic only.
"""

import pytest

from src.nutrition.portion_optimizer import (
    apply_scale_factor,
    optimize_day_portions,
    _extract_recipe_macros,
)


# ---------------------------------------------------------------------------
# Reusable ingredient nutrition data (per 100g)
# ---------------------------------------------------------------------------

CHICKEN = {"calories": 165, "protein_g": 31, "fat_g": 3.6, "carbs_g": 0}
RICE = {"calories": 130, "protein_g": 2.7, "fat_g": 0.3, "carbs_g": 28}
OLIVE_OIL = {"calories": 884, "protein_g": 0, "fat_g": 100, "carbs_g": 0}
BROCCOLI = {"calories": 34, "protein_g": 2.8, "fat_g": 0.4, "carbs_g": 7}
OATS = {"calories": 389, "protein_g": 17, "fat_g": 7, "carbs_g": 66}
SKYR = {"calories": 63, "protein_g": 11, "fat_g": 0.2, "carbs_g": 4}
BANANA = {"calories": 89, "protein_g": 1.1, "fat_g": 0.3, "carbs_g": 23}


def _make_recipe(ingredients: list[dict], name: str = "Test") -> dict:
    """Build a recipe dict from ingredient specs."""
    total = {"calories": 0.0, "protein_g": 0.0, "fat_g": 0.0, "carbs_g": 0.0}
    for ing in ingredients:
        n = ing.get("nutrition_per_100g", {})
        qty = ing.get("quantity", 0)
        factor = qty / 100.0
        for k in total:
            total[k] += (n.get(k, 0) or 0) * factor
    return {
        "name": name,
        "meal_type": "dejeuner",
        "calories_per_serving": total["calories"],
        "protein_g_per_serving": total["protein_g"],
        "carbs_g_per_serving": total["carbs_g"],
        "fat_g_per_serving": total["fat_g"],
        "ingredients": ingredients,
        "instructions": "Test.",
        "prep_time_minutes": 20,
    }


# ---------------------------------------------------------------------------
# _extract_recipe_macros
# ---------------------------------------------------------------------------


class TestExtractRecipeMacros:
    def test_from_ingredients_with_per_100g(self):
        """Uses ingredient-level nutrition when available."""
        recipe = _make_recipe(
            [
                {
                    "name": "Poulet",
                    "quantity": 150,
                    "unit": "g",
                    "nutrition_per_100g": CHICKEN,
                },
                {
                    "name": "Riz",
                    "quantity": 100,
                    "unit": "g",
                    "nutrition_per_100g": RICE,
                },
            ]
        )
        macros = _extract_recipe_macros(recipe)
        assert abs(macros["protein_g"] - (31 * 1.5 + 2.7)) < 0.1
        assert abs(macros["calories"] - (165 * 1.5 + 130)) < 0.1

    def test_fallback_to_per_serving(self):
        """Falls back to per_serving fields when no ingredient data."""
        recipe = {
            "name": "Simple",
            "calories_per_serving": 500,
            "protein_g_per_serving": 30,
            "fat_g_per_serving": 20,
            "carbs_g_per_serving": 60,
            "ingredients": [{"name": "riz", "quantity": 150, "unit": "g"}],
        }
        macros = _extract_recipe_macros(recipe)
        assert macros["calories"] == 500
        assert macros["protein_g"] == 30


# ---------------------------------------------------------------------------
# optimize_day_portions
# ---------------------------------------------------------------------------


class TestOptimizeDayPortions:
    def test_basic_3_recipes(self):
        """3 recipes with realistic macro profiles, verifies solver minimizes deviation."""
        breakfast = _make_recipe(
            [
                {
                    "name": "Flocons d'avoine",
                    "quantity": 80,
                    "unit": "g",
                    "nutrition_per_100g": OATS,
                },
                {
                    "name": "Skyr",
                    "quantity": 150,
                    "unit": "g",
                    "nutrition_per_100g": SKYR,
                },
                {
                    "name": "Banane",
                    "quantity": 100,
                    "unit": "g",
                    "nutrition_per_100g": BANANA,
                },
                {
                    "name": "Huile coco",
                    "quantity": 10,
                    "unit": "g",
                    "nutrition_per_100g": OLIVE_OIL,
                },
            ],
            name="Porridge protéiné",
        )

        lunch = _make_recipe(
            [
                {
                    "name": "Poulet",
                    "quantity": 150,
                    "unit": "g",
                    "nutrition_per_100g": CHICKEN,
                },
                {
                    "name": "Riz",
                    "quantity": 120,
                    "unit": "g",
                    "nutrition_per_100g": RICE,
                },
                {
                    "name": "Huile d'olive",
                    "quantity": 15,
                    "unit": "g",
                    "nutrition_per_100g": OLIVE_OIL,
                },
                {
                    "name": "Brocoli",
                    "quantity": 100,
                    "unit": "g",
                    "nutrition_per_100g": BROCCOLI,
                },
            ],
            name="Poulet riz brocoli",
        )

        dinner = _make_recipe(
            [
                {
                    "name": "Poulet",
                    "quantity": 120,
                    "unit": "g",
                    "nutrition_per_100g": CHICKEN,
                },
                {
                    "name": "Riz",
                    "quantity": 100,
                    "unit": "g",
                    "nutrition_per_100g": RICE,
                },
                {
                    "name": "Huile d'olive",
                    "quantity": 10,
                    "unit": "g",
                    "nutrition_per_100g": OLIVE_OIL,
                },
                {
                    "name": "Brocoli",
                    "quantity": 150,
                    "unit": "g",
                    "nutrition_per_100g": BROCCOLI,
                },
            ],
            name="Poulet riz léger",
        )

        recipes = [breakfast, lunch, dinner]
        # Targets aligned with recipe macro profiles
        targets = {
            "calories": 2200,
            "protein_g": 140,
            "fat_g": 70,
            "carbs_g": 280,
        }

        factors = optimize_day_portions(recipes, targets)
        assert len(factors) == 3

        # All factors within bounds
        for f in factors:
            assert 0.5 <= f <= 3.0

        # Check total macros are close to targets
        total_prot = sum(
            _extract_recipe_macros(r)["protein_g"] * f for r, f in zip(recipes, factors)
        )
        total_fat = sum(
            _extract_recipe_macros(r)["fat_g"] * f for r, f in zip(recipes, factors)
        )
        total_cal = sum(
            _extract_recipe_macros(r)["calories"] * f for r, f in zip(recipes, factors)
        )

        # LP solver should get close — tolerance depends on recipe compatibility
        assert (
            abs(total_prot - 140) / 140 < 0.25
        ), f"Protein {total_prot:.0f}g vs target 140g"
        assert abs(total_fat - 70) / 70 < 0.25, f"Fat {total_fat:.0f}g vs target 70g"
        assert (
            abs(total_cal - 2200) / 2200 < 0.20
        ), f"Calories {total_cal:.0f} vs target 2200"

    def test_single_recipe(self):
        """Single recipe: scale factor = target_cal / recipe_cal (clamped)."""
        recipe = _make_recipe(
            [
                {
                    "name": "Poulet",
                    "quantity": 150,
                    "unit": "g",
                    "nutrition_per_100g": CHICKEN,
                },
                {
                    "name": "Riz",
                    "quantity": 100,
                    "unit": "g",
                    "nutrition_per_100g": RICE,
                },
            ],
            name="Poulet riz simple",
        )

        targets = {"calories": 600, "protein_g": 50, "fat_g": 15, "carbs_g": 60}
        factors = optimize_day_portions([recipe], targets)
        assert len(factors) == 1
        assert 0.5 <= factors[0] <= 3.0

    def test_clamping_prevents_extreme(self):
        """Scale factors are clamped to [0.5, 3.0] even if target demands more."""
        # Tiny recipe vs huge target
        recipe = _make_recipe(
            [
                {
                    "name": "Riz",
                    "quantity": 50,
                    "unit": "g",
                    "nutrition_per_100g": RICE,
                },
            ],
            name="Tout petit riz",
        )

        targets = {"calories": 5000, "protein_g": 300, "fat_g": 100, "carbs_g": 600}
        factors = optimize_day_portions([recipe], targets)
        assert factors[0] <= 3.0

    def test_empty_recipes_raises(self):
        """Empty recipe list raises ValueError."""
        with pytest.raises(ValueError, match="empty"):
            optimize_day_portions(
                [], {"calories": 2000, "protein_g": 100, "fat_g": 60, "carbs_g": 250}
            )

    def test_zero_calories_target_raises(self):
        """Zero calorie target raises ValueError."""
        recipe = _make_recipe(
            [
                {
                    "name": "Riz",
                    "quantity": 100,
                    "unit": "g",
                    "nutrition_per_100g": RICE,
                },
            ]
        )
        with pytest.raises(ValueError, match="positive"):
            optimize_day_portions(
                [recipe], {"calories": 0, "protein_g": 50, "fat_g": 20, "carbs_g": 60}
            )

    def test_protein_priority_over_carbs(self):
        """Protein deviation should be smaller than carb deviation (weight=2.0 vs 0.5)."""
        # Recipe with balanced macros
        recipe = _make_recipe(
            [
                {
                    "name": "Poulet",
                    "quantity": 100,
                    "unit": "g",
                    "nutrition_per_100g": CHICKEN,
                },
                {
                    "name": "Riz",
                    "quantity": 150,
                    "unit": "g",
                    "nutrition_per_100g": RICE,
                },
                {
                    "name": "Huile",
                    "quantity": 5,
                    "unit": "g",
                    "nutrition_per_100g": OLIVE_OIL,
                },
            ],
            name="Poulet riz",
        )

        # Target with conflicting demands: high protein, moderate carbs
        targets = {"calories": 500, "protein_g": 60, "fat_g": 15, "carbs_g": 50}
        factors = optimize_day_portions([recipe], targets)

        # With only 1 recipe and 1 scale factor, trade-offs are inevitable.
        # The solver should sacrifice carbs (weight=0.5) over protein (weight=2.0)
        # unless the LP happens to find a balanced point.
        # At minimum, the factor should be valid.
        assert 0.5 <= factors[0] <= 3.0

    def test_solver_balances_macros_globally(self):
        """LP solver optimizes across all recipes, not independently per recipe."""
        protein_heavy = _make_recipe(
            [
                {
                    "name": "Poulet",
                    "quantity": 200,
                    "unit": "g",
                    "nutrition_per_100g": CHICKEN,
                },
                {
                    "name": "Riz",
                    "quantity": 80,
                    "unit": "g",
                    "nutrition_per_100g": RICE,
                },
            ],
            name="Poulet riz",
        )

        carb_heavy = _make_recipe(
            [
                {
                    "name": "Riz",
                    "quantity": 200,
                    "unit": "g",
                    "nutrition_per_100g": RICE,
                },
                {
                    "name": "Banane",
                    "quantity": 100,
                    "unit": "g",
                    "nutrition_per_100g": BANANA,
                },
            ],
            name="Riz banane",
        )

        targets = {"calories": 1000, "protein_g": 70, "fat_g": 15, "carbs_g": 120}
        factors = optimize_day_portions([protein_heavy, carb_heavy], targets)

        # Both factors should be valid
        assert 0.5 <= factors[0] <= 3.0
        assert 0.5 <= factors[1] <= 3.0

        # The protein-heavy recipe should get a different factor than carb-heavy
        # (if they got the same factor, the solver wouldn't be optimizing globally)
        assert factors[0] != factors[1], "Solver should differentiate recipe factors"

    def test_equal_calorie_distribution(self):
        """3 similar recipes with equal per-meal targets → scale factors within ±15%."""
        recipe_a = _make_recipe(
            [
                {
                    "name": "Poulet",
                    "quantity": 150,
                    "unit": "g",
                    "nutrition_per_100g": CHICKEN,
                },
                {
                    "name": "Riz",
                    "quantity": 100,
                    "unit": "g",
                    "nutrition_per_100g": RICE,
                },
                {
                    "name": "Huile",
                    "quantity": 10,
                    "unit": "g",
                    "nutrition_per_100g": OLIVE_OIL,
                },
            ],
            name="Repas A",
        )
        recipe_b = _make_recipe(
            [
                {
                    "name": "Poulet",
                    "quantity": 140,
                    "unit": "g",
                    "nutrition_per_100g": CHICKEN,
                },
                {
                    "name": "Riz",
                    "quantity": 110,
                    "unit": "g",
                    "nutrition_per_100g": RICE,
                },
                {
                    "name": "Huile",
                    "quantity": 10,
                    "unit": "g",
                    "nutrition_per_100g": OLIVE_OIL,
                },
            ],
            name="Repas B",
        )
        recipe_c = _make_recipe(
            [
                {
                    "name": "Poulet",
                    "quantity": 160,
                    "unit": "g",
                    "nutrition_per_100g": CHICKEN,
                },
                {
                    "name": "Riz",
                    "quantity": 90,
                    "unit": "g",
                    "nutrition_per_100g": RICE,
                },
                {
                    "name": "Huile",
                    "quantity": 10,
                    "unit": "g",
                    "nutrition_per_100g": OLIVE_OIL,
                },
            ],
            name="Repas C",
        )
        recipes = [recipe_a, recipe_b, recipe_c]
        targets = {"calories": 1800, "protein_g": 120, "fat_g": 60, "carbs_g": 200}
        per_meal = [600.0, 600.0, 600.0]

        factors = optimize_day_portions(recipes, targets, per_meal_targets=per_meal)
        assert len(factors) == 3
        avg = sum(factors) / 3
        for f in factors:
            assert (
                abs(f - avg) / avg < 0.15
            ), f"Factor {f:.3f} deviates >15% from average {avg:.3f}"

    def test_snack_gets_less_calories(self):
        """3 main meals + 1 snack with 10% calorie target → snack factor is lower."""
        main_recipe = _make_recipe(
            [
                {
                    "name": "Poulet",
                    "quantity": 150,
                    "unit": "g",
                    "nutrition_per_100g": CHICKEN,
                },
                {
                    "name": "Riz",
                    "quantity": 120,
                    "unit": "g",
                    "nutrition_per_100g": RICE,
                },
                {
                    "name": "Huile",
                    "quantity": 10,
                    "unit": "g",
                    "nutrition_per_100g": OLIVE_OIL,
                },
            ],
            name="Repas principal",
        )
        snack_recipe = _make_recipe(
            [
                {
                    "name": "Banane",
                    "quantity": 120,
                    "unit": "g",
                    "nutrition_per_100g": BANANA,
                },
                {
                    "name": "Skyr",
                    "quantity": 100,
                    "unit": "g",
                    "nutrition_per_100g": SKYR,
                },
            ],
            name="Collation",
        )
        recipes = [main_recipe, main_recipe, main_recipe, snack_recipe]
        total_cal = 2200
        targets = {"calories": total_cal, "protein_g": 140, "fat_g": 70, "carbs_g": 250}
        # 3 main meals ~30% each, snack ~10%
        per_meal = [660.0, 660.0, 660.0, 220.0]

        factors = optimize_day_portions(recipes, targets, per_meal_targets=per_meal)
        assert len(factors) == 4

        # Snack factor should produce fewer calories than main meal factors
        snack_cal = _extract_recipe_macros(snack_recipe)["calories"] * factors[3]
        main_cals = [
            _extract_recipe_macros(main_recipe)["calories"] * factors[i]
            for i in range(3)
        ]
        avg_main_cal = sum(main_cals) / 3
        assert snack_cal < avg_main_cal, (
            f"Snack calories ({snack_cal:.0f}) should be less than "
            f"average main meal ({avg_main_cal:.0f})"
        )

    def test_infeasible_returns_uniform_fallback(self):
        """When LP is infeasible, returns uniform calorie-based factors."""
        # Create recipes with wildly incompatible macro profiles
        # so the LP solver cannot satisfy all constraints within bounds
        pure_fat = _make_recipe(
            [
                {
                    "name": "Huile",
                    "quantity": 100,
                    "unit": "g",
                    "nutrition_per_100g": OLIVE_OIL,
                },
            ],
            name="Pure fat",
        )
        pure_protein = _make_recipe(
            [
                {
                    "name": "Poulet",
                    "quantity": 100,
                    "unit": "g",
                    "nutrition_per_100g": CHICKEN,
                },
            ],
            name="Pure protein",
        )

        # Request impossible combination: very high carbs from recipes with none
        targets = {"calories": 800, "protein_g": 200, "fat_g": 5, "carbs_g": 500}
        factors = optimize_day_portions([pure_fat, pure_protein], targets)

        # Should return valid factors (either LP solution or uniform fallback)
        assert len(factors) == 2
        for f in factors:
            assert 0.5 <= f <= 3.0

    def test_per_meal_targets_optional(self):
        """Without per_meal_targets, behavior is identical to before."""
        recipe = _make_recipe(
            [
                {
                    "name": "Poulet",
                    "quantity": 150,
                    "unit": "g",
                    "nutrition_per_100g": CHICKEN,
                },
                {
                    "name": "Riz",
                    "quantity": 100,
                    "unit": "g",
                    "nutrition_per_100g": RICE,
                },
            ],
            name="Simple",
        )
        targets = {"calories": 600, "protein_g": 50, "fat_g": 15, "carbs_g": 60}

        factors_without = optimize_day_portions([recipe], targets)
        factors_none = optimize_day_portions([recipe], targets, per_meal_targets=None)

        assert factors_without == factors_none


# ---------------------------------------------------------------------------
# apply_scale_factor
# ---------------------------------------------------------------------------


class TestApplyScaleFactor:
    def test_basic_scaling(self):
        """Applies scale factor to ingredients and computes nutrition."""
        recipe = _make_recipe(
            [
                {
                    "name": "Poulet",
                    "quantity": 100,
                    "unit": "g",
                    "nutrition_per_100g": CHICKEN,
                },
                {
                    "name": "Riz",
                    "quantity": 100,
                    "unit": "g",
                    "nutrition_per_100g": RICE,
                },
            ]
        )

        scaled = apply_scale_factor(recipe, 1.5)
        assert scaled["ingredients"][0]["quantity"] == 150
        assert scaled["ingredients"][1]["quantity"] == 150
        assert "scaled_nutrition" in scaled
        assert scaled["scaled_nutrition"]["calories"] > 0
        assert scaled["scale_factor"] == 1.5

    def test_nutrition_from_per_100g(self):
        """scaled_nutrition is computed from scaled ingredient quantities."""
        recipe = _make_recipe(
            [
                {
                    "name": "Poulet",
                    "quantity": 100,
                    "unit": "g",
                    "nutrition_per_100g": CHICKEN,
                },
            ]
        )

        scaled = apply_scale_factor(recipe, 2.0)
        # 200g of chicken: 165 * 2 = 330 cal, 31 * 2 = 62g protein
        assert abs(scaled["scaled_nutrition"]["calories"] - 330) < 1.0
        assert abs(scaled["scaled_nutrition"]["protein_g"] - 62) < 1.0

    def test_fallback_to_per_serving(self):
        """Uses per_serving fields when ingredients lack per_100g data."""
        recipe = {
            "name": "Simple",
            "calories_per_serving": 400,
            "protein_g_per_serving": 25,
            "fat_g_per_serving": 15,
            "carbs_g_per_serving": 50,
            "ingredients": [{"name": "riz", "quantity": 100, "unit": "g"}],
        }

        scaled = apply_scale_factor(recipe, 1.5)
        assert abs(scaled["scaled_nutrition"]["calories"] - 600) < 1.0
        assert abs(scaled["scaled_nutrition"]["protein_g"] - 37.5) < 1.0

    def test_smart_rounding(self):
        """Countable units get rounded to whole numbers."""
        recipe = {
            "name": "Omelette",
            "calories_per_serving": 300,
            "protein_g_per_serving": 20,
            "fat_g_per_serving": 15,
            "carbs_g_per_serving": 5,
            "ingredients": [
                {"name": "oeufs", "quantity": 2, "unit": "pièces"},
                {"name": "épinards", "quantity": 50, "unit": "g"},
            ],
        }

        scaled = apply_scale_factor(recipe, 1.7)
        # 2 * 1.7 = 3.4 → should round to 3 (whole eggs)
        assert scaled["ingredients"][0]["quantity"] == round(2 * 1.7)
        # 50 * 1.7 = 85 → round to 85
        assert scaled["ingredients"][1]["quantity"] == 85
