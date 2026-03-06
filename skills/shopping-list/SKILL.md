---
name: shopping-list
description: >-
    Generation de liste de courses categorisee a partir d'un plan de repas stocke
    en base de donnees. "liste de courses", "qu'est-ce que je dois acheter ?".
category: planning
---

# Shopping List - Liste de Courses

## Quand utiliser

- L'utilisateur demande une liste de courses
- L'utilisateur demande ce qu'il doit acheter pour la semaine

## Outils disponibles

| Script | Description |
|--------|-------------|
| `generate_shopping_list` | Liste de courses categorisee depuis plan stocke |

## Parametres `generate_shopping_list`

- `week_start` (str, optionnel) : YYYY-MM-DD du lundi de la semaine. Defaut = semaine courante.
- `selected_days` (list[str], optionnel) : Liste de jours a inclure (ex: `["Lundi", "Mardi"]`). Defaut = tous les jours du plan.
- `servings_multiplier` (float, optionnel) : Multiplicateur de portions. Defaut = 1.0.

## Execution

```python
# Liste de courses pour la semaine courante
run_skill_script("shopping-list", "generate_shopping_list", {})

# Liste de courses pour une semaine specifique
run_skill_script("shopping-list", "generate_shopping_list", {
    "week_start": "2026-02-23"
})

# Liste de courses pour certains jours seulement
run_skill_script("shopping-list", "generate_shopping_list", {
    "week_start": "2026-02-23",
    "selected_days": ["Lundi", "Mardi", "Mercredi"]
})
```
