import { v4 as uuidv4 } from 'uuid';
import { supabase } from './supabase';
import {
  Message,
  FileAttachment,
  DailyFoodLog,
  DailyFoodLogInsert,
  DailyFoodLogUpdate,
  FavoriteRecipe,
  FavoriteWithRecipe,
  Recipe,
  ShoppingList,
  ShoppingListItem,
} from '@/types/database.types';
import { logger } from '@/lib/logger';

// Environment variable to determine if streaming is enabled
const ENABLE_STREAMING = import.meta.env.VITE_ENABLE_STREAMING === 'true';
const AGENT_ENDPOINT = import.meta.env.VITE_AGENT_ENDPOINT;

// Base URL derived once — used by pages that call other API endpoints
export const API_BASE_URL = (() => {
  try { return new URL(AGENT_ENDPOINT).origin; }
  catch { return ''; }
})();

if (!API_BASE_URL) {
  logger.error(
    '[api] VITE_AGENT_ENDPOINT is missing or invalid — all apiFetch calls will fail. ' +
    'Set VITE_AGENT_ENDPOINT in frontend/.env',
  );
}

interface ApiResponse {
  title?: string;
  session_id?: string;
  output: string;
}

interface StreamingChunk {
  text?: string;
  title?: string;
  session_id?: string;
  done?: boolean;
  complete?: boolean;
  conversation_title?: string;
  error?: string;
  skills_used?: string[];
  // Generative UI fields
  type?: string;
  component?: string;
  props?: Record<string, unknown>;
  zone?: string;
  id?: string;
  ui_components?: Array<{
    id: string;
    component: string;
    props: Record<string, unknown>;
    zone: string;
  }>;
}

async function parseNDJSONStream(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  onChunk: (chunk: StreamingChunk) => void,
  initialSessionId: string,
): Promise<ApiResponse> {
  const decoder = new TextDecoder();
  let lastTextChunk = '';
  let finalText = '';
  let finalTitle = '';
  let finalSessionId = initialSessionId;

  function processLine(line: string): 'complete' | void {
    try {
      const chunk: StreamingChunk = JSON.parse(line);

      if (chunk.text !== undefined && chunk.text.trim() !== '') {
        lastTextChunk = chunk.text;
        finalText = chunk.text;
        onChunk(chunk);
      }

      if (chunk.type === 'ui_component' && chunk.component) {
        onChunk(chunk);
      }

      if (chunk.title) finalTitle = chunk.title;
      if (chunk.session_id) finalSessionId = chunk.session_id;
      if (chunk.conversation_title) finalTitle = chunk.conversation_title;

      if (chunk.complete === true) {
        if (chunk.text !== undefined && chunk.text.trim() !== '') {
          lastTextChunk = chunk.text;
          finalText = chunk.text;
        }
        onChunk({
          text: lastTextChunk,
          complete: true,
          session_id: finalSessionId,
          conversation_title: finalTitle,
          skills_used: chunk.skills_used,
        });
        return 'complete';
      }
    } catch (e) {
      logger.warn('Skipped invalid NDJSON line:', e);
    }
  }

  while (true) {
    const { done, value } = await reader.read();

    if (done) {
      const remaining = decoder.decode();
      if (remaining) {
        const lines = remaining.split('\n').filter(l => l.trim() !== '');
        for (const line of lines) processLine(line);
      }
      break;
    }

    const chunkText = decoder.decode(value, { stream: true });
    const lines = chunkText.split('\n').filter(l => l.trim() !== '');
    for (const line of lines) {
      if (processLine(line) === 'complete') {
        return {
          title: finalTitle || 'New conversation',
          session_id: finalSessionId,
          output: lastTextChunk || finalText,
        };
      }
    }
  }

  return {
    title: finalTitle || 'New conversation',
    session_id: finalSessionId,
    output: lastTextChunk || finalText,
  };
}

