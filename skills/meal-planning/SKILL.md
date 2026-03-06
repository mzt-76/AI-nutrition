---
name: meal-planning
description: >-
    Plans de repas personnalisés via recipe DB, ou créativité IA si demande particulière + scaling mathématique.
    Avant de générer un PLAN, poser ces questions EN UN SEUL message :
    (1) Combien de jours ? → défaut = 1 seul jour. JAMAIS 7 par défaut.
    (2) Cuisiner en avance (même plat 2-3 jours) ou repas différents chaque jour ? → défaut = repas différents.
    (3) Même petit-dej chaque matin ou varié ? → défaut = même.
    (4) Combien de repas par jour ? (ex: petit-dej + déjeuner + dîner, ou avec une collation en plus).
    (5) Autres préférences ?
    Si "go" → appliquer les défauts et générer immédiatement.
category: planning
---

# Meal Planning - Planification de Repas

## Quand utiliser

- L'utilisateur demande un plan de repas hebdomadaire
- L'utilisateur veut voir/récupérer un plan existant
- L'utilisateur demande une recette spécifique

**REGLE : Ne JAMAIS improviser une recette en texte libre.**
Toute demande de recette DOIT passer par `generate_custom_recipe`.
Le script sauvegarde la recette en DB et retourne un `recipe_id` dans `recipe.id` —
conserver ce `recipe_id` pour la liste de courses si demandee ensuite
(via `run_skill_script("shopping-list", "generate_from_recipes", {"recipe_ids": [recipe_id]})`).

## Nouveau Workflow (Recipe DB + Day-by-Day)

### Architecture

Le skill utilise une **base de recettes pré-validées** avec macros calculés via OpenFoodFacts.
Pour chaque jour, le système sélectionne des recettes → scale les portions mathématiquement → valide.
LLM fallback utilise **Claude Sonnet 4.5** via Anthropic API (uniquement quand nécessaire).

### Pipeline par jour

1. `select_recipes` → Cherche recettes dans la DB (filtrage allergènes, variété, préférences)
2. `scale_portions` → Ajuste les quantités pour atteindre les macros cibles exactement
3. `validate_day` → Vérifie allergènes (tolérance zéro) et macros (±5% protéines, ±10% reste)
4. Si validation échoue → retry avec d'autres recettes (max 2 tentatives)

### LLM Fallback (Claude Sonnet 4.5)

Si l'utilisateur demande une recette spécifique (ex: "risotto aux champignons") :
- `generate_custom_recipe` → Claude Sonnet 4.5 génère → macros calculés via OFF → sauvegardé en DB
- Si DB ne couvre pas un slot → LLM fallback automatique → recette sauvegardée pour réutilisation future

## Outils disponibles

| Script | Description |
|--------|-------------|
| `generate_week_plan` | Plan 7 jours (profile → macros → 7 × generate_day_plan → DB store) |
| `generate_custom_recipe` | Recette sur demande via Claude Sonnet 4.5 |
| `fetch_stored_meal_plan` | Récupérer plan existant (~500ms, DB only) |
| `seed_recipe_db` | Peupler la DB avec 120+ recettes (setup initial) |

## Paramètres `generate_weekly_meal_plan`

- `start_date` (str, optionnel) : YYYY-MM-DD. Si omis, utilise le lundi de la semaine courante.
- `target_calories_daily` (int, optionnel) : Cible kcal/jour. Si None, utilise le profil.
- `target_protein_g` (int, optionnel) : Cible protéines en grammes
- `target_carbs_g` (int, optionnel) : Cible glucides en grammes
- `target_fat_g` (int, optionnel) : Cible lipides en grammes
- `meal_structure` (str, optionnel) : **NE PAS SPÉCIFIER** sauf demande explicite. Le script auto-détecte la meilleure structure selon les calories cibles (≥2500 kcal → 3_meals_1_preworkout, sinon → 3_consequent_meals).
  - `3_consequent_meals` : 3 repas
  - `3_meals_2_snacks` : 3 repas + 2 collations
  - `4_meals` : 4 repas égaux
  - `3_meals_1_preworkout` : 3 repas + collation pré-training
