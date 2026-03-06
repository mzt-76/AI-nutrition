# Code Review — Pre-Deployment Final Audit

## Summary Stats

- **Commit:** d7427bc (+ 12 unpushed commits, + uncommitted changes)
- **Files Modified:** 6 (skills/meal-planning/SKILL.md, skills/meal-planning/scripts/generate_week_plan.py, skills/shopping-list/SKILL.md, skills/shopping-list/scripts/generate_shopping_list.py, src/api.py, tests/test_api.py)
- **Files Added:** 2 (skills/shopping-list/scripts/generate_from_recipes.py, tests/test_generate_from_recipes.py, evals/test_recipe_shopping_list_routing.py)
- **Pre-flight:** ruff format ✅ | ruff check ⚠️ (26 errors, all pre-existing — RAG_Pipeline, cli.py, verify_setup.py, clients.py) | pytest 495/498 ✅ (3 failures = Anthropic rate limiting, not code bugs)

## Pre-flight Results

### Level 1: Syntax & Style (ruff)
```
74 files already formatted — OK
26 lint errors — ALL pre-existing in unchanged files:
  - src/RAG_Pipeline/ (4 errors)
  - src/cli.py (3 errors)
  - src/clients.py (2 errors — unused vars)
  - src/nutrition/adjustments.py (1 error — unused var)
  - src/verify_setup.py (5 errors)
  - tests/ (2 errors — unused imports)
None in changed files.
```

### Level 2: Tests
```
498 tests collected
495 passed, 3 failed (rate limit 429), 1 skipped, 1 warning
All 3 failures are Anthropic rate limit errors in real-LLM tests (test_agent_basic, test_user_stories_e2e).
Zero logic failures.
```

## Issues Found: 3

---

### Issue #1 — FIXED

**Severity:** critical
**Category:** Logic
**File:** `skills/meal-planning/scripts/generate_week_plan.py:158-170`
**Verified:** ✅ yes (NameError confirmed via reproduction)

**Issue:**
`num_days` referenced at line 160 before definition at line 170 — `NameError` when `start_date` is not provided.

**Detail:**
This is the most common usage path: user says "génère un plan pour la semaine" without specifying a date. The script would crash immediately. All existing tests passed `start_date` explicitly, so this was never caught.

**Fix applied:** Moved `num_days = int(kwargs.get("num_days", 1))` before the `if not start_date:` block.

**Verification:**
```
python -m pytest tests/test_generate_week_plan.py — 14/14 passed after fix
```

---

### Issue #2

**Severity:** low
**Category:** Quality
**File:** `skills/meal-planning/scripts/generate_week_plan.py`
**Verified:** ⚠️ probable

**Issue:**
No test covers the `start_date=None` code path (the one that was just fixed).

**Suggested Fix:**
Add a test case in `tests/test_generate_week_plan.py` that omits `start_date` and verifies the script doesn't crash. This is important given this was a critical bug hiding in plain sight.

---

### Issue #3

**Severity:** low
**Category:** Standards
**File:** `src/api.py:260-266` (list_conversations) and `src/api.py:288-295` (agent_endpoint)
**Verified:** ✅ yes

**Issue:**
Auth enforcement was inconsistent — `list_conversations` and `agent_endpoint` previously allowed unauthenticated access (`if auth_user and ...`). The uncommitted changes fix this correctly by splitting into `if not auth_user: 401` then `if id != user_id: 403`.

**Detail:**
This is already fixed in the current diff. Noting it as a positive change — all 15+ endpoints now follow the same 3-step auth pattern consistently. Tests updated to match (test_no_token_returns_401 replaces test_no_token_allows_request).

---

## Cross-cutting Concerns

### Architecture Coherence

**Skill system:** Clean separation. 7 skills, each self-contained with SKILL.md + scripts/ + references/. New `generate_from_recipes` script follows the same `async def execute(**kwargs) -> str` pattern. SKILL.md routing rules clearly document when to use which script.

**Auth pattern:** All API endpoints now consistently require auth (401) and verify ownership (403). No endpoint is unprotected. Good.

**Generative UI:** 7 components, all Zod-validated. `generate_custom_recipe` correctly emits `<!--UI:MealCard:...-->` marker. Pipeline: agent text → extract_ui_components → NDJSON stream → React ComponentRenderer.

**Test coverage:** New `generate_from_recipes` script has 9 unit tests covering happy path, aggregation, multiplier, empty inputs, missing recipes, partial matches, no-user-id, custom title. Thorough.

**Eval coverage:** `evals/test_recipe_shopping_list_routing.py` covers the multi-turn routing scenario (recipe → shopping list) and regression (weekly plan shopping list). Well-structured with pydantic-evals.

### Pattern Analysis

**No duplicate code found** across changed files. `generate_from_recipes` and `generate_shopping_list` share underlying functions from `src.nutrition.meal_planning` (aggregate_ingredients, categorize_ingredients, flatten_categorized_to_items) — correct reuse, no duplication.

**Consistent error response format** across both shopping list scripts: `{"error": "...", "code": "ERROR_CODE"}`.

### Historical Issues (from review-20260305-153418)

Previous review found 2 low-severity issues:
1. MealPlanView fetchPlan useCallback — still low priority, not addressed (acceptable)
2. useDailyTracking toast dep — pre-existing, no functional impact

No recurring patterns from previous reviews.

## Security Assessment

- All endpoints require JWT auth ✅
- User ownership verified on every resource access ✅
- UUID format validation on path params (meal_plan_id, recipe_id) ✅
- Date format validation on daily-log GET ✅
- No SQL injection vectors (all queries via Supabase client) ✅
- CORS configurable via env var (not hardcoded `*`) ✅
- No secrets in code ✅
- Rate limiting on agent endpoint ✅
- Allergen zero tolerance enforced in generate_custom_recipe ✅

## Recommendations

### Critical (Fix before deploy)
- None remaining (Issue #1 already fixed)

### Important (Fix soon)
- Add test for `start_date=None` path in generate_week_plan (Issue #2)

### Nice-to-have
- Clean up 26 pre-existing ruff errors in RAG_Pipeline, cli.py, verify_setup.py, clients.py
- The 2 `test_agent_basic` tests that use real LLM should probably be in `evals/` not `tests/` per project convention

### Deploy Readiness
- Backend: Ready. All endpoints auth-protected, rate-limited, ownership-verified.
- Frontend: Build passes (verified in previous reviews). 3-tab mobile layout complete.
- Database: 16 tables, all RLS-enabled.
- Tests: 495/498 passing (3 = rate limit, not bugs).
- Evals: 13 datasets available for pre-release validation.
