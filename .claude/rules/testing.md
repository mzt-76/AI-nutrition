---
paths:
  - "tests/**"
  - "evals/**"
---

# Testing Conventions

## tests/ vs evals/ — One Rule

Ask: "Is a real LLM making a decision here?"
- **Yes → `evals/`**: real LLM behavior — routing, param extraction, response quality. Scored not asserted. Run on demand before releases.
- **No → `tests/`**: deterministic logic — calculations, validators, formatters, DB operations, agent structure with `FunctionModel`. Always passes. Runs on every commit.

## Eval Requirements

- **Always define `TEST_USER_PROFILE`** at the top of every eval file with ALL required fields:
  ```python
  TEST_USER_PROFILE = {
      "age": 30, "gender": "male", "height_cm": 180, "weight_kg": 80,
      "activity_level": "moderately_active", "goals": ["maintain_weight"]
  }
  ```
- **Evals needing DB access** (meal-planning, weekly-coaching) must use `create_agent_deps(user_id=...)` with a real Supabase user ID. Without `user_id`, the skill fails silently and the agent improvises.

## CI Safety

Tests must pass in CI where only fake env vars exist:
- **New env var?** → add a fake value in `.github/workflows/python-unit-tests.yml` env section
- **Test needs real DB/API?** → mark it `@requires_real_db` (defined in `tests/test_openfoodfacts_client.py`)
- **Avoid top-level code that crashes on missing env vars** — prefer lazy init or `if os.getenv(...)`

Full checklist: `.claude/reference/ci-best-practices.md`

## Supabase Mock Pattern

```python
from unittest.mock import AsyncMock, MagicMock

# Chain methods = MagicMock, .execute() = AsyncMock
mock_table = MagicMock()
mock_table.select.return_value.eq.return_value.execute = AsyncMock(
    return_value=MagicMock(data=[{"id": "123"}])
)
```

## Lint Before Commit

```bash
ruff format src/ tests/ && ruff check src/ tests/ && mypy src/
```

## Anti-patterns

- Never let a test hit a real service in CI — use `@requires_real_db` or mock
- Never rely on implicit profile data mid-eval-file — define `TEST_USER_PROFILE` at top
- Never put LLM-dependent tests in `tests/` — they belong in `evals/`
- Never skip the lint step before committing
