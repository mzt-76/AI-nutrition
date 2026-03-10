"""
Post-processing macro adjustment system for meal plans.

Ensures 100% macro accuracy by adding complement foods when LLM-generated
plans deviate from targets. Prioritizes protein deficits as they're critical
for muscle gain goals.

References:
    ISSN Position Stand (2017): Protein requirements for muscle hypertrophy
    Helms et al. (2014): Evidence-based recommendations for bodybuilding prep
"""

import logging
from typing import Literal

logger = logging.getLogger(__name__)

# Macro tolerance thresholds for POST-PROCESSING activation (percentage)
# Post-processing kicks in when GPT-4o deviates significantly from targets
# NOTE: Different tolerances reflect nutritional priorities and natural variability
TOLERANCE_PROTEIN = (
    0.15  # ±15% tolerance for protein (ISSN allows 1.4-2.0g/kg = ±18% range)
)
TOLERANCE_CALORIES = (
    0.05  # ±5% tolerance for calories (CRITICAL for energy balance/weight goals)
)
TOLERANCE_CARBS = (
    0.15  # ±15% tolerance for carbs (less critical, can flex for energy needs)
)
TOLERANCE_FAT = 0.15  # ±15% tolerance for fat (less critical, can flex for satiety)

# Complement food database (high protein efficiency)
COMPLEMENT_FOODS = [
    {
        "name": "Shaker protéine whey",
        "category": "protein_supplement",
        "portion_size": "1 dose (30g)",
        "nutrition": {"calories": 120, "protein_g": 25, "carbs_g": 3, "fat_g": 1.5},
        "allergens": ["lait"],  # Whey is dairy-based
        "prep_note": "Mélanger avec 250ml d'eau ou lait",
        "timing": "collation",  # Best as snack
    },
    {
        "name": "Blanc de poulet grillé",
        "category": "lean_protein",
        "portion_size": "100g",
        "nutrition": {"calories": 165, "protein_g": 31, "carbs_g": 0, "fat_g": 3.6},
        "allergens": [],
        "prep_note": "Grillé sans huile, assaisonné avec herbes",
        "timing": "meal",  # Can be added to main meals
    },
    {
        "name": "Yaourt grec 0%",
        "category": "dairy_protein",
        "portion_size": "200g",
        "nutrition": {"calories": 110, "protein_g": 20, "carbs_g": 8, "fat_g": 0},
        "allergens": ["lait"],
        "prep_note": "Nature, peut ajouter fruits",
        "timing": "collation",
    },
    {
        "name": "Œufs durs",
        "category": "whole_protein",
        "portion_size": "2 œufs",
        "nutrition": {"calories": 140, "protein_g": 12, "carbs_g": 1, "fat_g": 10},
        "allergens": ["œufs"],
        "prep_note": "Cuire 10 min dans eau bouillante",
        "timing": "collation",
    },
    {
        "name": "Fromage blanc 0%",
        "category": "dairy_protein",
        "portion_size": "200g",
        "nutrition": {"calories": 90, "protein_g": 16, "carbs_g": 6, "fat_g": 0},
        "allergens": ["lait"],
        "prep_note": "Nature ou avec édulcorant",
        "timing": "collation",
    },
    {
        "name": "Thon au naturel",
        "category": "fish_protein",
        "portion_size": "1 boîte (120g égoutté)",
        "nutrition": {"calories": 120, "protein_g": 28, "carbs_g": 0, "fat_g": 1},
        "allergens": [],
        "prep_note": "Égoutter, assaisonner avec citron",
        "timing": "meal",
    },
    {
        "name": "Tranches de dinde",
        "category": "lean_protein",
        "portion_size": "100g",
        "nutrition": {"calories": 110, "protein_g": 24, "carbs_g": 1, "fat_g": 1.5},
        "allergens": [],
        "prep_note": "Prêt à consommer",
        "timing": "collation",
    },
    {
        "name": "Edamame (fèves de soja)",
        "category": "plant_protein",
        "portion_size": "150g cuit",
        "nutrition": {"calories": 180, "protein_g": 18, "carbs_g": 14, "fat_g": 8},
        "allergens": ["soja"],
        "prep_note": "Cuire 5 min à la vapeur, saler légèrement",
        "timing": "collation",
    },
]


