---
name: shopping-list
description: >-
    Generation de liste de courses categorisee a partir d'un plan de repas stocke
    en base de donnees. "liste de courses", "qu'est-ce que je dois acheter ?".
category: planning
---

# Shopping List - Liste de Courses

## Quand utiliser

- L'utilisateur demande une liste de courses pour un **plan hebdo** → `generate_shopping_list`
- L'utilisateur demande une liste de courses pour une **recette specifique** → `generate_from_recipes`
- L'utilisateur demande ce qu'il doit acheter pour la semaine

**REGLE DE ROUTING :**
- Si l'utilisateur demande la liste de courses apres avoir genere une recette custom (via `generate_custom_recipe`), utiliser `generate_from_recipes` avec le `recipe_id` retourne par la recette.
- Si l'utilisateur demande la liste de courses pour son plan hebdomadaire, utiliser `generate_shopping_list`.

## Outils disponibles

| Script | Description |
|--------|-------------|
| `generate_shopping_list` | Liste de courses categorisee depuis plan hebdo stocke |
| `generate_from_recipes` | Liste de courses depuis recette(s) individuelle(s) par recipe_id |

## Parametres `generate_shopping_list`

- `week_start` (str, optionnel) : YYYY-MM-DD du lundi de la semaine. Defaut = semaine courante.
- `selected_days` (list[int], optionnel) : Indices des jours a inclure, 0=Lundi ... 6=Dimanche (ex: `[0, 1, 2]` pour Lundi-Mercredi). Defaut = tous les jours du plan.
- `servings_multiplier` (float, optionnel) : Multiplicateur de portions. Defaut = 1.0.

## Parametres `generate_from_recipes`

- `recipe_ids` (list[str], **requis**) : UUID(s) de recettes dans la table `recipes`. Retourne par `generate_custom_recipe` dans `recipe.id`.
- `servings_multiplier` (float, optionnel) : Multiplicateur de portions. Defaut = 1.0.
- `title` (str, optionnel) : Titre custom pour la liste.

## Execution

```python
# --- Plan hebdo ---

# Liste de courses pour la semaine courante
run_skill_script("shopping-list", "generate_shopping_list", {})

# Liste de courses pour une semaine specifique
run_skill_script("shopping-list", "generate_shopping_list", {
    "week_start": "2026-02-23"
})

# Liste de courses pour certains jours seulement
run_skill_script("shopping-list", "generate_shopping_list", {
    "week_start": "2026-02-23",
    "selected_days": [0, 1, 2]
})

# --- Recettes individuelles ---

# Liste de courses pour une recette (recipe_id retourne par generate_custom_recipe)
run_skill_script("shopping-list", "generate_from_recipes", {
    "recipe_ids": ["abc123-uuid-de-la-recette"]
})

# Liste de courses pour plusieurs recettes avec multiplicateur
run_skill_script("shopping-list", "generate_from_recipes", {
    "recipe_ids": ["uuid-recette-1", "uuid-recette-2"],
    "servings_multiplier": 2.0,
    "title": "Courses - Diner special"
})
```
