/**
 * A2UI Test Page
 * Simple page to test the A2UI catalog without other components
 */

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { A2UIRendererList } from "@/components/A2UIRenderer";
import { getRegisteredTypes, type A2UIComponent } from "@/lib/a2ui-catalog";

// Sample A2UI components for testing
const testComponents: A2UIComponent[] = [
  {
    id: 'test-headline-1',
    type: 'a2ui.HeadlineCard',
    props: {
      title: 'A2UI Catalog Successfully Registered',
      summary: 'The component catalog is now functional and can render 45+ component types from backend specs.',
      source: 'System Test',
      published_at: new Date().toISOString(),
      sentiment: 'positive',
    },
  },
  {
    id: 'test-stat-1',
    type: 'a2ui.StatCard',
    props: {
      label: 'Registered Components',
      value: String(getRegisteredTypes().length),
      trend: '+45 new',
      icon: '📦',
    },
  },
  {
    id: 'test-tldr-1',
    type: 'a2ui.TLDR',
    props: {
      summary: 'A2UI catalog maps backend component types to React components for dynamic rendering.',
      key_points: [
        '45+ component types supported',
        'Graceful handling of unknown types',
        'Full support for nested children',
        'Layout and styling configuration',
      ],
    },
  },
];

export default function A2UITestPage() {
  const registeredTypes = getRegisteredTypes();

  return (
    <div className="min-h-screen bg-background text-foreground p-8">
      <div className="max-w-4xl mx-auto space-y-8">
        <div className="text-center">
          <h1 className="text-4xl font-bold mb-2">A2UI Catalog Test</h1>
          <p className="text-muted-foreground">
            Testing {registeredTypes.length} registered component types
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Catalog Information</CardTitle>
            <CardDescription>All registered A2UI component types</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2 max-h-48 overflow-y-auto">
              {registeredTypes.map((type) => (
                <Badge key={type} variant="secondary" className="text-xs">
                  {type.replace('a2ui.', '')}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>

        <div>
          <h2 className="text-2xl font-bold mb-4">Sample Components</h2>
          <A2UIRendererList components={testComponents} spacing="md" />
        </div>
      </div>
    </div>
  );
}
