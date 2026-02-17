# Analyse: Génération de Plans Hebdomadaires - Pourquoi Opus Réussit et l'Agent Actuel Échoue

## 🔍 Problème Identifié

**Symptôme:** L'agent Pydantic AI avec GPT-4o hallucine ou diverge du prompt lors de la génération de plans hebdomadaires.

**Preuve:** Claude Opus a généré un plan correct du premier coup avec une approche simple et directe.

---

## 🎯 Ce Que Claude Opus A Fait Différemment

### 1. **Approche Séquentielle Claire**

```
Opus: "Je vais d'abord lire les fichiers → calculer tes besoins → créer le plan"
```

**vs.**

```
Agent actuel: Prompt massif de 500+ lignes avec toutes les instructions en même temps
```

### 2. **Calculs Explicites Présentés à l'Utilisateur**

```
Opus a montré:
- BMR (Mifflin-St Jeor) = 1,950 kcal
- TDEE = 1,950 × 1.55 = 3,022 kcal
- Surplus = +300 kcal = 3,300 kcal cibles
- Protéines (2.0g/kg) = 174g
- Lipides (25%) = 92g
- Glucides (reste) = 413g
```

**Impact:** L'utilisateur valide les calculs AVANT la génération, évitant les erreurs en aval.

### 3. **Prompt Simplifié et Structuré**

Opus n'a **pas utilisé** un prompt de 500 lignes. Il a probablement utilisé une structure simple:

```markdown
Crée un plan nutritionnel hebdomadaire avec:
- Profil: [données]
- Cibles: [macros calculées ci-dessus]
- Structure: 3 repas + 1 collation pré-workout
- Format: 7 jours complets avec recettes détaillées

Contraintes:
- Respect STRICT des allergies: [liste]
- Variété sur la semaine
- Recettes savoureuses et réalistes
```

### 4. **Pas de Calcul de Macros par le LLM**

**Clé du succès:**
- Opus s'est concentré sur la **création de recettes créatives et variées**
- Les macros sont calculés **après** via une API (OpenFoodFacts)
- Le LLM n'est pas surchargé de contraintes mathématiques contradictoires

---

## ❌ Problèmes de l'Implémentation Actuelle

### Problème #1: **Prompt Overload (Surcharge Cognitive)**

**Fichier:** `nutrition/meal_planning.py` ligne 238-529

**Contenu:** 291 lignes de prompt avec:
- 🚨 9 sections avec émojis et séparateurs visuels
- ⚠️ Instructions contradictoires:
  - Ligne 251: "NE GÉNÈRE PAS EN DESSOUS DE LA CIBLE"
  - Ligne 349: "Ne calcule PAS les macros, c'est FatSecret qui le fait"
  - Ligne 356: "VÉRIFIE que daily_totals.calories entre X et Y"
- 📐 Exemple de calcul (ligne 360-370) mais calcul désactivé
- ✅ Checklist finale (ligne 428-443) pour valider ce qu'il ne doit pas calculer

**Conséquence:** Le LLM ne sait plus ce qu'il doit faire. Il est paralysé par les instructions contradictoires.

### Problème #2: **Mauvaise Séparation des Responsabilités**

```
Agent actuel:
┌─────────────────────────────────────┐
│ GPT-4o doit:                        │
│ 1. Créer recettes variées           │ ← Mission principale
│ 2. Calculer les macros               │ ← CONTRADICTOIRE (désactivé)
│ 3. Vérifier les macros               │ ← CONTRADICTOIRE (désactivé)
│ 4. Ajuster les portions              │ ← Impossible si pas de calcul
│ 5. Vérifier les allergènes           │ ← OK
│ 6. Générer 7 jours complets          │ ← OK
└─────────────────────────────────────┘
```

**Solution Opus:**
```
┌─────────────────────────────────────┐
│ Claude Opus:                        │
│ 1. Calcule les macros EN AMONT      │ ✅
│ 2. Présente à l'utilisateur         │ ✅
│ 3. Génère recettes variées          │ ✅
│ 4. Macros calculés APRÈS (API)      │ ✅
└─────────────────────────────────────┘
```

### Problème #3: **Manque d'Exemples Concrets**

**Ce qui manque:**
```json
// Exemple de ce qu'on attend (1 seul jour)
{
  "day": "Lundi 2024-12-23",
  "meals": [
    {
      "meal_type": "Petit-déjeuner",
      "recipe_name": "Omelette protéinée aux épinards",
      "ingredients": [
        {"name": "eggs", "quantity": 4, "unit": "pieces"},
        {"name": "spinach fresh", "quantity": 100, "unit": "g"},
        {"name": "olive oil", "quantity": 10, "unit": "ml"}
      ],
      "instructions": "Battre les œufs. Faire revenir les épinards. Cuire l'omelette."
    },
    ...
  ]
}
```

