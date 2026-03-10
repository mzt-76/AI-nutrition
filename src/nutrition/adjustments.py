"""Weekly adjustment analysis and recommendation generation.

This module synthesizes weekly feedback observations, detects patterns in user
metabolic response and adherence, and generates personalized macro/calorie
adjustments based on scientific principles and individual metabolic variability.

References:
    Adaptive Thermogenesis: Fothergill et al. (2016)
    Helms et al. (2014): Body composition changes in resistance training
    ISSN Position Stand (2017): Macronutrient recommendations

IMPORTANT - Adjustment Bounds Design Philosophy (MVP):
    These bounds (MAX_CALORIE_ADJUSTMENT, MAX_PROTEIN_ADJUSTMENT_G, etc.) are
    DESIGN CHOICES, not direct recommendations from scientific literature.

    The bounds were chosen based on principles FROM those sources but are subject
    to optimization in future versions. See ADJUSTMENT_BOUNDS_RATIONALE below.
"""

import logging
from typing import Literal

logger = logging.getLogger(__name__)

# Weight change targets by goal (kg/week)
WEIGHT_LOSS_TARGET_RANGE = (-0.7, -0.3)  # Conservative: -0.3 to -0.7 kg/week
WEIGHT_LOSS_TARGET_OPTIMAL = -0.5

MUSCLE_GAIN_TARGET_RANGE = (0.2, 0.5)  # Slow, lean gain: +0.2 to +0.5 kg/week
MUSCLE_GAIN_TARGET_OPTIMAL = 0.3

MAINTENANCE_TARGET_RANGE = (-0.5, 0.5)
MAINTENANCE_TARGET_OPTIMAL = 0.0

PERFORMANCE_TARGET_RANGE = (-0.3, 0.3)  # Minimal change, focus on strength
PERFORMANCE_TARGET_OPTIMAL = 0.0

# Red flag thresholds
RED_FLAG_RAPID_LOSS_THRESHOLD = 1.0  # kg/week - signals deficit too aggressive
RED_FLAG_EXTREME_HUNGER_ADHERENCE = 40  # <40% adherence + high hunger = unsustainable
RED_FLAG_ENERGY_CRASH_WEEKS = 2  # Low energy for 2+ consecutive weeks
RED_FLAG_MOOD_SHIFT_KEYWORDS = [
    "depressed",
    "depression",
    "mood_swing",
    "anxious",
    "sad",
]

# Metabolic learning thresholds
MIN_WEEKS_FOR_METABOLIC_CONFIDENCE = 4
MIN_CONSISTENCY_FOR_PATTERN = 3  # Pattern must repeat 3+ times to be reliable

# Macro adjustment bounds (safety constraints)
#
# ADJUSTMENT_BOUNDS_RATIONALE:
# ============================
# These bounds are DESIGN CHOICES optimized for MVP (single-user, 4-week learning phase).
# They are NOT directly from scientific literature but informed by these principles:
#
# 1. MAX_CALORIE_ADJUSTMENT = 300 kcal
#    Rationale:
#    - ~10% of typical 3000 kcal daily intake → feels sustainable, not shocking
#    - Avoids triggering strong metabolic adaptation (Fothergill et al. 2016)
#    - Allows habit formation (behavioral change literature: 2-4 weeks to adapt)
#    - Enables pattern detection over 4 weeks (±300 kcal = slower detection than ±500)
#    - Current user (individual) can sustain small changes; larger changes risk dropout
#
#    Potential future optimization (Phase 2):
#    - Make goal-specific: weight_loss=±350, muscle_gain=±200, maintenance=±100
#    - Make confidence-dependent: week1=±100, week4+=±300
#    - Basis: Helms et al. (2014) shows muscle gain goals need tighter adherence
#
# 2. MAX_PROTEIN_ADJUSTMENT_G = 30
#    Rationale:
#    - ISSN (2017) recommends 1.6-3.1g/kg; 30g = ~0.35g/kg for 87kg user
#    - Small enough to avoid digestive stress, large enough to address hunger
#    - Satiety effect of protein is dose-dependent; 20-30g increments are validated
#
# 3. MAX_CARB_ADJUSTMENT_G = 50
#    Rationale:
#    - 50g carbs = ~200 kcal; moderate carb shift for energy/workout timing
#    - Allows pre-workout carb timing without overloading
#    - Individual carb sensitivity varies (Helms et al. 2014); 50g allows tuning
#
# 4. MAX_FAT_ADJUSTMENT_G = 15
#    Rationale:
#    - Fat is most satiating macro (9 kcal/g); small adjustments have large effect
#    - 15g = 135 kcal; enough to address cravings, not enough to dominate adjustment
#    - Prevents "fat loading" which can impair carb absorption
#
# NEXT STEPS FOR OPTIMIZATION:
# 1. After 4 weeks real user data: Analyze if 300 kcal limit is appropriate
# 2. Check: Do users hit the 300 kcal cap frequently? If yes, consider increasing
# 3. Check: Do users struggle with small adjustments? If yes, consider increasing
# 4. Check: Do users lose weight too fast? If yes, decrease to 250 kcal
# 5. Implement goal-specific bounds based on findings (see Phase 2 above)
#
MAX_CALORIE_ADJUSTMENT = 300  # Don't suggest more than ±300 kcal at once
MAX_PROTEIN_ADJUSTMENT_G = 30  # Don't suggest >±30g protein at once
MAX_CARB_ADJUSTMENT_G = 50  # Don't suggest >±50g carbs at once
MAX_FAT_ADJUSTMENT_G = 15  # Don't suggest >±15g fat at once

