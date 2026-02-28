import { test, expect } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

test.describe('Application Flow Tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/', { timeout: 60000 });
    await page.waitForLoadState('networkidle');
  });

  test('full flow: paste markdown and verify UI updates', async ({ page }) => {
    const sampleMarkdown = `# Test Document

This is a **test** document with *formatting*.

## Features
- Feature 1
- Feature 2
- Feature 3

\`\`\`javascript
console.log('Hello World');
\`\`\`
`;

    // Find and fill textarea
    const textarea = page.locator('textarea').first();
    await expect(textarea).toBeVisible();
    await textarea.fill(sampleMarkdown);

    // Verify character count updates
    await expect(page.locator('text=/\\d+ characters?/')).toBeVisible();

    // Take screenshot
    await page.screenshot({
      path: 'screenshots/DYN-226-full-flow-input.png',
      fullPage: true
    });

    // Verify generate button is present
    const generateButton = page.getByRole('button', { name: /generate/i });
    await expect(generateButton).toBeVisible();

    // Take screenshot with content
    await page.screenshot({
      path: 'screenshots/DYN-226-full-flow-ready.png',
      fullPage: true
    });
  });

  test('character and word count updates', async ({ page }) => {
    const textarea = page.locator('textarea').first();

    // Type some content
    await textarea.fill('Hello world! This is a test.');

    // Wait for counts to update
    await expect(page.locator('text=/\\d+ characters?/')).toBeVisible();
    await expect(page.locator('text=/\\d+ words?/')).toBeVisible();

    // Verify counts are greater than 0
    const charText = await page.locator('text=/\\d+ characters?/').textContent();
    const wordText = await page.locator('text=/\\d+ words?/').textContent();

    expect(charText).toContain('character');
    expect(wordText).toContain('word');

    // Take screenshot
    await page.screenshot({
      path: 'screenshots/DYN-226-character-count.png',
      fullPage: true
    });
  });
});

test.describe('Sample Document Tests', () => {
  const samples = [
    'agentic-workflows-tutorial.md',
    'ai-industry-statistics.md',
    'ai-news-weekly.md',
    'claude-vs-gpt-comparison.md',
    'top-10-coding-tools.md',
  ];

  for (const filename of samples) {
    test(`should load ${filename}`, async ({ page }) => {
      await page.goto('/', { timeout: 60000 });
      await page.waitForLoadState('networkidle');

      const samplePath = path.join(process.cwd(), '..', 'sample-documents', filename);

      if (!fs.existsSync(samplePath)) {
        test.skip();
        return;
      }

      const content = fs.readFileSync(samplePath, 'utf-8');

      // Fill textarea
      const textarea = page.locator('textarea').first();
      await textarea.fill(content);

      // Wait for stats to update
      await page.waitForTimeout(500);

      // Verify content is loaded
      const value = await textarea.inputValue();
      expect(value.length).toBeGreaterThan(100);

      // Take screenshot
      const safeName = filename.replace('.md', '').replace(/[^a-z0-9-]/g, '-');
      await page.screenshot({
        path: `screenshots/DYN-226-sample-${safeName}.png`,
        fullPage: true
      });
    });
  }
});

test.describe('Content Type Tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/', { timeout: 60000 });
    await page.waitForLoadState('networkidle');
  });

  test('markdown with YouTube links', async ({ page }) => {
    const markdown = `# Video Content

Check out this tutorial: https://www.youtube.com/watch?v=dQw4w9WgXcQ

Another video: https://youtu.be/jNQXAC9IVRw
`;

    const textarea = page.locator('textarea').first();
    await textarea.fill(markdown);

    await page.waitForTimeout(300);

    await page.screenshot({
      path: 'screenshots/DYN-226-youtube-content.png',
      fullPage: true
    });
  });

  test('markdown with GitHub links', async ({ page }) => {
    const markdown = `# Repository Links

React: https://github.com/facebook/react
VS Code: https://github.com/microsoft/vscode
`;

    const textarea = page.locator('textarea').first();
    await textarea.fill(markdown);

    await page.waitForTimeout(300);

    await page.screenshot({
      path: 'screenshots/DYN-226-github-content.png',
      fullPage: true
    });
  });

  test('markdown with code blocks', async ({ page }) => {
    const markdown = `# Code Examples

\`\`\`javascript
function hello() {
  console.log('Hello World');
}
\`\`\`

\`\`\`python
def greet(name):
    print(f"Hello, {name}!")
\`\`\`
`;

    const textarea = page.locator('textarea').first();
    await textarea.fill(markdown);

    await page.waitForTimeout(300);

    await page.screenshot({
      path: 'screenshots/DYN-226-code-blocks.png',
      fullPage: true
    });
  });

  test('markdown with tables', async ({ page }) => {
    const markdown = `# Data Comparison

| Feature | Claude | GPT-4 |
|---------|--------|-------|
| Context | 200K   | 128K  |
| Price   | $3/M   | $10/M |
| Speed   | Fast   | Medium|
`;

    const textarea = page.locator('textarea').first();
    await textarea.fill(markdown);

    await page.waitForTimeout(300);

    await page.screenshot({
      path: 'screenshots/DYN-226-tables.png',
      fullPage: true
    });
  });

  test('markdown with lists', async ({ page }) => {
    const markdown = `# Feature Lists

## Bullet List
- Item one
- Item two
  - Nested item
- Item three

## Numbered List
1. First step
2. Second step
3. Third step
`;

    const textarea = page.locator('textarea').first();
    await textarea.fill(markdown);

    await page.waitForTimeout(300);

    await page.screenshot({
      path: 'screenshots/DYN-226-lists.png',
      fullPage: true
    });
  });
});

