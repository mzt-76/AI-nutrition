/**
 * A2UI Protocol Validator
 *
 * Validates A2UI component specifications against the A2UI protocol.
 * Ensures components conform to the expected structure and constraints.
 */

import type { A2UIComponent } from '@/lib/a2ui-catalog';
import { isComponentRegistered } from '@/lib/a2ui-catalog';

/**
 * Validation error types
 */
export const ValidationErrorType = {
  MISSING_REQUIRED_FIELD: 'MISSING_REQUIRED_FIELD',
  INVALID_TYPE: 'INVALID_TYPE',
  UNREGISTERED_TYPE: 'UNREGISTERED_TYPE',
  INVALID_PROPS: 'INVALID_PROPS',
  NON_SERIALIZABLE_PROP: 'NON_SERIALIZABLE_PROP',
  CIRCULAR_REFERENCE: 'CIRCULAR_REFERENCE',
  INVALID_CHILDREN: 'INVALID_CHILDREN',
  MISSING_KEY: 'MISSING_KEY',
  DUPLICATE_KEY: 'DUPLICATE_KEY',
  INVALID_LAYOUT: 'INVALID_LAYOUT',
  INVALID_STYLING: 'INVALID_STYLING',
} as const;

export type ValidationErrorType = typeof ValidationErrorType[keyof typeof ValidationErrorType];

/**
 * Validation error
 */
export interface ValidationError {
  type: ValidationErrorType;
  message: string;
  path: string;
  component?: A2UIComponent;
}

/**
 * Validation result
 */
export interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
  warnings: ValidationError[];
  stats: {
    totalComponents: number;
    uniqueTypes: Set<string>;
    maxDepth: number;
    totalProps: number;
  };
}

/**
 * Validation options
 */
export interface ValidationOptions {
  /**
   * Check if component types are registered in catalog
   */
  checkRegistration?: boolean;

  /**
   * Maximum allowed nesting depth
   */
  maxDepth?: number;

  /**
   * Allow unregistered component types (warning instead of error)
   */
  allowUnregistered?: boolean;

  /**
   * Check for circular references
   */
  checkCircular?: boolean;

  /**
   * Strict mode: enforce all optional validations
   */
  strict?: boolean;
}

const DEFAULT_OPTIONS: ValidationOptions = {
  checkRegistration: true,
  maxDepth: 10,
  allowUnregistered: false,
  checkCircular: true,
  strict: false,
};

/**
 * Check if a value is serializable (no functions, undefined, symbols)
 */
function isSerializable(value: any): boolean {
  if (value === null) return true;

  const type = typeof value;

  // Primitives are serializable
  if (['string', 'number', 'boolean'].includes(type)) {
    return true;
  }

  // Functions, undefined, symbols are not serializable
  if (['function', 'undefined', 'symbol'].includes(type)) {
    return false;
  }

  // Arrays: check all elements
  if (Array.isArray(value)) {
    return value.every(isSerializable);
  }

  // Objects: check all values
  if (type === 'object') {
    return Object.values(value).every(isSerializable);
  }

  return false;
}

/**
 * Check for circular references in component tree
 */
function hasCircularReference(
  component: A2UIComponent,
  visited: Set<string> = new Set()
): boolean {
  if (visited.has(component.id)) {
    return true;
  }

  visited.add(component.id);

  if (component.children) {
    for (const child of component.children) {
      if (hasCircularReference(child, new Set(visited))) {
        return true;
      }
    }
  }

  return false;
}

/**
 * Validate a single A2UI component
 */
