import { test, expect } from '@playwright/test';

test.describe('Smoke Tests', () => {
  test('should load the application', async ({ page }) => {
    await page.goto('/', { timeout: 60000 });

    // Wait for page to be fully loaded
    await page.waitForLoadState('networkidle');

    // Verify the page title or main heading
    await expect(page.getByText('Second Brain Research Dashboard')).toBeVisible({ timeout: 10000 });

    // Take screenshot
    await page.screenshot({
      path: 'screenshots/DYN-226-smoke-test.png',
      fullPage: true
    });
  });

  test('should have responsive header', async ({ page }) => {
    await page.goto('/', { timeout: 60000 });
    await page.waitForLoadState('networkidle');

    // Verify header elements
    await expect(page.getByText('Second Brain Research Dashboard')).toBeVisible();
    await expect(page.getByText('Transform your markdown research')).toBeVisible();

    // Take screenshot
    await page.screenshot({
      path: 'screenshots/DYN-226-header.png',
      fullPage: true
    });
  });

  test('should have input panel', async ({ page }) => {
    await page.goto('/', { timeout: 60000 });
    await page.waitForLoadState('networkidle');

    // Verify input section
    await expect(page.getByText('Markdown Input')).toBeVisible();
    await expect(page.locator('textarea').first()).toBeVisible();

    // Take screenshot
    await page.screenshot({
      path: 'screenshots/DYN-226-input-panel.png',
      fullPage: true
    });
  });

  test('should have dashboard panel', async ({ page }) => {
    await page.goto('/', { timeout: 60000 });
    await page.waitForLoadState('networkidle');

    // Verify dashboard section (use heading role to avoid strict mode violation)
    await expect(page.getByRole('heading', { name: 'Generated Dashboard' })).toBeVisible();
    await expect(page.getByText('No Dashboard Yet')).toBeVisible();

    // Take screenshot
    await page.screenshot({
      path: 'screenshots/DYN-226-dashboard-panel.png',
      fullPage: true
    });
  });
});
