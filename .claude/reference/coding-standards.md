# Coding Standards

**Purpose:** Naming conventions, logging patterns, and testing guidelines for the AI Nutrition Assistant project.

---

## Code Style

### Naming Conventions

**Python:**
```python
# Functions: snake_case                # Classes: PascalCase
async def calculate_nutritional_needs(...) -> dict:
    pass

@dataclass
class AgentDeps:
    supabase: SupabaseAsyncClient  # from supabase._async.client

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

## Logging

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

## Testing

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
