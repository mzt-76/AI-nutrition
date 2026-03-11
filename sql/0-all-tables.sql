-- ==============================================================================
-- AI Nutrition Assistant — Complete Database Schema
-- ==============================================================================
-- This file recreates the entire public schema for a fresh Supabase project.
-- Run it once in the SQL Editor of a new project. It is idempotent: safe
-- cleanup drops everything first, then rebuilds from scratch.
--
-- Tables: 17 | Functions: 8 | Triggers: 5 | RLS policies: 60+
-- ==============================================================================

-- =============================================================================
-- 1. EXTENSIONS
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS vector;      -- pgvector for RAG embeddings
CREATE EXTENSION IF NOT EXISTS pg_trgm;     -- trigram similarity for food search
CREATE EXTENSION IF NOT EXISTS unaccent;    -- accent-insensitive search (French)

-- =============================================================================
-- 2. SAFE CLEANUP
-- =============================================================================

DO $$
DECLARE
    rec RECORD;
BEGIN
    -- Drop ALL public RLS policies
    FOR rec IN
        SELECT schemaname, tablename, policyname
        FROM pg_policies
        WHERE schemaname = 'public'
    LOOP
        EXECUTE format('DROP POLICY IF EXISTS %I ON %I.%I',
                      rec.policyname, rec.schemaname, rec.tablename);
    END LOOP;

    -- Drop public triggers
    FOR rec IN
        SELECT t.tgname, c.relname
        FROM pg_trigger t
        JOIN pg_class c ON t.tgrelid = c.oid
        JOIN pg_namespace n ON c.relnamespace = n.oid
        WHERE n.nspname = 'public'
        AND NOT t.tgisinternal
    LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS %I ON %I', rec.tgname, rec.relname);
    END LOOP;

    -- Drop auth schema trigger
    BEGIN
        DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
    EXCEPTION
        WHEN undefined_table THEN NULL;
        WHEN undefined_object THEN NULL;
    END;
END $$;

-- Drop functions
DROP FUNCTION IF EXISTS public.handle_new_user();
DROP FUNCTION IF EXISTS public.is_admin();
DROP FUNCTION IF EXISTS public.match_documents(vector, int, jsonb);
DROP FUNCTION IF EXISTS public.execute_custom_sql(text);
DROP FUNCTION IF EXISTS public.search_openfoodfacts(text, int);
DROP FUNCTION IF EXISTS public.increment_recipe_usage(uuid);
DROP FUNCTION IF EXISTS public.update_ingredient_mapping_updated_at();
DROP FUNCTION IF EXISTS public.update_off_search_vector();
DROP FUNCTION IF EXISTS public.update_rag_pipeline_state_updated_at();

-- Drop tables (reverse dependency order)
DROP TABLE IF EXISTS shopping_lists CASCADE;
DROP TABLE IF EXISTS favorite_recipes CASCADE;
DROP TABLE IF EXISTS daily_food_log CASCADE;
DROP TABLE IF EXISTS user_learning_profile CASCADE;
DROP TABLE IF EXISTS weekly_feedback CASCADE;
DROP TABLE IF EXISTS meal_plans CASCADE;
DROP TABLE IF EXISTS ingredient_mapping CASCADE;
DROP TABLE IF EXISTS openfoodfacts_products CASCADE;
DROP TABLE IF EXISTS recipes CASCADE;
DROP TABLE IF EXISTS document_rows CASCADE;
DROP TABLE IF EXISTS document_metadata CASCADE;
DROP TABLE IF EXISTS documents CASCADE;
DROP TABLE IF EXISTS messages CASCADE;
DROP TABLE IF EXISTS conversations CASCADE;
DROP TABLE IF EXISTS requests CASCADE;
DROP TABLE IF EXISTS user_profiles CASCADE;
DROP TABLE IF EXISTS rag_pipeline_state CASCADE;

