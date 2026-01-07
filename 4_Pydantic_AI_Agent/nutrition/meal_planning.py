"""
Helper functions for meal plan generation workflow.

Provides prompt building, daily total calculations, and response formatting.
"""

import logging
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)

# Meal structure definitions
MEAL_STRUCTURES = {
    "3_meals_2_snacks": {
        "description": "3 main meals + 2 snacks",
        "meals": [
            "Petit-déjeuner (07:30)",
            "Collation AM (10:00)",
            "Déjeuner (12:30)",
            "Collation PM (16:00)",
            "Dîner (19:30)",
        ],
    },
    "4_meals": {
        "description": "4 equal meals",
        "meals": [
            "Repas 1 (08:00)",
            "Repas 2 (12:00)",
            "Repas 3 (16:00)",
            "Repas 4 (20:00)",
        ],
    },
    "3_consequent_meals": {
        "description": "3 consecutive main meals (no snacks)",
        "meals": ["Petit-déjeuner (08:00)", "Déjeuner (13:00)", "Dîner (19:00)"],
    },
    "3_meals_1_preworkout": {
        "description": "3 meals + 1 snack before training",
        "meals": [
            "Petit-déjeuner (07:30)",
            "Déjeuner (12:30)",
            "Collation pré-entraînement (16:30)",
            "Dîner (20:00)",
        ],
    },
}


