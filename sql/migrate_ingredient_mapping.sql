-- Migration: Rename fatsecret_* columns to openfoodfacts_* in ingredient_mapping table
-- Purpose: Align SQL schema with actual Python code which already uses openfoodfacts_* column names
--
-- USAGE:
--   1. Check current state: SELECT column_name FROM information_schema.columns
--                           WHERE table_name = 'ingredient_mapping' ORDER BY ordinal_position;
--   2. If columns are STILL named fatsecret_*: Run the ALTER statements below
--   3. If columns are ALREADY named openfoodfacts_*: DB was already migrated, skip this file
--
-- VERIFY after migration:
--   SELECT openfoodfacts_code FROM ingredient_mapping LIMIT 1;

-- Step 1: Check current column names (run this first)
-- SELECT column_name FROM information_schema.columns
-- WHERE table_name = 'ingredient_mapping' ORDER BY ordinal_position;

-- Step 2: Rename columns (only if still named fatsecret_*)
ALTER TABLE ingredient_mapping RENAME COLUMN fatsecret_food_id TO openfoodfacts_code;
ALTER TABLE ingredient_mapping RENAME COLUMN fatsecret_food_name TO openfoodfacts_name;

-- Step 3: Update table comment
COMMENT ON TABLE ingredient_mapping IS 'Caches ingredient → OpenFoodFacts mappings to reduce API calls and improve meal plan generation performance';
COMMENT ON COLUMN ingredient_mapping.openfoodfacts_code IS 'OpenFoodFacts barcode/ID for the matched product';
COMMENT ON COLUMN ingredient_mapping.openfoodfacts_name IS 'Official OpenFoodFacts product name';
