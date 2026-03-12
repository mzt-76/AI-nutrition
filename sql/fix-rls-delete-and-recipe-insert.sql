-- Task 2.8: Fix RLS policies — allow user-scoped deletes + authenticated recipe inserts

-- meal_plans: allow users to delete their own plans
DROP POLICY IF EXISTS "deny delete meal_plans" ON meal_plans;
CREATE POLICY "users can delete own meal_plans"
  ON meal_plans FOR DELETE
  USING (auth.uid() = user_id);

-- conversations: allow users to delete their own conversations
DROP POLICY IF EXISTS "deny delete conversations" ON conversations;
CREATE POLICY "users can delete own conversations"
  ON conversations FOR DELETE
  USING (auth.uid() = user_id);

-- messages: allow users to delete messages in their conversations
DROP POLICY IF EXISTS "deny delete messages" ON messages;
CREATE POLICY "users can delete own messages"
  ON messages FOR DELETE
  USING (
    session_id IN (
      SELECT session_id FROM conversations WHERE user_id = auth.uid()
    )
  );

-- recipes: allow authenticated users to insert recipes
DROP POLICY IF EXISTS "deny insert recipes" ON recipes;
CREATE POLICY "authenticated users can insert recipes"
  ON recipes FOR INSERT
  WITH CHECK (auth.role() = 'authenticated');
