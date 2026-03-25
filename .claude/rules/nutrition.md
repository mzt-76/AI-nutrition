---
paths:
  - "src/nutrition/**"
  - "src/nutrition/*.py"
---

# Nutrition Engine Conventions

## Science-First Calculations

- BMR uses **Mifflin-St Jeor** exclusively. Cite sources in docstrings.
- Fat macros = 20–25% of **total** calories (goal-dependent).
- All formulas must have unit tests (happy path + error cases). Nutrition logic is critical.

## Safety Constraints (hardcoded, never bypass)

```python
MIN_CALORIES_WOMEN = 1200
MIN_CALORIES_MEN = 1500
ALLERGEN_ZERO_TOLERANCE = True
DISLIKED_FOODS_FILTERED = True  # recipe_db excludes disliked foods
```

## Tunable Constants

All pipeline-tunable parameters live in `src/nutrition/constants.py` (27 constants, organized by domain: scoring weights, macro tolerances, calorie adjustments, MILP bounds, LLM params). **Import from there — never hardcode magic numbers inline.**

```python
# CORRECT
from src.nutrition.constants import MACRO_TOLERANCE_PERCENT, PROTEIN_WEIGHT

# WRONG — magic number inline
tolerance = 0.10  # Where does this come from?
```

## Meal-Planning Pipeline

`select recipes (v2b sliding budget) → MILP per-ingredient optimize (v2f portion_optimizer_v2.py) → validate → repair`

- `ingredient_roles.py`: 155 mappings ingredient→role (protein, starch, vegetable, fat_source, fixed)
- `portion_optimizer_v2.py`: per-ingredient variables, divergence constraints, discrete items (eggs) as integers
- Full reference: `.claude/reference/meal-planning-workflow.md`

## Anti-patterns

- Never duplicate calculation logic — it lives here in `src/nutrition/`, nowhere else
- Never bypass safety constraints, even for "edge cases"
- Never use bare `dict` for agent tool parameters — use `dict[str, int] | None` (bare dict → weak JSON schema)
- Never hardcode scoring weights or tolerances — import from `constants.py`
