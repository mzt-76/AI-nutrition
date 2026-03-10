import { useEffect, useState, useCallback, useRef } from 'react';
import { Heart, Clock, UtensilsCrossed, Loader2, StickyNote } from 'lucide-react';
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
import { fetchRecipe, upsertRecipe, addFavorite, removeFavorite, checkFavorite, updateFavoriteNotes } from '@/lib/api';
import type { Recipe } from '@/types/database.types';
import { logger } from '@/lib/logger';
import { useToast } from '@/hooks/use-toast';
import { MEAL_ICONS, MEAL_LABELS, normalizeMealType, formatMealTypeFallback } from '@/lib/meal-constants';

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

export function RecipeDetailDrawer({
  open,
  onOpenChange,
  mealData,
  recipeId: propRecipeId,
  onFavoriteChange,
}: RecipeDetailDrawerProps) {
  const { user } = useAuth();
  const { toast } = useToast();
  const userId = user?.id ?? '';

  // Recipe data (resolved from either mode)
  const [recipe, setRecipe] = useState<Recipe | null>(null);
  const [loading, setLoading] = useState(false);

  // Favorite state
  const [isFavorite, setIsFavorite] = useState(false);
  const [favoriteId, setFavoriteId] = useState<string | null>(null);
  const [recipeId, setRecipeId] = useState<string | null>(propRecipeId ?? null);
  const [toggling, setToggling] = useState(false);

  // Notes state
  const [notes, setNotes] = useState('');
  const [savedNotes, setSavedNotes] = useState('');
  const [savingNotes, setSavingNotes] = useState(false);
  const notesTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Load recipe data when drawer opens
  useEffect(() => {
    if (!open) return;

    let cancelled = false;

    setRecipeId(propRecipeId ?? null);
    setIsFavorite(false);
    setFavoriteId(null);
    setNotes('');
    setSavedNotes('');

    if (propRecipeId) {
      // Mode B: fetch from API
      setLoading(true);
      fetchRecipe(propRecipeId)
        .then((data) => { if (!cancelled) setRecipe(data); })
        .catch((err) => {
          if (!cancelled) {
            setRecipe(null);
            logger.error('Failed to fetch recipe:', err);
            toast({ variant: 'destructive', title: 'Erreur', description: 'Impossible de charger la recette.' });
          }
        })
        .finally(() => { if (!cancelled) setLoading(false); });

      // Check favorite status
      if (userId) {
        checkFavorite(userId, propRecipeId)
          .then((res) => {
            if (!cancelled) {
              setIsFavorite(res.is_favorite);
              setFavoriteId(res.favorite_id);
              setNotes(res.notes ?? '');
              setSavedNotes(res.notes ?? '');
            }
          })
          .catch(() => {});
      }
    } else if (mealData) {
      // Mode A: use inline data, no fetch needed
      setRecipe(null);
      setLoading(false);
    }

    return () => { cancelled = true; };
  }, [open, propRecipeId, mealData, userId, toast]);

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
      logger.error('Favorite toggle error:', err);
      toast({
        variant: 'destructive',
        title: 'Erreur',
        description: 'Impossible de modifier le favori. Réessayez.',
      });
    } finally {
      setToggling(false);
    }
  }, [userId, toggling, isFavorite, favoriteId, recipeId, mealData, onFavoriteChange]);

  // Auto-save notes with debounce (1s after last keystroke)
  const handleNotesChange = useCallback(
    (value: string) => {
      setNotes(value);
      if (!favoriteId) return;

      if (notesTimerRef.current) clearTimeout(notesTimerRef.current);
      notesTimerRef.current = setTimeout(async () => {
        if (!favoriteId) return;
        setSavingNotes(true);
        try {
          await updateFavoriteNotes(favoriteId, value || null);
          setSavedNotes(value);
        } catch (err) {
          logger.error('Failed to save notes:', err);
        } finally {
          setSavingNotes(false);
        }
      }, 1000);
    },
    [favoriteId],
  );

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (notesTimerRef.current) clearTimeout(notesTimerRef.current);
    };
  }, []);

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
                      .split(/\n|(?=\d+[.)]\s)/)
                      .map((s) => s.trim().replace(/^\d+[.)]\s*/, ''))
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

              {/* Notes (only for favorites) */}
              {isFavorite && favoriteId && (
                <div>
                  <h4 className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2 flex items-center gap-1.5">
                    <StickyNote className="h-3 w-3" />
                    Notes personnelles
                    {savingNotes && (
                      <span className="text-[10px] text-emerald-400/60 font-normal normal-case ml-auto">
                        Sauvegarde...
                      </span>
                    )}
                    {!savingNotes && notes !== savedNotes && (
                      <span className="text-[10px] text-gray-500 font-normal normal-case ml-auto">
                        Non sauvegardé
                      </span>
                    )}
                    {!savingNotes && notes === savedNotes && notes.length > 0 && (
                      <span className="text-[10px] text-emerald-400/40 font-normal normal-case ml-auto">
                        Sauvegardé
                      </span>
                    )}
                  </h4>
                  <textarea
                    className="w-full bg-white/[0.04] border border-white/[0.06] rounded-lg p-3 text-sm text-gray-300 placeholder:text-gray-600 resize-none focus:outline-none focus:border-emerald-500/30 transition-colors"
                    rows={3}
                    maxLength={500}
                    placeholder="Ex: j'ai ajouté du citron, c'était top..."
                    value={notes}
                    onChange={(e) => handleNotesChange(e.target.value)}
                  />
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