export const sendMessage = async (
  query: string,
  user_id: string,
  session_id: string = '',
  access_token?: string,
  files?: FileAttachment[],
  onStreamChunk?: (chunk: StreamingChunk) => void,
  abortSignal?: AbortSignal,
  ephemeral?: boolean,
): Promise<ApiResponse> => {
  try {
    const request_id = uuidv4();
    const payload = {
      query,
      user_id,
      request_id,
      session_id,
      files,
      ephemeral: ephemeral ?? false,
    };

    // Use caller's signal or create a timeout signal
    const timeoutMs = onStreamChunk ? 120_000 : 30_000;
    let signal = abortSignal;
    let timeoutId: ReturnType<typeof setTimeout> | undefined;
    if (!signal) {
      const controller = new AbortController();
      signal = controller.signal;
      timeoutId = setTimeout(() => controller.abort(), timeoutMs);
    }

    const response = await fetch(AGENT_ENDPOINT, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(access_token ? { Authorization: `Bearer ${access_token}` } : {}),
      },
      body: JSON.stringify(payload),
      signal,
    });

    if (timeoutId) clearTimeout(timeoutId);

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`API error: ${response.status} - ${errorText}`);
    }

    // Handle streaming response if enabled
    if (ENABLE_STREAMING && onStreamChunk) {
      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('Failed to get response reader');
      }
      return parseNDJSONStream(reader, onStreamChunk, session_id);
    } else {
      // For non-streaming responses (original implementation)
      const responseText = await response.text();
      if (!responseText.trim()) {
        throw new Error('Empty response from API');
      }
      
      // Handle possible JSON array format from the API
      try {
        const parsedData = JSON.parse(responseText);
        
        // If the response is an array, take the first item
        if (Array.isArray(parsedData)) {
          if (parsedData.length === 0) {
            throw new Error('Réponse vide du serveur.');
          }
          return {
            title: parsedData[0]?.conversation_title || "Nouvelle conversation",
            session_id: parsedData[0]?.session_id || session_id,
            output: parsedData[0]?.output || "Désolé, je n'ai pas pu traiter votre demande."
          };
        }
        
        // Otherwise return the object directly
        return parsedData;
      } catch (jsonError) {
        logger.error('Error parsing JSON response:', jsonError, 'Response text:', responseText);
        throw new Error(`Invalid JSON response from API: ${jsonError instanceof Error ? jsonError.message : String(jsonError)}`);
      }
    }
  } catch (error) {
    logger.error('Error sending message to API:', error);
    throw error;
  }
};

// =============================================================================
// Helper: authenticated fetch against backend API
// =============================================================================

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  if (!API_BASE_URL) {
    throw new Error('API_BASE_URL is empty — VITE_AGENT_ENDPOINT is not configured');
  }

  let token = '';
  try {
    const { data: { session } } = await supabase.auth.getSession();
    token = session?.access_token ?? '';
  } catch (e) {
    logger.warn('[apiFetch] getSession() failed, proceeding without token:', e);
  }

  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers ?? {}),
    },
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }

  // DELETE endpoints return 200 with small JSON body
  return res.json() as Promise<T>;
}

// =============================================================================
// Food Search
// =============================================================================

export interface FoodSearchResult {
  matched_name: string;
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  quantity: number;
  unit: string;
  confidence: number;
}

export const searchFood = (
  query: string,
  quantity: number = 100,
  unit: string = 'g',
): Promise<FoodSearchResult> =>
  apiFetch(`/api/food-search?${new URLSearchParams({ q: query, quantity: String(quantity), unit })}`);

// =============================================================================
// Daily Food Log
// =============================================================================

export const fetchDailyLog = (userId: string, date: string): Promise<DailyFoodLog[]> =>
  apiFetch(`/api/daily-log?${new URLSearchParams({ user_id: userId, date })}`);

export const createDailyLogEntry = (entry: DailyFoodLogInsert): Promise<DailyFoodLog> =>
  apiFetch('/api/daily-log', { method: 'POST', body: JSON.stringify(entry) });

export const updateDailyLogEntry = (
  entryId: string,
  updates: DailyFoodLogUpdate,
): Promise<DailyFoodLog> =>
  apiFetch(`/api/daily-log/${entryId}`, { method: 'PUT', body: JSON.stringify(updates) });

export const deleteDailyLogEntry = (entryId: string): Promise<{ status: string }> =>
  apiFetch(`/api/daily-log/${entryId}`, { method: 'DELETE' });

// =============================================================================
// Meal Plans (list)
// =============================================================================

export interface MealPlanSummary {
  id: string;
  user_id: string;
  week_start: string | null;
  target_calories_daily: number | null;
  target_protein_g: number | null;
  target_carbs_g: number | null;
  target_fat_g: number | null;
  notes: string | null;
  created_at: string | null;
}

export const fetchMealPlans = (userId: string): Promise<MealPlanSummary[]> =>
  apiFetch(`/api/meal-plans?${new URLSearchParams({ user_id: userId })}`);

export const deleteMealPlan = (planId: string): Promise<{ status: string }> =>
  apiFetch(`/api/meal-plans/${planId}`, { method: 'DELETE' });

// =============================================================================
// Favorite Recipes
// =============================================================================

