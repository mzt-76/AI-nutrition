import { z } from 'zod';

const NutritionSummaryCardSchema = z.object({
  bmr: z.number(),
  tdee: z.number(),
  target_calories: z.number(),
  primary_goal: z.string(),
  rationale: z.string().optional(),
});

const MacroGaugesSchema = z.object({
  protein_g: z.number(),
  carbs_g: z.number(),
  fat_g: z.number(),
  target_calories: z.number(),
});

const MacrosSchema = z.object({
  protein_g: z.number(),
  carbs_g: z.number(),
  fat_g: z.number(),
});

const MealCardSchema = z.object({
  meal_type: z.string(),
  recipe_name: z.string(),
  calories: z.number(),
  macros: MacrosSchema,
  prep_time: z.number().optional(),
  ingredients: z.array(z.string()).optional(),
  instructions: z.string().optional(),
});

const DayPlanCardSchema = z.object({
  day_name: z.string(),
  meals: z.array(MealCardSchema),
  totals: z.object({
    calories: z.number(),
    protein_g: z.number(),
    carbs_g: z.number(),
    fat_g: z.number(),
  }),
});

const WeightTrendIndicatorSchema = z.object({
  weight_start: z.number(),
  weight_end: z.number(),
  trend: z.enum(['up', 'down', 'stable']),
  rate: z.number(),
});

const AdjustmentCardSchema = z.object({
  calorie_adjustment: z.number(),
  new_target: z.number(),
  reason: z.string(),
  red_flags: z.array(z.string()).optional(),
});

const QuickReplyChipsSchema = z.object({
  options: z.array(z.object({ label: z.string(), value: z.string() })),
});

const PROP_SCHEMAS: Record<string, z.ZodSchema> = {
  NutritionSummaryCard: NutritionSummaryCardSchema,
  MacroGauges: MacroGaugesSchema,
  MealCard: MealCardSchema,
  DayPlanCard: DayPlanCardSchema,
  WeightTrendIndicator: WeightTrendIndicatorSchema,
  AdjustmentCard: AdjustmentCardSchema,
  QuickReplyChips: QuickReplyChipsSchema,
};

/**
 * Validate and sanitize LLM-provided props against the known schema.
 * Returns validated props on success, null on failure.
 */
export function validateComponentProps(
  componentName: string,
  props: Record<string, unknown>
): Record<string, unknown> | null {
  const schema = PROP_SCHEMAS[componentName];
  if (!schema) {
    console.warn(`No schema for component: ${componentName}`);
    return null;
  }

  const result = schema.safeParse(props);
  if (!result.success) {
    console.warn(`Invalid props for ${componentName}:`, result.error.issues);
    return null;
  }

  return result.data as Record<string, unknown>;
}
