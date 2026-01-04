# AI Nutrition Assistant - Development Guide

**Stack:** Python 3.11+ | Pydantic AI | React 18 | TypeScript 5 | Supabase
**Status:** Module 4 - Python Backend Development

**⚠️ IMPORTANT:** Avant de modifier du code, lire `.claude/reference/dependency-safety-rules.md` pour éviter les breaking changes.

---

## 1. Core Principles

1. **Science-First**: All nutrition calculations use validated formulas (Mifflin-St Jeor for BMR). Cite sources in docstrings.

2. **Type Safety**: Full type hints in Python (args + return). No `any` in TypeScript. Strict mode enabled.

3. **Safety Constraints** (Hardcoded, never bypass):
   ```python
   MIN_CALORIES_WOMEN = 1200
   MIN_CALORIES_MEN = 1500
   ALLERGEN_ZERO_TOLERANCE = True  # Never suggest allergen foods
   ```

4. **Async by Default**: All I/O (API calls, DB, files) must be async with proper error handling.

5. **Documentation**: Google-style docstrings (Python), JSDoc (TypeScript) with Args/Returns/Examples.

---

## 2. Tech Stack

### Backend
- **Agent:** Pydantic AI, OpenAI API (GPT-4o/mini)
- **Database:** Supabase (PostgreSQL + pgvector), mem0 (long-term memory)
- **Tools:** httpx (async HTTP), Brave Search API, python-dotenv
- **Dev:** pytest + pytest-asyncio, ruff (lint/format), mypy (types)

### Frontend
- **Core:** React 18, TypeScript 5, Vite 5
- **UI:** shadcn/ui, Tailwind CSS, Lucide icons
- **State:** React Query, React Hook Form + Zod
- **Dev:** ESLint, TypeScript ESLint

---

## 3. Architecture

### Backend Structure
```
4_Pydantic_AI_Agent/
├── agent.py, tools.py, prompt.py, clients.py    # Core agent
├── nutrition/                                    # Domain logic
│   ├── calculations.py, adjustments.py, validators.py
├── RAG_Pipeline/                                 # Document sync
│   ├── common/ (db_handler, text_processor)
│   ├── Google_Drive/ (drive_watcher)
│   └── Local_Files/ (file_watcher)
├── tests/                                        # Test suite
└── sql/                                          # DB schema
```

**Patterns:** Agent orchestrates tools → Tools call nutrition logic → AgentDeps for shared resources (Supabase, HTTP client)

### Frontend Structure
```
src/
├── components/chat/      # ChatContainer, ChatInput, Message
├── hooks/                # useChat (API logic)
├── pages/                # Index (main page)
├── types/                # TypeScript interfaces
└── utils/                # sessionManager
```

**Patterns:** Feature folders → Custom hooks for logic → Small components → Type-safe interfaces

---

## 4. Code Style

### Naming Conventions

**Python:**
```python
# Functions: snake_case                # Classes: PascalCase
async def calculate_nutritional_needs(...) -> dict:
    pass

@dataclass
class AgentDeps:
    supabase: Client

# Variables: snake_case                # Constants: UPPER_SNAKE_CASE
target_calories = 3168                  MIN_CALORIES_WOMEN = 1200
```

**TypeScript:**
```typescript
// Functions: camelCase                // Components: PascalCase
const sendMessage = async (...) => {}   export function ChatContainer() {}

// Interfaces: PascalCase               // Constants: UPPER_SNAKE_CASE
interface Message { ... }               const WEBHOOK_URL = '...'
```

### Docstrings (Python - Google Style)

```python
async def calculate_weekly_adjustments(
    weight_start: float,
    weight_end: float,
    current_calories: int,
    user_goal: str = "maintenance"
) -> dict:
    """
    Analyze weekly feedback and recommend nutritional adjustments.

    Args:
        weight_start: Weight at start of week (kg)
        weight_end: Weight at end of week (kg)
        current_calories: Current daily calorie target
        user_goal: "weight_loss" | "muscle_gain" | "maintenance"

    Returns:
        Dict with status, adjustments, new_targets, rationale, tips

    Example:
        >>> result = await calculate_weekly_adjustments(87.0, 86.4, 3168, "muscle_gain")
        >>> print(result["status"])
        "stable"

    References:
        ISSN Position Stand (2017), Helms et al. (2014)
    """
```

---

## 5. Logging

**Python:** Structured logging with context
```python
logger = logging.getLogger(__name__)

# Log with extra fields
logger.info("Calculating needs", extra={"age": age, "weight_kg": weight_kg})
logger.error("Validation failed", extra={"error": str(e)}, exc_info=True)
```

