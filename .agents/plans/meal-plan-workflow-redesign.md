# Workflow Redesign: Génération de Plan Hebdomadaire

**Date:** 2026-01-14
**Status:** 🔄 En Discussion
**Objectif:** Standardiser le processus, limiter les hallucinations, séparer LLM (créativité) et Python (calculs)

---

## 🎯 Principe Directeur

> **Le LLM crée des recettes originales. Python calcule et ajuste les quantités pour atteindre les macros.**

**Séparation des responsabilités :**
- 🤖 **LLM (GPT-4o)** : Créativité, variété, respect des préférences
- 🐍 **Python** : Calculs précis, validation, ajustements automatiques

---

## 📋 Workflow Proposé (10 Étapes)

### **Étape 1: Chargement du Profil Utilisateur**

**Responsable:** Python (tool `fetch_my_profile_tool`)

**Actions:**
```python
profile = await fetch_my_profile_tool(supabase)

# Données récupérées:
# - Biométrie: age, gender, weight_kg, height_cm
# - Objectifs: goals (muscle_gain, weight_loss, etc.)
# - 🚨 Allergies: allergies[] (CRITIQUE)
# - Préférences: disliked_foods[], favorite_foods[], preferred_cuisines[]
# - Contraintes: max_prep_time, diet_type
# - Cibles actuelles: target_calories, target_protein_g, target_carbs_g, target_fat_g
```

**Validation:**
- Si profil incomplet → Demander les infos manquantes à l'utilisateur
- Si cibles nutritionnelles manquantes → Passer à l'étape 2

**Output:** `profile` dict complet

---

### **Étape 2: Calcul des Macros Journalières**

**Responsable:** Python (tool `calculate_nutritional_needs_tool`)

**Actions:**
```python
# SI les cibles ne sont pas dans le profil OU utilisateur veut recalculer
nutritional_needs = await calculate_nutritional_needs_tool(
    age=profile['age'],
    gender=profile['gender'],
    weight_kg=profile['weight_kg'],
    height_cm=profile['height_cm'],
    activity_level=profile['activity_level'],
    goals=profile['goals'],  # Ex: {"muscle_gain": 7, "performance": 5}
    activities=profile.get('activities'),
    context=None  # Pas besoin si goals explicites
)

# Résultat:
# - bmr: 1950 kcal (Mifflin-St Jeor)
# - tdee: 3022 kcal (TDEE = BMR × activity multiplier)
# - target_calories: 3300 kcal (TDEE + surplus/déficit selon goal)
# - target_protein_g: 174g (2.0g/kg pour muscle_gain)
# - target_carbs_g: 413g
# - target_fat_g: 92g
```

**Output:** Macros journalières validées

---

### **Étape 3: Calcul des Macros PAR REPAS**

**Responsable:** Python (nouvelle fonction `calculate_meal_macros_distribution`)

