---
description: "Create a new skill from conversation context and objective"
---

# Create a New Skill

## Objective: $ARGUMENTS

## Mission

Create a **complete, eval-validated skill** based on the conversation context and the objective above. The skill must follow the established architecture, reuse domain logic from `src/nutrition/`, and include structured eval cases for validation.

## Step 0: Load Context

Read these files to understand patterns and constraints:

- Best practices & patterns: @.claude/reference/skill-creation-guide.md
- Skill loader (discovery logic): @src/skill_loader.py
- Existing eval suite (add your cases here): @evals/test_skill_scripts.py
- Existing skill loading evals: @evals/test_skill_loading.py
- Agent tool wrappers (you may need to add one): @src/tools.py

Use skill-creator to design it : skills\skill-creator

## Step 1: Design the Skill

Based on the conversation context and the objective, determine:

1. **Skill name** (kebab-case, e.g., `meal-timing`)
2. **Category** (nutrition, coaching, search, analysis, planning, meta)
3. **Scripts needed** — what `execute()` functions are required
4. **Domain logic** — which `src/nutrition/*.py` functions to reuse (NEVER duplicate)
5. **External deps** — what needs mocking (Supabase, OpenAI, HTTP, or none)
6. **References** — what domain docs should live in `references/`

Ask the user if any of these are unclear before proceeding.

## Step 2: Create Skill Directory

Create the skill structure:

```
skills/<skill-name>/
├── SKILL.md
├── scripts/
│   └── <script_name>.py
└── references/       (if needed)
    └── <topic>.md
```

### SKILL.md

Follow the exact format from the guide — include `name`, `description`, `category` in frontmatter, `## Quand utiliser`, `## Outils disponibles`, `## Références`.

### Script(s)

Follow the script pattern strictly:
- `async def execute(**kwargs) -> str`
- Import domain logic from `src.nutrition.*`
- Structured error handling (ValueError → VALIDATION_ERROR, Exception → SCRIPT_ERROR)
- Return JSON strings for structured data
- Log with context

## Step 3: Add Agent Tool Wrapper (if needed)

If this skill needs to be callable as an agent tool, add a wrapper in `src/tools.py`:

```python
@agent.tool
async def <tool_name>(ctx: RunContext[AgentDeps], **params) -> str:
    """<Agent-optimized docstring with Use this when / Do NOT use>."""
    script = _load_skill_script("skills/<skill-name>/scripts/<script>.py")
    return await script.execute(supabase=ctx.deps.supabase, **params)
```

## Step 4: Write Eval Cases

Add eval cases to `evals/test_skill_scripts.py`:

1. **Add script path** to the `SCRIPTS` dict
2. **Create task function** that loads the script and builds mocks from `_` prefixed input keys
3. **Create dataset function** with at minimum:
   - 1 happy path case
   - 1 edge case
   - 1 validation error case
   - 1 external dependency error case (if applicable)
4. **Create pytest test function** that runs the dataset
5. Use existing evaluators: `IsValidJSON`, `JSONHasKey`, `JSONFieldEquals`, `JSONErrorCode`, `ContainsSubstring`, `MinLength`, `NoError`, `CaloriesInRange`, `JSONNumericFieldInRange`

## Step 5: Validate

Run these commands in order:

```bash
# 1. Lint the new files
ruff check skills/<skill-name>/scripts/ evals/test_skill_scripts.py

# 2. Run skill loading evals (ensure discovery works)
pytest evals/test_skill_loading.py -v

# 3. Run script evals (ensure new cases pass)
pytest evals/test_skill_scripts.py -v

# 4. Run ALL evals (no regressions)
pytest evals/ -v

# 5. Run full test suite (no regressions)
pytest tests/ -v
```

ALL commands must pass with 0 failures before the skill is considered complete.

## Step 6: Quick Validate with skill-creator

If available, run the skill-creator's validation script:

```python
# Load and run quick_validate
python -c "
import asyncio
from skills.skill_creator.scripts.quick_validate import execute
result = asyncio.run(execute(skill_name='<skill-name>'))
print(result)
"
```

## Deliverables

When done, report:

1. **Skill path**: `skills/<skill-name>/`
2. **Scripts created**: list of scripts with one-line descriptions
3. **Eval cases added**: count and names
4. **Validation results**: all 5 commands pass/fail
5. **Agent tool wrapper**: added to `src/tools.py` (yes/no + function name)
