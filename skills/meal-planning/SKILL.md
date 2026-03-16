---
name: meal-planning
description: >-
    Plans de repas personnalisés. CHARGER CE SKILL DÈS qu'un plan/recette/menu est demandé,
    ou quand l'utilisateur veut ajouter en favoris / sauvegarder une recette.
    2 routes : recettes DB (rapide, défaut) ou custom LLM (si plat spécifique mentionné).
    Défaut : 3 jours, même petit-déj, repas variés.

category: planning
---

# Meal Planning

## Quand utiliser
- Demande de plan de repas (1+ jours)
- Demande de recette spécifique
- Récupération d'un plan existant
- Ajouter une recette en favoris / sauvegarder une recette

## Comportement agent
- TOUJOURS poser **1 question groupée** avant de générer, sauf si l'utilisateur dit explicitement "go" / "lance" / "par défaut". La question doit couvrir :
  1. **Durée** : combien de jours ? (défaut 3)
  2. **Batch cooking** : préparer les mêmes plats plusieurs jours ? Si oui, combien ?
  3. **Préférences repas** : un plat ou ingrédient spécifique ? (petit-déj, déjeuner, dîner)
  4. **Variété petit-déj** : même petit-déj chaque jour ou varier ?
- Si "go", "lance", "génère" sans contexte → défauts automatiques, exécution immédiate
- Défaut : **3 jours**, même petit-déj, repas variés, **PAS de batch cooking** (chaque repas est différent sauf le petit-déj). Ne PAS passer `batch_days` sauf si l'utilisateur le demande explicitement.
- JAMAIS annoncer des recettes avant la génération
- JAMAIS improviser une recette en texte — toujours via script
- Toute recette générée a un `recipe.id` — le conserver pour la liste de courses

## 2 routes de génération

### Route 1 : Recettes DB (défaut)
- Aucune préférence spécifique → le script pioche dans la recipe DB
- Rapide, pas d'appel LLM
- Scaling mathématique pour atteindre les macros cibles

### Route 2 : Recettes custom (LLM)
- L'utilisateur mentionne un plat ou ingrédient spécifique → route LLM
- Passer via `meal_preferences` → déclenche `generate_custom_recipe` (Claude Haiku 4.5)
- Recette sauvegardée en DB pour réutilisation future

**Règle clé — recette custom + plan** : quand l'utilisateur demande un plan incluant une recette custom générée dans la conversation (qui a un `recipe_id`), **d'abord** appeler `add_favorite_recipe` avec ce `recipe_id`, **puis** `generate_week_plan` avec `custom_requests` référençant le nom de la recette. Le pipeline retrouvera la recette via le lookup favoris.

**Règle clé** : toute mention de plat ou d'ingrédient spécifique = route custom.
- "fais-moi un plan" → route DB
- "je veux de la baguette le matin" → `meal_preferences: {"petit-dejeuner": "baguette et chocolat chaud"}`
- "risotto mardi" → `notes: "risotto mardi"`

## Scripts (appels agent)

| Script | Quand |
|--------|-------|
| `generate_week_plan` | Générer un plan (1-7 jours) |
| `generate_custom_recipe` | Recette unique sur demande |
| `fetch_stored_meal_plan` | Récupérer un plan existant |
| `add_favorite_recipe` | Ajouter une recette aux favoris de l'utilisateur |

