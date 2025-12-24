CREATE TABLE IF NOT EXISTS user_learning_profile (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Personalization factors learned over time
  protein_sensitivity_g_per_kg NUMERIC(3,2),
  -- Range: 1.4 - 3.1 (ISSN guidelines extended for individual variability)
  -- Null = not yet learned

  carb_sensitivity TEXT CHECK (carb_sensitivity IN ('low', 'medium', 'high', NULL)),
  fat_sensitivity TEXT CHECK (fat_sensitivity IN ('low', 'medium', 'high', NULL)),

  -- Macro distribution preference (learned from optimal weeks)
  preferred_macro_distribution JSONB DEFAULT '{}'::JSONB,
  -- Example: {"carb_percent": 45, "protein_percent": 35, "fat_percent": 20}

  -- Adherence insights
  adherence_triggers JSONB DEFAULT '{}'::JSONB,
  -- Example: {"positive": ["pre-workout_carbs", "easy_meals"], "negative": ["fridays", "stress_periods"]}

  meal_preferences JSONB DEFAULT '{}'::JSONB,
  -- Example: {"loved": ["chicken_rice", "eggs"], "disliked": ["fish", "tofu"], "avoided_times": ["friday_low_carb"]}

  -- Energy & metabolism
  energy_patterns JSONB DEFAULT '{}'::JSONB,
  -- Example: {"friday_drops": true, "correlates_with": "low_carbs", "recovers_with": "extra_carbs_prewo"}

  calculated_tdee NUMERIC(4,0),
  -- TDEE from formula (e.g., 2868)

  observed_tdee NUMERIC(4,0),
  -- Actual TDEE inferred from weight changes over 4+ weeks
  -- Null until sufficient data

  metabolic_adaptation_detected BOOLEAN DEFAULT FALSE,
  metabolic_adaptation_factor NUMERIC(3,2),
  -- Factor to adjust future TDEE estimates (e.g., 0.95 = 5% lower metabolism)

  -- Learning confidence
  weeks_of_data INT DEFAULT 0,
  confidence_level NUMERIC(3,2) DEFAULT 0.0,
  -- 0.0 - 1.0: increases with weeks and consistency of patterns

  -- Psychological patterns
  stress_response JSONB DEFAULT '{}'::JSONB,
  -- Example: {"stress_increases_hunger": true, "needs_support": true, "recovery_strategy": "extra_planning"}

  motivation_pattern TEXT CHECK (motivation_pattern IN ('consistent', 'cycles', 'declining', NULL)),
  motivation_notes TEXT,

  -- Red flag history
  red_flags_history JSONB DEFAULT '{}'::JSONB,
  -- Example: {"rapid_weight_loss": 0, "extreme_hunger": 0, "energy_crash": 2, "stress_eating": 1}
  -- Counts of how many times each flag triggered

  -- Last update and next review
  updated_at TIMESTAMP DEFAULT NOW(),
  next_review_week_number INT
);

CREATE UNIQUE INDEX idx_learning_profile_one_per_user ON user_learning_profile(id);
-- Ensures only one profile per user (may add user_id constraint later if multi-user)
