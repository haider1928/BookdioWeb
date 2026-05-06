import { test, expect } from '@playwright/test';
import * as path from 'path';

const TEST_PDF = path.join(__dirname, '..', 'testData', 'sample.pdf');

test.describe('PDF Upload', () => {
  test('upload section shows correct UI elements', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('#uploadSection')).toBeVisible();
  });

  test('reject non-PDF files', async ({ page }) => {
    await page.goto('/');
    const input = page.locator('#fileInput');
    
    await input.setInputFiles({
      name: 'sample.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from('Not a PDF')
    });

    await page.waitForTimeout(500);
    const status = page.locator('#uploadStatus');
    const statusText = await status.textContent();
    expect(statusText.toLowerCase()).toContain('pdf');
  });

  test('page range option toggles input fields', async ({ page }) => {
    await page.goto('/');
    const pageRangeCheckbox = page.locator('#usePageRange');
    const pageStart = page.locator('#pageStart');
    const pageEnd = page.locator('#pageEnd');

    await expect(pageStart).toBeDisabled();
    await expect(pageEnd).toBeDisabled();

    await pageRangeCheckbox.check();
    await expect(pageStart).toBeEnabled();
    await expect(pageEnd).toBeEnabled();

    await pageRangeCheckbox.uncheck();
    await expect(pageStart).toBeDisabled();
    await expect(pageEnd).toBeDisabled();
  });

  test('accepts valid PDF file upload', async ({ page }) => {
    await page.goto('/');
    const fileInput = page.locator('#fileInput');
    await fileInput.setInputFiles(TEST_PDF);

    await expect(page.locator('#uploadProgress')).toBeVisible();
    await expect(page.locator('#pageInfo')).not.toBeEmpty();
  });

  test('convert button becomes enabled after upload', async ({ page }) => {
    await page.goto('/');
    const convertBtn = page.locator('#convertBtn');
    await expect(convertBtn).toBeDisabled();

    const fileInput = page.locator('#fileInput');
    await fileInput.setInputFiles(TEST_PDF);

    await expect(convertBtn).toBeEnabled({ timeout: 10000 });
  });
});