-- =============================================================================
-- 3. CREATE TABLES
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 3.1  user_profiles — nutrition profile for each authenticated user
-- -----------------------------------------------------------------------------
CREATE TABLE user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    full_name TEXT,
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Nutrition profile
    age INTEGER,
    gender TEXT,                           -- 'homme', 'femme'
    weight_kg NUMERIC,
    height_cm INTEGER,
    activity_level TEXT,                   -- 'sedentaire', 'leger', 'modere', 'actif', 'tres_actif'
    goals JSONB,                           -- {"type": "perte_de_poids", "target_weight_kg": 80}
    allergies TEXT[],                       -- ['lactose', 'gluten']
    diet_type TEXT,                         -- 'omnivore', 'vegetarien', 'vegan'
    disliked_foods TEXT[],
    favorite_foods TEXT[],
    preferred_cuisines TEXT[],
    max_prep_time INTEGER DEFAULT 45,

    -- Calculated targets (set by nutrition-calculating skill)
    bmr NUMERIC,
    tdee NUMERIC,
    target_calories NUMERIC,
    target_protein_g NUMERIC,
    target_carbs_g NUMERIC,
    target_fat_g NUMERIC
);

-- -----------------------------------------------------------------------------
-- 3.2  requests — immutable log of user queries
-- -----------------------------------------------------------------------------
CREATE TABLE requests (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    user_query TEXT NOT NULL
);

