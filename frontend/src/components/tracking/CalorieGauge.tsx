interface CalorieGaugeProps {
  consumed: number;
  target: number;
}

export function CalorieGauge({ consumed, target }: CalorieGaugeProps) {
  const percentage = target > 0 ? Math.min((consumed / target) * 100, 100) : 0;
  const remaining = Math.max(target - consumed, 0);

  // SVG arc calculation
  const radius = 72;
  const strokeWidth = 10;
  const center = 90;
  const circumference = 2 * Math.PI * radius;
  const dashOffset = circumference - (percentage / 100) * circumference;

  return (
    <div className="flex justify-center py-4 px-4">
      <div className="relative w-[180px] h-[180px]">
        {/* Glow behind the ring */}
        <div
          className="absolute inset-0 rounded-full opacity-30 blur-xl transition-opacity duration-700"
          style={{
            background: `radial-gradient(circle, hsl(160 84% 39% / ${percentage > 0 ? 0.4 : 0}) 0%, transparent 70%)`,
          }}
        />

        <svg viewBox="0 0 180 180" className="w-full h-full -rotate-90">
          {/* Track */}
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke="hsl(220 15% 14%)"
            strokeWidth={strokeWidth}
            strokeLinecap="round"
          />
          {/* Progress arc with gradient */}
          <defs>
            <linearGradient id="calorieGrad" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="hsl(160 84% 39%)" />
              <stop offset="100%" stopColor="hsl(142 76% 56%)" />
            </linearGradient>
          </defs>
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke="url(#calorieGrad)"
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={dashOffset}
            className="transition-all duration-700 ease-out"
            style={{
              filter: 'drop-shadow(0 0 6px hsl(160 84% 39% / 0.5))',
            }}
          />
        </svg>

        {/* Center content */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-3xl font-bold tracking-tight text-white tabular-nums">
            {Math.round(consumed)}
          </span>
          <span className="text-[11px] text-gray-500 mt-0.5">
            / {Math.round(target)} kcal
          </span>
          {remaining > 0 && consumed > 0 && (
            <span className="text-[10px] text-emerald-400/70 mt-1">
              {Math.round(remaining)} restants
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