- `num_days` (int, optionnel) : Nombre de jours à générer. **DÉFAUT : 1** (Lundi uniquement). Utiliser 7 pour une semaine complète uniquement si l'utilisateur le demande explicitement.
- `batch_days` (int, optionnel) : Nombre de jours consécutifs avec le même plat pour déjeuner et dîner (chaque repas a sa propre recette). Utile pour le batch cooking / préparation en avance. Ex: batch_days=3 → même déjeuner lundi-mercredi, même dîner lundi-mercredi, puis nouvelles recettes jeudi-samedi.
- `vary_breakfast` (bool, optionnel, défaut: false) : Par défaut, le même petit-déjeuner est servi chaque jour. Mettre à true si l'utilisateur veut varier ses petits-déjeuners.
- `meal_preferences` (dict, optionnel) : Préférences de recettes par type de repas, appliquées à TOUS les jours. Clé = slug meal_type (`petit-dejeuner`, `dejeuner`, `diner`, `collation`), valeur = description de la recette souhaitée. Ex: `{"petit-dejeuner": "omelette aux oeufs et épinards"}`. Utilise le LLM pour générer une recette correspondante, puis la réutilise chaque jour via batch. Les demandes per-day dans `notes` prennent priorité.
- `notes` (str, optionnel) : Préférences + demandes custom PAR JOUR (ex: "risotto mardi, pas de poisson vendredi")

## Structures de repas disponibles

- `3_consequent_meals` : 3 repas principaux (auto-sélectionné si < 2500 kcal)
- `3_meals_2_snacks` : Petit-dej, collation AM, déjeuner, collation PM, dîner
- `4_meals` : 4 repas égaux dans la journée
- `3_meals_1_preworkout` : 3 repas + 1 collation avant entraînement (auto-sélectionné si ≥ 2500 kcal)

**NE SPÉCIFIE PAS** `meal_structure` SI l'utilisateur n'a PAS demandé de structure spécifique.

## Exécution

```python
# Plan semaine courante (défaut)
run_skill_script("meal-planning", "generate_week_plan", {})

# Plan avec structure spécifique
run_skill_script("meal-planning", "generate_week_plan", {
    "meal_structure": "3_meals_1_preworkout"
})

# Plan avec préférence globale (ex: omelette tous les matins)
run_skill_script("meal-planning", "generate_week_plan", {
    "num_days": 7,
    "meal_preferences": {"petit-dejeuner": "omelette aux oeufs et épinards"}
})

# Plan avec demande custom par jour
run_skill_script("meal-planning", "generate_week_plan", {
    "start_date": "2026-02-23",
    "notes": "risotto mardi, pas de poisson vendredi"
})

# Recette sur demande
run_skill_script("meal-planning", "generate_custom_recipe", {
    "recipe_request": "salade niçoise protéinée",
    "meal_type": "dejeuner"  # TOUJOURS un slug français exact (voir enum ci-dessous)
})

# ⚠️ ENUM OBLIGATOIRE pour meal_type dans generate_custom_recipe :
# "petit-dejeuner" | "dejeuner" | "diner" | "collation"
# ❌ INTERDIT : "breakfast", "lunch", "dinner", "snack", "Déjeuner", "Dîner"
# Les majuscules et les accents sont invalides — utiliser uniquement les slugs ci-dessus.

# After calling generate_custom_recipe:
# The response JSON contains a `ui_marker` field — you MUST include it
# verbatim at the END of your text response. This renders the interactive
# MealCard component for the user.

# Récupérer un plan existant
run_skill_script("meal-planning", "fetch_stored_meal_plan", {
    "week_start": "2026-02-23"
})

```

## Question pré-planification (avant generate_week_plan)

Avant de lancer la génération, poser **UNE SEULE question rapide** qui couvre tout
en un message. Ne PAS poser les questions une par une en plusieurs messages.

**EXCEPTION — Exécution immédiate (pas de question) :**
Si l'utilisateur dit "go", "lance", "génère", "pas de préférence", ou si le message contient déjà toutes les infos (profil + objectif), lance directement `generate_week_plan` avec les défauts. Ne calcule PAS les besoins nutritionnels séparément — le skill le fait automatiquement.

**Défaut : 1 SEUL JOUR.** Ne JAMAIS générer 7 jours sauf si explicitement demandé.

