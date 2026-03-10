"""Ingredient role tagging for per-ingredient MILP optimization.

Maps ingredients to culinary roles (protein, starch, vegetable, fat_source, fixed)
to define scaling bounds and divergence constraints. Uses longest-first substring
matching to avoid false positives (e.g. "haricot vert" → vegetable, not protein).

References:
    USDA FoodData Central: Macronutrient profiles used to assign roles
"""

from src.nutrition.constants import (
    DISCRETE_UNITS,
    ROLE_BOUNDS,
)
from src.nutrition.openfoodfacts_client import normalize_ingredient_name

# ---------------------------------------------------------------------------
# Role exceptions — override substring matching for specific ingredients
# Must be checked BEFORE the general INGREDIENT_ROLES table.
# ---------------------------------------------------------------------------

ROLE_EXCEPTIONS: dict[str, str] = {
    "fromage blanc": "protein",
    "fromage frais": "protein",
    "yaourt": "protein",
    "yogourt": "protein",
    "skyr": "protein",
    "cottage": "protein",
    "blanc d'oeuf": "protein",
    "blanc d'œuf": "protein",
}

# ---------------------------------------------------------------------------
# Main role table — ~155 entries covering 95%+ of recipe ingredients
# ---------------------------------------------------------------------------

INGREDIENT_ROLES: dict[str, str] = {
    # === Protein (~40 entries) ===
    # Volaille
    "blanc de poulet": "protein",
    "cuisse de poulet": "protein",
    "escalope de dinde": "protein",
    "filet de dinde": "protein",
    "poulet": "protein",
    "dinde": "protein",
    "canard": "protein",
    # Viande rouge
    "filet mignon": "protein",
    "boeuf": "protein",
    "bœuf": "protein",
    "veau": "protein",
    "agneau": "protein",
    "porc": "protein",
    "steak": "protein",
    # Poisson & fruits de mer
    "pavé de saumon": "protein",
    "filet de cabillaud": "protein",
    "saumon": "protein",
    "cabillaud": "protein",
    "thon": "protein",
    "daurade": "protein",
    "crevette": "protein",
    "gambas": "protein",
    "moule": "protein",
    "calamar": "protein",
    "truite": "protein",
    "sardine": "protein",
    "maquereau": "protein",
    "colin": "protein",
    # Protéines végétales
    "tofu": "protein",
    "tempeh": "protein",
    "seitan": "protein",
    "protéine": "protein",
    # Œufs
    "oeuf": "protein",
    "œuf": "protein",
    "oeufs": "protein",
    "œufs": "protein",
    # Légumineuses
    "lentille": "protein",
    "pois chiche": "protein",
    "haricot rouge": "protein",
    "haricot noir": "protein",
    "haricot blanc": "protein",
    "edamame": "protein",
    "fève": "protein",
    # === Starch (~25 entries) ===
    # Céréales & grains
    "spaghetti": "starch",
    "tagliatelle": "starch",
    "vermicelle": "starch",
    "fusilli": "starch",
    "penne": "starch",
    "pâtes": "starch",
    "pasta": "starch",
    "riz": "starch",
    "nouille": "starch",
    "couscous": "starch",
    "quinoa": "starch",
    "boulgour": "starch",
    "semoule": "starch",
    "polenta": "starch",
    "orge": "starch",
    "avoine": "starch",
    "flocon": "starch",
    "muesli": "starch",
    "granola": "starch",
    # Pain & féculents
    "pomme de terre": "starch",
    "patate douce": "starch",
    "patate": "starch",
    "igname": "starch",
    "pain": "starch",
    "tortilla": "starch",
    "galette": "starch",
    "farine": "starch",
    "maïs": "starch",
    "wrap": "starch",
    "naan": "starch",
    "pita": "starch",
    # === Vegetable (~35 entries) ===
    "poivron rouge": "vegetable",
    "poivron vert": "vegetable",
    "haricot vert": "vegetable",
    "petit pois": "vegetable",
    "pak choi": "vegetable",
    "bok choy": "vegetable",
    "tomate": "vegetable",
    "courgette": "vegetable",
    "aubergine": "vegetable",
    "poivron": "vegetable",
    "brocoli": "vegetable",
    "chou-fleur": "vegetable",
    "épinard": "vegetable",
    "salade": "vegetable",
    "laitue": "vegetable",
    "roquette": "vegetable",
    "mâche": "vegetable",
    "concombre": "vegetable",
    "céleri": "vegetable",
    "carotte": "vegetable",
    "oignon": "vegetable",
    "échalote": "vegetable",
    "poireau": "vegetable",
    "fenouil": "vegetable",
    "navet": "vegetable",
    "radis": "vegetable",
    "betterave": "vegetable",
    "asperge": "vegetable",
    "champignon": "vegetable",
    "chou": "vegetable",
    "artichaut": "vegetable",
    "endive": "vegetable",
    "courge": "vegetable",
    "butternut": "vegetable",
    "potiron": "vegetable",
    "potimarron": "vegetable",
    "olive": "vegetable",
    "cornichon": "vegetable",
    # === Fat Source (~25 entries) ===
    # Huiles
    "huile d'olive": "fat_source",
    "huile de coco": "fat_source",
    "huile de sésame": "fat_source",
    "huile de colza": "fat_source",
    "huile": "fat_source",
    # Beurre & crème
    "beurre de cacahuète": "fat_source",
    "crème fraîche": "fat_source",
    "crème liquide": "fat_source",
    "lait de coco": "fat_source",
    "beurre": "fat_source",
    "margarine": "fat_source",
    "crème": "fat_source",
    # Fromage (high-fat dairy)
    "parmesan": "fat_source",
    "emmental": "fat_source",
    "gruyère": "fat_source",
    "mozzarella": "fat_source",
    "feta": "fat_source",
    "cheddar": "fat_source",
    "chèvre": "fat_source",
    "ricotta": "fat_source",
    "mascarpone": "fat_source",
    "fromage": "fat_source",
    # Oléagineux
    "noix de cajou": "fat_source",
    "graine de tournesol": "fat_source",
    "graine de lin": "fat_source",
    "graine de chia": "fat_source",
    "graine de courge": "fat_source",
    "avocat": "fat_source",
    "noix": "fat_source",
    "amande": "fat_source",
    "noisette": "fat_source",
    "cacahuète": "fat_source",
    "pistache": "fat_source",
    "tahini": "fat_source",
    # Viandes grasses
    "bacon": "fat_source",
    "lardons": "fat_source",
    "saucisse": "fat_source",
    "chorizo": "fat_source",
    # === Fixed (~30 entries — spices, sauces, garnishes) ===
    # Épices & aromates
    "herbes de provence": "fixed",
    "sel": "fixed",
    "poivre": "fixed",
    "cumin": "fixed",
    "paprika": "fixed",
    "curcuma": "fixed",
    "curry": "fixed",
    "cannelle": "fixed",
    "muscade": "fixed",
    "piment": "fixed",
    "origan": "fixed",
    "thym": "fixed",
    "romarin": "fixed",
    "basilic": "fixed",
    "persil": "fixed",
    "coriandre": "fixed",
    "menthe": "fixed",
    "ciboulette": "fixed",
    "aneth": "fixed",
    "estragon": "fixed",
    "laurier": "fixed",
    "ail": "fixed",
    "gingembre": "fixed",
    # Sauces & condiments
    "sauce soja": "fixed",
    "sauce teriyaki": "fixed",
    "sauce worcestershire": "fixed",
    "sauce poisson": "fixed",
    "concentré de tomate": "fixed",
    "pâte de curry": "fixed",
    "vinaigre": "fixed",
    "moutarde": "fixed",
    "sauce": "fixed",
    "ketchup": "fixed",
    "mayonnaise": "fixed",
    "miso": "fixed",
    "nuoc mam": "fixed",
    # Sucrants & assaisonnement liquide
    "miel": "fixed",
    "sirop d'érable": "fixed",
    "sucre": "fixed",
    "jus de citron": "fixed",
    "citron vert": "fixed",
    "citron": "fixed",
    # Garnitures
    "graines de sésame": "fixed",
    "sésame": "fixed",
    "chapelure": "fixed",
    "levure": "fixed",
    # Liquides de cuisson
    "eau": "fixed",
    "bouillon": "fixed",
    "vin blanc": "fixed",
    "vin rouge": "fixed",
    "lait": "fixed",
}

