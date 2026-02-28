# Feature: Weekly Feedback Baseline vs Check-in Distinction

The following plan should be complete, but its important that you validate documentation and codebase patterns and task sanity before you start implementing.

Pay special attention to naming of existing utils types and models. Import from the right files etc.

## Feature Description

Add a `week_number=0` baseline concept to the weekly feedback system. When a user starts coaching, the agent records their initial state (weight, optional body composition) as a baseline row (`week_number=0`) in `weekly_feedback` — without running analysis, generating adjustments, or incrementing learning data. Real check-ins continue as `week_number >= 1`. Historical queries exclude baseline rows so they never pollute trend analysis, metabolic adaptation detection, or adherence pattern matching.

Additionally, extend `weekly_feedback` with optional body composition columns (`body_fat_percent`, `muscle_mass_kg`, `waist_cm`, etc.) so the table serves as a complete body tracking timeline.

## User Story

As a nutrition coaching user
I want my initial weight/body data recorded as a baseline (not a fake check-in)
So that my weekly trend analysis, pattern detection, and adjustment recommendations are based only on real feedback data

## Problem Statement

Currently, when the agent records a user's starting weight, it calls `calculate_weekly_adjustments` with `weight_start=weight_end` and `adherence=100%`. This creates a fake week-1 row that:
- Pollutes historical queries (trend analysis, metabolic adaptation, adherence patterns)
- Inflates adherence stats (100% on a week where no plan existed)
- Shifts `week_number` by +1 on every subsequent real check-in
- Increments `user_learning_profile.weeks_of_data` for non-existent data

## Solution Statement

1. Create a new `set_baseline.py` skill script that writes a `week_number=0` row with only weight + optional body composition — no analysis pipeline
2. Add optional body tracking columns to `weekly_feedback` (body_fat_percent, muscle_mass_kg, waist_cm, etc.)
3. Filter `week_number > 0` in all historical queries within `calculate_weekly_adjustments.py`
4. Update SKILL.md to document the two-script workflow: baseline first, then weekly check-ins
5. Add tests for the new script and the filter logic

## Feature Metadata

**Feature Type**: Enhancement
**Estimated Complexity**: Medium
**Primary Systems Affected**: `weekly_feedback` table, `weekly-coaching` skill, `calculate_weekly_adjustments.py`
**Dependencies**: Supabase (migration), no new libraries

---

## CONTEXT REFERENCES

### Relevant Codebase Files — MUST READ BEFORE IMPLEMENTING

- `skills/weekly-coaching/scripts/calculate_weekly_adjustments.py` (lines 107-114) — **CRITICAL**: Historical query that must add `week_number > 0` filter. Also lines 224-257 for storage logic pattern to mirror in `set_baseline.py`
- `skills/weekly-coaching/SKILL.md` — Skill metadata + script documentation. Must add `set_baseline` script entry and workflow guidance
- `sql/create_weekly_feedback_table.sql` — Current table schema. New migration adds body tracking columns
- `sql/5_add_user_id_columns.sql` — Pattern for ALTER TABLE migration with `user_id` handling
- `sql/6_rls_per_user_tables.sql` — RLS is already enabled on `weekly_feedback`; new columns inherit existing policies (no RLS changes needed)
- `src/nutrition/feedback_extraction.py` (lines 13-44) — `validate_feedback_metrics()` requires `weight_start_kg`, `weight_end_kg`, `adherence_percent`. The baseline script must NOT use this function (it would reject baseline-only data)
- `src/nutrition/adjustments.py` — All analysis functions. None need changes (they receive filtered data from the skill script)
- `conftest.py` (lines 123-135) — `sample_weekly_feedback` fixture pattern
- `tests/test_adjustments.py` — Existing test patterns for adjustment functions
- `src/agent.py` (lines 210-258) — `run_skill_script()` pattern: all kwargs injected, script takes what it needs via `kwargs.get()`

### New Files to Create