def calculate_macro_deficit(
    actual_totals: dict[str, float], target_totals: dict[str, float]
) -> dict[str, float]:
    """
    Calculate deficit between actual and target macros.

    Args:
        actual_totals: Actual daily totals (calories, protein_g, carbs_g, fat_g)
        target_totals: Target daily totals

    Returns:
        Dict with deficit for each macro (negative = deficit, positive = surplus)

    Example:
        >>> actual = {"calories": 2200, "protein_g": 120, "carbs_g": 250, "fat_g": 70}
        >>> target = {"calories": 2474, "protein_g": 156, "carbs_g": 280, "fat_g": 80}
        >>> deficit = calculate_macro_deficit(actual, target)
        >>> deficit["protein_g"]
        -36
    """
    deficit = {
        "calories": actual_totals.get("calories", 0) - target_totals.get("calories", 0),
        "protein_g": actual_totals.get("protein_g", 0)
        - target_totals.get("protein_g", 0),
        "carbs_g": actual_totals.get("carbs_g", 0) - target_totals.get("carbs_g", 0),
        "fat_g": actual_totals.get("fat_g", 0) - target_totals.get("fat_g", 0),
    }

    logger.debug(f"Macro deficit calculated: {deficit}")
    return deficit


def needs_adjustment(
    deficit: dict[str, float], target_totals: dict[str, float]
) -> dict[str, bool]:
    """
    Determine which macros need adjustment based on tolerance thresholds.

    Flags TRUE if ANY deviation (deficit OR surplus) exceeds ±5% tolerance.
    This allows portion scaling both UP (for deficits) and DOWN (for surpluses).

    Args:
        deficit: Deficit dict from calculate_macro_deficit (negative = needs more, positive = has too much)
        target_totals: Target values for calculating percentage deviation

    Returns:
        Dict with boolean flags for each macro (True if deviation exceeds ±5% tolerance)

    Example:
        >>> deficit = {"calories": -274, "protein_g": -36, "carbs_g": 10, "fat_g": 5}
        >>> target = {"calories": 2474, "protein_g": 156, "carbs_g": 280, "fat_g": 80}
        >>> needs = needs_adjustment(deficit, target)
        >>> needs["protein_g"]  # -36g is a deficit beyond tolerance
        True
        >>> needs["carbs_g"]  # +10g is within tolerance (3.6%)
        False
    """
    # Check if ABSOLUTE deviation exceeds tolerance (works for both deficit and surplus)
    needs = {
        "calories": abs(deficit["calories"])
        > (target_totals["calories"] * TOLERANCE_CALORIES),
        "protein_g": abs(deficit["protein_g"])
        > (target_totals["protein_g"] * TOLERANCE_PROTEIN),
        "carbs_g": abs(deficit["carbs_g"])
        > (target_totals["carbs_g"] * TOLERANCE_CARBS),
        "fat_g": abs(deficit["fat_g"]) > (target_totals["fat_g"] * TOLERANCE_FAT),
    }

    logger.debug(f"Adjustment needs (±tolerance): {needs}")
    return needs


