-- Migration 8: Fix function search_path security warnings
-- Applied: 2026-02-25

ALTER FUNCTION public.update_ingredient_mapping_updated_at() SET search_path = public;
ALTER FUNCTION public.match_memories(vector, integer, jsonb) SET search_path = public;
ALTER FUNCTION public.handle_new_user() SET search_path = public;
ALTER FUNCTION public.is_admin() SET search_path = public;
ALTER FUNCTION public.match_documents(vector, integer, jsonb) SET search_path = public;
ALTER FUNCTION public.search_openfoodfacts(text, integer) SET search_path = public;
ALTER FUNCTION public.execute_custom_sql(text) SET search_path = public;
