# Plan: Project Audit Fixes

## Context
Auto-generated from audit report `.claude/audits/audit-2026-03-10-1500.md`.
Verified against actual code — false positives removed.
Async Supabase migration moved to dedicated plan: `.agents/plans/supabase-async-migration.md`.

---

## Phase 1 — High-Priority Fixes

### Task 1.1: Create sanitize_user_text() and apply at API boundary
- ACTION: Create function in `src/nutrition/validators.py`, edit `src/api.py`
- IMPLEMENT:
  - Create `sanitize_user_text(text: str, max_length: int, field_name: str) -> str` in `src/nutrition/validators.py`
  - The function should: (1) truncate to max_length, (2) strip XML-like tags that could interfere with system prompt delimiters (e.g. `<system>`, `</instructions>`), (3) log a warning if suspicious patterns detected
  - NOTE: `sanitize_user_text()` does NOT exist yet — it must be created, not imported
  - In `src/api.py` `agent_endpoint`, apply before passing to agent: `request.query = sanitize_user_text(request.query, 5000, "agent_query")`
- VALIDATE: `pytest tests/ -k "test_api" && ruff check src/api.py src/nutrition/validators.py`

### Task 1.2: Fix RecalculateRequest.gender to Literal type
- ACTION: Edit `src/api.py`
- IMPLEMENT: Change `RecalculateRequest.gender: str` to `gender: Literal["male", "female"]`. `from typing import Literal` is likely already imported — verify. Remove redundant validation at line 1254 (`if body.gender not in ("male", "female")`) since Pydantic now validates this.
- VALIDATE: `mypy src/api.py` — the arg-type error at line 1268 should disappear

### Task 1.3: Fix agent.py implicit Optional parameters
- ACTION: Edit `src/agent.py`
- IMPLEMENT: Change all parameters on lines 309-326 from `param: T = None` to `param: T | None = None`. Add early return with a helpful message if all params are None: `if all(v is None for v in [age, gender, weight_kg, height_cm, ...]):` return "Aucun champ à mettre à jour."
- VALIDATE: `mypy src/agent.py` — the 8 implicit Optional errors should disappear

### Task 1.4: Remove skill-creator from _VALID_SKILLS
- ACTION: Edit `src/agent.py` and `evals/test_skill_loading.py`
- IMPLEMENT: Remove `"skill-creator"` from the `_VALID_SKILLS` frozenset (line ~113). Also remove from `EXPECTED_SKILLS` in `evals/test_skill_loading.py`.
- VALIDATE: `pytest tests/test_agent.py`

### Task 1.5: Fix ComponentRenderer `any` type
- ACTION: Edit `frontend/src/components/generative-ui/ComponentRenderer.tsx`
- IMPLEMENT: Create a union type of all 7 component prop types. Replace `Record<string, React.FC<any>>` with a properly typed record. Remove the eslint-disable comment on line 13.
- VALIDATE: `cd frontend && npx tsc --noEmit`

---

## Phase 2 — Medium-Priority Fixes

### Task 2.1: Centralize safety constants in constants.py
- ACTION: Edit `src/nutrition/constants.py` and `src/api.py`
- IMPLEMENT: Add to constants.py: `MIN_CALORIES_WOMEN = 1200`, `MIN_CALORIES_MEN = 1500`, `ALLERGEN_ZERO_TOLERANCE = True`, `DISLIKED_FOODS_FILTERED = True` with docstrings. In api.py line ~1278, import and replace: `min_calories = MIN_CALORIES_WOMEN if body.gender == "female" else MIN_CALORIES_MEN`.
- VALIDATE: `pytest tests/ && ruff check src/`

### Task 2.2: Fix MIME type validation to exact match
- ACTION: Edit `src/api.py`
- IMPLEMENT: Change `_ALLOWED_MIME_PREFIXES = ("image/", "text/plain", "application/pdf")` to `_ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp", "text/plain", "application/pdf"}`. Change line 448-449 from `startswith(prefix)` to `f.mime_type in _ALLOWED_MIME_TYPES`.
- VALIDATE: `pytest tests/ -k "test_api"`

### Task 2.3: Fix eval TEST_USER_PROFILE compliance
- ACTION: Edit 5 eval files
- IMPLEMENT: Add `TEST_USER_PROFILE` constant to `evals/test_meal_pipeline_e2e.py`, `evals/test_meal_plan_quality_e2e.py`, `evals/test_milp_optimizer_e2e.py`, `evals/test_skill_loading.py`, `evals/test_skill_scripts.py` with all required fields (age, gender, height_cm, weight_kg, activity_level, goals).
- VALIDATE: `pytest evals/ --co -q` (collect only, verify no import errors)

### Task 2.4: Fix run_skill_script bare dict/list type
- ACTION: Edit `src/agent.py`
- IMPLEMENT: On line 251, change `parameters: dict[str, str | int | float | bool | list | dict | None]` to `parameters: dict[str, str | int | float | bool | list[str | int | float] | dict[str, str | int | float] | None] | None = None`. This gives the LLM a precise JSON schema for nested types.
- VALIDATE: `mypy src/agent.py`

### Task 2.5: Fix stale closure in useSpeechRecognition
- ACTION: Edit `frontend/src/hooks/useSpeechRecognition.ts`
- IMPLEMENT: In the `onend` handler (line ~94), remove the `isListening` check from the restart condition. Change `if (recognitionRef.current === recognition && isListening)` to `if (recognitionRef.current === recognition)`. The ref-clearing logic on line ~121 already prevents unwanted restarts after `stopListening()`.
- VALIDATE: `cd frontend && npx tsc --noEmit`

---

## NOTES — Low-Priority (no tasks, just awareness)

- **L1**: `scripts/seed_recipes_gaps_v2.py:1607` — remove `f` prefix from f-string without placeholders (Ruff F541)
- **L2**: `src/agent.py:438-468` — global client caching uses check-then-set without locking. Consider `asyncio.Lock()` for thread-safe initialization
- **L3**: `src/api.py:80` — `exc_info=exc` should be `exc_info=True` for proper traceback formatting
- **L4**: `frontend/src/components/chat/ChatInput.tsx:48-67` — `handleSubmit`/`handleKeyDown` not wrapped in useCallback
- **L5**: `frontend/src/pages/MyPlans.tsx:78-99` — optimistic delete lacks refresh mechanism on failure
- **L6**: `frontend/src/components/sidebar/SettingsModal.tsx:68-100` — inline TagInput not memoized, may lose state on parent re-render

---

## Removed findings (false positives verified against code)

- ~~M2: CORS fallback localhost en prod~~ — code already does `raise RuntimeError` in production (lines 157-161)
- ~~M3: _http_client race condition~~ — FastAPI lifespan guarantees init before any request
- ~~M1: Service key in httpx headers~~ — httpx async client doesn't log headers by default
- ~~H2: UUID validation on user_id~~ — `auth_user["id"] != user_id` check already rejects non-matching IDs (downgraded to note, not worth a task)
- ~~C1-C3: Committed secrets~~ — files never committed to git history