```python
# Plan par défaut (1 jour)
run_skill_script("meal-planning", "generate_week_plan", {})

# Plan 7 jours avec préférence globale (même plat TOUS les jours)
run_skill_script("meal-planning", "generate_week_plan", {
    "num_days": 7,
    "meal_preferences": {"petit-dejeuner": "omelette aux oeufs et épinards"}
})

# Plan avec demande pour un JOUR + REPAS spécifique (méthode recommandée)
run_skill_script("meal-planning", "generate_week_plan", {
    "num_days": 3,
    "custom_requests": {
        "Mardi": {"dejeuner": "poulet ratatouille pommes de terre"},
        "Mercredi": {"diner": "saumon grillé avec légumes"}
    }
})

# Combiné : préférence globale + override par jour
run_skill_script("meal-planning", "generate_week_plan", {
    "num_days": 5,
    "meal_preferences": {"petit-dejeuner": "porridge protéiné"},
    "custom_requests": {
        "Jeudi": {"dejeuner": "risotto aux champignons"}
    }
})

# Recette sur demande
run_skill_script("meal-planning", "generate_custom_recipe", {
    "recipe_request": "salade niçoise protéinée",
    "meal_type": "dejeuner"
})
# ENUM meal_type : "petit-dejeuner" | "dejeuner" | "diner" | "collation"
# After: include the `ui_marker` field from the response verbatim at END of your text

# Récupérer un plan existant
run_skill_script("meal-planning", "fetch_stored_meal_plan", {"week_start": "2026-02-23"})

# Ajouter une recette aux favoris (recipe_id vient de generate_custom_recipe)
run_skill_script("meal-planning", "add_favorite_recipe", {
    "recipe_id": "abc-123-uuid",
    "notes": "Ma recette d'escalope maison"
})
```

## Paramètres generate_week_plan

| Param | Type | Défaut | Description |
|-------|------|--------|-------------|
| `num_days` | int | 1 | Nombre de jours. 7 uniquement si demandé |
| `meal_preferences` | dict | {} | Préférences **globales** (tous les jours). Clé = slug DB (`petit-dejeuner`, `dejeuner`, `diner`, `collation`), valeur = description du plat |
| `custom_requests` | dict | {} | Demandes **par jour spécifique**. Clé = jour FR (`Lundi`, `Mardi`…), valeur = dict `{meal_type_slug: description}`. Prioritaire sur `meal_preferences` |
| `vary_breakfast` | bool | false | true si l'utilisateur veut varier le petit-déj |
| `batch_days` | int | - | Jours consécutifs avec même plat (batch cooking) |
| `notes` | str | - | Texte libre, parsé automatiquement en `custom_requests` (legacy — préférer `custom_requests` structuré) |
| `meal_structure` | str | auto | `3_consequent_meals` (3 repas, 0 collation), `3_meals_1_preworkout` (3 repas + 1 collation), `3_meals_2_snacks`, `4_meals`. Auto-detecte si omis (≥2500 kcal → ajoute collation). Specifier quand l'utilisateur demande un nombre de repas precis ou "sans collation". |

## Paramètres add_favorite_recipe

| Param | Type | Obligatoire | Description |
|-------|------|------------|-------------|
| `recipe_id` | str | oui | UUID de la recette (retourné par `generate_custom_recipe`) |
| `notes` | str | non | Note libre sur la recette |

## Paramètres generate_custom_recipe

| Param | Type | Obligatoire | Description |
|-------|------|------------|-------------|
| `recipe_request` | str | oui | Description de la recette souhaitée |
| `meal_type` | str | oui | Slug : `petit-dejeuner` / `dejeuner` / `diner` / `collation` |

## Conversion préférences utilisateur

### Préférence globale (tous les jours) → `meal_preferences`
- "omelette le matin" → `meal_preferences: {"petit-dejeuner": "omelette aux oeufs"}`
- "du poisson le soir" → `meal_preferences: {"diner": "plat à base de poisson"}`
- "go" / "par défaut" → `{}` (défauts automatiques)

### Demande pour un jour précis → `custom_requests`
- "mardi midi poulet ratatouille" → `custom_requests: {"Mardi": {"dejeuner": "poulet ratatouille"}}`
- "jeudi soir saumon grillé" → `custom_requests: {"Jeudi": {"diner": "saumon grillé"}}`
- "samedi matin pancakes" → `custom_requests: {"Samedi": {"petit-dejeuner": "pancakes protéinés"}}`
- "demain midi poulet grillé" → `custom_requests: {"Demain": {"dejeuner": "poulet grillé"}}` (résolu automatiquement)

