---
name: seed-recipes
description: Seed the recipe database with new healthy/sporty recipes that fill identified gaps. Use when the user wants to add recipes, enrich the recipe DB, fill coverage gaps, or improve variety. Triggers on requests like "ajoute des recettes", "seed recipes", "enrichir la base de recettes", "combler les gaps". Launches a background worktree subagent that analyzes gaps, creates recipes from OFF-validated ingredients only, and inserts them.
---

# Seed Recipes — Gap-Filling Workflow

## Process Overview

1. **Gap analysis** — Query DB for coverage by meal_type × diet_type × cuisine_type × macro profile
2. **Export context** — Save recipe signatures + validated ingredients to JSON files
3. **Launch subagent** — Background worktree agent creates and inserts recipes
4. **Verify** — Check for duplicates/similarity after insertion

## Step 1: Gap Analysis

Run these 3 SQL queries via `mcp__supabase__execute_sql`:

```sql
-- 1. Distribution meal_type × diet_type with macro averages
SELECT meal_type, diet_type, COUNT(*) as count,
  ROUND(AVG(calories_per_serving)) as avg_cal,
  ROUND(AVG(protein_g_per_serving)) as avg_prot,
  ROUND(AVG(fat_g_per_serving)) as avg_fat
FROM recipes WHERE off_validated = true
GROUP BY meal_type, diet_type ORDER BY meal_type, diet_type;

-- 2. Cuisine distribution
SELECT cuisine_type, meal_type, COUNT(*) as count
FROM recipes WHERE off_validated = true
GROUP BY cuisine_type, meal_type ORDER BY count DESC;

-- 3. Macro profile gaps (high-protein low-fat counts)
SELECT meal_type, COUNT(*) as total,
  COUNT(*) FILTER (WHERE protein_g_per_serving > 30 AND fat_g_per_serving < 20) as high_prot_low_fat,
  COUNT(*) FILTER (WHERE protein_g_per_serving > 25 AND fat_g_per_serving < 25) as good_prot_mod_fat,
  COUNT(*) FILTER (WHERE fat_g_per_serving > 30) as high_fat
FROM recipes WHERE off_validated = true
GROUP BY meal_type ORDER BY meal_type;
```

Present results to user as tables. Identify gaps: under-represented categories, missing cuisines, weak macro profiles.

## Step 2: Export Context Files

Run this Python snippet to create the two JSON files the subagent needs:

```bash
PYTHONPATH=. python -c "
from src.clients import get_supabase_client
import json

sb = get_supabase_client()

# Recipe signatures (dedup reference)
recipes = sb.table('recipes').select('name_normalized, meal_type, diet_type, cuisine_type, calories_per_serving, protein_g_per_serving, fat_g_per_serving, carbs_g_per_serving, ingredients').eq('off_validated', True).execute()
sigs = []
for r in recipes.data:
    ings = r.get('ingredients') or []
    if isinstance(ings, str): ings = json.loads(ings)
    sorted_ings = sorted(ings, key=lambda x: float(x.get('quantity', 0) or 0), reverse=True)
    sigs.append({'name': r['name_normalized'], 'meal': r['meal_type'], 'diet': r['diet_type'], 'cuisine': r['cuisine_type'],
        'cal': round(float(r.get('calories_per_serving') or 0)), 'prot': round(float(r.get('protein_g_per_serving') or 0)),
        'fat': round(float(r.get('fat_g_per_serving') or 0)), 'top_ing': [i.get('name','?') for i in sorted_ings[:4]]})
sigs.sort(key=lambda x: (x['meal'], x['name']))
with open('scripts/data/recipe_signatures.json', 'w', encoding='utf-8') as f: json.dump(sigs, f, ensure_ascii=False, indent=1)
print(f'{len(sigs)} signatures saved')

# Validated ingredients (OFF-guaranteed)
ings = sb.table('ingredient_mapping').select('ingredient_name, openfoodfacts_name, calories_per_100g, protein_g_per_100g, fat_g_per_100g, carbs_g_per_100g').gt('confidence_score', '0.5').execute()
items = [{'name': i['ingredient_name'], 'off_name': i['openfoodfacts_name'], 'cal': float(i['calories_per_100g']),
    'prot': float(i['protein_g_per_100g']), 'fat': float(i['fat_g_per_100g']), 'carbs': float(i['carbs_g_per_100g'])} for i in ings.data]
items.sort(key=lambda x: x['name'].lower())
with open('scripts/data/validated_ingredients.json', 'w', encoding='utf-8') as f: json.dump(items, f, ensure_ascii=False, indent=1)
print(f'{len(items)} validated ingredients saved')
"
```

## Step 3: Launch Subagent

Launch a **background worktree agent** with the prompt from `references/subagent-prompt.md`.

Customize the prompt before sending by replacing the `PRIORITIES` section with the actual gaps identified in Step 1. Specify:
- How many recipes per category
- Target macros (protein, fat, calorie ranges)
- Which diet_types and cuisine_types to prioritize
- Total recipe count

```
Agent(
  description="Seed N gap-filling recipes",
  mode="bypassPermissions",
  isolation="worktree",
  run_in_background=True,
  prompt=<contents of references/subagent-prompt.md with PRIORITIES filled in>
)
```

## Step 4: Verify After Completion

Once the agent finishes, run this duplicate check:

```sql
-- Check top-2 ingredient similarity between new and existing
WITH recipe_top2 AS (
  SELECT r.id, r.name, r.meal_type, r.source,
    (SELECT string_agg(x.ing_name, '|' ORDER BY x.qty DESC)
     FROM (SELECT elem->>'name' as ing_name, (elem->>'quantity')::float as qty
           FROM jsonb_array_elements(r.ingredients::jsonb) AS elem
           ORDER BY (elem->>'quantity')::float DESC LIMIT 2) x) as top2
  FROM recipes r WHERE r.off_validated = true
)
SELECT n.name as new_name, o.name as existing_name, n.meal_type, n.top2
FROM recipe_top2 n JOIN recipe_top2 o
  ON n.meal_type = o.meal_type AND n.top2 = o.top2 AND n.id != o.id
WHERE n.source = 'seed-gap-analysis'
  AND (o.source IS NULL OR o.source != 'seed-gap-analysis');
```

If true duplicates found (same dish, not just shared ingredients), delete them:
```sql
DELETE FROM recipes WHERE id IN (...duplicate_ids...);
```

Report final count and distribution to user.