**TypeScript:** Console logs with structured objects
```typescript
console.log('📤 Sending message', { sessionId, messageLength });
console.error('❌ Failed', { error: error.message, sessionId });
```

**What to Log:** Tool calls, API requests, calculations, errors with context
**Never Log:** API keys, passwords, sensitive user data

---

## 6. Testing

**Framework:** pytest + pytest-asyncio | Files: `test_<module>.py` | Tests: `test_<function>_<scenario>`

```python
@pytest.mark.asyncio
async def test_calculate_nutritional_needs_male_moderate():
    """Test BMR/TDEE for 35yo male, 87kg, 178cm, moderate activity."""
    result = await calculate_nutritional_needs(
        age=35, gender="male", weight_kg=87, height_cm=178, activity_level="moderate"
    )

    assert result["bmr"] == pytest.approx(1850, abs=5)  # Mifflin-St Jeor
    assert result["tdee"] == pytest.approx(2868, abs=10)  # BMR × 1.55
    assert result["target_protein_g"] >= 140  # At least 1.6g/kg

@pytest.mark.asyncio
async def test_calculate_needs_invalid_age():
    """Test age validation raises ValueError."""
    with pytest.raises(ValueError, match="Age must be between"):
        await calculate_nutritional_needs(age=15, gender="male", weight_kg=70, height_cm=175)
```

**Run:** `pytest` | `pytest tests/test_calculations.py` | `pytest --cov=nutrition`

---

## 7. API Contracts

**Type Matching (Python TypedDict ↔ TypeScript interface):**
```python
# Backend
class NutritionResult(TypedDict):
    bmr: int
    tdee: int
    target_calories: int
    target_protein_g: int
```

```typescript
// Frontend
interface NutritionResult {
  bmr: number;
  tdee: number;
  target_calories: number;
  target_protein_g: number;
}
```

**Error Handling:**
- Backend: `{"output": "..."}` or `{"error": "...", "code": "VALIDATION_ERROR"}`
- Frontend: Check `data.error`, fallback to `data.output || data.response`

---

## 8. Common Patterns

### Pattern 1: Pydantic AI Tool
```python
@dataclass
class AgentDeps:
    supabase: Client
    http_client: AsyncClient

agent = Agent(get_model(), system_prompt=PROMPT, deps_type=AgentDeps, retries=2)

@agent.tool
async def calculate_nutritional_needs(
    ctx: RunContext[AgentDeps],
    age: int,
    gender: str,
    weight_kg: float,
    height_cm: int,
    activity_level: str
) -> str:
    """Calculate BMR/TDEE using Mifflin-St Jeor. Returns JSON string."""
    logger.info(f"Calculating nutrition for age={age}, weight={weight_kg}kg")

    if not 18 <= age <= 100:
        raise ValueError("Age must be between 18 and 100")

    bmr = mifflin_st_jeor_bmr(age, gender, weight_kg, height_cm)
    tdee = calculate_tdee(bmr, activity_level)

    return json.dumps({"bmr": bmr, "tdee": tdee, "target_calories": tdee + 300})
```

### Pattern 2: Supabase RAG Query
```python
async def retrieve_relevant_documents(
    supabase: Client, embedding_client: AsyncOpenAI, user_query: str
) -> str:
    """Retrieve relevant chunks using semantic search."""
    response = await embedding_client.embeddings.create(
        model="text-embedding-3-small", input=user_query
    )
    query_embedding = response.data[0].embedding

    result = supabase.rpc("match_documents", {
        "query_embedding": query_embedding,
        "match_count": 4,
        "match_threshold": 0.7
    }).execute()

    if not result.data:
        return "No relevant documents found."

    return "\n".join([
        f"--- Doc {i} (sim: {d['similarity']:.2f}) ---\n{d['content']}"
        for i, d in enumerate(result.data, 1)
    ])
```

