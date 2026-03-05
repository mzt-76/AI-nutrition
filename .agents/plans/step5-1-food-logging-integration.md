# Step 5.1 — Agent Food Logging Integration (chat -> daily_food_log)

**Goal:** Verify and fix the full flow: user types food in TrackingInput OR Chat -> agent calls log_food_entries -> entries land in daily_food_log -> DailyTracking tab shows them.

**Status:** Happy path works via TrackingInput (wraps with [SUIVI RAPIDE] prefix). Key gaps: agent can't route without prefix, polling race condition, no macro feedback.

---

## What Already Works (verified by research)

1. **Backend script** `skills/meal-planning/scripts/log_food_entries.py`:
   - Takes `items` (list of {name, quantity, unit}), `log_date`, `meal_type`
   - Uses `match_ingredient()` from OFF client (cache-first, 275K products, 546 cached mappings)
   - Parallel lookup via `asyncio.gather`, inserts rows into `daily_food_log`
   - Returns JSON with per-item macros + totals + confidence scores

2. **SKILL.md routing**: Documents `log_food_entries` with decomposition rules
   - "j'ai mange..." triggers meal-planning skill
   - Agent must decompose composite dishes into individual ingredients BEFORE calling script

3. **TrackingInput.tsx**: Wraps user text with `[SUIVI RAPIDE - date: X]` prefix, sends via `sendMessage()`
   - Shows Loader2 spinner while sending
   - Polls 3x (1s interval) for new entries via `onEntryCreated` -> `refreshEntries()`
   - Toast confirmation on success/error

4. **API endpoints** (4 CRUD): GET list, POST create, PUT update, DELETE — all with JWT auth + ownership checks

5. **Tests**: 5 unit tests + 3 eval scenarios (4 cases, all 100% passing)

---

## Architecture Flow

```
TrackingInput: user types "200g poulet + riz"
  -> wraps: "[SUIVI RAPIDE - date: 2026-03-05] L'utilisateur déclare avoir mangé : '200g poulet + riz'"
  -> sendMessage() -> POST /api/agent (NDJSON streaming)
  -> Agent loads meal-planning skill, calls log_food_entries
  -> log_food_entries: parallel match_ingredient() via OFF
  -> inserts rows to daily_food_log
  -> Frontend polls GET /api/daily-log 3x (1s delay)
  -> useDailyTracking re-renders with new entries
```

---

## Known Issues

### Issue 1: Agent can't route without [SUIVI RAPIDE] prefix
- `src/prompt.py` does NOT mention food logging
- Without the prefix, the agent has no signal to use meal-planning/log_food_entries
- **Impact**: Chat tab won't log food unless user is very explicit (e.g., "enregistre dans mon journal")
- **Fix options**: (a) Add food logging hint to system prompt, or (b) accept that Chat requires explicit skill loading (current progressive disclosure design)

### Issue 2: Polling race condition
- 3 polls x 1s delay may miss if agent takes >3s (OFF lookup + DB insert)
- **Fix**: Increase to 5 polls with exponential backoff (1s, 2s, 3s, 4s, 5s) = 15s total window

### Issue 3: No macro feedback to user
- Toast only says "Enregistre" — no detail about what was logged or confidence
- **Fix**: Optional — show a small summary toast with calories logged

### Issue 4: Low-confidence OFF matches logged with 0 macros silently
- If OFF confidence < 0.5, item logged with all-zero macros, no user notification
- **Fix**: Optional — show warning toast for low-confidence items

---

## Tasks

### Task 1: Manual E2E verification via TrackingInput
- [ ] Start backend (`uvicorn src.api:app --port 8001`) + frontend (`cd frontend && npm run dev`)
- [ ] Login, go to Suivi du Jour
- [ ] Type "200g poulet + 150g riz" in TrackingInput
- [ ] Verify: entries appear in daily log within polling window
- [ ] Check Supabase `daily_food_log` table for correct rows + macros

### Task 2: Fix polling timing
- [ ] Change from 3x 1s to 5x exponential (1s, 2s, 3s, 4s, 5s) in `TrackingInput.tsx`
- [ ] Verify agent has enough time to complete OFF lookups

### Task 3: Test from Chat tab
- [ ] Type "j'ai mange une salade avec 100g de poulet et du riz" in Chat
- [ ] Verify agent loads meal-planning skill and calls log_food_entries
- [ ] Switch to Suivi du Jour tab, verify entries appear
- [ ] If agent doesn't route: decide whether to add hint to system prompt or accept current behavior

### Task 4: Test composite dish decomposition
- [ ] Type "pates carbonara" in TrackingInput
- [ ] Verify agent decomposes into 3+ ingredients (pates + lardons + oeuf + creme + parmesan)
- [ ] Verify each ingredient has macros from OFF

### Task 5: API test coverage for daily-log endpoints
Currently `test_api.py` has 0 tests for CRUD endpoints.
- [ ] Add `TestDailyLogEndpoints`: GET, POST, DELETE (happy path + auth checks)
- [ ] Mock Supabase, verify request validation, response format

---

## Estimated Scope
- ~1 hour manual testing + polling fix
- ~30 min adding API endpoint tests
- Low risk, mostly verification + minor fix

## Success Criteria
- User types food in TrackingInput -> entries appear in daily log within 15s
- Composite dishes decomposed into ingredients
- API endpoint tests pass
- Decision made on Chat tab routing (fix or accept)
