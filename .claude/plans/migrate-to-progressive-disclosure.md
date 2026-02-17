# Feature: Migrate to Content-Based Progressive Disclosure (Remove DynamicToolset)

Pay special attention to naming of existing utils types and models. Import from the right files etc.

## Feature Description

Migrate the AI Nutrition Assistant from DynamicToolset (private pydantic_ai API) to a **content-based progressive disclosure** architecture:
- Tool implementations move from monolithic `src/tools.py` into skill scripts (`skills/*/scripts/*.py`)
- Scripts are utility scripts: real executable Python modules that tool wrappers import from
- Remove DynamicToolset — all tools always registered via a single static FunctionToolset
- SKILL.md files reference scripts as utility executables (following Claude Skills best practices)
- **Exclude meal-planning** — will be redesigned separately

## User Story

As a developer maintaining the AI Nutrition Assistant
I want tool implementations to live inside their respective skills as utility scripts
So that each skill is self-contained, we remove the private DynamicToolset API dependency, and the codebase follows the Claude Skills progressive disclosure pattern

## Problem Statement

1. **Private API**: `from pydantic_ai.toolsets._dynamic import DynamicToolset` — will break on updates
2. **Monolithic tools.py**: ~1950 lines, all implementations in one file
3. **Complex agent.py**: DynamicToolset + SKILL_TOOLSETS + active_skills + wrapper functions = unnecessary complexity
4. **Skills not self-contained**: Script files are pseudocode, implementations live elsewhere

## Solution Statement

Move domain tool implementations from `src/tools.py` into `skills/*/scripts/*.py` as real executable Python modules. Tool wrappers in `agent.py` import from these scripts. Remove DynamicToolset — register all tools as static core tools. Skills become self-contained packages (instructions + scripts + references).

## Feature Metadata

**Feature Type**: Refactor
**Estimated Complexity**: Medium
**Primary Systems Affected**: `src/agent.py`, `src/tools.py`, `skills/*/scripts/*.py`, `src/prompt.py`
**Dependencies**: No new dependencies
**Excluded**: meal-planning skill (dysfunctional, needs full redesign)

---

## CONTEXT REFERENCES

### Relevant Codebase Files — MUST READ BEFORE IMPLEMENTING

- `src/agent.py` (637 lines) - **PRIMARY refactor target**. Remove DynamicToolset, SKILL_TOOLSETS, active_skills, get_active_skill_tools(). Simplify domain tool wrappers to import from skill scripts. Keep: `get_model()`, `AgentDeps`, core tool registrations, `add_dynamic_context`, `create_agent_deps`
- `src/tools.py` (~1954 lines) - Contains all tool implementations to extract. Keep only: `fetch_my_profile_tool` (line 256-316), `update_my_profile_tool` (line 319-502)
- `src/skill_tools.py` (210 lines) - Keep as-is. Three progressive disclosure tools (load_skill, read_skill_file, list_skill_files)
- `src/skill_loader.py` (136 lines) - Keep as-is. Skill discovery and metadata parsing
- `src/prompt.py` (105 lines) - Update progressive disclosure section
- `custom-agent-with-skills/src/agent.py` (134 lines) - **Reference pattern**: clean agent, static toolset, no DynamicToolset

### Scripts to Convert (pseudocode -> real executable)

**Excluding meal-planning (3 scripts skipped):**
- `skills/nutrition-calculating/scripts/calculate_nutritional_needs.py` - REWRITE
- `skills/weekly-coaching/scripts/calculate_weekly_adjustments.py` - REWRITE
- `skills/knowledge-searching/scripts/retrieve_relevant_documents.py` - REWRITE
- `skills/knowledge-searching/scripts/web_search.py` - REWRITE
- `skills/body-analyzing/scripts/image_analysis.py` - REWRITE

### Source Implementations (to extract from tools.py)

- `calculate_nutritional_needs_tool` (lines 74-253) → `skills/nutrition-calculating/scripts/`
- `retrieve_relevant_documents_tool` (lines 505-633) → `skills/knowledge-searching/scripts/`
- `web_search_tool` (lines 636-695) → `skills/knowledge-searching/scripts/`
- `image_analysis_tool` (lines 698-740) → `skills/body-analyzing/scripts/`
- `calculate_weekly_adjustments_tool` (lines 1653-1953) → `skills/weekly-coaching/scripts/`

### Patterns to Follow

**Utility script pattern** (from Claude Skills best practices):
```markdown
## Utility scripts
**calculate_nutritional_needs.py**: Calculate BMR, TDEE, macros
\`\`\`bash
python skills/nutrition-calculating/scripts/calculate_nutritional_needs.py
\`\`\`
```

