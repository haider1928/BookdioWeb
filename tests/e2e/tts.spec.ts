import { test, expect } from '@playwright/test';
import * as path from 'path';

const TEST_PDF = path.join(__dirname, '..', 'testData', 'sample.pdf');

async function waitForVoices(page) {
  await page.waitForTimeout(3000);
  await page.waitForFunction(() => {
    const select = document.getElementById('voiceSelect');
    return select && select.options && select.options.length > 1;
  }, { timeout: 10000 }).catch(() => {});
}

test.describe('Text-to-Speech (TTS)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await waitForVoices(page);
  });

  test('voice selection dropdown has multiple voices', async ({ page }) => {
    const voiceSelect = page.locator('#voiceSelect');
    const options = voiceSelect.locator('option');
    const count = await options.count();
    expect(count).toBeGreaterThan(1);
  });

  test('preview voice button works', async ({ page }) => {
    const voiceSelect = page.locator('#voiceSelect');
    const count = await voiceSelect.locator('option').count();
    
    if (count > 1) {
      await voiceSelect.selectOption({ index: 1 });
      const previewBtn = page.locator('#previewVoiceBtn');
      await previewBtn.click();
      const previewAudio = page.locator('#voicePreviewAudio');
      await expect(previewAudio).toBeAttached();
    }
  });

  test('speed control adjusts TTS speed', async ({ page }) => {
    const speedRange = page.locator('#speedRange');
    const speedVal = page.locator('#speedVal');
    
    await speedRange.fill('25');
    await expect(speedVal).toContainText('+25%');
    
    await speedRange.fill('-25');
    await expect(speedVal).toContainText('-25%');
  });

  test('convert button disabled before PDF upload', async ({ page }) => {
    const convertBtn = page.locator('#convertBtn');
    await expect(convertBtn).toBeDisabled();
  });

  test('conversion starts when clicking convert', async ({ page }) => {
    const voiceSelect = page.locator('#voiceSelect');
    await voiceSelect.selectOption({ index: 1 });
    
    const fileInput = page.locator('#fileInput');
    await fileInput.setInputFiles(TEST_PDF);
    
    const convertBtn = page.locator('#convertBtn');
    await expect(convertBtn).toBeEnabled({ timeout: 10000 });
    await convertBtn.click();

    const playerSection = page.locator('#playerSection');
    await expect(playerSection).not.toHaveClass(/hidden/, { timeout: 60000 });
  });
});