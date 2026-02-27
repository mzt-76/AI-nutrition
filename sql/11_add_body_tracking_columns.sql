-- Migration 11: Add body tracking columns to weekly_feedback
-- Applied: 2026-02-27
-- Purpose: Optional body composition & measurement columns for baseline and ongoing tracking

-- Body composition columns (all optional, nullable)
ALTER TABLE weekly_feedback ADD COLUMN IF NOT EXISTS body_fat_percent NUMERIC(4,1);
ALTER TABLE weekly_feedback ADD COLUMN IF NOT EXISTS muscle_mass_kg NUMERIC(5,2);
ALTER TABLE weekly_feedback ADD COLUMN IF NOT EXISTS water_percent NUMERIC(4,1);

-- Body measurements (optional, typically monthly or at baseline)
ALTER TABLE weekly_feedback ADD COLUMN IF NOT EXISTS waist_cm NUMERIC(5,1);
ALTER TABLE weekly_feedback ADD COLUMN IF NOT EXISTS hips_cm NUMERIC(5,1);
ALTER TABLE weekly_feedback ADD COLUMN IF NOT EXISTS chest_cm NUMERIC(5,1);
ALTER TABLE weekly_feedback ADD COLUMN IF NOT EXISTS arm_cm NUMERIC(5,1);
ALTER TABLE weekly_feedback ADD COLUMN IF NOT EXISTS thigh_cm NUMERIC(5,1);

-- Measurement context
ALTER TABLE weekly_feedback ADD COLUMN IF NOT EXISTS measurement_method TEXT;
-- Values: 'smart_scale', 'manual', 'image_analysis', 'calipers'

-- Photo references (optional, storage bucket paths)
ALTER TABLE weekly_feedback ADD COLUMN IF NOT EXISTS photo_refs JSONB;
-- Example: {"front": "storage/path/front.jpg", "side": "storage/path/side.jpg"}

-- Partial unique index: only one baseline (week_number=0) per user
CREATE UNIQUE INDEX IF NOT EXISTS idx_weekly_feedback_baseline_per_user
ON weekly_feedback (user_id) WHERE week_number = 0;