### Pattern 3: React Hook with API
```typescript
export function useNutritionCalculation() {
  const [result, setResult] = useState<NutritionResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const calculate = async (params: NutritionParams) => {
    setIsLoading(true);
    try {
      const res = await fetch(`${API_URL}/calculate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params)
      });
      setResult(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown');
    } finally {
      setIsLoading(false);
    }
  };

  return { result, isLoading, error, calculate };
}
```

---

## 8.5: Weekly Feedback Analysis & Continuous Learning System

### Overview
The weekly feedback analysis system enables the AI Nutrition Assistant to continuously learn from user data, detect patterns over time, and generate highly personalized recommendations. This section documents the `calculate_weekly_adjustments_tool` and supporting infrastructure.

### Weekly Adjustment Tool Workflow

**Tool Signature:**
```python
@agent.tool
async def calculate_weekly_adjustments(
    ctx: RunContext[AgentDeps],
    weight_start_kg: float,
    weight_end_kg: float,
    adherence_percent: int,
    hunger_level: str = "medium",
    energy_level: str = "medium",
    sleep_quality: str = "good",
    cravings: list[str] | None = None,
    notes: str = "",
) -> str:
    """
    Analyze weekly feedback and generate personalized nutrition adjustments.

    Returns JSON with: analysis (pattern detection), adjustments (calorie/macro changes),
    red_flags (safety alerts), confidence_level (0.3-1.0), recommendations (actionable tips)
    """
```

**User Flow:**
1. User provides weekly check-in data: weight change, adherence%, subjective metrics
2. Tool validates input metrics and fetches user profile + 4-week history
3. Analysis engine runs 6 core functions: weight_trend, metabolic_adaptation, adherence_patterns, calorie_adjustment, macro_adjustments, red_flag_detection
4. System detects patterns + confidence scoring
5. Stores feedback in `weekly_feedback` table, updates `user_learning_profile`
6. Agent presents results warmly with scientific rationale

### Safety Constraints for Adjustments

All adjustment recommendations are **strictly bounded** to prevent metabolic shock and maintain adherence:

```python
# Calorie Adjustments (Primary)
CALORIE_ADJUSTMENT_MAX = 300  # ±300 kcal/day maximum (MVP - see note below)

# Macro Adjustments (Secondary)
PROTEIN_ADJUSTMENT_MAX = 30   # ±30g per day
CARB_ADJUSTMENT_MAX = 50      # ±50g per day
FAT_ADJUSTMENT_MAX = 15       # ±15g per day

# Weight Loss Rate Targets (Goal-Specific)
MUSCLE_GAIN_TARGET = (0.2, 0.5)      # kg/week, range
WEIGHT_LOSS_TARGET = (-0.7, -0.3)    # kg/week, range (negative = loss)
MAINTENANCE_TARGET = (-0.5, 0.5)     # kg/week, range
```

**Rationale:** Conservative adjustments enable habit formation, prevent diet fatigue, and allow accurate pattern detection over 4+ week cycles.

---

**IMPORTANT MVP NOTE - Adjustment Bounds Design (Subject to Change):**

The adjustment bounds (300 kcal, 30g protein, 50g carbs, 15g fat) are **design choices optimized for MVP**, NOT direct recommendations from scientific literature.

- **Scientific Basis:** Informed by principles in Fothergill et al. (2016), Helms et al. (2014), and ISSN (2017), but not explicitly prescribed by these sources
- **MVP Rationale:** Conservative bounds allow habit formation over 4 weeks and enable accurate pattern detection
- **Potential Future Changes (Phase 2+):**
  - Make goal-specific: `weight_loss=±350 kcal`, `muscle_gain=±200 kcal`, `maintenance=±100 kcal`
  - Make confidence-dependent: Smaller bounds in week 1, larger by week 4+
  - Optimize based on real user data after 4+ weeks of use

**How to Optimize Later:**
1. Track whether users hit the 300 kcal cap frequently (indicates bounds too conservative)
2. Monitor if larger adjustments would accelerate progress without harming adherence
3. Analyze weight loss rate: if >1.0 kg/week, reduce to 250 kcal; if <0.2 kg/week, increase to 350 kcal
4. Implement goal-specific bounds based on adherence patterns observed

See `nutrition/adjustments.py` (lines 55-99) for detailed optimization guidelines.

### Weekly Feedback Workflow

The weekly feedback analysis workflow is the **core process** for continuous personalization:

**User Experience (5 Steps):**
1. **End of Week** - User mentions "week is done" or asks "how did I do?"
2. **Conversational Collection** - Agent asks natural questions (not form-filling) to gather: weight change, adherence%, hunger, energy, sleep
3. **Tool Invocation** - Agent calls `calculate_weekly_adjustments()` with explicit metrics
4. **Result Presentation** - Agent presents analysis warmly + scientifically, explains adjustments, shows confidence level
5. **Learning Update** - Profile auto-updates with discovered patterns for next week's personalization

**Data Collected:**
```python
# Required (for valid analysis)
weight_start_kg: float          # Weight at week start
weight_end_kg: float            # Weight at week end
adherence_percent: int (0-100)  # % of plan followed

