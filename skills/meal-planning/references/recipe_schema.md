# Recipe Schema Documentation

## Table: `recipes`

Pre-validated recipes with macros calculated via OpenFoodFacts. Used by the day-by-day meal planning pipeline.

## Schema

```sql
id UUID PRIMARY KEY DEFAULT gen_random_uuid()

-- Identification
name TEXT NOT NULL                    -- "Omelette protéinée aux épinards"
name_normalized TEXT NOT NULL         -- "omelette proteinee aux epinards" (for dedup)
description TEXT                      -- Short description (1-2 sentences)

-- Classification
meal_type TEXT NOT NULL               -- "petit-dejeuner" | "dejeuner" | "diner" | "collation"
cuisine_type TEXT DEFAULT 'française' -- "française" | "italienne" | "asiatique" | "méditerranéenne"
diet_type TEXT DEFAULT 'omnivore'     -- "omnivore" | "végétarien" | "vegan"
tags TEXT[] DEFAULT '{}'              -- ["high-protein", "quick", "low-carb"]

-- Recipe Content
ingredients JSONB NOT NULL            -- See ingredient schema below
instructions TEXT NOT NULL            -- French step-by-step instructions
prep_time_minutes INTEGER DEFAULT 30

-- Pre-calculated Nutrition (per 1 serving)
calories_per_serving NUMERIC(7,2) NOT NULL
protein_g_per_serving NUMERIC(6,2) NOT NULL
carbs_g_per_serving NUMERIC(6,2) NOT NULL
fat_g_per_serving NUMERIC(6,2) NOT NULL

-- Allergen Safety (pre-computed from ingredients)
allergen_tags TEXT[] DEFAULT '{}'     -- ["lactose", "gluten", "oeuf"] — empty = allergen-free

-- Quality & Usage
source TEXT DEFAULT 'llm_generated'  -- "llm_generated" | "user_validated" | "expert_curated"
off_validated BOOLEAN DEFAULT FALSE   -- TRUE if all ingredients matched in OpenFoodFacts
usage_count INTEGER DEFAULT 0         -- Incremented each time recipe is used in a meal plan
rating NUMERIC(2,1) DEFAULT 0.0       -- 0.0-5.0 user rating

-- Metadata
created_at TIMESTAMPTZ DEFAULT NOW()
updated_at TIMESTAMPTZ DEFAULT NOW()
```

## Ingredient Schema (JSONB array)

Each ingredient in the `ingredients` array:

```json
{
  "name": "Blancs d'oeufs",
  "quantity": 4,
  "unit": "pièces",
  "macros_calculated": {
    "calories": 68,
    "protein_g": 14,
    "carbs_g": 0.6,
    "fat_g": 0.1,
    "confidence": 0.95,
    "cache_hit": true
  }
}
```

## Meal Types

| `meal_type` | Description |
|-------------|-------------|
| `petit-dejeuner` | Breakfast (07:00-09:00) |
| `dejeuner` | Lunch (12:00-14:00) |
| `diner` | Dinner (19:00-21:00) |
| `collation` | Snack (any time) |

## Allergen Tags

Pre-computed from ingredients. Matches allergen families in `allergen_families.md`.

Common values: `lactose`, `gluten`, `oeuf`, `arachides`, `fruits-a-coque`, `soja`, `poisson`, `sesame`

Empty array `[]` means the recipe is free of all major allergens.

## Quality Levels

| `source` | `off_validated` | Reliability |
|----------|-----------------|-------------|
| `expert_curated` | TRUE | Highest — manually verified |
| `user_validated` | TRUE | High — user confirmed |
| `llm_generated` | TRUE | Good — OFF-validated macros |
| `llm_generated` | FALSE | Approximate — some ingredients unmatched |

## Output Format Contract

Recipes stored in the `meal_plans.plan_data` JSONB use this structure (compatible with shopping list and fetch tools):

```json
{
  "days": [
    {
      "day": "Lundi",
      "date": "2026-02-18",
      "meals": [
        {
          "meal_type": "Petit-déjeuner",
          "name": "Omelette protéinée aux épinards",
          "ingredients": [
            {"name": "oeufs", "quantity": 3, "unit": "pièces"},
            {"name": "épinards", "quantity": 50, "unit": "g"}
          ],
          "instructions": "Battre les oeufs, ajouter les épinards, cuire à feu moyen.",
          "prep_time_minutes": 10,
          "nutrition": {
            "calories": 450.0,
            "protein_g": 28.0,
            "carbs_g": 5.0,
            "fat_g": 35.0
          }
        }
      ],
      "daily_totals": {
        "calories": 2800.0,
        "protein_g": 175.0,
        "carbs_g": 350.0,
        "fat_g": 80.0
      }
    }
  ],
  "weekly_summary": {
    "average_calories": 2800.0,
    "average_protein_g": 175.0,
    "average_carbs_g": 350.0,
    "average_fat_g": 80.0
  }
}
```

## Indexes

- `idx_recipes_meal_type` — Primary query filter
- `idx_recipes_diet_type` — Diet filtering
- `idx_recipes_allergen_tags` GIN — Allergen filtering (Python-side)
- `idx_recipes_tags` GIN — Tag filtering
- `idx_recipes_name_normalized` — Deduplication
- `idx_recipes_calories` — Calorie range filtering
- `idx_recipes_protein` — Protein filtering
