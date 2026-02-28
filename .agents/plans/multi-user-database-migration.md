# Feature: Multi-User Database Migration

The following plan should be complete, but its important that you validate documentation and codebase patterns and task sanity before you start implementing.

Pay special attention to naming of existing utils types and models. Import from the right files etc.

## Feature Description

Complete the multi-user migration: secure the API with JWT verification, add `user_id` columns to remaining per-user tables, enable RLS everywhere, update skill scripts, and drop legacy `my_profile`.

## User Story

As a multi-user nutrition app
I want each user's data (meal plans, feedback, learning profile, memories) isolated by auth identity
So that users only see their own data and the app is secure for production

## Problem Statement

The frontend now has Supabase Auth (login, JWT sessions, real user UUIDs), and the backend API already accepts `user_id` — but the API **trusts** the request body without verifying the JWT. Three per-user tables (`meal_plans`, `weekly_feedback`, `user_learning_profile`) still have no `user_id` column and no RLS. Two meal-planning skill scripts don't filter by `user_id`. CLI/Streamlit pass `user_id=None` to the agent despite having hardcoded mem0 IDs.

## Solution Statement

1. Wire JWT verification into the FastAPI endpoint (following course `agent_api.py` pattern)
2. Add `user_id` FK columns + RLS to remaining per-user tables
3. Add RLS to global reference tables
4. Fix function search_path warnings
5. Update skill scripts that still lack `user_id` filtering
6. Fix CLI/Streamlit `user_id` passthrough
7. Drop `my_profile`

## Feature Metadata

**Feature Type**: Enhancement / Refactor
**Estimated Complexity**: High
**Primary Systems Affected**: `src/api.py`, database schema, skill scripts, `src/cli.py`, `src/streamlit_ui.py`
**Dependencies**: Frontend with Supabase Auth (done), course scripts 1-4 already applied
**Updated**: 2026-02-25

---

## WHAT'S ALREADY DONE

These items from the original plan are **complete** and should NOT be re-executed:

| Item | Status | Evidence |
|------|--------|----------|
| Dead tables dropped (`weekly_tracking`, `n8n_chat_histories`, `memories`, `ingredients_reference`) | DONE | Not in `pg_tables` |
| `user_profiles` created with nutrition columns | DONE | 24 columns including age, gender, weight_kg, goals, etc. |
| `conversations` + `messages` tables with RLS | DONE | `rowsecurity=true` |
| `requests` table with RLS | DONE | `rowsecurity=true` |
| `handle_new_user` trigger | DONE | Auto-creates `user_profiles` row on signup |
| `is_admin()` function | DONE | Used in RLS policies |
| `AgentDeps.user_id` field | DONE | `src/agent.py` line 146 |
| `run_skill_script` injects `user_id` | DONE | `src/agent.py` line 253 |
| `src/tools.py` dual-mode (user_profiles/my_profile) | DONE | Queries `user_profiles` when `user_id` provided |
| `src/api.py` passes `user_id` to `create_agent_deps()` | DONE | Line 284 |
| `generate_week_plan.py` reads `user_id` from kwargs | DONE | Line 159 |
| `calculate_weekly_adjustments.py` reads `user_id` from kwargs | DONE | Line 53 |
| Frontend with Supabase Auth (login, sessions, Google OAuth) | DONE | `frontend/` directory |
| Frontend sends `user.id` + `access_token` to backend | DONE | `frontend/src/lib/api.ts` |

---

## CURRENT STATE AUDIT (2026-02-25)

### Database

| Table | Has user_id? | RLS? | Rows |
|-------|-------------|------|------|
| `user_profiles` | PK=id (auth.uid) | YES | 1 |
| `conversations` | YES | YES | 8 |
| `messages` | computed | YES | 24 |
| `requests` | YES | YES | 8 |
| `meal_plans` | **NO** | **NO** | 52 |
| `weekly_feedback` | **NO** | **NO** | 10 |
| `user_learning_profile` | **NO** | **NO** | 0 |
| `recipes` | N/A (global) | **NO** | 123 |
| `ingredient_mapping` | N/A (global) | **NO** | 546 |
| `openfoodfacts_products` | N/A (global) | **NO** | 0 |
| `documents` | N/A (global) | **NO** | 0 |
| `document_metadata` | N/A (global) | **NO** | 0 |
| `document_rows` | N/A (global) | **NO** | 0 |
| `my_profile` | N/A (legacy) | **NO** | 0 |

### Security Advisors

