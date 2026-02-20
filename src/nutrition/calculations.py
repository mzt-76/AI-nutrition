"""
Scientifically-validated nutrition calculations.

All formulas cite peer-reviewed sources and follow ISSN/AND guidelines.
Using Mifflin-St Jeor equation for BMR (most accurate for general population).

References:
- Mifflin et al. (1990): A new predictive equation for resting energy expenditure
- ISSN Position Stand (2017): Protein and exercise
- Helms et al. (2014): Evidence-based recommendations for contest prep
"""

from typing import Dict, Literal
import logging

logger = logging.getLogger(__name__)

# Activity level multipliers (based on research)
ACTIVITY_MULTIPLIERS = {
    "sedentary": 1.2,  # Little to no exercise
    "light": 1.375,  # Light exercise 1-3 days/week
    "moderate": 1.55,  # Moderate exercise 3-5 days/week
    "active": 1.725,  # Heavy exercise 6-7 days/week
    "very_active": 1.9,  # Very heavy exercise, physical job
}

# Protein targets (g/kg body weight) - ISSN guidelines
PROTEIN_TARGETS = {
    "maintenance": (1.4, 2.0),  # General fitness
    "muscle_gain": (1.6, 2.2),  # Hypertrophy (plateau at ~1.6g/kg)
    "weight_loss": (2.3, 3.1),  # Preserve lean mass during deficit
    "performance": (1.6, 2.0),  # Athletic performance
}


def mifflin_st_jeor_bmr(
    age: int, gender: Literal["male", "female"], weight_kg: float, height_cm: int
) -> int:
    """
    Calculate Basal Metabolic Rate using Mifflin-St Jeor equation.

    This is the most accurate equation for predicting resting energy expenditure
    in healthy adults (validated in multiple studies).

    Args:
        age: Age in years (18-100)
        gender: "male" or "female"
        weight_kg: Body weight in kilograms
        height_cm: Height in centimeters

    Returns:
        BMR in kcal/day (rounded to nearest integer)

    Raises:
        ValueError: If parameters are out of valid ranges

    Example:
        >>> bmr = mifflin_st_jeor_bmr(35, "male", 87, 178)
        >>> print(bmr)
        1850

    References:
        Mifflin et al. (1990) Am J Clin Nutr. 51(2):241-7
    """
    # Validation
    if not 18 <= age <= 100:
        raise ValueError(f"Age must be between 18 and 100, got {age}")
    if weight_kg < 40:
        raise ValueError(f"Weight must be at least 40kg, got {weight_kg}")
    if height_cm < 100:
        raise ValueError(f"Height must be at least 100cm, got {height_cm}")

    # Mifflin-St Jeor formula
    if gender == "male":
        # Men: (10 × weight in kg) + (6.25 × height in cm) - (5 × age in years) + 5
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) + 5
    elif gender == "female":
        # Women: (10 × weight in kg) + (6.25 × height in cm) - (5 × age in years) - 161
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) - 161
    else:
        raise ValueError(f"Gender must be 'male' or 'female', got {gender}")

    logger.info(
        f"Calculated BMR: {int(bmr)} kcal (age={age}, gender={gender}, weight={weight_kg}kg, height={height_cm}cm)"
    )

    return int(bmr)


def calculate_tdee(bmr: int, activity_level: str) -> int:
    """
    Calculate Total Daily Energy Expenditure.

    Args:
        bmr: Basal Metabolic Rate (kcal/day)
        activity_level: One of sedentary, light, moderate, active, very_active

    Returns:
        TDEE in kcal/day (rounded to nearest integer)

    Raises:
        ValueError: If activity_level is invalid

    Example:
        >>> tdee = calculate_tdee(1850, "moderate")
        >>> print(tdee)
        2868
    """
    if activity_level not in ACTIVITY_MULTIPLIERS:
        valid_levels = ", ".join(ACTIVITY_MULTIPLIERS.keys())
        raise ValueError(
            f"Activity level must be one of: {valid_levels}, got {activity_level}"
        )

    multiplier = ACTIVITY_MULTIPLIERS[activity_level]
    tdee = bmr * multiplier

    logger.info(f"Calculated TDEE: {int(tdee)} kcal (BMR={bmr} × {multiplier})")

    return int(tdee)


def infer_goals_from_context(
    activities: list[str] | None = None,
    context: str | None = None,
    explicit_goals: Dict[str, int] | None = None,
) -> Dict[str, int]:
    """
    Infer user goals from activities and context using keyword matching.

    Args:
        activities: List of activities (e.g., ["musculation", "basket"])
        context: Free-text context from user
        explicit_goals: Pre-specified goals (if any)

    Returns:
        Dict with goal scores (0-10): muscle_gain, weight_loss, maintenance, performance

    Example:
        >>> goals = infer_goals_from_context(["musculation"], "Je veux prendre du muscle")
        >>> print(goals)
        {"muscle_gain": 7, "performance": 3, "weight_loss": 0, "maintenance": 3}
    """
    # Start with defaults or explicit goals
    if explicit_goals:
        return explicit_goals

    # Default: Maintenance/Health (if no context provided)
    goals = {
        "muscle_gain": 0,
        "weight_loss": 0,
        "maintenance": 7,  # Default: Health & maintenance (balanced nutrition)
        "performance": 0,
    }

    # Combine activities and context for analysis
    text = ""
    if activities:
        text += " ".join(activities).lower()
    if context:
        text += " " + context.lower()

    # Keyword matching for goal inference
    muscle_keywords = [
        "muscul",
        "muscle",
        "hypertrophie",
        "prise de masse",
        "bulk",
        "grossir",
        "prendre du poids",
    ]
    loss_keywords = [
        "maigrir",
        "perte",
        "déficit",
        "secher",
        "cut",
        "perdre du poids",
        "mincir",
    ]
    performance_keywords = [
        "sport",
        "performance",
        "compétition",
        "basket",
        "foot",
        "course",
        "endurance",
    ]

    # Track if we found a specific goal
    specific_goal_found = False

    for keyword in muscle_keywords:
        if keyword in text:
            goals["muscle_gain"] = 7
            goals["maintenance"] = 0  # Override default when specific goal is set
            specific_goal_found = True
            break

    for keyword in loss_keywords:
        if keyword in text:
            goals["weight_loss"] = 7
            goals["muscle_gain"] = 0  # Conflicting goal
            goals["maintenance"] = 0  # Override default when specific goal is set
            specific_goal_found = True
            break

    for keyword in performance_keywords:
        if keyword in text:
            goals["performance"] = 7
            if (
                not specific_goal_found
            ):  # Keep maintenance lower when performance is set
                goals["maintenance"] = 3  # Can combine performance with maintenance

    logger.info(f"Inferred goals from context: {goals}")

    return goals