def build_meal_plan_prompt(
    profile: dict,
    rag_context: str,
    start_date: str,
    meal_structure: str,
    notes: str | None = None,
    calculate_macros: bool = True,
) -> str:
    """
    Build comprehensive prompt for GPT-4o meal plan generation.

    Args:
        profile: User profile dict with allergies, targets, preferences
        rag_context: Scientific context from RAG retrieval
        start_date: Start date in YYYY-MM-DD format
        meal_structure: Meal structure key (e.g., "3_meals_2_snacks")
        notes: Additional user preferences or constraints

    Returns:
        Formatted prompt string for LLM

    Example:
        >>> prompt = build_meal_plan_prompt(
        ...     {"allergies": ["arachides"], "target_calories": 3000},
        ...     "RAG context...",
        ...     "2024-12-23",
        ...     "3_meals_2_snacks"
        ... )
        >>> "ALLERGIES" in prompt
        True
    """

    # Extract profile data with safe defaults
    # Ensure all list fields are actually lists (handle None, strings, etc.)
    def ensure_list(value):
        """Convert value to list if it's not already one."""
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            return [value] if value else []
        return []

    allergies_str = ", ".join(ensure_list(profile.get("allergies"))) or "AUCUNE"
    disliked_str = ", ".join(ensure_list(profile.get("disliked_foods"))) or "Aucun"
    favorites_str = ", ".join(ensure_list(profile.get("favorite_foods"))) or "Aucun"
    cuisines_str = ", ".join(ensure_list(profile.get("preferred_cuisines"))) or "Toutes"

    calories = profile.get("target_calories") or 2500
    protein = profile.get("target_protein_g") or 150
    carbs = profile.get("target_carbs_g") or 300
    fat = profile.get("target_fat_g") or 80

    max_prep_time = profile.get("max_prep_time", 60)
    diet_type = profile.get("diet_type", "omnivore")

    # Get meal structure info
    structure_info = MEAL_STRUCTURES[meal_structure]
    meals_list = "\n".join([f"  - {meal}" for meal in structure_info["meals"]])

    # Calculate dates for the week
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    days_of_week = []
    for i in range(7):
        day_dt = start_dt + timedelta(days=i)
        day_name = [
            "Lundi",
            "Mardi",
            "Mercredi",
            "Jeudi",
            "Vendredi",
            "Samedi",
            "Dimanche",
        ][day_dt.weekday()]
        days_of_week.append(f"{day_name} {day_dt.strftime('%Y-%m-%d')}")

    # Build allergen details with explicit examples
    allergen_details = []
    allergen_mapping = {
        "arachides": {
            "avoid": [
                "arachide",
                "cacahuète",
                "beurre de cacahuète",
                "huile d'arachide",
            ],
            "safe_alt": ["beurre de tournesol", "beurre de soja"],
        },
        "fruits à coque": {
            "avoid": [
                "amande",
                "noix",
                "noisette",
                "cajou",
                "pistache",
                "noix de pécan",
                "noix de macadamia",
                "noix du brésil",
                "lait d'amande",
                "beurre d'amande",
            ],
            "safe_alt": ["lait d'avoine", "lait de soja", "lait de riz"],
        },
        "lait": {
            "avoid": [
                "lait",
                "yaourt",
                "fromage",
                "beurre",
                "crème",
                "lactosérum",
                "caséine",
            ],
            "safe_alt": ["lait d'avoine", "lait de soja", "yaourt végétal"],
        },
        "œufs": {
            "avoid": ["œuf", "blanc d'œuf", "jaune d'œuf", "mayonnaise"],
            "safe_alt": ["graines de lin moulues", "compote de pomme"],
        },
    }

    if allergies_str != "AUCUNE":
        user_allergens = [a.strip().lower() for a in allergies_str.split(",")]
        for allergen in user_allergens:
            if allergen in allergen_mapping:
                details = allergen_mapping[allergen]
                avoid_list = ", ".join(details["avoid"])
                safe_list = ", ".join(details["safe_alt"])
                allergen_details.append(
                    f"  • {allergen.upper()}: ÉVITER ABSOLUMENT [{avoid_list}]\n"
                    f"    ✅ Alternatives sûres: {safe_list}"
                )

    allergen_section = (
        "\n".join(allergen_details) if allergen_details else "AUCUNE allergie"
    )

    prompt = f"""Tu es un nutritionniste expert créant un plan de repas personnalisé pour 7 jours.

🚨🚨🚨 CONTRAINTE CRITIQUE - ALLERGIES 🚨🚨🚨
ALLERGIES DE L'UTILISATEUR : {allergies_str}
{allergen_section}

⚠️ TOLÉRANCE ZÉRO - Si tu utilises LAIT D'AMANDE, BEURRE D'AMANDE ou tout ingrédient contenant
"amande", "noix", "cajou", etc., le plan sera REJETÉ. Utilise uniquement les alternatives sûres listées.

Vérifie CHAQUE ingrédient avant de l'inclure dans une recette

═══════════════════════════════════════════════════════════════

PROFIL UTILISATEUR :
- Objectif calorique quotidien : {calories} kcal (tolérance ±10%)
- Macronutriments cibles :
  * Protéines : {protein}g/jour
  * Glucides : {carbs}g/jour
  * Lipides : {fat}g/jour
- 🚨 ALLERGIES : {allergies_str} (TOLÉRANCE ZÉRO - VÉRIFIER CHAQUE INGRÉDIENT)
- Aliments détestés : {disliked_str}
- Aliments favoris : {favorites_str}
- Cuisines préférées : {cuisines_str}
- Temps de préparation max : {max_prep_time} min
- Type de régime : {diet_type}

═══════════════════════════════════════════════════════════════

STRUCTURE DE REPAS : {meal_structure}
Description : {structure_info["description"]}

Repas quotidiens :
{meals_list}

═══════════════════════════════════════════════════════════════

CONTEXTE SCIENTIFIQUE (bases nutritionnelles) :
{rag_context[:1500]}

═══════════════════════════════════════════════════════════════

NOTES SUPPLÉMENTAIRES :
{notes or "Aucune note supplémentaire"}

═══════════════════════════════════════════════════════════════

INSTRUCTIONS DE GÉNÉRATION :

1. GÉNÈRE un plan de 7 jours complet avec des recettes détaillées
2. CHAQUE recette doit inclure :
   - Nom de la recette (créatif et appétissant)
   - Liste complète des ingrédients avec quantités précises (en grammes de préférence)
   - Instructions de préparation (1 seule chaîne de texte, séparer les étapes par des points)
   {"- Informations nutritionnelles PRÉCISES (calories, protéines, glucides, lipides)" if calculate_macros else ""}

{"""
🚨 NE CALCULE PAS LES MACROS 🚨

