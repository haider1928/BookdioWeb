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

test.describe('Text Extraction & Translation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await waitForVoices(page);
    
    const voiceSelect = page.locator('#voiceSelect');
    const count = await voiceSelect.locator('option').count();
    if (count > 1) {
      await voiceSelect.selectOption({ index: 1 });
    }
    
    const fileInput = page.locator('#fileInput');
    await fileInput.setInputFiles(TEST_PDF);
    
    await page.locator('#convertBtn').waitFor({ state: 'visible' });
  });

  test('convert button works', async ({ page }) => {
    const convertBtn = page.locator('#convertBtn');
    await convertBtn.click();
    const statusText = page.locator('#statusText');
    await expect(statusText).not.toHaveText('', { timeout: 60000 });
  });
});