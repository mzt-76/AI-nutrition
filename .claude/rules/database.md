---
paths:
  - "src/db_utils.py"
  - "src/clients.py"
  - "sql/**"
---

# Database Conventions

## Supabase Async Client

Two factories in `src/clients.py`:
- `get_async_supabase_client()` → for API, agent, skills (async context)
- `get_supabase_client()` → for standalone `scripts/` only (sync)

**Chain pattern:** `.table().select().eq()` are sync, only `.execute()` is async:

```python
# CORRECT
result = await supabase.table("recipes").select("*").eq("id", recipe_id).execute()
row = result.data[0] if result.data else None

# WRONG — missing await on .execute()
result = supabase.table("recipes").select("*").execute()  # Returns coroutine, not data!
```

## Key Gotchas

- **`user_profiles` PK is `id`**, not `user_id` — use `.eq("id", user_id)`
- **Avoid `.maybe_single()`** — throws APIError 204. Use `.execute()` + `data[0]` instead.
- **`SupabaseAsyncClient` has NO `aclose()` method** — don't try to close it.
- **`timeout`/`verify` DeprecationWarning** — known issue in `src/clients.py`, not blocking.

## Test Mocking

```python
# Chain methods = MagicMock, .execute() = AsyncMock
mock_supabase.table.return_value.select.return_value.eq.return_value.execute = AsyncMock(
    return_value=MagicMock(data=[{"id": "123", "name": "Test"}])
)
```

## 17 Tables (all RLS-enabled)

Key tables: `user_profiles`, `recipes`, `conversations`, `messages`, `meal_plans`, `daily_logs`, `user_favorites`, `shopping_lists`, `openfoodfacts_products`, `ingredient_mapping`, `rag_pipeline_state`

## Anti-patterns

- Never use the sync client in async code (API, agent, skills)
- Never use `.maybe_single()` — it throws on empty results
- Never query `user_profiles` with `.eq("user_id", ...)` — the PK is `id`
- Never bypass RLS with service_key for user-facing operations (deferred refactor, but don't make it worse)
