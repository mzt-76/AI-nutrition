/**
 * A2UI Validator Test Page
 *
 * Interactive page to test A2UI protocol validation
 */

import React, { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  validateA2UIComponent,
  formatValidationResult,
  getValidationSummary,
  type ValidationResult,
} from '@/utils/a2ui-validator';
import type { A2UIComponent } from '@/lib/a2ui-catalog';
import { A2UIRenderer } from '@/components/A2UIRenderer';

// Test cases
const VALID_COMPONENT: A2UIComponent = {
  id: 'valid-stat',
  type: 'a2ui.StatCard',
  props: {
    label: 'Valid Component',
    value: '100',
    trend: '+12%',
    icon: '✓',
  },
};

const INVALID_MISSING_TYPE = {
  id: 'invalid-1',
  props: { label: 'Missing Type', value: '100' },
};

const INVALID_MISSING_ID = {
  type: 'a2ui.StatCard',
  props: { label: 'Missing ID', value: '100' },
};

const INVALID_NON_SERIALIZABLE = {
  id: 'invalid-2',
  type: 'a2ui.StatCard',
  props: {
    label: 'Non-Serializable',
    value: '100',
    onClick: () => {}, // Function not allowed
  },
};

const INVALID_UNREGISTERED_TYPE: A2UIComponent = {
  id: 'invalid-3',
  type: 'a2ui.NonExistentComponent',
  props: {},
};

const VALID_WITH_CHILDREN: A2UIComponent = {
  id: 'valid-section',
  type: 'a2ui.Section',
  props: { title: 'Test Section' },
  children: [
    {
      id: 'child-1',
      type: 'a2ui.StatCard',
      props: { label: 'Child 1', value: '100' },
    },
    {
      id: 'child-2',
      type: 'a2ui.StatCard',
      props: { label: 'Child 2', value: '200' },
    },
  ],
};

const INVALID_DUPLICATE_IDS: A2UIComponent = {
  id: 'parent',
  type: 'a2ui.Section',
  props: {},
  children: [
    { id: 'duplicate', type: 'a2ui.StatCard', props: { label: 'A', value: '1' } },
    { id: 'duplicate', type: 'a2ui.StatCard', props: { label: 'B', value: '2' } },
  ],
};

const COMPLEX_VALID: A2UIComponent = {
  id: 'dashboard',
  type: 'a2ui.Grid',
  props: { columns: 2, gap: 'md' },
  layout: { width: '100%' },
  styling: { variant: 'default' },
  children: [
    {
      id: 'stats-section',
      type: 'a2ui.Section',
      props: { title: 'Metrics' },
      children: [
        { id: 'stat-1', type: 'a2ui.StatCard', props: { label: 'Users', value: '1234' } },
        { id: 'stat-2', type: 'a2ui.StatCard', props: { label: 'Revenue', value: '$56,789' } },
      ],
    },
    {
      id: 'news-section',
      type: 'a2ui.Section',
      props: { title: 'News' },
      children: [
        {
          id: 'headline-1',
          type: 'a2ui.HeadlineCard',
          props: {
            title: 'A2UI Protocol Released',
            summary: 'New validation system ensures protocol compliance.',
            source: 'System',
            published_at: new Date().toISOString(),
          },
        },
      ],
    },
  ],
};

interface TestCase {
  name: string;
  component: any;
  description: string;
  expectedValid: boolean;
}

const TEST_CASES: TestCase[] = [
  {
    name: 'Valid Simple Component',
    component: VALID_COMPONENT,
    description: 'A valid StatCard with all required fields',
    expectedValid: true,
  },
  {
    name: 'Missing Type Field',
    component: INVALID_MISSING_TYPE,
    description: 'Component without type field (should fail)',
    expectedValid: false,
  },
  {
    name: 'Missing ID Field',
    component: INVALID_MISSING_ID,
    description: 'Component without id field (should fail)',
    expectedValid: false,
  },
  {
    name: 'Non-Serializable Props',
    component: INVALID_NON_SERIALIZABLE,
    description: 'Component with function in props (should fail)',
    expectedValid: false,
  },
  {
    name: 'Unregistered Type',
    component: INVALID_UNREGISTERED_TYPE,
    description: 'Component with unregistered type (should fail)',
    expectedValid: false,
  },
  {
    name: 'Valid with Children',
    component: VALID_WITH_CHILDREN,
    description: 'Section with valid child components',
    expectedValid: true,
  },
  {
    name: 'Duplicate IDs',
    component: INVALID_DUPLICATE_IDS,
    description: 'Section with duplicate child IDs (should fail)',
    expectedValid: false,
  },
  {
    name: 'Complex Valid Tree',
    component: COMPLEX_VALID,
    description: 'Multi-level component tree with layout and styling',
    expectedValid: true,
  },
];