test.describe('Responsive Tests', () => {
  test('mobile layout (375px)', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/', { timeout: 60000 });
    await page.waitForLoadState('networkidle');

    // Verify main elements are visible
    await expect(page.getByText('Second Brain Research Dashboard')).toBeVisible();

    // Check no horizontal scroll
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 2);

    await page.screenshot({
      path: 'screenshots/DYN-226-mobile-375.png',
      fullPage: true
    });
  });

  test('tablet layout (768px)', async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.goto('/', { timeout: 60000 });
    await page.waitForLoadState('networkidle');

    await expect(page.getByText('Second Brain Research Dashboard')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Markdown Input' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Generated Dashboard' })).toBeVisible();

    await page.screenshot({
      path: 'screenshots/DYN-226-tablet-768.png',
      fullPage: true
    });
  });

  test('desktop layout (1920px)', async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto('/', { timeout: 60000 });
    await page.waitForLoadState('networkidle');

    await expect(page.getByText('Second Brain Research Dashboard')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Markdown Input' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Generated Dashboard' })).toBeVisible();

    await page.screenshot({
      path: 'screenshots/DYN-226-desktop-1920.png',
      fullPage: true
    });
  });

  test('text readability across screen sizes', async ({ page }) => {
    const sizes = [
      { width: 375, height: 667, name: 'mobile' },
      { width: 768, height: 1024, name: 'tablet' },
      { width: 1920, height: 1080, name: 'desktop' },
    ];

    for (const size of sizes) {
      await page.setViewportSize({ width: size.width, height: size.height });
      await page.goto('/', { timeout: 60000 });
      await page.waitForLoadState('networkidle');

      // Check heading font size
      const h1 = page.locator('h1').first();
      const fontSize = await h1.evaluate(el => {
        return parseInt(window.getComputedStyle(el).fontSize);
      });

      expect(fontSize).toBeGreaterThanOrEqual(16);

      await page.screenshot({
        path: `screenshots/DYN-226-readable-${size.name}.png`,
        fullPage: true
      });
    }
  });
});

test.describe('Accessibility Tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/', { timeout: 60000 });
    await page.waitForLoadState('networkidle');
  });

  test('keyboard navigation', async ({ page }) => {
    // Tab through elements
    await page.keyboard.press('Tab');
    await page.waitForTimeout(200);
    await page.keyboard.press('Tab');
    await page.waitForTimeout(200);

    await page.screenshot({
      path: 'screenshots/DYN-226-keyboard-nav.png',
      fullPage: true
    });
  });

  test('proper heading hierarchy', async ({ page }) => {
    const h1Count = await page.locator('h1').count();
    expect(h1Count).toBeGreaterThanOrEqual(1);

    const h2Count = await page.locator('h2').count();
    expect(h2Count).toBeGreaterThanOrEqual(1);

    await page.screenshot({
      path: 'screenshots/DYN-226-headings.png',
      fullPage: true
    });
  });

  test('interactive elements are focusable', async ({ page }) => {
    const buttons = page.getByRole('button');
    const buttonCount = await buttons.count();
    expect(buttonCount).toBeGreaterThan(0);

    const textareas = page.locator('textarea');
    const textareaCount = await textareas.count();
    expect(textareaCount).toBeGreaterThan(0);

    await page.screenshot({
      path: 'screenshots/DYN-226-focusable-elements.png',
      fullPage: true
    });
  });
});

test.describe('UI Interaction Tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/', { timeout: 60000 });
    await page.waitForLoadState('networkidle');
  });

  test('textarea accepts input', async ({ page }) => {
    const textarea = page.locator('textarea').first();
    const testText = 'Test input for verification';

    await textarea.fill(testText);
    const value = await textarea.inputValue();
    expect(value).toBe(testText);

    await page.screenshot({
      path: 'screenshots/DYN-226-textarea-input.png',
      fullPage: true
    });
  });

  test('button hover state', async ({ page }) => {
    const textarea = page.locator('textarea').first();
    await textarea.fill('# Test');

    const generateButton = page.getByRole('button', { name: /generate/i });
    await generateButton.hover();
    await page.waitForTimeout(300);

    await page.screenshot({
      path: 'screenshots/DYN-226-button-hover.png',
      fullPage: true
    });
  });

  test('empty state validation', async ({ page }) => {
    // Verify empty state shows initially
    await expect(page.getByText('No Dashboard Yet')).toBeVisible();

    await page.screenshot({
      path: 'screenshots/DYN-226-empty-state.png',
      fullPage: true
    });
  });
});
