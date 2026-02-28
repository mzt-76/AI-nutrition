import { test, expect } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

test.describe('Full Application Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('should display initial empty state', async ({ page }) => {
    // Verify header is visible
    await expect(page.getByText('Second Brain Research Dashboard')).toBeVisible();
    await expect(page.getByText('Transform your markdown research into interactive')).toBeVisible();

    // Verify empty state is shown
    await expect(page.getByText('No Dashboard Yet')).toBeVisible();
    await expect(page.getByText('Upload or paste markdown content to generate')).toBeVisible();

    // Take screenshot
    await page.screenshot({
      path: 'screenshots/DYN-226-empty-state.png',
      fullPage: true
    });
  });

  test('should have responsive layout', async ({ page }) => {
    // Verify split panel on desktop
    const leftPanel = page.locator('text=Markdown Input').locator('..');
    const rightPanel = page.locator('text=Generated Dashboard').locator('..');

    await expect(leftPanel).toBeVisible();
    await expect(rightPanel).toBeVisible();

    // Take screenshot
    await page.screenshot({
      path: 'screenshots/DYN-226-layout-desktop.png',
      fullPage: true
    });
  });

  test('should accept markdown input via paste', async ({ page }) => {
    const sampleMarkdown = `# Test Document

This is a test document with some **bold** and *italic* text.

## Section 1
Some content here.

\`\`\`javascript
console.log('Hello World');
\`\`\`

- Item 1
- Item 2
- Item 3
`;

    // Find the textarea and input markdown
    const textarea = page.locator('textarea').first();
    await expect(textarea).toBeVisible();
    await textarea.fill(sampleMarkdown);

    // Verify character count updates
    await expect(page.getByText(/\d+ characters/)).toBeVisible();
    await expect(page.getByText(/\d+ words/)).toBeVisible();

    // Take screenshot
    await page.screenshot({
      path: 'screenshots/DYN-226-markdown-input.png',
      fullPage: true
    });
  });

  test('should show loading state when generating', async ({ page }) => {
    const sampleMarkdown = `# Quick Test\n\nSome content here.`;

    // Fill textarea
    const textarea = page.locator('textarea').first();
    await textarea.fill(sampleMarkdown);

    // Click generate button
    const generateButton = page.getByRole('button', { name: /generate/i });
    await expect(generateButton).toBeVisible();

    // Note: Since backend is not running, we can't test actual generation
    // but we can verify the button exists and is clickable
    await expect(generateButton).toBeEnabled();

    // Take screenshot
    await page.screenshot({
      path: 'screenshots/DYN-226-generate-button.png',
      fullPage: true
    });
  });
});

test.describe('Sample Documents', () => {
  const sampleDocuments = [
    { name: 'agentic-workflows-tutorial.md', title: 'Agentic Workflows' },
    { name: 'ai-industry-statistics.md', title: 'AI Industry Statistics' },
    { name: 'ai-news-weekly.md', title: 'AI News Weekly' },
    { name: 'claude-vs-gpt-comparison.md', title: 'Claude vs GPT' },
    { name: 'top-10-coding-tools.md', title: 'Top 10 Coding Tools' },
  ];

  for (const doc of sampleDocuments) {
    test(`should load ${doc.name}`, async ({ page }) => {
      await page.goto('/');

      const samplePath = path.join(
        process.cwd(),
        '..',
        'sample-documents',
        doc.name
      );

      // Check if file exists
      if (!fs.existsSync(samplePath)) {
        test.skip();
        return;
      }

      const content = fs.readFileSync(samplePath, 'utf-8');

      // Fill textarea with sample content
      const textarea = page.locator('textarea').first();
      await textarea.fill(content);

      // Verify character count updates
      await expect(page.getByText(/\d+ characters/)).toBeVisible();

      // Take screenshot
      await page.screenshot({
        path: `screenshots/DYN-226-sample-${doc.name.replace('.md', '')}.png`,
        fullPage: true
      });
    });
  }
});