**Actions:**
```python
def calculate_meal_macros_distribution(
    daily_calories: int,
    daily_protein_g: int,
    daily_carbs_g: int,
    daily_fat_g: int,
    meal_structure: str  # "3_meals_2_snacks", "4_meals", etc.
) -> dict:
    """
    Répartit les macros journalières entre les repas selon la structure choisie.

    Règles de répartition:
    - Repas principaux (petit-déj, déj, dîner): 75% des calories, 80% des protéines
    - Collations: 25% des calories, 20% des protéines
    - Si pas de collations: répartition équitable

    Returns:
        {
            "meals": [
                {
                    "meal_type": "Petit-déjeuner",
                    "time": "07:30",
                    "target_calories": 825,  # 25% de 3300 kcal
                    "target_protein_g": 58,   # 33% de 174g (si 3 repas principaux)
                    "target_carbs_g": 103,
                    "target_fat_g": 31
                },
                {
                    "meal_type": "Collation AM",
                    "time": "10:00",
                    "target_calories": 412,  # 12.5% de 3300 kcal
                    "target_protein_g": 17,   # 10% de 174g (si 2 collations)
                    "target_carbs_g": 52,
                    "target_fat_g": 11
                },
                ...
            ],
            "daily_totals": {
                "calories": 3300,
                "protein_g": 174,
                "carbs_g": 413,
                "fat_g": 92
            }
        }
    """

    structure_info = MEAL_STRUCTURES[meal_structure]
    meals = structure_info["meals"]

    # Classifier meals as main or snack
    main_meals = [m for m in meals if any(word in m.lower()
                  for word in ["petit-déjeuner", "déjeuner", "dîner", "repas"])]
    snacks = [m for m in meals if "collation" in m.lower()]

    num_main = len(main_meals)
    num_snacks = len(snacks)

    meal_targets = []

    if num_snacks > 0:
        # Split 75/25 for calories, 80/20 for protein
        cal_per_main = int((daily_calories * 0.75) / num_main)
        cal_per_snack = int((daily_calories * 0.25) / num_snacks)
        protein_per_main = int((daily_protein_g * 0.80) / num_main)
        protein_per_snack = int((daily_protein_g * 0.20) / num_snacks)
    else:
        # Equal split
        cal_per_main = int(daily_calories / num_main)
        protein_per_main = int(daily_protein_g / num_main)

    # Distribute carbs and fat proportionally to calories
    for meal in meals:
        if any(word in meal.lower() for word in ["petit-déjeuner", "déjeuner", "dîner", "repas"]):
            calories = cal_per_main
            protein = protein_per_main
        else:
            calories = cal_per_snack
            protein = protein_per_snack

        # Carbs and fat: proportional to calorie share
        carbs = int((calories / daily_calories) * daily_carbs_g)
        fat = int((calories / daily_calories) * daily_fat_g)

        meal_targets.append({
            "meal_type": meal.split("(")[0].strip(),
            "time": meal.split("(")[1].replace(")", "").strip(),
            "target_calories": calories,
            "target_protein_g": protein,
            "target_carbs_g": carbs,
            "target_fat_g": fat
        })

    return {
        "meals": meal_targets,
        "daily_totals": {
            "calories": daily_calories,
            "protein_g": daily_protein_g,
            "carbs_g": daily_carbs_g,
            "fat_g": daily_fat_g
        }
    }
```

**Exemple Output (structure "3_meals_2_snacks"):**
```json
{
  "meals": [
    {
      "meal_type": "Petit-déjeuner",
      "time": "07:30",
      "target_calories": 825,
      "target_protein_g": 58,
      "target_carbs_g": 103,
      "target_fat_g": 31
    },
    {
      "meal_type": "Collation AM",
      "time": "10:00",
      "target_calories": 412,
      "target_protein_g": 17,
      "target_carbs_g": 52,
      "target_fat_g": 11
    },
    ...
  ],
  "daily_totals": {
    "calories": 3300,
    "protein_g": 174,
    "carbs_g": 413,
    "fat_g": 92
  }
}
```

**Output:** Macros par repas calculées

---

### **Étape 4: Confirmation Utilisateur**

**Responsable:** Agent (via conversation)

**Actions:**
```python
# L'agent présente à l'utilisateur:
message = f"""
📊 **Récapitulatif de tes besoins nutritionnels**

**Profil:**
- {profile['age']} ans, {profile['gender']}, {profile['weight_kg']}kg, {profile['height_cm']}cm
- Niveau d'activité: {profile['activity_level']}
- Objectif principal: {primary_goal}

**Calculs:**
- BMR (Métabolisme de base): {bmr} kcal
- TDEE (Dépense quotidienne): {tdee} kcal
- **Cible calorique**: {target_calories} kcal/jour ({surplus_deficit})
- **Protéines**: {protein}g/jour ({protein_per_kg}g/kg)
- **Glucides**: {carbs}g/jour
- **Lipides**: {fat}g/jour

**Structure de repas choisie:** {meal_structure}
- Petit-déjeuner (07:30): ~{breakfast_cals} kcal, ~{breakfast_protein}g protéines
- Collation AM (10:00): ~{snack1_cals} kcal, ~{snack1_protein}g protéines
- Déjeuner (12:30): ~{lunch_cals} kcal, ~{lunch_protein}g protéines
- Collation PM (16:00): ~{snack2_cals} kcal, ~{snack2_protein}g protéines
- Dîner (19:30): ~{dinner_cals} kcal, ~{dinner_protein}g protéines

✅ Ces cibles te conviennent-elles ?
⚠️ Je vais maintenant générer un plan de 7 jours avec des recettes originales. **Durée estimée: 3-4 minutes.**
"""

# Attendre confirmation: "oui", "ok", "d'accord", "génère", etc.
```

