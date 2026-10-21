import { createRequire } from 'node:module';
import { readFile, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import assert from 'node:assert/strict';
const { chromium } = createRequire(import.meta.url)('C:/Users/34711/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const browser = await chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true });
const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
const folder = 'artifacts/attack-v14';
try {
  await page.goto('http://127.0.0.1:8767/');
  await page.getByRole('dialog').waitFor();
  await page.keyboard.press('Escape');
  const protocol = JSON.parse(await readFile('evaluation/proof_v14_old/protocol.json', 'utf8'));
  const doc = protocol.qa.find(c => c.id === 'whisper_segments').sources[0].document_id;
  await page.getByLabel('选择阅读文献', { exact: true }).selectOption(doc);
  await page.getByLabel('当前页码').fill('7');
  await page.getByLabel('当前页码').press('Enter');
  await page.locator('.paper-sheet canvas').waitFor();
  await page.getByText('正在呈现原文', { exact: true }).waitFor({ state: 'hidden', timeout: 30000 });
  assert(await page.locator('.paper-sheet canvas').evaluate(c => c.width > 0 && c.height > 0));
  assert.equal(await page.getByLabel('当前页码').inputValue(), '7');
  await page.screenshot({ path: `${folder}/reader-mobile-rendered.png`, fullPage: true });
  await page.goto(pathToFileURL(resolve('evaluation/reliability/report.html')).href);
  await page.evaluate(() => scrollTo(0, 0));
  await page.screenshot({ path: `${folder}/quality-dashboard-mobile-top.png` });
  await writeFile(`${folder}/read-only-views.json`, JSON.stringify({ pdfPage: 7, renderedCanvas: true, notice: 'Read-only screenshots; no new model queries or saved artifacts.' }, null, 2));
} finally {
  await browser.close();
}
