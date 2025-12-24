"""Feedback parsing and validation for weekly check-ins.

This module extracts implicit feedback signals from conversational text and
validates explicit metrics provided by the user. It handles incomplete feedback
gracefully and provides clear error messages for validation failures.
"""

import logging
from typing import Literal

logger = logging.getLogger(__name__)


def validate_feedback_metrics(feedback: dict) -> dict:
    """
    Validate feedback data ranges and types.

    Checks required fields, validates numeric ranges, and ensures enum values
    are valid. Sets defaults for optional fields.

    Args:
        feedback: Dict with metrics from user

    Returns:
        Validated feedback dict with defaults for optional fields

    Raises:
        ValueError: If required fields missing or out of range

    Example:
        >>> validated = validate_feedback_metrics({
        ...     "weight_start_kg": 87.0,
        ...     "weight_end_kg": 86.4,
        ...     "adherence_percent": 85
        ... })
        >>> print(validated["hunger_level"])
        "medium"  # Default applied
    """
    required_fields = ["weight_start_kg", "weight_end_kg", "adherence_percent"]

    # Check required
    for field in required_fields:
        if field not in feedback or feedback[field] is None:
            raise ValueError(f"Missing required field: {field}")

    # Validate weight range
    for field in ["weight_start_kg", "weight_end_kg"]:
        value = feedback[field]
        if not isinstance(value, (int, float)):
            raise ValueError(f"{field} must be a number")
        if not (40 <= value <= 300):
            raise ValueError(f"{field} must be 40-300 kg (you provided {value})")

    # Validate adherence 0-100%
    adherence = feedback["adherence_percent"]
    if not isinstance(adherence, (int, float)):
        raise ValueError("adherence_percent must be a number")
    if not (0 <= adherence <= 100):
        raise ValueError(f"adherence_percent must be 0-100% (you provided {adherence})")

    # Validate enum fields with defaults
    valid_hunger = ["low", "medium", "high"]
    if "hunger_level" in feedback:
        if feedback["hunger_level"] not in valid_hunger:
            raise ValueError(
                f"hunger_level must be one of {valid_hunger} (you provided {feedback['hunger_level']})"
            )
    else:
        feedback["hunger_level"] = "medium"

    valid_energy = ["low", "medium", "high"]
    if "energy_level" in feedback:
        if feedback["energy_level"] not in valid_energy:
            raise ValueError(
                f"energy_level must be one of {valid_energy} (you provided {feedback['energy_level']})"
            )
    else:
        feedback["energy_level"] = "medium"

    valid_sleep = ["poor", "fair", "good", "excellent"]
    if "sleep_quality" in feedback:
        if feedback["sleep_quality"] not in valid_sleep:
            raise ValueError(
                f"sleep_quality must be one of {valid_sleep} (you provided {feedback['sleep_quality']})"
            )
    else:
        feedback["sleep_quality"] = "good"

    # Validate cravings is a list
    if "cravings" in feedback:
        if not isinstance(feedback["cravings"], list):
            raise ValueError("cravings must be a list of strings")
    else:
        feedback["cravings"] = []

    # Set default for notes
    feedback.setdefault("notes", "")

    return feedback


