/**
 * Variety Enforcement Module
 *
 * Ensures diverse component selection in A2UI dashboards.
 * Enforces rules:
 * 1. Minimum 4 unique component types per dashboard
 * 2. No more than 2 consecutive components of the same type
 */

export interface ComponentSpec {
  type: string;
  id: string;
  props?: Record<string, any>;
  [key: string]: any;
}

export interface VarietyValidationResult {
  valid: boolean;
  uniqueTypesCount: number;
  maxConsecutiveSameType: number;
  meetsMinTypes: boolean;
  meetsNoConsecutive: boolean;
  violations: string[];
  componentTypeDistribution: Record<string, number>;
  consecutiveSequences?: ConsecutiveSequence[];
}

export interface ConsecutiveSequence {
  type: string;
  count: number;
  startIndex: number;
  endIndex: number;
}

/**
 * Variety enforcement rules
 */
export const VARIETY_RULES = {
  MIN_UNIQUE_TYPES: 4,
  MAX_CONSECUTIVE_SAME_TYPE: 2,
} as const;

/**
 * Validate component variety against enforcement rules.
 *
 * @param components - Array of component specifications
 * @returns Validation result with detailed statistics
 */
export function validateComponentVariety(
  components: ComponentSpec[]
): VarietyValidationResult {
  if (!components || components.length === 0) {
    return {
      valid: false,
      uniqueTypesCount: 0,
      maxConsecutiveSameType: 0,
      meetsMinTypes: false,
      meetsNoConsecutive: true,
      violations: ['No components provided'],
      componentTypeDistribution: {},
      consecutiveSequences: [],
    };
  }

  // Extract component types
  const componentTypes = components.map((c) => c.type);

  // Count unique types
  const uniqueTypes = new Set(componentTypes);
  const uniqueTypesCount = uniqueTypes.size;

  // Calculate component type distribution
  const componentTypeDistribution: Record<string, number> = {};
  componentTypes.forEach((type) => {
    componentTypeDistribution[type] = (componentTypeDistribution[type] || 0) + 1;
  });

  // Find consecutive sequences
  const consecutiveSequences: ConsecutiveSequence[] = [];
  let maxConsecutiveSameType = 1;
  let currentConsecutive = 1;
  let currentType = componentTypes[0];
  let startIndex = 0;

  for (let i = 1; i < componentTypes.length; i++) {
    if (componentTypes[i] === componentTypes[i - 1]) {
      currentConsecutive++;
      maxConsecutiveSameType = Math.max(maxConsecutiveSameType, currentConsecutive);
    } else {
      // Record sequence if > 1
      if (currentConsecutive > 1) {
        consecutiveSequences.push({
          type: currentType,
          count: currentConsecutive,
          startIndex,
          endIndex: i - 1,
        });
      }

      // Reset for new sequence
      currentType = componentTypes[i];
      currentConsecutive = 1;
      startIndex = i;
    }
  }

  // Record final sequence if > 1
  if (currentConsecutive > 1) {
    consecutiveSequences.push({
      type: currentType,
      count: currentConsecutive,
      startIndex,
      endIndex: componentTypes.length - 1,
    });
  }

  // Validation checks
  const meetsMinTypes = uniqueTypesCount >= VARIETY_RULES.MIN_UNIQUE_TYPES;
  const meetsNoConsecutive =
    maxConsecutiveSameType <= VARIETY_RULES.MAX_CONSECUTIVE_SAME_TYPE;

  // Build violations list
  const violations: string[] = [];
  if (!meetsMinTypes) {
    violations.push(
      `Only ${uniqueTypesCount} unique type(s), minimum required is ${VARIETY_RULES.MIN_UNIQUE_TYPES}`
    );
  }
  if (!meetsNoConsecutive) {
    violations.push(
      `Found ${maxConsecutiveSameType} consecutive same type, maximum allowed is ${VARIETY_RULES.MAX_CONSECUTIVE_SAME_TYPE}`
    );

    // Add details about problematic sequences
    consecutiveSequences
      .filter((seq) => seq.count > VARIETY_RULES.MAX_CONSECUTIVE_SAME_TYPE)
      .forEach((seq) => {
        violations.push(
          `  - ${seq.count} consecutive ${seq.type} components at positions ${seq.startIndex}-${seq.endIndex}`
        );
      });
  }

  return {
    valid: meetsMinTypes && meetsNoConsecutive,
    uniqueTypesCount,
    maxConsecutiveSameType,
    meetsMinTypes,
    meetsNoConsecutive,
    violations,
    componentTypeDistribution,
    consecutiveSequences,
  };
}

