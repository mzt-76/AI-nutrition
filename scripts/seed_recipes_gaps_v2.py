"""Seed ~60 new healthy/sporty recipes to fill identified gaps (V2).

LLM-free (rule 10) — uses only src.clients and stdlib.

Priorities:
  P1: 10 dejeuner vegan (high-protein, low-fat, varied cuisines)
  P2: 10 dejeuner végétarien
  P3: 8 diner vegan
  P4: 8 diner végétarien
  P5: 12 collation high-protein low-fat (4 omnivore, 4 végétarien, 4 vegan)
  P6: 12 petit-dejeuner high-protein low-fat (6 vegan, 6 végétarien)

Usage:
    PYTHONPATH=. python scripts/seed_recipes_gaps_v2.py
"""

import asyncio
import json
import logging
import unicodedata
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)

from src.clients import get_supabase_client  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent / "data"

# ---------------------------------------------------------------------------
# Priority targets
# ---------------------------------------------------------------------------

PRIORITY_TARGETS: dict[str, dict] = {
    "dejeuner": {"min_protein": 25, "max_fat": 20, "min_cal": 400, "max_cal": 700},
    "diner": {"min_protein": 25, "max_fat": 20, "min_cal": 400, "max_cal": 650},
    "collation": {"min_protein": 25, "max_fat": 15, "min_cal": 150, "max_cal": 350},
    "petit-dejeuner": {"min_protein": 25, "max_fat": 18, "min_cal": 350, "max_cal": 550},
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def normalize(name: str) -> str:
    nfkd = unicodedata.normalize("NFKD", name.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def load_ingredient_lookup() -> dict[str, dict]:
    with open(DATA_DIR / "validated_ingredients.json", encoding="utf-8") as f:
        data = json.load(f)
    return {item["name"]: item for item in data}


def load_existing_signatures() -> set[str]:
    with open(DATA_DIR / "recipe_signatures.json", encoding="utf-8") as f:
        data = json.load(f)
    return {f"{normalize(r['name'])}|{r['meal']}" for r in data}


ALLERGEN_MAP: dict[str, list[str]] = {
    "gluten": [
        "farine", "pain", "pâtes", "spaghetti", "penne", "nouilles", "blé",
        "couscous", "semoule", "chapelure", "tortilla", "flocons d'avoine",
        "avoine", "boulgour", "bread", "pasta", "oats", "flour", "noodle",
        "linguine", "rigatoni", "macaroni", "farfalle", "fettuccine",
        "lasagne", "crackers", "muesli", "granola", "brioche", "baguette",
        "muffin", "soba", "freekeh",
    ],
    "lactose": [
        "lait", "crème", "beurre", "fromage", "parmesan", "mozzarella",
        "feta", "yaourt", "skyr", "ricotta", "emmental", "gruyère",
        "comté", "cottage", "gouda", "cheddar", "cheese", "yogurt",
        "yoghurt", "milk", "paneer", "halloumi",
    ],
    "fruits_a_coque": [
        "amande", "noix", "cajou", "noisette", "pistache", "pecan",
    ],
    "arachides": ["cacahuète", "beurre de cacahuète", "arachide", "peanut"],
    "oeufs": ["oeuf", "œuf", "egg"],
    "soja": ["soja", "tofu", "tempeh", "edamame", "miso"],
    "poisson": [
        "saumon", "thon", "cabillaud", "sardine", "truite", "maquereau",
        "dorade", "daurade", "lieu noir", "merlu", "tilapia", "haddock",
        "colin", "morue", "salmon", "tuna", "cod", "anchois",
    ],
    "crustaces": ["crevette", "crabe", "homard", "prawn", "shrimp"],
}


def detect_allergens(ingredients: list[dict]) -> list[str]:
    allergens: set[str] = set()
    for ing_item in ingredients:
        name_lower = ing_item["name"].lower()
        for allergen, keywords in ALLERGEN_MAP.items():
            for kw in keywords:
                if kw in name_lower:
                    allergens.add(allergen)
    return sorted(allergens)


def calc_macros(ingredients: list[dict]) -> dict[str, float]:
    cal = prot = fat = carbs = 0.0
    for ing_item in ingredients:
        ratio = ing_item["quantity"] / 100.0
        n = ing_item["nutrition_per_100g"]
        cal += n["calories"] * ratio
        prot += n["protein_g"] * ratio
        fat += n["fat_g"] * ratio
        carbs += n["carbs_g"] * ratio
    return {
        "calories": round(cal, 1),
        "protein_g": round(prot, 1),
        "fat_g": round(fat, 1),
        "carbs_g": round(carbs, 1),
    }


def ing(name: str, quantity: float, unit: str, lookup: dict[str, dict]) -> dict:
    """Build an ingredient dict from validated_ingredients lookup."""
    item = lookup[name]
    return {
        "name": name,
        "quantity": quantity,
        "unit": unit,
        "nutrition_per_100g": {
            "calories": item["cal"],
            "protein_g": item["prot"],
            "fat_g": item["fat"],
            "carbs_g": item["carbs"],
        },
    }


# ---------------------------------------------------------------------------
# Auto-adjustment logic
# ---------------------------------------------------------------------------

# Ingredient role heuristics
PROTEIN_SOURCES = {
    "tofu", "tempeh", "lentilles", "pois chiches", "haricots", "edamame",
    "protéine", "protein", "seitan", "poulet", "dinde", "blanc",
    "cottage", "skyr", "fromage blanc", "whey",
}
FAT_SOURCES = {
    "huile", "beurre", "tahini", "noix", "amande", "cajou", "avocat",
    "coco", "crème", "fromage", "oil", "butter",
}
STARCH_SOURCES = {
    "riz", "pâtes", "pain", "semoule", "couscous", "quinoa", "boulgour",
    "pomme de terre", "patate", "tortilla", "nouilles", "flocons",
    "avoine", "rice", "pasta", "bread", "noodle",
}


def _classify_ingredient(name: str) -> str:
    name_lower = name.lower()
    for kw in PROTEIN_SOURCES:
        if kw in name_lower:
            return "protein"
    for kw in FAT_SOURCES:
        if kw in name_lower:
            return "fat"
    for kw in STARCH_SOURCES:
        if kw in name_lower:
            return "starch"
    return "other"


def auto_adjust(recipe: dict, target: dict) -> tuple[bool, str]:
    """Try to adjust ingredient quantities to meet targets. Returns (adjusted, reason)."""
    macros = calc_macros(recipe["ingredients"])
    prot = macros["protein_g"]
    fat = macros["fat_g"]
    cal = macros["calories"]

    needs_adjustment = (
        prot < target["min_protein"]
        or fat > target["max_fat"]
        or cal < target["min_cal"]
        or cal > target["max_cal"]
    )
    if not needs_adjustment:
        return False, "already passes"

    adjustments_made = 0

    # Try to fix protein
    if prot < target["min_protein"] and adjustments_made < 3:
        for i, ingredient in enumerate(recipe["ingredients"]):
            if _classify_ingredient(ingredient["name"]) == "protein" and adjustments_made < 3:
                old_qty = ingredient["quantity"]
                new_qty = min(old_qty * 1.3, 300)
                if new_qty != old_qty:
                    recipe["ingredients"][i]["quantity"] = round(new_qty, 0)
                    adjustments_made += 1

    # Try to fix fat
    if fat > target["max_fat"] and adjustments_made < 3:
        for i, ingredient in enumerate(recipe["ingredients"]):
            if _classify_ingredient(ingredient["name"]) == "fat" and adjustments_made < 3:
                old_qty = ingredient["quantity"]
                new_qty = max(old_qty * 0.7, 10)
                if new_qty != old_qty:
                    recipe["ingredients"][i]["quantity"] = round(new_qty, 0)
                    adjustments_made += 1

    # Try to fix calories
    recalc = calc_macros(recipe["ingredients"])
    if recalc["calories"] > target["max_cal"] and adjustments_made < 3:
        for i, ingredient in enumerate(recipe["ingredients"]):
            if _classify_ingredient(ingredient["name"]) == "starch" and adjustments_made < 3:
                old_qty = ingredient["quantity"]
                new_qty = max(old_qty * 0.8, 10)
                if new_qty != old_qty:
                    recipe["ingredients"][i]["quantity"] = round(new_qty, 0)
                    adjustments_made += 1
    elif recalc["calories"] < target["min_cal"] and adjustments_made < 3:
        for i, ingredient in enumerate(recipe["ingredients"]):
            if _classify_ingredient(ingredient["name"]) == "starch" and adjustments_made < 3:
                old_qty = ingredient["quantity"]
                new_qty = min(old_qty * 1.2, 300)
                if new_qty != old_qty:
                    recipe["ingredients"][i]["quantity"] = round(new_qty, 0)
                    adjustments_made += 1

    if adjustments_made > 0:
        return True, f"adjusted {adjustments_made} ingredients"
    return False, "no adjustable ingredients found"


# ---------------------------------------------------------------------------
# Recipe definitions
# ---------------------------------------------------------------------------


def define_recipes(lookup: dict[str, dict]) -> list[dict]:
    """Return all ~60 gap-filling recipes."""
    recipes: list[dict] = []

    # =======================================================================
    # PRIORITY 1: 10 Dejeuner Vegan (protein>25g, fat<20g, 400-700 kcal)
    # =======================================================================

    recipes.append({
        "name": "Bibimbap coréen au tempeh et légumes",
        "meal_type": "dejeuner",
        "cuisine_type": "coréenne",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Tempeh", 150, "g", lookup),
            ing("Riz complet", 70, "g", lookup),
            ing("Épinards frais", 80, "g", lookup),
            ing("Carottes", 60, "g", lookup),
            ing("Sauce soja allégée", 15, "ml", lookup),
            ing("Huile de sésame", 5, "ml", lookup),
            ing("Graines de sésame", 5, "g", lookup),
        ],
        "instructions": "1. Cuire le riz complet. 2. Trancher le tempeh et le saisir à sec dans une poêle. 3. Blanchir les épinards et râper les carottes. 4. Dresser le riz, disposer tempeh et légumes. 5. Arroser de sauce soja et huile de sésame, parsemer de graines.",
        "prep_time_minutes": 25,
    })

    recipes.append({
        "name": "Tacos mexicains aux lentilles et maïs",
        "meal_type": "dejeuner",
        "cuisine_type": "mexicaine",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Lentilles corail", 80, "g", lookup),
            ing("maïs", 100, "g", lookup),
            ing("corn tortillas", 60, "g", lookup),
            ing("Tomates concassées", 100, "g", lookup),
            ing("Oignon", 50, "g", lookup),
            ing("Cumin en poudre", 3, "g", lookup),
            ing("Coriandre fraîche", 5, "g", lookup),
        ],
        "instructions": "1. Cuire les lentilles corail 12 min. 2. Faire revenir l'oignon émincé, ajouter les tomates et le cumin. 3. Ajouter les lentilles et le maïs, mélanger. 4. Garnir les tortillas de la préparation. 5. Parsemer de coriandre fraîche.",
        "prep_time_minutes": 20,
    })

    recipes.append({
        "name": "Curry indien de tofu et épinards au curcuma",
        "meal_type": "dejeuner",
        "cuisine_type": "indienne",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Tofu ferme", 180, "g", lookup),
            ing("Épinards", 120, "g", lookup),
            ing("Tomates concassées", 150, "g", lookup),
            ing("Oignon", 60, "g", lookup),
            ing("Curry en poudre", 5, "g", lookup),
            ing("Riz basmati", 60, "g", lookup),
        ],
        "instructions": "1. Couper le tofu en cubes et le saisir à sec. 2. Faire revenir l'oignon, ajouter le curry. 3. Ajouter les tomates, cuire 10 min. 4. Incorporer le tofu et les épinards, mijoter 5 min. 5. Servir avec le riz basmati cuit.",
        "prep_time_minutes": 25,
    })

    recipes.append({
        "name": "Assiette libanaise houmous et lentilles vertes",
        "meal_type": "dejeuner",
        "cuisine_type": "libanaise",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Lentilles vertes cuites", 150, "g", lookup),
            ing("pois chiches cuits", 80, "g", lookup),
            ing("Concombre", 80, "g", lookup),
            ing("Tomates", 80, "g", lookup),
            ing("Jus de citron", 15, "ml", lookup),
            ing("Persil frais", 10, "g", lookup),
            ing("Cumin en poudre", 3, "g", lookup),
        ],
        "instructions": "1. Écraser partiellement les pois chiches avec le cumin et le jus de citron. 2. Dresser les lentilles tièdes dans un bol. 3. Couper concombre et tomates en dés, disposer autour. 4. Garnir du houmous rapide et de persil ciselé.",
        "prep_time_minutes": 15,
    })

    recipes.append({
        "name": "Wok asiatique de tofu fumé et brocoli au gingembre",
        "meal_type": "dejeuner",
        "cuisine_type": "asiatique",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Tofu fumé", 180, "g", lookup),
            ing("Brocoli frais", 150, "g", lookup),
            ing("Sauce soja allégée", 15, "ml", lookup),
            ing("Gingembre frais", 5, "g", lookup),
            ing("Riz basmati", 60, "g", lookup),
            ing("Poivron rouge", 60, "g", lookup),
        ],
        "instructions": "1. Couper le tofu fumé en tranches. 2. Saisir à feu vif dans un wok. 3. Ajouter le brocoli en fleurettes et le poivron émincé. 4. Déglacer à la sauce soja, ajouter le gingembre râpé. 5. Servir sur le riz basmati cuit.",
        "prep_time_minutes": 20,
    })

    recipes.append({
        "name": "Tajine marocain de pois chiches et courgette",
        "meal_type": "dejeuner",
        "cuisine_type": "marocaine",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("pois chiches cuits", 150, "g", lookup),
            ing("Courgette", 120, "g", lookup),
            ing("Tomates concassées", 150, "g", lookup),
            ing("Oignon", 50, "g", lookup),
            ing("Ras el hanout", 5, "g", lookup),
            ing("Semoule de couscous", 60, "g", lookup),
            ing("Coriandre fraîche", 5, "g", lookup),
        ],
        "instructions": "1. Faire revenir l'oignon avec le ras el hanout. 2. Ajouter les tomates et la courgette en rondelles. 3. Incorporer les pois chiches, mijoter 15 min. 4. Préparer la semoule. 5. Servir le tajine sur la semoule, garnir de coriandre.",
        "prep_time_minutes": 25,
    })

    recipes.append({
        "name": "Bowl coréen de tempeh grillé sauce gochujang",
        "meal_type": "dejeuner",
        "cuisine_type": "coréenne",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Tempeh", 160, "g", lookup),
            ing("Riz complet", 70, "g", lookup),
            ing("Concombre", 80, "g", lookup),
            ing("Carottes", 60, "g", lookup),
            ing("Sauce soja allégée", 10, "ml", lookup),
            ing("Vinaigre de riz", 10, "ml", lookup),
            ing("Edamame surgelé", 50, "g", lookup),
        ],
        "instructions": "1. Mariner le tempeh en tranches dans la sauce soja. 2. Griller le tempeh à la poêle. 3. Cuire le riz complet et les edamame. 4. Préparer le concombre en rubans et les carottes râpées. 5. Dresser en bowl, arroser de vinaigre de riz.",
        "prep_time_minutes": 25,
    })

    recipes.append({
        "name": "Dahl de lentilles corail aux tomates et semoule",
        "meal_type": "dejeuner",
        "cuisine_type": "indienne",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Lentilles corail", 100, "g", lookup),
            ing("Tomates concassées", 150, "g", lookup),
            ing("Oignon", 60, "g", lookup),
            ing("Curry en poudre", 5, "g", lookup),
            ing("Semoule de couscous", 50, "g", lookup),
            ing("Épinards frais", 60, "g", lookup),
        ],
        "instructions": "1. Faire revenir l'oignon émincé. 2. Ajouter les lentilles corail, les tomates et le curry. 3. Cuire 15 min en remuant. 4. Incorporer les épinards en fin de cuisson. 5. Servir avec la semoule préparée à part.",
        "prep_time_minutes": 20,
    })

    recipes.append({
        "name": "Salade mexicaine de haricots noirs et quinoa",
        "meal_type": "dejeuner",
        "cuisine_type": "mexicaine",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("haricots noirs", 150, "g", lookup),
            ing("quinoa", 60, "g", lookup),
            ing("Poivron rouge", 80, "g", lookup),
            ing("maïs", 80, "g", lookup),
            ing("Jus de citron", 15, "ml", lookup),
            ing("Coriandre fraîche", 5, "g", lookup),
            ing("Tomates cerises", 60, "g", lookup),
        ],
        "instructions": "1. Cuire le quinoa et laisser refroidir. 2. Égoutter les haricots noirs. 3. Couper le poivron et les tomates cerises en petits dés. 4. Mélanger tous les ingrédients. 5. Assaisonner avec le jus de citron et la coriandre.",
        "prep_time_minutes": 20,
    })

    recipes.append({
        "name": "Bol de riz au tofu mariné et edamame à la japonaise",
        "meal_type": "dejeuner",
        "cuisine_type": "asiatique",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Tofu ferme", 170, "g", lookup),
            ing("Riz basmati", 70, "g", lookup),
            ing("Edamame surgelé", 80, "g", lookup),
            ing("Sauce soja allégée", 15, "ml", lookup),
            ing("Concombre", 60, "g", lookup),
            ing("Graines de sésame", 5, "g", lookup),
        ],
        "instructions": "1. Mariner le tofu coupé en cubes dans la sauce soja 15 min. 2. Griller le tofu à la poêle. 3. Cuire le riz et les edamame. 4. Trancher le concombre en rondelles fines. 5. Assembler le bowl et parsemer de graines de sésame.",
        "prep_time_minutes": 25,
    })

    # =======================================================================
    # PRIORITY 2: 10 Dejeuner Végétarien (protein>25g, fat<20g, 400-700 kcal)
    # =======================================================================

    recipes.append({
        "name": "Bol de lentilles indiennes au yaourt et épinards",
        "meal_type": "dejeuner",
        "cuisine_type": "indienne",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Lentilles corail", 90, "g", lookup),
            ing("yaourt grec 0%", 100, "g", lookup),
            ing("Épinards frais", 80, "g", lookup),
            ing("Tomates concassées", 100, "g", lookup),
            ing("Oignon", 50, "g", lookup),
            ing("Curry en poudre", 5, "g", lookup),
            ing("Riz basmati", 60, "g", lookup),
        ],
        "instructions": "1. Cuire les lentilles corail avec les tomates et le curry 15 min. 2. Ajouter les épinards frais. 3. Préparer le riz basmati. 4. Servir le dahl sur le riz. 5. Garnir d'une cuillère de yaourt grec.",
        "prep_time_minutes": 25,
    })

    recipes.append({
        "name": "Wrap turc aux lentilles et fromage blanc",
        "meal_type": "dejeuner",
        "cuisine_type": "turque",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Lentilles vertes cuites", 120, "g", lookup),
            ing("Fromage blanc 0%", 80, "g", lookup),
            ing("Tortilla blé complet", 60, "g", lookup),
            ing("Tomates", 80, "g", lookup),
            ing("Concombre", 60, "g", lookup),
            ing("Cumin en poudre", 3, "g", lookup),
            ing("Persil frais", 5, "g", lookup),
        ],
        "instructions": "1. Mélanger les lentilles avec le cumin. 2. Couper tomates et concombre en dés. 3. Étaler le fromage blanc sur la tortilla. 4. Garnir de lentilles et légumes. 5. Rouler serré et couper en deux.",
        "prep_time_minutes": 15,
    })

    recipes.append({
        "name": "Buddha bowl méditerranéen aux pois chiches et feta",
        "meal_type": "dejeuner",
        "cuisine_type": "méditerranéenne",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("pois chiches cuits", 120, "g", lookup),
            ing("Feta", 40, "g", lookup),
            ing("Quinoa sec", 60, "g", lookup),
            ing("Concombre", 80, "g", lookup),
            ing("Tomates cerises", 80, "g", lookup),
            ing("Jus de citron", 10, "ml", lookup),
            ing("Épinards frais", 50, "g", lookup),
        ],
        "instructions": "1. Cuire le quinoa et laisser refroidir. 2. Rôtir les pois chiches au four avec un peu de paprika. 3. Couper le concombre et les tomates. 4. Dresser en bowl avec les épinards. 5. Émietter la feta et arroser de jus de citron.",
        "prep_time_minutes": 25,
    })

    recipes.append({
        "name": "Galettes de pois chiches à la turque et salade",
        "meal_type": "dejeuner",
        "cuisine_type": "turque",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Farine de pois chiches", 80, "g", lookup),
            ing("Œufs", 100, "g", lookup),
            ing("Oignon", 50, "g", lookup),
            ing("Épinards frais", 80, "g", lookup),
            ing("yaourt grec 0%", 80, "g", lookup),
            ing("Tomates cerises", 60, "g", lookup),
            ing("Cumin en poudre", 3, "g", lookup),
        ],
        "instructions": "1. Mélanger la farine de pois chiches avec les œufs et le cumin. 2. Ajouter l'oignon émincé. 3. Former des galettes et cuire à la poêle antiadhésive. 4. Servir avec les épinards et tomates en salade. 5. Accompagner de yaourt.",
        "prep_time_minutes": 20,
    })

    recipes.append({
        "name": "Assiette indienne de cottage cheese et lentilles",
        "meal_type": "dejeuner",
        "cuisine_type": "indienne",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("cottage cheese", 150, "g", lookup),
            ing("Lentilles corail", 70, "g", lookup),
            ing("Tomates concassées", 120, "g", lookup),
            ing("Épinards", 80, "g", lookup),
            ing("Garam masala", 4, "g", lookup),
            ing("Riz basmati", 60, "g", lookup),
        ],
        "instructions": "1. Cuire les lentilles avec les tomates et le garam masala. 2. Incorporer les épinards. 3. Cuire le riz basmati. 4. Servir les lentilles sur le riz. 5. Disposer le cottage cheese à côté.",
        "prep_time_minutes": 25,
    })

    recipes.append({
        "name": "Salade asiatique de soba aux œufs et edamame",
        "meal_type": "dejeuner",
        "cuisine_type": "asiatique",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Nouilles soba", 80, "g", lookup),
            ing("Œufs", 100, "g", lookup),
            ing("Edamame surgelé", 80, "g", lookup),
            ing("Concombre", 60, "g", lookup),
            ing("Sauce soja allégée", 15, "ml", lookup),
            ing("Vinaigre de riz", 10, "ml", lookup),
            ing("Graines de sésame", 5, "g", lookup),
        ],
        "instructions": "1. Cuire les nouilles soba et refroidir sous l'eau. 2. Cuire les œufs durs 10 min, les couper en deux. 3. Cuire les edamame. 4. Mélanger les soba avec le concombre tranché. 5. Assaisonner de sauce soja et vinaigre, garnir d'œufs et graines.",
        "prep_time_minutes": 20,
    })

    recipes.append({
        "name": "Shakshuka protéinée aux pois chiches et épinards",
        "meal_type": "dejeuner",
        "cuisine_type": "méditerranéenne",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Œufs", 150, "g", lookup),
            ing("pois chiches cuits", 100, "g", lookup),
            ing("Tomates concassées", 200, "g", lookup),
            ing("Épinards frais", 60, "g", lookup),
            ing("Poivron rouge", 60, "g", lookup),
            ing("Oignon", 50, "g", lookup),
            ing("Cumin en poudre", 3, "g", lookup),
        ],
        "instructions": "1. Faire revenir l'oignon et le poivron émincés. 2. Ajouter les tomates, le cumin et les pois chiches. 3. Mijoter 10 min. 4. Ajouter les épinards. 5. Creuser des puits, y casser les œufs et cuire à couvert 5 min.",
        "prep_time_minutes": 25,
    })

    recipes.append({
        "name": "Bol de freekeh aux légumes grillés et halloumi",
        "meal_type": "dejeuner",
        "cuisine_type": "méditerranéenne",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Freekeh", 70, "g", lookup),
            ing("halloumi", 60, "g", lookup),
            ing("Courgette", 100, "g", lookup),
            ing("Poivron rouge", 80, "g", lookup),
            ing("Tomates cerises", 80, "g", lookup),
            ing("Jus de citron", 10, "ml", lookup),
            ing("Persil frais", 5, "g", lookup),
        ],
        "instructions": "1. Cuire le freekeh selon les instructions. 2. Griller les courgettes et poivrons en lamelles. 3. Griller le halloumi en tranches. 4. Dresser le freekeh avec les légumes grillés. 5. Ajouter le halloumi, arroser de citron et parsemer de persil.",
        "prep_time_minutes": 25,
    })

    recipes.append({
        "name": "Soupe mexicaine de haricots rouges et œuf poché",
        "meal_type": "dejeuner",
        "cuisine_type": "mexicaine",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("haricots rouges", 100, "g", lookup),
            ing("Œufs", 100, "g", lookup),
            ing("Tomates concassées", 200, "g", lookup),
            ing("Oignon", 50, "g", lookup),
            ing("Poivron rouge", 60, "g", lookup),
            ing("Cumin en poudre", 3, "g", lookup),
            ing("Coriandre fraîche", 5, "g", lookup),
        ],
        "instructions": "1. Faire revenir l'oignon et le poivron. 2. Ajouter les tomates, les haricots et le cumin. 3. Mijoter 15 min. 4. Pocher les œufs dans la soupe. 5. Servir garni de coriandre fraîche.",
        "prep_time_minutes": 25,
    })

    recipes.append({
        "name": "Bol protéiné de boulgour aux œufs et pois chiches",
        "meal_type": "dejeuner",
        "cuisine_type": "turque",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Boulgour", 70, "g", lookup),
            ing("Œufs", 100, "g", lookup),
            ing("pois chiches cuits", 100, "g", lookup),
            ing("Tomates", 80, "g", lookup),
            ing("Concombre", 60, "g", lookup),
            ing("Jus de citron", 10, "ml", lookup),
            ing("Persil frais", 5, "g", lookup),
        ],
        "instructions": "1. Cuire le boulgour et laisser gonfler. 2. Cuire les œufs durs. 3. Mélanger le boulgour avec les tomates et concombre en dés. 4. Disposer les pois chiches et les œufs coupés. 5. Assaisonner de citron et parsemer de persil.",
        "prep_time_minutes": 20,
    })

    # =======================================================================
    # PRIORITY 3: 8 Diner Vegan (protein>25g, fat<20g, 400-650 kcal)
    # =======================================================================

    recipes.append({
        "name": "Pho vietnamien au tofu et herbes fraîches",
        "meal_type": "diner",
        "cuisine_type": "vietnamienne",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Tofu ferme", 180, "g", lookup),
            ing("Nouilles de riz", 60, "g", lookup),
            ing("Germes de soja", 80, "g", lookup),
            ing("Coriandre fraîche", 10, "g", lookup),
            ing("Sauce soja allégée", 15, "ml", lookup),
            ing("Gingembre frais", 5, "g", lookup),
            ing("Eau", 200, "ml", lookup),
        ],
        "instructions": "1. Préparer le bouillon avec l'eau, le gingembre et la sauce soja. 2. Cuire les nouilles de riz. 3. Griller le tofu coupé en tranches. 4. Disposer les nouilles dans un bol, verser le bouillon. 5. Garnir de tofu, germes de soja et coriandre.",
        "prep_time_minutes": 25,
    })

    recipes.append({
        "name": "Japchae coréen au tempeh et légumes",
        "meal_type": "diner",
        "cuisine_type": "coréenne",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Tempeh", 150, "g", lookup),
            ing("Nouilles de riz", 60, "g", lookup),
            ing("Épinards frais", 80, "g", lookup),
            ing("Carottes", 60, "g", lookup),
            ing("Poivron rouge", 60, "g", lookup),
            ing("Sauce soja allégée", 15, "ml", lookup),
            ing("Huile de sésame", 5, "ml", lookup),
        ],
        "instructions": "1. Cuire les nouilles et refroidir. 2. Trancher le tempeh et le saisir au wok. 3. Sauter les carottes et le poivron en julienne. 4. Blanchir les épinards. 5. Mélanger le tout avec la sauce soja et l'huile de sésame.",
        "prep_time_minutes": 25,
    })

    recipes.append({
        "name": "Moussaka libanaise aux lentilles et aubergines",
        "meal_type": "diner",
        "cuisine_type": "libanaise",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Lentilles vertes cuites", 150, "g", lookup),
            ing("Courgette", 120, "g", lookup),
            ing("Tomates concassées", 150, "g", lookup),
            ing("Oignon", 60, "g", lookup),
            ing("Cumin en poudre", 3, "g", lookup),
            ing("Persil frais", 10, "g", lookup),
        ],
        "instructions": "1. Trancher les courgettes en rondelles et les griller. 2. Faire revenir l'oignon avec le cumin. 3. Ajouter les tomates et les lentilles, mijoter 10 min. 4. Alterner couches de courgettes et lentilles dans un plat. 5. Passer au four 15 min à 180°C.",
        "prep_time_minutes": 35,
    })

    recipes.append({
        "name": "Harira marocaine de lentilles et pois chiches",
        "meal_type": "diner",
        "cuisine_type": "marocaine",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Lentilles corail", 80, "g", lookup),
            ing("pois chiches cuits", 100, "g", lookup),
            ing("Tomates concassées", 150, "g", lookup),
            ing("Oignon", 60, "g", lookup),
            ing("Coriandre fraîche", 10, "g", lookup),
            ing("Ras el hanout", 5, "g", lookup),
            ing("Eau", 200, "ml", lookup),
        ],
        "instructions": "1. Faire revenir l'oignon avec le ras el hanout. 2. Ajouter les tomates, l'eau, les lentilles. 3. Cuire 15 min. 4. Ajouter les pois chiches, mijoter 5 min. 5. Servir parsemé de coriandre fraîche.",
        "prep_time_minutes": 25,
    })

    recipes.append({
        "name": "Curry thaïlandais de tofu et haricots verts",
        "meal_type": "diner",
        "cuisine_type": "thaïlandaise",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Tofu ferme", 180, "g", lookup),
            ing("Haricots verts", 120, "g", lookup),
            ing("lait de coco light", 80, "ml", lookup),
            ing("Riz basmati", 60, "g", lookup),
            ing("Sauce soja allégée", 10, "ml", lookup),
            ing("Gingembre frais", 5, "g", lookup),
            ing("Coriandre fraîche", 5, "g", lookup),
        ],
        "instructions": "1. Couper le tofu en cubes et le saisir. 2. Ajouter le lait de coco et le gingembre. 3. Cuire les haricots verts à la vapeur 5 min. 4. Incorporer dans le curry avec la sauce soja. 5. Servir avec le riz basmati et la coriandre.",
        "prep_time_minutes": 20,
    })

    recipes.append({
        "name": "Soupe coréenne de tofu épicée aux champignons",
        "meal_type": "diner",
        "cuisine_type": "coréenne",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Tofu ferme", 200, "g", lookup),
            ing("Champignons de Paris", 100, "g", lookup),
            ing("Sauce soja allégée", 20, "ml", lookup),
            ing("Oignon", 50, "g", lookup),
            ing("Eau", 250, "ml", lookup),
            ing("Poivron rouge", 60, "g", lookup),
            ing("Edamame surgelé", 60, "g", lookup),
        ],
        "instructions": "1. Porter l'eau à ébullition avec la sauce soja. 2. Ajouter l'oignon émincé et les champignons tranchés. 3. Cuire 10 min. 4. Ajouter le tofu en cubes et le poivron. 5. Incorporer les edamame, cuire 3 min et servir.",
        "prep_time_minutes": 20,
    })

    recipes.append({
        "name": "Taboulé libanais de boulgour aux lentilles vertes",
        "meal_type": "diner",
        "cuisine_type": "libanaise",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Boulgour", 70, "g", lookup),
            ing("Lentilles vertes cuites", 120, "g", lookup),
            ing("Tomates", 100, "g", lookup),
            ing("Concombre", 80, "g", lookup),
            ing("Persil frais", 20, "g", lookup),
            ing("Jus de citron", 20, "ml", lookup),
        ],
        "instructions": "1. Préparer le boulgour avec de l'eau bouillante et laisser gonfler. 2. Couper les tomates et le concombre en petits dés. 3. Ciseler finement le persil. 4. Mélanger le tout avec les lentilles. 5. Assaisonner au jus de citron.",
        "prep_time_minutes": 15,
    })

    recipes.append({
        "name": "Poêlée vietnamienne de tempeh et légumes au wok",
        "meal_type": "diner",
        "cuisine_type": "vietnamienne",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Tempeh", 160, "g", lookup),
            ing("Brocoli frais", 120, "g", lookup),
            ing("Carottes", 60, "g", lookup),
            ing("Sauce soja allégée", 15, "ml", lookup),
            ing("Gingembre frais", 5, "g", lookup),
            ing("Riz basmati", 60, "g", lookup),
            ing("Coriandre fraîche", 5, "g", lookup),
        ],
        "instructions": "1. Couper le tempeh en lamelles et le saisir au wok. 2. Ajouter le brocoli en fleurettes et les carottes en julienne. 3. Sauter à feu vif 5 min. 4. Déglacer avec la sauce soja et le gingembre râpé. 5. Servir sur le riz avec la coriandre.",
        "prep_time_minutes": 20,
    })

    # =======================================================================
    # PRIORITY 4: 8 Diner Végétarien (protein>25g, fat<20g, 400-650 kcal)
    # =======================================================================

    recipes.append({
        "name": "Okonomiyaki japonais aux œufs et chou",
        "meal_type": "diner",
        "cuisine_type": "japonaise",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Farine de pois chiches", 60, "g", lookup),
            ing("Œufs", 150, "g", lookup),
            ing("chou chinois", 150, "g", lookup),
            ing("Oignon", 50, "g", lookup),
            ing("Sauce soja allégée", 15, "ml", lookup),
            ing("Edamame surgelé", 60, "g", lookup),
        ],
        "instructions": "1. Mélanger la farine de pois chiches avec les œufs. 2. Émincer finement le chou et l'oignon. 3. Incorporer à la pâte avec les edamame. 4. Cuire en galettes épaisses à la poêle antiadhésive. 5. Servir arrosé de sauce soja.",
        "prep_time_minutes": 20,
    })

    recipes.append({
        "name": "Tortilla espagnole protéinée aux lentilles",
        "meal_type": "diner",
        "cuisine_type": "espagnole",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Œufs", 150, "g", lookup),
            ing("Lentilles vertes cuites", 120, "g", lookup),
            ing("Pomme de terre", 100, "g", lookup),
            ing("Oignon", 50, "g", lookup),
            ing("Poivron rouge", 60, "g", lookup),
            ing("Persil frais", 5, "g", lookup),
        ],
        "instructions": "1. Cuire les pommes de terre en dés jusqu'à tendreté. 2. Faire revenir l'oignon et le poivron. 3. Battre les œufs, incorporer les légumes et les lentilles. 4. Cuire la tortilla à feu doux 10 min, retourner et cuire 5 min. 5. Servir avec le persil.",
        "prep_time_minutes": 25,
    })

    recipes.append({
        "name": "Menemen turc aux œufs et poivrons",
        "meal_type": "diner",
        "cuisine_type": "turque",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Œufs", 150, "g", lookup),
            ing("Tomates concassées", 200, "g", lookup),
            ing("Poivron rouge", 80, "g", lookup),
            ing("Oignon", 50, "g", lookup),
            ing("pois chiches cuits", 80, "g", lookup),
            ing("Pain complet", 40, "g", lookup),
            ing("Persil frais", 5, "g", lookup),
        ],
        "instructions": "1. Faire revenir l'oignon et le poivron émincés. 2. Ajouter les tomates et les pois chiches. 3. Mijoter 10 min. 4. Casser les œufs dans la sauce et cuire à couvert. 5. Servir avec le pain complet grillé.",
        "prep_time_minutes": 20,
    })

    recipes.append({
        "name": "Souvlaki de halloumi et salade grecque",
        "meal_type": "diner",
        "cuisine_type": "grecque",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("halloumi", 80, "g", lookup),
            ing("Lentilles vertes cuites", 100, "g", lookup),
            ing("Concombre", 80, "g", lookup),
            ing("Tomates cerises", 80, "g", lookup),
            ing("Jus de citron", 15, "ml", lookup),
            ing("Pain pita", 40, "g", lookup),
            ing("Persil frais", 5, "g", lookup),
        ],
        "instructions": "1. Griller le halloumi en tranches. 2. Couper concombre et tomates en morceaux. 3. Mélanger avec les lentilles et le jus de citron. 4. Griller le pain pita. 5. Servir le halloumi sur la salade avec le pita.",
        "prep_time_minutes": 15,
    })

    recipes.append({
        "name": "Curry de paneer indien aux petits pois et tomates",
        "meal_type": "diner",
        "cuisine_type": "indienne",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("cottage cheese", 150, "g", lookup),
            ing("Petits pois", 100, "g", lookup),
            ing("Tomates concassées", 150, "g", lookup),
            ing("Oignon", 50, "g", lookup),
            ing("Garam masala", 5, "g", lookup),
            ing("Riz basmati", 60, "g", lookup),
        ],
        "instructions": "1. Faire revenir l'oignon avec le garam masala. 2. Ajouter les tomates et mijoter 10 min. 3. Couper le cottage cheese en cubes, ajouter avec les petits pois. 4. Cuire 5 min. 5. Servir avec le riz basmati.",
        "prep_time_minutes": 25,
    })

    recipes.append({
        "name": "Galettes japonaises de tofu et légumes au sésame",
        "meal_type": "diner",
        "cuisine_type": "japonaise",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Tofu ferme", 180, "g", lookup),
            ing("Œufs", 50, "g", lookup),
            ing("Carottes", 60, "g", lookup),
            ing("chou chinois", 100, "g", lookup),
            ing("Sauce soja allégée", 15, "ml", lookup),
            ing("Graines de sésame", 10, "g", lookup),
            ing("Farine de pois chiches", 30, "g", lookup),
        ],
        "instructions": "1. Émietter le tofu, mélanger avec l'œuf battu et la farine. 2. Râper les carottes et émincer le chou, incorporer. 3. Former des galettes et cuire à la poêle antiadhésive. 4. Servir arrosé de sauce soja. 5. Parsemer de graines de sésame.",
        "prep_time_minutes": 20,
    })

    recipes.append({
        "name": "Soupe grecque de lentilles au citron et feta",
        "meal_type": "diner",
        "cuisine_type": "grecque",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Lentilles corail", 90, "g", lookup),
            ing("Feta", 40, "g", lookup),
            ing("Tomates concassées", 150, "g", lookup),
            ing("Carottes", 60, "g", lookup),
            ing("Oignon", 50, "g", lookup),
            ing("Jus de citron", 15, "ml", lookup),
            ing("Eau", 200, "ml", lookup),
        ],
        "instructions": "1. Faire revenir l'oignon et les carottes en dés. 2. Ajouter les tomates, l'eau et les lentilles. 3. Cuire 15 min jusqu'à tendreté. 4. Ajouter le jus de citron. 5. Servir avec la feta émiettée.",
        "prep_time_minutes": 25,
    })

    recipes.append({
        "name": "Bol espagnol de haricots blancs aux épinards et œuf",
        "meal_type": "diner",
        "cuisine_type": "espagnole",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Haricots blancs", 100, "g", lookup),
            ing("Œufs", 100, "g", lookup),
            ing("Épinards frais", 100, "g", lookup),
            ing("Tomates concassées", 150, "g", lookup),
            ing("Oignon", 50, "g", lookup),
            ing("Paprika douce", 3, "g", lookup),
        ],
        "instructions": "1. Faire revenir l'oignon avec le paprika. 2. Ajouter les tomates et les haricots blancs. 3. Mijoter 10 min. 4. Incorporer les épinards. 5. Pocher les œufs dans la préparation et servir.",
        "prep_time_minutes": 25,
    })

    # =======================================================================
    # PRIORITY 5: 12 Collations high-protein low-fat (prot>25g, fat<15g, 150-350 kcal)
    # Split: 4 omnivore, 4 végétarien, 4 vegan
    # =======================================================================

    # --- 4 omnivore collations ---
    recipes.append({
        "name": "Tartare de cabillaud aux herbes et concombre",
        "meal_type": "collation",
        "cuisine_type": "nordique",
        "diet_type": "omnivore",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Filet de cabillaud", 150, "g", lookup),
            ing("Concombre", 80, "g", lookup),
            ing("Jus de citron", 15, "ml", lookup),
            ing("Aneth", 5, "g", lookup),
        ],
        "instructions": "1. Couper le cabillaud en petits dés. 2. Mélanger avec le jus de citron et l'aneth ciselé. 3. Laisser mariner 10 min au frais. 4. Trancher le concombre en rondelles épaisses. 5. Servir le tartare sur les rondelles.",
        "prep_time_minutes": 15,
    })

    recipes.append({
        "name": "Brochettes de poulet au yaourt et paprika",
        "meal_type": "collation",
        "cuisine_type": "turque",
        "diet_type": "omnivore",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Blanc de poulet", 130, "g", lookup),
            ing("yaourt grec 0%", 50, "g", lookup),
            ing("Paprika douce", 3, "g", lookup),
            ing("Jus de citron", 10, "ml", lookup),
        ],
        "instructions": "1. Couper le poulet en cubes. 2. Mélanger le yaourt avec le paprika et le citron. 3. Mariner le poulet 15 min. 4. Enfiler sur des brochettes. 5. Griller à la poêle 3-4 min de chaque côté.",
        "prep_time_minutes": 25,
    })

    recipes.append({
        "name": "Verrines de thon blanc aux haricots cannellini",
        "meal_type": "collation",
        "cuisine_type": "méditerranéenne",
        "diet_type": "omnivore",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Thon en conserve au naturel", 100, "g", lookup),
            ing("Cannellini Beans", 80, "g", lookup),
            ing("Tomates cerises", 60, "g", lookup),
            ing("Jus de citron", 10, "ml", lookup),
            ing("Persil frais", 5, "g", lookup),
        ],
        "instructions": "1. Émietter le thon. 2. Égoutter les haricots cannellini. 3. Couper les tomates cerises en deux. 4. Mélanger le tout avec le jus de citron. 5. Dresser en verrines et garnir de persil.",
        "prep_time_minutes": 10,
    })

    recipes.append({
        "name": "Rouleaux de dinde fumée aux épinards et moutarde",
        "meal_type": "collation",
        "cuisine_type": "française",
        "diet_type": "omnivore",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Blanc de dinde en tranches", 120, "g", lookup),
            ing("Épinards frais", 60, "g", lookup),
            ing("Moutarde de Dijon", 10, "g", lookup),
            ing("Fromage blanc 0%", 40, "g", lookup),
        ],
        "instructions": "1. Étaler les tranches de dinde. 2. Tartiner de moutarde et fromage blanc. 3. Déposer des feuilles d'épinards frais. 4. Rouler serré. 5. Couper en tronçons et servir frais.",
        "prep_time_minutes": 10,
    })

    # --- 4 végétarien collations ---
    recipes.append({
        "name": "Bowl de cottage cheese aux épinards et tomates séchées",
        "meal_type": "collation",
        "cuisine_type": "méditerranéenne",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("cottage cheese", 200, "g", lookup),
            ing("Épinards frais", 40, "g", lookup),
            ing("tomates séchées", 15, "g", lookup),
            ing("Graines de tournesol", 10, "g", lookup),
        ],
        "instructions": "1. Disposer le cottage cheese dans un bol. 2. Ajouter les épinards frais en chiffonnade. 3. Hacher les tomates séchées et ajouter. 4. Parsemer de graines de tournesol. 5. Mélanger légèrement et servir.",
        "prep_time_minutes": 5,
    })

    recipes.append({
        "name": "Muffins protéinés aux blancs d'œufs et courgette",
        "meal_type": "collation",
        "cuisine_type": "internationale",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Blancs d'œufs", 200, "g", lookup),
            ing("Courgette", 80, "g", lookup),
            ing("Farine de pois chiches", 30, "g", lookup),
            ing("Oignon", 30, "g", lookup),
            ing("Persil frais", 5, "g", lookup),
        ],
        "instructions": "1. Râper la courgette et émincer l'oignon. 2. Battre les blancs d'œufs, incorporer la farine de pois chiches. 3. Ajouter les légumes et le persil. 4. Répartir dans des moules à muffins. 5. Cuire au four 20 min à 180°C.",
        "prep_time_minutes": 30,
    })

    recipes.append({
        "name": "Skyr protéiné aux graines de courge et cannelle",
        "meal_type": "collation",
        "cuisine_type": "nordique",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Skyr nature 0% MG", 200, "g", lookup),
            ing("graines de courge", 10, "g", lookup),
            ing("Cannelle en poudre", 2, "g", lookup),
            ing("Miel", 10, "g", lookup),
        ],
        "instructions": "1. Verser le skyr dans un bol. 2. Saupoudrer de cannelle. 3. Ajouter les graines de courge. 4. Arroser d'un filet de miel. 5. Servir frais.",
        "prep_time_minutes": 5,
    })

    recipes.append({
        "name": "Galettes de fromage blanc salées aux herbes",
        "meal_type": "collation",
        "cuisine_type": "française",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Fromage blanc 0%", 150, "g", lookup),
            ing("Blancs d'œufs", 100, "g", lookup),
            ing("Farine de pois chiches", 30, "g", lookup),
            ing("Ciboulette fraîche", 5, "g", lookup),
            ing("Persil frais", 5, "g", lookup),
        ],
        "instructions": "1. Mélanger le fromage blanc avec les blancs d'œufs. 2. Incorporer la farine de pois chiches. 3. Ajouter les herbes ciselées. 4. Former des galettes et cuire à la poêle antiadhésive. 5. Servir tiède.",
        "prep_time_minutes": 15,
    })

    # --- 4 vegan collations ---
    recipes.append({
        "name": "Boulettes de protéine de pois au cacao et dattes",
        "meal_type": "collation",
        "cuisine_type": "internationale",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Protéine de pois", 30, "g", lookup),
            ing("Dattes Medjool", 40, "g", lookup),
            ing("Poudre de cacao non sucrée", 10, "g", lookup),
            ing("Flocons d'avoine", 20, "g", lookup),
        ],
        "instructions": "1. Dénoyauter les dattes et les hacher finement. 2. Mélanger tous les ingrédients dans un bol. 3. Ajouter un peu d'eau si nécessaire. 4. Former des boulettes de la taille d'une noix. 5. Réfrigérer 30 min avant de servir.",
        "prep_time_minutes": 15,
    })

    recipes.append({
        "name": "Shake protéiné vegan banane et protéine de pois",
        "meal_type": "collation",
        "cuisine_type": "internationale",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Protéine de pois", 30, "g", lookup),
            ing("Banane", 100, "g", lookup),
            ing("Lait de soja", 200, "ml", lookup),
            ing("Cannelle en poudre", 2, "g", lookup),
        ],
        "instructions": "1. Peler et couper la banane en rondelles. 2. Placer tous les ingrédients dans un blender. 3. Mixer jusqu'à obtenir une consistance lisse. 4. Servir immédiatement.",
        "prep_time_minutes": 5,
    })

    recipes.append({
        "name": "Bol de lentilles corail épicées au curcuma",
        "meal_type": "collation",
        "cuisine_type": "indienne",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Lentilles corail", 80, "g", lookup),
            ing("Tomates concassées", 80, "g", lookup),
            ing("Oignon", 30, "g", lookup),
            ing("Cumin en poudre", 3, "g", lookup),
            ing("Coriandre fraîche", 5, "g", lookup),
        ],
        "instructions": "1. Cuire les lentilles corail 12 min. 2. Faire revenir l'oignon émincé. 3. Ajouter les tomates et le cumin. 4. Mélanger avec les lentilles. 5. Servir garni de coriandre.",
        "prep_time_minutes": 15,
    })

    recipes.append({
        "name": "Tempeh grillé aux herbes et citron",
        "meal_type": "collation",
        "cuisine_type": "asiatique",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Tempeh", 130, "g", lookup),
            ing("Jus de citron", 15, "ml", lookup),
            ing("Sauce soja allégée", 10, "ml", lookup),
            ing("Persil frais", 5, "g", lookup),
        ],
        "instructions": "1. Trancher le tempeh en fines lamelles. 2. Mariner dans le jus de citron et la sauce soja 10 min. 3. Griller à la poêle antiadhésive 3 min de chaque côté. 4. Parsemer de persil ciselé. 5. Servir chaud ou tiède.",
        "prep_time_minutes": 15,
    })

    # =======================================================================
    # PRIORITY 6: 12 Petit-dejeuner high-protein low-fat (prot>25g, fat<18g, 350-550 kcal)
    # Split: 6 vegan, 6 végétarien
    # =======================================================================

    # --- 6 vegan petit-dejeuner ---
    recipes.append({
        "name": "Porridge protéiné au lait de soja et graines de courge",
        "meal_type": "petit-dejeuner",
        "cuisine_type": "nordique",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Flocons d'avoine", 60, "g", lookup),
            ing("Lait de soja", 200, "ml", lookup),
            ing("Protéine de pois", 20, "g", lookup),
            ing("graines de courge", 10, "g", lookup),
            ing("Banane", 80, "g", lookup),
        ],
        "instructions": "1. Chauffer le lait de soja et ajouter les flocons d'avoine. 2. Cuire 5 min en remuant. 3. Incorporer la protéine de pois hors du feu. 4. Couper la banane en rondelles. 5. Garnir de graines de courge et banane.",
        "prep_time_minutes": 10,
    })

    recipes.append({
        "name": "Tofu brouillé asiatique aux épinards et champignons",
        "meal_type": "petit-dejeuner",
        "cuisine_type": "asiatique",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Tofu ferme", 200, "g", lookup),
            ing("Épinards frais", 80, "g", lookup),
            ing("Champignons de Paris", 80, "g", lookup),
            ing("Sauce soja allégée", 10, "ml", lookup),
            ing("Pain complet", 50, "g", lookup),
            ing("Oignon", 30, "g", lookup),
        ],
        "instructions": "1. Émietter le tofu à la fourchette. 2. Faire revenir l'oignon et les champignons tranchés. 3. Ajouter le tofu émietté et la sauce soja. 4. Incorporer les épinards et cuire 3 min. 5. Servir avec le pain complet grillé.",
        "prep_time_minutes": 15,
    })

    recipes.append({
        "name": "Pancakes vegan à la protéine de pois et myrtilles",
        "meal_type": "petit-dejeuner",
        "cuisine_type": "américaine",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Farine de pois chiches", 60, "g", lookup),
            ing("Protéine de pois", 25, "g", lookup),
            ing("Lait de soja", 150, "ml", lookup),
            ing("Myrtilles", 80, "g", lookup),
            ing("Sirop d'érable", 15, "ml", lookup),
        ],
        "instructions": "1. Mélanger la farine, la protéine et le lait de soja. 2. Former une pâte lisse. 3. Cuire des pancakes à la poêle antiadhésive. 4. Garnir de myrtilles fraîches. 5. Arroser de sirop d'érable.",
        "prep_time_minutes": 15,
    })

    recipes.append({
        "name": "Bol de quinoa salé aux lentilles et épinards",
        "meal_type": "petit-dejeuner",
        "cuisine_type": "internationale",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("quinoa", 60, "g", lookup),
            ing("Lentilles corail", 60, "g", lookup),
            ing("Épinards frais", 80, "g", lookup),
            ing("Tomates cerises", 60, "g", lookup),
            ing("Levure nutritionnelle", 10, "g", lookup),
            ing("Jus de citron", 10, "ml", lookup),
        ],
        "instructions": "1. Cuire le quinoa et les lentilles corail séparément. 2. Mélanger dans un bol. 3. Ajouter les épinards et les tomates cerises coupées. 4. Parsemer de levure nutritionnelle. 5. Arroser de jus de citron.",
        "prep_time_minutes": 20,
    })

    recipes.append({
        "name": "Smoothie bowl protéiné vegan mangue et pois",
        "meal_type": "petit-dejeuner",
        "cuisine_type": "internationale",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Protéine de pois", 30, "g", lookup),
            ing("mangue surgelée", 100, "g", lookup),
            ing("Lait de soja", 150, "ml", lookup),
            ing("Flocons d'avoine", 30, "g", lookup),
            ing("Graines de chia", 10, "g", lookup),
        ],
        "instructions": "1. Mixer la mangue avec le lait de soja et la protéine de pois. 2. Verser dans un bol. 3. Garnir de flocons d'avoine et graines de chia. 4. Servir immédiatement.",
        "prep_time_minutes": 10,
    })

    recipes.append({
        "name": "Tartines nordiques au tempeh fumé et avocat",
        "meal_type": "petit-dejeuner",
        "cuisine_type": "nordique",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Tempeh", 120, "g", lookup),
            ing("Pain de seigle", 60, "g", lookup),
            ing("Tomates cerises", 60, "g", lookup),
            ing("Roquette", 30, "g", lookup),
            ing("Jus de citron", 10, "ml", lookup),
            ing("Sauce soja allégée", 10, "ml", lookup),
        ],
        "instructions": "1. Trancher le tempeh et le griller à la poêle avec la sauce soja. 2. Griller le pain de seigle. 3. Disposer la roquette sur le pain. 4. Ajouter le tempeh et les tomates cerises coupées. 5. Arroser de jus de citron.",
        "prep_time_minutes": 15,
    })

    # --- 6 végétarien petit-dejeuner ---
    recipes.append({
        "name": "Omelette protéinée aux champignons et fromage blanc",
        "meal_type": "petit-dejeuner",
        "cuisine_type": "française",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Blancs d'œufs", 200, "g", lookup),
            ing("Œufs", 50, "g", lookup),
            ing("Champignons de Paris", 100, "g", lookup),
            ing("Fromage blanc 0%", 50, "g", lookup),
            ing("Ciboulette fraîche", 5, "g", lookup),
            ing("Pain complet", 40, "g", lookup),
        ],
        "instructions": "1. Battre les blancs d'œufs avec l'œuf entier. 2. Faire revenir les champignons tranchés. 3. Verser les œufs et cuire l'omelette. 4. Garnir de fromage blanc et ciboulette. 5. Servir avec le pain complet.",
        "prep_time_minutes": 15,
    })

    recipes.append({
        "name": "Bol de skyr aux flocons d'avoine et protéine vanille",
        "meal_type": "petit-dejeuner",
        "cuisine_type": "nordique",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Skyr nature 0% MG", 200, "g", lookup),
            ing("Flocons d'avoine", 40, "g", lookup),
            ing("Protéine en poudre vanille", 15, "g", lookup),
            ing("Banane", 80, "g", lookup),
            ing("Myrtilles", 50, "g", lookup),
        ],
        "instructions": "1. Mélanger le skyr avec la protéine en poudre. 2. Ajouter les flocons d'avoine. 3. Couper la banane en rondelles. 4. Garnir de myrtilles. 5. Servir frais.",
        "prep_time_minutes": 5,
    })

    recipes.append({
        "name": "Crêpes de sarrasin aux blancs d'œufs et épinards",
        "meal_type": "petit-dejeuner",
        "cuisine_type": "française",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Farine de sarrasin", 50, "g", lookup),
            ing("Blancs d'œufs", 150, "g", lookup),
            ing("Épinards frais", 80, "g", lookup),
            ing("Fromage blanc 0%", 60, "g", lookup),
            ing("Lait demi-écrémé", 100, "ml", lookup),
        ],
        "instructions": "1. Mélanger la farine de sarrasin avec les blancs d'œufs et le lait. 2. Cuire des crêpes fines à la poêle. 3. Faire sauter les épinards. 4. Garnir chaque crêpe d'épinards et de fromage blanc. 5. Rouler et servir.",
        "prep_time_minutes": 20,
    })

    recipes.append({
        "name": "Açaí bowl protéiné aux graines de chia et banane",
        "meal_type": "petit-dejeuner",
        "cuisine_type": "internationale",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("yaourt grec 0%", 150, "g", lookup),
            ing("açaí surgelé", 80, "g", lookup),
            ing("Banane", 80, "g", lookup),
            ing("Graines de chia", 10, "g", lookup),
            ing("Flocons d'avoine", 30, "g", lookup),
            ing("Protéine en poudre vanille", 10, "g", lookup),
        ],
        "instructions": "1. Mixer l'açaí avec le yaourt. 2. Incorporer la protéine en poudre. 3. Verser dans un bol. 4. Garnir de banane en rondelles, graines de chia et flocons d'avoine. 5. Servir immédiatement.",
        "prep_time_minutes": 10,
    })

    recipes.append({
        "name": "Muffins salés aux blancs d'œufs, brocoli et fromage blanc",
        "meal_type": "petit-dejeuner",
        "cuisine_type": "américaine",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Blancs d'œufs", 200, "g", lookup),
            ing("Brocoli frais", 100, "g", lookup),
            ing("Fromage blanc 0%", 80, "g", lookup),
            ing("Farine de pois chiches", 30, "g", lookup),
            ing("Oignon", 30, "g", lookup),
        ],
        "instructions": "1. Couper le brocoli en petits fleurettes et le blanchir. 2. Battre les blancs d'œufs avec la farine. 3. Incorporer le fromage blanc, le brocoli et l'oignon émincé. 4. Répartir dans des moules à muffins. 5. Cuire 20 min à 180°C.",
        "prep_time_minutes": 30,
    })

    recipes.append({
        "name": "Bol de fromage blanc aux flocons d'avoine et fraises",
        "meal_type": "petit-dejeuner",
        "cuisine_type": "française",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat"],
        "ingredients": [
            ing("Fromage blanc 0%", 200, "g", lookup),
            ing("Flocons d'avoine", 40, "g", lookup),
            ing("Fraises", 100, "g", lookup),
            ing("Protéine en poudre vanille", 15, "g", lookup),
            ing("Miel", 10, "g", lookup),
        ],
        "instructions": "1. Mélanger le fromage blanc avec la protéine vanille. 2. Ajouter les flocons d'avoine. 3. Couper les fraises en morceaux. 4. Garnir de fraises. 5. Arroser de miel et servir.",
        "prep_time_minutes": 5,
    })

    return recipes


