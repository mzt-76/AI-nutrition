"""Shared meal type normalization for mapping display names to DB keys."""

# Comprehensive meal type mapping from display names to DB keys
MEAL_TYPE_MAP: dict[str, str] = {
    # French display names (exact)
    "petit-déjeuner": "petit-dejeuner",
    "petit-dejeuner": "petit-dejeuner",
    "déjeuner": "dejeuner",
    "dejeuner": "dejeuner",
    "dîner": "diner",
    "diner": "diner",
    "collation": "collation",
    # Structured meal names (from MEAL_STRUCTURES)
    "collation am": "collation",
    "collation pm": "collation",
    "collation pré-entraînement": "collation",
    # Numbered meals (4_meals structure)
    "repas 1": "dejeuner",
    "repas 2": "dejeuner",
    "repas 3": "diner",
    "repas 4": "diner",
}


def normalize_meal_type(meal_type_display: str) -> str:
    """Map display meal type to DB meal_type key.

    Args:
        meal_type_display: Display name like "Petit-déjeuner", "Collation AM", etc.

    Returns:
        DB key: "petit-dejeuner", "dejeuner", "diner", or "collation"
    """
    meal_lower = meal_type_display.lower()

    # Try exact/substring match against the map
    for key, value in MEAL_TYPE_MAP.items():
        if key in meal_lower:
            return value

    # Keyword fallback
    if "petit" in meal_lower or "breakfast" in meal_lower:
        return "petit-dejeuner"
    if "djeuner" in meal_lower or "lunch" in meal_lower:
        return "dejeuner"
    if "dner" in meal_lower or "dinner" in meal_lower or "soir" in meal_lower:
        return "diner"
    if "collation" in meal_lower or "snack" in meal_lower:
        return "collation"

    return "dejeuner"  # Safe fallback
