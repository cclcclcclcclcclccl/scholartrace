import { createRequire } from 'node:module';
import { readFile, writeFile } from 'node:fs/promises';
import assert from 'node:assert/strict';
const { chromium } = createRequire(import.meta.url)('C:/Users/34711/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const round = process.env.SCHOLARTRACE_ROUND || 'v20';
assert(/^v\d+$/.test(round));
const folder = `artifacts/attack-${round}`;
const old = JSON.parse(await readFile(`evaluation/proof_${round}_old/protocol.json`, 'utf8'));
const known = JSON.parse(await readFile(`evaluation/proof_${round}_known/protocol.json`, 'utf8'));
const items = [known.qa.find(c => c.id === 'baseline_only'), old.qa.find(c => c.id === 'clip_pairs'), old.qa.find(c => c.id === 'whisper_segments')];
const browser = await chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, baseURL: 'http://127.0.0.1:8767' });
const report = { notice: 'Actual local model and browser; isolated database. Previously exposed questions, not independent evaluation.', checks: [], errors: [], answers: [] };
page.on('pageerror', error => report.errors.push(String(error)));
try {
  await page.goto('/');
  await page.getByRole('dialog').waitFor();
  await page.keyboard.press('Escape');
  report.checks.push('First-visit tutorial shown and dismissible');
  for (const item of items) {
    await page.getByLabel('筛选文献').fill(item.files[0]);
    await page.locator('.document-item').first().click();
    const pending = page.waitForResponse(r => r.url().endsWith('/api/ask') && r.request().method() === 'POST', { timeout: 300000 });
    await page.getByLabel('研究问题').fill(item.question);
    await page.getByLabel('研究问题').press('Enter');
    const response = await pending;
    assert(response.ok());
    const answer = await response.json();
    report.answers.push({ id: item.id, answer });
    const text = answer.model_answer.map(c => c.text).join(' ');
    for (const pattern of item.required_patterns) assert(new RegExp(pattern, 'i').test(text), pattern + ': ' + text);
    assert(!(answer.subquestions || []).some(p => p.reason?.includes('处理失败')));
    let anchor;
    if (item.id === 'whisper_segments') {
      assert(/语音活动检测|VAD|voice activity detection/i.test(text), 'Training use must appear in answer, not only quotation');
      anchor = answer.model_answer.find(c => /语音活动检测|VAD|voice activity detection/i.test(c.text));
      assert(anchor.page === 2 && /voice activity detection/.test(anchor.support_span));
    } else {
      anchor = answer.model_answer.find(c => /1\.28|128/.test(c.text));
      assert(anchor && /ResNet/.test(anchor.text), 'Baseline entity and sample count required');
      assert(anchor.page === 1 && /1\.28 million/.test(anchor.support_span) && /ResNet-50/.test(anchor.support_span));
    }
    report.checks.push(`${item.id}: Enter submits; requested facts and correct support sentence retained`);
    const saved = await (await page.request.get('/api/artifacts/' + answer.artifact_id)).json();
    assert.deepEqual(saved.content.sections[0].claims, answer.model_answer);
    const exported = await page.request.get('/api/artifacts/' + answer.artifact_id + '/export?format=md');
    assert(exported.ok());
    const markdown = await exported.text();
    for (const claim of answer.model_answer) assert(markdown.includes(claim.text));
    await writeFile(`${folder}/${item.id}-export.md`, markdown);
    report.checks.push(`${item.id}: saved artifact and Markdown preserve exact response and source`);
    if (!await page.getByRole('button', { name: '任务与成果', exact: true }).isVisible()) await page.getByText('更多工具与成果', { exact: true }).click();
    await page.getByRole('button', { name: '任务与成果', exact: true }).click();
    await page.getByRole('button').filter({ hasText: item.question }).first().click();
    const artifact = page.locator('.artifact-result');
    const claim = artifact.locator('.grounded-claim').filter({ hasText: anchor.text }).first();
    await claim.locator('.claim-source summary').click();
    assert.equal(await claim.locator('.claim-source blockquote').innerText(), anchor.quote);
    await artifact.screenshot({ path: `${folder}/${item.id}-desktop.png` });
    await claim.getByRole('button', { name: new RegExp(`第\\s*${anchor.page}\\s*页原文`) }).click();
    assert.equal(await page.getByLabel('当前页码').inputValue(), String(anchor.page));
    await page.getByText('正在呈现原文', { exact: true }).waitFor({ state: 'hidden', timeout: 30000 });
    report.checks.push(`${item.id}: reopened full quote verified; original PDF page rendered`);
  }
  await page.setViewportSize({ width: 390, height: 844 });
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
  await page.screenshot({ path: `${folder}/recovery-mobile.png` });
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
