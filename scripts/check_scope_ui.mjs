import { createRequire } from 'node:module';
import { readFile, writeFile } from 'node:fs/promises';
import assert from 'node:assert/strict';
const { chromium } = createRequire(import.meta.url)('C:/Users/34711/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const folder = 'artifacts/attack-v15';
const protocol = JSON.parse(await readFile('evaluation/proof_v15_transfer/protocol.json', 'utf8'));
const browser = await chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, baseURL: 'http://127.0.0.1:8767' });
const report = { notice: 'Actual local model and browser; disposable database. No independent evaluation.', checks: [], errors: [], answers: [] };
page.on('pageerror', error => report.errors.push(String(error)));
try {
  await page.goto('/');
  await page.getByRole('dialog').waitFor();
  await page.keyboard.press('Escape');
  report.checks.push('First-visit tutorial remains available');
  for (const id of ['transfer_llama_context', 'transfer_flash_variants']) {
    const item = protocol.qa.find(c => c.id === id);
    await page.getByLabel('筛选文献').fill(item.files[0]);
    await page.locator('.document-item').first().click();
    const pending = page.waitForResponse(r => r.url().endsWith('/api/ask') && r.request().method() === 'POST', { timeout: 300000 });
    await page.getByLabel('研究问题').fill(item.question);
    await page.getByLabel('研究问题').press('Enter');
    const response = await pending;
    assert(response.ok());
    const answer = await response.json();
    report.answers.push({ id, answer });
    const text = answer.model_answer.map(c => c.text).join(' ');
    for (const pattern of item.required_patterns) assert(new RegExp(pattern, 'i').test(text), pattern + ': ' + text);
    assert(!(answer.subquestions || []).some(p => p.reason?.includes('处理失败')));
    assert.equal(answer.subquestions.length, 2);
    if (id === 'transfer_llama_context') {
      assert(answer.model_answer.some(c => /150/.test(c.text) && c.page === 47));
      assert(answer.subquestions[1].question.startsWith('比较两种窗口'));
    } else {
      assert(!answer.model_answer.some(c => /所有序列|速度|更快/.test(c.text)));
      assert(answer.subquestions[1].question.includes('请区分两者'));
    }
    report.checks.push(`${id}: Enter submits; requested facts and original two-clause structure retained`);
    const saved = await (await page.request.get('/api/artifacts/' + answer.artifact_id)).json();
    assert.deepEqual(saved.content.sections[0].claims, answer.model_answer);
    const exported = await page.request.get('/api/artifacts/' + answer.artifact_id + '/export?format=md');
    assert(exported.ok());
    const markdown = await exported.text();
    for (const c of answer.model_answer) assert(markdown.includes(c.text));
    await writeFile(`${folder}/${id}-export.md`, markdown);
    report.checks.push(`${id}: saved and exported claims match actual response`);
  }
  const answer = report.answers[0].answer;
  await page.getByText('更多工具与成果', { exact: true }).click();
  await page.getByRole('button', { name: '任务与成果', exact: true }).click();
  await page.getByRole('button').filter({ hasText: protocol.qa[1].question }).first().click();
  const artifact = page.locator('.artifact-result');
  await artifact.locator('.grounded-claim').first().waitFor();
  const labels = await artifact.locator('.grounded-claim > small').allTextContents();
  assert(labels.some(s => s.includes('比较两种窗口')));
  assert(labels.every(s => !s.includes('前文（仅用于确定指代对象）')));
  const source = artifact.locator('.claim-source').first();
  await source.locator('summary').click();
  assert.equal(await source.locator('blockquote').innerText(), answer.model_answer[0].quote);
  await artifact.screenshot({ path: `${folder}/scope-answer-desktop.png` });
  report.checks.push('Saved comparison answer retains original clauses and exact expandable full quote');
  await artifact.locator('.grounded-claim').first().getByRole('button', { name: /第\s*47\s*页原文/ }).click();
  assert.equal(await page.getByLabel('当前页码').inputValue(), '47');
  await page.getByText('正在呈现原文', { exact: true }).waitFor({ state: 'hidden', timeout: 30000 });
  report.checks.push('Saved controlled-comparison citation opens and renders PDF page 47');
  await page.setViewportSize({ width: 390, height: 844 });
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
  await page.screenshot({ path: `${folder}/scope-reader-mobile.png` });
  report.checks.push('390px viewport has no whole-page horizontal overflow');
  assert.deepEqual(report.errors, []);
} catch (error) {
  report.failure = String(error);
  await page.screenshot({ path: `${folder}/browser-failure.png` });
  throw error;
} finally {
  await writeFile(`${folder}/browser.json`, JSON.stringify(report, null, 2));
  await browser.close();
  console.log(JSON.stringify({ checks: report.checks, failure: report.failure, errors: report.errors }));
}