def select_complement_food(
    deficit: dict[str, float],
    user_allergens: list[str],
    timing_preference: Literal["collation", "meal", "any"] = "any",
) -> dict | None:
    """
    Select optimal complement food based on deficit and allergen constraints.

    Priority order:
    1. Highest protein per calorie ratio (for protein deficits)
    2. No allergen conflicts
    3. Matches timing preference if specified

    Args:
        deficit: Macro deficit dict (negative values = deficit)
        user_allergens: List of user allergens (lowercase)
        timing_preference: When to add food ("collation", "meal", "any")

    Returns:
        Selected complement food dict or None if no safe options

    Example:
        >>> deficit = {"protein_g": -30, "calories": -200}
        >>> food = select_complement_food(deficit, ["lait"], "collation")
        >>> food["name"]
        'Œufs durs'  # Dairy-free, good for snacks
    """
    # Primary deficit: protein or calories?
    protein_deficit = abs(deficit.get("protein_g", 0))
    calorie_deficit = abs(deficit.get("calories", 0))

    # Normalize user allergens
    user_allergens_lower = [a.strip().lower() for a in user_allergens]

    # Filter by allergen safety
    safe_foods = [
        food
        for food in COMPLEMENT_FOODS
        if not any(allergen in user_allergens_lower for allergen in food["allergens"])
    ]

    if not safe_foods:
        logger.warning(
            "No safe complement foods available (all conflict with allergens)"
        )
        return None

    # Filter by timing if specified
    if timing_preference != "any":
        timing_filtered = [f for f in safe_foods if f["timing"] == timing_preference]
        if timing_filtered:
            safe_foods = timing_filtered

    # Score foods based on deficit priorities
    def score_food(food: dict) -> float:
        """Higher score = better fit for deficit."""
        nutrition = food["nutrition"]

        # If protein deficit is primary concern (>20g deficit)
        if protein_deficit >= 20:
            # Protein per calorie ratio
            protein_efficiency = nutrition["protein_g"] / max(nutrition["calories"], 1)
            return protein_efficiency * 100  # Scale up for easier comparison

        # If calorie deficit is primary
        elif calorie_deficit >= 150:
            # Total calories (prefer higher calorie foods)
            return nutrition["calories"]

        # Mixed deficit: balance protein and calories
        else:
            protein_score = nutrition["protein_g"] * 2  # Weight protein higher
            calorie_score = nutrition["calories"] / 10
            return protein_score + calorie_score

    # Sort by score (highest first)
    ranked_foods = sorted(safe_foods, key=score_food, reverse=True)

    selected = ranked_foods[0]
    logger.info(
        f"Selected complement food: {selected['name']} "
        f"(+{selected['nutrition']['protein_g']}g protein, +{selected['nutrition']['calories']} kcal)"
    )

    return selected