**Script module convention** (each exports `execute()` async function):
```python
# skills/nutrition-calculating/scripts/calculate_nutritional_needs.py
"""Calculate BMR, TDEE, and target macronutrients.
Utility script — can be imported by agent tool wrapper or run standalone.
"""
import json
import logging
from src.nutrition.calculations import (
    mifflin_st_jeor_bmr, calculate_tdee, infer_goals_from_context,
    calculate_protein_target, calculate_macros,
)

logger = logging.getLogger(__name__)

async def execute(**kwargs) -> str:
    """Entry point for tool wrapper. Returns JSON string."""
    age = kwargs["age"]
    # ... implementation from tools.py ...
```

**Thin tool wrapper in agent.py** (imports from skill script):
```python
async def calculate_nutritional_needs(ctx: RunContext[AgentDeps], ...) -> str:
    """Calculate BMR, TDEE, and target macros. [Schema stays for LLM]"""
    from skills.nutrition_calculating.scripts.calculate_nutritional_needs import execute
    return await execute(age=age, gender=gender, ...)
```

---

## IMPLEMENTATION PLAN

### Phase 1: Convert Scripts (5 scripts, excluding meal-planning)

Replace pseudocode in `skills/*/scripts/*.py` with real implementations extracted from `src/tools.py`. Each script:
- Exports `async def execute(**kwargs) -> str`
- Imports domain logic from `src/nutrition/` (unchanged)
- Contains full error handling and logging
- Is also runnable standalone for testing

### Phase 2: Simplify Agent

Refactor `src/agent.py`:
- Remove `DynamicToolset` import and usage
- Remove `SKILL_TOOLSETS`, `get_active_skill_tools()`, `active_skills`
- Simplify domain tool wrappers to import from skill scripts
- Register ALL tools in one `core_tools` FunctionToolset
- Agent creation: `toolsets=[core_tools]`

### Phase 3: Clean Up

- Strip domain tool implementations from `src/tools.py` (keep profile tools)
- Update `src/prompt.py` progressive disclosure section
- Update SKILL.md files to reference scripts as utility executables
- Update tests

---

## STEP-BY-STEP TASKS

### Task 1: REWRITE `skills/nutrition-calculating/scripts/calculate_nutritional_needs.py`

- **IMPLEMENT**: Real executable with `async def execute(**kwargs) -> str`
- **SOURCE**: Extract from `src/tools.py` lines 74-253 (`calculate_nutritional_needs_tool`)
- **KWARGS**: `age, gender, weight_kg, height_cm, activity_level, goals, activities, context`
- **IMPORTS**: `from src.nutrition.calculations import mifflin_st_jeor_bmr, calculate_tdee, infer_goals_from_context, calculate_protein_target, calculate_macros`
- **KEEP**: Full error handling (ValueError, generic Exception), logging, JSON output
- **VALIDATE**: `python -c "import importlib.util; spec = importlib.util.spec_from_file_location('mod', 'skills/nutrition-calculating/scripts/calculate_nutritional_needs.py'); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); print(hasattr(mod, 'execute'))"`

### Task 2: REWRITE `skills/knowledge-searching/scripts/retrieve_relevant_documents.py`

- **IMPLEMENT**: Real executable with `async def execute(**kwargs) -> str`
- **SOURCE**: Extract from `src/tools.py` lines 505-633 (`retrieve_relevant_documents_tool`)
- **KWARGS**: `supabase, embedding_client, user_query`
- **IMPORTS**: Standard only (no src.nutrition imports needed — uses supabase RPC + openai embeddings)
- **VALIDATE**: Verify `execute` function exists and has correct signature

### Task 3: REWRITE `skills/knowledge-searching/scripts/web_search.py`

- **IMPLEMENT**: Real executable with `async def execute(**kwargs) -> str`
- **SOURCE**: Extract from `src/tools.py` lines 636-695 (`web_search_tool`)
- **KWARGS**: `query, http_client, brave_api_key, searxng_base_url`
- **VALIDATE**: Verify `execute` function exists

### Task 4: REWRITE `skills/body-analyzing/scripts/image_analysis.py`

- **IMPLEMENT**: Real executable with `async def execute(**kwargs) -> str`
- **SOURCE**: Extract from `src/tools.py` lines 698-740 (`image_analysis_tool`)
- **KWARGS**: `image_url, analysis_prompt, openai_client`
- **VALIDATE**: Verify `execute` function exists

