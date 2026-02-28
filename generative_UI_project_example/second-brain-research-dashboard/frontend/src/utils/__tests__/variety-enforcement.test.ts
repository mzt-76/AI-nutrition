/**
 * Variety Enforcement Tests
 *
 * Comprehensive test suite for component variety enforcement.
 * Tests cover:
 * - Minimum 4 unique component types requirement
 * - Maximum 2 consecutive same type constraint
 * - Edge cases and real-world scenarios
 */

import { describe, it, expect } from 'vitest';
import {
  validateComponentVariety,
  wouldViolateVariety,
  suggestDiverseType,
  formatVarietyReport,
  VARIETY_RULES,
  type ComponentSpec,
} from '../variety-enforcement';

describe('Variety Enforcement - validateComponentVariety', () => {
  describe('Valid Cases', () => {
    it('should pass with 4+ unique types and no 3+ consecutive', () => {
      const components: ComponentSpec[] = [
        { type: 'a2ui.TLDR', id: 'tldr-1' },
        { type: 'a2ui.StatCard', id: 'stat-1' },
        { type: 'a2ui.HeadlineCard', id: 'headline-1' },
        { type: 'a2ui.VideoCard', id: 'video-1' },
        { type: 'a2ui.StatCard', id: 'stat-2' },
      ];

      const result = validateComponentVariety(components);

      expect(result.valid).toBe(true);
      expect(result.uniqueTypesCount).toBe(4);
      expect(result.maxConsecutiveSameType).toBe(1);
      expect(result.meetsMinTypes).toBe(true);
      expect(result.meetsNoConsecutive).toBe(true);
      expect(result.violations).toHaveLength(0);
    });

    it('should pass with exactly 2 consecutive of same type', () => {
      const components: ComponentSpec[] = [
        { type: 'a2ui.TLDR', id: 'tldr-1' },
        { type: 'a2ui.StatCard', id: 'stat-1' },
        { type: 'a2ui.StatCard', id: 'stat-2' }, // 2 consecutive - allowed
        { type: 'a2ui.HeadlineCard', id: 'headline-1' },
        { type: 'a2ui.VideoCard', id: 'video-1' },
      ];

      const result = validateComponentVariety(components);

      expect(result.valid).toBe(true);
      expect(result.uniqueTypesCount).toBe(4);
      expect(result.maxConsecutiveSameType).toBe(2);
      expect(result.meetsNoConsecutive).toBe(true);
      expect(result.violations).toHaveLength(0);
    });

    it('should pass with 10+ unique types and varied distribution', () => {
      const components: ComponentSpec[] = [
        { type: 'a2ui.TLDR', id: '1' },
        { type: 'a2ui.StatCard', id: '2' },
        { type: 'a2ui.HeadlineCard', id: '3' },
        { type: 'a2ui.VideoCard', id: '4' },
        { type: 'a2ui.ProfileCard', id: '5' },
        { type: 'a2ui.CompanyCard', id: '6' },
        { type: 'a2ui.QuoteCard', id: '7' },
        { type: 'a2ui.LinkCard', id: '8' },
        { type: 'a2ui.CodeBlock', id: '9' },
        { type: 'a2ui.TableOfContents', id: '10' },
      ];

      const result = validateComponentVariety(components);

      expect(result.valid).toBe(true);
      expect(result.uniqueTypesCount).toBe(10);
      expect(result.violations).toHaveLength(0);
    });

    it('should handle complex patterns with multiple 2-consecutive sequences', () => {
      const components: ComponentSpec[] = [
        { type: 'a2ui.StatCard', id: 's1' },
        { type: 'a2ui.StatCard', id: 's2' }, // 2 consecutive
        { type: 'a2ui.HeadlineCard', id: 'h1' },
        { type: 'a2ui.HeadlineCard', id: 'h2' }, // 2 consecutive
        { type: 'a2ui.VideoCard', id: 'v1' },
        { type: 'a2ui.VideoCard', id: 'v2' }, // 2 consecutive
        { type: 'a2ui.ProfileCard', id: 'p1' },
      ];

      const result = validateComponentVariety(components);

      expect(result.valid).toBe(true);
      expect(result.uniqueTypesCount).toBe(4);
      expect(result.maxConsecutiveSameType).toBe(2);
      expect(result.consecutiveSequences).toHaveLength(3);
    });
  });

  describe('Invalid Cases - Insufficient Types', () => {
    it('should fail with only 1 unique type', () => {
      const components: ComponentSpec[] = [
        { type: 'a2ui.StatCard', id: 'stat-1' },
        { type: 'a2ui.StatCard', id: 'stat-2' },
      ];

      const result = validateComponentVariety(components);

      expect(result.valid).toBe(false);
      expect(result.uniqueTypesCount).toBe(1);
      expect(result.meetsMinTypes).toBe(false);
      expect(result.violations).toContain(
        `Only 1 unique type(s), minimum required is ${VARIETY_RULES.MIN_UNIQUE_TYPES}`
      );
    });

    it('should fail with only 2 unique types', () => {
      const components: ComponentSpec[] = [
        { type: 'a2ui.StatCard', id: 's1' },
        { type: 'a2ui.HeadlineCard', id: 'h1' },
        { type: 'a2ui.StatCard', id: 's2' },
      ];

      const result = validateComponentVariety(components);

      expect(result.valid).toBe(false);
      expect(result.uniqueTypesCount).toBe(2);
      expect(result.meetsMinTypes).toBe(false);
    });

    it('should fail with only 3 unique types', () => {
      const components: ComponentSpec[] = [
        { type: 'a2ui.TLDR', id: '1' },
        { type: 'a2ui.StatCard', id: '2' },
        { type: 'a2ui.HeadlineCard', id: '3' },
        { type: 'a2ui.StatCard', id: '4' },
      ];

      const result = validateComponentVariety(components);

      expect(result.valid).toBe(false);
      expect(result.uniqueTypesCount).toBe(3);
      expect(result.meetsMinTypes).toBe(false);
    });
  });

  describe('Invalid Cases - Too Many Consecutive', () => {
    it('should fail with 3 consecutive same type', () => {
      const components: ComponentSpec[] = [
        { type: 'a2ui.TLDR', id: '1' },
        { type: 'a2ui.StatCard', id: 's1' },
        { type: 'a2ui.StatCard', id: 's2' },
        { type: 'a2ui.StatCard', id: 's3' }, // 3 consecutive - violation!
        { type: 'a2ui.HeadlineCard', id: 'h1' },
        { type: 'a2ui.VideoCard', id: 'v1' },
      ];

      const result = validateComponentVariety(components);

      expect(result.valid).toBe(false);
      expect(result.maxConsecutiveSameType).toBe(3);
      expect(result.meetsNoConsecutive).toBe(false);
      expect(result.violations).toContain(
        `Found 3 consecutive same type, maximum allowed is ${VARIETY_RULES.MAX_CONSECUTIVE_SAME_TYPE}`
      );
    });

    it('should fail with 5 consecutive same type', () => {
      const components: ComponentSpec[] = [
        { type: 'a2ui.TLDR', id: '1' },
        { type: 'a2ui.StatCard', id: 's1' },
        { type: 'a2ui.StatCard', id: 's2' },
        { type: 'a2ui.StatCard', id: 's3' },
        { type: 'a2ui.StatCard', id: 's4' },
        { type: 'a2ui.StatCard', id: 's5' }, // 5 consecutive!
        { type: 'a2ui.HeadlineCard', id: 'h1' },
        { type: 'a2ui.VideoCard', id: 'v1' },
      ];

      const result = validateComponentVariety(components);

      expect(result.valid).toBe(false);
      expect(result.maxConsecutiveSameType).toBe(5);
      expect(result.consecutiveSequences?.[0]).toMatchObject({
        type: 'a2ui.StatCard',
        count: 5,
        startIndex: 1,
        endIndex: 5,
      });
    });

    it('should fail with all components of same type', () => {
      const components: ComponentSpec[] = [
        { type: 'a2ui.StatCard', id: 's1' },
        { type: 'a2ui.StatCard', id: 's2' },
        { type: 'a2ui.StatCard', id: 's3' },
        { type: 'a2ui.StatCard', id: 's4' },
        { type: 'a2ui.StatCard', id: 's5' },
      ];

      const result = validateComponentVariety(components);

      expect(result.valid).toBe(false);
      expect(result.uniqueTypesCount).toBe(1);
      expect(result.maxConsecutiveSameType).toBe(5);
      expect(result.violations.length).toBeGreaterThanOrEqual(2); // At least 2 violations (may include detail lines)
      expect(result.violations.some(v => v.includes('unique type'))).toBe(true);
      expect(result.violations.some(v => v.includes('consecutive'))).toBe(true);
    });
  });

  describe('Invalid Cases - Both Rules Violated', () => {
    it('should fail when both min types and consecutive rules are violated', () => {
      const components: ComponentSpec[] = [
        { type: 'a2ui.StatCard', id: 's1' },
        { type: 'a2ui.StatCard', id: 's2' },
        { type: 'a2ui.StatCard', id: 's3' }, // 3 consecutive
        { type: 'a2ui.HeadlineCard', id: 'h1' },
        { type: 'a2ui.StatCard', id: 's4' },
      ];

      const result = validateComponentVariety(components);

      expect(result.valid).toBe(false);
      expect(result.uniqueTypesCount).toBe(2); // Only 2 types
      expect(result.maxConsecutiveSameType).toBe(3); // 3 consecutive
      expect(result.meetsMinTypes).toBe(false);
      expect(result.meetsNoConsecutive).toBe(false);
      expect(result.violations.length).toBeGreaterThanOrEqual(2);
    });
  });

  describe('Edge Cases', () => {
    it('should handle empty component list', () => {
      const result = validateComponentVariety([]);

      expect(result.valid).toBe(false);
      expect(result.uniqueTypesCount).toBe(0);
      expect(result.violations).toContain('No components provided');
    });

    it('should handle single component', () => {
      const components: ComponentSpec[] = [
        { type: 'a2ui.TLDR', id: 'tldr-1' },
      ];

      const result = validateComponentVariety(components);

      expect(result.valid).toBe(false);
      expect(result.uniqueTypesCount).toBe(1);
      expect(result.maxConsecutiveSameType).toBe(1);
      expect(result.meetsMinTypes).toBe(false);
      expect(result.meetsNoConsecutive).toBe(true); // Single component doesn't violate consecutive
    });

    it('should handle exactly 4 unique types (boundary)', () => {
      const components: ComponentSpec[] = [
        { type: 'a2ui.TLDR', id: '1' },
        { type: 'a2ui.StatCard', id: '2' },
        { type: 'a2ui.HeadlineCard', id: '3' },
        { type: 'a2ui.VideoCard', id: '4' },
      ];

      const result = validateComponentVariety(components);

      expect(result.valid).toBe(true);
      expect(result.uniqueTypesCount).toBe(4); // Exactly at boundary
      expect(result.meetsMinTypes).toBe(true);
    });

    it('should handle consecutive at the end of list', () => {
      const components: ComponentSpec[] = [
        { type: 'a2ui.TLDR', id: '1' },
        { type: 'a2ui.StatCard', id: '2' },
        { type: 'a2ui.HeadlineCard', id: '3' },
        { type: 'a2ui.VideoCard', id: 'v1' },
        { type: 'a2ui.VideoCard', id: 'v2' },
        { type: 'a2ui.VideoCard', id: 'v3' }, // 3 consecutive at end
      ];

      const result = validateComponentVariety(components);

      expect(result.valid).toBe(false);
      expect(result.maxConsecutiveSameType).toBe(3);
      expect(result.consecutiveSequences?.[0].endIndex).toBe(5);
    });

    it('should handle consecutive at the beginning of list', () => {
      const components: ComponentSpec[] = [
        { type: 'a2ui.StatCard', id: 's1' },
        { type: 'a2ui.StatCard', id: 's2' },
        { type: 'a2ui.StatCard', id: 's3' }, // 3 consecutive at start
        { type: 'a2ui.TLDR', id: '1' },
        { type: 'a2ui.HeadlineCard', id: '3' },
        { type: 'a2ui.VideoCard', id: 'v1' },
      ];

      const result = validateComponentVariety(components);

      expect(result.valid).toBe(false);
      expect(result.consecutiveSequences?.[0].startIndex).toBe(0);
    });
  });

  describe('Component Type Distribution', () => {
    it('should correctly count component type distribution', () => {
      const components: ComponentSpec[] = [
        { type: 'a2ui.StatCard', id: 's1' },
        { type: 'a2ui.StatCard', id: 's2' },
        { type: 'a2ui.HeadlineCard', id: 'h1' },
        { type: 'a2ui.VideoCard', id: 'v1' },
        { type: 'a2ui.VideoCard', id: 'v2' },
        { type: 'a2ui.VideoCard', id: 'v3' },
        { type: 'a2ui.ProfileCard', id: 'p1' },
      ];

      const result = validateComponentVariety(components);

      expect(result.componentTypeDistribution).toEqual({
        'a2ui.StatCard': 2,
        'a2ui.HeadlineCard': 1,
        'a2ui.VideoCard': 3,
        'a2ui.ProfileCard': 1,
      });
    });
  });

  describe('Consecutive Sequences Tracking', () => {
    it('should identify all consecutive sequences', () => {
      const components: ComponentSpec[] = [
        { type: 'a2ui.StatCard', id: 's1' },
        { type: 'a2ui.StatCard', id: 's2' }, // Sequence 1: 2 consecutive
        { type: 'a2ui.HeadlineCard', id: 'h1' },
        { type: 'a2ui.VideoCard', id: 'v1' },
        { type: 'a2ui.VideoCard', id: 'v2' },
        { type: 'a2ui.VideoCard', id: 'v3' }, // Sequence 2: 3 consecutive
        { type: 'a2ui.ProfileCard', id: 'p1' },
        { type: 'a2ui.ProfileCard', id: 'p2' }, // Sequence 3: 2 consecutive
      ];

      const result = validateComponentVariety(components);

      expect(result.consecutiveSequences).toHaveLength(3);
      expect(result.consecutiveSequences?.[0]).toMatchObject({
        type: 'a2ui.StatCard',
        count: 2,
      });
      expect(result.consecutiveSequences?.[1]).toMatchObject({
        type: 'a2ui.VideoCard',
        count: 3,
      });
      expect(result.consecutiveSequences?.[2]).toMatchObject({
        type: 'a2ui.ProfileCard',
        count: 2,
      });
    });

    it('should not include single components in consecutive sequences', () => {
      const components: ComponentSpec[] = [
        { type: 'a2ui.TLDR', id: '1' },
        { type: 'a2ui.StatCard', id: '2' },
        { type: 'a2ui.HeadlineCard', id: '3' },
        { type: 'a2ui.VideoCard', id: '4' },
      ];

      const result = validateComponentVariety(components);

      expect(result.consecutiveSequences).toHaveLength(0);
    });
  });
});