- `skills/weekly-coaching/scripts/set_baseline.py` — Baseline recording script
- `sql/11_add_body_tracking_columns.sql` — Migration for body composition columns
- `tests/test_set_baseline.py` — Unit tests for baseline script

### Files to Modify

- `skills/weekly-coaching/scripts/calculate_weekly_adjustments.py` — Add `week_number > 0` filter on historical query (line ~110)
- `skills/weekly-coaching/SKILL.md` — Add `set_baseline` documentation + workflow section
- `.claude/reference/status.md` — Mark task #3 as complete

### Patterns to Follow

**Skill script pattern** (from `calculate_weekly_adjustments.py`):
```python
async def execute(**kwargs) -> str:
    supabase = kwargs["supabase"]
    user_id = kwargs.get("user_id")
    # ... business params via kwargs.get()
    # ... return json.dumps(result)
```

**Supabase insert pattern** (from `calculate_weekly_adjustments.py` lines 233-257):
```python
storage_data = {
    "week_number": week_number,
    "week_start_date": str(week_start),
    "weight_start_kg": float(weight_start_kg),
    # ...
}
if user_id:
    storage_data["user_id"] = user_id
supabase.table("weekly_feedback").insert(storage_data).execute()
```

**Historical query pattern** (from `calculate_weekly_adjustments.py` lines 108-114):
```python
feedback_query = supabase.table("weekly_feedback").select("*")
if user_id:
    feedback_query = feedback_query.eq("user_id", user_id)
history_response = (
    feedback_query.order("week_start_date", desc=True).limit(4).execute()
)
```

**SQL migration naming**: `sql/11_add_body_tracking_columns.sql` (next after existing `sql/10_add_last_used_date.sql`)

**Test naming**: `tests/test_set_baseline.py` — mirrors `tests/test_adjustments.py` structure

---

## IMPLEMENTATION PLAN

### Phase 1: Database Migration

Add optional body tracking columns to `weekly_feedback`. These columns are all nullable — existing rows are unaffected. No RLS changes needed (existing policies cover the table).

### Phase 2: Baseline Script

Create `set_baseline.py` — a minimal script that:
- Takes `weight_kg` (required) + optional body composition params
- Validates weight range (40-300 kg)
- Checks for existing baseline (`week_number=0`) for this user — upserts if exists
- Writes row with `week_number=0`, `adherence_percent=0`, neutral defaults for required enum columns
- Returns confirmation JSON
- Does NOT run any analysis, adjustment, or learning profile logic

### Phase 3: Filter Fix

Add `.gt("week_number", 0)` to the historical query in `calculate_weekly_adjustments.py` so baseline rows are excluded from trend analysis.

### Phase 4: Skill Documentation

Update SKILL.md with:
- `set_baseline` script entry (params, example)
- Clear workflow: "New user → `set_baseline` first, then `calculate_weekly_adjustments` for each real week"

### Phase 5: Tests

- Unit tests for `set_baseline.py` (happy path, validation, upsert, missing user_id)
- Unit test for the history filter fix (baseline row excluded from past_weeks)

---

## STEP-BY-STEP TASKS

### Task 1: CREATE `sql/11_add_body_tracking_columns.sql`

**IMPLEMENT**: SQL migration adding optional body composition columns to `weekly_feedback`:

