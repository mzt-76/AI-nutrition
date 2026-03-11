-- Migration 16: Enable RLS on requests table
-- The requests table stores user_query (verbatim user messages with health data).
-- Without RLS, any authenticated user could read all other users' queries via PostgREST.

ALTER TABLE requests ENABLE ROW LEVEL SECURITY;

-- Users can view only their own requests
CREATE POLICY "Users can view their own requests"
ON requests FOR SELECT USING (auth.uid() = user_id);

-- Users can insert their own requests
CREATE POLICY "Users can insert their own requests"
ON requests FOR INSERT WITH CHECK (auth.uid() = user_id);

-- No updates allowed on requests (immutable log)
CREATE POLICY "Deny update for requests"
ON requests FOR UPDATE USING (false);

-- No deletes allowed on requests (immutable log)
CREATE POLICY "Deny delete for requests"
ON requests FOR DELETE USING (false);

-- Admins can view all requests (for monitoring/debugging)
CREATE POLICY "Admins can view all requests"
ON requests FOR SELECT USING (is_admin());
