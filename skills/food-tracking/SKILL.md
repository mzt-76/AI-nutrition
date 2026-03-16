---
name: food-tracking
description: >-
    Suivi alimentaire et journal de repas. Utiliser quand l'utilisateur :
    (1) declare avoir mange ("j'ai mange...", "j'ai pris..."),
    (2) demande d'ajouter un repas/recette a son tracker ou onglet suivi
    ("ajoute ca a mon tracker", "mets dans mon suivi", "enregistre ce repas",
    "log cette recette"),
    (3) demande de logger une recette qu'on vient de generer dans la conversation,
    (4) fait reference a l'onglet "Suivi du Jour" de l'application,
    (5) demande son bilan calorique ou ce qu'il lui reste ("combien il me reste ?",
    "mon bilan du jour", "qu'est-ce que j'ai mange ?"),
    (6) demande des conseils pour completer son quota calorique,
    (7) veut modifier une entree existante dans son journal alimentaire.
    Deux scripts : `log_food_entries` (ecriture) et `get_daily_summary` (lecture).
---

# Food Tracking

## Scripts

| Script | Action |
|--------|--------|
| `log_food_entries` | Ecrire des aliments dans `daily_food_log` (INSERT ou UPDATE) |
| `get_daily_summary` | Lire le bilan calorique/macros du jour (consomme vs objectifs) |

## Parametres `log_food_entries`

| Parametre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `items` | list | **oui** | Liste d'objets `{name: str, quantity: float, unit: str}`. Chaque item = 1 ingredient simple. Cle = `name` (pas `food_name`). |
| `log_date` | str | non | YYYY-MM-DD. Defaut = aujourd'hui. Cle = `log_date` (pas `date`). |
| `meal_type` | str | non | `"petit-dejeuner"` \| `"dejeuner"` \| `"diner"` \| `"collation"`. Defaut = `"dejeuner"`. Au **niveau racine**, pas dans chaque item. |
| `entry_id` | str | non | ID d'une entree existante a modifier. Le premier item de `items` remplace l'aliment (recalcul macros via OFF). |

## Parametres `get_daily_summary`

| Parametre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `log_date` | str | non | YYYY-MM-DD. Defaut = aujourd'hui. |

## Regles

**Decomposition obligatoire** : Toujours decomposer les plats composes en ingredients individuels avec quantites estimees AVANT d'appeler `log_food_entries`. Le script ne traite que des ingredients simples.

Ex : "pates carbonara" → pates 150g + lardons 50g + creme 30ml + oeuf 1 + parmesan 20g.

**Recette issue de la conversation** : Quand l'utilisateur demande de logger une recette qu'on vient de generer, reprendre EXACTEMENT les ingredients et quantites de la recette. Ne pas reestimer — utiliser les donnees deja presentes dans la conversation. Determiner le `meal_type` selon le contexte.

**Lecture du tracker** : Quand l'utilisateur demande ce qu'il a mange ou veut voir son suivi, appeler `get_daily_summary`.

## Exemples

```python
# Ingredients simples
run_skill_script("food-tracking", "log_food_entries", {
    "items": [
        {"name": "poulet grille", "quantity": 200, "unit": "g"},
        {"name": "riz basmati", "quantity": 150, "unit": "g"}
    ],
    "meal_type": "dejeuner"
})

# Recette complete depuis la conversation (reprendre les ingredients exacts)
run_skill_script("food-tracking", "log_food_entries", {
    "items": [
        {"name": "escalope de poulet", "quantity": 400, "unit": "g"},
        {"name": "farine de ble noir", "quantity": 50, "unit": "g"},
        {"name": "riz blanc", "quantity": 100, "unit": "g"},
        {"name": "poivron rouge", "quantity": 100, "unit": "g"},
        {"name": "oignon", "quantity": 60, "unit": "g"},
        {"name": "tomate", "quantity": 80, "unit": "g"},
        {"name": "creme fraiche allegee", "quantity": 60, "unit": "ml"},
        {"name": "huile d'olive", "quantity": 8, "unit": "ml"}
    ],
    "meal_type": "dejeuner"
})

# Modifier un aliment existant
run_skill_script("food-tracking", "log_food_entries", {
    "entry_id": "uuid-de-l-entree",
    "items": [{"name": "skyr", "quantity": 200, "unit": "g"}],
    "meal_type": "petit-dejeuner"
})

# Bilan du jour
run_skill_script("food-tracking", "get_daily_summary", {})

# Bilan d'une date specifique
run_skill_script("food-tracking", "get_daily_summary", {"log_date": "2026-03-05"})
```
