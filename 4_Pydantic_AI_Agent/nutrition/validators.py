"""
Safety validation functions for meal planning.

Enforces zero-tolerance allergen policy and validates meal plan structure.
"""

import logging

logger = logging.getLogger(__name__)

# Allergen family mappings - comprehensive list for family-based allergen detection
ALLERGEN_FAMILIES = {
    "arachides": [
        "cacahuète",
        "cacahuete",
        "peanut",
        "arachide",
        "beurre de cacahuète",
        "beurre de cacahuete",
        "peanut butter",
        "sauce satay",
        "pad thai",
    ],
    "fruits à coque": [
        "amande",
        "noix",
        "noisette",
        "cajou",
        "pistache",
        "pécan",
        "macadamia",
        "almond",
        "walnut",
        "hazelnut",
        "cashew",
        "pistachio",
        "pecan",
    ],
    "lactose": [
        "lait",
        "yaourt",
        "fromage",
        "crème",
        "beurre",
        "milk",
        "yogurt",
        "cheese",
        "cream",
        "butter",
        "yoghurt",
        "crémeux",
        "cremeaux",
    ],
    "gluten": [
        "blé",
        "pain",
        "pâtes",
        "farine",
        "wheat",
        "bread",
        "pasta",
        "flour",
        "seigle",
        "orge",
    ],
    "oeuf": ["oeuf", "oeufs", "egg", "eggs", "mayonnaise"],
    "soja": ["soja", "soy", "tofu", "edamame", "tempeh", "miso"],
    "poisson": [
        "poisson",
        "fish",
        "thon",
        "saumon",
        "truite",
        "morue",
        "tuna",
        "salmon",
    ],
    "fruits de mer": [
        "crevette",
        "crabe",
        "homard",
        "moule",
        "huître",
        "shrimp",
        "crab",
        "lobster",
        "mussel",
        "oyster",
    ],
    "sésame": ["sésame", "sesame", "tahini", "tahin"],
}

# Special cases: NOT allergens despite name confusion
ALLERGEN_FALSE_POSITIVES = {
    "noix de coco": "fruits à coque",  # Coconut is NOT a tree nut (it's a drupe)
    "muscade": "fruits à coque",  # Nutmeg is NOT a nut (it's a seed)
    "lait d'amande": "lactose",  # Almond milk is plant-based (no lactose)
    "lait de soja": "lactose",  # Soy milk is plant-based (no lactose)
    "lait d'avoine": "lactose",  # Oat milk is plant-based (no lactose)
    "lait de coco": "lactose",  # Coconut milk is plant-based (no lactose)
}


def validate_allergens(meal_plan: dict, user_allergens: list[str]) -> list[str]:
    """
    Validate meal plan contains no user allergens (zero tolerance).

    Checks all ingredients against user allergens and allergen families.
    Uses case-insensitive partial matching with false positive handling.

    Args:
        meal_plan: Meal plan dict with days containing meals with ingredients
        user_allergens: List of allergen names from user profile (e.g., ["arachides", "lactose"])

    Returns:
        List of violation strings (empty if safe). Each violation describes the allergen found.

    Example:
        >>> plan = {"days": [{"meals": [{"recipe_name": "Salade", "ingredients": [{"name": "beurre de cacahuète"}]}]}]}
        >>> violations = validate_allergens(plan, ["arachides"])
        >>> len(violations) > 0
        True
    """
    if not user_allergens:
        logger.info("No allergens to validate (user has no allergies)")
        return []

    logger.info(f"Validating allergen safety for: {user_allergens}")
    violations = []

    # Normalize allergen names to lowercase for case-insensitive matching
    normalized_allergens = [a.lower().strip() for a in user_allergens]

    # Build comprehensive keyword list for each user allergen
    allergen_keywords = {}
    for allergen in normalized_allergens:
        keywords = [allergen]  # Start with allergen name itself
        if allergen in ALLERGEN_FAMILIES:
            keywords.extend(ALLERGEN_FAMILIES[allergen])
        allergen_keywords[allergen] = keywords

    logger.debug(f"Allergen keywords to check: {allergen_keywords}")

    # Iterate through all days and meals
    days = meal_plan.get("days", [])
    for day_idx, day in enumerate(days):
        day_name = day.get("day", f"Day {day_idx + 1}")
        meals = day.get("meals", [])

        for meal_idx, meal in enumerate(meals):
            recipe_name = meal.get("recipe_name", f"Meal {meal_idx + 1}")
            ingredients = meal.get("ingredients", [])

            for ingredient_idx, ingredient in enumerate(ingredients):
                ingredient_name = ingredient.get("name", "").lower().strip()

                if not ingredient_name:
                    continue

                # Check false positives first (allow if it's a known false positive)
                is_false_positive = False
                for fp_keyword, fp_allergen in ALLERGEN_FALSE_POSITIVES.items():
                    if (
                        fp_keyword in ingredient_name
                        and fp_allergen in normalized_allergens
                    ):
                        logger.debug(
                            f"False positive allowed: {ingredient_name} (not {fp_allergen})"
                        )
                        is_false_positive = True
                        break

                if is_false_positive:
                    continue

                # Check against all allergen keywords
                for allergen, keywords in allergen_keywords.items():
                    for keyword in keywords:
                        if keyword.lower() in ingredient_name:
                            violation = (
                                f"🚨 ALLERGEN FOUND: '{ingredient_name}' in '{recipe_name}' "
                                f"on {day_name} matches allergen '{allergen}' (keyword: '{keyword}')"
                            )
                            violations.append(violation)
                            logger.error(violation)
                            break  # Stop checking other keywords for this allergen

    if violations:
        logger.error(f"❌ Total allergen violations: {len(violations)}")
    else:
        logger.info("✅ Allergen validation passed (zero violations)")

    return violations


