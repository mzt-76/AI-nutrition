# Plan: Project Audit Fixes (2026-03-10 v3)

## Context
Auto-generated from audit report `.claude/audits/audit-2026-03-10-1600.md`.
Supersedes previous audit fix plans.

## Phase 1 — Critical Fixes

### Task 1.1: Validate MealCard props with Zod in MessageItem callback
- ACTION: Edit `frontend/src/components/chat/MessageItem.tsx`
- IMPLEMENT: In handleMealClick, validate comp.props using the MealCard Zod schema before casting. Return early if validation fails.
- VALIDATE: `cd frontend && npx tsc --noEmit`

### Task 1.2: Sanitize conversation title before DB storage
- ACTION: Edit `src/api.py`
- IMPLEMENT: Add `conversation_title = sanitize_user_text(conversation_title, 100, "conversation_title")` before `update_conversation_title()` around line 1385.
- VALIDATE: `pytest tests/ -k "conversation" -x`

### Task 1.3: Add UUID validation to /api/favorites/check
- ACTION: Edit `src/api.py`
- IMPLEMENT: Add `_validate_uuid(recipe_id)` after auth check in `check_favorite()`, before the Supabase query.
- VALIDATE: `pytest tests/ -k "favorite" -x`

## Phase 2 — High-Priority Fixes

### Task 2.1: Fix type annotations in feedback_extraction.py
- ACTION: Edit `src/nutrition/feedback_extraction.py`
- IMPLEMENT: (1) Add explicit type annotation for result dict at line 259. (2) Change energy_level/hunger_level to `tuple[str, float] | None`. (3) Initialize mood_indicators and stress_indicators as `list[str] = []`.
- VALIDATE: `mypy src/nutrition/feedback_extraction.py`

### Task 2.2: Fix implicit Optional in macro_adjustments.py
- ACTION: Edit `src/nutrition/macro_adjustments.py`
- IMPLEMENT: Change `user_allergens: list[str] = None` to `user_allergens: list[str] | None = None`.
- VALIDATE: `mypy src/nutrition/macro_adjustments.py`

### Task 2.3: Add TEST_USER_PROFILE to eval files
- ACTION: Edit `evals/test_agent_e2e.py`, `evals/test_calorie_floor_e2e.py`, `evals/test_fat_pct_disliked_foods_e2e.py`, `evals/test_multi_allergen_safety_e2e.py`, `evals/test_weight_loss_macros_e2e.py`
- IMPLEMENT: Add module-level TEST_USER_PROFILE constant with ALL required fields matching the inline persona.
- VALIDATE: `grep -l "TEST_USER_PROFILE" evals/*.py | wc -l` should match number of eval files

### Task 2.4: Pass user_id to create_agent_deps in eval files
- ACTION: Edit `evals/test_agent_e2e.py`, `evals/test_calorie_floor_e2e.py`, `evals/test_fat_pct_disliked_foods_e2e.py`, `evals/test_multi_allergen_safety_e2e.py`
- IMPLEMENT: Add TEST_USER_ID constant and pass `user_id=TEST_USER_ID` to all `create_agent_deps()` calls.
- VALIDATE: Run one eval to verify profile is correctly loaded

### Task 2.5: Extract SettingsModal sub-components
- ACTION: Edit `frontend/src/components/sidebar/SettingsModal.tsx`
- PREREQUISITE: Run /frontend-design to design the solution first
- IMPLEMENT: Extract ProfileSection, NutritionTargetSection, DietPreferencesSection. Move recalculation logic to custom hook.
- VALIDATE: `cd frontend && npx tsc --noEmit` + visual test desktop/mobile

### Task 2.6: Add Fragment key to ComponentRenderer zone map
- ACTION: Edit `frontend/src/components/generative-ui/ComponentRenderer.tsx`
- IMPLEMENT: Wrap inner zoneComponents.map in `<React.Fragment key={zone}>`.
- VALIDATE: `cd frontend && npx tsc --noEmit`

## Phase 3 — Medium-Priority Fixes

### Task 3.1: Add UUID validation to Pydantic models
- ACTION: Edit `src/api_models.py`
- IMPLEMENT: Add `Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")` to user_id in DailyLogCreate, FavoriteCreate, ShoppingListCreate. Same for request_id, recipe_id, meal_plan_id.
- VALIDATE: `pytest tests/ -k "api" -x`

### Task 3.2: Add UUID validation to query parameters
- ACTION: Edit `src/api.py`
- IMPLEMENT: Change `user_id: str` to `user_id: str = Query(..., pattern=...)` for /conversations, /meal-plans, /daily-log, /favorites endpoints.
- VALIDATE: `pytest tests/ -k "api" -x`

### Task 3.3: Replace regex ArgsJson parsing with json.loads
- ACTION: Edit `src/api.py`
- IMPLEMENT: Replace regex parsing with `json.loads()` or structured attribute access.
- VALIDATE: `mypy src/api.py` + manual test of agent streaming

### Task 3.4: Move hardcoded tolerances to constants.py
- ACTION: Edit `src/nutrition/constants.py` and `skills/meal-planning/scripts/generate_day_plan.py`
- IMPLEMENT: Add MACRO_RATIO_TOLERANCE_STRICT=0.20 and MACRO_RATIO_TOLERANCE_WIDE=0.50 to constants.py. Import in generate_day_plan.py.
- VALIDATE: `pytest tests/ -k "meal" -x`

### Task 3.5: Fix DayPlanCard React key
- ACTION: Edit `frontend/src/components/generative-ui/components/DayPlanCard.tsx`
- IMPLEMENT: Replace index-based key with stable key using recipe_name + meal_type.
- VALIDATE: `cd frontend && npx tsc --noEmit`

### Task 3.6: Remove unused imports in eval files
- ACTION: Edit `evals/test_multi_allergen_safety_e2e.py` (remove `import re`), `evals/test_skill_loading.py` (remove `Contains`)
- VALIDATE: `ruff check evals/`

### Task 3.7: Add division guard in adjustments.py
- ACTION: Edit `src/nutrition/adjustments.py`
- IMPLEMENT: Guard before line 153: `if weight_start_kg <= 0: weight_change_percent = 0.0`.
- VALIDATE: `pytest tests/ -k "adjustment" -x`

## NOTES — Low-Priority (awareness only)
- VARIETY_WEIGHT_FAVORITE additive bonus lacks bounds doc in score_recipe_variety()
- minute_resp.count in db_utils.py:247 typed as Any, works but could use explicit cast
- get_model() in agent.py doesn't distinguish "no API key" from "invalid key" errors
- Env var validation in api.py:118-124 could use Pydantic Settings
- ChatLayout useEffect for isGeneratingResponse could be computed directly
- Global vars in api.py:100-102 typed as Any, should be precise union types
- agent.py mypy union-attr errors — type narrowing needed for None checks
