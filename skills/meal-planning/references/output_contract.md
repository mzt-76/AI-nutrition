# Output Contract JSON — generate_week_plan

L'outil `generate_week_plan` retourne UN SEUL JSON. Toutes les valeurs affichées doivent provenir de ce JSON — **jamais calculées, estimées ou inventées**.

## Structure exacte

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

## Chemin des champs

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

## Règles OBLIGATOIRES pour l'affichage

**MUST (obligatoire) :**
- Utiliser UNIQUEMENT les valeurs du JSON — ne JAMAIS calculer, estimer ou inventer
- Afficher les macros exactement telles que retournées (arrondi à l'entier pour l'affichage)
- Sourcer chaque valeur nutritionnelle de `nutrition.*` ou `daily_totals.*` ou `weekly_summary.*`
- Mentionner le chemin `markdown_document` comme document téléchargeable

**MUST NOT (interdit) :**
- Ne JAMAIS additionner ou recalculer les macros — utiliser `daily_totals` directement
- Ne JAMAIS inventer un nom de recette ou un ingrédient non présent dans le JSON
- Ne JAMAIS annoncer ou promettre des recettes AVANT d'avoir le résultat JSON
- Ne JAMAIS afficher les 7 jours en détail (trop long) — voir format de présentation
- Ne JAMAIS afficher le JSON brut

**Si `success: false` ou `error` présent :**
- Signaler l'échec avec le champ `error` du JSON
- Proposer de relancer ou contacter le support