# Confidence levels
CONFIDENCE_INSUFFICIENT_DATA = 0.3
CONFIDENCE_SINGLE_DATA_POINT = 0.5
CONFIDENCE_PATTERN_DETECTED = 0.75
CONFIDENCE_CONFIRMED_PATTERN = 0.9


def analyze_weight_trend(
    weight_start_kg: float,
    weight_end_kg: float,
    goal: Literal["muscle_gain", "weight_loss", "maintenance", "performance"],
    weeks_on_plan: int = 1,
) -> dict:
    """
    Analyze weight change against goal-specific targets.

    Compares actual weight change to goal-specific optimal ranges and determines
    if the rate is optimal, too fast, or too slow. Returns analysis with
    assessment and confidence level.

    Args:
        weight_start_kg: Weight at start of week (kg)
        weight_end_kg: Weight at end of week (kg)
        goal: Primary goal (muscle_gain, weight_loss, maintenance, performance)
        weeks_on_plan: How many weeks user has been following plan

    Returns:
        Dict with trend analysis:
        {
            "change_kg": -0.6,
            "change_percent": -0.69,
            "goal": "muscle_gain",
            "trend": "stable",  # stable, too_fast, too_slow, optimal
            "assessment": "Perfect weight loss for muscle gain phase",
            "is_optimal": true,
            "confidence": 0.9,
            "rationale": [reasons...]
        }

    Example:
        >>> result = analyze_weight_trend(87.0, 86.4, "muscle_gain", 2)
        >>> print(result["trend"])
        "stable"

    References:
        Helms et al. (2014): Body composition changes in resistance training
        ISSN Position Stand (2017): Protein for muscle gain during hypertrophy
    """
    weight_change_kg = weight_end_kg - weight_start_kg
    if weight_start_kg <= 0:
        weight_change_percent = 0.0
    else:
        weight_change_percent = (weight_change_kg / weight_start_kg) * 100

    # Select target range based on goal
    goal_targets = {
        "weight_loss": {
            "target_range": WEIGHT_LOSS_TARGET_RANGE,
            "optimal": WEIGHT_LOSS_TARGET_OPTIMAL,
        },
        "muscle_gain": {
            "target_range": MUSCLE_GAIN_TARGET_RANGE,
            "optimal": MUSCLE_GAIN_TARGET_OPTIMAL,
        },
        "maintenance": {
            "target_range": MAINTENANCE_TARGET_RANGE,
            "optimal": MAINTENANCE_TARGET_OPTIMAL,
        },
        "performance": {
            "target_range": PERFORMANCE_TARGET_RANGE,
            "optimal": PERFORMANCE_TARGET_OPTIMAL,
        },
    }

    target_info = goal_targets.get(goal, goal_targets["maintenance"])
    target_range = target_info["target_range"]
    optimal = target_info["optimal"]

    # Determine trend
    # Note: For weight_loss, min_target is -0.7 and max_target is -0.3
    # So weight_change_kg between -0.7 and -0.3 is good
    min_target, max_target = target_range

    # Determine if goal expects positive or negative weight change
    # muscle_gain: expects positive (gaining weight)
    # weight_loss: expects negative (losing weight)
    # maintenance/performance: expects near zero
    goal_expects_gain = goal == "muscle_gain"
    goal_expects_loss = goal == "weight_loss"

    # Special case: near-zero weight change is "stable" regardless of goal
    # This handles normal weekly fluctuations (measurement error, hydration, etc.)
    if abs(weight_change_kg) < 0.1:
        trend = "stable"
        is_optimal = False
        assessment = f"No significant change this week ({weight_change_kg:+.1f}kg). This is normal variance - focus on the trend over 4 weeks."
        confidence = CONFIDENCE_PATTERN_DETECTED
    elif min_target <= weight_change_kg <= max_target:
        trend = "stable"
        is_optimal = abs(weight_change_kg - optimal) < 0.1
        if is_optimal:
            trend = "optimal"
            assessment = f"Perfect! Your {weight_change_kg:.1f}kg change matches optimal {goal} target of {optimal}kg/week"
            confidence = CONFIDENCE_CONFIRMED_PATTERN
        else:
            assessment = f"Good! Your change ({weight_change_kg:.1f}kg) is within target range ({min_target}–{max_target}kg/week) for {goal}"
            confidence = CONFIDENCE_PATTERN_DETECTED
    elif weight_change_kg < min_target:
        # Below min_target: meaning depends on goal direction
        if goal_expects_gain:
            # For muscle_gain: below min (0.2) means not gaining enough or losing
            trend = "too_slow"
            is_optimal = False
            if weight_change_kg < 0:
                assessment = f"You're losing weight ({weight_change_kg:+.1f}kg) instead of gaining. Increase calories to support muscle growth. Target: {optimal:+.1f}kg/week"
            else:
                assessment = f"Weight gain too slow ({weight_change_kg:+.1f}kg vs {optimal:+.1f}kg target). Consider increasing calories slightly."
            confidence = CONFIDENCE_CONFIRMED_PATTERN
        else:
            # For weight_loss: below min (-0.7) means losing too fast
            trend = "too_fast"
            is_optimal = False
            assessment = f"Weight loss too fast ({weight_change_kg:.1f}kg). Risk of muscle loss and metabolic slowdown. Target: {optimal}kg/week"
            confidence = CONFIDENCE_CONFIRMED_PATTERN
    else:  # weight_change_kg > max_target
        # Above max_target: meaning depends on goal direction
        if goal_expects_loss:
            # For weight_loss: above max (-0.3) means not losing enough or gaining
            trend = "too_slow"
            is_optimal = False
            if weight_change_kg > 0:
                assessment = f"You're gaining weight ({weight_change_kg:+.1f}kg) instead of losing. Review calorie intake and adherence."
            else:
                assessment = f"Weight loss slower than optimal ({weight_change_kg:.1f}kg vs {optimal}kg target). Increase deficit slightly."
            confidence = CONFIDENCE_CONFIRMED_PATTERN
        else:
            # For muscle_gain: above max (0.5) means gaining too fast (risk of fat)
            trend = "too_fast"
            is_optimal = False
            assessment = f"Weight gain too fast ({weight_change_kg:+.1f}kg). May indicate excess fat gain. Target: {optimal:+.1f}kg/week"
            confidence = CONFIDENCE_CONFIRMED_PATTERN

    rationale = [
        f"Week {weeks_on_plan}: {weight_change_kg:+.1f}kg change",
        f"Target for {goal}: {min_target}–{max_target}kg/week",
        assessment,
    ]

    return {
        "change_kg": round(weight_change_kg, 2),
        "change_percent": round(weight_change_percent, 2),
        "goal": goal,
        "trend": trend,
        "assessment": assessment,
        "is_optimal": is_optimal,
        "confidence": confidence,
        "rationale": rationale,
    }


