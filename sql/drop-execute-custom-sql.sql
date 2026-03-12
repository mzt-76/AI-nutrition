-- Task 1.1: Drop unused execute_custom_sql function (security risk)
DROP FUNCTION IF EXISTS public.execute_custom_sql(text);
