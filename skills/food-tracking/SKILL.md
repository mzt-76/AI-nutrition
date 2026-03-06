---
name: food-tracking
description: >-
    Suivi alimentaire et food logging. Enregistrement d'aliments dans le journal
    alimentaire via le script `log_food_entries` ("j'ai mange...", suivi rapide).
category: tracking
---

# Food Tracking - Suivi Alimentaire

## Quand utiliser

- L'utilisateur declare avoir mange quelque chose
- Suivi alimentaire / enregistrement d'aliments
- Modification d'une entree existante dans le journal

## Outils disponibles

| Script | Description |
|--------|-------------|
| `log_food_entries` | Enregistrer des aliments dans le journal alimentaire (daily_food_log) |

## Parametres `log_food_entries`

Les noms de parametres ci-dessous sont les noms exacts a utiliser.

| Parametre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `items` | list | **oui** | Liste d'objets `{name: str, quantity: float, unit: str}`. Chaque item = 1 ingredient simple. La cle de chaque objet doit etre `name` (pas `food_name`). |
| `log_date` | str | non | YYYY-MM-DD. Defaut = aujourd'hui. La cle doit etre `log_date` (pas `date`). |
| `meal_type` | str | non | `"petit-dejeuner"` \| `"dejeuner"` \| `"diner"` \| `"collation"`. Defaut = `"dejeuner"`. Ce parametre doit etre au **niveau racine** des parametres, pas a l'interieur de chaque item. |
| `entry_id` | str | non | ID d'une entree existante a modifier. Si fourni, le premier item de `items` remplace l'aliment de cette entree (recalcul macros via OFF). |

**Regle de decomposition** : Si l'utilisateur mentionne un plat compose (ex: "pates carbonara", "salade nicoise"), le decomposer en ingredients individuels avec des quantites estimees pour 1 portion AVANT d'appeler le script. Le script ne traite que des ingredients simples.

## Execution

```python
# Enregistrer des aliments (suivi alimentaire)
# IMPORTANT : AVANT d'appeler log_food_entries, decomposer les plats composes
# en ingredients individuels avec quantites estimees pour 1 portion.
# Ex: "pates carbo" -> pates 150g + lardons 50g + creme 30ml + oeuf 1 + parmesan 20g
run_skill_script("food-tracking", "log_food_entries", {
    "items": [
        {"name": "poulet grille", "quantity": 200, "unit": "g"},
        {"name": "riz basmati", "quantity": 150, "unit": "g"}
    ],
    "log_date": "2026-03-05",
    "meal_type": "dejeuner"
})

# Modifier un aliment existant (ex: "yaourt" -> "skyr")
run_skill_script("food-tracking", "log_food_entries", {
    "entry_id": "uuid-de-l-entree",
    "items": [{"name": "skyr", "quantity": 200, "unit": "g"}],
    "log_date": "2026-03-05",
    "meal_type": "petit-dejeuner"
})
```
