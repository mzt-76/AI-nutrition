# Skill Creation Guide — Best Practices & Reference

## Skill Architecture

Each skill is a self-contained domain module under `skills/<skill-name>/`:

```
skills/<skill-name>/
├── SKILL.md              # Metadata: name, description, when-to-use, tools list
├── scripts/              # Executable Python scripts
│   └── <script_name>.py  # async execute(**kwargs) -> str
└── references/           # Domain docs, formulas, protocols
    └── <topic>.md
```

## SKILL.md Format

```markdown
---
name: <skill-name>
description: <one-line description>
category: <nutrition|coaching|search|analysis|planning|meta>
---

# <Skill Display Name>

## Quand utiliser

- <When the agent should invoke this skill>
- <Trigger conditions>

## Outils disponibles

| Outil | Script | Description |
|-------|--------|-------------|
| <tool_name> | `scripts/<script>.py` | <what it does> |

## Références

- `references/<file>.md` — <what it contains>
```

## Script Pattern

Every skill script MUST follow this pattern:

```python
"""<One-line description>.

Utility script — can be imported by agent tool wrapper or run standalone.
<Additional context about what it does and why>.

Source: <origin of this logic>
"""

import json
import logging

# Import domain logic from src.nutrition.* — NEVER duplicate calculations
from src.nutrition.<module> import <functions>

logger = logging.getLogger(__name__)


async def execute(**kwargs) -> str:
    """<What this script does>.

    Args:
        <param>: <description and constraints>.

    Returns:
        <Format description — usually JSON string or formatted text>.
    """
    # Extract required params
    param = kwargs["required_param"]
    optional = kwargs.get("optional_param", "default")

    try:
        # Core logic — delegate to src.nutrition.* for calculations
        result = do_something(param)

        return json.dumps(result, indent=2)

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return json.dumps({"error": str(e), "code": "VALIDATION_ERROR"})
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return json.dumps({"error": "Internal error", "code": "SCRIPT_ERROR"})
```

### Key Rules

1. **Single entry point**: `async def execute(**kwargs) -> str`
2. **Domain logic lives in `src/nutrition/`** — scripts are orchestrators, not calculators
3. **Return JSON strings** for structured data, plain text for human-readable output
4. **Catch ValueError** for validation errors with code `VALIDATION_ERROR`
5. **Catch Exception** for unexpected errors with a descriptive code
6. **Log with context** — include key parameters in log messages
7. **No global state** — scripts must be stateless and idempotent

## Mocking Strategy for External Dependencies

| Dependency | Mock Approach |
|-----------|---------------|
| Pure calculation (src.nutrition.*) | **No mock needed** — test directly |
| Supabase (DB reads/writes) | `MagicMock` with chained `.table().select().execute()` |
| OpenAI (embeddings, chat, vision) | `AsyncMock` with configured `.create()` return |
| HTTP client (Brave, APIs) | `AsyncMock` with `.get()` returning `MagicMock(json=...)` |

## Eval Pattern for Validation

Every script should have eval cases in `evals/test_skill_scripts.py`:

```python
# 1. Task function: loads script and calls execute() with mocks
async def _my_script_task(inputs: dict) -> str:
    params = {k: v for k, v in inputs.items() if not k.startswith("_")}
    # Build mocks from _prefixed keys
    mock_client = _mock_factory(inputs.get("_mock_data"))
    module = _load_script(SCRIPTS["my_script"])
    return await module.execute(client=mock_client, **params)

# 2. Dataset: cases with inputs + evaluators
def my_script_dataset() -> Dataset:
    return Dataset(
        name="my_script",
        cases=[
            Case(
                name="happy_path",
                inputs={"param": "value"},
                evaluators=(IsValidJSON(), JSONHasKey(key="result")),
            ),
            Case(
                name="validation_error",
                inputs={"param": "invalid"},
                evaluators=(JSONErrorCode(code="VALIDATION_ERROR"),),
            ),
        ],
    )

# 3. Pytest test
@pytest.mark.asyncio
async def test_my_script_eval():
    report = await my_script_dataset().evaluate(task=_my_script_task)
    report.print()
    assert len(report.failures) == 0
```

### Available Evaluators

| Evaluator | Purpose |
|-----------|---------|
| `IsValidJSON()` | Output parses as JSON |
| `JSONHasKey(key=...)` | JSON has specific key |
| `JSONFieldEquals(key=..., expected=...)` | Field matches value |
| `JSONErrorCode(code=...)` | Error response has code |
| `CaloriesInRange(min_cal=..., max_cal=...)` | target_calories in bounds |
| `JSONNumericFieldInRange(key=..., min_val=..., max_val=...)` | Numeric field in range |
| `ContainsSubstring(substring=...)` | Output contains text |
| `MinLength(min_chars=...)` | Output meets length |
| `NoError()` | Doesn't start with "Error" |

## Existing Skills Reference

| Skill | Scripts | Mocking |
|-------|---------|---------|
| `nutrition-calculating` | `calculate_nutritional_needs.py` | None (pure calc) |
| `knowledge-searching` | `retrieve_relevant_documents.py`, `web_search.py` | Supabase RPC + embedding, HTTP |
| `body-analyzing` | `image_analysis.py` | OpenAI Vision |
| `weekly-coaching` | `calculate_weekly_adjustments.py` | Supabase tables |
| `meal-planning` | `generate_weekly_meal_plan.py`, `generate_shopping_list.py`, `fetch_stored_meal_plan.py` | Supabase + OpenAI |
| `skill-creator` | `init_skill.py`, `quick_validate.py`, `package_skill.py` | Filesystem |

## File Paths Quick Reference

- Skill loader: `src/skill_loader.py`
- Skill agent tools: `src/skill_tools.py`
- Agent tool wrappers: `src/tools.py`
- Domain logic: `src/nutrition/*.py`
- Eval suite: `evals/test_skill_scripts.py`
- Eval loading tests: `evals/test_skill_loading.py`
- Existing skills: `skills/*/SKILL.md`
- Skill-creator scripts: `skills/skill-creator/scripts/`
