import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import { MacroGauges } from '@/components/generative-ui/components/MacroGauges';
import { DayPlanCard } from '@/components/generative-ui/components/DayPlanCard';
import { MealCardProps } from '@/types/generative-ui.types';
import { ArrowLeft, CalendarDays, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { LoadingDots } from '@/components/ui/loading-dots';
import { apiFetch } from '@/lib/api';

// Ingredient from recipe DB can be string or structured object
interface IngredientObj {
  name: string;
  quantity?: number;
  unit?: string;
}

interface MealPlanDay {
  day: string;
  meals: Array<{
    meal_type: string;
    name: string;
    nutrition: {
      calories: number;
      protein_g: number;
      carbs_g: number;
      fat_g: number;
    };
    ingredients?: Array<string | IngredientObj>;
    prep_time_minutes?: number;
  }>;
  daily_totals: {
    calories: number;
    protein_g: number;
    carbs_g: number;
    fat_g: number;
  };
}

interface MealPlanData {
  id: string;
  plan_data: {
    days: MealPlanDay[];
    weekly_summary?: {
      average_calories: number;
      average_protein_g: number;
      average_carbs_g?: number;
      average_fat_g?: number;
    };
  };
  created_at: string;
}

export default function MealPlanView() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { session } = useAuth();
  const [plan, setPlan] = useState<MealPlanData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchPlan = async () => {
    if (!id || !session) return;
    setLoading(true);
    setError(null);

    try {
      const data = await apiFetch<MealPlanData>(`/api/meal-plans/${id}`);
      setPlan(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur inconnue');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPlan();
  }, [id, session]);

  if (loading) {
    return (
      <div className="min-h-screen gradient-bg flex items-center justify-center gap-3">
        <LoadingDots className="text-emerald-400" />
        <span className="text-sm text-gray-400">Chargement du plan</span>
      </div>
    );
  }

  if (error || !plan) {
    return (
      <div className="min-h-screen gradient-bg flex flex-col items-center justify-center gap-4">
        <p className="text-sm text-red-400/80">
          {error ? 'Impossible de charger le plan.' : 'Plan non trouvé.'}
        </p>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={fetchPlan}>
            <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
            Réessayer
          </Button>
          <Button variant="ghost" size="sm" onClick={() => navigate('/')}>
            <ArrowLeft className="h-3.5 w-3.5 mr-1.5" />
            Retour
          </Button>
        </div>
      </div>
    );
  }

  const { plan_data } = plan;
  const summary = plan_data.weekly_summary;

  return (
    <div className="min-h-screen gradient-bg">
      <div className="max-w-5xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="flex items-center gap-4 mb-8">
          <Button variant="ghost" size="icon" onClick={() => navigate('/')}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
              <CalendarDays className="h-6 w-6 text-emerald-400" />
              Plan Repas
            </h1>
            <p className="text-sm text-gray-400">
              Créé le {new Date(plan.created_at).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })}
            </p>
          </div>
        </div>

        {/* Weekly summary */}
        {summary && (
          <div className="mb-8">
            <MacroGauges
              protein_g={summary.average_protein_g}
              carbs_g={summary.average_carbs_g ?? 0}
              fat_g={summary.average_fat_g ?? 0}
              target_calories={summary.average_calories}
            />
          </div>
        )}

        {/* Days */}
        <div className="space-y-6">
          {plan_data.days.map((day) => {
            const meals: MealCardProps[] = day.meals.map(m => ({
              meal_type: m.meal_type,
              recipe_name: m.name,
              calories: m.nutrition.calories,
              macros: {
                protein_g: m.nutrition.protein_g,
                carbs_g: m.nutrition.carbs_g,
                fat_g: m.nutrition.fat_g,
              },
              prep_time: m.prep_time_minutes,
              ingredients: m.ingredients?.map(ing =>
                typeof ing === 'string' ? ing : `${ing.name}${ing.quantity ? ` (${ing.quantity}${ing.unit || ''})` : ''}`
              ),
            }));

            return (
              <DayPlanCard
                key={day.day}
                day_name={day.day}
                meals={meals}
                totals={day.daily_totals}
              />
            );
          })}
        </div>
      </div>
    </div>
  );
}