Fournis SEULEMENT :
- Noms des recettes (créatifs et appétissants)
- Ingrédients avec quantités précises (ex: 'poulet': 200, 'riz': 150, unités en grammes)
- Instructions de préparation

NE fournis PAS de champs 'nutrition' ou 'daily_totals' dans le JSON.
Les macros seront calculés automatiquement via FatSecret API avec une précision de 100%.

Concentre-toi sur :
- VARIÉTÉ des recettes (7 jours différents, créatifs, savoureux)
- GOÛT et plaisir culinaire
- RESPECT STRICT des allergènes : """ + allergies_str + """
- Quantités réalistes et préparables

IMPORTANT : Structure JSON exacte à respecter :
{{
  "days": [
    {{
      "day": "Lundi",
      "meals": [
        {{
          "name": "Nom de la recette",
          "time": "07:30",
          "ingredients": [
            {{"name": "poulet", "quantity": 200, "unit": "g"}},
            {{"name": "riz basmati", "quantity": 150, "unit": "g"}}
          ],
          "instructions": "Instructions de préparation ici",
          "tags": ["petit-déjeuner"]
        }}
      ]
    }}
  ]
}}

3. 🎯 CIBLES NUTRITIONNELLES (pour info uniquement, ne calcule pas) :
   - Calories cible : """ + str(calories) + """ kcal/jour
   - Protéines cible : """ + str(protein) + """g/jour
   - Glucides cible : """ + str(carbs) + """g/jour
   - Lipides cible : """ + str(fat) + """g/jour

   Le système FatSecret ajustera automatiquement les portions pour atteindre ces cibles.
