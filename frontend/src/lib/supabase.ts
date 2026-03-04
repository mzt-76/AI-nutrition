
import { createClient } from '@supabase/supabase-js';
import { Database } from '../types/database.types';

// Get environment variables
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

// Check if environment variables are defined
if (!supabaseUrl || !supabaseAnonKey) {
  console.error('Supabase URL or Anon Key is missing. Please check your .env file.');
}

// Initialize Supabase client
export const supabase = createClient<Database>(
  supabaseUrl || '',
  supabaseAnonKey || ''
);

export type SupabaseClient = typeof supabase;
