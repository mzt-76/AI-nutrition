# Plan: Project Audit Fixes (2026-03-12 Pre-Deployment + Docker)

## Context
Auto-generated from audit report `.claude/audits/audit-2026-03-12-0700.md`
4-agent team audit with cross-review. 45 unique findings after dedup.
Supersedes previous audit fix plans.

**User decisions (2026-03-12):**
- C1 (service_role → user-scoped tokens): **deferred** — tracked in `status.md`
- C3 (result.data → result.output): **downgraded to NOTES** — dev-only paths, excluded from Docker
- C4 (pin deps with ==): **deferred** — keeping `>=` for Docker flexibility, tracked in `status.md`

---

## Phase 1 — Critical Fixes

### Task 1.1: Drop unused `execute_custom_sql` function
- ACTION: Create SQL migration `sql/drop-execute-custom-sql.sql`
- IMPLEMENT: `DROP FUNCTION IF EXISTS public.execute_custom_sql(text);`
- VALIDATE: `mcp__supabase__execute_sql` to run the drop, then verify function no longer exists

### Task 1.2: Create `requirements-prod.txt` without dev deps
- ACTION: Create `requirements-prod.txt`
- IMPLEMENT: Copy requirements.txt, remove streamlit, rich. Keep Pillow (needed by image_analysis). Update Dockerfile to use `requirements-prod.txt`.
- VALIDATE: `docker build -t test-backend .` succeeds

---

## Phase 2 — High-Priority Fixes

### Task 2.1: Apply `sanitize_user_text()` to all CRUD text fields
- ACTION: Edit `src/api.py`
- IMPLEMENT: Add sanitization to: `create_daily_log` (food_name), `update_daily_log` (food_name), `upsert_recipe` (name, instructions, ingredients[].name)
- VALIDATE: `pytest tests/ -k "daily_log or recipe"` + manual test with `<script>alert(1)</script>` in food_name

### Task 2.2: Add UUID validation to 7 GET endpoints
- ACTION: Edit `src/api.py`
- IMPLEMENT: Add `_validate_uuid(user_id)` to: `list_conversations`, `list_meal_plans`, `get_daily_log`, `list_favorites`, `check_favorite`, `list_shopping_lists`, `food_search`
- VALIDATE: `curl "localhost:8001/api/conversations?user_id=not-a-uuid"` returns 422

### Task 2.3: Fix nginx security headers inheritance + add CSP/HSTS
- ACTION: Edit `frontend/nginx.conf`
- IMPLEMENT: Create a security headers snippet repeated in every location block. Add CSP and HSTS. Redirect logs to /dev/stdout and /dev/stderr. Add /var/log/nginx to Dockerfile chown.
- VALIDATE: `curl -I localhost:8080/index.html` shows all security headers

### Task 2.4: Validate `image_url` scheme
- ACTION: Edit `skills/body-analyzing/scripts/image_analysis.py`
- IMPLEMENT: Add `if not image_url.startswith("https://"): return "Error: image_url must use HTTPS"`
- VALIDATE: `pytest tests/ -k "image_analysis"`

### Task 2.5: Add null checks on `spec.loader`
- ACTION: Edit `src/agent.py:149-153` and `skills/meal-planning/scripts/generate_week_plan.py:90-95`
- IMPLEMENT: Add `if spec is None or spec.loader is None: raise ImportError(f"Cannot load {script_path}")`
- VALIDATE: `pytest tests/ -k "agent"`

### Task 2.7: Fix rate limiter fail-open
- ACTION: Edit `src/db_utils.py`
- IMPLEMENT: Add in-memory token bucket fallback when DB is unavailable. Fail closed on unknown errors.
- VALIDATE: `pytest tests/ -k "rate_limit"`

### Task 2.8: Update RLS policies for delete + recipe insert
- ACTION: Create SQL migration `sql/fix-rls-delete-and-recipe-insert.sql`
- IMPLEMENT: Replace deny-delete policies with user-scoped delete on meal_plans, conversations, messages. Add authenticated user INSERT on recipes.
- VALIDATE: `mcp__supabase__execute_sql` to apply, then test delete endpoints

---

## Phase 3 — Medium-Priority Fixes

### Task 3.1: Fix ruff errors in RAG_Pipeline
- ACTION: Run `ruff check --fix src/RAG_Pipeline/` then manually fix F841 issues
- VALIDATE: `ruff check src/RAG_Pipeline/` returns 0 errors

