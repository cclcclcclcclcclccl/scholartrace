import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { readFile, writeFile } from 'node:fs/promises';
const { chromium } = createRequire(import.meta.url)('C:/Users/34711/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const folder = 'artifacts/page-ocr-20261020';
const base = 'http://127.0.0.1:8767';
const browser = await chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true });
const report = { checks: [], errors: [] };
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true });
  page.on('pageerror', e => report.errors.push(String(e)));
  await page.goto(base);
  await page.getByRole('dialog').waitFor(); await page.keyboard.press('Escape');
  const bytes = await readFile(`${folder}/native-caption-image-body.pdf`);
  await page.locator('input[type=file]').first().setInputFiles({ name: 'Browser per-page OCR.pdf', mimeType: 'application/pdf', buffer: Buffer.concat([bytes, Buffer.from('\n% page-ocr-browser\n')]) });
  await page.getByText('文献已导入', { exact: true }).waitFor();
  const papers = await (await page.request.get(`${base}/api/documents`)).json();
  const doc = papers.find(p => p.name === 'Browser per-page OCR.pdf'); assert.ok(doc);
  const getBlocks = async n => (await page.request.get(`${base}/api/documents/${doc.id}/pages/${n}/blocks`)).json();
  const originals = [await getBlocks(1), await getBlocks(2)];
  await page.getByRole('button', { name: '文献管理', exact: true }).click();
  await page.getByLabel('搜索文献库', { exact: true }).fill('Browser per-page OCR');
  await page.locator(`tr[data-document-id="${doc.id}"]`).getByRole('button', { name: /^管理 / }).click();
  const panel = page.getByRole('region', { name: '逐页文字覆盖检查' });
  await panel.getByText('有文字 2 / 2 页 · 需核对 0 页', { exact: true }).waitFor();
  await panel.getByLabel('显示全部页面').check();
  await panel.getByRole('button', { name: '补充识别第 1 页', exact: true }).waitFor();
  report.checks.push('Native-text-ready pages expose explicit per-page supplement controls');
  const posted = page.waitForRequest(r => r.method() === 'POST' && r.url().endsWith('/api/jobs'));
  await panel.getByRole('button', { name: '补充识别第 1 页', exact: true }).click();
  const request = (await posted).postDataJSON();
  assert.equal(request.payload.page, 1); assert.equal(request.payload.document_id, doc.id);
  await panel.getByText(/本页识别结束：新增 2 行，跳过 1 行重复文字/).waitFor({ timeout: 90000 });
  await panel.getByText(/第 1 页 · 原生 \+ OCR 补充/).waitFor();
  assert.ok(await panel.getByLabel('显示全部页面').isChecked());
  assert.equal(await panel.getByRole('button', { name: '补充识别第 1 页', exact: true }).count(), 0);
  const first = await getBlocks(1);
  assert.deepEqual(first.filter(b => b.method === 'native'), originals[0]);
  assert.deepEqual(await getBlocks(2), originals[1]);
  assert.ok(first.some(b => b.method === 'rapidocr' && b.text.includes('73 samples')));
  report.checks.push('Actual page-one OCR skips duplicate caption, adds two lines, auto-refreshes, and preserves unselected page');
  const down = page.waitForEvent('download');
  await panel.getByRole('button', { name: '导出文字检查' }).click();
  await (await down).saveAs(`${folder}/browser-export.json`);
  const quality = await (await page.request.get(`${base}/api/documents/${doc.id}/text-quality`)).json();
  assert.deepEqual(JSON.parse(await readFile(`${folder}/browser-export.json`, 'utf8')), quality);
  report.checks.push('Export preserves mixed-page state, added OCR confidence and duplicate statistics');
  await panel.getByText('如何使用文字检查', { exact: true }).click();
  await panel.getByText(/勾选“显示全部页面”后点击“补充识别本页”/).waitFor();
  await panel.screenshot({ path: `${folder}/desktop.png` });
  await page.setViewportSize({ width: 390, height: 844 });
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
  await panel.screenshot({ path: `${folder}/mobile.png` });
  report.checks.push('Per-page tutorial visible; 390px layout does not overflow');
  // Deliberately intercept polling only to validate failure feedback, not OCR correctness.
  await page.route('**/api/jobs/*', async route => {
    if (route.request().method() === 'GET' && /\/api\/jobs\/[^/]+$/.test(route.request().url()))
      await route.fulfill({ status: 503, contentType: 'application/json', body: '{}' });
    else await route.continue();
  });
  await panel.getByRole('button', { name: '补充识别第 2 页', exact: true }).click();
  await panel.getByText(/进度读取失败；任务可能仍在执行/).waitFor();
  await page.unroute('**/api/jobs/*');
  report.checks.push('Simulated polling failure clearly says task may continue, without falsely reporting completion');
  // The real submitted page-two job continues despite the injected polling failure.
  for (let i = 0; i < 90; i++) {
    if ((await getBlocks(2)).some(b => b.method === 'rapidocr')) break;
    await page.waitForTimeout(1000);
  }
  assert.ok((await getBlocks(2)).some(b => b.text.includes('74 samples')));
  await panel.getByRole('button', { name: '刷新文字检查' }).click();
  await panel.getByText(/第 2 页 · 原生 \+ OCR 补充/).waitFor();
  report.checks.push('Background page-two OCR continues after polling error; manual refresh recovers final state');
  await panel.getByRole('button', { name: '查看第 2 页原图' }).click();
  const jump = page.getByRole('spinbutton', { name: '当前页码' });
  await jump.waitFor(); assert.equal(await jump.inputValue(), '2');
  await page.waitForFunction(() => document.querySelector('canvas')?.width > 0 && !document.body.innerText.includes('正在呈现原文'));
  report.checks.push('Supplemented page remains linked to original PDF page 2');
  assert.deepEqual(report.errors, []);
  report.document_id = doc.id;
} catch (error) {
  report.failure = String(error.stack || error); process.exitCode = 1;
} finally {
  await writeFile(`${folder}/browser.json`, JSON.stringify(report, null, 2));
  await browser.close();
}
console.log(JSON.stringify(report, null, 2));
