import { memo } from 'react';
import { DayPlanCardProps } from '@/types/generative-ui.types';
import { MealCard } from './MealCard';
import { CalendarDays } from 'lucide-react';

export const DayPlanCard = memo(function DayPlanCard({ day_name, meals, totals, onMealClick }: DayPlanCardProps) {
  return (
    <div className="glass-effect rounded-lg border border-emerald-500/20 p-4">
      <div className="flex items-center gap-2 mb-3">
        <CalendarDays className="h-5 w-5 text-emerald-400" />
        <h3 className="text-lg font-semibold text-foreground">{day_name}</h3>
      </div>

      <div className="space-y-3 mb-3">
        {meals.map((meal, idx) => (
          <MealCard
            key={`${meal.meal_type}-${idx}`}
            {...meal}
            onClick={onMealClick ? () => onMealClick(idx) : undefined}
          />
        ))}
      </div>

      <div className="border-t border-emerald-500/10 pt-3 flex items-center justify-between">
        <span className="text-sm font-medium text-gray-400">Total journée</span>
        <div className="flex gap-3 text-sm">
          <span className="text-emerald-400 font-bold">{totals.calories} kcal</span>
          <span className="text-blue-400">P {totals.protein_g}g</span>
          <span className="text-amber-400">G {totals.carbs_g}g</span>
          <span className="text-rose-400">L {totals.fat_g}g</span>
        </div>
      </div>
    </div>
  );
});