# Optional but valuable
hunger_level: "low" | "medium" | "high"
energy_level: "low" | "medium" | "high"
sleep_quality: "poor" | "fair" | "good" | "excellent"
cravings: list[str]             # ["chocolate", "pizza"]
notes: str                      # Free-text observations
```

**Analysis Performed:**
- **Weight Trend**: Compare to goal targets (Helms et al. 2014 recommendations)
- **Metabolic Adaptation**: Detect if actual TDEE < calculated TDEE
- **Adherence Patterns**: Identify recurring triggers (e.g., "Friday energy drops")
- **Macro Sensitivity**: Discover individual protein/carb/fat response
- **Red Flags**: 6-type safety check (rapid loss, hunger, energy, mood, abandonment, stress)

**Output Format:**
```json
{
  "status": "success",
  "analysis": {
    "weight_trend": {"change_kg": -0.6, "trend": "optimal"},
    "patterns_detected": ["energy_stable", "hunger_managed"],
    "new_insights": ["Friday routine consistent with adherence"]
  },
  "adjustments": {
    "suggested": {"calories": 50, "protein_g": 20, "carbs_g": 0, "fat_g": 0},
    "rationale": ["High hunger → increase protein for satiety", "Energy stable → no adjustment needed"]
  },
  "red_flags": [],
  "confidence_level": 0.78,
  "recommendations": [
    "Your -0.6kg loss is exactly on target!",
    "Adding 20g protein should help with hunger",
    "Keep Friday routine—it's working for you"
  ]
}
```

### Red Flag Detection (6 Types)

The system monitors for 6 categories of concerning patterns with tiered responses:

```python
# RED FLAG TYPE 1: Rapid Weight Loss
# Trigger: Weight loss > 1.0 kg/week
# Severity: CRITICAL
# Action: Reduce calorie deficit by 200-300 kcal, recommend doctor consultation
# Why: Risk of muscle loss, metabolic damage, nutrient deficiency
# Reference: Fothergill et al. (2016) - rapid loss increases metabolic adaptation

# RED FLAG TYPE 2: Extreme Hunger
# Trigger: hunger_level = "extreme" for 2+ consecutive weeks
# Severity: WARNING
# Action: Increase calories by 150 kcal, boost protein/fat satiety factors
# Why: Unsustainable deficit, adherence risk, quality of life concern

# RED FLAG TYPE 3: Energy Crash
# Trigger: energy_level = "low/crashed" + adherence > 80%
# Severity: WARNING
# Action: Reduce deficit by 100 kcal, check micronutrients, consider rest day
# Why: Possible underfueling despite adherence, carb/electrolyte depletion

# RED FLAG TYPE 4: Mood/Mental Health Shift
# Trigger: mood = "depressed" or stress_level = "high"
# Severity: CRITICAL
# Action: Pause aggressive deficit, suggest mental health support, reduce deficit 20%
# Why: Psychological safety > physical results, nutrition is secondary

# RED FLAG TYPE 5: Abandonment Risk
# Trigger: adherence drops >25% from prior week OR < 60% absolute
# Severity: WARNING
# Action: Simplify meal plan, reduce adjustment size, increase check-in frequency
# Why: Pattern precedes dropout; early intervention essential

# RED FLAG TYPE 6: Stress Overload
# Trigger: stress_level = "extreme" + sleep_quality < "fair"
# Severity: WARNING
# Action: Maintain current targets (no changes), focus on sleep/stress management
# Why: Stress + sleep deprivation impairs metabolism; changes ineffective
```

**Critical Rule:** Mental health flags (Types 4, 6) override all other recommendations. Always prioritize user wellbeing.

### Red Flag Response Protocol

When a red flag is detected, follow this **priority-based response protocol**:

**Priority 1: Immediate Safety (Critical Flags - Types 4 & 6)**

Mental health or severe stress overload:
```
Actions:
1. Acknowledge with EMPATHY (not fear)
   ✅ "I notice you're stressed. Let's pause adjustments and focus on you."
   ❌ "WARNING: Depression detected!"

2. Offer SUPPORT (not diet advice)
   ✅ "Would talking to someone help? Should we simplify things?"
   ❌ "Just eat more protein and you'll feel better."

3. PAUSE aggressive changes
   - Maintain current targets
   - Suggest rest day or stress management
   - Follow up next week on wellbeing first

4. Always document: Reason, response, follow-up date
```

**Priority 2: Pattern Monitoring (Warning Flags - Types 1, 2, 3, 5)**

Physical patterns (rapid loss, hunger, energy, abandonment risk):
```
Actions:
1. Explain MECHANISM (not judgment)
   ✅ "Rapid loss triggers metabolic slowdown. Let's adjust gently."
   ❌ "You're losing too fast—you're doing it wrong!"

