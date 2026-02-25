-- Migration 5: Add user_id FK columns to per-user tables
-- Applied: 2026-02-25
-- Tables: meal_plans, weekly_feedback, user_learning_profile

-- meal_plans
ALTER TABLE meal_plans
  ADD COLUMN user_id UUID REFERENCES user_profiles(id) ON DELETE CASCADE;

CREATE INDEX idx_meal_plans_user_id ON meal_plans(user_id);

UPDATE meal_plans SET user_id = '5745fc58-9c75-48b1-bc79-12855a8c6021'
WHERE user_id IS NULL;

-- weekly_feedback
ALTER TABLE weekly_feedback
  ADD COLUMN user_id UUID REFERENCES user_profiles(id) ON DELETE CASCADE;

CREATE INDEX idx_weekly_feedback_user_id ON weekly_feedback(user_id);

UPDATE weekly_feedback SET user_id = '5745fc58-9c75-48b1-bc79-12855a8c6021'
WHERE user_id IS NULL;

-- user_learning_profile (UNIQUE — one per user, empty table so no backfill)
ALTER TABLE user_learning_profile
  ADD COLUMN user_id UUID UNIQUE REFERENCES user_profiles(id) ON DELETE CASCADE;

CREATE UNIQUE INDEX idx_learning_profile_user_id ON user_learning_profile(user_id);