-- -----------------------------------------------------------------------------
-- 3.3  conversations
-- -----------------------------------------------------------------------------
CREATE TABLE conversations (
    session_id VARCHAR PRIMARY KEY NOT NULL,
    user_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    title VARCHAR,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_message_at TIMESTAMPTZ DEFAULT NOW(),
    is_archived BOOLEAN DEFAULT FALSE,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- -----------------------------------------------------------------------------
-- 3.4  messages
-- -----------------------------------------------------------------------------
CREATE TABLE messages (
    id INT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    computed_session_user_id UUID GENERATED ALWAYS AS (
        CAST(SPLIT_PART(session_id, '~', 1) AS UUID)
    ) STORED,
    session_id VARCHAR NOT NULL REFERENCES conversations(session_id),
    message JSONB NOT NULL,
    message_data TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- 3.5  recipes — pre-validated recipes with macros from OpenFoodFacts
-- -----------------------------------------------------------------------------
CREATE TABLE recipes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identification
    name TEXT NOT NULL,
    name_normalized TEXT NOT NULL,
    description TEXT,

    -- Classification
    meal_type TEXT NOT NULL,                 -- 'petit-dejeuner', 'dejeuner', 'diner', 'collation'
    cuisine_type TEXT DEFAULT 'française',
    diet_type TEXT DEFAULT 'omnivore',
    tags TEXT[] DEFAULT '{}',

    -- Recipe content
    ingredients JSONB NOT NULL,
    instructions TEXT NOT NULL,
    prep_time_minutes INTEGER DEFAULT 30,

    -- Pre-calculated nutrition (per 1 serving)
    calories_per_serving NUMERIC(7,2) NOT NULL,
    protein_g_per_serving NUMERIC(6,2) NOT NULL,
    carbs_g_per_serving NUMERIC(6,2) NOT NULL,
    fat_g_per_serving NUMERIC(6,2) NOT NULL,

    -- Allergen safety
    allergen_tags TEXT[] DEFAULT '{}',

    -- Quality & usage
    source TEXT DEFAULT 'llm_generated',
    off_validated BOOLEAN DEFAULT FALSE,
    usage_count INTEGER DEFAULT 0,
    rating NUMERIC(2,1) DEFAULT 0.0,
    last_used_date TIMESTAMPTZ,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- 3.6  openfoodfacts_products — local copy of OFF products (French)
-- -----------------------------------------------------------------------------
CREATE TABLE openfoodfacts_products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code TEXT UNIQUE NOT NULL,
    product_name TEXT NOT NULL,
    product_name_fr TEXT,
    countries_tags TEXT[],

    -- Nutrition per 100g
    calories_per_100g NUMERIC(7,2) NOT NULL,
    protein_g_per_100g NUMERIC(6,2) NOT NULL,
    carbs_g_per_100g NUMERIC(6,2) NOT NULL,
    fat_g_per_100g NUMERIC(6,2) NOT NULL,

    -- Full-text search vector (auto-populated by trigger)
    search_vector tsvector,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- 3.7  ingredient_mapping — ingredient -> OFF product cache
-- -----------------------------------------------------------------------------
CREATE TABLE ingredient_mapping (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ingredient_name TEXT NOT NULL UNIQUE,
    ingredient_name_normalized TEXT NOT NULL,

    -- OpenFoodFacts mapping
    openfoodfacts_code TEXT NOT NULL,
    openfoodfacts_name TEXT NOT NULL,

    -- Nutrition per 100g
    calories_per_100g NUMERIC(7,2) NOT NULL,
    protein_g_per_100g NUMERIC(6,2) NOT NULL,
    carbs_g_per_100g NUMERIC(6,2) NOT NULL,
    fat_g_per_100g NUMERIC(6,2) NOT NULL,

    -- Quality metrics
    confidence_score NUMERIC(3,2) NOT NULL DEFAULT 0.0
        CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),
    verified BOOLEAN NOT NULL DEFAULT FALSE,
    usage_count INTEGER NOT NULL DEFAULT 1,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- 3.8  meal_plans
-- -----------------------------------------------------------------------------
CREATE TABLE meal_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES user_profiles(id) ON DELETE CASCADE,
    week_start DATE,
    plan_data JSONB,
    target_calories_daily NUMERIC,
    target_protein_g NUMERIC,
    target_carbs_g NUMERIC,
    target_fat_g NUMERIC,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- 3.9  weekly_feedback — weekly check-in data + body tracking
-- -----------------------------------------------------------------------------
CREATE TABLE weekly_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES user_profiles(id) ON DELETE CASCADE,
    week_number INT NOT NULL,
    week_start_date DATE NOT NULL,

    -- User observations
    weight_start_kg NUMERIC(5,2) NOT NULL,
    weight_end_kg NUMERIC(5,2) NOT NULL,
    adherence_percent INT NOT NULL CHECK (adherence_percent >= 0 AND adherence_percent <= 100),
    hunger_level TEXT NOT NULL CHECK (hunger_level IN ('low', 'medium', 'high')),
    energy_level TEXT NOT NULL CHECK (energy_level IN ('low', 'medium', 'high')),
    sleep_quality TEXT NOT NULL CHECK (sleep_quality IN ('poor', 'fair', 'good', 'excellent')),
    cravings TEXT[] DEFAULT ARRAY[]::TEXT[],
    subjective_notes TEXT,

    -- Computed columns
    weight_change_kg NUMERIC(5,2) GENERATED ALWAYS AS (weight_end_kg - weight_start_kg) STORED,
    weight_change_percent NUMERIC(5,3) GENERATED ALWAYS AS (
        (weight_end_kg - weight_start_kg) / weight_start_kg * 100
    ) STORED,

    -- Analysis results
    detected_patterns JSONB DEFAULT '{}'::JSONB,
    adjustments_suggested JSONB DEFAULT '{}'::JSONB,
    adjustment_rationale TEXT[],
    adjustment_sources JSONB DEFAULT '{}'::JSONB,
    adjustments_applied BOOLEAN DEFAULT FALSE,
    user_accepted BOOLEAN,
    adjustment_effectiveness TEXT CHECK (adjustment_effectiveness IN ('effective', 'neutral', 'ineffective', NULL)),

    -- Metadata
    feedback_quality TEXT CHECK (feedback_quality IN ('incomplete', 'adequate', 'comprehensive')),
    agent_confidence_percent INT DEFAULT 50 CHECK (agent_confidence_percent >= 0 AND agent_confidence_percent <= 100),
    red_flags JSONB DEFAULT '{}'::JSONB,

    -- Body composition (optional)
    body_fat_percent NUMERIC(4,1),
    muscle_mass_kg NUMERIC(5,2),
    water_percent NUMERIC(4,1),

    -- Body measurements (optional)
    waist_cm NUMERIC(5,1),
    hips_cm NUMERIC(5,1),
    chest_cm NUMERIC(5,1),
    arm_cm NUMERIC(5,1),
    thigh_cm NUMERIC(5,1),

    -- Measurement context
    measurement_method TEXT,               -- 'smart_scale', 'manual', 'image_analysis', 'calipers'
    photo_refs JSONB,                      -- {"front": "path/front.jpg", "side": "path/side.jpg"}

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- 3.10 user_learning_profile — personalization factors learned over time
-- -----------------------------------------------------------------------------
CREATE TABLE user_learning_profile (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID UNIQUE REFERENCES user_profiles(id) ON DELETE CASCADE,

    -- Sensitivity factors
    protein_sensitivity_g_per_kg NUMERIC(3,2),
    carb_sensitivity TEXT CHECK (carb_sensitivity IN ('low', 'medium', 'high', NULL)),
    fat_sensitivity TEXT CHECK (fat_sensitivity IN ('low', 'medium', 'high', NULL)),

    -- Macro distribution preference
    preferred_macro_distribution JSONB DEFAULT '{}'::JSONB,
    adherence_triggers JSONB DEFAULT '{}'::JSONB,
    meal_preferences JSONB DEFAULT '{}'::JSONB,
    energy_patterns JSONB DEFAULT '{}'::JSONB,

    -- Energy & metabolism
    calculated_tdee NUMERIC(4,0),
    observed_tdee NUMERIC(4,0),
    metabolic_adaptation_detected BOOLEAN DEFAULT FALSE,
    metabolic_adaptation_factor NUMERIC(3,2),

    -- Learning confidence
    weeks_of_data INT DEFAULT 0,
    confidence_level NUMERIC(3,2) DEFAULT 0.0,

    -- Psychological patterns
    stress_response JSONB DEFAULT '{}'::JSONB,
    motivation_pattern TEXT CHECK (motivation_pattern IN ('consistent', 'cycles', 'declining', NULL)),
    motivation_notes TEXT,
    red_flags_history JSONB DEFAULT '{}'::JSONB,

    updated_at TIMESTAMP DEFAULT NOW(),
    next_review_week_number INT
);

-- -----------------------------------------------------------------------------
-- 3.11 daily_food_log — per-meal food tracking
-- -----------------------------------------------------------------------------
CREATE TABLE daily_food_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    log_date DATE NOT NULL DEFAULT CURRENT_DATE,
    meal_type TEXT NOT NULL,               -- 'petit-dejeuner', 'dejeuner', 'diner', 'collation'
    food_name TEXT NOT NULL,
    quantity NUMERIC DEFAULT 1,
    unit TEXT DEFAULT 'portion',
    calories NUMERIC NOT NULL DEFAULT 0,
    protein_g NUMERIC NOT NULL DEFAULT 0,
    carbs_g NUMERIC NOT NULL DEFAULT 0,
    fat_g NUMERIC NOT NULL DEFAULT 0,
    source TEXT DEFAULT 'openfoodfacts',   -- 'openfoodfacts', 'manual', 'meal_plan'
    meal_plan_id UUID REFERENCES meal_plans(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- 3.12 favorite_recipes
-- -----------------------------------------------------------------------------
CREATE TABLE favorite_recipes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    recipe_id UUID NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, recipe_id)
);

-- -----------------------------------------------------------------------------
-- 3.13 shopping_lists
-- -----------------------------------------------------------------------------
CREATE TABLE shopping_lists (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    meal_plan_id UUID REFERENCES meal_plans(id),
    title TEXT NOT NULL DEFAULT 'Liste de courses',
    items JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- 3.14 documents — RAG vector embeddings
-- -----------------------------------------------------------------------------
CREATE TABLE documents (
    id BIGSERIAL PRIMARY KEY,
    content TEXT,
    metadata JSONB,
    embedding vector(1536)
);

-- -----------------------------------------------------------------------------
-- 3.15 document_metadata — RAG document metadata
-- -----------------------------------------------------------------------------
CREATE TABLE document_metadata (
    id TEXT PRIMARY KEY,
    title TEXT,
    url TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    schema TEXT
);

-- -----------------------------------------------------------------------------
-- 3.16 document_rows — RAG document rows
-- -----------------------------------------------------------------------------
CREATE TABLE document_rows (
    id SERIAL PRIMARY KEY,
    dataset_id TEXT REFERENCES document_metadata(id),
    row_data JSONB
);

-- -----------------------------------------------------------------------------
-- 3.17 rag_pipeline_state — RAG sync state tracking
-- -----------------------------------------------------------------------------
CREATE TABLE rag_pipeline_state (
    pipeline_id TEXT PRIMARY KEY,
    pipeline_type TEXT NOT NULL,
    last_check_time TIMESTAMP,
    known_files JSONB,
    last_run TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- 4. CREATE INDEXES
-- =============================================================================

-- Conversations & messages
CREATE INDEX idx_conversations_user ON conversations(user_id);
CREATE INDEX idx_messages_session ON messages(session_id);
CREATE INDEX idx_messages_computed_session ON messages(computed_session_user_id);

-- Recipes
CREATE INDEX idx_recipes_meal_type ON recipes(meal_type);
CREATE INDEX idx_recipes_diet_type ON recipes(diet_type);
CREATE INDEX idx_recipes_allergen_tags ON recipes USING GIN(allergen_tags);
CREATE INDEX idx_recipes_tags ON recipes USING GIN(tags);
CREATE INDEX idx_recipes_name_normalized ON recipes(name_normalized);
CREATE INDEX idx_recipes_calories ON recipes(calories_per_serving);
CREATE INDEX idx_recipes_protein ON recipes(protein_g_per_serving);

-- OpenFoodFacts
CREATE INDEX idx_off_search ON openfoodfacts_products USING GIN(search_vector);
CREATE INDEX idx_off_countries ON openfoodfacts_products USING GIN(countries_tags);
CREATE INDEX idx_off_code ON openfoodfacts_products(code);
CREATE INDEX idx_off_product_name_trgm ON openfoodfacts_products USING GIN(product_name gin_trgm_ops);
CREATE INDEX idx_off_product_name_fr_trgm ON openfoodfacts_products USING GIN(product_name_fr gin_trgm_ops);

-- Ingredient mapping
CREATE INDEX idx_ingredient_name ON ingredient_mapping(ingredient_name);
CREATE INDEX idx_ingredient_normalized ON ingredient_mapping(ingredient_name_normalized);
CREATE INDEX idx_verified ON ingredient_mapping(verified) WHERE verified = TRUE;
CREATE INDEX idx_usage_count ON ingredient_mapping(usage_count DESC);

-- Meal plans
CREATE INDEX idx_meal_plans_user_id ON meal_plans(user_id);

-- Weekly feedback
CREATE INDEX idx_weekly_feedback_week_start ON weekly_feedback(week_start_date);
CREATE INDEX idx_weekly_feedback_week_number ON weekly_feedback(week_number);
CREATE INDEX idx_weekly_feedback_user_id ON weekly_feedback(user_id);
CREATE UNIQUE INDEX idx_weekly_feedback_baseline_per_user
    ON weekly_feedback(user_id) WHERE week_number = 0;

-- User learning profile
CREATE UNIQUE INDEX idx_learning_profile_user_id ON user_learning_profile(user_id);

-- Daily food log
CREATE INDEX idx_daily_food_log_user_id ON daily_food_log(user_id);
CREATE INDEX idx_daily_food_log_date ON daily_food_log(log_date);

-- RAG pipeline state
CREATE INDEX idx_rag_pipeline_state_pipeline_type ON rag_pipeline_state(pipeline_type);
CREATE INDEX idx_rag_pipeline_state_last_run ON rag_pipeline_state(last_run);

-- =============================================================================
-- 5. CREATE FUNCTIONS
-- =============================================================================

-- 5.1 handle_new_user — auto-create user_profiles row on signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    INSERT INTO public.user_profiles (id, email)
    VALUES (new.id, new.email);
    RETURN new;
END;
$$;

-- 5.2 is_admin — helper for RLS policies
CREATE OR REPLACE FUNCTION public.is_admin()
RETURNS BOOLEAN
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

-- 5.3 match_documents — vector similarity search for RAG
CREATE OR REPLACE FUNCTION public.match_documents(
    query_embedding vector(1536),
    match_count int DEFAULT NULL,
    filter jsonb DEFAULT '{}'
)
RETURNS TABLE (
    id bigint,
    content text,
    metadata jsonb,
    similarity float
)
LANGUAGE plpgsql
SET search_path = public
AS $$
#variable_conflict use_column
BEGIN
    RETURN QUERY
    SELECT
        id,
        content,
        metadata,
        1 - (documents.embedding <=> query_embedding) AS similarity
    FROM documents
    WHERE metadata @> filter
    ORDER BY documents.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- 5.4 execute_custom_sql — admin-only SQL execution
CREATE OR REPLACE FUNCTION public.execute_custom_sql(sql_query text)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    result JSONB;
BEGIN
    EXECUTE 'SELECT jsonb_agg(t) FROM (' || sql_query || ') t' INTO result;
    RETURN COALESCE(result, '[]'::jsonb);
EXCEPTION
    WHEN OTHERS THEN
        RETURN jsonb_build_object(
            'error', SQLERRM,
            'detail', SQLSTATE
        );
END;
$$;

-- 5.5 search_openfoodfacts — full-text + trigram search
CREATE OR REPLACE FUNCTION public.search_openfoodfacts(
    search_query TEXT,
    max_results INT DEFAULT 5
)
RETURNS TABLE (
    code TEXT,
    product_name TEXT,
    product_name_fr TEXT,
    calories_per_100g NUMERIC,
    protein_g_per_100g NUMERIC,
    carbs_g_per_100g NUMERIC,
    fat_g_per_100g NUMERIC,
    similarity_score FLOAT
)
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
    RETURN QUERY
    SELECT
        p.code,
        p.product_name,
        p.product_name_fr,
        p.calories_per_100g,
        p.protein_g_per_100g,
        p.carbs_g_per_100g,
        p.fat_g_per_100g,
        GREATEST(
            similarity(unaccent(search_query), unaccent(p.product_name)),
            similarity(unaccent(search_query), unaccent(COALESCE(p.product_name_fr, '')))
        )::FLOAT AS similarity_score
    FROM openfoodfacts_products p
    WHERE
        (p.search_vector @@ plainto_tsquery('french', search_query)
         OR similarity(unaccent(search_query), unaccent(p.product_name)) > 0.3
         OR similarity(unaccent(search_query), unaccent(COALESCE(p.product_name_fr, ''))) > 0.3)
        AND 'en:france' = ANY(p.countries_tags)
    ORDER BY similarity_score DESC
    LIMIT max_results;
END;
$$;

-- 5.6 increment_recipe_usage — atomic usage counter update
CREATE OR REPLACE FUNCTION public.increment_recipe_usage(p_recipe_id uuid)
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

-- 5.7 update_ingredient_mapping_updated_at — generic updated_at trigger function
CREATE OR REPLACE FUNCTION public.update_ingredient_mapping_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

-- 5.8 update_off_search_vector — tsvector trigger for OFF products
CREATE OR REPLACE FUNCTION public.update_off_search_vector()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('pg_catalog.french', COALESCE(NEW.product_name_fr, '')), 'A') ||
        setweight(to_tsvector('pg_catalog.french', COALESCE(NEW.product_name, '')), 'B');
    RETURN NEW;
END;
$$;

-- 5.9 update_rag_pipeline_state_updated_at
CREATE OR REPLACE FUNCTION public.update_rag_pipeline_state_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

-- =============================================================================
-- 6. CREATE TRIGGERS
-- =============================================================================

-- 6.1 Auto-create user profile on signup
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- 6.2 Updated_at on ingredient_mapping
CREATE TRIGGER trigger_update_ingredient_mapping_timestamp
    BEFORE UPDATE ON ingredient_mapping
    FOR EACH ROW EXECUTE FUNCTION update_ingredient_mapping_updated_at();

-- 6.3 Updated_at on recipes (reuses same function)
CREATE TRIGGER trigger_update_recipes_timestamp
    BEFORE UPDATE ON recipes
    FOR EACH ROW EXECUTE FUNCTION update_ingredient_mapping_updated_at();

-- 6.4 tsvector auto-update on openfoodfacts_products
CREATE TRIGGER tsvector_update_off
    BEFORE INSERT OR UPDATE ON openfoodfacts_products
    FOR EACH ROW EXECUTE FUNCTION update_off_search_vector();

-- 6.5 Updated_at on rag_pipeline_state
CREATE TRIGGER update_rag_pipeline_state_updated_at
    BEFORE UPDATE ON rag_pipeline_state
    FOR EACH ROW EXECUTE FUNCTION update_rag_pipeline_state_updated_at();

-- =============================================================================
-- 7. ENABLE ROW LEVEL SECURITY
-- =============================================================================

ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE recipes ENABLE ROW LEVEL SECURITY;
ALTER TABLE openfoodfacts_products ENABLE ROW LEVEL SECURITY;
ALTER TABLE ingredient_mapping ENABLE ROW LEVEL SECURITY;
ALTER TABLE meal_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE weekly_feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_learning_profile ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_food_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE favorite_recipes ENABLE ROW LEVEL SECURITY;
ALTER TABLE shopping_lists ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_metadata ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_rows ENABLE ROW LEVEL SECURITY;
ALTER TABLE rag_pipeline_state ENABLE ROW LEVEL SECURITY;

-- =============================================================================
-- 8. CREATE RLS POLICIES
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 8.1  user_profiles
-- ---------------------------------------------------------------------------
CREATE POLICY "Users can view their own profile"
    ON user_profiles FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can update their own profile"
    ON user_profiles FOR UPDATE
    USING (auth.uid() = id)
    WITH CHECK (auth.uid() = id AND is_admin IS NOT DISTINCT FROM FALSE);

CREATE POLICY "Only admins can change admin status"
    ON user_profiles FOR UPDATE TO authenticated
    USING (is_admin()) WITH CHECK (is_admin());

CREATE POLICY "Admins can view all profiles"
    ON user_profiles FOR SELECT USING (is_admin());

CREATE POLICY "Admins can update all profiles"
    ON user_profiles FOR UPDATE USING (is_admin());

CREATE POLICY "Deny delete for user_profiles"
    ON user_profiles FOR DELETE USING (false);

-- ---------------------------------------------------------------------------
-- 8.2  requests (immutable log)
-- ---------------------------------------------------------------------------
CREATE POLICY "Users can view their own requests"
    ON requests FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own requests"
    ON requests FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Deny update for requests"
    ON requests FOR UPDATE USING (false);

CREATE POLICY "Deny delete for requests"
    ON requests FOR DELETE USING (false);

CREATE POLICY "Admins can view all requests"
    ON requests FOR SELECT USING (is_admin());

-- ---------------------------------------------------------------------------
-- 8.3  conversations
-- ---------------------------------------------------------------------------
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

-- ---------------------------------------------------------------------------
-- 8.4  messages (ownership via conversations join)
-- ---------------------------------------------------------------------------
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

-- ---------------------------------------------------------------------------
-- 8.5  meal_plans
-- ---------------------------------------------------------------------------
CREATE POLICY "Users can view their own meal plans"
    ON meal_plans FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own meal plans"
    ON meal_plans FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own meal plans"
    ON meal_plans FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Admins can view all meal plans"
    ON meal_plans FOR SELECT USING (is_admin());

CREATE POLICY "Admins can insert meal plans"
    ON meal_plans FOR INSERT WITH CHECK (is_admin());

CREATE POLICY "Deny delete for meal_plans"
    ON meal_plans FOR DELETE USING (false);

-- ---------------------------------------------------------------------------
-- 8.6  weekly_feedback
-- ---------------------------------------------------------------------------
CREATE POLICY "Users can view their own weekly feedback"
    ON weekly_feedback FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own weekly feedback"
    ON weekly_feedback FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own weekly feedback"
    ON weekly_feedback FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Admins can view all weekly feedback"
    ON weekly_feedback FOR SELECT USING (is_admin());

CREATE POLICY "Admins can insert weekly feedback"
    ON weekly_feedback FOR INSERT WITH CHECK (is_admin());

CREATE POLICY "Deny delete for weekly_feedback"
    ON weekly_feedback FOR DELETE USING (false);

-- ---------------------------------------------------------------------------
-- 8.7  user_learning_profile
-- ---------------------------------------------------------------------------
CREATE POLICY "Users can view their own learning profile"
    ON user_learning_profile FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own learning profile"
    ON user_learning_profile FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own learning profile"
    ON user_learning_profile FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Admins can view all learning profiles"
    ON user_learning_profile FOR SELECT USING (is_admin());

CREATE POLICY "Deny delete for user_learning_profile"
    ON user_learning_profile FOR DELETE USING (false);

-- ---------------------------------------------------------------------------
-- 8.8  daily_food_log (users can delete their own entries)
-- ---------------------------------------------------------------------------
CREATE POLICY "Users can view their own food log"
    ON daily_food_log FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own food log"
    ON daily_food_log FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own food log"
    ON daily_food_log FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own food log"
    ON daily_food_log FOR DELETE USING (auth.uid() = user_id);

CREATE POLICY "Admins can view all food logs"
    ON daily_food_log FOR SELECT USING (is_admin());

-- ---------------------------------------------------------------------------
-- 8.9  favorite_recipes (users can delete their own)
-- ---------------------------------------------------------------------------
CREATE POLICY "Users can view their own favorites"
    ON favorite_recipes FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own favorites"
    ON favorite_recipes FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own favorites"
    ON favorite_recipes FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own favorites"
    ON favorite_recipes FOR DELETE USING (auth.uid() = user_id);

CREATE POLICY "Admins can view all favorites"
    ON favorite_recipes FOR SELECT USING (is_admin());

-- ---------------------------------------------------------------------------
-- 8.10 shopping_lists (users can delete their own)
-- ---------------------------------------------------------------------------
CREATE POLICY "Users can view their own shopping lists"
    ON shopping_lists FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own shopping lists"
    ON shopping_lists FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own shopping lists"
    ON shopping_lists FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own shopping lists"
    ON shopping_lists FOR DELETE USING (auth.uid() = user_id);

CREATE POLICY "Admins can view all shopping lists"
    ON shopping_lists FOR SELECT USING (is_admin());

-- ---------------------------------------------------------------------------
-- 8.11 recipes (global reference — authenticated read, admin write)
-- ---------------------------------------------------------------------------
CREATE POLICY "Authenticated users can read recipes"
    ON recipes FOR SELECT TO authenticated USING (true);

CREATE POLICY "Admins can insert recipes"
    ON recipes FOR INSERT WITH CHECK (is_admin());

CREATE POLICY "Admins can update recipes"
    ON recipes FOR UPDATE USING (is_admin());

CREATE POLICY "Deny delete for recipes"
    ON recipes FOR DELETE USING (false);

-- ---------------------------------------------------------------------------
-- 8.12 ingredient_mapping (global reference)
-- ---------------------------------------------------------------------------
CREATE POLICY "Authenticated users can read ingredient mapping"
    ON ingredient_mapping FOR SELECT TO authenticated USING (true);

CREATE POLICY "Admins can insert ingredient mapping"
    ON ingredient_mapping FOR INSERT WITH CHECK (is_admin());

CREATE POLICY "Admins can update ingredient mapping"
    ON ingredient_mapping FOR UPDATE USING (is_admin());

CREATE POLICY "Deny delete for ingredient_mapping"
    ON ingredient_mapping FOR DELETE USING (false);

-- ---------------------------------------------------------------------------
-- 8.13 openfoodfacts_products (global reference)
-- ---------------------------------------------------------------------------
CREATE POLICY "Authenticated users can read openfoodfacts products"
    ON openfoodfacts_products FOR SELECT TO authenticated USING (true);

CREATE POLICY "Admins can insert openfoodfacts products"
    ON openfoodfacts_products FOR INSERT WITH CHECK (is_admin());

CREATE POLICY "Admins can update openfoodfacts products"
    ON openfoodfacts_products FOR UPDATE USING (is_admin());

CREATE POLICY "Deny delete for openfoodfacts_products"
    ON openfoodfacts_products FOR DELETE USING (false);

-- ---------------------------------------------------------------------------
-- 8.14 documents (RAG — authenticated read, admin manage)
-- ---------------------------------------------------------------------------
CREATE POLICY "Authenticated can read documents"
    ON documents FOR SELECT TO authenticated USING (true);

CREATE POLICY "Admins can manage documents"
    ON documents FOR ALL USING (is_admin());

-- ---------------------------------------------------------------------------
-- 8.15 document_metadata (RAG)
-- ---------------------------------------------------------------------------
CREATE POLICY "Authenticated can read document_metadata"
    ON document_metadata FOR SELECT TO authenticated USING (true);

CREATE POLICY "Admins can manage document_metadata"
    ON document_metadata FOR ALL USING (is_admin());

-- ---------------------------------------------------------------------------
-- 8.16 document_rows (RAG)
-- ---------------------------------------------------------------------------
CREATE POLICY "Authenticated can read document_rows"
    ON document_rows FOR SELECT TO authenticated USING (true);

CREATE POLICY "Admins can manage document_rows"
    ON document_rows FOR ALL USING (is_admin());

-- ---------------------------------------------------------------------------
-- 8.17 rag_pipeline_state (backend only — no user access)
-- ---------------------------------------------------------------------------
-- No policies = service_role only (RLS enabled but no grants)

-- =============================================================================
-- 9. REVOKE PERMISSIONS
-- =============================================================================

-- Prevent non-admin users from calling execute_custom_sql directly
REVOKE EXECUTE ON FUNCTION execute_custom_sql(text) FROM PUBLIC, authenticated;

-- =============================================================================
-- SETUP COMPLETE
-- =============================================================================
-- The database schema is now fully configured with:
--   17 tables with proper foreign key relationships
--   35+ indexes for query performance
--   9 functions (auth, search, admin, triggers)
--   5 triggers (user creation, updated_at, tsvector)
--   RLS enabled on all 17 tables with 60+ policies
--   Secure function permissions
--
-- Next steps:
--   1. Configure application environment variables
--   2. Import recipe data (scripts/seed_recipes.py)
--   3. Import OpenFoodFacts data (python -m src.nutrition.openfoodfacts_import)
--   4. Start the backend (uvicorn src.api:app --port 8001)
--   5. Start the frontend (cd frontend && npm run dev)