def extract_feedback_from_text(text: str) -> dict:
    """
    Extract implicit feedback signals from conversational text.

    Uses keyword matching to detect energy, hunger, mood, and adherence signals.
    Returns dict with detected metrics and confidence levels for each.

    Args:
        text: Free-text user feedback (e.g., "This week I felt pretty tired Friday")

    Returns:
        Dict with detected signals:
        {
            "energy_level": ("medium", 0.7),  # (value, confidence)
            "hunger_level": ("low", 0.6),
            "notes": "text input",
            "mood_indicators": ["tired", "good"],
        }

    Example:
        >>> result = extract_feedback_from_text("This week I felt pretty tired Friday but managed well")
        >>> print(result["energy_level"])
        ("medium", 0.7)
    """
    text_lower = text.lower()
    result = {
        "energy_level": None,
        "hunger_level": None,
        "mood_indicators": [],
        "stress_indicators": [],
        "notes": text,
    }

    # Energy keywords
    high_energy_keywords = [
        "energetic",
        "powerful",
        "strong",
        "lively",
        "excellent",
        "great",
        "amazing",
        "pumped",
    ]
    low_energy_keywords = [
        "tired",
        "exhausted",
        "weak",
        "fatigued",
        "drained",
        "sluggish",
        "low",
        "flat",
    ]

    high_energy_matches = sum(
        1 for kw in high_energy_keywords if kw in text_lower
    )
    low_energy_matches = sum(1 for kw in low_energy_keywords if kw in text_lower)

    if high_energy_matches > low_energy_matches:
        result["energy_level"] = ("high", 0.7 + (high_energy_matches * 0.05))
    elif low_energy_matches > high_energy_matches:
        result["energy_level"] = ("low", 0.7 + (low_energy_matches * 0.05))
    else:
        result["energy_level"] = ("medium", 0.5)

    # Hunger keywords
    high_hunger_keywords = [
        "starving",
        "hungry",
        "cravings",
        "ravenous",
        "famished",
        "constant hunger",
    ]
    low_hunger_keywords = [
        "satisfied",
        "full",
        "adequate",
        "not hungry",
        "good satiety",
    ]

    high_hunger_matches = sum(1 for kw in high_hunger_keywords if kw in text_lower)
    low_hunger_matches = sum(1 for kw in low_hunger_keywords if kw in text_lower)

    if high_hunger_matches > low_hunger_matches:
        result["hunger_level"] = ("high", 0.7 + (high_hunger_matches * 0.05))
    elif low_hunger_matches > high_hunger_matches:
        result["hunger_level"] = ("low", 0.7 + (low_hunger_matches * 0.05))
    else:
        result["hunger_level"] = ("medium", 0.5)

    # Mood indicators
    mood_keywords = {
        "happy": "positive",
        "good": "positive",
        "great": "positive",
        "motivated": "positive",
        "depressed": "negative",
        "sad": "negative",
        "anxious": "negative",
        "stressed": "negative",
    }

    for keyword, mood_type in mood_keywords.items():
        if keyword in text_lower:
            result["mood_indicators"].append(keyword)

    # Stress indicators
    stress_keywords = ["stress", "busy", "overwhelm", "pressure", "hectic"]
    for keyword in stress_keywords:
        if keyword in text_lower:
            result["stress_indicators"].append(keyword)

    return result


def format_feedback_for_storage(feedback: dict) -> dict:
    """
    Format validated feedback for database storage.

    Converts extracted/validated feedback into database-ready format.

    Args:
        feedback: Validated feedback dict from validate_feedback_metrics

    Returns:
        Dict ready for weekly_feedback table insertion

    Example:
        >>> formatted = format_feedback_for_storage(validated_feedback)
        >>> supabase.table("weekly_feedback").insert(formatted).execute()
    """
    from datetime import date, timedelta

    # Calculate week info
    today = date.today()
    week_start = today - timedelta(days=today.weekday())

    storage_dict = {
        "week_number": today.isocalendar()[1],  # ISO week number
        "week_start_date": str(week_start),
        "weight_start_kg": float(feedback["weight_start_kg"]),
        "weight_end_kg": float(feedback["weight_end_kg"]),
        "adherence_percent": int(feedback["adherence_percent"]),
        "hunger_level": feedback["hunger_level"],
        "energy_level": feedback["energy_level"],
        "sleep_quality": feedback["sleep_quality"],
        "cravings": feedback.get("cravings", []),
        "subjective_notes": feedback.get("notes", ""),
    }

    return storage_dict


def check_feedback_completeness(feedback: dict) -> dict:
    """
    Assess completeness of feedback data.

    Checks how many optional fields were provided and returns a quality rating.

    Args:
        feedback: Validated feedback dict

    Returns:
        Dict with completeness assessment:
        {
            "quality": "adequate",  # incomplete, adequate, comprehensive
            "missing_fields": [],
            "confidence_impact": 0.15  # How much quality reduces confidence
        }

    Example:
        >>> assessment = check_feedback_completeness(feedback)
        >>> if assessment["quality"] == "incomplete":
        ...     print("Please provide energy and sleep info for better recommendations")
    """
    optional_fields = [
        "hunger_level",
        "energy_level",
        "sleep_quality",
        "cravings",
        "notes",
    ]

    provided = sum(1 for field in optional_fields if feedback.get(field))
    total_optional = len(optional_fields)

    if provided >= 4:
        quality = "comprehensive"
        confidence_impact = 0.0
    elif provided >= 2:
        quality = "adequate"
        confidence_impact = 0.1
    else:
        quality = "incomplete"
        confidence_impact = 0.25

    missing = [f for f in optional_fields if not feedback.get(f)]

    return {
        "quality": quality,
        "missing_fields": missing,
        "confidence_impact": confidence_impact,
        "completeness_percent": int((provided / total_optional) * 100),
    }
