"""
Safety validation functions for meal planning.

Enforces zero-tolerance allergen policy and validates meal plan structure.
"""

import logging
import re
import unicodedata

from src.nutrition.constants import (
    MACRO_TOLERANCE_CALORIES,
    MACRO_TOLERANCE_CARBS,
    MACRO_TOLERANCE_FAT,
    MACRO_TOLERANCE_PROTEIN,
)

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
        "pâte feuilletée",
        "pâte brisée",
        "béchamel",
        "gratin",
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
        "pâte feuilletée",
        "pâte brisée",
        "pâte sablée",
        "croûte",
        "panure",
        "chapelure",
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


# ---------------------------------------------------------------------------
# Prompt injection sanitisation
# ---------------------------------------------------------------------------
_INJECTION_PATTERNS = re.compile(
    r"(?:ignore previous|ignore above|disregard|new instructions|system prompt"
    r"|you are now|forget everything|override|```|<script|<\|"
    r"|\{\{|\{%|role:|assistant:|human:|\n\n)",
    re.IGNORECASE,
)


def sanitize_user_text(text: str, max_length: int, context: str = "user_input") -> str:
    """Sanitize free-form user text before injection into LLM prompts.

    Steps:
        1. NFKC-normalize (collapse homoglyphs)
        2. Collapse whitespace (newlines, tabs → single space)
        3. Truncate to *max_length*
        4. Reject if any _INJECTION_PATTERNS match

    Args:
        text: Raw user text.
        max_length: Maximum allowed length after normalisation.
        context: Label for log messages (e.g. "recipe_request").

    Returns:
        Sanitized text (safe to embed in prompts).

    Raises:
        ValueError: If an injection pattern is detected.
    """
    # NFKC normalisation (e.g. fullwidth chars → ASCII, homoglyphs collapsed)
    text = unicodedata.normalize("NFKC", text)
    # Collapse whitespace
    text = re.sub(r"[\n\r\t]+", " ", text).strip()
    # Truncate
    text = text[:max_length]

    if _INJECTION_PATTERNS.search(text):
        logger.warning(
            "Prompt injection attempt blocked in %s: %r",
            context,
            text[:80],
        )
        raise ValueError("Requête invalide")

    return text


# ---------------------------------------------------------------------------
# Allergen helpers
# ---------------------------------------------------------------------------


def matches_allergen(ingredient_name: str, user_allergens: list[str]) -> list[str]:
    """Check if an ingredient name matches any user allergen.

    Uses ALLERGEN_FAMILIES for family-based detection and ALLERGEN_FALSE_POSITIVES
    to avoid false matches (e.g. "coconut" is not a tree nut).

    Args:
        ingredient_name: Ingredient name to check
        user_allergens: List of allergen names (e.g. ["arachides", "lactose"])

    Returns:
        List of matched allergen names (empty if safe)
    """
    if not user_allergens or not ingredient_name:
        return []

    name_lower = ingredient_name.lower().strip()
    normalized_allergens = [a.lower().strip() for a in user_allergens]

    # Check false positives first
    for fp_keyword, fp_allergen in ALLERGEN_FALSE_POSITIVES.items():
        if fp_keyword in name_lower and fp_allergen in normalized_allergens:
            return []

    matched: list[str] = []
    for allergen in normalized_allergens:
        keywords = [allergen]
        if allergen in ALLERGEN_FAMILIES:
            keywords.extend(ALLERGEN_FAMILIES[allergen])
        for keyword in keywords:
            if keyword.lower() in name_lower:
                matched.append(allergen)
                break

    return matched


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
                raw_name = ingredient.get("name", "")
                # Handle None or non-string values
                if raw_name is None or not isinstance(raw_name, str):
                    continue
                ingredient_name = raw_name.lower().strip()

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


def validate_recipe_allergens(recipe: dict, user_allergens: list[str]) -> list[str]:
    """Check a single recipe for allergen violations.

    Convenience wrapper around validate_allergens() that avoids the
    boilerplate of wrapping a recipe in {days:[{meals:[...]}]}.

    Args:
        recipe: Recipe dict with an ``ingredients`` list of dicts containing ``name``.
        user_allergens: List of allergen names (e.g. ``["arachides", "lactose"]``).

    Returns:
        List of violation strings (empty if safe).
    """
    if not user_allergens:
        return []
    wrapped = {
        "days": [
            {
                "day": "generated",
                "meals": [
                    {
                        "recipe_name": recipe.get("name", ""),
                        "ingredients": recipe.get("ingredients", []),
                    }
                ],
            }
        ]
    }
    return validate_allergens(wrapped, user_allergens)