### Structure repas → `meal_structure`
- "3 repas sans collation" / "supprime la collation" / "juste 3 repas" → `meal_structure: "3_consequent_meals"`
- "ajoute une collation pre-workout" → `meal_structure: "3_meals_1_preworkout"`
- "4 repas egaux" → `meal_structure: "4_meals"`

**Règle** : dès qu'un jour est nommé + un repas + un plat → utiliser `custom_requests`, PAS `meal_preferences`.
**Clés jour** : `Lundi`, `Mardi`, `Mercredi`, `Jeudi`, `Vendredi`, `Samedi`, `Dimanche` (majuscule initiale). Aussi accepté : `Demain`, `Aujourd'hui`, `Après-demain` (résolu automatiquement).
**Clés repas** : `petit-dejeuner`, `dejeuner`, `diner`, `collation` (slugs DB, sans accents).
**Mots-clés repas** : "matin/petit-déj" → `petit-dejeuner`, "midi/déjeuner" → `dejeuner`, "soir/dîner" → `diner`, "collation/goûter" → `collation`.

## Présentation du résultat — FORMAT OBLIGATOIRE

**Le script retourne un JSON avec `meal_plan_id`, `meal_plan.days[]`, `weekly_summary`. Tu DOIS utiliser ce JSON exactement.**

### Étape 1 : Résumé court (3-4 lignes max)
- Nombre de jours, calories moyennes (`weekly_summary.average_calories`), protéines moyennes
- Sécurité allergènes : validation passée ✅

### Étape 2 : Résumé par jour (texte simple)
Pour chaque jour, afficher un résumé compact :

**Lundi** (2026-03-09) — 2 964 kcal, 172g protéines
- Petit-déjeuner : Omelette aux épinards
- Déjeuner : Poulet grillé aux légumes
- Dîner : Saumon teriyaki

NE PAS émettre de marqueurs `<!--UI:DayPlanCard:...-->` — le détail complet
(ingrédients, macros, instructions) est sur la page dédiée via le lien ci-dessous.

### Étape 3 : Lien plan complet — OBLIGATOIRE
Copie-colle le champ `plan_link` du JSON **tel quel, seul sur une ligne, sans emoji ni mise en forme** :

{response.plan_link}

NE PAS entourer de `**bold**`, `📖`, ni de texte additionnel sur la même ligne.
**Sans ce lien, l'utilisateur ne peut pas accéder au plan ni l'ajouter en favori.**

### Étape 4 : QuickReplyChips
```
<!--UI:QuickReplyChips:{"options":[{"label":"Liste de courses","value":"generate_grocery_list"},{"label":"Régénérer le plan","value":"regenerate_plan"}]}-->
```

### CE QUI EST INTERDIT
- Émettre des marqueurs `<!--UI:DayPlanCard:...-->` — le détail est sur la page dédiée
- Omettre le lien `/plans/{meal_plan_id}` — sinon pas de favori possible
- Inventer des valeurs — tout vient du JSON retourné par le script

## MealCard — OBLIGATOIRE pour toute recette

Chaque fois que tu proposes une recette (individuelle OU dans un plan), tu DOIS émettre un marqueur `MealCard` à la fin de ta réponse. Les scripts de recette retournent un champ `ui_marker` — copie-le tel quel. Sans ce marqueur, la recette n'est pas sauvegardable.

```
[ton texte avec instructions, ingrédients, etc.]

<!--UI:MealCard:{"meal_type":"dejeuner","recipe_name":"Poulet rôti aux herbes","calories":650,"macros":{"protein_g":52,"carbs_g":68,"fat_g":15},"prep_time":35,"ingredients":["Filet de poulet 200g","Riz complet 80g","Brocoli 150g"],"instructions":"1. Préchauffer le four à 200°C\n2. Assaisonner le poulet\n3. Cuire 25 min\n4. Cuire le riz et le brocoli en parallèle\n5. Dresser l'assiette"}-->
```

## Sécurité allergènes
Tolérance zéro — filtrage Python automatique en 2 couches.
Voir `references/allergen_families.md`.
