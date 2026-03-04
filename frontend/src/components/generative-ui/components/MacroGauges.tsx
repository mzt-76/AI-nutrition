import { MacroGaugesProps } from '@/types/generative-ui.types';

interface MacroBarProps {
  label: string;
  grams: number;
  calPerGram: number;
  targetCalories: number;
  textColor: string;
  barColor: string;
  bgColor: string;
}

function MacroBar({ label, grams, calPerGram, targetCalories, textColor, barColor, bgColor }: MacroBarProps) {
  const calories = grams * calPerGram;
  const percentage = Math.round((calories / targetCalories) * 100);

  return (
    <div className="flex-1">
      <div className="flex justify-between items-baseline mb-1">
        <span className="text-sm font-medium text-gray-300">{label}</span>
        <span className={`text-lg font-bold ${textColor}`}>{grams}g</span>
      </div>
      <div className={`h-2 rounded-full ${bgColor}`}>
        <div
          className={`h-full rounded-full transition-all duration-500 ${barColor}`}
          style={{ width: `${Math.min(percentage, 100)}%` }}
        />
      </div>
      <div className="flex justify-between mt-1">
        <span className="text-xs text-gray-500">{calories} kcal</span>
        <span className="text-xs text-gray-500">{percentage}%</span>
      </div>
    </div>
  );
}

export function MacroGauges({ protein_g, carbs_g, fat_g, target_calories }: MacroGaugesProps) {
  return (
    <div className="glass-effect rounded-lg border border-emerald-500/20 p-4">
      <h4 className="text-sm font-semibold text-gray-400 mb-3 uppercase tracking-wide">Répartition Macros</h4>
      <div className="flex gap-4">
        <MacroBar
          label="Protéines"
          grams={protein_g}
          calPerGram={4}
          targetCalories={target_calories}
          textColor="text-blue-400"
          barColor="bg-blue-400"
          bgColor="bg-blue-400/10"
        />
        <MacroBar
          label="Glucides"
          grams={carbs_g}
          calPerGram={4}
          targetCalories={target_calories}
          textColor="text-amber-400"
          barColor="bg-amber-400"
          bgColor="bg-amber-400/10"
        />
        <MacroBar
          label="Lipides"
          grams={fat_g}
          calPerGram={9}
          targetCalories={target_calories}
          textColor="text-rose-400"
          barColor="bg-rose-400"
          bgColor="bg-rose-400/10"
        />
      </div>
    </div>
  );
}
