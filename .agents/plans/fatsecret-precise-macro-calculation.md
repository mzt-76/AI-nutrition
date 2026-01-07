# Feature: FatSecret API Integration for Precise Macro Calculation

## Feature Description

Replace GPT-4o's approximative macro calculations with precise Python-based calculations using the FatSecret Platform API. Implements a dual-phase architecture where GPT-4o generates creative meal plans (recipes, ingredients, instructions) and Python calculates exact nutritional macros via FatSecret's 500,000+ food database.

**Current Problem:** GPT-4o generates meal plans 400 kcal below target (-14% deficit) on 6/7 days despite strict prompts.

**Proposed Solution:** Separate creativity (GPT-4o) from precision (Python + FatSecret API), using portion adjustments before resorting to complements.

## User Story

As a **nutrition coach using the AI Nutrition Assistant**
I want **meal plans with guaranteed macro accuracy (±5%)**
So that **my clients hit their protein/calorie targets for muscle gain goals without artificial supplement recommendations**

## Problem Statement

Current system relies on GPT-4o to both create recipes AND calculate macros. LLMs cannot perform precise mathematical calculations, leading to:

1. **Systematic calorie deficit:** 6/7 days miss targets by -11% to -14% (-274 to -415 kcal/day)
2. **Protein shortfalls:** Consistent -20 to -36g protein/day below target
3. **Artificial solutions:** Post-processing adds 3+ complement foods per day
4. **Poor UX:** Plans feel "robotic" with too many supplements
5. **Wasted GPT-4o calls:** Regenerating plans hoping for better accuracy


## Solution Statement

Implement **Dual-Phase Optimization Architecture**:

**Phase 1: Creative Generation (GPT-4o)**
- Generate 7-day meal plans with recipes, ingredients (with quantities), and instructions
- NO macro calculation by LLM
- Focus on variety, taste, user preferences, allergen safety

**Phase 2: Precise Calculation (Python + FatSecret API)**
- Match each ingredient to FatSecret's food database using fuzzy matching
- Calculate exact macros per ingredient → per meal → per day
- Cache ingredient mappings in Supabase for performance
- Optimize portions proportionally (±25% max) to hit targets
- Add complements only if portion scaling insufficient

**Phase 3: Validation & Storage**
- Validate allergen safety (zero tolerance)
- Store plan with precise macros in database
- Generate user-friendly adjustment summary

**Result:** 100% macro accuracy with natural meal plans, minimal artificial complements, scalable performance via caching.

## Feature Metadata

**Feature Type**: Enhancement (replaces existing meal planning accuracy system)
**Estimated Complexity**: High (12-17 hours implementation + testing)

**Primary Systems Affected**:
- `tools.py::generate_weekly_meal_plan_tool` (lines 604-889)
- `nutrition/meal_planning.py::build_meal_plan_prompt`
- New: `nutrition/fatsecret_client.py` (OAuth + API integration)
- New: `nutrition/meal_plan_optimizer.py` (portion optimization)
- New: Supabase table `ingredient_mapping` (caching)

**Dependencies**:
- FatSecret Platform API credentials (already in `.env`)
- No new Python packages (uses existing `httpx`, `difflib` stdlib)

---

## CONTEXT REFERENCES

### Relevant Codebase Files - READ BEFORE IMPLEMENTING!

**Core Architecture:**
- `agent.py` (lines 77-102) - AgentDeps pattern for shared resources
- `agent.py` (lines 121-498) - Tool registration with `@agent.tool` decorator
- `clients.py` - Client initialization (Supabase, OpenAI, httpx)

