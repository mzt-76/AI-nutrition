# Feature: Weekly Meal Plan Generator Tool

The following plan is comprehensive and ready for implementation. **IMPORTANT**: Validate documentation links, codebase patterns, and task feasibility before starting implementation. Pay special attention to existing naming conventions, import paths, and database schema.

## Feature Description

Create a Pydantic AI tool that generates personalized 7-day meal plans for users based on their nutritional profile, goals, allergies, and preferences. The tool uses GPT-4o to generate complete recipes with ingredients, quantities, instructions, and nutritional information, stores the meal plan in the database, and enforces zero-tolerance allergen safety checks.

This feature enables the AI nutrition coach to provide weekly meal planning services, a core value proposition mentioned in the PRD: "generates weekly personalized meal plans with recipes and shopping lists."

## User Story

**As a** nutrition coaching app user
**I want to** receive a complete 7-day meal plan tailored to my calorie/macro targets, allergies, and food preferences
**So that** I can follow a structured nutrition plan without spending hours researching recipes and calculating macros

## Problem Statement

Currently, the AI nutrition coach can calculate BMR/TDEE and provide macro targets, but cannot generate actionable weekly meal plans. Users receive numerical targets (e.g., "3108 kcal, 156g protein") but no concrete meal structure to achieve them. This gap prevents users from translating nutritional guidance into daily eating habits.

**Key challenges:**
- Recipe database is empty (`recipes` table has 0 rows)
- Need to balance macros across 21+ meals per week (7 days × 3+ meals)
- **CRITICAL**: Must enforce zero-tolerance allergen safety
- Must respect user preferences (disliked foods, cuisines, prep time limits)
- Need structured meal plan storage for future reference

## Solution Statement

Implement `generate_weekly_meal_plan` as a Pydantic AI tool that:

1. **Fetches user context** from `my_profile` table (allergies, targets, preferences)
2. **Queries RAG** for scientific meal planning context (nutrient timing, meal frequency research)
3. **Uses GPT-4o with JSON mode** to generate a structured 7-day meal plan with complete recipes
4. **Validates allergen safety** using a dedicated validation function (zero tolerance)
5. **Stores meal plan** in `meal_plans` table with JSONB plan_data
6. **Returns structured JSON** containing the full meal plan for user presentation

This approach leverages LLM recipe generation (since recipe DB is empty) while maintaining strict safety constraints and scientific grounding through RAG retrieval.

## Feature Metadata

**Feature Type**: New Capability
**Estimated Complexity**: High
**Primary Systems Affected**:
- Agent tools layer (`tools.py`)
- Nutrition domain logic (`nutrition/meal_planning.py` - NEW)
- Safety validators (`nutrition/validators.py` - NEW)
- Database (`meal_plans` table in Supabase)
- Agent orchestrator (`agent.py` - tool registration)
- System prompt (`prompt.py` - capability documentation)

**Dependencies**:
- `openai>=1.71.0` (GPT-4o with JSON mode)
- `supabase>=2.15.0` (database storage)
- `pydantic-ai>=0.0.53` (tool framework)
- Existing: `fetch_my_profile_tool`, `retrieve_relevant_documents_tool`

---

## CONTEXT REFERENCES

### Relevant Codebase Files - IMPORTANT: READ THESE BEFORE IMPLEMENTING!

**Existing Tool Patterns:**
- `4_Pydantic_AI_Agent/tools.py` (lines 31-129) - **WHY**: Pattern for async tool implementation with try/except error handling, JSON returns, logging
- `4_Pydantic_AI_Agent/tools.py` (lines 131-180) - **WHY**: Profile fetching pattern with incomplete profile detection
- `4_Pydantic_AI_Agent/tools.py` (lines 182-329) - **WHY**: Update profile pattern with validation and field normalization
- `4_Pydantic_AI_Agent/tools.py` (lines 331-400) - **WHY**: RAG retrieval pattern for knowledge base queries

**Agent Registration Patterns:**
- `4_Pydantic_AI_Agent/agent.py` (lines 78-97) - **WHY**: AgentDeps dataclass structure for dependency injection
- `4_Pydantic_AI_Agent/agent.py` (lines 124-164) - **WHY**: Tool decorator pattern with RunContext[AgentDeps]
- `4_Pydantic_AI_Agent/agent.py` (lines 167-183) - **WHY**: Profile tool registration example
- `4_Pydantic_AI_Agent/agent.py` (lines 339-362) - **WHY**: create_agent_deps() function for initializing dependencies

**Calculation Patterns:**
- `4_Pydantic_AI_Agent/nutrition/calculations.py` (lines 36-88) - **WHY**: Validation pattern (age, weight, height ranges) with raise ValueError
- `4_Pydantic_AI_Agent/nutrition/calculations.py` (lines 186-246) - **WHY**: Function returning tuple with multiple values (protein_g, per_kg, range)
- `4_Pydantic_AI_Agent/nutrition/calculations.py` (lines 14-18) - **WHY**: Logging pattern with structured logger.info()

**System Prompt Patterns:**
- `4_Pydantic_AI_Agent/prompt.py` (lines 46-60) - **WHY**: Safety constraints section with allergen zero tolerance rules
- `4_Pydantic_AI_Agent/prompt.py` (lines 106-121) - **WHY**: Allergen filtering workflow by family (arachides → all peanut products)
- `4_Pydantic_AI_Agent/prompt.py` (lines 88-95) - **WHY**: RAG-first workflow for nutrition questions

**Project Rules:**
- `CLAUDE.md` (lines 1-50) - **WHY**: Core principles (Science-First, Type Safety, Safety Constraints, Async, Documentation)
- `CLAUDE.md` (lines 76-100) - **WHY**: Code style conventions (snake_case, Google docstrings, structured logging)
- `CLAUDE.md` (lines 213-242) - **WHY**: Common pattern examples (Pydantic AI tool, Supabase RAG query)

### New Files to Create

1. **`4_Pydantic_AI_Agent/nutrition/meal_planning.py`**
   Purpose: Helper functions for meal plan generation
   - `format_meal_plan_for_llm_prompt()` - Build LLM prompt with profile context
   - `parse_meal_plan_response()` - Validate and parse LLM JSON response
   - `calculate_daily_totals()` - Sum macros for a day's meals
   - `categorize_meal_type()` - Map meal types to time of day

2. **`4_Pydantic_AI_Agent/nutrition/validators.py`**
   Purpose: Safety validation functions
   - `validate_allergens()` - **CRITICAL** Check no allergens in meal plan (returns list of violations)
   - `validate_daily_macros()` - Ensure daily totals within ±10% tolerance
   - `validate_meal_plan_structure()` - Verify required JSON fields present

3. **`4_Pydantic_AI_Agent/tests/test_meal_planning.py`**
   Purpose: Unit tests for meal planning functions
   - Test allergen validation (edge cases: family matching, hidden allergens)
   - Test macro validation (tolerance ranges)
   - Test meal plan structure validation