def find_worst_meal(
    meals: list[dict],
    daily_totals: dict,
    target_macros: dict,
) -> int:
    """Identify the meal index contributing most to the worst macro violation.

    Pure scoring function — no I/O.  Higher score = more responsible for
    the total deviation from targets.

    Args:
        meals: List of meal dicts, each with a ``nutrition`` sub-dict.
        daily_totals: Aggregated daily nutrition (calories, protein_g, …).
        target_macros: Target daily nutrition values.

    Returns:
        Index of the worst-offending meal (0 if *meals* is empty).
    """
    if not meals:
        return 0

    worst_idx = 0
    worst_score = -1.0

    for i, meal in enumerate(meals):
        nutrition = meal.get("nutrition", {})
        score = 0.0
        for macro in ("calories", "protein_g", "carbs_g", "fat_g"):
            try:
                target = float(target_macros.get(macro, 0) or 0)
                if target <= 0:
                    continue
                actual = float(daily_totals.get(macro, 0) or 0)
                deviation = actual - target
                meal_contribution = float(nutrition.get(macro, 0) or 0)
                if deviation > 0:
                    score += (meal_contribution / target) * abs(deviation / target)
                else:
                    expected_share = target / max(len(meals), 1)
                    if expected_share > 0 and meal_contribution < expected_share:
                        score += abs(deviation / target) * (
                            1 - meal_contribution / expected_share
                        )
            except (TypeError, ValueError):
                continue

        if score > worst_score:
            worst_score = score
            worst_idx = i

    return worst_idx


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

    return {"valid": valid, "violations": violations}


def validate_meal_plan_macros(
    meal_plan: dict,
    target_calories: float,
    target_protein: float,
    target_carbs: float,
    target_fat: float,
    protein_tolerance: float = MACRO_TOLERANCE_PROTEIN,
    carbs_tolerance: float = MACRO_TOLERANCE_CARBS,
    fat_tolerance: float = MACRO_TOLERANCE_FAT,
    calorie_tolerance: float = MACRO_TOLERANCE_CALORIES,
) -> dict:
    """
    Validate all days in a meal plan have macros within tolerance.

    Uses different tolerances for protein (stricter) vs other macros.

    Args:
        meal_plan: Full meal plan with days array
        target_calories: Daily calorie target
        target_protein: Daily protein target in grams
        target_carbs: Daily carbs target in grams
        target_fat: Daily fat target in grams
        protein_tolerance: Tolerance for protein (default 5%)
        carbs_tolerance: Tolerance for carbs (default 10%)
        fat_tolerance: Tolerance for fat (default 10%)
        calorie_tolerance: Tolerance for calories (default 10%)

    Returns:
        Dict with validation result:
        {
            "valid": bool,
            "day_results": list of per-day results,
            "violations": list of all violations across days
        }

    Example:
        >>> result = validate_meal_plan_macros(plan, 2000, 150, 200, 70)
        >>> result["valid"]
        True
    """
    days = meal_plan.get("days", [])
    all_violations = []
    day_results = []

    for day_idx, day_data in enumerate(days):
        daily_totals = day_data.get("daily_totals", {})

        # Normalize key names (support both protein and protein_g formats)
        normalized_totals = {
            "calories": daily_totals.get(
                "calories", daily_totals.get("total_calories", 0)
            ),
            "protein_g": daily_totals.get("protein_g", daily_totals.get("protein", 0)),
            "carbs_g": daily_totals.get("carbs_g", daily_totals.get("carbs", 0)),
            "fat_g": daily_totals.get("fat_g", daily_totals.get("fat", 0)),
        }

        # Validate each macro with appropriate tolerance
        day_violations = []

        # Calories
        cal_lower = target_calories * (1 - calorie_tolerance)
        cal_upper = target_calories * (1 + calorie_tolerance)
        actual_cal = normalized_totals["calories"]
        if not (cal_lower <= actual_cal <= cal_upper):
            dev = ((actual_cal - target_calories) / target_calories) * 100
            day_violations.append(
                f"Day {day_idx + 1} calories: {actual_cal:.0f} (target: {target_calories:.0f}, "
                f"deviation: {dev:+.1f}%)"
            )

        # Protein (stricter tolerance)
        prot_lower = target_protein * (1 - protein_tolerance)
        prot_upper = target_protein * (1 + protein_tolerance)
        actual_prot = normalized_totals["protein_g"]
        if not (prot_lower <= actual_prot <= prot_upper):
            dev = ((actual_prot - target_protein) / target_protein) * 100
            day_violations.append(
                f"Day {day_idx + 1} protein: {actual_prot:.0f}g (target: {target_protein:.0f}g, "
                f"deviation: {dev:+.1f}%)"
            )

        # Carbs
        carbs_lower = target_carbs * (1 - carbs_tolerance)
        carbs_upper = target_carbs * (1 + carbs_tolerance)
        actual_carbs = normalized_totals["carbs_g"]
        if not (carbs_lower <= actual_carbs <= carbs_upper):
            dev = ((actual_carbs - target_carbs) / target_carbs) * 100
            day_violations.append(
                f"Day {day_idx + 1} carbs: {actual_carbs:.0f}g (target: {target_carbs:.0f}g, "
                f"deviation: {dev:+.1f}%)"
            )

        # Fat
        fat_lower = target_fat * (1 - fat_tolerance)
        fat_upper = target_fat * (1 + fat_tolerance)
        actual_fat = normalized_totals["fat_g"]
        if not (fat_lower <= actual_fat <= fat_upper):
            dev = ((actual_fat - target_fat) / target_fat) * 100
            day_violations.append(
                f"Day {day_idx + 1} fat: {actual_fat:.0f}g (target: {target_fat:.0f}g, "
                f"deviation: {dev:+.1f}%)"
            )

        day_results.append(
            {
                "day": day_idx + 1,
                "valid": len(day_violations) == 0,
                "violations": day_violations,
            }
        )
        all_violations.extend(day_violations)

    all_valid = len(all_violations) == 0

    if all_valid:
        logger.info("✅ All days pass macro validation")
    else:
        logger.warning(f"Macro validation issues in {len(all_violations)} instances")

    return {
        "valid": all_valid,
        "day_results": day_results,
        "violations": all_violations,
    }


