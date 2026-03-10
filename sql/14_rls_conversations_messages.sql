-- Migration 14: Enable RLS on conversations and messages tables
-- Applied: 2026-03-10
-- Purpose: Version-control RLS policies (may already exist via console)

-- conversations
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own conversations"
ON conversations FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own conversations"
ON conversations FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own conversations"
ON conversations FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Admins can view all conversations"
ON conversations FOR SELECT USING (is_admin());

CREATE POLICY "Deny delete for conversations"
ON conversations FOR DELETE USING (false);

-- messages (ownership via session_id -> conversations.session_id -> user_id)
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own messages"
ON messages FOR SELECT USING (
    EXISTS (
        SELECT 1 FROM conversations c
        WHERE c.session_id = messages.session_id
        AND c.user_id = auth.uid()
    )
);

CREATE POLICY "Users can insert their own messages"
ON messages FOR INSERT WITH CHECK (
    EXISTS (
        SELECT 1 FROM conversations c
        WHERE c.session_id = messages.session_id
        AND c.user_id = auth.uid()
    )
);

CREATE POLICY "Admins can view all messages"
ON messages FOR SELECT USING (is_admin());

CREATE POLICY "Deny delete for messages"
ON messages FOR DELETE USING (false);