# ---------------------------------------------------------------------------
# Validation pipeline
# ---------------------------------------------------------------------------


def validate_and_build(
    recipes: list[dict],
    lookup: dict[str, dict],
    existing_sigs: set[str],
) -> tuple[list[dict], list[str], dict[str, dict]]:
    """Validate recipes, auto-adjust if needed, reject failures.

    Returns (valid_rows, rejection_reasons, priority_stats).
    """
    valid_rows: list[dict] = []
    rejections: list[str] = []
    stats: dict[str, dict] = {}

    for recipe in recipes:
        name = recipe["name"]
        meal_type = recipe["meal_type"]
        diet_type = recipe["diet_type"]
        priority_key = f"{meal_type}_{diet_type}"

        if priority_key not in stats:
            stats[priority_key] = {"created": 0, "passed": 0, "adjusted": 0, "rejected": 0}
        stats[priority_key]["created"] += 1

        sig = f"{normalize(name)}|{meal_type}"

        # Check duplicate
        if sig in existing_sigs:
            reason = f"DUPLICATE: {name} ({meal_type}) already exists"
            rejections.append(reason)
            stats[priority_key]["rejected"] += 1
            logger.warning(reason)
            continue

        # Check all ingredients exist
        missing = [i["name"] for i in recipe["ingredients"] if i["name"] not in lookup]
        if missing:
            reason = f"MISSING INGREDIENTS in '{name}': {missing}"
            rejections.append(reason)
            stats[priority_key]["rejected"] += 1
            logger.warning(reason)
            continue

        # Check minimum ingredients
        if len(recipe["ingredients"]) < 3:
            reason = f"TOO FEW INGREDIENTS in '{name}': {len(recipe['ingredients'])}"
            rejections.append(reason)
            stats[priority_key]["rejected"] += 1
            logger.warning(reason)
            continue

        # Step A: Calculate macros
        macros = calc_macros(recipe["ingredients"])
        target = PRIORITY_TARGETS.get(meal_type, {})

        # Step B: Check against priority targets
        passes_target = True
        if target:
            if (macros["protein_g"] < target.get("min_protein", 0)
                    or macros["fat_g"] > target.get("max_fat", 999)
                    or macros["calories"] < target.get("min_cal", 0)
                    or macros["calories"] > target.get("max_cal", 9999)):
                passes_target = False

        adjusted = False
        if not passes_target and target:
            # Step C: Auto-adjust
            adjusted, adj_reason = auto_adjust(recipe, target)
            if adjusted:
                # Recalculate after adjustment
                macros = calc_macros(recipe["ingredients"])
                logger.info(f"  ADJUSTED '{name}': {adj_reason}")

            # Step D: Final validation gate
            if (macros["protein_g"] < target.get("min_protein", 0)
                    or macros["fat_g"] > target.get("max_fat", 999)
                    or macros["calories"] < target.get("min_cal", 0)
                    or macros["calories"] > target.get("max_cal", 9999)):
                reason = (
                    f"REJECTED: '{name}' — protein={macros['protein_g']:.1f}g "
                    f"(min {target.get('min_protein', 0)}), "
                    f"fat={macros['fat_g']:.1f}g (max {target.get('max_fat', 999)}), "
                    f"cal={macros['calories']:.0f} "
                    f"(range {target.get('min_cal', 0)}-{target.get('max_cal', 9999)})"
                )
                rejections.append(reason)
                stats[priority_key]["rejected"] += 1
                logger.warning(reason)
                continue

        if adjusted:
            stats[priority_key]["adjusted"] += 1
        stats[priority_key]["passed"] += 1

        # Detect allergens
        allergens = detect_allergens(recipe["ingredients"])

        # Build DB row
        row = {
            "name": name,
            "name_normalized": normalize(name),
            "description": f"{name} — recette sportive riche en protéines.",
            "meal_type": meal_type,
            "cuisine_type": recipe["cuisine_type"],
            "diet_type": diet_type,
            "prep_time_minutes": recipe.get("prep_time_minutes", 20),
            "ingredients": recipe["ingredients"],
            "instructions": recipe["instructions"],
            "tags": recipe.get("tags", []),
            "allergen_tags": allergens,
            "calories_per_serving": round(macros["calories"], 1),
            "protein_g_per_serving": round(macros["protein_g"], 1),
            "carbs_g_per_serving": round(macros["carbs_g"], 1),
            "fat_g_per_serving": round(macros["fat_g"], 1),
            "source": "seed-gap-analysis",
            "off_validated": True,
        }
        valid_rows.append(row)
        existing_sigs.add(sig)  # Prevent internal duplicates

    return valid_rows, rejections, stats


