import { WeightTrendIndicatorProps } from '@/types/generative-ui.types';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

export function WeightTrendIndicator({ weight_start, weight_end, trend, rate }: WeightTrendIndicatorProps) {
  const diff = weight_end - weight_start;
  const diffStr = diff > 0 ? `+${diff.toFixed(1)}` : diff.toFixed(1);

  const trendConfig = {
    up: { icon: TrendingUp, color: 'text-red-400', bg: 'bg-red-400/10', border: 'border-red-500/30' },
    down: { icon: TrendingDown, color: 'text-emerald-400', bg: 'bg-emerald-400/10', border: 'border-emerald-500/30' },
    stable: { icon: Minus, color: 'text-blue-400', bg: 'bg-blue-400/10', border: 'border-blue-500/30' },
  };

  const config = trendConfig[trend];
  const Icon = config.icon;

  return (
    <div className="glass-effect rounded-lg border border-emerald-500/20 p-4">
      <h4 className="text-sm font-semibold text-gray-400 mb-3 uppercase tracking-wide">Tendance Poids</h4>
      <div className="flex items-center gap-4">
        <div className={`h-12 w-12 rounded-full ${config.bg} border ${config.border} flex items-center justify-center`}>
          <Icon className={`h-6 w-6 ${config.color}`} />
        </div>
        <div className="flex-1">
          <div className="flex items-baseline gap-2">
            <span className="text-gray-400">{weight_start} kg</span>
            <span className="text-gray-600">&rarr;</span>
            <span className="text-foreground font-bold">{weight_end} kg</span>
          </div>
          <div className="flex items-center gap-2 mt-1">
            <span className={`text-sm font-semibold ${config.color}`}>{diffStr} kg</span>
            <span className={`px-2 py-0.5 rounded-full text-xs ${config.bg} ${config.color} border ${config.border}`}>
              {rate} kg/sem
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
