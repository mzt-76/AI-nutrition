"""
Manual recipe seeder — no LLM API calls.

Defines 40 recipes (10 per meal type) with estimated calories + protein.
Derives carbs/fat via src.nutrition.calculations.calculate_macros().
Inserts directly into Supabase recipes table.

Run: python scripts/seed_recipes_manual.py
"""

import asyncio
import json
import unicodedata
import logging
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)

from src.clients import get_supabase_client
from src.nutrition.calculations import calculate_macros

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def normalize(name: str) -> str:
    """Lowercase + strip accents for deduplication."""
    nfkd = unicodedata.normalize("NFKD", name.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


# ---------------------------------------------------------------------------
# Recipe definitions: only fill what we know — macros computed automatically
# Format: (name, calories, protein_g, meal_type, cuisine, diet, prep_min,
#          ingredients, instructions, tags, allergen_tags)
# ---------------------------------------------------------------------------

RECIPES = [
    # ── PETIT-DÉJEUNER ──────────────────────────────────────────────────────
    (
        "Omelette aux herbes et fromage",
        380, 28, "petit-dejeuner", "française", "omnivore", 10,
        [{"name": "Œufs", "quantity": 3, "unit": "pièces"},
         {"name": "Gruyère râpé", "quantity": 30, "unit": "g"},
         {"name": "Ciboulette", "quantity": 10, "unit": "g"},
         {"name": "Beurre", "quantity": 10, "unit": "g"}],
        "Battre les œufs, ajouter le fromage et la ciboulette. Cuire dans le beurre à feu moyen 3 min.",
        ["high-protein", "low-carb", "quick"], ["gluten", "lactose", "oeuf"],
    ),
    (
        "Bol d'avoine aux fruits rouges",
        420, 14, "petit-dejeuner", "internationale", "végétarien", 5,
        [{"name": "Flocons d'avoine", "quantity": 80, "unit": "g"},
         {"name": "Lait demi-écrémé", "quantity": 200, "unit": "ml"},
         {"name": "Fruits rouges mélangés", "quantity": 100, "unit": "g"},
         {"name": "Miel", "quantity": 15, "unit": "g"}],
        "Chauffer le lait, verser sur les flocons. Laisser gonfler 3 min. Ajouter fruits et miel.",
        ["high-carb", "vegetarian", "quick"], ["gluten", "lactose"],
    ),
    (
        "Toast avocat et œuf poché",
        380, 16, "petit-dejeuner", "internationale", "végétarien", 10,
        [{"name": "Pain complet", "quantity": 2, "unit": "tranches"},
         {"name": "Avocat", "quantity": 80, "unit": "g"},
         {"name": "Œuf", "quantity": 1, "unit": "pièce"},
         {"name": "Jus de citron", "quantity": 5, "unit": "ml"}],
        "Toaster le pain. Écraser l'avocat avec le citron. Pocher l'œuf 3 min. Assembler.",
        ["vegetarian", "healthy-fats", "quick"], ["gluten", "oeuf"],
    ),
    (
        "Yaourt grec granola et miel",
        360, 18, "petit-dejeuner", "méditerranéenne", "végétarien", 5,
        [{"name": "Yaourt grec", "quantity": 200, "unit": "g"},
         {"name": "Granola", "quantity": 50, "unit": "g"},
         {"name": "Miel", "quantity": 15, "unit": "g"},
         {"name": "Noix", "quantity": 20, "unit": "g"}],
        "Verser le yaourt dans un bol. Ajouter le granola, les noix et le miel.",
        ["high-protein", "vegetarian", "quick"], ["lactose", "gluten", "noix"],
    ),
    (
        "Galette sarrasin jambon fromage",
        420, 24, "petit-dejeuner", "française", "omnivore", 15,
        [{"name": "Farine de sarrasin", "quantity": 60, "unit": "g"},
         {"name": "Jambon blanc", "quantity": 60, "unit": "g"},
         {"name": "Emmental râpé", "quantity": 30, "unit": "g"},
         {"name": "Œuf", "quantity": 1, "unit": "pièce"}],
        "Préparer la pâte sarrasin avec eau. Cuire la galette, garnir jambon, fromage et œuf.",
        ["high-protein", "gluten-free-option", "traditional"], ["lactose", "oeuf"],
    ),
    (
        "Smoothie protéiné banane épinards",
        340, 22, "petit-dejeuner", "internationale", "végétarien", 5,
        [{"name": "Banane", "quantity": 1, "unit": "pièce"},
         {"name": "Épinards frais", "quantity": 50, "unit": "g"},
         {"name": "Lait demi-écrémé", "quantity": 200, "unit": "ml"},
         {"name": "Protéine en poudre vanille", "quantity": 30, "unit": "g"}],
        "Mixer tous les ingrédients jusqu'à consistance lisse. Servir frais.",
        ["high-protein", "vegetarian", "quick", "smoothie"], ["lactose"],
    ),
    (
        "Pain complet beurre d'amande et banane",
        400, 12, "petit-dejeuner", "internationale", "végétarien", 5,
        [{"name": "Pain complet", "quantity": 2, "unit": "tranches"},
         {"name": "Beurre d'amande", "quantity": 30, "unit": "g"},
         {"name": "Banane", "quantity": 1, "unit": "pièce"}],
        "Toaster le pain. Tartiner de beurre d'amande. Trancher la banane dessus.",
        ["vegetarian", "quick", "energy"], ["gluten", "noix"],
    ),
    (
        "Fromage blanc fruits et graines",
        300, 20, "petit-dejeuner", "française", "végétarien", 5,
        [{"name": "Fromage blanc 0%", "quantity": 200, "unit": "g"},
         {"name": "Fruits rouges", "quantity": 80, "unit": "g"},
         {"name": "Graines de chia", "quantity": 15, "unit": "g"},
         {"name": "Miel", "quantity": 10, "unit": "g"}],
        "Mélanger le fromage blanc et le miel. Ajouter les fruits et les graines.",
        ["high-protein", "vegetarian", "low-cal", "quick"], ["lactose"],
    ),
    (
        "Crêpe protéinée avoine banane",
        360, 20, "petit-dejeuner", "française", "végétarien", 15,
        [{"name": "Flocons d'avoine mixés", "quantity": 60, "unit": "g"},
         {"name": "Œuf", "quantity": 2, "unit": "pièces"},
         {"name": "Banane", "quantity": 1, "unit": "pièce"},
         {"name": "Lait", "quantity": 50, "unit": "ml"}],
        "Mixer avoine, œufs, banane et lait. Cuire comme des crêpes épaisses à feu moyen.",
        ["high-protein", "vegetarian", "gluten-free-option"], ["gluten", "oeuf", "lactose"],
    ),
    (
        "Pain perdu cannelle et lait",
        420, 16, "petit-dejeuner", "française", "omnivore", 15,
        [{"name": "Pain de mie", "quantity": 2, "unit": "tranches"},
         {"name": "Œuf", "quantity": 2, "unit": "pièces"},
         {"name": "Lait", "quantity": 100, "unit": "ml"},
         {"name": "Cannelle", "quantity": 2, "unit": "g"},
         {"name": "Beurre", "quantity": 10, "unit": "g"}],
        "Battre œufs, lait et cannelle. Tremper le pain. Dorer au beurre 2 min par face.",
        ["traditional", "vegetarian", "comfort"], ["gluten", "oeuf", "lactose"],
    ),

    # ── DÉJEUNER ────────────────────────────────────────────────────────────
    (
        "Poulet grillé riz et brocolis",
        550, 45, "dejeuner", "internationale", "omnivore", 25,
        [{"name": "Blanc de poulet", "quantity": 180, "unit": "g"},
         {"name": "Riz basmati", "quantity": 80, "unit": "g"},
         {"name": "Brocolis", "quantity": 150, "unit": "g"},
         {"name": "Huile d'olive", "quantity": 10, "unit": "ml"}],
        "Cuire le riz 12 min. Griller le poulet 6 min par face. Vapeur les brocolis. Assaisonner.",
        ["high-protein", "meal-prep", "balanced"], [],
    ),
    (
        "Salade niçoise au thon",
        450, 35, "dejeuner", "méditerranéenne", "omnivore", 15,
        [{"name": "Thon en conserve", "quantity": 120, "unit": "g"},
         {"name": "Œufs durs", "quantity": 2, "unit": "pièces"},
         {"name": "Tomates cerises", "quantity": 100, "unit": "g"},
         {"name": "Olives noires", "quantity": 30, "unit": "g"},
         {"name": "Haricots verts", "quantity": 80, "unit": "g"},
         {"name": "Huile d'olive", "quantity": 15, "unit": "ml"}],
        "Cuire les haricots verts 5 min. Assembler tous les ingrédients. Arroser d'huile.",
        ["high-protein", "mediterranean", "no-cook"], ["oeuf", "poisson"],
    ),
    (
        "Pâtes saumon sauce légère",
        580, 38, "dejeuner", "italienne", "omnivore", 20,
        [{"name": "Pâtes complètes", "quantity": 80, "unit": "g"},
         {"name": "Saumon frais", "quantity": 150, "unit": "g"},
         {"name": "Crème fraîche légère", "quantity": 50, "unit": "ml"},
         {"name": "Aneth", "quantity": 5, "unit": "g"},
         {"name": "Citron", "quantity": 0.5, "unit": "pièce"}],
        "Cuire les pâtes al dente. Poêler le saumon 4 min. Mélanger avec crème et aneth.",
        ["high-protein", "omega3", "creamy"], ["gluten", "lactose", "poisson"],
    ),
    (
        "Bowl quinoa légumes rôtis",
        480, 18, "dejeuner", "internationale", "végétarien", 30,
        [{"name": "Quinoa", "quantity": 80, "unit": "g"},
         {"name": "Poivron rouge", "quantity": 100, "unit": "g"},
         {"name": "Courgette", "quantity": 100, "unit": "g"},
         {"name": "Pois chiches", "quantity": 80, "unit": "g"},
         {"name": "Huile d'olive", "quantity": 15, "unit": "ml"}],
        "Cuire le quinoa 15 min. Rôtir légumes et pois chiches 20 min à 200°C. Assembler.",
        ["vegetarian", "vegan", "meal-prep", "gluten-free"], [],
    ),
    (
        "Steak haché et patate douce",
        580, 42, "dejeuner", "française", "omnivore", 25,
        [{"name": "Steak haché 5%", "quantity": 180, "unit": "g"},
         {"name": "Patate douce", "quantity": 200, "unit": "g"},
         {"name": "Salade verte", "quantity": 50, "unit": "g"},
         {"name": "Huile d'olive", "quantity": 10, "unit": "ml"}],
        "Cuire la patate douce au four 25 min. Griller le steak 3 min par face. Servir avec salade.",
        ["high-protein", "balanced", "meal-prep"], [],
    ),
    (
        "Wrap thon et crudités",
        460, 32, "dejeuner", "internationale", "omnivore", 10,
        [{"name": "Tortilla de blé", "quantity": 1, "unit": "pièce"},
         {"name": "Thon en conserve", "quantity": 100, "unit": "g"},
         {"name": "Avocat", "quantity": 60, "unit": "g"},
         {"name": "Tomate", "quantity": 80, "unit": "g"},
         {"name": "Salade", "quantity": 30, "unit": "g"}],
        "Égoutter le thon. Écraser l'avocat. Disposer tous les ingrédients sur la tortilla. Rouler.",
        ["high-protein", "quick", "no-cook"], ["gluten", "poisson"],
    ),
    (
        "Soupe lentilles corail épinards",
        380, 20, "dejeuner", "méditerranéenne", "vegan", 25,
        [{"name": "Lentilles corail", "quantity": 100, "unit": "g"},
         {"name": "Épinards", "quantity": 80, "unit": "g"},
         {"name": "Tomates pelées", "quantity": 200, "unit": "g"},
         {"name": "Oignon", "quantity": 1, "unit": "pièce"},
         {"name": "Cumin", "quantity": 3, "unit": "g"}],
        "Faire revenir l'oignon. Ajouter lentilles, tomates et bouillon. Cuire 20 min. Ajouter épinards.",
        ["vegan", "high-fiber", "budget", "gluten-free"], [],
    ),
    (
        "Taboulé et poulet grillé",
        480, 36, "dejeuner", "méditerranéenne", "omnivore", 20,
        [{"name": "Semoule fine", "quantity": 80, "unit": "g"},
         {"name": "Blanc de poulet", "quantity": 150, "unit": "g"},
         {"name": "Concombre", "quantity": 80, "unit": "g"},
         {"name": "Tomates", "quantity": 80, "unit": "g"},
         {"name": "Persil", "quantity": 20, "unit": "g"},
         {"name": "Huile d'olive", "quantity": 10, "unit": "ml"}],
        "Hydrater la semoule. Griller le poulet. Mélanger semoule, légumes et persil. Servir ensemble.",
        ["high-protein", "mediterranean", "fresh"], ["gluten"],
    ),
    (
        "Risotto champignons parmesan",
        520, 16, "dejeuner", "italienne", "végétarien", 30,
        [{"name": "Riz arborio", "quantity": 80, "unit": "g"},
         {"name": "Champignons de Paris", "quantity": 150, "unit": "g"},
         {"name": "Parmesan", "quantity": 30, "unit": "g"},
         {"name": "Oignon", "quantity": 1, "unit": "pièce"},
         {"name": "Bouillon de légumes", "quantity": 400, "unit": "ml"}],
        "Faire revenir oignon et champignons. Ajouter riz, incorporer le bouillon louche par louche.",
        ["vegetarian", "comfort", "italian"], ["lactose", "gluten"],
    ),
    (
        "Escalope dinde haricots verts",
        450, 44, "dejeuner", "française", "omnivore", 20,
        [{"name": "Escalope de dinde", "quantity": 200, "unit": "g"},
         {"name": "Haricots verts", "quantity": 150, "unit": "g"},
         {"name": "Moutarde de Dijon", "quantity": 15, "unit": "g"},
         {"name": "Huile d'olive", "quantity": 10, "unit": "ml"}],
        "Badigeonner la dinde de moutarde. Griller 5 min par face. Cuire les haricots verts à la vapeur.",
        ["high-protein", "low-fat", "french"], [],
    ),

    # ── DÎNER ───────────────────────────────────────────────────────────────
    (
        "Saumon vapeur et haricots verts",
        400, 38, "diner", "française", "omnivore", 15,
        [{"name": "Pavé de saumon", "quantity": 180, "unit": "g"},
         {"name": "Haricots verts", "quantity": 150, "unit": "g"},
         {"name": "Citron", "quantity": 0.5, "unit": "pièce"},
         {"name": "Aneth", "quantity": 5, "unit": "g"}],
        "Cuire le saumon vapeur 10 min. Cuire haricots verts 5 min. Servir avec citron et aneth.",
        ["high-protein", "omega3", "light", "gluten-free"], ["poisson"],
    ),
    (
        "Poulet curry et riz basmati",
        560, 40, "diner", "asiatique", "omnivore", 30,
        [{"name": "Blanc de poulet", "quantity": 180, "unit": "g"},
         {"name": "Riz basmati", "quantity": 80, "unit": "g"},
         {"name": "Lait de coco", "quantity": 100, "unit": "ml"},
         {"name": "Curry en poudre", "quantity": 5, "unit": "g"},
         {"name": "Oignon", "quantity": 1, "unit": "pièce"}],
        "Faire revenir poulet et oignon. Ajouter curry et lait de coco. Mijoter 15 min. Servir avec riz.",
        ["high-protein", "spicy", "asian"], ["lactose"],
    ),
    (
        "Ratatouille et poulet rôti",
        380, 32, "diner", "française", "omnivore", 40,
        [{"name": "Blanc de poulet", "quantity": 150, "unit": "g"},
         {"name": "Courgette", "quantity": 100, "unit": "g"},
         {"name": "Aubergine", "quantity": 100, "unit": "g"},
         {"name": "Poivron", "quantity": 80, "unit": "g"},
         {"name": "Tomates concassées", "quantity": 150, "unit": "g"},
         {"name": "Huile d'olive", "quantity": 10, "unit": "ml"}],
        "Rôtir le poulet 20 min. Faire mijoter les légumes en ratatouille 25 min. Servir ensemble.",
        ["high-protein", "mediterranean", "low-carb", "gluten-free"], [],
    ),
    (
        "Cabillaud en papillote légumes",
        340, 38, "diner", "française", "omnivore", 20,
        [{"name": "Filet de cabillaud", "quantity": 200, "unit": "g"},
         {"name": "Courgette", "quantity": 100, "unit": "g"},
         {"name": "Tomates cerises", "quantity": 80, "unit": "g"},
         {"name": "Citron", "quantity": 0.5, "unit": "pièce"},
         {"name": "Huile d'olive", "quantity": 10, "unit": "ml"}],
        "Placer le cabillaud et légumes sur papier cuisson. Citronner. Fermer et cuire 15 min à 180°C.",
        ["high-protein", "light", "gluten-free", "omega3"], ["poisson"],
    ),
    (
        "Curry de pois chiches et épinards",
        420, 16, "diner", "asiatique", "vegan", 25,
        [{"name": "Pois chiches", "quantity": 150, "unit": "g"},
         {"name": "Épinards", "quantity": 100, "unit": "g"},
         {"name": "Lait de coco", "quantity": 100, "unit": "ml"},
         {"name": "Tomates concassées", "quantity": 150, "unit": "g"},
         {"name": "Curry", "quantity": 5, "unit": "g"}],
        "Faire revenir les épices. Ajouter pois chiches et tomates. Incorporer lait de coco 10 min.",
        ["vegan", "high-fiber", "gluten-free", "budget"], [],
    ),
    (
        "Omelette poireaux et chèvre",
        360, 24, "diner", "française", "végétarien", 15,
        [{"name": "Œufs", "quantity": 3, "unit": "pièces"},
         {"name": "Poireau", "quantity": 100, "unit": "g"},
         {"name": "Fromage de chèvre", "quantity": 50, "unit": "g"},
         {"name": "Beurre", "quantity": 10, "unit": "g"}],
        "Faire suer le poireau au beurre 5 min. Battre les œufs, verser sur les poireaux. Ajouter chèvre.",
        ["vegetarian", "low-carb", "quick"], ["oeuf", "lactose"],
    ),
    (
        "Velouté de potiron",
        240, 6, "diner", "française", "vegan", 30,
        [{"name": "Potiron", "quantity": 400, "unit": "g"},
         {"name": "Oignon", "quantity": 1, "unit": "pièce"},
         {"name": "Bouillon de légumes", "quantity": 500, "unit": "ml"},
         {"name": "Crème de coco", "quantity": 50, "unit": "ml"},
         {"name": "Muscade", "quantity": 1, "unit": "g"}],
        "Faire revenir oignon. Ajouter potiron et bouillon. Cuire 20 min. Mixer. Ajouter crème de coco.",
        ["vegan", "light", "comfort", "gluten-free"], [],
    ),
    (
        "Wok crevettes légumes",
        380, 32, "diner", "asiatique", "omnivore", 15,
        [{"name": "Crevettes décortiquées", "quantity": 150, "unit": "g"},
         {"name": "Brocolis", "quantity": 100, "unit": "g"},
         {"name": "Poivron rouge", "quantity": 80, "unit": "g"},
         {"name": "Sauce soja", "quantity": 15, "unit": "ml"},
         {"name": "Huile de sésame", "quantity": 10, "unit": "ml"},
         {"name": "Gingembre", "quantity": 5, "unit": "g"}],
        "Chauffer wok très chaud. Sauter les crevettes 3 min. Ajouter légumes et sauce. Cuire 5 min.",
        ["high-protein", "asian", "quick", "low-carb"], ["crustaces", "soja"],
    ),
    (
        "Escalope dinde champignons",
        360, 38, "diner", "française", "omnivore", 20,
        [{"name": "Escalope de dinde", "quantity": 200, "unit": "g"},
         {"name": "Champignons de Paris", "quantity": 150, "unit": "g"},
         {"name": "Échalote", "quantity": 1, "unit": "pièce"},
         {"name": "Crème légère", "quantity": 50, "unit": "ml"}],
        "Poêler la dinde 5 min par face. Faire revenir champignons et échalote. Déglacer à la crème.",
        ["high-protein", "french", "creamy"], ["lactose"],
    ),
    (
        "Lentilles et saumon poché",
        480, 40, "diner", "française", "omnivore", 25,
        [{"name": "Lentilles vertes", "quantity": 100, "unit": "g"},
         {"name": "Pavé de saumon", "quantity": 150, "unit": "g"},
         {"name": "Carotte", "quantity": 80, "unit": "g"},
         {"name": "Thym", "quantity": 2, "unit": "g"},
         {"name": "Huile d'olive", "quantity": 10, "unit": "ml"}],
        "Cuire les lentilles avec carottes et thym 20 min. Pocher le saumon 8 min. Servir ensemble.",
        ["high-protein", "omega3", "iron-rich", "gluten-free"], ["poisson"],
    ),

    # ── COLLATION ───────────────────────────────────────────────────────────
    (
        "Yaourt grec et amandes",
        200, 16, "collation", "méditerranéenne", "végétarien", 2,
        [{"name": "Yaourt grec", "quantity": 150, "unit": "g"},
         {"name": "Amandes", "quantity": 20, "unit": "g"},
         {"name": "Miel", "quantity": 10, "unit": "g"}],
        "Verser le yaourt dans un bol. Ajouter les amandes et le miel.",
        ["high-protein", "vegetarian", "quick", "low-carb"], ["lactose", "noix"],
    ),
    (
        "Fromage blanc miel et noix",
        220, 14, "collation", "française", "végétarien", 2,
        [{"name": "Fromage blanc", "quantity": 150, "unit": "g"},
         {"name": "Noix", "quantity": 20, "unit": "g"},
         {"name": "Miel", "quantity": 10, "unit": "g"}],
        "Mélanger fromage blanc et miel. Concasser les noix et ajouter dessus.",
        ["vegetarian", "quick", "high-protein"], ["lactose", "noix"],
    ),
    (
        "Pomme et beurre d'amande",
        240, 6, "collation", "internationale", "vegan", 2,
        [{"name": "Pomme", "quantity": 1, "unit": "pièce"},
         {"name": "Beurre d'amande", "quantity": 30, "unit": "g"}],
        "Couper la pomme en tranches. Servir avec le beurre d'amande pour tremper.",
        ["vegan", "quick", "gluten-free", "natural"], ["noix"],
    ),
    (
        "Shake protéiné chocolat",
        260, 24, "collation", "internationale", "végétarien", 3,
        [{"name": "Lait demi-écrémé", "quantity": 250, "unit": "ml"},
         {"name": "Protéine en poudre chocolat", "quantity": 30, "unit": "g"},
         {"name": "Banane", "quantity": 0.5, "unit": "pièce"}],
        "Mixer tous les ingrédients pendant 30 secondes. Servir immédiatement.",
        ["high-protein", "quick", "post-workout"], ["lactose"],
    ),
    (
        "Crackers houmous et crudités",
        220, 8, "collation", "méditerranéenne", "vegan", 5,
        [{"name": "Crackers de seigle", "quantity": 3, "unit": "pièces"},
         {"name": "Houmous", "quantity": 60, "unit": "g"},
         {"name": "Carotte", "quantity": 80, "unit": "g"},
         {"name": "Concombre", "quantity": 60, "unit": "g"}],
        "Tartiner les crackers de houmous. Couper les légumes en bâtonnets. Déguster.",
        ["vegan", "quick", "fiber-rich"], ["gluten", "sesame"],
    ),
    (
        "Œufs durs au sel",
        160, 14, "collation", "française", "végétarien", 12,
        [{"name": "Œufs", "quantity": 2, "unit": "pièces"},
         {"name": "Sel", "quantity": 1, "unit": "pincée"}],
        "Plonger les œufs dans l'eau bouillante 10 min. Refroidir et écaler.",
        ["high-protein", "vegetarian", "budget", "gluten-free", "quick"], ["oeuf"],
    ),
    (
        "Cottage cheese et fruits rouges",
        180, 16, "collation", "internationale", "végétarien", 2,
        [{"name": "Cottage cheese", "quantity": 150, "unit": "g"},
         {"name": "Fruits rouges mélangés", "quantity": 80, "unit": "g"}],
        "Mélanger le cottage cheese et les fruits rouges dans un bol.",
        ["high-protein", "vegetarian", "low-cal", "quick"], ["lactose"],
    ),
    (
        "Mélange noix et raisins secs",
        280, 6, "collation", "internationale", "vegan", 1,
        [{"name": "Noix mélangées", "quantity": 30, "unit": "g"},
         {"name": "Raisins secs", "quantity": 20, "unit": "g"},
         {"name": "Cranberries séchées", "quantity": 15, "unit": "g"}],
        "Mélanger noix et fruits secs dans un petit bol ou sachet.",
        ["vegan", "gluten-free", "energy", "portable"], ["noix"],
    ),
    (
        "Shake protéiné vanille et lait",
        240, 24, "collation", "internationale", "végétarien", 3,
        [{"name": "Lait demi-écrémé", "quantity": 250, "unit": "ml"},
         {"name": "Protéine en poudre vanille", "quantity": 30, "unit": "g"}],
        "Shaker vigoureusement le lait et la protéine pendant 30 secondes.",
        ["high-protein", "quick", "post-workout"], ["lactose"],
    ),
    (
        "Banane et beurre de cacahuète",
        280, 8, "collation", "internationale", "vegan", 2,
        [{"name": "Banane", "quantity": 1, "unit": "pièce"},
         {"name": "Beurre de cacahuète", "quantity": 30, "unit": "g"}],
        "Éplucher la banane. Tartiner ou tremper dans le beurre de cacahuète.",
        ["vegan", "gluten-free", "quick", "energy"], ["arachides"],
    ),
]


def build_recipe_row(recipe_tuple: tuple) -> dict:
    (name, calories, protein_g, meal_type, cuisine, diet,
     prep_min, ingredients, instructions, tags, allergen_tags) = recipe_tuple

    macros = calculate_macros(calories, protein_g, goal_type="maintenance")

    return {
        "name": name,
        "name_normalized": normalize(name),
        "description": f"{name} — recette équilibrée {cuisine}.",
        "meal_type": meal_type,
        "cuisine_type": cuisine,
        "diet_type": diet,
        "prep_time_minutes": prep_min,
        "ingredients": json.dumps(ingredients, ensure_ascii=False),
        "instructions": instructions,
        "tags": tags,
        "allergen_tags": allergen_tags,
        "calories_per_serving": float(calories),
        "protein_g_per_serving": float(protein_g),
        "carbs_g_per_serving": float(macros["carbs_g"]),
        "fat_g_per_serving": float(macros["fat_g"]),
        "source": "manual",
        "off_validated": False,
    }


def seed(supabase) -> None:
    counts = {"petit-dejeuner": 0, "dejeuner": 0, "diner": 0, "collation": 0}
    failed = 0

    for recipe_tuple in RECIPES:
        row = build_recipe_row(recipe_tuple)
        try:
            supabase.table("recipes").insert(row).execute()
            counts[row["meal_type"]] += 1
            logger.info(f"  ✓ {row['name']} ({row['calories_per_serving']} kcal, "
                        f"{row['protein_g_per_serving']}g protein)")
        except Exception as e:
            logger.error(f"  ✗ {row['name']}: {e}")
            failed += 1

    total = sum(counts.values())
    logger.info(f"\nDone: {total} inserted, {failed} failed.")
    logger.info(f"Coverage: {counts}")


if __name__ == "__main__":
    supabase = get_supabase_client()
    seed(supabase)
