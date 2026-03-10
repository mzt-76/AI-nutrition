"""Seed ~65 new healthy/sporty recipes to fill identified gaps.

LLM-free (rule 10) — uses only src.clients and stdlib.

Priorities:
  P1: 20 high-protein low-fat collations
  P2: 15 high-protein low-fat petit-dejeuners
  P3: 20 végétarien/vegan dejeuner+diner
  P4: 10 under-represented cuisines

Usage:
    PYTHONPATH=. python scripts/seed_recipes_gaps.py
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
    return {f"{r['name']}|{r['meal']}" for r in data}


ALLERGEN_MAP: dict[str, list[str]] = {
    "gluten": [
        "farine", "pain", "pâtes", "spaghetti", "penne", "nouilles", "blé",
        "couscous", "semoule", "chapelure", "tortilla", "flocons d'avoine",
        "avoine", "boulgour", "bread", "pasta", "oats", "flour", "noodle",
        "linguine", "rigatoni", "macaroni", "farfalle", "fettuccine",
        "lasagne", "crackers", "muesli", "granola", "brioche", "baguette",
        "muffin", "soba",
    ],
    "lactose": [
        "lait", "crème", "beurre", "fromage", "parmesan", "mozzarella",
        "feta", "yaourt", "skyr", "ricotta", "emmental", "gruyère",
        "comté", "cottage", "gouda", "cheddar", "cheese", "yogurt",
        "yoghurt", "milk",
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
    for ing in ingredients:
        name_lower = ing["name"].lower()
        for allergen, keywords in ALLERGEN_MAP.items():
            for kw in keywords:
                if kw in name_lower:
                    allergens.add(allergen)
    return sorted(allergens)


def calc_macros(ingredients: list[dict]) -> dict[str, float]:
    cal = prot = fat = carbs = 0.0
    for ing in ingredients:
        ratio = ing["quantity"] / 100.0
        n = ing["nutrition_per_100g"]
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
# Recipe definitions
# ---------------------------------------------------------------------------


def define_recipes(lookup: dict[str, dict]) -> list[dict]:
    """Return all ~65 gap-filling recipes."""
    recipes: list[dict] = []

    # === PRIORITY 1: 20 Collations high-protein low-fat ===

    # --- 8 omnivore collations ---
    recipes.append({
        "name": "Verrines de Skyr aux Myrtilles et Graines de Chia",
        "meal_type": "collation",
        "cuisine_type": "nordique",
        "diet_type": "omnivore",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Skyr nature 0%", 200, "g", lookup),
            ing("Myrtilles", 80, "g", lookup),
            ing("Graines de chia", 10, "g", lookup),
            ing("Miel", 10, "g", lookup),
        ],
        "instructions": "1. Déposer la moitié du skyr dans un verre. 2. Ajouter une couche de myrtilles. 3. Couvrir avec le reste du skyr. 4. Parsemer de graines de chia et d'un filet de miel.",
        "prep_time_minutes": 5,
    })

    recipes.append({
        "name": "Tartare de Thon Frais sur Concombre",
        "meal_type": "collation",
        "cuisine_type": "japonaise",
        "diet_type": "omnivore",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Steak de thon", 120, "g", lookup),
            ing("Concombre", 100, "g", lookup),
            ing("Sauce soja allégée", 10, "ml", lookup),
            ing("Gingembre frais", 5, "g", lookup),
            ing("Graines de sésame", 5, "g", lookup),
        ],
        "instructions": "1. Couper le thon en petits dés. 2. Mélanger avec la sauce soja et le gingembre râpé. 3. Trancher le concombre en rondelles épaisses. 4. Déposer le tartare sur les rondelles de concombre. 5. Parsemer de graines de sésame.",
        "prep_time_minutes": 10,
    })

    recipes.append({
        "name": "Blancs de Poulet Grillés aux Épices Cajun",
        "meal_type": "collation",
        "cuisine_type": "américaine",
        "diet_type": "omnivore",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Blanc de poulet", 130, "g", lookup),
            ing("cajun", 3, "g", lookup),
            ing("Jus de citron", 10, "ml", lookup),
        ],
        "instructions": "1. Couper le poulet en lanières. 2. Assaisonner avec les épices cajun et le jus de citron. 3. Griller à la poêle à feu vif 3-4 min de chaque côté. 4. Servir tiède ou froid.",
        "prep_time_minutes": 10,
    })

    recipes.append({
        "name": "Roulades de Dinde au Fromage Blanc et Ciboulette",
        "meal_type": "collation",
        "cuisine_type": "française",
        "diet_type": "omnivore",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Blanc de dinde en tranches", 100, "g", lookup),
            ing("Fromage blanc 0%", 80, "g", lookup),
            ing("Ciboulette fraîche", 5, "g", lookup),
            ing("Poivre noir moulu", 1, "g", lookup),
        ],
        "instructions": "1. Mélanger le fromage blanc avec la ciboulette ciselée et le poivre. 2. Étaler le mélange sur chaque tranche de dinde. 3. Rouler les tranches et maintenir avec un cure-dent. 4. Réfrigérer 15 min avant de servir.",
        "prep_time_minutes": 10,
    })

    recipes.append({
        "name": "Bâtonnets de Crevettes Marinées au Citron Vert",
        "meal_type": "collation",
        "cuisine_type": "asiatique",
        "diet_type": "omnivore",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Crevettes décortiquées", 150, "g", lookup),
            ing("Jus de citron", 15, "ml", lookup),
            ing("Coriandre fraîche", 5, "g", lookup),
            ing("Ail haché", 3, "g", lookup),
        ],
        "instructions": "1. Mariner les crevettes dans le jus de citron, l'ail et la coriandre pendant 10 min. 2. Enfiler les crevettes sur des brochettes. 3. Griller sur une poêle bien chaude 2 min de chaque côté. 4. Servir tiède avec un reste de marinade.",
        "prep_time_minutes": 15,
    })

    recipes.append({
        "name": "Bol de Cottage Cheese aux Radis et Herbes",
        "meal_type": "collation",
        "cuisine_type": "française",
        "diet_type": "omnivore",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("fat-free cottage cheese", 200, "g", lookup),
            ing("Radis", 60, "g", lookup),
            ing("Ciboulette", 5, "g", lookup),
            ing("Sel fin", 1, "g", lookup),
        ],
        "instructions": "1. Couper les radis en fines rondelles. 2. Disposer le cottage cheese dans un bol. 3. Garnir avec les radis et la ciboulette ciselée. 4. Assaisonner et servir frais.",
        "prep_time_minutes": 5,
    })

    recipes.append({
        "name": "Filet de Cabillaud Poché aux Herbes",
        "meal_type": "collation",
        "cuisine_type": "méditerranéenne",
        "diet_type": "omnivore",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Filet de cabillaud", 130, "g", lookup),
            ing("Jus de citron", 10, "ml", lookup),
            ing("Persil frais", 5, "g", lookup),
            ing("Sel fin", 1, "g", lookup),
        ],
        "instructions": "1. Porter de l'eau à frémissement avec le jus de citron. 2. Pocher le cabillaud 8-10 min à feu doux. 3. Égoutter et émietter dans un bol. 4. Parsemer de persil ciselé et servir tiède.",
        "prep_time_minutes": 15,
    })

    recipes.append({
        "name": "Salade de Blanc de Poulet et Edamame",
        "meal_type": "collation",
        "cuisine_type": "asiatique",
        "diet_type": "omnivore",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Blanc de poulet cuit", 80, "g", lookup),
            ing("Edamame surgelé", 80, "g", lookup),
            ing("Concombre", 50, "g", lookup),
            ing("Sauce soja allégée", 10, "ml", lookup),
        ],
        "instructions": "1. Décongeler les edamames et les écosser. 2. Trancher le poulet cuit en lamelles. 3. Couper le concombre en dés. 4. Mélanger le tout et assaisonner avec la sauce soja.",
        "prep_time_minutes": 10,
    })

    # --- 6 végétarien collations ---
    recipes.append({
        "name": "Fromage Blanc Protéiné aux Fraises",
        "meal_type": "collation",
        "cuisine_type": "française",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Fromage blanc 0%", 200, "g", lookup),
            ing("Fraises fraîches", 80, "g", lookup),
            ing("Extrait de vanille", 3, "ml", lookup),
        ],
        "instructions": "1. Laver et couper les fraises en morceaux. 2. Disposer le fromage blanc dans un bol. 3. Ajouter les fraises et l'extrait de vanille. 4. Mélanger délicatement et servir frais.",
        "prep_time_minutes": 5,
    })

    recipes.append({
        "name": "Galettes de Riz au Cottage Cheese et Tomate",
        "meal_type": "collation",
        "cuisine_type": "internationale",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Galettes de riz soufflé", 30, "g", lookup),
            ing("cottage cheese", 150, "g", lookup),
            ing("Tomates cerises", 60, "g", lookup),
            ing("Basilic frais", 3, "g", lookup),
        ],
        "instructions": "1. Tartiner les galettes de riz de cottage cheese. 2. Couper les tomates cerises en deux. 3. Disposer les tomates sur le cottage cheese. 4. Garnir de feuilles de basilic frais.",
        "prep_time_minutes": 5,
    })

    recipes.append({
        "name": "Skyr Protéiné Vanille et Banane",
        "meal_type": "collation",
        "cuisine_type": "nordique",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Skyr nature 0% MG", 200, "g", lookup),
            ing("Banane", 80, "g", lookup),
            ing("Cannelle en poudre", 2, "g", lookup),
        ],
        "instructions": "1. Trancher la banane en rondelles. 2. Disposer le skyr dans un bol. 3. Ajouter les rondelles de banane. 4. Saupoudrer de cannelle et servir.",
        "prep_time_minutes": 5,
    })

    recipes.append({
        "name": "Blancs d'Œufs Brouillés aux Champignons",
        "meal_type": "collation",
        "cuisine_type": "française",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Blancs d'œufs", 200, "g", lookup),
            ing("Champignons de Paris", 80, "g", lookup),
            ing("Persil frais", 5, "g", lookup),
            ing("Sel fin", 1, "g", lookup),
        ],
        "instructions": "1. Émincer les champignons et les faire sauter à sec dans une poêle antiadhésive. 2. Ajouter les blancs d'œufs et remuer à feu doux. 3. Poursuivre la cuisson en remuant jusqu'à obtenir une consistance crémeuse. 4. Parsemer de persil et servir.",
        "prep_time_minutes": 10,
    })

    recipes.append({
        "name": "Yaourt Grec Protéiné aux Fruits Rouges",
        "meal_type": "collation",
        "cuisine_type": "grecque",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("yaourt grec 0%", 250, "g", lookup),
            ing("Fruits rouges mélangés", 60, "g", lookup),
            ing("Miel", 5, "g", lookup),
        ],
        "instructions": "1. Verser le yaourt grec dans un bol. 2. Laver les fruits rouges et les disposer sur le yaourt. 3. Arroser d'un filet de miel. 4. Servir immédiatement.",
        "prep_time_minutes": 5,
    })

    recipes.append({
        "name": "Wrap de Blancs d'Œufs aux Épinards",
        "meal_type": "collation",
        "cuisine_type": "internationale",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Blancs d'œuf", 150, "g", lookup),
            ing("Épinards frais", 50, "g", lookup),
            ing("Tortilla blé complet", 30, "g", lookup),
            ing("Moutarde de Dijon", 5, "g", lookup),
        ],
        "instructions": "1. Cuire les blancs d'œufs en omelette fine dans une poêle antiadhésive. 2. Faire revenir les épinards 1 min à la poêle. 3. Tartiner la tortilla de moutarde. 4. Garnir avec l'omelette de blancs et les épinards, rouler serré.",
        "prep_time_minutes": 10,
    })

    # --- 6 vegan collations ---
    recipes.append({
        "name": "Edamames Épicés au Paprika Fumé",
        "meal_type": "collation",
        "cuisine_type": "asiatique",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Edamame surgelé", 200, "g", lookup),
            ing("Paprika fumé", 3, "g", lookup),
            ing("Sel de mer", 1, "g", lookup),
        ],
        "instructions": "1. Cuire les edamames dans de l'eau bouillante salée 3-4 min. 2. Égoutter et transférer dans un bol. 3. Saupoudrer de paprika fumé et de sel de mer. 4. Mélanger et servir tiède.",
        "prep_time_minutes": 8,
    })

    recipes.append({
        "name": "Houmous de Lentilles Corail au Cumin",
        "meal_type": "collation",
        "cuisine_type": "libanaise",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Lentilles corail", 60, "g", lookup),
            ing("Jus de citron", 15, "ml", lookup),
            ing("Cumin en poudre", 3, "g", lookup),
            ing("Ail haché", 5, "g", lookup),
            ing("Eau", 100, "ml", lookup),
        ],
        "instructions": "1. Cuire les lentilles corail dans l'eau 12-15 min jusqu'à ce qu'elles soient tendres. 2. Égoutter et laisser tiédir. 3. Mixer avec le jus de citron, le cumin et l'ail. 4. Servir avec des bâtonnets de légumes.",
        "prep_time_minutes": 20,
    })

    recipes.append({
        "name": "Bouchées de Tofu Fumé à la Sauce Soja",
        "meal_type": "collation",
        "cuisine_type": "asiatique",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Tofu fumé", 150, "g", lookup),
            ing("Sauce soja allégée", 10, "ml", lookup),
            ing("Gingembre frais", 5, "g", lookup),
            ing("Graines de sésame", 5, "g", lookup),
        ],
        "instructions": "1. Couper le tofu fumé en cubes de 2 cm. 2. Mélanger la sauce soja avec le gingembre râpé. 3. Poêler les cubes de tofu à feu vif 2-3 min de chaque côté. 4. Napper de sauce et parsemer de sésame.",
        "prep_time_minutes": 10,
    })

    recipes.append({
        "name": "Salade de Pois Chiches au Citron et Persil",
        "meal_type": "collation",
        "cuisine_type": "méditerranéenne",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Pois chiches", 150, "g", lookup),
            ing("Jus de citron", 15, "ml", lookup),
            ing("Persil frais", 10, "g", lookup),
            ing("Cumin en poudre", 2, "g", lookup),
        ],
        "instructions": "1. Égoutter et rincer les pois chiches. 2. Ciseler finement le persil. 3. Mélanger les pois chiches avec le jus de citron, le persil et le cumin. 4. Servir frais ou à température ambiante.",
        "prep_time_minutes": 5,
    })

    recipes.append({
        "name": "Boulettes de Lentilles Corail Épicées",
        "meal_type": "collation",
        "cuisine_type": "indienne",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Lentilles corail", 60, "g", lookup),
            ing("Oignon", 30, "g", lookup),
            ing("Curry en poudre", 3, "g", lookup),
            ing("Coriandre fraîche", 5, "g", lookup),
            ing("Jus de citron", 10, "ml", lookup),
        ],
        "instructions": "1. Cuire les lentilles corail 12 min et bien égoutter. 2. Écraser en purée épaisse. 3. Ajouter l'oignon finement haché, le curry et la coriandre. 4. Former des boulettes et les cuire à la poêle antiadhésive 3 min de chaque côté. 5. Arroser de jus de citron et servir.",
        "prep_time_minutes": 20,
    })

    recipes.append({
        "name": "Bol de Protéine de Pois au Cacao et Banane",
        "meal_type": "collation",
        "cuisine_type": "internationale",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Protéine de pois", 25, "g", lookup),
            ing("Banane", 80, "g", lookup),
            ing("Cacao en poudre", 8, "g", lookup),
            ing("Lait d'avoine", 100, "ml", lookup),
        ],
        "instructions": "1. Mixer la banane avec le lait d'avoine. 2. Ajouter la protéine de pois et le cacao. 3. Mixer jusqu'à obtenir une consistance crémeuse. 4. Verser dans un bol et servir immédiatement.",
        "prep_time_minutes": 5,
    })

    # === PRIORITY 2: 15 Petits-déjeuners high-protein low-fat ===

    # --- 6 omnivore petit-dejeuner ---
    recipes.append({
        "name": "Omelette de Blancs d'Œufs aux Épinards et Dinde",
        "meal_type": "petit-dejeuner",
        "cuisine_type": "française",
        "diet_type": "omnivore",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Blancs d'œufs", 200, "g", lookup),
            ing("Épinards frais", 80, "g", lookup),
            ing("Blanc de dinde en tranches", 60, "g", lookup),
            ing("Champignons de Paris", 50, "g", lookup),
            ing("Pain complet", 40, "g", lookup),
        ],
        "instructions": "1. Faire revenir les champignons émincés et les épinards à la poêle. 2. Ajouter les blancs d'œufs et cuire en omelette. 3. Garnir avec les tranches de dinde. 4. Servir avec le pain complet grillé.",
        "prep_time_minutes": 15,
    })

    recipes.append({
        "name": "Porridge Protéiné au Blanc de Poulet et Champignons",
        "meal_type": "petit-dejeuner",
        "cuisine_type": "internationale",
        "diet_type": "omnivore",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Flocons d'avoine", 50, "g", lookup),
            ing("Blanc de poulet cuit", 100, "g", lookup),
            ing("Champignons de Paris", 60, "g", lookup),
            ing("Bouillon de légumes (cube)", 200, "ml", lookup),
            ing("Persil frais", 5, "g", lookup),
        ],
        "instructions": "1. Faire chauffer le bouillon. 2. Ajouter les flocons d'avoine et cuire 5 min en remuant. 3. Faire sauter les champignons émincés à sec. 4. Émietter le poulet cuit dans le porridge. 5. Garnir de champignons et de persil.",
        "prep_time_minutes": 15,
    })

    recipes.append({
        "name": "Tartine Nordique au Saumon Fumé et Skyr",
        "meal_type": "petit-dejeuner",
        "cuisine_type": "nordique",
        "diet_type": "omnivore",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Pain de seigle", 60, "g", lookup),
            ing("Saumon fumé", 60, "g", lookup),
            ing("Skyr nature 0%", 80, "g", lookup),
            ing("Aneth", 3, "g", lookup),
            ing("Concombre", 40, "g", lookup),
        ],
        "instructions": "1. Tartiner les tranches de pain de seigle avec le skyr. 2. Déposer les tranches de saumon fumé. 3. Ajouter des rondelles de concombre. 4. Garnir d'aneth frais.",
        "prep_time_minutes": 8,
    })

    recipes.append({
        "name": "Crêpes Protéinées aux Blancs d'Œufs et Jambon",
        "meal_type": "petit-dejeuner",
        "cuisine_type": "française",
        "diet_type": "omnivore",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Blancs d'œufs", 150, "g", lookup),
            ing("Farine complète", 30, "g", lookup),
            ing("Jambon blanc", 60, "g", lookup),
            ing("Lait demi-écrémé", 50, "ml", lookup),
            ing("Fromage blanc 0%", 50, "g", lookup),
        ],
        "instructions": "1. Mixer les blancs d'œufs avec la farine et le lait pour obtenir une pâte. 2. Cuire les crêpes fines dans une poêle antiadhésive. 3. Garnir chaque crêpe de jambon et de fromage blanc. 4. Rouler et servir.",
        "prep_time_minutes": 15,
    })

    recipes.append({
        "name": "Bowl de Flocons d'Avoine au Thon et Tomate",
        "meal_type": "petit-dejeuner",
        "cuisine_type": "internationale",
        "diet_type": "omnivore",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Flocons d'avoine", 50, "g", lookup),
            ing("Thon en conserve au naturel", 80, "g", lookup),
            ing("Tomates cerises", 60, "g", lookup),
            ing("Eau", 150, "ml", lookup),
            ing("Persil frais", 5, "g", lookup),
        ],
        "instructions": "1. Cuire les flocons d'avoine dans l'eau 5 min. 2. Égoutter le thon et l'émietter. 3. Couper les tomates cerises en deux. 4. Disposer le thon et les tomates sur le porridge salé. 5. Garnir de persil.",
        "prep_time_minutes": 10,
    })

    recipes.append({
        "name": "Muffins Anglais au Poulet et Épinards",
        "meal_type": "petit-dejeuner",
        "cuisine_type": "américaine",
        "diet_type": "omnivore",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("muffin anglais", 80, "g", lookup),
            ing("Blanc de poulet cuit", 120, "g", lookup),
            ing("Épinards frais", 50, "g", lookup),
            ing("Moutarde de Dijon", 5, "g", lookup),
            ing("Tomate", 60, "g", lookup),
        ],
        "instructions": "1. Griller le muffin anglais coupé en deux. 2. Tartiner de moutarde. 3. Faire revenir les épinards à la poêle. 4. Disposer le poulet émincé, les épinards et des rondelles de tomate. 5. Refermer et servir.",
        "prep_time_minutes": 10,
    })

    # --- 5 végétarien petit-dejeuner ---
    recipes.append({
        "name": "Pancakes Protéinés au Fromage Blanc et Myrtilles",
        "meal_type": "petit-dejeuner",
        "cuisine_type": "américaine",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Blancs d'œufs", 150, "g", lookup),
            ing("Fromage blanc 0%", 100, "g", lookup),
            ing("Flocons d'avoine", 40, "g", lookup),
            ing("Myrtilles fraîches", 60, "g", lookup),
            ing("Levure chimique", 3, "g", lookup),
        ],
        "instructions": "1. Mixer les blancs d'œufs, le fromage blanc, les flocons d'avoine et la levure. 2. Chauffer une poêle antiadhésive. 3. Verser des petits cercles de pâte et cuire 2 min par côté. 4. Servir avec les myrtilles fraîches.",
        "prep_time_minutes": 15,
    })

    recipes.append({
        "name": "Porridge Salé au Cottage Cheese et Brocoli",
        "meal_type": "petit-dejeuner",
        "cuisine_type": "internationale",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Flocons d'avoine", 50, "g", lookup),
            ing("cottage cheese", 120, "g", lookup),
            ing("Brocoli frais", 80, "g", lookup),
            ing("Eau", 150, "ml", lookup),
            ing("Sel fin", 1, "g", lookup),
        ],
        "instructions": "1. Couper le brocoli en petits fleurettes et le cuire à la vapeur 4 min. 2. Cuire les flocons d'avoine dans l'eau salée 5 min. 3. Ajouter le cottage cheese et mélanger. 4. Garnir de brocoli et servir.",
        "prep_time_minutes": 12,
    })

    recipes.append({
        "name": "Bol de Skyr aux Flocons d'Avoine et Pomme",
        "meal_type": "petit-dejeuner",
        "cuisine_type": "nordique",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Skyr nature 0% MG", 200, "g", lookup),
            ing("Flocons d'avoine", 40, "g", lookup),
            ing("Pomme", 100, "g", lookup),
            ing("Cannelle en poudre", 2, "g", lookup),
            ing("Miel", 10, "g", lookup),
        ],
        "instructions": "1. Râper ou couper la pomme en petits dés. 2. Mélanger le skyr avec les flocons d'avoine. 3. Ajouter la pomme, la cannelle et le miel. 4. Laisser reposer 5 min et servir.",
        "prep_time_minutes": 8,
    })

    recipes.append({
        "name": "Omelette de Blancs d'Œufs aux Poivrons et Feta",
        "meal_type": "petit-dejeuner",
        "cuisine_type": "grecque",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Blancs d'œufs", 200, "g", lookup),
            ing("Poivron rouge", 80, "g", lookup),
            ing("Feta", 25, "g", lookup),
            ing("Origan séché", 2, "g", lookup),
            ing("Pain complet", 40, "g", lookup),
        ],
        "instructions": "1. Couper le poivron en petits dés et le faire sauter à la poêle. 2. Verser les blancs d'œufs sur les poivrons. 3. Émietter la feta par dessus. 4. Cuire à feu doux 5 min. 5. Servir avec le pain complet.",
        "prep_time_minutes": 12,
    })

    recipes.append({
        "name": "Tartine de Fromage Blanc aux Herbes et Tomate",
        "meal_type": "petit-dejeuner",
        "cuisine_type": "française",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Pain complet", 60, "g", lookup),
            ing("Fromage blanc 0%", 150, "g", lookup),
            ing("Tomates cerises", 80, "g", lookup),
            ing("Ciboulette fraîche", 5, "g", lookup),
            ing("Poivre noir moulu", 1, "g", lookup),
        ],
        "instructions": "1. Griller les tranches de pain complet. 2. Mélanger le fromage blanc avec la ciboulette et le poivre. 3. Tartiner généreusement les tartines. 4. Garnir de tomates cerises coupées en deux.",
        "prep_time_minutes": 8,
    })

    # --- 4 vegan petit-dejeuner ---
    recipes.append({
        "name": "Scramble de Tofu aux Épinards et Champignons",
        "meal_type": "petit-dejeuner",
        "cuisine_type": "internationale",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Tofu ferme", 200, "g", lookup),
            ing("Épinards frais", 80, "g", lookup),
            ing("Champignons de Paris", 60, "g", lookup),
            ing("Curry en poudre", 3, "g", lookup),
            ing("Pain complet", 50, "g", lookup),
            ing("Levure nutritionnelle", 8, "g", lookup),
        ],
        "instructions": "1. Émietter le tofu à la fourchette. 2. Faire sauter les champignons émincés. 3. Ajouter les épinards et le tofu. 4. Assaisonner avec le curry et la levure nutritionnelle. 5. Cuire 5 min en remuant. 6. Servir avec le pain complet grillé.",
        "prep_time_minutes": 15,
    })

    recipes.append({
        "name": "Porridge Protéiné Vegan aux Lentilles Corail",
        "meal_type": "petit-dejeuner",
        "cuisine_type": "indienne",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Flocons d'avoine", 40, "g", lookup),
            ing("Lentilles corail", 40, "g", lookup),
            ing("Lait d'avoine", 150, "ml", lookup),
            ing("Curry en poudre", 3, "g", lookup),
            ing("Coriandre fraîche", 5, "g", lookup),
        ],
        "instructions": "1. Cuire les lentilles corail dans le lait d'avoine 10 min. 2. Ajouter les flocons d'avoine et cuire 5 min supplémentaires. 3. Assaisonner avec le curry. 4. Garnir de coriandre fraîche ciselée.",
        "prep_time_minutes": 18,
    })

    recipes.append({
        "name": "Smoothie Bowl Protéiné Vegan au Cacao",
        "meal_type": "petit-dejeuner",
        "cuisine_type": "internationale",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Protéine de pois", 30, "g", lookup),
            ing("Banane", 100, "g", lookup),
            ing("Cacao en poudre", 10, "g", lookup),
            ing("Lait d'avoine", 150, "ml", lookup),
            ing("Flocons d'avoine", 30, "g", lookup),
        ],
        "instructions": "1. Mixer la banane congelée avec le lait d'avoine. 2. Ajouter la protéine de pois et le cacao, mixer. 3. Verser dans un bol. 4. Garnir de flocons d'avoine et servir immédiatement.",
        "prep_time_minutes": 8,
    })

    recipes.append({
        "name": "Galettes de Pois Chiches aux Herbes",
        "meal_type": "petit-dejeuner",
        "cuisine_type": "méditerranéenne",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Farine de pois chiches", 60, "g", lookup),
            ing("Eau", 120, "ml", lookup),
            ing("Épinards frais", 60, "g", lookup),
            ing("Persil frais", 10, "g", lookup),
            ing("Cumin en poudre", 3, "g", lookup),
            ing("Tomates cerises", 60, "g", lookup),
        ],
        "instructions": "1. Mélanger la farine de pois chiches avec l'eau pour former une pâte. 2. Ajouter les épinards hachés, le persil et le cumin. 3. Cuire des galettes à la poêle antiadhésive 3 min par côté. 4. Servir avec les tomates cerises.",
        "prep_time_minutes": 15,
    })

    # === PRIORITY 3: 20 Dejeuner + Diner végétarien/vegan ===

    # --- 5 dejeuner végétarien ---
    recipes.append({
        "name": "Curry Thaï de Légumes au Tofu et Lait de Coco",
        "meal_type": "dejeuner",
        "cuisine_type": "thaïlandaise",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Tofu ferme", 150, "g", lookup),
            ing("Brocoli frais", 100, "g", lookup),
            ing("Poivron rouge", 80, "g", lookup),
            ing("Lait de coco", 60, "ml", lookup),
            ing("Thai red curry paste", 15, "g", lookup),
            ing("Riz basmati", 60, "g", lookup),
        ],
        "instructions": "1. Couper le tofu en cubes et le faire dorer à la poêle. 2. Faire sauter les légumes coupés en morceaux. 3. Ajouter la pâte de curry et le lait de coco. 4. Laisser mijoter 10 min. 5. Cuire le riz basmati. 6. Servir le curry sur le riz.",
        "prep_time_minutes": 25,
    })

    recipes.append({
        "name": "Salade Grecque Protéinée aux Pois Chiches et Feta",
        "meal_type": "dejeuner",
        "cuisine_type": "grecque",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Pois chiches", 150, "g", lookup),
            ing("Feta", 40, "g", lookup),
            ing("Concombre", 100, "g", lookup),
            ing("Tomates cerises", 80, "g", lookup),
            ing("Olives noires dénoyautées", 15, "g", lookup),
            ing("Jus de citron", 10, "ml", lookup),
            ing("Origan séché", 2, "g", lookup),
        ],
        "instructions": "1. Égoutter et rincer les pois chiches. 2. Couper le concombre et les tomates en morceaux. 3. Émietter la feta. 4. Assembler tous les ingrédients. 5. Assaisonner avec le citron et l'origan.",
        "prep_time_minutes": 10,
    })

    recipes.append({
        "name": "Bibimbap Végétarien aux Œufs et Légumes",
        "meal_type": "dejeuner",
        "cuisine_type": "coréenne",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Riz complet", 70, "g", lookup),
            ing("Œufs", 100, "g", lookup),
            ing("Épinards frais", 60, "g", lookup),
            ing("Carottes", 50, "g", lookup),
            ing("Courgette", 60, "g", lookup),
            ing("Sauce soja allégée", 15, "ml", lookup),
            ing("Huile de sésame", 5, "ml", lookup),
        ],
        "instructions": "1. Cuire le riz complet. 2. Blanchir les épinards, râper les carottes, trancher la courgette. 3. Faire sauter chaque légume séparément. 4. Pocher les œufs. 5. Disposer le riz dans un bol, garnir des légumes et des œufs. 6. Assaisonner de sauce soja et d'huile de sésame.",
        "prep_time_minutes": 30,
    })

    recipes.append({
        "name": "Wraps de Haricots Noirs à la Mexicaine",
        "meal_type": "dejeuner",
        "cuisine_type": "mexicaine",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Haricots noirs cuits", 150, "g", lookup),
            ing("Tortilla blé complet", 50, "g", lookup),
            ing("Poivron rouge", 60, "g", lookup),
            ing("Tomates concassées", 60, "g", lookup),
            ing("yaourt grec 0%", 40, "g", lookup),
            ing("Cumin en poudre", 3, "g", lookup),
        ],
        "instructions": "1. Faire chauffer les haricots noirs avec les tomates concassées et le cumin. 2. Couper le poivron en lanières et le faire sauter. 3. Garnir les tortillas avec le mélange de haricots et les poivrons. 4. Ajouter une cuillère de yaourt grec. 5. Rouler et servir.",
        "prep_time_minutes": 15,
    })

    recipes.append({
        "name": "Tabboulé de Boulgour aux Lentilles et Menthe",
        "meal_type": "dejeuner",
        "cuisine_type": "libanaise",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Boulgour", 60, "g", lookup),
            ing("Lentilles vertes cuites", 80, "g", lookup),
            ing("Concombre", 60, "g", lookup),
            ing("Tomates cerises", 60, "g", lookup),
            ing("Menthe fraîche", 8, "g", lookup),
            ing("Jus de citron", 15, "ml", lookup),
        ],
        "instructions": "1. Cuire le boulgour selon les instructions et laisser refroidir. 2. Mélanger avec les lentilles cuites. 3. Couper le concombre et les tomates en dés. 4. Ajouter la menthe ciselée et le jus de citron. 5. Mélanger et servir frais.",
        "prep_time_minutes": 20,
    })

    # --- 5 dejeuner vegan ---
    recipes.append({
        "name": "Curry de Lentilles Corail au Lait de Coco",
        "meal_type": "dejeuner",
        "cuisine_type": "indienne",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Lentilles corail", 80, "g", lookup),
            ing("Lait de coco", 60, "ml", lookup),
            ing("Tomates concassées", 100, "g", lookup),
            ing("Curry en poudre", 5, "g", lookup),
            ing("Oignon", 50, "g", lookup),
            ing("Riz basmati", 60, "g", lookup),
        ],
        "instructions": "1. Faire revenir l'oignon émincé. 2. Ajouter les lentilles, les tomates concassées et le curry. 3. Verser le lait de coco et 200 ml d'eau. 4. Laisser mijoter 15-20 min. 5. Cuire le riz basmati. 6. Servir le dal sur le riz.",
        "prep_time_minutes": 25,
    })

    recipes.append({
        "name": "Sauté de Tempeh aux Brocolis et Sésame",
        "meal_type": "dejeuner",
        "cuisine_type": "asiatique",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Tempeh", 150, "g", lookup),
            ing("Brocoli frais", 120, "g", lookup),
            ing("Sauce soja allégée", 15, "ml", lookup),
            ing("Gingembre frais", 5, "g", lookup),
            ing("Graines de sésame", 8, "g", lookup),
            ing("Riz basmati", 60, "g", lookup),
        ],
        "instructions": "1. Couper le tempeh en lamelles et le faire dorer. 2. Couper le brocoli en fleurettes et le faire sauter. 3. Ajouter la sauce soja et le gingembre râpé. 4. Cuire le riz basmati. 5. Servir le sauté sur le riz et parsemer de sésame.",
        "prep_time_minutes": 20,
    })

    recipes.append({
        "name": "Bowl de Quinoa aux Haricots Rouges et Avocat",
        "meal_type": "dejeuner",
        "cuisine_type": "mexicaine",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Quinoa sec", 60, "g", lookup),
            ing("Haricots rouges cuits", 120, "g", lookup),
            ing("Avocat", 40, "g", lookup),
            ing("Tomates cerises", 60, "g", lookup),
            ing("Jus de citron", 10, "ml", lookup),
            ing("Coriandre fraîche", 5, "g", lookup),
        ],
        "instructions": "1. Cuire le quinoa dans de l'eau salée 15 min. 2. Égoutter les haricots rouges. 3. Couper l'avocat en tranches et les tomates en deux. 4. Assembler le bowl : quinoa, haricots, avocat, tomates. 5. Arroser de citron et parsemer de coriandre.",
        "prep_time_minutes": 20,
    })

    recipes.append({
        "name": "Pad Thaï Vegan aux Nouilles de Riz et Tofu",
        "meal_type": "dejeuner",
        "cuisine_type": "thaïlandaise",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Nouilles de riz", 60, "g", lookup),
            ing("Tofu ferme", 150, "g", lookup),
            ing("Germes de soja", 50, "g", lookup),
            ing("Carottes", 40, "g", lookup),
            ing("Sauce soja allégée", 15, "ml", lookup),
            ing("Cacahuètes concassées", 10, "g", lookup),
            ing("Jus de citron", 10, "ml", lookup),
        ],
        "instructions": "1. Cuire les nouilles de riz selon les instructions. 2. Couper le tofu en cubes et le faire dorer. 3. Râper les carottes. 4. Faire sauter les germes de soja et les carottes. 5. Mélanger le tout avec la sauce soja et le jus de citron. 6. Parsemer de cacahuètes.",
        "prep_time_minutes": 20,
    })

    recipes.append({
        "name": "Salade de Pois Chiches Méditerranéenne aux Herbes",
        "meal_type": "dejeuner",
        "cuisine_type": "méditerranéenne",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Pois chiches", 180, "g", lookup),
            ing("Concombre", 80, "g", lookup),
            ing("Tomates cerises", 80, "g", lookup),
            ing("Persil frais", 10, "g", lookup),
            ing("Jus de citron", 15, "ml", lookup),
            ing("Menthe fraîche", 5, "g", lookup),
            ing("Huile d'olive", 5, "ml", lookup),
        ],
        "instructions": "1. Égoutter et rincer les pois chiches. 2. Couper le concombre et les tomates en dés. 3. Ciseler le persil et la menthe. 4. Mélanger tous les ingrédients. 5. Assaisonner avec le citron et un filet d'huile d'olive.",
        "prep_time_minutes": 10,
    })

    # --- 5 diner végétarien ---
    recipes.append({
        "name": "Poivrons Farcis au Quinoa et Fromage de Chèvre",
        "meal_type": "diner",
        "cuisine_type": "méditerranéenne",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Poivron rouge", 150, "g", lookup),
            ing("Quinoa sec", 50, "g", lookup),
            ing("Fromage de chèvre", 30, "g", lookup),
            ing("Épinards frais", 60, "g", lookup),
            ing("Concentré de tomate", 15, "g", lookup),
            ing("Origan séché", 2, "g", lookup),
        ],
        "instructions": "1. Cuire le quinoa 15 min. 2. Évider les poivrons. 3. Mélanger le quinoa avec les épinards hachés, le concentré de tomate et l'origan. 4. Farcir les poivrons. 5. Émietter le fromage de chèvre sur le dessus. 6. Enfourner 20 min à 180°C.",
        "prep_time_minutes": 35,
    })

    recipes.append({
        "name": "Soupe Coréenne aux Œufs et Tofu",
        "meal_type": "diner",
        "cuisine_type": "coréenne",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Tofu soyeux", 150, "g", lookup),
            ing("Œufs", 100, "g", lookup),
            ing("Champignons de Paris", 60, "g", lookup),
            ing("Sauce soja allégée", 15, "ml", lookup),
            ing("Oignon", 40, "g", lookup),
            ing("Eau", 300, "ml", lookup),
        ],
        "instructions": "1. Faire revenir l'oignon émincé. 2. Ajouter l'eau et porter à ébullition. 3. Couper le tofu en cubes et ajouter avec les champignons. 4. Laisser mijoter 10 min. 5. Battre les œufs et les verser en filet dans la soupe en remuant. 6. Assaisonner de sauce soja.",
        "prep_time_minutes": 20,
    })

    recipes.append({
        "name": "Frittata de Blancs d'Œufs aux Courgettes et Patate Douce",
        "meal_type": "diner",
        "cuisine_type": "italienne",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Blancs d'œufs", 250, "g", lookup),
            ing("Courgette", 120, "g", lookup),
            ing("Patate douce", 100, "g", lookup),
            ing("Oignon", 40, "g", lookup),
            ing("Parmesan râpé", 15, "g", lookup),
            ing("Persil frais", 5, "g", lookup),
        ],
        "instructions": "1. Cuire la patate douce en dés 10 min à la vapeur. 2. Trancher la courgette en rondelles fines et l'oignon en lamelles. 3. Faire sauter les légumes à la poêle. 4. Ajouter la patate douce et verser les blancs d'œufs. 5. Cuire à feu doux 10 min. 6. Parsemer de parmesan et passer 2 min sous le grill.",
        "prep_time_minutes": 25,
    })

    recipes.append({
        "name": "Soupe de Lentilles Vertes au Cumin et Citron",
        "meal_type": "diner",
        "cuisine_type": "libanaise",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Lentilles vertes", 70, "g", lookup),
            ing("Oignon", 50, "g", lookup),
            ing("Carottes", 60, "g", lookup),
            ing("Cumin en poudre", 3, "g", lookup),
            ing("Jus de citron", 15, "ml", lookup),
            ing("Eau", 400, "ml", lookup),
            ing("yaourt grec 0%", 40, "g", lookup),
        ],
        "instructions": "1. Faire revenir l'oignon émincé. 2. Ajouter les carottes coupées en rondelles et les lentilles. 3. Verser l'eau et le cumin, porter à ébullition. 4. Laisser mijoter 25 min. 5. Mixer grossièrement et ajouter le jus de citron. 6. Servir avec une cuillère de yaourt.",
        "prep_time_minutes": 35,
    })

    recipes.append({
        "name": "Salade Indienne de Pois Chiches au Yaourt",
        "meal_type": "diner",
        "cuisine_type": "indienne",
        "diet_type": "végétarien",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Pois chiches", 160, "g", lookup),
            ing("yaourt grec 0%", 80, "g", lookup),
            ing("Concombre", 60, "g", lookup),
            ing("Tomate", 60, "g", lookup),
            ing("Curry en poudre", 3, "g", lookup),
            ing("Coriandre fraîche", 5, "g", lookup),
        ],
        "instructions": "1. Égoutter les pois chiches. 2. Couper le concombre et la tomate en dés. 3. Mélanger le yaourt avec le curry en poudre. 4. Assembler les pois chiches et les légumes. 5. Napper de sauce au yaourt et garnir de coriandre.",
        "prep_time_minutes": 10,
    })

    # --- 5 diner vegan ---
    recipes.append({
        "name": "Curry Vert Thaï au Tofu et Brocoli",
        "meal_type": "diner",
        "cuisine_type": "thaïlandaise",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Tofu ferme", 150, "g", lookup),
            ing("Brocoli frais", 100, "g", lookup),
            ing("Lait de coco", 50, "ml", lookup),
            ing("Thai red curry paste", 15, "g", lookup),
            ing("Riz basmati", 60, "g", lookup),
            ing("Coriandre fraîche", 5, "g", lookup),
        ],
        "instructions": "1. Couper le tofu en cubes et le griller à sec. 2. Couper le brocoli en fleurettes. 3. Faire chauffer la pâte de curry, ajouter le lait de coco. 4. Ajouter le tofu et le brocoli. 5. Mijoter 10 min. 6. Servir sur du riz basmati avec la coriandre.",
        "prep_time_minutes": 25,
    })

    recipes.append({
        "name": "Tacos Vegan aux Haricots Noirs et Maïs",
        "meal_type": "diner",
        "cuisine_type": "mexicaine",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Haricots noirs cuits", 150, "g", lookup),
            ing("corn tortillas", 60, "g", lookup),
            ing("Corn kernels", 50, "g", lookup),
            ing("Tomates concassées", 80, "g", lookup),
            ing("Coriandre fraîche", 5, "g", lookup),
            ing("Cumin en poudre", 3, "g", lookup),
            ing("Jus de citron", 10, "ml", lookup),
        ],
        "instructions": "1. Faire chauffer les haricots noirs avec les tomates concassées et le cumin. 2. Ajouter le maïs et cuire 5 min. 3. Réchauffer les tortillas à sec. 4. Garnir les tortillas du mélange de haricots. 5. Arroser de jus de citron et garnir de coriandre.",
        "prep_time_minutes": 15,
    })

    recipes.append({
        "name": "Sauté de Tofu Fumé aux Légumes et Nouilles Soba",
        "meal_type": "diner",
        "cuisine_type": "japonaise",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Tofu fumé", 150, "g", lookup),
            ing("Nouilles soba", 60, "g", lookup),
            ing("Courgette", 80, "g", lookup),
            ing("Carottes", 50, "g", lookup),
            ing("Sauce soja allégée", 15, "ml", lookup),
            ing("Gingembre frais", 5, "g", lookup),
        ],
        "instructions": "1. Cuire les nouilles soba selon les instructions. 2. Couper le tofu en cubes et le faire dorer. 3. Trancher la courgette et râper les carottes. 4. Faire sauter les légumes avec le gingembre. 5. Ajouter les nouilles et la sauce soja. 6. Mélanger et servir.",
        "prep_time_minutes": 20,
    })

    recipes.append({
        "name": "Dal de Lentilles Corail aux Épinards",
        "meal_type": "diner",
        "cuisine_type": "indienne",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Lentilles corail", 80, "g", lookup),
            ing("Épinards frais", 80, "g", lookup),
            ing("Oignon", 50, "g", lookup),
            ing("Gingembre frais", 5, "g", lookup),
            ing("Curry en poudre", 5, "g", lookup),
            ing("Riz basmati", 60, "g", lookup),
            ing("Eau", 200, "ml", lookup),
        ],
        "instructions": "1. Faire revenir l'oignon et le gingembre. 2. Ajouter les lentilles, l'eau et le curry. 3. Cuire 15 min à feu doux. 4. Ajouter les épinards et cuire 3 min. 5. Cuire le riz basmati. 6. Servir le dal sur le riz.",
        "prep_time_minutes": 25,
    })

    recipes.append({
        "name": "Bol de Tempeh Teriyaki aux Légumes",
        "meal_type": "diner",
        "cuisine_type": "japonaise",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Tempeh", 150, "g", lookup),
            ing("Riz complet", 60, "g", lookup),
            ing("Brocoli frais", 80, "g", lookup),
            ing("Carottes", 50, "g", lookup),
            ing("Sauce soja allégée", 15, "ml", lookup),
            ing("Miel", 10, "g", lookup),
            ing("Gingembre frais", 5, "g", lookup),
        ],
        "instructions": "1. Couper le tempeh en tranches et le mariner dans la sauce soja, le miel et le gingembre. 2. Cuire le riz complet. 3. Faire sauter le tempeh mariné à la poêle. 4. Cuire le brocoli à la vapeur et les carottes en julienne. 5. Assembler le bol avec le riz, le tempeh et les légumes.",
        "prep_time_minutes": 25,
    })

    # === PRIORITY 4: 10 Cuisines sous-représentées ===

    recipes.append({
        "name": "Larb de Poulet Thaïlandais aux Herbes",
        "meal_type": "dejeuner",
        "cuisine_type": "thaïlandaise",
        "diet_type": "omnivore",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Blanc de poulet", 150, "g", lookup),
            ing("Jus de citron", 15, "ml", lookup),
            ing("Menthe fraîche", 8, "g", lookup),
            ing("Coriandre fraîche", 5, "g", lookup),
            ing("Sauce soja allégée", 10, "ml", lookup),
            ing("Laitue romaine", 60, "g", lookup),
            ing("Riz basmati", 50, "g", lookup),
        ],
        "instructions": "1. Hacher finement le poulet cru. 2. Cuire le poulet haché à sec dans une poêle chaude. 3. Ajouter le jus de citron et la sauce soja. 4. Mélanger avec la menthe et la coriandre ciselées. 5. Cuire le riz. 6. Servir le larb dans les feuilles de laitue avec le riz.",
        "prep_time_minutes": 15,
    })

    recipes.append({
        "name": "Bibimbap au Bœuf Maigre et Légumes",
        "meal_type": "diner",
        "cuisine_type": "coréenne",
        "diet_type": "omnivore",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Rumsteck", 120, "g", lookup),
            ing("Riz complet", 70, "g", lookup),
            ing("Épinards frais", 60, "g", lookup),
            ing("Carottes", 50, "g", lookup),
            ing("Champignons de Paris", 50, "g", lookup),
            ing("Sauce soja allégée", 15, "ml", lookup),
            ing("Huile de sésame", 5, "ml", lookup),
        ],
        "instructions": "1. Cuire le riz complet. 2. Trancher le bœuf en fines lamelles et le saisir à feu vif. 3. Blanchir les épinards, râper les carottes, émincer les champignons. 4. Faire sauter chaque légume séparément. 5. Assembler le bibimbap avec le riz, le bœuf et les légumes. 6. Arroser de sauce soja et d'huile de sésame.",
        "prep_time_minutes": 30,
    })

    recipes.append({
        "name": "Souvlaki de Poulet Grec avec Boulgour",
        "meal_type": "dejeuner",
        "cuisine_type": "grecque",
        "diet_type": "omnivore",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Blanc de poulet", 150, "g", lookup),
            ing("Boulgour", 50, "g", lookup),
            ing("yaourt grec 0%", 50, "g", lookup),
            ing("Concombre", 60, "g", lookup),
            ing("Tomate", 60, "g", lookup),
            ing("Jus de citron", 10, "ml", lookup),
            ing("Origan séché", 3, "g", lookup),
        ],
        "instructions": "1. Couper le poulet en cubes et mariner dans le yaourt, le citron et l'origan. 2. Enfiler sur des brochettes. 3. Cuire le boulgour 12 min. 4. Griller les brochettes 10-12 min en les retournant. 5. Préparer la salade avec le concombre et la tomate. 6. Servir les brochettes avec le boulgour et la salade.",
        "prep_time_minutes": 25,
    })

    recipes.append({
        "name": "Phở au Blanc de Poulet et Herbes Fraîches",
        "meal_type": "diner",
        "cuisine_type": "vietnamienne",
        "diet_type": "omnivore",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Blanc de poulet", 130, "g", lookup),
            ing("Nouilles de riz", 50, "g", lookup),
            ing("Germes de soja", 40, "g", lookup),
            ing("Coriandre fraîche", 8, "g", lookup),
            ing("Gingembre frais", 5, "g", lookup),
            ing("Sauce soja allégée", 10, "ml", lookup),
            ing("Eau", 400, "ml", lookup),
        ],
        "instructions": "1. Porter l'eau à ébullition avec le gingembre tranché. 2. Ajouter le poulet entier et pocher 15 min. 3. Retirer le poulet et le trancher finement. 4. Cuire les nouilles de riz dans le bouillon. 5. Servir dans un bol avec les germes de soja et la coriandre. 6. Assaisonner de sauce soja.",
        "prep_time_minutes": 25,
    })

    recipes.append({
        "name": "Kefta de Dinde Libanaise aux Herbes",
        "meal_type": "diner",
        "cuisine_type": "libanaise",
        "diet_type": "omnivore",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("dinde hachée", 150, "g", lookup),
            ing("Persil frais", 10, "g", lookup),
            ing("Oignon", 40, "g", lookup),
            ing("Cumin en poudre", 3, "g", lookup),
            ing("Boulgour", 50, "g", lookup),
            ing("Concombre", 50, "g", lookup),
            ing("Jus de citron", 10, "ml", lookup),
        ],
        "instructions": "1. Mélanger la dinde hachée avec le persil, l'oignon râpé et le cumin. 2. Former des boulettes allongées. 3. Griller les kefta à la poêle 4-5 min de chaque côté. 4. Cuire le boulgour. 5. Préparer une salade de concombre au citron. 6. Servir les kefta avec le boulgour et la salade.",
        "prep_time_minutes": 25,
    })

    recipes.append({
        "name": "Tom Kha Tofu aux Champignons",
        "meal_type": "diner",
        "cuisine_type": "thaïlandaise",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Tofu ferme", 150, "g", lookup),
            ing("Champignons de Paris", 80, "g", lookup),
            ing("Lait de coco", 60, "ml", lookup),
            ing("Gingembre frais", 8, "g", lookup),
            ing("Jus de citron", 15, "ml", lookup),
            ing("Coriandre fraîche", 5, "g", lookup),
            ing("Eau", 200, "ml", lookup),
        ],
        "instructions": "1. Porter l'eau et le lait de coco à frémissement avec le gingembre tranché. 2. Ajouter les champignons émincés et cuire 5 min. 3. Couper le tofu en cubes et l'ajouter. 4. Laisser mijoter 10 min. 5. Ajouter le jus de citron. 6. Servir garni de coriandre fraîche.",
        "prep_time_minutes": 20,
    })

    recipes.append({
        "name": "Falafel Bowl au Boulgour et Houmous",
        "meal_type": "dejeuner",
        "cuisine_type": "libanaise",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Falafel", 120, "g", lookup),
            ing("Boulgour", 50, "g", lookup),
            ing("Concombre", 60, "g", lookup),
            ing("Tomate", 60, "g", lookup),
            ing("Persil frais", 8, "g", lookup),
            ing("Jus de citron", 10, "ml", lookup),
        ],
        "instructions": "1. Cuire le boulgour 12 min et laisser refroidir. 2. Réchauffer les falafels au four 10 min à 180°C. 3. Couper le concombre et la tomate en dés. 4. Assembler le bol : boulgour, falafels, légumes. 5. Parsemer de persil et arroser de citron.",
        "prep_time_minutes": 20,
    })

    recipes.append({
        "name": "Bún Chay Vietnamien aux Légumes et Tofu",
        "meal_type": "dejeuner",
        "cuisine_type": "vietnamienne",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Nouilles de riz", 60, "g", lookup),
            ing("Tofu ferme", 130, "g", lookup),
            ing("Carottes", 50, "g", lookup),
            ing("Concombre", 50, "g", lookup),
            ing("Menthe fraîche", 5, "g", lookup),
            ing("Sauce soja allégée", 10, "ml", lookup),
            ing("Jus de citron", 10, "ml", lookup),
        ],
        "instructions": "1. Cuire les nouilles de riz et les rincer à l'eau froide. 2. Couper le tofu en cubes et le griller à la poêle. 3. Râper les carottes et trancher le concombre. 4. Préparer la sauce avec la sauce soja et le jus de citron. 5. Assembler les nouilles, le tofu et les légumes. 6. Garnir de menthe fraîche et napper de sauce.",
        "prep_time_minutes": 20,
    })

    recipes.append({
        "name": "Salade Grecque de Lentilles au Citron et Origan",
        "meal_type": "dejeuner",
        "cuisine_type": "grecque",
        "diet_type": "vegan",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Lentilles vertes cuites", 150, "g", lookup),
            ing("Concombre", 80, "g", lookup),
            ing("Tomates cerises", 60, "g", lookup),
            ing("Olives noires dénoyautées", 15, "g", lookup),
            ing("Jus de citron", 15, "ml", lookup),
            ing("Origan séché", 3, "g", lookup),
            ing("Oignon rouge", 30, "g", lookup),
        ],
        "instructions": "1. Rincer les lentilles cuites. 2. Couper le concombre, les tomates et l'oignon. 3. Mélanger avec les olives et les lentilles. 4. Assaisonner de jus de citron et d'origan. 5. Servir frais.",
        "prep_time_minutes": 10,
    })

    recipes.append({
        "name": "Dak Galbi Poulet Coréen Épicé",
        "meal_type": "dejeuner",
        "cuisine_type": "coréenne",
        "diet_type": "omnivore",
        "tags": ["high-protein", "low-fat", "sportif"],
        "ingredients": [
            ing("Blanc de poulet", 150, "g", lookup),
            ing("Patate douce", 80, "g", lookup),
            ing("chou chinois", 60, "g", lookup),
            ing("Sauce soja allégée", 15, "ml", lookup),
            ing("Gingembre frais", 5, "g", lookup),
            ing("Riz complet", 60, "g", lookup),
        ],
        "instructions": "1. Couper le poulet en morceaux et mariner dans la sauce soja et le gingembre. 2. Couper la patate douce en cubes et le chou en lanières. 3. Faire sauter le poulet à feu vif 5 min. 4. Ajouter les légumes et cuire 10 min. 5. Cuire le riz complet. 6. Servir le dak galbi sur le riz.",
        "prep_time_minutes": 25,
    })

    return recipes


# ---------------------------------------------------------------------------
# Validation & build
# ---------------------------------------------------------------------------


def validate_and_build(
    recipes: list[dict],
    lookup: dict[str, dict],
    existing_sigs: set[str],
) -> list[dict]:
    """Validate each recipe, calculate macros, build DB rows."""
    valid_rows: list[dict] = []
    errors: list[str] = []

    for recipe in recipes:
        name = recipe["name"]
        meal_type = recipe["meal_type"]
        sig = f"{normalize(name)}|{meal_type}"

        # Check duplicate with existing DB
        if sig in existing_sigs:
            errors.append(f"DUPLICATE: {name} ({meal_type}) already exists")
            continue

        # Check all ingredients exist in validated list
        missing = [
            i["name"] for i in recipe["ingredients"] if i["name"] not in lookup
        ]
        if missing:
            errors.append(f"MISSING INGREDIENTS in '{name}': {missing}")
            continue

        # Check minimum ingredients
        if len(recipe["ingredients"]) < 3:
            errors.append(f"TOO FEW INGREDIENTS in '{name}': {len(recipe['ingredients'])}")
            continue

        # Check instructions
        if not recipe.get("instructions"):
            errors.append(f"NO INSTRUCTIONS for '{name}'")
            continue

        # Calculate macros
        macros = calc_macros(recipe["ingredients"])
        cal = macros["calories"]
        prot = macros["protein_g"]
        fat = macros["fat_g"]
        carbs = macros["carbs_g"]

        # Validate calorie ranges
        if meal_type == "collation":
            if not (100 <= cal <= 350):
                errors.append(f"CAL OUT OF RANGE for collation '{name}': {cal:.0f}")
                continue
        else:
            if not (250 <= cal <= 750):
                errors.append(f"CAL OUT OF RANGE for '{name}' ({meal_type}): {cal:.0f}")
                continue

        # Detect allergens
        allergens = detect_allergens(recipe["ingredients"])

        # Build DB row
        row = {
            "name": name,
            "name_normalized": normalize(name),
            "description": f"{name} — recette sportive riche en protéines.",
            "meal_type": meal_type,
            "cuisine_type": recipe["cuisine_type"],
            "diet_type": recipe["diet_type"],
            "prep_time_minutes": recipe.get("prep_time_minutes", 20),
            "ingredients": recipe["ingredients"],
            "instructions": recipe["instructions"],
            "tags": recipe.get("tags", []),
            "allergen_tags": allergens,
            "calories_per_serving": round(cal, 1),
            "protein_g_per_serving": round(prot, 1),
            "carbs_g_per_serving": round(carbs, 1),
            "fat_g_per_serving": round(fat, 1),
            "source": "seed-gap-analysis",
            "off_validated": True,
        }
        valid_rows.append(row)

    # Report errors
    for err in errors:
        logger.warning(err)

    return valid_rows


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def seed() -> None:
    supabase = get_supabase_client()
    lookup = load_ingredient_lookup()
    existing_sigs = load_existing_signatures()

    recipes = define_recipes(lookup)
    logger.info(f"Defined {len(recipes)} recipes")

    rows = validate_and_build(recipes, lookup, existing_sigs)
    logger.info(f"Validated {len(rows)} recipes (rejected {len(recipes) - len(rows)})")

    # Print macro stats per priority
    collations = [r for r in rows if r["meal_type"] == "collation"]
    pdej = [r for r in rows if r["meal_type"] == "petit-dejeuner"]
    mains = [r for r in rows if r["meal_type"] in ("dejeuner", "diner")]

    for label, group in [("Collations", collations), ("Petits-déjeuners", pdej), ("Dejeuner/Diner", mains)]:
        if group:
            avg_cal = sum(r["calories_per_serving"] for r in group) / len(group)
            avg_prot = sum(r["protein_g_per_serving"] for r in group) / len(group)
            avg_fat = sum(r["fat_g_per_serving"] for r in group) / len(group)
            logger.info(
                f"  {label} ({len(group)}): avg cal={avg_cal:.0f}, prot={avg_prot:.1f}g, fat={avg_fat:.1f}g"
            )

    # Upsert into DB
    inserted = 0
    failed = 0
    counts: dict[str, int] = {}

    for row in rows:
        try:
            supabase.table("recipes").upsert(
                row, on_conflict="name_normalized,meal_type"
            ).execute()
            inserted += 1
            mt = row["meal_type"]
            counts[mt] = counts.get(mt, 0) + 1
            logger.info(
                f"  ✓ {row['name']} ({row['calories_per_serving']:.0f} kcal, "
                f"P{row['protein_g_per_serving']:.0f}g F{row['fat_g_per_serving']:.0f}g)"
            )
        except Exception as e:
            logger.error(f"  ✗ {row['name']}: {e}")
            failed += 1

    logger.info(f"\nDone: {inserted} inserted, {failed} failed.")
    logger.info(f"Coverage: {counts}")


if __name__ == "__main__":
    asyncio.run(seed())
