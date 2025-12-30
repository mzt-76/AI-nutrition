# Adjustment Bounds Optimization Guide

**Status:** MVP - Baseline established, ready for Phase 2 optimization
**Last Updated:** December 30, 2024
**Owner:** AI Nutrition Team

---

## Overview

The adjustment bounds (±300 kcal, ±30g protein, ±50g carbs, ±15g fat) are **design choices for MVP**, not direct scientific recommendations. This document tracks optimization opportunities for Phase 2+.

---

## Current MVP Bounds

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| **MAX_CALORIE_ADJUSTMENT** | ±300 kcal | ~10% of daily intake; avoids metabolic shock |
| **MAX_PROTEIN_ADJUSTMENT_G** | ±30g | ~0.35g/kg; addresses hunger without overloading |
| **MAX_CARB_ADJUSTMENT_G** | ±50g | ~200 kcal; allows pre-workout timing tuning |
| **MAX_FAT_ADJUSTMENT_G** | ±15g | ~135 kcal; enough for cravings, not too much |

---

## Scientific Basis vs. Direct Recommendation

### What the Literature Says

| Source | Finding | Application to Bounds |
|--------|---------|----------------------|
| **Fothergill et al. (2016)** | Metabolic adaptation occurs in response to large deficits | ±300 kcal is conservative enough to delay adaptation |
| **Helms et al. (2014)** | Slower weight loss (-0.3 to -0.7 kg/week) preserves muscle mass | ±300 kcal adjustments maintain slower weight change rate |
| **ISSN (2017)** | Protein 1.6-3.1 g/kg; individual macro response varies widely | ±30g protein allows tuning within ISSN range |

### What the Literature Does NOT Say

- ❌ "Use exactly ±300 kcal adjustments" (not explicitly recommended)
- ❌ "Protein adjustments should be ±30g" (not specified)
- ❌ "Carb bounds are ±50g" (not mentioned)

**Conclusion:** Bounds are inferred from principles, not directly prescribed.

---

## Phase 2 Optimization Roadmap

### Option 1: Goal-Specific Bounds (Recommended)

**Rationale:** Different goals have different adherence requirements

```python
# Proposed Phase 2 Implementation
ADJUSTMENT_BOUNDS_BY_GOAL = {
    "weight_loss": {
        "calories": 350,  # More aggressive for loss (Helms: -0.7 kg/week is safe)
        "protein": 30,    # Same (satiety for hunger control)
        "carbs": 50,      # Same
        "fat": 15         # Same
    },
    "muscle_gain": {
        "calories": 200,  # More conservative (needs precision, Helms et al. 2014)
        "protein": 40,    # Higher (protein synthesis focus)
        "carbs": 40,      # Slightly lower (more calculated)
        "fat": 10         # Lower (precision needed)
    },
    "maintenance": {
        "calories": 100,  # Very conservative (minimal change needed)
        "protein": 20,    # Small adjustments only
        "carbs": 30,      # Small adjustments only
        "fat": 8          # Very small
    }
}
```

**Scientific Support:**
- Helms et al. (2014): Muscle gain is more sensitive to deficit/surplus precision
- ISSN (2017): Individual variability is high; smaller initial adjustments allow tuning

**Implementation Steps:**
1. Fetch user's goal from profile
2. Look up bounds from `ADJUSTMENT_BOUNDS_BY_GOAL[goal]`
3. Apply bounds instead of fixed 300 kcal

**Testing Plan:**
- Week 1-4: Monitor if users hit the bounds frequently
- Week 4: Compare actual weight change vs. target by goal
  - If weight_loss users losing >1.0 kg/week → reduce to 300 kcal
  - If muscle_gain users not gaining → increase to 250 kcal
  - If maintenance users stable → bounds are good

---

### Option 2: Confidence-Dependent Bounds (Advanced)

**Rationale:** Early weeks lack data; later weeks have confirmed patterns

```python
# Proposed Phase 3 Implementation
def get_adjustment_bounds(confidence_level: float) -> dict:
    """Return bounds based on recommendation confidence."""

    if confidence_level < 0.5:
        # Week 1: Very low confidence, tiny adjustments
        return {"calories": 100, "protein": 15, "carbs": 25, "fat": 5}

    elif confidence_level < 0.75:
        # Week 2-3: Moderate confidence, small adjustments
        return {"calories": 200, "protein": 25, "carbs": 40, "fat": 10}

    else:
        # Week 4+: High confidence, standard adjustments
        return {"calories": 300, "protein": 30, "carbs": 50, "fat": 15}
```