describe('Variety Enforcement - wouldViolateVariety', () => {
  it('should return false for empty component list', () => {
    const result = wouldViolateVariety([], 'a2ui.StatCard');
    expect(result).toBe(false);
  });

  it('should return false when adding different type', () => {
    const components: ComponentSpec[] = [
      { type: 'a2ui.StatCard', id: 's1' },
      { type: 'a2ui.StatCard', id: 's2' },
    ];

    const result = wouldViolateVariety(components, 'a2ui.HeadlineCard');
    expect(result).toBe(false);
  });

  it('should return false when adding same type to 1 consecutive', () => {
    const components: ComponentSpec[] = [
      { type: 'a2ui.TLDR', id: '1' },
      { type: 'a2ui.StatCard', id: 's1' },
    ];

    const result = wouldViolateVariety(components, 'a2ui.StatCard');
    expect(result).toBe(false); // Would make 2 consecutive, which is allowed
  });

  it('should return true when adding would create 3 consecutive', () => {
    const components: ComponentSpec[] = [
      { type: 'a2ui.TLDR', id: '1' },
      { type: 'a2ui.StatCard', id: 's1' },
      { type: 'a2ui.StatCard', id: 's2' },
    ];

    const result = wouldViolateVariety(components, 'a2ui.StatCard');
    expect(result).toBe(true); // Would make 3 consecutive - violation!
  });

  it('should return true when adding would create 4+ consecutive', () => {
    const components: ComponentSpec[] = [
      { type: 'a2ui.StatCard', id: 's1' },
      { type: 'a2ui.StatCard', id: 's2' },
      { type: 'a2ui.StatCard', id: 's3' },
      { type: 'a2ui.StatCard', id: 's4' },
    ];

    const result = wouldViolateVariety(components, 'a2ui.StatCard');
    expect(result).toBe(true);
  });

  it('should handle alternating pattern correctly', () => {
    const components: ComponentSpec[] = [
      { type: 'a2ui.StatCard', id: 's1' },
      { type: 'a2ui.HeadlineCard', id: 'h1' },
      { type: 'a2ui.StatCard', id: 's2' },
      { type: 'a2ui.HeadlineCard', id: 'h2' },
    ];

    expect(wouldViolateVariety(components, 'a2ui.HeadlineCard')).toBe(false);
    expect(wouldViolateVariety(components, 'a2ui.StatCard')).toBe(false);
  });
});

