import { Page, expect } from '@playwright/test';

/**
 * Helper functions for E2E tests
 */

export async function loadSampleDocument(page: Page, filename: string): Promise<void> {
  const fs = await import('fs');
  const path = await import('path');

  const samplePath = path.join(process.cwd(), '..', 'sample-documents', filename);
  const content = fs.readFileSync(samplePath, 'utf-8');

  const textarea = page.locator('textarea').first();
  await textarea.fill(content);
}

export async function verifyNoHorizontalScroll(page: Page): Promise<void> {
  const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
  const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
  expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 1); // Allow 1px tolerance
}

export async function waitForAnimations(page: Page, timeout = 1000): Promise<void> {
  await page.waitForTimeout(timeout);
}

export async function verifyEmptyState(page: Page): Promise<void> {
  await expect(page.getByText('No Dashboard Yet')).toBeVisible();
  await expect(page.getByText('Upload or paste markdown content')).toBeVisible();
}

export async function verifyLoadingState(page: Page): Promise<void> {
  // Check for skeleton loaders or loading indicators
  const loadingElement = page.locator('[data-testid="loading-skeleton"]').or(
    page.getByText(/loading|generating/i)
  );
  await expect(loadingElement.first()).toBeVisible();
}

export async function fillMarkdownInput(page: Page, content: string): Promise<void> {
  const textarea = page.locator('textarea').first();
  await textarea.fill(content);
}

export async function clickGenerate(page: Page): Promise<void> {
  const generateButton = page.getByRole('button', { name: /generate/i });
  await generateButton.click();
}

export async function verifyCharacterCount(page: Page, expectedMin: number): Promise<void> {
  const countText = await page.getByText(/\d+ characters?/).textContent();
  const count = parseInt(countText?.match(/\d+/)?.[0] || '0');
  expect(count).toBeGreaterThanOrEqual(expectedMin);
}

export async function verifyWordCount(page: Page, expectedMin: number): Promise<void> {
  const countText = await page.getByText(/\d+ words?/).textContent();
  const count = parseInt(countText?.match(/\d+/)?.[0] || '0');
  expect(count).toBeGreaterThanOrEqual(expectedMin);
}

export async function takeScreenshot(
  page: Page,
  name: string,
  fullPage = true
): Promise<void> {
  await page.screenshot({
    path: `screenshots/DYN-226-${name}.png`,
    fullPage,
  });
}

export async function setViewportSize(
  page: Page,
  preset: 'mobile' | 'tablet' | 'desktop'
): Promise<void> {
  const sizes = {
    mobile: { width: 375, height: 667 },
    tablet: { width: 768, height: 1024 },
    desktop: { width: 1920, height: 1080 },
  };

  await page.setViewportSize(sizes[preset]);
}

export async function verifyResponsiveLayout(page: Page): Promise<void> {
  // Verify essential elements are visible
  await expect(page.getByText('Second Brain Research Dashboard')).toBeVisible();
  await verifyNoHorizontalScroll(page);
}

export async function verifyAccessibility(page: Page): Promise<void> {
  // Check for basic accessibility features
  const h1 = page.locator('h1');
  await expect(h1).toBeVisible();

  // Verify interactive elements are focusable
  const buttons = page.getByRole('button');
  const buttonCount = await buttons.count();
  expect(buttonCount).toBeGreaterThan(0);
}

export const SAMPLE_DOCUMENTS = [
  'agentic-workflows-tutorial.md',
  'ai-industry-statistics.md',
  'ai-news-weekly.md',
  'claude-vs-gpt-comparison.md',
  'top-10-coding-tools.md',
];

export const TEST_MARKDOWN = {
  simple: '# Hello World\n\nThis is a simple test.',

  withCode: `# Code Example

\`\`\`javascript
function hello() {
  console.log('Hello, World!');
}
\`\`\`
`,

  withYouTube: `# Video Content

Check out this video: https://www.youtube.com/watch?v=dQw4w9WgXcQ
`,

  withGitHub: `# Repository

Check out: https://github.com/facebook/react
`,

  withTable: `# Data Table

| Feature | Value |
|---------|-------|
| Speed   | Fast  |
| Quality | High  |
`,

  withLists: `# Lists

- Item 1
- Item 2
  - Nested item
- Item 3

1. First
2. Second
3. Third
`,

  complex: `# Complex Document

## Introduction

This is a **complex** document with *various* elements.

### Code Block

\`\`\`python
def greet(name):
    print(f"Hello, {name}!")
\`\`\`

### Links

- YouTube: https://www.youtube.com/watch?v=dQw4w9WgXcQ
- GitHub: https://github.com/facebook/react

### Table

| Feature | Claude | GPT-4 |
|---------|--------|-------|
| Context | 200K   | 128K  |

### List

1. First item
2. Second item
3. Third item
`,
};