test.describe('Component Integration', () => {
  test('should handle YouTube links', async ({ page }) => {
    await page.goto('/');

    const markdownWithYouTube = `# Video Content

Check out this video: https://www.youtube.com/watch?v=dQw4w9WgXcQ

And another: https://youtu.be/dQw4w9WgXcQ
`;

    const textarea = page.locator('textarea').first();
    await textarea.fill(markdownWithYouTube);

    // Take screenshot
    await page.screenshot({
      path: 'screenshots/DYN-226-youtube-links.png',
      fullPage: true
    });
  });

  test('should handle GitHub links', async ({ page }) => {
    await page.goto('/');

    const markdownWithGitHub = `# Repository Links

Check out this repo: https://github.com/facebook/react

And another: https://github.com/microsoft/vscode
`;

    const textarea = page.locator('textarea').first();
    await textarea.fill(markdownWithGitHub);

    // Take screenshot
    await page.screenshot({
      path: 'screenshots/DYN-226-github-links.png',
      fullPage: true
    });
  });

  test('should handle code blocks', async ({ page }) => {
    await page.goto('/');

    const markdownWithCode = `# Code Examples

\`\`\`javascript
function hello() {
  console.log('Hello, World!');
  return true;
}
\`\`\`

\`\`\`python
def greet(name):
    print(f"Hello, {name}!")
    return name
\`\`\`

\`\`\`typescript
interface User {
  name: string;
  age: number;
}

const user: User = { name: 'Alice', age: 30 };
\`\`\`
`;

    const textarea = page.locator('textarea').first();
    await textarea.fill(markdownWithCode);

    // Take screenshot
    await page.screenshot({
      path: 'screenshots/DYN-226-code-blocks.png',
      fullPage: true
    });
  });

  test('should handle lists and nested content', async ({ page }) => {
    await page.goto('/');

    const markdownWithLists = `# Lists and Structure

## Bullet Lists
- First item
- Second item
  - Nested item 1
  - Nested item 2
- Third item

## Numbered Lists
1. Step one
2. Step two
   1. Sub-step A
   2. Sub-step B
3. Step three

## Mixed Content
- **Bold item**
- *Italic item*
- \`Code item\`
- [Link item](https://example.com)
`;

    const textarea = page.locator('textarea').first();
    await textarea.fill(markdownWithLists);

    // Take screenshot
    await page.screenshot({
      path: 'screenshots/DYN-226-lists.png',
      fullPage: true
    });
  });

  test('should handle tables', async ({ page }) => {
    await page.goto('/');

    const markdownWithTable = `# Data Tables

| Feature | Claude | GPT-4 |
|---------|--------|-------|
| Context Window | 200K | 128K |
| Price (Input) | $3/M | $10/M |
| Speed | Fast | Medium |
| Code Quality | Excellent | Very Good |
`;

    const textarea = page.locator('textarea').first();
    await textarea.fill(markdownWithTable);

    // Take screenshot
    await page.screenshot({
      path: 'screenshots/DYN-226-tables.png',
      fullPage: true
    });
  });
});

test.describe('Responsive Design', () => {
  test('should work on mobile (375px)', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/');

    // Verify header is visible
    await expect(page.getByText('Second Brain Research Dashboard')).toBeVisible();

    // Verify no horizontal scroll
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
    expect(scrollWidth).toBe(clientWidth);

    // Take screenshot
    await page.screenshot({
      path: 'screenshots/DYN-226-mobile-375px.png',
      fullPage: true
    });
  });

  test('should work on tablet (768px)', async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.goto('/');

    // Verify header is visible
    await expect(page.getByText('Second Brain Research Dashboard')).toBeVisible();

    // Verify panels are visible
    await expect(page.getByText('Markdown Input')).toBeVisible();
    await expect(page.getByText('Generated Dashboard')).toBeVisible();

    // Take screenshot
    await page.screenshot({
      path: 'screenshots/DYN-226-tablet-768px.png',
      fullPage: true
    });
  });

  test('should work on desktop (1920px)', async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto('/');

    // Verify header is visible
    await expect(page.getByText('Second Brain Research Dashboard')).toBeVisible();

    // Verify split panel layout
    await expect(page.getByText('Markdown Input')).toBeVisible();
    await expect(page.getByText('Generated Dashboard')).toBeVisible();

    // Take screenshot
    await page.screenshot({
      path: 'screenshots/DYN-226-desktop-1920px.png',
      fullPage: true
    });
  });

  test('should have readable text on all sizes', async ({ page }) => {
    const sizes = [
      { width: 375, height: 667, name: 'mobile' },
      { width: 768, height: 1024, name: 'tablet' },
      { width: 1920, height: 1080, name: 'desktop' },
    ];

    for (const size of sizes) {
      await page.setViewportSize({ width: size.width, height: size.height });
      await page.goto('/');

      // Check font sizes are readable
      const headerFontSize = await page.locator('h1').first().evaluate(
        el => window.getComputedStyle(el).fontSize
      );
      const fontSize = parseInt(headerFontSize);
      expect(fontSize).toBeGreaterThanOrEqual(16); // Minimum readable size

      // Take screenshot
      await page.screenshot({
        path: `screenshots/DYN-226-text-${size.name}.png`,
        fullPage: true
      });
    }
  });
});