### Task 5: REWRITE `skills/weekly-coaching/scripts/calculate_weekly_adjustments.py`

- **IMPLEMENT**: Real executable with `async def execute(**kwargs) -> str`
- **SOURCE**: Extract from `src/tools.py` lines 1653-1953 (`calculate_weekly_adjustments_tool`)
- **KWARGS**: `supabase, embedding_client, weight_start_kg, weight_end_kg, adherence_percent, hunger_level, energy_level, sleep_quality, cravings, notes`
- **IMPORTS**: `from src.nutrition.adjustments import analyze_weight_trend, detect_metabolic_adaptation, detect_adherence_patterns, generate_calorie_adjustment, generate_macro_adjustments, detect_red_flags` + `from src.nutrition.feedback_extraction import validate_feedback_metrics, check_feedback_completeness`
- **GOTCHA**: This is the second most complex tool (300 lines). Preserve ALL 11 pipeline steps
- **VALIDATE**: Verify `execute` function exists

### Task 6: REFACTOR `src/agent.py` — Remove DynamicToolset, simplify tool registration

- **REMOVE**: `from pydantic_ai.toolsets._dynamic import DynamicToolset` (line 16)
- **REMOVE**: All domain tool imports from `src.tools` (lines 33-44) — keep only `fetch_my_profile_tool, update_my_profile_tool`
- **REMOVE**: All separate domain FunctionToolset instances:
  - `_nutrition_science_tools` (lines 250-283)
  - `_meal_planning_tools` (lines 287-396)
  - `_weekly_coaching_tools` (lines 400-442)
  - `_knowledge_search_tools` (lines 446-478)
  - `_body_analysis_tools` (lines 482-499)
- **REMOVE**: `SKILL_TOOLSETS` dict (lines 505-511)
- **REMOVE**: `get_active_skill_tools()` function (lines 519-537)
- **REMOVE**: `active_skills: set[str]` from `AgentDeps` dataclass (line 113)
- **UPDATE**: Agent creation — change from `toolsets=[core_tools, DynamicToolset(...)]` to `toolsets=[core_tools]`
- **UPDATE**: `load_skill` wrapper — remove `ctx.deps.active_skills` logic (lines 141-143)
- **UPDATE**: `create_agent_deps()` — remove `active_skills=set()` parameter
- **SIMPLIFY**: Domain tool wrappers to import from skill scripts via `importlib.util`:

  ```python
  # Helper to import from hyphenated skill directories
  def _import_skill_script(skill_name: str, script_name: str):
      """Import a script module from a skill directory."""
      import importlib.util
      script_path = project_root / "skills" / skill_name / "scripts" / f"{script_name}.py"
      spec = importlib.util.spec_from_file_location(f"skill_script.{script_name}", script_path)
      module = importlib.util.module_from_spec(spec)
      spec.loader.exec_module(module)
      return module
  ```

  Then each tool wrapper becomes:
  ```python
  async def calculate_nutritional_needs(ctx: RunContext[AgentDeps], age: int, ...) -> str:
      """Calculate BMR, TDEE, and target macros. [Keep full docstring for LLM schema]"""
      module = _import_skill_script("nutrition-calculating", "calculate_nutritional_needs")
      return await module.execute(age=age, gender=gender, ...)
  ```

- **ADD**: Register ALL domain tools in `core_tools` (not separate FunctionToolsets):
  ```python
  core_tools.add_function(calculate_nutritional_needs)
  core_tools.add_function(retrieve_relevant_documents)
  core_tools.add_function(web_search)
  core_tools.add_function(image_analysis)
  core_tools.add_function(calculate_weekly_adjustments)
  # meal-planning tools: keep existing wrappers importing from src.tools for now
  core_tools.add_function(generate_weekly_meal_plan)
  core_tools.add_function(fetch_stored_meal_plan)
  core_tools.add_function(generate_shopping_list)
  ```
- **KEEP**: Meal-planning tool wrappers unchanged (still import from `src/tools.py`) — will be migrated during meal-planning redesign
- **VALIDATE**: `python -c "from src.agent import agent, create_agent_deps; print('Agent OK')"`

### Task 7: CLEAN UP `src/tools.py` — Remove migrated implementations

