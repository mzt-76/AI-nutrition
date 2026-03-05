import { v4 as uuidv4 } from 'uuid';
import { supabase } from './supabase';
import {
  Message,
  FileAttachment,
  DailyFoodLog,
  DailyFoodLogInsert,
  DailyFoodLogUpdate,
  FavoriteRecipe,
  ShoppingList,
  ShoppingListItem,
} from '@/types/database.types';

// Environment variable to determine if streaming is enabled
const ENABLE_STREAMING = import.meta.env.VITE_ENABLE_STREAMING === 'true';
const AGENT_ENDPOINT = import.meta.env.VITE_AGENT_ENDPOINT;

// Base URL derived once — used by pages that call other API endpoints
export const API_BASE_URL = (() => {
  try { return new URL(AGENT_ENDPOINT).origin; }
  catch { return ''; }
})();

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

export const sendMessage = async (
  query: string,
  user_id: string,
  session_id: string = '',
  access_token?: string,
  files?: FileAttachment[],
  onStreamChunk?: (chunk: StreamingChunk) => void
): Promise<ApiResponse> => {
  try {
    const request_id = uuidv4();
    const payload = {
      query,
      user_id,
      request_id,
      session_id,
      files
    };

    const response = await fetch(AGENT_ENDPOINT, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': access_token ? `Bearer ${access_token}` : '',
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`API error: ${response.status} - ${errorText}`);
    }

    // Handle streaming response if enabled
    if (ENABLE_STREAMING && onStreamChunk) {
      // For streaming responses
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let finalText = '';

      if (!reader) {
        throw new Error('Failed to get response reader');
      }

      // Variables to track the state of the stream
      let lastTextChunk = '';
      let finalTitle = '';
      let finalSessionId = session_id;

      while (true) {
        const { done, value } = await reader.read();
        
        // If the stream is done
        if (done) {
          // Make sure to flush the decoder when we're done
          const finalChunk = decoder.decode();
          if (finalChunk) {
            try {
              const finalLines = finalChunk.split('\n').filter(line => line.trim() !== '');
              for (const line of finalLines) {
                try {
                  const chunk = JSON.parse(line);
                  
                  // Process text if present
                  if (chunk.text !== undefined && chunk.text.trim() !== '') {
                    lastTextChunk = chunk.text;
                    finalText = chunk.text;
                    onStreamChunk(chunk);
                  }

                  // Forward ui_component chunks to the callback
                  if (chunk.type === 'ui_component' && chunk.component) {
                    onStreamChunk(chunk);
                  }

                  // Check for complete flag
                  if (chunk.complete === true) {
                    if (chunk.conversation_title) finalTitle = chunk.conversation_title;
                    if (chunk.session_id) finalSessionId = chunk.session_id;
                  }
                } catch (e) {}
              }
            } catch (e) {}
          }
          break;
        }

        // Decode the chunk with stream true to maintain state between chunks
        const chunkText = decoder.decode(value, { stream: true });
        
        try {
          // Split by newlines in case we get multiple JSON objects in one chunk
          const lines = chunkText.split('\n').filter(line => line.trim() !== '');
          
          for (const line of lines) {
            try {
              // Each line should be a JSON object with a text field
              const chunk = JSON.parse(line);
              
              // Process text if present
              if (chunk.text !== undefined && chunk.text.trim() !== '') {
                lastTextChunk = chunk.text;
                finalText = chunk.text;
                // Pass the chunk to the callback
                onStreamChunk(chunk);
              }

              // Forward ui_component chunks to the callback
              if (chunk.type === 'ui_component' && chunk.component) {
                onStreamChunk(chunk);
              }

              // Store metadata if present
              if (chunk.title) finalTitle = chunk.title;
              if (chunk.session_id) finalSessionId = chunk.session_id;
              if (chunk.conversation_title) finalTitle = chunk.conversation_title;
              
              // Check if this chunk indicates completion
              if (chunk.complete === true) {
                // If this chunk has text, use it as the final text
                // Otherwise, keep the last text chunk we received
                if (chunk.text !== undefined && chunk.text.trim() !== '') {
                  lastTextChunk = chunk.text;
                  finalText = chunk.text;
                }
                
                // Send a final chunk with the complete flag to signal completion
                onStreamChunk({
                  text: lastTextChunk,
                  complete: true,
                  session_id: finalSessionId,
                  conversation_title: finalTitle
                });
                
                // We can exit the streaming loop now
                return {
                  title: finalTitle || 'New conversation',
                  session_id: finalSessionId,
                  output: lastTextChunk || finalText
                };
              }
            } catch (error) {
              // Skip invalid JSON
            }
          }
        } catch (error) {
          // Skip any errors in processing
        }
      }
      
      // Return the final response with the most complete information
      return {
        title: finalTitle || 'New conversation',
        session_id: finalSessionId,
        output: lastTextChunk || finalText
      };
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
          return {
            title: parsedData[0]?.conversation_title || "New conversation",
            session_id: parsedData[0]?.session_id || session_id,
            output: parsedData[0]?.output || "Sorry, I couldn't process your request."
          };
        }
        
        // Otherwise return the object directly
        return parsedData;
      } catch (jsonError) {
        console.error('Error parsing JSON response:', jsonError, 'Response text:', responseText);
        throw new Error(`Invalid JSON response from API: ${jsonError.message}`);
      }
    }
  } catch (error) {
    console.error('Error sending message to API:', error);
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
  const { data: { session } } = await supabase.auth.getSession();
  const token = session?.access_token ?? '';

  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Authorization: token ? `Bearer ${token}` : '',
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
// Daily Food Log
// =============================================================================

export const fetchDailyLog = (userId: string, date: string): Promise<DailyFoodLog[]> =>
  apiFetch(`/api/daily-log?user_id=${userId}&date=${date}`);

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
  apiFetch(`/api/meal-plans?user_id=${userId}`);

// =============================================================================
// Favorite Recipes
// =============================================================================

export const fetchFavorites = (userId: string): Promise<FavoriteRecipe[]> =>
  apiFetch(`/api/favorites?user_id=${userId}`);

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

// =============================================================================
// Shopping Lists
// =============================================================================

export const fetchShoppingLists = (userId: string): Promise<ShoppingList[]> =>
  apiFetch(`/api/shopping-lists?user_id=${userId}`);

export const fetchShoppingList = (listId: string): Promise<ShoppingList> =>
  apiFetch(`/api/shopping-lists/${listId}`);

export const updateShoppingList = (
  listId: string,
  updates: { title?: string; items?: ShoppingListItem[] },
): Promise<ShoppingList> =>
  apiFetch(`/api/shopping-lists/${listId}`, { method: 'PUT', body: JSON.stringify(updates) });

// =============================================================================
// Conversations
// =============================================================================

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
    console.error('Error fetching conversations:', error);
    throw error;
  }
};

export const fetchMessages = async (session_id: string, user_id: string) => {
  try {
    // Updated query approach - instead of using computed_session_user_id, query directly by session_id
    // This avoids the UUID format issue
    const { data, error } = await supabase
      .from('messages')
      .select('*')
      .eq('session_id', session_id)
      .order('created_at', { ascending: true });

    if (error) throw error;
    return data as Message[];
  } catch (error) {
    console.error('Error fetching messages:', error);
    throw error;
  }
};