**Validation:**
- Utilisateur confirme → Continuer
- Utilisateur ajuste → Recalculer avec nouveaux paramètres

**Output:** Validation utilisateur obtenue

---

### **Étape 5: Génération des Recettes par le LLM**

**Responsable:** LLM (GPT-4o) via prompt simplifié

**Actions:**
```python
# Récupérer contexte scientifique (RAG)
rag_context = await retrieve_relevant_documents_tool(
    supabase,
    openai_client,
    query="meal planning nutrient timing protein distribution meal frequency"
)

# Construire prompt SIMPLIFIÉ (100 lignes max)
prompt = build_meal_plan_prompt_simple(
    profile=profile,
    meal_macros_distribution=meal_macros,  # De l'étape 3
    rag_context=rag_context,
    start_date=start_date
)

# Appeler GPT-4o en mode JSON
response = await openai_client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": prompt}],
    response_format={"type": "json_object"},
    temperature=0.8,  # Créativité encouragée
    max_tokens=12000
)

meal_plan_raw = json.loads(response.choices[0].message.content)
```

**Nouveau Prompt Simplifié (`build_meal_plan_prompt_simple`):**

```python
def build_meal_plan_prompt_simple(
    profile: dict,
    meal_macros_distribution: dict,
    rag_context: str,
    start_date: str
) -> str:
    """
    Prompt simplifié - Focus sur la CRÉATIVITÉ, pas les calculs.
    """

    allergies_str = ", ".join(profile.get("allergies", [])) or "AUCUNE"
    disliked_str = ", ".join(profile.get("disliked_foods", [])) or "Aucun"
    favorites_str = ", ".join(profile.get("favorite_foods", [])) or "Aucun"
    cuisines_str = ", ".join(profile.get("preferred_cuisines", [])) or "Toutes"

    # Format meal targets for display
    meal_targets_display = "\n".join([
        f"   - {meal['meal_type']} ({meal['time']}): ~{meal['target_calories']} kcal, "
        f"~{meal['target_protein_g']}g protéines"
        for meal in meal_macros_distribution["meals"]
    ])

    # Calculate dates
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    days_of_week = []
    for i in range(7):
        day_dt = start_dt + timedelta(days=i)
        day_name = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"][day_dt.weekday()]
        days_of_week.append(f"{day_name} {day_dt.strftime('%Y-%m-%d')}")

    prompt = f"""Tu es un chef nutritionniste expert créant des recettes personnalisées pour 7 jours.

🚨 CONTRAINTE CRITIQUE - ALLERGIES 🚨
**ALLERGIES DE L'UTILISATEUR:** {allergies_str}

⚠️ TOLÉRANCE ZÉRO - Vérifie CHAQUE ingrédient avant de l'inclure dans une recette.
Si tu utilises un allergène ({allergies_str}), le plan sera REJETÉ.

═══════════════════════════════════════════════════════════════

📋 PROFIL UTILISATEUR

**Aliments à éviter:** {disliked_str}
**Aliments favoris:** {favorites_str}
**Cuisines préférées:** {cuisines_str}
**Temps de préparation max:** {profile.get('max_prep_time', 60)} min
**Régime alimentaire:** {profile.get('diet_type', 'omnivore')}

═══════════════════════════════════════════════════════════════

🎯 TA MISSION

Crée 7 jours de recettes ORIGINALES et VARIÉES pour la structure de repas suivante:

{meal_targets_display}

**IMPORTANT - NE CALCULE PAS LES MACROS:**
- Le système calculera automatiquement les macros via OpenFoodFacts
- Concentre-toi sur la CRÉATIVITÉ et la VARIÉTÉ
- Propose des quantités RÉALISTES (ex: 200g de poulet pour un repas principal)

═══════════════════════════════════════════════════════════════

📖 CONTEXTE SCIENTIFIQUE (pour inspiration)

{rag_context[:800]}

═══════════════════════════════════════════════════════════════

📝 FORMAT JSON REQUIS

{{
  "days": [
    {{
      "day": "{days_of_week[0]}",
      "date": "{start_date}",
      "meals": [
        {{
          "meal_type": "Petit-déjeuner",
          "time": "07:30",
          "recipe_name": "Bowl protéiné avoine-banane aux myrtilles",
          "ingredients": [
            {{"name": "oats", "quantity": 80, "unit": "g"}},
            {{"name": "banana", "quantity": 1, "unit": "pieces"}},
            {{"name": "blueberries", "quantity": 50, "unit": "g"}},
            {{"name": "whey protein powder vanilla", "quantity": 30, "unit": "g"}},
            {{"name": "almond milk unsweetened", "quantity": 200, "unit": "ml"}},
            {{"name": "honey", "quantity": 10, "unit": "g"}}
          ],
          "instructions": "Faire chauffer le lait d'amande. Cuire l'avoine 3-4 min. Ajouter la banane écrasée et les myrtilles. Mélanger la whey avec un peu d'eau et incorporer. Drizzler de miel. Servir chaud.",
          "prep_time_min": 10,
          "tags": ["petit-déjeuner", "rapide", "protéiné"]
        }},
        {{
          "meal_type": "Collation AM",
          "time": "10:00",
          "recipe_name": "Yaourt grec aux noix et miel",
          ...
        }}
      ]
    }},
    ... // Répéter pour les 7 jours
  ]
}}

⚠️ RÈGLES CRITIQUES:

1. **Noms d'ingrédients en ANGLAIS** (ex: "chicken breast" pas "poulet", "white rice" pas "riz")
   → Nécessaire pour la base OpenFoodFacts

2. **Quantités réalistes en grammes de préférence**
   → Évite les portions ridicules (ex: 50g de poulet pour un repas = trop peu)

3. **Instructions en FRANÇAIS** (1 seule chaîne de texte, étapes séparées par des points)
   → Exemple: "Faire revenir l'oignon. Ajouter le poulet. Cuire 15 min. Servir avec du riz."

4. **GÉNÈRE LES 7 JOURS COMPLETS**
   → Pas de "...", "etc.", ou jours manquants
   → Les 7 jours sont: {", ".join(days_of_week)}

5. **VARIÉTÉ MAXIMALE**
   → Pas de répétition exacte sur la semaine
   → Varie les sources de protéines (poulet, bœuf, poisson, œufs, légumineuses)
   → Varie les types de glucides (riz, pâtes, pain, pommes de terre, quinoa)

6. **VÉRIFIE LES ALLERGIES**
   → Avant de soumettre, RELIS chaque ingrédient
   → Aucun ingrédient ne doit contenir: {allergies_str}

═══════════════════════════════════════════════════════════════

🚨 RAPPEL FINAL

Ton rôle = Créer des recettes savoureuses et variées
Le système Python = Ajuster les quantités pour atteindre les macros cibles

Focus sur la CRÉATIVITÉ, le GOÛT, et le RESPECT des ALLERGIES.

COMMENCE maintenant avec le Jour 1 ({days_of_week[0]}) et CONTINUE jusqu'au Jour 7 ({days_of_week[6]}).
"""

    return prompt
```

