# Subagent Prompt: Seed Gap-Filling Recipes

Create and insert new healthy/sporty recipes into Supabase using ONLY OFF-validated ingredients.

## DATA FILES — READ FIRST

1. `scripts/data/validated_ingredients.json` — OFF-validated ingredients with macros per 100g. ONLY use ingredients from this list.
2. `scripts/data/recipe_signatures.json` — Existing recipes with top ingredients, macros, meal_type, diet_type. Avoid duplicates or near-duplicates.

## CRITICAL RULES

1. **ONLY ingredients from validated_ingredients.json** — guarantees OFF validation
2. **Calculate macros precisely**: `sum(ingredient_qty / 100 * macro_per_100g)` for each macro
3. **No duplicates** — check recipe_signatures.json. Avoid recipes with same top 3 ingredients + same meal_type
4. **French names** — all recipe names in French
5. **Healthy/sporty profile** — high protein, moderate-to-low fat
6. **Realistic portions** — 400-700 kcal main meals, 150-350 kcal collations

## PRIORITIES

<!-- Replace this section with actual gaps from Step 1 -->

### Priority 1: [description]
Create N recipes: target macros, diet_types, cuisine variety

### Priority 2: [description]
...

## RECIPE ROW FORMAT

```python
{
    "name": "Nom en Français",
    "name_normalized": "nom en francais sans accents",  # lowercase, no accents (unicodedata NFKD)
    "meal_type": "dejeuner",  # dejeuner | diner | petit-dejeuner | collation
    "cuisine_type": "française",
    "diet_type": "omnivore",  # omnivore | végétarien | vegan
    "tags": ["high-protein", "low-fat"],
    "ingredients": [
        {
            "name": "poulet",        # MUST exist in validated_ingredients.json
            "quantity": 150,          # grams (or ml for liquids)
            "unit": "g",
            "nutrition_per_100g": {   # copy from validated_ingredients.json
                "calories": 179, "protein_g": 20, "fat_g": 10.9, "carbs_g": 0
            }
        }
    ],
    "instructions": "1. Couper... 2. Faire chauffer... 3. Servir...",
    "prep_time_minutes": 20,
    "allergen_tags": [],             # auto-detect from ingredients (see below)
    "calories_per_serving": 0,       # calculated from ingredients
    "protein_g_per_serving": 0,
    "carbs_g_per_serving": 0,
    "fat_g_per_serving": 0,
    "off_validated": true,
    "source": "seed-gap-analysis"
}
```

## ALLERGEN DETECTION

Tag if any ingredient name contains:
- **gluten**: farine, pain, pâtes, spaghetti, penne, nouilles, blé, couscous, semoule, chapelure, tortilla
- **lactose**: lait, crème, beurre, fromage, parmesan, mozzarella, feta, yaourt, skyr, ricotta
- **fruits_a_coque**: amande, noix, cajou, noisette, pistache
- **arachides**: cacahuète, beurre de cacahuète
- **oeufs**: oeuf
- **soja**: soja, tofu, tempeh, edamame, sauce soja
- **poisson**: saumon, thon, cabillaud, sardine, truite, maquereau
- **crustaces**: crevette, crabe, homard

## IMPLEMENTATION

Create `scripts/seed_recipes_gaps.py` (LLM-free — no anthropic/openai imports):

1. Define all recipes as data (list of dicts)
2. Calculate macros from nutrition_per_100g
3. Detect allergens from ingredient names
4. Validate: calories in range, protein meets target, no duplicate name_normalized+meal_type
5. Upsert via `supabase.table("recipes").upsert(row, on_conflict="name_normalized,meal_type").execute()`
6. Run: `PYTHONPATH=. python scripts/seed_recipes_gaps.py`
7. Report: count inserted, count failed, macro averages per priority

## QUALITY CHECKLIST

- [ ] Every ingredient exists in validated_ingredients.json
- [ ] Macros match sum of ingredient contributions (no manual guessing)
- [ ] No recipe shares top 3 ingredients + meal_type with existing recipes
- [ ] Vegan recipes: NO dairy, eggs, meat, fish
- [ ] Végétarien recipes: NO meat, fish (dairy/eggs OK)
- [ ] Instructions are realistic (3-6 steps, a real person can cook this)
- [ ] Cooking methods varied: grillé, sauté, vapeur, rôti, cru, mariné, poêlé
- [ ] At least 3 ingredients per recipe
