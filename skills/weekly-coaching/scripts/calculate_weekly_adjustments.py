"""Synthesize weekly feedback and generate personalized nutritional adjustments.

Utility script — can be imported by agent tool wrapper or run standalone.
Analyzes real-world outcomes against goal targets, detects individual patterns,
and generates science-backed recommendations with confidence scoring.

Source: Extracted from src/tools.py calculate_weekly_adjustments_tool
References:
    Fothergill et al. (2016): Adaptive Thermogenesis
    Helms et al. (2014): Body composition changes in resistance training
    ISSN Position Stand (2017): Macronutrient recommendations
"""

import json
import logging
from datetime import datetime, timedelta

from src.nutrition.adjustments import (
    analyze_weight_trend,
    detect_metabolic_adaptation,
    detect_adherence_patterns,
    generate_calorie_adjustment,
    generate_macro_adjustments,
    detect_red_flags,
)
from src.nutrition.feedback_extraction import (
    validate_feedback_metrics,
    check_feedback_completeness,
)

logger = logging.getLogger(__name__)


async def execute(**kwargs) -> str:
    """Analyze weekly check-in and generate personalized adjustments.

    Args:
        supabase: Supabase client for database access.
        embedding_client: OpenAI async client for embeddings.
        weight_start_kg: Weight at start of week (kg).
        weight_end_kg: Weight at end of week (kg).
        adherence_percent: Percentage of plan followed (0-100%).
        hunger_level: Reported hunger ("low", "medium", "high").
        energy_level: Reported energy ("low", "medium", "high").
        sleep_quality: Sleep quality ("poor", "fair", "good", "excellent").
        cravings: List of craving types if any.
        notes: Free-text observations from the week.

    Returns:
        JSON string with analysis, adjustments, red flags, and confidence.
    """
    supabase = kwargs["supabase"]
    user_id = kwargs.get("user_id")
    # embedding_client accepted for future use (e.g., RAG-based coaching)
    kwargs.get("embedding_client")
    weight_start_kg = kwargs["weight_start_kg"]
    weight_end_kg = kwargs["weight_end_kg"]
    adherence_percent = kwargs["adherence_percent"]
    hunger_level = kwargs.get("hunger_level", "medium")
    energy_level = kwargs.get("energy_level", "medium")
    sleep_quality = kwargs.get("sleep_quality", "good")
    cravings = kwargs.get("cravings")
    notes = kwargs.get("notes", "")

    try:
        logger.info(
            f"Weekly adjustment synthesis starting: weight {weight_start_kg}→{weight_end_kg}kg, adherence {adherence_percent}%"
        )

        # Step 1: Validate and parse input
        feedback_data = validate_feedback_metrics(
            {
                "weight_start_kg": weight_start_kg,
                "weight_end_kg": weight_end_kg,
                "adherence_percent": adherence_percent,
                "hunger_level": hunger_level,
                "energy_level": energy_level,
                "sleep_quality": sleep_quality,
                "cravings": cravings or [],
                "notes": notes,
            }
        )

        completeness = check_feedback_completeness(feedback_data)
        logger.info(
            f"Feedback completeness: {completeness['quality']} ({completeness['completeness_percent']}%)"
        )

        # Step 2: Fetch current profile
        if not user_id:
            return json.dumps({"error": "No user_id provided", "code": "NO_USER_ID"})
        profile_response = await (
            supabase.table("user_profiles")
            .select("*")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )
        if not profile_response.data:
            return json.dumps(
                {"error": "No user profile found", "code": "PROFILE_NOT_FOUND"}
            )
        profile = profile_response.data[0]
        goal = profile.get("primary_goal", "maintenance")
        current_protein_g = profile.get("current_protein_g", 150)

        # Step 3: Fetch historical data (past 4 weeks, excluding baseline)
        feedback_query = supabase.table("weekly_feedback").select("*")
        if user_id:
            feedback_query = feedback_query.eq("user_id", user_id)
        history_response = await (
            feedback_query.gt("week_number", 0)
            .order("week_start_date", desc=True)
            .limit(4)
            .execute()
        )
        past_weeks = history_response.data if history_response.data else []
        logger.info(f"Retrieved {len(past_weeks)} weeks of historical feedback")

        # Step 4: Load learning profile
        learning_query = supabase.table("user_learning_profile").select("*")
        if user_id:
            learning_query = learning_query.eq("user_id", user_id)
        learning_response = await learning_query.limit(1).execute()
        learning_profile = learning_response.data[0] if learning_response.data else {}
        logger.info(
            f"Learning profile loaded: {learning_profile.get('weeks_of_data', 0)} weeks of data"
        )

        # Step 5: Analyze weight trend
        weight_analysis = analyze_weight_trend(
            weight_start_kg, weight_end_kg, goal, weeks_on_plan=len(past_weeks) + 1
        )
        logger.info(f"Weight trend: {weight_analysis['trend']}")

        # Step 6: Detect patterns
        metabolic = detect_metabolic_adaptation(
            past_weeks,
            learning_profile.get("observed_tdee"),
            profile.get("tdee", 2868),
        )
        adherence_patterns = detect_adherence_patterns(past_weeks)
        logger.info(
            f"Pattern detection: metabolic_adaptation={metabolic['detected']}, patterns={len(adherence_patterns['positive_triggers'])}"
        )

        # Step 7: Generate rule-based adjustments
        calorie_adj = generate_calorie_adjustment(
            weight_analysis["change_kg"], goal, adherence_percent, len(past_weeks) + 1
        )
        macro_adj = generate_macro_adjustments(
            hunger_level,
            energy_level,
            feedback_data.get("cravings", []),
            current_protein_g,
            profile.get("current_carbs_g", 350),
            profile.get("current_fat_g", 90),
            learning_profile,
        )
        logger.info(
            f"Adjustments generated: cal={calorie_adj['adjustment_kcal']}kcal, protein={macro_adj['protein_g']}g"
        )

        # Step 8: Detect red flags
        red_flags = detect_red_flags(feedback_data, past_weeks, profile)
        if red_flags:
            logger.warning(f"Red flags: {[f['flag_type'] for f in red_flags]}")

        # Step 9: Calculate confidence
        weeks_count = len(past_weeks)
        base_confidence = 0.3 + (min(weeks_count, 8) / 8) * 0.5  # 0.3-0.8 range

        data_quality = completeness.get("quality", "incomplete")
        if data_quality == "incomplete":
            base_confidence *= 0.8
        elif data_quality == "adequate":
            base_confidence *= 0.9

        if red_flags:
            base_confidence = max(0.5, base_confidence - 0.2)

        final_confidence = min(0.95, max(0.3, base_confidence))

        # Build result
        result = {
            "status": "success",
            "week_number": len(past_weeks) + 1,
            "analysis": {
                "weight_analysis": weight_analysis,
                "metabolic_analysis": metabolic,
                "adherence_analysis": {
                    "rate_percent": adherence_percent,
                    "assessment": "Excellent"
                    if adherence_percent >= 85
                    else "Good"
                    if adherence_percent >= 70
                    else "Fair"
                    if adherence_percent >= 50
                    else "Low",
                    "positive_triggers": adherence_patterns["positive_triggers"],
                    "negative_triggers": adherence_patterns["negative_triggers"],
                },
            },
            "adjustments": {
                "suggested": {
                    "calories": calorie_adj["adjustment_kcal"],
                    "protein_g": macro_adj["protein_g"],
                    "carbs_g": macro_adj["carbs_g"],
                    "fat_g": macro_adj["fat_g"],
                },
                "rationale": [
                    *calorie_adj["reasoning"],
                    *macro_adj["adjustments_rationale"].values(),
                ],
            },
            "red_flags": red_flags,
            "feedback_completeness": completeness["quality"],
            "confidence_level": round(final_confidence, 2),
            "recommendations": [
                weight_analysis["assessment"],
                f"Adherence: {adherence_patterns['recommendation']}"
                if adherence_patterns["recommendation"]
                else "",
            ],
        }

        # Step 10: Store results in database
        if feedback_data.get("week_start_date"):
            week_start = datetime.fromisoformat(feedback_data["week_start_date"]).date()
        else:
            today = datetime.now().date()
            week_start = today - timedelta(days=today.weekday())

        week_number = week_start.isocalendar()[1]

        storage_data = {
            "week_number": week_number,
            "week_start_date": str(week_start),
            "weight_start_kg": float(weight_start_kg),
            "weight_end_kg": float(weight_end_kg),
            "adherence_percent": int(adherence_percent),
            "hunger_level": hunger_level,
            "energy_level": energy_level,
            "sleep_quality": sleep_quality,
            "cravings": feedback_data.get("cravings", []),
            "subjective_notes": notes,
            "detected_patterns": {
                "metabolic_adaptation": metabolic["detected"],
                "adherence_patterns": adherence_patterns["positive_triggers"],
            },
            "adjustments_suggested": result["adjustments"]["suggested"],
            "adjustment_rationale": result["adjustments"]["rationale"],
            "feedback_quality": completeness["quality"],
            "agent_confidence_percent": int(final_confidence * 100),
            "red_flags": {f["flag_type"]: f["severity"] for f in red_flags},
        }
        if user_id:
            storage_data["user_id"] = user_id

        await supabase.table("weekly_feedback").insert(storage_data).execute()
        logger.info("Weekly feedback stored in database")

        # Step 11: Update learning profile
        if learning_profile:
            weeks_data = learning_profile.get("weeks_of_data", 0) + 1
            new_confidence = min(0.95, 0.3 + (weeks_data / 8.0))
            update_data = {
                "weeks_of_data": weeks_data,
                "confidence_level": new_confidence,
                "updated_at": datetime.now().isoformat(),
            }
            try:
                await supabase.table("user_learning_profile").update(update_data).eq(
                    "id", learning_profile["id"]
                ).execute()
                logger.info(f"Learning profile updated: {weeks_data} weeks of data")
            except Exception as e:
                logger.warning(f"Could not update learning profile: {e}")
        else:
            LEARNING_PROFILE_UUID = "550e8400-e29b-41d4-a716-446655440000"
            try:
                upsert_data: dict = {
                    "id": LEARNING_PROFILE_UUID,
                    "weeks_of_data": 1,
                    "confidence_level": 0.3,
                    "updated_at": datetime.now().isoformat(),
                }
                if user_id:
                    upsert_data["user_id"] = user_id
                await supabase.table("user_learning_profile").upsert(upsert_data).execute()
                logger.info("New learning profile created")
            except Exception as e:
                logger.warning(f"Could not create learning profile: {e}")

        logger.info("Weekly adjustments synthesized successfully")
        return json.dumps(result, indent=2, ensure_ascii=False)

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return json.dumps({"error": str(e), "code": "VALIDATION_ERROR"})
    except Exception as e:
        logger.error(f"Unexpected error in weekly adjustments: {e}", exc_info=True)
        return json.dumps(
            {
                "error": "Internal error during weekly synthesis",
                "code": "ADJUSTMENT_ERROR",
            }
        )