**Caractéristiques du nouveau prompt:**
- ✅ **100 lignes** (vs 500 actuellement)
- ✅ **Pas de calcul de macros** demandé au LLM
- ✅ **Exemple concret** en haut
- ✅ **Allergies répétées** 3 fois
- ✅ **Instructions claires** sans contradiction
- ✅ **Focus créativité** et variété

**Output:** `meal_plan_raw` (JSON avec recettes, sans macros calculées)

---

### **Étape 6: Calcul des Macros Réelles via OpenFoodFacts**

**Responsable:** Python (fonction `calculate_meal_plan_macros`)

**Actions:**
```python
from nutrition.meal_plan_optimizer import calculate_meal_plan_macros

# Cette fonction existe déjà dans meal_plan_optimizer.py
meal_plan_with_macros = await calculate_meal_plan_macros(
    meal_plan_raw,
    supabase
)

# Processus:
# 1. Pour chaque ingrédient de chaque recette:
#    - Recherche dans OpenFoodFacts (via openfoodfacts_client.py)
#    - Récupère calories, protéines, glucides, lipides
#    - Cache en base (92%+ hit rate)
# 2. Calcule les macros pour chaque repas
# 3. Calcule les totaux journaliers
# 4. Retourne le plan avec toutes les nutrition info complètes
```

