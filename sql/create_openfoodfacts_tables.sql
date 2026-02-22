-- OpenFoodFacts Database Setup
-- Creates the products table, search RPC function, and required extensions.
--
-- PREREQUISITES (run once in Supabase SQL Editor if not already enabled):
--   CREATE EXTENSION IF NOT EXISTS pg_trgm;
--   CREATE EXTENSION IF NOT EXISTS unaccent;
--
-- USAGE:
--   1. Enable extensions (above) if not already active
--   2. Run this entire file in Supabase SQL Editor
--   3. Import data: python -m src.nutrition.openfoodfacts_import
--   4. Verify: SELECT * FROM search_openfoodfacts('poulet', 3);

-- =============================================================================
-- Extensions (idempotent)
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- =============================================================================
-- Table: openfoodfacts_products
-- =============================================================================

CREATE TABLE IF NOT EXISTS openfoodfacts_products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Product identification
    code TEXT UNIQUE NOT NULL,                  -- OpenFoodFacts barcode
    product_name TEXT NOT NULL,                 -- International name
    product_name_fr TEXT,                       -- French name (preferred for matching)

    -- Geographic availability
    countries_tags TEXT[],                      -- e.g., ['en:france', 'en:belgium']

    -- Nutrition per 100g
    calories_per_100g NUMERIC(7, 2) NOT NULL,
    protein_g_per_100g NUMERIC(6, 2) NOT NULL,
    carbs_g_per_100g NUMERIC(6, 2) NOT NULL,
    fat_g_per_100g NUMERIC(6, 2) NOT NULL,

    -- Full-text search vector (auto-populated by trigger)
    search_vector tsvector,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for search performance
CREATE INDEX IF NOT EXISTS idx_off_search ON openfoodfacts_products USING GIN(search_vector);
CREATE INDEX IF NOT EXISTS idx_off_countries ON openfoodfacts_products USING GIN(countries_tags);
CREATE INDEX IF NOT EXISTS idx_off_code ON openfoodfacts_products(code);
CREATE INDEX IF NOT EXISTS idx_off_product_name_trgm ON openfoodfacts_products USING GIN(product_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_off_product_name_fr_trgm ON openfoodfacts_products USING GIN(product_name_fr gin_trgm_ops);

-- Auto-update search_vector on INSERT/UPDATE
CREATE OR REPLACE FUNCTION update_off_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('pg_catalog.french', COALESCE(NEW.product_name_fr, '')), 'A') ||
        setweight(to_tsvector('pg_catalog.french', COALESCE(NEW.product_name, '')), 'B');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tsvector_update_off ON openfoodfacts_products;
CREATE TRIGGER tsvector_update_off
    BEFORE INSERT OR UPDATE ON openfoodfacts_products
    FOR EACH ROW EXECUTE FUNCTION update_off_search_vector();

-- =============================================================================
-- RPC Function: search_openfoodfacts
-- Called by src/nutrition/openfoodfacts_client.py search_food_local()
-- =============================================================================

CREATE OR REPLACE FUNCTION search_openfoodfacts(
    search_query TEXT,
    max_results INT DEFAULT 5
)
RETURNS TABLE (
    code TEXT,
    product_name TEXT,
    product_name_fr TEXT,
    calories_per_100g NUMERIC,
    protein_g_per_100g NUMERIC,
    carbs_g_per_100g NUMERIC,
    fat_g_per_100g NUMERIC,
    similarity_score FLOAT
) LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT
        p.code,
        p.product_name,
        p.product_name_fr,
        p.calories_per_100g,
        p.protein_g_per_100g,
        p.carbs_g_per_100g,
        p.fat_g_per_100g,
        GREATEST(
            similarity(unaccent(search_query), unaccent(p.product_name)),
            similarity(unaccent(search_query), unaccent(COALESCE(p.product_name_fr, '')))
        )::FLOAT AS similarity_score
    FROM openfoodfacts_products p
    WHERE
        -- Full-text search OR trigram similarity match
        (p.search_vector @@ plainto_tsquery('french', search_query)
         OR similarity(unaccent(search_query), unaccent(p.product_name)) > 0.3
         OR similarity(unaccent(search_query), unaccent(COALESCE(p.product_name_fr, ''))) > 0.3)
        -- Only French products
        AND 'en:france' = ANY(p.countries_tags)
    ORDER BY similarity_score DESC
    LIMIT max_results;
END; $$;

-- =============================================================================
-- Comments
-- =============================================================================

COMMENT ON TABLE openfoodfacts_products IS 'Local copy of OpenFoodFacts products (French, with nutrition data). Populated by src/nutrition/openfoodfacts_import.py';
COMMENT ON FUNCTION search_openfoodfacts IS 'Full-text + trigram search for ingredient matching. Called by openfoodfacts_client.py';