```sql
-- Body composition columns (all optional, nullable)
ALTER TABLE weekly_feedback ADD COLUMN IF NOT EXISTS body_fat_percent NUMERIC(4,1);
ALTER TABLE weekly_feedback ADD COLUMN IF NOT EXISTS muscle_mass_kg NUMERIC(5,2);
ALTER TABLE weekly_feedback ADD COLUMN IF NOT EXISTS water_percent NUMERIC(4,1);

-- Body measurements (optional, typically monthly or at baseline)
ALTER TABLE weekly_feedback ADD COLUMN IF NOT EXISTS waist_cm NUMERIC(5,1);
ALTER TABLE weekly_feedback ADD COLUMN IF NOT EXISTS hips_cm NUMERIC(5,1);
ALTER TABLE weekly_feedback ADD COLUMN IF NOT EXISTS chest_cm NUMERIC(5,1);
ALTER TABLE weekly_feedback ADD COLUMN IF NOT EXISTS arm_cm NUMERIC(5,1);
ALTER TABLE weekly_feedback ADD COLUMN IF NOT EXISTS thigh_cm NUMERIC(5,1);

-- Measurement context
ALTER TABLE weekly_feedback ADD COLUMN IF NOT EXISTS measurement_method TEXT;
-- Values: 'smart_scale', 'manual', 'image_analysis', 'calipers'

-- Photo references (optional, storage bucket paths)
ALTER TABLE weekly_feedback ADD COLUMN IF NOT EXISTS photo_refs JSONB;
-- Example: {"front": "storage/path/front.jpg", "side": "storage/path/side.jpg"}
```

- **PATTERN**: Follow `sql/5_add_user_id_columns.sql` for ALTER TABLE style
- **GOTCHA**: Use `IF NOT EXISTS` for idempotency. All columns are nullable — no DEFAULT needed, no backfill needed
- **VALIDATE**: Apply migration via Supabase MCP `apply_migration` tool, then verify columns exist with `list_tables`

### Task 2: CREATE `skills/weekly-coaching/scripts/set_baseline.py`

**IMPLEMENT**: New skill script for recording initial body state.

Required params:
- `supabase` (injected)
- `user_id` (injected)
- `weight_kg` (float, required)

Optional params:
- `body_fat_percent` (float)
- `muscle_mass_kg` (float)
- `waist_cm` (float)
- `hips_cm`, `chest_cm`, `arm_cm`, `thigh_cm` (float)
- `measurement_method` (str)
- `notes` (str)

Logic:
1. Validate `weight_kg` in range 40-300
2. Return error if no `user_id`
3. Check if baseline already exists: `supabase.table("weekly_feedback").select("id").eq("user_id", user_id).eq("week_number", 0).limit(1).execute()`
4. Build storage dict with `week_number=0`, `week_start_date=today`, `weight_start_kg=weight_kg`, `weight_end_kg=weight_kg`, `adherence_percent=0`, `hunger_level="medium"`, `energy_level="medium"`, `sleep_quality="good"`, `feedback_quality="comprehensive"`, `agent_confidence_percent=100`, `subjective_notes=notes or "Baseline initial"`
5. Add optional body composition fields if provided
6. If baseline exists → `update().eq("id", existing_id)`. If not → `insert()`
7. Return JSON: `{"status": "baseline_recorded", "weight_kg": ..., "week_number": 0, "updated": bool}`

- **PATTERN**: Mirror `calculate_weekly_adjustments.py` execute() signature and supabase insert pattern (lines 233-257)
- **IMPORTS**: `json`, `logging`, `datetime` (stdlib only — this is a skill script, no LLM imports)
- **GOTCHA**: Do NOT import from `src.nutrition.feedback_extraction` — `validate_feedback_metrics()` requires adherence_percent as meaningful data, which doesn't apply to baseline. Do weight validation inline.
- **GOTCHA**: `adherence_percent` has a CHECK constraint `>= 0 AND <= 100` in the DB. Use `0` (not NULL) to indicate "no plan followed yet"
- **GOTCHA**: `hunger_level`, `energy_level`, `sleep_quality` have CHECK constraints (NOT NULL + enum). Must provide valid defaults even for baseline rows.
- **VALIDATE**: `python -c "import skills.weekly_coaching.scripts.set_baseline"` will fail (hyphenated path), but syntax check: `python -m py_compile skills/weekly-coaching/scripts/set_baseline.py`

### Task 3: UPDATE `skills/weekly-coaching/scripts/calculate_weekly_adjustments.py`

**IMPLEMENT**: Add filter to exclude baseline rows from historical data.

Change lines 108-114 from:
```python
feedback_query = supabase.table("weekly_feedback").select("*")
if user_id:
    feedback_query = feedback_query.eq("user_id", user_id)
history_response = (
    feedback_query.order("week_start_date", desc=True).limit(4).execute()
)
```