**Scientific Support:**
- Fothergill et al. (2016): Metabolic adaptation is gradual; allow time before large changes
- Behavioral science: Habit formation improves confidence in adjustments

**Benefits:**
- Week 1: Cautious → user doesn't experience shock
- Week 4+: More responsive → user sees faster progress once patterns confirmed

---

### Option 3: Hybrid Approach (Best)

Combine Option 1 + Option 2 for maximum personalization:

```python
def get_adjustment_bounds(goal: str, confidence_level: float) -> dict:
    """Return bounds based on goal AND confidence."""

    # Base bounds by goal (Option 1)
    goal_bounds = ADJUSTMENT_BOUNDS_BY_GOAL[goal]

    # Apply confidence multiplier (Option 2)
    if confidence_level < 0.5:
        multiplier = 0.3
    elif confidence_level < 0.75:
        multiplier = 0.6
    else:
        multiplier = 1.0

    return {
        "calories": int(goal_bounds["calories"] * multiplier),
        "protein": int(goal_bounds["protein"] * multiplier),
        "carbs": int(goal_bounds["carbs"] * multiplier),
        "fat": int(goal_bounds["fat"] * multiplier),
    }
```

**Example Usage:**
```
User: muscle_gain, week 1 (confidence=0.5)
  Base bounds: calories=200, protein=40
  Multiplier: 0.6 (confidence < 0.75)
  Result: calories=120, protein=24 ✅ (very conservative)

User: muscle_gain, week 4 (confidence=0.85)
  Base bounds: calories=200, protein=40
  Multiplier: 1.0 (confidence >= 0.75)
  Result: calories=200, protein=40 ✅ (full bounds)
```

---

## Optimization Metrics (Tracking)

After MVP, track these metrics to inform Phase 2 changes:

### Metric 1: Bound Saturation
**Question:** Are users hitting the 300 kcal cap frequently?

```python
# Track in weekly_feedback table
cap_hit_count = count(rows where abs(adjustment_suggested) >= 290)
cap_hit_rate = cap_hit_count / total_weeks

# Interpretation:
if cap_hit_rate > 0.3:  # >30% hitting cap
    "Consider increasing to 350 kcal"
elif cap_hit_rate < 0.05:  # <5% hitting cap
    "Could decrease to 250 kcal (more conservative)"
```

### Metric 2: Weight Change Rate

**Question:** Are users hitting target weight change by goal?

```python
# For weight_loss: target -0.3 to -0.7 kg/week
avg_loss_rate = mean([abs(w["weight_change_kg"]) for w in past_8_weeks])

# Interpretation:
if avg_loss_rate > 1.0:
    "Deficit too aggressive → reduce MAX_CALORIE_ADJUSTMENT to 250"
elif avg_loss_rate < 0.2:
    "Deficit too conservative → increase to 350"

# For muscle_gain: target +0.2 to +0.5 kg/week
# Same logic
```

### Metric 3: Adherence by Adjustment Size

**Question:** Do smaller/larger adjustments lead to better adherence?

```python
# Compare adherence by adjustment size
small_adjustments = [w for w in weeks if abs(adjustment) < 150]
large_adjustments = [w for w in weeks if abs(adjustment) >= 250]

avg_adherence_small = mean([w["adherence_percent"] for w in small_adjustments])
avg_adherence_large = mean([w["adherence_percent"] for w in large_adjustments])

# Interpretation:
if avg_adherence_large > avg_adherence_small:
    "Users adhere better to larger adjustments → increase bounds"
elif avg_adherence_small > avg_adherence_large:
    "Users adhere better to smaller adjustments → decrease bounds"
```

### Metric 4: Red Flags by Goal

**Question:** Does the goal affect red flag frequency?

```python
# Count red flags by goal
red_flags_by_goal = {
    "weight_loss": count(...),
    "muscle_gain": count(...),
    "maintenance": count(...)
}

# Interpretation:
if red_flags[muscle_gain] > 0.5:  # >50% of muscle gain weeks flag
    "Bounds may be too aggressive for muscle gain → reduce to 200 kcal"
```