**Actuellement:** Le prompt montre un exemple ligne 456-507, mais noyé dans 500 lignes d'instructions.

### Problème #4: **Pas de Validation Intermédiaire**

```
Flow actuel:
Prompt → GPT-4o → JSON complet (7 jours) → Validation

Si 1 jour est mauvais → TOUT est rejeté → Agent frustré
```

**Flow Opus (implicite):**
```
Calculs → Validation user → Génération progressive → Succès
```

---

## ✅ Recommandations d'Amélioration

### Recommandation #1: **Simplifier Radicalement le Prompt**

**Action:** Réduire le prompt de 500 lignes à **~100 lignes max**

**Nouveau prompt (structure suggérée):**

```python
def build_meal_plan_prompt_v2(profile: dict, start_date: str, meal_structure: str) -> str:
    """Version simplifiée - focus sur la création, pas le calcul."""

    prompt = f"""Tu es un chef nutritionniste créant un plan de 7 jours.

📋 PROFIL UTILISATEUR
- Cibles: {profile['target_calories']} kcal, {profile['target_protein_g']}g protéines, {profile['target_carbs_g']}g glucides, {profile['target_fat_g']}g lipides
- 🚨 ALLERGIES (TOLÉRANCE ZÉRO): {', '.join(profile['allergies']) or 'Aucune'}
- Aliments détestés: {', '.join(profile.get('disliked_foods', [])) or 'Aucun'}
- Cuisines préférées: {', '.join(profile.get('preferred_cuisines', [])) or 'Toutes'}

🎯 TA MISSION
Génère 7 jours de repas ({meal_structure}) avec des recettes CRÉATIVES et VARIÉES.

NE calcule PAS les macros (le système le fera automatiquement).
Concentre-toi sur:
1. Recettes savoureuses et réalistes
2. Variété maximale (7 jours différents)
3. Respect STRICT des allergies: {', '.join(profile['allergies'])}
4. Quantités réalistes (ex: 200g poulet pour un repas principal)

📝 FORMAT JSON REQUIS

{{
  "days": [
    {{
      "day": "Lundi {start_date}",
      "meals": [
        {{
          "meal_type": "Petit-déjeuner",
          "recipe_name": "Nom créatif en français",
          "ingredients": [
            {{"name": "chicken breast", "quantity": 200, "unit": "g"}},
            {{"name": "white rice", "quantity": 150, "unit": "g"}}
          ],
          "instructions": "Étapes de préparation en français.",
          "tags": ["protéiné", "rapide"]
        }}
      ]
    }}
  ]
}}

⚠️ CRITIQUES
- Génère LES 7 JOURS COMPLETS (pas de "...")
- Noms d'ingrédients en ANGLAIS (ex: "chicken breast" pas "poulet")
- Vérifie CHAQUE ingrédient contre allergies: {', '.join(profile['allergies'])}

COMMENCE maintenant."""

    return prompt
```

**Gains:**
- ✅ 100 lignes au lieu de 500
- ✅ Instructions claires sans contradiction
- ✅ Focus sur la créativité, pas les maths
- ✅ Allergies répétées 3 fois (début, mission, fin)

### Recommandation #2: **Séparer Calcul et Création**

**Avant (actuel):**
```python
# Tool unique qui fait TOUT
generate_weekly_meal_plan_tool(
    target_calories=3300,  # Calculé où ?
    target_protein_g=174,  # D'où viennent ces chiffres ?
    ...
)
```

**Après (proposé):**
```python
# 1. Calcul explicite (agent visibility)
needs = await calculate_nutritional_needs_tool(...)
# Retourne: {"bmr": 1950, "tdee": 3022, "target_calories": 3300, ...}

# Agent présente à l'utilisateur:
# "Ton profil: BMR 1950 kcal, TDEE 3022 kcal, cible 3300 kcal (+300 surplus)
#  Protéines: 174g (2.0g/kg), Glucides: 413g, Lipides: 92g
#
#  Je génère maintenant ton plan hebdomadaire avec ces cibles. ⏱️ ~4 min"

# 2. Génération du plan (sans recalcul)
plan = await generate_weekly_meal_plan_tool(
    target_calories_daily=needs["target_calories"],  # Explicit
    target_protein_g=needs["target_protein_g"],
    ...
)
```

**Gains:**
- ✅ Transparence totale pour l'utilisateur
- ✅ Validation des macros avant génération
- ✅ Agent comprend le flow
- ✅ Debugging facile

### Recommandation #3: **Ajouter un Exemple Concret en Haut du Prompt**

**Ajouter au début du prompt:**

