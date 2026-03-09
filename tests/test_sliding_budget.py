"""Tests for v2b sliding budget helpers."""

import sys
from pathlib import Path

import pytest

sys.path.insert(
    0,
    str(
        Path(__file__).resolve().parent.parent / "skills" / "meal-planning" / "scripts"
    ),
)

from generate_day_plan import (  # noqa: E402
    _compute_required_ratios,
    _determine_selection_order,
    _recipe_macro_ratios,
)


class TestRecipeMacroRatios:
    def test_balanced_recipe(self):
        recipe = {
            "calories_per_serving": 400,
            "protein_g_per_serving": 25,  # 100 kcal = 25%
            "fat_g_per_serving": 11,  # 99 kcal ~ 25%
            "carbs_g_per_serving": 50,  # 200 kcal = 50%
        }
        ratios = _recipe_macro_ratios(recipe)
        assert ratios["protein_ratio"] == pytest.approx(0.25, abs=0.01)
        assert ratios["fat_ratio"] == pytest.approx(0.25, abs=0.01)

    def test_high_fat_recipe(self):
        recipe = {
            "calories_per_serving": 500,
            "protein_g_per_serving": 20,
            "fat_g_per_serving": 28,  # 252 kcal ~ 50%
            "carbs_g_per_serving": 42,
        }
        assert _recipe_macro_ratios(recipe)["fat_ratio"] > 0.45

    def test_zero_calories_no_crash(self):
        recipe = {
            "calories_per_serving": 0,
            "protein_g_per_serving": 0,
            "fat_g_per_serving": 0,
            "carbs_g_per_serving": 0,
        }
        assert _recipe_macro_ratios(recipe)["protein_ratio"] == 0


class TestComputeRequiredRatios:
    DAILY = {"protein_ratio": 0.25, "fat_ratio": 0.25, "carb_ratio": 0.50}

    def test_no_consumed_returns_daily_target(self):
        result = _compute_required_ratios(self.DAILY, [], [0.33, 0.33, 0.34])
        assert result["protein_ratio"] == pytest.approx(0.25, abs=0.01)

    def test_fatty_meal_lowers_fat_requirement(self):
        consumed = [
            {
                "cal_share": 0.35,
                "recipe_ratios": {
                    "protein_ratio": 0.20,
                    "fat_ratio": 0.40,
                    "carb_ratio": 0.40,
                },
            }
        ]
        result = _compute_required_ratios(self.DAILY, consumed, [0.25, 0.30, 0.10])
        # (0.25 - 0.40×0.35) / 0.65 = 0.169
        assert result["fat_ratio"] == pytest.approx(0.169, abs=0.01)
        # (0.25 - 0.20×0.35) / 0.65 = 0.276
        assert result["protein_ratio"] == pytest.approx(0.276, abs=0.01)

    def test_collation_low_impact(self):
        consumed = [
            {
                "cal_share": 0.10,
                "recipe_ratios": {
                    "protein_ratio": 0.15,
                    "fat_ratio": 0.50,
                    "carb_ratio": 0.35,
                },
            }
        ]
        result = _compute_required_ratios(self.DAILY, consumed, [0.35, 0.30, 0.25])
        # (0.25 - 0.50×0.10) / 0.90 = 0.222 — barely shifted
        assert result["fat_ratio"] == pytest.approx(0.222, abs=0.01)

    def test_main_meal_high_impact(self):
        consumed = [
            {
                "cal_share": 0.35,
                "recipe_ratios": {
                    "protein_ratio": 0.15,
                    "fat_ratio": 0.30,
                    "carb_ratio": 0.55,
                },
            }
        ]
        result = _compute_required_ratios(self.DAILY, consumed, [0.35, 0.20, 0.10])
        # (0.25 - 0.15×0.35) / 0.65 = 0.304
        assert result["protein_ratio"] == pytest.approx(0.304, abs=0.01)

    def test_overshoot_clamped_to_zero(self):
        consumed = [
            {
                "cal_share": 0.60,
                "recipe_ratios": {
                    "protein_ratio": 0.20,
                    "fat_ratio": 0.50,
                    "carb_ratio": 0.30,
                },
            }
        ]
        result = _compute_required_ratios(self.DAILY, consumed, [0.40])
        assert result["fat_ratio"] == 0.0

    def test_two_consumed_meals(self):
        consumed = [
            {
                "cal_share": 0.30,
                "recipe_ratios": {
                    "protein_ratio": 0.20,
                    "fat_ratio": 0.35,
                    "carb_ratio": 0.45,
                },
            },
            {
                "cal_share": 0.35,
                "recipe_ratios": {
                    "protein_ratio": 0.30,
                    "fat_ratio": 0.20,
                    "carb_ratio": 0.50,
                },
            },
        ]
        result = _compute_required_ratios(self.DAILY, consumed, [0.25, 0.10])
        # (0.25 - 0.35×0.30 - 0.20×0.35) / 0.35 = 0.214
        assert result["fat_ratio"] == pytest.approx(0.214, abs=0.01)

    def test_empty_remaining_returns_none(self):
        assert _compute_required_ratios(self.DAILY, [], []) is None

    def test_single_remaining_absorbs_all(self):
        consumed = [
            {
                "cal_share": 0.35,
                "recipe_ratios": {
                    "protein_ratio": 0.20,
                    "fat_ratio": 0.40,
                    "carb_ratio": 0.40,
                },
            },
            {
                "cal_share": 0.35,
                "recipe_ratios": {
                    "protein_ratio": 0.22,
                    "fat_ratio": 0.30,
                    "carb_ratio": 0.48,
                },
            },
        ]
        result = _compute_required_ratios(self.DAILY, consumed, [0.30])
        assert result is not None
        assert result["fat_ratio"] < 0.25


class TestDetermineSelectionOrder:
    def test_fixed_first_then_by_calories(self):
        meals = [
            {"meal_type": "Petit-déjeuner", "target_calories": 500},
            {"meal_type": "Déjeuner", "target_calories": 800},
            {"meal_type": "Dîner", "target_calories": 700},
        ]
        order = _determine_selection_order(meals, {"diner": "burger"}, None)
        assert order[0] == 2  # Dîner first (custom)
        assert order[1] == 1  # Déjeuner (800 kcal)
        assert order[2] == 0  # Petit-déj (500 kcal)

    def test_batch_treated_as_fixed(self):
        meals = [
            {"meal_type": "Petit-déjeuner", "target_calories": 500},
            {"meal_type": "Déjeuner", "target_calories": 800},
        ]
        order = _determine_selection_order(meals, {}, {"petit-dejeuner": "uuid"})
        assert order[0] == 0

    def test_no_fixed_all_by_calories_desc(self):
        meals = [
            {"meal_type": "Collation", "target_calories": 200},
            {"meal_type": "Déjeuner", "target_calories": 800},
            {"meal_type": "Dîner", "target_calories": 700},
        ]
        assert _determine_selection_order(meals, {}, None) == [1, 2, 0]

    def test_collation_last(self):
        meals = [
            {"meal_type": "Collation", "target_calories": 200},
            {"meal_type": "Petit-déjeuner", "target_calories": 500},
            {"meal_type": "Déjeuner", "target_calories": 700},
        ]
        order = _determine_selection_order(meals, {}, None)
        assert order[-1] == 0
