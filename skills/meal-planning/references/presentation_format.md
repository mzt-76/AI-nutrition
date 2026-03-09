# Format de Presentation du Plan de Repas

## Structure OBLIGATOIRE

### A. Resume global (texte)
- Nombre total de recettes uniques
- Temps de preparation moyen
- Securite allergenes (validation passee)

### B. NE PAS emettre de DayPlanCard

**NE PAS emettre de marqueurs `<!--UI:DayPlanCard:...-->` dans le chat.**

Le detail complet (ingredients, macros, instructions) est disponible sur la page dediee
via le lien `/plans/{meal_plan_id}`. Afficher un resume texte compact par jour (voir SKILL.md).

### C. Pour les plans > 2 jours

- NE GENERE PAS de resume detaille des jours restants
- NE LISTE PAS les totaux caloriques des jours 3-7

**SEULEMENT CE MESSAGE** :
```
---
Le plan complet des {N} jours est sauvegarde dans la base de donnees.
```

### D. Lien vers le plan complet
- Inclure : `[Voir le plan complet](/plans/{meal_plan_id})`

### E. Proposition explicite + QuickReplyChips

Terminer avec des boutons de suivi :

```
<!--UI:QuickReplyChips:{"options":[{"label":"Liste de courses","value":"generate_grocery_list"},{"label":"Regenerer le plan","value":"regenerate_plan"}]}-->
```

## Exemple Complet

```
Plan de 7 jours cree avec succes !

**Resume Hebdomadaire**
- 21 recettes uniques
- Temps de preparation moyen : 35 min
- Securite allergenes : aucun allergene detecte

**Lundi** (2026-01-06) — 1 820 kcal, 128g proteines
- Petit-dejeuner : Omelette aux epinards et toast avocat
- Dejeuner : Poulet grille et salade quinoa
- Diner : Saumon au four avec legumes rotis

**Mardi** (2026-01-07) — 1 850 kcal, 135g proteines
- Petit-dejeuner : ...
- Dejeuner : ...
- Diner : ...

---
Le plan complet des 7 jours est sauvegarde dans la base de donnees.

[Voir le plan complet](/plans/abc-123-def)

<!--UI:QuickReplyChips:{"options":[{"label":"Liste de courses","value":"generate_grocery_list"},{"label":"Regenerer le plan","value":"regenerate_plan"}]}-->
```
