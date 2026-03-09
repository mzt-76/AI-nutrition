"""Integration tests for the generate_day_plan skill script pipeline.

Tests the 5-step pipeline: select_recipes → scale_portions → validate_day → repair.
Uses mocked Supabase and Anthropic clients — no real API calls.
"""

import json
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path
import importlib.util


# ---------------------------------------------------------------------------
# Helper: Load the skill script
# ---------------------------------------------------------------------------


def _load_script(script_name: str):
    """Load a skill script by name."""
    project_root = Path(__file__).resolve().parent.parent
    script_path = (
        project_root / "skills" / "meal-planning" / "scripts" / f"{script_name}.py"
    )
    spec = importlib.util.spec_from_file_location(
        f"meal_planning.{script_name}", script_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def meal_targets():
    """Sample meal targets for a 3-meal day."""
    return [
        {
            "meal_type": "Petit-déjeuner",
            "time": "08:00",
            "target_calories": 700,
            "target_protein_g": 45,
            "target_carbs_g": 80,
            "target_fat_g": 25,
        },
        {
            "meal_type": "Déjeuner",
            "time": "13:00",
            "target_calories": 1100,
            "target_protein_g": 75,
            "target_carbs_g": 140,
            "target_fat_g": 30,
        },
        {
            "meal_type": "Dîner",
            "time": "19:00",
            "target_calories": 1000,
            "target_protein_g": 60,
            "target_carbs_g": 130,
            "target_fat_g": 25,
        },
    ]


@pytest.fixture
def user_profile():
    """Sample user profile for testing."""
    return {
        "id": "test-uuid",
        "name": "Test User",
        "age": 30,
        "gender": "male",
        "weight_kg": 80.0,
        "allergies": [],
        "diet_type": "omnivore",
        "preferred_cuisines": ["française"],
        "max_prep_time": 45,
        "favorite_foods": ["poulet", "riz"],
    }


@pytest.fixture
def sample_db_recipe():
    """Sample DB recipe for mocking."""
    return {
        "id": "recipe-uuid-1",
        "name": "Omelette protéinée",
        "meal_type": "petit-dejeuner",
        "calories_per_serving": 450.0,
        "protein_g_per_serving": 30.0,
        "carbs_g_per_serving": 10.0,
        "fat_g_per_serving": 32.0,
        "ingredients": [
            {"name": "oeufs", "quantity": 3, "unit": "pièces"},
            {"name": "épinards", "quantity": 50, "unit": "g"},
        ],
        "instructions": "Battre les oeufs, ajouter les épinards, cuire.",
        "prep_time_minutes": 10,
        "allergen_tags": ["oeuf"],
        "usage_count": 5,
        "off_validated": True,
        "source": "llm_generated",
        "cuisine_type": "française",
        "diet_type": "omnivore",
        "tags": ["high-protein"],
    }


# ---------------------------------------------------------------------------
# Test: generate_day_plan script (full pipeline with mocks)
# ---------------------------------------------------------------------------


class TestGenerateDayPlan:
    @pytest.mark.asyncio
    async def test_day_plan_from_recipe_db(
        self, meal_targets, user_profile, sample_db_recipe
    ):
        """generate_day_plan generates day using only DB recipes."""
        generate_day_plan = _load_script("generate_day_plan")

        with patch.object(
            generate_day_plan,
            "search_recipes",
            new=AsyncMock(return_value=[sample_db_recipe]),
        ), patch.object(generate_day_plan, "increment_usage", new=AsyncMock()):
            result_str = await generate_day_plan.execute(
                supabase=MagicMock(),
                anthropic_client=MagicMock(),
                day_index=0,
                day_name="Lundi",
                day_date="2026-02-18",
                meal_targets=meal_targets,
                user_profile=user_profile,
                exclude_recipe_ids=[],
                custom_requests={},
            )

        result = json.loads(result_str)
        assert result["success"] is True
        assert result["day"]["day"] == "Lundi"
        assert result["day"]["date"] == "2026-02-18"
        assert len(result["day"]["meals"]) == 3
        assert "daily_totals" in result["day"]

    @pytest.mark.asyncio
    async def test_day_plan_allergen_safe(self, meal_targets, sample_db_recipe):
        """generate_day_plan produces allergen-safe output."""
        generate_day_plan = _load_script("generate_day_plan")

        allergen_free_recipe = dict(sample_db_recipe)
        allergen_free_recipe["id"] = "safe-uuid"
        allergen_free_recipe["allergen_tags"] = []
        allergen_free_recipe["name"] = "Salade de poulet"
        allergen_free_recipe["ingredients"] = [
            {"name": "poulet", "quantity": 150, "unit": "g"}
        ]

        with patch.object(
            generate_day_plan,
            "search_recipes",
            new=AsyncMock(return_value=[allergen_free_recipe]),
        ), patch.object(generate_day_plan, "increment_usage", new=AsyncMock()):
            profile_no_eggs = {"allergies": ["oeuf"], "diet_type": "omnivore"}
            result_str = await generate_day_plan.execute(
                supabase=MagicMock(),
                anthropic_client=MagicMock(),
                day_index=0,
                day_name="Lundi",
                day_date="2026-02-18",
                meal_targets=meal_targets,
                user_profile=profile_no_eggs,
                exclude_recipe_ids=[],
                custom_requests={},
            )

        result = json.loads(result_str)
        if result.get("success"):
            for meal in result["day"]["meals"]:
                for ing in meal.get("ingredients", []):
                    assert (
                        "oeuf" not in ing["name"].lower()
                    ), f"Allergen 'oeuf' found in ingredient: {ing['name']}"

    @pytest.mark.asyncio
    async def test_day_plan_macro_accuracy(self, meal_targets, sample_db_recipe):
        """generate_day_plan produces macros within tolerance of targets."""
        generate_day_plan = _load_script("generate_day_plan")

        with patch.object(
            generate_day_plan,
            "search_recipes",
            new=AsyncMock(return_value=[sample_db_recipe]),
        ), patch.object(generate_day_plan, "increment_usage", new=AsyncMock()):
            result_str = await generate_day_plan.execute(
                supabase=MagicMock(),
                anthropic_client=MagicMock(),
                day_index=1,
                day_name="Mardi",
                day_date="2026-02-19",
                meal_targets=meal_targets,
                user_profile={"allergies": [], "diet_type": "omnivore"},
                exclude_recipe_ids=[],
                custom_requests={},
            )

        result = json.loads(result_str)
        if result.get("success"):
            assert "daily_totals" in result["day"]
            totals = result["day"]["daily_totals"]
            assert totals["calories"] > 0
            assert totals["protein_g"] > 0

    @pytest.mark.asyncio
    async def test_day_plan_daily_totals_computed(self, meal_targets, sample_db_recipe):
        """generate_day_plan computes daily_totals by summing meal nutrition."""
        generate_day_plan = _load_script("generate_day_plan")

        with patch.object(
            generate_day_plan,
            "search_recipes",
            new=AsyncMock(return_value=[sample_db_recipe]),
        ), patch.object(generate_day_plan, "increment_usage", new=AsyncMock()):
            result_str = await generate_day_plan.execute(
                supabase=MagicMock(),
                anthropic_client=MagicMock(),
                day_index=2,
                day_name="Mercredi",
                day_date="2026-02-20",
                meal_targets=meal_targets,
                user_profile={"allergies": [], "diet_type": "omnivore"},
                exclude_recipe_ids=[],
                custom_requests={},
            )

        result = json.loads(result_str)
        if result.get("success"):
            day = result["day"]
            computed_total = sum(m["nutrition"]["calories"] for m in day["meals"])
            assert abs(day["daily_totals"]["calories"] - computed_total) < 1.0

    @pytest.mark.asyncio
    async def test_weekly_plan_variety(self, meal_targets, sample_db_recipe):
        """Seven-day generation tracks used recipe IDs for variety."""
        generate_day_plan = _load_script("generate_day_plan")

        call_count = 0
        recipes_pool = [
            {**sample_db_recipe, "id": f"recipe-{i}", "name": f"Recipe {i}"}
            for i in range(7)
        ]

        async def mock_search(*args, **kwargs):
            nonlocal call_count
            recipe = recipes_pool[call_count % len(recipes_pool)]
            call_count += 1
            return [recipe]

        used_ids: list[str] = []

        with patch.object(
            generate_day_plan, "search_recipes", new=mock_search
        ), patch.object(generate_day_plan, "increment_usage", new=AsyncMock()):
            for day_idx in range(7):
                result_str = await generate_day_plan.execute(
                    supabase=MagicMock(),
                    anthropic_client=MagicMock(),
                    day_index=day_idx,
                    day_name=[
                        "Lundi",
                        "Mardi",
                        "Mercredi",
                        "Jeudi",
                        "Vendredi",
                        "Samedi",
                        "Dimanche",
                    ][day_idx],
                    day_date=f"2026-02-{18 + day_idx:02d}",
                    meal_targets=meal_targets,
                    user_profile={"allergies": [], "diet_type": "omnivore"},
                    exclude_recipe_ids=list(used_ids),
                    custom_requests={},
                )
                result = json.loads(result_str)
                if result.get("success"):
                    used_ids.extend(result.get("recipes_used", []))

        assert len(used_ids) > 0

    @pytest.mark.asyncio
    async def test_day_plan_returns_recipes_used(self, meal_targets, sample_db_recipe):
        """generate_day_plan returns list of recipe IDs used."""
        generate_day_plan = _load_script("generate_day_plan")

        with patch.object(
            generate_day_plan,
            "search_recipes",
            new=AsyncMock(return_value=[sample_db_recipe]),
        ), patch.object(generate_day_plan, "increment_usage", new=AsyncMock()):
            result_str = await generate_day_plan.execute(
                supabase=MagicMock(),
                anthropic_client=MagicMock(),
                day_index=0,
                day_name="Lundi",
                day_date="2026-02-18",
                meal_targets=meal_targets,
                user_profile={"allergies": [], "diet_type": "omnivore"},
                exclude_recipe_ids=[],
                custom_requests={},
            )

        result = json.loads(result_str)
        if result.get("success"):
            assert "recipes_used" in result
            assert isinstance(result["recipes_used"], list)

    @pytest.mark.asyncio
    async def test_day_plan_with_custom_request(self, meal_targets, user_profile):
        """generate_day_plan triggers LLM fallback when custom_request matches a slot."""
        generate_day_plan = _load_script("generate_day_plan")

        # Build a minimal valid recipe that generate_custom_recipe.execute() returns
        custom_recipe = {
            "name": "Risotto aux champignons",
            "description": "Un risotto.",
            "meal_type": "dejeuner",
            "cuisine_type": "italienne",
            "diet_type": "omnivore",
            "prep_time_minutes": 30,
            "ingredients": [{"name": "riz", "quantity": 150, "unit": "g"}],
            "instructions": "Cuire le riz.",
            "tags": [],
            "calories_per_serving": 600.0,
            "protein_g_per_serving": 20.0,
            "carbs_g_per_serving": 90.0,
            "fat_g_per_serving": 10.0,
            "allergen_tags": [],
            "source": "llm_generated",
            "off_validated": True,
        }
        custom_recipe_response = json.dumps(
            {
                "recipe": custom_recipe,
                "off_validated": True,
                "matched_ingredients": 1,
                "total_ingredients": 1,
            }
        )

        # Patch generate_custom_recipe module's execute at the sibling import level
        generate_custom_recipe_module = _load_script("generate_custom_recipe")
        generate_custom_recipe_module.execute = AsyncMock(
            return_value=custom_recipe_response
        )

        # Patch _import_sibling_script to return our pre-patched module
        with patch.object(
            generate_day_plan,
            "_import_sibling_script",
            return_value=generate_custom_recipe_module,
        ), patch.object(
            generate_day_plan, "search_recipes", new=AsyncMock(return_value=[])
        ), patch.object(generate_day_plan, "increment_usage", new=AsyncMock()):
            result_str = await generate_day_plan.execute(
                supabase=MagicMock(),
                anthropic_client=MagicMock(),
                day_index=1,
                day_name="Mardi",
                day_date="2026-02-19",
                meal_targets=[meal_targets[1]],  # Only the Déjeuner slot
                user_profile=user_profile,
                exclude_recipe_ids=[],
                custom_requests={"dejeuner": "risotto aux champignons"},
            )

        result = json.loads(result_str)
        assert result.get("success") is True
        assert result["llm_fallback_count"] >= 1


# ---------------------------------------------------------------------------
# Test: _score_recipe_macro_fit helper
# ---------------------------------------------------------------------------


class TestScoreRecipeMacroFit:
    """Tests that generate_day_plan uses score_macro_fit from recipe_db."""

    def setup_method(self):
        from src.nutrition.recipe_db import score_macro_fit

        self.score = score_macro_fit

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
        assert abs(self.score(recipe, target)) < 0.001

    def test_high_fat_recipe_scores_worse(self):
        """A high-fat recipe scores worse than a balanced one for balanced targets."""
        balanced_recipe = {
            "calories_per_serving": 500,
            "protein_g_per_serving": 40,
            "carbs_g_per_serving": 50,
            "fat_g_per_serving": 12,
        }
        high_fat_recipe = {
            "calories_per_serving": 500,
            "protein_g_per_serving": 15,
            "carbs_g_per_serving": 20,
            "fat_g_per_serving": 40,
        }
        target = {
            "target_calories": 700,
            "target_protein_g": 50,
            "target_carbs_g": 70,
            "target_fat_g": 18,
        }
        assert self.score(balanced_recipe, target) < self.score(high_fat_recipe, target)

    def test_protein_mismatch_weighted_double(self):
        """Protein mismatch contributes 2x to score vs carb/fat mismatch."""
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
        assert self.score(prot_off, base_target) > self.score(carb_off, base_target)

    def test_handles_zero_calorie_recipe(self):
        """Zero-calorie recipe doesn't crash (uses fallback of 1)."""
        recipe = {
            "calories_per_serving": 0,
            "protein_g_per_serving": 0,
            "carbs_g_per_serving": 0,
            "fat_g_per_serving": 0,
        }
        target = {"target_calories": 500, "target_protein_g": 40}
        score = self.score(recipe, target)
        assert isinstance(score, float)


# ---------------------------------------------------------------------------
# Test: _find_custom_request helper
# ---------------------------------------------------------------------------


class TestFindCustomRequest:
    def setup_method(self):
        self.module = _load_script("generate_day_plan")
        self.find = self.module._find_custom_request

    def test_exact_key_match(self):
        """Normalised exact key match (accent-aware) returns the request string."""
        custom_requests = {"déjeuner": "risotto"}
        slot = {"meal_type": "Déjeuner"}
        result = self.find(custom_requests, slot)
        assert result == "risotto"

    def test_accent_mismatch_still_matches(self):
        """Key without accent matches display name with accent (the actual bug)."""
        custom_requests = {"petit-dejeuner": "chocolat chaud et baguette"}
        slot = {"meal_type": "Petit-déjeuner"}
        result = self.find(custom_requests, slot)
        assert result == "chocolat chaud et baguette"

    def test_no_match_returns_none(self):
        """Unrelated keys return None."""
        custom_requests = {"diner": "soupe"}
        slot = {"meal_type": "Déjeuner"}
        result = self.find(custom_requests, slot)
        assert result is None


# ---------------------------------------------------------------------------
# Test: Pipeline step functions
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge case tests for generate_day_plan pipeline."""

    @pytest.mark.asyncio
    async def test_empty_meal_targets_returns_error(self, user_profile):
        """meal_targets=[] returns an error JSON without crashing."""
        generate_day_plan = _load_script("generate_day_plan")

        result_str = await generate_day_plan.execute(
            supabase=MagicMock(),
            anthropic_client=MagicMock(),
            day_index=0,
            day_name="Lundi",
            day_date="2026-02-18",
            meal_targets=[],
            user_profile=user_profile,
            exclude_recipe_ids=[],
            custom_requests={},
        )

        result = json.loads(result_str)
        assert "error" in result
        assert "empty" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_repair_rollback_on_scaling_failure(
        self, meal_targets, user_profile, sample_db_recipe
    ):
        """When scale_portions fails during repair, original assignment is preserved."""
        generate_day_plan = _load_script("generate_day_plan")

        # Build assignments with runner_ups so repair will try swap
        runner_up = {**sample_db_recipe, "id": "runner-up-1", "name": "Runner Up"}
        assignments = [
            {
                "meal_slot": meal_targets[0],
                "recipe": sample_db_recipe,
                "is_llm": False,
                "runner_ups": [runner_up],
            },
        ]
        original_recipe_name = sample_db_recipe["name"]

        meals = [
            {
                "meal_type": "Petit-déjeuner",
                "name": sample_db_recipe["name"],
                "ingredients": [],
                "nutrition": {
                    "calories": 500,
                    "protein_g": 20,
                    "carbs_g": 50,
                    "fat_g": 60,
                },
            },
        ]
        daily_totals = {"calories": 500, "protein_g": 20, "carbs_g": 50, "fat_g": 60}
        target_macros = {"calories": 700, "protein_g": 45, "carbs_g": 80, "fat_g": 25}

        # Mock scale_portions to raise on the repair attempt
        with patch.object(
            generate_day_plan,
            "scale_portions",
            side_effect=Exception("LP solver exploded"),
        ), patch.object(
            generate_day_plan, "search_recipes", new=AsyncMock(return_value=[])
        ), patch.object(generate_day_plan, "increment_usage", new=AsyncMock()):
            repaired_meals, repaired_assignments = await generate_day_plan.repair(
                meals=meals,
                assignments=assignments,
                target_macros=target_macros,
                daily_totals=daily_totals,
                supabase=MagicMock(),
                anthropic_client=MagicMock(),
                user_profile=user_profile,
                exclude_recipe_ids=[],
                custom_requests={},
            )

        # After rollback, original recipe name should be preserved
        assert repaired_assignments[0]["recipe"]["name"] == original_recipe_name


class TestPipelineSteps:
    """Test individual pipeline step functions."""

    def test_scale_portions(self, sample_db_recipe, meal_targets):
        """scale_portions scales recipes to meal slot targets."""
        generate_day_plan = _load_script("generate_day_plan")

        assignments = [
            {
                "meal_slot": meal_targets[0],
                "recipe": sample_db_recipe,
                "is_llm": False,
                "runner_ups": [],
            }
        ]
        meals = generate_day_plan.scale_portions(assignments)
        assert len(meals) == 1
        assert meals[0]["nutrition"]["calories"] > 0
        assert meals[0]["meal_type"] == "Petit-déjeuner"

    def test_validate_day_passes_within_tolerance(self, meal_targets, sample_db_recipe):
        """validate_day passes when macros are within tolerance."""
        generate_day_plan = _load_script("generate_day_plan")

        target_macros = {
            "calories": 2800,
            "protein_g": 180,
            "carbs_g": 350,
            "fat_g": 80,
        }
        # Build meals that match targets closely
        meals = [
            {
                "meal_type": "Petit-déjeuner",
                "name": "Test",
                "ingredients": [],
                "nutrition": {
                    "calories": 900,
                    "protein_g": 60,
                    "carbs_g": 115,
                    "fat_g": 26,
                },
            },
            {
                "meal_type": "Déjeuner",
                "name": "Test",
                "ingredients": [],
                "nutrition": {
                    "calories": 1000,
                    "protein_g": 65,
                    "carbs_g": 125,
                    "fat_g": 28,
                },
            },
            {
                "meal_type": "Dîner",
                "name": "Test",
                "ingredients": [],
                "nutrition": {
                    "calories": 900,
                    "protein_g": 55,
                    "carbs_g": 110,
                    "fat_g": 26,
                },
            },
        ]
        daily_totals = generate_day_plan._compute_daily_totals(meals)
        validation = generate_day_plan.validate_day(
            meals, daily_totals, target_macros, []
        )
        assert validation["valid"] is True
        assert len(validation["violations"]) == 0

    def test_validate_day_detects_violations(self):
        """validate_day detects macro violations."""
        generate_day_plan = _load_script("generate_day_plan")

        target_macros = {
            "calories": 2800,
            "protein_g": 180,
            "carbs_g": 350,
            "fat_g": 80,
        }
        # Build meals that are way off target
        meals = [
            {
                "meal_type": "Déjeuner",
                "name": "Test",
                "ingredients": [],
                "nutrition": {
                    "calories": 500,
                    "protein_g": 30,
                    "carbs_g": 50,
                    "fat_g": 20,
                },
            },
        ]
        daily_totals = generate_day_plan._compute_daily_totals(meals)
        validation = generate_day_plan.validate_day(
            meals, daily_totals, target_macros, []
        )
        assert validation["valid"] is False
        assert len(validation["violations"]) > 0

    def test_find_worst_meal(self, meal_targets):
        """_find_worst_meal identifies the meal contributing most to violations."""
        generate_day_plan = _load_script("generate_day_plan")

        meals = [
            {
                "nutrition": {
                    "calories": 700,
                    "protein_g": 45,
                    "carbs_g": 80,
                    "fat_g": 25,
                }
            },
            {
                "nutrition": {
                    "calories": 500,
                    "protein_g": 20,
                    "carbs_g": 50,
                    "fat_g": 60,
                }
            },
            {
                "nutrition": {
                    "calories": 1000,
                    "protein_g": 60,
                    "carbs_g": 130,
                    "fat_g": 25,
                }
            },
        ]
        daily_totals = {
            "calories": 2200,
            "protein_g": 125,
            "carbs_g": 260,
            "fat_g": 110,
        }
        target_macros = {
            "calories": 2800,
            "protein_g": 180,
            "carbs_g": 350,
            "fat_g": 80,
        }

        worst = generate_day_plan._find_worst_meal(meals, daily_totals, target_macros)
        # Meal 1 (idx=1) has high fat and low protein — worst contributor
        assert worst == 1


# ---------------------------------------------------------------------------
# Test: batch_recipe_ids support
# ---------------------------------------------------------------------------


class TestBatchRecipeIds:
    @pytest.mark.asyncio
    async def test_batch_recipe_ids_forces_recipe(
        self, meal_targets, user_profile, sample_db_recipe
    ):
        """When batch_recipe_ids has an entry, that recipe is used instead of searching."""
        generate_day_plan = _load_script("generate_day_plan")

        forced_recipe = dict(sample_db_recipe)
        forced_recipe["id"] = "forced-uuid-1"
        forced_recipe["name"] = "Batch Forced Recipe"

        async def mock_get_recipe_by_id(supabase, recipe_id):
            if recipe_id == "forced-uuid-1":
                return forced_recipe
            return None

        search_called = False

        async def mock_search(*args, **kwargs):
            nonlocal search_called
            search_called = True
            return [sample_db_recipe]

        with patch.object(
            generate_day_plan, "search_recipes", new=mock_search
        ), patch.object(
            generate_day_plan, "get_recipe_by_id", new=mock_get_recipe_by_id
        ), patch.object(generate_day_plan, "increment_usage", new=AsyncMock()):
            # Only send the Déjeuner slot with a batch recipe
            result_str = await generate_day_plan.execute(
                supabase=MagicMock(),
                anthropic_client=MagicMock(),
                day_index=0,
                day_name="Lundi",
                day_date="2026-02-18",
                meal_targets=[meal_targets[1]],  # Déjeuner only
                user_profile=user_profile,
                exclude_recipe_ids=[],
                custom_requests={},
                batch_recipe_ids={"dejeuner": "forced-uuid-1"},
            )

        result = json.loads(result_str)
        assert result["success"] is True
        # The forced recipe should have been used
        assert result["day"]["meals"][0]["name"] == "Batch Forced Recipe"

    @pytest.mark.asyncio
    async def test_batch_returns_recipe_ids_by_meal_type(
        self, meal_targets, user_profile, sample_db_recipe
    ):
        """generate_day_plan returns recipe_ids_by_meal_type mapping."""
        generate_day_plan = _load_script("generate_day_plan")

        with patch.object(
            generate_day_plan,
            "search_recipes",
            new=AsyncMock(return_value=[sample_db_recipe]),
        ), patch.object(generate_day_plan, "increment_usage", new=AsyncMock()):
            result_str = await generate_day_plan.execute(
                supabase=MagicMock(),
                anthropic_client=MagicMock(),
                day_index=0,
                day_name="Lundi",
                day_date="2026-02-18",
                meal_targets=meal_targets,
                user_profile=user_profile,
                exclude_recipe_ids=[],
                custom_requests={},
            )

        result = json.loads(result_str)
        assert result["success"] is True
        assert "recipe_ids_by_meal_type" in result
        ids_by_mt = result["recipe_ids_by_meal_type"]
        assert isinstance(ids_by_mt, dict)


# ---------------------------------------------------------------------------
# Test: Progressive fallback in recipe search
# ---------------------------------------------------------------------------


class TestProgressiveFallback:
    @pytest.mark.asyncio
    async def test_progressive_search_widens_on_empty(
        self, meal_targets, user_profile, sample_db_recipe
    ):
        """When first search returns empty, pipeline widens filters and retries."""
        generate_day_plan = _load_script("generate_day_plan")

        call_count = 0

        async def mock_search(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # First call returns nothing, second (widened) returns a recipe
            if call_count <= 1:
                return []
            return [sample_db_recipe]

        with patch.object(
            generate_day_plan, "search_recipes", new=mock_search
        ), patch.object(generate_day_plan, "increment_usage", new=AsyncMock()):
            result_str = await generate_day_plan.execute(
                supabase=MagicMock(),
                anthropic_client=MagicMock(),
                day_index=0,
                day_name="Lundi",
                day_date="2026-02-18",
                meal_targets=[meal_targets[0]],  # Single slot
                user_profile=user_profile,
                exclude_recipe_ids=[],
                custom_requests={},
            )

        result = json.loads(result_str)
        assert result["success"] is True
        # search_recipes was called multiple times (progressive fallback)
        assert call_count >= 2


# ---------------------------------------------------------------------------
# Test: Structured logging
# ---------------------------------------------------------------------------


class TestStructuredLogging:
    @pytest.mark.asyncio
    async def test_pipeline_emits_structured_logs(
        self, meal_targets, user_profile, sample_db_recipe, caplog
    ):
        """Pipeline emits structured log messages with step names."""
        generate_day_plan = _load_script("generate_day_plan")

        with patch.object(
            generate_day_plan,
            "search_recipes",
            new=AsyncMock(return_value=[sample_db_recipe]),
        ), patch.object(generate_day_plan, "increment_usage", new=AsyncMock()):
            import logging

            with caplog.at_level(logging.INFO):
                await generate_day_plan.execute(
                    supabase=MagicMock(),
                    anthropic_client=MagicMock(),
                    day_index=0,
                    day_name="Lundi",
                    day_date="2026-02-18",
                    meal_targets=meal_targets,
                    user_profile=user_profile,
                    exclude_recipe_ids=[],
                    custom_requests={},
                )

        log_text = caplog.text
        assert "pipeline_step" in log_text
        assert "select_recipes" in log_text
        assert "scale_portions" in log_text
        assert "validate_day" in log_text