- **11 tables** with RLS disabled (all the **NO** entries above)
- **Function search_path warnings** on 7 functions (unchanged)
- Backend uses **service role key** (bypasses RLS), so backend queries still work — RLS protects against direct Supabase client access from frontend

### API Auth Gap

- `src/api.py` line 99: `"Auth is NOT implemented yet — user_id comes from request body"`
- `verify_token()` is a placeholder returning empty dict
- Frontend sends `Authorization: Bearer {token}` header but backend ignores it
- **Risk**: Any HTTP client can impersonate any user by sending a fake `user_id`

### Skill Scripts Gap

| Script | user_id handling |
|--------|-----------------|
| `generate_week_plan.py` | YES — reads kwargs, passes to profile fetch |
| `fetch_stored_meal_plan.py` | **NO** — queries meal_plans without user_id filter |
| `generate_shopping_list.py` | **NO** — queries meal_plans without user_id filter |
| `calculate_weekly_adjustments.py` | YES — conditional user_profiles/my_profile |

### CLI / Streamlit Gap

- `src/cli.py`: `USER_ID = "cli_user"` for mem0, but passes `user_id=None` to `create_agent_deps()`
- `src/streamlit_ui.py`: `user_id = "streamlit_user"` for mem0, but passes `user_id=None` to `create_agent_deps()`
- Both have a mismatch: mem0 gets a fake ID, agent gets None

---

## CONTEXT REFERENCES

### Course Auth Pattern (agent_api.py)

The course verifies JWTs by calling Supabase Auth API:

```python
async def verify_token(credentials: HTTPAuthorizationCredentials = Security(HTTPBearer(optional=True))):
    """Verify Supabase JWT and return user dict."""
    if not credentials:
        return None  # Allow unauthenticated for backward compat

    token = credentials.credentials
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {token}",
                "apikey": SUPABASE_SERVICE_KEY,
            },
        )
    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid token")
    return response.json()
```

Then in the endpoint:
```python
# Verify user_id matches token
if auth_user and auth_user.get("id") != request.user_id:
    raise HTTPException(status_code=403, detail="user_id mismatch")
```

### Relevant Codebase Files — MUST READ BEFORE IMPLEMENTING

- `src/api.py` — Main file to update: add JWT verification, wire to endpoint
- `src/tools.py` (lines 29-305) — Already dual-mode, no changes needed
- `src/agent.py` (lines 120-146, 253, 383-414) — Already has user_id infra, no changes needed
- `skills/meal-planning/scripts/fetch_stored_meal_plan.py` — Needs user_id filter
- `skills/meal-planning/scripts/generate_shopping_list.py` — Needs user_id filter
- `src/cli.py` (lines 45, 342) — Needs user_id passthrough fix
- `src/streamlit_ui.py` (lines 59-60, 228) — Needs user_id passthrough fix

---

## IMPLEMENTATION PLAN

### Phase 1: API JWT Authentication (NEW — not in original plan)
### Phase 2: Database — Add user_id columns to per-user tables
### Phase 3: Database — RLS on per-user tables
### Phase 4: Database — RLS on global reference tables
### Phase 5: Database — Fix function search paths
### Phase 6: Update skill scripts
### Phase 7: Fix CLI/Streamlit user_id passthrough
### Phase 8: Drop my_profile (final cleanup)
### Phase 9: Update tests

---

## STEP-BY-STEP TASKS

IMPORTANT: Execute every task in order, top to bottom. Each task is atomic and independently testable.

---

### Task 1: IMPLEMENT JWT verification in src/api.py

**ACTION**: UPDATE `src/api.py`

**1a. Add imports and security scheme:**
```python
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Security

security = HTTPBearer(auto_error=False)
```

**1b. Replace the placeholder `verify_token()` with a real implementation:**
```python
async def verify_token(
    credentials: HTTPAuthorizationCredentials | None = Security(security),
) -> dict | None:
    """Verify Supabase JWT by calling the Auth API.

    Returns the user dict (with 'id' field) or None if no token provided.
    Raises HTTPException 401 if token is invalid.
    """
    if not credentials:
        return None

    token = credentials.credentials
    supabase_url = os.getenv("SUPABASE_URL", "")
    service_key = os.getenv("SUPABASE_SERVICE_KEY", "")

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{supabase_url}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {token}",
                "apikey": service_key,
            },
        )

    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Token invalide ou expiré")

    return response.json()
```

**1c. Wire `verify_token` as a dependency on the `/api/agent` endpoint:**
```python
@app.post("/api/agent")
async def agent_endpoint(
    request: AgentRequest,
    auth_user: dict | None = Depends(verify_token),
):
```