**Output:** `meal_plan_with_macros` (JSON avec macros réelles calculées)

**Exemple de structure après cette étape:**
```json
{
  "days": [
    {
      "day": "Lundi 2024-12-23",
      "meals": [
        {
          "meal_type": "Petit-déjeuner",
          "recipe_name": "Bowl protéiné avoine-banane",
          "ingredients": [
            {
              "name": "oats",
              "quantity": 80,
              "unit": "g",
              "nutrition": {
                "calories": 304,
                "protein_g": 10.6,
                "carbs_g": 54.4,
                "fat_g": 5.6
              }
            },
            ...
          ],
          "nutrition": {
            "calories": 520,  // Somme des ingrédients
            "protein_g": 38,
            "carbs_g": 68,
            "fat_g": 12
          }
        },
        ...
      ],
      "daily_totals": {
        "calories": 2850,  // Somme des repas (pas encore ajusté)
        "protein_g": 165,
        "carbs_g": 380,
        "fat_g": 85
      }
    },
    ...
  ]
}
```

---

### **Étape 7: Ajustement des Quantités pour Atteindre les Cibles**

**Responsable:** Python (fonction `optimize_meal_plan_portions`)

**Actions:**
```python
from nutrition.meal_plan_optimizer import optimize_meal_plan_portions

target_macros = {
    "calories": 3300,
    "protein_g": 174,
    "carbs_g": 413,
    "fat_g": 92
}

# Algorithme génétique pour ajuster les portions
optimized_plan = await optimize_meal_plan_portions(
    meal_plan_with_macros,
    target_macros,
    profile['allergies']
)

# Processus:
# 1. Compare daily_totals actuels vs target_macros
# 2. Si écart > 5% sur n'importe quel macro:
#    - Ajuste les quantités d'ingrédients proportionnellement
#    - Recalcule les macros
#    - Itère jusqu'à convergence (±5% sur tout)
# 3. Vérifie que les portions restent réalistes (pas 450g de poulet...)
# 4. Re-valide les allergies après ajustement
```

**Exemple de transformation:**

**AVANT ajustement (Jour 1):**
```json
{
  "daily_totals": {
    "calories": 2850,  // -450 kcal vs cible (3300)
    "protein_g": 165,   // -9g vs cible (174)
    "carbs_g": 380,     // -33g vs cible (413)
    "fat_g": 85         // -7g vs cible (92)
  }
}
```

**APRÈS ajustement (Jour 1):**
```json
{
  "daily_totals": {
    "calories": 3285,  // ±5% de 3300 ✅
    "protein_g": 172,   // ±5% de 174 ✅
    "carbs_g": 408,     // ±5% de 413 ✅
    "fat_g": 91         // ±5% de 92 ✅
  }
}
```

**Output:** `optimized_plan` (portions ajustées pour atteindre cibles ±5%)

---

### **Étape 8: Validation Automatique Multi-Niveaux**

**Responsable:** Python (fonction `validate_meal_plan_complete`)

