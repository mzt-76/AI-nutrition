# Format de Presentation du Plan de Repas

## Structure OBLIGATOIRE

### A. Resume global (texte)
- Nombre total de recettes uniques
- Temps de preparation moyen
- Securite allergenes (validation passee)

### B. Composants UI pour CHAQUE jour retourne

**Tu DOIS emettre un marqueur `DayPlanCard` pour chaque jour dans `meal_plan.days[]`.**

Construis le marqueur a partir du JSON retourne par le script :

```
<!--UI:DayPlanCard:{
  "day_name": meal_plan.days[i].day,
  "meals": [
    {
      "meal_type": meals[j].meal_type,
      "recipe_name": meals[j].name,
      "calories": meals[j].nutrition.calories,
      "macros": {
        "protein_g": meals[j].nutrition.protein_g,
        "carbs_g": meals[j].nutrition.carbs_g,
        "fat_g": meals[j].nutrition.fat_g
      },
      "prep_time": meals[j].prep_time_minutes,
      "ingredients": meals[j].ingredients (convertir objets en strings: "nom (quantite unite)")
    }
  ],
  "totals": {
    "calories": days[i].daily_totals.calories,
    "protein_g": days[i].daily_totals.protein_g,
    "carbs_g": days[i].daily_totals.carbs_g,
    "fat_g": days[i].daily_totals.fat_g
  }
}-->
```

**Regles** :
- Arrondir toutes les valeurs numeriques a l'entier
- Convertir les ingredients objets `{name, quantity, unit}` en strings lisibles : `"Poulet (150 g)"`
- Emettre un `DayPlanCard` par jour — ne PAS combiner plusieurs jours dans un seul marqueur
- Maximum 2 jours en detail. Si plus de 2 jours, afficher les 2 premiers avec `DayPlanCard`, puis mentionner que le reste est dans la base

### C. Pour les plans > 2 jours

- NE GENERE PAS de resume des jours restants
- NE LISTE PAS les totaux caloriques des jours 3-7

**SEULEMENT CE MESSAGE** :
```
---
Le plan complet des 7 jours (avec tous les details) est sauvegarde dans la base de donnees.
```

### D. Lien vers le plan complet
- Inclure : `[Voir le plan complet](/plans/{meal_plan_id})`

### E. Proposition explicite + QuickReplyChips

Terminer avec des boutons de suivi :

```
<!--UI:QuickReplyChips:{"options":[{"label":"Afficher un autre jour","value":"show_another_day"},{"label":"Liste de courses","value":"generate_grocery_list"},{"label":"Regenerer le plan","value":"regenerate_plan"}]}-->
```

## Exemple Complet

```
Plan de 7 jours cree avec succes ! Voici les details des 2 premiers jours :

**Resume Hebdomadaire**
- 21 recettes uniques
- Temps de preparation moyen : 35 min
- Securite allergenes : aucun allergene detecte

<!--UI:DayPlanCard:{"day_name":"Lundi 6 Janvier","meals":[{"meal_type":"Petit-dejeuner","recipe_name":"Omelette aux epinards et toast avocat","calories":520,"macros":{"protein_g":28,"carbs_g":45,"fat_g":24},"prep_time":15,"ingredients":["Oeufs (3)","Epinards frais (50 g)","Pain complet (60 g)","Avocat (80 g)"]},{"meal_type":"Dejeuner","recipe_name":"Poulet grille et salade quinoa","calories":680,"macros":{"protein_g":52,"carbs_g":55,"fat_g":22},"prep_time":25,"ingredients":["Poulet (150 g)","Quinoa cuit (80 g)","Tomates cerises (100 g)","Concombre (50 g)","Huile d'olive (15 ml)"]},{"meal_type":"Diner","recipe_name":"Saumon au four avec legumes rotis","calories":620,"macros":{"protein_g":48,"carbs_g":45,"fat_g":26},"prep_time":30,"ingredients":["Saumon (150 g)","Brocoli (100 g)","Carottes (100 g)","Pommes de terre (120 g)","Huile d'olive (10 ml)"]}],"totals":{"calories":1820,"protein_g":128,"carbs_g":145,"fat_g":72}}-->

<!--UI:DayPlanCard:{"day_name":"Mardi 7 Janvier","meals":[...],"totals":{...}}-->

---
Le plan complet des 7 jours est sauvegarde dans la base de donnees.

[Voir le plan complet](/plans/abc-123-def)

<!--UI:QuickReplyChips:{"options":[{"label":"Afficher un autre jour","value":"show_another_day"},{"label":"Liste de courses","value":"generate_grocery_list"},{"label":"Regenerer le plan","value":"regenerate_plan"}]}-->
```
