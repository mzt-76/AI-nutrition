"""Validate a single day's meal plan.

Runs allergen check (zero tolerance) and macro validation
for one day. Lighter than the full 4-level validate_meal_plan_complete.

Source: Extracted from src/nutrition/validators.py
"""

import json
import logging

from src.nutrition.validators import validate_allergens, validate_daily_macros

logger = logging.getLogger(__name__)


async def execute(**kwargs) -> str:
    """Validate one day.

    Args:
        day_plan: Day dict with meals, each with ingredients and nutrition.
            Format: {"day": "Lundi", "date": "...", "meals": [...], "daily_totals": {...}}
        user_allergens: List of allergen strings from user profile
        target_macros: Dict with calories, protein_g, carbs_g, fat_g
        protein_tolerance: Default 0.05 (±5%)
        other_tolerance: Default 0.10 (±10%)

    Returns:
        JSON: {
            "valid": bool,
            "violations": [...],
            "day": "Lundi",
            "allergen_violations": [...],
            "macro_violations": [...]
        }
    """
    day_plan = kwargs["day_plan"]
    user_allergens = kwargs.get("user_allergens", [])
    target_macros = kwargs.get("target_macros", {})
    protein_tolerance = kwargs.get("protein_tolerance", 0.05)
    other_tolerance = kwargs.get("other_tolerance", 0.10)

    day_name = day_plan.get("day", "Unknown")

    try:
        logger.info(f"Validating day: {day_name}")

        all_violations = []

        # 1. Allergen validation (zero tolerance)
        # Wrap day_plan in {"days": [...]} format expected by validate_allergens
        wrapped = {"days": [day_plan]}
        allergen_violations = validate_allergens(wrapped, user_allergens)
        all_violations.extend(allergen_violations)

        # 2. Macro validation
        macro_violations = []
        if target_macros and "daily_totals" in day_plan:
            daily_totals = day_plan["daily_totals"]

            # Validate protein with stricter tolerance
            protein_result = validate_daily_macros(
                daily_totals={"protein_g": daily_totals.get("protein_g", 0)},
                targets={"protein_g": target_macros.get("protein_g", 0)},
                tolerance=protein_tolerance,
            )
            if not protein_result["valid"]:
                macro_violations.extend(protein_result["violations"])

            # Validate other macros with wider tolerance
            other_result = validate_daily_macros(
                daily_totals={
                    "calories": daily_totals.get("calories", 0),
                    "carbs_g": daily_totals.get("carbs_g", 0),
                    "fat_g": daily_totals.get("fat_g", 0),
                },
                targets={
                    "calories": target_macros.get("calories", 0),
                    "carbs_g": target_macros.get("carbs_g", 0),
                    "fat_g": target_macros.get("fat_g", 0),
                },
                tolerance=other_tolerance,
            )
            if not other_result["valid"]:
                macro_violations.extend(other_result["violations"])

            all_violations.extend(macro_violations)

        valid = len(all_violations) == 0

        if valid:
            logger.info(f"✅ Day {day_name} validation passed")
        else:
            logger.warning(
                f"❌ Day {day_name} validation failed: {len(all_violations)} violations"
            )

        return json.dumps(
            {
                "valid": valid,
                "violations": all_violations,
                "day": day_name,
                "allergen_violations": allergen_violations,
                "macro_violations": macro_violations,
            },
            indent=2,
            ensure_ascii=False,
        )

    except ValueError as e:
        logger.error(f"Validation error in validate_day: {e}")
        return json.dumps({"error": str(e), "code": "VALIDATION_ERROR"})
    except Exception as e:
        logger.error(f"Unexpected error in validate_day: {e}", exc_info=True)
        return json.dumps({"error": "Internal error", "code": "SCRIPT_ERROR"})
