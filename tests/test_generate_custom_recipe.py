"""Tests for the generate_custom_recipe skill script.

Mocks: anthropic_client (LLM), match_ingredient (OFF), save_recipe (DB).
No real API calls.
"""

import json
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helper: load script
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
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def module():
    return _load_script("generate_custom_recipe")


def _make_llm_response(recipe_dict: dict) -> MagicMock:
    """Build an anthropic message mock returning a JSON recipe."""
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=json.dumps(recipe_dict))]
    return mock_message


def _sample_recipe_dict(**overrides) -> dict:
    base = {
        "name": "Risotto aux champignons",
        "description": "Un risotto crémeux.",
        "meal_type": "dejeuner",
        "cuisine_type": "italienne",
        "diet_type": "omnivore",
        "prep_time_minutes": 30,
        "ingredients": [
            {"name": "riz arborio", "quantity": 150, "unit": "g"},
            {"name": "champignons", "quantity": 100, "unit": "g"},
        ],
        "instructions": "Faire revenir, ajouter le bouillon.",
        "tags": ["vegetarien"],
    }
    base.update(overrides)
    return base


def _make_anthropic_client(recipe_dict: dict) -> MagicMock:
    """Build a mock anthropic client that returns the given recipe."""
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=_make_llm_response(recipe_dict))
    return client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGenerateCustomRecipe:
    @pytest.mark.asyncio
    async def test_recipe_request_truncated_at_200_chars(self, module):
        """Input >200 chars is truncated to MAX_RECIPE_REQUEST_LENGTH before being sent to LLM."""
        long_request = "x" * 300
        recipe = _sample_recipe_dict()
        anthropic_client = _make_anthropic_client(recipe)

        with patch.object(
            module,
            "match_ingredient",
            new=AsyncMock(
                return_value={
                    "calories": 100,
                    "protein_g": 5,
                    "carbs_g": 20,
                    "fat_g": 1,
                }
            ),
        ), patch.object(
            module, "save_recipe", new=AsyncMock(return_value={"id": "saved-id"})
        ):
            await module.execute(
                anthropic_client=anthropic_client,
                supabase=MagicMock(),
                recipe_request=long_request,
                save_to_db=False,
            )

        # Inspect the prompt passed to the LLM
        create_call = anthropic_client.messages.create.call_args
        prompt_sent = create_call.kwargs["messages"][0]["content"]
        # The truncated request (200 chars of "x") must appear; the 201st must not
        assert "x" * 200 in prompt_sent
        assert "x" * 201 not in prompt_sent

    @pytest.mark.asyncio
    async def test_json_parse_error_returns_error_code(self, module):
        """LLM returning non-JSON → {'code': 'JSON_PARSE_ERROR'}."""
        client = MagicMock()
        bad_message = MagicMock()
        bad_message.content = [MagicMock(text="not valid json")]
        client.messages.create = AsyncMock(return_value=bad_message)

        result_str = await module.execute(
            anthropic_client=client,
            supabase=MagicMock(),
            recipe_request="une quiche lorraine",
        )
        result = json.loads(result_str)
        assert result["code"] == "JSON_PARSE_ERROR"

    @pytest.mark.asyncio
    async def test_allergen_rejection(self, module):
        """Recipe containing user allergen ingredient → ALLERGEN_VIOLATION, save_recipe NOT called."""
        # Recipe has "beurre" (lactose allergen)
        recipe = _sample_recipe_dict(
            ingredients=[
                {"name": "beurre", "quantity": 30, "unit": "g"},
                {"name": "farine", "quantity": 100, "unit": "g"},
            ]
        )
        anthropic_client = _make_anthropic_client(recipe)
        mock_save = AsyncMock()

        with patch.object(
            module, "match_ingredient", new=AsyncMock(return_value=None)
        ), patch.object(module, "save_recipe", new=mock_save):
            result_str = await module.execute(
                anthropic_client=anthropic_client,
                supabase=MagicMock(),
                recipe_request="une quiche",
                user_allergens=["lactose"],
                save_to_db=True,
            )

        result = json.loads(result_str)
        assert result["code"] == "ALLERGEN_VIOLATION"
        mock_save.assert_not_called()

    @pytest.mark.asyncio
    async def test_off_validated_true_all_matched(self, module):
        """All ingredients matched via OFF → off_validated: True, matched_ingredients == total."""
        recipe = _sample_recipe_dict()  # 2 ingredients
        anthropic_client = _make_anthropic_client(recipe)
        macros = {"calories": 200, "protein_g": 10, "carbs_g": 30, "fat_g": 5}

        with patch.object(
            module, "match_ingredient", new=AsyncMock(return_value=macros)
        ), patch.object(
            module, "save_recipe", new=AsyncMock(return_value={"id": "saved-id"})
        ):
            result_str = await module.execute(
                anthropic_client=anthropic_client,
                supabase=MagicMock(),
                recipe_request="risotto",
                save_to_db=False,
            )

        result = json.loads(result_str)
        assert result["off_validated"] is True
        assert result["matched_ingredients"] == 2
        assert result["total_ingredients"] == 2

    @pytest.mark.asyncio
    async def test_off_validated_false_partial_match(self, module):
        """One ingredient unmatched → off_validated: False."""
        recipe = _sample_recipe_dict()  # 2 ingredients
        anthropic_client = _make_anthropic_client(recipe)

        # First call returns macros, second returns None
        macros = {"calories": 200, "protein_g": 10, "carbs_g": 30, "fat_g": 5}
        mock_match = AsyncMock(side_effect=[macros, None])

        with patch.object(module, "match_ingredient", new=mock_match), patch.object(
            module, "save_recipe", new=AsyncMock(return_value={"id": "saved-id"})
        ):
            result_str = await module.execute(
                anthropic_client=anthropic_client,
                supabase=MagicMock(),
                recipe_request="risotto",
                save_to_db=False,
            )

        result = json.loads(result_str)
        assert result["off_validated"] is False
        assert result["matched_ingredients"] == 1
        assert result["total_ingredients"] == 2

    @pytest.mark.asyncio
    async def test_recipe_saved_to_db_when_save_to_db_true(self, module):
        """save_recipe is called once; returned recipe contains 'id' field."""
        recipe = _sample_recipe_dict()
        anthropic_client = _make_anthropic_client(recipe)
        macros = {"calories": 200, "protein_g": 10, "carbs_g": 30, "fat_g": 5}
        mock_save = AsyncMock(return_value={"id": "db-generated-id"})

        with patch.object(
            module, "match_ingredient", new=AsyncMock(return_value=macros)
        ), patch.object(module, "save_recipe", new=mock_save):
            result_str = await module.execute(
                anthropic_client=anthropic_client,
                supabase=MagicMock(),
                recipe_request="risotto",
                save_to_db=True,
            )

        mock_save.assert_called_once()
        result = json.loads(result_str)
        assert "id" in result["recipe"]
        assert result["recipe"]["id"] == "db-generated-id"