2. Suggest GRADUATED change (not dramatic)
   ✅ "Try -100 kcal this week, see how you feel"
   ❌ "Immediately cut 300 kcal and increase cardio"

3. MONITOR closely for next report
   - If pattern improves: celebrate + continue
   - If pattern repeats: escalate to Priority 1

4. Educate with SCIENCE and DATA
   - "Helms et al. shows rapid loss increases abandonment"
   - "Your -0.5kg/week average is actually perfect!"
```

**Priority 3: Informational (Positive Observations)**

Patterns detected with no safety concern:
```
Response: Celebrate + educate. No action required.

Examples:
- "3 consecutive Fridays with high energy! Keep that pattern."
- "You've discovered high carbs help your energy. Perfect insight!"
- "Your weekend adherence is 90%—you're crushing it!"
```

**Response Template (for Red Flag Presentation):**
```
[If RED FLAG detected]

I notice something: [OBSERVATION without judgment]

Why it matters: [SCIENTIFIC BASIS from paper/research]

My suggestion: [GRADUATED ACTION, not dramatic change]

Your thoughts: [ASK FOR FEEDBACK AND BUY-IN]

Example:
---
I noticed rapid weight loss this week (-1.2kg).
This can trigger metabolic adaptation where your body adjusts.

Helms et al. research shows slower loss (0.5kg/week) leads to
better long-term results and less abandonment risk.

How about we reduce by 100 kcal this week? We can check next
week if you feel better.

How does that sound? Any concerns?
---
```

**Critical Safety Guardrails:**
1. **Never blame**: "Hunger is normal at this deficit—let's adjust"
2. **Never dismiss**: Investigate all patterns, even if user says "it's fine"
3. **Never override consent**: Always ask "Does this work for you?"
4. **Never delay Priority 1**: Stop everything if mental health flag appears
5. **Always document**: Flag date, reason, action taken, next check-in date

### Learning Profile: Continuous Personalization

The system maintains a per-user `user_learning_profile` table that accumulates insights:

**Phase 1: First 4 Weeks (Learning Mode)**
- Generic recommendations based on profile
- Weekly_feedback table accumulates data
- Confidence scoring: 0.5 (baseline, incomplete data)
- Next tool uses: Meal planning, adjustment generation

**Phase 2: 4+ Weeks (Adaptation Mode)**
- Pattern detection activates with 4+ weekly records
- Learning profile populated with discovered sensitivities
- Confidence scoring: 0.75 base (can increase with perfect data)
- Tool uses discovered patterns for personalization

**Learned Insights Captured:**
```python
# Sensitivities (macro impact on weight/energy)
protein_sensitivity_g_per_kg: float      # How sensitive to protein changes
carb_sensitivity: str                    # "low" | "medium" | "high"
fat_sensitivity: str                     # "low" | "medium" | "high"

# Patterns (behavioral triggers)
adherence_triggers: dict                 # What enables/blocks adherence
energy_patterns: dict                    # When energy crashes, optimal macros
meal_preferences: list[str]              # Preferred foods that fit macros
psychological_patterns: dict             # Stress response, motivation patterns
```

**Example:** After 4 weeks, system detects "Carb sensitivity: HIGH". When adjusting macros, the system now:
- Prefers fat/protein increases over carb increases
- Suggests timing carbs around activity
- Monitors energy closely when reducing carbs

### Learning Profile Integration Pattern

The learning profile automatically influences four key tools and workflows:

**1. Meal Plan Generation** (`generate_weekly_meal_plan_tool`)
```python
# Before generating meal plan, fetch learning profile:
learning_profile = supabase.table("user_learning_profile").select("*").execute()

# Extract personalization hints:
if learning_profile.get("meal_preferences"):
    prompt += f"User loves: {learning_profile['meal_preferences']['loved']}"
    prompt += f"User dislikes: {learning_profile['meal_preferences']['disliked']}"

if learning_profile.get("energy_patterns"):
    # "Friday energy drops with low carbs" → plan higher carbs Friday
    if learning_profile["energy_patterns"].get("friday_drops"):
        prompt += "Friday: Include higher carbs pre-activity"

if learning_profile.get("carb_sensitivity") == "high":
    # User performs better on higher carbs → optimize macro ratio
    prompt += "This user responds well to 45%+ carbs"