**1d. Add user_id validation inside the endpoint (after rate limit check):**
```python
    # Verify user_id matches the authenticated user
    if auth_user:
        if auth_user.get("id") != request.user_id:
            raise HTTPException(
                status_code=403,
                detail="user_id does not match authenticated user",
            )
    # If no auth_user (no token), allow for backward compat (CLI mode)
```

**1e. Also wire to GET `/api/conversations/{user_id}` if it exists:**
- Add `auth_user: dict | None = Depends(verify_token)` as param
- Validate `auth_user["id"] == user_id` if token present

- **VALIDATE**: Start backend, send request with valid JWT from frontend → 200. Send request with wrong user_id → 403. Send request without token → still works (backward compat for CLI).
- **GOTCHA**: `httpx` is already imported in api.py. `os` is already imported. Just need `Security`, `HTTPBearer`, `HTTPAuthorizationCredentials` from fastapi.

---

### Task 2: ADD user_id column to meal_plans

**ACTION**: Apply migration via Supabase MCP

```sql
ALTER TABLE meal_plans
  ADD COLUMN user_id UUID REFERENCES user_profiles(id) ON DELETE CASCADE;

CREATE INDEX idx_meal_plans_user_id ON meal_plans(user_id);

-- Backfill existing 52 rows to current single user
UPDATE meal_plans SET user_id = '5745fc58-9c75-48b1-bc79-12855a8c6021'
WHERE user_id IS NULL;
```

- **VALIDATE**: `SELECT column_name FROM information_schema.columns WHERE table_name = 'meal_plans' AND column_name = 'user_id';`
- **NOTE**: Backfill assigns all existing plans to your user. After backfill, consider `ALTER TABLE meal_plans ALTER COLUMN user_id SET NOT NULL;`

---

### Task 3: ADD user_id column to weekly_feedback

**ACTION**: Apply migration via Supabase MCP

```sql
ALTER TABLE weekly_feedback
  ADD COLUMN user_id UUID REFERENCES user_profiles(id) ON DELETE CASCADE;

CREATE INDEX idx_weekly_feedback_user_id ON weekly_feedback(user_id);

-- Backfill existing 10 rows
UPDATE weekly_feedback SET user_id = '5745fc58-9c75-48b1-bc79-12855a8c6021'
WHERE user_id IS NULL;
```

---

### Task 4: ADD user_id column to user_learning_profile

**ACTION**: Apply migration via Supabase MCP

```sql
ALTER TABLE user_learning_profile
  ADD COLUMN user_id UUID UNIQUE REFERENCES user_profiles(id) ON DELETE CASCADE;

CREATE UNIQUE INDEX idx_learning_profile_user_id ON user_learning_profile(user_id);
```

- **GOTCHA**: UNIQUE constraint — one learning profile per user. Table is empty so no backfill needed.

---

### Task 5: ADD RLS to meal_plans

**ACTION**: Apply migration via Supabase MCP

```sql
ALTER TABLE meal_plans ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own meal plans"
ON meal_plans FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own meal plans"
ON meal_plans FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own meal plans"
ON meal_plans FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Admins can view all meal plans"
ON meal_plans FOR SELECT USING (is_admin());

CREATE POLICY "Admins can insert meal plans"
ON meal_plans FOR INSERT WITH CHECK (is_admin());

CREATE POLICY "Deny delete for meal_plans"
ON meal_plans FOR DELETE USING (false);
```

---

### Task 6: ADD RLS to weekly_feedback

**ACTION**: Apply migration — same pattern as Task 5

```sql
ALTER TABLE weekly_feedback ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own weekly feedback"
ON weekly_feedback FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own weekly feedback"
ON weekly_feedback FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own weekly feedback"
ON weekly_feedback FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Admins can view all weekly feedback"
ON weekly_feedback FOR SELECT USING (is_admin());

CREATE POLICY "Admins can insert weekly feedback"
ON weekly_feedback FOR INSERT WITH CHECK (is_admin());

CREATE POLICY "Deny delete for weekly_feedback"
ON weekly_feedback FOR DELETE USING (false);
```

---

### Task 7: ADD RLS to user_learning_profile

**ACTION**: Apply migration

```sql
ALTER TABLE user_learning_profile ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own learning profile"
ON user_learning_profile FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own learning profile"
ON user_learning_profile FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own learning profile"
ON user_learning_profile FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Admins can view all learning profiles"
ON user_learning_profile FOR SELECT USING (is_admin());

CREATE POLICY "Deny delete for user_learning_profile"
ON user_learning_profile FOR DELETE USING (false);
```

