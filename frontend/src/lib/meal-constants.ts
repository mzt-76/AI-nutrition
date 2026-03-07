import { Coffee, Sun, Moon, Cookie } from 'lucide-react';

export const MEAL_TYPE_ORDER = ['petit-dejeuner', 'dejeuner', 'diner', 'collation'] as const;
export type MealType = (typeof MEAL_TYPE_ORDER)[number];

export const MEAL_ICONS: Record<MealType, typeof Coffee> = {
  'petit-dejeuner': Coffee,
  dejeuner: Sun,
  diner: Moon,
  collation: Cookie,
};

export const MEAL_LABELS: Record<MealType, string> = {
  'petit-dejeuner': 'Petit-déjeuner',
  dejeuner: 'Déjeuner',
  diner: 'Dîner',
  collation: 'Collation',
};

export const MEAL_ACCENT: Record<MealType, string> = {
  'petit-dejeuner': 'text-amber-400/70',
  dejeuner: 'text-orange-400/70',
  diner: 'text-indigo-400/70',
  collation: 'text-emerald-400/70',
};

/** Normalize a display meal_type string (e.g. "Petit-déjeuner", "Collation AM") to a DB key. */
export function normalizeMealType(raw: string): MealType {
  const s = raw.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  if (s.startsWith('petit')) return 'petit-dejeuner';
  if (s.startsWith('dejeuner') || s.startsWith('déjeuner') || s === 'lunch') return 'dejeuner';
  if (s.startsWith('din') || s.startsWith('dîn') || s === 'dinner') return 'diner';
  return 'collation';
}

export function formatMealTypeFallback(raw: string): string {
  return raw.replace(/_/g, ' ').toLowerCase().replace(/^./, (c) => c.toUpperCase());
}