**Actions:**
```python
def validate_meal_plan_complete(
    meal_plan: dict,
    target_macros: dict,
    user_allergens: list[str],
    meal_structure: str
) -> dict:
    """
    Validation complète en 4 niveaux.

    Returns:
        {
            "valid": bool,
            "validations": {
                "structure": {"valid": bool, "errors": []},
                "allergens": {"valid": bool, "violations": []},
                "macros": {"valid": bool, "daily_deviations": []},
                "completeness": {"valid": bool, "missing": []}
            }
        }
    """

    validations = {}

    # 1. Validation de structure
    structure_check = validate_meal_plan_structure(meal_plan, require_nutrition=True)
    validations["structure"] = structure_check

    # 2. Validation des allergènes
    allergen_violations = validate_allergens(meal_plan, user_allergens)
    validations["allergens"] = {
        "valid": len(allergen_violations) == 0,
        "violations": allergen_violations
    }

    # 3. Validation des macros (±5% tolérance)
    macro_validations = []
    for day in meal_plan.get("days", []):
        daily_totals = day.get("daily_totals", {})

        deviations = {
            "day": day.get("day"),
            "calories": {
                "actual": daily_totals.get("calories", 0),
                "target": target_macros["calories"],
                "deviation_pct": abs((daily_totals.get("calories", 0) - target_macros["calories"]) / target_macros["calories"] * 100),
                "within_tolerance": abs((daily_totals.get("calories", 0) - target_macros["calories"]) / target_macros["calories"] * 100) <= 5
            },
            "protein_g": {
                "actual": daily_totals.get("protein_g", 0),
                "target": target_macros["protein_g"],
                "deviation_pct": abs((daily_totals.get("protein_g", 0) - target_macros["protein_g"]) / target_macros["protein_g"] * 100),
                "within_tolerance": abs((daily_totals.get("protein_g", 0) - target_macros["protein_g"]) / target_macros["protein_g"] * 100) <= 5
            },
            "carbs_g": {
                "actual": daily_totals.get("carbs_g", 0),
                "target": target_macros["carbs_g"],
                "deviation_pct": abs((daily_totals.get("carbs_g", 0) - target_macros["carbs_g"]) / target_macros["carbs_g"] * 100),
                "within_tolerance": abs((daily_totals.get("carbs_g", 0) - target_macros["carbs_g"]) / target_macros["carbs_g"] * 100) <= 5
            },
            "fat_g": {
                "actual": daily_totals.get("fat_g", 0),
                "target": target_macros["fat_g"],
                "deviation_pct": abs((daily_totals.get("fat_g", 0) - target_macros["fat_g"]) / target_macros["fat_g"] * 100),
                "within_tolerance": abs((daily_totals.get("fat_g", 0) - target_macros["fat_g"]) / target_macros["fat_g"] * 100) <= 5
            }
        }

        day_valid = all([
            deviations["calories"]["within_tolerance"],
            deviations["protein_g"]["within_tolerance"],
            deviations["carbs_g"]["within_tolerance"],
            deviations["fat_g"]["within_tolerance"]
        ])

        deviations["valid"] = day_valid
        macro_validations.append(deviations)

    validations["macros"] = {
        "valid": all([day["valid"] for day in macro_validations]),
        "daily_deviations": macro_validations
    }

    # 4. Validation de complétude (7 jours, tous les repas)
    completeness_errors = []
    if len(meal_plan.get("days", [])) != 7:
        completeness_errors.append(f"Expected 7 days, got {len(meal_plan.get('days', []))}")

    expected_meals_per_day = len(MEAL_STRUCTURES[meal_structure]["meals"])
    for day in meal_plan.get("days", []):
        if len(day.get("meals", [])) != expected_meals_per_day:
            completeness_errors.append(
                f"{day.get('day')}: Expected {expected_meals_per_day} meals, got {len(day.get('meals', []))}"
            )

    validations["completeness"] = {
        "valid": len(completeness_errors) == 0,
        "missing": completeness_errors
    }

    # Validation globale
    all_valid = all([
        validations["structure"]["valid"],
        validations["allergens"]["valid"],
        validations["macros"]["valid"],
        validations["completeness"]["valid"]
    ])

    return {
        "valid": all_valid,
        "validations": validations
    }


# Dans le workflow:
validation_result = validate_meal_plan_complete(
    optimized_plan,
    target_macros,
    profile['allergies'],
    meal_structure
)

if not validation_result["valid"]:
    # Log les erreurs pour debugging
    logger.error(f"Meal plan validation failed: {validation_result['validations']}")

    # Retourner erreur à l'utilisateur
    return json.dumps({
        "error": "Meal plan validation failed",
        "code": "VALIDATION_FAILED",
        "details": validation_result["validations"]
    })

logger.info("✅ Meal plan validation PASSED on all 4 levels")
```

**Output:** Validation complète réussie ou erreurs détaillées

---

### **Étape 9: Stockage en Base de Données**

**Responsable:** Python (Supabase insert)

**Actions:**
```python
# Même logique qu'actuellement
meal_plan_record = {
    "week_start": start_date,
    "plan_data": optimized_plan,  # JSONB avec tout
    "target_calories_daily": target_macros["calories"],
    "target_protein_g": target_macros["protein_g"],
    "target_carbs_g": target_macros["carbs_g"],
    "target_fat_g": target_macros["fat_g"],
    "notes": notes,
    "created_at": datetime.now().isoformat()
}

db_response = supabase.table("meal_plans").insert(meal_plan_record).execute()

meal_plan_id = db_response.data[0].get("id") if db_response.data else None

logger.info(f"✅ Meal plan stored in database (ID: {meal_plan_id})")
```