def validate_meal_plan_structure(
    meal_plan: dict, require_nutrition: bool = True
) -> dict:
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
                # Validate every meal structure
                meals = day["meals"]
                for meal_idx, meal in enumerate(meals):
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
                            missing_fields.append(
                                f"days[{day_idx}].meals[{meal_idx}].{field}"
                            )

                    # Validate ingredients array
                    if "ingredients" in meal and not isinstance(
                        meal["ingredients"], list
                    ):
                        missing_fields.append(
                            f"days[{day_idx}].meals[{meal_idx}].ingredients (must be list)"
                        )

                    # Validate nutrition object
                    if "nutrition" in meal and not isinstance(meal["nutrition"], dict):
                        missing_fields.append(
                            f"days[{day_idx}].meals[{meal_idx}].nutrition (must be dict)"
                        )

    valid = len(missing_fields) == 0

    if not valid:
        logger.error(f"Meal plan structure validation failed: {missing_fields}")
    else:
        logger.info("✅ Meal plan structure validation passed")

    return {"valid": valid, "missing_fields": missing_fields}


def validate_meal_plan_complete(
    meal_plan: dict,
    target_macros: dict,
    user_allergens: list[str],
    meal_structure: str,
    protein_tolerance: float = MACRO_TOLERANCE_PROTEIN,
    fat_tolerance: float = MACRO_TOLERANCE_FAT,
    calorie_tolerance: float = MACRO_TOLERANCE_CALORIES,
    carbs_tolerance: float = MACRO_TOLERANCE_CARBS,
) -> dict:
    """
    Comprehensive 4-level validation of meal plan with custom tolerances.

    This is the master validation function that runs all validation checks
    in sequence. Returns detailed results for each level.

    Validation Levels:
    1. Structure: 7 days, required fields present
    2. Allergens: Zero tolerance for user allergens
    3. Macros: Per-macro tolerances from constants.py
    4. Completeness: Correct number of meals per day

    Args:
        meal_plan: Complete meal plan dict with structure:
            {
                "days": [
                    {
                        "day": "Lundi",
                        "date": "YYYY-MM-DD",
                        "meals": [...],
                        "daily_totals": {"calories": int, "protein_g": int, ...}
                    }
                ],
                "meal_structure": "3_meals_2_snacks"
            }
        target_macros: Daily target macros dict with keys:
            - calories, protein_g, carbs_g, fat_g
        user_allergens: List of user allergen strings (e.g., ["peanuts", "lactose"])
        meal_structure: Meal structure key (e.g., "3_meals_2_snacks")
        protein_tolerance: Protein tolerance (default: ±5% from constants)
        fat_tolerance: Fat tolerance (default: ±10% from constants)
        calorie_tolerance: Calorie tolerance (default: ±10% from constants)
        carbs_tolerance: Carbs tolerance (default: ±20% from constants)

    Returns:
        Dict with validation results:
        {
            "valid": bool,  # True only if ALL levels pass
            "validations": {
                "structure": {"valid": bool, "missing_fields": []},
                "allergens": {"valid": bool, "violations": []},
                "macros": {"valid": bool, "daily_deviations": []},
                "completeness": {"valid": bool, "errors": []}
            }
        }

    Example:
        >>> plan = {
        ...     "days": [...],  # 7 days with meals
        ...     "meal_structure": "3_meals_2_snacks"
        ... }
        >>> targets = {"calories": 3000, "protein_g": 180, "carbs_g": 375, "fat_g": 83}
        >>> result = validate_meal_plan_complete(
        ...     plan, targets, ["peanuts"], "3_meals_2_snacks"
        ... )
        >>> result["valid"]
        True
        >>> result["validations"]["allergens"]["valid"]
        True

    References:
        - ISSN Position Stand (2017): ±5% protein tolerance for athletes
        - Plan: refactor-meal-plan-generation-workflow.md
    """
    logger.info(
        f"Starting 4-level meal plan validation: "
        f"protein=±{protein_tolerance*100}%, fat=±{fat_tolerance*100}%, "
        f"calories=±{calorie_tolerance*100}%, carbs=±{carbs_tolerance*100}%"
    )

    validations = {}

    # Level 1: Structure validation
    logger.info("Level 1/4: Validating structure...")
    structure_result = validate_meal_plan_structure(meal_plan)
    validations["structure"] = structure_result

    # Level 2: Allergen validation
    logger.info("Level 2/4: Validating allergens...")
    allergen_violations = validate_allergens(meal_plan, user_allergens)
    # Wrap list result in dict format for consistency
    validations["allergens"] = {
        "valid": len(allergen_violations) == 0,
        "violations": allergen_violations,
    }

    # Level 3: Macro validation with custom tolerances
    logger.info("Level 3/4: Validating macros...")
    macro_result = validate_meal_plan_macros(
        meal_plan,
        target_macros["calories"],
        target_macros["protein_g"],
        target_macros["carbs_g"],
        target_macros["fat_g"],
        protein_tolerance=protein_tolerance,
        carbs_tolerance=carbs_tolerance,
        fat_tolerance=fat_tolerance,
        calorie_tolerance=calorie_tolerance,
    )
    validations["macros"] = macro_result

    # Level 4: Completeness validation (correct number of meals)
    logger.info("Level 4/4: Validating completeness...")
    completeness_result = validate_meal_plan_completeness(meal_plan, meal_structure)
    validations["completeness"] = completeness_result

    # Overall validation passes only if ALL levels pass
    all_valid = all(
        validation.get("valid", False) for validation in validations.values()
    )

    if all_valid:
        logger.info("✅ ALL validation levels passed")
    else:
        failed_levels = [
            level
            for level, result in validations.items()
            if not result.get("valid", False)
        ]
        logger.error(f"❌ Validation FAILED at levels: {failed_levels}")

    return {
        "valid": all_valid,
        "validations": validations,
    }