/**
 * Check if a component list would violate variety rules if a new component is added.
 *
 * @param existingComponents - Current component list
 * @param newComponentType - Type of component to add
 * @returns True if adding the component would violate rules
 */
export function wouldViolateVariety(
  existingComponents: ComponentSpec[],
  newComponentType: string
): boolean {
  if (existingComponents.length === 0) {
    return false;
  }

  // Check if adding would create 3+ consecutive
  const lastComponent = existingComponents[existingComponents.length - 1];
  if (lastComponent.type !== newComponentType) {
    return false; // Different type, no violation
  }

  // Count consecutive of same type at end
  let consecutiveCount = 1;
  for (let i = existingComponents.length - 1; i > 0; i--) {
    if (existingComponents[i].type === existingComponents[i - 1].type) {
      consecutiveCount++;
    } else {
      break;
    }
  }

  // Would adding one more exceed the limit?
  return consecutiveCount >= VARIETY_RULES.MAX_CONSECUTIVE_SAME_TYPE;
}

/**
 * Suggest component types to break up consecutive sequences.
 *
 * @param components - Current component list
 * @param availableTypes - Types that can be used
 * @returns Suggested type(s) to add, or null if no suggestion needed
 */
export function suggestDiverseType(
  components: ComponentSpec[],
  availableTypes: string[]
): string | null {
  if (components.length === 0) {
    return availableTypes[0] || null;
  }

  const lastType = components[components.length - 1].type;

  // Filter out the last type to ensure variety
  const differentTypes = availableTypes.filter((t) => t !== lastType);

  if (differentTypes.length === 0) {
    return null; // No alternatives available
  }

  // Count usage of each type to prefer less-used types
  const typeCounts: Record<string, number> = {};
  components.forEach((c) => {
    typeCounts[c.type] = (typeCounts[c.type] || 0) + 1;
  });

  // Find least-used type among different types
  let leastUsedType = differentTypes[0];
  let minCount = typeCounts[leastUsedType] || 0;

  differentTypes.forEach((type) => {
    const count = typeCounts[type] || 0;
    if (count < minCount) {
      minCount = count;
      leastUsedType = type;
    }
  });

  return leastUsedType;
}

/**
 * Get a formatted report of variety validation results.
 *
 * @param result - Validation result
 * @returns Human-readable report string
 */
export function formatVarietyReport(result: VarietyValidationResult): string {
  const lines: string[] = [];

  lines.push('=== Component Variety Validation Report ===\n');
  lines.push(`Status: ${result.valid ? '✓ VALID' : '✗ INVALID'}\n`);

  lines.push('--- Statistics ---');
  lines.push(`Unique Component Types: ${result.uniqueTypesCount} (min: ${VARIETY_RULES.MIN_UNIQUE_TYPES})`);
  lines.push(`Max Consecutive Same Type: ${result.maxConsecutiveSameType} (max: ${VARIETY_RULES.MAX_CONSECUTIVE_SAME_TYPE})`);
  lines.push(`Meets Min Types: ${result.meetsMinTypes ? '✓' : '✗'}`);
  lines.push(`Meets No Consecutive: ${result.meetsNoConsecutive ? '✓' : '✗'}\n`);

  lines.push('--- Component Type Distribution ---');
  Object.entries(result.componentTypeDistribution)
    .sort((a, b) => b[1] - a[1])
    .forEach(([type, count]) => {
      lines.push(`  ${type}: ${count}`);
    });

  if (result.consecutiveSequences && result.consecutiveSequences.length > 0) {
    lines.push('\n--- Consecutive Sequences ---');
    result.consecutiveSequences.forEach((seq) => {
      const status = seq.count > VARIETY_RULES.MAX_CONSECUTIVE_SAME_TYPE ? '✗' : '✓';
      lines.push(`  ${status} ${seq.count} × ${seq.type} (positions ${seq.startIndex}-${seq.endIndex})`);
    });
  }

  if (result.violations.length > 0) {
    lines.push('\n--- Violations ---');
    result.violations.forEach((violation) => {
      lines.push(`  ${violation}`);
    });
  }

  return lines.join('\n');
}