function validateComponent(
  component: any,
  path: string,
  options: Required<ValidationOptions>,
  errors: ValidationError[],
  warnings: ValidationError[],
  stats: ValidationResult['stats'],
  depth: number = 0,
  seenKeys: Set<string> = new Set()
): void {
  stats.totalComponents++;
  stats.maxDepth = Math.max(stats.maxDepth, depth);

  // Check depth limit
  if (depth > options.maxDepth) {
    errors.push({
      type: ValidationErrorType.INVALID_CHILDREN,
      message: `Component nesting exceeds maximum depth of ${options.maxDepth}`,
      path,
    });
    return;
  }

  // Validate required field: id
  if (!component.id || typeof component.id !== 'string') {
    errors.push({
      type: ValidationErrorType.MISSING_REQUIRED_FIELD,
      message: 'Component must have a valid "id" field (string)',
      path,
      component,
    });
  } else {
    // Check for duplicate keys
    if (seenKeys.has(component.id)) {
      errors.push({
        type: ValidationErrorType.DUPLICATE_KEY,
        message: `Duplicate component id: "${component.id}"`,
        path,
        component,
      });
    }
    seenKeys.add(component.id);
  }

  // Validate required field: type
  if (!component.type || typeof component.type !== 'string') {
    errors.push({
      type: ValidationErrorType.MISSING_REQUIRED_FIELD,
      message: 'Component must have a valid "type" field (string)',
      path,
      component,
    });
  } else {
    stats.uniqueTypes.add(component.type);

    // Check if type follows a2ui.* convention
    if (!component.type.startsWith('a2ui.')) {
      warnings.push({
        type: ValidationErrorType.INVALID_TYPE,
        message: `Component type "${component.type}" does not follow a2ui.* naming convention`,
        path,
        component,
      });
    }

    // Check if type is registered in catalog
    if (options.checkRegistration) {
      if (!isComponentRegistered(component.type)) {
        const error: ValidationError = {
          type: ValidationErrorType.UNREGISTERED_TYPE,
          message: `Component type "${component.type}" is not registered in the catalog`,
          path,
          component,
        };

        if (options.allowUnregistered) {
          warnings.push(error);
        } else {
          errors.push(error);
        }
      }
    }
  }

  // Validate required field: props
  if (component.props === undefined || component.props === null) {
    errors.push({
      type: ValidationErrorType.MISSING_REQUIRED_FIELD,
      message: 'Component must have a "props" field',
      path,
      component,
    });
  } else if (typeof component.props !== 'object' || Array.isArray(component.props)) {
    errors.push({
      type: ValidationErrorType.INVALID_PROPS,
      message: 'Component "props" must be an object',
      path,
      component,
    });
  } else {
    stats.totalProps += Object.keys(component.props).length;

    // Check if props are serializable
    for (const [key, value] of Object.entries(component.props)) {
      if (!isSerializable(value)) {
        errors.push({
          type: ValidationErrorType.NON_SERIALIZABLE_PROP,
          message: `Prop "${key}" contains non-serializable value (function, undefined, or symbol)`,
          path: `${path}.props.${key}`,
          component,
        });
      }
    }
  }

  // Validate optional field: children
  if (component.children !== undefined) {
    if (!Array.isArray(component.children)) {
      errors.push({
        type: ValidationErrorType.INVALID_CHILDREN,
        message: 'Component "children" must be an array',
        path,
        component,
      });
    } else {
      component.children.forEach((child: any, index: number) => {
        validateComponent(
          child,
          `${path}.children[${index}]`,
          options,
          errors,
          warnings,
          stats,
          depth + 1,
          seenKeys
        );
      });
    }
  }

  // Validate optional field: layout
  if (component.layout !== undefined) {
    if (typeof component.layout !== 'object' || Array.isArray(component.layout)) {
      errors.push({
        type: ValidationErrorType.INVALID_LAYOUT,
        message: 'Component "layout" must be an object',
        path,
        component,
      });
    } else {
      const validPositions = ['relative', 'absolute', 'fixed', 'sticky'];
      if (
        component.layout.position !== undefined &&
        !validPositions.includes(component.layout.position)
      ) {
        errors.push({
          type: ValidationErrorType.INVALID_LAYOUT,
          message: `Invalid layout.position value: "${component.layout.position}". Must be one of: ${validPositions.join(', ')}`,
          path: `${path}.layout.position`,
          component,
        });
      }
    }
  }

  // Validate optional field: styling
  if (component.styling !== undefined) {
    if (typeof component.styling !== 'object' || Array.isArray(component.styling)) {
      errors.push({
        type: ValidationErrorType.INVALID_STYLING,
        message: 'Component "styling" must be an object',
        path,
        component,
      });
    }
  }
}

/**
 * Validate an A2UI component tree
 *
 * @param component - Root component to validate
 * @param options - Validation options
 * @returns Validation result with errors, warnings, and stats
 */