def detect_metabolic_adaptation(
    past_weeks: list[dict],
    observed_tdee: float | None,
    calculated_tdee: float | None,
) -> dict:
    """
    Detect if user's metabolism is adapting (actual expenditure < calculated).

    Compares actual weight changes over past weeks to calculated TDEE. If actual
    weight loss is consistently slower than expected, infers lower metabolic rate.

    Args:
        past_weeks: Previous weekly_feedback records (dicts with weight_change_kg, adherence_percent)
        observed_tdee: Previously calculated actual TDEE (None on first detection)
        calculated_tdee: TDEE from Mifflin-St Jeor formula (can be None if profile incomplete)

    Returns:
        Dict with adaptation analysis:
        {
            "detected": boolean,
            "confidence": 0.0-1.0,
            "observed_tdee": 2650,
            "adaptation_factor": 0.92,
            "rationale": ["explanations..."],
            "recommendation": "Increase deficit by 100 kcal to account for adaptation"
        }

    References:
        Adaptive Thermogenesis: Fothergill et al. (2016)
        Metabolic Adaptation review: Müller et al. (2010)
    """
    if len(past_weeks) < MIN_WEEKS_FOR_METABOLIC_CONFIDENCE:
        return {
            "detected": False,
            "confidence": CONFIDENCE_INSUFFICIENT_DATA,
            "observed_tdee": None,
            "adaptation_factor": None,
            "rationale": [
                f"Need {MIN_WEEKS_FOR_METABOLIC_CONFIDENCE} weeks of data to detect metabolic adaptation; have {len(past_weeks)}"
            ],
            "recommendation": "Continue tracking; metabolic confidence builds week by week",
        }

    # Validate calculated_tdee is available
    if calculated_tdee is None or calculated_tdee <= 0:
        return {
            "detected": False,
            "confidence": CONFIDENCE_INSUFFICIENT_DATA,
            "observed_tdee": None,
            "adaptation_factor": None,
            "rationale": [
                "Cannot detect metabolic adaptation without baseline TDEE calculation",
                "Profile data (age, weight, height, activity) required for TDEE calculation",
            ],
            "recommendation": "Complete profile data to enable metabolic adaptation detection",
        }

    # Calculate average adherence and weight change
    avg_adherence = sum(w.get("adherence_percent", 50) for w in past_weeks) / len(
        past_weeks
    )
    avg_weight_change = sum(w.get("weight_change_kg", 0) for w in past_weeks) / len(
        past_weeks
    )

    # Rough TDEE inference: if user is 85% adherent and losing X kg/week,
    # actual deficit = weight_change_kg * 7700 kcal/kg / week
    # (rough; ignores protein synthesis, water retention, etc.)
    if avg_adherence > 0:
        inferred_deficit = (
            abs(avg_weight_change) * 7700 / 7
        )  # kcal/day from weight loss
        inferred_tdee = calculated_tdee - inferred_deficit

        # Account for adherence being <100%
        if avg_adherence < 100:
            inferred_tdee = inferred_tdee * (100 / avg_adherence)

        adaptation_factor = (
            inferred_tdee / calculated_tdee if calculated_tdee > 0 else 1.0
        )

        # Threshold: >5% difference suggests adaptation
        detected = adaptation_factor < 0.95
        confidence = (
            CONFIDENCE_PATTERN_DETECTED if detected else CONFIDENCE_SINGLE_DATA_POINT
        )

        recommendation = (
            f"Metabolic adaptation detected. Increase deficit by ~{int((1 - adaptation_factor) * calculated_tdee)} kcal to maintain progress"
            if detected
            else "No metabolic adaptation detected; TDEE appears stable"
        )
    else:
        inferred_tdee = calculated_tdee
        adaptation_factor = 1.0
        detected = False
        confidence = CONFIDENCE_SINGLE_DATA_POINT
        recommendation = "Monitor adherence to enable metabolic detection"

    return {
        "detected": detected,
        "confidence": confidence,
        "observed_tdee": round(inferred_tdee, 0) if inferred_tdee else None,
        "adaptation_factor": round(adaptation_factor, 2),
        "rationale": [
            f"Calculated TDEE: {calculated_tdee} kcal/day",
            f"Observed TDEE (inferred): {inferred_tdee:.0f} kcal/day"
            if inferred_tdee
            else "",
            f"Adaptation factor: {adaptation_factor:.2%}" if adaptation_factor else "",
        ],
        "recommendation": recommendation,
    }


