import { useState, useEffect, useCallback } from 'react';
import { format, addDays, subDays, isToday } from 'date-fns';
import { fr } from 'date-fns/locale';
import { supabase } from '@/lib/supabase';
import { useAuth } from '@/hooks/useAuth';
import { useToast } from '@/hooks/use-toast';
import {
  fetchDailyLog,
  createDailyLogEntry,
  deleteDailyLogEntry,
  fetchMealPlans,
  apiFetch,
} from '@/lib/api';
import type { DailyFoodLog, DailyFoodLogInsert } from '@/types/database.types';

// Meal plan detail shape from the backend
interface PlanMeal {
  name: string;
  meal_type: string;
  nutrition: { calories: number; protein_g: number; carbs_g: number; fat_g: number };
  ingredients: unknown[];
  instructions: string;
  prep_time_minutes: number;
}

interface PlanDay {
  day: string;
  meals: PlanMeal[];
}

interface MealPlanDetail {
  id: string;
  plan_data: { days: PlanDay[] };
  [key: string]: unknown;
}

export interface NutritionTargets {
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
}

export interface NutritionTotals {
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
}

const MEAL_TYPE_ORDER = ['petit-dejeuner', 'dejeuner', 'diner', 'collation'] as const;
export type MealType = (typeof MEAL_TYPE_ORDER)[number];

export const MEAL_TYPE_LABELS: Record<MealType, string> = {
  'petit-dejeuner': 'Petit-déjeuner',
  dejeuner: 'Déjeuner',
  diner: 'Dîner',
  collation: 'Collation',
};

/** Normalize a display meal_type string (e.g. "Petit-déjeuner", "Collation AM") to a DB key. */
function normalizeMealType(raw: string): MealType {
  const s = raw.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  if (s.startsWith('petit')) return 'petit-dejeuner';
  if (s.startsWith('dejeuner') || s.startsWith('déjeuner') || s === 'lunch') return 'dejeuner';
  if (s.startsWith('din') || s.startsWith('dîn') || s === 'dinner') return 'diner';
  return 'collation';
}

// Map French day names from plan_data to date-fns weekday format
const FRENCH_DAYS: Record<string, string> = {
  Lundi: 'lundi',
  Mardi: 'mardi',
  Mercredi: 'mercredi',
  Jeudi: 'jeudi',
  Vendredi: 'vendredi',
  Samedi: 'samedi',
  Dimanche: 'dimanche',
};

