import { createRequire } from 'node:module';
import { readFile, writeFile } from 'node:fs/promises';
import assert from 'node:assert/strict';
const { chromium } = createRequire(import.meta.url)('C:/Users/34711/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const folder = process.env.SCHOLARTRACE_UI_OUTPUT || 'artifacts/attack-v10';
const protocol = JSON.parse(await readFile('evaluation/proof_v10_confirm_known/protocol.json', 'utf8'));
const oldProtocol = JSON.parse(await readFile('evaluation/proof_v10_old/protocol.json', 'utf8'));
protocol.qa.push(oldProtocol.qa.find(c => c.id === 'whisper_segments'));
const browser = await chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, baseURL: 'http://127.0.0.1:8767' });
const report = { notice: 'Real local model and browser, disposable database on 8767; developer checks only.', checks: [], errors: [], answers: [] };
page.on('pageerror', error => report.errors.push(String(error)));
try {
  await page.goto('/');
  await page.getByRole('dialog').waitFor();
  await page.keyboard.press('Escape');
  report.checks.push('First-visit tutorial opens and can be dismissed');
  for (const id of ['runtime_configuration', 'whisper_segments', 'non_speech_role']) {
    const item = protocol.qa.find(c => c.id === id);
    await page.getByLabel('筛选文献').fill(item.files[0]);
    await page.locator('.document-item').first().click();
    const pager = page.getByLabel('当前页码');
    await pager.fill('');
    assert.equal(await pager.inputValue(), '');
    await pager.fill('7');
    await pager.press('Enter');
    assert.equal(await pager.inputValue(), '7');
    const pending = page.waitForResponse(r => r.url().endsWith('/api/ask') && r.request().method() === 'POST', { timeout: 300000 });
    await page.getByLabel('研究问题').fill(item.question);
    await page.getByLabel('研究问题').press('Enter');
    const response = await pending;
    assert(response.ok());
    const answer = await response.json();
    report.answers.push({ id, answer });
    const text = answer.model_answer.map(c => c.text).join(' ');
    assert(answer.model_answer.length > 0);
    assert(!(answer.subquestions || []).some(p => p.reason?.includes('处理失败')));
    // This replay checks the formerly truncated 30-second answer. Completeness
    // remains scored separately against ALL frozen fields in the QA audit.
    const patterns = id === 'whisper_segments' ? ['30', '秒|second'] : item.required_patterns;
    for (const pattern of patterns) assert(new RegExp(pattern, 'i').test(text), pattern + ': ' + text);
    if (id === 'runtime_configuration') assert(answer.model_answer.some(c => c.page === 10));
    const saved = await (await page.request.get('/api/artifacts/' + answer.artifact_id)).json();
    assert.deepEqual(saved.content.sections[0].claims, answer.model_answer);
    const exported = await page.request.get('/api/artifacts/' + answer.artifact_id + '/export?format=md');
    assert(exported.ok());
    const markdown = await exported.text();
    for (const c of answer.model_answer) assert(markdown.includes(c.text));
    await writeFile(`${folder}/${id}-export.md`, markdown);
    report.checks.push(`${id}: Enter submits; ${id === 'whisper_segments' ? '30-second answer completes; full coverage assessed separately' : 'expected fields retained'}; source anchors and saved/exported claims match`);
  }
  report.checks.push('Page input can be emptied, changed to 7 and confirmed');
  const latest = report.answers.at(-1).answer;
  await page.getByText('更多工具与成果', { exact: true }).click();
  await page.getByRole('button', { name: '任务与成果', exact: true }).click();
  await page.getByRole('button').filter({ hasText: protocol.qa.find(c => c.id === 'non_speech_role').question }).first().click();
  const artifact = page.locator('.artifact-result');
  await artifact.locator('.grounded-claim').first().waitFor();
  const labels = await artifact.locator('.grounded-claim > small').allTextContents();
  assert(labels.length > 0 && labels.every(s => !s.includes('前文（仅用于确定指代对象）')));
  assert(labels.some(s => s.includes('这些片段')));
  const original = artifact.locator('.claim-source').first();
  await original.locator('summary').click();
  assert.equal(await original.locator('blockquote').innerText(), latest.model_answer[0].quote);
  await original.locator('summary').click();
  await artifact.locator('.answer-coverage').screenshot({ path: `${folder}/answer-desktop.png` });
  report.checks.push('Reopened artifact uses original user clause, and full source expands without truncation');
  const candidate = artifact.locator('.grounded-claim').first().getByRole('button', { name: /第\s*\d+\s*页原文/ });
  const target = Number((await candidate.innerText()).match(/第\s*(\d+)\s*页/)[1]);
  await candidate.click();
  assert.equal(Number(await page.getByLabel('当前页码').inputValue()), target);
  report.checks.push('Saved answer source button opens the corresponding PDF page');
  await page.setViewportSize({ width: 390, height: 844 });
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
  await page.screenshot({ path: `${folder}/reader-mobile.png` });
  report.checks.push('390px viewport has no whole-page horizontal overflow');
  assert.deepEqual(report.errors, []);
} catch (error) {
  report.failure = String(error);
  await page.screenshot({ path: `${folder}/browser-failure.png` });
  throw error;
} finally {
  await writeFile(`${folder}/browser.json`, JSON.stringify(report, null, 2));
  await browser.close();
  console.log(JSON.stringify({ checks: report.checks, failure: report.failure }));
}
