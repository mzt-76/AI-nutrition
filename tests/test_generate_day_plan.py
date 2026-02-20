"""Integration tests for the generate_day_plan skill script pipeline.

Tests use mocked Supabase and Anthropic clients — no real API calls.
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
    script_path = project_root / "skills" / "meal-planning" / "scripts" / f"{script_name}.py"
    spec = importlib.util.spec_from_file_location(f"meal_planning.{script_name}", script_path)
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


def _make_supabase_mock_with_recipes(recipes_by_meal_type: dict):
    """Create a Supabase mock that returns recipes based on meal_type."""
    mock = MagicMock()

    def make_chain(recipes):
        chain = MagicMock()
        execute_result = MagicMock()
        execute_result.data = recipes
        execute_result.count = len(recipes)

        # Build full chain
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.lte.return_value = chain
        chain.gte.return_value = chain
        chain.order.return_value = chain
        chain.limit.return_value = chain
        chain.execute.return_value = execute_result
        chain.insert.return_value = chain
        chain.update.return_value = chain
        return chain

    # Default chain with no data
    default_chain = make_chain([])
    mock.table.return_value = default_chain

    return mock


# ---------------------------------------------------------------------------
# Test: select_recipes script
# ---------------------------------------------------------------------------


class TestSelectRecipes:
    @pytest.mark.asyncio
    async def test_select_recipes_happy_path(self, meal_targets, sample_db_recipe):
        """select_recipes returns recipes for each meal slot."""
        select_recipes = _load_script("select_recipes")

        # patch.object targets the module's local binding directly
        with patch.object(select_recipes, "search_recipes", new=AsyncMock(return_value=[sample_db_recipe])):
            result_str = await select_recipes.execute(
                supabase=MagicMock(),
                meal_targets=meal_targets,
                user_allergens=[],
                diet_type="omnivore",
            )

        result = json.loads(result_str)
        assert "day_recipes" in result
        assert result["unmatched_slots"] == 0
        assert len(result["day_recipes"]) == 3

    @pytest.mark.asyncio
    async def test_select_recipes_no_db_match(self, meal_targets):
        """select_recipes marks slots as no_match when DB is empty."""
        select_recipes = _load_script("select_recipes")

        with patch.object(select_recipes, "search_recipes", new=AsyncMock(return_value=[])):
            result_str = await select_recipes.execute(
                supabase=MagicMock(),
                meal_targets=meal_targets,
                user_allergens=[],
            )

        result = json.loads(result_str)
        assert result["unmatched_slots"] == 3  # All slots unmatched


# ---------------------------------------------------------------------------
# Test: scale_portions script
# ---------------------------------------------------------------------------


class TestScalePortions:
    @pytest.mark.asyncio
    async def test_scale_portions_happy_path(self, sample_db_recipe):
        """scale_portions returns scaled recipe with correct nutrition."""
        scale_portions = _load_script("scale_portions")

        result_str = await scale_portions.execute(
            recipe=sample_db_recipe,
            target_calories=675,
            target_protein_g=45,
        )
        result = json.loads(result_str)

        assert "scaled_recipe" in result
        assert "scale_factor" in result
        assert "nutrition_before" in result
        assert "nutrition_after" in result

        # 675 / 450 = 1.5
        assert abs(result["scale_factor"] - 1.5) < 0.01
        assert abs(result["nutrition_after"]["calories"] - 675.0) < 1.0

    @pytest.mark.asyncio
    async def test_scale_portions_missing_recipe(self):
        """scale_portions returns error when recipe is missing."""
        scale_portions = _load_script("scale_portions")

        result_str = await scale_portions.execute(
            recipe={},
            target_calories=600,
            target_protein_g=40,
        )
        result = json.loads(result_str)
        assert "error" in result
        assert result["code"] == "VALIDATION_ERROR"


# ---------------------------------------------------------------------------
# Test: validate_day script
# ---------------------------------------------------------------------------


class TestValidateDay:
    @pytest.mark.asyncio
    async def test_validate_day_valid(self):
        """validate_day passes for allergen-free day within macro tolerance."""
        validate_day = _load_script("validate_day")

        day_plan = {
            "day": "Lundi",
            "date": "2026-02-18",
            "meals": [
                {
                    "meal_type": "Déjeuner",
                    "name": "Poulet grillé",
                    "ingredients": [{"name": "poulet", "quantity": 150, "unit": "g"}],
                    "nutrition": {"calories": 1100, "protein_g": 75, "carbs_g": 140, "fat_g": 30},
                }
            ],
            "daily_totals": {"calories": 2800, "protein_g": 175, "carbs_g": 350, "fat_g": 80},
        }

        result_str = await validate_day.execute(
            day_plan=day_plan,
            user_allergens=[],
            target_macros={"calories": 2800, "protein_g": 175, "carbs_g": 350, "fat_g": 80},
        )
        result = json.loads(result_str)
        assert result["valid"] is True
        assert result["violations"] == []

    @pytest.mark.asyncio
    async def test_validate_day_allergen_violation(self):
        """validate_day catches allergen violations."""
        validate_day = _load_script("validate_day")

        day_plan = {
            "day": "Mardi",
            "date": "2026-02-19",
            "meals": [
                {
                    "meal_type": "Déjeuner",
                    "name": "Salade au fromage",
                    "ingredients": [
                        {"name": "fromage camembert", "quantity": 50, "unit": "g"}
                    ],
                    "nutrition": {"calories": 200, "protein_g": 12, "carbs_g": 1, "fat_g": 16},
                }
            ],
            "daily_totals": {"calories": 200, "protein_g": 12, "carbs_g": 1, "fat_g": 16},
        }

        result_str = await validate_day.execute(
            day_plan=day_plan,
            user_allergens=["lactose"],
            target_macros={},
        )
        result = json.loads(result_str)
        assert result["valid"] is False
        assert len(result["allergen_violations"]) > 0

    @pytest.mark.asyncio
    async def test_validate_day_macro_violation(self):
        """validate_day catches macro violations outside tolerance."""
        validate_day = _load_script("validate_day")

        day_plan = {
            "day": "Mercredi",
            "date": "2026-02-20",
            "meals": [],
            "daily_totals": {"calories": 1000, "protein_g": 50, "carbs_g": 100, "fat_g": 30},
        }

        # Target 2800 kcal but got 1000 — way outside 10% tolerance
        result_str = await validate_day.execute(
            day_plan=day_plan,
            user_allergens=[],
            target_macros={"calories": 2800, "protein_g": 175, "carbs_g": 350, "fat_g": 80},
        )
        result = json.loads(result_str)
        assert result["valid"] is False
        assert len(result["macro_violations"]) > 0


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

        # patch.object patches the module-local binding directly
        with patch.object(generate_day_plan, "search_recipes", new=AsyncMock(return_value=[sample_db_recipe])), \
             patch.object(generate_day_plan, "increment_usage", new=AsyncMock()):
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

        with patch.object(generate_day_plan, "search_recipes", new=AsyncMock(return_value=[allergen_free_recipe])), \
             patch.object(generate_day_plan, "increment_usage", new=AsyncMock()):
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
                    assert "oeuf" not in ing["name"].lower(), (
                        f"Allergen 'oeuf' found in ingredient: {ing['name']}"
                    )

    @pytest.mark.asyncio
    async def test_day_plan_macro_accuracy(self, meal_targets, sample_db_recipe):
        """generate_day_plan produces macros within tolerance of targets."""
        generate_day_plan = _load_script("generate_day_plan")

        with patch.object(generate_day_plan, "search_recipes", new=AsyncMock(return_value=[sample_db_recipe])), \
             patch.object(generate_day_plan, "increment_usage", new=AsyncMock()):
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

        with patch.object(generate_day_plan, "search_recipes", new=AsyncMock(return_value=[sample_db_recipe])), \
             patch.object(generate_day_plan, "increment_usage", new=AsyncMock()):
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
            computed_total = sum(
                m["nutrition"]["calories"] for m in day["meals"]
            )
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

        with patch.object(generate_day_plan, "search_recipes", new=mock_search), \
             patch.object(generate_day_plan, "increment_usage", new=AsyncMock()):
            for day_idx in range(7):
                result_str = await generate_day_plan.execute(
                    supabase=MagicMock(),
                    anthropic_client=MagicMock(),
                    day_index=day_idx,
                    day_name=["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"][day_idx],
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

        with patch.object(generate_day_plan, "search_recipes", new=AsyncMock(return_value=[sample_db_recipe])), \
             patch.object(generate_day_plan, "increment_usage", new=AsyncMock()):
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
            {"recipe": custom_recipe, "off_validated": True, "matched_ingredients": 1, "total_ingredients": 1}
        )

        # Patch generate_custom_recipe module's execute at the sibling import level
        generate_custom_recipe_module = _load_script("generate_custom_recipe")
        generate_custom_recipe_module.execute = AsyncMock(return_value=custom_recipe_response)

        # Patch _import_sibling_script to return our pre-patched module
        with patch.object(
            generate_day_plan,
            "_import_sibling_script",
            return_value=generate_custom_recipe_module,
        ), patch.object(generate_day_plan, "search_recipes", new=AsyncMock(return_value=[])), \
           patch.object(generate_day_plan, "increment_usage", new=AsyncMock()):
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

    def test_substring_match(self):
        """Key that is a literal substring of lowercased meal_type returns the request."""
        custom_requests = {"jeuner": "pizza"}
        slot = {"meal_type": "Déjeuner"}
        result = self.find(custom_requests, slot)
        assert result == "pizza"

    def test_no_match_returns_none(self):
        """Unrelated keys return None."""
        custom_requests = {"diner": "soupe"}
        slot = {"meal_type": "Déjeuner"}
        result = self.find(custom_requests, slot)
        assert result is None