export default function A2UIValidatorTest() {
  const [selectedTest, setSelectedTest] = useState<number>(0);
  const [validationResult, setValidationResult] = useState<ValidationResult | null>(null);

  const runValidation = (testIndex: number) => {
    setSelectedTest(testIndex);
    const testCase = TEST_CASES[testIndex];
    const result = validateA2UIComponent(testCase.component);
    setValidationResult(result);
  };

  const runAllTests = () => {
    const results = TEST_CASES.map((testCase) => {
      const result = validateA2UIComponent(testCase.component);
      const passed = result.valid === testCase.expectedValid;
      return { testCase, result, passed };
    });

    const allPassed = results.every((r) => r.passed);
    console.log('=== All Tests Results ===');
    console.log(`Passed: ${results.filter((r) => r.passed).length}/${results.length}`);
    results.forEach((r, i) => {
      console.log(`\n${i + 1}. ${r.testCase.name}: ${r.passed ? '✓ PASS' : '✗ FAIL'}`);
      if (!r.passed) {
        console.log(`   Expected valid: ${r.testCase.expectedValid}, Got: ${r.result.valid}`);
      }
    });

    alert(
      allPassed
        ? `All ${results.length} tests passed! ✓`
        : `${results.filter((r) => !r.passed).length} tests failed.`
    );
  };

  React.useEffect(() => {
    runValidation(0);
  }, []);

  const currentTest = TEST_CASES[selectedTest];
  const summary = validationResult ? getValidationSummary(validationResult) : null;

  return (
    <div className="min-h-screen bg-background text-foreground p-8">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div className="text-center space-y-2">
          <h1 className="text-4xl font-bold">A2UI Protocol Validator</h1>
          <p className="text-muted-foreground">
            Test A2UI component validation and protocol compliance
          </p>
        </div>

        {/* Test Controls */}
        <Card>
          <CardHeader>
            <CardTitle>Test Cases</CardTitle>
            <CardDescription>Select a test case to validate</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap gap-2">
              {TEST_CASES.map((testCase, index) => (
                <Button
                  key={index}
                  variant={selectedTest === index ? 'default' : 'outline'}
                  onClick={() => runValidation(index)}
                  size="sm"
                >
                  {testCase.name}
                  {validationResult &&
                    selectedTest === index &&
                    (validationResult.valid ? (
                      <Badge className="ml-2 bg-green-500">✓</Badge>
                    ) : (
                      <Badge className="ml-2 bg-red-500">✗</Badge>
                    ))}
                </Button>
              ))}
            </div>

            <Button onClick={runAllTests} variant="default" className="w-full">
              Run All Tests
            </Button>
          </CardContent>
        </Card>

        {/* Current Test */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>{currentTest.name}</CardTitle>
                <CardDescription>{currentTest.description}</CardDescription>
              </div>
              {summary && (
                <Badge variant={summary.valid ? 'default' : 'destructive'} className="text-lg px-4 py-2">
                  {summary.valid ? '✓ VALID' : '✗ INVALID'}
                </Badge>
              )}
            </div>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="result">
              <TabsList className="grid grid-cols-3 w-full">
                <TabsTrigger value="result">Validation Result</TabsTrigger>
                <TabsTrigger value="spec">Component Spec</TabsTrigger>
                <TabsTrigger value="preview">Preview</TabsTrigger>
              </TabsList>

              <TabsContent value="result" className="space-y-4">
                {validationResult && summary && (
                  <>
                    {/* Summary */}
                    <div className="grid grid-cols-4 gap-4">
                      <Card>
                        <CardContent className="pt-6">
                          <div className="text-2xl font-bold">{summary.componentCount}</div>
                          <div className="text-xs text-muted-foreground">Components</div>
                        </CardContent>
                      </Card>
                      <Card>
                        <CardContent className="pt-6">
                          <div className="text-2xl font-bold">{summary.typeCount}</div>
                          <div className="text-xs text-muted-foreground">Unique Types</div>
                        </CardContent>
                      </Card>
                      <Card>
                        <CardContent className="pt-6">
                          <div className="text-2xl font-bold text-red-500">{summary.errorCount}</div>
                          <div className="text-xs text-muted-foreground">Errors</div>
                        </CardContent>
                      </Card>
                      <Card>
                        <CardContent className="pt-6">
                          <div className="text-2xl font-bold text-yellow-500">
                            {summary.warningCount}
                          </div>
                          <div className="text-xs text-muted-foreground">Warnings</div>
                        </CardContent>
                      </Card>
                    </div>

                    {/* Errors */}
                    {validationResult.errors.length > 0 && (
                      <Card className="border-red-500">
                        <CardHeader>
                          <CardTitle className="text-red-700">
                            Errors ({validationResult.errors.length})
                          </CardTitle>
                        </CardHeader>
                        <CardContent>
                          <div className="space-y-3">
                            {validationResult.errors.map((error, index) => (
                              <div key={index} className="p-3 bg-red-500/10 rounded border border-red-500">
                                <div className="flex items-center gap-2 mb-1">
                                  <Badge variant="destructive">{error.type}</Badge>
                                  <code className="text-xs text-muted-foreground">{error.path}</code>
                                </div>
                                <p className="text-sm text-red-700">{error.message}</p>
                              </div>
                            ))}
                          </div>
                        </CardContent>
                      </Card>
                    )}

                    {/* Warnings */}
                    {validationResult.warnings.length > 0 && (
                      <Card className="border-yellow-500">
                        <CardHeader>
                          <CardTitle className="text-yellow-700">
                            Warnings ({validationResult.warnings.length})
                          </CardTitle>
                        </CardHeader>
                        <CardContent>
                          <div className="space-y-3">
                            {validationResult.warnings.map((warning, index) => (
                              <div key={index} className="p-3 bg-yellow-500/10 rounded border border-yellow-500">
                                <div className="flex items-center gap-2 mb-1">
                                  <Badge variant="outline">{warning.type}</Badge>
                                  <code className="text-xs text-muted-foreground">{warning.path}</code>
                                </div>
                                <p className="text-sm text-yellow-700">{warning.message}</p>
                              </div>
                            ))}
                          </div>
                        </CardContent>
                      </Card>
                    )}

                    {/* Formatted Result */}
                    <Card>
                      <CardHeader>
                        <CardTitle>Formatted Result</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <pre className="text-xs bg-muted p-4 rounded overflow-x-auto">
                          {formatValidationResult(validationResult)}
                        </pre>
                      </CardContent>
                    </Card>
                  </>
                )}
              </TabsContent>

              <TabsContent value="spec">
                <Card>
                  <CardHeader>
                    <CardTitle>Component Specification</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <pre className="text-xs bg-muted p-4 rounded overflow-x-auto max-h-[500px]">
                      {JSON.stringify(currentTest.component, null, 2)}
                    </pre>
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="preview">
                <Card>
                  <CardHeader>
                    <CardTitle>Rendered Preview</CardTitle>
                    <CardDescription>
                      {validationResult?.valid
                        ? 'Component will render successfully'
                        : 'Component has validation errors'}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="border rounded p-4">
                      <A2UIRenderer component={currentTest.component as A2UIComponent} showErrors={true} />
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>

        {/* Documentation Link */}
        <Card>
          <CardContent className="pt-6">
            <div className="text-center space-y-2">
              <p className="text-sm text-muted-foreground">
                For complete protocol documentation, see:
              </p>
              <code className="text-sm bg-muted px-3 py-1 rounded">
                /frontend/docs/A2UI_PROTOCOL.md
              </code>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