```

**2. Adjustment Recommendation** (`calculate_weekly_adjustments_tool`)
```python
# Use learned macro sensitivity to refine suggestions:
if learning_profile.get("carb_sensitivity") == "high":
    # Don't suggest carb cuts → prefer protein/fat adjustments
    adjustment_strategy = "adjust_protein_fat_first"
elif learning_profile.get("protein_sensitivity_g_per_kg") == 2.5:
    # User needs 2.5g/kg, not ISSN's 1.6g/kg → prioritize protein
    adjustment_strategy = "boost_protein_aggressive"
```

**3. Red Flag Detection** (enhanced context)
```python
# Red flag thresholds can be personalized:
# Generic: rapid loss = >1.0 kg/week
# Personalized: if user has history of rapid adaptation, adjust threshold to >0.8 kg/week

red_flag_thresholds = {
    "rapid_weight_loss": learning_profile.get("rapid_loss_threshold", 1.0),
    "extreme_hunger": learning_profile.get("hunger_threshold", "extreme"),
    ...
}
```

**4. Confidence Scoring** (account for profile maturity)
```python
# Confidence increases as profile becomes more predictive
base_confidence = 0.5

# Boost if learning profile is well-populated
if learning_profile.get("weeks_of_data", 0) >= 4:
    base_confidence = 0.75

if learning_profile.get("macro_sensitivity_detected"):
    base_confidence += 0.1  # More confident with known patterns

if learning_profile.get("adherence_triggers"):
    base_confidence += 0.05  # More confident with behavior triggers
```

**Integration Points Checklist:**
- [ ] Meal plan tool queries learning profile before generating
- [ ] Adjustment tool uses learned sensitivities when calculating macros
- [ ] Red flag detection uses personalized thresholds (if available)
- [ ] Confidence scoring accounts for profile completeness
- [ ] Learning profile automatically updates after each weekly synthesis
- [ ] Profile data never overwrites; only adds/refines patterns

### Confidence Scoring System

Recommendations include a confidence score (0.3-1.0) indicating recommendation reliability:

```python
# Base Confidence
base_confidence = 0.75 if weeks_of_data >= 4 else 0.5

# Penalties (Each reduces confidence by specified amount)
incomplete_weight_data: -0.15     # Missing weight_start or weight_end
incomplete_adherence: -0.15       # Adherence not provided
no_subjective_metrics: -0.10      # Missing hunger/energy/sleep signals
red_flags_present: -0.10          # Active warnings reduce confidence

# Floor: Confidence never drops below 0.3
# Ceiling: Confidence never exceeds 1.0

# Interpretation Guide
# 0.3-0.5: Very Low - Recommend doctor consultation, use baseline values
# 0.5-0.7: Low - Use adjustments cautiously, verify with user
# 0.7-0.85: Moderate - Standard recommendation, explain reasoning
# 0.85-1.0: High - Confidence is high, can recommend proactively
```

**Usage:** Agent shows confidence in output: "High confidence (0.92): Based on 6 weeks of data..."

### Integration Points

**Meal Planning Enhancement:**
The `generate_weekly_meal_plan_tool` now queries `user_learning_profile` for personalization hints:
- Meal preferences: Suggests preferred foods that fit current macros
- Energy patterns: Times carbs for optimal energy (e.g., higher carbs pre-workout if sensitive)
- Adherence triggers: Incorporates what helped/hindered prior weeks
- Macro sensitivity: Respects discovered sensitivities when generating meals

**Database Tables:**
- `weekly_feedback`: 27 columns, stores feedback + analysis + adjustments per week
- `user_learning_profile`: 23 columns, stores accumulated patterns + psychological insights

### Phase 2-3 Roadmap: Learning System Evolution

The MVP (Phase 1) establishes baseline patterns. Phase 2-3 optimize based on real user data.

**Phase 2 Timeline: Weeks 4-8 (After First Batch of Users)**

Prerequisite: 4 weeks of real user data collected

**Phase 2 Goals:**
1. **Validate MVP Bounds** - Are ±300 kcal bounds correct?
   - Metric: Track if users hit cap frequently (>30% = too conservative)
   - Metric: Monitor weight loss rate (should be -0.3 to -0.7 kg/week)
   - Decision: Keep as-is, or implement goal-specific bounds?

2. **Implement Goal-Specific Bounds** (Optional)
   ```python
   # Current: ±300 kcal for all goals
   # Proposed: weight_loss=±350, muscle_gain=±200, maintenance=±100
   # Reason: Different goals have different adherence requirements
   ```

3. **Personalize Red Flag Thresholds**
   - Current: Fixed thresholds (e.g., >1.0 kg/week = rapid loss)
   - Proposed: User-specific thresholds based on profile
   - Example: "User A metabolizes fast; set threshold to >0.8 kg/week"

**Phase 3 Timeline: Weeks 8-12 (After Pattern Confirmation)**

Prerequisite: 8 weeks of data showing consistent patterns

**Phase 3 Goals:**
1. **Implement Confidence-Dependent Bounds**
   - Week 1: ±100 kcal (very conservative)
   - Weeks 2-3: ±150 kcal (moderate)
   - Week 4+: ±300 kcal (full bounds)
   - Reason: Early weeks lack data; later weeks have proven consistency

2. **Enable Macro Personalization**
   - Current: Recommend all users follow ISSN guidelines (1.6-3.1 g/kg protein)
   - Proposed: Use learned `protein_sensitivity_g_per_kg` for custom targets
   - Example: If user thrives on 2.5g/kg, recommend that instead

3. **Activate Learning Profile Influence**
   - Meal plans automatically incorporate learned preferences
   - Adjustment recommendations respect discovered macro sensitivities
   - Red flags use personalized thresholds

**Transition from Phase to Phase:**
1. **Phase 1→2**: Analyze metrics → Make decisions → Update constants in code
2. **Phase 2→3**: Confirm patterns persist → Implement more complex logic
3. **Phase 3→Production**: Run parallel tests (MVP bounds vs. new bounds) → Choose best performer

**Detailed Roadmap Document:**
See `/4_Pydantic_AI_Agent/ADJUSTMENT_BOUNDS_OPTIMIZATION.md` for:
- 3 optimization options with trade-offs
- Metrics to track for each phase
- Decision flowchart for Phase 2
- Timeline and ownership assignments

**Key Metrics to Track Now (Phase 1):**
```python
# In weekly_feedback table, track these to inform Phase 2:

