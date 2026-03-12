export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "14.1"
  }
  public: {
    Tables: {
      conversations: {
        Row: {
          created_at: string | null
          is_archived: boolean | null
          last_message_at: string | null
          metadata: Json | null
          session_id: string
          title: string | null
          user_id: string
        }
        Insert: {
          created_at?: string | null
          is_archived?: boolean | null
          last_message_at?: string | null
          metadata?: Json | null
          session_id: string
          title?: string | null
          user_id: string
        }
        Update: {
          created_at?: string | null
          is_archived?: boolean | null
          last_message_at?: string | null
          metadata?: Json | null
          session_id?: string
          title?: string | null
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "conversations_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "user_profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      daily_food_log: {
        Row: {
          calories: number
          carbs_g: number
          created_at: string | null
          fat_g: number
          food_name: string
          id: string
          log_date: string
          meal_plan_id: string | null
          meal_type: string
          protein_g: number
          quantity: number | null
          source: string | null
          unit: string | null
          updated_at: string | null
          user_id: string
        }
        Insert: {
          calories?: number
          carbs_g?: number
          created_at?: string | null
          fat_g?: number
          food_name: string
          id?: string
          log_date?: string
          meal_plan_id?: string | null
          meal_type: string
          protein_g?: number
          quantity?: number | null
          source?: string | null
          unit?: string | null
          updated_at?: string | null
          user_id: string
        }
        Update: {
          calories?: number
          carbs_g?: number
          created_at?: string | null
          fat_g?: number
          food_name?: string
          id?: string
          log_date?: string
          meal_plan_id?: string | null
          meal_type?: string
          protein_g?: number
          quantity?: number | null
          source?: string | null
          unit?: string | null
          updated_at?: string | null
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "daily_food_log_meal_plan_id_fkey"
            columns: ["meal_plan_id"]
            isOneToOne: false
            referencedRelation: "meal_plans"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "daily_food_log_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "user_profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      document_metadata: {
        Row: {
          created_at: string | null
          id: string
          schema: string | null
          title: string | null
          url: string | null
        }
        Insert: {
          created_at?: string | null
          id: string
          schema?: string | null
          title?: string | null
          url?: string | null
        }
        Update: {
          created_at?: string | null
          id?: string
          schema?: string | null
          title?: string | null
          url?: string | null
        }
        Relationships: []
      }
      document_rows: {
        Row: {
          dataset_id: string | null
          id: number
          row_data: Json | null
        }
        Insert: {
          dataset_id?: string | null
          id?: number
          row_data?: Json | null
        }
        Update: {
          dataset_id?: string | null
          id?: number
          row_data?: Json | null
        }
        Relationships: [
          {
            foreignKeyName: "document_rows_dataset_id_fkey"
            columns: ["dataset_id"]
            isOneToOne: false
            referencedRelation: "document_metadata"
            referencedColumns: ["id"]
          },
        ]
      }
      documents: {
        Row: {
          content: string | null
          embedding: string | null
          id: number
          metadata: Json | null
        }
        Insert: {
          content?: string | null
          embedding?: string | null
          id?: number
          metadata?: Json | null
        }
        Update: {
          content?: string | null
          embedding?: string | null
          id?: number
          metadata?: Json | null
        }
        Relationships: []
      }
      favorite_recipes: {
        Row: {
          created_at: string | null
          id: string
          notes: string | null
          recipe_id: string
          user_id: string
        }
        Insert: {
          created_at?: string | null
          id?: string
          notes?: string | null
          recipe_id: string
          user_id: string
        }
        Update: {
          created_at?: string | null
          id?: string
          notes?: string | null
          recipe_id?: string
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "favorite_recipes_recipe_id_fkey"
            columns: ["recipe_id"]
            isOneToOne: false
            referencedRelation: "recipes"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "favorite_recipes_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "user_profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      ingredient_mapping: {
        Row: {
          calories_per_100g: number
          carbs_g_per_100g: number
          confidence_score: number
          created_at: string
          fat_g_per_100g: number
          id: string
          ingredient_name: string
          ingredient_name_normalized: string
          openfoodfacts_code: string
          openfoodfacts_name: string
          protein_g_per_100g: number
          updated_at: string
          usage_count: number
          verified: boolean
        }
        Insert: {
          calories_per_100g: number
          carbs_g_per_100g: number
          confidence_score?: number
          created_at?: string
          fat_g_per_100g: number
          id?: string
          ingredient_name: string
          ingredient_name_normalized: string
          openfoodfacts_code: string
          openfoodfacts_name: string
          protein_g_per_100g: number
          updated_at?: string
          usage_count?: number
          verified?: boolean
        }
        Update: {
          calories_per_100g?: number
          carbs_g_per_100g?: number
          confidence_score?: number
          created_at?: string
          fat_g_per_100g?: number
          id?: string
          ingredient_name?: string
          ingredient_name_normalized?: string
          openfoodfacts_code?: string
          openfoodfacts_name?: string
          protein_g_per_100g?: number
          updated_at?: string
          usage_count?: number
          verified?: boolean
        }
        Relationships: []
      }
      meal_plans: {
        Row: {
          created_at: string | null
          id: string
          notes: string | null
          plan_data: Json | null
          target_calories_daily: number | null
          target_carbs_g: number | null
          target_fat_g: number | null
          target_protein_g: number | null
          user_id: string
          week_start: string | null
        }
        Insert: {
          created_at?: string | null
          id?: string
          notes?: string | null
          plan_data?: Json | null
          target_calories_daily?: number | null
          target_carbs_g?: number | null
          target_fat_g?: number | null
          target_protein_g?: number | null
          user_id: string
          week_start?: string | null
        }
        Update: {
          created_at?: string | null
          id?: string
          notes?: string | null
          plan_data?: Json | null
          target_calories_daily?: number | null
          target_carbs_g?: number | null
          target_fat_g?: number | null
          target_protein_g?: number | null
          user_id?: string
          week_start?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "meal_plans_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "user_profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      messages: {
        Row: {
          computed_session_user_id: string | null
          created_at: string | null
          id: number
          message: Json
          message_data: string | null
          session_id: string
        }
        Insert: {
          computed_session_user_id?: string | null
          created_at?: string | null
          id?: never
          message: Json
          message_data?: string | null
          session_id: string
        }
        Update: {
          computed_session_user_id?: string | null
          created_at?: string | null
          id?: never
          message?: Json
          message_data?: string | null
          session_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "messages_session_id_fkey"
            columns: ["session_id"]
            isOneToOne: false
            referencedRelation: "conversations"
            referencedColumns: ["session_id"]
          },
        ]
      }
      openfoodfacts_products: {
        Row: {
          calories_per_100g: number
          carbs_g_per_100g: number
          code: string
          countries_tags: string[] | null
          created_at: string | null
          fat_g_per_100g: number
          id: string
          product_name: string
          product_name_fr: string | null
          protein_g_per_100g: number
          search_vector: unknown
        }
        Insert: {
          calories_per_100g: number
          carbs_g_per_100g: number
          code: string
          countries_tags?: string[] | null
          created_at?: string | null
          fat_g_per_100g: number
          id?: string
          product_name: string
          product_name_fr?: string | null
          protein_g_per_100g: number
          search_vector?: unknown
        }
        Update: {
          calories_per_100g?: number
          carbs_g_per_100g?: number
          code?: string
          countries_tags?: string[] | null
          created_at?: string | null
          fat_g_per_100g?: number
          id?: string
          product_name?: string
          product_name_fr?: string | null
          protein_g_per_100g?: number
          search_vector?: unknown
        }
        Relationships: []
      }
      rag_pipeline_state: {
        Row: {
          created_at: string | null
          known_files: Json | null
          last_check_time: string | null
          last_run: string | null
          pipeline_id: string
          pipeline_type: string
          updated_at: string | null
        }
        Insert: {
          created_at?: string | null
          known_files?: Json | null
          last_check_time?: string | null
          last_run?: string | null
          pipeline_id: string
          pipeline_type: string
          updated_at?: string | null
        }
        Update: {
          created_at?: string | null
          known_files?: Json | null
          last_check_time?: string | null
          last_run?: string | null
          pipeline_id?: string
          pipeline_type?: string
          updated_at?: string | null
        }
        Relationships: []
      }
      recipes: {
        Row: {
          allergen_tags: string[] | null
          calories_per_serving: number
          carbs_g_per_serving: number
          created_at: string | null
          cuisine_type: string | null
          description: string | null
          diet_type: string | null
          fat_g_per_serving: number
          id: string
          ingredients: Json
          instructions: string
          last_used_date: string | null
          meal_type: string
          name: string
          name_normalized: string
          off_validated: boolean | null
          prep_time_minutes: number | null
          protein_g_per_serving: number
          rating: number | null
          source: string | null
          tags: string[] | null
          updated_at: string | null
          usage_count: number | null
        }
        Insert: {
          allergen_tags?: string[] | null
          calories_per_serving: number
          carbs_g_per_serving: number
          created_at?: string | null
          cuisine_type?: string | null
          description?: string | null
          diet_type?: string | null
          fat_g_per_serving: number
          id?: string
          ingredients: Json
          instructions: string
          last_used_date?: string | null
          meal_type: string
          name: string
          name_normalized: string
          off_validated?: boolean | null
          prep_time_minutes?: number | null
          protein_g_per_serving: number
          rating?: number | null
          source?: string | null
          tags?: string[] | null
          updated_at?: string | null
          usage_count?: number | null
        }
        Update: {
          allergen_tags?: string[] | null
          calories_per_serving?: number
          carbs_g_per_serving?: number
          created_at?: string | null
          cuisine_type?: string | null
          description?: string | null
          diet_type?: string | null
          fat_g_per_serving?: number
          id?: string
          ingredients?: Json
          instructions?: string
          last_used_date?: string | null
          meal_type?: string
          name?: string
          name_normalized?: string
          off_validated?: boolean | null
          prep_time_minutes?: number | null
          protein_g_per_serving?: number
          rating?: number | null
          source?: string | null
          tags?: string[] | null
          updated_at?: string | null
          usage_count?: number | null
        }
        Relationships: []
      }
      requests: {
        Row: {
          id: string
          timestamp: string | null
          user_id: string
          user_query: string
        }
        Insert: {
          id: string
          timestamp?: string | null
          user_id: string
          user_query: string
        }
        Update: {
          id?: string
          timestamp?: string | null
          user_id?: string
          user_query?: string
        }
        Relationships: [
          {
            foreignKeyName: "requests_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "user_profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      shopping_lists: {
        Row: {
          created_at: string | null
          id: string
          items: Json
          meal_plan_id: string | null
          title: string
          updated_at: string | null
          user_id: string
        }
        Insert: {
          created_at?: string | null
          id?: string
          items?: Json
          meal_plan_id?: string | null
          title?: string
          updated_at?: string | null
          user_id: string
        }
        Update: {
          created_at?: string | null
          id?: string
          items?: Json
          meal_plan_id?: string | null
          title?: string
          updated_at?: string | null
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "shopping_lists_meal_plan_id_fkey"
            columns: ["meal_plan_id"]
            isOneToOne: false
            referencedRelation: "meal_plans"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "shopping_lists_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "user_profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      user_learning_profile: {
        Row: {
          adherence_triggers: Json | null
          calculated_tdee: number | null
          carb_sensitivity: string | null
          confidence_level: number | null
          energy_patterns: Json | null
          fat_sensitivity: string | null
          id: string
          meal_preferences: Json | null
          metabolic_adaptation_detected: boolean | null
          metabolic_adaptation_factor: number | null
          motivation_notes: string | null
          motivation_pattern: string | null
          next_review_week_number: number | null
          observed_tdee: number | null
          preferred_macro_distribution: Json | null
          protein_sensitivity_g_per_kg: number | null
          red_flags_history: Json | null
          stress_response: Json | null
          updated_at: string | null
          user_id: string | null
          weeks_of_data: number | null
        }
        Insert: {
          adherence_triggers?: Json | null
          calculated_tdee?: number | null
          carb_sensitivity?: string | null
          confidence_level?: number | null
          energy_patterns?: Json | null
          fat_sensitivity?: string | null
          id?: string
          meal_preferences?: Json | null
          metabolic_adaptation_detected?: boolean | null
          metabolic_adaptation_factor?: number | null
          motivation_notes?: string | null
          motivation_pattern?: string | null
          next_review_week_number?: number | null
          observed_tdee?: number | null
          preferred_macro_distribution?: Json | null
          protein_sensitivity_g_per_kg?: number | null
          red_flags_history?: Json | null
          stress_response?: Json | null
          updated_at?: string | null
          user_id?: string | null
          weeks_of_data?: number | null
        }
        Update: {
          adherence_triggers?: Json | null
          calculated_tdee?: number | null
          carb_sensitivity?: string | null
          confidence_level?: number | null
          energy_patterns?: Json | null
          fat_sensitivity?: string | null
          id?: string
          meal_preferences?: Json | null
          metabolic_adaptation_detected?: boolean | null
          metabolic_adaptation_factor?: number | null
          motivation_notes?: string | null
          motivation_pattern?: string | null
          next_review_week_number?: number | null
          observed_tdee?: number | null
          preferred_macro_distribution?: Json | null
          protein_sensitivity_g_per_kg?: number | null
          red_flags_history?: Json | null
          stress_response?: Json | null
          updated_at?: string | null
          user_id?: string | null
          weeks_of_data?: number | null
        }
        Relationships: [
          {
            foreignKeyName: "user_learning_profile_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: true
            referencedRelation: "user_profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      user_profiles: {
        Row: {
          activity_level: string | null
          age: number | null
          allergies: string[] | null
          bmr: number | null
          created_at: string
          diet_type: string | null
          disliked_foods: string[] | null
          email: string
          favorite_foods: string[] | null
          full_name: string | null
          gender: string | null
          goals: Json | null
          height_cm: number | null
          id: string
          is_admin: boolean | null
          max_prep_time: number | null
          preferred_cuisines: string[] | null
          target_calories: number | null
          target_carbs_g: number | null
          target_fat_g: number | null
          target_protein_g: number | null
          tdee: number | null
          updated_at: string
          weight_kg: number | null
        }
        Insert: {
          activity_level?: string | null
          age?: number | null
          allergies?: string[] | null
          bmr?: number | null
          created_at?: string
          diet_type?: string | null
          disliked_foods?: string[] | null
          email: string
          favorite_foods?: string[] | null
          full_name?: string | null
          gender?: string | null
          goals?: Json | null
          height_cm?: number | null
          id: string
          is_admin?: boolean | null
          max_prep_time?: number | null
          preferred_cuisines?: string[] | null
          target_calories?: number | null
          target_carbs_g?: number | null
          target_fat_g?: number | null
          target_protein_g?: number | null
          tdee?: number | null
          updated_at?: string
          weight_kg?: number | null
        }
        Update: {
          activity_level?: string | null
          age?: number | null
          allergies?: string[] | null
          bmr?: number | null
          created_at?: string
          diet_type?: string | null
          disliked_foods?: string[] | null
          email?: string
          favorite_foods?: string[] | null
          full_name?: string | null
          gender?: string | null
          goals?: Json | null
          height_cm?: number | null
          id?: string
          is_admin?: boolean | null
          max_prep_time?: number | null
          preferred_cuisines?: string[] | null
          target_calories?: number | null
          target_carbs_g?: number | null
          target_fat_g?: number | null
          target_protein_g?: number | null
          tdee?: number | null
          updated_at?: string
          weight_kg?: number | null
        }
        Relationships: []
      }
      weekly_feedback: {
        Row: {
          adherence_percent: number
          adjustment_effectiveness: string | null
          adjustment_rationale: string[] | null
          adjustment_sources: Json | null
          adjustments_applied: boolean | null
          adjustments_suggested: Json | null
          agent_confidence_percent: number | null
          arm_cm: number | null
          body_fat_percent: number | null
          chest_cm: number | null
          cravings: string[] | null
          created_at: string | null
          detected_patterns: Json | null
          energy_level: string
          feedback_quality: string | null
          hips_cm: number | null
          hunger_level: string
          id: string
          measurement_method: string | null
          muscle_mass_kg: number | null
          photo_refs: Json | null
          red_flags: Json | null
          sleep_quality: string
          subjective_notes: string | null
          thigh_cm: number | null
          updated_at: string | null
          user_accepted: boolean | null
          user_id: string | null
          waist_cm: number | null
          water_percent: number | null
          week_number: number
          week_start_date: string
          weight_change_kg: number | null
          weight_change_percent: number | null
          weight_end_kg: number
          weight_start_kg: number
        }
        Insert: {
          adherence_percent: number
          adjustment_effectiveness?: string | null
          adjustment_rationale?: string[] | null
          adjustment_sources?: Json | null
          adjustments_applied?: boolean | null
          adjustments_suggested?: Json | null
          agent_confidence_percent?: number | null
          arm_cm?: number | null
          body_fat_percent?: number | null
          chest_cm?: number | null
          cravings?: string[] | null
          created_at?: string | null
          detected_patterns?: Json | null
          energy_level: string
          feedback_quality?: string | null
          hips_cm?: number | null
          hunger_level: string
          id?: string
          measurement_method?: string | null
          muscle_mass_kg?: number | null
          photo_refs?: Json | null
          red_flags?: Json | null
          sleep_quality: string
          subjective_notes?: string | null
          thigh_cm?: number | null
          updated_at?: string | null
          user_accepted?: boolean | null
          user_id?: string | null
          waist_cm?: number | null
          water_percent?: number | null
          week_number: number
          week_start_date: string
          weight_change_kg?: number | null
          weight_change_percent?: number | null
          weight_end_kg: number
          weight_start_kg: number
        }
        Update: {
          adherence_percent?: number
          adjustment_effectiveness?: string | null
          adjustment_rationale?: string[] | null
          adjustment_sources?: Json | null
          adjustments_applied?: boolean | null
          adjustments_suggested?: Json | null
          agent_confidence_percent?: number | null
          arm_cm?: number | null
          body_fat_percent?: number | null
          chest_cm?: number | null
          cravings?: string[] | null
          created_at?: string | null
          detected_patterns?: Json | null
          energy_level?: string
          feedback_quality?: string | null
          hips_cm?: number | null
          hunger_level?: string
          id?: string
          measurement_method?: string | null
          muscle_mass_kg?: number | null
          photo_refs?: Json | null
          red_flags?: Json | null
          sleep_quality?: string
          subjective_notes?: string | null
          thigh_cm?: number | null
          updated_at?: string | null
          user_accepted?: boolean | null
          user_id?: string | null
          waist_cm?: number | null
          water_percent?: number | null
          week_number?: number
          week_start_date?: string
          weight_change_kg?: number | null
          weight_change_percent?: number | null
          weight_end_kg?: number
          weight_start_kg?: number
        }
        Relationships: [
          {
            foreignKeyName: "weekly_feedback_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "user_profiles"
            referencedColumns: ["id"]
          },
        ]
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      increment_recipe_usage: {
        Args: { p_recipe_id: string }
        Returns: undefined
      }
      is_admin: { Args: never; Returns: boolean }
      match_documents: {
        Args: { filter?: Json; match_count?: number; query_embedding: string }
        Returns: {
          content: string
          id: number
          metadata: Json
          similarity: number
        }[]
      }
      search_openfoodfacts: {
        Args: { max_results?: number; search_query: string }
        Returns: {
          calories_per_100g: number
          carbs_g_per_100g: number
          code: string
          fat_g_per_100g: number
          product_name: string
          product_name_fr: string
          protein_g_per_100g: number
          similarity_score: number
        }[]
      }
      show_limit: { Args: never; Returns: number }
      show_trgm: { Args: { "": string }; Returns: string[] }
      unaccent: { Args: { "": string }; Returns: string }
    }
    Enums: {
      [_ in never]: never
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {},
  },
} as const

// --- Custom application types ---

export interface ShoppingListItem {
  name: string;
  quantity: number;
  unit: string;
  category: string;
  checked: boolean;
}

export interface FileAttachment {
  fileName: string;
  content: string; // Base64 encoded content
  mimeType: string;
}

export type Conversation = Database['public']['Tables']['conversations']['Row'];
// Message: DB stores `message` as Json, but frontend expects structured content
export type Message = Omit<Database['public']['Tables']['messages']['Row'], 'id' | 'message' | 'message_data'> & {
  id: string | number;
  message_data?: string | null;
  message: {
    type: 'human' | 'ai';
    content: string;
    files?: FileAttachment[];
    ui_components?: Array<{
      id: string;
      component: string;
      props: Record<string, unknown>;
      zone: string;
    }>;
  };
};
export type UserProfile = Database['public']['Tables']['user_profiles']['Row'];
export type DailyFoodLog = Database['public']['Tables']['daily_food_log']['Row'];
export type DailyFoodLogInsert = Database['public']['Tables']['daily_food_log']['Insert'];
export type DailyFoodLogUpdate = Database['public']['Tables']['daily_food_log']['Update'];
export type FavoriteRecipe = Database['public']['Tables']['favorite_recipes']['Row'];
export type ShoppingList = Database['public']['Tables']['shopping_lists']['Row'];

// Full recipe from the recipes table
export interface Recipe {
  id: string;
  name: string;
  name_normalized: string;
  description: string | null;
  meal_type: string;
  cuisine_type: string | null;
  diet_type: string | null;
  tags: string[] | null;
  ingredients: Array<{
    name: string;
    quantity?: number;
    unit?: string;
    macros_calculated?: {
      calories: number;
      protein_g: number;
      carbs_g: number;
      fat_g: number;
      confidence?: number;
    };
  }>;
  instructions: string | null;
  prep_time_minutes: number | null;
  calories_per_serving: number;
  protein_g_per_serving: number;
  carbs_g_per_serving: number;
  fat_g_per_serving: number;
  allergen_tags: string[] | null;
  source: string | null;
  created_at: string | null;
}

// Favorite with joined recipe data (from select("*, recipes(*)"))
export interface FavoriteWithRecipe {
  id: string;
  user_id: string;
  recipe_id: string;
  notes: string | null;
  created_at: string | null;
  recipes: Recipe | null;
}
