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

## MACRO VALIDATION GATE (mandatory before insertion)

Every recipe MUST pass through this validation pipeline before insertion. No exceptions.

### Step A: Calculate macros from ingredients
```python
protein = sum(ing["quantity"] / 100 * ing["nutrition_per_100g"]["protein_g"] for ing in recipe["ingredients"])
fat     = sum(ing["quantity"] / 100 * ing["nutrition_per_100g"]["fat_g"]     for ing in recipe["ingredients"])
carbs   = sum(ing["quantity"] / 100 * ing["nutrition_per_100g"]["carbs_g"]   for ing in recipe["ingredients"])
calories = sum(ing["quantity"] / 100 * ing["nutrition_per_100g"]["calories"] for ing in recipe["ingredients"])
```

### Step B: Check against priority targets
Each priority defines target thresholds (e.g. protein > 25g, fat < 20g, calories 400-700).
If a recipe **fails** its target → go to Step C. If it passes → go to Step D.

### Step C: Auto-adjust ingredient quantities (one attempt)
Try small adjustments (±10-30%) on key ingredients to reach the target:
- **Protein too low?** Increase the main protein source (meat, tofu, legumes) by 10-30%
- **Fat too high?** Reduce fatty ingredients (oil, cheese, nuts) by 10-30%, or substitute (e.g. less oil)
- **Calories out of range?** Scale starchy ingredients (rice, pasta, bread) up or down by 10-20%

Constraints on adjustment:
- Never adjust an ingredient below 10g or above 300g (unrealistic portions)
- Never adjust more than 3 ingredients per recipe
- Keep total portion weight reasonable (200-600g for mains, 100-300g for collations)

After adjustment, **recalculate all macros** (Step A again).

### Step D: Final validation gate
Check the adjusted macros against targets:
- **PASS** → recipe proceeds to insertion
- **FAIL** → recipe is **rejected** (skipped), logged with reason: `"REJECTED: protein=22g < target 25g, fat=24g > target 20g"`

The script must print a summary:
```
=== MACRO VALIDATION REPORT ===
Priority 1 (dejeuner vegan): 10 created, 8 passed, 1 adjusted+passed, 1 rejected
  Rejected: "Curry de pois chiches" — protein=18g < 25g target (even after adjustment)
Priority 2 ...
```

## IMPLEMENTATION

Create `scripts/seed_recipes_gaps.py` (LLM-free — no anthropic/openai imports):

1. Define all recipes as data (list of dicts)
2. **Calculate macros** from nutrition_per_100g (Step A)
3. **Validate against priority targets** (Step B)
4. **Auto-adjust** quantities if targets not met (Step C), then re-validate (Step D)
5. **Reject** recipes that still fail after adjustment — log with reason
6. Detect allergens from ingredient names
7. Validate: no duplicate name_normalized+meal_type
8. Upsert passing recipes via `supabase.table("recipes").upsert(row, on_conflict="name_normalized,meal_type").execute()`
9. Run: `PYTHONPATH=. python scripts/seed_recipes_gaps.py`
10. **Post-insertion DB audit** (Step E) — see below
11. Report: count inserted, count adjusted, count rejected, count purged, macro averages per priority

## STEP E: POST-INSERTION DB AUDIT

After all recipes are inserted, run a SQL query to catch any recipe that slipped through with bad macros.
This is a safety net — the script validation (Steps A-D) should catch most issues, but this catches edge cases.

```python
# Query all newly inserted recipes and re-verify macros from the DB
result = supabase.table("recipes").select(
    "id, name, meal_type, calories_per_serving, protein_g_per_serving, fat_g_per_serving, ingredients"
).eq("source", "seed-gap-analysis").execute()

bad_ids = []
for r in result.data:
    # Recalculate macros from stored ingredients (ground truth)
    ingredients = r["ingredients"] if isinstance(r["ingredients"], list) else json.loads(r["ingredients"])
    calc_prot = sum(i["quantity"] / 100 * i["nutrition_per_100g"]["protein_g"] for i in ingredients)
    calc_fat  = sum(i["quantity"] / 100 * i["nutrition_per_100g"]["fat_g"]     for i in ingredients)
    calc_cal  = sum(i["quantity"] / 100 * i["nutrition_per_100g"]["calories"]  for i in ingredients)

    # Check 1: stored macros match calculated (tolerance ±2g / ±10 kcal)
    if abs(r["protein_g_per_serving"] - calc_prot) > 2 or abs(r["fat_g_per_serving"] - calc_fat) > 2 or abs(r["calories_per_serving"] - calc_cal) > 10:
        print(f"MISMATCH: {r['name']} — stored prot={r['protein_g_per_serving']}g vs calc={calc_prot:.1f}g")
        bad_ids.append(r["id"])
        continue

    # Check 2: macros meet priority targets (lookup from PRIORITY_TARGETS dict)
    target = PRIORITY_TARGETS.get(r["meal_type"])  # defined earlier in script
    if target:
        if calc_prot < target["min_protein"] or calc_fat > target["max_fat"]:
            print(f"OUT OF TARGET: {r['name']} — prot={calc_prot:.1f}g (min {target['min_protein']}), fat={calc_fat:.1f}g (max {target['max_fat']})")
            bad_ids.append(r["id"])

# Delete bad recipes from DB
if bad_ids:
    print(f"\n🗑️ Purging {len(bad_ids)} recipes that failed post-insertion audit")
    for rid in bad_ids:
        supabase.table("recipes").delete().eq("id", rid).execute()
else:
    print("\n✅ Post-insertion audit: all recipes pass")
```

This ensures NO recipe with incorrect macros remains in the database.

## QUALITY CHECKLIST

- [ ] Every ingredient exists in validated_ingredients.json
- [ ] Macros match sum of ingredient contributions (no manual guessing)
- [ ] No recipe shares top 3 ingredients + meal_type with existing recipes
- [ ] Vegan recipes: NO dairy, eggs, meat, fish
- [ ] Végétarien recipes: NO meat, fish (dairy/eggs OK)
- [ ] Instructions are realistic (3-6 steps, a real person can cook this)
- [ ] Cooking methods varied: grillé, sauté, vapeur, rôti, cru, mariné, poêlé
- [ ] At least 3 ingredients per recipe
