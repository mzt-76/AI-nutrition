import { NutritionSummaryCardProps } from '@/types/generative-ui.types';
import { Flame, Target, TrendingUp } from 'lucide-react';

export function NutritionSummaryCard({ bmr, tdee, target_calories, primary_goal, rationale }: NutritionSummaryCardProps) {
  return (
    <div className="glass-effect rounded-lg border border-emerald-500/20 p-5">
      <div className="flex items-center gap-2 mb-4">
        <div className="h-8 w-8 rounded-full gradient-green flex items-center justify-center">
          <Target className="h-4 w-4 text-white" />
        </div>
        <h3 className="text-lg font-semibold text-foreground">Bilan Nutritionnel</h3>
        <span className="ml-auto px-3 py-1 rounded-full text-xs font-medium bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
          {primary_goal}
        </span>
      </div>

      <div className="grid grid-cols-3 gap-4 mb-4">
        <div className="text-center">
          <div className="flex items-center justify-center gap-1 mb-1">
            <Flame className="h-4 w-4 text-orange-400" />
            <span className="text-sm text-gray-400">BMR</span>
          </div>
          <span className="text-xl font-bold text-foreground">{bmr}</span>
          <span className="text-xs text-gray-500 ml-1">kcal</span>
        </div>
        <div className="text-center">
          <div className="flex items-center justify-center gap-1 mb-1">
            <TrendingUp className="h-4 w-4 text-blue-400" />
            <span className="text-sm text-gray-400">TDEE</span>
          </div>
          <span className="text-xl font-bold text-foreground">{tdee}</span>
          <span className="text-xs text-gray-500 ml-1">kcal</span>
        </div>
        <div className="text-center">
          <div className="flex items-center justify-center gap-1 mb-1">
            <Target className="h-4 w-4 text-emerald-400" />
            <span className="text-sm text-gray-400">Cible</span>
          </div>
          <span className="text-xl font-bold text-emerald-400">{target_calories}</span>
          <span className="text-xs text-gray-500 ml-1">kcal</span>
        </div>
      </div>

      {rationale && (
        <p className="text-sm text-gray-400 border-t border-emerald-500/10 pt-3">{rationale}</p>
      )}
    </div>
  );
}
