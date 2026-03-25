---
paths:
  - "scripts/**"
---

# Scripts Conventions

## LLM-Free Rule

Scripts in `scripts/` must **never** import `anthropic`, `openai`, or any LLM client. They may only use:
- `src.nutrition.*`
- `src.clients.get_supabase_client()` (sync client)
- stdlib and third-party non-LLM libraries

If a task requires an LLM, it belongs in `skills/` as a skill script instead.

**This is enforced by `tests/test_scripts_no_llm.py`.**

## Imports

Always use `src.` prefix:
```python
from src.nutrition.calculations import calculate_macros
from src.clients import get_supabase_client
```

## Anti-patterns

- Never import `anthropic`, `openai`, or any LLM client in `scripts/`
- Never use the async Supabase client in scripts — use `get_supabase_client()` (sync)