**Output:** Plan stocké avec `meal_plan_id`

---

### **Étape 10: Formatage de la Réponse Utilisateur**

**Responsable:** Python (fonction `format_meal_plan_response_for_user`)

**Actions:**
```python
def format_meal_plan_response_for_user(
    meal_plan: dict,
    meal_plan_id: int,
    display_mode: str = "summary"  # "summary" ou "detailed"
) -> str:
    """
    Formate le plan pour affichage utilisateur.

    display_mode:
    - "summary": Tableau synthétique par jour (macros + nombre de repas)
    - "detailed": Détails complets (recettes, ingrédients, instructions)
    """

    if display_mode == "summary":
        # Tableau synthétique
        summary = f"""
📊 **Plan Nutritionnel Hebdomadaire Généré** (ID: {meal_plan_id})

| Jour | Calories | Protéines | Glucides | Lipides | Repas |
|------|----------|-----------|----------|---------|-------|
"""
        for day in meal_plan["days"]:
            totals = day["daily_totals"]
            num_meals = len(day["meals"])
            summary += f"| {day['day'][:10]} | {totals['calories']} kcal | {totals['protein_g']}g | {totals['carbs_g']}g | {totals['fat_g']}g | {num_meals} repas |\n"

        summary += f"""
**Moyennes hebdomadaires:**
- Calories: {sum([d['daily_totals']['calories'] for d in meal_plan['days']]) / 7:.0f} kcal/jour
- Protéines: {sum([d['daily_totals']['protein_g'] for d in meal_plan['days']]) / 7:.1f}g/jour
- Glucides: {sum([d['daily_totals']['carbs_g'] for d in meal_plan['days']]) / 7:.1f}g/jour
- Lipides: {sum([d['daily_totals']['fat_g'] for d in meal_plan['days']]) / 7:.1f}g/jour

✅ Toutes les macros sont à ±5% des cibles
✅ Allergies vérifiées (0 violation)
✅ 7 jours complets avec recettes détaillées

📥 Veux-tu voir le **détail jour par jour** ? (réponds "détails jour X" ou "tous les détails")
🛒 Veux-tu générer la **liste de courses** pour cette semaine ? (réponds "liste de courses")
"""
        return summary

    elif display_mode == "detailed":
        # Détails complets
        detailed = f"""
📋 **Plan Nutritionnel Détaillé** (ID: {meal_plan_id})

"""
        for day in meal_plan["days"]:
            detailed += f"""
## {day['day']}

"""
            for meal in day["meals"]:
                detailed += f"""
### {meal['meal_type']} - {meal['time']}
**{meal['recipe_name']}**

**Nutrition:**
- {meal['nutrition']['calories']} kcal
- Protéines: {meal['nutrition']['protein_g']}g
- Glucides: {meal['nutrition']['carbs_g']}g
- Lipides: {meal['nutrition']['fat_g']}g

**Ingrédients:**
"""
                for ing in meal['ingredients']:
                    detailed += f"- {ing['name']}: {ing['quantity']}{ing['unit']}\n"

                detailed += f"""
**Instructions:**
{meal['instructions']}

**Temps de préparation:** {meal.get('prep_time_min', 'N/A')} min

---
"""

            detailed += f"""
**Total du jour:** {day['daily_totals']['calories']} kcal | {day['daily_totals']['protein_g']}g protéines | {day['daily_totals']['carbs_g']}g glucides | {day['daily_totals']['fat_g']}g lipides

═══════════════════════════════════════════════════════════════

"""

        return detailed


# Dans le workflow:
# Par défaut, retourner le summary
response = format_meal_plan_response_for_user(
    optimized_plan,
    meal_plan_id,
    display_mode="summary"
)

return response
```

**Output:** Réponse formatée pour l'utilisateur (summary par défaut)

---

## 🔧 Nouvelles Fonctions à Créer

### Fichier: `nutrition/meal_distribution.py` (NOUVEAU)

```python
"""
Meal macro distribution calculations.

Calculates how to split daily macros across meals based on meal structure.
"""

def calculate_meal_macros_distribution(
    daily_calories: int,
    daily_protein_g: int,
    daily_carbs_g: int,
    daily_fat_g: int,
    meal_structure: str
) -> dict:
    """[Code détaillé dans l'étape 3]"""
    pass
```

