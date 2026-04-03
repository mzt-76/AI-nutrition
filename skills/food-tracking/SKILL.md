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
    (7) veut modifier une entree existante dans son journal alimentaire,
    (8) veut supprimer une entree ("supprime", "enleve", "retire du suivi",
    "delete", "efface").
    Trois scripts : `log_food_entries` (ecriture), `get_daily_summary` (lecture),
    `delete_food_entry` (suppression).
---

# Food Tracking

## Scripts

| Script | Action |
|--------|--------|
| `log_food_entries` | Ecrire des aliments dans `daily_food_log` (INSERT ou UPDATE) |
| `get_daily_summary` | Lire le bilan du jour : macros consomme/restant + detail par repas (aliments, quantites, macros) |
| `delete_food_entry` | Supprimer une entree du journal (par entry_id ou par recherche food_name) |

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

## Parametres `delete_food_entry`

| Parametre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `entry_id` | str | non* | UUID de l'entree a supprimer (prefere). |
| `food_name` | str | non* | Nom de l'aliment a chercher (fuzzy). *Au moins un des deux requis. |
| `meal_type` | str | non | Filtre par repas (avec `food_name`). |
| `log_date` | str | non | YYYY-MM-DD. Defaut = aujourd'hui. |

Si `food_name` matche plusieurs entrees → retourne la liste (`code: "AMBIGUOUS"`) pour que l'agent demande confirmation ou precise avec `entry_id`.

## Regles

**Decomposition obligatoire** : Toujours decomposer les plats composes en ingredients individuels avec quantites estimees AVANT d'appeler `log_food_entries`. Le script ne traite que des ingredients simples.

Ex : "pates carbonara" → pates 150g + lardons 50g + creme 30ml + oeuf 1 + parmesan 20g.

**Recette issue de la conversation** : Quand l'utilisateur demande de logger une recette qu'on vient de generer, reprendre EXACTEMENT les ingredients et quantites de la recette. Ne pas reestimer — utiliser les donnees deja presentes dans la conversation. Determiner le `meal_type` selon le contexte.

**Lecture du tracker** : Quand l'utilisateur demande ce qu'il a mange ou veut voir son suivi, appeler `get_daily_summary`. La reponse inclut `meals_detail` avec chaque aliment (nom, quantite, unite, macros) groupe par repas — utile pour repondre a "qu'est-ce que j'ai mange ce matin ?" ou reutiliser un repas dans un plan.

**Recette favorite → tracker** : Quand l'utilisateur demande d'ajouter une recette favorite a son suivi :
1. Appeler `get_user_favorites` (skill `meal-planning`) avec le nom de la recette
2. Le resultat contient `ingredients` (liste `{name, quantity, unit}`) — les extraire
3. Passer ces ingredients a `log_food_entries` avec le `meal_type` du favori
Ne JAMAIS logger le nom de la recette comme un seul aliment — toujours decomposer en ingredients.

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

# Ajouter un favori au tracker (2 etapes)
# Etape 1 : recuperer le favori et ses ingredients
run_skill_script("meal-planning", "get_user_favorites", {"name": "poulet grillé"})
# → retourne ingredients: [{"name": "poulet", "quantity": 200, "unit": "g"}, ...]

# Etape 2 : logger les ingredients individuels
run_skill_script("food-tracking", "log_food_entries", {
    "items": [
        {"name": "poulet", "quantity": 200, "unit": "g"},
        {"name": "herbes de provence", "quantity": 5, "unit": "g"}
    ],
    "meal_type": "dejeuner"
})

# Supprimer par nom (recherche fuzzy dans les entrees du jour)
run_skill_script("food-tracking", "delete_food_entry", {
    "food_name": "riz basmati",
    "meal_type": "dejeuner"
})

# Supprimer par entry_id (retourne par get_daily_summary dans meals_detail)
run_skill_script("food-tracking", "delete_food_entry", {
    "entry_id": "uuid-de-l-entree"
})

# Bilan du jour
run_skill_script("food-tracking", "get_daily_summary", {})

# Bilan d'une date specifique
run_skill_script("food-tracking", "get_daily_summary", {"log_date": "2026-03-05"})
```
