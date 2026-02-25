-- Migration 6: Enable RLS on per-user tables
-- Applied: 2026-02-25
-- Tables: meal_plans, weekly_feedback, user_learning_profile

-- meal_plans
ALTER TABLE meal_plans ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own meal plans"
ON meal_plans FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own meal plans"
ON meal_plans FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own meal plans"
ON meal_plans FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Admins can view all meal plans"
ON meal_plans FOR SELECT USING (is_admin());

CREATE POLICY "Admins can insert meal plans"
ON meal_plans FOR INSERT WITH CHECK (is_admin());

CREATE POLICY "Deny delete for meal_plans"
ON meal_plans FOR DELETE USING (false);

-- weekly_feedback
ALTER TABLE weekly_feedback ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own weekly feedback"
ON weekly_feedback FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own weekly feedback"
ON weekly_feedback FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own weekly feedback"
ON weekly_feedback FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Admins can view all weekly feedback"
ON weekly_feedback FOR SELECT USING (is_admin());

CREATE POLICY "Admins can insert weekly feedback"
ON weekly_feedback FOR INSERT WITH CHECK (is_admin());

CREATE POLICY "Deny delete for weekly_feedback"
ON weekly_feedback FOR DELETE USING (false);

-- user_learning_profile
ALTER TABLE user_learning_profile ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own learning profile"
ON user_learning_profile FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own learning profile"
ON user_learning_profile FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own learning profile"
ON user_learning_profile FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Admins can view all learning profiles"
ON user_learning_profile FOR SELECT USING (is_admin());

CREATE POLICY "Deny delete for user_learning_profile"
ON user_learning_profile FOR DELETE USING (false);