### Fichier: `nutrition/meal_planning.py` (MODIFIER)

```python
# Ajouter la fonction simplifiée
def build_meal_plan_prompt_simple(
    profile: dict,
    meal_macros_distribution: dict,
    rag_context: str,
    start_date: str
) -> str:
    """[Code détaillé dans l'étape 5]"""
    pass
```

### Fichier: `nutrition/validators.py` (MODIFIER)

```python
# Ajouter la validation complète multi-niveaux
def validate_meal_plan_complete(
    meal_plan: dict,
    target_macros: dict,
    user_allergens: list[str],
    meal_structure: str
) -> dict:
    """[Code détaillé dans l'étape 8]"""
    pass
```

### Fichier: `nutrition/meal_plan_formatter.py` (NOUVEAU)

```python
"""
Meal plan response formatting for user display.
"""

def format_meal_plan_response_for_user(
    meal_plan: dict,
    meal_plan_id: int,
    display_mode: str = "summary"
) -> str:
    """[Code détaillé dans l'étape 10]"""
    pass
```

---

## 📊 Comparaison: Workflow Actuel vs Nouveau

| Étape | Actuel | Nouveau | Amélioration |
|-------|--------|---------|--------------|
| **Calcul macros** | Fait en silence (profil ou params) | Calculé explicitement + présenté à user | ✅ Transparence |
| **Répartition par repas** | Incluse dans prompt (LLM devine) | Calculée en Python avant génération | ✅ Précision |
| **Prompt LLM** | 500 lignes avec instructions contradictoires | 100 lignes focalisées sur créativité | ✅ Clarté |
| **Calcul macros recettes** | ❌ LLM doit calculer (désactivé) | ✅ Python + OpenFoodFacts | ✅ Fiabilité |
| **Ajustement portions** | ❌ Post-processing basique | ✅ Algorithme génétique ±5% | ✅ Précision |
| **Validation** | Allergies + structure basique | 4 niveaux (structure, allergies, macros, complétude) | ✅ Robustesse |
| **Réponse user** | JSON dump complet | Summary + option détails | ✅ UX |

---

## 🚀 Bénéfices Attendus

1. **Moins d'hallucinations**
   - Prompt simple et clair
   - Responsabilités séparées (LLM = créativité, Python = calculs)

2. **Précision à 100%**
   - OpenFoodFacts pour macros réelles
   - Ajustement automatique des portions (±5%)

3. **Transparence totale**
   - Utilisateur voit les calculs AVANT génération
   - Peut valider ou ajuster

4. **Debugging facilité**
   - Chaque étape est isolée et loggée
   - Validation multi-niveaux identifie les problèmes

5. **Meilleure UX**
   - Summary concis par défaut
   - Détails sur demande
   - Temps d'attente transparent

---

## ❓ Points à Discuter

1. **Tolérance macros:** ±5% sur tout ou différencier (±3% protéines, ±5% glucides, ±8% lipides) ?

2. **Retry logic:** Si validation échoue, régénérer automatiquement (max 2 retries) ou erreur directe ?

3. **Display mode:** Toujours retourner summary d'abord, ou laisser l'agent décider ?

4. **Meal structure:** Demander systématiquement à l'utilisateur ou utiliser "3_consequent_meals" par défaut ?

5. **RAG context:** 800 caractères suffisants ou augmenter à 1500 ?

---

## 📝 Prochaines Étapes

- [ ] **Étape 1:** Review de ce workflow ensemble
- [ ] **Étape 2:** Valider les choix (tolérance macros, retry logic, etc.)
- [ ] **Étape 3:** Créer les nouvelles fonctions (`meal_distribution.py`, `meal_plan_formatter.py`)
- [ ] **Étape 4:** Modifier `build_meal_plan_prompt_simple()` dans `meal_planning.py`
- [ ] **Étape 5:** Refactoriser `generate_weekly_meal_plan_tool()` dans `tools.py`
- [ ] **Étape 6:** Tester avec 2-3 profils différents
- [ ] **Étape 7:** Ajuster selon les résultats

---

**Prêt à discuter et affiner ce workflow ?** 🎯
