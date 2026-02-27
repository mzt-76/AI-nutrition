-- Add last_used_date column to recipes for temporal decay scoring.
-- Backfill from updated_at for recipes that have been used at least once.
ALTER TABLE public.recipes ADD COLUMN last_used_date TIMESTAMPTZ DEFAULT NULL;
UPDATE public.recipes SET last_used_date = updated_at WHERE usage_count > 0;
