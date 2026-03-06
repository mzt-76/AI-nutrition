export type SemanticZone = 'hero' | 'macros' | 'meals' | 'progress' | 'actions' | 'content';

export interface UIComponentBlock {
  id: string;
  component: string;
  props: Record<string, unknown>;
  zone: SemanticZone;
}

export interface NutritionSummaryCardProps {
  bmr: number;
  tdee: number;
  target_calories: number;
  primary_goal: string;
  rationale?: string;
}

export interface MacroGaugesProps {
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  target_calories: number;
}

export interface MealCardProps {
  meal_type: string;
  recipe_name: string;
  calories: number;
  macros: { protein_g: number; carbs_g: number; fat_g: number };
  prep_time?: number;
  ingredients?: string[];
  onClick?: () => void;
}

export interface DayPlanCardProps {
  day_name: string;
  meals: MealCardProps[];
  totals: { calories: number; protein_g: number; carbs_g: number; fat_g: number };
  onMealClick?: (mealIndex: number) => void;
}

export interface WeightTrendIndicatorProps {
  weight_start: number;
  weight_end: number;
  trend: 'up' | 'down' | 'stable';
  rate: number;
}

export interface AdjustmentCardProps {
  calorie_adjustment: number;
  new_target: number;
  reason: string;
  red_flags?: string[];
}

export interface QuickReplyChipsProps {
  options: Array<{ label: string; value: string }>;
  onAction?: (value: string) => void;
}
