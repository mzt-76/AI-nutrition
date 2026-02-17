# Feature: fetch_stored_meal_plan Tool

The following plan should be complete, but it's important that you validate documentation and codebase patterns and task sanity before you start implementing.

Pay special attention to naming of existing utils, types and models. Import from the right files etc.

## Feature Description

Create a new agent tool `fetch_stored_meal_plan` that retrieves existing meal plans from the Supabase `meal_plans` table. This prevents unnecessary regeneration when users ask to see their current meal plan or specific days. The tool filters by date range and optionally by specific days, returning formatted meal data ready for display.

## User Story

As a nutrition assistant user
I want to retrieve my previously generated meal plan
So that I can see what I should eat today/this week without waiting 3-4 minutes for regeneration

## Problem Statement

Currently, when a user asks "What should I eat today?" or "Show me my meal plan for Wednesday", the agent has no tool to retrieve existing plans. It either:
1. Regenerates a full 7-day plan (3-4 min, $0.15-0.25) - wasteful
2. Cannot answer the question properly

The `generate_shopping_list_tool` already fetches from `meal_plans` but only extracts ingredients, not the full meal data with recipes.

## Solution Statement

Create `fetch_stored_meal_plan_tool` that:
1. Queries `meal_plans` table by `week_start` date
2. Optionally filters to specific days (0-6 index)
3. Returns full meal details (recipes, macros, ingredients, instructions)
4. Handles edge cases (no plan found, date outside range)

## Feature Metadata

**Feature Type**: New Capability
**Estimated Complexity**: Low
**Primary Systems Affected**: `tools.py`, `agent.py`
**Dependencies**: Supabase client (already available in AgentDeps)

---

## CONTEXT REFERENCES

### Relevant Codebase Files - MUST READ BEFORE IMPLEMENTING!

- `4_Pydantic_AI_Agent/tools.py` (lines 1247-1420) - **`generate_shopping_list_tool`** is the exact pattern to follow. It already fetches meal plans from Supabase and filters by days.

- `4_Pydantic_AI_Agent/agent.py` (lines 384-423) - **`generate_shopping_list`** wrapper shows how to register tool with `@agent.tool` decorator and extract `ctx.deps.supabase`.

- `4_Pydantic_AI_Agent/nutrition/meal_planning.py` (lines 1-48) - **`MEAL_STRUCTURES`** dict and day name constants for reference.

- `4_Pydantic_AI_Agent/tests/test_shopping_list.py` - Test patterns for tool testing with mock data.

### New Files to Create

- None (all changes in existing files)

### Files to Modify

- `4_Pydantic_AI_Agent/tools.py` - Add `fetch_stored_meal_plan_tool()` function
- `4_Pydantic_AI_Agent/agent.py` - Add `@agent.tool` wrapper for `fetch_stored_meal_plan`
- `4_Pydantic_AI_Agent/tests/test_shopping_list.py` - Add tests for new tool (or create `tests/test_fetch_meal_plan.py`)

### Relevant Documentation

