/**
 * Summary Components Test Page
 * Tests all summary-type A2UI components with sample data
 */

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { A2UIRendererList } from "@/components/A2UIRenderer";
import type { A2UIComponent } from "@/lib/a2ui-catalog";

// Sample A2UI components for testing summary components
const summaryTestComponents: A2UIComponent[] = [
  // TLDR Component
  {
    id: 'test-tldr-1',
    type: 'a2ui.TLDR',
    props: {
      summary: 'The A2UI framework enables dynamic component rendering from backend specifications, supporting 45+ component types with dark theme and hierarchical layouts.',
      key_points: [
        'Modular component architecture with type safety',
        'Dark theme support using Tailwind CSS',
        'Backend-driven component generation',
        'Graceful error handling for missing types',
      ],
      icon: '⚡',
    },
  },

  // KeyTakeaways Component - Simple strings
  {
    id: 'test-takeaways-1',
    type: 'a2ui.KeyTakeaways',
    props: {
      title: 'Project Implementation Takeaways',
      items: [
        'Component catalog successfully maps 45+ backend types to React',
        'TypeScript interfaces ensure type safety across frontend-backend boundary',
        'Shadcn/ui provides consistent, accessible component primitives',
        'Dark theme support implemented using Tailwind dark: prefix',
      ],
    },
  },

  // KeyTakeaways Component - With category badges
  {
    id: 'test-takeaways-2',
    type: 'a2ui.KeyTakeaways',
    props: {
      title: 'Development Insights',
      items: [
        { text: 'React component composition enables flexible layouts', category: 'insights' },
        { text: 'TypeScript prevents runtime errors through compile-time checks', category: 'learnings' },
        { text: 'A2UIRenderer handles nested component trees recursively', category: 'conclusions' },
        { text: 'Consider adding component preview mode for debugging', category: 'recommendations' },
      ],
    },
  },

  // ExecutiveSummary Component - Full featured
  {
    id: 'test-exec-summary-1',
    type: 'a2ui.ExecutiveSummary',
    props: {
      title: 'DYN-215 Implementation Summary',
      summary: 'Successfully implemented all four summary components (TLDR, KeyTakeaways, ExecutiveSummary, TableOfContents) with comprehensive TypeScript typing, dark theme support, and integration with the A2UI catalog. Components follow established patterns and support flexible data structures.',
      metrics: [
        { label: 'Components Created', value: 4, unit: '', trend: 'up' },
        { label: 'Lines of Code', value: '350+', trend: 'up' },
        { label: 'Type Coverage', value: 100, unit: '%', trend: 'neutral' },
        { label: 'Test Coverage', value: 'TBD', trend: 'neutral' },
      ],
      recommendations: [
        'Add Playwright tests to verify component rendering and styling',
        'Document component props and usage examples in Storybook',
        'Consider adding animation transitions for better UX',
        'Test components with real backend data from orchestrator',
      ],
    },
  },

  // TableOfContents Component - Multi-level hierarchy
  {
    id: 'test-toc-1',
    type: 'a2ui.TableOfContents',
    props: {
      title: 'Documentation Outline',
      show_page_numbers: true,
      items: [
        { title: 'Introduction', level: 0, page: 1 },
        { title: 'Getting Started', level: 0, page: 2 },
        { title: 'Installation', level: 1, page: 2 },
        { title: 'Prerequisites', level: 2, page: 2 },
        { title: 'Setup Steps', level: 2, page: 3 },
        { title: 'Configuration', level: 1, page: 4 },
        { title: 'Component Architecture', level: 0, page: 5 },
        { title: 'Core Components', level: 1, page: 5 },
        { title: 'A2UIRenderer', level: 2, page: 6 },
        { title: 'Component Catalog', level: 2, page: 7 },
        { title: 'Custom Components', level: 1, page: 8 },
        { title: 'Best Practices', level: 0, page: 9 },
        { title: 'TypeScript Patterns', level: 1, page: 9 },
        { title: 'Error Handling', level: 1, page: 10 },
        { title: 'Testing Strategy', level: 1, page: 11 },
        { title: 'Conclusion', level: 0, page: 12 },
      ],
    },
  },

  // TableOfContents Component - Without page numbers
  {
    id: 'test-toc-2',
    type: 'a2ui.TableOfContents',
    props: {
      title: 'Quick Navigation',
      show_page_numbers: false,
      items: [
        { title: 'Summary Components Overview', level: 0, anchor: '#overview' },
        { title: 'TLDR Component', level: 1, anchor: '#tldr' },
        { title: 'KeyTakeaways Component', level: 1, anchor: '#takeaways' },
        { title: 'ExecutiveSummary Component', level: 1, anchor: '#executive' },
        { title: 'TableOfContents Component', level: 1, anchor: '#toc' },
        { title: 'Usage Examples', level: 0, anchor: '#examples' },
        { title: 'API Reference', level: 0, anchor: '#api' },
      ],
    },
  },
];

export default function SummaryComponentsTestPage() {
  return (
    <div className="min-h-screen bg-background text-foreground p-8">
      <div className="max-w-4xl mx-auto space-y-8">
        <div className="text-center">
          <h1 className="text-4xl font-bold mb-2">Summary Components Test</h1>
          <p className="text-muted-foreground">
            Testing TLDR, KeyTakeaways, ExecutiveSummary, and TableOfContents components
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Component Information</CardTitle>
            <CardDescription>Summary component types registered in the A2UI catalog</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              <Badge variant="secondary">a2ui.TLDR</Badge>
              <Badge variant="secondary">a2ui.KeyTakeaways</Badge>
              <Badge variant="secondary">a2ui.ExecutiveSummary</Badge>
              <Badge variant="secondary">a2ui.TableOfContents</Badge>
            </div>
          </CardContent>
        </Card>

        <div>
          <h2 className="text-2xl font-bold mb-4">Component Examples</h2>
          <A2UIRendererList components={summaryTestComponents} spacing="lg" />
        </div>
      </div>
    </div>
  );
}