- **REMOVE**: `calculate_nutritional_needs_tool` (lines 74-253)
- **REMOVE**: `retrieve_relevant_documents_tool` (lines 505-633)
- **REMOVE**: `web_search_tool` (lines 636-695)
- **REMOVE**: `image_analysis_tool` (lines 698-740)
- **REMOVE**: `calculate_weekly_adjustments_tool` (lines 1653-1953)
- **REMOVE**: Unused imports (nutrition.calculations, nutrition.adjustments, nutrition.feedback_extraction)
- **KEEP**: `fetch_my_profile_tool`, `update_my_profile_tool` (profile tools — always available)
- **KEEP**: Meal-planning tools (`generate_weekly_meal_plan_tool`, `generate_shopping_list_tool`, `fetch_stored_meal_plan_tool`) — will be migrated later
- **KEEP**: Imports needed by remaining tools
- **VALIDATE**: `python -c "from src.tools import fetch_my_profile_tool, update_my_profile_tool, generate_weekly_meal_plan_tool; print('OK')"`

### Task 8: UPDATE `src/prompt.py` — Simplified progressive disclosure workflow

- **UPDATE**: Replace the `## Progressive Disclosure - Utilisation des Skills` section (lines 68-85) with:
  ```
  ## Progressive Disclosure - Utilisation des Skills

  **Tu as des outils toujours disponibles** pour profil, calculs, recherche, coaching et analyse.

  **Pour le contexte et les instructions detaillees d'un domaine :**
  1. `load_skill(skill_name)` → Charge les instructions completes (workflow, parametres, exemples)
  2. `read_skill_file(skill_name, file_path)` → Charge les references detaillees si besoin
  3. `list_skill_files(skill_name)` → Decouvre les fichiers disponibles

  **Mapping skill → outils :**
  - `nutrition-calculating` → `calculate_nutritional_needs`
  - `meal-planning` → `generate_weekly_meal_plan`, `fetch_stored_meal_plan`, `generate_shopping_list`
  - `weekly-coaching` → `calculate_weekly_adjustments`
  - `knowledge-searching` → `retrieve_relevant_documents`, `web_search`
  - `body-analyzing` → `image_analysis`

  **Workflow recommande :** Charge le skill (`load_skill`) AVANT d'utiliser ses outils pour avoir le contexte complet (workflow en etapes, regles metier, formats de presentation).
  ```
- **VALIDATE**: `python -c "from src.prompt import AGENT_SYSTEM_PROMPT; print(len(AGENT_SYSTEM_PROMPT), 'chars')"`

### Task 9: UPDATE `add_dynamic_context` in agent.py

- **UPDATE**: Remove mention of "domain tools appear after load_skill". The new message:
  ```python
  sections.append(
      "\n\n## Skills Disponibles (Progressive Disclosure)\n"
      "Charge un skill avec `load_skill(skill_name)` pour obtenir les instructions "
      "detaillees (workflow, parametres, regles metier) AVANT d'utiliser ses outils.\n\n"
      f"{skill_metadata}"
  )
  ```
- **VALIDATE**: Included in Task 7 validation

### Task 10: UPDATE SKILL.md files — Reference scripts as utility executables

For each of the 4 skills (excluding meal-planning), update the `## Scripts` section to clearly indicate they are executable:

Example for `skills/nutrition-calculating/SKILL.md`:
```markdown
## Scripts

**calculate_nutritional_needs.py**: Calcul BMR/TDEE/macros complet
- Execute via l'outil `calculate_nutritional_needs` de l'agent
- Implementation de reference : `scripts/calculate_nutritional_needs.py`
- Pipeline : BMR (Mifflin-St Jeor) → TDEE → inference objectifs → macros
```

- **FILES**: nutrition-calculating, weekly-coaching, knowledge-searching, body-analyzing SKILL.md
- **VALIDATE**: Manual review — verify each SKILL.md references its scripts correctly

### Task 11: UPDATE tests for new architecture

- **UPDATE**: `tests/test_agent_basic.py` — Remove references to `DynamicToolset`, `SKILL_TOOLSETS`, `active_skills`, `get_active_skill_tools`
- **UPDATE**: Any test importing domain tools from `src.tools` that were removed — update to import from skill scripts or adjust mocking
- **KEEP**: Tests for meal-planning tools unchanged (still in tools.py)
- **ADD**: Basic import test for each skill script:
  ```python
  def test_skill_scripts_importable():
      """Verify all migrated skill scripts have execute() function."""
      import importlib.util
      scripts = [
          ("nutrition-calculating", "calculate_nutritional_needs"),
          ("knowledge-searching", "retrieve_relevant_documents"),
          ("knowledge-searching", "web_search"),
          ("body-analyzing", "image_analysis"),
          ("weekly-coaching", "calculate_weekly_adjustments"),
      ]
      for skill, script in scripts:
          path = Path(f"skills/{skill}/scripts/{script}.py")
          spec = importlib.util.spec_from_file_location("test_mod", path)
          mod = importlib.util.module_from_spec(spec)
          spec.loader.exec_module(mod)
          assert hasattr(mod, "execute"), f"{skill}/{script} missing execute()"
  ```
