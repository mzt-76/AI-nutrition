import { memo } from 'react';
import { MacroGaugesProps } from '@/types/generative-ui.types';
import { Flame } from 'lucide-react';

interface MacroRingProps {
  label: string;
  grams: number;
  percentage: number;
  color: string;
  ringColor: string;
}

const MacroRing = memo(function MacroRing({ label, grams, percentage, color, ringColor }: MacroRingProps) {
  const radius = 28;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (percentage / 100) * circumference;

  return (
    <div className="flex flex-col items-center gap-1.5">
      <div className="relative w-14 h-14 sm:w-16 sm:h-16">
        <svg viewBox="0 0 64 64" className="w-full h-full -rotate-90">
          <circle cx="32" cy="32" r={radius} fill="none" stroke="currentColor" strokeWidth="4" className="text-white/[0.04]" />
          <circle
            cx="32" cy="32" r={radius} fill="none"
            stroke={ringColor} strokeWidth="4" strokeLinecap="round"
            strokeDasharray={circumference} strokeDashoffset={strokeDashoffset}
            className="transition-all duration-700"
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className={`text-xs sm:text-sm font-bold ${color}`}>{percentage}%</span>
        </div>
      </div>
      <span className="text-xs font-medium text-gray-400">{label}</span>
      <span className={`text-sm font-semibold ${color}`}>{Math.round(grams)}g</span>
    </div>
  );
});

export const MacroGauges = memo(function MacroGauges({ protein_g, carbs_g, fat_g, target_calories }: MacroGaugesProps) {
  const totalCal = protein_g * 4 + carbs_g * 4 + fat_g * 9;
  const pPct = totalCal > 0 ? Math.round((protein_g * 4 / totalCal) * 100) : 0;
  const cPct = totalCal > 0 ? Math.round((carbs_g * 4 / totalCal) * 100) : 0;
  const fPct = totalCal > 0 ? Math.round((fat_g * 9 / totalCal) * 100) : 0;

  return (
    <div className="glass-effect rounded-xl border border-emerald-500/20 p-5">
      <div className="flex items-center justify-between mb-4">
        <h4 className="text-sm font-semibold text-gray-400 uppercase tracking-wide">Moyenne journalière</h4>
        <div className="flex items-center gap-1.5 text-emerald-400">
          <Flame className="h-4 w-4" />
          <span className="text-sm font-bold">{Math.round(target_calories)} kcal</span>
        </div>
      </div>
      <div className="flex justify-around">
        <MacroRing label="Protéines" grams={protein_g} percentage={pPct} color="text-blue-400" ringColor="hsl(217, 91%, 60%)" />
        <MacroRing label="Glucides" grams={carbs_g} percentage={cPct} color="text-amber-400" ringColor="hsl(43, 96%, 56%)" />
        <MacroRing label="Lipides" grams={fat_g} percentage={fPct} color="text-rose-400" ringColor="hsl(351, 95%, 71%)" />
      </div>
    </div>
  );
});
