import { useEffect, useState, useCallback } from 'react';
import { Heart, Clock, UtensilsCrossed, Coffee, Sun, Moon, Cookie, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
  DrawerDescription,
  DrawerFooter,
} from '@/components/ui/drawer';
import { Skeleton } from '@/components/ui/skeleton';
import { useAuth } from '@/hooks/useAuth';
import { fetchRecipe, upsertRecipe, addFavorite, removeFavorite, checkFavorite } from '@/lib/api';
import type { Recipe } from '@/types/database.types';

// Meal data as stored in plan_data (denormalized)
export interface MealDataFromPlan {
  name: string;
  meal_type: string;
  ingredients: Array<string | { name: string; quantity?: number; unit?: string }>;
  instructions?: string;
  prep_time_minutes?: number;
  nutrition: { calories: number; protein_g: number; carbs_g: number; fat_g: number };
}

interface RecipeDetailDrawerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Mode A: inline meal data from plan_data (no recipe ID yet) */
  mealData?: MealDataFromPlan;
  /** Mode B: fetch recipe by ID (from favorites) */
  recipeId?: string;
  /** Called when favorite state changes so parent can refresh */
  onFavoriteChange?: (recipeId: string, isFavorite: boolean) => void;
}

const MEAL_ICONS: Record<string, typeof Coffee> = {
  'petit-dejeuner': Coffee,
  dejeuner: Sun,
  diner: Moon,
  collation: Cookie,
};

const MEAL_LABELS: Record<string, string> = {
  'petit-dejeuner': 'Petit-déjeuner',
  dejeuner: 'Déjeuner',
  diner: 'Dîner',
  collation: 'Collation',
};

function formatMealTypeFallback(raw: string): string {
  return raw.replace(/_/g, ' ').toLowerCase().replace(/^./, c => c.toUpperCase());
}

function normalizeMealType(raw: string): string {
  return raw
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/\s+/g, '-');
}