def detect_adherence_patterns(
    past_weeks: list[dict],
) -> dict:
    """
    Identify recurring adherence obstacles and positive triggers.

    Looks for patterns: low adherence on specific days, correlations with hunger/energy,
    stress periods, specific meal types that work better.

    Args:
        past_weeks: List of previous weekly_feedback records

    Returns:
        Dict with adherence analysis:
        {
            "positive_triggers": ["pre-workout_carbs", "easy_meals_on_fridays"],
            "negative_triggers": ["low_carb_fridays", "stressful_work_weeks"],
            "pattern_strength": 0.8,
            "days_most_difficult": ["friday", "sunday"],
            "recommendation": "Pre-plan Friday meals to reduce adherence friction"
        }
    """
    if not past_weeks:
        return {
            "positive_triggers": [],
            "negative_triggers": [],
            "pattern_strength": 0.0,
            "days_most_difficult": [],
            "recommendation": "Collect more data to identify adherence patterns",
        }

    # Find high and low adherence weeks
    high_adherence_weeks = [
        w for w in past_weeks if w.get("adherence_percent", 0) >= 80
    ]
    low_adherence_weeks = [w for w in past_weeks if w.get("adherence_percent", 0) < 50]

    positive_triggers = []
    negative_triggers = []

    # Look for energy/hunger patterns in high adherence weeks
    if high_adherence_weeks:
        avg_energy_high = sum(
            1 for w in high_adherence_weeks if w.get("energy_level") == "high"
        ) / len(high_adherence_weeks)
        avg_hunger_low = sum(
            1 for w in high_adherence_weeks if w.get("hunger_level") == "low"
        ) / len(high_adherence_weeks)

        if avg_energy_high > 0.5:
            positive_triggers.append("high_energy_weeks")
        if avg_hunger_low > 0.5:
            positive_triggers.append("low_hunger_weeks")

    # Look for obstacles in low adherence weeks
    if low_adherence_weeks:
        avg_hunger_high = sum(
            1 for w in low_adherence_weeks if w.get("hunger_level") == "high"
        ) / len(low_adherence_weeks)
        avg_energy_low = sum(
            1 for w in low_adherence_weeks if w.get("energy_level") == "low"
        ) / len(low_adherence_weeks)

        if avg_hunger_high > 0.5:
            negative_triggers.append("high_hunger")
        if avg_energy_low > 0.5:
            negative_triggers.append("low_energy")

    # Calculate pattern strength
    pattern_strength = (
        len(positive_triggers) + len(negative_triggers)
    ) / 6.0  # Max 6 patterns
    pattern_strength = min(pattern_strength, 1.0)

    recommendation = ""
    if negative_triggers and high_adherence_weeks:
        avg_high_adherence = sum(
            w.get("adherence_percent", 0) for w in high_adherence_weeks
        ) / len(high_adherence_weeks)
        recommendation = f"You achieve {avg_high_adherence:.0f}% adherence when {', '.join(positive_triggers) if positive_triggers else 'feeling good'}. Avoid weeks with {', '.join(negative_triggers) if negative_triggers else 'low energy/high hunger'}."

    return {
        "positive_triggers": positive_triggers,
        "negative_triggers": negative_triggers,
        "pattern_strength": min(pattern_strength, 1.0),
        "days_most_difficult": [],  # Would require daily-level data
        "recommendation": recommendation or "Continue building adherence data",
    }


