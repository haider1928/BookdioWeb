import { test, expect } from '@playwright/test';

test.describe('Video Generation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(3000);
  });

  test('style presets are visible', async ({ page }) => {
    await expect(page.locator('.style-btn[data-style="spotify"]')).toBeVisible();
    await expect(page.locator('.style-btn[data-style="classic"]')).toBeVisible();
    await expect(page.locator('.style-btn[data-style="neon"]')).toBeVisible();
    await expect(page.locator('.style-btn[data-style="minimal"]')).toBeVisible();
    await expect(page.locator('.style-btn[data-style="block"]')).toBeVisible();
  });

  test('style presets are clickable', async ({ page }) => {
    const spotifyBtn = page.locator('.style-btn[data-style="spotify"]');
    await spotifyBtn.click();
    await expect(spotifyBtn).toHaveClass(/active/);
  });

  test('custom style options exist in DOM', async ({ page }) => {
    const bgColorPicker = page.locator('#bgColorPicker');
    await expect(bgColorPicker).toBeAttached();
  });

  test('layout options exist in DOM', async ({ page }) => {
    const layoutSelect = page.locator('#layoutSelect');
    await expect(layoutSelect).toBeAttached();
  });

  test('word highlight checkbox exists in DOM', async ({ page }) => {
    const wordHighlightCheckbox = page.locator('#wordHighlightCheckbox');
    await expect(wordHighlightCheckbox).toBeAttached();
    await expect(wordHighlightCheckbox).toBeChecked();
  });
});