export function RecipeDetailDrawer({
  open,
  onOpenChange,
  mealData,
  recipeId: propRecipeId,
  onFavoriteChange,
}: RecipeDetailDrawerProps) {
  const { user } = useAuth();
  const userId = user?.id ?? '';

  // Recipe data (resolved from either mode)
  const [recipe, setRecipe] = useState<Recipe | null>(null);
  const [loading, setLoading] = useState(false);

  // Favorite state
  const [isFavorite, setIsFavorite] = useState(false);
  const [favoriteId, setFavoriteId] = useState<string | null>(null);
  const [recipeId, setRecipeId] = useState<string | null>(propRecipeId ?? null);
  const [toggling, setToggling] = useState(false);

  // Load recipe data when drawer opens
  useEffect(() => {
    if (!open) return;

    setRecipeId(propRecipeId ?? null);
    setIsFavorite(false);
    setFavoriteId(null);

    if (propRecipeId) {
      // Mode B: fetch from API
      setLoading(true);
      fetchRecipe(propRecipeId)
        .then((data) => setRecipe(data))
        .catch(() => setRecipe(null))
        .finally(() => setLoading(false));

      // Check favorite status
      if (userId) {
        checkFavorite(userId, propRecipeId)
          .then((res) => {
            setIsFavorite(res.is_favorite);
            setFavoriteId(res.favorite_id);
          })
          .catch(err => console.error('Failed to check favorite:', err));
      }
    } else if (mealData) {
      // Mode A: use inline data, no fetch needed
      setRecipe(null);
      setLoading(false);
    }
  }, [open, propRecipeId, mealData, userId]);

  // Derived display data (works for both modes)
  const displayName = recipe?.name ?? mealData?.name ?? '';
  const rawMealType = recipe?.meal_type ?? mealData?.meal_type ?? '';
  const mealTypeNorm = normalizeMealType(rawMealType);
  const MealIcon = MEAL_ICONS[mealTypeNorm] ?? UtensilsCrossed;
  const mealLabel = MEAL_LABELS[mealTypeNorm] ?? formatMealTypeFallback(rawMealType);

  const calories = recipe?.calories_per_serving ?? mealData?.nutrition.calories ?? 0;
  const protein = recipe?.protein_g_per_serving ?? mealData?.nutrition.protein_g ?? 0;
  const carbs = recipe?.carbs_g_per_serving ?? mealData?.nutrition.carbs_g ?? 0;
  const fat = recipe?.fat_g_per_serving ?? mealData?.nutrition.fat_g ?? 0;
  const prepTime = recipe?.prep_time_minutes ?? mealData?.prep_time_minutes;

  const ingredients = recipe?.ingredients ?? mealData?.ingredients ?? [];
  const instructions = recipe?.instructions ?? mealData?.instructions ?? '';

  const handleToggleFavorite = useCallback(async () => {
    if (!userId || toggling) return;
    setToggling(true);

    try {
      if (isFavorite && favoriteId) {
        // Remove favorite
        await removeFavorite(favoriteId);
        setIsFavorite(false);
        setFavoriteId(null);
        onFavoriteChange?.(recipeId ?? '', false);
      } else {
        // Need a recipe_id first
        let rid = recipeId;
        if (!rid && mealData) {
          // Upsert recipe from plan data
          const created = await upsertRecipe({
            name: mealData.name,
            meal_type: mealData.meal_type,
            ingredients: mealData.ingredients.map((ing) =>
              typeof ing === 'string' ? { name: ing } : ing,
            ),
            instructions: mealData.instructions ?? '',
            prep_time_minutes: mealData.prep_time_minutes ?? 30,
            calories_per_serving: mealData.nutrition.calories,
            protein_g_per_serving: mealData.nutrition.protein_g,
            carbs_g_per_serving: mealData.nutrition.carbs_g,
            fat_g_per_serving: mealData.nutrition.fat_g,
          });
          rid = created.id;
          setRecipeId(rid);
        }

        if (rid) {
          const fav = await addFavorite(userId, rid);
          setIsFavorite(true);
          setFavoriteId(fav.id);
          onFavoriteChange?.(rid, true);
        }
      }
    } catch (err) {
      console.error('Favorite toggle error:', err);
    } finally {
      setToggling(false);
    }
  }, [userId, toggling, isFavorite, favoriteId, recipeId, mealData, onFavoriteChange]);

  return (
    <Drawer open={open} onOpenChange={onOpenChange}>
      <DrawerContent className="max-h-[85vh] glass-effect border-emerald-500/20">
        {loading ? (
          <div className="p-6 space-y-4">
            <Skeleton className="h-6 w-3/4 bg-white/[0.06]" />
            <Skeleton className="h-4 w-1/2 bg-white/[0.04]" />
            <Skeleton className="h-20 w-full bg-white/[0.04]" />
          </div>
        ) : (
          <>
            <DrawerHeader className="text-left">
              <div className="flex items-center gap-2 mb-1">
                <MealIcon className="h-4 w-4 text-emerald-400" />
                <span className="text-[10px] font-medium tracking-wide text-gray-500 bg-white/[0.04] rounded-full px-2 py-0.5">
                  {mealLabel}
                </span>
                {prepTime && (
                  <span className="flex items-center gap-1 text-[10px] text-gray-500 ml-auto">
                    <Clock className="h-3 w-3" />
                    {prepTime} min
                  </span>
                )}
              </div>
              <DrawerTitle className="text-foreground">{displayName}</DrawerTitle>
              <DrawerDescription className="sr-only">
                Detail de la recette {displayName}
              </DrawerDescription>

              {/* Macros bar */}
              <div className="flex items-center gap-3 mt-2">
                <span className="text-emerald-400 font-bold text-sm">{Math.round(calories)} kcal</span>
                <div className="flex gap-2 text-xs">
                  <span className="text-blue-400">P {Math.round(protein)}g</span>
                  <span className="text-amber-400">G {Math.round(carbs)}g</span>
                  <span className="text-rose-400">L {Math.round(fat)}g</span>
                </div>
              </div>
            </DrawerHeader>

            <div className="overflow-y-auto px-4 pb-2 space-y-4">
              {/* Ingredients */}
              {ingredients.length > 0 && (
                <div>
                  <h4 className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2">
                    Ingredients
                  </h4>
                  <ul className="space-y-1">
                    {ingredients.map((ing, i) => {
                      const label =
                        typeof ing === 'string'
                          ? ing
                          : `${ing.name}${ing.quantity ? ` — ${ing.quantity}${ing.unit ? ` ${ing.unit}` : ''}` : ''}`;
                      return (
                        <li key={i} className="text-sm text-gray-300 flex items-start gap-2">
                          <span className="text-emerald-500/60 mt-1.5 shrink-0 h-1 w-1 rounded-full bg-emerald-500/60" />
                          {label}
                        </li>
                      );
                    })}
                  </ul>
                </div>
              )}

              {/* Instructions */}
              {instructions ? (
                <div>
                  <h4 className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2">
                    Préparation
                  </h4>
                  <ol className="space-y-2">
                    {instructions
                      .split(/\n|(?=\d+[\.\)]\s)/)
                      .map((s) => s.trim().replace(/^\d+[\.\)]\s*/, ''))
                      .filter(Boolean)
                      .map((step, i) => (
                        <li key={i} className="text-sm text-gray-300 flex gap-2">
                          <span className="text-emerald-400/70 font-medium shrink-0">{i + 1}.</span>
                          {step}
                        </li>
                      ))}
                  </ol>
                </div>
              ) : (
                <div>
                  <h4 className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2">
                    Préparation
                  </h4>
                  <p className="text-sm text-gray-500 italic">Aucune instruction disponible.</p>
                </div>
              )}
            </div>

            <DrawerFooter>
              <Button
                variant="outline"
                className={`w-full border-emerald-500/20 ${
                  isFavorite
                    ? 'text-red-400 hover:text-red-300'
                    : 'text-gray-400 hover:text-emerald-400'
                }`}
                onClick={handleToggleFavorite}
                disabled={toggling}
              >
                {toggling ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                ) : (
                  <Heart className={`h-4 w-4 mr-2 ${isFavorite ? 'fill-current' : ''}`} />
                )}
                {isFavorite ? 'Retirer des recettes' : 'Ajouter aux recettes'}
              </Button>
            </DrawerFooter>
          </>
        )}
      </DrawerContent>
    </Drawer>
  );
}
