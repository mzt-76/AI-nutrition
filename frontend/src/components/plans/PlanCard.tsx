import { ChevronRight, CalendarDays, Flame, Beef } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import type { MealPlanSummary } from '@/lib/api';

interface PlanCardProps {
  plan: MealPlanSummary;
}

export function PlanCard({ plan }: PlanCardProps) {
  const navigate = useNavigate();

  const weekLabel = plan.week_start
    ? `Semaine du ${new Date(plan.week_start).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long' })}`
    : 'Plan repas';

  const createdLabel = plan.created_at
    ? `Créé le ${new Date(plan.created_at).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long' })}`
    : '';

  return (
    <button
      onClick={() => navigate(`/plans/${plan.id}`)}
      className="w-full text-left rounded-xl glass-effect border border-white/5 p-4 hover:bg-white/[0.03] active:bg-white/[0.05] transition-colors"
    >
      <div className="flex items-center gap-3">
        <CalendarDays className="h-5 w-5 text-emerald-400 shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-200 truncate">{weekLabel}</p>
          {createdLabel && <p className="text-[11px] text-gray-500 mt-0.5">{createdLabel}</p>}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {plan.target_calories_daily != null && (
            <span className="flex items-center gap-1 text-[11px] text-gray-400 bg-white/[0.04] rounded-full px-2 py-0.5">
              <Flame className="h-3 w-3 text-orange-400/70" />
              {plan.target_calories_daily}
            </span>
          )}
          {plan.target_protein_g != null && (
            <span className="flex items-center gap-1 text-[11px] text-gray-400 bg-white/[0.04] rounded-full px-2 py-0.5">
              <Beef className="h-3 w-3 text-red-400/70" />
              {plan.target_protein_g}g
            </span>
          )}
        </div>
        <ChevronRight className="h-4 w-4 text-gray-600 shrink-0" />
      </div>
    </button>
  );
}