def generate_calorie_adjustment(
    weight_change_kg: float,
    goal: str,
    adherence_percent: int,
    weeks_on_plan: int,
) -> dict:
    """
    Calculate suggested calorie adjustment based on weight trend and adherence.

    Uses rule-based approach: if weight too fast → reduce deficit, if too slow →
    increase deficit. Applies safety bounds (±300 kcal max per week).

    Args:
        weight_change_kg: Actual weight change this week (kg)
        goal: User's primary goal (muscle_gain, weight_loss, maintenance)
        adherence_percent: Percentage of plan followed (0-100)
        weeks_on_plan: How many weeks user has been on plan

    Returns:
        Dict with calorie adjustment:
        {
            "adjustment_kcal": 50,
            "reasoning": ["Weight loss 20% faster than target..."],
            "conservative_adjustment": 25,
            "aggressive_adjustment": 100,
        }
    """
    # Rule-based adjustment
    adjustment_kcal = 0
    reasoning = []

    if goal == "weight_loss":
        if weight_change_kg > -0.3:
            # Too slow; increase deficit
            adjustment_kcal = -50  # Reduce calories (increase deficit)
            reasoning.append(
                f"Weight loss {weight_change_kg:.1f}kg is slower than target -0.5kg/week"
            )
            reasoning.append("Increasing deficit by ~50 kcal/day")
        elif weight_change_kg < -1.0:
            # Too fast; reduce deficit
            adjustment_kcal = 100  # Add calories (reduce deficit)
            reasoning.append(
                f"Weight loss {weight_change_kg:.1f}kg exceeds safe rate; risk of muscle loss"
            )
            reasoning.append("Reducing deficit by ~100 kcal/day to preserve muscle")

    elif goal == "muscle_gain":
        if weight_change_kg < 0:
            # Losing weight instead of gaining
            adjustment_kcal = 150
            reasoning.append("Losing weight instead of gaining muscle")
            reasoning.append("Adding ~150 kcal/day to support muscle gain")
        elif weight_change_kg > 0.7:
            # Gaining too fast (too much fat)
            adjustment_kcal = -50
            reasoning.append(
                f"Weight gain {weight_change_kg:.1f}kg is too fast; may indicate excess fat"
            )
            reasoning.append("Reducing surplus by ~50 kcal/day")

    # Clamp adjustment to safety limits
    adjustment_kcal = max(
        -MAX_CALORIE_ADJUSTMENT,
        min(MAX_CALORIE_ADJUSTMENT, adjustment_kcal),
    )

    # Conservative and aggressive variants
    conservative = adjustment_kcal * 0.5
    aggressive = adjustment_kcal * 1.5
    conservative = max(
        -MAX_CALORIE_ADJUSTMENT,
        min(MAX_CALORIE_ADJUSTMENT, conservative),
    )
    aggressive = max(
        -MAX_CALORIE_ADJUSTMENT,
        min(MAX_CALORIE_ADJUSTMENT, aggressive),
    )

    if not reasoning:
        reasoning.append(f"Weight change {weight_change_kg:+.1f}kg on track for {goal}")
        reasoning.append("No calorie adjustment needed")

    return {
        "adjustment_kcal": int(adjustment_kcal),
        "reasoning": reasoning,
        "conservative_adjustment": int(conservative),
        "aggressive_adjustment": int(aggressive),
    }