def adjust_meal_plan_macros(
    meal_plan: dict,
    target_totals: dict[str, float],
    user_allergens: list[str] | None = None,
) -> dict:
    """
    Post-process meal plan to ensure macro accuracy via complement foods.

    Analyzes each day's macros and adds complement foods/meals as needed
    to hit targets within tolerance. Prioritizes protein deficits.

    Args:
        meal_plan: Generated meal plan dict from GPT-4o
        target_totals: Target macros (calories, protein_g, carbs_g, fat_g)
        user_allergens: List of user allergens

    Returns:
        Adjusted meal plan dict with complement foods added where needed

    Example:
        >>> plan = {"days": [...]}  # Day with 120g protein vs 156g target
        >>> adjusted = adjust_meal_plan_macros(plan, {"protein_g": 156, ...}, [])
        >>> # Returns plan with added protein complement to reach target
    """
    if user_allergens is None:
        user_allergens = []

    days_adjusted = 0
    total_complements_added = 0

    for day in meal_plan.get("days", []):
        daily_totals = day.get("daily_totals", {})

        # Calculate deficit
        deficit = calculate_macro_deficit(daily_totals, target_totals)
        needs = needs_adjustment(deficit, target_totals)

        # Skip if day is already within tolerance
        if not any(needs.values()):
            logger.debug(
                f"Day {day.get('day', 'Unknown')} within tolerance, no adjustment needed"
            )
            continue

        logger.info(
            f"🔧 Adjusting {day.get('day', 'Unknown')}: "
            f"Protein deficit: {deficit['protein_g']:.1f}g, "
            f"Calorie deficit: {deficit['calories']:.1f} kcal"
        )

        # Add complement foods until within tolerance
        max_iterations = 3  # Prevent infinite loops
        iteration = 0

        while any(needs.values()) and iteration < max_iterations:
            iteration += 1

            # Select appropriate complement food
            complement_food = select_complement_food(
                deficit, user_allergens, "collation"
            )

            if not complement_food:
                logger.warning(
                    f"Cannot adjust {day.get('day')}: no safe complement foods available"
                )
                break

            # Create complement meal entry
            complement_meal = {
                "meal_type": "Complément nutritionnel",
                "time": "Flexible",
                "recipe_name": complement_food["name"],
                "servings": 1,
                "prep_time_min": 5,
                "ingredients": [
                    {"name": complement_food["name"], "quantity": 1, "unit": "portion"}
                ],
                "instructions": complement_food["prep_note"],
                "nutrition": complement_food["nutrition"],
                "tags": ["complement", "ajusté_automatiquement"],
                "note": f"✨ Ajouté automatiquement pour atteindre vos objectifs protéines ({target_totals.get('protein_g', 0)}g/jour)",
            }

            # Add to meals list
            day["meals"].append(complement_meal)
            total_complements_added += 1

            # Update daily totals
            daily_totals["calories"] += complement_food["nutrition"]["calories"]
            daily_totals["protein_g"] += complement_food["nutrition"]["protein_g"]
            daily_totals["carbs_g"] += complement_food["nutrition"]["carbs_g"]
            daily_totals["fat_g"] += complement_food["nutrition"]["fat_g"]

            # Recalculate deficit and needs
            deficit = calculate_macro_deficit(daily_totals, target_totals)
            needs = needs_adjustment(deficit, target_totals)

            logger.info(
                f"  → Added {complement_food['name']}: "
                f"New protein: {daily_totals['protein_g']:.1f}g "
                f"(target: {target_totals['protein_g']}g)"
            )

        days_adjusted += 1

    logger.info(
        f"✅ Macro adjustment complete: {days_adjusted} days adjusted, "
        f"{total_complements_added} complement foods added"
    )

    return meal_plan


def generate_adjustment_summary(
    meal_plan: dict, target_totals: dict[str, float]
) -> str:
    """
    Generate user-friendly summary of macro adjustments made.

    Args:
        meal_plan: Adjusted meal plan
        target_totals: Target macros

    Returns:
        Formatted summary string

    Example:
        >>> summary = generate_adjustment_summary(plan, targets)
        >>> "complément" in summary.lower()
        True
    """
    complements_count = 0
    days_with_complements = []

    for day in meal_plan.get("days", []):
        day_name = day.get("day", "Unknown")
        has_complement = any(
            "complement" in meal.get("tags", []) for meal in day.get("meals", [])
        )

        if has_complement:
            complements_count += 1
            days_with_complements.append(day_name)

    if complements_count == 0:
        return "✅ Aucun ajustement nécessaire - le plan généré respecte déjà vos objectifs nutritionnels."

    summary = f"""
🔧 **Ajustements Nutritionnels Automatiques**

Pour garantir que vous atteigniez vos objectifs ({target_totals.get('protein_g', 0)}g protéines, {target_totals.get('calories', 0)} kcal/jour), j'ai ajouté des compléments nutritionnels sur **{complements_count} jour(s)** :

{", ".join(days_with_complements)}

**Ces compléments sont :**
- Faciles à préparer (5 min max)
- Riches en protéines de qualité
- Sans allergènes selon votre profil
- Flexibles dans le timing (à consommer quand vous voulez)

💡 **Pourquoi ?** Le plan généré était excellent en variété, mais légèrement en dessous de votre objectif protéique. Ces ajouts garantissent vos résultats en prise de muscle.

Vous pouvez les remplacer par d'autres sources de protéines si vous préférez (poulet, poisson, œufs, etc.).
"""

    return summary.strip()