```python
prompt = f"""...

📖 EXEMPLE DE STRUCTURE ATTENDUE (1 jour)

{{
  "day": "Lundi 2024-12-23",
  "meals": [
    {{
      "meal_type": "Petit-déjeuner",
      "recipe_name": "Bowl protéiné avoine-banane",
      "ingredients": [
        {{"name": "oats", "quantity": 80, "unit": "g"}},
        {{"name": "banana", "quantity": 1, "unit": "pieces"}},
        {{"name": "whey protein powder", "quantity": 30, "unit": "g"}},
        {{"name": "almond milk", "quantity": 200, "unit": "ml"}}
      ],
      "instructions": "Cuire l'avoine avec le lait d'amande. Ajouter la banane écrasée et la whey. Mélanger.",
      "tags": ["petit-déjeuner", "rapide", "protéiné"]
    }},
    {{
      "meal_type": "Déjeuner",
      "recipe_name": "Poulet grillé riz basmati légumes",
      ...
    }}
  ]
}}

Génère maintenant 7 jours dans ce format exact.

...
"""
```

**Gains:**
- ✅ LLM voit exactement ce qu'on attend
- ✅ Format ancré visuellement
- ✅ Moins d'hallucinations

### Recommandation #4: **Validation Progressive (Optionnel)**

**Approche actuelle:**
```
Génère 7 jours → Valide tout → Si 1 erreur, tout rejeter
```

**Approche progressive:**
```python
# Option 1: Générer 2 jours d'abord (validation rapide)
prompt_day1_2 = f"Génère SEULEMENT les jours 1 et 2..."
response = await openai_client.chat.completions.create(...)

# Valider
if validate_ok:
    # Option 2: Générer les 5 jours restants
    prompt_day3_7 = f"Continue avec jours 3 à 7..."
```

**OU (plus simple):**
```python
# Générer 7 jours + système de retry intelligent
max_retries = 2
for attempt in range(max_retries):
    plan = await generate_plan(...)
    if validate(plan):
        break
    else:
        # Ajuster le prompt avec feedback
        prompt = add_error_feedback(prompt, validation_errors)
```

---

## 🎯 Plan d'Action Recommandé

### Phase 1: **Quick Win - Simplifier le Prompt** (1-2h)

1. Créer `build_meal_plan_prompt_simple()` dans `meal_planning.py`
2. Réduire à ~100 lignes avec structure claire
3. Ajouter exemple concret en haut
4. Tester avec 1 génération

**Résultat attendu:** Moins d'hallucinations, meilleure cohérence

### Phase 2: **Séparer Calcul et Création** (2-3h)

1. Modifier `prompt.py` pour expliciter les calculs
2. Agent présente macros AVANT génération
3. User valide → génération démarre

**Résultat attendu:** Transparence totale, debugging facile

### Phase 3: **Améliorer la Robustesse** (3-4h)

1. Ajouter retry logic avec feedback
2. Logger les prompts exacts envoyés
3. Créer tests avec profils variés

**Résultat attendu:** 95%+ de succès rate

---

## 📈 Métriques de Succès

**Avant (actuel):**
- ❌ Hallucinations fréquentes
- ❌ Plans incomplets ou incohérents
- ❌ Macros non respectées

**Après (objectif):**
- ✅ Génération réussie 95%+ du temps
- ✅ 7 jours complets et variés
- ✅ Allergies respectées à 100%
- ✅ Macros ajustées automatiquement (OpenFoodFacts)

---

## 🔧 Code à Modifier

### Fichiers concernés:

1. **`nutrition/meal_planning.py`**
   - Simplifier `build_meal_plan_prompt()` (ligne 51-532)
   - Créer `build_meal_plan_prompt_simple()` (nouveau)

2. **`tools.py`**
   - Ajouter logging du prompt exact (ligne 1003)
   - Ajouter retry logic (optionnel)

3. **`prompt.py`**
   - Améliorer instructions de génération de plan (ligne 145-150)
   - Expliciter le workflow calcul → présentation → génération

---

## 💡 Inspiration de l'Approche Opus

**Ce que tu dois retenir de la conversation avec Opus:**

1. **Calculer d'abord, générer ensuite** (pas simultanément)
2. **Montrer les calculs à l'utilisateur** (confiance + validation)
3. **Prompt simple et direct** (pas de surcharge cognitive)
4. **Focus sur la créativité** (recettes variées, savoureuses)
5. **Laisser l'API gérer les macros** (OpenFoodFacts = 100% précision)

**Citation clé de ta conversation:**
> "Opus a réussi du premier coup parce qu'il a fait simple et logique, pas de la prompt engineering à outrance."

---

## 🚀 Next Steps

1. Review cette analyse ensemble
2. Décider quelle recommandation implémenter en priorité
3. Tester avec un prompt simplifié
4. Itérer basé sur les résultats

Veux-tu que je t'aide à implémenter la recommandation #1 (simplifier le prompt) en premier ?