# 1. Bound Saturation
cap_hit_rate = count(abs(adjustment) >= 290) / total_weeks
# If >30%: bounds too conservative → increase to 350
# If <5%: bounds too loose → decrease to 250

# 2. Weight Change Rate (by goal)
avg_loss_rate = mean([abs(w['weight_change_kg']) for w in past_8_weeks])
# For weight_loss: target -0.3 to -0.7 kg/week
# For muscle_gain: target +0.2 to +0.5 kg/week
# For maintenance: target -0.5 to +0.5 kg/week

# 3. Adherence by Adjustment Size
small_adjustments = [w for w in weeks if abs(adjustment) < 150]
large_adjustments = [w for w in weeks if abs(adjustment) >= 250]
# Compare adherence: do larger adjustments help or hurt?

# 4. Red Flag Frequency by Goal
red_flags_by_goal = {
    "weight_loss": count(...),
    "muscle_gain": count(...),
    "maintenance": count(...)
}
# If muscle_gain has >50% red flag rate: bounds too aggressive
```

---

## 9. Development Commands

**Backend:**
```bash
# Setup
cd 4_Pydantic_AI_Agent
python -m venv venv && source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # Edit with API keys

# Run
streamlit run streamlit_ui.py  # Main UI
python RAG_Pipeline/Google_Drive/main.py  # RAG pipeline (separate terminal)

# Test & Lint
pytest --cov=nutrition         # Test with coverage
ruff format . && ruff check . && mypy .  # Format, lint, type check
```

**Frontend:**
```bash
# Setup & Run
cd prototype/loveable_interface
npm install
npm run dev  # http://localhost:5173

