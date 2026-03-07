-- is_admin() helper — referenced by RLS policies in sql/6 and sql/7.
-- Captured from live DB to version-control it.

CREATE OR REPLACE FUNCTION is_admin()
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  is_admin_user BOOLEAN;
BEGIN
  SELECT COALESCE(up.is_admin, FALSE) INTO is_admin_user
  FROM user_profiles up
  WHERE up.id = auth.uid();

  RETURN is_admin_user;
END;
$$;
