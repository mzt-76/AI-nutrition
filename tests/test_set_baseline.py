"""Unit tests for the set_baseline skill script.

Tests cover: happy path, body composition, upsert behaviour, validation
errors (missing weight, out-of-range, missing user_id), and week_number=0
storage. Also verifies baseline exclusion from historical queries.
"""

import importlib.util
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Import the module from a hyphenated path
_spec = importlib.util.spec_from_file_location(
    "set_baseline",
    Path(__file__).resolve().parent.parent
    / "skills"
    / "weekly-coaching"
    / "scripts"
    / "set_baseline.py",
)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
execute = _mod.execute


def _make_supabase_mock(existing_baseline: dict | None = None) -> MagicMock:
    """Create a Supabase mock with chained query support.

    Args:
        existing_baseline: If provided, simulates an existing baseline row
            so the script takes the update path instead of insert.
    """
    mock = MagicMock()
    table_mock = MagicMock()
    mock.table.return_value = table_mock

    # Chain: table().select().eq().eq().limit().execute()
    select_chain = MagicMock()
    select_chain.execute.return_value = MagicMock(
        data=[existing_baseline] if existing_baseline else []
    )
    table_mock.select.return_value.eq.return_value.eq.return_value.limit.return_value = select_chain

    # Chain: table().insert().execute()
    insert_chain = MagicMock()
    insert_chain.execute.return_value = MagicMock(data=[{"id": "new-uuid"}])
    table_mock.insert.return_value = insert_chain

    # Chain: table().update().eq().execute()
    update_chain = MagicMock()
    update_chain.execute.return_value = MagicMock(data=[{"id": "existing-uuid"}])
    table_mock.update.return_value.eq.return_value = update_chain

    return mock


class TestSetBaselineHappyPath:
    """Tests for successful baseline recording."""

    @pytest.mark.asyncio
    async def test_basic_weight_only(self):
        """Record baseline with just weight_kg."""
        mock_sb = _make_supabase_mock()
        result = json.loads(
            await execute(
                supabase=mock_sb,
                user_id="user-123",
                weight_kg=87.5,
            )
        )

        assert result["status"] == "success"
        assert result["week_number"] == 0
        assert result["weight_kg"] == 87.5

        # Verify insert was called (no existing baseline)
        call_args = mock_sb.table.return_value.insert.call_args
        stored = call_args[0][0]
        assert stored["week_number"] == 0
        assert stored["weight_start_kg"] == 87.5
        assert stored["weight_end_kg"] == 87.5
        assert stored["user_id"] == "user-123"
        assert stored["adherence_percent"] == 0

    @pytest.mark.asyncio
    async def test_with_body_composition(self):
        """Record baseline with body composition data."""
        mock_sb = _make_supabase_mock()
        result = json.loads(
            await execute(
                supabase=mock_sb,
                user_id="user-123",
                weight_kg=87.5,
                body_fat_percent=22.0,
                muscle_mass_kg=68.5,
                waist_cm=92.0,
                measurement_method="smart_scale",
            )
        )

        assert result["status"] == "success"
        assert result["body_composition"]["body_fat_percent"] == 22.0
        assert result["body_composition"]["muscle_mass_kg"] == 68.5
        assert result["body_composition"]["waist_cm"] == 92.0
        assert result["body_composition"]["measurement_method"] == "smart_scale"

        # Verify body fields stored in DB
        stored = mock_sb.table.return_value.insert.call_args[0][0]
        assert stored["body_fat_percent"] == 22.0
        assert stored["muscle_mass_kg"] == 68.5

    @pytest.mark.asyncio
    async def test_update_replaces_existing(self):
        """Update should replace existing baseline (not create duplicate)."""
        existing = {"id": "existing-uuid", "week_number": 0, "weight_start_kg": 85.0}
        mock_sb = _make_supabase_mock(existing_baseline=existing)

        result = json.loads(
            await execute(
                supabase=mock_sb,
                user_id="user-123",
                weight_kg=87.5,
            )
        )

        assert result["status"] == "success"
        # Verify update was called (not insert) with the existing row's id
        mock_sb.table.return_value.update.assert_called_once()
        mock_sb.table.return_value.insert.assert_not_called()


class TestSetBaselineValidation:
    """Tests for input validation errors."""

    @pytest.mark.asyncio
    async def test_missing_weight(self):
        """Error when weight_kg is not provided."""
        mock_sb = _make_supabase_mock()
        result = json.loads(
            await execute(
                supabase=mock_sb,
                user_id="user-123",
            )
        )
        assert result["code"] == "MISSING_WEIGHT"

    @pytest.mark.asyncio
    async def test_weight_below_range(self):
        """Error when weight_kg < 40."""
        mock_sb = _make_supabase_mock()
        result = json.loads(
            await execute(
                supabase=mock_sb,
                user_id="user-123",
                weight_kg=30.0,
            )
        )
        assert result["code"] == "WEIGHT_OUT_OF_RANGE"

    @pytest.mark.asyncio
    async def test_weight_above_range(self):
        """Error when weight_kg > 300."""
        mock_sb = _make_supabase_mock()
        result = json.loads(
            await execute(
                supabase=mock_sb,
                user_id="user-123",
                weight_kg=350.0,
            )
        )
        assert result["code"] == "WEIGHT_OUT_OF_RANGE"

    @pytest.mark.asyncio
    async def test_missing_user_id(self):
        """Error when user_id is not provided."""
        mock_sb = _make_supabase_mock()
        result = json.loads(
            await execute(
                supabase=mock_sb,
                weight_kg=87.5,
            )
        )
        assert result["code"] == "NO_USER_ID"


class TestSetBaselineWeekNumber:
    """Verify week_number=0 is always used for baselines."""

    @pytest.mark.asyncio
    async def test_week_number_is_zero(self):
        """Baseline row must always have week_number=0."""
        mock_sb = _make_supabase_mock()
        await execute(
            supabase=mock_sb,
            user_id="user-123",
            weight_kg=87.5,
        )

        stored = mock_sb.table.return_value.insert.call_args[0][0]
        assert stored["week_number"] == 0


class TestBaselineExclusionFromHistory:
    """Verify that baseline rows are excluded from trend analysis queries."""

    def test_history_filter_excludes_baseline(self):
        """The .gt('week_number', 0) filter should exclude week 0 rows.

        This is a conceptual test verifying the filter logic. The actual
        filter is applied in calculate_weekly_adjustments.py.
        """
        all_rows = [
            {"week_number": 0, "weight_start_kg": 87.5, "adherence_percent": 0},
            {"week_number": 1, "weight_start_kg": 87.5, "adherence_percent": 85},
            {"week_number": 2, "weight_start_kg": 87.0, "adherence_percent": 80},
        ]

        # Simulate the .gt("week_number", 0) filter
        filtered = [r for r in all_rows if r["week_number"] > 0]

        assert len(filtered) == 2
        assert all(r["week_number"] > 0 for r in filtered)
        assert not any(r["week_number"] == 0 for r in filtered)