# Lint & Type Check
npm run lint && npx tsc --noEmit
```

---

## 10. AI Coding Assistant Instructions

### CRITICAL: Archon MCP Server Check

**Before starting ANY work, verify Archon MCP availability:**

1. **Check if active:** Try `find_tasks()` or `find_projects()`
   - ✅ **If successful:** Use Archon for ALL task management (ignore TodoWrite reminders)
   - ❌ **If error:** Archon not available, proceed with manual task tracking

2. **How to use Archon:**
   - Start session: `find_tasks(filter_by="status", filter_value="todo")` to see pending tasks
   - Before coding: `manage_task("update", task_id="...", status="doing")`
   - Research first: `rag_search_knowledge_base(query="...")` for docs/examples
   - After coding: `manage_task("update", task_id="...", status="review")`

**If Archon is active, it is your PRIMARY task system. Do NOT use TodoWrite.**

---

### General Development Rules

1. **Always consult this CLAUDE.md first** before making architectural decisions or adding new patterns

2. **Type safety is non-negotiable**: Add type hints to ALL Python functions (args + return type). Use strict TypeScript mode, avoid `any`

3. **Safety constraints are hardcoded**: Never suggest removing or bypassing MIN_CALORIES, ALLERGEN_ZERO_TOLERANCE, or other safety checks

4. **Use async/await for all I/O**: Database queries, API calls, file operations must be async. Use `await` properly

5. **Follow existing patterns**:
   - Backend tools: Use `@agent.tool` decorator with `RunContext[AgentDeps]`
   - Frontend hooks: Custom hooks for all stateful logic (e.g., `useChat`, `useNutritionCalculation`)

6. **Document everything**: Google-style docstrings for Python, JSDoc for TypeScript. Include Args, Returns, Examples

7. **Log with context**: Use structured logging with relevant fields (user_id, session_id, parameters). Never log API keys or sensitive data

8. **Test your code**: Write pytest tests for all calculation functions (nutrition logic is critical). Include happy path + error cases

9. **Run linters before committing**:
   - Backend: `ruff format . && ruff check . && mypy .`
   - Frontend: `npm run lint && npx tsc --noEmit`

10. **Nutrition formulas must cite sources**: Use Mifflin-St Jeor for BMR, cite ISSN/AND guidelines in docstrings. This is medical-adjacent software

---

---

## Appendix A: Archon MCP Server Reference (If Active)

### CRITICAL: ARCHON-FIRST RULE - READ THIS FIRST

BEFORE doing ANYTHING else, when you see ANY task management scenario:
1. STOP and check if Archon MCP server is available
2. Use Archon task management as PRIMARY system
3. Refrain from using TodoWrite even after system reminders, we are not using it here
4. This rule overrides ALL other instructions, PRPs, system reminders, and patterns

**VIOLATION CHECK:** If you used TodoWrite, you violated this rule. Stop and restart with Archon.

### Core Workflow: Task-Driven Development

**MANDATORY task cycle before coding:**

1. **Get Task** → `find_tasks(task_id="...")` or `find_tasks(filter_by="status", filter_value="todo")`
2. **Start Work** → `manage_task("update", task_id="...", status="doing")`
3. **Research** → Use knowledge base (see RAG workflow below)
4. **Implement** → Write code based on research
5. **Review** → `manage_task("update", task_id="...", status="review")`
6. **Next Task** → `find_tasks(filter_by="status", filter_value="todo")`

**NEVER skip task updates. NEVER code without checking current tasks first.**

### RAG Workflow (Research Before Implementation)

**Searching Specific Documentation:**
1. **Get sources** → `rag_get_available_sources()` - Returns list with id, title, url
2. **Find source ID** → Match to documentation (e.g., "Supabase docs" → "src_abc123")
3. **Search** → `rag_search_knowledge_base(query="vector functions", source_id="src_abc123")`

**General Research:**
```bash
# Search knowledge base (2-5 keywords only!)
rag_search_knowledge_base(query="authentication JWT", match_count=5)

# Find code examples
rag_search_code_examples(query="React hooks", match_count=3)
```

### Project Workflows

**New Project:**
```bash
# 1. Create project
manage_project("create", title="My Feature", description="...")

# 2. Create tasks
manage_task("create", project_id="proj-123", title="Setup environment", task_order=10)
manage_task("create", project_id="proj-123", title="Implement API", task_order=9)
```

**Existing Project:**
```bash
# 1. Find project
find_projects(query="auth")  # or find_projects() to list all

# 2. Get project tasks
find_tasks(filter_by="project", filter_value="proj-123")

# 3. Continue work or create new tasks
```

### Tool Reference

**Projects:**
- `find_projects(query="...")` - Search projects
- `find_projects(project_id="...")` - Get specific project
- `manage_project("create"/"update"/"delete", ...)` - Manage projects

**Tasks:**
- `find_tasks(query="...")` - Search tasks by keyword
- `find_tasks(task_id="...")` - Get specific task
- `find_tasks(filter_by="status"/"project"/"assignee", filter_value="...")` - Filter tasks
- `manage_task("create"/"update"/"delete", ...)` - Manage tasks

**Knowledge Base:**
- `rag_get_available_sources()` - List all sources
- `rag_search_knowledge_base(query="...", source_id="...")` - Search docs
- `rag_search_code_examples(query="...", source_id="...")` - Find code

### Important Notes

- Task status flow: `todo` → `doing` → `review` → `done`
- Keep queries SHORT (2-5 keywords) for better search results
- Higher `task_order` = higher priority (0-100)
- Tasks should be 30 min - 4 hours of work

---

**Version:** 1.0
**Last Updated:** December 14, 2024
**Maintained By:** AI-Nutrition Team