describe('Variety Enforcement - suggestDiverseType', () => {
  const availableTypes = [
    'a2ui.StatCard',
    'a2ui.HeadlineCard',
    'a2ui.VideoCard',
    'a2ui.ProfileCard',
  ];

  it('should return first type for empty components', () => {
    const result = suggestDiverseType([], availableTypes);
    expect(result).toBe('a2ui.StatCard');
  });

  it('should suggest different type from last component', () => {
    const components: ComponentSpec[] = [
      { type: 'a2ui.StatCard', id: 's1' },
    ];

    const result = suggestDiverseType(components, availableTypes);
    expect(result).not.toBe('a2ui.StatCard');
    expect(availableTypes).toContain(result as string);
  });

  it('should prefer least-used type', () => {
    const components: ComponentSpec[] = [
      { type: 'a2ui.StatCard', id: 's1' },
      { type: 'a2ui.StatCard', id: 's2' },
      { type: 'a2ui.StatCard', id: 's3' }, // Used 3 times
      { type: 'a2ui.HeadlineCard', id: 'h1' },
      { type: 'a2ui.HeadlineCard', id: 'h2' }, // Used 2 times
      { type: 'a2ui.VideoCard', id: 'v1' }, // Used 1 time - least used!
    ];

    const result = suggestDiverseType(components, availableTypes);

    // Should suggest ProfileCard (never used) or HeadlineCard/VideoCard (used less)
    // Should NOT suggest StatCard (last used and most common)
    expect(result).not.toBe('a2ui.StatCard');
  });

  it('should return null when no alternatives available', () => {
    const components: ComponentSpec[] = [
      { type: 'a2ui.StatCard', id: 's1' },
    ];

    const result = suggestDiverseType(components, ['a2ui.StatCard']);
    expect(result).toBeNull();
  });

  it('should avoid consecutive same type', () => {
    const components: ComponentSpec[] = [
      { type: 'a2ui.StatCard', id: 's1' },
      { type: 'a2ui.StatCard', id: 's2' },
    ];

    const result = suggestDiverseType(components, availableTypes);
    expect(result).not.toBe('a2ui.StatCard'); // Don't create 3 consecutive
  });
});

