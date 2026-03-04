
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

export interface Database {
  public: {
    Tables: {
      conversations: {
        Row: {
          session_id: string;
          user_id: string;
          title: string | null;
          created_at: string | null;
          last_message_at: string | null;
          is_archived: boolean | null;
          metadata: Record<string, unknown> | null;
        };
        Insert: {
          session_id: string;
          user_id: string;
          title?: string | null;
          created_at?: string | null;
          last_message_at?: string | null;
          is_archived?: boolean | null;
          metadata?: Record<string, unknown> | null;
        };
        Update: {
          session_id?: string;
          user_id?: string;
          title?: string | null;
          created_at?: string | null;
          last_message_at?: string | null;
          is_archived?: boolean | null;
          metadata?: Record<string, unknown> | null;
        };
      };
      messages: {
        Row: {
          id: number;
          session_id: string;
          computed_session_user_id: string | null;
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
          message_data: string | null;
          created_at: string | null;
        };
        Insert: {
          id?: never; // auto-generated identity
          session_id: string;
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
          message_data?: string | null;
          created_at?: string | null;
        };
        Update: {
          session_id?: string;
          message?: {
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
          message_data?: string | null;
          created_at?: string | null;
        };
      };
      daily_food_log: {
        Row: {
          id: string;
          user_id: string;
          log_date: string;
          meal_type: string;
          food_name: string;
          quantity: number | null;
          unit: string | null;
          calories: number;
          protein_g: number;
          carbs_g: number;
          fat_g: number;
          source: string | null;
          meal_plan_id: string | null;
          created_at: string | null;
          updated_at: string | null;
        };
        Insert: {
          id?: string;
          user_id: string;
          log_date?: string;
          meal_type: string;
          food_name: string;
          quantity?: number | null;
          unit?: string | null;
          calories?: number;
          protein_g?: number;
          carbs_g?: number;
          fat_g?: number;
          source?: string | null;
          meal_plan_id?: string | null;
          created_at?: string | null;
          updated_at?: string | null;
        };
        Update: {
          id?: string;
          user_id?: string;
          log_date?: string;
          meal_type?: string;
          food_name?: string;
          quantity?: number | null;
          unit?: string | null;
          calories?: number;
          protein_g?: number;
          carbs_g?: number;
          fat_g?: number;
          source?: string | null;
          meal_plan_id?: string | null;
          created_at?: string | null;
          updated_at?: string | null;
        };
      };
      favorite_recipes: {
        Row: {
          id: string;
          user_id: string;
          recipe_id: string;
          notes: string | null;
          created_at: string | null;
        };
        Insert: {
          id?: string;
          user_id: string;
          recipe_id: string;
          notes?: string | null;
          created_at?: string | null;
        };
        Update: {
          id?: string;
          user_id?: string;
          recipe_id?: string;
          notes?: string | null;
          created_at?: string | null;
        };
      };
      shopping_lists: {
        Row: {
          id: string;
          user_id: string;
          meal_plan_id: string | null;
          title: string;
          items: ShoppingListItem[];
          created_at: string | null;
          updated_at: string | null;
        };
        Insert: {
          id?: string;
          user_id: string;
          meal_plan_id?: string | null;
          title?: string;
          items?: ShoppingListItem[];
          created_at?: string | null;
          updated_at?: string | null;
        };
        Update: {
          id?: string;
          user_id?: string;
          meal_plan_id?: string | null;
          title?: string;
          items?: ShoppingListItem[];
          created_at?: string | null;
          updated_at?: string | null;
        };
      };
      user_profiles: {
        Row: {
          id: string;
          email: string;
          full_name: string | null;
          is_admin: boolean | null;
          created_at: string;
          updated_at: string;
          age: number | null;
          gender: string | null;
          weight_kg: number | null;
          height_cm: number | null;
          activity_level: string | null;
          goals: Record<string, unknown> | null;
          allergies: string[] | null;
          diet_type: string | null;
          disliked_foods: string[] | null;
          favorite_foods: string[] | null;
          preferred_cuisines: string[] | null;
          max_prep_time: number | null;
          bmr: number | null;
          tdee: number | null;
          target_calories: number | null;
          target_protein_g: number | null;
          target_carbs_g: number | null;
          target_fat_g: number | null;
        };
        Insert: {
          id: string;
          email: string;
          full_name?: string | null;
          is_admin?: boolean | null;
          created_at?: string;
          updated_at?: string;
          age?: number | null;
          gender?: string | null;
          weight_kg?: number | null;
          height_cm?: number | null;
          activity_level?: string | null;
          goals?: Record<string, unknown> | null;
          allergies?: string[] | null;
          diet_type?: string | null;
          disliked_foods?: string[] | null;
          favorite_foods?: string[] | null;
          preferred_cuisines?: string[] | null;
          max_prep_time?: number | null;
          bmr?: number | null;
          tdee?: number | null;
          target_calories?: number | null;
          target_protein_g?: number | null;
          target_carbs_g?: number | null;
          target_fat_g?: number | null;
        };
        Update: {
          id?: string;
          email?: string;
          full_name?: string | null;
          is_admin?: boolean | null;
          created_at?: string;
          updated_at?: string;
          age?: number | null;
          gender?: string | null;
          weight_kg?: number | null;
          height_cm?: number | null;
          activity_level?: string | null;
          goals?: Record<string, unknown> | null;
          allergies?: string[] | null;
          diet_type?: string | null;
          disliked_foods?: string[] | null;
          favorite_foods?: string[] | null;
          preferred_cuisines?: string[] | null;
          max_prep_time?: number | null;
          bmr?: number | null;
          tdee?: number | null;
          target_calories?: number | null;
          target_protein_g?: number | null;
          target_carbs_g?: number | null;
          target_fat_g?: number | null;
        };
      };
    };
  };
}

export type Conversation = Database['public']['Tables']['conversations']['Row'];
// Use string | number for Message id to support temporary UI messages with string IDs
export type Message = Omit<Database['public']['Tables']['messages']['Row'], 'id'> & { id: string | number };
export type UserProfile = Database['public']['Tables']['user_profiles']['Row'];
export type DailyFoodLog = Database['public']['Tables']['daily_food_log']['Row'];
export type DailyFoodLogInsert = Database['public']['Tables']['daily_food_log']['Insert'];
export type DailyFoodLogUpdate = Database['public']['Tables']['daily_food_log']['Update'];
export type FavoriteRecipe = Database['public']['Tables']['favorite_recipes']['Row'];
export type ShoppingList = Database['public']['Tables']['shopping_lists']['Row'];
