import { MealCardProps } from '@/types/generative-ui.types';
import { Clock, UtensilsCrossed } from 'lucide-react';

export function MealCard({ meal_type, recipe_name, calories, macros, prep_time, ingredients, onClick }: MealCardProps) {
  return (
    <div
      className={`glass-effect rounded-lg border border-emerald-500/20 p-4 ${onClick ? 'cursor-pointer hover:border-emerald-500/40 transition-colors' : ''}`}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? (e) => { if (e.key === 'Enter' || e.key === ' ') onClick(); } : undefined}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <UtensilsCrossed className="h-4 w-4 text-emerald-400" />
          <span className="text-xs font-medium uppercase tracking-wide text-gray-400">{meal_type}</span>
        </div>
        {prep_time && (
          <div className="flex items-center gap-1 text-xs text-gray-500">
            <Clock className="h-3 w-3" />
            {prep_time} min
          </div>
        )}
      </div>

      <h4 className="font-semibold text-foreground mb-2">{recipe_name}</h4>

      <div className="flex items-center gap-3 mb-3">
        <span className="text-emerald-400 font-bold">{calories} kcal</span>
        <div className="flex gap-2 text-xs text-gray-400">
          <span className="text-blue-400">P {macros.protein_g}g</span>
          <span className="text-amber-400">G {macros.carbs_g}g</span>
          <span className="text-rose-400">L {macros.fat_g}g</span>
        </div>
      </div>

      {ingredients && ingredients.length > 0 && (
        <div className="border-t border-emerald-500/10 pt-2">
          <p className="text-xs text-gray-500 mb-1">Ingrédients :</p>
          <p className="text-xs text-gray-400">{ingredients.join(', ')}</p>
        </div>
      )}
    </div>
  );
}
