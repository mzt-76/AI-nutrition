# Plan: Project Audit Fixes (2026-03-10 v2)

## Context
Auto-generated from audit report `.claude/audits/audit-2026-03-10-2000.md`.
Supersedes the previous audit fix plan. Previous fixes (sanitize_user_text, Literal gender, implicit Optional, bare dict/list, MIME type, safety constants) have been verified as already completed.

---

## Phase 1 -- High-Priority Fixes

### Task 1.1: Move MACRO_TOLERANCE constants to constants.py
- ACTION: Edit `src/nutrition/constants.py`, `src/nutrition/validators.py`, `skills/meal-planning/scripts/generate_day_plan.py`
- IMPLEMENT:
  - Add new section "MACRO TOLERANCES" to `constants.py` with:
    - `MACRO_TOLERANCE_PROTEIN = 0.05`
    - `MACRO_TOLERANCE_FAT = 0.10`
    - `MACRO_TOLERANCE_CALORIES = 0.10`
    - `MACRO_TOLERANCE_CARBS = 0.20`
  - In `validators.py`, remove the 4 constant definitions (lines 119-122). Import from constants.py.
  - In `generate_day_plan.py`, update import from `src.nutrition.validators` to `src.nutrition.constants`
- VALIDATE: `pytest tests/test_generate_day_plan.py tests/test_validators.py -x`

### Task 1.2: Create RLS migration for conversations and messages
- ACTION: Create `sql/14_rls_conversations_messages.sql`
- IMPLEMENT:
  - Enable RLS on `conversations` and `messages` tables
  - `conversations`: SELECT/INSERT/UPDATE by `auth.uid() = user_id`
  - `messages`: SELECT/INSERT via session_id ownership (join to conversations or parse user_id from session_id format `{user_id}~{random}`)
  - Deny direct DELETE (API handles it with service key)
- NOTE: Verify current RLS state in Supabase console first. If already applied, this just version-controls it.
- VALIDATE: Test frontend conversations list and message loading still work

### Task 1.3: Create RLS migration for food log, favorites, shopping lists
- ACTION: Create `sql/15_rls_food_favorites_shopping.sql`
- IMPLEMENT:
  - Enable RLS on `daily_food_log`, `favorite_recipes`, `shopping_lists`
  - All: SELECT/INSERT/UPDATE/DELETE by `auth.uid() = user_id`
  - Admin override: SELECT for `is_admin()`
- NOTE: Same as 1.2 -- verify current state in Supabase console first.
- VALIDATE: Test frontend tracking and favorites tabs still work

### Task 1.4: Extract API models to separate file
- ACTION: Create `src/api_models.py`, edit `src/api.py`
- IMPLEMENT:
  - Move all Pydantic models (FileAttachment, AgentRequest, DailyLogCreate, DailyLogUpdate, FavoriteCreate, FavoriteUpdate, RecipeCreate, RecalculateRequest, ShoppingListItemModel, ShoppingListCreate, ShoppingListUpdate) to `src/api_models.py`
  - Update imports in `src/api.py`
- VALIDATE: `pytest tests/test_api.py tests/test_api_crud.py -x && ruff check src/`

---

## Phase 2 -- Medium-Priority Fixes

### Task 2.1: Update legacy typing imports in skill_loader.py
- ACTION: Edit `src/skill_loader.py`
- IMPLEMENT: Replace `Dict[str, SkillMetadata]` with `dict[str, SkillMetadata]`, `List[SkillMetadata]` with `list[SkillMetadata]`, `Optional[SkillMetadata]` with `SkillMetadata | None`. Remove `from typing import Dict, List, Optional`.
- VALIDATE: `ruff check src/skill_loader.py && pytest tests/test_skill_loader.py -x`

### Task 2.2: Update legacy typing in calculations.py
- ACTION: Edit `src/nutrition/calculations.py`
- IMPLEMENT: Replace `Dict[str, int]` with `dict[str, int]`. Change `from typing import Dict, Literal` to `from typing import Literal`.
- VALIDATE: `pytest tests/ -k "calc" -x`

### Task 2.3: Update legacy typing in macro_adjustments.py
- ACTION: Edit `src/nutrition/macro_adjustments.py`
- IMPLEMENT: Replace all `Dict[`, `List[` with `dict[`, `list[`. Remove unused typing imports.
- VALIDATE: `pytest tests/test_adjustments.py -x`

### Task 2.4: Move FAT_PCT_OF_TOTAL to constants.py
- ACTION: Edit `src/nutrition/constants.py`, `src/nutrition/calculations.py`
- IMPLEMENT: Add `FAT_PCT_OF_TOTAL: dict[str, float]` to constants.py. Import in calculations.py.
- VALIDATE: `pytest tests/ -k "calc" -x`

### Task 2.5: Add calorie_tolerance parameter to validate_meal_plan_macros
- ACTION: Edit `src/nutrition/validators.py`
- IMPLEMENT: Add `calorie_tolerance: float = 0.10` parameter. Replace `carbs_tolerance` usage for calorie bounds (line 505-506) with `calorie_tolerance`.
- VALIDATE: `pytest tests/test_validators.py -x`

### Task 2.6: Clean up fetchMessages unused parameter
- ACTION: Edit `frontend/src/lib/api.ts`, callers
- IMPLEMENT: Remove `_user_id` parameter from `fetchMessages`. Update callers in MessageHandling.tsx and useConversations.ts.
- NOTE: Only after verifying RLS is configured on messages table.
- VALIDATE: `cd frontend && npx tsc --noEmit`

### Task 2.7: Fix structure validation to check all meals
- ACTION: Edit `src/nutrition/validators.py`
- IMPLEMENT: In `validate_meal_plan_structure()` (line 621-623), replace single-meal check with loop over all meals. Change `meal = meals[0]` to `for meal_idx, meal in enumerate(meals):`.
- VALIDATE: `pytest tests/test_validators.py -x`

### Task 2.8: Remove committed venv from RAG_Pipeline
- ACTION: Edit `.gitignore`, run git rm
- IMPLEMENT: Add `src/RAG_Pipeline/venv/` to `.gitignore`. Run `git rm -r --cached src/RAG_Pipeline/venv/`.
- NOTE: Verify RAG_Pipeline has requirements.txt first.
- VALIDATE: `git status` shows venv removed from tracking

---

## NOTES -- Low-Priority (no dedicated tasks)

- **L1**: `validators.py` -- `find_worst_meal()` is a scoring function, not validation. Consider moving to `meal_planning.py` during next refactor.
- **L2**: `validators.py` -- `validate_allergens()` reimplements `matches_allergen()` logic. DRY refactor when touching allergen code.
- **L3**: `clients.py:47` -- `import logging` placed after constant definition. Move to top imports.
- **L4**: 4 eval files may be missing `TEST_USER_PROFILE`. Check `test_agent_e2e.py`, `test_meal_pipeline_e2e.py`, `test_milp_optimizer_e2e.py`, `test_skill_scripts.py`.

---

## Completed (from previous audit, verified)

- sanitize_user_text() created and applied at API boundary
- RecalculateRequest.gender changed to Literal["male", "female"]
- agent.py implicit Optional parameters fixed to T | None = None
- run_skill_script parameters use precise types (not bare dict/list)
- MIME type validation changed to exact set match
- Safety constants (MIN_CALORIES_*) centralized in constants.py
- skill-creator removed from _VALID_SKILLS
