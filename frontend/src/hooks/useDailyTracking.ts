import { useState, useEffect, useCallback, useMemo } from 'react';
import { format, addDays, subDays, isToday } from 'date-fns';
import { fr } from 'date-fns/locale';
import { supabase } from '@/lib/supabase';
import { useAuth } from '@/hooks/useAuth';
import { useToast } from '@/hooks/use-toast';
import {
  fetchDailyLog,
  createDailyLogEntry,
  updateDailyLogEntry,
  deleteDailyLogEntry,
  fetchMealPlans,
  searchFood,
  apiFetch,
} from '@/lib/api';
import type { DailyFoodLog, DailyFoodLogInsert } from '@/types/database.types';
import { normalizeMealType, MEAL_LABELS } from '@/lib/meal-constants';
import type { MealType } from '@/lib/meal-constants';
import { logger } from '@/lib/logger';

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

// Re-export for backward compatibility
export type { MealType };
export { MEAL_LABELS as MEAL_TYPE_LABELS };

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
      const { data, error } = await supabase
        .from('user_profiles')
        .select('target_calories, target_protein_g, target_carbs_g, target_fat_g')
        .eq('id', user.id)
        .single();
      if (error || !data) return; // Use default targets already set in state
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
  const refreshEntries = useCallback(async (silent = false) => {
    if (!user) return;
    if (!silent) setLoading(true);
    try {
      const data = await fetchDailyLog(user.id, dateStr);
      setEntries(data);
    } catch (err) {
      logger.error('Failed to fetch daily log:', err);
      toast({ variant: 'destructive', title: 'Erreur', description: 'Impossible de charger le journal.' });
    } finally {
      if (!silent) setLoading(false);
    }
  }, [user, dateStr, toast]);

  useEffect(() => {
    const t = setTimeout(() => refreshEntries(), 300);
    return () => clearTimeout(t);
  }, [refreshEntries]);

  // Cache the full plan detail so we only fetch once (not on every date change)
  const [cachedPlanDetail, setCachedPlanDetail] = useState<MealPlanDetail | null>(null);

  // Fetch active meal plan (only when user changes)
  useEffect(() => {
    if (!user) return;
    let cancelled = false;

    const fetchPlan = async () => {
      setPlanLoading(true);
      try {
        const plans = await fetchMealPlans(user.id);
        if (cancelled) return;
        if (plans.length === 0) {
          setPlanDayMeals([]);
          setActivePlanId(null);
          setCachedPlanDetail(null);
          return;
        }
        const latest = plans[0];
        setActivePlanId(latest.id);

        const detail = await apiFetch<MealPlanDetail>(`/api/meal-plans/${latest.id}`);
        if (!cancelled) setCachedPlanDetail(detail);
      } catch (err) {
        logger.error('Failed to fetch meal plan:', err);
        if (!cancelled) {
          setPlanDayMeals([]);
          setActivePlanId(null);
          setCachedPlanDetail(null);
        }
      } finally {
        if (!cancelled) setPlanLoading(false);
      }
    };
    fetchPlan();
    return () => { cancelled = true; };
  }, [user]);

  // Match day from cached plan when date changes (no API call)
  useEffect(() => {
    if (!cachedPlanDetail) {
      setPlanDayMeals([]);
      return;
    }
    const weekday = format(selectedDate, 'EEEE', { locale: fr });
    const matchedDay = cachedPlanDetail.plan_data.days.find(
      (d) => (FRENCH_DAYS[d.day] ?? d.day.toLowerCase()) === weekday,
    );
    setPlanDayMeals(matchedDay?.meals ?? []);
  }, [selectedDate, cachedPlanDetail]);

  const totals: NutritionTotals = useMemo(() => entries.reduce(
    (acc, e) => ({
      calories: acc.calories + (e.calories ?? 0),
      protein_g: acc.protein_g + (e.protein_g ?? 0),
      carbs_g: acc.carbs_g + (e.carbs_g ?? 0),
      fat_g: acc.fat_g + (e.fat_g ?? 0),
    }),
    { calories: 0, protein_g: 0, carbs_g: 0, fat_g: 0 },
  ), [entries]);

  const groupedEntries: Record<MealType, DailyFoodLog[]> = useMemo(() => {
    const groups: Record<MealType, DailyFoodLog[]> = {
      'petit-dejeuner': [],
      dejeuner: [],
      diner: [],
      collation: [],
    };
    for (const entry of entries) {
      const mt = entry.meal_type as MealType;
      if (mt in groups) {
        groups[mt].push(entry);
      } else {
        groups.collation.push(entry);
      }
    }
    return groups;
  }, [entries]);

  // Delete entry
  const deleteEntry = useCallback(
    async (id: string) => {
      try {
        await deleteDailyLogEntry(id);
        await refreshEntries(true);
        toast({ title: 'Supprimé', description: 'Entrée supprimée.' });
      } catch (err) {
        logger.error('Failed to delete entry:', err);
        toast({ variant: 'destructive', title: 'Erreur', description: 'Impossible de supprimer.' });
      }
    },
    [refreshEntries, toast],
  );

  // Update entry quantity (recalculates macros proportionally)
  const updateEntryQuantity = useCallback(
    async (id: string, newQuantity: number) => {
      const entry = entries.find((e) => e.id === id);
      if (!entry || !entry.quantity || entry.quantity === 0) return;

      const ratio = newQuantity / entry.quantity;
      try {
        await updateDailyLogEntry(id, {
          quantity: newQuantity,
          calories: Math.round(entry.calories * ratio),
          protein_g: Math.round(entry.protein_g * ratio * 10) / 10,
          carbs_g: Math.round(entry.carbs_g * ratio * 10) / 10,
          fat_g: Math.round(entry.fat_g * ratio * 10) / 10,
        });
        await refreshEntries(true);
        toast({ title: 'Mis à jour', description: `Quantité modifiée à ${newQuantity}${entry.unit ?? 'g'}.` });
      } catch (err) {
        logger.error('Failed to update entry quantity:', err);
        toast({ variant: 'destructive', title: 'Erreur', description: 'Impossible de modifier la quantité.' });
      }
    },
    [entries, refreshEntries, toast],
  );

  // Update entry food name (backend recalculates macros)
  const updateEntryFood = useCallback(
    async (id: string, newName: string) => {
      try {
        await updateDailyLogEntry(id, { food_name: newName });
        await refreshEntries(true);
        toast({ title: 'Mis à jour', description: `Aliment modifié en ${newName}.` });
      } catch (err: unknown) {
        const msg =
          err instanceof Error && err.message?.includes('422')
            ? 'Aliment non trouvé dans la base.'
            : "Impossible de modifier l'aliment.";
        toast({ variant: 'destructive', title: 'Erreur', description: msg });
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
        await refreshEntries(true);
        toast({ title: 'Ajouté', description: `${meal.name} enregistré.` });
      } catch (err) {
        logger.error('Failed to log plan meal:', err);
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

  // Add a manual food entry by name (searches macros, creates log entry)
  const addManualEntry = useCallback(
    async (mealType: MealType, foodName: string) => {
      if (!user) return;

      const result = await searchFood(foodName, 100, 'g');

      const entry: DailyFoodLogInsert = {
        user_id: user.id,
        log_date: dateStr,
        meal_type: mealType,
        food_name: result.matched_name.toLowerCase(),
        calories: Math.round(result.calories),
        protein_g: Math.round(result.protein_g * 10) / 10,
        carbs_g: Math.round(result.carbs_g * 10) / 10,
        fat_g: Math.round(result.fat_g * 10) / 10,
        quantity: result.quantity,
        unit: result.unit,
        source: 'manual_entry',
      };

      await createDailyLogEntry(entry);
      await refreshEntries(true);
      toast({ title: 'Ajouté', description: `${result.matched_name.toLowerCase()} enregistré.` });
    },
    [user, dateStr, refreshEntries, toast],
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
    updateEntryQuantity,
    updateEntryFood,
    addManualEntry,
    logPlanMeal,
    isPlanMealLogged,
    refreshEntries,
  };
}

export type { PlanMeal };