describe('Variety Enforcement - formatVarietyReport', () => {
  it('should format valid result correctly', () => {
    const components: ComponentSpec[] = [
      { type: 'a2ui.TLDR', id: '1' },
      { type: 'a2ui.StatCard', id: '2' },
      { type: 'a2ui.HeadlineCard', id: '3' },
      { type: 'a2ui.VideoCard', id: '4' },
    ];

    const result = validateComponentVariety(components);
    const report = formatVarietyReport(result);

    expect(report).toContain('✓ VALID');
    expect(report).toContain('Unique Component Types: 4');
    expect(report).toContain('Meets Min Types: ✓');
    expect(report).toContain('Meets No Consecutive: ✓');
  });

  it('should format invalid result with violations', () => {
    const components: ComponentSpec[] = [
      { type: 'a2ui.StatCard', id: 's1' },
      { type: 'a2ui.StatCard', id: 's2' },
      { type: 'a2ui.StatCard', id: 's3' },
    ];

    const result = validateComponentVariety(components);
    const report = formatVarietyReport(result);

    expect(report).toContain('✗ INVALID');
    expect(report).toContain('Violations');
    expect(report).toContain('Only 1 unique type');
    expect(report).toContain('Found 3 consecutive');
  });

  it('should include component type distribution', () => {
    const components: ComponentSpec[] = [
      { type: 'a2ui.StatCard', id: 's1' },
      { type: 'a2ui.StatCard', id: 's2' },
      { type: 'a2ui.HeadlineCard', id: 'h1' },
      { type: 'a2ui.VideoCard', id: 'v1' },
      { type: 'a2ui.ProfileCard', id: 'p1' },
    ];

    const result = validateComponentVariety(components);
    const report = formatVarietyReport(result);

    expect(report).toContain('Component Type Distribution');
    expect(report).toContain('a2ui.StatCard: 2');
    expect(report).toContain('a2ui.HeadlineCard: 1');
  });

  it('should show consecutive sequences when present', () => {
    const components: ComponentSpec[] = [
      { type: 'a2ui.StatCard', id: 's1' },
      { type: 'a2ui.StatCard', id: 's2' },
      { type: 'a2ui.HeadlineCard', id: 'h1' },
      { type: 'a2ui.VideoCard', id: 'v1' },
      { type: 'a2ui.ProfileCard', id: 'p1' },
    ];

    const result = validateComponentVariety(components);
    const report = formatVarietyReport(result);

    expect(report).toContain('Consecutive Sequences');
    expect(report).toContain('2 × a2ui.StatCard');
  });
});