def generate_macro_adjustments(
    hunger_level: str,
    energy_level: str,
    cravings: list[str],
    current_protein_g: int,
    current_carbs_g: int,
    current_fat_g: int,
    learned_sensitivity: dict | None = None,
) -> dict:
    """
    Calculate macro adjustments based on subjective signals and learned sensitivity.

    Increases protein for hunger, carbs for low energy, adjusts based on learned
    individual sensitivity patterns.

    Args:
        hunger_level: Reported hunger (low, medium, high)
        energy_level: Reported energy (low, medium, high)
        cravings: List of specific cravings (e.g., ["sweets", "carbs"])
        current_protein_g: Current protein target (g/day)
        current_carbs_g: Current carbs target (g/day)
        current_fat_g: Current fat target (g/day)
        learned_sensitivity: Optional dict with learned macro sensitivity

    Returns:
        Dict with macro adjustments:
        {
            "protein_g": 20,
            "carbs_g": 30,
            "fat_g": 0,
            "adjustments_rationale": {
                "protein": "High hunger reported; +20g protein improves satiety",
                "carbs": "Low energy Friday; +30g carbs pre-workout for your type"
            }
        }
    """
    if learned_sensitivity is None:
        learned_sensitivity = {}

    protein_adj = 0
    carbs_adj = 0
    fat_adj = 0
    rationale = {}

    # Hunger management: increase protein
    if hunger_level == "high":
        protein_adj += 20
        rationale[
            "protein"
        ] = "High hunger: +20g protein improves satiety signaling (ISSN)"
    elif hunger_level == "low":
        protein_adj -= 10
        rationale["protein"] = "Low hunger: -10g protein is sufficient for satiety"

    # Energy management: increase carbs for low energy
    if energy_level == "low":
        carbs_adj += 30
        rationale[
            "carbs"
        ] = "Low energy: +30g carbs support ATP production, especially pre-workout"
    elif energy_level == "high":
        carbs_adj -= 10
        rationale["carbs"] = "High energy: -10g carbs, energy demand met"

    # Learned sensitivities
    carb_sensitivity = learned_sensitivity.get("carb_sensitivity")
    if carb_sensitivity == "high" and energy_level == "low":
        carbs_adj += 15
        rationale["carbs"] = (
            rationale.get("carbs", "") + " (You respond well to higher carbs)"
        )
    elif carb_sensitivity == "low" and carbs_adj > 0:
        carbs_adj = max(0, carbs_adj - 10)
        rationale["carbs"] = (
            rationale.get("carbs", "") + " (You tolerate lower carbs well)"
        )

    # Cravings: small adjustments
    if "sweets" in cravings or "sugar" in cravings:
        carbs_adj += 10
        rationale["carbs"] = rationale.get("carbs", "") + " (Cravings suggest increase)"
    if "fat" in cravings or "nuts" in cravings:
        fat_adj += 5
        rationale["fat"] = "Cravings suggest small fat increase (+5g)"

    # Apply safety bounds
    protein_adj = max(
        -MAX_PROTEIN_ADJUSTMENT_G,
        min(MAX_PROTEIN_ADJUSTMENT_G, protein_adj),
    )
    carbs_adj = max(
        -MAX_CARB_ADJUSTMENT_G,
        min(MAX_CARB_ADJUSTMENT_G, carbs_adj),
    )
    fat_adj = max(-MAX_FAT_ADJUSTMENT_G, min(MAX_FAT_ADJUSTMENT_G, fat_adj))

    # Set defaults for missing rationale
    if "protein" not in rationale:
        rationale["protein"] = "Protein: no adjustment needed"
    if "carbs" not in rationale:
        rationale["carbs"] = "Carbs: no adjustment needed"
    if "fat" not in rationale:
        rationale["fat"] = "Fat: no adjustment needed"

    return {
        "protein_g": int(protein_adj),
        "carbs_g": int(carbs_adj),
        "fat_g": int(fat_adj),
        "adjustments_rationale": rationale,
    }


