# Plan: Project Audit Fixes (2026-03-11 v4)

## Context
Auto-generated from audit report `.claude/audits/audit-2026-03-11-0823.md`.
Supersedes previous audit fix plans.
3 critical, 12 high, 15 medium findings. Low-severity items in NOTES only.

---

## Phase 1 — Critical Fixes

### Task 1.1: Sanitize user query at entry point, before DB writes
- ACTION: Edit `src/api.py`
- IMPLEMENT: Move `sanitize_user_text(request.query, 5000, "agent_query")` to the top of `agent_endpoint()`, before `store_request()`, `store_message()`, `mem0_client.search()`, and `generate_conversation_title()`. Use `sanitized_query` everywhere downstream. Remove the redundant sanitization block inside `_stream_agent_response()`. Also apply `sanitize_user_text()` to the `q` parameter in the `/api/food-search` endpoint.
- VALIDATE: `pytest tests/ -x -q` + manually test agent endpoint with a long string containing XML tags

### Task 1.2: Harden `POST /api/recipes` — Atwater validation + correct source label
- ACTION: Edit `src/api.py`
- IMPLEMENT: Two changes in the `upsert_recipe` endpoint:
  1. **Add Atwater macro validation** before insert — import `_passes_atwater_check` from `src.nutrition.openfoodfacts_client` and reject recipes where `calories ≈ protein*4 + carbs*4 + fat*9` fails (>30% discrepancy). Return 422 with `"Données nutritionnelles incohérentes"`.
  2. **Change `source` from `"user_validated"` to `"user_saved"`** — this label is used only for recipes saved via the favorites flow (already validated by the agent pipeline). Distinguishes them from curated/OFF-validated recipes.
- CONTEXT: This endpoint is called by the frontend when a user favorites a meal from a plan. The meal data is already OFF-validated by the agent pipeline, so the Atwater check is a defense-in-depth guard against direct API calls with falsified macros. No admin check needed — users need this flow.
- VALIDATE: `pytest tests/ -x -q` + test with coherent macros (passes) and falsified macros (422)

### Task 1.3: Add safety calorie floor in nutrition-calculating skill script
- ACTION: Edit `skills/nutrition-calculating/scripts/calculate_nutritional_needs.py`
- IMPLEMENT: After computing `target_calories`, add:
  ```python
  from src.nutrition.constants import MIN_CALORIES_WOMEN, MIN_CALORIES_MEN
  min_cal = MIN_CALORIES_WOMEN if gender == "female" else MIN_CALORIES_MEN
  target_calories = max(target_calories, min_cal)
  ```
- VALIDATE: `pytest tests/ -x -q` + write a quick test confirming a sedentary female on weight_loss gets >= 1200

---

## Phase 2 — High-Priority Fixes

### Task 2.1: Add RLS migration for `requests` table
- ACTION: Create `sql/16_rls_requests_table.sql`
- IMPLEMENT: `ALTER TABLE requests ENABLE ROW LEVEL SECURITY;` + per-user SELECT/INSERT policies + admin read-all policy + deny UPDATE/DELETE
- VALIDATE: Apply migration via Supabase MCP `apply_migration`

### Task 2.2: Use `_require_supabase()` as FastAPI dependency
- ACTION: Edit `src/api.py`
- IMPLEMENT: Convert `_require_supabase()` to a FastAPI `Depends` that returns the client or raises `503 Service Unavailable`. Inject into all endpoints that use `supabase`.
- VALIDATE: `pytest tests/ -x -q`

### Task 2.3: Replace `.single()` with `.limit(1)` in log_food_entries
- ACTION: Edit `skills/food-tracking/scripts/log_food_entries.py`
- IMPLEMENT: Replace `.single()` with `.limit(1)` on line 98-99
- VALIDATE: `pytest tests/test_log_food_entries.py -x -q`

### Task 2.4: Fix hardcoded UUID in weekly-coaching upsert
- ACTION: Edit `skills/weekly-coaching/scripts/calculate_weekly_adjustments.py`
- IMPLEMENT: Remove `LEARNING_PROFILE_UUID`. Upsert on `user_id` with `on_conflict="user_id"` instead of hardcoded `id`.
- VALIDATE: `pytest tests/ -x -q`

### Task 2.5: Fix naive `datetime.now()` — weekly-coaching (3 occurrences)
- ACTION: Edit `skills/weekly-coaching/scripts/calculate_weekly_adjustments.py`
- IMPLEMENT: Replace `datetime.now()` with `datetime.now(timezone.utc)` on lines 231, 270, 286. Add `from datetime import timezone`.
- VALIDATE: `pytest tests/ -x -q`