def validate_meal_plan_completeness(meal_plan: dict, meal_structure: str) -> dict:
    """
    Validate that each day has the correct number of meals for the structure.

    Args:
        meal_plan: Meal plan dict with days array
        meal_structure: Expected meal structure (e.g., "3_meals_2_snacks")

    Returns:
        Dict with validation result:
        {
            "valid": bool,
            "errors": []  # List of error messages if validation fails
        }

    Example:
        >>> plan = {"days": [{"meals": [{}, {}, {}]}]}
        >>> result = validate_meal_plan_completeness(plan, "3_consequent_meals")
        >>> result["valid"]
        True
    """
    from src.nutrition.meal_distribution import MEAL_STRUCTURES

    errors = []

    # Get expected number of meals
    if meal_structure not in MEAL_STRUCTURES:
        errors.append(f"Unknown meal structure: {meal_structure}")
        return {"valid": False, "errors": errors}

    expected_meal_count = len(MEAL_STRUCTURES[meal_structure]["meals"])

    # Check each day
    days = meal_plan.get("days", [])
    for day_idx, day_data in enumerate(days):
        meals = day_data.get("meals", [])
        actual_count = len(meals)

        if actual_count != expected_meal_count:
            day_name = day_data.get("day", f"Day {day_idx+1}")
            errors.append(
                f"{day_name}: Expected {expected_meal_count} meals "
                f"for {meal_structure}, got {actual_count}"
            )

    valid = len(errors) == 0

    if not valid:
        logger.error(f"Completeness validation failed: {errors}")
    else:
        logger.info(
            f"✅ Completeness validation passed: {expected_meal_count} meals/day"
        )

    return {"valid": valid, "errors": errors}
