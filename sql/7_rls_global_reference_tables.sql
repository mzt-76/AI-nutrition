-- Migration 7: Enable RLS on global reference tables
-- Applied: 2026-02-25
-- Tables: recipes, ingredient_mapping, openfoodfacts_products, documents, document_metadata, document_rows

-- Recipes
ALTER TABLE recipes ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Authenticated users can read recipes"
ON recipes FOR SELECT TO authenticated USING (true);
CREATE POLICY "Admins can insert recipes"
ON recipes FOR INSERT WITH CHECK (is_admin());
CREATE POLICY "Admins can update recipes"
ON recipes FOR UPDATE USING (is_admin());
CREATE POLICY "Deny delete for recipes"
ON recipes FOR DELETE USING (false);

-- Ingredient mapping
ALTER TABLE ingredient_mapping ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Authenticated users can read ingredient mapping"
ON ingredient_mapping FOR SELECT TO authenticated USING (true);
CREATE POLICY "Admins can insert ingredient mapping"
ON ingredient_mapping FOR INSERT WITH CHECK (is_admin());
CREATE POLICY "Admins can update ingredient mapping"
ON ingredient_mapping FOR UPDATE USING (is_admin());
CREATE POLICY "Deny delete for ingredient_mapping"
ON ingredient_mapping FOR DELETE USING (false);

-- OpenFoodFacts products
ALTER TABLE openfoodfacts_products ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Authenticated users can read openfoodfacts products"
ON openfoodfacts_products FOR SELECT TO authenticated USING (true);
CREATE POLICY "Admins can insert openfoodfacts products"
ON openfoodfacts_products FOR INSERT WITH CHECK (is_admin());
CREATE POLICY "Admins can update openfoodfacts products"
ON openfoodfacts_products FOR UPDATE USING (is_admin());
CREATE POLICY "Deny delete for openfoodfacts_products"
ON openfoodfacts_products FOR DELETE USING (false);

-- Document tables (RAG)
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_metadata ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_rows ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated can read documents" ON documents FOR SELECT TO authenticated USING (true);
CREATE POLICY "Authenticated can read document_metadata" ON document_metadata FOR SELECT TO authenticated USING (true);
CREATE POLICY "Authenticated can read document_rows" ON document_rows FOR SELECT TO authenticated USING (true);

CREATE POLICY "Admins can manage documents" ON documents FOR ALL USING (is_admin());
CREATE POLICY "Admins can manage document_metadata" ON document_metadata FOR ALL USING (is_admin());
CREATE POLICY "Admins can manage document_rows" ON document_rows FOR ALL USING (is_admin());