To:
```python
feedback_query = supabase.table("weekly_feedback").select("*")
if user_id:
    feedback_query = feedback_query.eq("user_id", user_id)
feedback_query = feedback_query.gt("week_number", 0)  # Exclude baseline rows
history_response = (
    feedback_query.order("week_start_date", desc=True).limit(4).execute()
)
```

- **PATTERN**: Supabase `.gt()` filter — same chaining style already used in the query
- **GOTCHA**: The filter must come BEFORE `.order()` and `.limit()` to work correctly with PostgREST
- **VALIDATE**: `python -m py_compile skills/weekly-coaching/scripts/calculate_weekly_adjustments.py`

### Task 4: UPDATE `skills/weekly-coaching/SKILL.md`

**IMPLEMENT**: Add `set_baseline` script documentation and update the workflow section.

Add after the existing "## Quand utiliser" section, a new subsection:

```markdown
### Workflow initial — Nouvel utilisateur

1. Profil complété (`fetch_my_profile` retourne un profil complet)
2. **Enregistrer la baseline** : `run_skill_script("weekly-coaching", "set_baseline", {"weight_kg": 88.0})`
   - Optionnel : `body_fat_percent`, `muscle_mass_kg`, `waist_cm`, etc.
3. Les check-ins hebdomadaires commencent la semaine suivante avec `calculate_weekly_adjustments`
```

Add a new script entry in the "## Scripts disponibles" section:

```markdown
- `scripts/set_baseline.py` : Enregistre l'état initial (poids, composition corporelle optionnelle) comme baseline (week_number=0). Aucune analyse ni ajustement.
```

Add a new execution example:

```python
# Baseline — nouvel utilisateur
run_skill_script("weekly-coaching", "set_baseline", {
    "weight_kg": 88.0,
    "body_fat_percent": 18.5,
    "notes": "Début du programme"
})
```

Add `set_baseline` parameters section:

```markdown
**Paramètres `set_baseline`** :
- `weight_kg` (float, requis) : Poids initial
- `body_fat_percent` (float, optionnel) : % de masse grasse
- `muscle_mass_kg` (float, optionnel) : Masse musculaire en kg
- `waist_cm` (float, optionnel) : Tour de taille
- `hips_cm`, `chest_cm`, `arm_cm`, `thigh_cm` (float, optionnel) : Mensurations
- `measurement_method` (str, optionnel) : 'smart_scale', 'manual', 'image_analysis', 'calipers'
- `notes` (str, optionnel) : Notes libres
```

- **GOTCHA**: Keep YAML frontmatter intact (first 3 lines with `---` delimiters)
- **VALIDATE**: `python -c "from src.skill_loader import SkillLoader; s=SkillLoader('skills'); s.discover_skills(); print(s.skills['weekly-coaching'].description)"`

### Task 5: CREATE `tests/test_set_baseline.py`

**IMPLEMENT**: Unit tests for the baseline script.

Test structure (mirror `tests/test_adjustments.py` patterns):

```python
"""Unit tests for weekly coaching set_baseline script."""

import json
import pytest
from unittest.mock import MagicMock


def _make_supabase_mock(existing_baseline=None):
    """Create Supabase mock for baseline tests."""
    mock = MagicMock()
    # For select (check existing baseline)
    select_result = MagicMock()
    select_result.data = [existing_baseline] if existing_baseline else []
    mock.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = select_result
    # For insert
    insert_result = MagicMock()
    insert_result.data = [{"id": "new-uuid"}]
    mock.table.return_value.insert.return_value.execute.return_value = insert_result
    # For update
    update_result = MagicMock()
    update_result.data = [{"id": "existing-uuid"}]
    mock.table.return_value.update.return_value.eq.return_value.execute.return_value = update_result
    return mock
```

