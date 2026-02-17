"""
Log meal plan validation errors for debugging and analysis.

Creates comprehensive JSON logs when meal plan validation fails, including
all validation results, target vs actual macros, full meal plan data, and
user constraints. Logs are timestamped and stored in logs/ directory.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def log_meal_plan_validation_error(
    validation_result: dict,
    meal_plan: dict,
    target_macros: dict,
    user_allergens: list[str],
    meal_structure: str,
) -> Path:
    """
    Save comprehensive validation failure details to JSON log file.

    Creates logs/meal_plan_errors_{timestamp}.json with complete context
    for debugging. Logs include:
    - Timestamp and validation result (all 4 levels)
    - Target vs actual macros for each day
    - Complete meal plan data
    - User allergens and meal structure

    Args:
        validation_result: Result from validate_meal_plan_complete() with structure:
            {
                "valid": False,
                "validations": {
                    "structure": {"valid": bool, "missing_fields": []},
                    "allergens": {"valid": bool, "violations": []},
                    "macros": {"valid": bool, "daily_deviations": []},
                    "completeness": {"valid": bool, "errors": []}
                }
            }
        meal_plan: Complete meal plan dictionary (from LLM)
        target_macros: Daily macro targets dict with keys:
            - calories, protein_g, carbs_g, fat_g
        user_allergens: List of user allergen strings
        meal_structure: Meal structure key (e.g., "3_meals_2_snacks")

    Returns:
        Path object pointing to created log file

    Raises:
        OSError: If unable to create or write log file

    Example:
        >>> validation = {"valid": False, "validations": {...}}
        >>> plan = {"days": [...]}
        >>> targets = {"calories": 3000, "protein_g": 180}
        >>> path = log_meal_plan_validation_error(
        ...     validation, plan, targets, ["peanuts"], "3_meals_2_snacks"
        ... )
        >>> path.exists()
        True
    """
    # Generate timestamp-based filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    logs_dir = Path(__file__).parent.parent / "logs"
    logs_dir.mkdir(exist_ok=True)
    log_file = logs_dir / f"meal_plan_errors_{timestamp}.json"

    # Extract daily totals for comparison
    days = meal_plan.get("days", [])
    daily_comparisons = []

    for day_data in days:
        day_name = day_data.get("day", "Unknown")
        day_date = day_data.get("date", "")
        daily_totals = day_data.get("daily_totals", {})

        actual_cals = daily_totals.get("calories", 0)
        actual_prot = daily_totals.get("protein_g", 0)
        actual_carbs = daily_totals.get("carbs_g", 0)
        actual_fat = daily_totals.get("fat_g", 0)

        target_cals = target_macros.get("calories", 0)
        target_prot = target_macros.get("protein_g", 0)
        target_carbs = target_macros.get("carbs_g", 0)
        target_fat = target_macros.get("fat_g", 0)

        # Calculate deviations
        cal_deviation = (
            ((actual_cals - target_cals) / target_cals * 100) if target_cals > 0 else 0
        )
        prot_deviation = (
            ((actual_prot - target_prot) / target_prot * 100) if target_prot > 0 else 0
        )
        carbs_deviation = (
            ((actual_carbs - target_carbs) / target_carbs * 100)
            if target_carbs > 0
            else 0
        )
        fat_deviation = (
            ((actual_fat - target_fat) / target_fat * 100) if target_fat > 0 else 0
        )

        daily_comparisons.append(
            {
                "day": day_name,
                "date": day_date,
                "target": {
                    "calories": target_cals,
                    "protein_g": target_prot,
                    "carbs_g": target_carbs,
                    "fat_g": target_fat,
                },
                "actual": {
                    "calories": actual_cals,
                    "protein_g": actual_prot,
                    "carbs_g": actual_carbs,
                    "fat_g": actual_fat,
                },
                "deviations_percent": {
                    "calories": round(cal_deviation, 2),
                    "protein_g": round(prot_deviation, 2),
                    "carbs_g": round(carbs_deviation, 2),
                    "fat_g": round(fat_deviation, 2),
                },
            }
        )

    # Build comprehensive error log
    error_log = {
        "timestamp": datetime.now().isoformat(),
        "log_type": "meal_plan_validation_error",
        "validation_result": validation_result,
        "user_constraints": {
            "allergens": user_allergens,
            "meal_structure": meal_structure,
            "target_macros": target_macros,
        },
        "daily_comparisons": daily_comparisons,
        "full_meal_plan": meal_plan,
        "summary": {
            "num_days": len(days),
            "validation_failed_reasons": [
                level
                for level, result in validation_result.get("validations", {}).items()
                if not result.get("valid", True)
            ],
        },
    }

    # Write to file with pretty formatting
    try:
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(error_log, f, indent=2, ensure_ascii=False)

        logger.error(
            f"🚨 Meal plan validation failed. Full error log saved to: {log_file}"
        )
        logger.error(
            f"Failed validation levels: {error_log['summary']['validation_failed_reasons']}"
        )

        return log_file

    except OSError as e:
        logger.error(f"Failed to write error log to {log_file}: {e}")
        raise


class MealPlanErrorLogger:
    """
    Logger class for meal plan generation errors.

    Provides methods to log various types of errors during meal plan
    generation and validation with configurable log directory.

    Attributes:
        log_dir: Directory for error log files

    Example:
        >>> logger = MealPlanErrorLogger(log_dir="/tmp/logs")
        >>> logger.log_generation_error("timeout", "LLM timed out", {"attempt": 1})
    """

    def __init__(self, log_dir: str | None = None) -> None:
        """
        Initialize the error logger.

        Args:
            log_dir: Directory for log files (default: ./logs)
        """
        if log_dir:
            self.log_dir = Path(log_dir)
        else:
            self.log_dir = Path(__file__).parent.parent / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def log_generation_error(
        self,
        error_type: str,
        error_message: str,
        context: dict | None = None,
    ) -> Path:
        """
        Log a general meal plan generation error.

        Args:
            error_type: Category of error (e.g., "validation_failed", "timeout")
            error_message: Human-readable error description
            context: Additional context dict (user_id, attempt, etc.)

        Returns:
            Path to the created log file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = self.log_dir / f"meal_plan_errors_{timestamp}.json"

        error_log = {
            "timestamp": datetime.now().isoformat(),
            "error_type": error_type,
            "error_message": error_message,
            "context": context or {},
        }

        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(error_log, f, indent=2, ensure_ascii=False)

        logger.error(f"Error logged to: {log_file}")
        return log_file

    def log_validation_failure(
        self,
        validation_errors: list[str],
        meal_plan_summary: dict,
        targets: dict,
    ) -> Path:
        """
        Log a validation failure with details.

        Args:
            validation_errors: List of validation error messages
            meal_plan_summary: Summary of the failed meal plan
            targets: Target macros dict

        Returns:
            Path to the created log file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = self.log_dir / f"meal_plan_errors_{timestamp}.json"

        error_log = {
            "timestamp": datetime.now().isoformat(),
            "error_type": "validation_failure",
            "validation_errors": validation_errors,
            "meal_plan_summary": meal_plan_summary,
            "targets": targets,
        }

        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(error_log, f, indent=2, ensure_ascii=False)

        logger.error(f"Validation failure logged to: {log_file}")
        return log_file


def list_recent_error_logs(limit: int = 10) -> list[Path]:
    """
    List most recent error log files.

    Args:
        limit: Maximum number of files to return (default: 10)

    Returns:
        List of Path objects sorted by modification time (newest first)

    Example:
        >>> recent_logs = list_recent_error_logs(limit=5)
        >>> len(recent_logs) <= 5
        True
    """
    logs_dir = Path(__file__).parent.parent / "logs"

    if not logs_dir.exists():
        return []

    # Find all error log files
    error_logs = list(logs_dir.glob("meal_plan_errors_*.json"))

    # Sort by modification time (newest first)
    error_logs.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    return error_logs[:limit]
