CREATE TABLE IF NOT EXISTS weekly_feedback (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  week_number INT NOT NULL,
  week_start_date DATE NOT NULL,

  -- User observations (input metrics)
  weight_start_kg NUMERIC(5,2) NOT NULL,
  weight_end_kg NUMERIC(5,2) NOT NULL,
  adherence_percent INT NOT NULL CHECK (adherence_percent >= 0 AND adherence_percent <= 100),
  hunger_level TEXT NOT NULL CHECK (hunger_level IN ('low', 'medium', 'high')),
  energy_level TEXT NOT NULL CHECK (energy_level IN ('low', 'medium', 'high')),
  sleep_quality TEXT NOT NULL CHECK (sleep_quality IN ('poor', 'fair', 'good', 'excellent')),
  cravings TEXT[] DEFAULT ARRAY[]::TEXT[],
  subjective_notes TEXT,

  -- Analysis results (computed)
  weight_change_kg NUMERIC(5,2) GENERATED ALWAYS AS (weight_end_kg - weight_start_kg) STORED,
  weight_change_percent NUMERIC(5,3) GENERATED ALWAYS AS ((weight_end_kg - weight_start_kg) / weight_start_kg * 100) STORED,

  -- Detected patterns (JSON)
  detected_patterns JSONB DEFAULT '{}'::JSONB,
  -- Example: {"energy_stable": true, "hunger_managed": true, "friday_energy_drop": true}

  -- Suggested adjustments
  adjustments_suggested JSONB DEFAULT '{}'::JSONB,
  -- Example: {"calories": 0, "protein_g": 20, "carbs_g": 30, "fat_g": 0}

  adjustment_rationale TEXT[],
  adjustment_sources JSONB DEFAULT '{}'::JSONB,
  -- Example: {"issn_protein": "ISSN Position Stand (2017)", "metabolic_adaptation": "Helms et al."}

  -- Adjustments applied
  adjustments_applied BOOLEAN DEFAULT FALSE,
  user_accepted BOOLEAN,

  -- Outcome tracking (from next week's data)
  adjustment_effectiveness TEXT CHECK (adjustment_effectiveness IN ('effective', 'neutral', 'ineffective', NULL)),

  -- Metadata
  feedback_quality TEXT CHECK (feedback_quality IN ('incomplete', 'adequate', 'comprehensive')),
  agent_confidence_percent INT DEFAULT 50 CHECK (agent_confidence_percent >= 0 AND agent_confidence_percent <= 100),
  red_flags JSONB DEFAULT '{}'::JSONB,
  -- Example: {"rapid_weight_loss": false, "extreme_hunger": false, "energy_crash": false}

  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_weekly_feedback_week_start ON weekly_feedback(week_start_date);
CREATE INDEX idx_weekly_feedback_week_number ON weekly_feedback(week_number);
