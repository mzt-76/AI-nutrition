"""Smart quantity rounding for recipe ingredients.

Rounds quantities based on unit type and ingredient context
to produce natural, user-friendly amounts.
"""


def round_quantity_smart(
    quantity: float, unit: str, ingredient_name: str = ""
) -> float:
    """Round quantity intelligently based on unit and ingredient type.

    Args:
        quantity: Raw quantity value
        unit: Unit of measurement (g, ml, pieces, etc.)
        ingredient_name: Name of ingredient (for context)

    Returns:
        Rounded quantity following UX guidelines

    Rules:
        - Countable items (pieces, oeufs, tranches): Always whole numbers
        - Grams (g): Round to integer
        - Milliliters (ml): Round to integer
        - Small spices/seasonings (< 10g): Keep 1 decimal
    """
    unit_lower = unit.lower().strip()
    name_lower = ingredient_name.lower().strip()

    # Countable units: always whole numbers
    countable_units = [
        "pièces",
        "piece",
        "pieces",
        "pièce",
        "tranche",
        "tranches",
        "slice",
        "oeuf",
        "oeufs",
        "egg",
        "eggs",
    ]
    if any(u in unit_lower for u in countable_units):
        return round(quantity)

    # Grams and milliliters
    if unit_lower in [
        "g",
        "gram",
        "gramme",
        "grammes",
        "grams",
        "ml",
        "millilitre",
        "millilitres",
        "milliliter",
        "milliliters",
    ]:
        # Exception: small quantities of spices/seasonings (< 10)
        spice_keywords = [
            "sel",
            "salt",
            "poivre",
            "pepper",
            "épice",
            "spice",
            "herbe",
            "herb",
            "cannelle",
            "cinnamon",
        ]
        if quantity < 10 and any(keyword in name_lower for keyword in spice_keywords):
            return round(quantity, 1)

        # Default: round to integer
        return round(quantity)

    # Other units: keep 1 decimal as fallback
    return round(quantity, 1)