# ---------------------------------------------------------------------------
# Pre-sorted keys for longest-first matching (computed once at module load)
# ---------------------------------------------------------------------------

_EXCEPTIONS_SORTED: list[tuple[str, str]] = sorted(
    ((normalize_ingredient_name(k), v) for k, v in ROLE_EXCEPTIONS.items()),
    key=lambda x: len(x[0]),
    reverse=True,
)

_ROLES_SORTED: list[tuple[str, str]] = sorted(
    ((normalize_ingredient_name(k), v) for k, v in INGREDIENT_ROLES.items()),
    key=lambda x: len(x[0]),
    reverse=True,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_ingredient_role(name: str) -> str:
    """Determine the culinary role of an ingredient via longest-first substring matching.

    Checks ROLE_EXCEPTIONS first (e.g. "fromage blanc" → protein),
    then INGREDIENT_ROLES, then falls back to "unknown".

    Args:
        name: Ingredient name (any case, accents ok).

    Returns:
        One of: "protein", "starch", "vegetable", "fat_source", "fixed", "unknown".
    """
    normalized = normalize_ingredient_name(name)

    # 1. Exceptions first (longest-first)
    for key, role in _EXCEPTIONS_SORTED:
        if key in normalized:
            return role

    # 2. Main roles table (longest-first)
    for key, role in _ROLES_SORTED:
        if key in normalized:
            return role

    return "unknown"


def is_discrete_unit(unit: str) -> bool:
    """Check if a unit represents countable items (eggs, slices, pieces)."""
    return unit.lower().strip() in DISCRETE_UNITS


def get_role_bounds(role: str) -> tuple[float, float]:
    """Return (min_scale, max_scale) bounds for a given role."""
    return ROLE_BOUNDS.get(role, ROLE_BOUNDS["unknown"])