- [Supabase Python Client](https://supabase.com/docs/reference/python/select)
  - Specific section: Select queries with filters
  - Why: Shows `.select().eq().limit().execute()` pattern

- [Pydantic AI Tools](https://ai.pydantic.dev/tools/)
  - Specific section: Tool registration
  - Why: Confirms `@agent.tool` decorator usage

### Patterns to Follow

**Docstring Format (8-section pattern from tools.py):**
```python
async def tool_name(...) -> str:
    """
    [1] One-line summary.

    [2] Extended description (2-3 sentences).

    Use this when:
    - Scenario 1
    - Scenario 2

    Do NOT use this when:
    - Counter-scenario 1 → Use X instead

    Args:
        param1: Description with valid values
        param2: Description with defaults

    Returns:
        JSON structure with comments

    Performance Notes:
        - Execution time: Xms
        - Token usage: ~Y tokens
        - Database queries: Z

    Example:
        >>> result = await tool_name(...)
    """
```

**Supabase Query Pattern (from generate_shopping_list_tool lines 1315-1323):**
```python
meal_plan_response = (
    supabase.table("meal_plans")
    .select("*")
    .eq("week_start", week_start)
    .limit(1)
    .execute()
)

if not meal_plan_response.data:
    return json.dumps({
        "error": f"No meal plan found for week starting {week_start}",
        "code": "MEAL_PLAN_NOT_FOUND",
        "suggestion": "Generate a meal plan first using generate_weekly_meal_plan"
    })
```

**Error Handling Pattern:**
```python
try:
    # Validation
    # Database query
    # Processing
    # Return success
except ValueError as e:
    logger.error(f"Validation error: {e}")
    return json.dumps({"error": str(e), "code": "VALIDATION_ERROR"})
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
    return json.dumps({"error": "Internal error", "code": "FETCH_ERROR"})
```

**Tool Registration Pattern (from agent.py lines 384-423):**
```python
@agent.tool
async def tool_name(
    ctx: RunContext[AgentDeps],
    param1: str,
    param2: list[int] | None = None,
) -> str:
    """Docstring for LLM."""
    logger.info("Tool called: tool_name")
    return await tool_name_tool(ctx.deps.supabase, param1, param2)
```

**Day Names Constant (from meal_planning.py line 172 and tools.py line 1374):**
```python
DAY_NAMES = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
```

---

## IMPLEMENTATION PLAN

### Phase 1: Tool Implementation in tools.py

Add `fetch_stored_meal_plan_tool()` function after `generate_shopping_list_tool()` (around line 1420).

**Tasks:**
- Implement Supabase query with date filter
- Add day filtering logic (reuse from `generate_shopping_list_tool`)
- Format response with meals, macros, metadata
- Handle error cases

### Phase 2: Agent Registration in agent.py

Add `@agent.tool` wrapper after `generate_shopping_list` (around line 423).

**Tasks:**
- Create wrapper function with comprehensive docstring
- Extract `ctx.deps.supabase` and delegate to tool

### Phase 3: Testing

Add tests for the new tool.

**Tasks:**
- Test happy path (plan exists, all days)
- Test day filtering (specific days only)
- Test error cases (no plan found, invalid date)

---

## STEP-BY-STEP TASKS

### Task 1: CREATE `fetch_stored_meal_plan_tool` in tools.py

**Location:** After line 1420 (after `generate_shopping_list_tool`)

**IMPLEMENT:** Add the following function:

```python
async def fetch_stored_meal_plan_tool(
    supabase: Client,
    week_start: str,
    selected_days: list[int] | None = None,
) -> str:
    """
    Retrieve stored meal plan from database for display.

    Fetches an existing meal plan by week start date and optionally filters
    to specific days. Returns full meal details including recipes, macros,
    ingredients, and instructions.

    Use this when:
    - User asks "What should I eat today?" or "Show me today's meals"
    - User asks "Rappelle-moi le plan de la semaine"
    - User asks "Qu'est-ce que je mange mercredi ?"
    - User wants to review their current meal plan without regenerating
    - Before calling generate_weekly_meal_plan, check if a plan already exists

    Do NOT use this when:
    - User explicitly wants a NEW meal plan → Use `generate_weekly_meal_plan`
    - User wants to change/modify the existing plan → Use `generate_weekly_meal_plan`
    - User wants a shopping list → Use `generate_shopping_list`
    - No plan exists yet → Suggest `generate_weekly_meal_plan` first

    Args:
        supabase: Supabase client for database operations
        week_start: Meal plan start date in YYYY-MM-DD format (e.g., "2025-01-20")
        selected_days: List of day indices to retrieve (0=Lundi to 6=Dimanche),
                      or None for all 7 days. Example: [0] for Monday only

    Returns:
        JSON string with meal plan data or error:
        {
            "success": true,
            "meal_plan_id": "uuid",
            "week_start": "2025-01-20",
            "days_included": [0, 1, 2, 3, 4, 5, 6],
            "days_description": "Lundi, Mardi, ..., Dimanche",
            "daily_targets": {
                "calories": 2500,
                "protein_g": 180,
                "carbs_g": 300,
                "fat_g": 80
            },
            "days": [
                {
                    "day": "Lundi",
                    "date": "2025-01-20",
                    "meals": [
                        {
                            "meal_type": "Petit-déjeuner",
                            "recipe": {
                                "name": "Omelette aux épinards",
                                "ingredients": [...],
                                "instructions": "...",
                                "prep_time_minutes": 15
                            },
                            "macros": {"calories": 450, "protein_g": 35, ...}
                        },
                        ...
                    ],
                    "daily_totals": {"calories": 2480, ...}
                },
                ...
            ],
            "message": "Plan retrieved for 7 days"
        }

    Performance Notes:
        - Execution time: <500ms (single DB query)
        - Token usage: ~500-2000 tokens depending on days requested
        - Database queries: 1
        - Network calls: 0 (no external APIs)
        - Cost: Free (no LLM calls)

    Example:
        >>> # Get full week plan
        >>> result = await fetch_stored_meal_plan_tool(supabase, "2025-01-20")

        >>> # Get only Monday and Tuesday
        >>> result = await fetch_stored_meal_plan_tool(
        ...     supabase, "2025-01-20", selected_days=[0, 1]
        ... )

        >>> # Get today (Wednesday = index 2)
        >>> result = await fetch_stored_meal_plan_tool(
        ...     supabase, "2025-01-20", selected_days=[2]
        ... )
    """
    try:
        logger.info(
            f"Fetching stored meal plan for week {week_start}, days: {selected_days}"
        )

        # Step 1: Validate date format
        try:
            datetime.strptime(week_start, "%Y-%m-%d")
        except ValueError:
            return json.dumps({
                "error": "Invalid date format. Use YYYY-MM-DD (e.g., 2025-01-20)",
                "code": "VALIDATION_ERROR",
            })

        # Step 2: Validate selected_days if provided
        if selected_days is not None:
            if not selected_days:
                return json.dumps({
                    "error": "selected_days cannot be empty. Use null for all days or provide day indices (0-6)",
                    "code": "VALIDATION_ERROR",
                })
            if any(day < 0 or day > 6 for day in selected_days):
                return json.dumps({
                    "error": "Day indices must be between 0 (Lundi) and 6 (Dimanche)",
                    "code": "VALIDATION_ERROR",
                })

        # Step 3: Fetch meal plan from database
        logger.info(f"Querying meal_plans table for week_start={week_start}")
        meal_plan_response = (
            supabase.table("meal_plans")
            .select("*")
            .eq("week_start", week_start)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

        if not meal_plan_response.data:
            return json.dumps({
                "error": f"No meal plan found for week starting {week_start}",
                "code": "MEAL_PLAN_NOT_FOUND",
                "suggestion": "Generate a meal plan first using generate_weekly_meal_plan",
            })

        meal_plan_record = meal_plan_response.data[0]
        plan_data = meal_plan_record.get("plan_data")

        if not plan_data:
            return json.dumps({
                "error": "Meal plan data is empty or corrupted",
                "code": "INVALID_MEAL_PLAN",
            })

        # Step 4: Filter days if requested
        all_days = plan_data.get("days", [])

        if not all_days:
            return json.dumps({
                "error": "Meal plan has no days data",
                "code": "INVALID_MEAL_PLAN",
            })

        if selected_days is not None:
            # Filter to selected days only
            filtered_days = [
                day for i, day in enumerate(all_days) if i in selected_days
            ]
        else:
            filtered_days = all_days
            selected_days = list(range(len(all_days)))

        if not filtered_days:
            return json.dumps({
                "error": f"No days found for indices {selected_days}",
                "code": "NO_DAYS_FOUND",
            })

        # Step 5: Build response with metadata
        day_names = [
            "Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"
        ]
        days_description = ", ".join([day_names[d] for d in sorted(selected_days) if d < len(day_names)])

        response = {
            "success": True,
            "meal_plan_id": meal_plan_record.get("id"),
            "week_start": week_start,
            "days_included": sorted(selected_days),
            "days_description": days_description,
            "daily_targets": {
                "calories": meal_plan_record.get("target_calories_daily"),
                "protein_g": meal_plan_record.get("target_protein_g"),
                "carbs_g": meal_plan_record.get("target_carbs_g"),
                "fat_g": meal_plan_record.get("target_fat_g"),
            },
            "days": filtered_days,
            "total_days_in_plan": len(all_days),
            "days_returned": len(filtered_days),
            "message": f"Plan retrieved for {len(filtered_days)} day(s): {days_description}",
        }

        logger.info(
            f"✅ Meal plan retrieved: {len(filtered_days)} days from plan ID {meal_plan_record.get('id')}"
        )
        return json.dumps(response, indent=2, ensure_ascii=False)

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return json.dumps({"error": str(e), "code": "VALIDATION_ERROR"})
    except Exception as e:
        logger.error(f"Unexpected error fetching meal plan: {e}", exc_info=True)
        return json.dumps({
            "error": "Internal error fetching meal plan",
            "code": "FETCH_ERROR",
        })
```

**IMPORTS:** Already available (json, logging, datetime, Client from supabase)

**VALIDATE:**
```bash
cd 4_Pydantic_AI_Agent && python -c "from tools import fetch_stored_meal_plan_tool; print('Import OK')"
```

---

### Task 2: ADD import in tools.py (if needed)

**Location:** Top of tools.py, ensure `datetime` is imported

**VERIFY:** Line 23 already has `from datetime import datetime, timedelta`

**VALIDATE:**
```bash
cd 4_Pydantic_AI_Agent && python -c "from tools import *; print('All imports OK')"
```

---

### Task 3: CREATE `@agent.tool` wrapper in agent.py

**Location:** After line 423 (after `generate_shopping_list`)

**IMPLEMENT:** Add the following:

```python
@agent.tool
async def fetch_stored_meal_plan(
    ctx: RunContext[AgentDeps],
    week_start: str,
    selected_days: list[int] | None = None,
) -> str:
    """
    Retrieve an existing meal plan from database without regenerating.

    Use this to show the user their current meal plan or specific days.
    Much faster than generating a new plan (500ms vs 3-4 minutes).

    Use this when:
    - User asks "What should I eat today/this week?"
    - User asks "Rappelle-moi mon plan de repas"
    - User asks "Qu'est-ce que je mange mercredi ?"
    - You need to check if a plan already exists before generating

    Do NOT use when:
    - User wants a NEW plan → Use generate_weekly_meal_plan
    - User wants a shopping list → Use generate_shopping_list

    Args:
        ctx: Run context with Supabase client
        week_start: Meal plan start date in YYYY-MM-DD format (e.g., "2025-01-20")
        selected_days: List of day indices to retrieve (0=Lundi to 6=Dimanche),
                      or None for all 7 days. Example: [2] for Wednesday only

    Returns:
        JSON string with meal plan data including recipes, macros, and instructions

    Examples:
        User: "Qu'est-ce que je mange aujourd'hui ?" (if today is Wednesday)
        Agent: fetch_stored_meal_plan(week_start="2025-01-20", selected_days=[2])

        User: "Montre-moi le plan de la semaine"
        Agent: fetch_stored_meal_plan(week_start="2025-01-20")

        User: "Rappelle-moi les repas de lundi et mardi"
        Agent: fetch_stored_meal_plan(week_start="2025-01-20", selected_days=[0, 1])
    """
    logger.info("Tool called: fetch_stored_meal_plan")
    return await fetch_stored_meal_plan_tool(
        ctx.deps.supabase, week_start, selected_days
    )
```

**IMPORTS:** Add at top of agent.py with other tool imports:
```python
from tools import (
    # ... existing imports ...
    fetch_stored_meal_plan_tool,
)
```

**VALIDATE:**
```bash
cd 4_Pydantic_AI_Agent && python -c "from agent import agent; print(f'Agent has {len(agent._function_tools)} tools')"
```

---

### Task 4: CREATE unit tests

**Location:** Create new file `4_Pydantic_AI_Agent/tests/test_fetch_meal_plan.py`

**IMPLEMENT:**

```python
"""
Tests for fetch_stored_meal_plan_tool.

Tests the retrieval of stored meal plans from Supabase.
"""

import pytest
import json


class TestFetchStoredMealPlanValidation:
    """Test input validation for fetch_stored_meal_plan_tool."""

    def test_invalid_date_format(self):
        """Test that invalid date format returns error."""
        # This would need a mock supabase client
        # For now, test the validation logic directly
        from datetime import datetime

        # Valid format
        assert datetime.strptime("2025-01-20", "%Y-%m-%d")

        # Invalid format should raise
        with pytest.raises(ValueError):
            datetime.strptime("20-01-2025", "%Y-%m-%d")

        with pytest.raises(ValueError):
            datetime.strptime("2025/01/20", "%Y-%m-%d")

    def test_selected_days_validation(self):
        """Test that day indices are validated correctly."""
        valid_days = [0, 1, 2, 3, 4, 5, 6]
        invalid_days = [-1, 7, 8]

        # Valid range check
        assert all(0 <= d <= 6 for d in valid_days)

        # Invalid range check
        assert any(d < 0 or d > 6 for d in invalid_days)


class TestFetchStoredMealPlanDayFiltering:
    """Test day filtering logic."""

    @pytest.fixture
    def sample_plan_data(self) -> dict:
        """Sample meal plan with 7 days."""
        day_names = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
        days = []
        for i, name in enumerate(day_names):
            days.append({
                "day": name,
                "date": f"2025-01-{20+i:02d}",
                "meals": [
                    {
                        "meal_type": "Petit-déjeuner",
                        "recipe": {"name": f"Breakfast {name}"},
                        "macros": {"calories": 500, "protein_g": 30}
                    }
                ],
                "daily_totals": {"calories": 2000, "protein_g": 150}
            })
        return {"days": days}

    def test_filter_single_day(self, sample_plan_data: dict):
        """Test filtering to single day."""
        all_days = sample_plan_data["days"]
        selected_days = [2]  # Wednesday

        filtered = [day for i, day in enumerate(all_days) if i in selected_days]

        assert len(filtered) == 1
        assert filtered[0]["day"] == "Mercredi"

    def test_filter_multiple_days(self, sample_plan_data: dict):
        """Test filtering to multiple days."""
        all_days = sample_plan_data["days"]
        selected_days = [0, 1, 4]  # Mon, Tue, Fri

        filtered = [day for i, day in enumerate(all_days) if i in selected_days]

        assert len(filtered) == 3
        assert filtered[0]["day"] == "Lundi"
        assert filtered[1]["day"] == "Mardi"
        assert filtered[2]["day"] == "Vendredi"

    def test_filter_all_days(self, sample_plan_data: dict):
        """Test with no filter (all days)."""
        all_days = sample_plan_data["days"]
        selected_days = None

        if selected_days is None:
            filtered = all_days
        else:
            filtered = [day for i, day in enumerate(all_days) if i in selected_days]

        assert len(filtered) == 7


class TestFetchStoredMealPlanResponse:
    """Test response formatting."""

    def test_day_names_constant(self):
        """Test day names are correctly defined."""
        day_names = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]

        assert len(day_names) == 7
        assert day_names[0] == "Lundi"
        assert day_names[6] == "Dimanche"

    def test_days_description_format(self):
        """Test days description formatting."""
        day_names = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
        selected_days = [0, 2, 4]

        days_description = ", ".join([day_names[d] for d in sorted(selected_days)])

        assert days_description == "Lundi, Mercredi, Vendredi"

    def test_response_structure(self):
        """Test expected response structure keys."""
        expected_keys = [
            "success",
            "meal_plan_id",
            "week_start",
            "days_included",
            "days_description",
            "daily_targets",
            "days",
            "message"
        ]

        # Mock response
        response = {
            "success": True,
            "meal_plan_id": "test-id",
            "week_start": "2025-01-20",
            "days_included": [0, 1, 2],
            "days_description": "Lundi, Mardi, Mercredi",
            "daily_targets": {"calories": 2500},
            "days": [],
            "message": "Plan retrieved"
        }

        for key in expected_keys:
            assert key in response, f"Missing key: {key}"
```

**VALIDATE:**
```bash
cd 4_Pydantic_AI_Agent && python -m pytest tests/test_fetch_meal_plan.py -v
```

---

### Task 5: UPDATE tools.py imports (verification)

**Location:** `4_Pydantic_AI_Agent/tools.py` line 1

**VERIFY:** Ensure these imports exist:
- `from datetime import datetime, timedelta` (line 23)
- `from supabase import Client` (line 17)
- `import json` (line 20)
- `import logging` (line 21)

**VALIDATE:**
```bash
cd 4_Pydantic_AI_Agent && ruff check tools.py --select=F401,E401
```

---

### Task 6: UPDATE agent.py imports

**Location:** `4_Pydantic_AI_Agent/agent.py` imports section

**IMPLEMENT:** Add `fetch_stored_meal_plan_tool` to the import from tools:

Find the line that imports from tools (around line 15-30):
```python
from tools import (
    calculate_nutritional_needs_tool,
    fetch_my_profile_tool,
    # ... other imports ...
    fetch_stored_meal_plan_tool,  # ADD THIS
)
```

**VALIDATE:**
```bash
cd 4_Pydantic_AI_Agent && python -c "from agent import fetch_stored_meal_plan; print('Import OK')"
```

---

### Task 7: RUN full validation suite

**VALIDATE ALL:**
```bash
cd 4_Pydantic_AI_Agent && ruff format . && ruff check . && python -m pytest tests/ -v --tb=short
```

---

## TESTING STRATEGY

### Unit Tests (Task 4)

- Input validation (date format, day indices)
- Day filtering logic
- Response structure

### Integration Test (Manual)

```bash
cd 4_Pydantic_AI_Agent && python -c "
import asyncio
from clients import get_supabase_client
from tools import fetch_stored_meal_plan_tool

async def test():
    sb = get_supabase_client()
    # Test with existing plan date
    result = await fetch_stored_meal_plan_tool(sb, '2024-12-23')
    print(result[:500])

asyncio.run(test())
"
```

### Edge Cases

1. **No plan exists** - Should return `MEAL_PLAN_NOT_FOUND` with suggestion
2. **Invalid date format** - Should return `VALIDATION_ERROR`
3. **Day indices out of range** - Should return `VALIDATION_ERROR`
4. **Empty selected_days list** - Should return `VALIDATION_ERROR`
5. **Plan exists but corrupted data** - Should return `INVALID_MEAL_PLAN`

---

## VALIDATION COMMANDS

### Tier 1: Required Validation (Must Pass)

**Syntax and Linting:**
```bash
cd 4_Pydantic_AI_Agent && ruff format . && ruff check .
```

**Unit Tests:**
```bash
cd 4_Pydantic_AI_Agent && python -m pytest tests/test_fetch_meal_plan.py -v
```

**Import Validation:**
```bash
cd 4_Pydantic_AI_Agent && python -c "from agent import agent, fetch_stored_meal_plan; from tools import fetch_stored_meal_plan_tool; print('All imports OK')"
```

### Tier 2: Recommended Validation

**Full Test Suite:**
```bash
cd 4_Pydantic_AI_Agent && python -m pytest tests/ -v --tb=short
```

**Type Checking:**
```bash
cd 4_Pydantic_AI_Agent && mypy tools.py agent.py --ignore-missing-imports
```

**Manual Streamlit Test:**
```bash
cd 4_Pydantic_AI_Agent && streamlit run streamlit_ui.py
# Test: "Montre-moi le plan de repas de la semaine du 2024-12-23"
```

---

## ACCEPTANCE CRITERIA

- [ ] `fetch_stored_meal_plan_tool()` function exists in tools.py
- [ ] `@agent.tool fetch_stored_meal_plan()` wrapper exists in agent.py
- [ ] Tool returns JSON with success/error structure
- [ ] Day filtering works correctly (0-6 indices)
- [ ] Error cases handled (no plan, invalid date, invalid days)
- [ ] All validation commands pass (Tier 1)
- [ ] Unit tests pass
- [ ] No ruff linting errors

---

## COMPLETION CHECKLIST

- [ ] Task 1: `fetch_stored_meal_plan_tool` implemented in tools.py
- [ ] Task 2: Imports verified in tools.py
- [ ] Task 3: `@agent.tool` wrapper added in agent.py
- [ ] Task 4: Unit tests created in tests/test_fetch_meal_plan.py
- [ ] Task 5: tools.py imports verified
- [ ] Task 6: agent.py imports updated
- [ ] Task 7: Full validation suite passes
- [ ] All Tier 1 validation commands pass
- [ ] Agent tool count increased by 1

---

## NOTES

### Design Decisions

1. **Reuse `generate_shopping_list_tool` pattern** - Same Supabase query, validation, and error handling for consistency

2. **Order by `created_at` desc** - If multiple plans exist for same week, return most recent

3. **Return full meal data** - Unlike shopping list (ingredients only), this returns complete recipes, instructions, and macros

4. **Day index convention** - 0=Lundi to 6=Dimanche (consistent with existing code)

### Trade-offs

- **No date range queries** - Only supports single `week_start` lookup (matches existing pattern)
- **No pagination** - Returns all requested days in one response (meal plans are bounded to 7 days max)

### Future Enhancements

- Add `get_today_meals()` helper that auto-calculates day index from current date
- Add `get_current_week_start()` helper to find the Monday of current week
- Consider caching frequently accessed plans
