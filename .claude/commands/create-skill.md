---
description: "Create or modify a skill"
---

# Create / Modify a Skill

## Objective: $ARGUMENTS

## Step 1 — Follow skill-creator

Load and follow the Anthropic skill-creator guide:

```
load_skill("skill-creator")
```

It covers everything: structure, SKILL.md format, progressive disclosure, init/package scripts.

## Step 2 — Project-specific rules (AI-Nutrition only)

Four rules that override or extend skill-creator for this project:

**1. Script entry point**
Every script in `scripts/` must expose:
```python
async def execute(**kwargs) -> str:
    """..."""
```

**2. Domain logic lives in `src/nutrition/`**
Scripts are orchestrators. Import calculations from `src.nutrition.*` — never duplicate them.
```python
from src.nutrition.calculations import calculate_bmr  # ✓
# Don't rewrite BMR in the script              # ✗
```

**3. Execution — no wrappers ever**
Document the call in SKILL.md. The agent uses `run_skill_script`:
```python
run_skill_script("skill-name", "script_name", {
    "param1": "value",
    "param2": 42,
})
```
**Never add a wrapper to `src/agent.py`.**

**4. Tests + evals**
- Unit tests in `tests/test_<script_name>.py` — mock external deps:
  - Supabase → `MagicMock` with chained `.table().select().execute()`
  - OpenAI/Anthropic → `AsyncMock` with `.create()` return
  - HTTP → `AsyncMock` with `.get()` returning `MagicMock(json=...)`
- Add eval cases to `evals/test_skill_scripts.py` (min: happy path + error case)

## Step 3 — Validate

```bash
ruff check skills/<skill-name>/scripts/
pytest evals/test_skill_loading.py -v
pytest evals/test_skill_scripts.py -v
pytest tests/ -v
```
