import { createRequire } from 'node:module';
import { readFile, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import assert from 'node:assert/strict';
const { chromium } = createRequire(import.meta.url)('C:/Users/34711/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const folder = 'artifacts/attack-v14/diagrams';
const run = JSON.parse(await readFile(`${folder}/run.json`, 'utf8'));
assert(run.complete);
const browser = await chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true });
const page = await browser.newPage({ viewport: { width: 1400, height: 950 } });
const report = { checks: [], errors: [] };
page.on('pageerror', e => report.errors.push(String(e)));
try {
  await page.setContent('<html lang="zh-CN"><meta charset="utf-8"><style>body{font-family:system-ui,"Microsoft YaHei",sans-serif;margin:32px;color:#193033}h1{font-size:24px}#diagram{padding:24px;border:1px solid #ccd8d2;border-radius:12px}svg{max-width:100%;height:auto}</style><h1>研证 · 流程图回归</h1><p id="goal"></p><div id="diagram"></div></html>');
  await page.addScriptTag({ path: resolve('frontend/node_modules/mermaid/dist/mermaid.min.js') });
  for (const row of run.cases) {
    assert(!row.error && row.result.code);
    const svg = await page.evaluate(async ({ code, goal, id }) => {
      mermaid.initialize({ startOnLoad: false, securityLevel: 'strict', theme: 'neutral', maxTextSize: 12000 });
      await mermaid.parse(code);
      const result = await mermaid.render(`diagram-${id}`, code);
      document.getElementById('goal').textContent = goal;
      document.getElementById('diagram').innerHTML = result.svg;
      return result.svg;
    }, { code: row.result.code, goal: row.topic, id: row.id });
    assert(await page.locator('#diagram svg').count() === 1);
    await writeFile(`${folder}/${row.id}.svg`, svg);
    await page.screenshot({ path: `${folder}/${row.id}.png`, fullPage: true });
    report.checks.push(`${row.id}: actual generated Mermaid parses and renders with product settings`);
  }
  assert.deepEqual(report.errors, []);
} catch (e) {
  report.failure = String(e);
  throw e;
} finally {
  await writeFile(`${folder}/render.json`, JSON.stringify(report, null, 2));
  await browser.close();
  console.log(JSON.stringify(report));
}
