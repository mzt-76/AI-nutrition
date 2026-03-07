-- RPC function to atomically increment recipe usage_count and update last_used_date.
-- Replaces the fetch-then-update pattern (2 round-trips → 1).

CREATE OR REPLACE FUNCTION increment_recipe_usage(p_recipe_id uuid)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    IF auth.uid() IS NULL THEN
        RAISE EXCEPTION 'Authentication required';
    END IF;

    UPDATE recipes
    SET usage_count = COALESCE(usage_count, 0) + 1,
        last_used_date = now()
    WHERE id = p_recipe_id;
END;
$$;
