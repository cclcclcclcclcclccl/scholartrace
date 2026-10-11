import { createRequire } from 'node:module';
import { writeFile } from 'node:fs/promises';
const require = createRequire(import.meta.url);
const { chromium } = require('C:/Users/34711/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const browser = await chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true });
const page = await browser.newPage({ viewport: { width: 1512, height: 1100 } });
const errors = [];
page.on('pageerror', e => errors.push(String(e)));
try {
  await page.goto('http://127.0.0.1:8765', { waitUntil: 'domcontentloaded' });
  await page.getByRole('dialog').getByRole('button', { name: '稍后再看', exact: true }).click();
  await page.locator('.document-item').filter({ hasText: 'Understanding Deep Learning' }).click();
  await page.waitForFunction(() => !document.querySelector('.reader-state') && document.querySelector('canvas')?.width > 200);
  await page.getByRole('spinbutton', { name: '当前页码' }).fill('540');
  await page.getByRole('spinbutton', { name: '当前页码' }).press('Enter');
  await page.waitForFunction(() => document.querySelector('input[aria-label="当前页码"]').value === '540' && !document.querySelector('.reader-state'));
  await page.screenshot({ path: 'artifacts/browser/06-longbook.png', fullPage: true });
  const result = { document: 'UnderstandingDeepLearning_02_09_26_C.pdf', tested_page: 540, total_pages: 541, page_errors: errors, passed: !errors.length };
  await writeFile('artifacts/browser/longbook.json', JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result));
  if (errors.length) process.exitCode = 1;
} finally { await browser.close(); }