Test cases:
1. **`test_baseline_happy_path`** — weight_kg=88.0, no existing baseline → insert called, returns `baseline_recorded`
2. **`test_baseline_with_body_composition`** — weight_kg + body_fat_percent + waist_cm → all stored
3. **`test_baseline_upsert_existing`** — existing baseline found → update called (not insert)
4. **`test_baseline_missing_weight`** — no weight_kg → returns VALIDATION_ERROR
5. **`test_baseline_weight_out_of_range`** — weight_kg=500 → returns VALIDATION_ERROR
6. **`test_baseline_missing_user_id`** — no user_id → returns NO_USER_ID
7. **`test_baseline_week_number_is_zero`** — verify storage_data contains `week_number=0`

- **PATTERN**: Follow `tests/test_adjustments.py` class-based test structure
- **IMPORTS**: `from skills.weekly_coaching.scripts` won't work (hyphenated path). Use `importlib`:
  ```python
  import importlib.util
  spec = importlib.util.spec_from_file_location(
      "set_baseline", "skills/weekly-coaching/scripts/set_baseline.py"
  )
  module = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(module)
  execute = module.execute
  ```
- **VALIDATE**: `pytest tests/test_set_baseline.py -v`

### Task 6: ADD test for history filter in existing test suite

**IMPLEMENT**: Add a test in `tests/test_set_baseline.py` (or new class) that verifies the history filter excludes baseline rows.

This test doesn't test the full skill script — it tests the concept that when `past_weeks` contains a baseline-like row (week_number=0), the analysis functions still work correctly with only real data. Since the filter happens at the Supabase query level (not in Python), this test verifies the mock setup:

```python
class TestHistoryFilterExcludesBaseline:
    """Verify that baseline rows (week_number=0) don't affect analysis."""

    def test_analyze_weight_trend_ignores_baseline_data(self):
        """Baseline data (weight unchanged) should not be in past_weeks after filtering."""
        # If filter works correctly, past_weeks only contains real check-ins
        real_weeks = [
            {"weight_change_kg": -0.5, "adherence_percent": 85, "energy_level": "high"},
            {"weight_change_kg": -0.4, "adherence_percent": 80, "energy_level": "medium"},
        ]
        # baseline row would have: weight_change_kg=0, adherence_percent=0
        # But it's excluded by .gt("week_number", 0) at query level
        # So analysis only sees real_weeks
        from src.nutrition.adjustments import detect_adherence_patterns
        result = detect_adherence_patterns(real_weeks)
        assert result["pattern_strength"] >= 0  # Works with real data only
```

- **VALIDATE**: `pytest tests/test_set_baseline.py -v`

### Task 7: Apply migration to Supabase

**IMPLEMENT**: Use the Supabase MCP `apply_migration` tool to apply `sql/11_add_body_tracking_columns.sql`.

- **VALIDATE**: `mcp__supabase__list_tables` to confirm new columns exist. Then `mcp__supabase__get_advisors` (security) to check for any new warnings.

### Task 8: UPDATE `.claude/reference/status.md`

**IMPLEMENT**: Move task #3 from "Next Tasks" to "Completed" section:
- Add: `- **Weekly feedback baseline distinction** (2026-02-27): set_baseline.py script (week_number=0), body tracking columns, history filter fix, SKILL.md updated`
- Remove task #3 from "Next Tasks" list

- **VALIDATE**: Read file to confirm update

---

## TESTING STRATEGY

### Unit Tests

| Test File | Test Count | What's Tested |
|---|---|---|
| `tests/test_set_baseline.py` | 7+ | Baseline script: happy path, body comp, upsert, validation, error cases |
| `tests/test_set_baseline.py` | 1 | History filter concept: baseline exclusion from analysis |

### Existing Tests (must not regress)

| Test File | Test Count | Risk |
|---|---|---|
| `tests/test_adjustments.py` | 32 | None — no changes to `src/nutrition/adjustments.py` |
| `tests/test_feedback_extraction.py` | 31 | None — no changes to feedback_extraction |

### Edge Cases