---

## Decision Flowchart (Phase 2)

```
After 4 weeks of real user data:

1. Analyze weight change rate
   ├─ If >1.0 kg/week → "TOO FAST" → Reduce to 250 kcal
   ├─ If <0.2 kg/week → "TOO SLOW" → Increase to 350 kcal
   └─ If 0.3-0.7 kg/week → "OPTIMAL" → Keep at 300 kcal

2. Analyze adherence rate
   ├─ If <70% adherence → "STRUGGLING" → Check if adjustments too large
   │   └─ Consider 250 kcal or confidence-dependent scaling
   ├─ If 70-85% adherence → "GOOD" → Current bounds OK
   └─ If >85% adherence → "EXCELLENT" → Can increase to 350 kcal safely

3. Check if hitting cap
   ├─ If >30% weeks hit cap → "CONSERVATIVE" → Increase to 350 kcal
   ├─ If 5-30% weeks hit cap → "BALANCED" → Current bounds OK
   └─ If <5% weeks hit cap → "LOOSE" → Could decrease to 250 kcal

4. Implement optimization
   ├─ If weight loss goals need changes → Modify MUSCLE_GAIN_TARGET
   ├─ If muscle gain goals need changes → Modify WEIGHT_LOSS_TARGET
   └─ If all need changes → Implement goal-specific bounds (Option 1)
```

---

## Timeline & Ownership

| Phase | When | What | Owner |
|-------|------|------|-------|
| **MVP** | Week 0-4 | Baseline: ±300 kcal bounds | AI-Nutrition Team |
| **Phase 2** | Week 4-8 | Analyze metrics, implement goal-specific bounds | TBD |
| **Phase 3** | Week 8-12 | Implement confidence-dependent bounds | TBD |
| **Production** | Week 12+ | Continuous optimization based on aggregate user data | TBD |

---

## How to Change Later

### To Modify MAX_CALORIE_ADJUSTMENT:

**File:** `nutrition/adjustments.py` (line 100)
```python
# Change this:
MAX_CALORIE_ADJUSTMENT = 300

# To this:
MAX_CALORIE_ADJUSTMENT = 350  # or any value
```

### To Implement Goal-Specific Bounds:

**File:** `nutrition/adjustments.py` (add after line 104)
```python
# Add dictionary
ADJUSTMENT_BOUNDS_BY_GOAL = {
    "weight_loss": {"calories": 350, ...},
    "muscle_gain": {"calories": 200, ...},
    ...
}

# Modify generate_calorie_adjustment() function to use:
goal = profile["goal"]
max_adjustment = ADJUSTMENT_BOUNDS_BY_GOAL[goal]["calories"]
```

### To Implement Confidence-Dependent Bounds:

**File:** `nutrition/adjustments.py` (add helper function)
```python
def get_adjustment_bounds(confidence_level: float) -> dict:
    """Return bounds based on confidence."""
    if confidence_level < 0.5:
        return {"calories": 100, ...}
    # ... etc
```

**File:** `tools.py` (in calculate_weekly_adjustments_tool)
```python
bounds = get_adjustment_bounds(confidence_level)
adjustment_kcal = max(-bounds["calories"], min(bounds["calories"], adjustment_kcal))
```

---

## Success Criteria (Phase 2)

- [ ] 4 weeks of real user data collected
- [ ] All 4 metrics (saturation, weight change, adherence, red flags) analyzed
- [ ] Decision made: keep MVP bounds vs. optimize
- [ ] If optimizing: implement Option 1 (goal-specific) or Option 3 (hybrid)
- [ ] New bounds tested with next 2 weeks of user data
- [ ] Weight change rate matches goal targets (±0.05 kg/week tolerance)
- [ ] Adherence >80% sustained
- [ ] Red flag frequency <20% of weeks
- [ ] Documentation updated with new rationale

---

## Related Files

- `nutrition/adjustments.py` - Main implementation (lines 55-103 contain rationale)
- `CLAUDE.md` - Section 8.5: Weekly Adjustment System
- `tools.py` - `calculate_weekly_adjustments_tool` function
- `tests/test_adjustments.py` - Unit tests for bounds enforcement

---

**Version:** 1.0
**Status:** MVP - Ready for Phase 2 optimization
**Next Review:** After 4 weeks of real user data
