-- Ingredient Mapping Table for FatSecret API Caching
-- Purpose: Cache ingredient → FatSecret food database mappings to reduce API calls and improve performance

CREATE TABLE IF NOT EXISTS ingredient_mapping (
    -- Primary Key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Ingredient Identification
    ingredient_name TEXT NOT NULL UNIQUE,  -- Original name as provided (e.g., "Poulet rôti", "Riz basmati")
    ingredient_name_normalized TEXT NOT NULL,  -- Lowercase, accent-free version for matching (e.g., "poulet roti", "riz basmati")

    -- FatSecret Mapping
    fatsecret_food_id TEXT NOT NULL,  -- FatSecret database ID (e.g., "12345")
    fatsecret_food_name TEXT NOT NULL,  -- Official FatSecret name (e.g., "Chicken, roasted")

    -- Nutritional Data (per 100g)
    calories_per_100g NUMERIC(7, 2) NOT NULL,  -- kcal per 100g
    protein_g_per_100g NUMERIC(6, 2) NOT NULL,  -- grams per 100g
    carbs_g_per_100g NUMERIC(6, 2) NOT NULL,    -- grams per 100g
    fat_g_per_100g NUMERIC(6, 2) NOT NULL,      -- grams per 100g

    -- Quality Metrics
    confidence_score NUMERIC(3, 2) NOT NULL DEFAULT 0.0 CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),  -- Fuzzy match score (0.0-1.0)
    verified BOOLEAN NOT NULL DEFAULT FALSE,  -- Manually verified by nutrition expert
    usage_count INTEGER NOT NULL DEFAULT 1,   -- How many times this mapping has been used

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for Performance
CREATE INDEX IF NOT EXISTS idx_ingredient_name ON ingredient_mapping(ingredient_name);
CREATE INDEX IF NOT EXISTS idx_ingredient_normalized ON ingredient_mapping(ingredient_name_normalized);
CREATE INDEX IF NOT EXISTS idx_verified ON ingredient_mapping(verified) WHERE verified = TRUE;
CREATE INDEX IF NOT EXISTS idx_usage_count ON ingredient_mapping(usage_count DESC);  -- Most-used ingredients first

-- Update timestamp trigger
CREATE OR REPLACE FUNCTION update_ingredient_mapping_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_ingredient_mapping_timestamp
    BEFORE UPDATE ON ingredient_mapping
    FOR EACH ROW
    EXECUTE FUNCTION update_ingredient_mapping_updated_at();

-- Comments for documentation
COMMENT ON TABLE ingredient_mapping IS 'Caches ingredient → FatSecret food database mappings to reduce API calls and improve meal plan generation performance';
COMMENT ON COLUMN ingredient_mapping.ingredient_name IS 'Original ingredient name as provided in meal plans (e.g., "Poulet rôti")';
COMMENT ON COLUMN ingredient_mapping.ingredient_name_normalized IS 'Normalized version for fuzzy matching: lowercase, no accents, trimmed spaces';
COMMENT ON COLUMN ingredient_mapping.fatsecret_food_id IS 'FatSecret Platform API food ID';
COMMENT ON COLUMN ingredient_mapping.confidence_score IS 'Fuzzy match confidence (0.0-1.0). Values <0.5 indicate low confidence matches that should be reviewed';
COMMENT ON COLUMN ingredient_mapping.verified IS 'TRUE if manually verified by nutrition expert, FALSE if auto-matched';
COMMENT ON COLUMN ingredient_mapping.usage_count IS 'Number of times this mapping has been used in meal plans. Higher = more popular ingredient';