---

### Task 8: ADD RLS to global reference tables (read-only for authenticated)

**ACTION**: Apply migration

```sql
-- Recipes
ALTER TABLE recipes ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Authenticated users can read recipes"
ON recipes FOR SELECT TO authenticated USING (true);
CREATE POLICY "Admins can insert recipes"
ON recipes FOR INSERT WITH CHECK (is_admin());
CREATE POLICY "Admins can update recipes"
ON recipes FOR UPDATE USING (is_admin());
CREATE POLICY "Deny delete for recipes"
ON recipes FOR DELETE USING (false);

-- Ingredient mapping
ALTER TABLE ingredient_mapping ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Authenticated users can read ingredient mapping"
ON ingredient_mapping FOR SELECT TO authenticated USING (true);
CREATE POLICY "Admins can insert ingredient mapping"
ON ingredient_mapping FOR INSERT WITH CHECK (is_admin());
CREATE POLICY "Admins can update ingredient mapping"
ON ingredient_mapping FOR UPDATE USING (is_admin());
CREATE POLICY "Deny delete for ingredient_mapping"
ON ingredient_mapping FOR DELETE USING (false);

-- OpenFoodFacts products
ALTER TABLE openfoodfacts_products ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Authenticated users can read openfoodfacts products"
ON openfoodfacts_products FOR SELECT TO authenticated USING (true);
CREATE POLICY "Admins can insert openfoodfacts products"
ON openfoodfacts_products FOR INSERT WITH CHECK (is_admin());
CREATE POLICY "Admins can update openfoodfacts products"
ON openfoodfacts_products FOR UPDATE USING (is_admin());
CREATE POLICY "Deny delete for openfoodfacts_products"
ON openfoodfacts_products FOR DELETE USING (false);
```

---

### Task 9: ADD RLS to RAG/document tables

**ACTION**: Apply migration

```sql
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_metadata ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_rows ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated can read documents" ON documents FOR SELECT TO authenticated USING (true);
CREATE POLICY "Authenticated can read document_metadata" ON document_metadata FOR SELECT TO authenticated USING (true);
CREATE POLICY "Authenticated can read document_rows" ON document_rows FOR SELECT TO authenticated USING (true);

CREATE POLICY "Admins can manage documents" ON documents FOR ALL USING (is_admin());
CREATE POLICY "Admins can manage document_metadata" ON document_metadata FOR ALL USING (is_admin());
CREATE POLICY "Admins can manage document_rows" ON document_rows FOR ALL USING (is_admin());
```

---

### Task 10: FIX function search_path warnings

**ACTION**: Apply migration

```sql
ALTER FUNCTION public.update_ingredient_mapping_updated_at() SET search_path = public;
ALTER FUNCTION public.match_memories(vector, integer, jsonb) SET search_path = public;
ALTER FUNCTION public.handle_new_user() SET search_path = public;
ALTER FUNCTION public.is_admin() SET search_path = public;
ALTER FUNCTION public.match_documents(vector, integer, jsonb) SET search_path = public;
ALTER FUNCTION public.search_openfoodfacts(text, integer) SET search_path = public;
ALTER FUNCTION public.execute_custom_sql(text) SET search_path = public;
```

- **VALIDATE**: Run `get_advisors` security — search_path warnings should be resolved
- **GOTCHA**: Function signatures must match exactly. If any fail, query `pg_proc` to verify.

---

### Task 11: UPDATE fetch_stored_meal_plan.py — Add user_id filter

**ACTION**: UPDATE `skills/meal-planning/scripts/fetch_stored_meal_plan.py`

- Add `user_id = kwargs.get("user_id", "")` in `execute()`
- Add `.eq("user_id", user_id)` to the `meal_plans` query chain

- **VALIDATE**: `ruff check skills/meal-planning/scripts/fetch_stored_meal_plan.py`

---

### Task 12: UPDATE generate_shopping_list.py — Add user_id filter

**ACTION**: UPDATE `skills/meal-planning/scripts/generate_shopping_list.py`

- Add `user_id = kwargs.get("user_id", "")` in `execute()`
- Add `.eq("user_id", user_id)` to the `meal_plans` query chain

- **VALIDATE**: `ruff check skills/meal-planning/scripts/generate_shopping_list.py`

---

### Task 13: UPDATE generate_week_plan.py — Add user_id to meal_plans insert