""" if not calculate_macros else """
3. 🎯 MACROS OBLIGATOIRES (NON-NÉGOCIABLE) :"""}
   - Chaque jour DOIT atteindre EXACTEMENT : {calories} kcal (±3% MAX - si en dessous, plan REJETÉ)
   - Protéines : {protein}g ±3% MAX (CRITIQUE pour prise de muscle - PRIORITÉ ABSOLUE)
   - Glucides : {carbs}g ±5% MAX
   - Lipides : {fat}g ±8% MAX

   🚨 INSTRUCTION CRITIQUE - NE GÉNÈRE PAS EN DESSOUS DE LA CIBLE 🚨
   Si ton plan fait 2500 kcal alors que la cible est {calories} kcal, c'est INACCEPTABLE.
   AUGMENTE les portions de glucides/lipides pour atteindre EXACTEMENT la cible.
   Il vaut mieux être à +2% qu'à -15% !

   📐 EXEMPLE DE CALCUL POUR ATTEINDRE {calories} KCAL :

   Si ton premier brouillon donne 2540 kcal (déficit de {int(calories - 2540)} kcal), AUGMENTE :
   - Riz/Pâtes : +50g cru = +180 kcal, +40g glucides
   - Huile d'olive : +10ml = +90 kcal, +10g lipides
   - Pain : +30g = +75 kcal, +15g glucides
   - Fruits secs : +20g = +100 kcal, +15g glucides, +5g lipides

   VÉRIFIE : 2540 + 180 + 90 + 75 = 2885 kcal → Proche de {calories} kcal ✅

   Si encore en dessous, AJOUTE une collation supplémentaire (ex: banane + beurre d'amande = 200 kcal)

   🚨🚨🚨 INSTRUCTION CRITIQUE - PROTÉINES 🚨🚨🚨
   Pour atteindre {protein}g de protéines, utilise CETTE RÉPARTITION EXACTE :

   RÉPARTITION PROTÉINES OBLIGATOIRE PAR REPAS :
   ┌─────────────────┬──────────────┬───────────────────────────────┐
   │ Repas           │ Protéines    │ Sources recommandées          │
   ├─────────────────┼──────────────┼───────────────────────────────┤
   │ Petit-déjeuner  │ 35-40g       │ Œufs (3-4) + yaourt grec 0%   │
   │ Collation 1     │ 25-30g       │ Shaker protéine + banane      │
   │ Déjeuner        │ 45-50g       │ Poulet 200g / Poisson 250g    │
   │ Collation 2     │ 25-30g       │ Fromage blanc 200g + fruits   │
   │ Dîner           │ 40-45g       │ Viande 200g / Poisson 250g    │
   └─────────────────┴──────────────┴───────────────────────────────┘
   TOTAL MINIMUM : 170g (donne marge de sécurité pour {protein}g cible)

   **ALIMENTS RICHES EN PROTÉINES (utilise massivement) :**
   - Poulet : 30g protéines / 100g
   - Poisson blanc : 25g protéines / 100g
   - Œufs : 6g protéines / œuf (utilise 3-4 par petit-déjeuner)
   - Yaourt grec 0% : 10g protéines / 100g
   - Fromage blanc 0% : 8g protéines / 100g
   - Poudre protéine : 25g protéines / dose (AJOUTE si besoin)

   **VÉRIFICATION FINALE AVANT DE GÉNÉRER LE JSON :**
   1. ADDITIONNE les protéines : petit-déj + coll1 + déj + coll2 + dîner
   2. Si total < {protein}g → AJOUTE shaker protéiné (25g) à une collation
   3. Si total > {protein}g + 10% → RÉDUIS portions de viande
   4. ÉCRIS le total dans daily_totals.protein_g
   5. VÉRIFIE que daily_totals.protein_g est entre {int(protein * 0.95)}g et {int(protein * 1.05)}g

4. 🎯 CALORIES OBLIGATOIRES : {calories} kcal/jour (±5% MAX)

   RÉPARTITION CALORIES PAR REPAS :
   - Petit-déjeuner : ~{int(calories * 0.20)} kcal (20%)
   - Collation 1 : ~{int(calories * 0.10)} kcal (10%)
   - Déjeuner : ~{int(calories * 0.35)} kcal (35%)
   - Collation 2 : ~{int(calories * 0.10)} kcal (10%)
   - Dîner : ~{int(calories * 0.25)} kcal (25%)

   **VÉRIFICATION CALORIES FINALE :**
   - ADDITIONNE : petit-déj + coll1 + déj + coll2 + dîner
   - VÉRIFIE que daily_totals.calories est entre {int(calories * 0.95)} et {int(calories * 1.05)} kcal
   - Si trop bas → AUGMENTE portions de glucides (riz, pâtes, pain)
   - Si trop haut → RÉDUIS lipides (huile, fromage, avocat)

5. VARIE les recettes (pas de répétitions exactes sur la semaine)
6. RESPECTE le temps de préparation maximum
7. ADAPTE au type de régime ({diet_type})
8. 🚨 VÉRIFIE chaque ingrédient contre les allergies : {allergies_str}

═══════════════════════════════════════════════════════════════

🚨🚨🚨 VÉRIFICATION FINALE OBLIGATOIRE AVANT GÉNÉRATION 🚨🚨🚨

AVANT de générer le JSON, pour CHAQUE jour, vérifie :

✅ CHECKLIST MACROS (CRITIQUE) :
   □ daily_totals.calories entre {int(calories * 0.95)} et {int(calories * 1.05)} kcal ?
   □ daily_totals.protein_g entre {int(protein * 0.95)} et {int(protein * 1.05)}g ?
   □ daily_totals.carbs_g entre {int(carbs * 0.90)} et {int(carbs * 1.10)}g ?
   □ daily_totals.fat_g entre {int(fat * 0.90)} et {int(fat * 1.10)}g ?

✅ CHECKLIST SÉCURITÉ :
   □ AUCUN ingrédient avec allergènes : {allergies_str} ?
   □ AUCUN aliment détesté : {disliked_str} ?

✅ CHECKLIST QUALITÉ :
   □ 5 repas définis (petit-déj, coll1, déj, coll2, dîner) ?
   □ Chaque recette a nom, ingrédients, instructions, nutrition ?
   □ 7 jours complets (pas de "...") ?

Si UNE SEULE case n'est pas cochée → AJUSTE le plan avant de générer le JSON.

═══════════════════════════════════════════════════════════════

FORMAT JSON REQUIS (STRUCTURE EXACTE) :

⚠️ RÈGLES JSON CRITIQUES :
- PAS de commentaires (//) dans le JSON
- Utilise des guillemets doubles (") partout
- Échappe les apostrophes dans le texte : utilise "l apostrophe" au lieu de "l'apostrophe"
- Instructions en 1 seule chaîne de texte (pas de tableau)
- GÉNÈRE LES 7 JOURS COMPLETS (pas de "...")

{{
  "meal_plan_id": "plan_{start_date}",
  "start_date": "{start_date}",
  "meal_structure": "{meal_structure}",
  "daily_targets": {{
    "calories": {calories},
    "protein_g": {protein},
    "carbs_g": {carbs},
    "fat_g": {fat}
  }},
  "days": [
    {{
      "day": "{days_of_week[0]}",
      "date": "{start_date}",
      "meals": [
        {{
          "meal_type": "Petit-déjeuner",
          "time": "07:30",
          "recipe_name": "Omelette aux épinards et toast avocat",
          "servings": 1,
          "prep_time_min": 15,
          "ingredients": [
            {{"name": "oeufs", "quantity": 3, "unit": "pièces"}},
            {{"name": "épinards frais", "quantity": 50, "unit": "g"}},
            {{"name": "pain complet", "quantity": 60, "unit": "g"}},
            {{"name": "avocat", "quantity": 80, "unit": "g"}}
          ],
          "instructions": "Battre les oeufs. Faire revenir les épinards dans une poêle. Ajouter les oeufs battus et cuire en omelette. Griller le pain et étaler l avocat. Servir ensemble.",
          "nutrition": {{
            "calories": 520,
            "protein_g": 28,
            "carbs_g": 45,
            "fat_g": 24
          }},
          "tags": ["protéiné", "rapide", "petit-déjeuner"]
        }}
      ],
      "daily_totals": {{
        "calories": {calories},
        "protein_g": {protein},
        "carbs_g": {carbs},
        "fat_g": {fat}
      }}
    }}
  ],
  "weekly_summary": {{
    "total_unique_recipes": 21,
    "avg_prep_time_min": 35,
    "allergen_check": "PASSED",
    "adherence_tips": "Préparer les ingrédients à l avance. Varier les sources de protéines. Ajuster les portions si nécessaire."
  }}
}}

🚨🚨🚨 INSTRUCTION CRITIQUE 🚨🚨🚨
TU DOIS GÉNÉRER EXACTEMENT 7 JOURS COMPLETS DANS LE TABLEAU "days".
- NE génère PAS seulement 1 ou 2 jours
- NE mets PAS de "..." ou commentaires
- CHAQUE jour doit avoir sa propre structure complète avec tous les repas
- Si tu ne génères pas les 7 jours, ta réponse sera REJETÉE

Les 7 jours sont : {", ".join(days_of_week)}

COMMENCE MAINTENANT avec le Jour 1 ({days_of_week[0]}) et CONTINUE jusqu'au Jour 7 ({days_of_week[6]}).

═══════════════════════════════════════════════════════════════

🚨🚨🚨 RAPPEL FINAL ALLERGIES 🚨🚨🚨
AVANT de soumettre le plan, VÉRIFIE TOUS les ingrédients :
- Allergies à éviter : {allergies_str}
- Aucun ingrédient ne doit contenir ces allergènes ou leurs dérivés
- En cas de doute, EXCLUS l'ingrédient

GÉNÈRE maintenant le plan JSON complet en respectant STRICTEMENT ce format.
"""

    logger.info(f"Prompt built: {len(prompt)} chars, allergies: {allergies_str}")
    return prompt