### Task 2.6: Fix naive `datetime.now()` — week-plan generation (2 occurrences)
- ACTION: Edit `skills/meal-planning/scripts/generate_week_plan.py`
- IMPLEMENT: Replace `datetime.now()` with `datetime.now(timezone.utc)` on lines 77, 223.
- VALIDATE: `pytest tests/ -x -q`

### Task 2.7: Replace raw error string with French fallback in MessageHandling
- ACTION: Edit `frontend/src/components/chat/MessageHandling.tsx`
- IMPLEMENT: Replace `content: \`Error: ${errorMessage}\`` with `content: "Une erreur est survenue. Veuillez réessayer."`. Log the actual error with `logger.error`.
- VALIDATE: `cd frontend && npx tsc --noEmit`

### Task 2.8: Fix hooks deps in useConversations
- ACTION: Edit `frontend/src/components/admin/conversations/useConversations.ts`
- IMPLEMENT: Wrap `fetchConversations` in `useCallback` with proper deps. Remove `eslint-disable` comment.
- VALIDATE: `cd frontend && npx tsc --noEmit`

### Task 2.9: Fix hooks deps in UsersTable
- ACTION: Edit `frontend/src/components/admin/UsersTable.tsx`
- IMPLEMENT: Wrap `fetchUsers` in `useCallback`. Remove `eslint-disable` comment.
- VALIDATE: `cd frontend && npx tsc --noEmit`

### Task 2.10: Route admin profile edits through backend API
- ACTION: Edit `frontend/src/components/admin/UsersTable.tsx`
- IMPLEMENT: Remove direct client-side Supabase `user_profiles.email` update. Route through a backend API endpoint with server-side admin validation.
- VALIDATE: `cd frontend && npx tsc --noEmit`

### Task 2.11: Enable production error logging
- ACTION: Edit `frontend/src/lib/logger.ts`
- IMPLEMENT: Always log errors regardless of env: `error: (...args: unknown[]) => console.error(...args)`
- VALIDATE: `cd frontend && npx tsc --noEmit`

### Task 2.12: Clear adminCache on sign-out
- ACTION: Edit `frontend/src/App.tsx`
- IMPLEMENT: In `onAuthStateChange`, add `if (event === 'SIGNED_OUT') adminCache.clear();`
- VALIDATE: `cd frontend && npx tsc --noEmit`

---

## Phase 3 — Medium-Priority Fixes

### Task 3.1: Add `max_length` constraints to Pydantic model string fields
- ACTION: Edit `src/api_models.py`
- IMPLEMENT: Add `Field(..., max_length=N)` to `food_name` (200), `meal_type` (50), `unit` (30), `source` (50), `title` (200), `name` (200), `category` (50).
- VALIDATE: `pytest tests/ -x -q`

### Task 3.2: Fix rate limiter to fail open on DB errors
- ACTION: Edit `src/api.py`
- IMPLEMENT: In `check_rate_limit` exception handler, return `(True, None)` instead of `(False, error_message)`.
- VALIDATE: `pytest tests/ -x -q`

### Task 3.3: Move 4 tunable constants from `generate_day_plan.py` to `constants.py`
- ACTION: Edit `skills/meal-planning/scripts/generate_day_plan.py` + `src/nutrition/constants.py`
- IMPLEMENT: Move `MAX_RETRIES`, `LLM_FALLBACK_WARN_THRESHOLD`, `CALORIE_RANGE_MIN_DIVISOR`, `CALORIE_RANGE_MAX_MULTIPLIER` to `constants.py`. Import in `generate_day_plan.py`.
- VALIDATE: `pytest tests/ -x -q`

### Task 3.4: Move `SNACK_STRUCTURE_CALORIE_THRESHOLD` to `constants.py`
- ACTION: Edit `skills/meal-planning/scripts/generate_week_plan.py` + `src/nutrition/constants.py`
- IMPLEMENT: Move `SNACK_STRUCTURE_CALORIE_THRESHOLD = 2500` to `constants.py`. Import in `generate_week_plan.py`.
- VALIDATE: `pytest tests/ -x -q`

### Task 3.5: Replace bare `assert` with explicit guard in MILP optimizer
- ACTION: Edit `src/nutrition/portion_optimizer_v2.py`
- IMPLEMENT: Replace `assert per_meal_targets is not None` with `if per_meal_targets is None: raise ValueError("per_meal_targets required when use_meal_balance=True")`
- VALIDATE: `pytest tests/test_portion_optimizer_v2.py -x -q`

### Task 3.6: Optimize N+1 DB queries in food-tracking loop
- ACTION: Edit `skills/food-tracking/scripts/log_food_entries.py`
- IMPLEMENT: Use upsert with ON CONFLICT clause instead of per-item SELECT+INSERT/UPDATE loop. Or batch the SELECT queries with `asyncio.gather`.
- VALIDATE: `pytest tests/test_log_food_entries.py -x -q`

