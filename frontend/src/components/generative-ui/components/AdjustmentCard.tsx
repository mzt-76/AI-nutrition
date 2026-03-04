import { AdjustmentCardProps } from '@/types/generative-ui.types';
import { Settings, AlertTriangle } from 'lucide-react';

export function AdjustmentCard({ calorie_adjustment, new_target, reason, red_flags }: AdjustmentCardProps) {
  const isIncrease = calorie_adjustment > 0;
  const adjustStr = isIncrease ? `+${calorie_adjustment}` : `${calorie_adjustment}`;

  return (
    <div className="glass-effect rounded-lg border border-emerald-500/20 p-4">
      <div className="flex items-center gap-2 mb-3">
        <Settings className="h-5 w-5 text-emerald-400" />
        <h4 className="text-sm font-semibold text-gray-400 uppercase tracking-wide">Ajustement</h4>
      </div>

      <div className="flex items-center gap-4 mb-3">
        <div className={`px-3 py-1 rounded-lg text-lg font-bold ${isIncrease ? 'bg-emerald-400/10 text-emerald-400' : 'bg-amber-400/10 text-amber-400'}`}>
          {adjustStr} kcal
        </div>
        <div>
          <span className="text-sm text-gray-400">Nouvelle cible : </span>
          <span className="text-emerald-400 font-semibold">{new_target} kcal</span>
        </div>
      </div>

      <p className="text-sm text-gray-300 mb-2">{reason}</p>

      {red_flags && red_flags.length > 0 && (
        <div className="border-t border-red-500/20 pt-2 mt-2">
          {red_flags.map((flag, idx) => (
            <div key={idx} className="flex items-center gap-2 text-sm text-red-400 mt-1">
              <AlertTriangle className="h-3 w-3 shrink-0" />
              <span>{flag}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