export function validateA2UIComponent(
  component: any,
  options: ValidationOptions = {}
): ValidationResult {
  const opts = {
    ...DEFAULT_OPTIONS,
    ...options,
  } as Required<ValidationOptions>;

  const errors: ValidationError[] = [];
  const warnings: ValidationError[] = [];
  const stats: ValidationResult['stats'] = {
    totalComponents: 0,
    uniqueTypes: new Set(),
    maxDepth: 0,
    totalProps: 0,
  };

  // Check for circular references
  if (opts.checkCircular && hasCircularReference(component)) {
    errors.push({
      type: ValidationErrorType.CIRCULAR_REFERENCE,
      message: 'Component tree contains circular references',
      path: 'root',
      component,
    });
  }

  // Validate component tree
  validateComponent(component, 'root', opts, errors, warnings, stats, 0);

  return {
    valid: errors.length === 0,
    errors,
    warnings,
    stats,
  };
}

/**
 * Validate multiple A2UI components
 *
 * @param components - Array of components to validate
 * @param options - Validation options
 * @returns Validation result for all components
 */
export function validateA2UIComponents(
  components: any[],
  options: ValidationOptions = {}
): ValidationResult {
  if (!Array.isArray(components)) {
    return {
      valid: false,
      errors: [
        {
          type: ValidationErrorType.INVALID_TYPE,
          message: 'Input must be an array of components',
          path: 'root',
        },
      ],
      warnings: [],
      stats: {
        totalComponents: 0,
        uniqueTypes: new Set(),
        maxDepth: 0,
        totalProps: 0,
      },
    };
  }

  const opts = {
    ...DEFAULT_OPTIONS,
    ...options,
  } as Required<ValidationOptions>;

  const errors: ValidationError[] = [];
  const warnings: ValidationError[] = [];
  const stats: ValidationResult['stats'] = {
    totalComponents: 0,
    uniqueTypes: new Set(),
    maxDepth: 0,
    totalProps: 0,
  };

  const globalSeenKeys = new Set<string>();

  components.forEach((component, index) => {
    validateComponent(
      component,
      `components[${index}]`,
      opts,
      errors,
      warnings,
      stats,
      0,
      globalSeenKeys
    );
  });

  return {
    valid: errors.length === 0,
    errors,
    warnings,
    stats,
  };
}

/**
 * Format validation result as a readable string
 */
export function formatValidationResult(result: ValidationResult): string {
  const lines: string[] = [];

  lines.push('=== A2UI Validation Result ===\n');
  lines.push(`Status: ${result.valid ? '✓ VALID' : '✗ INVALID'}\n`);
  lines.push(`Total Components: ${result.stats.totalComponents}`);
  lines.push(`Unique Types: ${result.stats.uniqueTypes.size}`);
  lines.push(`Max Depth: ${result.stats.maxDepth}`);
  lines.push(`Total Props: ${result.stats.totalProps}\n`);

  if (result.errors.length > 0) {
    lines.push(`\n--- Errors (${result.errors.length}) ---`);
    result.errors.forEach((error, index) => {
      lines.push(`\n${index + 1}. [${error.type}] ${error.path}`);
      lines.push(`   ${error.message}`);
    });
  }

  if (result.warnings.length > 0) {
    lines.push(`\n--- Warnings (${result.warnings.length}) ---`);
    result.warnings.forEach((warning, index) => {
      lines.push(`\n${index + 1}. [${warning.type}] ${warning.path}`);
      lines.push(`   ${warning.message}`);
    });
  }

  return lines.join('\n');
}

/**
 * Quick validation check - returns true if valid
 */
export function isValidA2UIComponent(component: any): boolean {
  return validateA2UIComponent(component, { checkRegistration: false }).valid;
}

/**
 * Get validation summary
 */
export function getValidationSummary(result: ValidationResult): {
  valid: boolean;
  errorCount: number;
  warningCount: number;
  componentCount: number;
  typeCount: number;
} {
  return {
    valid: result.valid,
    errorCount: result.errors.length,
    warningCount: result.warnings.length,
    componentCount: result.stats.totalComponents,
    typeCount: result.stats.uniqueTypes.size,
  };
}