**Message unique à envoyer :**
> Avant de lancer le plan, quelques préférences rapides :
> 1. **Batch cooking** — Tu préfères des repas différents chaque jour, ou cuisiner
>    en avance et manger le même plat 2-3 jours de suite ?
> 2. **Petit-déjeuner** — Par défaut c'est le même chaque matin. Tu veux varier ?
> 3. Autre préférence ? (type de petit-dej, recettes souhaitées, etc.)
>
> (Si pas de préférence, je fais variété max + même petit-dej toute la semaine.)

**Interprétation des réponses :**
- "repas différents" ou pas de préférence → `batch_days` omis (variété max)
- "2 jours de suite" → `batch_days=2`
- "3 jours" → `batch_days=3`
- "varier le petit-dej" → `vary_breakfast=True`
- "même petit-dej" ou pas de réponse → défaut (même recette toute la semaine)

Note : `batch_days` s'applique au déjeuner ET au dîner séparément (chacun a sa
propre recette, répétée N jours consécutifs).

**Capturer les préférences dans `meal_preferences` :**
Si l'utilisateur mentionne un souhait pour un type de repas (ex: "je veux des oeufs
le matin", "omelette pour le petit-déj"), le convertir en entrée `meal_preferences`.
- "omelette le matin" → `meal_preferences={"petit-dejeuner": "omelette aux oeufs"}`
- "du poisson le soir" → `meal_preferences={"diner": "plat à base de poisson"}`

**INTERDIT : ne JAMAIS annoncer des recettes spécifiques avant la génération.**
Ne pas dire "tu auras une omelette le matin" — dire simplement "Je note ta
préférence pour les oeufs au petit-déj, je lance la génération" puis présenter
les résultats réels du JSON.

## Contrat de sortie JSON (Output Contract)

L'outil `generate_weekly_meal_plan` retourne UN SEUL JSON. Toutes les valeurs affichées doivent provenir de ce JSON — **jamais calculées, estimées ou inventées**.

### Structure exacte

```json
{
  "success": true,
  "message": "Meal plan generated successfully",
  "stored_in_database": true,
  "meal_plan_id": 123,
  "markdown_document": "/tmp/meal_plan_123_abc.md",
  "meal_plan": {
    "days": [
      {
        "day": "Lundi",
        "date": "2026-02-18",
        "meals": [
          {
            "meal_type": "Petit-déjeuner",
            "name": "Omelette protéinée",
            "ingredients": [
              {"name": "oeufs", "quantity": 3, "unit": "pièces"}
            ],
            "instructions": "Battre les oeufs et cuire à feu doux.",
            "prep_time_minutes": 10,
            "nutrition": {
              "calories": 320.0,
              "protein_g": 25.0,
              "carbs_g": 4.0,
              "fat_g": 22.0
            }
          }
        ],
        "daily_totals": {
          "calories": 2150.0,
          "protein_g": 165.0,
          "carbs_g": 210.0,
          "fat_g": 65.0
        }
      }
    ],
    "weekly_summary": {
      "average_calories": 2150.0,
      "average_protein_g": 165.0,
      "average_carbs_g": 210.0,
      "average_fat_g": 65.0
    }
  },
  "summary": {
    "total_days": 7,
    "weekly_summary": { "average_calories": 2150.0, "..." : "..." }
  }
}
```

### Chemin des champs → Usage d'affichage

| Champ JSON | Usage |
|---|---|
| `meal_plan.weekly_summary.average_calories` | Calories moyennes dans le résumé global |
| `meal_plan.weekly_summary.average_protein_g` | Protéines moyennes dans le résumé global |
| `meal_plan.days[i].day` | Nom du jour (ex: "Lundi") |
| `meal_plan.days[i].date` | Date du jour (ex: "2026-02-18") |
| `meal_plan.days[i].meals[j].name` | Nom de la recette |
| `meal_plan.days[i].meals[j].meal_type` | Type de repas (ex: "Déjeuner") |
| `meal_plan.days[i].meals[j].prep_time_minutes` | Temps de préparation |
| `meal_plan.days[i].meals[j].ingredients` | Liste d'ingrédients avec quantités |
| `meal_plan.days[i].meals[j].instructions` | Instructions de préparation |
| `meal_plan.days[i].meals[j].nutrition.calories` | Calories du repas |
| `meal_plan.days[i].meals[j].nutrition.protein_g` | Protéines du repas |
| `meal_plan.days[i].daily_totals.calories` | Total kcal du jour |
| `meal_plan.days[i].daily_totals.protein_g` | Total protéines du jour |
| `markdown_document` | Chemin du fichier Markdown téléchargeable |
| `meal_plan_id` | ID du plan en base (pour la liste de courses) |

