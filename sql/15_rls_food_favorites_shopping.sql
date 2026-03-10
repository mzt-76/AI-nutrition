-- Migration 15: Enable RLS on daily_food_log, favorite_recipes, shopping_lists
-- Applied: 2026-03-10
-- Purpose: Version-control RLS policies (may already exist via console)

-- daily_food_log
ALTER TABLE daily_food_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own food log"
ON daily_food_log FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own food log"
ON daily_food_log FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own food log"
ON daily_food_log FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own food log"
ON daily_food_log FOR DELETE USING (auth.uid() = user_id);

CREATE POLICY "Admins can view all food logs"
ON daily_food_log FOR SELECT USING (is_admin());

-- favorite_recipes
ALTER TABLE favorite_recipes ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own favorites"
ON favorite_recipes FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own favorites"
ON favorite_recipes FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own favorites"
ON favorite_recipes FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own favorites"
ON favorite_recipes FOR DELETE USING (auth.uid() = user_id);

CREATE POLICY "Admins can view all favorites"
ON favorite_recipes FOR SELECT USING (is_admin());

-- shopping_lists
ALTER TABLE shopping_lists ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own shopping lists"
ON shopping_lists FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own shopping lists"
ON shopping_lists FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own shopping lists"
ON shopping_lists FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own shopping lists"
ON shopping_lists FOR DELETE USING (auth.uid() = user_id);

CREATE POLICY "Admins can view all shopping lists"
ON shopping_lists FOR SELECT USING (is_admin());
