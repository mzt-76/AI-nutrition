import React, { useMemo } from 'react';
import { UIComponentBlock, SemanticZone } from '@/types/generative-ui.types';
import { validateComponentProps } from './validateProps';
import { logger } from '@/lib/logger';
import { NutritionSummaryCard } from './components/NutritionSummaryCard';
import { MacroGauges } from './components/MacroGauges';
import { MealCard } from './components/MealCard';
import { DayPlanCard } from './components/DayPlanCard';
import { WeightTrendIndicator } from './components/WeightTrendIndicator';
import { AdjustmentCard } from './components/AdjustmentCard';
import { QuickReplyChips } from './components/QuickReplyChips';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const COMPONENT_CATALOG: Record<string, React.FC<any>> = {
  NutritionSummaryCard,
  MacroGauges,
  MealCard,
  DayPlanCard,
  WeightTrendIndicator,
  AdjustmentCard,
  QuickReplyChips,
};

const ZONE_ORDER: SemanticZone[] = ['hero', 'macros', 'meals', 'progress', 'content', 'actions'];

function getZoneClassName(zone: SemanticZone): string {
  switch (zone) {
    case 'hero': return 'col-span-full';
    case 'macros': return 'col-span-full';
    case 'meals': return 'col-span-full md:col-span-6';
    case 'progress': return 'col-span-full md:col-span-6';
    case 'actions': return 'col-span-full';
    case 'content': return 'col-span-full';
    default: return 'col-span-full';
  }
}

interface ComponentRendererProps {
  components: UIComponentBlock[];
  onAction?: (value: string) => void;
  onMealClick?: (component: UIComponentBlock) => void;
}

export function ComponentRenderer({ components, onAction, onMealClick }: ComponentRendererProps) {
  const grouped = useMemo(() => {
    const g = new Map<SemanticZone, UIComponentBlock[]>();
    for (const comp of components) {
      const zone = comp.zone as SemanticZone;
      if (!g.has(zone)) g.set(zone, []);
      g.get(zone)!.push(comp);
    }
    return g;
  }, [components]);

  return (
    <div className="grid grid-cols-12 gap-3 mt-4">
      {ZONE_ORDER.map(zone => {
        const zoneComponents = grouped.get(zone);
        if (!zoneComponents?.length) return null;
        return zoneComponents.map(comp => {
          const Component = COMPONENT_CATALOG[comp.component];
          if (!Component) {
            logger.warn(`Unknown UI component: ${comp.component}`);
            return null;
          }
          const validatedProps = validateComponentProps(comp.component, comp.props);
          if (!validatedProps) {
            return null;
          }
          const extraProps: Record<string, unknown> = { onAction };
          if (comp.component === 'MealCard' && onMealClick) {
            extraProps.onClick = () => onMealClick(comp);
          }
          return (
            <div key={comp.id} className={getZoneClassName(zone)}>
              <Component {...validatedProps} {...extraProps} />
            </div>
          );
        });
      })}
    </div>
  );
}