# ---------------------------------------------------------------------------
# Post-insertion DB audit (Step E)
# ---------------------------------------------------------------------------


def post_insertion_audit(supabase) -> int:
    """Re-verify all seed-gap-analysis recipes from DB. Delete bad ones."""
    result = (
        supabase.table("recipes")
        .select("id, name, meal_type, calories_per_serving, protein_g_per_serving, fat_g_per_serving, ingredients")
        .eq("source", "seed-gap-analysis")
        .execute()
    )

    bad_ids: list[str] = []
    for r in result.data:
        ingredients = r["ingredients"] if isinstance(r["ingredients"], list) else json.loads(r["ingredients"])
        calc_prot = sum(i["quantity"] / 100 * i["nutrition_per_100g"]["protein_g"] for i in ingredients)
        calc_fat = sum(i["quantity"] / 100 * i["nutrition_per_100g"]["fat_g"] for i in ingredients)
        calc_cal = sum(i["quantity"] / 100 * i["nutrition_per_100g"]["calories"] for i in ingredients)

        # Check 1: stored macros match calculated (tolerance +-2g / +-10 kcal)
        if (abs(r["protein_g_per_serving"] - calc_prot) > 2
                or abs(r["fat_g_per_serving"] - calc_fat) > 2
                or abs(r["calories_per_serving"] - calc_cal) > 10):
            logger.warning(
                f"MISMATCH: {r['name']} — stored prot={r['protein_g_per_serving']}g "
                f"vs calc={calc_prot:.1f}g, stored fat={r['fat_g_per_serving']}g "
                f"vs calc={calc_fat:.1f}g, stored cal={r['calories_per_serving']} "
                f"vs calc={calc_cal:.1f}"
            )
            bad_ids.append(r["id"])
            continue

        # Check 2: macros meet priority targets
        target = PRIORITY_TARGETS.get(r["meal_type"])
        if target:
            if calc_prot < target["min_protein"] or calc_fat > target["max_fat"]:
                logger.warning(
                    f"OUT OF TARGET: {r['name']} — prot={calc_prot:.1f}g "
                    f"(min {target['min_protein']}), fat={calc_fat:.1f}g "
                    f"(max {target['max_fat']})"
                )
                bad_ids.append(r["id"])

    # Delete bad recipes from DB
    if bad_ids:
        logger.warning(f"\nPurging {len(bad_ids)} recipes that failed post-insertion audit")
        for rid in bad_ids:
            supabase.table("recipes").delete().eq("id", rid).execute()
    else:
        logger.info("\nPost-insertion audit: all recipes pass")

    return len(bad_ids)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def seed() -> None:
    supabase = get_supabase_client()
    lookup = load_ingredient_lookup()
    existing_sigs = load_existing_signatures()

    recipes = define_recipes(lookup)
    logger.info(f"Defined {len(recipes)} recipes")

    rows, rejections, stats = validate_and_build(recipes, lookup, existing_sigs)
    logger.info(f"Validated {len(rows)} recipes (rejected {len(rejections)})")

    # Print validation report
    print("\n=== MACRO VALIDATION REPORT ===")
    for key, s in sorted(stats.items()):
        print(
            f"  {key}: {s['created']} created, {s['passed']} passed, "
            f"{s['adjusted']} adjusted+passed, {s['rejected']} rejected"
        )
    if rejections:
        print("\n  Rejected recipes:")
        for r in rejections:
            print(f"    {r}")

    # Print macro stats
    print("\n=== MACRO AVERAGES ===")
    by_category: dict[str, list[dict]] = {}
    for r in rows:
        key = f"{r['meal_type']}_{r['diet_type']}"
        by_category.setdefault(key, []).append(r)

    for key, group in sorted(by_category.items()):
        avg_cal = sum(r["calories_per_serving"] for r in group) / len(group)
        avg_prot = sum(r["protein_g_per_serving"] for r in group) / len(group)
        avg_fat = sum(r["fat_g_per_serving"] for r in group) / len(group)
        print(f"  {key} ({len(group)}): avg cal={avg_cal:.0f}, prot={avg_prot:.1f}g, fat={avg_fat:.1f}g")

    # Upsert into DB
    inserted = 0
    failed = 0

    for row in rows:
        try:
            supabase.table("recipes").upsert(
                row, on_conflict="name_normalized,meal_type"
            ).execute()
            inserted += 1
            logger.info(
                f"  OK {row['name']} ({row['calories_per_serving']:.0f} kcal, "
                f"P{row['protein_g_per_serving']:.0f}g F{row['fat_g_per_serving']:.0f}g)"
            )
        except Exception as e:
            logger.error(f"  FAIL {row['name']}: {e}")
            failed += 1

    logger.info(f"\nInsertion done: {inserted} inserted, {failed} failed.")

    # Step E: Post-insertion DB audit
    purged = post_insertion_audit(supabase)

    # Final summary
    print(f"\n=== FINAL SUMMARY ===")
    print(f"  Defined: {len(recipes)}")
    print(f"  Passed validation: {len(rows)}")
    print(f"  Inserted to DB: {inserted}")
    print(f"  Failed insertion: {failed}")
    print(f"  Purged by audit: {purged}")
    print(f"  Net recipes added: {inserted - purged}")


if __name__ == "__main__":
    asyncio.run(seed())
