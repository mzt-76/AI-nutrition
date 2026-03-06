"""Generate a complete 7-day meal plan using Recipe DB + day-by-day generation.

Orchestrates: profile fetch → macro distribution → 7 × generate_day_plan
→ weekly summary → DB store → markdown document.

Cross-day variety tracking via accumulated used_recipe_ids prevents recipe
repetition across the week.

Source: Refactored from src/tools.py generate_weekly_meal_plan_tool
"""

import importlib.util
import json
import logging
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from src.nutrition.meal_distribution import MEAL_STRUCTURES
from src.nutrition.meal_planning import format_meal_plan_response
from src.nutrition.meal_distribution import calculate_meal_macros_distribution
from src.nutrition.meal_plan_formatter import format_meal_plan_as_markdown
from src.tools import fetch_my_profile_tool

logger = logging.getLogger(__name__)

_DAY_NAMES = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]


def _get_current_monday() -> str:
    """Return the Monday of the current week in YYYY-MM-DD format."""
    today = datetime.now()
    monday = today - timedelta(days=today.weekday())
    return monday.strftime("%Y-%m-%d")


def _import_sibling_script(script_name: str):
    """Import a sibling skill script by name.

    Args:
        script_name: Script filename without .py (e.g., "generate_day_plan")

    Returns:
        Loaded module with execute() function
    """
    script_path = Path(__file__).parent / f"{script_name}.py"
    spec = importlib.util.spec_from_file_location(
        f"meal_planning.{script_name}", script_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _parse_custom_requests(notes: str) -> dict:
    """Parse notes string into custom_requests dict keyed by day name.

    Simple parser: looks for French day name mentions followed by recipe descriptions.

    Args:
        notes: Free-text notes (e.g., "risotto champignons mardi, pizza vendredi")

    Returns:
        Dict of {day_name: {meal_type: recipe_request}} or empty dict
    """
    if not notes:
        return {}

    custom_requests: dict = {}
    notes_lower = notes.lower()

    day_map = {
        "lundi": "Lundi",
        "mardi": "Mardi",
        "mercredi": "Mercredi",
        "jeudi": "Jeudi",
        "vendredi": "Vendredi",
        "samedi": "Samedi",
        "dimanche": "Dimanche",
    }

    for day_fr, day_canonical in day_map.items():
        if day_fr in notes_lower:
            idx = notes_lower.index(day_fr)
            rest = notes[idx + len(day_fr) :].strip().lstrip(",:").strip()
            for other_day in day_map:
                if other_day in rest.lower():
                    cutoff = rest.lower().index(other_day)
                    rest = rest[:cutoff]
                    break
            rest = rest[:100].strip()
            if rest:
                custom_requests[day_canonical] = {"dejeuner": rest}

    return custom_requests


def _compute_weekly_summary(days: list[dict]) -> dict:
    """Compute average daily macros across all days.

    Args:
        days: List of day dicts with daily_totals

    Returns:
        Dict with average_calories, average_protein_g, average_carbs_g, average_fat_g
    """
    if not days:
        return {}

    n = len(days)
    totals = {"calories": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0}

    for day in days:
        dt = day.get("daily_totals", {})
        for key in totals:
            totals[key] += dt.get(key, 0.0)

    return {
        "average_calories": round(totals["calories"] / n, 1),
        "average_protein_g": round(totals["protein_g"] / n, 1),
        "average_carbs_g": round(totals["carbs_g"] / n, 1),
        "average_fat_g": round(totals["fat_g"] / n, 1),
    }


async def execute(**kwargs) -> str:
    """Generate 7-day meal plan with recipe DB + day-by-day generation.

    Args:
        supabase: Supabase client for database operations
        anthropic_client: AsyncAnthropic client for LLM fallback (Claude Sonnet 4.5)
        start_date: Start date in YYYY-MM-DD format
        target_calories_daily: Daily calorie target (None = use profile)
        target_protein_g: Daily protein target in grams
        target_carbs_g: Daily carbs target in grams
        target_fat_g: Daily fat target in grams
        meal_structure: Meal distribution pattern (default: 3_consequent_meals)
        num_days: Number of days to generate (default: 1). Use 7 for a full week.
        notes: Free-text preferences and custom recipe requests
            (e.g., "risotto mardi, pas de poisson vendredi")

    Returns:
        JSON with complete 7-day meal plan:
        {
            "success": true,
            "meal_plan_id": 123,
            "markdown_document": "/tmp/meal_plan_123_abc.md",
            "meal_plan": {
                "days": [...],
                "weekly_summary": {"average_calories": 2150, ...}
            },
            "summary": {"total_days": 7, "weekly_summary": {...}}
        }
    """
    supabase = kwargs["supabase"]
    anthropic_client = kwargs["anthropic_client"]
    user_id = kwargs.get("user_id")
    start_date = kwargs.get("start_date") or _get_current_monday()
    target_calories_daily = kwargs.get("target_calories_daily")
    target_protein_g = kwargs.get("target_protein_g")
    target_carbs_g = kwargs.get("target_carbs_g")
    target_fat_g = kwargs.get("target_fat_g")
    meal_structure = kwargs.get("meal_structure")  # None = auto-detect
    notes = kwargs.get("notes")
    num_days = int(kwargs.get("num_days", 1))
    batch_days = int(kwargs.get("batch_days") or 0) or None
    vary_breakfast = bool(kwargs.get("vary_breakfast", False))
    meal_preferences: dict[str, str] = kwargs.get("meal_preferences") or {}

    try:
        # Step 1: Validate meal structure (if explicitly provided)
        if meal_structure is not None and meal_structure not in MEAL_STRUCTURES:
            return json.dumps(
                {
                    "error": f"Invalid meal structure. Must be one of: {list(MEAL_STRUCTURES.keys())}",
                    "code": "VALIDATION_ERROR",
                }
            )

        # Step 2: Validate date format
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            return json.dumps(
                {
                    "error": "Invalid date format. Use YYYY-MM-DD (e.g., 2024-12-23)",
                    "code": "VALIDATION_ERROR",
                }
            )

        # Step 3: Fetch user profile
        profile_result = await fetch_my_profile_tool(supabase, user_id=user_id)
        profile_data = json.loads(profile_result)

        if "error" in profile_data:
            return json.dumps(
                {
                    "error": "Cannot generate meal plan: user profile incomplete or not found",
                    "code": "PROFILE_ERROR",
                    "details": profile_data,
                }
            )

        # Step 4: Resolve nutritional targets (from args or profile)
        calories = target_calories_daily or profile_data.get("target_calories")
        protein = target_protein_g or profile_data.get("target_protein_g")
        carbs = target_carbs_g or profile_data.get("target_carbs_g")
        fat = target_fat_g or profile_data.get("target_fat_g")

        if not all([calories, protein, carbs, fat]):
            return json.dumps(
                {
                    "error": "Missing nutritional targets. Provide targets or complete profile.",
                    "code": "MISSING_TARGETS",
                }
            )

        # Step 4b: Auto-detect meal structure if not explicitly set
        if not meal_structure:
            if calories >= 2500:
                meal_structure = "3_meals_1_preworkout"
                logger.info(
                    f"Auto-selected meal_structure={meal_structure} "
                    f"(calories={calories} >= 2500)"
                )
            else:
                meal_structure = "3_consequent_meals"
                logger.info(
                    f"Auto-selected meal_structure={meal_structure} "
                    f"(calories={calories} < 2500)"
                )

        logger.info(
            f"Generating weekly meal plan: start={start_date}, structure={meal_structure}"
        )

        # Step 5: Calculate meal-by-meal macro distribution
        meal_macros_distribution = calculate_meal_macros_distribution(
            daily_calories=calories,
            daily_protein_g=protein,
            daily_carbs_g=carbs,
            daily_fat_g=fat,
            meal_structure=meal_structure,
        )
        meal_targets = meal_macros_distribution["meals"]
        logger.info(f"Meal distribution: {len(meal_targets)} meals/day")

        # Step 6: Parse notes into per-day custom recipe requests
        custom_requests = _parse_custom_requests(notes) if notes else {}
        if custom_requests:
            logger.info(f"Custom recipe requests: {list(custom_requests.keys())}")
        if meal_preferences:
            logger.info(f"Meal preferences (all days): {meal_preferences}")

        # Step 7: Load generate_day_plan sibling script
        generate_day_plan = _import_sibling_script("generate_day_plan")

        # Step 8: Generate days one at a time (variety tracked via used_recipe_ids)
        all_days = []
        used_recipe_ids: list[str] = []

        # Batch cooking state
        batch_breakfast_recipe_id: str | None = None
        batch_lunch_recipe_id: str | None = None
        batch_dinner_recipe_id: str | None = None
        batch_counter = 0

        for day_idx in range(num_days):
            day_name = _DAY_NAMES[day_idx % 7]
            day_date = (start_dt + timedelta(days=day_idx)).strftime("%Y-%m-%d")

            logger.info(f"Generating {day_name} ({day_date})...")

            # Build batch_recipe_ids for this day
            batch_recipe_ids: dict[str, str] = {}

            # Breakfast: same every day unless vary_breakfast=True
            if not vary_breakfast and batch_breakfast_recipe_id:
                batch_recipe_ids["petit-dejeuner"] = batch_breakfast_recipe_id

            # Lunch & dinner: batch blocks of N days
            if batch_days and batch_counter < batch_days:
                if batch_lunch_recipe_id:
                    batch_recipe_ids["dejeuner"] = batch_lunch_recipe_id
                if batch_dinner_recipe_id:
                    batch_recipe_ids["diner"] = batch_dinner_recipe_id
                batch_counter += 1
            else:
                # Reset batch block — new recipes will be selected
                batch_lunch_recipe_id = None
                batch_dinner_recipe_id = None
                batch_counter = 1 if batch_days else 0

            # Merge meal_preferences (global) + day-specific custom requests
            # Day-specific overrides take priority over global preferences
            # But batch_recipe_ids take priority over both (already handled downstream)
            day_custom = dict(meal_preferences)  # base: global preferences
            day_custom.update(custom_requests.get(day_name, {}))  # override per-day

            day_result_str = await generate_day_plan.execute(
                supabase=supabase,
                anthropic_client=anthropic_client,
                day_index=day_idx,
                day_name=day_name,
                day_date=day_date,
                meal_targets=meal_targets,
                user_profile=profile_data,
                exclude_recipe_ids=used_recipe_ids,
                custom_requests=day_custom,
                batch_recipe_ids=batch_recipe_ids,
            )
            day_result = json.loads(day_result_str)

            if not day_result.get("success"):
                logger.error(
                    f"Day {day_name} generation failed: {day_result.get('error')}"
                )
                return json.dumps(
                    {
                        "error": f"Failed to generate day plan for {day_name}",
                        "code": "DAY_GENERATION_FAILED",
                        "day": day_name,
                        "details": day_result,
                    }
                )

            all_days.append(day_result["day"])
            used_recipe_ids.extend(day_result.get("recipes_used", []))

            # Capture recipe IDs for batch tracking
            ids_by_mt = day_result.get("recipe_ids_by_meal_type", {})

            # Capture breakfast ID from first day (for default same-breakfast behavior)
            if day_idx == 0 and not vary_breakfast:
                batch_breakfast_recipe_id = ids_by_mt.get("petit-dejeuner")

            # Capture lunch/dinner IDs at start of each new batch block
            if batch_days and batch_counter == 1:
                batch_lunch_recipe_id = ids_by_mt.get("dejeuner")
                batch_dinner_recipe_id = ids_by_mt.get("diner")

            logger.info(
                f"  {day_name} ✅ ({day_result['day']['daily_totals']['calories']:.0f} kcal)"
            )

        # Step 9: Compute weekly summary from daily_totals
        weekly_summary = _compute_weekly_summary(all_days)
        meal_plan_json = {"days": all_days, "weekly_summary": weekly_summary}

        # Step 10: Store meal plan in database
        meal_plan_record = {
            "week_start": start_date,
            "plan_data": meal_plan_json,
            "target_calories_daily": calories,
            "target_protein_g": protein,
            "target_carbs_g": carbs,
            "target_fat_g": fat,
            "notes": notes,
        }
        if user_id:
            meal_plan_record["user_id"] = user_id

        db_response = supabase.table("meal_plans").insert(meal_plan_record).execute()

        if db_response.data:
            meal_plan_id = db_response.data[0].get("id", 0)
            store_success = True
            logger.info(f"Meal plan stored in database (ID: {meal_plan_id})")
        else:
            meal_plan_id = 0
            store_success = False
            logger.warning("Meal plan generated but storage failed")

        # Step 11: Generate downloadable Markdown document
        markdown_doc = format_meal_plan_as_markdown(meal_plan_json, meal_plan_id)

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".md",
            delete=False,
            encoding="utf-8",
            prefix=f"meal_plan_{meal_plan_id}_",
        ) as f:
            f.write(markdown_doc)
            markdown_path = f.name

        logger.info(f"Markdown document generated: {markdown_path}")

        response_data = json.loads(
            format_meal_plan_response(meal_plan_json, store_success)
        )
        response_data["markdown_document"] = markdown_path
        response_data["meal_plan_id"] = meal_plan_id

        return json.dumps(response_data, indent=2, ensure_ascii=False)

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return json.dumps({"error": str(e), "code": "VALIDATION_ERROR"})
    except Exception as e:
        logger.error(f"Unexpected error generating weekly plan: {e}", exc_info=True)
        return json.dumps(
            {"error": "Internal error generating meal plan", "code": "GENERATION_ERROR"}
        )