export const fetchFavorites = (userId: string): Promise<FavoriteWithRecipe[]> =>
  apiFetch(`/api/favorites?${new URLSearchParams({ user_id: userId })}`);

export const addFavorite = (
  userId: string,
  recipeId: string,
  notes?: string,
): Promise<FavoriteRecipe> =>
  apiFetch('/api/favorites', {
    method: 'POST',
    body: JSON.stringify({ user_id: userId, recipe_id: recipeId, notes }),
  });

export const removeFavorite = (favoriteId: string): Promise<{ status: string }> =>
  apiFetch(`/api/favorites/${favoriteId}`, { method: 'DELETE' });

export const updateFavoriteNotes = (
  favoriteId: string,
  notes: string | null,
): Promise<FavoriteRecipe> =>
  apiFetch(`/api/favorites/${favoriteId}`, {
    method: 'PATCH',
    body: JSON.stringify({ notes }),
  });

export const checkFavorite = (
  userId: string,
  recipeId: string,
): Promise<{ is_favorite: boolean; favorite_id: string | null; notes: string | null }> =>
  apiFetch(`/api/favorites/check?${new URLSearchParams({ user_id: userId, recipe_id: recipeId })}`);

// =============================================================================
// Recipes
// =============================================================================

export const fetchRecipe = (recipeId: string): Promise<Recipe> =>
  apiFetch(`/api/recipes/${recipeId}`);

export const upsertRecipe = (data: {
  name: string;
  meal_type: string;
  ingredients: Array<Record<string, unknown>>;
  instructions?: string;
  prep_time_minutes?: number;
  calories_per_serving: number;
  protein_g_per_serving: number;
  carbs_g_per_serving: number;
  fat_g_per_serving: number;
}): Promise<Recipe> =>
  apiFetch('/api/recipes', { method: 'POST', body: JSON.stringify(data) });

// =============================================================================
// Shopping Lists
// =============================================================================

export const fetchShoppingLists = (userId: string): Promise<ShoppingList[]> =>
  apiFetch(`/api/shopping-lists?${new URLSearchParams({ user_id: userId })}`);

export const fetchShoppingList = (listId: string): Promise<ShoppingList> =>
  apiFetch(`/api/shopping-lists/${listId}`);

export const createShoppingList = (data: {
  user_id: string;
  meal_plan_id?: string;
  title: string;
  items: ShoppingListItem[];
}): Promise<ShoppingList> =>
  apiFetch('/api/shopping-lists', { method: 'POST', body: JSON.stringify(data) });

export const updateShoppingList = (
  listId: string,
  updates: { title?: string; items?: ShoppingListItem[] },
): Promise<ShoppingList> =>
  apiFetch(`/api/shopping-lists/${listId}`, { method: 'PUT', body: JSON.stringify(updates) });

export const deleteShoppingList = (listId: string): Promise<{ status: string }> =>
  apiFetch(`/api/shopping-lists/${listId}`, { method: 'DELETE' });

// =============================================================================
// Profile Recalculate
// =============================================================================

export const recalculateProfile = (data: {
  age: number;
  gender: string;
  weight_kg: number;
  height_cm: number;
  activity_level: string;
  goals?: Record<string, number>;
}): Promise<{
  bmr: number;
  tdee: number;
  target_calories: number;
  target_protein_g: number;
  target_carbs_g: number;
  target_fat_g: number;
  primary_goal: string;
}> =>
  apiFetch('/api/profile/recalculate', { method: 'POST', body: JSON.stringify(data) });

// =============================================================================
// Conversations
// =============================================================================

export const deleteConversation = (sessionId: string): Promise<{ status: string }> =>
  apiFetch(`/api/conversations/${sessionId}`, { method: 'DELETE' });

export const fetchConversations = async (user_id: string) => {
  try {
    const { data, error } = await supabase
      .from('conversations')
      .select('*')
      .eq('user_id', user_id)
      .order('created_at', { ascending: false });

    if (error) throw error;
    return data;
  } catch (error) {
    logger.error('Error fetching conversations:', error);
    throw error;
  }
};

export const fetchMessages = async (session_id: string) => {
  try {
    // Updated query approach - instead of using computed_session_user_id, query directly by session_id
    // This avoids the UUID format issue
    const { data, error } = await supabase
      .from('messages')
      .select('*')
      .eq('session_id', session_id)
      .order('created_at', { ascending: true });

    if (error) throw error;
    return data as unknown as Message[];
  } catch (error) {
    logger.error('Error fetching messages:', error);
    throw error;
  }
};