def detect_red_flags(
    current_week: dict,
    past_weeks: list[dict],
    profile: dict,
) -> list[dict]:
    """
    Identify concerning patterns that need immediate attention.

    Detects 6 types of red flags: rapid weight loss, extreme hunger, energy crash,
    mood shift, abandonment risk, stress patterns.

    Args:
        current_week: Current week's feedback (dict with metrics)
        past_weeks: List of previous weekly_feedback records
        profile: User profile dict (age, gender, goal, etc.)

    Returns:
        List of red flag dicts:
        [
            {
                "flag_type": "rapid_weight_loss",
                "severity": "warning",  # warning, critical
                "description": "Losing 1.2 kg/week (threshold: 1.0 kg/week)",
                "action": "Reduce deficit by 200 kcal to avoid muscle loss",
                "scientific_basis": "Rapid losses >1kg/week correlate with lean mass loss"
            },
            ...
        ]

    References:
        Helms et al. (2014): Body composition during dieting
        Hall & Guo (2017): Compensation of energy expenditure during caloric restriction
    """
    flags = []

    # Flag 1: Rapid weight loss
    weight_change_kg = current_week.get("weight_change_kg", 0)
    if abs(weight_change_kg) > RED_FLAG_RAPID_LOSS_THRESHOLD:
        if len(past_weeks) > 0:
            past_loss = sum(abs(w.get("weight_change_kg", 0)) for w in past_weeks[-3:])
            if past_loss > RED_FLAG_RAPID_LOSS_THRESHOLD:
                flags.append(
                    {
                        "flag_type": "rapid_weight_loss",
                        "severity": "critical",
                        "description": f"Losing {abs(weight_change_kg):.1f}kg/week for multiple weeks (threshold: {RED_FLAG_RAPID_LOSS_THRESHOLD}kg)",
                        "action": "Reduce deficit by 200-300 kcal/day immediately",
                        "scientific_basis": "Rapid losses >1kg/week correlate with lean mass loss and metabolic slowdown (Helms et al.)",
                    }
                )
        else:
            flags.append(
                {
                    "flag_type": "rapid_weight_loss",
                    "severity": "warning",
                    "description": f"Rapid weight loss this week: {abs(weight_change_kg):.1f}kg (target: {RED_FLAG_RAPID_LOSS_THRESHOLD}kg)",
                    "action": "Monitor next week; if repeats, increase calories",
                    "scientific_basis": "Single rapid loss could be water/glycogen, but confirm is safe",
                }
            )

    # Flag 2: Extreme hunger
    hunger = current_week.get("hunger_level", "medium")
    adherence = current_week.get("adherence_percent", 50)
    if hunger == "high" and adherence < RED_FLAG_EXTREME_HUNGER_ADHERENCE:
        flags.append(
            {
                "flag_type": "extreme_hunger",
                "severity": "warning",
                "description": f"High hunger + low adherence ({adherence}%); plan may be unsustainable",
                "action": "Increase calories by 100-150 kcal, increase protein or satiety-promoting foods",
                "scientific_basis": "Extreme hunger that impacts adherence signals insufficient energy for sustainable deficit",
            }
        )

    # Flag 3: Energy crash
    energy = current_week.get("energy_level", "medium")
    if energy == "low":
        if len(past_weeks) > 0:
            # Have historical data: check if low energy persists across weeks
            recent_energy = [w.get("energy_level") == "low" for w in past_weeks[-2:]]
            if sum(recent_energy) >= RED_FLAG_ENERGY_CRASH_WEEKS - 1:
                flags.append(
                    {
                        "flag_type": "energy_crash",
                        "severity": "warning",
                        "description": f"Low energy for {RED_FLAG_ENERGY_CRASH_WEEKS}+ weeks; affects training and recovery",
                        "action": "Check carbs (especially pre-workout), increase sleep, check stress levels",
                        "scientific_basis": "Persistent low energy may indicate insufficient carbs or need for refeed day",
                    }
                )
        else:
            # Week 1: flag low energy as warning (no history to confirm pattern yet)
            flags.append(
                {
                    "flag_type": "energy_crash",
                    "severity": "warning",
                    "description": "Low energy reported in week 1; monitor if this continues",
                    "action": "Check carbs timing, sleep quality, and stress levels. If persists next week, we'll adjust",
                    "scientific_basis": "Low energy in early stages may indicate underfueling or lifestyle factors",
                }
            )

    # Flag 4: Mood shift
    notes = current_week.get("subjective_notes", "").lower()
    mood_keywords_found = [kw for kw in RED_FLAG_MOOD_SHIFT_KEYWORDS if kw in notes]
    if mood_keywords_found:
        flags.append(
            {
                "flag_type": "mood_shift",
                "severity": "critical",
                "description": f"Mood concerns detected: {', '.join(mood_keywords_found)}",
                "action": "Prioritize mental health; consider lifting restriction or consulting professional",
                "scientific_basis": "Mood changes during diet may indicate psychological strain; mental health is priority",
            }
        )

    # Flag 5: Abandonment risk
    if adherence < 30:
        flags.append(
            {
                "flag_type": "abandonment_risk",
                "severity": "critical",
                "description": f"Very low adherence ({adherence}%); plan may not be working",
                "action": "Simplify plan, reduce targets, or take strategic break",
                "scientific_basis": "Adherence <30% indicates frustration or plan incompatibility",
            }
        )

    # Flag 6: Stress pattern
    if "stress" in notes or "busy" in notes:
        if adherence < 70:
            flags.append(
                {
                    "flag_type": "stress_pattern",
                    "severity": "warning",
                    "description": "Stress detected alongside lower adherence; normal response",
                    "action": "Offer simpler meal prep, remind of flexibility, prioritize sleep",
                    "scientific_basis": "Stress increases cortisol, which can impair adherence and metabolism",
                }
            )

    # Log flags
    if flags:
        logger.warning(f"🚨 Red flags detected: {[f['flag_type'] for f in flags]}")

    return flags
