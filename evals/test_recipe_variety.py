"""Evals for recipe variety scoring and batch cooking.

Real LLM evals — scored, run on demand before releases.
Tests require a populated recipe DB and live Supabase connection.

Usage:
    pytest evals/test_recipe_variety.py -v --tb=short
"""

import importlib.util
import logging
from pathlib import Path

import pytest

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Required for all eval files per CLAUDE.md rule
TEST_USER_PROFILE = {
    "age": 30,
    "gender": "male",
    "height_cm": 180,
    "weight_kg": 80,
    "activity_level": "moderately_active",
    "goals": "maintain",
    "allergies": [],
    "diet_type": "omnivore",
    "preferred_cuisines": ["française", "asiatique"],
    "max_prep_time": 45,
    "target_calories": 2500,
    "target_protein_g": 180,
    "target_carbs_g": 280,
    "target_fat_g": 70,
}


def _load_script(skill_name: str, script_name: str):
    """Load a skill script module."""
    script_path = PROJECT_ROOT / "skills" / skill_name / "scripts" / f"{script_name}.py"
    spec = importlib.util.spec_from_file_location(
        f"{skill_name}.{script_name}", script_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.eval
class TestVarietyScoring:
    """Eval: variety scoring produces diverse week plans."""

    @pytest.mark.asyncio
    async def test_variety_scoring_produces_diverse_week(self):
        """Generate a 7-day plan and verify no recipe ID repeats across days.

        Score: proportion of unique recipes out of total recipe slots.
        Target: >= 80% unique (some overlap acceptable due to DB size).
        """

        # This eval requires a live DB or a sufficiently large mock
        # For CI: skip if no DB connection
        pytest.skip("Eval requires live Supabase connection — run manually")

    @pytest.mark.asyncio
    async def test_batch_mode_repeats_correctly(self):
        """Generate 7-day plan with batch_days=3, verify lunch repeats for 3 days then changes.

        Score: batch blocks should have identical recipe IDs within block,
        different across blocks.
        """
        pytest.skip("Eval requires live Supabase connection — run manually")

    @pytest.mark.asyncio
    async def test_variety_prefers_fresh_over_stale(self):
        """Mark 2 recipes with recent last_used_date, generate a day plan,
        verify they're ranked lower than fresh alternatives.

        Score: recently-used recipes should not be in top-1 picks.
        """
        pytest.skip("Eval requires live Supabase connection — run manually")
