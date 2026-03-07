import { Heart, Coffee } from 'lucide-react';
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import type { FavoriteWithRecipe } from '@/types/database.types';
import { MEAL_ICONS, MEAL_LABELS, normalizeMealType, formatMealTypeFallback } from '@/lib/meal-constants';

export function FavoriteCard({ favorite, onRemove, onClick }: FavoriteCardProps) {
  const [removing, setRemoving] = useState(false);
  const recipe = favorite.recipes;
  if (!recipe) return null;

  const mealTypeNorm = normalizeMealType(recipe.meal_type);
  const Icon = MEAL_ICONS[mealTypeNorm] ?? Coffee;

  const handleRemove = (e: React.MouseEvent) => {
    e.stopPropagation();
    setRemoving(true);
    onRemove(favorite.id);
  };

  return (
    <div
      className={`rounded-xl glass-effect border border-white/5 p-4 transition-all ${removing ? 'opacity-30' : ''} ${onClick ? 'cursor-pointer hover:border-emerald-500/20' : ''}`}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? (e) => { if (e.key === 'Enter' || e.key === ' ') onClick(); } : undefined}
    >
      <div className="flex items-start gap-3">
        <Icon className="h-4 w-4 text-gray-500 mt-0.5 shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="flex items-start gap-2">
            <p className="text-sm font-medium text-gray-200 break-words">{recipe.name}</p>
            <span className="text-[10px] text-gray-500 bg-white/[0.04] rounded-full px-1.5 py-0.5 shrink-0 mt-0.5">
              {MEAL_LABELS[mealTypeNorm] ?? formatMealTypeFallback(recipe.meal_type)}
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 mt-1.5 text-[11px] text-gray-500 tabular-nums">
            <span>{recipe.calories_per_serving} kcal</span>
            <span>{recipe.protein_g_per_serving}g prot</span>
            <span>{recipe.carbs_g_per_serving}g glu</span>
            <span>{recipe.fat_g_per_serving}g lip</span>
          </div>
          {favorite.notes && (
            <p className="text-[11px] text-gray-500 italic mt-1 break-words">{favorite.notes}</p>
          )}
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 text-red-400 hover:text-red-300 shrink-0"
          onClick={handleRemove}
          disabled={removing}
        >
          <Heart className="h-4 w-4 fill-current" />
        </Button>
      </div>
    </div>
  );
}
