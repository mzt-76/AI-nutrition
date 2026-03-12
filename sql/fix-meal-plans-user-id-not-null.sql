-- Task 3.5: Make meal_plans.user_id non-nullable
ALTER TABLE meal_plans ALTER COLUMN user_id SET NOT NULL;