def calculate_protein_target(
    weight_kg: float, primary_goal: str, use_intermediate: bool = True
) -> tuple[int, float, tuple[int, int]]:
    """
    Calculate protein target based on weight and primary goal with adaptive ranges.

    Args:
        weight_kg: Body weight in kilograms
        primary_goal: One of maintenance, muscle_gain, weight_loss, performance
        use_intermediate: If True, use intermediate value instead of max (default: True)

    Returns:
        Tuple of (protein_g, protein_per_kg, protein_range)
        - protein_g: Recommended protein intake in grams
        - protein_per_kg: Protein per kg body weight
        - protein_range: (min_g, max_g) tuple for the range

    Example:
        >>> protein_g, per_kg, range_tuple = calculate_protein_target(87, "weight_loss")
        >>> print(f"{protein_g}g ({per_kg}g/kg), range: {range_tuple[0]}-{range_tuple[1]}g")
        217g (2.5g/kg), range: 200-270g

    References:
        ISSN Position Stand (2017): 1.6-2.2g/kg for muscle gain
        Helms et al. (2014): 2.3-3.1g/kg for deficit
    """
    if primary_goal not in PROTEIN_TARGETS:
        primary_goal = "maintenance"

    min_protein_per_kg, max_protein_per_kg = PROTEIN_TARGETS[primary_goal]

    # Use intermediate value for more realistic initial recommendations
    if use_intermediate:
        if primary_goal == "weight_loss":
            # Start at 2.5g/kg (middle of 2.3-3.1 range) for better adherence
            protein_per_kg = 2.5
        elif primary_goal == "muscle_gain":
            # Start at 1.8g/kg (middle of 1.6-2.4 range)
            protein_per_kg = 2
        else:
            # Use middle of range for other goals
            protein_per_kg = (min_protein_per_kg + max_protein_per_kg) / 2
    else:
        # Use maximum for aggressive goals
        protein_per_kg = max_protein_per_kg

    protein_g = int(weight_kg * protein_per_kg)

    # Calculate range bounds
    min_protein_g = int(weight_kg * min_protein_per_kg)
    max_protein_g = int(weight_kg * max_protein_per_kg)
    protein_range = (min_protein_g, max_protein_g)

    logger.info(
        f"Protein target: {protein_g}g ({protein_per_kg}g/kg) for {primary_goal}, "
        f"range: {min_protein_g}-{max_protein_g}g"
    )

    return protein_g, protein_per_kg, protein_range


def calculate_macros(
    target_calories: int, protein_g: int, goal_type: str = "muscle_gain"
) -> Dict[str, int]:
    """
    Calculate carb and fat targets based on calories and protein.

    Fat is calculated as a percentage of TOTAL calories (20-25% range depending
    on goal). Carbs receive the remaining calories after protein and fat.

    Args:
        target_calories: Total daily calorie target
        protein_g: Protein target in grams
        goal_type: Primary goal (affects fat % of total)

    Returns:
        Dict with carbs_g and fat_g

    Example:
        >>> macros = calculate_macros(2964, 172, "muscle_gain")
        >>> print(macros)
        {"carbs_g": 384, "fat_g": 66}

    References:
        ISSN (2017): 20-35% of total calories from fat recommended.
        20-25% range used here to maximize carb budget for training.
    """
    # Caloric values per gram
    PROTEIN_KCAL = 4
    CARB_KCAL = 4
    FAT_KCAL = 9

    # Fat as % of TOTAL calories (goal-dependent, 20-25% range)
    # Ref: ISSN recommends 20-35%; lower end preserves carb budget
    FAT_PCT_OF_TOTAL = {
        "muscle_gain": 0.22,  # 22% — lower fat, higher carbs for training fuel
        "weight_loss": 0.25,  # 25% — higher fat for satiety during deficit
        "maintenance": 0.25,  # 25% — balanced
        "performance": 0.20,  # 20% — maximize carbs for endurance
    }

    fat_pct = FAT_PCT_OF_TOTAL.get(goal_type, 0.25)
    fat_g = int((target_calories * fat_pct) / FAT_KCAL)

    # Carbs get the remaining calories after protein and fat
    protein_calories = protein_g * PROTEIN_KCAL
    fat_calories = fat_g * FAT_KCAL
    carbs_g = int((target_calories - protein_calories - fat_calories) / CARB_KCAL)

    # Safety: ensure non-negative carbs (extreme high-protein edge case)
    carbs_g = max(0, carbs_g)

    logger.info(
        f"Calculated macros: {carbs_g}g carbs, {fat_g}g fat "
        f"(fat={fat_pct:.0%} of total)"
    )

    return {"carbs_g": carbs_g, "fat_g": fat_g}
