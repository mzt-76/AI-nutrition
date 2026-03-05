interface MacroValues {
  protein_g: number;
  carbs_g: number;
  fat_g: number;
}

interface TrackingMacrosProps {
  consumed: MacroValues;
  targets: MacroValues;
}

interface MacroRowProps {
  label: string;
  consumed: number;
  target: number;
  color: string;
  glowColor: string;
  bgColor: string;
}

function MacroRow({ label, consumed, target, color, glowColor, bgColor }: MacroRowProps) {
  const pct = target > 0 ? Math.min((consumed / target) * 100, 100) : 0;

  return (
    <div className="flex items-center gap-3">
      <span className="text-[11px] text-gray-500 uppercase tracking-wider w-[72px] shrink-0">{label}</span>
      <div className={`flex-1 h-1.5 rounded-full ${bgColor} relative overflow-hidden`}>
        <div
          className="h-full rounded-full transition-all duration-700 ease-out"
          style={{
            width: `${pct}%`,
            background: glowColor,
            boxShadow: pct > 0 ? `0 0 8px ${glowColor}40` : 'none',
          }}
        />
      </div>
      <div className="flex items-baseline gap-0.5 shrink-0 w-[72px] justify-end">
        <span className={`text-sm font-bold tabular-nums ${color}`}>{Math.round(consumed)}</span>
        <span className="text-[10px] text-gray-600">/ {Math.round(target)}g</span>
      </div>
    </div>
  );
}

export function TrackingMacros({ consumed, targets }: TrackingMacrosProps) {
  return (
    <div className="mx-4 px-4 py-3 rounded-xl glass-effect border border-white/5 space-y-2.5">
      <MacroRow
        label="Protéines"
        consumed={consumed.protein_g}
        target={targets.protein_g}
        color="text-blue-400"
        glowColor="#60a5fa"
        bgColor="bg-blue-400/10"
      />
      <MacroRow
        label="Glucides"
        consumed={consumed.carbs_g}
        target={targets.carbs_g}
        color="text-amber-400"
        glowColor="#fbbf24"
        bgColor="bg-amber-400/10"
      />
      <MacroRow
        label="Lipides"
        consumed={consumed.fat_g}
        target={targets.fat_g}
        color="text-rose-400"
        glowColor="#fb7185"
        bgColor="bg-rose-400/10"
      />
    </div>
  );
}