**ACTION**: UPDATE `skills/meal-planning/scripts/generate_week_plan.py`

- The script already reads `user_id = kwargs.get("user_id")` (line 159)
- Add `"user_id": user_id` to the `meal_plan_record` dict when inserting into `meal_plans`

- **VALIDATE**: `ruff check skills/meal-planning/scripts/generate_week_plan.py`

---

### Task 14: UPDATE calculate_weekly_adjustments.py — Add user_id to inserts

**ACTION**: UPDATE `skills/weekly-coaching/scripts/calculate_weekly_adjustments.py`

- Already reads `user_id` from kwargs (line 53)
- Add `.eq("user_id", user_id)` to `weekly_feedback` and `user_learning_profile` queries
- Add `"user_id": user_id` to `weekly_feedback` insert record
- Add `"user_id": user_id` to `user_learning_profile` upsert record

- **VALIDATE**: `ruff check skills/weekly-coaching/scripts/calculate_weekly_adjustments.py`

---

### Task 15: FIX src/cli.py — Pass user_id to agent

**ACTION**: UPDATE `src/cli.py`

- Change `user_id=None` in `create_agent_deps()` call to `user_id=USER_ID`
- Make USER_ID configurable: `USER_ID = os.getenv("NUTRITION_USER_ID", "cli_user")`
- This way CLI can work with a real UUID via env var, or fall back to `"cli_user"` for local dev

- **VALIDATE**: `ruff check src/cli.py`

---

### Task 16: FIX src/streamlit_ui.py — Pass user_id to agent

**ACTION**: UPDATE `src/streamlit_ui.py`

- Change `user_id=None` in `create_agent_deps()` call to `user_id=st.session_state.user_id`
- This ensures mem0 and agent tools see the same user_id

- **VALIDATE**: `ruff check src/streamlit_ui.py`

---

### Task 17: DROP my_profile and remove fallback code

**ACTION**:

**17a. Apply migration:**
```sql
DROP TABLE IF EXISTS my_profile CASCADE;
```

**17b. UPDATE `src/tools.py`:**
- Remove the `my_profile` fallback branch from `fetch_my_profile_tool` and `update_my_profile_tool`
- Always query `user_profiles` with `user_id` (no more dual-mode)
- If `user_id` is None or empty, return an error message

**17c. UPDATE `skills/weekly-coaching/scripts/calculate_weekly_adjustments.py`:**
- Remove the `my_profile` fallback — always use `user_profiles` with user_id

- **VALIDATE**: `list_tables` — `my_profile` gone. `ruff check src/ skills/`
- **GOTCHA**: Only do this AFTER Tasks 15-16 ensure CLI/Streamlit pass real user_id.

---

### Task 18: UPDATE tests

**ACTION**: UPDATE test files

**18a. `tests/test_user_stories_e2e.py`:**
- Update mock supabase chains to expect `user_profiles` table (not `my_profile`)
- Add `.eq("id", user_id)` expectations

**18b. `evals/test_skill_scripts.py`:**
- Add `user_id` to kwargs in meal-planning script calls
- Update mock chains to handle `.eq("user_id", ...)` filters

**18c. `conftest.py`:**
- Add `user_id` field to relevant fixtures

- **VALIDATE**: `pytest tests/ -v --tb=short`

---

### Task 19: COPY SQL scripts to sql/ folder

**ACTION**: CREATE SQL migration files for version control

- `sql/5_add_user_id_columns.sql` — Tasks 2-4
- `sql/6_rls_per_user_tables.sql` — Tasks 5-7
- `sql/7_rls_global_reference_tables.sql` — Tasks 8-9
- `sql/8_fix_function_search_paths.sql` — Task 10
- `sql/9_drop_my_profile.sql` — Task 17a

---

## TESTING STRATEGY

### Unit Tests

- All existing `pytest tests/ -v` must pass after changes
- Mock supabase calls updated to expect `user_id` filters
- Profile tool tests verify `user_profiles` table (not `my_profile`)

### Integration Tests (Manual)

1. Start backend + frontend
2. Login as `meuzeretl@gmail.com` → verify chat works with streaming
3. Verify meal plan generation stores `user_id` in DB
4. Verify fetch retrieves only that user's plans
5. Test JWT: send request with wrong user_id → expect 403
6. Test no JWT: send request without Authorization header → should still work (CLI compat)
7. CLI: run with `NUTRITION_USER_ID=5745fc58-9c75-48b1-bc79-12855a8c6021` → verify profile loads

