import { Trash2, Coffee, Sun, Moon, Cookie } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { DailyFoodLog } from '@/types/database.types';
import type { MealType } from '@/hooks/useDailyTracking';
import { MEAL_TYPE_LABELS } from '@/hooks/useDailyTracking';

interface MealSectionProps {
  mealType: MealType;
  entries: DailyFoodLog[];
  onDelete: (id: string) => void;
}

const MEAL_ICONS: Record<MealType, typeof Coffee> = {
  'petit-dejeuner': Coffee,
  dejeuner: Sun,
  diner: Moon,
  collation: Cookie,
};

const MEAL_ACCENT: Record<MealType, string> = {
  'petit-dejeuner': 'text-amber-400/70',
  dejeuner: 'text-orange-400/70',
  diner: 'text-indigo-400/70',
  collation: 'text-emerald-400/70',
};

export function MealSection({ mealType, entries, onDelete }: MealSectionProps) {
  const totalKcal = entries.reduce((sum, e) => sum + (e.calories ?? 0), 0);
  const Icon = MEAL_ICONS[mealType];

  return (
    <div className="px-4 py-1.5">
      {/* Header */}
      <div className="flex items-center gap-2 mb-1.5">
        <Icon className={`h-3.5 w-3.5 ${MEAL_ACCENT[mealType]}`} />
        <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider flex-1">
          {MEAL_TYPE_LABELS[mealType]}
        </span>
        {entries.length > 0 && (
          <span className="text-[11px] text-gray-500 tabular-nums font-medium">
            {Math.round(totalKcal)} kcal
          </span>
        )}
      </div>

      {/* Entries */}
      {entries.length === 0 ? (
        <div className="py-2 pl-5.5">
          <span className="text-xs text-gray-600 italic">Aucun aliment</span>
        </div>
      ) : (
        <div className="space-y-0.5">
          {entries.map((entry) => (
            <div
              key={entry.id}
              className="flex items-center gap-2 py-1.5 px-2 -mx-1 rounded-lg hover:bg-white/[0.03] group transition-colors"
            >
              <div className="w-1 h-1 rounded-full bg-gray-600 shrink-0" />
              <span className="text-sm text-gray-300 truncate flex-1">{entry.food_name}</span>
              {entry.quantity && entry.unit && (
                <span className="text-[10px] text-gray-600 shrink-0">
                  {entry.quantity}{entry.unit}
                </span>
              )}
              <span className="text-xs text-gray-500 tabular-nums shrink-0 w-12 text-right">
                {Math.round(entry.calories)}
              </span>
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6 text-gray-600 hover:text-red-400 active:text-red-400 transition-colors shrink-0"
                onClick={() => onDelete(entry.id)}
              >
                <Trash2 className="h-3 w-3" />
                <span className="sr-only">Supprimer {entry.food_name}</span>
              </Button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