**Tool Implementation Reference:**
- `ai-agent-mastery/4_Pydantic_AI_Agent/tools.py` (lines 316-420) - **REFERENCE:** `execute_safe_code_tool` example
  - Shows how to create secure calculation tools with precise math operations
  - Demonstrates safe execution environment setup
  - Pattern for tools that perform computational tasks (not just data retrieval)
  - Uses RestrictedPython for security (we'll use direct Python calculations instead)

**Existing Meal Planning System:**
- `tools.py` (lines 604-889) - **CRITICAL:** 12-step meal plan generation workflow
- `tools.py` (lines 738-744) - GPT-4o prompt building (MODIFY)
- `tools.py` (lines 822-846) - Post-processing macro adjustment (REPLACE)
- `nutrition/meal_planning.py` (lines 216-237) - Prompt instructions (MODIFY)
- `nutrition/macro_adjustments.py` (lines 298-407) - Existing post-processing (REFERENCE)

**Calculation & Validation:**
- `nutrition/calculations.py` (lines 249-295) - `calculate_macros()` function
- `nutrition/validators.py` - Allergen validation, macro tolerance checking
- `nutrition/macro_adjustments.py` (lines 18-24) - Tolerance constants (±10%)

**Database & Testing Patterns:**
- `sql/create_weekly_feedback_table.sql` - Example Supabase schema
- `tests/test_validators.py` - Parametrized test examples
- `.env` (lines 80-81) - FatSecret credentials

### New Files to Create

- `nutrition/fatsecret_client.py` - FatSecret OAuth + API (search, get, matching)
- `nutrition/meal_plan_optimizer.py` - Macro calculation + portion optimization
- `sql/create_ingredient_mapping_table.sql` - Caching table
- `tests/test_fatsecret_client.py` - Unit tests for OAuth, search, fuzzy matching
- `tests/test_meal_plan_optimizer.py` - Unit tests for calculation, optimization

### Files to Modify

- `tools.py` (lines 822-846) - Replace post-processing with FatSecret integration
- `nutrition/meal_planning.py` (lines 216-237) - Disable GPT-4o macro calculation

### Relevant Documentation

**FatSecret Platform API:**
- [OAuth 2.0 Authentication](https://platform.fatsecret.com/docs/guides/authentication/oauth2) - Client Credentials Grant for 24-hour bearer tokens
- [REST API Methods](https://platform.fatsecret.com/api/Default.aspx?screen=rapiref2) - `foods.search`, `food.get` endpoints
- [Response Formats](https://platform.fatsecret.com/docs/guides/response-formats) - JSON structure for servings (per 100g)

**Python Libraries:**
- [HTTPX Async Client](https://www.python-httpx.org/async/) - Connection pooling, timeouts, HTTP/2
- [difflib.SequenceMatcher](https://docs.python.org/3/library/difflib.html) - String similarity for fuzzy matching (stdlib)

**Supabase:**
- [Python Client](https://supabase.com/docs/reference/python/select) - `.insert()`, `.update()`, `.select()`, `.eq()`

### Key Patterns from Codebase

**1. Async Tool Implementation** (from `tools.py`)
- Google-style docstrings with Args/Returns/Example/References
- Try-except with 3 layers: ValueError → Exception → JSON error response
- Logging with context: `logger.info(f"Tool called: param={param}")`
- Return JSON strings: `json.dumps(result, indent=2)`

**IMPORTANT REFERENCE: Computational Tool Pattern**

See `ai-agent-mastery/4_Pydantic_AI_Agent/tools.py::execute_safe_code_tool` (lines 316-420) for example of:
- **Direct computation tool:** Performs precise calculations instead of approximations
- **Environment setup:** Creates controlled execution context
- **Error handling:** Captures execution errors gracefully
- **Result formatting:** Returns formatted output

**Key Difference for Our Implementation:**
- `execute_safe_code_tool`: Uses RestrictedPython for dynamic code execution (security sandbox)
- `match_ingredient`: Uses direct Python calculations (no dynamic code, just FatSecret API + math)
- Both share: Precise computational approach vs. LLM approximation

**2. AgentDeps Context Access**
- Tools receive `RunContext[AgentDeps]` for shared resources
- Access via `ctx.deps.supabase`, `ctx.deps.http_client`

**3. Supabase Queries**
- Pattern: `.table("name").select("*").eq("field", value).execute()`
- Always check `if response.data:` before accessing
- Insert: `.insert(dict).execute()`
- Update: `.update(dict).eq("id", id).execute()`

**4. Logging Standards**
- Entry: `logger.info("Calculating nutrition for age=35")`
- Progress: `logger.info(f"Retrieved {len(data)} records")`
- Success: `logger.info("✅ Success message")`
- Errors: `logger.error(f"Error: {e}", exc_info=True)`

**5. Testing Patterns**
- `@pytest.mark.asyncio` for async tests
- `@pytest.mark.parametrize` for multiple scenarios
- Mock external dependencies (FatSecret API, Supabase)

**Naming Conventions:**
- Functions: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Files: `snake_case.py`

---

## IMPLEMENTATION PLAN

### PHASE 1: Foundation - FatSecret Client & Caching Infrastructure

**Duration:** 4-6 hours

**Objective:** Build the foundation for FatSecret API integration with OAuth 2.0, caching, and fuzzy matching.

#### 1.1 Database Schema (30 min)

**File:** `sql/create_ingredient_mapping_table.sql`

**Create table with:**
- `id` (UUID, primary key)
- `ingredient_name` (TEXT, unique) - Original name
- `ingredient_name_normalized` (TEXT) - Lowercase, accent-free for matching
- `fatsecret_food_id` (TEXT) - FatSecret database ID
- `fatsecret_food_name` (TEXT) - Official FatSecret name
- Nutritional data per 100g: `calories_per_100g`, `protein_g_per_100g`, `carbs_g_per_100g`, `fat_g_per_100g`
- Quality metrics: `confidence_score` (0.0-1.0), `verified` (boolean), `usage_count` (int)
- Metadata: `created_at`, `updated_at`

**Indexes:**
- `idx_ingredient_name` on `ingredient_name`
- `idx_ingredient_normalized` on `ingredient_name_normalized`
- `idx_verified` on `verified` WHERE verified = TRUE

**Deploy:** Run SQL via Supabase SQL editor or psql

#### 1.2 FatSecret OAuth 2.0 Manager (2-3 hours)

**File:** `nutrition/fatsecret_client.py`

**Implement `FatSecretAuthManager` class:**

**Methods:**
- `__init__(client_id, client_secret)` - Store credentials
- `async get_token(http_client)` - Get cached or request new token
- `async _request_new_token(http_client)` - OAuth 2.0 flow with Basic auth

**OAuth Flow Details:**
- Endpoint: `POST https://oauth.fatsecret.com/connect/token`
- Headers: `Authorization: Basic <base64(client_id:client_secret)>`
- Body: `grant_type=client_credentials&scope=basic`
- Response: `{"access_token": "...", "expires_in": 86400}`

**Token Caching Strategy:**
- Store token + expiry datetime in instance variables
- Check expiry with 60s buffer before reuse
- Use `asyncio.Lock()` for thread-safe refresh
- Token lifetime: 24 hours (86400 seconds)

**Error Handling:**
- 401 Unauthorized → Token expired, refresh
- 403 Forbidden → IP not whitelisted in FatSecret settings
- Timeout → Retry with exponential backoff (3 attempts)

#### 1.3 FatSecret API Endpoints (1-2 hours)

**File:** `nutrition/fatsecret_client.py`

**Implement API functions:**

**`async search_food(query, token, max_results=5)`:**
- Endpoint: `GET https://platform.fatsecret.com/rest/server.api`
- Params: `method=foods.search&search_expression=<query>&format=json`
- Headers: `Authorization: Bearer <token>`
- Response parsing: Handle dict vs list (API returns dict if 1 result, list if 2+)
- Return: List of `{"food_id": "...", "food_name": "...", "food_description": "..."}`

**`async get_food_nutrition(food_id, token)`:**
- Endpoint: `GET https://platform.fatsecret.com/rest/server.api`
- Params: `method=food.get&food_id=<id>&format=json`
- Parse servings array, find 100g serving or convert first serving to 100g equivalent
- Return: `{"food_id": "...", "food_name": "...", "calories_per_100g": X, "protein_g_per_100g": Y, ...}`

**Rate Limiting:**
- Basic tier: 5,000 calls/day (~200 calls/hour)
- Implement simple token bucket if needed (not critical for MVP)

#### 1.4 Fuzzy String Matching (1 hour)

**File:** `nutrition/fatsecret_client.py`

**Implement matching functions:**

**`calculate_similarity(text1, text2)`:**
- Use `difflib.SequenceMatcher(None, text1.lower(), text2.lower()).ratio()`
- Return: Float 0.0-1.0 (1.0 = exact match)

**`normalize_ingredient_name(name)`:**
- Remove accents: `unicodedata.normalize("NFD", name)` + filter
- Lowercase: `.lower()`
- Strip spaces: `.strip()`
- Collapse multiple spaces: `" ".join(name.split())`

**`async match_ingredient(ingredient_name, quantity, unit, supabase, token)`:**

**Workflow:**
1. Normalize ingredient name
2. Check cache: `supabase.table("ingredient_mapping").select("*").eq("ingredient_name_normalized", normalized).execute()`
3. If cache hit:
   - Increment `usage_count`
   - Calculate macros for given quantity (multiply per-100g by quantity/100)
   - Return with `cache_hit: True`
4. If cache miss:
   - Call `search_food()` with normalized name
   - Score each result: `calculate_similarity(normalized_name, food_name)`
   - Add keyword bonus: +0.1 for each keyword match
   - Select best match (highest score)
   - If score < 0.5: Log warning, return None
   - Call `get_food_nutrition()` for detailed data
   - Store in cache with confidence score
   - Calculate macros for quantity
   - Return with `cache_hit: False`

**Unit Conversion:**
- `g` → multiplier = quantity / 100
- `kg` → multiplier = (quantity * 1000) / 100
- `ml` → assume 1ml = 1g (approximation for liquids)
- `pièce` → use default serving_size from cache

#### 1.5 Unit Tests for FatSecret Client (1 hour)

**File:** `tests/test_fatsecret_client.py`

**Test cases:**
1. `test_oauth_token_request` - Mock OAuth, verify token caching
2. `test_oauth_token_refresh` - Verify refresh after expiry
3. `test_search_food_success` - Mock search with multiple results
4. `test_search_food_single_result` - Handle dict vs list
5. `test_get_food_nutrition` - Parse servings correctly
6. `test_calculate_similarity` - Verify SequenceMatcher ratios
7. `test_normalize_ingredient_name` - Handle accents, case, spaces
8. `test_match_ingredient_cache_hit` - Verify cache lookup
9. `test_match_ingredient_cache_miss` - Verify FatSecret fallback
10. `test_match_ingredient_low_confidence` - Handle <50% similarity

**Validation:** `uv run pytest tests/test_fatsecret_client.py -v --cov=nutrition.fatsecret_client`

---

### PHASE 2: Core Implementation - Macro Calculation & Portion Optimization

**Duration:** 4-5 hours

**Objective:** Build the macro calculation engine that replaces GPT-4o approximations with precise Python calculations.

#### 2.1 Precise Macro Calculation Engine (2 hours)

**File:** `nutrition/meal_plan_optimizer.py`

**Implement `async calculate_meal_plan_macros(meal_plan, supabase, token)`:**

**Purpose:** Calculate precise macros for entire meal plan using FatSecret data.

**Algorithm:**
```
For each day in meal_plan:
    daily_totals = {calories: 0, protein_g: 0, carbs_g: 0, fat_g: 0}

    For each meal in day:
        meal_totals = {calories: 0, protein_g: 0, carbs_g: 0, fat_g: 0}

        For each ingredient in meal:
            Try:
                ingredient_macros = await match_ingredient(
                    name=ingredient["name"],
                    quantity=ingredient["quantity"],
                    unit=ingredient["unit"],
                    supabase=supabase,
                    token=token
                )

                Accumulate to meal_totals
                Store FatSecret match data in ingredient dict

            Except ValueError:
                Log error, skip ingredient, continue

        Store meal_totals in meal["nutrition"]
        Add meal_totals to daily_totals

    Store daily_totals in day["daily_totals"]

Return meal_plan
```

**Error Handling:**
- If ingredient not found: Log warning, skip, continue with other ingredients
- If FatSecret API fails: Log error, return plan with partial data
- If low confidence match (<0.5): Log warning, store but flag for review

**Logging:**
- Entry: `logger.info("Calculating macros via FatSecret for 7-day plan")`
- Per day: `logger.info(f"Lundi: 2540 kcal, 140g prot")`
- Cache stats: `logger.info(f"Cache hit rate: 65% (13/20 ingredients)")`
- Success: `logger.info("✅ Macros calculated for all 7 days")`

#### 2.2 Portion Optimization Logic (2-3 hours)

**File:** `nutrition/meal_plan_optimizer.py`

**Implement `async optimize_meal_plan_portions(meal_plan, target_totals, user_allergens)`:**

**Purpose:** Adjust portions to hit target macros, minimizing artificial complements.

**Algorithm:**
```
For each day in meal_plan:
    1. Calculate deficit:
       deficit = calculate_macro_deficit(daily_totals, target_totals)
       needs = needs_adjustment(deficit, target_totals)

    2. If within tolerance (±5%):
       Skip day, continue

    3. Strategy 1 - Portion Scaling:
       If actual_calories > 0:
           scale_factor = target_calories / actual_calories
           scale_factor = clamp(scale_factor, 0.75, 1.25)  # Max ±25%

           For each meal (skip complements):
               For each ingredient:
                   ingredient["quantity"] *= scale_factor
               meal["nutrition"] *= scale_factor

           daily_totals *= scale_factor
           Recalculate deficit

    4. Strategy 2 - Add Complements (if scaling insufficient):
       While needs_adjustment and iterations < 2:
           complement_food = select_complement_food(deficit, allergens, "collation")

           If complement_food:
               Create complement meal with tags ["complement", "optimisé"]
               Add to day["meals"]
               Update daily_totals
               Recalculate deficit
           Else:
               Break (no safe complements available)

Return meal_plan
```

**Key Constraints:**
- Scale factors: 0.75x - 1.25x (avoid extreme changes like 200g chicken → 350g)
- Max 2 complements per day (not 3+ like old system)
- Skip meals already tagged "complement" when scaling
- Prioritize protein deficit (use `select_complement_food()` from existing module)

**Reuse Existing Functions:**
- `calculate_macro_deficit()` from `nutrition/macro_adjustments.py`
- `needs_adjustment()` from `nutrition/macro_adjustments.py`
- `select_complement_food()` from `nutrition/macro_adjustments.py`
- Tolerance constants: `TOLERANCE_PROTEIN = 0.10`, `TOLERANCE_CALORIES = 0.10`

**Logging:**
- Per day: `logger.info("🔧 Optimizing Lundi: -274 kcal deficit")`
- Scaling: `logger.info("  → Scaling portions by 1.11x")`
- Complements: `logger.info("  → Added Shaker protéine whey (+120 kcal, +25g prot)")`
- Success: `logger.info("✅ 7/7 days within ±5% tolerance")`

#### 2.3 Unit Tests for Optimizer (1 hour)

**File:** `tests/test_meal_plan_optimizer.py`

**Test cases:**
1. `test_calculate_macros_all_found` - All ingredients match successfully
2. `test_calculate_macros_missing_ingredient` - Graceful skip on missing
3. `test_optimize_within_tolerance` - No adjustment needed (±5%)
4. `test_optimize_scale_up` - Portions scaled up 15%
5. `test_optimize_scale_down` - Portions scaled down (rare)
6. `test_optimize_add_complement` - Scaling insufficient, add 1 complement
7. `test_optimize_allergen_respect` - Complements avoid allergens
8. `test_optimize_max_iterations` - Stop after 2 complements

**Parametrized tests:**
- Different deficit scenarios: -100 kcal, -400 kcal, -600 kcal
- Different scale factors: 1.05x, 1.15x, 1.25x
- Different allergen combinations: ["lait"], ["lait", "œufs"], []

**Validation:** `uv run pytest tests/test_meal_plan_optimizer.py -v --cov=nutrition.meal_plan_optimizer`

---

### PHASE 3: Integration & Validation

**Duration:** 4-6 hours

**Objective:** Integrate FatSecret-based calculation into existing workflow, validate macro accuracy, and ensure no regressions.

#### 3.1 Modify GPT-4o Prompt (30 min)

**File:** `nutrition/meal_planning.py`

**Function:** `build_meal_plan_prompt()` (lines 216-237)

**Changes:**
1. Add parameter: `calculate_macros: bool = False`
2. Add conditional block:

```
If not calculate_macros:
    Add instructions:
    "🚨 NE CALCULE PAS LES MACROS 🚨

    Fournis SEULEMENT :
    - Noms des recettes (créatifs et appétissants)
    - Ingrédients avec quantités précises (ex: 'poulet': 200g, 'riz': 150g)
    - Instructions de préparation

    NE fournis PAS de champs 'nutrition' ou 'daily_totals'.
    Les macros seront calculés automatiquement via FatSecret API.

    Concentre-toi sur VARIÉTÉ, GOÛT, ALLERGÈNES."

Else:
    Keep existing prompt (backward compatibility)
```

**Rationale:** Prevent GPT-4o from calculating macros (which it does poorly), let Python handle precision.

#### 3.2 Integrate into Meal Planning Tool (2 hours)

**File:** `tools.py`

**Function:** `generate_weekly_meal_plan_tool()` (lines 604-889)

**Changes:**

**1. Add module-level FatSecret auth manager (after imports ~line 62):**
```python
from nutrition.fatsecret_client import FatSecretAuthManager
import os

FATSECRET_AUTH_MANAGER = FatSecretAuthManager(
    client_id=os.getenv("FAT_SECRET_ClientID"),
    client_secret=os.getenv("FAT_SECRET_ClientSecret")
)
```

**2. Modify prompt call (line 738-744):**
```python
prompt = build_meal_plan_prompt(
    profile=profile_data,
    rag_context=rag_result,
    start_date=start_date,
    meal_structure=meal_structure,
    notes=notes,
    calculate_macros=False  # NEW: Disable GPT-4o macro calculation
)
```

**3. Replace post-processing (lines 822-846) with FatSecret integration:**

```
Remove existing:
- Lines 822-846 (adjust_meal_plan_macros call)

Add new:
1. Get FatSecret token:
   fatsecret_token = await FATSECRET_AUTH_MANAGER.get_token(ctx.deps.http_client)

2. Calculate precise macros:
   meal_plan_with_macros = await calculate_meal_plan_macros(
       meal_plan_json, supabase, fatsecret_token
   )

3. Optimize portions:
   optimized_plan = await optimize_meal_plan_portions(
       meal_plan_with_macros, target_macros, user_allergens
   )

4. Generate summary (keep existing):
   adjustment_summary = generate_adjustment_summary(optimized_plan, target_macros)
```

**Preserve unchanged:**
- Steps 1-7 (profile fetch, RAG, prompt build, GPT-4o call)
- Allergen validation (lines 789-803)
- Database storage (lines 849-869)
- Error handling (lines 874-889)

**Logging additions:**
- `logger.info("🔧 Calculating precise macros via FatSecret API...")`
- `logger.info("✅ Macros calculated via FatSecret")`
- `logger.info("✅ Portions optimized to hit targets (±5%)")`

#### 3.3 Integration Testing (1-2 hours)

**Manual Test: Generate Real Meal Plan**

**Command:**
```bash
uv run python -c "
from agent import agent
from clients import create_agent_deps
import asyncio

deps = create_agent_deps()
result = asyncio.run(agent.run('Génère-moi un plan pour la semaine du 13 janvier 2025', deps=deps))
print(result.data)
"
```

**Verify with check_meal_plan.py:**
```bash
uv run python check_meal_plan.py
```

**Success Criteria:**
- 7/7 days within ±5% of targets (2955 kcal, 156g protein)
- 0-1 complement foods per day (vs 3+ before)
- No allergen violations
- Plan feels natural (not robotic)

**Performance Benchmarking (1 hour)**

**Test:** Generate 3 plans sequentially, measure cache performance

**Commands:**
```bash
for i in {1..3}; do
  echo "Plan $i:"
  time uv run python -c "from agent import agent; ..."
done
```

**Metrics to Track:**
- Cache hit rate: Plan 1 (0%), Plan 2 (50%), Plan 3 (70%+)
- FatSecret API calls: Plan 1 (~150), Plan 2 (~75), Plan 3 (~30)
- Total latency: Plan 1 (~35s), Plan 2-3 (~28s)
- Complement usage: 0-1 per day

**Add cache statistics logging:**
```python
# In match_ingredient()
CACHE_STATS = {"hits": 0, "misses": 0}

if cache_hit:
    CACHE_STATS["hits"] += 1
    logger.info(f"Cache HIT (rate: {hits/(hits+misses)*100:.1f}%)")
else:
    CACHE_STATS["misses"] += 1
```

#### 3.4 Edge Case Testing (1 hour)

**Test scenarios:**

**1. Obscure ingredient (not in FatSecret):**
- Input: "fonio" (African grain)
- Expected: Log warning, skip ingredient, continue
- Validation: Plan generated, ingredient has 0 macros

**2. Allergen conflict with complement:**
- Input: User allergic to "lait", system needs protein
- Expected: Select non-dairy (eggs, chicken, tuna)
- Validation: Zero allergen violations

**3. Low confidence match (<50%):**
- Input: "sandwich poulet mayo" (compound)
- Expected: Log warning, skip or decompose
- Validation: No crash, graceful degradation

**4. FatSecret API timeout:**
- Input: Mock network timeout
- Expected: Retry 3x with backoff, then fallback to GPT macros
- Validation: Plan generated, logged error

**5. Token expiry mid-generation:**
- Input: Generate when token 10s from expiry
- Expected: Auto-refresh before calls
- Validation: No 401 errors

**6. Typo in ingredient name:**
- Input: "chiken breast" (typo)
- Expected: Fuzzy match to "chicken breast" (85% similarity)
- Validation: Correct match with confidence logged

#### 3.5 Regression Testing (30 min)

**Run existing test suite:**
```bash
uv run pytest tests/test_validators.py -v
uv run pytest tests/test_adjustments.py -v
uv run pytest tests/test_meal_planning.py -v
```

**Verify:**
- All existing tests pass (no regressions)
- Allergen validation still works (zero tolerance)
- Macro adjustment logic unchanged (tolerance constants)

---

## VALIDATION COMMANDS

### Tier 1: Required Validation (Must Pass)

**Linting:**
```bash
uv run ruff format 4_Pydantic_AI_Agent/nutrition/fatsecret_client.py
uv run ruff format 4_Pydantic_AI_Agent/nutrition/meal_plan_optimizer.py
uv run ruff check 4_Pydantic_AI_Agent/nutrition/
uv run ruff check 4_Pydantic_AI_Agent/tools.py
```

**Unit Tests:**
```bash
uv run pytest tests/test_fatsecret_client.py -v
uv run pytest tests/test_meal_plan_optimizer.py -v
uv run pytest tests/test_validators.py -v
uv run pytest tests/test_adjustments.py -v
```

**Type Checking:**
```bash
uv run mypy 4_Pydantic_AI_Agent/nutrition/fatsecret_client.py --strict
uv run mypy 4_Pydantic_AI_Agent/nutrition/meal_plan_optimizer.py --strict
```

**Manual Smoke Test:**
```bash
# Generate plan
uv run python -c "from agent import agent; ..."

# Verify macros
uv run python check_meal_plan.py
```

### Tier 2: Recommended Validation (Best Effort)

**Integration Tests:**
```bash
uv run pytest tests/test_meal_planning_integration.py -v -m integration
```

**Performance Benchmark:**
```bash
for i in {1..3}; do time uv run python -c "..."; done
```

**Real FatSecret API Test:**
```bash
uv run python -c "
from nutrition.fatsecret_client import FatSecretAuthManager, search_food
import httpx, asyncio, os

async def test():
    auth = FatSecretAuthManager(os.getenv('FAT_SECRET_ClientID'), os.getenv('FAT_SECRET_ClientSecret'))
    async with httpx.AsyncClient() as client:
        token = await auth.get_token(client)
        results = await search_food('chicken breast', token, 5)
        print(f'Found {len(results)} results')

asyncio.run(test())
"
```

---

## ACCEPTANCE CRITERIA

- [ ] 7/7 days within ±5% macro tolerance (vs 1/7 before)
- [ ] 0-1 complement foods per day (vs 3+ before)
- [ ] All Tier 1 validation commands pass
- [ ] Unit test coverage >80% for new modules
- [ ] Cache hit rate >70% by 3rd plan
- [ ] No allergen violations (zero tolerance maintained)
- [ ] No regressions (all existing tests pass)
- [ ] Performance: Total generation <40s, FatSecret overhead <5s

---

## COMPLETION CHECKLIST

- [ ] All tasks completed in order
- [ ] Each task validated immediately
- [ ] Tier 1 validation passed
- [ ] Manual testing confirms 100% macro accuracy
- [ ] check_meal_plan.py shows ±5% for all days
- [ ] Cache performance benchmarked (70%+ hit rate)
- [ ] Edge cases tested (typos, missing ingredients)
- [ ] No regressions in existing functionality

---

## NOTES

### Design Decisions

**Why Dual-Phase (GPT-4o + FatSecret)?**
- Separation of concerns: LLMs = creativity, Python = precision
- Cost efficiency: Single GPT-4o call vs iterative trial-and-error
- Scalability: Caching makes subsequent generations 10x faster

**Why Portion Scaling Before Complements?**
- Preserves recipe naturalness (200g → 230g chicken feels normal)
- Avoids "supplement stack" appearance (3+ shakes per day)
- Better user experience: Real food > artificial complements

**Why FatSecret vs Alternatives?**
- ✅ 500,000+ foods (most comprehensive free database)
- ✅ OAuth 2.0 (secure, standard)
- ✅ Per-100g nutrition (easy conversions)
- ❌ USDA FoodData Central (free but less comprehensive)
- ❌ Nutritionix (paid, $50/month)

**Why Supabase Cache vs In-Memory?**
- Persistent across restarts
- Queryable (analyze most-used ingredients)
- Shareable across agent instances
- Manual verification possible (verify flag)

### Trade-offs

**Accepted:**
- Complexity: 2 new modules, 1 new table
- Latency: +10s first plan (0% cache), +3s subsequent (70% cache)
- Dependency: FatSecret API uptime (mitigated by fallback)

### Confidence: 8.5/10

**Strengths:**
- Clear architecture separation
- Patterns well-documented
- FatSecret API well-suited
- Strong caching strategy

**Uncertainties:**
- FatSecret rate limits (5000 calls/day Basic tier)
- Fuzzy matching for French ingredients
- Portion scaling UX (15% larger portions noticeable?)

**Mitigations:**
- Monitor API usage, upgrade tier if needed
- Pre-populate cache with top 50 French ingredients
- Log low-confidence matches (<75%) for review
- Prompt GPT-4o to decompose compound foods

### Rollback Plan

**If critical issue:**
- Keep old post-processing code commented
- Feature flag: `USE_FATSECRET=false` in .env
- Rollback time: <5 minutes
- Revert to old system immediately

### Expected Performance

**Current (GPT-4o only):**
- Latency: ~25s
- Accuracy: 14% (1/7 days ±10%)
- Complements: 3+/day

**New (GPT-4o + FatSecret):**
- Latency: 35s (first), 28s (cached)
- Accuracy: 100% (7/7 days ±5%)
- Complements: 0-1/day

**Cache Performance:**
- Plan 1: 0% hit rate
- Plan 2: 50% hit rate
- Plan 3+: 70-80% hit rate
