---
paths:
  - "skills/**"
  - "src/skill_loader.py"
  - "src/skill_tools.py"
---

# Skill System Conventions

## Architecture

```
Agent calls load_skill(name) → reads SKILL.md → calls run_skill_script(skill, script, params)
```

- `run_skill_script` injects all shared clients (supabase, anthropic, etc.) + `user_id` automatically
- Adding a new skill = only touch files inside `skills/<name>/`
- **Never grow `src/agent.py`** — it has 6 fixed tools, frozen

## Skill Script Contract

```python
async def execute(**kwargs) -> str:
    """Every skill script must follow this signature."""
    supabase = kwargs.get("supabase")      # SupabaseAsyncClient
    anthropic = kwargs.get("anthropic")     # AsyncAnthropic
    user_id = kwargs.get("user_id")         # str | None
    # ... extract what you need via kwargs.get()
```

## Skill Directory Structure

```
skills/<name>/
├── SKILL.md          # Metadata + triggers + script interface docs
├── scripts/          # Python scripts with execute(**kwargs)
└── references/       # Domain-specific rules (loaded by agent, not CLAUDE.md)
```

## Key Rules

1. **Scripts are orchestrators, not reimplementers**: Calculation/domain logic lives in `src/nutrition/` — import it, never rewrite it.
2. **`src/prompt.py` stays generic**: Skill-specific behavior (presentation formats, default params, routing exceptions) → the skill's `SKILL.md` or `references/`, NOT the system prompt.
3. **Routing failures → fix SKILL.md first**: When an eval shows the agent doesn't route to a script, the cause is usually a too-narrow SKILL.md description/triggers — not a missing hint in `src/prompt.py`.

## Available Skills (7)

`nutrition-calculating` | `meal-planning` | `food-tracking` | `shopping-list` | `weekly-coaching` | `knowledge-searching` | `body-analyzing`

## Anti-patterns

- Never add a tool wrapper in `src/agent.py` — use a skill script
- Never reimplement `src.nutrition` calculation logic in a skill script
- Never put skill-specific routing hints in `src/prompt.py`
- Never forget to document new scripts in the skill's `SKILL.md`