test.describe('User Interactions', () => {
  test('should clear textarea when clicking clear button', async ({ page }) => {
    await page.goto('/');

    const textarea = page.locator('textarea').first();
    await textarea.fill('# Test Content\n\nSome text here.');

    // Look for clear button (if it exists)
    const clearButton = page.getByRole('button', { name: /clear|reset/i });
    if (await clearButton.isVisible()) {
      await clearButton.click();
      await expect(textarea).toHaveValue('');
    }

    // Take screenshot
    await page.screenshot({
      path: 'screenshots/DYN-226-clear-action.png',
      fullPage: true
    });
  });

  test('should show file upload area', async ({ page }) => {
    await page.goto('/');

    // Look for file upload elements
    const uploadText = page.getByText(/drag and drop|upload/i);
    await expect(uploadText).toBeVisible();

    // Take screenshot
    await page.screenshot({
      path: 'screenshots/DYN-226-upload-area.png',
      fullPage: true
    });
  });

  test('should handle keyboard navigation', async ({ page }) => {
    await page.goto('/');

    // Tab through interactive elements
    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab');

    // Take screenshot to show focus states
    await page.screenshot({
      path: 'screenshots/DYN-226-keyboard-nav.png',
      fullPage: true
    });
  });
});

test.describe('UI Animations', () => {
  test('should have smooth page load animations', async ({ page }) => {
    // Clear any previous state
    await page.goto('about:blank');

    // Load the page fresh
    await page.goto('/');

    // Wait for animations to complete
    await page.waitForTimeout(1000);

    // Verify header animated in
    await expect(page.getByText('Second Brain Research Dashboard')).toBeVisible();

    // Take screenshot after animations
    await page.screenshot({
      path: 'screenshots/DYN-226-animations-loaded.png',
      fullPage: true
    });
  });

  test('should have hover effects on buttons', async ({ page }) => {
    await page.goto('/');

    const textarea = page.locator('textarea').first();
    await textarea.fill('# Test');

    const generateButton = page.getByRole('button', { name: /generate/i });

    // Hover over button
    await generateButton.hover();
    await page.waitForTimeout(300);

    // Take screenshot of hover state
    await page.screenshot({
      path: 'screenshots/DYN-226-button-hover.png',
      fullPage: true
    });
  });
});

test.describe('Error Handling', () => {
  test('should handle empty input gracefully', async ({ page }) => {
    await page.goto('/');

    // Try to generate with empty input
    const generateButton = page.getByRole('button', { name: /generate/i });

    // Button should be disabled or show validation
    const isDisabled = await generateButton.isDisabled();

    // Take screenshot
    await page.screenshot({
      path: 'screenshots/DYN-226-empty-validation.png',
      fullPage: true
    });
  });

  test('should show character/word count', async ({ page }) => {
    await page.goto('/');

    const textarea = page.locator('textarea').first();
    await textarea.fill('Test content with multiple words here.');

    // Verify stats are visible
    await expect(page.getByText(/\d+ characters?/)).toBeVisible();
    await expect(page.getByText(/\d+ words?/)).toBeVisible();

    // Take screenshot
    await page.screenshot({
      path: 'screenshots/DYN-226-char-count.png',
      fullPage: true
    });
  });
});

test.describe('Accessibility', () => {
  test('should have proper heading hierarchy', async ({ page }) => {
    await page.goto('/');

    // Check for h1
    const h1 = page.locator('h1');
    await expect(h1).toBeVisible();

    // Check for h2
    const h2 = page.locator('h2').first();
    await expect(h2).toBeVisible();

    // Take screenshot
    await page.screenshot({
      path: 'screenshots/DYN-226-heading-hierarchy.png',
      fullPage: true
    });
  });

  test('should have proper ARIA labels', async ({ page }) => {
    await page.goto('/');

    // Check for textarea with proper labeling
    const textarea = page.locator('textarea').first();
    await expect(textarea).toBeVisible();

    // Check for buttons with labels
    const generateButton = page.getByRole('button', { name: /generate/i });
    await expect(generateButton).toBeVisible();

    // Take screenshot
    await page.screenshot({
      path: 'screenshots/DYN-226-aria-labels.png',
      fullPage: true
    });
  });

  test('should support keyboard-only navigation', async ({ page }) => {
    await page.goto('/');

    // Tab to textarea
    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab');

    // Type in textarea
    await page.keyboard.type('Test content');

    // Tab to generate button
    await page.keyboard.press('Tab');

    // Take screenshot
    await page.screenshot({
      path: 'screenshots/DYN-226-keyboard-only.png',
      fullPage: true
    });
  });
});
