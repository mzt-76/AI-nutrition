---
paths:
  - "src/api.py"
  - "src/api_models.py"
---

# API Conventions

## Stack

FastAPI with NDJSON streaming, JWT auth via Supabase Auth, CORS middleware.

```bash
uvicorn src.api:app --port 8001 --reload
```

## Auth Flow

`Authorization: Bearer <JWT>` → decode → extract `user.id` → pass as `AgentDeps.user_id`

## NDJSON Streaming

`POST /api/agent` returns a stream of newline-delimited JSON chunks:
- `text` — agent text response (may contain `<!--UI:Component:{json}-->` markers)
- `ui_component` — extracted UI component data for frontend rendering
- `error` — error message

## Input Validation

- All user text must go through `sanitize_user_text()` from `src/nutrition/validators.py`
- Use Pydantic models from `src/api_models.py` for request/response validation
- Types in `frontend/src/types/database.types.ts` must match actual Supabase schema

## Key Endpoints

- `POST /api/agent` — streaming agent chat
- `GET/POST /api/meal-plans` — meal plan CRUD
- `GET/POST /api/daily-logs` — food tracking logs
- `GET/POST /api/favorites` — recipe favorites
- `GET/POST /api/shopping-lists` — shopping lists
- `POST /api/recalculate` — macro recalculation

## Contracts Reference

Python ↔ TypeScript type matching: `.claude/reference/api-contracts.md`

## Anti-patterns

- Never skip input sanitization on user-provided text
- Never return raw exception messages to the client
- Never use the sync Supabase client in API endpoints — use `get_async_supabase_client()`