### Task 3.2: Add RAG Pipeline healthcheck
- ACTION: Edit `docker-compose.yml` and create a heartbeat check
- IMPLEMENT: Add `healthcheck:` to rag-pipeline service with file-based heartbeat
- VALIDATE: `docker compose config` validates


### Task 3.4: Add DATABASE_URL to startup validation
- ACTION: Edit `src/api.py:118-124`
- IMPLEMENT: Add `DATABASE_URL` to the required env vars check
- VALIDATE: Start without DATABASE_URL, verify clear error at startup

### Task 3.5: Fix meal_plans.user_id nullable
- ACTION: Create SQL migration
- IMPLEMENT: `ALTER TABLE meal_plans ALTER COLUMN user_id SET NOT NULL;`
- VALIDATE: `mcp__supabase__execute_sql`

### Task 3.6: Fix French localization (3 "Loading..." strings)
- ACTION: Edit `frontend/src/App.tsx:35,88,116`
- IMPLEMENT: Replace `"Loading..."` with `"Chargement..."`
- VALIDATE: Visual check

### Task 3.7: Fix `noFallthroughCasesInSwitch`
- ACTION: Edit `frontend/tsconfig.app.json`
- IMPLEMENT: Change `"noFallthroughCasesInSwitch": false` to `true`
- VALIDATE: `cd frontend && npx tsc --noEmit`

### Task 3.8: Remove `MealPlanDetail` index signature
- ACTION: Edit `frontend/src/hooks/useDailyTracking.ts:39`
- IMPLEMENT: Remove `[key: string]: unknown;` line
- VALIDATE: `cd frontend && npx tsc --noEmit`

### Task 3.9: Fix setTimeout stale closure race condition
- ACTION: Edit `frontend/src/components/chat/MessageHandling.tsx:240-259`
- IMPLEMENT: Change `completionReceived` from `let` to `useRef`
- VALIDATE: Manual test of streaming responses

### Task 3.10: Add `is_admin()` STABLE volatility
- ACTION: Create SQL migration
- IMPLEMENT: `CREATE OR REPLACE FUNCTION public.is_admin() ... STABLE SECURITY DEFINER ...`
- VALIDATE: `mcp__supabase__execute_sql`

### Task 3.11: Remove dead env vars from docker-compose
- ACTION: Edit `docker-compose.yml`
- IMPLEMENT: Remove `LLM_PROVIDER`, `EMBEDDING_PROVIDER`, `SKILLS_DIR` from backend service
- VALIDATE: `docker compose config`

### Task 3.12: Add protected fields blocklist in update_my_profile_tool
- ACTION: Edit `src/tools.py`
- IMPLEMENT: Add `PROTECTED_FIELDS = {"is_admin", "id", "email", "created_at"}` filter on update_data
- VALIDATE: `pytest tests/ -k "update_my_profile"`

---

## NOTES — Low-Priority / Deferred (awareness only)

- **DEFERRED: Service_role key → user-scoped tokens** — architectural refactor tracked in `status.md`. Backend uses service_key for all DB ops, bypassing RLS. Fix: create user-scoped Supabase clients per request.
- **DEFERRED: requirements.txt `>=` pins** — keeping `>=` for Docker flexibility. Tracked in `status.md`. Reconsider if a build breaks from silent upgrade.
- **DOWNGRADED: `result.data` → `result.output`** in `src/agent.py:550` and `src/streamlit_ui.py:234` — dev-only paths excluded from Docker. Fix when touching these files.
- `verify_setup.py` queries legacy `my_profile` table — fix to `user_profiles`
- `count_recipes_by_meal_type` fetches all rows to count — use server-side aggregation
- `api.py` global state typed as `Any` — add proper type annotations
- `_validate_uuid` missing `from None` — add for clean exception chaining
- Hardcoded model names in 3 skill scripts — move to constants.py or env vars
- DRY: `_import_sibling_script` duplicated in 2 files — extract to shared utility
- Naive `datetime.now()` in `set_baseline.py` — change to `datetime.now(timezone.utc)`
- Dead `kwargs.get("embedding_client")` no-op — remove or assign
- Missing "Ingrédients" accent in RecipeDetailDrawer — fix spelling
- Zod schema `id: z.string()` vs `Message.id: string | number` — use `z.union`
- SettingsModal 581 lines — PREREQUISITE: Run /frontend-design first. Extract sub-components.
- AdminRoute + useAdmin duplicated logic — consolidate into useAdmin hook
- Unnecessary `ENV` lines in frontend Dockerfile — remove (keep ARG)