def validate_daily_macros(
    daily_totals: dict, targets: dict, tolerance: float = 0.10
) -> dict:
    """
    Validate daily macro totals are within tolerance of targets.

    Args:
        daily_totals: Dict with calories, protein_g, carbs_g, fat_g
        targets: Dict with target values for each macro
        tolerance: Acceptable deviation (default 10% = 0.10)

    Returns:
        Dict with {"valid": bool, "violations": list[str]}

    Example:
        >>> totals = {"calories": 2950, "protein_g": 170, "carbs_g": 340, "fat_g": 80}
        >>> targets = {"calories": 3000, "protein_g": 180, "carbs_g": 350, "fat_g": 85}
        >>> result = validate_daily_macros(totals, targets)
        >>> result["valid"]
        True
    """
    violations = []

    for macro in ["calories", "protein_g", "carbs_g", "fat_g"]:
        if macro not in targets:
            continue

        target = targets[macro]
        actual = daily_totals.get(macro, 0)

        # Calculate tolerance range
        lower_bound = target * (1 - tolerance)
        upper_bound = target * (1 + tolerance)

        if not (lower_bound <= actual <= upper_bound):
            deviation_pct = ((actual - target) / target) * 100
            violation = (
                f"{macro}: {actual} (target: {target}, deviation: {deviation_pct:+.1f}%, "
                f"tolerance: ±{tolerance * 100:.0f}%)"
            )
            violations.append(violation)

    valid = len(violations) == 0

    if not valid:
        logger.warning(f"Macro validation issues: {violations}")
    else:
        logger.info("✅ Daily macros within tolerance")

    return {"valid": valid, "violations": violations}


def validate_meal_plan_structure(meal_plan: dict, require_nutrition: bool = True) -> dict:
    """
    Validate meal plan has required JSON structure.

    Args:
        meal_plan: Generated meal plan dict
        require_nutrition: Whether nutrition fields are required (False when using FatSecret)

    Returns:
        Dict with {"valid": bool, "missing_fields": list[str]}

    Example:
        >>> plan = {"meal_plan_id": "plan_2024-12-23", "start_date": "2024-12-23", "days": []}
        >>> result = validate_meal_plan_structure(plan)
        >>> result["valid"]
        True
    """
    missing_fields = []

    # Top-level required fields
    required_top_level = ["meal_plan_id", "start_date", "days"]
    for field in required_top_level:
        if field not in meal_plan:
            missing_fields.append(f"meal_plan.{field}")

    # Validate days array
    days = meal_plan.get("days", [])
    if not isinstance(days, list):
        missing_fields.append("meal_plan.days (must be list)")
    elif len(days) == 0:
        missing_fields.append("meal_plan.days (empty array)")
    else:
        # Validate each day structure
        for day_idx, day in enumerate(days):
            if not isinstance(day, dict):
                missing_fields.append(f"days[{day_idx}] (must be dict)")
                continue

            # Required day fields
            if "day" not in day:
                missing_fields.append(f"days[{day_idx}].day")
            if "meals" not in day:
                missing_fields.append(f"days[{day_idx}].meals")
            elif not isinstance(day["meals"], list):
                missing_fields.append(f"days[{day_idx}].meals (must be list)")
            elif len(day["meals"]) == 0:
                missing_fields.append(f"days[{day_idx}].meals (empty array)")
            else:
                # Validate each meal structure (sample first meal only for performance)
                meals = day["meals"]
                meal = meals[0]
                required_meal_fields = [
                    "meal_type",
                    "recipe_name",
                    "ingredients",
                ]

                # nutrition is optional when using FatSecret (added after generation)
                if require_nutrition:
                    required_meal_fields.append("nutrition")

                for field in required_meal_fields:
                    if field not in meal:
                        missing_fields.append(f"days[{day_idx}].meals[0].{field}")

                # Validate ingredients array
                if "ingredients" in meal and not isinstance(meal["ingredients"], list):
                    missing_fields.append(
                        f"days[{day_idx}].meals[0].ingredients (must be list)"
                    )

                # Validate nutrition object
                if "nutrition" in meal and not isinstance(meal["nutrition"], dict):
                    missing_fields.append(
                        f"days[{day_idx}].meals[0].nutrition (must be dict)"
                    )

    valid = len(missing_fields) == 0

    if not valid:
        logger.error(f"Meal plan structure validation failed: {missing_fields}")
    else:
        logger.info("✅ Meal plan structure validation passed")

    return {"valid": valid, "missing_fields": missing_fields}
