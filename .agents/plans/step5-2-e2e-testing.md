# Step 5.2 — End-to-End Testing

**Goal:** Verify all mobile MVP flows work correctly before deploy.
**Depends on:** Step 5.1 complete

---

## Current Test Coverage (detailed research)

**Total: 415 test functions + 45 eval functions across 37 files**

### Well-tested:
- **Nutrition domain** (~150 tests): calculations, validators, adjustments, feedback extraction, meal distribution, portion scaler, recipe_db, shopping list, edge cases
- **Agent routing** (~20 tests): `test_user_stories_e2e.py` covers 8 user stories with FunctionModel (deterministic)
- **Skill scripts** (~100 tests): log food entries (5), set baseline, generate day/week plan, custom recipe, fetch meal plan
- **API core** (6 tests): health, conversations, agent endpoint (rate limit, auth, streaming accept)
- **Other**: OpenFoodFacts client, UI components, profile caching, skill loader, db_utils

### NOT tested (12 of 15 API endpoints = 0 tests):
- `GET/POST/PUT/DELETE /api/daily-log` — 0 tests
- `GET /api/meal-plans`, `GET /api/meal-plans/:id` — 0 tests
- `GET/POST/DELETE /api/favorites` — 0 tests
- `GET/PUT /api/shopping-lists` — 0 tests
- **Frontend** — 0 tests (no vitest/jest/playwright setup)
- **Auth ownership validation** — only basic token bypass in test_api.py
- **Streaming NDJSON path** — no test
- **Concurrent updates** — no test
- **Date/meal_type format validation** — no test

### Evals (45 functions, run on demand with real LLM):
- Agent E2E (10+), food logging (3 scenarios), coaching baseline (10+)
- Recipe variety (5+), generative UI markers (5+), skill scripts (12+)

### Fixtures (conftest.py):
- `sample_profile` (male, 35, moderate, muscle_gain)
- `sample_meal_plan` (7-day, 3 meals/day)
- `sample_weekly_feedback` (weight, adherence, hunger, energy, sleep)

---

## Tasks

### Task 1: Backend API endpoint tests (~35-40 tests)
Add to `tests/test_api.py` (or split into separate files):

**`TestDailyLogEndpoints`** (~12 tests):
- [ ] GET /api/daily-log — happy path (returns entries for user+date)
- [ ] GET /api/daily-log — empty result (no entries for date)
- [ ] POST /api/daily-log — happy path (create entry, returns created)
- [ ] POST /api/daily-log — missing required fields (400)
- [ ] POST /api/daily-log — invalid meal_type value
- [ ] PUT /api/daily-log/:id — happy path (update entry)
- [ ] PUT /api/daily-log/:id — wrong user (403)
- [ ] DELETE /api/daily-log/:id — happy path
- [ ] DELETE /api/daily-log/:id — wrong user (403)
- [ ] All endpoints — no auth token (401)

**`TestMealPlansEndpoints`** (~6 tests):
- [ ] GET /api/meal-plans — list plans for user
- [ ] GET /api/meal-plans/:id — fetch specific plan with plan_data
- [ ] GET /api/meal-plans/:id — wrong user (403)
- [ ] GET /api/meal-plans/:id — not found (404)

**`TestFavoritesEndpoints`** (~6 tests):
- [ ] GET /api/favorites — list favorites for user
- [ ] POST /api/favorites — add favorite
- [ ] DELETE /api/favorites/:id — remove favorite
- [ ] DELETE /api/favorites/:id — wrong user (403)

**`TestShoppingListsEndpoints`** (~6 tests):
- [ ] GET /api/shopping-lists — list for user
- [ ] GET /api/shopping-lists/:id — fetch specific
- [ ] PUT /api/shopping-lists/:id — update items
- [ ] PUT /api/shopping-lists/:id — wrong user (403)

### Task 2: Manual E2E flow testing (checklist)
Test on mobile viewport (375px width in Chrome DevTools):

**Auth flow:**
- [ ] Login with email/password
- [ ] Login with Google OAuth
- [ ] Session persists on refresh
- [ ] Logout works

**Chat tab:**
- [ ] Send message, get streaming response
- [ ] Conversation saves and appears in sidebar/drawer
- [ ] Load previous conversation
- [ ] Generative UI components render (NutritionSummary, MacroGauges, etc.)

**Suivi du Jour tab:**
- [ ] Date navigation (prev/next/today)
- [ ] CalorieGauge shows correct consumed/target
- [ ] TrackingMacros bars update correctly
- [ ] MealSection groups entries by meal type in correct order
- [ ] PlanValidation: check meal from plan -> auto-logs with macros
- [ ] TrackingInput: type food -> agent logs -> entries appear
- [ ] Delete entry works
- [ ] Mic button (if supported browser)

**Mes Plans tab:**
- [ ] Plans tab: lists plans, click navigates to /plans/:id
- [ ] Favoris tab: shows favorites, heart removes (optimistic)
- [ ] Courses tab: shows shopping lists, checkboxes persist
- [ ] Empty states show guidance messages

**Cross-tab:**
- [ ] Generate plan in Chat -> appears in Mes Plans
- [ ] Log food in Chat -> appears in Suivi du Jour
- [ ] Generate shopping list in Chat -> appears in Courses

### Task 3: Fix bugs found during testing
- [ ] Document and fix each issue as found
- [ ] Re-test after fixes

---

## Success Criteria
- All API CRUD endpoints have tests (happy + error paths)
- All manual E2E checklist items pass
- No critical bugs blocking deploy
