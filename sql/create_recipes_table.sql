-- Recipe Database Table for AI Nutrition Assistant
-- Purpose: Store pre-validated recipes with macros calculated via OpenFoodFacts
-- Used by: meal-planning skill scripts (select_recipes, generate_day_plan)

CREATE TABLE IF NOT EXISTS recipes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identification
    name TEXT NOT NULL,                          -- "Omelette protéinée aux épinards"
    name_normalized TEXT NOT NULL,               -- "omelette proteinee aux epinards"
    description TEXT,                            -- Short description

    -- Classification
    meal_type TEXT NOT NULL,                     -- "petit-dejeuner", "dejeuner", "diner", "collation"
    cuisine_type TEXT DEFAULT 'française',       -- "française", "italienne", "asiatique", etc.
    diet_type TEXT DEFAULT 'omnivore',           -- "omnivore", "végétarien", "vegan", etc.
    tags TEXT[] DEFAULT '{}',                    -- ["high-protein", "quick", "low-carb"]

    -- Recipe Content
    ingredients JSONB NOT NULL,                  -- [{"name": "Eggs", "quantity": 3, "unit": "units", "nutrition_per_100g": {...}}]
    instructions TEXT NOT NULL,                  -- French instructions
    prep_time_minutes INTEGER DEFAULT 30,

    -- Pre-calculated Nutrition (per 1 serving)
    calories_per_serving NUMERIC(7,2) NOT NULL,
    protein_g_per_serving NUMERIC(6,2) NOT NULL,
    carbs_g_per_serving NUMERIC(6,2) NOT NULL,
    fat_g_per_serving NUMERIC(6,2) NOT NULL,

    -- Allergen Safety (pre-computed from ingredients)
    allergen_tags TEXT[] DEFAULT '{}',           -- ["lactose", "gluten", "oeuf"]

    -- Quality & Usage
    source TEXT DEFAULT 'llm_generated',         -- "llm_generated", "user_validated", "expert_curated"
    off_validated BOOLEAN DEFAULT FALSE,          -- All ingredients matched in OpenFoodFacts
    usage_count INTEGER DEFAULT 0,
    rating NUMERIC(2,1) DEFAULT 0.0,             -- 0.0-5.0 user rating

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for Performance
CREATE INDEX IF NOT EXISTS idx_recipes_meal_type ON recipes(meal_type);
CREATE INDEX IF NOT EXISTS idx_recipes_diet_type ON recipes(diet_type);
CREATE INDEX IF NOT EXISTS idx_recipes_allergen_tags ON recipes USING GIN(allergen_tags);
CREATE INDEX IF NOT EXISTS idx_recipes_tags ON recipes USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_recipes_name_normalized ON recipes(name_normalized);
CREATE INDEX IF NOT EXISTS idx_recipes_calories ON recipes(calories_per_serving);
CREATE INDEX IF NOT EXISTS idx_recipes_protein ON recipes(protein_g_per_serving);

-- Trigger for updated_at (reuses the function from ingredient_mapping)
CREATE TRIGGER trigger_update_recipes_timestamp
    BEFORE UPDATE ON recipes
    FOR EACH ROW
    EXECUTE FUNCTION update_ingredient_mapping_updated_at();

-- Comments for documentation
COMMENT ON TABLE recipes IS 'Pre-validated recipes with macros from OpenFoodFacts. Used by day-by-day meal planning for fast, reliable plan generation.';
COMMENT ON COLUMN recipes.name_normalized IS 'Lowercase, accent-free version for deduplication and matching';
COMMENT ON COLUMN recipes.meal_type IS 'One of: petit-dejeuner, dejeuner, diner, collation';
COMMENT ON COLUMN recipes.allergen_tags IS 'Pre-computed allergen tags from ingredients. Used for Python-side filtering (zero tolerance).';
COMMENT ON COLUMN recipes.off_validated IS 'TRUE if all ingredients were matched in OpenFoodFacts. Macros are reliable.';
COMMENT ON COLUMN recipes.usage_count IS 'Incremented each time recipe is used in a meal plan. Used for variety tracking.';
