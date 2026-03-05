import { Check, Circle, ClipboardList } from 'lucide-react';
import type { PlanMeal } from '@/hooks/useDailyTracking';

interface PlanValidationProps {
  meals: PlanMeal[];
  onLogMeal: (meal: PlanMeal) => void;
  isMealLogged: (meal: PlanMeal) => boolean;
}

function badgeColor(mealType: string): string {
  const s = mealType.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  if (s.startsWith('petit')) return 'bg-amber-500/15 text-amber-400/80';
  if (s.startsWith('dejeuner') || s.startsWith('lunch')) return 'bg-orange-500/15 text-orange-400/80';
  if (s.startsWith('din')) return 'bg-indigo-500/15 text-indigo-400/80';
  return 'bg-emerald-500/15 text-emerald-400/80';
}

export function PlanValidation({ meals, onLogMeal, isMealLogged }: PlanValidationProps) {
  if (meals.length === 0) return null;

  const loggedCount = meals.filter(isMealLogged).length;

  return (
    <div className="px-4 py-2">
      {/* Header */}
      <div className="flex items-center gap-2 mb-2">
        <ClipboardList className="h-3.5 w-3.5 text-emerald-400/60" />
        <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider flex-1">
          Plan du jour
        </span>
        <span className="text-[10px] text-gray-500 tabular-nums">
          {loggedCount}/{meals.length}
        </span>
      </div>

      {/* Plan meals list */}
      <div className="rounded-xl glass-effect border border-white/5 overflow-hidden">
        {meals.map((meal, idx) => {
          const logged = isMealLogged(meal);
          return (
            <button
              key={`${meal.meal_type}-${meal.name}`}
              onClick={logged ? undefined : () => onLogMeal(meal)}
              disabled={logged}
              className={`w-full flex items-center gap-3 px-3 py-2.5 text-left transition-colors
                ${idx > 0 ? 'border-t border-white/[0.03]' : ''}
                ${logged ? 'opacity-60' : 'hover:bg-white/[0.03] active:bg-white/[0.05]'}
              `}
            >
              {/* Checkbox */}
              <div
                className={`h-5 w-5 rounded-full flex items-center justify-center shrink-0 transition-all
                  ${logged ? 'bg-emerald-500/20' : 'border border-gray-600'}
                `}
              >
                {logged ? (
                  <Check className="h-3 w-3 text-emerald-400" />
                ) : (
                  <Circle className="h-2.5 w-2.5 text-transparent" />
                )}
              </div>

              {/* Meal info */}
              <div className="flex-1 min-w-0">
                <span
                  className={`text-sm block truncate ${logged ? 'text-gray-500 line-through decoration-gray-600' : 'text-gray-200'}`}
                >
                  {meal.name}
                </span>
              </div>

              {/* Badge + calories */}
              <span
                className={`text-[9px] px-1.5 py-0.5 rounded-full shrink-0 ${badgeColor(meal.meal_type)}`}
              >
                {meal.meal_type}
              </span>
              <span className="text-[11px] text-gray-500 tabular-nums shrink-0 w-12 text-right">
                {Math.round(meal.nutrition.calories)}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