### Edge Cases

- Empty `user_id` parameter — tools should return clear error
- CLI without env var → uses `"cli_user"`, profile tools return "profile not found" (acceptable)
- `user_learning_profile` UNIQUE constraint on user_id — test duplicate insert fails gracefully

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style

```bash
ruff format src/ tests/ skills/ && ruff check src/ tests/ skills/ && mypy src/
```

### Level 2: Unit Tests

```bash
pytest tests/ -v --tb=short
```

### Level 3: Security Audit

```
# Via Supabase MCP
get_advisors(type: "security")
# Expected: 0 RLS-disabled errors, 0 mutable search_path warnings
```

### Level 4: JWT Verification

```bash
# With valid token (from frontend login)
curl -X POST http://localhost:8001/api/agent \
  -H "Authorization: Bearer <valid_jwt>" \
  -H "Content-Type: application/json" \
  -d '{"query":"hello","user_id":"5745fc58-...","request_id":"test"}'
# Expected: 200

# With mismatched user_id
curl -X POST http://localhost:8001/api/agent \
  -H "Authorization: Bearer <valid_jwt>" \
  -H "Content-Type: application/json" \
  -d '{"query":"hello","user_id":"wrong-uuid","request_id":"test"}'
# Expected: 403

# Without token (CLI mode)
curl -X POST http://localhost:8001/api/agent \
  -H "Content-Type: application/json" \
  -d '{"query":"hello","user_id":"cli_user","request_id":"test"}'
# Expected: 200 (backward compat)
```

---

## ACCEPTANCE CRITERIA

- [ ] JWT verification wired to `/api/agent` endpoint
- [ ] user_id mismatch returns 403
- [ ] No-token requests still work (CLI backward compat)
- [ ] `user_id` FK column added to `meal_plans`, `weekly_feedback`, `user_learning_profile`
- [ ] Existing rows backfilled with your user UUID
- [ ] RLS enabled on ALL public tables (0 security advisor errors)
- [ ] Function search_path fixed (0 warnings)
- [ ] `fetch_stored_meal_plan.py` + `generate_shopping_list.py` filter by `user_id`
- [ ] `generate_week_plan.py` inserts `user_id` into meal_plans
- [ ] `calculate_weekly_adjustments.py` inserts `user_id` into weekly_feedback + learning_profile
- [ ] CLI passes `USER_ID` to `create_agent_deps()`
- [ ] Streamlit passes `user_id` to `create_agent_deps()`
- [ ] `my_profile` table dropped
- [ ] `src/tools.py` no longer references `my_profile`
- [ ] All tests pass (`pytest tests/ -v`)
- [ ] SQL migration files saved in `sql/` folder
- [ ] `ruff format && ruff check && mypy` all pass

---

## NOTES

### Design Decisions

1. **JWT verification via Supabase Auth API** (not local JWT decode): Simpler, no need to manage JWT secrets or JWKS. Small latency cost per request (~50ms) is acceptable. Matches the course pattern exactly.

2. **Backward compatibility for CLI/Streamlit**: The endpoint accepts requests without Authorization header. When no token is present, `verify_token` returns `None` and user_id validation is skipped. This lets CLI/Streamlit continue to work during the transition.

3. **Backfill existing data**: The 52 meal_plans and 10 weekly_feedback rows are assigned to your user UUID during migration. This preserves your existing data under your authenticated account.

4. **Service role bypasses RLS**: Backend uses `SUPABASE_SERVICE_KEY` (service role). RLS policies only affect direct client access via the frontend Supabase client. Backend queries continue working unchanged.

5. **Drop my_profile last**: Task 17 is intentionally last among code changes. Until then, CLI without a real user_id falls back to `my_profile`. After the drop, CLI must provide a valid UUID via `NUTRITION_USER_ID` env var.

6. **mem0 user_id**: mem0 already stores user_id in metadata JSONB. The 7 existing memories tagged `cli_user`/`streamlit_user` become orphaned when switching to real UUIDs. Low risk — recreated naturally through usage.

### Risks

- **RLS before user_id populated**: If migration Tasks 5-7 run before Task 2-4 backfill, rows with NULL user_id become invisible. Mitigation: Tasks are ordered so user_id column + backfill happen first.
- **Function signature mismatch in Task 10**: If a function's actual signature doesn't match, ALTER fails. Query `pg_proc` to verify first.
- **CLI breaks after my_profile drop**: Expected. CLI user must set `NUTRITION_USER_ID` env var with a real UUID. Document this in dev-commands.md.