def calculate_daily_totals(meals: list[dict]) -> dict:
    """
    Sum nutritional totals from all meals in a day.

    Args:
        meals: List of meal dicts with nutrition field

    Returns:
        Dict with calories, protein_g, carbs_g, fat_g totals

    Example:
        >>> meals = [
        ...     {"nutrition": {"calories": 500, "protein_g": 30, "carbs_g": 50, "fat_g": 15}},
        ...     {"nutrition": {"calories": 600, "protein_g": 35, "carbs_g": 60, "fat_g": 20}}
        ... ]
        >>> totals = calculate_daily_totals(meals)
        >>> totals["calories"]
        1100
    """
    totals = {"calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0}

    for meal in meals:
        nutrition = meal.get("nutrition", {})
        totals["calories"] += nutrition.get("calories", 0)
        totals["protein_g"] += nutrition.get("protein_g", 0)
        totals["carbs_g"] += nutrition.get("carbs_g", 0)
        totals["fat_g"] += nutrition.get("fat_g", 0)

    logger.debug(f"Daily totals calculated: {totals}")
    return totals


def format_meal_plan_response(meal_plan: dict, store_success: bool) -> str:
    """
    Format meal plan for user-friendly JSON return.

    Args:
        meal_plan: Generated meal plan dict
        store_success: Whether database storage succeeded

    Returns:
        Formatted JSON string with meal plan and metadata

    Example:
        >>> plan = {"meal_plan_id": "plan_2024-12-23", "days": []}
        >>> response = format_meal_plan_response(plan, True)
        >>> "success" in response
        True
    """
    response = {
        "success": True,
        "message": "Meal plan generated successfully",
        "stored_in_database": store_success,
        "meal_plan": meal_plan,
        "summary": {
            "total_days": len(meal_plan.get("days", [])),
            "start_date": meal_plan.get("start_date", "N/A"),
            "meal_structure": meal_plan.get("meal_structure", "N/A"),
            "weekly_summary": meal_plan.get("weekly_summary", {}),
        },
    }

    logger.info(
        f"Response formatted: {len(meal_plan.get('days', []))} days, stored: {store_success}"
    )
    return json.dumps(response, indent=2, ensure_ascii=False)


# ============================================================================
# Shopping List Helper Functions
# ============================================================================

# Category keyword mappings for ingredient categorization
INGREDIENT_CATEGORIES = {
    "produce": [
        "tomate",
        "oignon",
        "ail",
        "carotte",
        "pomme",
        "banane",
        "orange",
        "citron",
        "salade",
        "laitue",
        "épinard",
        "brocoli",
        "courgette",
        "poivron",
        "concombre",
        "champignon",
        "avocat",
        "fruits",
        "légumes",
        "légume",
        "fruit",
    ],
    "proteins": [
        "poulet",
        "boeuf",
        "porc",
        "viande",
        "poisson",
        "thon",
        "saumon",
        "oeuf",
        "oeufs",
        "tofu",
        "tempeh",
        "lentille",
        "pois chiche",
        "haricot",
        "protéine",
    ],
    "grains": [
        "riz",
        "pâtes",
        "pain",
        "farine",
        "quinoa",
        "avoine",
        "céréale",
        "blé",
        "semoule",
        "couscous",
    ],
    "dairy": [
        "lait",
        "fromage",
        "yaourt",
        "yogurt",
        "beurre",
        "crème",
        "cream",
    ],
    "pantry": [
        "huile",
        "sel",
        "poivre",
        "épice",
        "sauce",
        "miel",
        "sucre",
        "vinaigre",
        "moutarde",
        "mayonnaise",
    ],
}


def extract_ingredients_from_meal_plan(
    meal_plan_data: dict, selected_days: list[int] | None = None
) -> list[dict]:
    """
    Extract ingredients from meal plan for selected days.

    Args:
        meal_plan_data: Meal plan JSONB data (plan_data from database)
        selected_days: List of day indices to include (0-6), or None for all days

    Returns:
        List of ingredient dicts with name, quantity, unit

    Example:
        >>> plan_data = {"days": [{"meals": [{"ingredients": [...]}]}]}
        >>> ingredients = extract_ingredients_from_meal_plan(plan_data, [0, 1])
        >>> len(ingredients) > 0
        True
    """
    if selected_days is None:
        selected_days = list(range(7))  # All 7 days

    ingredients_list = []
    days = meal_plan_data.get("days", [])

    for day_idx in selected_days:
        if day_idx >= len(days):
            logger.warning(
                f"Day index {day_idx} out of range (plan has {len(days)} days)"
            )
            continue

        day = days[day_idx]
        meals = day.get("meals", [])

        for meal in meals:
            meal_ingredients = meal.get("ingredients", [])
            ingredients_list.extend(meal_ingredients)

    logger.info(
        f"Extracted {len(ingredients_list)} ingredients from {len(selected_days)} days"
    )
    return ingredients_list


def aggregate_ingredients(
    ingredients_list: list[dict], servings_multiplier: float = 1.0
) -> dict:
    """
    Aggregate ingredient quantities by name+unit, apply servings multiplier.

    Args:
        ingredients_list: List of ingredient dicts with name, quantity, unit
        servings_multiplier: Multiplier for all quantities (e.g., 2.0 for double portions)

    Returns:
        Dict mapping "ingredient_name|unit" to total quantity

    Example:
        >>> ingredients = [
        ...     {"name": "riz", "quantity": 200, "unit": "g"},
        ...     {"name": "riz", "quantity": 150, "unit": "g"},
        ...     {"name": "riz", "quantity": 1, "unit": "tasse"}
        ... ]
        >>> result = aggregate_ingredients(ingredients, servings_multiplier=1.5)
        >>> result["riz|g"]
        525.0
    """
    aggregated: dict[str, float] = {}

    for ingredient in ingredients_list:
        name = ingredient.get("name", "").strip().lower()
        quantity = ingredient.get("quantity", 0)
        unit = ingredient.get("unit", "").strip().lower()

        if not name or not unit:
            logger.warning(f"Skipping invalid ingredient: {ingredient}")
            continue

        # Create unique key: ingredient_name|unit
        key = f"{name}|{unit}"

        # Apply servings multiplier and aggregate
        adjusted_quantity = quantity * servings_multiplier

        if key in aggregated:
            aggregated[key] += adjusted_quantity
        else:
            aggregated[key] = adjusted_quantity

    logger.info(
        f"Aggregated {len(ingredients_list)} ingredients into {len(aggregated)} unique items"
    )
    return aggregated


def categorize_ingredients(aggregated_ingredients: dict) -> dict:
    """
    Categorize aggregated ingredients into food groups.

    Uses keyword matching against INGREDIENT_CATEGORIES.
    Ingredients not matching any category go into "other".

    Args:
        aggregated_ingredients: Dict mapping "name|unit" to quantity

    Returns:
        Dict with category names as keys, each containing list of
        {"name": str, "quantity": float, "unit": str} dicts

    Example:
        >>> agg = {"riz|g": 500, "poulet|g": 600, "unknown_item|kg": 2}
        >>> categorized = categorize_ingredients(agg)
        >>> "grains" in categorized
        True
        >>> "proteins" in categorized
        True
    """
    categorized: dict[str, list[dict]] = {
        "produce": [],
        "proteins": [],
        "grains": [],
        "dairy": [],
        "pantry": [],
        "other": [],
    }

    for key, quantity in aggregated_ingredients.items():
        # Parse key: "ingredient_name|unit"
        parts = key.split("|")
        if len(parts) != 2:
            logger.warning(f"Invalid aggregated key format: {key}")
            continue

        name, unit = parts
        ingredient_item = {"name": name, "quantity": round(quantity, 1), "unit": unit}

        # Find matching category
        matched_category = None
        for category, keywords in INGREDIENT_CATEGORIES.items():
            if any(keyword in name for keyword in keywords):
                matched_category = category
                break

        if matched_category:
            categorized[matched_category].append(ingredient_item)
        else:
            categorized["other"].append(ingredient_item)

    # Log category counts
    category_counts = {cat: len(items) for cat, items in categorized.items()}
    logger.info(f"Categorized ingredients: {category_counts}")

    return categorized
