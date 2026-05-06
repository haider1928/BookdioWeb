import { test, expect } from '@playwright/test';

test.describe('Subtitles (VTT)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(3000);
  });

  test('player section is hidden initially', async ({ page }) => {
    const playerSection = page.locator('#playerSection');
    await expect(playerSection).toHaveClass(/hidden/);
  });

  test('karaoke panel element exists in DOM', async ({ page }) => {
    const karaokePanel = page.locator('#karaokePanel');
    await expect(karaokePanel).toBeAttached();
  });

  test('audio player element exists', async ({ page }) => {
    const audioPlayer = page.locator('#audioPlayer');
    await expect(audioPlayer).toBeAttached();
  });
});