export function useDailyTracking() {
  const { user } = useAuth();
  const { toast } = useToast();

  const [selectedDate, setSelectedDate] = useState(new Date());
  const [entries, setEntries] = useState<DailyFoodLog[]>([]);
  const [targets, setTargets] = useState<NutritionTargets>({
    calories: 2000,
    protein_g: 150,
    carbs_g: 250,
    fat_g: 65,
  });
  const [planDayMeals, setPlanDayMeals] = useState<PlanMeal[]>([]);
  const [activePlanId, setActivePlanId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [planLoading, setPlanLoading] = useState(false);

  const dateStr = format(selectedDate, 'yyyy-MM-dd');
  const isSelectedToday = isToday(selectedDate);

  // Navigation
  const goToPreviousDay = useCallback(() => setSelectedDate((d) => subDays(d, 1)), []);
  const goToNextDay = useCallback(() => setSelectedDate((d) => addDays(d, 1)), []);
  const goToToday = useCallback(() => setSelectedDate(new Date()), []);

  // Fetch profile targets
  useEffect(() => {
    if (!user) return;
    const fetchTargets = async () => {
      const { data } = await supabase
        .from('user_profiles')
        .select('target_calories, target_protein_g, target_carbs_g, target_fat_g')
        .eq('id', user.id)
        .single();
      if (data) {
        setTargets({
          calories: data.target_calories ?? 2000,
          protein_g: data.target_protein_g ?? 150,
          carbs_g: data.target_carbs_g ?? 250,
          fat_g: data.target_fat_g ?? 65,
        });
      }
    };
    fetchTargets();
  }, [user]);

  // Fetch daily log entries
  const refreshEntries = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    try {
      const data = await fetchDailyLog(user.id, dateStr);
      setEntries(data);
    } catch (err) {
      console.error('Failed to fetch daily log:', err);
      toast({ variant: 'destructive', title: 'Erreur', description: 'Impossible de charger le journal.' });
    } finally {
      setLoading(false);
    }
  }, [user, dateStr, toast]);

  useEffect(() => {
    refreshEntries();
  }, [refreshEntries]);

  // Fetch active meal plan + match day
  useEffect(() => {
    if (!user) return;
    const fetchPlan = async () => {
      setPlanLoading(true);
      try {
        const plans = await fetchMealPlans(user.id);
        if (plans.length === 0) {
          setPlanDayMeals([]);
          setActivePlanId(null);
          return;
        }
        // Take the most recent plan
        const latest = plans[0];
        setActivePlanId(latest.id);

        const detail = await apiFetch<MealPlanDetail>(`/api/meal-plans/${latest.id}`);
        const weekday = format(selectedDate, 'EEEE', { locale: fr }); // e.g. "lundi"
        const matchedDay = detail.plan_data.days.find(
          (d) => (FRENCH_DAYS[d.day] ?? d.day.toLowerCase()) === weekday,
        );
        setPlanDayMeals(matchedDay?.meals ?? []);
      } catch (err) {
        console.error('Failed to fetch meal plan:', err);
        setPlanDayMeals([]);
        setActivePlanId(null);
      } finally {
        setPlanLoading(false);
      }
    };
    fetchPlan();
  }, [user, selectedDate]);

  // Computed totals
  const totals: NutritionTotals = entries.reduce(
    (acc, e) => ({
      calories: acc.calories + (e.calories ?? 0),
      protein_g: acc.protein_g + (e.protein_g ?? 0),
      carbs_g: acc.carbs_g + (e.carbs_g ?? 0),
      fat_g: acc.fat_g + (e.fat_g ?? 0),
    }),
    { calories: 0, protein_g: 0, carbs_g: 0, fat_g: 0 },
  );

  // Group entries by meal_type
  const groupedEntries: Record<MealType, DailyFoodLog[]> = {
    'petit-dejeuner': [],
    dejeuner: [],
    diner: [],
    collation: [],
  };
  for (const entry of entries) {
    const mt = entry.meal_type as MealType;
    if (mt in groupedEntries) {
      groupedEntries[mt].push(entry);
    } else {
      groupedEntries.collation.push(entry);
    }
  }

  // Delete entry
  const deleteEntry = useCallback(
    async (id: string) => {
      try {
        await deleteDailyLogEntry(id);
        await refreshEntries();
        toast({ title: 'Supprimé', description: 'Entrée supprimée.' });
      } catch (err) {
        console.error('Failed to delete entry:', err);
        toast({ variant: 'destructive', title: 'Erreur', description: 'Impossible de supprimer.' });
      }
    },
    [refreshEntries, toast],
  );

  // Log a meal from the plan
  const logPlanMeal = useCallback(
    async (meal: PlanMeal) => {
      if (!user || !activePlanId) return;

      const entry: DailyFoodLogInsert = {
        user_id: user.id,
        log_date: dateStr,
        meal_type: normalizeMealType(meal.meal_type),
        food_name: meal.name,
        calories: Math.round(meal.nutrition.calories),
        protein_g: Math.round(meal.nutrition.protein_g * 10) / 10,
        carbs_g: Math.round(meal.nutrition.carbs_g * 10) / 10,
        fat_g: Math.round(meal.nutrition.fat_g * 10) / 10,
        source: 'plan_validation',
        meal_plan_id: activePlanId,
      };

      try {
        await createDailyLogEntry(entry);
        await refreshEntries();
        toast({ title: 'Ajouté', description: `${meal.name} enregistré.` });
      } catch (err) {
        console.error('Failed to log plan meal:', err);
        toast({ variant: 'destructive', title: 'Erreur', description: "Impossible d'enregistrer le repas." });
      }
    },
    [user, activePlanId, dateStr, refreshEntries, toast],
  );

  // Check if a plan meal is already logged
  const isPlanMealLogged = useCallback(
    (meal: PlanMeal): boolean => {
      const expectedType = normalizeMealType(meal.meal_type);
      return entries.some(
        (e) => e.meal_plan_id === activePlanId && e.food_name === meal.name && e.meal_type === expectedType,
      );
    },
    [entries, activePlanId],
  );

  return {
    selectedDate,
    dateStr,
    isSelectedToday,
    goToPreviousDay,
    goToNextDay,
    goToToday,
    entries,
    targets,
    totals,
    groupedEntries,
    planDayMeals,
    activePlanId,
    loading,
    planLoading,
    deleteEntry,
    logPlanMeal,
    isPlanMealLogged,
    refreshEntries,
  };
}

export type { PlanMeal };