4. **`4_Pydantic_AI_Agent/tests/test_validators.py`**
   Purpose: Unit tests for safety validators
   - Test zero tolerance allergen detection
   - Test allergen family matching (arachides → peanut butter, etc.)
   - Test false positives (noix de coco vs fruits à coque)

### Relevant Documentation - READ BEFORE IMPLEMENTING!

**OpenAI Structured Outputs:**
- [Structured Outputs Guide](https://platform.openai.com/docs/guides/structured-outputs)
  **Specific section**: JSON mode with `response_format={"type": "json_object"}`
  **WHY**: Required for forcing GPT-4o to return valid JSON meal plans reliably

- [Introducing Structured Outputs in the API](https://openai.com/index/introducing-structured-outputs-in-the-api/)
  **Specific section**: Models supporting structured outputs (gpt-4o-2024-08-06 and later)
  **WHY**: Verify GPT-4o supports JSON mode (100% reliability for schema adherence)

**Pydantic AI Tool Patterns:**
- [Pydantic AI Tools Documentation](https://ai.pydantic.dev/)
  **Specific section**: @agent.tool decorator and RunContext dependency injection
  **WHY**: Official pattern for tool registration with type-safe dependencies

- [Multi-Agent Patterns](https://ai.pydantic.dev/multi-agent-applications/)
  **Specific section**: Tool delegation and orchestration patterns
  **WHY**: Understanding how tools can call other tools (e.g., meal planner calling fetch_my_profile)

**Project-Specific:**
- `PRD.md` (lines 686-820) - Database schema for `meal_plans`, `my_profile`, `ingredients_reference` tables
- `PRD.md` (lines 336-395) - Tool 1 specification for meal plan generator (original n8n design)
- `PROJECT_STATUS.md` (lines 70-77) - Current database state (recipes empty, meal_plans empty)

### Patterns to Follow

**1. Async Tool Function Pattern** (from `tools.py:31-129`)
```python
async def tool_name_tool(
    param1: Type,
    param2: Type | None = None
) -> str:
    """
    Brief description.

    Args:
        param1: Description
        param2: Optional description

    Returns:
        JSON string with result or error

    Example:
        >>> result = await tool_name_tool(value1, value2)
    """
    try:
        logger.info(f"Tool called with param1={param1}")

        # Main logic here
        result = {"key": "value"}

        logger.info(f"Tool completed successfully")
        return json.dumps(result, indent=2)

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return json.dumps({"error": str(e), "code": "VALIDATION_ERROR"})
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return json.dumps({"error": "Internal error", "code": "INTERNAL_ERROR"})
```

**2. Supabase Database Insert Pattern** (from `tools.py:297-314`)
```python
# Check if record exists
check_response = supabase.table("table_name").select("id").limit(1).execute()

if check_response.data:
    # Update existing
    record_id = check_response.data[0]["id"]
    response = supabase.table("table_name").update(data).eq("id", record_id).execute()
else:
    # Insert new
    response = supabase.table("table_name").insert(data).execute()

if response.data:
    return json.dumps({"success": True, "data": response.data[0]})
else:
    return json.dumps({"error": "Operation failed", "code": "DB_ERROR"})
```

**3. Error Handling Pattern** (from `tools.py:123-128`)
```python
except ValueError as e:
    logger.error(f"Validation error in tool_name: {e}")
    return json.dumps({"error": str(e), "code": "VALIDATION_ERROR"})
except Exception as e:
    logger.error(f"Unexpected error in tool_name: {e}", exc_info=True)
    return json.dumps({"error": "Internal error message", "code": "ERROR_CODE"})
```

**4. Logging Pattern** (from `nutrition/calculations.py:86-87, 117`)
```python
logger = logging.getLogger(__name__)

logger.info(f"Calculating needs: age={age}, weight={weight_kg}kg")
logger.info(f"Calculation complete: {target_calories} kcal")
logger.error(f"Validation failed: {e}", exc_info=True)
```

**5. JSON Return Pattern** (from `tools.py:97-120`)
```python
result = {
    "field1": value1,
    "field2": value2,
    "nested": {
        "subfield": value3
    },
    "list_field": [item1, item2]
}

return json.dumps(result, indent=2)  # Always indent=2 for readability
```

**6. Agent Tool Registration Pattern** (from `agent.py:124-164`)
```python
@agent.tool
async def tool_function_name(
    ctx: RunContext[AgentDeps],
    param1: type,
    param2: type | None = None
) -> str:
    """Tool docstring - passed to LLM as tool description."""
    logger.info("Tool called: tool_function_name")
    return await tool_implementation_function(
        ctx.deps.supabase,
        ctx.deps.other_dependency,
        param1,
        param2
    )
```

**7. Validation with ValueError Pattern** (from `nutrition/calculations.py:69-74`)
```python
if not 18 <= age <= 100:
    raise ValueError(f"Age must be between 18 and 100, got {age}")
if weight_kg < 40:
    raise ValueError(f"Weight must be at least 40kg, got {weight_kg}")
```

**8. GPT-4 Vision Pattern** (from `tools.py:484-504`, adapt for JSON mode)
```python
response = await openai_client.chat.completions.create(
    model="gpt-4o",  # Use GPT-4o for JSON mode
    messages=[
        {"role": "user", "content": prompt}
    ],
    response_format={"type": "json_object"},  # Force JSON mode
    max_tokens=4000  # Increase for meal plan generation
)

result = response.choices[0].message.content
meal_plan_json = json.loads(result)  # Parse JSON response
```

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation - Safety Validators

Create the critical safety validation infrastructure before any meal plan generation.

**Rationale**: Allergen validation must be bulletproof. Build and test this independently before integrating with LLM generation.

**Tasks:**
1. Create `nutrition/validators.py` with allergen family mappings
2. Implement `validate_allergens()` function with comprehensive family matching
3. Implement `validate_daily_macros()` for macro tolerance checks
4. Implement `validate_meal_plan_structure()` for JSON schema validation
5. Write unit tests with edge cases (hidden allergens, false positives)

### Phase 2: Core Implementation - Meal Plan Generator

Build the main tool that orchestrates profile fetching, RAG querying, LLM generation, and validation.

**Rationale**: With validators in place, we can safely generate meal plans and validate before storing.

**Tasks:**
1. Create `nutrition/meal_planning.py` with helper functions
2. Implement `generate_weekly_meal_plan_tool()` in `tools.py`
3. Implement GPT-4o JSON mode generation with comprehensive prompt
4. Integrate allergen validation (reject meal plan if violations found)
5. Store validated meal plan in `meal_plans` table

### Phase 3: Integration - Agent Registration

Connect the new tool to the Pydantic AI agent and update documentation.

**Rationale**: Make the tool available to the agent and document its usage in the system prompt.

**Tasks:**
1. Register tool in `agent.py` with `@agent.tool` decorator
2. Update `prompt.py` to document meal planning capability
3. Add tool usage examples to system prompt
4. Test agent tool calling in conversation

### Phase 4: Testing & Validation

Comprehensive testing of the end-to-end meal planning workflow.

**Rationale**: High-stakes feature (allergen safety) requires extensive testing before production use.

**Tasks:**
1. Unit tests for all helper functions
2. Integration tests for tool workflow
3. Edge case tests (allergen families, empty profile, invalid dates)
4. Manual testing with real user profile

---

## STEP-BY-STEP TASKS

Execute every task in order, top to bottom. Each task is atomic and independently testable.

### CREATE `nutrition/validators.py`

**IMPLEMENT**: Allergen safety validation functions with family matching

**PATTERN**: Mirror validation pattern from `nutrition/calculations.py:69-74` (raise ValueError)

**IMPORTS**:
```python
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)
```

**CRITICAL LOGIC** - Allergen Family Mappings:
```python
ALLERGEN_FAMILIES = {
    "arachides": ["cacahuète", "cacahuete", "peanut", "arachide", "beurre de cacahuète",
                  "beurre de cacahuete", "peanut butter", "sauce satay", "pad thai"],
    "fruits à coque": ["amande", "noix", "noisette", "cajou", "pistache", "pécan", "macadamia",
                       "almond", "walnut", "hazelnut", "cashew", "pistachio", "pecan"],
    "lactose": ["lait", "yaourt", "fromage", "crème", "beurre", "milk", "yogurt", "cheese",
                "cream", "butter", "yoghurt"],
    "gluten": ["blé", "pain", "pâtes", "farine", "wheat", "bread", "pasta", "flour", "seigle", "orge"],
    "oeuf": ["oeuf", "oeufs", "egg", "eggs", "mayonnaise"],
    "soja": ["soja", "soy", "tofu", "edamame", "tempeh", "miso"],
    "poisson": ["poisson", "fish", "thon", "saumon", "truite", "morue", "tuna", "salmon"],
    "fruits de mer": ["crevette", "crabe", "homard", "moule", "huître", "shrimp", "crab",
                      "lobster", "mussel", "oyster"],
    "sésame": ["sésame", "sesame", "tahini", "tahin"]
}

# Special cases: NOT allergens despite name confusion
ALLERGEN_FALSE_POSITIVES = {
    "noix de coco": "fruits à coque",  # Coconut is NOT a tree nut (it's a drupe)
    "muscade": "fruits à coque",  # Nutmeg is NOT a nut (it's a seed)
}
```

**FUNCTION 1**: `validate_allergens(meal_plan: dict, user_allergens: list[str]) -> list[str]`
- Iterate through all days → meals → ingredients
- For each ingredient, check against user allergens AND allergen families
- Check false positives (allow noix de coco if only fruits à coque allergy)
- Return list of violation strings (empty if safe)
- Log all checks for debugging

**FUNCTION 2**: `validate_daily_macros(daily_totals: dict, targets: dict, tolerance: float = 0.10) -> dict`
- Check calories, protein, carbs, fat within ±10% of targets
- Return dict with `{"valid": bool, "violations": list[str]}`

**FUNCTION 3**: `validate_meal_plan_structure(meal_plan: dict) -> dict`
- Check required fields: meal_plan_id, start_date, days (list of 7)
- Each day must have: day, meals (list), daily_totals
- Each meal must have: meal_type, recipe_name, ingredients, nutrition
- Return `{"valid": bool, "missing_fields": list[str]}`

**GOTCHA**: Case-insensitive matching (user might say "Arachides" or "arachides")

**GOTCHA**: Partial matches (ingredient "beurre de cacahuète bio" must match "cacahuète" keyword)

**VALIDATE**: Create test file `tests/test_validators.py` and run:
```bash
pytest tests/test_validators.py -v
```

---

### CREATE `nutrition/meal_planning.py`

**IMPLEMENT**: Helper functions for meal plan generation workflow

**PATTERN**: Mirror calculation pattern from `nutrition/calculations.py` (pure functions with logging)

**IMPORTS**:
```python
from typing import Dict, List, Literal
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
```

**FUNCTION 1**: `build_meal_plan_prompt(profile: dict, rag_context: str, start_date: str, meal_structure: str, notes: str = None) -> str`
- Extract profile data (calories, macros, allergies, preferences)
- Build comprehensive prompt for GPT-4o with JSON structure requirements
- Include meal structure details (3_meals_2_snacks, 4_meals, etc.)
- Include RAG scientific context
- Include allergen warnings in bold uppercase
- Return formatted prompt string

**MEAL STRUCTURE DEFINITIONS**:
```python
MEAL_STRUCTURES = {
    "3_meals_2_snacks": {
        "description": "3 main meals + 2 snacks",
        "meals": ["Petit-déjeuner (07:30)", "Collation AM (10:00)", "Déjeuner (12:30)",
                  "Collation PM (16:00)", "Dîner (19:30)"]
    },
    "4_meals": {
        "description": "4 equal meals",
        "meals": ["Repas 1 (08:00)", "Repas 2 (12:00)", "Repas 3 (16:00)", "Repas 4 (20:00)"]
    },
    "3_consequent_meals": {
        "description": "3 consecutive main meals (no snacks)",
        "meals": ["Petit-déjeuner (08:00)", "Déjeuner (13:00)", "Dîner (19:00)"]
    },
    "3_meals_1_preworkout": {
        "description": "3 meals + 1 snack before training",
        "meals": ["Petit-déjeuner (07:30)", "Déjeuner (12:30)",
                  "Collation pré-entraînement (16:30)", "Dîner (20:00)"]
    }
}
```

**FUNCTION 2**: `calculate_daily_totals(meals: list[dict]) -> dict`
- Sum calories, protein_g, carbs_g, fat_g from all meals in day
- Return `{"calories": int, "protein_g": int, "carbs_g": int, "fat_g": int}`

**FUNCTION 3**: `format_meal_plan_response(meal_plan: dict, store_success: bool) -> str`
- Format meal plan for user-friendly JSON return
- Include success message, summary stats
- Return formatted JSON string

**VALIDATE**: Create test file `tests/test_meal_planning.py` and run:
```bash
pytest tests/test_meal_planning.py -v
```

---

### UPDATE `tools.py` - Add meal plan generator tool

**IMPLEMENT**: Main tool function `generate_weekly_meal_plan_tool()`

**PATTERN**: Mirror tool pattern from `tools.py:31-129` (async, try/except, JSON return)

**IMPORTS** (add to top of file):
```python
from nutrition.meal_planning import (
    build_meal_plan_prompt,
    calculate_daily_totals,
    format_meal_plan_response,
    MEAL_STRUCTURES
)
from nutrition.validators import (
    validate_allergens,
    validate_daily_macros,
    validate_meal_plan_structure
)
from datetime import datetime
```

**FUNCTION**: Add at end of `tools.py` (after `image_analysis_tool`)

```python
async def generate_weekly_meal_plan_tool(
    supabase: Client,
    openai_client: AsyncOpenAI,
    start_date: str,
    target_calories_daily: int = None,
    target_protein_g: int = None,
    target_carbs_g: int = None,
    target_fat_g: int = None,
    meal_structure: str = "3_meals_2_snacks",
    notes: str = None
) -> str:
    """
    Generate personalized 7-day meal plan with complete recipes.

    Uses GPT-4o to generate recipes matching user profile, validates allergen safety,
    and stores in meal_plans table.

    Args:
        supabase: Supabase client for database operations
        openai_client: OpenAI client for GPT-4o generation
        start_date: Start date in YYYY-MM-DD format (Monday preferred)
        target_calories_daily: Daily calorie target (if None, fetch from profile)
        target_protein_g: Daily protein target in grams
        target_carbs_g: Daily carbs target in grams
        target_fat_g: Daily fat target in grams
        meal_structure: One of "3_meals_2_snacks", "4_meals", "3_consequent_meals", "3_meals_1_preworkout"
        notes: Additional user preferences or constraints

    Returns:
        JSON string with meal plan or error

    Example:
        >>> plan = await generate_weekly_meal_plan_tool(
        ...     supabase, openai_client, "2024-12-23",
        ...     meal_structure="3_meals_1_preworkout"
        ... )
    """
    try:
        logger.info(f"Generating weekly meal plan starting {start_date}, structure: {meal_structure}")

        # Step 1: Validate meal structure
        if meal_structure not in MEAL_STRUCTURES:
            return json.dumps({
                "error": f"Invalid meal structure. Must be one of: {list(MEAL_STRUCTURES.keys())}",
                "code": "VALIDATION_ERROR"
            })

        # Step 2: Validate date format
        try:
            datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            return json.dumps({
                "error": "Invalid date format. Use YYYY-MM-DD (e.g., 2024-12-23)",
                "code": "VALIDATION_ERROR"
            })

        # Step 3: Fetch user profile
        profile_result = await fetch_my_profile_tool(supabase)
        profile_data = json.loads(profile_result)

        if "error" in profile_data:
            return json.dumps({
                "error": "Cannot generate meal plan: user profile incomplete or not found",
                "code": "PROFILE_ERROR",
                "details": profile_data
            })

        # Step 4: Use provided targets or fetch from profile
        calories = target_calories_daily or profile_data.get("target_calories")
        protein = target_protein_g or profile_data.get("target_protein_g")
        carbs = target_carbs_g or profile_data.get("target_carbs_g")
        fat = target_fat_g or profile_data.get("target_fat_g")

        if not all([calories, protein, carbs, fat]):
            return json.dumps({
                "error": "Missing nutritional targets. Provide targets or complete profile.",
                "code": "MISSING_TARGETS"
            })

        # Step 5: Query RAG for meal planning scientific context
        rag_query = "meal planning nutrient timing meal frequency protein distribution"
        rag_result = await retrieve_relevant_documents_tool(supabase, openai_client, rag_query)

        # Step 6: Build LLM prompt
        prompt = build_meal_plan_prompt(
            profile=profile_data,
            rag_context=rag_result,
            start_date=start_date,
            meal_structure=meal_structure,
            notes=notes
        )

        logger.info("Calling GPT-4o for meal plan generation...")

        # Step 7: Generate meal plan with GPT-4o JSON mode
        response = await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.7,  # Balance creativity with consistency
            max_tokens=4000  # Sufficient for 7-day plan
        )

        meal_plan_json = json.loads(response.choices[0].message.content)

        logger.info("Meal plan generated, validating structure...")

        # Step 8: Validate meal plan structure
        structure_validation = validate_meal_plan_structure(meal_plan_json)
        if not structure_validation["valid"]:
            logger.error(f"Invalid meal plan structure: {structure_validation['missing_fields']}")
            return json.dumps({
                "error": "Generated meal plan has invalid structure",
                "code": "STRUCTURE_ERROR",
                "details": structure_validation
            })

        # Step 9: CRITICAL - Validate allergen safety
        user_allergens = profile_data.get("allergies", [])
        allergen_violations = validate_allergens(meal_plan_json, user_allergens)

        if allergen_violations:
            logger.error(f"🚨 ALLERGEN VIOLATIONS DETECTED: {allergen_violations}")
            return json.dumps({
                "error": "Meal plan contains allergens from user profile",
                "code": "ALLERGEN_VIOLATION",
                "violations": allergen_violations,
                "allergens": user_allergens
            })

        logger.info("✅ Allergen validation passed (zero violations)")

        # Step 10: Validate daily macro totals
        for day in meal_plan_json["days"]:
            if "daily_totals" in day:
                targets = {"calories": calories, "protein_g": protein, "carbs_g": carbs, "fat_g": fat}
                macro_validation = validate_daily_macros(day["daily_totals"], targets)

                if not macro_validation["valid"]:
                    logger.warning(f"Day {day['day']} macros outside tolerance: {macro_validation['violations']}")

        # Step 11: Store meal plan in database
        meal_plan_record = {
            "week_start": start_date,
            "plan_data": meal_plan_json,
            "target_calories_daily": calories,
            "target_protein_g": protein,
            "target_carbs_g": carbs,
            "target_fat_g": fat,
            "notes": notes,
            "created_at": "now()"
        }

        db_response = supabase.table("meal_plans").insert(meal_plan_record).execute()

        if db_response.data:
            logger.info(f"✅ Meal plan stored in database (ID: {db_response.data[0].get('id', 'N/A')})")
            store_success = True
        else:
            logger.warning("Meal plan generated but storage failed")
            store_success = False

        # Step 12: Format and return result
        return format_meal_plan_response(meal_plan_json, store_success)

    except json.JSONDecodeError as e:
        logger.error(f"LLM returned invalid JSON: {e}")
        return json.dumps({
            "error": "Failed to parse meal plan from LLM (invalid JSON)",
            "code": "JSON_PARSE_ERROR"
        })
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return json.dumps({"error": str(e), "code": "VALIDATION_ERROR"})
    except Exception as e:
        logger.error(f"Unexpected error generating meal plan: {e}", exc_info=True)
        return json.dumps({
            "error": "Internal error generating meal plan",
            "code": "GENERATION_ERROR"
        })
```

**GOTCHA**: GPT-4o JSON mode requires `response_format={"type": "json_object"}` - DO NOT use `response_format={"type": "json_schema"}` (different feature)

**GOTCHA**: Must parse LLM response with `json.loads()` before validation

**GOTCHA**: Allergen validation must happen BEFORE database storage (reject bad plans)

**VALIDATE**: Add unit test in `tests/test_tools.py`:
```bash
pytest tests/test_tools.py::test_generate_weekly_meal_plan_tool -v
```

---

### UPDATE `agent.py` - Register meal plan tool

**ADD**: Tool registration after existing tools (after `image_analysis` tool, before `create_agent_deps`)

**PATTERN**: Mirror registration from `agent.py:167-183`

**LOCATION**: Insert around line 337 (before `create_agent_deps` function)

```python
@agent.tool
async def generate_weekly_meal_plan(
    ctx: RunContext[AgentDeps],
    start_date: str,
    target_calories_daily: int = None,
    target_protein_g: int = None,
    target_carbs_g: int = None,
    target_fat_g: int = None,
    meal_structure: str = "3_meals_2_snacks",
    notes: str = None
) -> str:
    """
    Generate personalized 7-day meal plan with complete recipes.

    Creates a weekly meal plan based on user profile, nutritional targets, allergies,
    and preferences. Includes complete recipes with ingredients, quantities, instructions,
    and nutritional information for each meal.

    Args:
        ctx: Run context with Supabase and OpenAI clients
        start_date: Start date in YYYY-MM-DD format (Monday preferred), e.g. "2024-12-23"
        target_calories_daily: Daily calorie target (if None, uses profile target)
        target_protein_g: Daily protein target in grams
        target_carbs_g: Daily carbs target in grams
        target_fat_g: Daily fat target in grams
        meal_structure: Meal distribution pattern:
            - "3_meals_2_snacks": Breakfast, AM snack, Lunch, PM snack, Dinner (default)
            - "4_meals": 4 equal meals throughout day
            - "3_consequent_meals": 3 consecutive main meals (no snacks)
            - "3_meals_1_preworkout": 3 meals + 1 snack before training
        notes: Additional preferences (e.g., "pas de viande rouge cette semaine")

    Returns:
        JSON string with complete meal plan including all recipes, ingredients,
        nutritional information, and weekly summary

    Example:
        User: "Crée-moi un plan pour cette semaine avec 3 repas + collation pré-training"
        Agent: generate_weekly_meal_plan(
            start_date="2024-12-23",
            meal_structure="3_meals_1_preworkout"
        )
    """
    logger.info("Tool called: generate_weekly_meal_plan")
    return await generate_weekly_meal_plan_tool(
        ctx.deps.supabase,
        ctx.deps.embedding_client,  # Reuse for OpenAI client
        start_date,
        target_calories_daily,
        target_protein_g,
        target_carbs_g,
        target_fat_g,
        meal_structure,
        notes
    )
```

**IMPORTS**: Add to top of `agent.py` (around line 29):
```python
from tools import (
    calculate_nutritional_needs_tool,
    fetch_my_profile_tool,
    update_my_profile_tool,
    retrieve_relevant_documents_tool,
    web_search_tool,
    image_analysis_tool,
    generate_weekly_meal_plan_tool  # ADD THIS LINE
)
```

**VALIDATE**: Run agent test:
```bash
python agent.py
```
Check that agent initializes without errors and tool is registered.

---

### UPDATE `prompt.py` - Document meal planning capability

**ADD**: Meal planning section to system prompt

**LOCATION**: After "## Tes Capacités" section (around line 44, after body composition analysis)

**PATTERN**: Mirror existing capability descriptions

```python
### 6. Planification de Repas Hebdomadaire
- Génération de plans de 7 jours avec recettes complètes
- Respect automatique des allergies et aliments détestés
- Équilibrage des macros quotidiens (±10% de tolérance)
- 4 structures de repas disponibles :
  * "3_meals_2_snacks" : Petit-déj, collation AM, déjeuner, collation PM, dîner
  * "4_meals" : 4 repas égaux dans la journée
  * "3_consequent_meals" : 3 repas consécutifs principaux (sans collations)
  * "3_meals_1_preworkout" : 3 repas + 1 collation avant entraînement
- Stockage automatique dans la base de données pour référence future
```

**ADD**: Workflow section for meal planning (after "### Analyse d'Image (Body Fat)" around line 135)

```python
### Planification de Repas Hebdomadaire
**🚨 WORKFLOW DE SÉCURITÉ ALLERGIES - CRITIQUE** :
1. **AVANT génération** : Le tool vérifie AUTOMATIQUEMENT les allergies du profil
2. **Pendant génération** : Le LLM reçoit les allergies en MAJUSCULES dans le prompt
3. **Après génération** : Validation avec tolérance zéro (plan rejeté si allergen détecté)
4. **Stockage** : Plan sauvegardé uniquement si validation passée

**Utilisation** :
1. Vérifie que l'utilisateur a un profil complet (si incomplet : demande les données manquantes)
2. Appelle `generate_weekly_meal_plan` avec :
   - `start_date` : Date de début (YYYY-MM-DD, lundi de préférence)
   - `meal_structure` : Structure souhaitée (demande à l'utilisateur ou utilise "3_meals_2_snacks" par défaut)
   - `notes` : Préférences additionnelles fournies par l'utilisateur
3. Présente le plan avec :
   - Résumé de la semaine (nombre de recettes uniques, temps de préparation moyen)
   - Mise en avant de la sécurité allergènes ("✅ Aucun allergène détecté")
   - Structure du plan (aperçu des repas)
   - Proposition de générer la liste de courses (via `generate_shopping_list`)

**Exemple de Réponse** :
```
✅ **Plan de 7 jours créé** (23-29 décembre)

📊 **Résumé**
- 21 recettes uniques
- Temps de préparation moyen : 35 min
- Structure : 3 repas + 1 collation pré-entraînement

🛡️ **Sécurité Allergènes**
✅ Aucun allergène détecté (vérifié : arachides)

📅 **Aperçu Semaine**
**Lundi** : Omelette aux légumes | Poulet grillé + riz | Collation : banane + amandes | Saumon + quinoa
**Mardi** : ...

💡 **Next Steps**
Veux-tu que je génère la liste de courses pour cette semaine ?
```
```

**VALIDATE**: Read the file to ensure syntax is correct:
```bash
python -c "from prompt import AGENT_SYSTEM_PROMPT; print('✅ Prompt loaded successfully')"
```

---

### CREATE `tests/test_validators.py`

**IMPLEMENT**: Comprehensive test suite for allergen validation

**PATTERN**: Mirror pytest pattern from existing test files in project

**IMPORTS**:
```python
import pytest
from nutrition.validators import validate_allergens, validate_daily_macros, validate_meal_plan_structure
```

**TEST 1**: Test zero violations (clean meal plan)
```python
def test_validate_allergens_no_violations():
    meal_plan = {
        "days": [
            {
                "meals": [
                    {
                        "recipe_name": "Poulet grillé",
                        "ingredients": [
                            {"name": "poulet", "quantity": 200, "unit": "g"},
                            {"name": "riz", "quantity": 100, "unit": "g"}
                        ]
                    }
                ]
            }
        ]
    }
    user_allergens = ["arachides", "lactose"]
    violations = validate_allergens(meal_plan, user_allergens)
    assert violations == []
```

**TEST 2**: Test direct allergen match
```python
def test_validate_allergens_direct_match():
    meal_plan = {
        "days": [
            {
                "meals": [
                    {
                        "recipe_name": "Salade",
                        "ingredients": [
                            {"name": "beurre de cacahuète", "quantity": 30, "unit": "g"}
                        ]
                    }
                ]
            }
        ]
    }
    user_allergens = ["arachides"]
    violations = validate_allergens(meal_plan, user_allergens)
    assert len(violations) > 0
    assert "cacahuète" in violations[0].lower()
```

**TEST 3**: Test family matching
**TEST 4**: Test false positives (noix de coco should NOT trigger fruits à coque)
**TEST 5**: Test case insensitivity
**TEST 6**: Test macro validation within tolerance
**TEST 7**: Test macro validation outside tolerance
**TEST 8**: Test meal plan structure validation

**VALIDATE**:
```bash
pytest tests/test_validators.py -v --cov=nutrition.validators
```

---

### CREATE `tests/test_meal_planning.py`

**IMPLEMENT**: Tests for meal planning helper functions

**TEST 1**: Test build_meal_plan_prompt contains all required elements
**TEST 2**: Test calculate_daily_totals sums correctly
**TEST 3**: Test format_meal_plan_response returns valid JSON
**TEST 4**: Test meal structure definitions are complete

**VALIDATE**:
```bash
pytest tests/test_meal_planning.py -v --cov=nutrition.meal_planning
```

---

### REFACTOR `nutrition/meal_planning.py` - Implement build_meal_plan_prompt

**IMPLEMENT**: Complete prompt builder with all meal structure details

**CRITICAL PROMPT ELEMENTS**:
1. User profile context (allergies in UPPERCASE, preferences, constraints)
2. Nutritional targets (calories, macros with ±10% tolerance)
3. Meal structure definition with times
4. RAG scientific context
5. JSON schema requirements (exact structure)
6. Allergen warnings (REPEATED multiple times for emphasis)
7. Example meals for each structure type

**PROMPT TEMPLATE** (key sections):
```python
def build_meal_plan_prompt(...) -> str:
    allergies_str = ", ".join(profile.get("allergies", [])) or "AUCUNE"
    disliked_str = ", ".join(profile.get("disliked_foods", [])) or "Aucun"

    structure_info = MEAL_STRUCTURES[meal_structure]
    meals_list = "\n".join([f"  - {meal}" for meal in structure_info["meals"]])

    prompt = f"""Tu es un nutritionniste expert créant un plan de repas pour 7 jours.

🚨🚨🚨 CONTRAINTE CRITIQUE - ALLERGIES 🚨🚨🚨
ALLERGIES DE L'UTILISATEUR : {allergies_str}
CES ALLERGIES DOIVENT ÊTRE ABSOLUMENT ÉVITÉES - TOLÉRANCE ZÉRO
NE JAMAIS inclure : {allergies_str} ni AUCUN aliment de leur famille
Vérifie CHAQUE ingrédient avant de l'inclure dans une recette

PROFIL UTILISATEUR :
- Calories/jour : {calories} kcal (tolérance ±10%)
- Protéines : {protein}g | Glucides : {carbs}g | Lipides : {fat}g
- 🚨 ALLERGIES : {allergies_str} (TOLÉRANCE ZÉRO)
- Aliments détestés : {disliked_str}
- Aliments favoris : {profile.get("favorite_foods", [])}
- Temps de préparation max : {profile.get("max_prep_time", 60)} min
- Cuisines préférées : {profile.get("preferred_cuisines", [])}
- Régime : {profile.get("diet_type", "omnivore")}

STRUCTURE DE REPAS : {meal_structure}
{structure_info["description"]}
Repas quotidiens :
{meals_list}

CONTEXTE SCIENTIFIQUE :
{rag_context[:1000]}

NOTES SUPPLÉMENTAIRES :
{notes or "Aucune"}

GÉNÈRE un plan JSON avec cette structure EXACTE :
{{
  "meal_plan_id": "plan_{start_date}",
  "start_date": "{start_date}",
  "meal_structure": "{meal_structure}",
  "daily_targets": {{
    "calories": {calories},
    "protein_g": {protein},
    "carbs_g": {carbs},
    "fat_g": {fat}
  }},
  "days": [
    {{
      "day": "Lundi {start_date}",
      "date": "{start_date}",
      "meals": [
        {{
          "meal_type": "Petit-déjeuner",
          "time": "07:30",
          "recipe_name": "Nom de la recette",
          "servings": 1,
          "prep_time_min": 15,
          "ingredients": [
            {{"name": "nom_ingredient", "quantity": 100, "unit": "g"}},
            ...
          ],
          "instructions": [
            "Étape 1...",
            "Étape 2..."
          ],
          "nutrition": {{
            "calories": 420,
            "protein_g": 28,
            "carbs_g": 35,
            "fat_g": 18
          }},
          "tags": ["protéiné", "rapide"]
        }},
        ...
      ],
      "daily_totals": {{
        "calories": {calories},
        "protein_g": {protein},
        "carbs_g": {carbs},
        "fat_g": {fat}
      }}
    }},
    ... (6 autres jours)
  ],
  "weekly_summary": {{
    "total_unique_recipes": 21,
    "avg_prep_time_min": 35,
    "allergen_check": "PASSED - Aucun allergène détecté : {allergies_str}",
    "adherence_tips": ["Conseil 1", "Conseil 2"]
  }}
}}

🚨 RAPPEL FINAL : NE JAMAIS inclure {allergies_str} ou aliments de leur famille
Vérifie TOUS les ingrédients avant de répondre !
"""

    return prompt
```

**GOTCHA**: Allergen warnings must appear MULTIPLE times (top, middle, end) - LLMs sometimes ignore single mentions

**VALIDATE**: Test prompt generation:
```bash
python -c "from nutrition.meal_planning import build_meal_plan_prompt; print(build_meal_plan_prompt({'allergies': ['arachides'], 'target_calories': 3000}, 'RAG context', '2024-12-23', '3_meals_2_snacks')[:500])"
```

---

## TESTING STRATEGY

### Unit Tests (pytest + pytest-asyncio)

**Scope**: Test individual functions in isolation with mocked dependencies

**Framework**: `pytest==8.3.5` + `pytest-asyncio==0.26.0` (already in requirements.txt)

**Test Files**:
- `tests/test_validators.py` - All validator functions (8+ tests)
- `tests/test_meal_planning.py` - All helper functions (4+ tests)
- `tests/test_tools.py` - Add `test_generate_weekly_meal_plan_tool` (mock Supabase, OpenAI)

**Fixtures** (create in `tests/conftest.py`):
```python
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_supabase():
    """Mock Supabase client."""
    mock = MagicMock()
    mock.table.return_value.select.return_value.limit.return_value.execute.return_value.data = [
        {
            "id": "user-123",
            "name": "Test User",
            "allergies": ["arachides"],
            "target_calories": 3000,
            "target_protein_g": 180,
            "target_carbs_g": 350,
            "target_fat_g": 85
        }
    ]
    return mock

@pytest.fixture
def mock_openai():
    """Mock OpenAI client for GPT-4o."""
    mock = AsyncMock()
    mock.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content='{"meal_plan_id": "plan_2024-12-23", "days": [...]}'))
    ]
    return mock

@pytest.fixture
def sample_meal_plan():
    """Sample meal plan for testing validators."""
    return {
        "meal_plan_id": "plan_2024-12-23",
        "start_date": "2024-12-23",
        "days": [
            {
                "day": "Lundi 2024-12-23",
                "meals": [
                    {
                        "recipe_name": "Omelette",
                        "ingredients": [
                            {"name": "oeufs", "quantity": 3, "unit": "pièces"},
                            {"name": "tomate", "quantity": 100, "unit": "g"}
                        ],
                        "nutrition": {"calories": 300, "protein_g": 20, "carbs_g": 10, "fat_g": 15}
                    }
                ],
                "daily_totals": {"calories": 3000, "protein_g": 180, "carbs_g": 350, "fat_g": 85}
            }
        ]
    }
```

**Coverage Target**: 80%+ for `nutrition/` modules

---

### Integration Tests

**Scope**: Test end-to-end workflow with real (or realistic mock) dependencies

**Test Scenarios**:
1. **Happy Path**: Generate meal plan with valid profile → Store in DB → Retrieve and verify
2. **Allergen Rejection**: Meal plan with allergen → Validate → Rejection with error code
3. **Incomplete Profile**: Missing allergies field → Fetch profile → Handles gracefully
4. **Invalid Date**: Bad date format → Validation error before LLM call

**Pattern**:
```python
@pytest.mark.asyncio
async def test_generate_meal_plan_integration(mock_supabase, mock_openai):
    """Test full meal plan generation workflow."""
    result = await generate_weekly_meal_plan_tool(
        mock_supabase,
        mock_openai,
        start_date="2024-12-23",
        meal_structure="3_meals_2_snacks"
    )

    result_json = json.loads(result)
    assert "meal_plan" in result_json
    assert result_json["meal_plan"]["start_date"] == "2024-12-23"
    assert len(result_json["meal_plan"]["days"]) == 7
```

---

### Edge Cases Tests

**Critical Edge Cases to Test**:

1. **Allergen Family Matching**:
   - User allergic to "arachides", meal contains "beurre de cacahuète" → REJECT
   - User allergic to "fruits à coque", meal contains "amandes" → REJECT
   - User allergic to "fruits à coque", meal contains "noix de coco" → ALLOW (false positive)

2. **Macro Tolerance**:
   - Daily total: 2950 kcal (target 3000) → PASS (within ±10%)
   - Daily total: 2600 kcal (target 3000) → WARN (outside tolerance)

3. **Meal Structure Validation**:
   - Missing "daily_totals" field → Structure validation FAIL
   - Missing "ingredients" in meal → Structure validation FAIL

4. **Empty or Null Fields**:
   - User has no allergies (`allergies: []`) → No validation errors
   - User has no disliked foods → Generate plan normally

5. **LLM JSON Parse Failures**:
   - LLM returns malformed JSON → Catch `JSONDecodeError` → Return error code

**Test Implementation**:
```python
@pytest.mark.parametrize("allergen,ingredient,should_reject", [
    ("arachides", "beurre de cacahuète", True),
    ("fruits à coque", "amandes", True),
    ("fruits à coque", "noix de coco", False),  # False positive
    ("lactose", "lait d'amande", False),  # Plant-based alternative
])
def test_allergen_edge_cases(allergen, ingredient, should_reject):
    meal_plan = {
        "days": [{
            "meals": [{
                "recipe_name": "Test",
                "ingredients": [{"name": ingredient, "quantity": 100, "unit": "g"}]
            }]
        }]
    }
    violations = validate_allergens(meal_plan, [allergen])
    if should_reject:
        assert len(violations) > 0
    else:
        assert len(violations) == 0
```

---

## VALIDATION COMMANDS

Execute every command to ensure zero regressions and 100% feature correctness.

### Level 1: Syntax & Style

**Linting and Formatting** (project uses `ruff`):
```bash
cd 4_Pydantic_AI_Agent
ruff format .
ruff check .
mypy nutrition/validators.py nutrition/meal_planning.py tools.py
```

**Expected Output**: Zero errors, zero warnings

**If Errors**: Fix all type hints, import errors, and style violations before proceeding

---

### Level 2: Unit Tests

**Run All Tests**:
```bash
cd 4_Pydantic_AI_Agent
pytest tests/test_validators.py -v
pytest tests/test_meal_planning.py -v
pytest tests/test_tools.py::test_generate_weekly_meal_plan_tool -v
```

**Coverage Check**:
```bash
pytest --cov=nutrition.validators --cov=nutrition.meal_planning --cov-report=term-missing
```

**Expected Output**: All tests passing, coverage >80%

**If Failures**: Debug failing tests, fix implementation, rerun until all pass

---

### Level 3: Integration Tests

**Manual Agent Test** (verify tool is registered and callable):
```bash
cd 4_Pydantic_AI_Agent
python -c "
import asyncio
from agent import agent, create_agent_deps

async def test():
    deps = create_agent_deps()
    result = await agent.run(
        'Génère un plan de repas pour cette semaine en commençant lundi 23 décembre',
        deps=deps
    )
    print(result.data)

asyncio.run(test())
"
```

**Expected Output**: Agent calls `generate_weekly_meal_plan` tool, returns structured meal plan (or profile error if profile incomplete)

**If Errors**: Check tool registration, dependency injection, and error messages

---

### Level 4: Manual Validation

**Test 1: Profile Loading**
```bash
cd 4_Pydantic_AI_Agent
streamlit run streamlit_ui.py
```
In UI:
1. Send: "Charge mon profil"
2. **VERIFY**: Profile loads or returns PROFILE_INCOMPLETE error
3. If incomplete, send profile data: "23 ans, homme, 86kg, 191cm, sédentaire, allergique aux arachides"

**Test 2: Meal Plan Generation**
1. Send: "Crée un plan de repas pour cette semaine avec 3 repas + collation pré-training"
2. **VERIFY**: Tool is called (check logs)
3. **VERIFY**: Meal plan JSON is returned with 7 days
4. **VERIFY**: Allergen check message appears ("✅ Aucun allergène détecté")

**Test 3: Allergen Safety**
1. Set user allergies: "Je suis allergique aux arachides et au lactose"
2. Generate plan: "Crée un plan pour cette semaine"
3. **VERIFY**: No recipes contain peanuts, peanut butter, dairy, milk, cheese
4. If violations: **CRITICAL BUG** - Fix immediately

**Test 4: Meal Structures**
Test each structure:
- "Plan avec 3 repas + 2 collations"
- "Plan avec 4 repas égaux"
- "Plan avec 3 repas consécutifs sans collation"
- "Plan avec 3 repas + collation pré-entraînement"

**VERIFY**: Meal counts match structure definition

---

### Level 5: Additional Validation (Optional)

**Database Inspection** (verify storage):
```bash
# Open Supabase dashboard
# Navigate to Table Editor → meal_plans
# Verify: Latest record has correct start_date, plan_data JSONB is populated
```

**Log Analysis**:
```bash
cd 4_Pydantic_AI_Agent
# Run agent with debug logging
python -c "
import logging
logging.basicConfig(level=logging.DEBUG)
# ... run agent test ...
"
# Check for:
# - "Generating weekly meal plan starting..."
# - "Calling GPT-4o for meal plan generation..."
# - "✅ Allergen validation passed"
# - "✅ Meal plan stored in database"
```

---

## ACCEPTANCE CRITERIA

**ALL criteria must be met for feature completion:**

- [x] `nutrition/validators.py` created with 3 validation functions
- [x] `nutrition/meal_planning.py` created with 4 helper functions
- [x] `generate_weekly_meal_plan_tool()` implemented in `tools.py`
- [x] Tool registered in `agent.py` with `@agent.tool` decorator
- [x] System prompt updated in `prompt.py` with meal planning section
- [x] All meal structures implemented: `3_meals_2_snacks`, `4_meals`, `3_consequent_meals`, `3_meals_1_preworkout`
- [x] Allergen validation enforces zero tolerance (rejects plans with violations)
- [x] Allergen family matching works (arachides → beurre de cacahuète)
- [x] False positive handling works (noix de coco NOT rejected for fruits à coque allergy)
- [x] Daily macros validated within ±10% tolerance
- [x] Meal plan structure validated (all required fields present)
- [x] Meal plan stored in `meal_plans` table with JSONB plan_data
- [x] RAG query for scientific context included in prompt
- [x] GPT-4o JSON mode returns valid JSON 100% of time (structured outputs)
- [x] Unit test coverage >80% for `nutrition/validators.py` and `nutrition/meal_planning.py`
- [x] All validation commands pass with zero errors
- [x] Manual testing confirms 4 meal structures work correctly
- [x] No regressions in existing tools (all previous tools still functional)
- [x] Comprehensive error handling (profile errors, validation errors, JSON parse errors)
- [x] Logging at all critical steps (generation start, validation, storage)

---

## COMPLETION CHECKLIST

**Before marking feature complete, verify:**

- [ ] All tasks completed in order (top to bottom)
- [ ] Each task validated immediately after implementation
- [ ] `ruff format && ruff check && mypy` passes with zero errors
- [ ] All unit tests pass (`pytest tests/test_validators.py tests/test_meal_planning.py`)
- [ ] Integration test passes (agent can generate meal plan)
- [ ] Manual testing in Streamlit UI successful for all 4 meal structures
- [ ] Allergen validation tested with edge cases (family matching, false positives)
- [ ] Macro tolerance validation tested (±10% boundary conditions)
- [ ] Meal plan stored in database (verified in Supabase dashboard)
- [ ] System prompt updated and syntax correct (no Python errors on import)
- [ ] Logs show structured logging at all critical steps
- [ ] No security vulnerabilities (allergen bypass, SQL injection via user input)
- [ ] Code reviewed for quality (follows CLAUDE.md conventions)
- [ ] Documentation complete (docstrings on all functions)

---

## NOTES

### Design Decisions

**1. Why LLM-Generated Recipes Instead of Database Queries?**
- **RATIONALE**: Recipe database is currently empty (0 rows)
- **ALTERNATIVE CONSIDERED**: Manually populate recipes first → REJECTED (time-consuming, blocks MVP)
- **TRADE-OFF**: LLM recipes may have less precise macros vs validated recipes, BUT provides immediate value
- **MITIGATION**: Daily macro validation with ±10% tolerance catches significant errors

**2. Why GPT-4o Instead of GPT-4o-mini?**
- **RATIONALE**: Structured outputs (JSON mode) require consistent schema adherence
- **EVIDENCE**: GPT-4o trained specifically for complex schemas (OpenAI docs), 100% reliability claim
- **COST**: ~$0.015 per meal plan (4000 tokens) vs $0.003 for mini → ACCEPTABLE for weekly frequency
- **ALTERNATIVE**: Could use mini with JSON repair library → REJECTED (adds complexity, not guaranteed)

**3. Why Zero Tolerance Allergen Policy?**
- **RATIONALE**: Medical safety - even trace amounts can cause severe reactions
- **PATTERN**: Follow system prompt requirement (prompt.py:49-56)
- **IMPLEMENTATION**: Triple validation (LLM prompt warning + post-generation validation + family matching)
- **TRADE-OFF**: May reject some safe plans due to false positives → ACCEPTABLE (safety > convenience)

**4. Why Store Meal Plan as JSONB Instead of Normalized Tables?**
- **RATIONALE**: Flexible structure (meal counts vary by structure), easier versioning
- **PRD ALIGNMENT**: Database schema already defines `meal_plans.plan_data JSONB` (PRD.md:781-791)
- **TRADE-OFF**: Harder to query individual recipes → ACCEPTABLE (query use case is "load full plan")

### Known Limitations

**1. LLM Hallucination Risk**
- **ISSUE**: GPT-4o may generate recipes with incorrect nutritional calculations
- **MITIGATION**: Macro validation catches outliers (±10% tolerance), RAG provides scientific grounding
- **FUTURE**: Validate recipes against USDA nutritional database (Phase 2)

**2. Language Mixing (French Queries, English Knowledge Base)**
- **ISSUE**: RAG documents in English, user queries in French → lower similarity scores
- **STATUS**: Already addressed in existing RAG tool (threshold lowered to 0.5, PROJECT_STATUS.md:117)
- **IMPACT**: Meal planning prompt includes RAG context, may be less relevant for French-specific queries

**3. No Unit Conversion in Shopping List**
- **ISSUE**: Ingredients in different units (200g rice + 1 cup rice) → can't aggregate
- **DEFERRED**: Shopping list tool (separate feature) will handle this
- **WORKAROUND**: LLM generates recipes with consistent units (grams preferred)

### Future Enhancements (Out of Scope)

- Recipe database population (manual curation or API import)
- Recipe selection algorithm (constraint optimization for macro balancing)
- User recipe rating and feedback system
- Meal plan versioning (track changes, revert to previous plans)
- Integration with shopping list generator (automatic aggregation)
- Nutrition label verification (scan barcode, compare to LLM-generated macros)
- Multi-week meal planning (4-week rotation, avoid recipe repetition)

---

**Plan Version**: 1.0
**Created**: 2025-12-23
**Estimated Implementation Time**: 6-8 hours
**Confidence Score**: 8/10 for one-pass success

**Risk Factors**:
- GPT-4o JSON reliability (10% risk of schema drift)
- Allergen family matching completeness (may miss edge cases)
- Integration with existing agent (5% risk of dependency conflicts)

**Success Factors**:
- Comprehensive validation at every step
- Existing tool patterns to follow
- Clear error handling and logging
- Extensive test coverage requirements
