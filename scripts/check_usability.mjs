import { createRequire } from 'node:module';
import { mkdir, writeFile } from 'node:fs/promises';
import assert from 'node:assert/strict';
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.CODEX_BROWSER_MODULE || 'C:/Users/34711/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const browser = await chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true });
const context = await browser.newContext({ viewport: { width: 1512, height: 1100 } });
const page = await context.newPage();
const errors = [];
page.on('pageerror', error => errors.push(String(error)));
const result = {};
await mkdir('artifacts/usability', { recursive: true });
const ready = () => page.waitForFunction(() => {
  const stage = document.querySelector('.paper-stage');
  const canvas = stage?.querySelector('canvas');
  const signature = [canvas?.width, canvas?.height, stage?.getAttribute('aria-busy'), stage?.querySelector('.textLayer')?.textContent].join(':');
  const old = window.__stableReader;
  window.__stableReader = { signature, frames: old?.signature === signature ? old.frames + 1 : 0 };
  return canvas?.width > 200 && stage?.getAttribute('aria-busy') === 'false' && window.__stableReader.frames >= 4;
});
const jumpInput = () => page.getByRole('spinbutton', { name: '当前页码' });
const keyboardReplace = async value => { await jumpInput().focus(); await jumpInput().press('Control+a'); await jumpInput().press('Backspace'); assert.equal(await jumpInput().inputValue(), ''); if (value) await jumpInput().pressSequentially(value); };
const helpDialog = () => page.getByRole('dialog');
try {
  await page.goto('http://127.0.0.1:8765');
  await helpDialog().waitFor();
  await page.getByRole('heading', { name: '让论文里的依据，跟得上你的研究。' }).waitFor();
  await page.screenshot({ path: 'artifacts/usability/01-first-visit.png', fullPage: true });
  // Native modal keeps tab focus inside, including at either end of the controls.
  for (let i = 0; i < 20; i++) {
    await page.keyboard.press('Tab');
    assert.ok(await page.evaluate(() => !!document.activeElement?.closest('dialog')), 'Focus escaped tutorial');
  }
  for (let i = 0; i < 3; i++) await helpDialog().getByRole('button', { name: '下一步', exact: true }).click();
  await page.getByRole('heading', { name: '论文更新后，你之前记下的话还适用吗？' }).waitFor();
  assert.ok((await helpDialog().textContent()).includes('代码将于近期公开'));
  await page.screenshot({ path: 'artifacts/usability/02-version-guide.png', fullPage: true });
  await helpDialog().getByRole('button', { name: '开始使用', exact: true }).click();
  await ready();
  await page.reload(); await ready();
  assert.equal(await helpDialog().count(), 0, 'Tutorial repeated after completion');
  result.first_visit_tutorial_and_persistence = true;
  await page.getByRole('button', { name: '使用教程', exact: true }).click();
  await helpDialog().waitFor();
  await page.keyboard.press('Escape');
  assert.equal(await helpDialog().count(), 0);
  assert.ok(await page.getByRole('button', { name: '使用教程', exact: true }).evaluate(el => el === document.activeElement));
  result.reopen_escape_and_focus_restore = true;

  // Reproduce the actual reported keystrokes, not Playwright's fill shortcut.
  await page.getByRole('textbox', { name: '筛选文献' }).fill('1706.03762v1.pdf');
  await page.locator('.document-item').first().click(); await ready();
  await keyboardReplace('1'); await jumpInput().press('Enter'); await ready();
  for (const target of [7, 6, 8, 9]) {
    const previousText = await page.locator('.textLayer').textContent();
    await keyboardReplace(String(target));
    // The draft must not trigger premature rendering.
    assert.equal(await page.locator('.textLayer').textContent(), previousText);
    await jumpInput().press('Enter'); await ready();
    assert.equal(await jumpInput().inputValue(), String(target));
    assert.notEqual(await page.locator('.textLayer').textContent(), previousText);
  }
  await keyboardReplace('7'); await page.getByRole('button', { name: '跳转', exact: true }).click(); await ready();
  assert.ok((await page.locator('.textLayer').textContent()).includes('P100'));
  await keyboardReplace('8'); await page.getByRole('textbox', { name: '研究问题' }).click(); await ready();
  assert.equal(await jumpInput().inputValue(), '8');
  await keyboardReplace(''); await page.getByRole('textbox', { name: '研究问题' }).click();
  assert.equal(await jumpInput().inputValue(), '8');
  await keyboardReplace('3'); await jumpInput().press('Escape');
  assert.equal(await jumpInput().inputValue(), '8');
  for (const value of ['0', '16', '1.5', 'abc']) {
    await keyboardReplace(value); await jumpInput().press('Enter');
    assert.equal(await jumpInput().inputValue(), '8');
    await page.getByRole('alert').filter({ hasText: '整数页码' }).waitFor();
  }
  result.page_deletion_6_to_9_enter_click_blur_escape_and_validation = true;
  await page.getByRole('textbox', { name: '筛选文献' }).fill('UnderstandingDeepLearning');
  await page.locator('.document-item').first().click(); await ready();
  await keyboardReplace('540'); await jumpInput().press('Enter'); await ready();
  await page.reload(); await ready();
  assert.equal(await jumpInput().inputValue(), '540');
  result.longbook_multi_digit_page_restores_after_reload = true;
  await page.getByRole('textbox', { name: '筛选文献' }).fill('1706.03762v1.pdf');
  await page.locator('.document-item').first().click(); await ready();

  const question = page.getByRole('textbox', { name: '研究问题' });
  const submitted = [];
  page.on('request', request => { if (new URL(request.url()).pathname === '/api/ask') submitted.push(request.postDataJSON()); });
  await page.waitForFunction(() => document.querySelector('.model-state')?.textContent.includes('已连接'));
  // One real model call validates the default Enter path through the actual server.
  await question.fill('训练用了哪些 GPU？'); await question.press('Enter');
  await page.locator('.claim-quote').first().waitFor({ timeout: 120000 });
  assert.equal(submitted.length, 1);
  assert.ok((await page.locator('.claim-quote').first().textContent()).includes('P100'));
  result.enter_sends_real_question = true;
  await page.screenshot({ path: 'artifacts/usability/03-reader-controls.png', fullPage: true });
  // Subsequent shortcut checks stub inference to isolate keyboard behavior and avoid GPU churn.
  await page.route('**/api/ask', route => route.fulfill({ json: { evidence: [], message: '键盘交互测试', mode: 'evidence_only', model_answer: null } }));
  await question.fill('第一行'); await question.press('Shift+Enter'); await question.pressSequentially('second');
  assert.equal(await question.inputValue(), '第一行\nsecond'); assert.equal(submitted.length, 1);
  await question.fill(''); await question.press('Enter'); assert.equal(submitted.length, 1);
  await question.fill('中文选词测试');
  await question.dispatchEvent('compositionstart');
  await question.dispatchEvent('keydown', { key: 'Enter', code: 'Enter', keyCode: 229, isComposing: true, bubbles: true });
  await question.dispatchEvent('compositionend', { data: '测试' });
  assert.equal(submitted.length, 1, 'Chinese composition accidentally sent a question');
  result.shift_enter_blank_and_ime_protection = true;
  await page.getByRole('combobox', { name: '回车键行为' }).selectOption('newline');
  await question.fill('第一行'); await question.press('Enter'); await question.pressSequentially('second');
  assert.equal(await question.inputValue(), '第一行\nsecond'); assert.equal(submitted.length, 1);
  await question.press('Control+Enter');
  await page.waitForFunction(() => document.querySelector('.result-note')?.textContent === '键盘交互测试');
  assert.equal(submitted.length, 2);
  await page.reload(); await ready();
  assert.equal(await page.getByRole('combobox', { name: '回车键行为' }).inputValue(), 'newline');
  result.enter_newline_ctrl_enter_and_saved_preference = true;
  await page.getByRole('combobox', { name: '回车键行为' }).selectOption('send');
  let finishRequest;
  const pending = new Promise(resolve => { finishRequest = resolve; });
  await page.unroute('**/api/ask');
  await page.route('**/api/ask', async route => { await pending; await route.fulfill({ json: { evidence: [], message: '结束等待', mode: 'evidence_only', model_answer: null } }); });
  await question.fill('只提交一次'); await question.press('Enter');
  await page.getByRole('button', { name: '停止等待', exact: true }).waitFor();
  await question.press('Enter'); await question.press('Enter');
  assert.equal(submitted.length, 3);
  finishRequest(); await page.getByRole('button', { name: '停止等待', exact: true }).waitFor({ state: 'hidden' });
  result.busy_does_not_duplicate_question = true;

  // Every currently available module has a nearby, functional help entry.
  await question.fill('帮助关闭后保留我的问题');
  for (const name of ['文献库使用说明', '文献阅读台使用说明', '与证据对话使用说明']) {
    await page.getByRole('button', { name, exact: true }).click();
    await helpDialog().waitFor();
    assert.ok((await helpDialog().textContent()).includes('功能与使用要点'));
    await helpDialog().getByRole('button', { name: '我知道了', exact: true }).click();
  }
  assert.equal(await question.inputValue(), '帮助关闭后保留我的问题');
  for (const [view, helpName] of [['证据笔记', '证据笔记使用说明'], ['版本复核', '版本复核使用说明']]) {
    await page.locator('.nav-list').getByRole('button', { name: view }).click();
    await page.getByRole('button', { name: helpName, exact: true }).click(); await helpDialog().waitFor();
    if (view === '版本复核') await page.getByRole('heading', { name: '用已有样例，第一次就能看懂' }).waitFor();
    await page.keyboard.press('Escape');
  }
  result.all_five_module_help_entries = true;
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('button', { name: '版本复核使用说明', exact: true }).click();
  await helpDialog().waitFor();
  const geometry = await helpDialog().evaluate(dialog => {
    const bounds = dialog.getBoundingClientRect();
    return { fits: bounds.left >= 0 && bounds.right <= innerWidth && bounds.top >= 0 && bounds.bottom <= innerHeight, overflows: dialog.scrollWidth > dialog.clientWidth + 1 };
  });
  assert.equal(geometry.fits, true); assert.equal(geometry.overflows, false);
  await page.screenshot({ path: 'artifacts/usability/04-mobile-guide.png', fullPage: true });
  await helpDialog().getByRole('button', { name: '我知道了', exact: true }).click();
  await page.locator('.nav-list').getByRole('button', { name: '文献阅读台' }).click(); await ready();
  await keyboardReplace('7'); await jumpInput().press('Enter'); await ready();
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 2), false);
  await page.screenshot({ path: 'artifacts/usability/05-mobile-reader.png', fullPage: true });
  result.mobile_dialog_and_reader_fit = true;
  assert.deepEqual(errors, []);
  result.passed = true;
} catch (error) { result.failure = String(error); await page.screenshot({ path: 'artifacts/usability/failure.png', fullPage: true }); throw error; }
finally { await writeFile('artifacts/usability/results.json', JSON.stringify({ ...result, page_errors: errors }, null, 2)); await browser.close(); }
console.log(JSON.stringify(result, null, 2));