### Règles OBLIGATOIRES pour l'affichage

**MUST (obligatoire) :**
- Utiliser UNIQUEMENT les valeurs du JSON — ne JAMAIS calculer, estimer ou inventer
- Afficher les macros exactement telles que retournées (arrondi à l'entier pour l'affichage)
- Sourcer chaque valeur nutritionnelle de `nutrition.*` ou `daily_totals.*` ou `weekly_summary.*`
- Mentionner le chemin `markdown_document` comme document téléchargeable

**MUST NOT (interdit) :**
- Ne JAMAIS additionner ou recalculer les macros — utiliser `daily_totals` directement
- Ne JAMAIS inventer un nom de recette ou un ingrédient non présent dans le JSON
- Ne JAMAIS annoncer ou promettre des recettes AVANT d'avoir le résultat JSON (le système choisit via scoring — l'agent ne sait pas à l'avance ce qui sera sélectionné)
- Ne JAMAIS afficher les 7 jours en détail (trop long) — voir format ci-dessous
- Ne JAMAIS afficher le JSON brut

**Si `success: false` ou `error` présent :**
- Signaler l'échec avec le champ `error` du JSON
- Proposer de relancer ou contacter le support

## Présentation du plan - FORMAT OBLIGATOIRE

Voir `references/presentation_format.md` pour le format détaillé avec exemples.

**Résumé rapide** :
- A. Résumé global (texte) : `weekly_summary.average_calories`, `weekly_summary.average_protein_g`, nombre de jours (`summary.total_days`), sécurité allergènes (filtrage Python garanti 2 couches)
- B. **Composants UI OBLIGATOIRES** : Émettre un marqueur `<!--UI:DayPlanCard:{...}-->` pour chaque jour dans `meal_plan.days[]` (max 2 jours détaillés). Construire les props depuis le JSON retourné — voir `references/presentation_format.md` pour le mapping exact des champs.
- C. Lien vers le plan complet : `[Voir le plan complet](/plans/{meal_plan_id})`
- D. **OBLIGATOIRE** : Terminer avec `<!--UI:QuickReplyChips:...-->` proposant d'afficher d'autres jours ou la liste de courses

## Sécurité Allergènes - TOLÉRANCE ZÉRO

Voir `references/allergen_families.md` pour les familles d'allergènes complètes.

**Filtrage en 2 couches** :
- Couche 1 : Filtrage Python côté DB (allergen_tags)
- Couche 2 : Validation Python après génération (validate_allergens)

## Règles d'Arrondi des Quantités

- **Pièces** (oeufs, fruits entiers) : TOUJOURS nombre entier
- **Grammes (g)** : Arrondir à l'entier
- **Millilitres (ml)** : Arrondir à l'entier
- **Exception** : Épices/assaisonnements < 10g peuvent garder 1 décimale

## Pré-requis: Seeding de la Recipe DB

Avant la première utilisation du nouveau système, `seed_recipe_db.py` doit être exécuté :
- Minimum: 10 recettes par type de repas (40 total) pour éviter le LLM fallback excessif
- Cible: 30 recettes par type (120 total)

Si la DB est vide → LLM fallback automatique (système fonctionne mais plus lentement).

## Scripts disponibles

- `scripts/generate_week_plan.py` : **Entrée principale** — pipeline 7 jours (profile → macros → boucle → DB store → markdown)
- `scripts/generate_day_plan.py` : Orchestrateur 1 jour (select → scale → validate → retry)
- `scripts/select_recipes.py` : Sélection de recettes depuis la DB avec filtrage
- `scripts/scale_portions.py` : Scaling mathématique des portions
- `scripts/validate_day.py` : Validation allergènes + macros pour 1 jour
- `scripts/generate_custom_recipe.py` : Recette custom via Claude Sonnet 4.5
- `scripts/seed_recipe_db.py` : Peuplement initial de la recipe DB
- `scripts/fetch_stored_meal_plan.py` : Récupération d'un plan existant