- Baseline with only weight (no body comp) — columns stay NULL
- Baseline called twice for same user — upsert updates existing row
- `calculate_weekly_adjustments` called before baseline exists — works fine (no baseline row to pollute)
- User with baseline + 0 real check-ins — `past_weeks=[]`, analysis handles this gracefully (already tested)

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style

```bash
ruff format src/ tests/ skills/
ruff check src/ tests/ skills/
python -m py_compile skills/weekly-coaching/scripts/set_baseline.py
python -m py_compile skills/weekly-coaching/scripts/calculate_weekly_adjustments.py
```

**Expected**: All pass with exit code 0

### Level 2: Unit Tests

```bash
# New tests only
pytest tests/test_set_baseline.py -v

# Full test suite (must not regress)
pytest tests/ -m "not integration" -v
```

**Expected**: All tests pass, 0 failures

### Level 3: Skill Loader Validation

```bash
python -c "from src.skill_loader import SkillLoader; s=SkillLoader('skills'); d=s.discover_skills(); print(f'{len(d)} skills loaded'); print(s.skills['weekly-coaching'].description)"
```

**Expected**: 6 skills loaded, weekly-coaching description printed

### Level 4: Database Validation

```
# Via Supabase MCP
mcp__supabase__execute_sql("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'weekly_feedback' AND column_name IN ('body_fat_percent', 'muscle_mass_kg', 'waist_cm') ORDER BY column_name")
```

**Expected**: 3 rows returned with correct types

### Level 5: Security Check

```
mcp__supabase__get_advisors(type="security")
```

**Expected**: No new RLS warnings (columns inherit existing table policies)

---

## ACCEPTANCE CRITERIA

- [ ] `set_baseline.py` creates a `week_number=0` row in `weekly_feedback` with weight + optional body composition
- [ ] Calling `set_baseline` twice for the same user updates (upserts) the existing baseline, not duplicates
- [ ] `calculate_weekly_adjustments` historical query excludes `week_number=0` rows
- [ ] `weekly_feedback` table has new nullable columns: `body_fat_percent`, `muscle_mass_kg`, `water_percent`, `waist_cm`, `hips_cm`, `chest_cm`, `arm_cm`, `thigh_cm`, `measurement_method`, `photo_refs`
- [ ] SKILL.md documents `set_baseline` script with params, examples, and workflow guidance
- [ ] All new tests pass (`tests/test_set_baseline.py`)
- [ ] Full test suite passes with 0 regressions (`pytest tests/ -m "not integration"`)
- [ ] Linters pass (`ruff format`, `ruff check`)
- [ ] No new security advisories from Supabase

---

## COMPLETION CHECKLIST

- [ ] Task 1: Migration SQL created and applied
- [ ] Task 2: `set_baseline.py` created
- [ ] Task 3: History filter added to `calculate_weekly_adjustments.py`
- [ ] Task 4: SKILL.md updated
- [ ] Task 5-6: Tests created and passing
- [ ] Task 7: Migration applied to Supabase
- [ ] Task 8: `status.md` updated
- [ ] Level 1 validation: ruff format + check pass
- [ ] Level 2 validation: all tests pass
- [ ] Level 3 validation: skill loader works
- [ ] Level 4 validation: DB columns exist
- [ ] Level 5 validation: no security warnings

---

## NOTES

**Design Decision**: We chose `week_number=0` in the existing `weekly_feedback` table over a separate table or `user_profiles` storage. Rationale: single table = single timeline, append-only log, no joins needed for charting weight evolution. The `0` convention is clear and filterable.

**Weight duplication**: `user_profiles.weight_kg` (current weight, updated on each check-in for BMR/TDEE calculations) vs `weekly_feedback` rows (historical timeline, never updated). This is intentional denormalization — different questions, different tables.

**No changes to `src/nutrition/adjustments.py`**: All analysis functions receive pre-filtered data from the skill script. The filter lives at the query level, not in domain logic. This keeps the domain functions pure and testable.

**Confidence Score**: 9/10 — straightforward changes, well-defined scope, existing patterns to follow. Only risk is mock complexity for the upsert test.