- **VALIDATE**: `pytest tests/ -v --tb=short`

---

## TESTING STRATEGY

### Unit Tests

- Each skill script's `execute()` function tested with mock dependencies
- `_import_skill_script` helper tested for correct module loading
- Error cases: missing script, script without execute(), runtime errors

### Integration Tests

- Agent creates successfully with new `toolsets=[core_tools]`
- Tool wrapper → skill script delegation works end-to-end
- load_skill still returns SKILL.md body correctly

### Edge Cases

- Skill script raises exception → tool wrapper returns JSON error
- Missing kwargs → script validates and returns helpful error
- Concurrent tool calls → importlib thread safety (Python GIL handles this)

---

## VALIDATION COMMANDS

### Tier 1: Required (Must Pass)

```bash
# Linting
ruff format src/ tests/ && ruff check src/ tests/

# Agent imports
python -c "from src.agent import agent, create_agent_deps; print('Agent OK')"

# Tools imports (remaining in tools.py)
python -c "from src.tools import fetch_my_profile_tool, update_my_profile_tool, generate_weekly_meal_plan_tool; print('Tools OK')"

# Unit tests
pytest tests/test_skill_tools.py tests/test_skill_loader.py -v

# Full test suite
pytest tests/ -v --tb=short
```

### Tier 2: Recommended

```bash
# Type checking
mypy src/agent.py src/tools.py --ignore-missing-imports

# Manual smoke test
python -m src.cli
# Type: "Calcule mes besoins: 35 ans, homme, 87kg, 178cm, modéré"
# Verify: calculation works via skill script delegation
```

---

## ACCEPTANCE CRITERIA

- [ ] `DynamicToolset` import completely removed from codebase
- [ ] `SKILL_TOOLSETS`, `get_active_skill_tools()`, `active_skills` removed
- [ ] All 5 skill scripts (excluding meal-planning) are real executable Python modules with `async def execute(**kwargs) -> str`
- [ ] Tool wrappers in agent.py import from skill scripts via `_import_skill_script`
- [ ] Agent uses `toolsets=[core_tools]` (single static FunctionToolset)
- [ ] `src/tools.py` no longer contains migrated tool implementations (keeps profile + meal-planning tools)
- [ ] Meal-planning tools untouched (still import from src/tools.py)
- [ ] System prompt updated with simplified progressive disclosure workflow
- [ ] SKILL.md files reference scripts as utility executables
- [ ] All tests pass
- [ ] `ruff check` passes with zero errors

---

## COMPLETION CHECKLIST

- [ ] All 11 tasks completed in order
- [ ] Each task validation passed
- [ ] All Tier 1 validation commands pass
- [ ] Full test suite passes
- [ ] No linting errors
- [ ] Agent starts and responds to queries
- [ ] Skills are self-contained (script + instructions + references)

---

## NOTES

**Why not `run_skill_action`:**
The existing skill_tools (load_skill, read_skill_file, list_skill_files) are sufficient for skill manipulation. Domain tools stay registered with proper schemas so the LLM knows their parameters. Scripts are utility implementations referenced by SKILL.md and imported by tool wrappers.

**Why keep domain tools registered:**
The LLM needs typed parameter schemas to know what arguments to pass. Without registered tools, the LLM would need a generic tool with kwargs dict, losing type safety. Keeping tools registered but delegating to skill scripts gives us both: proper schemas + self-contained skills.

**Meal-planning excluded:**
The meal-planning skill is dysfunctional and will need a total redesign. Its 3 tool implementations stay in `src/tools.py` and its wrappers in `agent.py` remain as-is. This avoids scope creep.

**Script loading:**
Skill scripts loaded via `importlib.util.spec_from_file_location()` (file-path based, no `__init__.py` needed). No package import constraints with hyphenated directory names.

**What stays unchanged:**
- `src/nutrition/` modules (all domain logic)
- `src/skill_loader.py`, `src/skill_tools.py`
- `src/clients.py`
- `sql/`
- `skills/*/references/`
- Meal-planning tools and scripts

**Confidence Score: 8/10**
- High confidence: clear pattern, implementations are copy-paste from tools.py, reference project validates approach
- Risk: importlib loading of hyphenated paths needs testing, some tests may reference removed code