### Task 3.7: Localize admin UI strings to French
- ACTION: Edit `frontend/src/components/admin/UsersTable.tsx`, `useConversations.ts`, `ConversationRow.tsx`, `SearchBar.tsx`
- PREREQUISITE: Run /frontend-design first
- IMPLEMENT: Translate all English user-visible strings to French.
- VALIDATE: `cd frontend && npx tsc --noEmit` + visual check

### Task 3.8: Remove dead `setConversations` export
- ACTION: Edit `frontend/src/components/chat/ConversationManagement.tsx`
- IMPLEMENT: Remove `setConversations` from the hook's return value.
- VALIDATE: `cd frontend && npx tsc --noEmit`

### Task 3.9: Remove unused `message_data` from frontend types
- ACTION: Edit `frontend/src/types/database.types.ts`
- IMPLEMENT: Remove `message_data: string | null` from Row, Insert, and Update types for messages.
- VALIDATE: `cd frontend && npx tsc --noEmit`

### Task 3.10: Move deterministic tests from `evals/` to `tests/`
- ACTION: Move `evals/test_skill_loading.py` → `tests/test_skill_loading.py`, `evals/test_skill_scripts.py` → `tests/test_skill_scripts.py`
- VALIDATE: `pytest tests/test_skill_loading.py tests/test_skill_scripts.py -x -q`

### Task 3.11: Add `TEST_USER_PROFILE` to 3 eval files
- ACTION: Edit `evals/test_meal_pipeline_e2e.py`, `evals/test_milp_optimizer_e2e.py`, `evals/test_meal_plan_quality_e2e.py`
- IMPLEMENT: Add `TEST_USER_PROFILE` dict constant at top of each file with all required fields.
- VALIDATE: `pytest evals/test_meal_pipeline_e2e.py --co -q` (collect-only to check imports)

### Task 3.12: Move MealCard obligation from `prompt.py` to skill SKILL.md
- ACTION: Edit `src/prompt.py` + `skills/meal-planning/SKILL.md`
- IMPLEMENT: Remove MealCard-specific rule (lines 136-143) from `prompt.py`. Add equivalent rule to `skills/meal-planning/SKILL.md` and `skills/knowledge-searching/SKILL.md`.
- VALIDATE: `pytest tests/ -x -q`

### Task 3.13: Remove `MEAL_STRUCTURES` re-export from `meal_planning.py`
- ACTION: Edit `src/nutrition/meal_planning.py` + `tests/test_meal_planning.py`
- IMPLEMENT: Remove line 11 (`from src.nutrition.meal_distribution import MEAL_STRUCTURES  # noqa: F401`). Update test import to use `from src.nutrition.meal_distribution import MEAL_STRUCTURES`.
- VALIDATE: `pytest tests/test_meal_planning.py -x -q`

### Task 3.14: Enable `noUnusedLocals`/`noUnusedParameters` in tsconfig.app.json
- ACTION: Edit `frontend/tsconfig.app.json`
- IMPLEMENT: Set both to `true` (or remove lines to inherit from root tsconfig). Fix any resulting compiler errors.
- VALIDATE: `cd frontend && npx tsc --noEmit`

### Task 3.15: Move real LLM tests from `tests/` to `evals/`
- ACTION: Move integration methods from `tests/test_agent_basic.py` → `evals/test_agent_e2e.py`, move `@pytest.mark.integration` methods from `tests/test_user_stories_e2e.py` → `evals/test_user_stories_e2e.py`
- IMPLEMENT: Keep deterministic `FunctionModel` tests in `tests/`. Move real-LLM tests to `evals/`.
- VALIDATE: `pytest tests/ -x -q` (should pass without API credentials)

---

## NOTES — Low-Priority (awareness only)

- **L1**: Truncate `user_query` at insert in `store_request` (`db_utils.py:275`) — defense-in-depth after C1 fix
- **L2**: Hardcoded UUID in `sql/5_add_user_id_columns.sql` — already applied, add comment
- **L3**: Global `_shared_clients` init pattern in `agent.py:471` — fragile but GIL-safe for now
- **L4**: Dead `kwargs.get("embedding_client")` in `calculate_weekly_adjustments.py:53` — remove
- **L5**: Inline `import re as _re` in `api.py:1336` — move to module level
- **L6**: Session ID entropy in `db_utils.py:112` — increase to `token_urlsafe(16)`
- **L7**: Arbitrary `setTimeout(100)` in `MessageHandling.tsx:240` — remove or restructure
- **L8**: `React.useEffect` vs named import in `ChatLayout.tsx:52` — standardize
- **L9**: Dead `round_quantity_smart` re-export in `meal_plan_optimizer.py:24` — delete line
- **L10**: `sys.path.insert` hack in `test_sliding_budget.py:8` — use `importlib.util.spec_from_file_location`
